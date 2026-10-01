"""CJK font compatibility patch for data-profiling reports."""

from __future__ import annotations

import logging
from collections.abc import Callable, Generator
from contextlib import contextmanager
from importlib import import_module
from types import ModuleType
from typing import Any, Literal, Protocol, cast

import matplotlib
import wordcloud.wordcloud as wordcloud_module
from matplotlib import font_manager

Language = Literal["ja", "zh-cn", "zh-tw", "ko", "mixed"]


FONT_CANDIDATES: dict[Language, list[str]] = {
    "ja": [
        "Meiryo",
        "Yu Gothic",
        "Hiragino Sans",
        "Noto Sans CJK JP",
        "Noto Sans JP",
        "IPAexGothic",
    ],
    "zh-cn": [
        "Microsoft YaHei",
        "PingFang SC",
        "Heiti SC",
        "Hiragino Sans GB",
        "Songti SC",
        "Noto Sans CJK SC",
        "Noto Sans SC",
    ],
    "zh-tw": [
        "Microsoft JhengHei",
        "PingFang TC",
        "Heiti TC",
        "Songti TC",
        "Noto Sans CJK TC",
        "Noto Sans TC",
    ],
    "ko": [
        "Malgun Gothic",
        "Apple SD Gothic Neo",
        "Noto Sans CJK KR",
        "Noto Sans KR",
    ],
    # A mixed-language WordCloud needs a single font with CJK-wide coverage.
    # Do not fall back to a language-specific system font here: it can render
    # part of the text as tofu characters.
    "mixed": [
        "Noto Sans CJK JP",
        "Noto Sans CJK SC",
        "Noto Sans CJK TC",
        "Noto Sans CJK KR",
    ],
}


# Matplotlib can fall back across multiple fonts.
# Put these after the language-specific fonts for mixed-language text.
# These are CJK-capable fallbacks.  At least one of these or a language-specific
# candidate must be present: WordCloud has no multi-font fallback mechanism.
CJK_FALLBACKS = [
    "Noto Sans CJK JP",
    "Noto Sans CJK SC",
    "Noto Sans CJK TC",
    "Noto Sans CJK KR",
]


# These can be useful to Matplotlib for non-CJK text, but must not make CJK
# font discovery appear successful.
MATPLOTLIB_FINAL_FALLBACKS = [
    "Arial Unicode MS",
    "DejaVu Sans",
]


FontValidator = Callable[..., list[str]]


class _ReportStructureModule(Protocol):
    slugify: Callable[..., str]


def _dom_id_slugify(value: object) -> str:
    """Encode a column name losslessly for use in a DOM identifier."""

    return str(value).encode("utf-8").hex()


def _report_structure_module() -> ModuleType | None:
    """Return the installed profiling package's report-structure module.

    ``fg-data-profiling`` exposes this module as ``data_profiling``. Older
    ``ydata-profiling`` releases expose the same structure from
    ``ydata_profiling`` instead. Current fg-data-profiling installations may
    ship a compatibility ``ydata_profiling`` shim, so prefer the fg module and
    avoid importing that deprecated shim when it is not needed.
    """

    module_names = (
        "data_profiling.report.structure.report",
        "ydata_profiling.report.structure.report",
    )
    for module_name in module_names:
        try:
            return import_module(module_name)
        except ModuleNotFoundError as error:
            # Only treat the target profiling package being absent as optional.
            # A missing dependency inside an installed package remains an error.
            if module_name.startswith(f"{error.name}."):
                continue
            raise
    return None


@contextmanager
def _patch_report_slugify() -> Generator[None, None, None]:
    """Temporarily make report-structure DOM IDs collision-free.

    This intentionally changes only the ``slugify`` reference imported by the
    report-structure module. It does not modify the profiling package's
    dataframe helper, which is also used for non-DOM identifiers.
    """

    report_module = _report_structure_module()
    if report_module is None:
        yield
        return

    slugify_module = cast(_ReportStructureModule, report_module)
    original_slugify = slugify_module.slugify
    if not callable(original_slugify):
        raise RuntimeError("The profiling report module has no callable slugify.")

    slugify_module.slugify = _dom_id_slugify
    try:
        yield
    finally:
        slugify_module.slugify = original_slugify


class _NotoSansJPWeightWarningFilter(logging.Filter):
    """Suppress Matplotlib's harmless variable-font weight warning."""

    _MESSAGE_PREFIX = (
        "findfont: Failed to find font weight normal for Noto Sans JP, now using "
    )

    def filter(self, record: logging.LogRecord) -> bool:
        return not record.getMessage().startswith(self._MESSAGE_PREFIX)


@contextmanager
def _suppress_noto_sans_jp_weight_warning() -> Generator[None, None, None]:
    """Suppress only Noto Sans JP's known, non-fatal weight warning."""

    logger = logging.getLogger("matplotlib.font_manager")
    warning_filter = _NotoSansJPWeightWarningFilter()
    logger.addFilter(warning_filter)
    try:
        yield
    finally:
        logger.removeFilter(warning_filter)


def _find_font(family: str) -> str | None:
    try:
        return font_manager.findfont(
            family,
            fallback_to_default=False,
        )
    except ValueError:
        return None


def _find_fonts(language: Language) -> tuple[list[str], str]:
    """Return Matplotlib font families and a font path for WordCloud."""

    families: list[str] = []
    wordcloud_font_path: str | None = None

    cjk_candidates = [
        *FONT_CANDIDATES[language],
        *CJK_FALLBACKS,
    ]

    # Some Noto Sans JP variable-font distributions report a default weight of
    # 100. Matplotlib still resolves them correctly, but logs a non-fatal
    # warning while probing candidates.
    with _suppress_noto_sans_jp_weight_warning():
        for family in cjk_candidates:
            if family in families:
                continue

            path = _find_font(family)
            if path is None:
                continue

            families.append(family)

            # WordCloud can use only one font, so use the first CJK-capable font.
            if wordcloud_font_path is None:
                wordcloud_font_path = path

        for family in MATPLOTLIB_FINAL_FALLBACKS:
            if family in families:
                continue

            if _find_font(family) is not None:
                families.append(family)

    if wordcloud_font_path is None:
        raise RuntimeError(f"No suitable font was found for language={language!r}.")

    return families, wordcloud_font_path


@contextmanager
def cjk_data_profiling(language: Language) -> Generator[None, None, None]:
    """Temporarily enable CJK fonts for data-profiling plots.

    This works around data-profiling overriding Matplotlib's
    ``font.sans-serif`` setting internally.

    It also temporarily replaces the profiling report module's ``slugify``
    reference so interaction DOM IDs remain unique for CJK and other column
    names that would otherwise collide.

    WordCloud's default font is also temporarily replaced.
    Explicit ``font_path`` arguments passed to WordCloud still take
    precedence.

    Matplotlib and WordCloud settings are process-global, so concurrent use
    from multiple threads in the same process is not supported.
    """
    if language not in FONT_CANDIDATES:
        raise ValueError(f"Unsupported language: {language!r}")
    families, wordcloud_font_path = _find_fonts(language)
    validators = cast(dict[str, FontValidator], matplotlib.rcParams.validate)

    if "font.sans-serif" not in validators:
        raise RuntimeError(
            "The installed Matplotlib version does not expose the expected "
            "'font.sans-serif' validator."
        )

    original_validator = validators["font.sans-serif"]
    original_sans_serif = list(matplotlib.rcParams["font.sans-serif"])
    original_unicode_minus = matplotlib.rcParams["axes.unicode_minus"]
    original_wordcloud_font_path = cast(str, wordcloud_module.FONT_PATH)

    def validate_font_sans_serif(value: Any) -> list[str]:
        requested = original_validator(value)

        return [
            *families,
            *(font for font in requested if font not in families),
        ]

    try:
        validators["font.sans-serif"] = validate_font_sans_serif
        wordcloud_module.FONT_PATH = wordcloud_font_path

        # Apply the patched validator to the current setting as well.
        matplotlib.rcParams["font.sans-serif"] = original_sans_serif
        # Several CJK system fonts omit U+2212.  Use ASCII hyphen for negative
        # tick labels while the CJK compatibility patch is active.
        # related: https://github.com/matplotlib/matplotlib/issues/27838
        matplotlib.rcParams["axes.unicode_minus"] = False
        with _patch_report_slugify():
            yield
    finally:
        # Restore the validator before restoring rcParams.  Nested finally
        # blocks ensure a failed restoration cannot skip a later one.
        try:
            validators["font.sans-serif"] = original_validator
        finally:
            try:
                try:
                    matplotlib.rcParams["font.sans-serif"] = original_sans_serif
                finally:
                    matplotlib.rcParams["axes.unicode_minus"] = original_unicode_minus
            finally:
                wordcloud_module.FONT_PATH = original_wordcloud_font_path
