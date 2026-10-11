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


class PublishProgressDialog(QDialog):
    """Modal dialog showing the export progress, one row per layout.

    Each row has a status mark: a grey dot while waiting, an amber ellipsis
    while exporting, a green check once exported, or a red cross on failure.
    The dialog cannot be closed while an export is running.
    """

    def __init__(self, names, fmt, export_dir, parent=None):
        """Build the dialog with one pending row per layout.

        Args:
            names (list[str]): Names of the layouts that will be exported.
            fmt (str): Export format shown in the header ("PDF" or "PNG").
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

        layout = QVBoxLayout(self)

        self.header = QLabel(f"Exporting {len(names)} layout(s) as {fmt}…")
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
            mark = QLabel("·")
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
        self.btn_close = QPushButton("Close")
        self.btn_close.setEnabled(False)
        self.btn_close.clicked.connect(self.accept)
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
        self._set_mark(name, "…", COLOR_RUNNING)

    def set_done(self, name):
        """Mark a layout as exported successfully (green check)."""
        self._set_mark(name, "✓", COLOR_OK)

    def set_failed(self, name, message):
        """Mark a layout as failed (red cross), with the error as tooltip."""
        self._set_mark(name, "✗", COLOR_FAIL, message)

    def advance(self):
        """Advance the progress bar by one finished layout."""
        self.progress.setValue(self.progress.value() + 1)

    def finish(self, n_ok, n_failed):
        """Show the summary and allow the dialog to be closed.

        Args:
            n_ok (int): Number of layouts exported successfully.
            n_failed (int): Number of layouts that failed.
        """
        self._running = False
        text = f"Done: {n_ok} exported"
        if n_failed:
            text += f", {n_failed} failed (hover over ✗ for details)"
        self.header.setText(text)
        self.btn_close.setEnabled(True)

    # Don't allow closing while an export is still running
    def closeEvent(self, event):
        """Ignore close requests (window X) while an export is running."""
        if self._running:
            event.ignore()
        else:
            super().closeEvent(event)

    def reject(self):
        """Ignore Esc while an export is running; otherwise close normally."""
        if not self._running:
            super().reject()
