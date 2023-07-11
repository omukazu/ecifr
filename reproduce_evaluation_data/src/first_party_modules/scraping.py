from collections import defaultdict
from copy import deepcopy
from itertools import chain
from pathlib import Path
from typing import Union

from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams, LTAnno, LTChar, LTContainer, LTCurve, LTTextLine
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser


class Page:
    def __init__(self, page: PDFPage, layout) -> None:
        _, _, width, height = page.mediabox
        self.width = width
        self.height = height

        text_lines = self.extract_text_lines(layout)
        self.text_lines = self.aggregate_text_lines(text_lines)
        rects = self.extract_rects(layout)
        self.boxes = self.aggregate_rects(rects)

        self.update_text_lines()
        self.text = "".join(text_line["text"] for text_line in self.text_lines)

    def extract_text_lines(self, layout) -> list[LTTextLine]:
        if isinstance(layout, LTTextLine):
            return [layout]
        elif isinstance(layout, LTContainer):
            instances = []
            for child in layout:
                instances.extend(self.extract_text_lines(child))
            return instances
        return []

    def aggregate_text_lines(self, text_lines: list[LTTextLine]) -> list[dict[str, Union[str, list[LTChar], bool]]]:
        y2text_lines, prev = defaultdict(list), 1000000
        for text_line in sorted(text_lines, key=lambda x: -x.y0):
            y = round(-text_line.y0)
            # y軸上でoverlapしていたらまとめる
            if abs(prev - y) <= text_line.height / 4:
                popped = y2text_lines.pop(prev)
                y2text_lines[y].extend(popped)
            y2text_lines[y].append(text_line)
            prev = y

        aggregated = []
        for clustered_text_lines in y2text_lines.values():
            chars = [char for char in chain.from_iterable(clustered_text_lines) if self.valid(char)]
            x2char, prev = {}, 1000000
            for char in sorted(chars, key=lambda x: x.x0):
                x0 = round(char.x0)
                # x軸上でoverlapしていたら無視
                if abs(prev - x0) <= char.width / 4:
                    char = x2char.pop(prev)
                x2char[x0] = char
                prev = x0
            chars = [*x2char.values()]
            if len(chars) >= 1:
                aggregated.append(
                    {
                        "text": "".join(char.get_text().strip() for char in chars),
                        "chars": chars,
                    }
                )
        return aggregated

    @staticmethod
    def valid(char: Union[LTChar, LTAnno]) -> bool:
        return isinstance(char, LTChar) and len(char.get_text().strip()) == 1 and char.x0 >= 0.0 and char.y0 >= 0.0

    def extract_rects(self, layout) -> list[tuple[int, int, int, int]]:
        if isinstance(layout, LTCurve):
            try:
                rect = self.curve2rect(layout)
                if rect[2] - rect[0] < self.width * 5 / 6 or rect[3] - rect[1] < self.height * 5 / 6:
                    return [rect]
            except IndexError:
                pass
        elif isinstance(layout, LTContainer):
            instances = []
            for child in layout:
                instances.extend(self.extract_rects(child))
            return instances
        return []

    @staticmethod
    def curve2rect(curve: LTCurve) -> tuple[int, int, int, int]:
        if type(curve) == LTCurve:
            xs, ys = zip(*curve.pts)
            return round(min(xs)), round(min(ys)), round(max(xs)), round(max(ys))
        else:
            return round(curve.x0), round(curve.y0), round(curve.x1), round(curve.y1)

    @staticmethod
    def aggregate_rects(rects: list[tuple[int, int, int, int]]) -> list[tuple[int, int, int, int]]:
        y2xs = defaultdict(set)
        for x0, y0, x1, y1 in rects:
            for y in range(y0, y1 + 1):
                y2xs[y] |= {x0, x1}

        boxes = []  # bounding
        for rect in rects:
            x0, y0, x1, y1 = rect
            if len(y2xs[round((y0 + y1) / 2)]) <= 2:
                continue
            boxes.append(rect)
            overlapped = [
                box for box in boxes if max(x0, box[0]) <= min(x1, box[2]) and max(y0, box[1]) <= min(y1, box[3])
            ]
            boxes = [box for box in boxes if box not in overlapped]
            x0s, y0s, x1s, y1s = zip(*overlapped)
            boxes.append((min(x0s), min(y0s), max(x1s), max(y1s)))
        return boxes

    def update_text_lines(self) -> None:
        for i, text_line in enumerate(self.text_lines):
            min_x0 = round(min(char.x0 for char in text_line["chars"]))
            min_y0 = round(min(char.y0 for char in text_line["chars"]))
            max_x1 = round(max(char.x1 for char in text_line["chars"]))
            max_y1 = round(max(char.y1 for char in text_line["chars"]))
            exclude = any(
                x0 - 1 <= min_x0 and max_x1 <= x1 + 1 and y0 - 1 <= min_y0 and max_y1 <= y1 + 1
                for x0, y0, x1, y1 in self.boxes
            )
            # max_width = max(char.width for char in text_line['chars'])
            # exclude |= any(
            #     # 同一行内で文字同士が離れている = 本文でない可能性が高い
            #     char2.x0 - char1.x1 >= max_width * 2.25
            #     for char1, char2 in zip(text_line['chars'], text_line['chars'][1:] + text_line['chars'][:1])
            # )
            if i == 0:
                # ヘッダー
                exclude |= max_y1 >= self.height * 0.95
            elif i + 1 == len(self.text_lines):
                # フッター
                exclude |= min_y0 <= self.height * 0.05
            text_line["exclude"] = exclude

            text_line["line_break"] = round(text_line["chars"][-1].x1) < self.width * 5 / 6 and i + 1 != len(
                self.text_lines
            )


def extract_pages(path: Path) -> list[Page]:
    pages = []
    with path.open(mode="rb") as f:
        pdf_parser = PDFParser(f)
        pdf_document = PDFDocument(pdf_parser)
        pdf_resource_manager = PDFResourceManager()
        pdf_page_aggregator = PDFPageAggregator(pdf_resource_manager, laparams=LAParams(all_texts=True))
        pdf_page_interpreter = PDFPageInterpreter(pdf_resource_manager, pdf_page_aggregator)
        for page in PDFPage.create_pages(pdf_document):
            pdf_page_interpreter.process_page(page)
            layout = pdf_page_aggregator.get_result()
            pages.append(Page(page, layout))
    return pages


def get_qualitative_information(pages: list[Page]):
    toc_idx = 1
    for idx, page in enumerate(pages):
        if "目次" in page.text:
            toc_idx = idx
            break

    sections = {
        "precede": pages[: toc_idx + 1],
        "qualitative_information": pages[toc_idx + 1 :],
        "succeed": [],
    }

    pages = pages[toc_idx + 1 :]

    flag = False
    for idx, page in enumerate(pages):
        if flag:
            break

        # 財政状態: に関する説明, の概況, に関する定性的情報, の分析, に関する概況, に関する分析
        # 将来予測情報: に関する説明 / 業績予想: に関する説明, に関する定性的情報 / 今後の見通し, 次期の見通し
        for query in [
            "財政状態に関する",
            "財政状態の",
            "将来予測情報に関する",
            "業績予想に関する",
            "今後の見通し",
        ]:
            if (char_idx := page.text.find(query)) >= 0:
                if idx == 0:
                    if char_idx > 150:  # 3行
                        flag = True
                    # （１）当四半期決算の経営成績・財政状態の概況 パターン
                    elif (appendix := page.text[char_idx + len(query) :].find(query)) >= 0:
                        char_idx = char_idx + len(query) + appendix
                        flag = True
                else:
                    flag = True

                if flag:
                    sub_page = deepcopy(page)
                    page.text = page.text[:char_idx]
                    sub_page.text = sub_page.text[char_idx:]
                    char_idx2text_line_idx = [
                        text_line_idx
                        for text_line_idx, text_line in enumerate(page.text_lines)
                        for _ in text_line["text"]
                    ]
                    text_line_idx = char_idx2text_line_idx[char_idx]
                    page.text_lines = page.text_lines[:text_line_idx]
                    sub_page.text_lines = sub_page.text_lines[text_line_idx:]
                    sections["qualitative_information"] = pages[:idx] + [page]
                    sections["succeed"] = [sub_page] + pages[idx + 1 :]
                    break

    return sections


def get_text(pages: list[Page], line_break: bool = True) -> str:
    return "".join(
        text_line["text"] + "　" * int(line_break and text_line["line_break"])
        for page in pages
        for text_line in page.text_lines
        if not text_line["exclude"]
    )
