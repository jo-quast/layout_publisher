"""Progress dialog shown while Layout Publisher exports layouts."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

# Colours of the status marks in the progress dialog
COLOR_PENDING = "#8a97a6"  # grey: waiting
COLOR_RUNNING = "#d08a00"  # amber: currently exporting
COLOR_OK = "#2e8b57"  # green: exported
COLOR_FAIL = "#c0392b"  # red: failed

# Status marks shown in front of each layout
MARK_PENDING = "·"  # waiting
MARK_RUNNING = "…"  # currently exporting
MARK_DONE = "✓"  # exported
MARK_FAILED = "✗"  # failed
MARK_SKIPPED = "–"  # skipped because the export was stopped

# Texts of the dialog
MSG_EXPORTING = "Exporting {n_layouts} layout(s) as {fmt}…"
MSG_STOPPING = "Stopping after the current layout…"
MSG_SUMMARY = "Done: {n_ok} exported"
MSG_SUMMARY_FAILED = ", {n_failed} failed (hover over {mark} for details)"
MSG_SUMMARY_SKIPPED = ", {n_skipped} skipped"
TOOLTIP_SKIPPED = "Skipped (export stopped)"


class PublishProgressDialog(QDialog):
    """Modal dialog showing the export progress, one row per layout.

    Each row has a status mark: a grey dot while waiting, an amber ellipsis
    while exporting, a green check once exported, a red cross on failure, or
    a grey dash if the layout was skipped because the export was stopped.

    While an export is running, the Stop button, Esc and the window's close
    button (X) stop it after the current layout instead of closing the
    dialog. Once the export has finished, Stop is replaced by Close.
    """

    def __init__(self, names, fmt, export_dir, parent=None):
        """Build the dialog with one pending row per layout.

        Args:
            names (list[str]): Names of the layouts that will be exported.
            fmt (ExportFormat): Export format shown in the header.
            export_dir (str): Target folder, shown below the header.
            parent (QWidget, optional): Parent widget, usually the QGIS
                main window.
        """
        super().__init__(parent)
        self.setWindowTitle("Publishing layouts")
        self.setModal(True)
        self.setMinimumWidth(380)
        self._running = True
        self._rows = {}
        self.stop_requested = False  # set by request_stop(); checked by the export loop

        layout = QVBoxLayout(self)

        self.header = QLabel(MSG_EXPORTING.format(n_layouts=len(names), fmt=fmt.value))
        self.header.setWordWrap(True)
        layout.addWidget(self.header)

        path_label = QLabel(export_dir)
        path_label.setWordWrap(True)
        path_label.setStyleSheet(f"color: {COLOR_PENDING};")
        layout.addWidget(path_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, len(names))
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        # Scrollable list of rows, so a long list of layouts still fits on the screen
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        inner = QWidget()
        rows = QVBoxLayout(inner)
        for name in names:
            row = QHBoxLayout()
            mark = QLabel(MARK_PENDING)
            mark.setFixedWidth(20)
            mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
            mark.setStyleSheet(f"color: {COLOR_PENDING}; font-weight: bold;")
            text = QLabel(name)
            row.addWidget(mark)
            row.addWidget(text, 1)
            rows.addLayout(row)
            self._rows[name] = (mark, text)
        rows.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_stop = QPushButton("Stop")
        self.btn_stop.clicked.connect(self.request_stop)
        self.btn_stop.setAutoDefault(False)
        self.btn_close = QPushButton("Close")
        self.btn_close.setVisible(False)
        self.btn_close.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_stop)
        btn_row.addWidget(self.btn_close)
        layout.addLayout(btn_row)

    def _set_mark(self, name, symbol, color, tooltip=""):
        """Change the status mark of one row.

        Args:
            name (str): Layout name identifying the row.
            symbol (str): Character to show as the mark.
            color (str): CSS colour of the mark.
            tooltip (str, optional): Tooltip for the row, e.g. an error text.
        """
        mark, text = self._rows[name]
        mark.setText(symbol)
        mark.setStyleSheet(f"color: {color}; font-weight: bold;")
        mark.setToolTip(tooltip)
        text.setToolTip(tooltip)

    def set_running(self, name):
        """Mark a layout as currently being exported."""
        self._set_mark(name, MARK_RUNNING, COLOR_RUNNING)

    def set_done(self, name):
        """Mark a layout as exported successfully (green check)."""
        self._set_mark(name, MARK_DONE, COLOR_OK)

    def set_failed(self, name, message):
        """Mark a layout as failed (red cross), with the error as tooltip."""
        self._set_mark(name, MARK_FAILED, COLOR_FAIL, message)

    def set_skipped(self, name):
        """Mark a layout as skipped because the export was stopped (grey dash)."""
        self._set_mark(name, MARK_SKIPPED, COLOR_PENDING, TOOLTIP_SKIPPED)

    def advance(self):
        """Advance the progress bar by one finished layout."""
        self.progress.setValue(self.progress.value() + 1)

    def finish(self, n_ok, n_failed, n_skipped):
        """Show the summary, fill the progress bar and allow the dialog to be closed.

        The bar is filled even if layouts were skipped, so it shows that the
        export is over. Replaces the Stop button with Close, which becomes the
        default button (activated by Enter).

        Args:
            n_ok (int): Number of layouts exported successfully.
            n_failed (int): Number of layouts that failed.
            n_skipped (int): Number of layouts skipped because the export
                was stopped.
        """
        self._running = False
        text = MSG_SUMMARY.format(n_ok=n_ok)
        if n_failed:
            text += MSG_SUMMARY_FAILED.format(n_failed=n_failed, mark=MARK_FAILED)
        if n_skipped:
            text += MSG_SUMMARY_SKIPPED.format(n_skipped=n_skipped)
        self.header.setText(text)
        self.progress.setValue(self.progress.maximum())
        self.btn_stop.setVisible(False)
        self.btn_close.setVisible(True)
        self.btn_close.setDefault(True)

    def request_stop(self):
        """Ask the export to stop after the current layout.

        Connected to the Stop button, and called by ``reject()`` for Esc and
        the window's close button. Sets ``stop_requested``, which the export loop
        checks before each layout, and disables the button so it can't be
        clicked twice.
        """
        self.stop_requested = True
        self.header.setText(MSG_STOPPING)
        self.btn_stop.setEnabled(False)

    def reject(self):
        """Stop the export while it is running, otherwise close the dialog.

        Qt calls this when the user presses Esc, and QDialog's closeEvent calls
        it when the window's close button (X) is clicked.
        """
        if self._running:
            self.request_stop()
        else:
            super().reject()
