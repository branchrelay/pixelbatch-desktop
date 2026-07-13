from i18n import I18nManager
from theme import DARK_COLORS, LIGHT_COLORS, color


def test_i18n_switches_both_directions_and_falls_back() -> None:
    i18n = I18nManager("ru")
    assert i18n.t("Generate Images") == "Генерация изображений"
    assert i18n.t("unknown.technical.value") == "unknown.technical.value"
    i18n.set_language("en")
    assert i18n.t("Генерация изображений") == "Generate Images"


def test_theme_contains_matching_light_and_dark_tokens() -> None:
    assert set(LIGHT_COLORS) == set(DARK_COLORS)
    assert color("accent") == ("#6658D9", "#8A7CF2")
    assert color("app_bg") == ("#F6F7FB", "#151821")
