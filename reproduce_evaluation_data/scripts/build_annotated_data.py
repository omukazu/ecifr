import subprocess
from argparse import ArgumentParser
from pathlib import Path
from time import sleep

import pandas as pd
from scraping import extract_pages, get_qualitative_information, get_text
from ssplit import ssplit


def main():
    parser = ArgumentParser()
    parser.add_argument("ANNOTATION", type=str, help="path to annotation.tsv")
    parser.add_argument("MASTER_DATA", type=str, help="path to master_data.csv")
    parser.add_argument("OUT", type=str, help="path to output")
    args = parser.parse_args()

    annotation = pd.read_csv(args.ANNOTATION, sep="\t")
    master_df = pd.read_csv(args.MASTER_DATA)
    work_dir = Path("./pdf")
    work_dir.mkdir(exist_ok=True)

    sentences = []
    for ignore, stock_code, url, basename in master_df[["ignore", "stock_code", "url", "basename"]].values:
        if ignore == 1:
            continue

        pdf_path = work_dir / basename
        subprocess.run(["wget", "-O", str(pdf_path), "--timeout", "6", "-t", "6", url], check=True)
        sleep(1)

        sentences.append("sentence")
        pages = extract_pages(pdf_path)
        sections = get_qualitative_information(pages)
        for key, section in sections.items():
            text = get_text(section)
            sentences.extend([sentence.strip() for sentence in ssplit(text) if sentence.strip()])

    annotation["sentence"] = sentences[1:]
    annotation.to_csv(args.OUT, sep="\t", index=False)


if __name__ == "__main__":
    main()
