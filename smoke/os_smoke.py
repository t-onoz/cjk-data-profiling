from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from wordcloud import WordCloud

from cjk_data_profiling import Language, cjk_data_profiling

OUTPUT_DIR = Path("test_output")

CASES: list[tuple[Language, str]] = [
    ("ja", "日本語 フォント テスト"),
    ("zh-cn", "简体中文 字体 测试"),
    ("zh-tw", "繁體中文 字型 測試"),
    ("ko", "한국어 글꼴 테스트"),
    ("mixed", "日本語 简体中文 繁體中文 한국어 English"),
]


from matplotlib import font_manager


def print_cjk_fonts() -> None:
    keywords = (
        "pingfang",
        "songti",
        "heiti",
        "hiragino",
        "gothic",
        "yahei",
        "jhenghei",
        "malgun",
        "noto",
    )

    for font in font_manager.fontManager.ttflist:
        name = font.name.lower()
        if any(key in name for key in keywords):
            print(font.name, "->", font.fname)


def render_case(language: Language, text: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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


def main() -> None:
    print_cjk_fonts()
    failed: list[tuple[Language, Exception]] = []

    for language, text in CASES:
        try:
            render_case(language, text)
        except Exception as exc:
            print(f"FAILED: {language}: {exc}")
            failed.append((language, exc))

    if failed:
        raise RuntimeError(
            "Smoke test failed for: " + ", ".join(language for language, _ in failed)
        )


if __name__ == "__main__":
    main()
