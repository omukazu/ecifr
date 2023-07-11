import json
from argparse import ArgumentParser
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

EXPECTED_STATS = {
    "dev": {
        "num_examples": 632,
        "num_positive_causality": 252,
        "num_negative_causality": 380,
        "num_positive_polarity": 188,
        "num_negative_polarity": 49,
    },
    "test": {
        "num_examples": 3411,
        "num_positive_causality": 1331,
        "num_negative_causality": 2080,
        "num_positive_polarity": 910,
        "num_negative_polarity": 351,
    },
}


@dataclass
class Example:
    doc_id: str
    stock_code: str
    sentence: str
    causality: str
    polarity: str
    importance: str


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
        segment,
        causality1,
        causality2,
        causality3,
        causality4,
        polarity,
        importance,
        sentence,
    ) in annotated_df.values:
        if target in {"target", "0"}:
            continue

        sentence = sentence.translate(str.maketrans("*+", "＊＋"))

        majority, num_votes = Counter([causality1, causality2, causality3, causality4]).most_common()[0]
        causality = majority if num_votes >= 3 else ""

        example = Example(
            doc_id=doc_id,
            stock_code=doc_id2stock_code[doc_id + ".pdf"],
            sentence=sentence,
            causality=causality_map[causality],
            polarity=polarity_map[polarity],
            importance=importance,
        )
        switch = dev if doc_id + ".pdf" in dev_doc_ids else test
        switch.append(example)
    return dev, test


def save_examples(output_path: Path, examples: list[Example]) -> None:
    with output_path.open(mode="w") as f:
        for example in examples:
            f.write(json.dumps(asdict(example), ensure_ascii=False) + "\n")


def get_stats(examples: list[Example]) -> dict[str, int]:
    ctr = defaultdict(int)
    for example in examples:
        ctr[example.causality] += 1
        if example.causality == "正例":
            ctr[example.polarity] += 1
    return {
        "num_examples": len(examples),
        "num_positive_causality": ctr["正例"],
        "num_negative_causality": ctr["負例"],
        "num_positive_polarity": ctr["+"],
        "num_negative_polarity": ctr["-"],
    }


def main():
    parser = ArgumentParser()
    parser.add_argument("ANNOTATED_DATA", type=str, help="path to annotated_data.tsv")
    parser.add_argument("MASTER_DATA", type=str, help="path to master_data.csv")
    parser.add_argument("OUT_DIR", help="path to output dir")
    args = parser.parse_args()

    columns = [
        "doc_id",
        "target",
        "segment",
        "causality1",
        "causality2",
        "causality3",
        "causality4",
        "polarity",
        "importance",
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
    dataset = {"dev": dev, "test": test}

    out_dir = Path(args.OUT_DIR)
    out_dir.mkdir(exist_ok=True)
    for stem, examples in dataset.items():
        save_examples(out_dir / f"{stem}.jsonl", examples)
        for key, value in get_stats(examples).items():
            if value != EXPECTED_STATS[stem][key]:
                print(f"{stem}-{key} isn't reproduced ({value} vs {EXPECTED_STATS[stem][key]})")


if __name__ == "__main__":
    main()
