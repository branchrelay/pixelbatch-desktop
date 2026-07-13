"""Central colour system for PixelBatch."""

from __future__ import annotations


LIGHT_COLORS = {
    "app_bg": "#F6F7FB", "sidebar_bg": "#F0F2F7", "surface": "#FFFFFF",
    "surface_alt": "#F8F9FC", "text_primary": "#1C2230", "text_secondary": "#667085",
    "text_muted": "#98A2B3", "accent": "#6658D9", "accent_hover": "#574AC5",
    "accent_pressed": "#493DB2", "accent_soft": "#E9E7FB", "accent_text": "#5146C7",
    "border": "#D8DCE6", "border_soft": "#E8EAF0", "success": "#2E9B66",
    "success_soft": "#E8F6EF", "warning": "#B7791F", "warning_soft": "#FFF4D6",
    "error": "#C94A4A", "error_soft": "#FDECEC", "info": "#3978C6",
    "info_soft": "#EAF2FC", "disabled_bg": "#ECEEF3", "disabled_text": "#A4A9B3",
}

DARK_COLORS = {
    "app_bg": "#151821", "sidebar_bg": "#1B1F2A", "surface": "#212633",
    "surface_alt": "#282E3C", "text_primary": "#F2F4F7", "text_secondary": "#B8BECA",
    "text_muted": "#858C99", "accent": "#8A7CF2", "accent_hover": "#9A8EF5",
    "accent_pressed": "#8A7CF2", "accent_soft": "#302B52", "accent_text": "#9A8EF5",
    "border": "#394050", "border_soft": "#303644", "success": "#53C58A",
    "success_soft": "#203C31", "warning": "#E1A84B", "warning_soft": "#45371F",
    "error": "#E57373", "error_soft": "#47292E", "info": "#67A4E8",
    "info_soft": "#243A55", "disabled_bg": "#303644", "disabled_text": "#858C99",
}


def color(name: str) -> tuple[str, str]:
    """Return a CustomTkinter light/dark colour tuple."""
    return LIGHT_COLORS[name], DARK_COLORS[name]


APP_BG = color("app_bg")
SIDEBAR_BG = color("sidebar_bg")
SURFACE = color("surface")
SURFACE_ALT = color("surface_alt")
TEXT_PRIMARY = color("text_primary")
TEXT_SECONDARY = color("text_secondary")
TEXT_MUTED = color("text_muted")
ACCENT = color("accent")
ACCENT_HOVER = color("accent_hover")
ACCENT_SOFT = color("accent_soft")
ACCENT_TEXT = color("accent_text")
BORDER = color("border")
ERROR = color("error")
ERROR_SOFT = color("error_soft")
INFO = color("info")
INFO_SOFT = color("info_soft")
WARNING = color("warning")
WARNING_SOFT = color("warning_soft")
