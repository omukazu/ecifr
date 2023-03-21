# Data and Scripts for Reproducing Evaluation Data

This repository contains data and scripts for reproducing the evaluation data used in [[大村ら2023]](https://www.anlp.jp/proceedings/annual_meeting/2023/pdf_dir/D11-2.pdf).

### Requirements

- Python: 3.9
- Poetry: 1.2+
- Dependencies: see pyproject.toml.

### Set up Python Virtual Environment

```shell
# pip install poetry
poetry install
```

### [OPTIONAL] Set up pre-commit

Please install pre-commit when contributing to this repository.

```shell
# pip install pre-commit
pre-commit install
```

### Command Examples

```shell
# reproduce annotated data from annotation and master data
poetry run python scripts/build_annotated_data.py data/annotation.tsv data/master_data.csv data/annotated_data.tsv
# build evaluation data from (by splitting) annotated data
poetry run python scripts/build_evaluation_data.py data/annotated_data.tsv data/master_data.csv dataset/
```

### Data Format

The format of evaluation data is JSON Lines.

```json
{
  "doc_id": "00000009",
  "stock_code": "3777",
  "sentence": "...",
  "label": "負例",
  "prime": "",
  "polarity": ""
}
```

| Key      | Type | Description                                                 |
|----------|-----|-------------------------------------------------------------|
| doc_id   | str | unique id for the financial results                         |
| stock_code | str | stock code of a company that released the financial results |
| sentence | str | raw text of the annotated sentence                          |
| label    | str | whether the sentence is causal or not ("正例" or "負例")        |
| prime    | str | whether the sentence is important or not ("1", "?", or "")  |
| polarity | str | polarity of revenue/profit ("+", "-", "?", or "")           |

### License
This work is licensed under [a Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0) License](https://creativecommons.org/licenses/by-sa/4.0/).

### References

```bibtex
@InProceedings{omura_et_al_2023,
    author    = "大村 和正 and
        白井 穂乃 and
        石原 祥太郎 and
        澤 紀彦",
    title     = "極性と重要度を考慮した決算短信からの業績要因文の抽出",
    booktitle = "言語処理学会第29回年次大会 発表論文集",
    year      = "2023",
    address   = "沖縄",
}
```
