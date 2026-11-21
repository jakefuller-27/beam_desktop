"""Tkinter desktop interface for the Beam Designer."""

from __future__ import annotations

import csv
import subprocess
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib.patches import Polygon

from beam_calculations import (
    MATERIAL_PROPERTIES,
    SECTIONS,
    AnalysisResult,
    MaterialKey,
    PointLoad,
    Section,
    SupportType,
    UniformLoad,
    analyze_beam,
    lightest_passing_section,
)
from beam_design_io import BeamDesign, load_design, save_design
from beam_print import export_calculation_sheet, open_pdf
from beam_results_export import export_results_csv


BACKGROUND = "#edf2f6"
CARD = "#ffffff"
INK = "#203344"
ACCENT = "#2f6f9f"
MUTED = "#657786"
WARNING = "#a85d18"


class LoadEditor:
    def __init__(
        self,
        app: "BeamDesigner",
        parent: ttk.Frame,
        kind: str,
        magnitude: float,
        first_position: float,
        second_position: float | None = None,
    ) -> None:
        self.app = app
        self.kind = kind
        self.frame = ttk.Frame(parent, style="Card.TFrame", padding=(8, 6))
        self.magnitude_var = tk.StringVar(value=f"{magnitude:g}")
        self.first_var = tk.StringVar(value=f"{first_position:g}")
        self.second_var = tk.StringVar(
            value="" if second_position is None else f"{second_position:g}"
        )
        self._build()
        for variable in self.variables:
            variable.trace_add("write", self.app._input_changed)

    @property
    def variables(self) -> tuple[tk.StringVar, ...]:
        if self.kind == "point":
            return self.magnitude_var, self.first_var
        return self.magnitude_var, self.first_var, self.second_var

    def _build(self) -> None:
        heading = "Point load" if self.kind == "point" else "Uniform load"
        ttk.Label(self.frame, text=heading, style="LoadTitle.TLabel").grid(
            row=0, column=0, sticky="w", columnspan=4
        )
        ttk.Button(
            self.frame,
            text="Remove",
            width=8,
            command=lambda: self.app._remove_load(self),
        ).grid(row=0, column=4, sticky="e")
        self.frame.columnconfigure(4, weight=1)
        ttk.Label(self.frame, text="Magnitude").grid(row=1, column=0, sticky="w")
        ttk.Entry(self.frame, textvariable=self.magnitude_var, width=9).grid(
            row=1, column=1, sticky="w", padx=(4, 3)
        )
        ttk.Label(
            self.frame,
            text="kips" if self.kind == "point" else "kips/ft",
            style="Unit.TLabel",
        ).grid(row=1, column=2, sticky="w")
        if self.kind == "point":
            ttk.Label(self.frame, text="Position").grid(
                row=2, column=0, sticky="w", pady=(5, 0)
            )
            ttk.Entry(self.frame, textvariable=self.first_var, width=9).grid(
                row=2, column=1, sticky="w", padx=(4, 3), pady=(5, 0)
            )
            ttk.Label(self.frame, text="ft", style="Unit.TLabel").grid(
                row=2, column=2, sticky="w", pady=(5, 0)
            )
        else:
            ttk.Label(self.frame, text="Start / end").grid(
                row=2, column=0, sticky="w", pady=(5, 0)
            )
            ttk.Entry(self.frame, textvariable=self.first_var, width=7).grid(
                row=2, column=1, sticky="w", padx=(4, 2), pady=(5, 0)
            )
            ttk.Entry(self.frame, textvariable=self.second_var, width=7).grid(
                row=2, column=2, sticky="w", padx=(2, 2), pady=(5, 0)
            )
            ttk.Label(self.frame, text="ft", style="Unit.TLabel").grid(
                row=2, column=3, sticky="w", pady=(5, 0)
            )

    def set_first(self, value: float) -> None:
        self.first_var.set(f"{value:g}")

    def set_second(self, value: float) -> None:
        self.second_var.set(f"{value:g}")


class BeamDesigner:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Beam Designer")
        self.root.geometry("1440x940")
        self.root.minsize(1120, 760)
        self.root.configure(background=BACKGROUND)

        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background=BACKGROUND)
        style.configure("Card.TFrame", background=CARD)
        style.configure("TLabel", background=BACKGROUND, foreground=INK, font=("Helvetica", 10))
        style.configure("Card.TLabel", background=CARD, foreground=INK, font=("Helvetica", 10))
        style.configure(
            "Title.TLabel", background=BACKGROUND, foreground=INK,
            font=("Helvetica", 18, "bold")
        )
        style.configure(
            "Section.TLabel", background=CARD, foreground=INK,
            font=("Helvetica", 11, "bold")
        )
        style.configure(
            "LoadTitle.TLabel", background=CARD, foreground=ACCENT,
            font=("Helvetica", 10, "bold")
        )
        style.configure("Unit.TLabel", background=CARD, foreground=MUTED)
        style.configure("Muted.TLabel", background=CARD, foreground=MUTED)
        style.configure("Accent.TButton", font=("Helvetica", 10, "bold"))
        style.configure("TCheckbutton", background=CARD, foreground=INK)
        style.configure("TRadiobutton", background=CARD, foreground=INK)

        self._syncing = False
        self._normalizing = False
        self.inputs_valid = True
        self.load_editors: list[LoadEditor] = []
        self.span_var = tk.DoubleVar(value=20.0)
        self.span_entry_var = tk.StringVar(value="20")
        self.support_var = tk.StringVar(value="Simply supported")
        self.material_var = tk.StringVar(value="Steel W-shape")
        self.section_var = tk.StringVar(value="W12x26")
        self.deflection_var = tk.IntVar(value=360)
        self.self_weight_var = tk.BooleanVar(value=False)
        self.warning_var = tk.StringVar(value="")
        self.max_load_var = tk.StringVar(value="")
        self.weight_var = tk.StringVar(value="")
        self.weight_load_var = tk.StringVar(value="")
        self.self_weight_note_var = tk.StringVar(value="")
        self.allowable_stress_var = tk.StringVar(value="")
        self.recommendation_var = tk.StringVar(value="")
        self.summary_vars = {
            "shear": tk.StringVar(value="—"),
            "moment": tk.StringVar(value="—"),
            "deflection": tk.StringVar(value="—"),
            "reactions": tk.StringVar(value="—"),
        }
        self.result: AnalysisResult | None = None
        self.recommendation: Section | None = None
        self.current_design_path: Path | None = None
        self.point_loads: tuple[PointLoad, ...] = ()
        self.uniform_loads: tuple[UniformLoad, ...] = ()
        self.dragged_editor: LoadEditor | None = None

        self._build_file_menu()
        self._build_layout()
        self._add_load("uniform", 1.0, 0.0, 20.0)
        self.span_entry_var.trace_add("write", self._input_changed)
        self.support_var.trace_add("write", self._input_changed)
        self.section_var.trace_add("write", self._input_changed)
        self.deflection_var.trace_add("write", self._input_changed)
        self.self_weight_var.trace_add("write", self._input_changed)
        self._input_changed()

    def _build_file_menu(self) -> None:
        menu_bar = tk.Menu(self.root)
        file_menu = tk.Menu(menu_bar, tearoff=False)
        file_menu.add_command(label="Save", command=self._save_design)
        file_menu.add_command(label="Open", command=self._open_design)
        menu_bar.add_cascade(label="File", menu=file_menu)
        self.root.configure(menu=menu_bar)

    def _build_layout(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=0, minsize=350)
        outer.columnconfigure(1, weight=1)

        self.left_canvas = tk.Canvas(
            outer, width=360, background=BACKGROUND, highlightthickness=0
        )
        self.left_scroll = ttk.Scrollbar(
            outer, orient="vertical", command=self.left_canvas.yview
        )
        self.left_canvas.configure(yscrollcommand=self.left_scroll.set)
        self.left_canvas.grid(row=0, column=0, sticky="nsew")
        self.left_scroll.grid(row=0, column=0, sticky="nse")
        self.input_panel = ttk.Frame(self.left_canvas, padding=(0, 0, 10, 0))
        self.input_window = self.left_canvas.create_window(
            (0, 0), window=self.input_panel, anchor="nw", width=340
        )
        self.input_panel.bind(
            "<Configure>",
            lambda _event: self.left_canvas.configure(
                scrollregion=self.left_canvas.bbox("all")
            ),
        )
        self.left_canvas.bind(
            "<Configure>",
            lambda event: self.left_canvas.itemconfigure(
                self.input_window, width=event.width - 12
            ),
        )
        self.left_canvas.bind("<Enter>", lambda _event: self._bind_scroll(True))
        self.left_canvas.bind("<Leave>", lambda _event: self._bind_scroll(False))
        self._build_controls()
        self._build_results(outer)

    def _bind_scroll(self, enabled: bool) -> None:
        if enabled:
            self.root.bind_all("<MouseWheel>", self._mousewheel)
        else:
            self.root.unbind_all("<MouseWheel>")

    def _mousewheel(self, event: tk.Event) -> None:
        delta = int(event.delta)
        units = -int(delta / 120) if abs(delta) >= 120 else -delta
        self.left_canvas.yview_scroll(units, "units")

    def _card(self, parent: ttk.Frame, title: str) -> ttk.Frame:
        card = ttk.Frame(parent, style="Card.TFrame", padding=12)
        card.pack(fill="x", pady=(0, 10))
        ttk.Label(card, text=title, style="Section.TLabel").pack(anchor="w", pady=(0, 9))
        return card

    def _build_controls(self) -> None:
        ttk.Label(self.input_panel, text="Beam Designer", style="Title.TLabel").pack(
            anchor="w", pady=(2, 12)
        )
        support_card = self._card(self.input_panel, "Beam")
        ttk.Label(support_card, text="Support type", style="Card.TLabel").pack(anchor="w")
        ttk.Combobox(
            support_card,
            textvariable=self.support_var,
            values=("Simply supported", "Cantilever"),
            state="readonly",
        ).pack(fill="x", pady=(4, 10))
        span_header = ttk.Frame(support_card, style="Card.TFrame")
        span_header.pack(fill="x")
        ttk.Label(span_header, text="Span", style="Card.TLabel").pack(side="left")
        ttk.Entry(span_header, textvariable=self.span_entry_var, width=8).pack(
            side="right"
        )
        ttk.Label(span_header, text="ft", style="Card.TLabel").pack(
            side="right", padx=(0, 6)
        )
        self.span_scale = tk.Scale(
            support_card,
            variable=self.span_var,
            from_=4,
            to=40,
            resolution=0.25,
            orient="horizontal",
            showvalue=False,
            background=CARD,
            highlightthickness=0,
            troughcolor="#dce5ec",
            activebackground=ACCENT,
            command=self._span_slider_changed,
        )
        self.span_scale.pack(fill="x", pady=(2, 0))
        ttk.Label(
            support_card,
            text="4 to 40 ft",
            style="Muted.TLabel",
        ).pack(anchor="e")

        section_card = self._card(self.input_panel, "Section & material")
        ttk.Label(section_card, text="Material", style="Card.TLabel").pack(anchor="w")
        self.material_select = ttk.Combobox(
            section_card,
            textvariable=self.material_var,
            values=tuple(SECTIONS),
            state="readonly",
        )
        self.material_select.pack(fill="x", pady=(4, 9))
        self.material_select.bind("<<ComboboxSelected>>", self._material_changed)
        ttk.Label(section_card, text="Section", style="Card.TLabel").pack(anchor="w")
        self.section_select = ttk.Combobox(
            section_card, textvariable=self.section_var, state="readonly"
        )
        self.section_select.pack(fill="x", pady=(4, 9))
        self._set_section_options()
        ttk.Checkbutton(
            section_card,
            text="Include self-weight",
            variable=self.self_weight_var,
        ).pack(anchor="w", pady=(1, 7))
        ttk.Label(section_card, textvariable=self.weight_var, style="Card.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            section_card, textvariable=self.weight_load_var, style="Muted.TLabel"
        ).pack(anchor="w", pady=(3, 0))

        deflection_card = self._card(self.input_panel, "Deflection limit")
        ttk.Radiobutton(
            deflection_card, text="L/240", value=240, variable=self.deflection_var
        ).pack(side="left", padx=(0, 18))
        ttk.Radiobutton(
            deflection_card, text="L/360", value=360, variable=self.deflection_var
        ).pack(side="left")

        self.loads_card = self._card(self.input_panel, "Loads")
        self.loads_frame = ttk.Frame(self.loads_card, style="Card.TFrame")
        self.loads_frame.pack(fill="x")
        add_frame = ttk.Frame(self.loads_card, style="Card.TFrame")
        add_frame.pack(fill="x", pady=(8, 0))
        self.add_point_button = ttk.Button(
            add_frame,
            text="Add point load",
            command=lambda: self._add_load("point"),
        )
        self.add_point_button.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.add_uniform_button = ttk.Button(
            add_frame,
            text="Add uniform load",
            command=lambda: self._add_load("uniform"),
        )
        self.add_uniform_button.pack(side="left", fill="x", expand=True, padx=(4, 0))
        ttk.Label(
            self.loads_card, textvariable=self.max_load_var, style="Muted.TLabel"
        ).pack(anchor="w", pady=(5, 0))

    def _build_results(self, parent: ttk.Frame) -> None:
        self.right = ttk.Frame(parent, padding=(14, 0, 0, 0))
        self.right.grid(row=0, column=1, sticky="nsew")
        self.right.rowconfigure(2, weight=1)
        self.right.columnconfigure(0, weight=1)

        header = ttk.Frame(self.right)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 7))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Analysis results", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.print_button = ttk.Button(
            header, text="Print / Save PDF", style="Accent.TButton",
            command=self._print_pdf,
        )
        self.print_button.grid(row=0, column=2, sticky="e")
        self.export_button = ttk.Button(
            header, text="Export CSV", command=self._export_csv
        )
        self.export_button.grid(row=0, column=1, sticky="e", padx=(0, 8))
        self.warning_label = ttk.Label(
            self.right, textvariable=self.warning_var, foreground=WARNING
        )
        self.warning_label.grid(row=1, column=0, sticky="w", pady=(0, 5))

        chart_frame = ttk.Frame(self.right, style="Card.TFrame", padding=7)
        chart_frame.grid(row=2, column=0, sticky="nsew")
        chart_frame.rowconfigure(0, weight=1)
        chart_frame.columnconfigure(0, weight=1)
        self.figure = Figure(figsize=(10.5, 7.6), dpi=100, facecolor=CARD)
        self.chart_canvas = FigureCanvasTkAgg(self.figure, master=chart_frame)
        self.chart_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self.hover_label = ttk.Label(
            chart_frame, text="", style="Muted.TLabel", anchor="e"
        )
        self.hover_label.grid(row=1, column=0, sticky="ew", pady=(2, 0))
        self.chart_canvas.mpl_connect("motion_notify_event", self._on_hover)
        self.chart_canvas.mpl_connect("button_press_event", self._start_drag)
        self.chart_canvas.mpl_connect("motion_notify_event", self._drag_load)
        self.chart_canvas.mpl_connect("button_release_event", self._stop_drag)

        lower = ttk.Frame(self.right)
        lower.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        lower.columnconfigure((0, 1), weight=1)
        summary = ttk.Frame(lower, style="Card.TFrame", padding=12)
        summary.grid(row=0, column=0, columnspan=2, sticky="ew", padx=(0, 0))
        ttk.Label(summary, text="Peak results", style="Section.TLabel").pack(
            anchor="w", pady=(0, 9)
        )
        summary_body = ttk.Frame(summary, style="Card.TFrame")
        summary_body.pack(fill="x")
        summary_rows = (
            ("shear", "Maximum shear"),
            ("moment", "Maximum moment"),
            ("deflection", "Maximum deflection"),
            ("reactions", "Reactions"),
        )
        for key, title in summary_rows:
            row_frame = ttk.Frame(summary_body, style="Card.TFrame")
            row_frame.pack(fill="x", pady=2)
            ttk.Label(row_frame, text=title, style="Card.TLabel").pack(side="left")
            ttk.Label(
                row_frame, textvariable=self.summary_vars[key], style="Card.TLabel"
            ).pack(side="right")
        checks_row = ttk.Frame(lower)
        checks_row.grid(row=1, column=0, columnspan=2, sticky="ew")
        checks_row.columnconfigure((0, 1), weight=1)
        self.bending_card, self.bending_widgets = self._check_card(
            checks_row, "Bending"
        )
        self.bending_card.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.deflection_card, self.deflection_widgets = self._check_card(
            checks_row, "Deflection"
        )
        self.deflection_card.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        info_card = ttk.Frame(lower, style="Card.TFrame", padding=9)
        info_card.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Label(
            info_card, textvariable=self.self_weight_note_var, style="Card.TLabel"
        ).pack(anchor="w")
        ttk.Label(
            info_card, textvariable=self.allowable_stress_var, style="Card.TLabel"
        ).pack(anchor="w", pady=(4, 0))
        rec_frame = ttk.Frame(info_card, style="Card.TFrame")
        rec_frame.pack(fill="x", pady=(7, 0))
        self.recommendation_label = ttk.Label(
            rec_frame, textvariable=self.recommendation_var, style="Card.TLabel"
        )
        self.recommendation_label.pack(side="left", fill="x", expand=True)
        self.use_recommendation_button = ttk.Button(
            rec_frame, text="Use section", command=self._use_recommendation
        )
        self.use_recommendation_button.pack(side="right")

    def _check_card(
        self, parent: ttk.Frame, title: str
    ) -> tuple[ttk.Frame, dict[str, object]]:
        card = ttk.Frame(parent, style="Card.TFrame", padding=10)
        title_label = ttk.Label(card, text=title, style="Section.TLabel")
        title_label.pack(anchor="w")
        value_label = ttk.Label(card, text="—", style="Card.TLabel")
        value_label.pack(anchor="w", pady=(6, 2))
        allow_label = ttk.Label(card, text="—", style="Muted.TLabel")
        allow_label.pack(anchor="w")
        bar = tk.Canvas(card, height=13, background="#e6ebef", highlightthickness=0)
        bar.pack(fill="x", pady=(7, 4))
        status_label = ttk.Label(card, text="—", style="Card.TLabel")
        status_label.pack(anchor="w")
        bar.bind(
            "<Configure>",
            lambda _event, canvas=bar: self._draw_ratio_bar(canvas, 0.0),
        )
        return card, {
            "value": value_label,
            "allowable": allow_label,
            "bar": bar,
            "status": status_label,
        }

    def _draw_ratio_bar(self, canvas: tk.Canvas, ratio: float) -> None:
        canvas.delete("all")
        width = max(canvas.winfo_width(), 2)
        color = "#3e9367" if ratio < 0.7 else "#d69a2d" if ratio <= 1 else "#c84c4c"
        canvas.create_rectangle(0, 0, width, 13, fill="#e6ebef", outline="")
        canvas.create_rectangle(
            0, 0, min(width, width * max(0.0, min(ratio, 1.5)) / 1.5), 13,
            fill=color, outline="",
        )
        for mark in (0.7, 1.0):
            canvas.create_line(width * mark / 1.5, 0, width * mark / 1.5, 13, fill="white")

    def _set_section_options(self) -> None:
        material = self.material_var.get()
        section_names = tuple(section.name for section in SECTIONS[material])
        self.section_select.configure(values=section_names)

    def _material_changed(self, _event: tk.Event | None = None) -> None:
        self._set_section_options()
        self.section_var.set(SECTIONS[self.material_var.get()][0].name)
        self._input_changed()

    def _add_load(
        self,
        kind: str,
        magnitude: float | None = None,
        first_position: float | None = None,
        second_position: float | None = None,
    ) -> None:
        if len(self.load_editors) >= 10:
            return
        span = float(self.span_var.get())
        if kind == "point":
            value = 10.0 if magnitude is None else magnitude
            position = (
                span if self.support_var.get() == "Cantilever" else span / 2
            ) if first_position is None else first_position
            editor = LoadEditor(self, self.loads_frame, kind, value, position)
        else:
            editor = LoadEditor(
                self,
                self.loads_frame,
                kind,
                1.0 if magnitude is None else magnitude,
                0.0 if first_position is None else first_position,
                span if second_position is None else second_position,
            )
        editor.frame.pack(fill="x", pady=(0, 6))
        self.load_editors.append(editor)
        self._input_changed()

    def _remove_load(self, editor: LoadEditor) -> None:
        self.load_editors.remove(editor)
        editor.frame.destroy()
        self._input_changed()

    def _span_slider_changed(self, value: str) -> None:
        if self._syncing:
            return
        self._syncing = True
        self.span_entry_var.set(f"{float(value):g}")
        self._syncing = False
        self._input_changed()

    def _input_changed(self, *_args: object) -> None:
        if self._syncing or self._normalizing:
            return
        warnings: list[str] = []
        try:
            span = float(self.span_entry_var.get())
            if not np.isfinite(span):
                raise ValueError
            bounded_span = min(40.0, max(4.0, span))
            if bounded_span != span:
                span = bounded_span
                self.span_entry_var.set(f"{span:g}")
                warnings.append("Span limited to 4–40 ft.")
            self._syncing = True
            self.span_var.set(span)
            self._syncing = False

            points: list[PointLoad] = []
            uniforms: list[UniformLoad] = []
            self._normalizing = True
            for editor in self.load_editors:
                magnitude = float(editor.magnitude_var.get())
                first = float(editor.first_var.get())
                if not all(np.isfinite(value) for value in (magnitude, first)):
                    raise ValueError
                magnitude_limit = 100.0 if editor.kind == "point" else 10.0
                bounded_magnitude = min(
                    magnitude_limit, max(-magnitude_limit, magnitude)
                )
                if bounded_magnitude != magnitude:
                    magnitude = bounded_magnitude
                    editor.magnitude_var.set(f"{magnitude:g}")
                    warnings.append("Load magnitude limited to its allowed range.")
                bounded_first = min(span, max(0.0, first))
                if bounded_first != first:
                    first = bounded_first
                    editor.set_first(first)
                    warnings.append("Load position clamped to the beam.")
                if editor.kind == "point":
                    points.append(PointLoad(magnitude, first))
                    continue
                second = float(editor.second_var.get())
                if not np.isfinite(second):
                    raise ValueError
                bounded_second = min(span, max(0.0, second))
                if bounded_second != second:
                    second = bounded_second
                    editor.set_second(second)
                    warnings.append("Load position clamped to the beam.")
                if first > second:
                    first, second = second, first
                    editor.set_first(first)
                    editor.set_second(second)
                    warnings.append("Uniform-load start and end positions swapped.")
                uniforms.append(UniformLoad(magnitude, first, second))
        except ValueError:
            self._normalizing = False
            self.inputs_valid = False
            self.warning_var.set("Enter valid numeric values for span and loads.")
            return
        finally:
            self._syncing = False
            self._normalizing = False

        self.point_loads = tuple(points)
        self.uniform_loads = tuple(uniforms)
        material = self.material_var.get()
        section = next(
            item for item in SECTIONS[material] if item.name == self.section_var.get()
        )
        try:
            self.result = analyze_beam(
                span_ft=span,
                support=self.support_var.get(),  # type: ignore[arg-type]
                point_loads=self.point_loads,
                uniform_loads=self.uniform_loads,
                material=material,  # type: ignore[arg-type]
                section=section,
                deflection_limit=self.deflection_var.get(),
                include_self_weight=self.self_weight_var.get(),
            )
            self.recommendation = None
            if self.point_loads or self.uniform_loads:
                self.recommendation = lightest_passing_section(
                    span_ft=span,
                    support=self.support_var.get(),  # type: ignore[arg-type]
                    point_loads=self.point_loads,
                    uniform_loads=self.uniform_loads,
                    material=material,  # type: ignore[arg-type]
                    deflection_limit=self.deflection_var.get(),
                    include_self_weight=self.self_weight_var.get(),
                )
        except ValueError as error:
            self.inputs_valid = False
            self.warning_var.set(str(error))
            return

        self.inputs_valid = True
        if not warnings and not self.point_loads and not self.uniform_loads:
            warnings.append("Add a load to see results.")
        self.warning_var.set("  ".join(dict.fromkeys(warnings)))
        self._update_load_controls()
        self._update_weight_labels(section)
        self._update_results(section, material)
        self._draw_diagrams(span)

    def _update_load_controls(self) -> None:
        at_limit = len(self.load_editors) >= 10
        self.add_point_button.configure(state="disabled" if at_limit else "normal")
        self.add_uniform_button.configure(state="disabled" if at_limit else "normal")
        self.max_load_var.set("Maximum of 10 loads." if at_limit else "")

    def _update_weight_labels(self, section: Section) -> None:
        kip_ft = section.weight_lb_ft / 1000.0
        self.weight_var.set(f"Section weight: {section.weight_lb_ft:.2f} lb/ft")
        self.weight_load_var.set(f"Equivalent self-weight: {kip_ft:.5f} kip/ft")
        self.self_weight_note_var.set(
            "Self-weight is included." if self.self_weight_var.get()
            else "Self-weight is ignored."
        )
        allowable = MATERIAL_PROPERTIES[self.material_var.get()][1]
        self.allowable_stress_var.set(
            f"Allowable bending stress: Fb = {allowable:g} ksi "
            f"({'steel' if self.material_var.get() == 'Steel W-shape' else 'lumber'})."
        )

    def _update_results(self, section: Section, material: MaterialKey) -> None:
        result = self.result
        if result is None:
            return
        has_loads = bool(self.point_loads or self.uniform_loads)
        self.summary_vars["shear"].set(
            f"{result.max_shear_kip:.2f} k at {result.max_shear_position_ft:.2f} ft"
        )
        self.summary_vars["moment"].set(
            f"{result.max_moment_kip_ft:.2f} kip-ft at "
            f"{result.max_moment_position_ft:.2f} ft"
        )
        self.summary_vars["deflection"].set(
            f"{result.max_deflection_in:.3f} in at "
            f"{result.max_deflection_position_ft:.2f} ft"
        )
        if result.right_reaction_kip is None:
            reaction_text = (
                f"R_A = {result.left_reaction_kip:.2f} k; "
                f"M_A = {result.fixed_end_moment_kip_ft:.2f} kip-ft"
            )
        else:
            reaction_text = (
                f"R_A = {result.left_reaction_kip:.2f} k; "
                f"R_B = {result.right_reaction_kip:.2f} k"
            )
        self.summary_vars["reactions"].set(reaction_text)

        checks = result.checks
        self._update_check_card(
            self.bending_widgets,
            actual=f"{checks.bending_stress_ksi:.2f} ksi",
            allowable=f"Allowable: {checks.allowable_bending_ksi:g} ksi",
            ratio=checks.bending_stress_ksi / checks.allowable_bending_ksi,
            passes=checks.bending_passes,
            has_loads=has_loads,
        )
        self._update_check_card(
            self.deflection_widgets,
            actual=f"{abs(checks.max_deflection_in):.3f} in",
            allowable=f"Allowable: {checks.allowable_deflection_in:.3f} in",
            ratio=abs(checks.max_deflection_in) / checks.allowable_deflection_in,
            passes=checks.deflection_passes,
            has_loads=has_loads,
        )
        if self.recommendation is None and has_loads:
            self.recommendation_var.set("No section in this list passes.")
            self.use_recommendation_button.pack_forget()
        elif self.recommendation is not None and has_loads:
            if self.recommendation.name == section.name:
                self.recommendation_var.set(
                    f"{section.name} is already the lightest passing section."
                )
                self.use_recommendation_button.pack_forget()
            else:
                self.recommendation_var.set(
                    f"Lightest passing section: {self.recommendation.name}"
                )
                self.use_recommendation_button.pack(side="right")
        else:
            self.recommendation_var.set("")
            self.use_recommendation_button.pack_forget()

    def _update_check_card(
        self,
        widgets: dict[str, object],
        *,
        actual: str,
        allowable: str,
        ratio: float,
        passes: bool,
        has_loads: bool,
    ) -> None:
        value_label = widgets["value"]
        allowable_label = widgets["allowable"]
        status_label = widgets["status"]
        bar = widgets["bar"]
        assert isinstance(value_label, ttk.Label)
        assert isinstance(allowable_label, ttk.Label)
        assert isinstance(status_label, ttk.Label)
        assert isinstance(bar, tk.Canvas)
        value_label.configure(text=actual)
        allowable_label.configure(text=allowable)
        status_label.configure(
            text=("PASS" if passes else "FAIL") if has_loads else "Add a load",
            foreground=("#2f8056" if passes else "#b43f3f") if has_loads else MUTED,
        )
        self._draw_ratio_bar(bar, ratio if has_loads else 0.0)

    def _draw_diagrams(self, span: float) -> None:
        result = self.result
        if result is None:
            return
        self.figure.clear()
        grid = self.figure.add_gridspec(
            4, 1, height_ratios=(1.15, 1.2, 1.2, 1.2), hspace=0.42
        )
        beam_axis = self.figure.add_subplot(grid[0])
        self.beam_axis = beam_axis
        shear_axis = self.figure.add_subplot(grid[1])
        moment_axis = self.figure.add_subplot(grid[2], sharex=shear_axis)
        deflection_axis = self.figure.add_subplot(grid[3], sharex=shear_axis)
        self.diagram_axes = (shear_axis, moment_axis, deflection_axis)
        self.hover_lines = []

        self._draw_beam_axis(beam_axis, span, result)
        x_shear, y_shear = self._shear_plot_values(result, span)
        shear_axis.plot(x_shear, y_shear, color="#377aa5", linewidth=1.6)
        shear_axis.fill_between(x_shear, 0, y_shear, color="#6ca5ca", alpha=0.22)
        moment_axis.plot(
            result.x_ft, result.moment_kip_ft, color="#4d8c6b", linewidth=1.6
        )
        moment_axis.fill_between(
            result.x_ft, 0, result.moment_kip_ft, color="#78b48f", alpha=0.22
        )
        deflection_axis.plot(
            result.x_ft, result.deflection_in, color="#ba7b37", linewidth=1.6
        )
        deflection_axis.fill_between(
            result.x_ft, 0, result.deflection_in, color="#dca96e", alpha=0.2
        )
        axes_specs = (
            (shear_axis, "Shear", "kips"),
            (moment_axis, "Moment", "kip-ft"),
            (deflection_axis, "Deflection", "in"),
        )
        for axis, title, unit in axes_specs:
            axis.axhline(0, color="#6b7780", linewidth=0.7)
            axis.set_xlim(0, span)
            axis.set_ylabel(f"{title}\n({unit})", fontsize=8)
            axis.grid(axis="x", color="#e3e8ec", linewidth=0.7)
            axis.tick_params(labelsize=8, labelbottom=False)
            line = axis.axvline(0, color="#293b49", linewidth=0.8, alpha=0.65)
            line.set_visible(False)
            self.hover_lines.append(line)
        deflection_axis.tick_params(labelbottom=True)
        deflection_axis.set_xlabel("Position along beam (ft)", fontsize=8)
        shear_axis.annotate(
            f"{result.max_shear_kip:.2f} k",
            xy=(result.max_shear_position_ft, result.max_shear_kip),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8,
            color="#2b658c",
        )
        moment_axis.annotate(
            f"{result.max_moment_kip_ft:.2f} kip-ft",
            xy=(result.max_moment_position_ft, result.max_moment_kip_ft),
            xytext=(5, 5 if result.max_moment_kip_ft >= 0 else -12),
            textcoords="offset points",
            fontsize=8,
            color="#3e7658",
        )
        deflection_axis.annotate(
            f"{result.max_deflection_in:.3f} in",
            xy=(result.max_deflection_position_ft, result.max_deflection_in),
            xytext=(5, 5 if result.max_deflection_in >= 0 else -12),
            textcoords="offset points",
            fontsize=8,
            color="#94602d",
        )
        self.figure.subplots_adjust(left=0.09, right=0.985, top=0.985, bottom=0.08)
        self.chart_canvas.draw_idle()

    def _draw_beam_axis(
        self, axis, span: float, result: AnalysisResult
    ) -> None:
        axis.plot((0, span), (0, 0), color="#283d4c", linewidth=4, solid_capstyle="round")
        if self.support_var.get() == "Simply supported":
            for x in (0, span):
                axis.add_patch(
                    Polygon(
                        ((x, -0.07), (x - span * 0.025, -0.43),
                         (x + span * 0.025, -0.43)),
                        closed=True, facecolor="#d6e0e8", edgecolor="#344c5c",
                    )
                )
        else:
            axis.plot((0, 0), (-0.55, 0.72), color="#293e4d", linewidth=4)
            for y in np.linspace(-0.5, 0.7, 9):
                axis.plot((-span * 0.018, 0), (y - 0.12, y), color="#597083", linewidth=0.7)

        for index, load in enumerate(self.uniform_loads):
            y = 0.76 + index * 0.30
            axis.plot(
                (load.start_ft, load.end_ft), (y, y),
                color="#3b779d", linewidth=1.1,
            )
            for x in np.linspace(load.start_ft, load.end_ft, 9):
                self._load_arrow(axis, float(x), y, load.magnitude_kip_ft, "#3b779d")
            axis.text(
                (load.start_ft + load.end_ft) / 2, y + 0.12,
                f"{load.magnitude_kip_ft:g} kip/ft",
                ha="center", fontsize=7, color="#315f7d",
            )
        if self.self_weight_var.get():
            self_weight = result.effective_uniform_loads[-1]
            y = 0.82 + len(self.uniform_loads) * 0.30
            axis.plot((0, span), (y, y), color="#d38a32", linestyle="--")
            for x in np.linspace(0, span, 9):
                self._load_arrow(axis, float(x), y, self_weight.magnitude_kip_ft, "#d38a32")
            axis.text(
                span / 2, y + 0.12,
                f"Self-weight {self_weight.magnitude_kip_ft:.3f} kip/ft",
                ha="center", fontsize=7, color="#a5671e",
            )
        for load in self.point_loads:
            self._load_arrow(axis, load.position_ft, 1.25, load.magnitude_kip, "#2c6083")
            axis.text(
                load.position_ft, 1.34,
                f"{load.magnitude_kip:g} k",
                ha="center", fontsize=7, color="#2c6083",
            )

        axis.annotate(
            f"R_A {result.left_reaction_kip:.2f} k",
            xy=(0, -0.38), xytext=(span * 0.05, -0.88),
            fontsize=7, color="#a14444",
            arrowprops={"arrowstyle": "->", "color": "#a14444", "lw": 0.8},
        )
        if result.right_reaction_kip is not None:
            axis.annotate(
                f"R_B {result.right_reaction_kip:.2f} k",
                xy=(span, -0.38), xytext=(span * 0.78, -0.88),
                fontsize=7, color="#a14444",
                arrowprops={"arrowstyle": "->", "color": "#a14444", "lw": 0.8},
            )
        else:
            axis.annotate(
                "", xy=(span * 0.04, 0.52), xytext=(span * 0.20, 0.52),
                arrowprops={
                    "arrowstyle": "->", "color": "#a14444",
                    "connectionstyle": "arc3,rad=0.6",
                },
            )
            axis.text(
                span * 0.21, 0.55,
                f"M_A {result.fixed_end_moment_kip_ft:.2f} kip-ft",
                fontsize=7, color="#a14444",
            )
        axis.set_xlim(-span * 0.07, span * 1.07)
        axis.set_ylim(-1.0, 1.75 + 0.30 * (len(self.uniform_loads) + int(self.self_weight_var.get())))
        axis.set_xticks([])
        axis.set_yticks([])
        for spine in axis.spines.values():
            spine.set_visible(False)
        axis.set_title("Beam and applied loads", fontsize=8, loc="left", color=INK)

    def _load_arrow(self, axis, x: float, top: float, magnitude: float, color: str) -> None:
        if magnitude >= 0:
            axis.annotate(
                "", xy=(x, 0.08), xytext=(x, top),
                arrowprops={"arrowstyle": "-|>", "color": color, "lw": 0.7},
            )
        else:
            axis.annotate(
                "", xy=(x, top), xytext=(x, 0.08),
                arrowprops={"arrowstyle": "-|>", "color": color, "lw": 0.7},
            )

    def _shear_plot_values(
        self, result: AnalysisResult, span: float
    ) -> tuple[np.ndarray, np.ndarray]:
        point_jumps = {position: (left, right) for position, left, right in result.point_load_shear}
        x_values: list[float] = []
        y_values: list[float] = []
        for x, value in zip(result.x_ft, result.shear_kip):
            position = float(x)
            jump = next(
                (values for load_position, values in point_jumps.items()
                 if abs(load_position - position) < 1e-10),
                None,
            )
            if jump is not None:
                x_values.extend((position, position))
                y_values.extend(jump)
            elif (
                self.support_var.get() == "Simply supported"
                and abs(position - span) < 1e-10
            ):
                left_value = float(value) - (result.right_reaction_kip or 0.0)
                x_values.extend((position, position))
                y_values.extend((left_value, float(value)))
            else:
                x_values.append(position)
                y_values.append(float(value))
        return np.asarray(x_values), np.asarray(y_values)

    def _on_hover(self, event) -> None:
        if event.inaxes not in getattr(self, "diagram_axes", ()):
            for line in getattr(self, "hover_lines", ()):
                line.set_visible(False)
            self.hover_label.configure(text="")
            self.chart_canvas.draw_idle()
            return
        result = self.result
        if result is None or event.xdata is None:
            return
        x = min(float(self.span_var.get()), max(0.0, float(event.xdata)))
        for line in self.hover_lines:
            line.set_xdata((x, x))
            line.set_visible(True)
        shear = float(np.interp(x, result.x_ft, result.shear_kip))
        moment = float(np.interp(x, result.x_ft, result.moment_kip_ft))
        deflection = float(np.interp(x, result.x_ft, result.deflection_in))
        self.hover_label.configure(
            text=f"x = {x:.2f} ft     V = {shear:.2f} k     "
            f"M = {moment:.2f} kip-ft     y = {deflection:.3f} in"
        )
        self.chart_canvas.draw_idle()

    def _start_drag(self, event) -> None:
        if (
            event.button != 1
            or event.inaxes is not getattr(self, "beam_axis", None)
            or event.xdata is None
        ):
            return
        point_editors = [editor for editor in self.load_editors if editor.kind == "point"]
        if not point_editors:
            return
        span = float(self.span_var.get())
        nearest = min(
            point_editors,
            key=lambda editor: abs(float(editor.first_var.get()) - float(event.xdata)),
        )
        if abs(float(nearest.first_var.get()) - float(event.xdata)) <= span * 0.035:
            self.dragged_editor = nearest

    def _drag_load(self, event) -> None:
        if self.dragged_editor is None or event.x is None or event.y is None:
            return
        beam_axis = getattr(self, "beam_axis", None)
        if beam_axis is None:
            return
        x_position = float(
            beam_axis.transData.inverted().transform((event.x, event.y))[0]
        )
        span = float(self.span_var.get())
        snapped = round(min(span, max(0.0, x_position)) * 4.0) / 4.0
        self.dragged_editor.set_first(min(span, snapped))

    def _stop_drag(self, _event) -> None:
        self.dragged_editor = None

    def _use_recommendation(self) -> None:
        if self.recommendation is not None:
            self.section_var.set(self.recommendation.name)
            self._input_changed()

    def _current_design(self) -> BeamDesign:
        if not self.inputs_valid:
            raise ValueError("Correct the invalid beam inputs before saving.")
        point_loads = iter(self.point_loads)
        uniform_loads = iter(self.uniform_loads)
        ordered_loads = tuple(
            next(point_loads) if editor.kind == "point" else next(uniform_loads)
            for editor in self.load_editors
        )
        return BeamDesign(
            support_type=self.support_var.get(),  # type: ignore[arg-type]
            span_ft=float(self.span_var.get()),
            material=self.material_var.get(),  # type: ignore[arg-type]
            section_name=self.section_var.get(),
            deflection_limit=self.deflection_var.get(),
            include_self_weight=self.self_weight_var.get(),
            loads=ordered_loads,
        )

    def _save_design(self) -> None:
        if not self.inputs_valid:
            messagebox.showerror(
                "Could not save beam design",
                "Correct the invalid beam inputs before saving.",
                parent=self.root,
            )
            return
        path = self.current_design_path
        if path is None:
            selected_path = filedialog.asksaveasfilename(
                parent=self.root,
                title="Save beam design",
                defaultextension=".beam.json",
                filetypes=(
                    ("Beam design files", "*.beam.json"),
                    ("JSON files", "*.json"),
                ),
                initialfile="beam-design.beam.json",
            )
            if not selected_path:
                return
            path = Path(selected_path)
        try:
            saved_path = save_design(path, self._current_design())
        except (OSError, ValueError) as error:
            messagebox.showerror(
                "Could not save beam design",
                str(error),
                parent=self.root,
            )
            return
        self.current_design_path = saved_path
        messagebox.showinfo(
            "Beam design saved",
            f"Saved beam design to:\n{saved_path}",
            parent=self.root,
        )

    def _open_design(self) -> None:
        path = filedialog.askopenfilename(
            parent=self.root,
            title="Open beam design",
            filetypes=(
                ("Beam design files", "*.beam.json"),
                ("JSON files", "*.json"),
            ),
        )
        if not path:
            return
        try:
            design = load_design(path)
        except (OSError, ValueError) as error:
            messagebox.showerror(
                "Could not open beam design",
                str(error),
                parent=self.root,
            )
            return
        self._apply_design(design)
        self.current_design_path = Path(path)
        messagebox.showinfo(
            "Beam design opened",
            f"Opened beam design from:\n{path}",
            parent=self.root,
        )

    def _apply_design(self, design: BeamDesign) -> None:
        self._syncing = True
        self.dragged_editor = None
        try:
            self.span_entry_var.set(f"{design.span_ft:g}")
            self.span_var.set(design.span_ft)
            self.support_var.set(design.support_type)
            self.material_var.set(design.material)
            self._set_section_options()
            self.section_var.set(design.section_name)
            self.deflection_var.set(design.deflection_limit)
            self.self_weight_var.set(design.include_self_weight)
            for editor in self.load_editors:
                editor.frame.destroy()
            self.load_editors.clear()
            for load in design.loads:
                if isinstance(load, PointLoad):
                    self._add_load("point", load.magnitude_kip, load.position_ft)
                else:
                    self._add_load(
                        "uniform",
                        load.magnitude_kip_ft,
                        load.start_ft,
                        load.end_ft,
                    )
        finally:
            self._syncing = False
        self._input_changed()

    def _print_pdf(self) -> None:
        if self.result is None:
            return
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Save calculation sheet",
            defaultextension=".pdf",
            filetypes=(("PDF document", "*.pdf"),),
            initialfile="beam-calculation-sheet.pdf",
        )
        if not path:
            return
        section = next(
            item for item in SECTIONS[self.material_var.get()]
            if item.name == self.section_var.get()
        )
        try:
            output = export_calculation_sheet(
                path,
                span_ft=float(self.span_var.get()),
                support=self.support_var.get(),  # type: ignore[arg-type]
                material=self.material_var.get(),  # type: ignore[arg-type]
                section=section,
                deflection_limit=self.deflection_var.get(),
                include_self_weight=self.self_weight_var.get(),
                point_loads=self.point_loads,
                uniform_loads=self.uniform_loads,
                result=self.result,
                recommendation=self.recommendation,
            )
            open_pdf(output)
        except (
            OSError,
            ValueError,
            tk.TclError,
            subprocess.SubprocessError,
        ) as error:
            messagebox.showerror(
                "Could not create or open the PDF",
                f"The calculation sheet could not be saved or opened at:\n{path}\n\n{error}",
                parent=self.root,
            )

    def _export_csv(self) -> None:
        if self.result is None:
            return
        if not self.inputs_valid:
            messagebox.showerror(
                "Could not export results",
                "Correct the invalid beam inputs before exporting.",
                parent=self.root,
            )
            return
        path = filedialog.asksaveasfilename(
            parent=self.root,
            title="Export beam results",
            defaultextension=".csv",
            filetypes=(("CSV files", "*.csv"),),
            initialfile="beam-results.csv",
        )
        if not path:
            return
        try:
            output = export_results_csv(path, self.result)
        except (OSError, ValueError, csv.Error) as error:
            messagebox.showerror(
                "Could not export results",
                str(error),
                parent=self.root,
            )
            return
        messagebox.showinfo(
            "Results exported",
            f"Exported beam results to:\n{output}",
            parent=self.root,
        )


def main() -> None:
    root = tk.Tk()
    BeamDesigner(root)
    root.mainloop()


if __name__ == "__main__":
    main()
