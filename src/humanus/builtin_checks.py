"""Built-in prose checks for the rules lane.

Each check reads the segmented document (prose only: code, quotes, directives
and the other protected regions never reach it) and yields matches as
(start, end, message, replacement) in document offsets.
"""
from __future__ import annotations

import gzip
import re
from collections import defaultdict
from typing import Callable, Iterable

from .emoji import EMOJI_PATTERN
from .segmentation import Segment, SegmentedDocument, mask_inline, normalize_text, plain_text
from .standard_checks import STANDARD_CHECKS

Match = tuple[int, int, "str | None", "str | None"]
BuiltinCheck = Callable[[SegmentedDocument, list[Segment], list[Segment], dict], Iterable[Match]]

EMPTY_LEADIN_PATTERNS = (
    "^In today's\\b",
    '^It is important to note\\b',
    '^When it comes to\\b',
    '^At the end of the day\\b',
    '^In conclusion\\b',
)
CRUTCH_WORDS = ('actually', 'really', 'very', 'basically', 'essentially', 'literally', 'simply', 'clearly', 'obviously')
CONTRACTION_PAIRS = (
    ('that is', "that's"),
    ('it is', "it's"),
    ('there is', "there's"),
    ('who is', "who's"),
    ('what is', "what's"),
    ('do not', "don't"),
    ('does not', "doesn't"),
    ('did not', "didn't"),
    ('cannot', "can't"),
    ('can not', "can't"),
    ('will not', "won't"),
    ('would not', "wouldn't"),
    ('should not', "shouldn't"),
    ('could not', "couldn't"),
    ('is not', "isn't"),
    ('are not', "aren't"),
    ('was not', "wasn't"),
    ('were not', "weren't"),
    ('have not', "haven't"),
    ('has not', "hasn't"),
    ('had not', "hadn't"),
    ('they are', "they're"),
    ('we are', "we're"),
    ('you are', "you're"),
    ('i am', "I'm"),
    ('let us', "let's"),
)
PHRASE_CERTAINTY = re.compile('\\b(everyone knows|undeniably|proven)\\b', re.IGNORECASE)
ALWAYS_NEVER = re.compile('\\b(always|never)\\b', re.IGNORECASE)
HYPHENATED_ALWAYS_NEVER = re.compile('\\b(always|never)-\\w+', re.IGNORECASE)
NEVER_AUXILIARY = re.compile('\\bnever\\s+(had|would|could|should|might|may|will|can)\\b', re.IGNORECASE)
CLEARLY_ASSERTIVE = re.compile('\\bclearly\\s+(shows|demonstrates|proves|will|is)\\b', re.IGNORECASE)
CITATION = re.compile('(https?://|\\[[0-9]+\\]|according to|\\([12][0-9]{3}\\)|\\b20[0-9]{2}\\b)', re.IGNORECASE)
LIST_SHAPED = re.compile('\\bFirst,\\s+.+\\bSecond,\\s+.+\\bThird,\\s+', re.IGNORECASE)
INTENSIFIER_VAGUE = re.compile('\\b(very|significantly|dramatically|truly|really)\\b.+\\b(transform|revolutionize|leverage)\\b', re.IGNORECASE)
IRREGULAR_PARTICIPLES = (
    'made', 'done', 'given', 'taken', 'held', 'kept', 'put', 'set', 'sent', 'shown', 'known', 'seen', 'written',
    'built', 'found', 'paid', 'told', 'brought', 'bought', 'caught', 'taught', 'thought', 'lost', 'begun', 'chosen',
    'driven', 'eaten', 'forgotten', 'gotten', 'hidden', 'broken', 'spoken', 'stolen', 'worn', 'torn', 'drawn',
    'grown', 'thrown', 'sold', 'shut', 'led', 'fed', 'laid', 'said', 'heard', 'meant', 'understood', 'struck',
    'hung', 'won', 'spent', 'bound',
)
PASSIVE = re.compile(
    rf"\b(is|are|was|were|be|been|being)\s+(\w+ed|{'|'.join(IRREGULAR_PARTICIPLES)})\b", re.IGNORECASE
)
STAT_PERCENT = re.compile('\\d+(?:\\.\\d+)?%')
STAT_MULTIPLIER = re.compile('\\d+\\s*[×x]\\b|\\d+\\s+times\\b', re.IGNORECASE)
STAT_COUNT_UNIT = re.compile('\\b\\d{3,}\\s+(users|ms|seconds|minutes|hours|days|requests|tokens)\\b', re.IGNORECASE)
STICKER_NUMBER = re.compile('#\\d+\\b')
REFRAIN_MAX_WORDS = 12
TOKEN = re.compile(r"[A-Za-z0-9']+")

# Function-word inventory aligned with Ure (1971) / Halliday lexical-density practice.
FUNCTION_WORDS = frozenset(
    """
    a about above after again against all am an and any are as at be because been before being
    below between both but by can could did do does doing down during each few for from further
    had has have having he her here hers herself him himself his how i if in into is it its
    itself just me more most my myself no nor not now of off on once only or other our ours
    ourselves out over own same she should so some such than that the their theirs them
    themselves then there these they this those through to too under until up very was we were
    what when where which while who whom why will with would you your yours yourself yourselves
    """.split()
)


# --- sentence predicates ----------------------------------------------------------


def has_unsupported_certainty(sentence: str) -> bool:
    if PHRASE_CERTAINTY.search(sentence) or CLEARLY_ASSERTIVE.search(sentence):
        return True
    if not ALWAYS_NEVER.search(HYPHENATED_ALWAYS_NEVER.sub(" ", sentence)):
        return False
    if NEVER_AUXILIARY.search(sentence) or re.match(r"^Never\s+\w", sentence.strip()):
        return False
    return True


def has_statistical_claim(sentence: str) -> bool:
    return bool(STAT_PERCENT.search(sentence) or STAT_MULTIPLIER.search(sentence) or STAT_COUNT_UNIT.search(sentence))


def _sentence_check(predicate: Callable[[Segment], bool], message: str) -> BuiltinCheck:
    def run(document, paragraphs, sentences, params):
        for sentence in sentences:
            if predicate(sentence):
                yield sentence.start, sentence.end, message, None

    return run


def _empty_leadin(sentence: Segment) -> bool:
    return any(re.search(pattern, sentence.text, re.IGNORECASE) for pattern in EMPTY_LEADIN_PATTERNS)


def _unsupported_certainty(sentence: Segment) -> bool:
    return has_unsupported_certainty(sentence.text) and not CITATION.search(sentence.source)


def _missing_attribution(sentence: Segment) -> bool:
    if not has_statistical_claim(sentence.text) or CITATION.search(sentence.source):
        return False
    return not (STICKER_NUMBER.search(sentence.text) and not STAT_PERCENT.search(sentence.text))


# --- paragraph and document checks --------------------------------------------------


def _list_shaped_prose(document, paragraphs, sentences, params):
    for paragraph in paragraphs:
        if LIST_SHAPED.search(paragraph.text):
            yield paragraph.start, paragraph.end, "Paragraph reads like an inline list without substantive development.", None


def _uniform_cadence(document, paragraphs, sentences, params):
    prose = [s for s in sentences if s.block == "paragraph"]
    run_start = 0
    while len(prose) >= 5 and run_start < len(prose):
        anchor = len(prose[run_start].text.split())
        run_end = run_start + 1
        while run_end < len(prose) and abs(len(prose[run_end].text.split()) - anchor) <= 3:
            run_end += 1
        if run_end - run_start >= 5:
            yield prose[run_start].start, prose[run_end - 1].end, "Five or more consecutive sentences share nearly identical length.", None
            run_start = run_end
        else:
            run_start += 1


def _overused_words(document, paragraphs, sentences, params):
    words = " ".join(p.text for p in paragraphs)
    total = max(len(words.split()), 1)
    threshold = max(3, round(total / 250))
    for word in CRUTCH_WORDS:
        pattern = re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
        uses = len(pattern.findall(words))
        if uses <= threshold:
            continue
        for paragraph in paragraphs:
            first = pattern.search(mask_inline(paragraph.source))
            if first:
                yield (
                    paragraph.start + first.start(),
                    paragraph.start + first.end(),
                    f"'{word}' appears {uses} times across {total} words; cut most of them.",
                    None,
                )
                break


def _uncontracted_forms(document, paragraphs, sentences, params):
    for paragraph in paragraphs:
        masked = mask_inline(paragraph.source)
        taken: list[tuple[int, int]] = []
        for formal, contracted in CONTRACTION_PAIRS:
            for match in re.finditer(rf"\b{re.escape(formal)}\b", masked, re.IGNORECASE):
                start, end = match.span()
                if any(start < b and end > a for a, b in taken):
                    continue
                if formal == "that is" and masked[end : end + 1] == ",":
                    continue  # the "i.e." sense; contracting it changes the meaning
                matched = paragraph.source[start:end]
                replacement = contracted[0].upper() + contracted[1:] if matched[0].isupper() else contracted
                taken.append((start, end))
                yield paragraph.start + start, paragraph.start + end, f"'{matched}' could contract to '{replacement}'.", replacement


def _emphasis_spans(source: str) -> list[tuple[int, int]]:
    """Spans inside single *...* or _..._ emphasis (not ** bold): italic quotations and formulas."""
    return [m.span(2) for m in re.finditer(r"(?<![*_\w])([*_])(?!\1)(.+?)(?<!\1)\1(?![*_\w])", source, re.S)]


def _redundancy(document, paragraphs, sentences, params):
    """Sentences in different places that share a four-word phrase.

    Italic passages, prose inside container directives (pull quotes repeat the
    body on purpose) and short identical refrains are not redundancy.
    """
    shingles: dict[str, list[Segment]] = defaultdict(list)
    for sentence in sentences:
        if sentence.block == "heading" or sentence.container is not None:
            continue
        masked = mask_inline(sentence.source)
        italic = _emphasis_spans(sentence.source)
        tokens = [
            (match.group().lower(), match.start(), match.end())
            for match in TOKEN.finditer(masked)
            if sentence.source[match.start() : match.end()] == match.group()
        ]
        seen: set[str] = set()
        for index in range(len(tokens) - 3):
            start, end = tokens[index][1], tokens[index + 3][2]
            if any(a <= start and end <= b for a, b in italic):
                continue
            shingle = " ".join(token for token, _, _ in tokens[index : index + 4])
            if shingle not in seen:
                seen.add(shingle)
                shingles[shingle].append(sentence)
    flagged: set[str] = set()
    for members in shingles.values():
        unique = list({s.id: s for s in members}.values())
        if len(unique) < 2:
            continue
        texts = {normalize_text(s.text).lower() for s in unique}
        if len(texts) == 1 and len(next(iter(texts)).split()) <= REFRAIN_MAX_WORDS:
            continue
        for sentence in unique:
            if sentence.id not in flagged:
                flagged.add(sentence.id)
                yield sentence.start, sentence.end, "Repeats a four-word phrase used elsewhere in the document.", None


def lexical_density(tokens: list[str]) -> float:
    return sum(1 for token in tokens if token not in FUNCTION_WORDS) / len(tokens) if tokens else 0.0


def gzip_ratio(text: str) -> float:
    encoded = text.encode("utf-8")
    return len(gzip.compress(encoded)) / len(encoded) if encoded else 1.0


def _information_density(document, paragraphs, sentences, params):
    prose = "\n\n".join(p.text for p in paragraphs)
    tokens = [token.lower() for token in TOKEN.findall(prose)]
    if len(tokens) < params.get("minWords", 400):
        return
    density = lexical_density(tokens)
    minimum = params.get("minLexicalDensity", 0.45)
    if density < minimum:
        yield 0, len(document.text), f"Lexical density {density:.3f} is below {minimum:.3f}: many words, little content.", None
    ratio = gzip_ratio(prose)
    maximum = params.get("maxGzipRatio", 0.35)
    if ratio <= maximum:
        yield 0, len(document.text), f"The text compresses unusually well (gzip ratio {ratio:.3f} <= {maximum:.3f}): it repeats itself.", None


def _contrast_cap(document, paragraphs, sentences, params):
    cap = params["max"]
    matches = [
        (p.start + m.start(), p.start + m.end())
        for p in paragraphs
        for m in re.finditer(r",\s*not\s+\w+", mask_inline(p.source), re.IGNORECASE)
    ]
    if len(matches) > cap:
        for start, end in matches:
            yield start, end, f"{len(matches)} 'X, not Y' contrasts in this document; the cap is {cap}.", None


def _no_emojis(document, paragraphs, sentences, params):
    for paragraph in paragraphs:
        for match in EMOJI_PATTERN.finditer(paragraph.source):
            yield paragraph.start + match.start(), paragraph.start + match.end(), "Contains an emoji.", ""


def _passive_voice(document, paragraphs, sentences, params):
    """Passive voice; with ``_quotations`` (document spans), words inside a quotation do not count."""
    quotations = params.get("_quotations", ())
    for sentence in sentences:
        source = sentence.source
        for a, b in quotations:
            lo, hi = max(a, sentence.start) - sentence.start, min(b, sentence.end) - sentence.start
            if lo < hi:
                source = source[:lo] + " " * (hi - lo) + source[hi:]
        text = plain_text(source) if source != sentence.source else sentence.text
        if PASSIVE.search(text):
            yield sentence.start, sentence.end, "Sentence uses passive voice.", None


BUILTIN_CHECKS: dict[str, BuiltinCheck] = {
    "empty_leadin": _sentence_check(_empty_leadin, "Sentence opens with empty boilerplate instead of a concrete stake."),
    "list_shaped_prose": _list_shaped_prose,
    "vague_claim": _sentence_check(
        lambda s: bool(INTENSIFIER_VAGUE.search(s.text)),
        "Sentence pairs empty intensifiers with vague transformation language.",
    ),
    "unsupported_certainty": _sentence_check(_unsupported_certainty, "Sentence states certainty without attributable evidence."),
    "uniform_cadence": _uniform_cadence,
    "redundancy": _redundancy,
    "passive_voice": _passive_voice,
    "missing_attribution": _sentence_check(_missing_attribution, "Numeric or statistical claim lacks attributable evidence."),
    "information_density": _information_density,
    "overused_words": _overused_words,
    "uncontracted_forms": _uncontracted_forms,
    "contrast_cap": _contrast_cap,
    "no_emojis": _no_emojis,
    **STANDARD_CHECKS,
}
