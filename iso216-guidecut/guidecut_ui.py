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
    build_command,
    build_output_pdf_path,
    normalize_target_format,
    open_folder,
    resolve_open_folder,
    resolve_output_directory,
    run_command_streaming,
    tooltip_text_for_format,
)


SCRIPT_PATH = Path(__file__).with_name("iso216_guidecut.py")
SCRIPT_CWD = SCRIPT_PATH.parent


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
            background="#FFFFE0",
            relief=tk.SOLID,
            borderwidth=1,
            padx=6,
            pady=4,
        )
        self._label.pack()

    def _hide(self, _event=None) -> None:
        if self._window is None:
            return
        self._window.destroy()
        self._window = None
        self._label = None

    def refresh(self) -> None:
        if self._label is not None:
            self._label.configure(text=self.text_provider())


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

        self._build_ui()
        self.after(100, self._drain_queue)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        root = ttk.Frame(self, padding=12)
        root.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(1, weight=1)
        root.rowconfigure(6, weight=1)

        usage_text = (
            "Usage: 1) Choose an input file. 2) Select target format. "
            "3) Optionally set output directory. 4) Click Run."
        )
        ttk.Label(root, text=usage_text, justify=tk.LEFT, wraplength=720).grid(
            row=0,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(0, 10),
        )

        ttk.Label(root, text="Input File").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
        self.input_entry = ttk.Entry(root, textvariable=self.input_var)
        self.input_entry.grid(row=1, column=1, sticky="ew", pady=(0, 8))
        ttk.Button(root, text="Browse...", command=self._browse_input).grid(
            row=1,
            column=2,
            padx=(8, 0),
            pady=(0, 8),
        )

        ttk.Label(root, text="Target Format").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=(0, 8))
        self.target_combo = ttk.Combobox(
            root,
            textvariable=self.target_var,
            values=list(SUPPORTED_FORMATS),
            state="readonly",
        )
        self.target_combo.grid(row=2, column=1, sticky="ew", pady=(0, 8))

        self.info_button = ttk.Button(root, text="i", width=3, command=lambda: None, takefocus=True)
        self.info_button.grid(row=2, column=2, padx=(8, 0), pady=(0, 8), sticky="e")
        self.info_tooltip = HoverTooltip(self.info_button, self._format_tooltip_text)
        self.target_var.trace_add("write", lambda *_args: self.info_tooltip.refresh())

        self.output_toggle = ttk.Checkbutton(
            root,
            text="Specify output directory",
            variable=self.specify_output_var,
            command=self._toggle_output_controls,
        )
        self.output_toggle.grid(row=3, column=0, columnspan=3, sticky="w", pady=(0, 8))

        self.output_row = ttk.Frame(root)
        self.output_row.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        self.output_row.columnconfigure(0, weight=1)
        self.output_entry = ttk.Entry(self.output_row, textvariable=self.output_dir_var)
        self.output_entry.grid(row=0, column=0, sticky="ew")
        self.output_browse = ttk.Button(self.output_row, text="Browse Output...", command=self._browse_output)
        self.output_browse.grid(row=0, column=1, padx=(8, 0))
        self.output_row.grid_remove()

        button_row = ttk.Frame(root)
        button_row.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        button_row.columnconfigure(0, weight=1)
        self.open_button = ttk.Button(button_row, text="Open Folder", command=self._open_folder)
        self.open_button.grid(row=0, column=1, padx=(8, 0))
        self.run_button = ttk.Button(button_row, text="Run", command=self._run)
        self.run_button.grid(row=0, column=2, padx=(8, 0))

        self.status = ScrolledText(root, wrap=tk.WORD, height=14, state=tk.DISABLED)
        self.status.grid(row=6, column=0, columnspan=3, sticky="nsew")

    def _format_tooltip_text(self) -> str:
        try:
            return tooltip_text_for_format(self.target_var.get())
        except ValueError:
            return "Unsupported format."

    def _browse_input(self) -> None:
        file_path = filedialog.askopenfilename()
        if file_path:
            self.input_var.set(file_path)

    def _browse_output(self) -> None:
        folder = filedialog.askdirectory()
        if folder:
            self.output_dir_var.set(folder)

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

    def _resolve_run_inputs(self) -> tuple[Path, str, Path | None]:
        if not SCRIPT_PATH.exists():
            raise ValueError(f"Script not found: {SCRIPT_PATH}")

        input_text = self.input_var.get().strip()
        if not input_text:
            raise ValueError("Input file is required.")

        input_path = Path(input_text).expanduser().resolve()
        if not input_path.exists() or not input_path.is_file():
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
                self.input_var.set("")
                self.input_entry.focus_set()

        self.after(100, self._drain_queue)


def main() -> int:
    app = GuidecutApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
