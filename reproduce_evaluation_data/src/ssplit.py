import re

PARENTHESIS2ALTERNATIVE = {
    "（": "ω",
    "(": "ψ",
    "「": "χ",
    "“": "φ",
    "）": "υ",
    ")": "τ",
    "」": "σ",
    "”": "ρ",
}
ALTERNATIVE2PARENTHESIS = str.maketrans(
    {"ω": "（", "ψ": "(", "χ": "「", "φ": "“", "υ": "）", "τ": ")", "σ": "」", "ρ": "”"}
)


def ssplit(text, model="regex"):
    """Split text into sentences.

    Parameters
    ----------
    text : str
        A input text to be split.
    model : str
        A model name (default: regex).

    Returns
    -------
    list[str]
    """
    if model == "regex":
        return _ssplit_regex(text)
    else:
        raise NotImplementedError


def _ssplit_regex(text):
    """Split text into sentences by regular expressions.

    Parameters
    ----------
    text : str
        A input text to be split.

    Returns
    -------
    list[str]
    """
    _balanced = _balance(text)
    _regex = re.compile("[^。]*。|[^。]*$")
    _sentence_candidates = []
    for line in _balanced.split("\n"):
        _sentence_candidates += re.findall(_regex, line + "\n")
    _sentence_candidates = _merge_sentence_candidates(_sentence_candidates)
    return _clean_up_sentence_candidates(_sentence_candidates)


def _balance(text):
    """Balance text that contains unclosed parenthesis.

    Parameters
    ----------
    text : str
        A input text to be balanced.

    Returns
    -------
    str
    """
    balanced = list(text)
    stack = {}

    for idx, char in enumerate(text):
        if char in {"（", "(", "「", "“"}:
            stack[idx] = char
        elif char in {"）", ")", "」", "”"}:
            if stack:
                for key, value in sorted(stack.items(), reverse=True):
                    # key < idx
                    if (
                        value == "（"
                        and char in {"）", ")"}
                        or value == "("  # == > and > or
                        and char in {"）", ")"}
                        or value == "「"
                        and char == "」"
                        or value == "“"
                        and char == "”"
                    ):
                        del stack[key]
                        break
            else:
                balanced[idx] = PARENTHESIS2ALTERNATIVE[char]

    for key, char in stack.items():
        balanced[key] = PARENTHESIS2ALTERNATIVE[char]

    return "".join(balanced)


def _merge_sentence_candidates(sentence_candidates):
    """Merge sentence candidates.

    Parameters
    ----------
    sentence_candidates : list[str]
        A list of sentence candidates.

    Returns
    -------
    list[str]
    """
    sentence_candidates = _merge_single_periods(sentence_candidates)
    sentence_candidates = _merge_parenthesis(sentence_candidates)
    return sentence_candidates


def _merge_single_periods(sentence_candidates):
    """Merge sentence candidates that consist of a single period.

    Parameters
    ----------
    sentence_candidates : list[str]
        A list of sentence candidates.

    Returns
    -------
    list[str]
    """
    _regex = re.compile(r"^。$")

    merged_sentences = [""]
    for sentence_candidate in sentence_candidates:
        if re.match(_regex, sentence_candidate):
            merged_sentences[-1] += sentence_candidate
        else:
            merged_sentences.append(sentence_candidate)

    if merged_sentences[0] == "":
        merged_sentences.pop(0)  # remove the dummy sentence
    return merged_sentences


def _merge_parenthesis(sentence_candidates):
    """Merge sentence candidates so that they save strings in parentheses or brackets.

    Parameters
    ----------
    sentence_candidates : list[str]
        A list of sentence candidates.

    Returns
    -------
    list[str]
    """
    parenthesis_level = 0
    quotation_level = 0

    merged_sentences = []
    _sentence_candidate = ""
    while sentence_candidates:
        sentence_candidate = sentence_candidates.pop(0)

        parenthesis_level += sentence_candidate.count("（") + sentence_candidate.count("(")
        parenthesis_level -= sentence_candidate.count("）") + sentence_candidate.count(")")

        quotation_level += sentence_candidate.count("「") + sentence_candidate.count("“")
        quotation_level -= sentence_candidate.count("」") + sentence_candidate.count("”")

        if parenthesis_level == 0 and quotation_level == 0:
            sentence_candidate = _sentence_candidate + sentence_candidate
            merged_sentences.append(sentence_candidate)
            _sentence_candidate = ""
        else:
            if "\n" in sentence_candidate:
                sentence_candidate, rest = sentence_candidate.split("\n", maxsplit=1)
                sentence_candidate = _sentence_candidate + sentence_candidate
                merged_sentences.append(sentence_candidate)
                _sentence_candidate = ""
                sentence_candidates.insert(0, rest)
                parenthesis_level = 0
                quotation_level = 0
            else:
                _sentence_candidate += sentence_candidate

    if _sentence_candidate:
        merged_sentences.append(_sentence_candidate)
    return merged_sentences


def _clean_up_sentence_candidates(sentence_candidates):
    """Remove empty sentence candidates.

    Parameters
    ----------
    sentence_candidates : list[str]
        A list of sentence candidates.

    Returns
    -------
    list[str]
    """
    return [
        sentence_candidate.translate(ALTERNATIVE2PARENTHESIS)
        for sentence_candidate in sentence_candidates
        if sentence_candidate
    ]
