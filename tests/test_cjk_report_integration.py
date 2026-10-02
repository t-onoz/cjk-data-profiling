from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import pytest
from fontTools.ttLib import (  # type: ignore[import-untyped]
    TTCollection,
    TTFont,
    TTLibFileIsCollectionError,
)
from wordcloud import WordCloud  # type: ignore[reportMissingImports]

import cjk_data_profiling as module

REPORT_OUTPUT_DIRECTORY = Path("test_output/integration-reports")
INTERACTION_COLUMNS = ("a b", "a-b", "\u6e29\u5ea6", "\u6e7f\u5ea6")

CJK_CASES: list[tuple[module.Language, str, tuple[str, str, str]]] = [
    (
        "ja",
        "\u6771\u4eac \u5927\u962a \u4eac\u90fd \u9ad9 \ufa11",
        ("\u58f2\u4e0a", "\u5229\u76ca", "\u9867\u5ba2\u6570"),
    ),
    (
        "zh-cn",
        "\u5317\u4eac \u4e0a\u6d77 \u5e7f\u5dde \u6c49\u5b57 \u6570\u636e",
        ("\u9500\u552e\u989d", "\u5229\u6da6", "\u5ba2\u6237\u6570"),
    ),
    (
        "zh-tw",
        "\u81fa\u5317 \u9ad8\u96c4 \u53f0\u7063 \u6f22\u5b57 \u8cc7\u6599",
        ("\u92b7\u552e\u984d", "\u5229\u6f64", "\u5ba2\u6236\u6578"),
    ),
    (
        "ko",
        "\uc11c\uc6b8 \ubd80\uc0b0 \ub300\uad6c \ud55c\uae00 \ub370\uc774\ud130",
        ("\ub9e4\ucd9c", "\uc774\uc775", "\uace0\uac1d\uc218"),
    ),
    (
        "mixed",
        "\u6771\u4eac \u5317\u4eac \uc11c\uc6b8 \ud55c\uae00 \u6570\u636e",
        ("\u58f2\u4e0a", "\u9500\u552e\u989d", "\ub9e4\ucd9c"),
    ),
]


def _font_codepoints(font_path: str) -> set[int]:
    try:
        font = TTFont(font_path)
    except TTLibFileIsCollectionError:
        # WordCloud opens a TrueType Collection with its default font index (0).
        font = TTCollection(font_path).fonts[0]

    cmap = cast(Any, font["cmap"])
    return {
        codepoint
        for table in cmap.tables
        if table.isUnicode()
        for codepoint in table.cmap
    }


def _wordcloud_font_path(language: module.Language, text: str) -> str:
    try:
        _, font_path = module._find_fonts(language)
    except RuntimeError:
        pytest.skip(f"A CJK font is required for language={language!r}")

    missing_characters = [
        character
        for character in text
        if not character.isspace() and ord(character) not in _font_codepoints(font_path)
    ]
    assert not missing_characters, "The WordCloud font lacks glyphs for: " + "".join(
        missing_characters
    )
    return font_path


@pytest.mark.parametrize(
    ("language", "text", "numeric_columns"),
    CJK_CASES,
    ids=[
        "japanese",
        "simplified-chinese",
        "traditional-chinese",
        "korean",
        "mixed-cjk",
    ],
)
def test_wordcloud_font_covers_cjk_text(
    language: module.Language,
    text: str,
    numeric_columns: tuple[str, str, str],
) -> None:
    _wordcloud_font_path(language, text)


@pytest.mark.integration
@pytest.mark.parametrize("profiling_module", ["ydata_profiling", "data_profiling"])
@pytest.mark.parametrize(
    ("language", "text", "numeric_columns"),
    CJK_CASES,
    ids=[
        "japanese",
        "simplified-chinese",
        "traditional-chinese",
        "korean",
        "mixed-cjk",
    ],
)
def test_profile_report_renders_cjk_text(
    profiling_module: str,
    language: module.Language,
    text: str,
    numeric_columns: tuple[str, str, str],
) -> None:
    pandas = pytest.importorskip("pandas")
    profiling = pytest.importorskip(profiling_module)
    wordcloud_font_path = _wordcloud_font_path(language, text)

    values = list(range(1, 31))
    dataframe = pandas.DataFrame(
        {
            numeric_columns[0]: values,
            numeric_columns[1]: [value * 2 + value % 3 for value in values],
            numeric_columns[2]: [value * 3 - value % 5 for value in values],
            "CJK text": [text] * len(values),
        }
    )
    REPORT_OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_OUTPUT_DIRECTORY / f"{profiling_module}-{language}.html"
    wordcloud_path = REPORT_OUTPUT_DIRECTORY / f"{profiling_module}-{language}.png"

    with module.cjk_data_profiling(language):
        report = profiling.ProfileReport(
            dataframe,
            title=f"CJK font integration check: {language}",
            vars={"cat": {"words": True, "characters": True}},
            correlations={"pearson": {"calculate": True}},
            interactions={"continuous": False},
        )
        report.to_file(report_path)
        WordCloud(
            width=800,
            height=400,
            background_color="white",
            font_path=wordcloud_font_path,
        ).generate(" ".join([text] * len(values))).to_file(wordcloud_path)

    html = report_path.read_text(encoding="utf-8")
    assert text in html
    assert all(column in html for column in numeric_columns)
    assert wordcloud_path.is_file()


@pytest.mark.integration
@pytest.mark.parametrize("profiling_module", ["ydata_profiling", "data_profiling"])
def test_profile_report_has_unique_interaction_selectors(
    profiling_module: str,
) -> None:
    """Generate an inspectable report for CJK and colliding interaction columns."""

    pandas = pytest.importorskip("pandas")
    profiling = pytest.importorskip(profiling_module)

    try:
        module._find_fonts("ja")
    except RuntimeError:
        pytest.skip("A Japanese CJK font is required for this integration test")

    values = list(range(1, 31))
    dataframe = pandas.DataFrame(
        {
            "a b": values,
            "a-b": [value * 2 + value % 3 for value in values],
            "\u6e29\u5ea6": [value * 3 - value % 5 for value in values],
            "\u6e7f\u5ea6": [value * 5 + value % 7 for value in values],
        }
    )
    REPORT_OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    report_path = (
        REPORT_OUTPUT_DIRECTORY / f"{profiling_module}-interaction-selectors.html"
    )

    with module.cjk_data_profiling("ja"):
        report = profiling.ProfileReport(
            dataframe,
            title="CJK interaction selector integration check",
            interactions={"continuous": True, "targets": list(INTERACTION_COLUMNS)},
        )
        report.to_file(report_path)

    html = report_path.read_text(encoding="utf-8")
    expected_anchor_ids = {
        f"interactions_{module._dom_id_slugify(x_column)}"
        for x_column in INTERACTION_COLUMNS
    }
    expected_anchor_ids.update(
        f"interactions_{module._dom_id_slugify(x_column)}_"
        f"{module._dom_id_slugify(y_column)}"
        for x_column in INTERACTION_COLUMNS
        for y_column in INTERACTION_COLUMNS
    )

    assert all(column in html for column in INTERACTION_COLUMNS)
    assert expected_anchor_ids <= {
        match.group(0)
        for match in re.finditer(r"interactions_[0-9a-f_]+", html)
    }
    assert len(expected_anchor_ids) == 20
