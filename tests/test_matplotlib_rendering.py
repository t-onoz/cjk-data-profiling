from __future__ import annotations

import warnings
from io import BytesIO

import matplotlib

matplotlib.use("Agg", force=True)

import matplotlib.pyplot as pyplot
import pytest
from matplotlib.figure import Figure

import cjk_data_profiling as module

RENDER_CASES: list[tuple[module.Language, str, str, str]] = [
    ("ja", "\u58f2\u4e0a\u3068\u5229\u76ca", "\u6708", "\u91d1\u984d"),
    ("zh-cn", "\u9500\u552e\u989d\u4e0e\u5229\u6da6", "\u6708\u4efd", "\u91d1\u989d"),
    ("zh-tw", "\u92b7\u552e\u984d\u8207\u5229\u6f64", "\u6708\u4efd", "\u91d1\u984d"),
    ("ko", "\ub9e4\ucd9c\uacfc \uc774\uc775", "\uc6d4", "\uae08\uc561"),
]


def _render_without_missing_glyph_warnings(figure: Figure) -> None:
    buffer = BytesIO()
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "error",
            message=r"Glyph .* missing from font",
            category=UserWarning,
        )
        figure.savefig(buffer, format="png")

    assert buffer.getbuffer().nbytes > 0


@pytest.mark.parametrize(
    ("language", "title", "x_label", "y_label"),
    RENDER_CASES,
    ids=["japanese", "simplified-chinese", "traditional-chinese", "korean"],
)
def test_matplotlib_renders_cjk_axes_legend_and_negative_ticks(
    language: module.Language,
    title: str,
    x_label: str,
    y_label: str,
) -> None:
    try:
        module._find_fonts(language)
    except RuntimeError:
        pytest.skip(f"A CJK font is required for language={language!r}")

    with module.cjk_data_profiling(language):
        figure, axes = pyplot.subplots()
        try:
            axes.plot([-2, -1, 0, 1, 2], label=title)
            axes.set_title(title)
            axes.set_xlabel(x_label)
            axes.set_ylabel(y_label)
            axes.annotate(title, xy=(2, 2), xytext=(0, 1))
            axes.legend()
            _render_without_missing_glyph_warnings(figure)
        finally:
            pyplot.close(figure)


@pytest.mark.parametrize(
    ("language", "title", "x_label", "y_label"),
    RENDER_CASES,
    ids=["japanese", "simplified-chinese", "traditional-chinese", "korean"],
)
def test_matplotlib_renders_cjk_table_and_tick_labels(
    language: module.Language,
    title: str,
    x_label: str,
    y_label: str,
) -> None:
    try:
        module._find_fonts(language)
    except RuntimeError:
        pytest.skip(f"A CJK font is required for language={language!r}")

    with module.cjk_data_profiling(language):
        figure, axes = pyplot.subplots()
        try:
            axes.axis("off")
            axes.set_title(title)
            axes.table(
                cellText=[["-2", "2"], ["-1", "1"]],
                colLabels=[x_label, y_label],
                rowLabels=[title, title],
                loc="center",
            )
            _render_without_missing_glyph_warnings(figure)
        finally:
            pyplot.close(figure)
