from __future__ import annotations

import logging
from typing import Any, cast

import matplotlib
import pytest

import cjk_data_profiling as module


class _MessageCapturingHandler(logging.Handler):
    def __init__(self, messages: list[str]) -> None:
        super().__init__()
        self.messages = messages

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


def test_find_fonts_preserves_candidate_order_and_deduplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    paths = {
        "Meiryo": "/fonts/meiryo.ttf",
        "Noto Sans CJK JP": "/fonts/noto-cjk-jp.ttf",
        "DejaVu Sans": "/fonts/dejavu.ttf",
    }
    monkeypatch.setattr(module, "_find_font", paths.get)

    families, wordcloud_font_path = module._find_fonts("ja")

    assert families == ["Meiryo", "Noto Sans CJK JP", "DejaVu Sans"]
    assert wordcloud_font_path == "/fonts/meiryo.ttf"


@pytest.mark.parametrize("language", ["ja", "zh-cn", "zh-tw", "ko"])
def test_find_fonts_uses_first_available_cjk_font_for_wordcloud(
    language: module.Language,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_family = module.FONT_CANDIDATES[language][0]
    expected_path = f"/fonts/{language}.ttf"
    monkeypatch.setattr(
        module,
        "_find_font",
        lambda family: expected_path if family == expected_family else None,
    )

    families, wordcloud_font_path = module._find_fonts(language)

    assert families == [expected_family]
    assert wordcloud_font_path == expected_path


def test_find_fonts_rejects_non_cjk_matplotlib_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        module,
        "_find_font",
        lambda family: "/fonts/DejaVuSans.ttf" if family == "DejaVu Sans" else None,
    )

    with pytest.raises(RuntimeError, match="No suitable font"):
        module._find_fonts("ja")


def test_context_applies_and_restores_global_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        module, "_find_fonts", lambda language: (["Test CJK"], "/test.ttf")
    )
    original_validator = matplotlib.rcParams.validate["font.sans-serif"]
    original_sans_serif = list(matplotlib.rcParams["font.sans-serif"])
    original_unicode_minus = matplotlib.rcParams["axes.unicode_minus"]
    original_wordcloud_font_path = module.wordcloud_module.FONT_PATH

    with module.cjk_data_profiling("ja"):
        assert matplotlib.rcParams["font.sans-serif"][0] == "Test CJK"
        assert matplotlib.rcParams["axes.unicode_minus"] is False
        assert module.wordcloud_module.FONT_PATH == "/test.ttf"

    assert matplotlib.rcParams.validate["font.sans-serif"] is original_validator
    assert matplotlib.rcParams["font.sans-serif"] == original_sans_serif
    assert matplotlib.rcParams["axes.unicode_minus"] == original_unicode_minus
    assert original_wordcloud_font_path == module.wordcloud_module.FONT_PATH


def test_context_restores_settings_after_body_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        module, "_find_fonts", lambda language: (["Test CJK"], "/test.ttf")
    )
    original_wordcloud_font_path = module.wordcloud_module.FONT_PATH

    with pytest.raises(ValueError, match="expected"), module.cjk_data_profiling("ja"):
        raise ValueError("expected")

    assert original_wordcloud_font_path == module.wordcloud_module.FONT_PATH


def test_context_restores_settings_after_setup_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        module, "_find_fonts", lambda language: (["Test CJK"], "/test.ttf")
    )
    original_validator = matplotlib.rcParams.validate["font.sans-serif"]
    original_wordcloud_font_path = module.wordcloud_module.FONT_PATH
    rc_params_type = type(matplotlib.rcParams)
    original_setitem = cast(Any, rc_params_type.__setitem__)

    def failing_setitem(self: Any, key: str, value: Any) -> None:
        if key == "font.sans-serif":
            raise RuntimeError("setting failed")
        original_setitem(self, key, value)

    monkeypatch.setattr(rc_params_type, "__setitem__", failing_setitem)

    with (
        pytest.raises(RuntimeError, match="setting failed"),
        module.cjk_data_profiling("ja"),
    ):
        pytest.fail("The context body must not run after setup failure")

    assert matplotlib.rcParams.validate["font.sans-serif"] is original_validator
    assert original_wordcloud_font_path == module.wordcloud_module.FONT_PATH


def test_nested_context_restores_outer_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    font_settings = {
        "ja": (["Japanese Test"], "/ja.ttf"),
        "ko": (["Korean Test"], "/ko.ttf"),
    }
    monkeypatch.setattr(module, "_find_fonts", font_settings.__getitem__)

    with module.cjk_data_profiling("ja"):
        assert matplotlib.rcParams["font.sans-serif"][0] == "Japanese Test"
        assert module.wordcloud_module.FONT_PATH == "/ja.ttf"

        with module.cjk_data_profiling("ko"):
            assert matplotlib.rcParams["font.sans-serif"][0] == "Korean Test"
            assert module.wordcloud_module.FONT_PATH == "/ko.ttf"

        assert matplotlib.rcParams["font.sans-serif"][0] == "Japanese Test"
        assert module.wordcloud_module.FONT_PATH == "/ja.ttf"


def test_context_rejects_missing_matplotlib_validator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        module, "_find_fonts", lambda language: (["Test CJK"], "/test.ttf")
    )
    original_wordcloud_font_path = module.wordcloud_module.FONT_PATH
    monkeypatch.delitem(matplotlib.rcParams.validate, "font.sans-serif")

    with (
        pytest.raises(RuntimeError, match=r"font\.sans-serif.*validator"),
        module.cjk_data_profiling("ja"),
    ):
        pytest.fail("The context body must not run without a validator")

    assert original_wordcloud_font_path == module.wordcloud_module.FONT_PATH


def test_noto_sans_jp_weight_warning_filter_is_scoped() -> None:
    messages: list[str] = []
    logger = logging.getLogger("matplotlib.font_manager")
    handler = _MessageCapturingHandler(messages)
    logger.addHandler(handler)

    suppressed_message = (
        "findfont: Failed to find font weight normal for Noto Sans JP, now using 100."
    )
    other_message = "findfont: unrelated warning"

    try:
        with module._suppress_noto_sans_jp_weight_warning():
            logger.warning(suppressed_message)
            logger.warning(other_message)

        logger.warning(suppressed_message)
    finally:
        logger.removeHandler(handler)

    assert messages == [other_message, suppressed_message]


@pytest.mark.integration
@pytest.mark.parametrize("profiling_module", ["ydata_profiling", "data_profiling"])
def test_profile_report_generates_cjk_html(profiling_module: str) -> None:
    pandas = pytest.importorskip("pandas")
    profiling = pytest.importorskip(profiling_module)

    try:
        module._find_fonts("ja")
    except RuntimeError:
        pytest.skip("A Japanese CJK font is required for this integration test")

    dataframe = pandas.DataFrame({"city": ["東京", "大阪", "東京"]})

    with module.cjk_data_profiling("ja"):
        report = profiling.ProfileReport(
            dataframe,
            minimal=True,
            vars={"cat": {"words": True, "characters": True}},
        )
        html = report.to_html()

    assert "東京" in html
