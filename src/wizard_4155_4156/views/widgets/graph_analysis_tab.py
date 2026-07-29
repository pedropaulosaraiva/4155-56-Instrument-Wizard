"""
views/widgets/graph_analysis_tab.py
-----------------------------------
"Analysis" sidebar tab — Curve Fit and Trace Math on the ACTIVE plot.

Passive view: model/operation options are *pushed in* by the presenter
(built from the ``models/graph`` registries), so new fit models or math
operations appear here without any view change.  All payloads use the
stable string trace ids.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from wizard_4155_4156.gui_text.general_text import (
    CommandWizardText as TXT,
)
from wizard_4155_4156.gui_text.general_text import tr_ui
from wizard_4155_4156.styles.icons import AppIcon24, app_icon
from wizard_4155_4156.styles.stylesheets import (
    graph_analysis_message_stylesheet,
    graph_results_list_stylesheet,
    qscv_reference_note_stylesheet,
    runs_primary_button_stylesheet,
    runs_secondary_button_stylesheet,
    table_selector_label_stylesheet,
    unit_card_combo_stylesheet,
)
from wizard_4155_4156.styles.theme import PALETTE as P
from wizard_4155_4156.views.widgets.config_sections import (
    SectionFrame,
    SegmentedGroup,
    form_row,
    spinbox,
)

_LABEL_WIDTH = 90
_TRACE_ID_ROLE = Qt.ItemDataRole.UserRole


def _data_combo() -> QComboBox:
    box = QComboBox()
    box.setStyleSheet(unit_card_combo_stylesheet())
    # Shrinkable minimum (not longest-item) + tooltips for clipped text.
    box.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    box.setMinimumContentsLength(8)
    box.currentTextChanged.connect(box.setToolTip)
    return box


def _fill_combo(
    box: QComboBox, options: list[tuple[str, str]], keep_current: bool = True
) -> None:
    """Rebuild a (data, label) combo, preserving the selection if asked."""
    current = box.currentData() if keep_current else None
    box.blockSignals(True)
    box.clear()
    for data, label in options:
        box.addItem(label, data)
        box.setItemData(box.count() - 1, label, Qt.ItemDataRole.ToolTipRole)
    box.setToolTip(box.currentText())
    if current is not None:
        idx = box.findData(current)
        if idx >= 0:
            box.setCurrentIndex(idx)
    box.blockSignals(False)


class _RemovableList(QWidget):
    """QListWidget + a remove button acting on the selected entry."""

    remove_requested = Signal(str)  # trace id

    def __init__(self, title: str, copyable: bool = False) -> None:
        super().__init__()
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)

        header = QLabel(title)
        header.setStyleSheet(table_selector_label_stylesheet())
        v.addWidget(header)

        self._list = QListWidget()
        self._list.setStyleSheet(graph_results_list_stylesheet())
        self._list.setWordWrap(True)  # wrap equations instead of clipping
        self._list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._list.setMinimumHeight(90)
        self._list.setMaximumHeight(132)
        self._list.itemSelectionChanged.connect(self._update_buttons_enabled)
        v.addWidget(self._list)

        buttons = QWidget()
        h = QHBoxLayout(buttons)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)

        self._copy_btn: QPushButton | None = None
        if copyable:
            self._copy_btn = QPushButton(tr_ui(TXT.GRAPH_BTN_COPY_FIT))
            self._copy_btn.setStyleSheet(runs_primary_button_stylesheet())
            self._copy_btn.setToolTip(tr_ui(TXT.GRAPH_TT_COPY_SELECTED))
            self._copy_btn.setEnabled(False)  # acts on the selected entry
            self._copy_btn.clicked.connect(self._on_copy)
            h.addWidget(self._copy_btn)
        h.addStretch(1)

        self._remove_btn = QPushButton()
        self._remove_btn.setIcon(app_icon(AppIcon24.X))
        self._remove_btn.setIconSize(QSize(12, 12))
        self._remove_btn.setStyleSheet(runs_secondary_button_stylesheet())
        self._remove_btn.setFixedWidth(34)
        self._remove_btn.setToolTip(tr_ui(TXT.GRAPH_TT_REMOVE_SELECTED))
        self._remove_btn.setEnabled(False)  # acts on the selected entry
        self._remove_btn.clicked.connect(self._on_remove)
        h.addWidget(self._remove_btn)
        v.addWidget(buttons)

    def display(self, entries: list[tuple[str, str]]) -> None:
        """(trace id, display text) rows."""
        self._list.clear()
        for trace_id, text in entries:
            item = QListWidgetItem(text)
            item.setData(_TRACE_ID_ROLE, trace_id)
            item.setToolTip(text)
            self._list.addItem(item)
        self._update_buttons_enabled()

    def _update_buttons_enabled(self) -> None:
        has_selection = self._list.currentItem() is not None
        self._remove_btn.setEnabled(has_selection)
        if self._copy_btn is not None:
            self._copy_btn.setEnabled(has_selection)

    def _on_remove(self) -> None:
        item = self._list.currentItem()
        if item is not None:
            self.remove_requested.emit(item.data(_TRACE_ID_ROLE))

    def _on_copy(self) -> None:
        item = self._list.currentItem()
        if item is not None:
            QApplication.clipboard().setText(item.text())


class GraphAnalysisTab(QWidget):
    """Curve Fit + Trace Math sections for the active plot."""

    fit_requested = Signal(str, str, int, bool)  # (trace, model, deg, roi)
    fit_removed = Signal(str)  # fit trace id
    math_requested = Signal(str, str, str)  # (op id, src a, src b or "")
    computed_trace_removed = Signal(str)
    math_category_changed = Signal(str)  # category id ("unary"…)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._category_labels: dict[str, str] = {}  # label → category id

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(14)

        self._message = QLabel("")
        self._message.setStyleSheet(graph_analysis_message_stylesheet())
        self._message.setWordWrap(True)
        root.addWidget(self._message)

        self._fit_section = self._build_fit_section()
        self._math_section = self._build_math_section()
        root.addWidget(self._fit_section)
        root.addWidget(self._math_section)
        root.addStretch(1)

    # ── Build helpers ───────────────────────────────────────────────────────

    def _build_fit_section(self) -> SectionFrame:
        section = SectionFrame(
            tr_ui(TXT.GRAPH_SEC_CURVE_FIT),
            flat=True,
            accent=P.GRAPH_TAB_ANALYSIS,
        )
        body = section.body()

        self._fit_trace = _data_combo()
        body.addWidget(
            form_row(
                tr_ui(TXT.GRAPH_LBL_FIT_TRACE), self._fit_trace, _LABEL_WIDTH
            )
        )

        self._fit_model = _data_combo()
        self._fit_model.currentIndexChanged.connect(self._on_fit_model_changed)
        body.addWidget(
            form_row(
                tr_ui(TXT.GRAPH_LBL_FIT_MODEL), self._fit_model, _LABEL_WIDTH
            )
        )

        self._fit_degree = spinbox(2, 6, 2)
        self._fit_degree_row = form_row(
            tr_ui(TXT.GRAPH_LBL_FIT_DEGREE),
            self._fit_degree,
            _LABEL_WIDTH,
        )
        body.addWidget(self._fit_degree_row)

        buttons = QWidget()
        h = QHBoxLayout(buttons)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)
        self._fit_roi_btn = QPushButton(tr_ui(TXT.GRAPH_BTN_FIT_ROI))
        self._fit_roi_btn.setStyleSheet(runs_primary_button_stylesheet())
        self._fit_roi_btn.clicked.connect(lambda: self._emit_fit(True))
        self._fit_full_btn = QPushButton(tr_ui(TXT.GRAPH_BTN_FIT_FULL))
        self._fit_full_btn.setStyleSheet(runs_secondary_button_stylesheet())
        self._fit_full_btn.clicked.connect(lambda: self._emit_fit(False))
        h.addWidget(self._fit_roi_btn)
        h.addWidget(self._fit_full_btn)
        body.addWidget(buttons)

        self._fits_list = _RemovableList(
            tr_ui(TXT.GRAPH_FITS_TITLE), copyable=True
        )
        self._fits_list.remove_requested.connect(self.fit_removed)
        body.addWidget(self._fits_list)
        return section

    def _build_math_section(self) -> SectionFrame:
        section = SectionFrame(
            tr_ui(TXT.GRAPH_SEC_TRACE_MATH),
            flat=True,
            accent=P.GRAPH_TAB_ANALYSIS,
        )
        body = section.body()

        # Placeholder segmented group; rebuilt by set_operations().
        self._category_holder = QVBoxLayout()
        body.addLayout(self._category_holder)
        self._category_group: SegmentedGroup | None = None

        self._op_combo = _data_combo()
        body.addWidget(
            form_row(
                tr_ui(TXT.GRAPH_LBL_OPERATION), self._op_combo, _LABEL_WIDTH
            )
        )

        self._src_a = _data_combo()
        body.addWidget(
            form_row(tr_ui(TXT.GRAPH_LBL_SOURCE_A), self._src_a, _LABEL_WIDTH)
        )
        self._src_b = _data_combo()
        self._src_b_row = form_row(
            tr_ui(TXT.GRAPH_LBL_SOURCE_B), self._src_b, _LABEL_WIDTH
        )
        body.addWidget(self._src_b_row)

        self._add_btn = QPushButton(tr_ui(TXT.GRAPH_BTN_ADD_COMPUTED))
        self._add_btn.setStyleSheet(runs_primary_button_stylesheet())
        self._add_btn.clicked.connect(self._emit_math)
        body.addWidget(self._add_btn)

        self._computed_list = _RemovableList(tr_ui(TXT.GRAPH_COMPUTED_TITLE))
        self._computed_list.remove_requested.connect(
            self.computed_trace_removed
        )
        body.addWidget(self._computed_list)

        self._math_footnote = QLabel(tr_ui(TXT.GRAPH_TRACE_MATH_FOOTNOTE))
        self._math_footnote.setStyleSheet(qscv_reference_note_stylesheet())
        self._math_footnote.setWordWrap(True)
        body.addWidget(self._math_footnote)
        return section

    # ── Public display API ──────────────────────────────────────────────────

    def set_fit_models(
        self, models: list[tuple[str, str, bool, int, int]]
    ) -> None:
        """(model id, label, has_degree, min degree, max degree) rows."""
        self._fit_degree_ranges = {
            model_id: (has_degree, lo, hi)
            for model_id, _label, has_degree, lo, hi in models
        }
        _fill_combo(
            self._fit_model,
            [(model_id, label) for model_id, label, *_ in models],
            keep_current=False,
        )
        self._on_fit_model_changed()

    def set_operations(
        self,
        categories: list[tuple[str, str]],
        by_category: dict[str, list[tuple[str, str]]],
        binary_categories: set[str],
    ) -> None:
        """(category id, label) list + per-category (op id, label) lists."""
        self._ops_by_category = by_category
        self._binary_categories = binary_categories
        self._category_labels = {
            label: category_id for category_id, label in categories
        }
        if self._category_group is not None:
            self._category_group.deleteLater()
        self._category_group = SegmentedGroup(
            [label for _cid, label in categories], compact=True
        )
        self._category_group.selection_changed.connect(
            self._on_category_changed
        )
        self._category_holder.addWidget(self._category_group)
        if categories:
            self._on_category_changed(categories[0][1])

    def display_trace_options(self, options: list[tuple[str, str]]) -> None:
        """Selectable source traces for fitting and math."""
        for box in (self._fit_trace, self._src_a, self._src_b):
            _fill_combo(box, options)

    def display_fits(self, entries: list[tuple[str, str]]) -> None:
        self._fits_list.display(entries)

    def display_computed(self, entries: list[tuple[str, str]]) -> None:
        self._computed_list.display(entries)

    def display_analysis_message(self, text: str) -> None:
        self._message.setText(text)
        self._message.setVisible(bool(text))

    def set_analysis_enabled(self, enabled: bool) -> None:
        self._fit_section.setEnabled(enabled)
        self._math_section.setEnabled(enabled)

    def set_fit_roi_enabled(self, enabled: bool) -> None:
        """ROI fitting is only offered while the ROI itself is active."""
        self._fit_roi_btn.setEnabled(enabled)
        self._fit_roi_btn.setToolTip(
            "" if enabled else tr_ui(TXT.GRAPH_FIT_NEED_ROI)
        )

    # ── Internals ───────────────────────────────────────────────────────────

    def _current_category(self) -> str:
        if self._category_group is None:
            return ""
        label = self._category_group.current_value()
        return self._category_labels.get(label, "")

    def _on_category_changed(self, label: str) -> None:
        category = self._category_labels.get(label, "")
        _fill_combo(
            self._op_combo,
            self._ops_by_category.get(category, []),
            keep_current=False,
        )
        self._src_b_row.setVisible(category in self._binary_categories)
        self.math_category_changed.emit(category)

    def _on_fit_model_changed(self) -> None:
        model_id = self._fit_model.currentData()
        ranges = getattr(self, "_fit_degree_ranges", {})
        has_degree, lo, hi = ranges.get(model_id, (False, 1, 1))
        self._fit_degree_row.setVisible(has_degree)
        if has_degree:
            self._fit_degree.setRange(lo, hi)

    def _emit_fit(self, over_roi: bool) -> None:
        trace_id = self._fit_trace.currentData()
        model_id = self._fit_model.currentData()
        if trace_id is None or model_id is None:
            return
        self.fit_requested.emit(
            trace_id, model_id, self._fit_degree.value(), over_roi
        )

    def _emit_math(self) -> None:
        op_id = self._op_combo.currentData()
        src_a = self._src_a.currentData()
        if op_id is None or src_a is None:
            return
        needs_b = self._current_category() in self._binary_categories
        src_b = self._src_b.currentData() if needs_b else None
        if needs_b and src_b is None:
            return
        self.math_requested.emit(op_id, src_a, src_b or "")
