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

from guidecut_runner import (
    SUPPORTED_FORMATS,
    browse_initial_directory,
    build_command,
    build_output_pdf_path,
    load_ui_state,
    normalize_target_format,
    open_folder,
    retained_input_value_after_run,
    resolve_open_folder,
    resolve_output_directory,
    run_command_streaming,
    save_ui_state,
    tooltip_text_for_format,
)
from guidecut_theme import COLORS, FONTS, RADIUS, SPACING, apply_ttk_theme


SCRIPT_PATH = Path(__file__).with_name("iso216_guidecut.py")
SCRIPT_CWD = SCRIPT_PATH.parent
STATE_PATH = SCRIPT_CWD / "guidecut_ui_state.json"


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
        self.minsize(760, 460)

        self.input_var = tk.StringVar()
        self.target_var = tk.StringVar(value="a2")
        self.specify_output_var = tk.BooleanVar(value=False)
        self.output_dir_var = tk.StringVar()

        self._event_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self._run_thread: threading.Thread | None = None
        self._last_run_input_path: Path | None = None
        self._startup_warnings: list[str] = []

        self._style = apply_ttk_theme(self)
        self._load_persisted_state()
        self._build_ui()
        self._toggle_output_controls()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        for warning in self._startup_warnings:
            self._append_status(f"Warning: {warning}")
        self.after(100, self._drain_queue)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        root = ttk.Frame(self, style="App.TFrame", padding=SPACING["md"])
        root.grid(row=0, column=0, sticky="nsew")
        root.rowconfigure(6, weight=1)

        panel = ttk.Frame(root, style="Panel.TFrame", padding=SPACING["md"])
        panel.grid(row=0, column=0, sticky="nsew")
        panel.columnconfigure(1, weight=1)
        panel.rowconfigure(6, weight=1)
        root.rowconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)

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

        ttk.Label(panel, text="Target Format", style="Form.TLabel").grid(
            row=2,
            column=0,
            sticky="w",
            padx=(0, SPACING["sm"]),
            pady=(0, SPACING["sm"]),
        )
        self.target_field = RoundedField(panel, radius=RADIUS["sm"], fill=COLORS["bg.input"])
        self.target_field.grid(row=2, column=1, sticky="ew", pady=(0, SPACING["sm"]))
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
            padx=SPACING["sm"],
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
            self.target_menu.add_radiobutton(label=fmt.upper(), value=fmt, variable=self.target_var)
        self.target_menu_button.configure(menu=self.target_menu)
        self.target_menu_button.pack(fill="x", expand=True, padx=SPACING["sm"], pady=SPACING["xs"])
        self.target_field.bind_focus_widget(self.target_menu_button)

        self.info_button = RoundedButton(
            panel,
            text="i",
            command=lambda: None,
            variant="secondary",
            radius=RADIUS["sm"],
            min_width=34,
            takefocus=True,
        )
        self.info_button.grid(row=2, column=2, padx=(SPACING["sm"], 0), pady=(0, SPACING["sm"]), sticky="e")
        self.info_tooltip = HoverTooltip(self.info_button, self._format_tooltip_text)
        self.target_var.trace_add("write", lambda *_args: self.info_tooltip.refresh())

        self.output_toggle = ttk.Checkbutton(
            panel,
            text="Specify output directory",
            variable=self.specify_output_var,
            command=self._toggle_output_controls,
        )
        self.output_toggle.grid(row=3, column=0, columnspan=3, sticky="w", pady=(0, SPACING["sm"]))

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

        button_row = ttk.Frame(panel, style="Panel.TFrame")
        button_row.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(0, SPACING["sm"]))
        button_row.columnconfigure(0, weight=1)
        self.open_button = RoundedButton(
            button_row,
            text="Open Folder",
            command=self._open_folder,
            variant="secondary",
            radius=RADIUS["sm"],
            min_width=120,
        )
        self.open_button.grid(row=0, column=1, padx=(SPACING["sm"], 0))
        self.run_button = RoundedButton(
            button_row,
            text="Run",
            command=self._run,
            variant="primary",
            radius=RADIUS["sm"],
            min_width=90,
        )
        self.run_button.grid(row=0, column=2, padx=(SPACING["sm"], 0))

        status_container = ttk.Frame(panel, style="Status.TFrame", padding=1)
        status_container.grid(row=6, column=0, columnspan=3, sticky="nsew")
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

    def _format_tooltip_text(self) -> str:
        try:
            return tooltip_text_for_format(self.target_var.get())
        except ValueError:
            return "Unsupported format."

    def _load_persisted_state(self) -> None:
        try:
            state = load_ui_state(STATE_PATH)
        except RuntimeError as exc:
            self._startup_warnings.append(str(exc))
            return

        self.target_var.set(state["target_format"])
        self.specify_output_var.set(bool(state["specify_output_dir"]))
        self.output_dir_var.set(state["output_dir"])

    def _on_close(self) -> None:
        try:
            save_ui_state(
                STATE_PATH,
                target_format=self.target_var.get(),
                specify_output_dir=self.specify_output_var.get(),
                output_dir=self.output_dir_var.get(),
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

    def _resolve_run_inputs(self) -> tuple[Path, str, Path | None]:
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

        if not self.specify_output_var.get():
            return input_path, target, None

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
        return input_path, target, output_pdf

    def _run(self) -> None:
        if self._run_thread and self._run_thread.is_alive():
            self._append_status("A run is already in progress.", error=True)
            return

        try:
            input_path, target, output_path = self._resolve_run_inputs()
        except ValueError as exc:
            self._append_status(str(exc), error=True)
            return

        command = build_command(
            python_executable=sys.executable,
            script_path=SCRIPT_PATH,
            input_path=input_path,
            target_format=target,
            output_path=output_path,
        )
        self._last_run_input_path = input_path

        display_command = " ".join(shlex.quote(part) for part in command)
        self._append_status("-" * 60)
        self._append_status(f"Running: {display_command}")
        if output_path is not None:
            self._append_status(f"Explicit output path: {output_path}")

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
        self._event_queue.put(("done", str(code)))

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
                channel, text = self._event_queue.get_nowait()
            except queue.Empty:
                break

            if channel == "stdout":
                self._append_status(text)
            elif channel == "stderr":
                self._append_status(text, error=True)
            elif channel == "done":
                code = int(text)
                if code == 0:
                    self._append_status("Run completed successfully.")
                else:
                    self._append_status(f"Run failed with exit code {code}.", error=True)
                self.run_button.state(["!disabled"])
                if self._last_run_input_path is not None:
                    self.input_var.set(retained_input_value_after_run(self._last_run_input_path))
                else:
                    self.input_var.set("")
                self.input_entry.focus_set()

        self.after(100, self._drain_queue)


def main() -> int:
    app = GuidecutApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
