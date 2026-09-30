from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pytest
from wordcloud import WordCloud

from cjk_data_profiling import Language, cjk_data_profiling

CASES: list[tuple[Language, str]] = [
    ("ja", "日本語 フォント テスト"),
    ("zh-cn", "简体中文 字体 测试"),
    ("zh-tw", "繁體中文 字型 測試"),
    ("ko", "한국어 글꼴 테스트"),
    ("mixed", "日本語 简体中文 繁體中文 한국어 English"),
]

OUTPUT_DIR = Path("test_output")


@pytest.mark.parametrize(("language", "text"), CASES)
def test_os_smoke(language: Language, text: str) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)

    with cjk_data_profiling(language):
        fig, ax = plt.subplots(figsize=(6, 3))
        ax.set_title(text)
        ax.plot([-1, 0, 1], [-1, 0, 1])
        fig.savefig(
            OUTPUT_DIR / f"matplotlib-{language}.png",
            dpi=120,
            bbox_inches="tight",
        )
        plt.close(fig)

        cloud = WordCloud(
            width=600,
            height=300,
            background_color="white",
        )
        cloud.generate_from_frequencies({text: 1})
        cloud.to_file(str(OUTPUT_DIR / f"wordcloud-{language}.png"))
