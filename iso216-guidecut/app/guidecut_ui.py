#!/usr/bin/env python3
"""
Tkinter UI for ISO216 Guidecut.
"""

from __future__ import annotations

import queue
import shlex
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from tkinter.scrolledtext import ScrolledText

from PIL import Image, ImageOps, ImageTk

from guidecut_runner import (
    SUPPORTED_FORMATS,
    browse_initial_directory,
    build_command,
    build_output_pdf_path,
    clamp_expand_bias_percent,
    choose_guide_style,
    effective_preview_state,
    expand_crop_for_source,
    load_ui_state,
    normalize_target_format,
    open_folder,
    preview_guides_for_source,
    retained_input_value_after_run,
    resolve_existing_input_file,
    resolve_open_folder,
    resolve_output_directory,
    run_command_streaming,
    sample_line_luminance,
    save_ui_state,
    tooltip_text_for_format,
)
from guidecut_theme import COLORS, FONTS, RADIUS, SPACING, apply_ttk_theme


MODULE_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = MODULE_ROOT / "cli" / "iso216_guidecut.py"
SCRIPT_CWD = SCRIPT_PATH.parent
STATE_PATH = Path(__file__).with_name("guidecut_ui_state.json")
PREVIEW_PANEL_MIN_WIDTH = 300
BASE_WINDOW_MIN_WIDTH = 760
PREVIEW_SPLITTER_WIDTH = 6
PREVIEW_SPLITTER_PAD_X = SPACING["sm"] + SPACING["xs"]
UI_PANEL_MIN_WIDTH = 460
DEFAULT_PREVIEW_SPLIT_RATIO = 0.5
AUTOFIT_WIDTH_TOLERANCE_PX = 2
PREVIEW_CONTRAST_DEBOUNCE_MS = 140
GUIDE_DASH_PATTERN = (6, 4)
GUIDE_STROKE_WIDTH = 1
GUIDE_HALO_WIDTH = 3
ENABLE_ADAPTIVE_GUIDE_CONTRAST = True
EXPAND_DEFAULT_BIAS_PERCENT = 50.0


class HoverTooltip:
    def __init__(self, widget: tk.Widget, text_provider) -> None:
        self.widget = widget
        self.text_provider = text_provider
        self._window: tk.Toplevel | None = None
        self._label: tk.Label | None = None

        self.widget.bind("<Enter>", self._show, add=True)
        self.widget.bind("<Leave>", self._hide, add=True)
        self.widget.bind("<FocusIn>", self._show, add=True)
        self.widget.bind("<FocusOut>", self._hide, add=True)

    def _show(self, _event=None) -> None:
        if self._window is not None:
            return
        text = self.text_provider()
        if not text:
            return

        self._window = tk.Toplevel(self.widget)
        self._window.wm_overrideredirect(True)
        x = self.widget.winfo_rootx() + self.widget.winfo_width() + 8
        y = self.widget.winfo_rooty() + 4
        self._window.wm_geometry(f"+{x}+{y}")
        self._label = tk.Label(
            self._window,
            text=text,
            justify=tk.LEFT,
            background=COLORS["bg.tooltip"],
            foreground=COLORS["text.primary"],
            font=FONTS["help"],
            relief=tk.SOLID,
            borderwidth=1,
            padx=SPACING["sm"],
            pady=SPACING["xs"],
        )
        self._label.pack()
        self._window.configure(background=COLORS["border.default"])

    def _hide(self, _event=None) -> None:
        if self._window is None:
            return
        self._window.destroy()
        self._window = None
        self._label = None

    def refresh(self) -> None:
        if self._label is not None:
            self._label.configure(text=self.text_provider())


class RoundedField(ttk.Frame):
    def __init__(
        self,
        parent: tk.Widget,
        *,
        radius: int = 8,
        height: int = 36,
        fill: str = COLORS["bg.input"],
        background: str = COLORS["bg.panel"],
    ) -> None:
        super().__init__(parent, style="Panel.TFrame")
        self.radius = radius
        self.height = height
        self.fill = fill
        self.background = background
        self._focused = False
        self._error = False

        self.canvas = tk.Canvas(
            self,
            height=height,
            highlightthickness=0,
            borderwidth=0,
            bg=background,
        )
        self.canvas.pack(fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=fill, highlightthickness=0, borderwidth=0)
        self._window_id = self.canvas.create_window(0, 0, anchor="nw", window=self.inner)
        self.canvas.bind("<Configure>", self._on_configure)
        self._draw()

    def bind_focus_widget(self, widget: tk.Widget) -> None:
        widget.bind("<FocusIn>", lambda _e: self.set_focused(True), add=True)
        widget.bind("<FocusOut>", lambda _e: self.set_focused(False), add=True)

    def set_focused(self, focused: bool) -> None:
        self._focused = focused
        self._draw()

    def set_error(self, has_error: bool) -> None:
        self._error = has_error
        self._draw()

    def _border_color(self) -> str:
        if self._error:
            return COLORS["state.error"]
        if self._focused:
            return COLORS["border.focus"]
        return COLORS["border.default"]

    @staticmethod
    def _rounded_points(x1: int, y1: int, x2: int, y2: int, r: int) -> list[int]:
        return [
            x1 + r,
            y1,
            x1 + r,
            y1,
            x2 - r,
            y1,
            x2 - r,
            y1,
            x2,
            y1,
            x2,
            y1 + r,
            x2,
            y1 + r,
            x2,
            y2 - r,
            x2,
            y2 - r,
            x2,
            y2,
            x2 - r,
            y2,
            x2 - r,
            y2,
            x1 + r,
            y2,
            x1 + r,
            y2,
            x1,
            y2,
            x1,
            y2 - r,
            x1,
            y2 - r,
            x1,
            y1 + r,
            x1,
            y1 + r,
            x1,
            y1,
        ]

    def _draw(self) -> None:
        self.canvas.delete("shape")
        width = max(self.canvas.winfo_width(), 2 * self.radius + 4)
        height = max(self.canvas.winfo_height(), self.height)
        points = self._rounded_points(1, 1, width - 1, height - 1, self.radius)
        self.canvas.create_polygon(
            points,
            smooth=True,
            fill=self.fill,
            outline=self._border_color(),
            width=1,
            tags="shape",
        )
        inset = 3
        self.canvas.coords(self._window_id, inset, inset)
        self.canvas.itemconfigure(self._window_id, width=max(1, width - 2 * inset), height=max(1, height - 2 * inset))

    def _on_configure(self, _event=None) -> None:
        self._draw()


class RoundedButton(tk.Canvas):
    def __init__(
        self,
        parent: tk.Widget,
        *,
        text: str,
        command=None,
        variant: str = "secondary",
        radius: int = 8,
        height: int = 34,
        min_width: int = 90,
        background: str = COLORS["bg.panel"],
        font=None,
        takefocus: bool = True,
    ) -> None:
        self._text = text
        self._command = command
        self._variant = variant
        self._radius = radius
        self._height = height
        self._disabled = False
        self._hovered = False
        self._pressed = False
        self._focused = False

        width = max(min_width, 24 + len(text) * 8)
        button_font = font or (FONTS["label"] if variant == "primary" else FONTS["body"])

        super().__init__(
            parent,
            width=width,
            height=height,
            highlightthickness=0,
            borderwidth=0,
            bg=background,
            takefocus=1 if takefocus else 0,
            cursor="hand2",
        )
        self._font = button_font

        self.bind("<Configure>", self._on_configure, add=True)
        self.bind("<Enter>", self._on_enter, add=True)
        self.bind("<Leave>", self._on_leave, add=True)
        self.bind("<ButtonPress-1>", self._on_press, add=True)
        self.bind("<ButtonRelease-1>", self._on_release, add=True)
        self.bind("<FocusIn>", self._on_focus_in, add=True)
        self.bind("<FocusOut>", self._on_focus_out, add=True)
        self.bind("<KeyPress-Return>", self._on_key_activate, add=True)
        self.bind("<KeyPress-space>", self._on_key_activate, add=True)

        self._draw()

    @staticmethod
    def _rounded_points(x1: int, y1: int, x2: int, y2: int, r: int) -> list[int]:
        return [
            x1 + r,
            y1,
            x1 + r,
            y1,
            x2 - r,
            y1,
            x2 - r,
            y1,
            x2,
            y1,
            x2,
            y1 + r,
            x2,
            y1 + r,
            x2,
            y2 - r,
            x2,
            y2 - r,
            x2,
            y2,
            x2 - r,
            y2,
            x2 - r,
            y2,
            x1 + r,
            y2,
            x1 + r,
            y2,
            x1,
            y2,
            x1,
            y2 - r,
            x1,
            y2 - r,
            x1,
            y1 + r,
            x1,
            y1 + r,
            x1,
            y1,
        ]

    def _palette(self) -> tuple[str, str, str]:
        if self._disabled:
            if self._variant == "primary":
                return COLORS["border.default"], COLORS["border.default"], COLORS["text.secondary"]
            return COLORS["bg.panel"], COLORS["border.default"], COLORS["text.secondary"]

        if self._variant == "primary":
            fill = COLORS["action.primary.hover"] if (self._hovered or self._pressed) else COLORS["action.primary"]
            border = COLORS["border.focus"] if self._focused else fill
            return fill, border, COLORS["text.inverse"]

        if self._hovered or self._pressed:
            fill = COLORS["action.secondary.hover"]
            border = COLORS["action.secondary.hover"]
            text = COLORS["text.inverse"]
        else:
            fill = COLORS["bg.panel"]
            border = COLORS["border.default"]
            text = COLORS["text.primary"]
        if self._focused:
            border = COLORS["border.focus"]
        return fill, border, text

    def _draw(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), 2 * self._radius + 4)
        height = max(self.winfo_height(), self._height)
        fill, border, text_color = self._palette()
        points = self._rounded_points(1, 1, width - 1, height - 1, self._radius)
        self.create_polygon(
            points,
            smooth=True,
            fill=fill,
            outline=border,
            width=1,
        )
        self.create_text(
            width // 2,
            height // 2,
            text=self._text,
            fill=text_color,
            font=self._font,
        )

    def _on_configure(self, _event=None) -> None:
        self._draw()

    def _on_enter(self, _event=None) -> None:
        self._hovered = True
        self._draw()

    def _on_leave(self, _event=None) -> None:
        self._hovered = False
        self._pressed = False
        self._draw()

    def _on_press(self, _event=None) -> None:
        if self._disabled:
            return
        self.focus_set()
        self._pressed = True
        self._draw()

    def _on_release(self, event=None) -> None:
        if self._disabled:
            return
        was_pressed = self._pressed
        self._pressed = False
        self._draw()
        if not was_pressed:
            return
        if event is None:
            self.invoke()
            return
        inside = 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height()
        if inside:
            self.invoke()

    def _on_focus_in(self, _event=None) -> None:
        self._focused = True
        self._draw()

    def _on_focus_out(self, _event=None) -> None:
        self._focused = False
        self._pressed = False
        self._draw()

    def _on_key_activate(self, _event=None) -> str | None:
        if self._disabled:
            return "break"
        self.invoke()
        return "break"

    def state(self, specs: list[str]) -> None:
        for spec in specs:
            if spec == "disabled":
                self._disabled = True
            elif spec == "!disabled":
                self._disabled = False
        self.configure(cursor="arrow" if self._disabled else "hand2")
        self._draw()

    def invoke(self) -> None:
        if self._disabled or self._command is None:
            return
        self._command()


class GuidecutApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("ISO216 Guidecut")
        self.minsize(BASE_WINDOW_MIN_WIDTH, 460)

        self.input_var = tk.StringVar()
        self.target_var = tk.StringVar(value="A2")
        self.specify_output_var = tk.BooleanVar(value=False)
        self.output_dir_var = tk.StringVar()
        self.show_preview_var = tk.BooleanVar(value=False)
        self.expand_to_format_var = tk.BooleanVar(value=False)
        self.expand_bias_var = tk.DoubleVar(value=EXPAND_DEFAULT_BIAS_PERCENT)
        self.expand_bias_label_var = tk.StringVar(value="Trim bias: 50.0%")

        self._event_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._run_thread: threading.Thread | None = None
        self._last_run_input_path: Path | None = None
        self._startup_warnings: list[str] = []
        self._pending_window_geometry: str = ""
        self._preview_panel_visible = False
        self._preview_source_path: Path | None = None
        self._preview_source_image: Image.Image | None = None
        self._preview_tk_image: ImageTk.PhotoImage | None = None
        self._preview_loading_path: Path | None = None
        self._preview_load_request_id = 0
        self._window_expanded_for_preview = False
        self._locked_left_panel_width = 0
        self._preview_split_ratio = DEFAULT_PREVIEW_SPLIT_RATIO
        self._current_preview_expand_width = 0
        self._preview_autofit_pending = False
        self._splitter_drag_start_x = 0
        self._splitter_drag_start_left_width = 0
        self._preview_contrast_after_id: str | None = None
        self._cached_guide_style_key: tuple | None = None
        self._cached_guide_styles: list[tuple[str, str | None]] = []
        self._active_input_document: str | None = None
        self._expand_drag_active = False
        self._expand_drag_axis: str | None = None
        self._expand_drag_start_pointer = 0
        self._expand_drag_start_leading_trim = 0
        self._expand_drag_excess = 0
        self._expand_drag_display_length = 0
        self._last_preview_crop_info = None
        self._last_preview_display_box = (0, 0, 0, 0)

        self._style = apply_ttk_theme(self)
        self._load_persisted_state()
        self._build_ui()
        self.input_var.trace_add("write", self._on_input_path_changed)
        self.target_var.trace_add("write", self._on_target_changed)
        self._toggle_output_controls()
        self._toggle_expand_controls()
        self._sync_expand_document_state()
        self._sync_preview_controls()
        self._apply_persisted_window_geometry()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        for warning in self._startup_warnings:
            self._append_status(f"Warning: {warning}")
        self.after(100, self._drain_queue)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.root_container = ttk.Frame(self, style="App.TFrame", padding=SPACING["md"])
        self.root_container.grid(row=0, column=0, sticky="nsew")
        self.root_container.rowconfigure(0, weight=1)
        self.root_container.columnconfigure(0, weight=1)
        self.root_container.columnconfigure(1, weight=0)
        self.root_container.columnconfigure(2, weight=0)

        panel = ttk.Frame(self.root_container, style="Panel.TFrame", padding=SPACING["md"])
        panel.grid(row=0, column=0, sticky="nsew")
        panel.columnconfigure(1, weight=1)
        panel.rowconfigure(8, weight=1)
        self.panel = panel

        self.preview_splitter = tk.Frame(
            self.root_container,
            width=PREVIEW_SPLITTER_WIDTH,
            bg=COLORS["border.default"],
            cursor="sb_h_double_arrow",
            highlightthickness=0,
            borderwidth=0,
        )
        self.preview_splitter.bind("<ButtonPress-1>", self._on_splitter_press, add=True)
        self.preview_splitter.bind("<B1-Motion>", self._on_splitter_drag, add=True)
        self.preview_splitter.bind("<ButtonRelease-1>", self._on_splitter_release, add=True)
        self.preview_splitter.grid_remove()

        usage_text = (
            "Usage: 1) Choose an input file. 2) Select target format. "
            "3) Optionally set output directory. 4) Click Run."
        )
        ttk.Label(panel, text=usage_text, style="Help.TLabel", justify=tk.LEFT, wraplength=720).grid(
            row=0,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(0, SPACING["md"]),
        )

        ttk.Label(panel, text="Input File", style="Form.TLabel").grid(
            row=1,
            column=0,
            sticky="w",
            padx=(0, SPACING["sm"]),
            pady=(0, SPACING["sm"]),
        )
        self.input_field = RoundedField(panel, radius=RADIUS["sm"], fill=COLORS["bg.input"])
        self.input_field.grid(row=1, column=1, sticky="ew", pady=(0, SPACING["sm"]))
        self.input_entry = tk.Entry(
            self.input_field.inner,
            textvariable=self.input_var,
            bg=COLORS["bg.input"],
            fg=COLORS["text.primary"],
            insertbackground=COLORS["text.primary"],
            selectbackground=COLORS["action.secondary"],
            selectforeground=COLORS["text.inverse"],
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            font=FONTS["body"],
        )
        self.input_entry.pack(fill="x", expand=True, padx=SPACING["sm"], pady=SPACING["xs"])
        self.input_field.bind_focus_widget(self.input_entry)
        self.input_browse = RoundedButton(
            panel,
            text="Browse...",
            command=self._browse_input,
            variant="secondary",
            radius=RADIUS["sm"],
            min_width=110,
        )
        self.input_browse.grid(
            row=1,
            column=2,
            padx=(SPACING["sm"], 0),
            pady=(0, SPACING["sm"]),
        )

        self.preview_toggle = ttk.Checkbutton(
            panel,
            text="Show preview",
            variable=self.show_preview_var,
            command=self._on_preview_toggle,
        )
        self.preview_toggle.grid(row=3, column=2, sticky="e", pady=(0, SPACING["sm"]))
        self.preview_toggle.grid_remove()

        self.output_toggle = ttk.Checkbutton(
            panel,
            text="Specify output directory",
            variable=self.specify_output_var,
            command=self._toggle_output_controls,
        )
        self.output_toggle.grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, SPACING["sm"]))

        self.output_row = ttk.Frame(panel, style="Panel.TFrame")
        self.output_row.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(0, SPACING["sm"]))
        self.output_row.columnconfigure(0, weight=1)
        self.output_field = RoundedField(self.output_row, radius=RADIUS["sm"], fill=COLORS["bg.input"])
        self.output_field.grid(row=0, column=0, sticky="ew")
        self.output_entry = tk.Entry(
            self.output_field.inner,
            textvariable=self.output_dir_var,
            bg=COLORS["bg.input"],
            fg=COLORS["text.primary"],
            insertbackground=COLORS["text.primary"],
            selectbackground=COLORS["action.secondary"],
            selectforeground=COLORS["text.inverse"],
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            font=FONTS["body"],
        )
        self.output_entry.pack(fill="x", expand=True, padx=SPACING["sm"], pady=SPACING["xs"])
        self.output_field.bind_focus_widget(self.output_entry)
        self.output_browse = RoundedButton(
            self.output_row,
            text="Browse Output...",
            command=self._browse_output,
            variant="secondary",
            radius=RADIUS["sm"],
            min_width=130,
        )
        self.output_browse.grid(row=0, column=1, padx=(SPACING["sm"], 0))
        self.output_row.grid_remove()

        self.expand_toggle = ttk.Checkbutton(
            panel,
            text="Expand to Format",
            variable=self.expand_to_format_var,
            command=self._on_expand_toggle,
        )
        self.expand_toggle.grid(row=5, column=0, sticky="w", pady=(0, SPACING["sm"]))

        self.expand_row = ttk.Frame(panel, style="Panel.TFrame")
        self.expand_row.grid(row=5, column=1, columnspan=2, sticky="ew", pady=(0, SPACING["sm"]))
        self.expand_row.columnconfigure(1, weight=1)
        self.expand_bias_label = ttk.Label(self.expand_row, text="Trim Bias", style="Form.TLabel")
        self.expand_bias_label.grid(row=0, column=0, sticky="w", padx=(0, SPACING["sm"]))
        self.expand_scale = ttk.Scale(
            self.expand_row,
            orient=tk.HORIZONTAL,
            from_=0.0,
            to=100.0,
            variable=self.expand_bias_var,
            command=self._on_expand_bias_scale,
        )
        self.expand_scale.grid(row=0, column=1, sticky="ew")
        self.expand_bias_value = ttk.Label(self.expand_row, textvariable=self.expand_bias_label_var, style="Help.TLabel")
        self.expand_bias_value.grid(row=0, column=2, sticky="e", padx=(SPACING["sm"], 0))
        self.expand_row.grid_remove()

        button_row = ttk.Frame(panel, style="Panel.TFrame")
        button_row.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(0, SPACING["sm"]))
        button_row.columnconfigure(1, weight=1)

        target_cluster = ttk.Frame(button_row, style="Panel.TFrame")
        target_cluster.grid(row=0, column=0, sticky="w")
        ttk.Label(target_cluster, text="Target Format", style="Form.TLabel").grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, SPACING["xs"]),
        )
        self.target_field = RoundedField(target_cluster, radius=RADIUS["sm"], fill=COLORS["bg.input"])
        self.target_field.grid(row=0, column=1, sticky="w")
        self.target_field.canvas.configure(width=60)
        self.target_menu_button = tk.Menubutton(
            self.target_field.inner,
            textvariable=self.target_var,
            bg=COLORS["bg.input"],
            fg=COLORS["text.primary"],
            activebackground=COLORS["bg.input"],
            activeforeground=COLORS["text.primary"],
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
            font=FONTS["body"],
            anchor="w",
            padx=2,
            pady=SPACING["xs"],
        )
        self.target_menu = tk.Menu(
            self.target_menu_button,
            tearoff=0,
            bg=COLORS["bg.input"],
            fg=COLORS["text.primary"],
            activebackground=COLORS["action.secondary"],
            activeforeground=COLORS["text.inverse"],
            relief=tk.SOLID,
            borderwidth=1,
            font=FONTS["body"],
        )
        for fmt in SUPPORTED_FORMATS:
            display_fmt = fmt.upper()
            self.target_menu.add_radiobutton(label=display_fmt, value=display_fmt, variable=self.target_var)
        self.target_menu_button.configure(menu=self.target_menu)
        self.target_menu_button.pack(fill="x", expand=True, padx=2, pady=SPACING["xs"], anchor="w")
        self.target_field.bind_focus_widget(self.target_menu_button)

        self.info_button = RoundedButton(
            target_cluster,
            text="i",
            command=lambda: None,
            variant="secondary",
            radius=RADIUS["sm"],
            min_width=26,
            takefocus=True,
        )
        self.info_button.grid(row=0, column=2, padx=(2, 0), sticky="w")
        self.info_tooltip = HoverTooltip(self.info_button, self._format_tooltip_text)
        self.open_button = RoundedButton(
            button_row,
            text="Open Folder",
            command=self._open_folder,
            variant="secondary",
            radius=RADIUS["sm"],
            min_width=120,
        )
        self.open_button.grid(row=0, column=2, padx=(SPACING["sm"], 0))
        self.run_button = RoundedButton(
            button_row,
            text="Run",
            command=self._run,
            variant="primary",
            radius=RADIUS["sm"],
            min_width=90,
        )
        self.run_button.grid(row=0, column=3, padx=(SPACING["sm"], 0))

        status_container = ttk.Frame(panel, style="Status.TFrame", padding=1)
        status_container.grid(row=8, column=0, columnspan=3, sticky="nsew")
        status_container.columnconfigure(0, weight=1)
        status_container.rowconfigure(0, weight=1)

        self.status = ScrolledText(
            status_container,
            wrap=tk.WORD,
            height=14,
            state=tk.DISABLED,
            relief=tk.FLAT,
            borderwidth=0,
            background=COLORS["bg.status"],
            foreground=COLORS["text.primary"],
            insertbackground=COLORS["text.primary"],
            font=FONTS["status"],
            highlightthickness=0,
        )
        self.status.grid(row=0, column=0, sticky="nsew")
        self.status.tag_configure("stdout", foreground=COLORS["text.primary"])
        self.status.tag_configure("stderr", foreground=COLORS["state.error"])

        self.preview_panel = ttk.Frame(
            self.root_container,
            style="Panel.TFrame",
            padding=SPACING["md"],
        )
        self.preview_panel.columnconfigure(0, weight=1)
        self.preview_panel.rowconfigure(1, weight=1)

        ttk.Label(self.preview_panel, text="Cut Preview", style="Form.TLabel").grid(row=0, column=0, sticky="w")

        self.preview_canvas = tk.Canvas(
            self.preview_panel,
            bg=COLORS["bg.input"],
            highlightthickness=0,
            borderwidth=0,
        )
        self.preview_canvas.grid(row=1, column=0, sticky="nsew", pady=(SPACING["sm"], SPACING["xs"]))
        self.preview_canvas.bind("<Configure>", self._on_preview_canvas_configure, add=True)
        self.preview_canvas.bind("<ButtonPress-1>", self._on_preview_drag_start, add=True)
        self.preview_canvas.bind("<B1-Motion>", self._on_preview_drag_motion, add=True)
        self.preview_canvas.bind("<ButtonRelease-1>", self._on_preview_drag_end, add=True)

        self.preview_status_var = tk.StringVar(value="Preview hidden.")
        ttk.Label(
            self.preview_panel,
            textvariable=self.preview_status_var,
            style="Help.TLabel",
            justify=tk.LEFT,
            wraplength=280,
        ).grid(row=2, column=0, sticky="w")
        self.preview_panel.grid_remove()

    def _format_tooltip_text(self) -> str:
        try:
            return tooltip_text_for_format(self.target_var.get())
        except ValueError:
            return "Unsupported format."

    @staticmethod
    def _resample_filter() -> int:
        if hasattr(Image, "Resampling"):
            return Image.Resampling.LANCZOS
        return Image.LANCZOS

    def _set_preview_status(self, message: str) -> None:
        self.preview_status_var.set(message)

    def _clear_preview_canvas(self) -> None:
        self.preview_canvas.delete("all")
        self._preview_tk_image = None
        self._last_preview_crop_info = None
        self._last_preview_display_box = (0, 0, 0, 0)
        self._expand_drag_active = False

    def _cancel_contrast_refresh(self) -> None:
        if self._preview_contrast_after_id is None:
            return
        try:
            self.after_cancel(self._preview_contrast_after_id)
        except tk.TclError:
            pass
        self._preview_contrast_after_id = None

    def _invalidate_guide_style_cache(self) -> None:
        self._cached_guide_style_key = None
        self._cached_guide_styles = []

    def _schedule_contrast_refresh(self) -> None:
        if not self._preview_panel_visible or self._preview_source_image is None:
            return
        self._cancel_contrast_refresh()
        self._preview_contrast_after_id = self.after(
            PREVIEW_CONTRAST_DEBOUNCE_MS,
            self._render_preview_with_contrast,
        )

    def _render_preview_with_contrast(self) -> None:
        self._preview_contrast_after_id = None
        if not self._preview_panel_visible or self._preview_source_image is None:
            return
        self._render_preview(compute_contrast=True)

    def _close_preview_source(self) -> None:
        self._cancel_contrast_refresh()
        self._invalidate_guide_style_cache()
        if self._preview_source_image is not None:
            try:
                self._preview_source_image.close()
            except Exception:  # noqa: BLE001
                pass
        self._preview_source_image = None
        self._preview_source_path = None

    def _update_preview_split_ratio(self) -> None:
        if not self._preview_panel_visible:
            return
        self.update_idletasks()
        left_width = max(1, self.panel.winfo_width())
        preview_width = max(0, self.preview_panel.winfo_width())
        if preview_width <= 0:
            return
        ratio = preview_width / left_width
        self._preview_split_ratio = max(0.2, min(3.0, ratio))

    def _show_preview_panel(self) -> None:
        if self._preview_panel_visible:
            return
        self.update_idletasks()
        self._locked_left_panel_width = max(UI_PANEL_MIN_WIDTH, self.panel.winfo_width())
        desired_preview_width = max(PREVIEW_PANEL_MIN_WIDTH, int(self._locked_left_panel_width * self._preview_split_ratio))
        self._current_preview_expand_width = desired_preview_width + PREVIEW_SPLITTER_WIDTH + PREVIEW_SPLITTER_PAD_X
        self.root_container.columnconfigure(0, weight=0, minsize=self._locked_left_panel_width)
        self.root_container.columnconfigure(1, weight=0, minsize=PREVIEW_SPLITTER_WIDTH)
        self.root_container.columnconfigure(2, weight=1, minsize=desired_preview_width)
        self.preview_splitter.grid(row=0, column=1, sticky="ns", padx=(SPACING["sm"], SPACING["xs"]))
        self.preview_panel.grid(row=0, column=2, sticky="nsew")
        current_w = self.winfo_width()
        current_h = self.winfo_height()
        current_x = self.winfo_x()
        current_y = self.winfo_y()
        self.update_idletasks()
        requested_w = self.winfo_reqwidth()
        if requested_w > current_w:
            self.geometry(f"{requested_w}x{current_h}+{current_x}+{current_y}")
            self.update_idletasks()
        self._current_preview_expand_width = max(0, self.root_container.winfo_width() - self.panel.winfo_width())
        self._window_expanded_for_preview = True
        self._preview_panel_visible = True
        self._preview_autofit_pending = True

    def _hide_preview_panel(self) -> None:
        if not self._preview_panel_visible:
            return
        self._cancel_contrast_refresh()
        self._update_preview_split_ratio()
        self.update_idletasks()
        preview_allocation = max(0, self.root_container.winfo_width() - self.panel.winfo_width())
        self.preview_splitter.grid_remove()
        self.preview_panel.grid_remove()
        self.root_container.columnconfigure(0, weight=1, minsize=0)
        self.root_container.columnconfigure(1, weight=0, minsize=0)
        self.root_container.columnconfigure(2, weight=0, minsize=0)
        self._locked_left_panel_width = 0
        if self._window_expanded_for_preview and preview_allocation > 0:
            self.update_idletasks()
            current_w = self.winfo_width()
            current_h = self.winfo_height()
            current_x = self.winfo_x()
            current_y = self.winfo_y()
            new_w = max(BASE_WINDOW_MIN_WIDTH, current_w - preview_allocation)
            self.geometry(f"{new_w}x{current_h}+{current_x}+{current_y}")
        self._window_expanded_for_preview = False
        self._current_preview_expand_width = 0
        self._preview_panel_visible = False
        self._preview_autofit_pending = False
        self._invalidate_guide_style_cache()
        self._clear_preview_canvas()

    def _on_target_changed(self, *_args) -> None:
        self.info_tooltip.refresh()
        if self.show_preview_var.get() and self._preview_source_image is not None:
            self._invalidate_guide_style_cache()
            self._render_preview(compute_contrast=True)

    def _on_input_path_changed(self, *_args) -> None:
        self._sync_expand_document_state()
        self._update_expand_slider_state()
        self._sync_preview_controls()

    def _on_preview_toggle(self) -> None:
        self._sync_preview_controls()

    def _on_expand_toggle(self) -> None:
        self._toggle_expand_controls()
        self._update_expand_slider_state()
        self._expand_drag_active = False
        if self._preview_panel_visible and self._preview_source_image is not None:
            self._invalidate_guide_style_cache()
            self._render_preview(compute_contrast=False)
            self._schedule_contrast_refresh()

    def _on_expand_bias_scale(self, value: str) -> None:
        try:
            parsed = float(value)
        except ValueError:
            return
        self._set_expand_bias_percent(parsed, rerender=True, fast_preview=True)

    def _sync_expand_document_state(self) -> None:
        file_path = resolve_existing_input_file(self.input_var.get())
        document_key = str(file_path) if file_path is not None else None
        if document_key is None:
            bias_not_default = abs(float(self.expand_bias_var.get()) - EXPAND_DEFAULT_BIAS_PERCENT) > 1e-6
            if self._active_input_document is not None or self.expand_to_format_var.get() or bias_not_default:
                self._active_input_document = None
                self._reset_expand_state_for_document()
            return
        if document_key == self._active_input_document:
            return
        self._active_input_document = document_key
        self._reset_expand_state_for_document()

    def _reset_expand_state_for_document(self) -> None:
        self.expand_to_format_var.set(False)
        self._set_expand_bias_percent(EXPAND_DEFAULT_BIAS_PERCENT, rerender=False, fast_preview=False)
        self._toggle_expand_controls()
        self._expand_drag_active = False

    def _toggle_expand_controls(self) -> None:
        if self.expand_to_format_var.get():
            self.expand_row.grid()
        else:
            self.expand_row.grid_remove()
        self._update_expand_slider_state()

    def _set_expand_bias_percent(self, value: float, *, rerender: bool, fast_preview: bool) -> None:
        clamped = clamp_expand_bias_percent(value, default=EXPAND_DEFAULT_BIAS_PERCENT)
        current = float(self.expand_bias_var.get())
        if abs(current - clamped) > 1e-6:
            self.expand_bias_var.set(clamped)
        self.expand_bias_label_var.set(f"Trim bias: {clamped:.1f}%")
        if rerender and self._preview_panel_visible and self._preview_source_image is not None:
            self._invalidate_guide_style_cache()
            self._render_preview(compute_contrast=not fast_preview)
            if fast_preview:
                self._schedule_contrast_refresh()

    def _current_expand_crop_info(self):
        file_path = resolve_existing_input_file(self.input_var.get())
        if file_path is None:
            return None

        if self._preview_source_path == file_path and self._preview_source_image is not None:
            width_px, height_px = self._preview_source_image.size
            return expand_crop_for_source(width_px, height_px, self.expand_bias_var.get())

        try:
            with Image.open(file_path) as image:
                width_px, height_px = image.size
        except Exception:  # noqa: BLE001
            return None
        return expand_crop_for_source(width_px, height_px, self.expand_bias_var.get())

    def _update_expand_slider_state(self) -> None:
        if not hasattr(self, "expand_scale"):
            return

        if not self.expand_to_format_var.get():
            self.expand_scale.state(["disabled"])
            self.expand_bias_label.configure(text="Trim Bias")
            return

        crop_info = self._current_expand_crop_info()
        if crop_info is None:
            self.expand_scale.state(["!disabled"])
            self.expand_bias_label.configure(text="Trim Bias")
            return

        if crop_info.axis is None or crop_info.excess_px <= 0:
            self.expand_scale.state(["disabled"])
            self.expand_bias_label.configure(text="Trim Bias (No excess edge)")
            return

        self.expand_scale.state(["!disabled"])
        axis_label = "Left/Right Trim" if crop_info.axis == "x" else "Top/Bottom Trim"
        self.expand_bias_label.configure(text=axis_label)

    def _sync_preview_controls(self) -> None:
        toggle_visible, preview_enabled, file_path = effective_preview_state(
            self.input_var.get(),
            self.show_preview_var.get(),
        )

        if toggle_visible:
            self.preview_toggle.grid()
        else:
            self.preview_toggle.grid_remove()

        if self.show_preview_var.get() != preview_enabled:
            self.show_preview_var.set(preview_enabled)

        if not preview_enabled or file_path is None:
            # Invalidate any in-flight preview load when preview is unavailable.
            self._preview_load_request_id += 1
            self._preview_loading_path = None
            self._hide_preview_panel()
            self._set_preview_status("Preview hidden.")
            return

        self._show_preview_panel()
        self._ensure_preview_for_file(file_path)

    def _ensure_preview_for_file(self, file_path: Path) -> None:
        if self._preview_source_path == file_path and self._preview_source_image is not None:
            self._render_preview(compute_contrast=True)
            return
        if self._preview_loading_path == file_path:
            return
        self._request_preview_load(file_path)

    def _request_preview_load(self, file_path: Path) -> None:
        self._preview_load_request_id += 1
        request_id = self._preview_load_request_id
        self._preview_loading_path = file_path
        self._clear_preview_canvas()
        self._set_preview_status(f"Loading preview: {file_path.name}")
        thread = threading.Thread(
            target=self._preview_load_worker,
            args=(request_id, file_path),
            daemon=True,
        )
        thread.start()

    def _preview_load_worker(self, request_id: int, file_path: Path) -> None:
        try:
            with Image.open(file_path) as source:
                try:
                    source.seek(0)
                except EOFError:
                    pass
                corrected = ImageOps.exif_transpose(source)
                corrected.load()
                preview_image = corrected.convert("RGB")
        except Exception as exc:  # noqa: BLE001
            self._event_queue.put(
                (
                    "preview_error",
                    {
                        "request_id": request_id,
                        "path": str(file_path),
                        "error": str(exc),
                    },
                )
            )
            return

        self._event_queue.put(
            (
                "preview_loaded",
                {
                    "request_id": request_id,
                    "path": str(file_path),
                    "image": preview_image,
                },
            )
        )

    def _handle_preview_loaded(self, payload: dict[str, object]) -> None:
        request_id = int(payload["request_id"])
        image = payload["image"]
        if not isinstance(image, Image.Image):
            return
        if request_id != self._preview_load_request_id:
            image.close()
            return

        self._preview_loading_path = None
        loaded_path = Path(str(payload["path"]))
        current_input = resolve_existing_input_file(self.input_var.get())
        if not self.show_preview_var.get() or current_input != loaded_path:
            image.close()
            return

        self._close_preview_source()
        self._preview_source_image = image
        self._preview_source_path = loaded_path
        self._preview_autofit_pending = True
        self._invalidate_guide_style_cache()
        self._update_expand_slider_state()
        self._render_preview(compute_contrast=True)

    def _handle_preview_error(self, payload: dict[str, object]) -> None:
        request_id = int(payload["request_id"])
        if request_id != self._preview_load_request_id:
            return
        self._preview_loading_path = None
        error_text = str(payload["error"])
        self._clear_preview_canvas()
        self._set_preview_status(f"Unable to preview file: {error_text}")

    def _on_preview_canvas_configure(self, _event=None) -> None:
        if self.show_preview_var.get() and self._preview_source_image is not None:
            self._render_preview(compute_contrast=False)
            self._schedule_contrast_refresh()

    def _preview_drag_is_available(self) -> bool:
        crop_info = self._last_preview_crop_info
        return (
            self._preview_panel_visible
            and self.expand_to_format_var.get()
            and self._preview_source_image is not None
            and crop_info is not None
            and crop_info.axis in {"x", "y"}
            and crop_info.excess_px > 0
        )

    def _on_preview_drag_start(self, event: tk.Event) -> None:
        if not self._preview_drag_is_available():
            self._expand_drag_active = False
            return

        offset_x, offset_y, display_w, display_h = self._last_preview_display_box
        if not (offset_x <= event.x <= offset_x + display_w and offset_y <= event.y <= offset_y + display_h):
            self._expand_drag_active = False
            return

        crop_info = self._last_preview_crop_info
        if crop_info is None:
            self._expand_drag_active = False
            return

        self._expand_drag_active = True
        self._expand_drag_axis = crop_info.axis
        self._expand_drag_start_pointer = int(event.x if crop_info.axis == "x" else event.y)
        self._expand_drag_start_leading_trim = int(crop_info.leading_trim_px)
        self._expand_drag_excess = int(crop_info.excess_px)
        self._expand_drag_display_length = max(1, int(display_w if crop_info.axis == "x" else display_h))

    def _on_preview_drag_motion(self, event: tk.Event) -> None:
        if not self._expand_drag_active or self._expand_drag_axis not in {"x", "y"}:
            return
        if self._expand_drag_excess <= 0 or self._expand_drag_display_length <= 0:
            return

        pointer = int(event.x if self._expand_drag_axis == "x" else event.y)
        delta_display = pointer - self._expand_drag_start_pointer
        delta_trim = int(round((delta_display / self._expand_drag_display_length) * self._expand_drag_excess))
        leading_trim = self._expand_drag_start_leading_trim + delta_trim
        leading_trim = max(0, min(self._expand_drag_excess, leading_trim))
        new_bias = (leading_trim / self._expand_drag_excess) * 100.0
        self._set_expand_bias_percent(new_bias, rerender=True, fast_preview=True)

    def _on_preview_drag_end(self, _event: tk.Event) -> None:
        self._expand_drag_active = False
        self._expand_drag_axis = None

    def _on_splitter_press(self, event: tk.Event) -> None:
        if not self._preview_panel_visible:
            return
        self.update_idletasks()
        self._splitter_drag_start_x = int(event.x_root)
        self._splitter_drag_start_left_width = max(1, self.panel.winfo_width())

    def _on_splitter_drag(self, event: tk.Event) -> None:
        if not self._preview_panel_visible:
            return
        self.update_idletasks()
        delta = int(event.x_root) - self._splitter_drag_start_x
        requested_left_width = self._splitter_drag_start_left_width + delta
        total_width = max(1, self.root_container.winfo_width())
        reserved = PREVIEW_PANEL_MIN_WIDTH + PREVIEW_SPLITTER_WIDTH + PREVIEW_SPLITTER_PAD_X
        max_left = max(UI_PANEL_MIN_WIDTH, total_width - reserved)
        clamped_left = max(UI_PANEL_MIN_WIDTH, min(requested_left_width, max_left))
        self._locked_left_panel_width = clamped_left
        self.root_container.columnconfigure(0, weight=0, minsize=clamped_left)

    def _on_splitter_release(self, _event: tk.Event) -> None:
        if not self._preview_panel_visible:
            return
        self.update_idletasks()
        self._locked_left_panel_width = max(UI_PANEL_MIN_WIDTH, self.panel.winfo_width())
        self._update_preview_split_ratio()

    def _render_preview(self, *, compute_contrast: bool = True) -> None:
        if not self._preview_panel_visible or self._preview_source_image is None:
            return

        source_w, source_h = self._preview_source_image.size
        if source_w <= 0 or source_h <= 0:
            self._clear_preview_canvas()
            self._set_preview_status("Unable to preview file: invalid image dimensions.")
            return

        crop_info = None
        working_image = self._preview_source_image
        owns_working_image = False
        if self.expand_to_format_var.get():
            crop_info = expand_crop_for_source(source_w, source_h, self.expand_bias_var.get())
            if crop_info.excess_px > 0:
                working_image = self._preview_source_image.crop(crop_info.rect.box)
                owns_working_image = True

        working_w, working_h = working_image.size

        if self._preview_autofit_pending:
            canvas_w = self.preview_canvas.winfo_width()
            canvas_h = self.preview_canvas.winfo_height()
            if canvas_w <= 4 or canvas_h <= 4:
                if owns_working_image:
                    working_image.close()
                return
            initial_scale = min(canvas_w / working_w, canvas_h / working_h)
            initial_display_w = max(1, int(working_w * initial_scale))
            self._autofit_preview_panel_to_image(initial_display_w, canvas_w)
            self.update_idletasks()

        canvas_w = self.preview_canvas.winfo_width()
        canvas_h = self.preview_canvas.winfo_height()
        if canvas_w <= 4 or canvas_h <= 4:
            if owns_working_image:
                working_image.close()
            return

        scale = min(canvas_w / working_w, canvas_h / working_h)
        display_w = max(1, int(working_w * scale))
        display_h = max(1, int(working_h * scale))
        offset_x = (canvas_w - display_w) // 2
        offset_y = (canvas_h - display_h) // 2

        resized = working_image.resize((display_w, display_h), self._resample_filter())
        self._preview_tk_image = ImageTk.PhotoImage(resized)
        self.preview_canvas.delete("all")
        self.preview_canvas.create_image(offset_x, offset_y, anchor="nw", image=self._preview_tk_image)
        self._last_preview_display_box = (offset_x, offset_y, display_w, display_h)
        self._last_preview_crop_info = crop_info

        cols, rows, vertical_guides, horizontal_guides = preview_guides_for_source(
            working_w,
            working_h,
            self.target_var.get(),
        )
        ratio_x = display_w / working_w
        ratio_y = display_h / working_h

        guide_segments: list[tuple[float, float, float, float]] = []
        sample_segments: list[tuple[int, int, int, int]] = []
        for guide_x in vertical_guides:
            x = offset_x + (guide_x * ratio_x)
            sample_x = int(round(guide_x * ratio_x))
            sample_x = max(0, min(display_w - 1, sample_x))
            guide_segments.append((x, offset_y, x, offset_y + display_h))
            sample_segments.append((sample_x, 0, sample_x, max(0, display_h - 1)))
        for guide_y in horizontal_guides:
            y = offset_y + (guide_y * ratio_y)
            sample_y = int(round(guide_y * ratio_y))
            sample_y = max(0, min(display_h - 1, sample_y))
            guide_segments.append((offset_x, y, offset_x + display_w, y))
            sample_segments.append((0, sample_y, max(0, display_w - 1), sample_y))

        default_style = (COLORS["border.focus"], None)
        style_key = (
            str(self._preview_source_path or ""),
            self.target_var.get(),
            display_w,
            display_h,
            crop_info.rect.box if crop_info is not None else None,
            crop_info.excess_px if crop_info is not None else 0,
            tuple(sample_segments),
        )
        guide_styles: list[tuple[str, str | None]] = [default_style] * len(guide_segments)
        if ENABLE_ADAPTIVE_GUIDE_CONTRAST:
            use_cache = (
                not compute_contrast
                and self._cached_guide_style_key == style_key
                and len(self._cached_guide_styles) == len(guide_segments)
            )
            if use_cache:
                guide_styles = list(self._cached_guide_styles)
            elif compute_contrast and guide_segments:
                computed: list[tuple[str, str | None]] = []
                for x0, y0, x1, y1 in sample_segments:
                    sampled = sample_line_luminance(
                        resized,
                        x0,
                        y0,
                        x1,
                        y1,
                    )
                    computed.append(choose_guide_style(sampled))
                if computed:
                    guide_styles = computed
                    self._cached_guide_style_key = style_key
                    self._cached_guide_styles = list(computed)
            elif compute_contrast:
                self._cached_guide_style_key = style_key
                self._cached_guide_styles = []

        for index, (x0, y0, x1, y1) in enumerate(guide_segments):
            stroke_color, halo_color = (
                guide_styles[index] if index < len(guide_styles) else default_style
            )
            if halo_color:
                self.preview_canvas.create_line(
                    x0,
                    y0,
                    x1,
                    y1,
                    fill=halo_color,
                    width=GUIDE_HALO_WIDTH,
                    dash=GUIDE_DASH_PATTERN,
                )
            self.preview_canvas.create_line(
                x0,
                y0,
                x1,
                y1,
                fill=stroke_color,
                width=GUIDE_STROKE_WIDTH,
                dash=GUIDE_DASH_PATTERN,
            )

        self.preview_canvas.create_rectangle(
            offset_x,
            offset_y,
            offset_x + display_w,
            offset_y + display_h,
            outline=COLORS["border.default"],
            width=1,
        )
        source_name = self._preview_source_path.name if self._preview_source_path is not None else "Preview"
        status_text = f"{source_name} ({working_w}x{working_h}px) | Grid {cols}x{rows}"
        if self.expand_to_format_var.get() and crop_info is not None and crop_info.excess_px > 0:
            axis = "left/right" if crop_info.axis == "x" else "top/bottom"
            status_text += f" | Expanded trim {crop_info.excess_px}px ({axis})"
        self._set_preview_status(status_text)
        if owns_working_image:
            working_image.close()

    def _autofit_preview_panel_to_image(self, display_width_px: int, canvas_width_px: int) -> None:
        if not self._preview_panel_visible:
            self._preview_autofit_pending = False
            return
        self.update_idletasks()
        panel_width = max(1, self.preview_panel.winfo_width())
        non_canvas_width = max(0, panel_width - max(1, canvas_width_px))
        desired_panel_width = max(PREVIEW_PANEL_MIN_WIDTH, display_width_px + non_canvas_width)
        width_delta = panel_width - desired_panel_width
        if width_delta <= AUTOFIT_WIDTH_TOLERANCE_PX:
            self._preview_autofit_pending = False
            return

        current_w = self.winfo_width()
        current_h = self.winfo_height()
        current_x = self.winfo_x()
        current_y = self.winfo_y()
        new_w = max(BASE_WINDOW_MIN_WIDTH, current_w - width_delta)
        self.root_container.columnconfigure(2, weight=1, minsize=desired_panel_width)
        if new_w != current_w:
            self.geometry(f"{new_w}x{current_h}+{current_x}+{current_y}")
            self.update_idletasks()
        self._current_preview_expand_width = max(0, self.root_container.winfo_width() - self.panel.winfo_width())
        self._update_preview_split_ratio()
        self._preview_autofit_pending = False

    def _load_persisted_state(self) -> None:
        try:
            state = load_ui_state(STATE_PATH)
        except RuntimeError as exc:
            self._startup_warnings.append(str(exc))
            return

        self.target_var.set(state["target_format"].upper())
        self.specify_output_var.set(bool(state["specify_output_dir"]))
        self.output_dir_var.set(state["output_dir"])
        self.input_var.set(state["input_dir"])
        self.expand_to_format_var.set(bool(state["expand_to_format"]))
        self.expand_bias_var.set(float(state["expand_bias_percent"]))
        self.expand_bias_label_var.set(f"Trim bias: {float(state['expand_bias_percent']):.1f}%")
        self._pending_window_geometry = state["window_geometry"]
        self._preview_split_ratio = float(state["preview_split_ratio"])

    def _apply_persisted_window_geometry(self) -> None:
        if not self._pending_window_geometry:
            return
        try:
            self.update_idletasks()
            self.geometry(self._pending_window_geometry)
        except tk.TclError as exc:
            self._startup_warnings.append(
                f"Unable to restore window geometry '{self._pending_window_geometry}': {exc}"
            )
            self._pending_window_geometry = ""

    def _current_window_geometry(self) -> str:
        try:
            self.update_idletasks()
            return self.geometry()
        except tk.TclError:
            return ""

    def _on_close(self) -> None:
        self._preview_load_request_id += 1
        self._update_preview_split_ratio()
        self._close_preview_source()
        window_geometry = self._current_window_geometry()
        if self._preview_panel_visible:
            self.update_idletasks()
            preview_allocation = max(0, self.root_container.winfo_width() - self.panel.winfo_width())
            if preview_allocation > 0:
                collapsed_width = max(BASE_WINDOW_MIN_WIDTH, self.winfo_width() - preview_allocation)
                window_geometry = f"{collapsed_width}x{self.winfo_height()}+{self.winfo_x()}+{self.winfo_y()}"
        try:
            save_ui_state(
                STATE_PATH,
                target_format=self.target_var.get(),
                specify_output_dir=self.specify_output_var.get(),
                output_dir=self.output_dir_var.get(),
                input_dir=self.input_var.get(),
                window_geometry=window_geometry,
                preview_split_ratio=self._preview_split_ratio,
                expand_to_format=self.expand_to_format_var.get(),
                expand_bias_percent=self.expand_bias_var.get(),
            )
        except RuntimeError as exc:
            self._append_status(f"Warning: {exc}")
        self.destroy()

    def _browse_input(self) -> None:
        dialog_kwargs: dict[str, str] = {}
        initial_dir = browse_initial_directory(self.input_var.get())
        if initial_dir:
            dialog_kwargs["initialdir"] = initial_dir
        file_path = filedialog.askopenfilename(**dialog_kwargs)
        if file_path:
            self.input_var.set(file_path)
            self.input_field.set_error(False)

    def _browse_output(self) -> None:
        folder = filedialog.askdirectory()
        if folder:
            self.output_dir_var.set(folder)
            self.output_field.set_error(False)

    def _toggle_output_controls(self) -> None:
        if self.specify_output_var.get():
            self.output_row.grid()
        else:
            self.output_row.grid_remove()

    def _append_status(self, message: str, *, error: bool = False) -> None:
        tag = "stderr" if error else "stdout"
        prefix = "ERROR: " if error else ""
        self.status.configure(state=tk.NORMAL)
        self.status.insert(tk.END, f"{prefix}{message}\n", tag)
        self.status.configure(state=tk.DISABLED)
        self.status.see(tk.END)

    def _clear_validation(self) -> None:
        self.input_field.set_error(False)
        self.output_field.set_error(False)

    def _resolve_run_inputs(self) -> tuple[Path, str, Path | None, bool, float]:
        self._clear_validation()

        if not SCRIPT_PATH.exists():
            raise ValueError(f"Script not found: {SCRIPT_PATH}")

        input_text = self.input_var.get().strip()
        if not input_text:
            self.input_field.set_error(True)
            raise ValueError("Input file is required.")

        input_path = Path(input_text).expanduser().resolve()
        if not input_path.exists() or not input_path.is_file():
            self.input_field.set_error(True)
            raise ValueError(f"Input path does not exist or is not a file: {input_path}")

        target = normalize_target_format(self.target_var.get())
        expand_enabled = bool(self.expand_to_format_var.get())
        expand_bias = clamp_expand_bias_percent(self.expand_bias_var.get(), default=EXPAND_DEFAULT_BIAS_PERCENT)

        if not self.specify_output_var.get():
            return input_path, target, None, expand_enabled, expand_bias

        output_dir = resolve_output_directory(
            input_path=input_path,
            explicit_enabled=True,
            explicit_dir_value=self.output_dir_var.get(),
        )
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self.output_field.set_error(True)
            raise ValueError(f"Unable to create output directory '{output_dir}': {exc}") from exc

        output_pdf = build_output_pdf_path(
            input_path=input_path,
            target_format=target,
            output_dir=output_dir,
        )
        return input_path, target, output_pdf, expand_enabled, expand_bias

    def _run(self) -> None:
        if self._run_thread and self._run_thread.is_alive():
            self._append_status("A run is already in progress.", error=True)
            return

        try:
            input_path, target, output_path, expand_enabled, expand_bias = self._resolve_run_inputs()
        except ValueError as exc:
            self._append_status(str(exc), error=True)
            return

        command = build_command(
            python_executable=sys.executable,
            script_path=SCRIPT_PATH,
            input_path=input_path,
            target_format=target,
            output_path=output_path,
            expand_to_format=expand_enabled,
            expand_bias_percent=expand_bias,
        )
        self._last_run_input_path = input_path

        display_command = " ".join(shlex.quote(part) for part in command)
        self._append_status("-" * 60)
        self._append_status(f"Running: {display_command}")
        if output_path is not None:
            self._append_status(f"Explicit output path: {output_path}")
        if expand_enabled:
            self._append_status(f"Expand to format enabled (bias={expand_bias:.1f}%).")

        self.run_button.state(["disabled"])
        self._run_thread = threading.Thread(
            target=self._run_worker,
            args=(command,),
            daemon=True,
        )
        self._run_thread.start()

    def _run_worker(self, command: list[str]) -> None:
        try:
            code = run_command_streaming(
                command=command,
                cwd=SCRIPT_CWD,
                on_stdout=lambda line: self._event_queue.put(("stdout", line)),
                on_stderr=lambda line: self._event_queue.put(("stderr", line)),
            )
        except Exception as exc:  # noqa: BLE001
            self._event_queue.put(("stderr", str(exc)))
            code = 1
        self._event_queue.put(("done", code))

    def _open_folder(self) -> None:
        try:
            folder = resolve_open_folder(
                input_path_value=self.input_var.get(),
                explicit_enabled=self.specify_output_var.get(),
                explicit_dir_value=self.output_dir_var.get(),
            )
            command = open_folder(folder)
            self._append_status(f"Opened folder: {folder}")
            self._append_status(f"Command: {' '.join(command)}")
        except Exception as exc:  # noqa: BLE001
            self._append_status(str(exc), error=True)

    def _drain_queue(self) -> None:
        while True:
            try:
                channel, payload = self._event_queue.get_nowait()
            except queue.Empty:
                break

            if channel == "stdout":
                self._append_status(str(payload))
            elif channel == "stderr":
                self._append_status(str(payload), error=True)
            elif channel == "done":
                code = int(payload)
                if code == 0:
                    self._append_status("Run completed successfully.")
                else:
                    self._append_status(f"Run failed with exit code {code}.", error=True)
                self.run_button.state(["!disabled"])
                if self._last_run_input_path is not None:
                    self.input_var.set(retained_input_value_after_run(self._last_run_input_path))
                else:
                    self.input_var.set("")
                self._active_input_document = None
                self._reset_expand_state_for_document()
                self.input_entry.focus_set()
            elif channel == "preview_loaded":
                if isinstance(payload, dict):
                    self._handle_preview_loaded(payload)
            elif channel == "preview_error":
                if isinstance(payload, dict):
                    self._handle_preview_error(payload)

        self.after(100, self._drain_queue)


def main() -> int:
    app = GuidecutApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
