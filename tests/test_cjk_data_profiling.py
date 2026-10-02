from __future__ import annotations

import logging
from contextlib import contextmanager
from types import ModuleType
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


@pytest.mark.parametrize("value", ["a b", "a-b", "温度", "湿度"])
def test_dom_id_slugify_is_non_empty_and_distinct(value: str) -> None:
    encoded_values = {
        module._dom_id_slugify(column)
        for column in ("a b", "a-b", "温度", "湿度")
    }

    assert module._dom_id_slugify(value)
    assert len(encoded_values) == 4


def test_report_structure_module_falls_back_to_ydata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ydata_report = ModuleType("ydata_report")
    requested_modules: list[str] = []

    def import_only_ydata(module_name: str) -> ModuleType:
        requested_modules.append(module_name)
        if module_name.startswith("data_profiling"):
            error = ModuleNotFoundError()
            error.name = "data_profiling"
            raise error
        return ydata_report

    monkeypatch.setattr(module, "import_module", import_only_ydata)

    assert module._report_structure_module() is ydata_report
    assert requested_modules == [
        "data_profiling.report.structure.report",
        "ydata_profiling.report.structure.report",
    ]


def test_report_slugify_patch_is_scoped_and_restored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_module = cast(Any, ModuleType("report"))

    def original_slugify(value: object) -> str:
        return f"original-{value}"

    report_module.slugify = original_slugify
    monkeypatch.setattr(module, "_report_structure_module", lambda: report_module)

    with module._patch_report_slugify():
        assert report_module.slugify("温度") == "e6b8a9e5baa6"

        with module._patch_report_slugify():
            assert report_module.slugify("湿度") == "e6b9bfe5baa6"

        assert report_module.slugify("温度") == "e6b8a9e5baa6"

    assert report_module.slugify is original_slugify


def test_report_slugify_patch_restores_after_body_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report_module = cast(Any, ModuleType("report"))

    def original_slugify(value: object) -> str:
        return str(value)

    report_module.slugify = original_slugify
    monkeypatch.setattr(module, "_report_structure_module", lambda: report_module)

    with pytest.raises(ValueError, match="expected"), module._patch_report_slugify():
        raise ValueError("expected")

    assert report_module.slugify is original_slugify


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


@pytest.mark.parametrize(
    ("options", "matplotlib_enabled", "wordcloud_enabled", "slugify_enabled"),
    [
        ({"enable_matplotlib": False}, False, True, True),
        ({"enable_wordcloud": False}, True, False, True),
        ({"enable_slugify": False}, True, True, False),
    ],
)
def test_context_can_disable_each_patch_independently(
    monkeypatch: pytest.MonkeyPatch,
    options: dict[str, bool],
    matplotlib_enabled: bool,
    wordcloud_enabled: bool,
    slugify_enabled: bool,
) -> None:
    monkeypatch.setattr(
        module, "_find_fonts", lambda language: (["Test CJK"], "/test.ttf")
    )
    report_module = cast(Any, ModuleType("report"))

    def original_slugify(value: object) -> str:
        return f"original-{value}"

    report_module.slugify = original_slugify
    monkeypatch.setattr(module, "_report_structure_module", lambda: report_module)

    original_validator = matplotlib.rcParams.validate["font.sans-serif"]
    original_sans_serif = list(matplotlib.rcParams["font.sans-serif"])
    original_unicode_minus = matplotlib.rcParams["axes.unicode_minus"]
    original_wordcloud_font_path = module.wordcloud_module.FONT_PATH

    with module.cjk_data_profiling("ja", **options):
        assert (matplotlib.rcParams["font.sans-serif"][0] == "Test CJK") is (
            matplotlib_enabled
        )
        assert matplotlib.rcParams["axes.unicode_minus"] == (
            False if matplotlib_enabled else original_unicode_minus
        )
        assert (module.wordcloud_module.FONT_PATH == "/test.ttf") is wordcloud_enabled
        assert (report_module.slugify("x") == "78") is slugify_enabled

    assert matplotlib.rcParams.validate["font.sans-serif"] is original_validator
    assert matplotlib.rcParams["font.sans-serif"] == original_sans_serif
    assert matplotlib.rcParams["axes.unicode_minus"] == original_unicode_minus
    assert original_wordcloud_font_path == module.wordcloud_module.FONT_PATH
    assert report_module.slugify is original_slugify


def test_context_with_all_patches_disabled_skips_external_lookups(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_lookup(*args: object, **kwargs: object) -> None:
        raise AssertionError("patch lookup should not run")

    monkeypatch.setattr(module, "_find_fonts", unexpected_lookup)
    monkeypatch.setattr(module, "_report_structure_module", unexpected_lookup)

    original_validator = matplotlib.rcParams.validate["font.sans-serif"]
    original_sans_serif = list(matplotlib.rcParams["font.sans-serif"])
    original_unicode_minus = matplotlib.rcParams["axes.unicode_minus"]
    original_wordcloud_font_path = module.wordcloud_module.FONT_PATH

    with module.cjk_data_profiling(
        "ja",
        enable_matplotlib=False,
        enable_wordcloud=False,
        enable_slugify=False,
    ):
        pass

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


def test_context_restores_matplotlib_when_wordcloud_setup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        module, "_find_fonts", lambda language: (["Test CJK"], "/test.ttf")
    )
    original_validator = matplotlib.rcParams.validate["font.sans-serif"]
    original_sans_serif = list(matplotlib.rcParams["font.sans-serif"])
    original_unicode_minus = matplotlib.rcParams["axes.unicode_minus"]

    @contextmanager
    def failing_wordcloud_patch(font_path: str):
        raise RuntimeError("WordCloud setup failed")
        yield

    monkeypatch.setattr(module, "_patch_wordcloud", failing_wordcloud_patch)

    with (
        pytest.raises(RuntimeError, match="WordCloud setup failed"),
        module.cjk_data_profiling("ja"),
    ):
        pytest.fail("The context body must not run after setup failure")

    assert matplotlib.rcParams.validate["font.sans-serif"] is original_validator
    assert matplotlib.rcParams["font.sans-serif"] == original_sans_serif
    assert matplotlib.rcParams["axes.unicode_minus"] == original_unicode_minus


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
