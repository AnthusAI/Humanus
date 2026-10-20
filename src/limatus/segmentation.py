"""Split a Markus/Markdown document into prose segments with exact offsets.

Every lane works on the same segmentation: one document segment, a paragraph
segment per prose block (paragraph, heading, list item) and a sentence segment
per sentence. Offsets are Python string indexes into the submitted text; the
check result converts them to UTF-16 at its boundary.

Markup that is not the author's prose is reported as a protected region and
never segmented: front matter, code, Markus directives, block quotes (someone
else's words), tables and raw HTML. Prose inside a container directive
(``:::callout`` ... ``:::``) is still prose.

Segment ids are derived from the segment's normalized text, so a paragraph
keeps its id when other paragraphs change. Repeated text gets an occurrence
suffix in document order.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache

from markdown_it import MarkdownIt

DOCUMENT_SEGMENT_ID = "doc"


@dataclass(frozen=True)
class Segment:
    id: str
    kind: str  # document | paragraph | sentence
    start: int
    end: int
    source: str  # exact source text, text[start:end]
    text: str  # plain prose with inline markup removed
    block: str | None = None  # paragraph | heading | listItem
    parent_id: str | None = None

    @property
    def text_hash(self) -> str:
        return _hash(normalize_text(self.text))


@dataclass(frozen=True)
class ProtectedRegion:
    kind: str  # frontMatter | code | directive | quote | table | html
    start: int
    end: int


@dataclass(frozen=True)
class SegmentedDocument:
    text: str
    segments: tuple[Segment, ...]
    protected: tuple[ProtectedRegion, ...] = field(default=())

    @property
    def paragraphs(self) -> tuple[Segment, ...]:
        return tuple(s for s in self.segments if s.kind == "paragraph")

    def sentences(self, paragraph: Segment | None = None) -> tuple[Segment, ...]:
        return tuple(
            s
            for s in self.segments
            if s.kind == "sentence" and (paragraph is None or s.parent_id == paragraph.id)
        )


def segment_document(text: str, format: str = "markus") -> SegmentedDocument:
    """Segment ``text`` written in ``format`` (``markus``, ``markdown`` or ``text``)."""
    if format == "text":
        protected: list[ProtectedRegion] = []
        blocks = [(m.start(), m.end(), "paragraph") for m in re.finditer(r"\S(?:.*\S)?(?:\n[ \t]*\S.*)*", text)]
        prose = [_trim_span(text, start, end) + (block,) for start, end, block in blocks]
    elif format in {"markus", "markdown"}:
        prose, protected = _markdown_blocks(text)
    else:
        raise ValueError(f"Unsupported content format '{format}'")
    return _build(text, prose, protected)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def plain_text(source: str) -> str:
    """Strip inline Markdown/Markus markup, keeping the words a reader sees."""
    result = source
    for pattern, replacement in _PLAIN_TEXT_RULES:
        result = pattern.sub(replacement, result)
    return normalize_text(result)


# --- building segments --------------------------------------------------------


def _build(text: str, prose: list[tuple[int, int, str]], protected: list[ProtectedRegion]) -> SegmentedDocument:
    segments = [Segment(DOCUMENT_SEGMENT_ID, "document", 0, len(text), text, plain_text(text))]
    ids = _IdAllocator()
    for start, end, block in sorted(prose):
        source = text[start:end]
        paragraph_text = plain_text(source)
        if not paragraph_text:
            continue
        paragraph_id = ids.allocate("p", paragraph_text)
        segments.append(Segment(paragraph_id, "paragraph", start, end, source, paragraph_text, block, DOCUMENT_SEGMENT_ID))
        for s_start, s_end in split_sentences(source):
            sentence_source = source[s_start:s_end]
            sentence_text = plain_text(sentence_source)
            if not sentence_text:
                continue
            segments.append(
                Segment(
                    ids.allocate("s", sentence_text),
                    "sentence",
                    start + s_start,
                    start + s_end,
                    sentence_source,
                    sentence_text,
                    block,
                    paragraph_id,
                )
            )
    return SegmentedDocument(text, tuple(segments), tuple(sorted(protected, key=lambda r: (r.start, r.end))))


class _IdAllocator:
    def __init__(self) -> None:
        self._seen: dict[str, int] = {}

    def allocate(self, prefix: str, text: str) -> str:
        base = f"{prefix}-{_hash(normalize_text(text))[:12]}"
        count = self._seen.get(base, 0) + 1
        self._seen[base] = count
        return base if count == 1 else f"{base}-{count}"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _trim_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


# --- Markdown / Markus block structure ----------------------------------------------

_FENCE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})")
_LEAF_DIRECTIVE = re.compile(r"^[ ]{0,3}::[A-Za-z][\w-]*")
_CONTAINER_OPEN = re.compile(r"^[ ]{0,3}:{3,}[A-Za-z][\w-]*")
_CONTAINER_CLOSE = re.compile(r"^[ ]{0,3}:{3,}\s*$")


@lru_cache(maxsize=1)
def _parser() -> MarkdownIt:
    return MarkdownIt("commonmark").enable("table")


def _markdown_blocks(text: str) -> tuple[list[tuple[int, int, str]], list[ProtectedRegion]]:
    lines = text.split("\n")
    line_starts = [0]
    for line in lines[:-1]:
        line_starts.append(line_starts[-1] + len(line) + 1)

    def line_span(first: int, last: int) -> tuple[int, int]:
        """Character span of lines first..last inclusive, without the final newline."""
        return line_starts[first], line_starts[last] + len(lines[last].rstrip("\r"))

    masked, protected = _mask_markus_lines(lines, line_span)
    tokens = _parser().parse("\n".join(masked))

    prose: list[tuple[int, int, str]] = []
    skip_until: str | None = None
    skip_level = 0
    list_depth = 0
    for index, token in enumerate(tokens):
        if skip_until is not None:
            if token.type == skip_until and token.level == skip_level:
                skip_until = None
            continue
        if token.type in {"blockquote_open", "table_open"} and token.map:
            protected.append(ProtectedRegion("quote" if token.type == "blockquote_open" else "table", *line_span(token.map[0], token.map[1] - 1)))
            skip_until, skip_level = token.type.replace("_open", "_close"), token.level
        elif token.type in {"fence", "code_block", "html_block"} and token.map:
            kind = "html" if token.type == "html_block" else "code"
            protected.append(ProtectedRegion(kind, *line_span(token.map[0], token.map[1] - 1)))
        elif token.type in {"bullet_list_open", "ordered_list_open"}:
            list_depth += 1
        elif token.type in {"bullet_list_close", "ordered_list_close"}:
            list_depth -= 1
        elif token.type == "inline" and token.map and token.content.strip():
            opener = tokens[index - 1].type
            block = "heading" if opener == "heading_open" else "listItem" if list_depth else "paragraph"
            span = _inline_source_span(token.content, lines, line_starts, token.map[0])
            if span is not None:
                prose.append((*span, block))
    return prose, protected


def _mask_markus_lines(lines: list[str], line_span) -> tuple[list[str], list[ProtectedRegion]]:
    """Blank out front matter and Markus directive syntax, keeping line numbers."""
    masked = list(lines)
    protected: list[ProtectedRegion] = []

    def blank(first: int, last: int, kind: str) -> None:
        for number in range(first, last + 1):
            masked[number] = ""
        protected.append(ProtectedRegion(kind, *line_span(first, last)))

    number = 0
    if lines and lines[0].rstrip("\r") == "---":
        for close in range(1, len(lines)):
            if lines[close].rstrip("\r") in {"---", "..."}:
                blank(0, close, "frontMatter")
                number = close + 1
                break

    fence: str | None = None
    while number < len(lines):
        line = lines[number]
        fence_match = _FENCE.match(line)
        if fence is not None:
            if fence_match and fence_match.group(1)[0] == fence[0] and len(fence_match.group(1)) >= len(fence):
                fence = None
        elif fence_match:
            fence = fence_match.group(1)
        elif _CONTAINER_OPEN.match(line) or _CONTAINER_CLOSE.match(line):
            blank(number, number, "directive")
        elif _LEAF_DIRECTIVE.match(line):
            last = number
            if "{" in line and "}" not in line[line.index("{") :]:
                while last + 1 < len(lines) and not lines[last].rstrip().endswith("}"):
                    last += 1
            blank(number, last, "directive")
            number = last
        number += 1
    return masked, protected


def _inline_source_span(content: str, lines: list[str], line_starts: list[int], first_line: int) -> tuple[int, int] | None:
    """Map a block's inline content back to its exact span in the source."""
    content_lines = content.split("\n")
    starts: list[int] = []
    ends: list[int] = []
    for offset, content_line in enumerate(content_lines):
        number = first_line + offset
        if number >= len(lines):
            return None
        source_line = lines[number].rstrip("\r")
        wanted = content_line.strip()
        if not wanted:
            continue
        suffix_at = len(source_line.rstrip()) - len(wanted)
        position = suffix_at if suffix_at >= 0 and source_line[suffix_at:].rstrip() == wanted else source_line.find(wanted)
        if position < 0:
            return None
        starts.append(line_starts[number] + position)
        ends.append(line_starts[number] + position + len(wanted))
    if not starts:
        return None
    return starts[0], ends[-1]


# --- sentences ------------------------------------------------------------------

_TERMINATORS = ".!?…"
_CLOSERS = "\"'”’)]*_"
_OPENERS = "\"'“‘([*_`"
_ABBREVIATIONS = frozenset(
    {
        "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "cf", "fig", "figs", "no", "nos",
        "approx", "dept", "est", "mt", "gen", "gov", "sen", "rep", "rev", "lt", "col", "sgt",
        "e.g", "i.e", "a.m", "p.m", "et al", "al", "ca", "vol", "pp", "op", "ed", "eds",
    }
)
_INLINE_MASKS = (
    re.compile(r"(`+)(?:(?!\1).)+?\1", re.S),  # inline code
    re.compile(r"!\[[^\]]*\]\([^)]*\)"),  # images
    re.compile(r"(?<=\])\([^)\s]*(?:\s+\"[^\"]*\")?\)"),  # link destinations
    re.compile(r"\[@[^\]]+\]"),  # citations
    re.compile(r"<[a-z][\w+.-]*:[^>\s]+>", re.I),  # autolinks
    re.compile(r"\bhttps?://\S+"),  # bare URLs
    re.compile(r"\{[^}\n]*\}"),  # inline directive attributes
)


def split_sentences(source: str) -> list[tuple[int, int]]:
    """Sentence spans within ``source`` (a single prose block)."""
    masked = _mask_inline(source)
    spans: list[tuple[int, int]] = []
    start = 0
    index = 0
    length = len(masked)
    while index < length:
        if masked[index] not in _TERMINATORS:
            index += 1
            continue
        end = index
        while end < length and masked[end] in _TERMINATORS:
            end += 1
        while end < length and masked[end] in _CLOSERS:
            end += 1
        if _is_boundary(masked, index, end):
            spans.append(_trim_span(source, start, end))
            start = end
        index = end
    if source[start:].strip():
        spans.append(_trim_span(source, start, length))
    return [span for span in spans if span[0] < span[1]]


def _mask_inline(source: str) -> str:
    masked = source
    for pattern in _INLINE_MASKS:
        masked = pattern.sub(lambda m: "x" * len(m.group(0)), masked)
    return masked


def _is_boundary(masked: str, terminator_at: int, end: int) -> bool:
    if end >= len(masked):
        return True
    if not masked[end].isspace():
        return False
    following = masked[end:].lstrip()
    if not following:
        return True
    starter = following.lstrip(_OPENERS)
    if not starter or not (starter[0].isupper() or starter[0].isdigit()):
        return False
    if masked[terminator_at] == "." and _is_abbreviation(masked[:terminator_at]):
        return False
    return True


def _is_abbreviation(before: str) -> bool:
    word = re.split(r"[\s(\[\"“'‘]", before)[-1]
    if not word:
        return False
    if re.fullmatch(r"[A-Z]", word):  # an initial, as in "J. Smith"
        return True
    if re.fullmatch(r"(?:[A-Za-z]\.)+[A-Za-z]", word):  # U.S, e.g, i.e
        return True
    return word.lower() in _ABBREVIATIONS


# --- plain text ------------------------------------------------------------------

_PLAIN_TEXT_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\\([\\`*_{}\[\]()#+\-.!])"), r"\1"),
    (re.compile(r"!\[([^\]]*)\]\([^)]*\)"), r"\1"),
    (re.compile(r"\[([^\]]+)\]\([^)]*\)"), r"\1"),
    (re.compile(r"\[([^\]]+)\]\[[^\]]*\]"), r"\1"),
    (re.compile(r"\s?\[@[^\]]+\]"), ""),
    (re.compile(r"<([a-z][\w+.-]*:[^>\s]+)>", re.I), r"\1"),
    (re.compile(r":[A-Za-z][\w-]*\[([^\]]*)\](?:\{[^}]*\})?"), r"\1"),
    (re.compile(r"(`+)(.+?)\1", re.S), r"\2"),
    (re.compile(r"(\*\*|__)(.+?)\1", re.S), r"\2"),
    (re.compile(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", re.S), r"\1"),
    (re.compile(r"(?<!\w)_(?!\s)(.+?)(?<!\s)_(?!\w)", re.S), r"\1"),
    (re.compile(r"~~(.+?)~~", re.S), r"\1"),
)

