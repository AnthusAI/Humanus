"""Language packs: what Humanus knows about reading one language.

A language pack is data shipped inside Humanus, one per language: how
sentences end, what counts as a unit of length, how phrases match, which
quotation marks enclose someone else's words, which built-in checks the
language can run, its word classes, its native baseline rates and its
typography. The engine asks the language for all of these and holds no
language knowledge of its own.

A regional variant (``es-419``) is a small overlay on its base pack (``es``):
only what differs (quotation marks, number forms) is written down. A request
names the variant it wants; the base pack means the base language and is
never a silent substitute for a variant Humanus does not have.

Every check request states the language of its content. A language with no
pack is refused (:class:`UnsupportedLanguageError`); it is never read as if it
were another language.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import cached_property, lru_cache
from importlib import resources
from typing import Any, Mapping

import yaml


class UnsupportedLanguageError(LookupError):
    """No language pack serves the requested language tag."""

    def __init__(self, tag: str) -> None:
        self.tag = tag
        super().__init__(
            f"Humanus has no language pack for '{tag}', so it cannot check text in that language. "
            f"Supported: {', '.join(list_languages())}"
        )


class LanguageCannotRun(Exception):
    """A detector needs something this language pack does not provide; the reason is reported, not hidden."""


@dataclass(frozen=True, eq=False)
class Language:
    tag: str
    version: str
    name: str
    base: str | None  # for a regional variant (es-419), the tag of the base language pack (es) it overlays
    aliases: tuple[str, ...]
    phrase_matching: str  # word | substring
    unit: str  # the name of the unit lengths are counted in: word | character
    unit_pattern: str
    terminators: str
    spaced_terminators: str
    closers: str
    openers: str
    capital_after: bool
    abbreviation_openers: str
    abbreviations: frozenset[str]
    quotations: tuple[tuple[str, str], ...]
    builtins: frozenset[str]
    lexicons: Mapping[str, tuple[str, ...]]
    tagger: str | None
    baseline: Mapping[str, Any]
    typography: Mapping[str, Any]

    @cached_property
    def _units(self) -> re.Pattern[str]:
        return re.compile(self.unit_pattern)

    def units(self, text: str) -> list[str]:
        """The units of length in ``text``: words, or characters for a language written without spaces."""
        return self._units.findall(text)

    def unit_spans(self, text: str) -> list[tuple[str, int, int]]:
        return [(m.group(), m.start(), m.end()) for m in self._units.finditer(text)]

    @cached_property
    def quotation_pattern(self) -> re.Pattern[str]:
        alternatives = []
        for opening, closing in self.quotations:
            o, c = re.escape(opening), re.escape(closing)
            alternatives.append(f"{o}[^{o}\\n]+{c}" if opening == closing else f"{o}[^{o}{c}]+{c}")
        return re.compile("|".join(alternatives))

    def phrase_pattern(self, phrases: tuple[str, ...], case_sensitive: bool = False) -> re.Pattern[str]:
        """A pattern for any of ``phrases``, matched the language's way (see :func:`phrase_pattern`)."""
        return phrase_pattern(tuple(phrases), case_sensitive, self.phrase_matching)

    def lexicon(self, name: str) -> tuple[str, ...]:
        if name not in self.lexicons:
            raise LanguageCannotRun(f"the {self.tag} language pack has no word class '{name}'")
        return self.lexicons[name]

    def require_tagger(self) -> str:
        if not self.tagger:
            raise LanguageCannotRun(f"the {self.tag} language pack has no part-of-speech tagger, so word classes by tag are unavailable")
        return self.tagger

    def typography_data(self, *keys: str) -> tuple[Any, ...]:
        missing = [key for key in keys if key not in self.typography]
        if missing:
            raise LanguageCannotRun(f"the {self.tag} language pack has no typography data for {', '.join(missing)}")
        return tuple(self.typography[key] for key in keys)


@lru_cache(maxsize=512)
def phrase_pattern(phrases: tuple[str, ...], case_sensitive: bool, mode: str) -> re.Pattern[str]:
    """``word`` mode: a phrase stands on word boundaries, its words separated by any white space.
    ``substring`` mode, for scripts written without spaces: a phrase matches anywhere, white space optional."""
    gap = r"\s+" if mode == "word" else r"\s*"
    alternatives = sorted((gap.join(map(re.escape, p.split())) for p in phrases), key=len, reverse=True)
    body = f"(?:{'|'.join(alternatives)})"
    flags = 0 if case_sensitive else re.IGNORECASE
    return re.compile(rf"(?<!\w){body}(?!\w)" if mode == "word" else body, flags)


def list_languages() -> list[str]:
    """Tags of the shipped language packs, e.g. ``["en", "es", "zh-Hans"]``."""
    return sorted(
        (entry.name.removesuffix(".yml") for entry in resources.files(__name__).iterdir() if entry.name.endswith(".yml")),
        key=str.lower,
    )


def resolve_language(tag: str) -> Language:
    """The language pack that serves BCP 47 ``tag``.

    The tag must name a pack's tag or one of its documented aliases exactly
    (case-insensitively): ``zh-CN`` is an alias of ``zh-Hans`` because
    mainland Chinese is written in Simplified characters. Nothing else is
    guessed: ``es-AR`` is not read as ``es`` or ``es-419``, and ``zh-TW`` is
    not read as ``zh-Hans``; both are refused until a pack serves them.
    """
    name = _index().get(tag.strip().lower())
    if name is None:
        raise UnsupportedLanguageError(tag)
    return _load(name)


@lru_cache(maxsize=1)
def _index() -> dict[str, str]:
    index: dict[str, str] = {}
    for tag in list_languages():
        language = _load(tag)
        for name in (language.tag, *language.aliases):
            index[name.lower()] = tag
    return index


def _read(tag: str) -> dict[str, Any]:
    return yaml.safe_load(resources.files(__name__).joinpath(f"{tag}.yml").read_text(encoding="utf-8"))


def _overlay(base: Mapping[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    """``base`` with ``overlay`` laid over it: mappings merge key by key, any other value replaces, null removes."""
    merged = dict(base)
    for key, value in overlay.items():
        if value is None:
            merged.pop(key, None)
        elif isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _overlay(merged[key], value)
        else:
            merged[key] = value
    return merged


@lru_cache(maxsize=None)
def _load(tag: str) -> Language:
    raw = _read(tag)
    base = raw.pop("base", None)
    if base is not None:
        # A regional variant is small overlay data on its base language's pack, never a copy.
        base_raw = _read(base)
        base_raw.pop("aliases", None)
        raw = _overlay(base_raw, raw)
    segmentation = raw["segmentation"]
    return Language(
        tag=raw["tag"],
        version=raw["version"],
        name=raw["name"],
        base=base,
        aliases=tuple(raw.get("aliases", ())),
        phrase_matching=raw["phraseMatching"],
        unit=raw["units"]["name"],
        unit_pattern=raw["units"]["pattern"],
        terminators=segmentation["terminators"],
        spaced_terminators=segmentation["spacedTerminators"],
        closers=segmentation["closers"],
        openers=segmentation["openers"],
        capital_after=segmentation["capitalAfter"],
        abbreviation_openers=segmentation["abbreviationOpeners"],
        abbreviations=frozenset(segmentation["abbreviations"]),
        quotations=tuple((pair[0], pair[1]) for pair in raw["quotations"]),
        builtins=frozenset(raw["builtins"]),
        lexicons={name: tuple(words) for name, words in raw["lexicons"].items()},
        tagger=raw["tagger"],
        baseline=raw["baseline"],
        typography=raw["typography"],
    )
