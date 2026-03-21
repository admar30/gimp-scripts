#!/usr/bin/env python3
"""
Centralized theme tokens and ttk style setup for Guidecut UI.
"""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk


COLORS = {
    "bg.app": "#DCE8EA",
    "bg.panel": "#EAF2F3",
    "bg.input": "#F2F8F8",
    "bg.tooltip": "#D6F0EE",
    "bg.status": "#EAF3F4",
    "text.primary": "#16363B",
    "text.secondary": "#2F5A60",
    "text.inverse": "#FFFFFF",
    "border.default": "#8DA8AE",
    "border.focus": "#0F8F84",
    "state.success": "#0C7A56",
    "state.warning": "#9A5A0A",
    "state.error": "#A22A2A",
    "action.primary": "#0F766E",
    "action.primary.hover": "#0B5E57",
    "action.secondary": "#245A61",
    "action.secondary.hover": "#1B464C",
}

SPACING = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
}

RADIUS = {
    "sm": 8,
    "md": 10,
}


def _font_family() -> str:
    if sys.platform.startswith("win"):
        return "Segoe UI"
    if sys.platform == "darwin":
        return "SF Pro Text"
    return "TkDefaultFont"


def _mono_family() -> str:
    if sys.platform.startswith("win"):
        return "Consolas"
    if sys.platform == "darwin":
        return "Menlo"
    return "TkFixedFont"


FONTS = {
    "body": (_font_family(), 10),
    "label": (_font_family(), 10, "bold"),
    "help": (_font_family(), 9),
    "status": (_mono_family(), 9),
}


def apply_ttk_theme(root: tk.Tk) -> ttk.Style:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        # Fall back to current default if clam is unavailable.
        pass

    root.configure(bg=COLORS["bg.app"])

    style.configure("App.TFrame", background=COLORS["bg.app"])
    style.configure("Panel.TFrame", background=COLORS["bg.panel"])
    style.configure(
        "Form.TLabel",
        background=COLORS["bg.panel"],
        foreground=COLORS["text.primary"],
        font=FONTS["label"],
    )
    style.configure(
        "Help.TLabel",
        background=COLORS["bg.panel"],
        foreground=COLORS["text.secondary"],
        font=FONTS["help"],
    )
    style.configure(
        "TCheckbutton",
        background=COLORS["bg.panel"],
        foreground=COLORS["text.primary"],
        font=FONTS["body"],
    )

    style.configure(
        "Form.TEntry",
        fieldbackground=COLORS["bg.input"],
        foreground=COLORS["text.primary"],
        bordercolor=COLORS["border.default"],
        lightcolor=COLORS["border.default"],
        darkcolor=COLORS["border.default"],
        padding=(8, 6),
    )
    style.map(
        "Form.TEntry",
        bordercolor=[("focus", COLORS["border.focus"])],
        lightcolor=[("focus", COLORS["border.focus"])],
        darkcolor=[("focus", COLORS["border.focus"])],
    )

    style.configure(
        "Form.TCombobox",
        fieldbackground=COLORS["bg.input"],
        background=COLORS["bg.input"],
        foreground=COLORS["text.primary"],
        arrowcolor=COLORS["text.primary"],
        bordercolor=COLORS["border.default"],
        lightcolor=COLORS["border.default"],
        darkcolor=COLORS["border.default"],
        padding=(8, 6),
    )
    style.map(
        "Form.TCombobox",
        fieldbackground=[("readonly", COLORS["bg.input"])],
        foreground=[("readonly", COLORS["text.primary"])],
        selectbackground=[("readonly", COLORS["action.secondary"])],
        selectforeground=[("readonly", COLORS["text.inverse"])],
        bordercolor=[("focus", COLORS["border.focus"])],
        lightcolor=[("focus", COLORS["border.focus"])],
        darkcolor=[("focus", COLORS["border.focus"])],
    )

    # Flat field variants for rounded-wrapper rendering.
    style.configure(
        "Flat.TEntry",
        fieldbackground=COLORS["bg.input"],
        foreground=COLORS["text.primary"],
        borderwidth=0,
        relief=tk.FLAT,
        padding=(8, 6),
    )
    style.configure(
        "Flat.TCombobox",
        fieldbackground=COLORS["bg.input"],
        background=COLORS["bg.input"],
        foreground=COLORS["text.primary"],
        arrowcolor=COLORS["text.primary"],
        borderwidth=0,
        relief=tk.FLAT,
        padding=(8, 6),
    )
    style.map(
        "Flat.TCombobox",
        fieldbackground=[("readonly", COLORS["bg.input"])],
        foreground=[("readonly", COLORS["text.primary"])],
        selectbackground=[("readonly", COLORS["action.secondary"])],
        selectforeground=[("readonly", COLORS["text.inverse"])],
    )

    style.configure(
        "Primary.TButton",
        font=FONTS["label"],
        padding=(12, 7),
        foreground=COLORS["text.inverse"],
        background=COLORS["action.primary"],
        bordercolor=COLORS["action.primary"],
        lightcolor=COLORS["action.primary"],
        darkcolor=COLORS["action.primary"],
        focuscolor=COLORS["border.focus"],
    )
    style.map(
        "Primary.TButton",
        background=[
            ("active", COLORS["action.primary.hover"]),
            ("pressed", COLORS["action.primary.hover"]),
            ("disabled", COLORS["border.default"]),
        ],
        foreground=[("disabled", COLORS["text.secondary"])],
        bordercolor=[("focus", COLORS["border.focus"])],
    )

    style.configure(
        "Secondary.TButton",
        font=FONTS["body"],
        padding=(10, 7),
        foreground=COLORS["text.primary"],
        background=COLORS["bg.panel"],
        bordercolor=COLORS["border.default"],
        lightcolor=COLORS["border.default"],
        darkcolor=COLORS["border.default"],
        focuscolor=COLORS["border.focus"],
    )
    style.map(
        "Secondary.TButton",
        background=[
            ("active", COLORS["action.secondary.hover"]),
            ("pressed", COLORS["action.secondary.hover"]),
            ("disabled", COLORS["bg.panel"]),
        ],
        foreground=[
            ("active", COLORS["text.inverse"]),
            ("pressed", COLORS["text.inverse"]),
            ("disabled", COLORS["text.secondary"]),
        ],
        bordercolor=[("focus", COLORS["border.focus"])],
    )

    style.configure(
        "Status.TFrame",
        background=COLORS["bg.status"],
        bordercolor=COLORS["border.default"],
        lightcolor=COLORS["border.default"],
        darkcolor=COLORS["border.default"],
        borderwidth=1,
        relief=tk.SOLID,
    )

    return style
