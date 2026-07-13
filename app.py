"""PixelBatch desktop entry point."""

from __future__ import annotations

import os
import queue
import threading
from pathlib import Path
from typing import Any, Callable

import customtkinter as ctk
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox
from PIL import Image

from modules.add_background import AddBackgroundOptions, add_background_batch
from modules.canvas_processor import CanvasOptions, normalize_hex_color, process_canvas
from modules.convert import CONVERSIONS, ConvertOptions, convert_batch
from modules.csv_processor import CsvSelection, preview_csv
from modules.generator import GenerationBatchOptions, ImageGenerationService
from modules.image_optimizer import size_to_bytes
from modules.logging_service import LoggingService
from modules.paths import display_settings_path, resource_path
from modules.providers import ProviderFactory
from modules.remove_bg import MODEL_INFO, RemoveBackgroundOptions, remove_background_batch
from modules.rename_files import (
    RenameOptions, RenamePreviewItem, build_preview, collect_files, execute_rename,
)
from modules.resize import RESIZE_MODES, ResizeOptions, resize_batch
from modules.settings import CredentialStoreError, PROVIDER_NAMES, SettingsManager
from i18n import I18nManager
from theme import (
    ACCENT, ACCENT_HOVER, ACCENT_SOFT, ACCENT_TEXT, APP_BG, BORDER, ERROR, ERROR_SOFT,
    INFO, INFO_SOFT, SIDEBAR_BG, SURFACE, SURFACE_ALT, TEXT_MUTED, TEXT_PRIMARY,
    WARNING, WARNING_SOFT,
)


APP_TITLE = "PixelBatch"
APP_VERSION = "0.1.0-alpha"
APP_SUBTITLE = "Batch Image Processing Desktop Tool"
CARD = SURFACE


class Tooltip:
    """Small Tk tooltip for full local paths without showing them inline."""

    def __init__(self, widget: Any, text_getter: Callable[[], str]) -> None:
        self.widget = widget
        self.text_getter = text_getter
        self.window: tk.Toplevel | None = None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")

    def show(self, _event: tk.Event | None = None) -> None:
        self.hide()
        text = self.text_getter()
        if not text:
            return
        x = self.widget.winfo_rootx() + 18
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.window,
            text=text,
            justify="left",
            background="#111827",
            foreground="white",
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=5,
        )
        label.pack()

    def hide(self, _event: tk.Event | None = None) -> None:
        if self.window is not None:
            self.window.destroy()
            self.window = None


class BasePage(ctk.CTkScrollableFrame):
    """Shared layout and progress/log behaviour for operation pages."""

    def __init__(self, master: ctk.CTkFrame, app: "ToolkitApp", title: str, subtitle: str) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(self, text=title, font=ctk.CTkFont(size=28, weight="bold"), anchor="w").grid(
            row=0, column=0, sticky="ew", padx=30, pady=(26, 2)
        )
        ctk.CTkLabel(self, text=subtitle, text_color=TEXT_MUTED, anchor="w", justify="left", wraplength=720).grid(
            row=1, column=0, sticky="ew", padx=30, pady=(0, 18)
        )

        self.form = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12, border_width=1, border_color=BORDER)
        self.form.grid(row=2, column=0, sticky="ew", padx=30)
        self.form.grid_columnconfigure(1, weight=1)

        self.log_card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12, border_width=1, border_color=BORDER)
        self.log_card.grid(row=3, column=0, sticky="nsew", padx=30, pady=(16, 14))
        self.log_card.grid_columnconfigure(0, weight=1)
        self.log_card.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(self.log_card, text=app.t("Log"), font=ctk.CTkFont(weight="bold"), anchor="w").grid(
            row=0, column=0, sticky="ew", padx=18, pady=(14, 7)
        )
        self.log_box = ctk.CTkTextbox(self.log_card, wrap="word", height=130, border_width=0)
        self.log_box.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 10))
        self.log_box.configure(state="disabled")
        self.progress = ctk.CTkProgressBar(self.log_card, progress_color=ACCENT)
        self.progress.grid(row=2, column=0, sticky="ew", padx=18, pady=(0, 15))
        self.progress.set(0)
        self.stats_label = ctk.CTkLabel(
            self.log_card,
            text=app.t("Processed: 0 / 0   Successful: 0   Errors: 0   Skipped: 0"),
            text_color=TEXT_MUTED,
            anchor="w",
        )
        self.stats_label.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 14))
        self.start_button: ctk.CTkButton | None = None
        self.cancel_button: ctk.CTkButton | None = None

    def add_path_row(
        self,
        row: int,
        label: str,
        variable: tk.StringVar,
        command: Callable[[], None],
        button_text: str = "Select",
    ) -> None:
        ctk.CTkLabel(self.form, text=label, anchor="w").grid(row=row, column=0, sticky="w", padx=(20, 12), pady=8)
        ctk.CTkEntry(self.form, textvariable=variable).grid(row=row, column=1, sticky="ew", pady=8)
        ctk.CTkButton(
            self.form,
            text=button_text,
            width=100,
            fg_color=SURFACE_ALT,
            hover_color=ACCENT_SOFT,
            text_color=TEXT_PRIMARY,
            border_color=BORDER,
            border_width=1,
            command=command,
        ).grid(row=row, column=2, padx=(12, 20), pady=8)

    def add_actions(self, row: int, command: Callable[[], None]) -> None:
        action_frame = ctk.CTkFrame(self.form, fg_color="transparent")
        action_frame.grid(row=row, column=0, columnspan=3, sticky="ew", padx=20, pady=(12, 20))
        self.start_button = ctk.CTkButton(
            action_frame,
            text=self.app.t("Start"),
            width=150,
            height=38,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(weight="bold"),
            command=command,
        )
        self.start_button.pack(side="left")
        self.cancel_button = ctk.CTkButton(
            action_frame,
            text=self.app.t("Cancel"),
            width=110,
            height=38,
            fg_color="transparent",
            border_width=1,
            text_color=TEXT_MUTED,
            state="disabled",
            command=self.app.cancel_task,
        )
        self.cancel_button.pack(side="left", padx=10)

    def set_running(self, running: bool) -> None:
        if self.start_button:
            self.start_button.configure(state="disabled" if running else "normal")
        if self.cancel_button:
            self.cancel_button.configure(state="normal" if running else "disabled")

    def clear_log(self) -> None:
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self.progress.set(0)
        self.stats_label.configure(text=self.app.t("Processed: 0 / 0   Successful: 0   Errors: 0   Skipped: 0"))

    def append_log(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message.rstrip() + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def set_progress(self, current: int, total: int) -> None:
        self.progress.set(current / total if total else 0)
        self.stats_label.configure(text=self.app.t("Processed") + f": {current} / {total}")

    def set_summary(self, result: Any) -> None:
        total = getattr(result, "total", 0)
        successful = getattr(result, "succeeded", 0)
        errors = getattr(result, "failed", 0)
        skipped = getattr(result, "skipped", 0)
        processed = successful + errors + skipped
        self.stats_label.configure(
            text=(f"{self.app.t('Processed')}: {processed} / {total}   {self.app.t('Successful')}: {successful}   "
                  f"{self.app.t('Errors')}: {errors}   {self.app.t('Skipped')}: {skipped}")
        )

    def choose_input_folder(self, variable: tk.StringVar, output: tk.StringVar, suffix: str) -> None:
        selected = filedialog.askdirectory(title=self.app.t("Choose a folder with images"))
        if selected:
            variable.set(selected)
            if not output.get().strip():
                output.set(str(Path(selected) / suffix))

    def choose_output_folder(self, variable: tk.StringVar) -> None:
        selected = filedialog.askdirectory(title=self.app.t("Choose an output folder"))
        if selected:
            variable.set(selected)

    def refresh_texts(self) -> None:
        self.app.localize_widget_tree(self)


class GeneratePage(BasePage):
    def __init__(self, master: ctk.CTkFrame, app: "ToolkitApp") -> None:
        super().__init__(
            master,
            app,
            app.t("Generate Images"),
            app.t("Experimental AI image generation from CSV through the selected provider"),
        )
        self.csv_path = tk.StringVar()
        self.output_path = tk.StringVar()
        ui = app.settings.get("ui", {})
        self.range_mode = tk.StringVar(value=ui.get("csv_mode", "All rows"))
        self.first_n = tk.StringVar(value=str(ui.get("first_n", 5)))
        self.from_row = tk.StringVar(value=str(ui.get("from_row", 1)))
        self.to_row = tk.StringVar(value=str(ui.get("to_row", 10)))
        self.skip_first = tk.StringVar(value=str(ui.get("skip_first_rows", 0)))
        self.prompt_column = tk.StringVar(value="prompt")
        self.prompt_template = tk.StringVar(value="{prompt}")
        self.output_format = tk.StringVar(value=ui.get("output_format", "PNG"))
        self.skip_existing = tk.BooleanVar(value=True)
        self.limit_size = tk.BooleanVar(value=False)
        self.allow_reduction = tk.BooleanVar(value=False)
        self.max_size = tk.StringVar(value="2")
        self.size_unit = tk.StringVar(value="MB")
        self.min_quality = tk.StringVar(value="60")

        self.add_path_row(0, app.t("CSV file"), self.csv_path, self._choose_csv, app.t("Browse"))
        self.add_path_row(1, app.t("Output folder"), self.output_path, lambda: self.choose_output_folder(self.output_path))
        self.provider_label = ctk.CTkLabel(self.form, text="", anchor="w", justify="left")
        self.provider_label.grid(row=2, column=0, columnspan=2, sticky="ew", padx=20, pady=8)
        ctk.CTkButton(self.form, text="Open Settings", width=120, command=lambda: app.navigate_to("settings")).grid(
            row=2, column=2, padx=(12, 20), pady=8
        )
        ctk.CTkLabel(self.form, text="CSV processing range", font=ctk.CTkFont(weight="bold")).grid(
            row=3, column=0, sticky="w", padx=20, pady=(14, 4)
        )
        range_frame = ctk.CTkFrame(self.form, fg_color="transparent")
        range_frame.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(0, 20), pady=(14, 4))
        ctk.CTkOptionMenu(range_frame, values=["All rows", "First N rows", "Row range"], variable=self.range_mode).pack(side="left")
        ctk.CTkLabel(range_frame, text="Skip first rows").pack(side="left", padx=(16, 6))
        ctk.CTkEntry(range_frame, textvariable=self.skip_first, width=65).pack(side="left")
        number_frame = ctk.CTkFrame(self.form, fg_color="transparent")
        number_frame.grid(row=4, column=1, columnspan=2, sticky="w", padx=(0, 20), pady=4)
        for label, variable in (("First N", self.first_n), ("From", self.from_row), ("To", self.to_row)):
            ctk.CTkLabel(number_frame, text=label).pack(side="left", padx=(0, 6))
            ctk.CTkEntry(number_frame, textvariable=variable, width=70).pack(side="left", padx=(0, 14))
        self.preview_label = ctk.CTkLabel(self.form, text="CSV not checked", text_color=TEXT_MUTED, anchor="w", justify="left")
        self.preview_label.grid(row=5, column=1, sticky="ew", pady=6)
        ctk.CTkButton(self.form, text="Check CSV", width=100, command=self.check_csv).grid(row=5, column=2, padx=(12, 20), pady=6)
        prompt_frame = ctk.CTkFrame(self.form, fg_color="transparent")
        prompt_frame.grid(row=6, column=0, columnspan=3, sticky="ew", padx=20, pady=6)
        ctk.CTkLabel(prompt_frame, text="Prompt column").pack(side="left")
        ctk.CTkEntry(prompt_frame, textvariable=self.prompt_column, width=100).pack(side="left", padx=8)
        ctk.CTkLabel(prompt_frame, text="Prompt template").pack(side="left", padx=(12, 6))
        ctk.CTkEntry(prompt_frame, textvariable=self.prompt_template).pack(side="left", fill="x", expand=True)
        options_frame = ctk.CTkFrame(self.form, fg_color="transparent")
        options_frame.grid(row=7, column=0, columnspan=3, sticky="ew", padx=20, pady=8)
        ctk.CTkLabel(options_frame, text="Output format").pack(side="left")
        ctk.CTkOptionMenu(options_frame, values=["PNG", "JPG", "JPEG", "WEBP"], variable=self.output_format, width=90).pack(side="left", padx=8)
        ctk.CTkCheckBox(options_frame, text="Skip existing files", variable=self.skip_existing).pack(side="left", padx=12)
        ctk.CTkCheckBox(options_frame, text="Limit maximum file size", variable=self.limit_size).pack(side="left", padx=12)
        size_frame = ctk.CTkFrame(self.form, fg_color="transparent")
        size_frame.grid(row=8, column=0, columnspan=3, sticky="w", padx=20, pady=4)
        ctk.CTkLabel(size_frame, text="Maximum size").pack(side="left")
        ctk.CTkEntry(size_frame, textvariable=self.max_size, width=70).pack(side="left", padx=8)
        ctk.CTkOptionMenu(size_frame, values=["KB", "MB"], variable=self.size_unit, width=70).pack(side="left")
        ctk.CTkLabel(size_frame, text="Minimum quality").pack(side="left", padx=(18, 6))
        ctk.CTkEntry(size_frame, textvariable=self.min_quality, width=60).pack(side="left")
        ctk.CTkCheckBox(size_frame, text="Allow resolution reduction", variable=self.allow_reduction).pack(side="left", padx=16)
        self.add_actions(9, self.start)
        self.refresh_provider()

    def _choose_csv(self) -> None:
        selected = filedialog.askopenfilename(
            title=self.app.t("Choose CSV"),
            filetypes=[(self.app.t("CSV files"), "*.csv"), (self.app.t("All files"), "*.*")],
        )
        if selected:
            self.csv_path.set(selected)
            if not self.output_path.get().strip():
                self.output_path.set(str(Path(selected).parent / "generated_images"))

    def refresh_provider(self) -> None:
        provider_id = self.app.settings.active_provider_id()
        config = self.app.settings.provider_config(provider_id)
        configured = bool(self.app.settings.api_key(provider_id) and config.get("model"))
        self.provider_label.configure(
            text=(f"{self.app.t('Active provider')}: {PROVIDER_NAMES[provider_id]}\n"
                  f"{self.app.t('Model')}: {config.get('model', '')}\n"
                  f"{self.app.t('Status')}: {self.app.t('Configured' if configured else 'Not configured')}")
        )

    def on_show(self) -> None:
        self.refresh_provider()

    def validate_generation_credentials(self) -> tuple[bool, str]:
        provider_id = self.app.settings.active_provider_id()
        config = self.app.settings.provider_config(provider_id)
        if not provider_id:
            return False, self.app.t("No image generation provider is selected.")
        if not self.app.settings.api_key(provider_id):
            return False, self.app.t("The selected provider requires an API key to generate images.")
        if not config.get("model"):
            return False, self.app.t("Set a model in Settings before generating images.")
        return True, ""

    def _selection(self) -> CsvSelection:
        try:
            return CsvSelection(
                self.app.i18n.canonical(self.range_mode.get()), int(self.first_n.get()), int(self.from_row.get()), int(self.to_row.get()), int(self.skip_first.get())
            )
        except ValueError as exc:
            raise ValueError("CSV range values must be integers") from exc

    def check_csv(self) -> Any:
        csv_path = self.csv_path.get().strip()
        if not csv_path:
            messagebox.showwarning(APP_TITLE, self.app.t("Select a CSV file first."))
            return None
        try:
            preview = preview_csv(
                csv_path, self._selection(), self.prompt_column.get().strip(), self.prompt_template.get()
            )
        except ValueError as exc:
            self.preview_label.configure(text=f"{self.app.t('Error')}: {self.app.user_message(str(exc))}")
            messagebox.showerror(APP_TITLE, self.app.user_message(str(exc)))
            return None
        self.preview_label.configure(
            text=(f"{self.app.t('Total data rows')}: {preview.total_rows}   "
                  f"{self.app.t('Selected rows')}: {len(preview.selected_rows)}\n"
                  f"{self.app.t('Rows to process')}: {preview.row_display}   "
                  f"{self.app.t('Invalid rows')}: {len(preview.invalid_rows)}")
        )
        return preview

    def start(self) -> None:
        csv_path = self.csv_path.get().strip()
        output = self.output_path.get().strip()
        if not csv_path or not output:
            messagebox.showwarning(APP_TITLE, self.app.t("Select a CSV file and an output folder."))
            return
        credentials_valid, credentials_error = self.validate_generation_credentials()
        if not credentials_valid:
            if self.app.show_api_key_required_dialog(credentials_error):
                self.app.navigate_to("settings")
            return
        preview = self.check_csv()
        if preview is None or not preview.valid_rows:
            messagebox.showerror(APP_TITLE, self.app.t("The selected range has no valid rows to process."))
            return
        for invalid in preview.invalid_rows:
            self.append_log(f"ERROR {invalid.error}")
        try:
            max_bytes = size_to_bytes(float(self.max_size.get()), self.size_unit.get()) if self.limit_size.get() else None
            min_quality = int(self.min_quality.get())
        except ValueError as exc:
            messagebox.showerror(APP_TITLE, self.app.user_message(str(exc)))
            return
        batch_options = GenerationBatchOptions(
            self.output_format.get(), self.skip_existing.get(), max_bytes, self.allow_reduction.get(), min_quality
        )

        def work(log: Callable[[str], None], progress: Callable[[int, int], None], cancel: threading.Event) -> Any:
            service = ImageGenerationService(self.app.settings)
            return service.generate_batch(preview.valid_rows, output, batch_options, log, progress, cancel)

        self.app.run_task(self, self.app.t("Generate Images"), work)


class RemoveBackgroundPage(BasePage):
    def __init__(self, master: ctk.CTkFrame, app: "ToolkitApp") -> None:
        super().__init__(master, app, app.t("Remove Background"), app.t("Batch background removal with local rembg models"))
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.model = tk.StringVar(value="BiRefNet General")
        self.output_format = tk.StringVar(value="PNG")
        self.skip_existing = tk.BooleanVar(value=True)
        self.limit_size = tk.BooleanVar(value=False)
        self.allow_reduction = tk.BooleanVar(value=False)
        self.max_size = tk.StringVar(value="2")
        self.size_unit = tk.StringVar(value="MB")
        self.add_path_row(
            0,
            app.t("Input folder"),
            self.input_path,
            lambda: self.choose_input_folder(self.input_path, self.output_path, "removed_background"),
        )
        self.add_path_row(1, app.t("Output folder"), self.output_path, lambda: self.choose_output_folder(self.output_path))
        ctk.CTkLabel(self.form, text="Model", anchor="w").grid(row=2, column=0, sticky="w", padx=(20, 12), pady=8)
        menu = ctk.CTkOptionMenu(
            self.form,
            values=list(MODEL_INFO),
            variable=self.model,
            fg_color=ACCENT,
            button_color=ACCENT_HOVER,
            command=lambda _value: self._update_hint(),
        )
        menu.grid(row=2, column=1, columnspan=2, sticky="ew", padx=(0, 20), pady=8)
        self.hint = ctk.CTkLabel(self.form, text="", text_color=TEXT_MUTED, anchor="w", justify="left")
        self.hint.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(0, 20), pady=(0, 8))
        self._update_hint()
        options = ctk.CTkFrame(self.form, fg_color="transparent")
        options.grid(row=4, column=0, columnspan=3, sticky="w", padx=20, pady=6)
        ctk.CTkLabel(options, text="Output").pack(side="left")
        ctk.CTkOptionMenu(options, values=["PNG", "WEBP"], variable=self.output_format, width=85).pack(side="left", padx=8)
        ctk.CTkCheckBox(options, text="Skip existing", variable=self.skip_existing).pack(side="left", padx=10)
        ctk.CTkCheckBox(options, text="Limit size", variable=self.limit_size).pack(side="left", padx=10)
        ctk.CTkEntry(options, textvariable=self.max_size, width=60).pack(side="left", padx=4)
        ctk.CTkOptionMenu(options, values=["KB", "MB"], variable=self.size_unit, width=70).pack(side="left")
        ctk.CTkCheckBox(options, text="Allow resolution reduction", variable=self.allow_reduction).pack(side="left", padx=10)
        self.add_actions(5, self.start)

    def _update_hint(self) -> None:
        info = MODEL_INFO[self.model.get()]
        memory = "high" if "birefnet" in info.model_id or info.model_id == "sam" else "low/medium"
        self.hint.configure(text=(f"{self.app.t('Best for')}: {self.app.t(info.use_case)}  •  "
                                  f"{self.app.t('Speed')}: {self.app.t(info.speed)}  •  "
                                  f"{self.app.t('Memory')}: {self.app.t(memory)}\n{self.app.t(info.hint)}"))

    def start(self) -> None:
        source, output = self.input_path.get().strip(), self.output_path.get().strip()
        if not source or not output:
            messagebox.showwarning(APP_TITLE, self.app.t("Select input and output folders."))
            return
        model = self.model.get()
        try:
            max_bytes = size_to_bytes(float(self.max_size.get()), self.size_unit.get()) if self.limit_size.get() else None
        except ValueError as exc:
            messagebox.showerror(APP_TITLE, self.app.user_message(str(exc)))
            return
        options = RemoveBackgroundOptions(
            self.output_format.get(), self.skip_existing.get(), max_bytes, self.allow_reduction.get()
        )
        self.app.run_task(
            self,
            self.app.t("Remove Background"),
            lambda log, progress, cancel: remove_background_batch(source, output, model, log, progress, cancel, options),
        )


class AddBackgroundPage(BasePage):
    def __init__(self, master: ctk.CTkFrame, app: "ToolkitApp") -> None:
        super().__init__(master, app, app.t("Add Background"), app.t("Background, canvas, centering, and padding for product images"))
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.output_format = tk.StringVar(value="PNG")
        self.color = tk.StringVar(value=app.settings.get("ui", {}).get("background_color", "#FFFFFF"))
        self.transparent = tk.BooleanVar(value=False)
        self.background_image = tk.StringVar()
        self.canvas_mode = tk.StringVar(value="Square canvas")
        self.width = tk.StringVar(value="1200")
        self.height = tk.StringVar(value="1200")
        self.square_side = tk.StringVar(value="1000")
        self.padding = tk.StringVar(value="10")
        self.padding_unit = tk.StringVar(value="%")
        self.crop = tk.BooleanVar(value=True)
        self.preserve = tk.BooleanVar(value=True)
        self.center = tk.BooleanVar(value=True)
        self.upscale = tk.BooleanVar(value=False)
        self.skip_existing = tk.BooleanVar(value=True)
        self.suffix = tk.StringVar(value="_background")
        self.limit_size = tk.BooleanVar(value=False)
        self.max_size = tk.StringVar(value="2")
        self.size_unit = tk.StringVar(value="MB")
        self.allow_reduction = tk.BooleanVar(value=False)
        self._preview_images: list[ctk.CTkImage] = []

        self.add_path_row(0, app.t("Input folder"), self.input_path, lambda: self.choose_input_folder(self.input_path, self.output_path, "backgrounds"))
        self.add_path_row(1, app.t("Output folder"), self.output_path, lambda: self.choose_output_folder(self.output_path))
        color_frame = ctk.CTkFrame(self.form, fg_color="transparent")
        color_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=20, pady=6)
        ctk.CTkLabel(color_frame, text="Background color").pack(side="left")
        color_entry = ctk.CTkEntry(color_frame, textvariable=self.color, width=100)
        color_entry.pack(side="left", padx=8)
        color_entry.bind("<FocusOut>", lambda _event: self._validate_color())
        ctk.CTkButton(color_frame, text="Choose Color", width=105, command=self._choose_color).pack(side="left")
        self.color_preview = ctk.CTkLabel(color_frame, text="", width=36, height=30, corner_radius=6, fg_color=self.color.get())
        self.color_preview.pack(side="left", padx=8)
        for label, value in (("White", "#FFFFFF"), ("Light Gray", "#F5F5F5"), ("Black", "#000000")):
            ctk.CTkButton(color_frame, text=label, width=70, command=lambda v=value: self._quick_color(v)).pack(side="left", padx=3)
        ctk.CTkButton(color_frame, text="Transparent", width=90, command=self._set_transparent).pack(side="left", padx=3)

        self.add_path_row(3, "Background image", self.background_image, self._choose_background_image, "Browse")

        canvas = ctk.CTkFrame(self.form, fg_color="transparent")
        canvas.grid(row=4, column=0, columnspan=3, sticky="ew", padx=20, pady=6)
        ctk.CTkLabel(canvas, text="Canvas size").pack(side="left")
        ctk.CTkOptionMenu(canvas, values=["Keep original size", "Square canvas", "Custom size"], variable=self.canvas_mode, width=150).pack(side="left", padx=8)
        for label, variable in (("Side", self.square_side), ("Width", self.width), ("Height", self.height)):
            ctk.CTkLabel(canvas, text=label).pack(side="left", padx=(8, 3))
            ctk.CTkEntry(canvas, textvariable=variable, width=70).pack(side="left")

        padding = ctk.CTkFrame(self.form, fg_color="transparent")
        padding.grid(row=5, column=0, columnspan=3, sticky="ew", padx=20, pady=6)
        ctk.CTkLabel(padding, text="Object padding").pack(side="left")
        ctk.CTkEntry(padding, textvariable=self.padding, width=70).pack(side="left", padx=8)
        ctk.CTkOptionMenu(padding, values=["%", "px"], variable=self.padding_unit, width=70).pack(side="left")
        ctk.CTkLabel(padding, text="Output format").pack(side="left", padx=(18, 6))
        ctk.CTkOptionMenu(padding, values=["PNG", "JPG", "JPEG", "WEBP"], variable=self.output_format, width=90).pack(side="left")
        ctk.CTkLabel(padding, text="Filename suffix").pack(side="left", padx=(18, 6))
        ctk.CTkEntry(padding, textvariable=self.suffix, width=120).pack(side="left")

        flags = ctk.CTkFrame(self.form, fg_color="transparent")
        flags.grid(row=6, column=0, columnspan=3, sticky="w", padx=20, pady=6)
        for text, variable in (
            ("Crop transparent margins", self.crop), ("Preserve aspect ratio", self.preserve),
            ("Center object", self.center), ("Allow upscaling", self.upscale), ("Skip existing", self.skip_existing),
        ):
            ctk.CTkCheckBox(flags, text=text, variable=variable).pack(side="left", padx=(0, 12))

        limit = ctk.CTkFrame(self.form, fg_color="transparent")
        limit.grid(row=7, column=0, columnspan=3, sticky="w", padx=20, pady=6)
        ctk.CTkCheckBox(limit, text="Limit maximum file size", variable=self.limit_size).pack(side="left")
        ctk.CTkEntry(limit, textvariable=self.max_size, width=65).pack(side="left", padx=6)
        ctk.CTkOptionMenu(limit, values=["KB", "MB"], variable=self.size_unit, width=70).pack(side="left")
        ctk.CTkCheckBox(limit, text="Allow resolution reduction", variable=self.allow_reduction).pack(side="left", padx=12)
        ctk.CTkButton(self.form, text="Preview", command=self.preview, width=110).grid(row=8, column=0, sticky="w", padx=20, pady=8)
        preview_frame = ctk.CTkFrame(self.form, fg_color="transparent")
        preview_frame.grid(row=8, column=1, columnspan=2, sticky="ew", padx=(0, 20), pady=8)
        self.original_preview = ctk.CTkLabel(preview_frame, text="Original preview")
        self.original_preview.pack(side="left", expand=True, padx=6)
        self.result_preview = ctk.CTkLabel(preview_frame, text="Result preview")
        self.result_preview.pack(side="left", expand=True, padx=6)
        self.add_actions(9, self.start)
        if self.start_button:
            self.start_button.configure(text="Process Folder")

    def _validate_color(self) -> bool:
        try:
            normalized = normalize_hex_color(self.color.get())
        except ValueError as exc:
            messagebox.showerror(APP_TITLE, self.app.user_message(str(exc)))
            return False
        self.color.set(normalized)
        self.color_preview.configure(fg_color=normalized)
        self.transparent.set(False)
        self.background_image.set("")
        return True

    def _quick_color(self, value: str) -> None:
        self.color.set(value)
        self.transparent.set(False)
        self.background_image.set("")
        self.color_preview.configure(fg_color=value)

    def _set_transparent(self) -> None:
        self.transparent.set(True)
        self.output_format.set("PNG")
        self.color_preview.configure(fg_color=("#D8D8D8", "#555555"))

    def _choose_color(self) -> None:
        _rgb, value = colorchooser.askcolor(color=self.color.get(), title=self.app.t("Background color"))
        if value:
            self._quick_color(value.upper())

    def _choose_background_image(self) -> None:
        selected = filedialog.askopenfilename(
            title=self.app.t("Choose background image"),
            filetypes=[(self.app.t("Images"), "*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff"), (self.app.t("All files"), "*.*")],
        )
        if selected:
            self.background_image.set(selected)
            self.transparent.set(False)

    def _canvas_options(self) -> CanvasOptions:
        if not self.transparent.get() and not self.background_image.get().strip() and not self._validate_color():
            raise ValueError("Invalid background color")
        return CanvasOptions(
            self.color.get(), self.transparent.get(), self.app.i18n.canonical(self.canvas_mode.get()), int(self.width.get()), int(self.height.get()),
            int(self.square_side.get()), float(self.padding.get()), self.padding_unit.get(), self.crop.get(),
            self.preserve.get(), self.center.get(), self.upscale.get(), self.background_image.get().strip()
        )

    def preview(self) -> None:
        folder = Path(self.input_path.get().strip())
        files = sorted(path for path in folder.iterdir() if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}) if folder.is_dir() else []
        if not files:
            messagebox.showwarning(APP_TITLE, self.app.t("Input folder contains no previewable images."))
            return
        try:
            with Image.open(files[0]) as source:
                original = source.convert("RGBA")
                result = process_canvas(source, self._canvas_options())
            original.thumbnail((220, 180), Image.Resampling.LANCZOS)
            result.thumbnail((220, 180), Image.Resampling.LANCZOS)
            left = ctk.CTkImage(light_image=original, dark_image=original, size=original.size)
            right = ctk.CTkImage(light_image=result, dark_image=result, size=result.size)
            self._preview_images = [left, right]
            self.original_preview.configure(text=files[0].name, image=left, compound="top")
            self.result_preview.configure(text=f"{result.width}×{result.height}", image=right, compound="top")
        except (OSError, ValueError) as exc:
            messagebox.showerror(APP_TITLE, self.app.user_message(str(exc)))

    def start(self) -> None:
        source, output = self.input_path.get().strip(), self.output_path.get().strip()
        if not source or not output:
            messagebox.showwarning(APP_TITLE, self.app.t("Select input and output folders."))
            return
        try:
            canvas = self._canvas_options()
            max_bytes = size_to_bytes(float(self.max_size.get()), self.size_unit.get()) if self.limit_size.get() else None
            options = AddBackgroundOptions(
                canvas, self.output_format.get(), self.suffix.get(), self.skip_existing.get(), max_bytes,
                self.allow_reduction.get(), 60
            )
        except ValueError as exc:
            messagebox.showerror(APP_TITLE, self.app.user_message(str(exc)))
            return
        self.app.run_task(
            self, self.app.t("Add Background"),
            lambda log, progress, cancel: add_background_batch(source, output, options, log, progress, cancel),
        )


class ResizePage(BasePage):
    def __init__(self, master: ctk.CTkFrame, app: "ToolkitApp") -> None:
        super().__init__(master, app, app.t("Resize Images"), app.t("Resize a folder of images with the Lanczos filter"))
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.width = tk.StringVar(value="1024")
        self.height = tk.StringVar(value="1024")
        self.percentage = tk.StringVar(value="50")
        self.mode = tk.StringVar(value=app.t(RESIZE_MODES[0]))
        self.preserve = tk.BooleanVar(value=True)
        self.upscale = tk.BooleanVar(value=False)
        self.skip_existing = tk.BooleanVar(value=True)
        self.limit_size = tk.BooleanVar(value=False)
        self.allow_reduction = tk.BooleanVar(value=False)
        self.max_size = tk.StringVar(value="2")
        self.size_unit = tk.StringVar(value="MB")
        self.add_path_row(
            0,
            app.t("Input folder"),
            self.input_path,
            lambda: self.choose_input_folder(self.input_path, self.output_path, "resized"),
        )
        self.add_path_row(1, app.t("Output folder"), self.output_path, lambda: self.choose_output_folder(self.output_path))
        ctk.CTkLabel(self.form, text="Size (px)", anchor="w").grid(row=2, column=0, sticky="w", padx=(20, 12), pady=8)
        dimensions = ctk.CTkFrame(self.form, fg_color="transparent")
        dimensions.grid(row=2, column=1, columnspan=2, sticky="ew", padx=(0, 20), pady=8)
        ctk.CTkEntry(dimensions, textvariable=self.width, width=110).pack(side="left")
        ctk.CTkLabel(dimensions, text="×", text_color=TEXT_MUTED).pack(side="left", padx=10)
        ctk.CTkEntry(dimensions, textvariable=self.height, width=110).pack(side="left")
        ctk.CTkOptionMenu(
            dimensions,
            values=[app.t("Stretch" if mode == "Exact" else mode) for mode in RESIZE_MODES],
            variable=self.mode,
            fg_color=ACCENT,
            button_color=ACCENT_HOVER,
            width=210,
        ).pack(side="left", padx=(18, 0))
        ctk.CTkLabel(dimensions, text="Percent").pack(side="left", padx=(12, 4))
        ctk.CTkEntry(dimensions, textvariable=self.percentage, width=60).pack(side="left")
        flags = ctk.CTkFrame(self.form, fg_color="transparent")
        flags.grid(row=3, column=0, columnspan=3, sticky="w", padx=20, pady=6)
        for text, variable in (("Preserve aspect ratio", self.preserve), ("Allow upscaling", self.upscale), ("Skip existing", self.skip_existing), ("Limit size", self.limit_size)):
            ctk.CTkCheckBox(flags, text=text, variable=variable).pack(side="left", padx=(0, 12))
        ctk.CTkEntry(flags, textvariable=self.max_size, width=60).pack(side="left", padx=4)
        ctk.CTkOptionMenu(flags, values=["KB", "MB"], variable=self.size_unit, width=70).pack(side="left")
        ctk.CTkCheckBox(flags, text="Allow resolution reduction", variable=self.allow_reduction).pack(side="left", padx=10)
        self.add_actions(4, self.start)

    def start(self) -> None:
        source, output = self.input_path.get().strip(), self.output_path.get().strip()
        try:
            width, height = int(self.width.get()), int(self.height.get())
            percentage = float(self.percentage.get())
            max_bytes = size_to_bytes(float(self.max_size.get()), self.size_unit.get()) if self.limit_size.get() else None
        except ValueError:
            messagebox.showwarning(APP_TITLE, self.app.t("Width and height must be integers."))
            return
        if not source or not output:
            messagebox.showwarning(APP_TITLE, self.app.t("Select input and output folders."))
            return
        mode = self.app.i18n.canonical(self.mode.get())
        if mode == "Stretch":
            mode = "Exact"
        options = ResizeOptions(
            self.preserve.get(), self.upscale.get(), self.skip_existing.get(), percentage,
            max_bytes, self.allow_reduction.get(), 60
        )
        self.app.run_task(
            self,
            self.app.t("Resize Images"),
            lambda log, progress, cancel: resize_batch(source, output, width, height, mode, log, progress, cancel, options),
        )


class ConvertPage(BasePage):
    def __init__(self, master: ctk.CTkFrame, app: "ToolkitApp") -> None:
        super().__init__(master, app, app.t("Convert Format"), app.t("Batch conversion of PNG, JPEG, WEBP, BMP, and TIFF"))
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.conversion = tk.StringVar(value=next(iter(CONVERSIONS)))
        self.quality = tk.StringVar(value="90")
        self.background = tk.StringVar(value="#FFFFFF")
        self.skip_existing = tk.BooleanVar(value=True)
        self.limit_size = tk.BooleanVar(value=False)
        self.allow_reduction = tk.BooleanVar(value=False)
        self.max_size = tk.StringVar(value="2")
        self.size_unit = tk.StringVar(value="MB")
        self.add_path_row(
            0,
            app.t("Input folder"),
            self.input_path,
            lambda: self.choose_input_folder(self.input_path, self.output_path, "converted"),
        )
        self.add_path_row(1, app.t("Output folder"), self.output_path, lambda: self.choose_output_folder(self.output_path))
        ctk.CTkLabel(self.form, text="Operation", anchor="w").grid(row=2, column=0, sticky="w", padx=(20, 12), pady=8)
        ctk.CTkOptionMenu(
            self.form,
            values=list(CONVERSIONS),
            variable=self.conversion,
        ).grid(row=2, column=1, columnspan=2, sticky="ew", padx=(0, 20), pady=8)
        options = ctk.CTkFrame(self.form, fg_color="transparent")
        options.grid(row=3, column=0, columnspan=3, sticky="w", padx=20, pady=6)
        ctk.CTkLabel(options, text="Quality").pack(side="left")
        ctk.CTkEntry(options, textvariable=self.quality, width=60).pack(side="left", padx=6)
        ctk.CTkLabel(options, text="Alpha background").pack(side="left", padx=(12, 4))
        ctk.CTkEntry(options, textvariable=self.background, width=95).pack(side="left")
        ctk.CTkCheckBox(options, text="Skip existing", variable=self.skip_existing).pack(side="left", padx=12)
        ctk.CTkCheckBox(options, text="Limit size", variable=self.limit_size).pack(side="left", padx=8)
        ctk.CTkEntry(options, textvariable=self.max_size, width=60).pack(side="left", padx=4)
        ctk.CTkOptionMenu(options, values=["KB", "MB"], variable=self.size_unit, width=70).pack(side="left")
        ctk.CTkCheckBox(options, text="Allow resolution reduction", variable=self.allow_reduction).pack(side="left", padx=8)
        self.add_actions(4, self.start)

    def start(self) -> None:
        source, output = self.input_path.get().strip(), self.output_path.get().strip()
        if not source or not output:
            messagebox.showwarning(APP_TITLE, self.app.t("Select input and output folders."))
            return
        conversion = self.conversion.get()
        try:
            background = normalize_hex_color(self.background.get())
            quality = int(self.quality.get())
            max_bytes = size_to_bytes(float(self.max_size.get()), self.size_unit.get()) if self.limit_size.get() else None
            options = ConvertOptions(quality, background, self.skip_existing.get(), max_bytes, self.allow_reduction.get(), 60)
        except ValueError as exc:
            messagebox.showerror(APP_TITLE, self.app.user_message(str(exc)))
            return
        self.app.run_task(
            self,
            self.app.t("Convert Format"),
            lambda log, progress, cancel: convert_batch(source, output, conversion, log, progress, cancel, options),
        )


class RenameFilesPage(BasePage):
    MODES = ("Create renamed copies", "Rename original files")
    EXTENSION_MODES = ("Images", "All files", "Custom extensions")
    CASE_MODES = ("None", "Lowercase", "Uppercase", "Title Case")

    def __init__(self, master: ctk.CTkFrame, app: "ToolkitApp") -> None:
        super().__init__(master, app, app.t("Rename Files"), app.t("This tool changes the names of many files at once."))
        self.files: list[Path] = []
        self.preview_items: list[RenamePreviewItem] = []
        self.source_root: Path | None = None

        self.source_label = tk.StringVar(value=app.t("No files selected"))
        self.output_path = tk.StringVar()
        self.mode = tk.StringVar(value=app.t("Create renamed copies"))
        self.include_subfolders = tk.BooleanVar(value=False)
        self.extension_mode = tk.StringVar(value=app.t("Images"))
        self.custom_extensions = tk.StringVar(value=".jpg, .png, .webp")
        self.prefix = tk.StringVar()
        self.suffix = tk.StringVar()
        self.remove_text = tk.StringVar()
        self.remove_case = tk.BooleanVar(value=False)
        self.remove_first_only = tk.BooleanVar(value=False)
        self.find_text = tk.StringVar()
        self.replace_text = tk.StringVar()
        self.replace_case = tk.BooleanVar(value=False)
        self.replace_all = tk.BooleanVar(value=True)
        self.normalize = tk.BooleanVar(value=False)
        self.extension_lowercase = tk.BooleanVar(value=False)
        self.case_mode = tk.StringVar(value=app.t("None"))
        self.numbering_enabled = tk.BooleanVar(value=False)
        self.numbering_base = tk.StringVar(value="product_")
        self.start_number = tk.StringVar(value="1")
        self.number_step = tk.StringVar(value="1")
        self.number_padding = tk.StringVar(value="3")
        self.confirm_original = tk.BooleanVar(value=False)

        self._build_source_block()
        self._build_operation_block()
        self._build_mode_block()
        self.add_actions(17, self.start)
        self._build_preview_block()
        self._wire_refresh()
        self._mode_changed()

    def _section(self, row: int, title: str) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.form, fg_color="transparent")
        frame.grid(row=row, column=0, columnspan=3, sticky="ew", padx=20, pady=(14, 4))
        frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(weight="bold"), anchor="w").grid(
            row=0, column=0, columnspan=4, sticky="ew", pady=(0, 8)
        )
        return frame

    def _build_source_block(self) -> None:
        frame = self._section(0, "Source files")
        ctk.CTkButton(frame, text="Select Files", width=120, command=self._select_files).grid(row=1, column=0, sticky="w", pady=4)
        ctk.CTkButton(frame, text="Select Folder", width=120, command=self._select_folder).grid(row=1, column=1, sticky="w", padx=10, pady=4)
        ctk.CTkButton(frame, text="Clear List", width=110, fg_color="transparent", border_width=1, text_color=TEXT_MUTED,
                      command=self._clear_files).grid(row=1, column=2, sticky="w", pady=4)
        ctk.CTkCheckBox(frame, text="Include subfolders", variable=self.include_subfolders,
                        command=self._reload_folder).grid(row=1, column=3, sticky="e", padx=(10, 0), pady=4)
        ctk.CTkLabel(frame, textvariable=self.source_label, text_color=TEXT_MUTED, anchor="w", wraplength=640).grid(
            row=2, column=0, columnspan=4, sticky="ew", pady=(6, 4)
        )
        filter_frame = ctk.CTkFrame(frame, fg_color="transparent")
        filter_frame.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        ctk.CTkLabel(filter_frame, text="Extension filter").pack(side="left", padx=(0, 8))
        ctk.CTkOptionMenu(
            filter_frame,
            values=[self.app.t(value) for value in self.EXTENSION_MODES],
            variable=self.extension_mode,
            command=lambda _value: self._reload_folder(),
            width=170,
        ).pack(side="left")
        ctk.CTkLabel(filter_frame, text="Custom extensions").pack(side="left", padx=(14, 8))
        ctk.CTkEntry(filter_frame, textvariable=self.custom_extensions, width=220).pack(side="left")

    def _build_operation_block(self) -> None:
        ctk.CTkLabel(self.form, text="Rename operations", font=ctk.CTkFont(weight="bold"), anchor="w").grid(
            row=1, column=0, columnspan=3, sticky="ew", padx=20, pady=(16, 6)
        )
        ctk.CTkLabel(self.form, text="Add prefix", anchor="w").grid(row=2, column=0, sticky="w", padx=(20, 12), pady=6)
        ctk.CTkEntry(self.form, textvariable=self.prefix, placeholder_text="product_").grid(row=2, column=1, columnspan=2, sticky="ew", padx=(0, 20), pady=6)
        ctk.CTkLabel(self.form, text="Add suffix", anchor="w").grid(row=3, column=0, sticky="w", padx=(20, 12), pady=6)
        ctk.CTkEntry(self.form, textvariable=self.suffix, placeholder_text="_ready").grid(row=3, column=1, columnspan=2, sticky="ew", padx=(0, 20), pady=6)
        ctk.CTkLabel(self.form, text="Remove text", anchor="w").grid(row=4, column=0, sticky="w", padx=(20, 12), pady=6)
        remove_frame = ctk.CTkFrame(self.form, fg_color="transparent")
        remove_frame.grid(row=4, column=1, columnspan=2, sticky="ew", padx=(0, 20), pady=6)
        ctk.CTkEntry(remove_frame, textvariable=self.remove_text, placeholder_text="_old").pack(side="left", fill="x", expand=True)
        ctk.CTkCheckBox(remove_frame, text="Case-sensitive", variable=self.remove_case).pack(side="left", padx=10)
        ctk.CTkCheckBox(remove_frame, text="First occurrence only", variable=self.remove_first_only).pack(side="left")
        ctk.CTkLabel(self.form, text="Find and replace", anchor="w").grid(row=5, column=0, sticky="w", padx=(20, 12), pady=6)
        replace_frame = ctk.CTkFrame(self.form, fg_color="transparent")
        replace_frame.grid(row=5, column=1, columnspan=2, sticky="ew", padx=(0, 20), pady=6)
        ctk.CTkEntry(replace_frame, textvariable=self.find_text, placeholder_text="old", width=220).pack(side="left")
        ctk.CTkLabel(replace_frame, text="Replace with").pack(side="left", padx=8)
        ctk.CTkEntry(replace_frame, textvariable=self.replace_text, placeholder_text="new", width=220).pack(side="left")
        replace_flags = ctk.CTkFrame(self.form, fg_color="transparent")
        replace_flags.grid(row=6, column=1, columnspan=2, sticky="w", padx=(0, 20), pady=2)
        ctk.CTkCheckBox(replace_flags, text="Case-sensitive", variable=self.replace_case).pack(side="left", padx=(0, 14))
        ctk.CTkCheckBox(replace_flags, text="Replace all", variable=self.replace_all).pack(side="left")
        options = ctk.CTkFrame(self.form, fg_color="transparent")
        options.grid(row=7, column=0, columnspan=3, sticky="ew", padx=20, pady=6)
        ctk.CTkLabel(options, text="Case").pack(side="left", padx=(0, 8))
        ctk.CTkOptionMenu(options, values=[self.app.t(value) for value in self.CASE_MODES], variable=self.case_mode, width=150).pack(side="left")
        ctk.CTkCheckBox(options, text="Normalize spaces and separators", variable=self.normalize).pack(side="left", padx=12)
        ctk.CTkCheckBox(options, text="Lowercase extension", variable=self.extension_lowercase).pack(side="left", padx=4)
        ctk.CTkLabel(self.form, text="Sequential numbering", anchor="w").grid(row=8, column=0, sticky="w", padx=(20, 12), pady=6)
        numbering = ctk.CTkFrame(self.form, fg_color="transparent")
        numbering.grid(row=8, column=1, columnspan=2, sticky="ew", padx=(0, 20), pady=6)
        ctk.CTkCheckBox(numbering, text="Enable numbering", variable=self.numbering_enabled).grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(numbering, text="Base name").grid(row=0, column=1, sticky="w", padx=(14, 4))
        ctk.CTkEntry(numbering, textvariable=self.numbering_base, width=150).grid(row=0, column=2, sticky="w")
        for row, column, label, variable, width in (
            (1, 0, "Start number", self.start_number, 70),
            (1, 2, "Step", self.number_step, 55),
            (2, 0, "Padding", self.number_padding, 55),
        ):
            ctk.CTkLabel(numbering, text=label).grid(row=row, column=column, sticky="w", pady=(6, 0))
            ctk.CTkEntry(numbering, textvariable=variable, width=width).grid(row=row, column=column + 1, sticky="w", padx=(4, 14), pady=(6, 0))

    def _build_mode_block(self) -> None:
        ctk.CTkLabel(self.form, text="Output mode", font=ctk.CTkFont(weight="bold"), anchor="w").grid(
            row=10, column=0, columnspan=3, sticky="ew", padx=20, pady=(16, 6)
        )
        ctk.CTkLabel(self.form, text="Mode", anchor="w").grid(row=11, column=0, sticky="w", padx=(20, 12), pady=6)
        ctk.CTkOptionMenu(
            self.form,
            values=[self.app.t(value) for value in self.MODES],
            variable=self.mode,
            command=lambda _value: self._mode_changed(),
        ).grid(row=11, column=1, columnspan=2, sticky="ew", padx=(0, 20), pady=6)
        self.output_label = ctk.CTkLabel(self.form, text="Output folder", anchor="w")
        self.output_label.grid(row=12, column=0, sticky="w", padx=(20, 12), pady=6)
        ctk.CTkEntry(self.form, textvariable=self.output_path).grid(row=12, column=1, sticky="ew", pady=6)
        self.output_button = ctk.CTkButton(self.form, text="Select", width=100, command=lambda: self.choose_output_folder(self.output_path))
        self.output_button.grid(row=12, column=2, sticky="e", padx=(12, 20), pady=6)
        self.mode_note = ctk.CTkLabel(
            self.form,
            text="The source files will not be changed. Renamed copies will be saved to the selected folder.",
            fg_color=INFO_SOFT,
            text_color=INFO,
            corner_radius=8,
            anchor="w",
            justify="left",
            wraplength=760,
        )
        self.mode_note.grid(row=13, column=0, columnspan=3, sticky="ew", padx=20, pady=(8, 4), ipadx=12, ipady=9)
        self.confirm_check = ctk.CTkCheckBox(
            self.form,
            text="I checked the new names and understand that the original files will be renamed",
            variable=self.confirm_original,
            command=self._update_start_state,
        )
        self.confirm_check.grid(row=14, column=0, columnspan=3, sticky="w", padx=20, pady=8)
        ctk.CTkButton(self.form, text="Refresh Preview", width=150, command=self.refresh_preview).grid(
            row=15, column=0, sticky="w", padx=20, pady=(8, 4)
        )

    def _build_preview_block(self) -> None:
        self.preview_title = ctk.CTkLabel(self.form, text="Preview", font=ctk.CTkFont(weight="bold"), anchor="w")
        self.preview_title.grid(row=18, column=0, columnspan=3, sticky="ew", padx=20, pady=(12, 6))
        self.preview_box = ctk.CTkTextbox(self.form, height=180, wrap="none", border_width=1, border_color=BORDER)
        self.preview_box.grid(row=19, column=0, columnspan=3, sticky="ew", padx=20, pady=(0, 18))
        self.preview_box.configure(state="disabled")

    def _wire_refresh(self) -> None:
        variables = [
            self.custom_extensions, self.prefix, self.suffix, self.remove_text, self.find_text,
            self.replace_text, self.numbering_base, self.start_number, self.number_step,
            self.number_padding,
        ]
        for variable in variables:
            variable.trace_add("write", lambda *_args: self.refresh_preview())
        for variable in (
            self.remove_case, self.remove_first_only, self.replace_case, self.replace_all,
            self.normalize, self.extension_lowercase, self.numbering_enabled,
        ):
            variable.trace_add("write", lambda *_args: self.refresh_preview())
        self.output_path.trace_add("write", lambda *_args: self.refresh_preview())
        self.confirm_original.trace_add("write", lambda *_args: self._update_start_state())

    def _rename_options(self) -> RenameOptions:
        try:
            start_number = int(self.start_number.get())
            number_step = int(self.number_step.get())
            number_padding = max(0, int(self.number_padding.get()))
        except ValueError as exc:
            raise ValueError("Numbering values must be integers") from exc
        if number_step < 0:
            raise ValueError("Numbering step must not be negative")
        return RenameOptions(
            prefix=self.prefix.get(),
            suffix=self.suffix.get(),
            remove_text=self.remove_text.get(),
            remove_case_sensitive=self.remove_case.get(),
            remove_first_only=self.remove_first_only.get(),
            find_text=self.find_text.get(),
            replace_text=self.replace_text.get(),
            replace_case_sensitive=self.replace_case.get(),
            replace_all=self.replace_all.get(),
            case_mode=self.app.i18n.canonical(self.case_mode.get()),
            normalize_separators=self.normalize.get(),
            extension_lowercase=self.extension_lowercase.get(),
            numbering_enabled=self.numbering_enabled.get(),
            numbering_base=self.numbering_base.get(),
            start_number=start_number,
            number_step=number_step,
            number_padding=number_padding,
        )

    def _select_files(self) -> None:
        selected = filedialog.askopenfilenames(title=self.app.t("Select Files"))
        if selected:
            self.source_root = None
            self.files = collect_files(
                selected,
                extension_mode=self.app.i18n.canonical(self.extension_mode.get()),
                custom_extensions=self.custom_extensions.get(),
            )
            self._update_source_label()
            self.refresh_preview()

    def _select_folder(self) -> None:
        selected = filedialog.askdirectory(title=self.app.t("Select Folder"))
        if selected:
            self.source_root = Path(selected)
            if not self.output_path.get().strip():
                self.output_path.set(str(self.source_root / "renamed"))
            self._reload_folder()

    def _reload_folder(self) -> None:
        if not self.source_root:
            self.refresh_preview()
            return
        self.files = collect_files(
            [self.source_root],
            include_subfolders=self.include_subfolders.get(),
            extension_mode=self.app.i18n.canonical(self.extension_mode.get()),
            custom_extensions=self.custom_extensions.get(),
        )
        self._update_source_label()
        self.refresh_preview()

    def _clear_files(self) -> None:
        self.files = []
        self.preview_items = []
        self.source_root = None
        self.source_label.set(self.app.t("No files selected"))
        self._write_preview(self.app.t("No files selected"))
        self._update_start_state()

    def _update_source_label(self) -> None:
        if self.source_root:
            text = f"{self.source_root} — {len(self.files)} {self.app.t('files found')}"
        elif self.files:
            text = f"{len(self.files)} {self.app.t('files selected')}"
        else:
            text = self.app.t("No files selected")
        self.source_label.set(text)

    def _mode_changed(self) -> None:
        mode = self.app.i18n.canonical(self.mode.get())
        originals = mode == "Rename original files"
        note = (
            "The original files will be renamed in the source folder.\n\n"
            "Check the preview carefully before continuing. After renaming, the previous file names will no longer be used."
            if originals else
            "The source files will not be changed. Renamed copies will be saved to the selected folder."
        )
        self.mode_note.configure(
            text=self.app.t(note),
            fg_color=WARNING_SOFT if originals else INFO_SOFT,
            text_color=WARNING if originals else INFO,
        )
        state = "disabled" if originals else "normal"
        self.output_label.configure(text_color=TEXT_MUTED if originals else TEXT_PRIMARY)
        self.output_button.configure(state=state)
        self.confirm_check.grid() if originals else self.confirm_check.grid_remove()
        self.refresh_preview()
        self._update_start_state()

    def _write_preview(self, text: str) -> None:
        self.preview_box.configure(state="normal")
        self.preview_box.delete("1.0", "end")
        self.preview_box.insert("end", text)
        self.preview_box.configure(state="disabled")

    def refresh_preview(self) -> None:
        if not hasattr(self, "preview_box"):
            return
        if not self.files:
            self.preview_items = []
            self._write_preview(self.app.t("No files selected"))
            self._update_start_state()
            return
        mode = self.app.i18n.canonical(self.mode.get())
        try:
            if mode == "Create renamed copies":
                output = self.output_path.get().strip()
                if not output:
                    self.preview_items = []
                    self._write_preview(self.app.t("Choose an output folder"))
                    self._update_start_state()
                    return
                if self.source_root and Path(output).resolve() == self.source_root.resolve():
                    self.preview_items = []
                    self._write_preview(self.app.t("Choose a different folder to create copies."))
                    self._update_start_state()
                    return
                self.preview_items = build_preview(
                    self.files, self._rename_options(), mode=mode, output_dir=output, source_root=self.source_root
                )
            else:
                self.preview_items = build_preview(self.files, self._rename_options(), mode=mode)
        except ValueError as exc:
            self.preview_items = []
            self._write_preview(self.app.user_message(str(exc)))
            self._update_start_state()
            return
        lines = [f"{self.app.t('Status'):<12} | {self.app.t('Old name')} -> {self.app.t('New name')}"]
        lines.append("-" * 92)
        for item in self.preview_items[:300]:
            status = self.app.t(item.status)
            error = f" — {self.app.t(item.error)}" if item.error else ""
            lines.append(f"{status:<12} | {item.old_name} -> {item.new_name}{error}")
        if len(self.preview_items) > 300:
            lines.append(self.app.t("Preview shows first 300 files."))
        errors = sum(1 for item in self.preview_items if item.status == "Error")
        skipped = sum(1 for item in self.preview_items if item.status == "Skipped")
        lines.append("")
        lines.append(f"{self.app.t('Files')}: {len(self.preview_items)}   {self.app.t('Errors')}: {errors}   {self.app.t('Skipped')}: {skipped}")
        self._write_preview("\n".join(lines))
        self._update_start_state()

    def _update_start_state(self) -> None:
        if not self.start_button:
            return
        mode = self.app.i18n.canonical(self.mode.get())
        errors = any(item.status == "Error" for item in self.preview_items)
        enabled = bool(self.preview_items) and not errors
        if mode == "Rename original files" and not self.confirm_original.get():
            enabled = False
        self.start_button.configure(state="normal" if enabled else "disabled")

    def start(self) -> None:
        self.refresh_preview()
        mode = self.app.i18n.canonical(self.mode.get())
        if not self.preview_items:
            messagebox.showwarning(APP_TITLE, self.app.t("Select files or a folder first."))
            return
        errors = [item for item in self.preview_items if item.status == "Error"]
        if errors:
            messagebox.showerror(APP_TITLE, self.app.t("Fix conflicts before starting."))
            return
        if mode == "Rename original files":
            if not self.confirm_original.get():
                messagebox.showwarning(APP_TITLE, self.app.t("Confirm that original files can be renamed."))
                return
            warning = (
                "The original files will be renamed in the source folder.\n\n"
                "Check the preview carefully before continuing. After renaming, the previous file names will no longer be used."
            )
            if not messagebox.askyesno(APP_TITLE, self.app.t(warning)):
                return
        self.app.run_task(
            self,
            self.app.t("Rename Files"),
            lambda log, progress, cancel: execute_rename(self.preview_items, mode=mode, log=log, progress=progress, cancel=cancel),
        )

    def set_running(self, running: bool) -> None:
        super().set_running(running)
        if not running:
            self.refresh_preview()

    def refresh_texts(self) -> None:
        current_mode = self.app.i18n.canonical(self.mode.get())
        current_extension = self.app.i18n.canonical(self.extension_mode.get())
        current_case = self.app.i18n.canonical(self.case_mode.get())
        self.app.localize_widget_tree(self)
        self.mode.set(self.app.t(current_mode))
        self.extension_mode.set(self.app.t(current_extension))
        self.case_mode.set(self.app.t(current_case))
        self._update_source_label()
        self._mode_changed()


class HowToUseFrame(ctk.CTkScrollableFrame):
    """Simple, API-independent instructions for every tool."""

    SECTIONS = (
        ("About PixelBatch", "PixelBatch is a desktop tool for batch image processing: background removal, resizing, format conversion, background and padding setup, mass renaming, and e-commerce image preparation.",
         "Version: 0.1.0-alpha. This project is currently in alpha development. Features and interfaces may change.", "info"),
        ("Quick Start", "Choose a tool from the menu on the left.\nSelect images or a CSV file.\nChoose where to save the result.\nSet the required options.\nClick “Start”.\nWait for the completion message.",
         "You do not need an API key to remove backgrounds, add backgrounds, resize images, convert formats, or rename files. An API key is required only for experimental image generation.", "info"),
        ("1. Generate Images", "This experimental tool creates new images with artificial intelligence.\n\nOpen “Generate Images”.\nSelect a CSV file or enter an image description.\nSelect the rows to process.\nChoose an output folder.\nCheck the selected model.\nClick “Start”.",
         "Experimental API feature: this tool requires a provider API key. Add it in Settings. Local batch image tools work without an API key.", "warning"),
        ("2. Remove Background", "This tool removes the background and leaves the object on a transparent background.\n\nOpen “Remove Background”.\nClick “Select Folder”.\nChoose a folder with one or more images.\nChoose an output folder.\nClick “Start”.\nCompleted images will appear in the selected folder.",
         "On first use, the app may download the background removal model once. Processing then runs on your computer.", "info"),
        ("3. Add Background", "This tool adds a solid, white, transparent, or image background.\n\nOpen “Add Background”.\nChoose the images folder.\nChoose a background color, transparency, or an image.\nSet the canvas size and padding if needed.\nChoose an output folder.\nClick “Start”.",
         "A HEX code is a color code. For example, white is #FFFFFF.", "info"),
        ("4. Resize Images", "This tool changes image width and height.\n\nOpen “Resize Images”.\nChoose the images folder.\nEnter width and height.\nKeep “Preserve aspect ratio” enabled to avoid stretching.\nChoose an output folder.\nClick “Start”.",
         "Fit: the whole image fits inside the size. Fill: the image fills the size and edges may be cropped. Stretch: the image stretches to the exact size.", "info"),
        ("5. Convert Format", "This tool saves images in another format.\n\nOpen “Convert Format”.\nChoose the images folder.\nChoose a new format.\nSet quality when available.\nChoose an output folder.\nClick “Start”.",
         "PNG supports transparency. JPEG is good for photos but not transparency. WEBP usually makes smaller files. BMP can be large. TIFF is suitable for high-quality printing and editing.", "info"),
        ("6. Rename Files", "This tool changes many filenames at once.\n\nOpen “Rename Files”.\nSelect files or a folder.\nChoose how names should change.\nReview the preview.\nChoose whether to create copies or rename originals.\nClick “Start”.",
         "If you are not sure, choose the copy mode. In this mode the source files stay unchanged.", "warning"),
        ("7. Settings", "Choose the language, theme, provider, model, and access settings here.",
         "Provider is the service that creates images. Model is the selected AI model. API Key is its private access code. Base URL normally does not need changing. Timeout is how long the app waits. Retries control temporary request repeats.", "info"),
        ("If something does not work", "Check that files and an output folder are selected. Make sure a file is not open in another app and that the disk has free space. For generation, check the API key. Read the message at the bottom. If needed, click “Cancel” and restart the app.", "", "warning"),
        ("Where are completed files?", "Completed files are saved in the folder shown in “Output folder”.", "", "info"),
        ("Original files are not deleted", "The app creates new files and does not delete the originals.", "", "info"),
    )

    def __init__(self, master: ctk.CTkFrame, app: "ToolkitApp") -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=app.t("How to Use PixelBatch"), font=ctk.CTkFont(size=28, weight="bold"), anchor="w").grid(
            row=0, column=0, sticky="ew", padx=30, pady=(26, 2)
        )
        ctk.CTkLabel(self, text=app.t("Choose a tool from the menu on the left and follow a few simple steps."),
                     text_color=TEXT_MUTED, anchor="w", wraplength=680, justify="left").grid(
            row=1, column=0, sticky="ew", padx=30, pady=(0, 18)
        )
        for row, (heading, body, note, tone) in enumerate(self.SECTIONS, start=2):
            card = ctk.CTkFrame(self, fg_color=SURFACE, border_color=BORDER, border_width=1, corner_radius=12)
            card.grid(row=row, column=0, sticky="ew", padx=30, pady=(0, 12))
            card.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(card, text=app.t(heading), font=ctk.CTkFont(size=16, weight="bold"),
                         text_color=TEXT_PRIMARY, anchor="w").grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 8))
            ctk.CTkLabel(card, text=app.t(body), text_color=TEXT_PRIMARY, anchor="w", justify="left",
                         wraplength=660).grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 12))
            if note:
                note_bg, note_color = (WARNING_SOFT, WARNING) if tone == "warning" else (INFO_SOFT, INFO)
                ctk.CTkLabel(card, text=app.t(note), fg_color=note_bg, text_color=note_color,
                             corner_radius=8, anchor="w", justify="left", wraplength=620).grid(
                    row=2, column=0, sticky="ew", padx=22, pady=(0, 18), ipadx=12, ipady=10
                )

    def refresh_texts(self) -> None:
        self.app.localize_widget_tree(self)


class SettingsPage(ctk.CTkScrollableFrame):
    def __init__(self, master: ctk.CTkFrame, app: "ToolkitApp") -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._loading = True
        self._dirty = False
        self._current_provider = app.settings.active_provider_id()
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text=app.t("Settings"), font=ctk.CTkFont(size=28, weight="bold"), anchor="w").grid(
            row=0, column=0, sticky="ew", padx=30, pady=(26, 2)
        )
        ctk.CTkLabel(
            self,
            text=app.t("Application and image generation settings"),
            text_color=TEXT_MUTED,
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", padx=30, pady=(0, 18))
        card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12, border_width=1, border_color=BORDER)
        card.grid(row=2, column=0, sticky="ew", padx=30)
        card.grid_columnconfigure(1, weight=1)
        self.provider = tk.StringVar(value=PROVIDER_NAMES[self._current_provider])
        self.api_key = tk.StringVar()
        self.model = tk.StringVar()
        self.base_url = tk.StringVar()
        self.timeout = tk.StringVar()
        self.retries = tk.StringVar()
        saved_appearance = app.settings.get("appearance_mode")
        self.appearance = tk.StringVar(value=app.t("System Default" if saved_appearance == "System" else saved_appearance))
        self.language = tk.StringVar(value=app.t("Russian" if app.i18n.language == "ru" else "English"))
        self.show_key = tk.BooleanVar(value=False)

        ctk.CTkLabel(card, text="Image generation provider", font=ctk.CTkFont(weight="bold"), anchor="w").grid(
            row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(20, 8)
        )
        ctk.CTkLabel(card, text="Active provider", anchor="w").grid(row=1, column=0, sticky="w", padx=20, pady=8)
        ctk.CTkOptionMenu(
            card, values=list(PROVIDER_NAMES.values()), variable=self.provider, command=self._provider_changed,
            fg_color=ACCENT, button_color=ACCENT_HOVER
        ).grid(row=1, column=1, sticky="ew", padx=(12, 20), pady=8)
        ctk.CTkLabel(card, text="Model", anchor="w").grid(row=2, column=0, sticky="w", padx=20, pady=8)
        ctk.CTkEntry(card, textvariable=self.model).grid(row=2, column=1, sticky="ew", padx=(12, 20), pady=8)
        ctk.CTkLabel(card, text="API Key", anchor="w").grid(row=3, column=0, sticky="w", padx=20, pady=8)
        self.key_entry = ctk.CTkEntry(card, textvariable=self.api_key, show="•", placeholder_text="sk-or-v1-…")
        self.key_entry.grid(row=3, column=1, sticky="ew", padx=(12, 20), pady=8)
        key_actions = ctk.CTkFrame(card, fg_color="transparent")
        key_actions.grid(row=4, column=1, sticky="w", padx=(12, 20), pady=(0, 8))
        ctk.CTkCheckBox(key_actions, text="Show/Hide API Key", variable=self.show_key, command=self._toggle_key).pack(side="left")
        ctk.CTkButton(key_actions, text="Delete Saved Key", width=160, fg_color="transparent",
                      hover_color=ERROR_SOFT, text_color=ERROR, border_color=ERROR,
                      border_width=1, command=self.delete_key).pack(side="left", padx=10)
        ctk.CTkLabel(card, text="Base URL", anchor="w").grid(row=5, column=0, sticky="w", padx=20, pady=8)
        ctk.CTkEntry(card, textvariable=self.base_url).grid(row=5, column=1, sticky="ew", padx=(12, 20), pady=8)
        network = ctk.CTkFrame(card, fg_color="transparent")
        network.grid(row=6, column=1, sticky="w", padx=(12, 20), pady=8)
        ctk.CTkLabel(network, text="Timeout (seconds)").pack(side="left")
        ctk.CTkEntry(network, textvariable=self.timeout, width=80).pack(side="left", padx=8)
        ctk.CTkLabel(network, text="Retries").pack(side="left", padx=(14, 6))
        ctk.CTkEntry(network, textvariable=self.retries, width=60).pack(side="left")
        ctk.CTkLabel(card, text="Theme", anchor="w").grid(row=7, column=0, sticky="w", padx=20, pady=8)
        ctk.CTkOptionMenu(
            card,
            values=[app.t("System Default"), app.t("Light"), app.t("Dark")],
            variable=self.appearance,
            fg_color=ACCENT,
            button_color=ACCENT_HOVER,
        ).grid(row=7, column=1, sticky="w", padx=(12, 20), pady=8)
        ctk.CTkLabel(card, text=app.t("Interface Language"), anchor="w").grid(
            row=8, column=0, sticky="w", padx=20, pady=8
        )
        self.language_menu = ctk.CTkOptionMenu(
            card, values=[app.t("Russian"), app.t("English")], variable=self.language,
            fg_color=ACCENT, button_color=ACCENT_HOVER, command=self._language_changed,
        )
        self.language_menu.grid(row=8, column=1, sticky="w", padx=(12, 20), pady=8)
        if app.settings.credentials.available:
            credential_text = app.t("The key is stored in Windows Credential Manager and is not written to settings.json.")
        else:
            credential_text = app.t("Windows Credential Manager is unavailable. The key is used only until the app closes and is not written to settings.json.")
        ctk.CTkLabel(
            card,
            text=(
                app.t("An API key is needed only for experimental image generation. Background removal, background addition, resize, conversion, and renaming work locally without a key.")
                + f"\n{credential_text}\n" + app.t("Only the active provider receives its key. No telemetry is collected.")
            ),
            text_color=TEXT_MUTED,
            justify="left",
            anchor="w",
            wraplength=700,
        ).grid(row=9, column=0, columnspan=2, sticky="ew", padx=20, pady=(10, 14))
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.grid(row=10, column=0, columnspan=2, sticky="w", padx=20, pady=(0, 16))
        self.test_button = ctk.CTkButton(actions, text="Test Connection", width=160, fg_color=SURFACE_ALT,
                                         hover_color=ACCENT_SOFT, text_color=TEXT_PRIMARY,
                                         border_color=BORDER, border_width=1, command=self.test_connection)
        self.test_button.pack(side="left")
        self.save_button = ctk.CTkButton(
            actions,
            text=app.t("Save Settings"),
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            font=ctk.CTkFont(weight="bold"),
            height=38,
            command=self.save,
        )
        self.save_button.pack(side="left", padx=10)
        self.log_box = ctk.CTkTextbox(card, height=95)
        self.log_box.grid(row=11, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 18))

        path_card = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12, border_width=1, border_color=BORDER)
        path_card.grid(row=3, column=0, sticky="ew", padx=30, pady=16)
        ctk.CTkLabel(path_card, text=app.t("Settings file"), font=ctk.CTkFont(weight="bold"), anchor="w").pack(
            fill="x", padx=20, pady=(16, 4)
        )
        self.settings_path_label = ctk.CTkLabel(
            path_card,
            text=display_settings_path(),
            text_color=TEXT_MUTED,
            anchor="w",
            wraplength=760,
        )
        self.settings_path_label.pack(fill="x", padx=20, pady=(0, 10))
        Tooltip(self.settings_path_label, lambda: str(self.app.settings.path))
        path_actions = ctk.CTkFrame(path_card, fg_color="transparent")
        path_actions.pack(fill="x", padx=20, pady=(0, 16))
        ctk.CTkButton(
            path_actions,
            text=app.t("Open Folder"),
            width=140,
            fg_color=SURFACE_ALT,
            hover_color=ACCENT_SOFT,
            text_color=TEXT_PRIMARY,
            border_color=BORDER,
            border_width=1,
            command=self.open_settings_folder,
        ).pack(side="left")
        ctk.CTkButton(
            path_actions,
            text=app.t("Copy Path"),
            width=140,
            fg_color=SURFACE_ALT,
            hover_color=ACCENT_SOFT,
            text_color=TEXT_PRIMARY,
            border_color=BORDER,
            border_width=1,
            command=self.copy_settings_path,
        ).pack(side="left", padx=10)
        ctk.CTkLabel(
            path_actions,
            text=app.t("Hover over the path to see the full location."),
            text_color=TEXT_MUTED,
            anchor="w",
            justify="left",
        ).pack(side="left", padx=(4, 0))
        self._tracked = (self.model, self.api_key, self.base_url, self.timeout, self.retries, self.appearance)
        for variable in self._tracked:
            variable.trace_add("write", self._mark_dirty)
        self._load_provider(self._current_provider)
        self._loading = False

    def _ensure_settings_location(self) -> Path:
        folder = self.app.settings.path.parent
        folder.mkdir(parents=True, exist_ok=True)
        if not self.app.settings.path.exists():
            self.app.settings.save()
        return folder

    def open_settings_folder(self) -> None:
        try:
            folder = self._ensure_settings_location()
            os.startfile(folder)  # type: ignore[attr-defined]
        except OSError as exc:
            messagebox.showerror(APP_TITLE, self.app.user_message(exc))

    def copy_settings_path(self) -> None:
        try:
            self._ensure_settings_location()
            self.clipboard_clear()
            self.clipboard_append(str(self.app.settings.path))
            self.append_log(self.app.t("Settings path copied."))
        except (OSError, tk.TclError) as exc:
            messagebox.showerror(APP_TITLE, self.app.user_message(exc))

    def _toggle_key(self) -> None:
        self.key_entry.configure(show="" if self.show_key.get() else "•")

    def _language_changed(self, display_name: str) -> None:
        language = "ru" if self.app.i18n.canonical(display_name) == "Russian" else "en"
        self.app.change_language(language)

    def _mark_dirty(self, *_args: Any) -> None:
        if not self._loading:
            self._dirty = True

    @staticmethod
    def _id_from_name(name: str) -> str:
        return next(key for key, value in PROVIDER_NAMES.items() if value == name)

    def _load_provider(self, provider_id: str) -> None:
        self._loading = True
        config = self.app.settings.provider_config(provider_id)
        self.model.set(config["model"])
        self.base_url.set(config["base_url"])
        self.timeout.set(str(config["timeout"]))
        self.retries.set(str(config["retries"]))
        self.api_key.set(self.app.settings.api_key(provider_id))
        self.provider.set(PROVIDER_NAMES[provider_id])
        self._current_provider = provider_id
        self._dirty = False
        self._loading = False

    def _provider_changed(self, display_name: str) -> None:
        provider_id = self._id_from_name(display_name)
        if provider_id == self._current_provider:
            return
        if self._dirty and not messagebox.askyesno(APP_TITLE, self.app.t("Discard unsaved provider changes?")):
            self._loading = True
            self.provider.set(PROVIDER_NAMES[self._current_provider])
            self._loading = False
            return
        self._load_provider(provider_id)

    def _current_config(self) -> dict[str, Any]:
        try:
            timeout, retries = int(self.timeout.get()), int(self.retries.get())
        except ValueError as exc:
            raise ValueError("Timeout and retries must be integers") from exc
        return {"model": self.model.get().strip(), "base_url": self.base_url.get().strip(), "timeout": timeout, "retries": retries}

    def delete_key(self) -> None:
        question = self.app.t("Delete the saved key for {provider}?", provider=PROVIDER_NAMES[self._current_provider])
        if not messagebox.askyesno(APP_TITLE, question):
            return
        self.app.settings.credentials.delete(self._current_provider)
        self.api_key.set("")
        self.append_log("OK " + self.app.t("Saved key deleted"))

    def test_connection(self) -> None:
        try:
            config = self._current_config()
        except ValueError as exc:
            messagebox.showerror(APP_TITLE, self.app.user_message(str(exc)))
            return
        provider_class = ProviderFactory.PROVIDERS[self._current_provider]
        key = self.api_key.get().strip()

        def work(log: Callable[[str], None], _progress: Callable[[int, int], None], cancel: threading.Event) -> Any:
            provider = provider_class(config, key, cancel=cancel)
            result = provider.test_connection()
            log(("OK " if result.success else "ERROR ") + result.message)
            return result

        self.app.run_task(self, "Testing connection", work)

    def save(self) -> None:
        try:
            config = self._current_config()
            if not config["model"]:
                raise ValueError("Model must not be empty")
            if not config["base_url"].startswith("https://"):
                raise ValueError("Base URL must use HTTPS")
        except ValueError as exc:
            messagebox.showwarning(APP_TITLE, self.app.user_message(str(exc)))
            return
        key = self.api_key.get().strip()
        try:
            self.app.settings.credentials.set(self._current_provider, key)
        except CredentialStoreError as exc:
            if not messagebox.askyesno(APP_TITLE, f"{exc}\n\n{self.app.t('Use this key for the current session only?')}"):
                return
            self.app.settings.credentials.set(self._current_provider, key, persist=False)
            self.append_log("WARNING " + self.app.t("API key is session-only and will not be saved"))
        try:
            self.app.settings.update_provider(self._current_provider, **config)
            appearance = self.app.i18n.canonical(self.appearance.get())
            if appearance == "System Default":
                appearance = "System"
            self.app.settings.update(active_provider=self._current_provider, appearance_mode=appearance,
                                     language=self.app.i18n.language)
            self.app.settings.save()
        except OSError as exc:
            messagebox.showerror(APP_TITLE, self.app.t("Could not save settings:") + f"\n{exc}")
            return
        appearance = self.app.i18n.canonical(self.appearance.get())
        ctk.set_appearance_mode("System" if appearance == "System Default" else appearance)
        generate_page = self.app.pages.get("generate")
        if isinstance(generate_page, GeneratePage):
            generate_page.refresh_provider()
        self._dirty = False
        self.app.set_status(self.app.t("Settings saved"))
        messagebox.showinfo(APP_TITLE, self.app.t("Settings saved locally."))

    def clear_log(self) -> None:
        self.log_box.delete("1.0", "end")

    def append_log(self, message: str) -> None:
        self.log_box.insert("end", message.rstrip() + "\n")
        self.log_box.see("end")

    def set_progress(self, _current: int, _total: int) -> None:
        return

    def set_summary(self, _result: Any) -> None:
        return

    def set_running(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        self.test_button.configure(state=state)
        self.save_button.configure(state=state)

    def refresh_texts(self) -> None:
        dirty = self._dirty
        self._loading = True
        self.app.localize_widget_tree(self)
        self._loading = False
        self._dirty = dirty


class ToolkitApp(ctk.CTk):
    NAV_LABELS = {
        "generate": "Generate Images", "remove": "Remove Background", "background": "Add Background",
        "resize": "Resize Images", "convert": "Convert Format", "rename": "Rename Files",
        "help": "How to Use", "settings": "Settings",
    }

    def __init__(self) -> None:
        self.settings = SettingsManager()
        self.i18n = I18nManager(self.settings.get("language", "ru"))
        self.logger = LoggingService()
        ctk.set_appearance_mode(self.settings.get("appearance_mode", "System"))
        ctk.set_default_color_theme("blue")
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1120x680")
        self.minsize(980, 680)
        try:
            self.iconbitmap(str(resource_path("assets/icon.ico")))
        except (tk.TclError, OSError) as exc:
            self.logger.write(f"Application icon could not be loaded: {exc}", "WARNING")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._cancel_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._active_page: BasePage | None = None
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        self._page_hosts: dict[str, ctk.CTkFrame] = {}
        self.current_page: str | None = None
        self._status_key = "Ready"

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.configure(fg_color=APP_BG)
        self.sidebar = ctk.CTkFrame(self, width=260, corner_radius=0, fg_color=SIDEBAR_BG)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(8, weight=1)
        self.content = ctk.CTkFrame(self, corner_radius=0, fg_color=APP_BG)
        self.content.grid(row=0, column=1, sticky="nsew")
        self.content.grid_rowconfigure(0, weight=1)
        self.content.grid_columnconfigure(0, weight=1)

        self._build_sidebar()
        page_types: dict[str, type[ctk.CTkFrame]] = {
            "generate": GeneratePage,
            "remove": RemoveBackgroundPage,
            "background": AddBackgroundPage,
            "resize": ResizePage,
            "convert": ConvertPage,
            "rename": RenameFilesPage,
            "help": HowToUseFrame,
            "settings": SettingsPage,
        }
        self.pages: dict[str, ctk.CTkFrame] = {}
        for name, page_type in page_types.items():
            host = ctk.CTkFrame(self.content, fg_color="transparent", corner_radius=0)
            host.grid(row=0, column=0, sticky="nsew")
            host.grid_rowconfigure(0, weight=1)
            host.grid_columnconfigure(0, weight=1)
            page = page_type(host, self)
            page.grid(row=0, column=0, sticky="nsew")
            self._page_hosts[name] = host
            self.pages[name] = page
        self._validate_navigation_registry()
        self.navigate_to("generate")
        self.refresh_all_texts()
        self.after(100, self._drain_events)

    def t(self, text: str, **kwargs: Any) -> str:
        return self.i18n.t(text, **kwargs)

    def user_message(self, message: str) -> str:
        return self.i18n.localize_message(self.t(message))

    def _build_sidebar(self) -> None:
        brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand.grid(row=0, column=0, sticky="ew", padx=20, pady=(26, 28))
        badge = ctk.CTkLabel(
            brand,
            text="PB",
            width=42,
            height=42,
            corner_radius=12,
            fg_color=ACCENT,
            text_color="white",
            font=ctk.CTkFont(size=17, weight="bold"),
        )
        badge.pack(side="left")
        brand_text = ctk.CTkFrame(brand, fg_color="transparent")
        brand_text.pack(side="left", padx=11)
        ctk.CTkLabel(
            brand_text,
            text=APP_TITLE,
            justify="left",
            anchor="w",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            brand_text,
            text=APP_SUBTITLE,
            justify="left",
            anchor="w",
            text_color=TEXT_MUTED,
            font=ctk.CTkFont(size=10),
        ).pack(anchor="w")

        items = [
            (key, label) for key, label in self.NAV_LABELS.items() if key != "settings"
        ]
        for row, (key, label) in enumerate(items, start=1):
            button = ctk.CTkButton(
                self.sidebar,
                text=label,
                anchor="w",
                height=42,
                corner_radius=10,
                fg_color="transparent",
                hover_color=SURFACE_ALT,
                text_color=TEXT_PRIMARY,
                command=lambda name=key: self.navigate_to(name),
            )
            button.grid(row=row, column=0, sticky="ew", padx=14, pady=3)
            self._nav_buttons[key] = button
        settings_button = ctk.CTkButton(
            self.sidebar,
            text="Settings",
            anchor="w",
            height=42,
            corner_radius=10,
            fg_color="transparent",
            hover_color=SURFACE_ALT,
            text_color=TEXT_PRIMARY,
            command=lambda: self.navigate_to("settings"),
        )
        settings_button.grid(row=9, column=0, sticky="ew", padx=14, pady=3)
        self._nav_buttons["settings"] = settings_button
        self.status_label = ctk.CTkLabel(
            self.sidebar,
            text="Status: Ready",
            text_color=TEXT_MUTED,
            anchor="w",
            wraplength=190,
        )
        self.status_label.grid(row=10, column=0, sticky="ew", padx=20, pady=(14, 22))

    def _validate_navigation_registry(self) -> None:
        page_names = set(self.pages)
        if page_names != set(self._nav_buttons) or page_names != set(self._page_hosts):
            raise RuntimeError(
                "Navigation registry mismatch: "
                f"pages={sorted(page_names)}, buttons={sorted(self._nav_buttons)}, hosts={sorted(self._page_hosts)}"
            )

    def set_active_item(self, name: str) -> None:
        for key, button in self._nav_buttons.items():
            selected = key == name
            button.configure(
                fg_color=ACCENT_SOFT if selected else "transparent",
                text_color=ACCENT_TEXT if selected else TEXT_PRIMARY,
            )

    def localize_widget_tree(self, widget: Any) -> None:
        """Refresh text in-place; pages and their state are never recreated."""
        try:
            current = widget.cget("text")
            if isinstance(current, str) and current:
                widget.configure(text=self.t(current))
        except (AttributeError, KeyError, TypeError, tk.TclError, ValueError):
            pass
        try:
            if isinstance(widget, ctk.CTkOptionMenu):
                widget.configure(fg_color=ACCENT, button_color=ACCENT_HOVER, button_hover_color=ACCENT_HOVER)
            elif isinstance(widget, ctk.CTkCheckBox):
                widget.configure(fg_color=ACCENT, hover_color=ACCENT_HOVER, border_color=BORDER)
            elif isinstance(widget, ctk.CTkButton):
                current_fg = widget.cget("fg_color")
                if current_fg != "transparent" and tuple(current_fg) not in {tuple(ACCENT), tuple(SURFACE_ALT)}:
                    widget.configure(fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="white")
            elif isinstance(widget, ctk.CTkEntry):
                widget.configure(fg_color=SURFACE_ALT, border_color=BORDER, text_color=TEXT_PRIMARY)
            elif isinstance(widget, ctk.CTkTextbox):
                widget.configure(fg_color=SURFACE_ALT, border_color=BORDER, text_color=TEXT_PRIMARY)
        except (AttributeError, KeyError, TypeError, tk.TclError, ValueError):
            pass
        try:
            values = widget.cget("values")
            if values:
                localized = [self.t(str(value)) for value in values]
                widget.configure(values=localized)
                variable = getattr(widget, "_variable", None)
                if variable is not None:
                    variable.set(self.t(str(variable.get())))
        except (AttributeError, KeyError, tk.TclError, ValueError):
            pass
        for child in widget.winfo_children():
            self.localize_widget_tree(child)

    def refresh_all_texts(self) -> None:
        self.title(APP_TITLE)
        for key, button in self._nav_buttons.items():
            button.configure(text=self.t(self.NAV_LABELS[key]))
        for page in self.pages.values():
            refresh = getattr(page, "refresh_texts", None)
            if callable(refresh):
                refresh()
        self.status_label.configure(text=f"{self.t('Status')}: {self.t(self._status_key)}")
        self.set_active_item(self.current_page or "generate")

    def change_language(self, language: str) -> None:
        if language == self.i18n.language:
            return
        previous = self.i18n.language
        self.i18n.set_language(language)
        self.settings.update(language=language)
        try:
            self.settings.save()
        except OSError as exc:
            self.i18n.set_language(previous)
            self.settings.update(language=previous)
            messagebox.showerror(APP_TITLE, self.t("Could not save settings:") + f"\n{exc}")
            return
        self.refresh_all_texts()

    def navigate_to(self, name: str) -> None:
        if name not in self.pages:
            raise KeyError(f"Unknown page: {name}")
        previous = self.current_page
        try:
            self._page_hosts[name].tkraise()
            self.current_page = name
            self.set_active_item(name)
            page = self.pages[name]
            on_show = getattr(page, "on_show", None)
            if callable(on_show):
                on_show()
            self.logger.write(f"Navigation: {previous or 'startup'} -> {name}", "INFO")
        except Exception as exc:
            self.logger.exception(exc)
            raise

    def show_page(self, name: str) -> None:
        """Backward-compatible alias for integrations using the prototype API."""
        self.navigate_to(name)

    def show_api_key_required_dialog(self, detail: str = "") -> bool:
        """Return True when the user chooses to open the existing Settings page."""
        dialog = ctk.CTkToplevel(self)
        dialog.title(self.t("API key required"))
        dialog.geometry("510x220")
        dialog.resizable(False, False)
        dialog.transient(self)
        result = {"open_settings": False}
        text = (
            self.t("An API key is required only to generate images. Local tools work without it.")
        )
        if detail:
            text += f"\n\n{detail}"
        ctk.CTkLabel(dialog, text=text, justify="left", wraplength=450, anchor="w").pack(
            fill="x", padx=28, pady=(28, 22)
        )
        buttons = ctk.CTkFrame(dialog, fg_color="transparent")
        buttons.pack(fill="x", padx=28, pady=(0, 24))

        def close(open_settings: bool) -> None:
            result["open_settings"] = open_settings
            dialog.grab_release()
            dialog.destroy()

        ctk.CTkButton(
            buttons, text=self.t("Open Settings"), fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=lambda: close(True)
        ).pack(side="left")
        ctk.CTkButton(
            buttons, text=self.t("Cancel"), fg_color="transparent", border_width=1,
            command=lambda: close(False)
        ).pack(side="left", padx=10)
        dialog.protocol("WM_DELETE_WINDOW", lambda: close(False))
        dialog.grab_set()
        dialog.focus_force()
        self.wait_window(dialog)
        return result["open_settings"]

    def set_status(self, message: str) -> None:
        self._status_key = self.i18n.canonical(message)
        self.status_label.configure(text=f"{self.t('Status')}: {self.t(self._status_key)}")

    def run_task(
        self,
        page: Any,
        title: str,
        operation: Callable[[Callable[[str], None], Callable[[int, int], None], threading.Event], Any],
    ) -> None:
        if self._worker and self._worker.is_alive():
            messagebox.showwarning(APP_TITLE, self.t("Wait for the current operation to finish or cancel it."))
            return
        page.clear_log()
        for candidate in self.pages.values():
            if hasattr(candidate, "set_running"):
                candidate.set_running(True)
        self._active_page = page
        self._cancel_event = threading.Event()
        self.set_status("Processing")

        def log(message: str) -> None:
            prefix = message.split(" ", 1)[0].upper()
            level = prefix if prefix in {"DEBUG", "INFO", "OK", "WARNING", "ERROR", "SKIP"} else "INFO"
            body = message.split(" ", 1)[1] if prefix == level and " " in message else message
            self._events.put(("log", self.logger.write(self.i18n.localize_message(body), level)))

        def progress(current: int, total: int) -> None:
            self._events.put(("progress", (current, total)))

        def runner() -> None:
            try:
                result = operation(log, progress, self._cancel_event)
                self._events.put(("done", result))
            except Exception as exc:
                self._events.put(("error", exc))

        self._worker = threading.Thread(target=runner, daemon=True, name="pixelbatch-worker")
        self._worker.start()

    def cancel_task(self) -> None:
        if self._worker and self._worker.is_alive():
            self._cancel_event.set()
            self.set_status("Cancelling")
            if self._active_page:
                self._active_page.append_log(self.t("Cancellation requested. The current file or API request will finish first."))

    def _summary_text(self, result: Any) -> str:
        succeeded = getattr(result, "succeeded", 0)
        skipped = getattr(result, "skipped", 0)
        failed = getattr(result, "failed", 0)
        parts = [f"{self.t('Successful').lower()}: {succeeded}"]
        if skipped:
            parts.append(f"{self.t('Skipped').lower()}: {skipped}")
        if failed:
            parts.append(f"{self.t('Errors').lower()}: {failed}")
        return ", ".join(parts)

    def _finish_task(self) -> None:
        for candidate in self.pages.values():
            if hasattr(candidate, "set_running"):
                candidate.set_running(False)
        self._active_page = None
        self._worker = None

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self._events.get_nowait()
                page = self._active_page
                if kind == "log" and page:
                    page.append_log(str(payload))
                elif kind == "progress" and page:
                    page.set_progress(*payload)
                elif kind == "done":
                    summary = self._summary_text(payload)
                    cancelled = bool(getattr(payload, "cancelled", False))
                    if page:
                        page.append_log((self.t("Operation cancelled; ") if cancelled else self.t("Completed; ")) + summary)
                        if hasattr(page, "set_summary"):
                            page.set_summary(payload)
                    failed = int(getattr(payload, "failed", 0))
                    self.set_status("Ready" if cancelled else ("Completed with errors" if failed else "Completed"))
                    self._finish_task()
                elif kind == "error":
                    cleaned = self.logger.exception(payload)
                    if page:
                        page.append_log(cleaned)
                    self.set_status("Error")
                    messagebox.showerror(APP_TITLE, self.user_message(cleaned))
                    self._finish_task()
        except queue.Empty:
            self.after(100, self._drain_events)
            return
        self.after(100, self._drain_events)

    def _on_close(self) -> None:
        if self._worker and self._worker.is_alive():
            if not messagebox.askyesno(APP_TITLE, self.t("The operation is still running. Cancel it and close the application?")):
                return
            self._cancel_event.set()
        self.destroy()


def main() -> None:
    app = ToolkitApp()
    app.mainloop()


if __name__ == "__main__":
    main()
