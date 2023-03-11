import json
from argparse import ArgumentParser
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd


@dataclass
class Example:
    doc_id: str
    stock_code: str
    sentence: str
    label: str
    prime: str
    polarity: str


def split_documents(master_df: pd.DataFrame) -> tuple[list[str], list[str]]:
    dev_doc_ids, test_doc_ids = [], []
    ctr = defaultdict(lambda: defaultdict(int))
    for _, group in master_df.groupby("industry"):
        value_counts = group["polarity"].value_counts()
        try:
            pos = round(value_counts["増"] * 0.8)
        except KeyError:
            pos = 0
        try:
            neg = round(value_counts["減"] * 0.8)
        except KeyError:
            neg = 0
        assert pos + neg == 8

        monitor = defaultdict(int)
        for idx, row in group.iterrows():
            doc_id, polarity = row["basename"], row["polarity"]
            if polarity == "増":
                if monitor[polarity] < pos:
                    test_doc_ids.append(doc_id)
                    ctr["test"][polarity] += 1
                else:
                    dev_doc_ids.append(doc_id)
                    ctr["dev"][polarity] += 1
            elif polarity == "減":
                if monitor[polarity] < neg:
                    test_doc_ids.append(doc_id)
                    ctr["test"][polarity] += 1
                else:
                    dev_doc_ids.append(doc_id)
                    ctr["dev"][polarity] += 1
            else:
                raise ValueError
            monitor[polarity] += 1

    print(ctr)
    return dev_doc_ids, test_doc_ids


def get_dev_and_test_splits(
    annotated_df: pd.DataFrame,
    doc_id2stock_code: dict[str, str],
    dev_doc_ids: list[str],
) -> tuple[list[Example], list[Example]]:
    dev, test = [], []
    causality_map = {"業績": "負例", "暗黙的な業績要因": "正例", "明示的な業績要因": "正例", "": "負例"}
    polarity_map = {"++": "+", "+": "+", "+-": "?", "-": "-", "--": "-", "": ""}
    for (
        doc_id,
        target,
        label1,
        label2,
        label3,
        label4,
        prime,
        polarity,
        sentence,
    ) in annotated_df.values:
        if target in {"target", "0"}:
            continue

        sentence = sentence.translate(str.maketrans("*+", "＊＋"))

        majority, num_votes = Counter([label1, label2, label3, label4]).most_common()[0]
        label = majority if num_votes >= 3 else ""

        example = Example(
            doc_id=doc_id,
            stock_code=doc_id2stock_code[doc_id + ".pdf"],
            sentence=sentence,
            label=causality_map[label],
            prime=prime,
            polarity=polarity_map[polarity],
        )
        switch = dev if doc_id + ".pdf" in dev_doc_ids else test
        switch.append(example)
    return dev, test


def main():
    parser = ArgumentParser()
    parser.add_argument("ANNOTATED_DATA", type=str, help="path to annotated_data.tsv")
    parser.add_argument("MASTER_DATA", type=str, help="path to master_data.csv")
    parser.add_argument("OUT_DIR", help="path to output dir")
    args = parser.parse_args()

    columns = [
        "doc_id",
        "target",
        "label1",
        "label2",
        "label3",
        "label4",
        "prime",
        "polarity",
        "sentence",
    ]
    annotated_df = pd.read_csv(args.ANNOTATED_DATA, sep="\t", usecols=columns)
    for column in columns:
        annotated_df[column].fillna("", inplace=True)

    master_df = pd.read_csv(args.MASTER_DATA)
    master_df = master_df[master_df["ignore"] != 1]
    master_df["polarity"] = master_df["polarity"].map(lambda x: x[0])
    doc_id2stock_code = {basename: stock_code for basename, stock_code in master_df[["basename", "stock_code"]].values}

    dev_doc_ids, test_doc_ids = split_documents(master_df)
    dev, test = get_dev_and_test_splits(annotated_df, doc_id2stock_code, dev_doc_ids)

    out_dir = Path(args.OUT_DIR)
    out_dir.mkdir(exist_ok=True)
    with open(out_dir.joinpath("dev.jsonl"), mode="w") as f:
        for example in dev:
            f.write(json.dumps(asdict(example), ensure_ascii=False) + "\n")
    with open(out_dir.joinpath("test.jsonl"), mode="w") as f:
        for example in test:
            f.write(json.dumps(asdict(example), ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
