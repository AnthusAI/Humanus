"""Built-in checks for published writing standards.

These are the mechanical rules that standards such as ASD-STE100 (Simplified
Technical English) and the Federal Plain Language Guidelines share: length
limits, readability, procedure-step shape, acronym definitions and one meaning
per word. Each check takes its limits and word lists from params, so a policy
pack sets the numbers its standard prescribes.

A sentence is a *procedure* sentence when it is in a list item, or when its
paragraph starts with an imperative verb. Every other sentence is a
*description* sentence.
"""
from __future__ import annotations

import re
from typing import Iterable

from .segmentation import Segment, SegmentedDocument, mask_inline

Match = tuple[int, int, "str | None", "str | None"]

WORD = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*")

IMPERATIVE_VERBS = frozenset(
    """
    add adjust align allow apply arrange ask assemble attach avoid back be bend block break bring build calculate
    call cancel change charge check choose clean clear click close collect compare complete confirm connect contact
    continue copy cover create cut decrease delete describe detach disconnect discard do download drain drill drive
    enable enter examine fill find fit fix flush follow fold give go grip hold identify inflate insert inspect install
    keep label leave lift limit lock loosen lower lubricate make mark measure meet monitor mount move note open order
    paint pay place plug point position pour prepare press prevent print protect pull push put raise read record
    reduce refer register release remove repair repeat replace report request reset restart return review rinse
    rotate run save scroll seal select send set shake shut sign slide speak specify start stop store submit supply
    switch take tap tell test tighten turn twist type unlock unplug update upload use verify visit wait wash wear
    wipe write
    """.split()
)

SUBJECT_TOKENS = frozenset(
    "you we i the a an it they he she there this that these those user users operator operators person people".split()
)

DETERMINERS = frozenset("a an the this that each every any no another its their your our his her".split())
VERB_MARKERS = frozenset("will would can could must should shall may might do does did not please".split())

NEGATORS = r"(?:not|never|no|\w+n['’]t)"
NEGATIVE_WORDS = (
    r"(?:nothing|nobody|none|nowhere|neither|never|no\s+one|"
    r"un(?:common|usual|likely|important|reasonable|known|clear|certain|aware|able|fair|helpful|necessary|"
    r"available|willing|wise|true|related|limited|acceptable|interesting|familiar|safe|lawful)|"
    r"in(?:frequent|significant|valid|correct|consistent|appropriate|accurate|complete|sufficient|capable)|"
    r"im(?:possible|probable|proper|material)|il(?:legal|logical)|ir(?:relevant|regular|responsible)|non\w{3,})"
)
DOUBLE_NEGATIVE = re.compile(rf"\b{NEGATORS}\b(?:\s+\w+){{0,2}}?\s+{NEGATIVE_WORDS}\b", re.IGNORECASE)

ACRONYM = re.compile(r"\b[A-Z][A-Z0-9]*[A-Z](?:s)?\b")
KNOWN_ACRONYMS = frozenset(
    "OK US USA UK EU UN AM PM TV ID PDF URL FAQ CEO DC II III IV VI VII VIII IX XI XII".split()
)

ING_WORD = re.compile(r"\b[A-Za-z]{2,}ing\b")
ING_NOUNS = frozenset(
    """
    anything bring ceiling cling during evening everything fling king morning nothing ping pudding ring sing sling
    something spring sting string swing thing things wedding wing
    """.split()
)

VOWEL_GROUP = re.compile(r"[aeiouy]+")


def words(text: str) -> list[str]:
    return WORD.findall(text)


def _verbs(params: dict) -> frozenset[str]:
    extra = params.get("imperativeVerbs")
    return IMPERATIVE_VERBS | {v.lower() for v in extra} if extra else IMPERATIVE_VERBS


def _first_word(text: str) -> str:
    found = words(text)
    return found[0].lower() if found else ""


def _is_procedure(sentence: Segment, paragraph: Segment | None, verbs: frozenset[str]) -> bool:
    if sentence.block == "listItem":
        return True
    return paragraph is not None and paragraph.block == "paragraph" and _first_word(paragraph.text) in verbs


def _with_topic(sentences: list[Segment], paragraphs: list[Segment], topic: str, verbs: frozenset[str]) -> list[Segment]:
    if topic == "any":
        return sentences
    by_id = {p.id: p for p in paragraphs}
    procedure = topic == "procedure"
    return [s for s in sentences if _is_procedure(s, by_id.get(s.parent_id), verbs) == procedure]


def _word_spans(segment: Segment) -> list[tuple[str, int, int]]:
    """Words in a segment's source, with document offsets; inline code and URLs are masked out."""
    return [(m.group(), segment.start + m.start(), segment.start + m.end()) for m in WORD.finditer(mask_inline(segment.source))]


# --- length and readability ----------------------------------------------------------


def _sentence_length(document, paragraphs, sentences, params):
    limit = params["maxWords"]
    verbs = _verbs(params)
    for sentence in _with_topic(sentences, paragraphs, params.get("topic", "any"), verbs):
        count = len(words(sentence.text))
        if count > limit:
            yield sentence.start, sentence.end, f"Sentence has {count} words; the limit is {limit}.", None


def _average_sentence_length(document, paragraphs, sentences, params):
    if len(sentences) < params.get("minSentences", 1):
        return
    average = sum(len(words(s.text)) for s in sentences) / len(sentences) if sentences else 0
    limit = params["maxWords"]
    if average > limit:
        yield 0, len(document.text), f"Sentences average {average:.1f} words; the target is {limit} or fewer.", None


def _paragraph_length(document, paragraphs, sentences, params):
    counts: dict[str, int] = {}
    for sentence in document.sentences():
        counts[sentence.parent_id] = counts.get(sentence.parent_id, 0) + 1
    max_sentences = params.get("maxSentences")
    max_words = params.get("maxWords")
    for paragraph in paragraphs:
        sentence_count = counts.get(paragraph.id, 0)
        word_count = len(words(paragraph.text))
        if max_sentences is not None and sentence_count > max_sentences:
            yield paragraph.start, paragraph.end, f"Paragraph has {sentence_count} sentences; the limit is {max_sentences}.", None
        elif max_words is not None and word_count > max_words:
            yield paragraph.start, paragraph.end, f"Paragraph has {word_count} words; the limit is {max_words}.", None


def syllables(word: str) -> int:
    word = word.lower().strip("'’")
    count = len(VOWEL_GROUP.findall(word))
    if word.endswith("e") and not word.endswith(("le", "ee", "ye")) and count > 1:
        count -= 1
    return max(count, 1)


def flesch_kincaid_grade(sentence_count: int, tokens: list[str]) -> float:
    if not sentence_count or not tokens:
        return 0.0
    syllable_count = sum(syllables(t) for t in tokens)
    return 0.39 * len(tokens) / sentence_count + 11.8 * syllable_count / len(tokens) - 15.59


def _reading_grade_level(document, paragraphs, sentences, params):
    tokens = [t for s in sentences for t in words(s.text)]
    if len(tokens) < params.get("minWords", 100):
        return
    grade = flesch_kincaid_grade(len(sentences), tokens)
    limit = params["maxGrade"]
    if grade > limit:
        yield 0, len(document.text), f"Reads at Flesch-Kincaid grade {grade:.1f}; the target is grade {limit} or lower.", None


# --- sentence shape ---------------------------------------------------------------------


def _double_negative(document, paragraphs, sentences, params):
    for paragraph in paragraphs:
        for match in DOUBLE_NEGATIVE.finditer(mask_inline(paragraph.source)):
            yield paragraph.start + match.start(), paragraph.start + match.end(), "Double negative: state it positively.", None


def _undefined_acronym(document, paragraphs, sentences, params):
    allow = KNOWN_ACRONYMS | set(params.get("allow", ()))
    seen: set[str] = set()
    for paragraph in paragraphs:
        masked = mask_inline(paragraph.source)
        for match in ACRONYM.finditer(masked):
            acronym = match.group().removesuffix("s") if match.group().endswith("s") else match.group()
            if acronym in seen or acronym in allow or len(acronym) < 2:
                continue
            seen.add(acronym)
            defined_inside = masked[: match.start()].rstrip().endswith("(") and masked[match.end() :].lstrip().startswith(")")
            defined_after = re.match(r"\s*\(\s*[A-Za-z]", masked[match.end() :]) is not None
            if not (defined_inside or defined_after):
                yield paragraph.start + match.start(), paragraph.start + match.end(), f"Define {acronym} the first time you use it.", None


def _steps(sentences: list[Segment], paragraphs: list[Segment], params: dict, verbs: frozenset[str]) -> list[Segment]:
    return sentences if params.get("wholeDocument") else _with_topic(sentences, paragraphs, "procedure", verbs)


def _multiple_instructions(document, paragraphs, sentences, params):
    verbs = _verbs(params)
    for sentence in _steps(sentences, paragraphs, params, verbs):
        parts = re.split(r"\b(?:and\s+then|and|then|or)\b|;", sentence.text, flags=re.IGNORECASE)
        if any(_first_word(part) in verbs for part in parts[1:]):
            yield sentence.start, sentence.end, "Write one instruction per step.", None


def _imperative_steps(document, paragraphs, sentences, params):
    first_sentence: dict[str, Segment] = {}
    for sentence in sentences:
        if sentence.block == "listItem" or params.get("wholeDocument"):
            first_sentence.setdefault(sentence.parent_id, sentence)
    for sentence in first_sentence.values():
        if _first_word(sentence.text) in SUBJECT_TOKENS:
            yield sentence.start, sentence.end, "Start each step with an imperative verb.", None


# --- word choice ---------------------------------------------------------------------------


def _ing_form(document, paragraphs, sentences, params):
    allow = ING_NOUNS | {w.lower() for w in params.get("allow", ())}
    for paragraph in paragraphs:
        for match in ING_WORD.finditer(mask_inline(paragraph.source)):
            if match.group().lower() not in allow:
                yield paragraph.start + match.start(), paragraph.start + match.end(), f"'{match.group()}' is an -ing form; use a simple verb or a noun.", None


def _missing_article(document, paragraphs, sentences, params):
    nouns = {n.lower() for n in params["nouns"]}
    for sentence in sentences:
        spans = _word_spans(sentence)
        if spans and spans[0][0].lower() in nouns:
            word, start, end = spans[0]
            yield start, end, f"Put an article (a, an, the) or another determiner before '{word}'.", None


def _one_meaning(document, paragraphs, sentences, params):
    meanings = {entry["word"].lower(): entry["meaning"] for entry in params["words"]}
    for sentence in sentences:
        spans = _word_spans(sentence)
        lowered = [w.lower() for w, _, _ in spans]
        for index, (word, start, end) in enumerate(spans):
            meaning = meanings.get(lowered[index])
            if meaning is None:
                continue
            before = lowered[index - 1] if index else None
            after = lowered[index + 1] if index + 1 < len(lowered) else None
            if meaning == "verb" and before in DETERMINERS:
                yield start, end, f"Use '{word}' only as a verb.", None
            elif meaning == "noun" and (before in VERB_MARKERS or (index == 0 and after in DETERMINERS)):
                yield start, end, f"Use '{word}' only as a noun.", None


STANDARD_CHECKS = {
    "sentence_length": _sentence_length,
    "average_sentence_length": _average_sentence_length,
    "paragraph_length": _paragraph_length,
    "reading_grade_level": _reading_grade_level,
    "double_negative": _double_negative,
    "undefined_acronym": _undefined_acronym,
    "multiple_instructions": _multiple_instructions,
    "imperative_steps": _imperative_steps,
    "ing_form": _ing_form,
    "missing_article": _missing_article,
    "one_meaning": _one_meaning,
}
