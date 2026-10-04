"""Dock panel and progress dialog for Layout Publisher.
 
The panel lists all print layouts of the current QGIS project and offers two
actions on the selected layouts:
 
* **Update** - refresh every map item (and optionally the whole layout).
* **Publish** - export the layouts as PDF or PNG into a default export
  location, showing per-layout progress in a small dialog.
 
The export folder and format are stored with ``QgsSettings`` so they persist
across sessions and projects.
"""

import os
import re

from qgis.core import (
    Qgis, QgsProject, QgsLayoutItemMap, QgsLayoutExporter, QgsSettings
)
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QListWidget,
    QListWidgetItem, QPushButton, QLabel, QAbstractItemView, QCheckBox,
    QApplication, QGroupBox, QComboBox, QLineEdit, QFileDialog, QToolButton,
    QDialog, QProgressBar, QScrollArea
)
from qgis.utils import iface

# Keys under which the export folder and format are stored in QgsSettings
SETTINGS_DIR = "LayoutPublisher/export_dir"
SETTINGS_FORMAT = "LayoutPublisher/export_format"

LEVEL_CRITICAL = Qgis.MessageLevel.Critical

# Colours of the status marks in the progress dialog
COLOR_PENDING = "#8a97a6"  # grey: waiting
COLOR_RUNNING = "#d08a00"  # amber: currently exporting
COLOR_OK = "#2e8b57"       # green: exported
COLOR_FAIL = "#c0392b"     # red: failed


class StatusLabel(QWidget):
    """Status text with a small x button. Hidden whenever the text is empty."""

    def __init__(self, parent=None):
        """Build the label and close button; the widget starts hidden.
 
        Args:
            parent (QWidget, optional): Parent widget.
        """
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel("")
        self.label.setWordWrap(True)
        row.addWidget(self.label, 1)

        self.btn_close = QToolButton()
        self.btn_close.setText("✕")
        self.btn_close.setAutoRaise(True)
        self.btn_close.setToolTip("Clear message")
        self.btn_close.clicked.connect(self.clear)
        row.addWidget(self.btn_close, 0, Qt.AlignmentFlag.AlignTop)

        self.hide()

    def setText(self, text):
        """Show ``text``, or hide the whole widget if it is empty.
 
        Args:
            text (str): The message to display.
        """
        self.label.setText(text)
        self.setVisible(bool(text))

    def clear(self):
        """Clear the message and hide the widget."""
        self.setText("")


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
        """Advance the progress bar by one finished layout."""
        self._set_mark(name, "✗", COLOR_FAIL, message)

    def advance(self):
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


class LayoutPublisherDock(QDockWidget):
    """Dockable panel to update and publish the project's print layouts.
 
    The layout list stays in sync with the project: it is refreshed whenever
    layouts are added, removed or renamed, or another project is opened.
    """

    def __init__(self, parent=None):
        """Build the panel, connect project signals and fill the layout list.
 
        Args:
            parent (QWidget, optional): Parent widget, usually the QGIS
                main window.
        """
        super().__init__("Layout Publisher", parent)
        self.setObjectName("LayoutPublisherDock")  # lets QGIS remember its position
        self.settings = QgsSettings()
        self._publish_dialog = None  # reference so the dialog isn't garbage-collected

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.addWidget(QLabel("Select layouts:"))

        # Multi-selection list; shared by the Update and Publish actions
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        layout.addWidget(self.list_widget)

        sel_row = QHBoxLayout()
        btn_all = QPushButton("All")
        btn_none = QPushButton("None")
        btn_all.clicked.connect(self.list_widget.selectAll)
        btn_none.clicked.connect(self.list_widget.clearSelection)
        sel_row.addWidget(btn_all)
        sel_row.addWidget(btn_none)
        sel_row.addStretch()
        layout.addLayout(sel_row)

        # --- Update group ---
        update_box = QGroupBox("Update")
        update_layout = QVBoxLayout(update_box)
        self.chk_layout_refresh = QCheckBox("Also update legends, labels and other items")
        self.chk_layout_refresh.setToolTip(
            "After refreshing the maps, also refresh the rest of the layouts: "
            "legends, scale bars, labels with dynamic text and attribute tables."
        )
        self.chk_layout_refresh.setChecked(True)
        update_layout.addWidget(self.chk_layout_refresh)
        btn_update = QPushButton("Update maps")
        btn_update.clicked.connect(self.update_maps)
        update_layout.addWidget(btn_update)
        layout.addWidget(update_box)

        # --- Publish group ---
        publish_box = QGroupBox("Publish")
        publish_layout = QVBoxLayout(publish_box)

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        self.format_combo.addItems(["PDF", "PNG"])
        # Restore the last used format, falling back to PDF
        saved_fmt = self.settings.value(SETTINGS_FORMAT, "PDF")
        idx = self.format_combo.findText(str(saved_fmt))
        self.format_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.format_combo.currentTextChanged.connect(
            lambda t: self.settings.setValue(SETTINGS_FORMAT, t)
        )
        fmt_row.addWidget(self.format_combo, 1)
        publish_layout.addLayout(fmt_row)

        publish_layout.addWidget(QLabel("Export location:"))
        loc_row = QHBoxLayout()
        self.dir_edit = QLineEdit()
        self.dir_edit.setReadOnly(True)  # changed only via the folder dialog
        self.dir_edit.setPlaceholderText("Not set")
        loc_row.addWidget(self.dir_edit, 1)
        self.btn_dir = QPushButton("Set…")
        self.btn_dir.clicked.connect(self.choose_export_dir)
        loc_row.addWidget(self.btn_dir)
        publish_layout.addLayout(loc_row)

        btn_publish = QPushButton("Publish")
        btn_publish.clicked.connect(self.publish_layouts)
        publish_layout.addWidget(btn_publish)
        layout.addWidget(publish_box)

        self.status = StatusLabel()
        layout.addWidget(self.status)

        self.setWidget(body)
        self.refresh_dir_display()

        project = QgsProject.instance()
        manager = project.layoutManager()
        manager.layoutAdded.connect(self.populate)
        manager.layoutRemoved.connect(self.populate)
        manager.layoutRenamed.connect(self.populate)
        project.readProject.connect(self.populate)
        project.cleared.connect(self.populate)

        self.populate()

    def disconnect_signals(self):
        """Disconnect the project signals that refresh the layout list.
 
        Called by the plugin before the panel is deleted on unload.
        """
        project = QgsProject.instance()
        manager = project.layoutManager()
        for sig in (manager.layoutAdded, manager.layoutRemoved, manager.layoutRenamed,
                    project.readProject, project.cleared):
            try:
                sig.disconnect(self.populate)
            except (TypeError, RuntimeError):
                pass

    # ---------- list handling ----------

    def populate(self, *args):
        """Fill the list, keeping the current selection where possible.
        
        Connected to several project signals, which pass different
        arguments, hence ``*args`` (ignored).
        """
        previously_selected = {i.text() for i in self.list_widget.selectedItems()}
        self.list_widget.clear()
        manager = QgsProject.instance().layoutManager()
        for lyt in sorted(manager.layouts(), key=lambda l: l.name().lower()):
            item = QListWidgetItem(lyt.name())
            self.list_widget.addItem(item)
            if lyt.name() in previously_selected:
                item.setSelected(True)

    # ---------- export location ----------

    def export_dir(self):
        """Return the saved export folder, or an empty string if not set."""
        return str(self.settings.value(SETTINGS_DIR, "") or "")

    def refresh_dir_display(self):
        """Show the saved export folder and label the button "Set…"/"Change…"."""
        path = self.export_dir()
        self.dir_edit.setText(path)
        self.dir_edit.setToolTip(path)
        self.btn_dir.setText("Change…" if path else "Set…")

    def choose_export_dir(self):
        """Let the user pick the export folder and save it in the settings."""
        start = self.export_dir() or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "Select export location", start)
        if path:
            self.settings.setValue(SETTINGS_DIR, path)
            self.refresh_dir_display()
            self.status.setText("")

    # ---------- messages ----------

    def show_error(self, text):
        """Show an error in the panel's status line and the QGIS message bar.
 
        Args:
            text (str): The error message.
        """
        self.status.setText(text)
        iface.messageBar().pushMessage("Layout Publisher", text, level=LEVEL_CRITICAL, duration=6)

    # ---------- actions ----------

    def update_maps(self):
        """Refresh all map items in the selected layouts.
 
        Optionally refreshes each whole layout as well (labels, legends,
        etc.), depending on the checkbox. A summary, including any errors,
        is shown in the status line.
        """
        selected = self.list_widget.selectedItems()
        if not selected:
            self.status.setText("Please select at least one layout.")
            return

        manager = QgsProject.instance().layoutManager()
        n_layouts = 0
        n_maps = 0
        errors = []

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            for list_item in selected:
                name = list_item.text()
                lyt = manager.layoutByName(name)
                if lyt is None:
                    errors.append(f"'{name}' not found")
                    continue
                try:
                    for item in lyt.items():
                        if isinstance(item, QgsLayoutItemMap):
                            item.refresh()
                            n_maps += 1
                    if self.chk_layout_refresh.isChecked():
                        lyt.refresh()
                    n_layouts += 1
                except Exception as e:
                    # Report the failure but keep going with the other layouts
                    errors.append(f"'{name}': {e}")
                QApplication.processEvents()
        finally:
            # Always restore the cursor, even if something unexpected fails
            QApplication.restoreOverrideCursor()

        msg = f"Updated {n_maps} map(s) in {n_layouts} layout(s)."
        if errors:
            msg += "\nErrors: " + "; ".join(errors)
        self.status.setText(msg)

    def publish_layouts(self):
        """Export the selected layouts to the export folder as PDF or PNG.
 
        Shows an error if no export folder is set (or it no longer exists)
        and nothing is exported. Otherwise a progress dialog is opened and
        each layout is exported as ``<layout name>.<pdf|png>``; existing
        files with the same name are overwritten. A summary, including any
        errors, is shown in the status line afterwards.
        """
        export_dir = self.export_dir()
        if not export_dir:
            self.show_error("Please set an export location.")
            return
        if not os.path.isdir(export_dir):
            self.show_error(f"Export location does not exist: {export_dir}")
            return

        selected = self.list_widget.selectedItems()
        if not selected:
            self.status.setText("Please select at least one layout.")
            return

        fmt = self.format_combo.currentText()
        names = [i.text() for i in selected]
        manager = QgsProject.instance().layoutManager()
        n_ok = 0
        errors = []

        dialog = PublishProgressDialog(names, fmt, export_dir, iface.mainWindow())
        self._publish_dialog = dialog  # keep a reference
        dialog.show()
        # Each export blocks the main thread, so let Qt repaint the dialog
        # between layouts to keep the marks and progress bar up to date.
        QApplication.processEvents()

        for name in names:
            dialog.set_running(name)
            QApplication.processEvents()

            lyt = manager.layoutByName(name)
            if lyt is None:
                errors.append(f"'{name}' not found")
                dialog.set_failed(name, "Layout not found")
            else:
                # Replace characters that are not allowed in file names
                safe_name = re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "layout"
                path = os.path.join(export_dir, f"{safe_name}.{fmt.lower()}")
                try:
                    exporter = QgsLayoutExporter(lyt)
                    if fmt == "PDF":
                        result = exporter.exportToPdf(path, QgsLayoutExporter.PdfExportSettings())
                    else:
                        result = exporter.exportToImage(
                            path, QgsLayoutExporter.ImageExportSettings()
                        )
                    if result == QgsLayoutExporter.ExportResult.Success:
                        n_ok += 1
                        dialog.set_done(name)
                    else:
                        errors.append(f"'{name}': export failed")
                        dialog.set_failed(name, "Export failed")
                except Exception as e:
                    # Report the failure but keep going with the other layouts
                    errors.append(f"'{name}': {e}")
                    dialog.set_failed(name, str(e))

            dialog.advance()
            QApplication.processEvents()

        dialog.finish(n_ok, len(errors))

        msg = f"Published {n_ok} layout(s) as {fmt} to {export_dir}."
        if errors:
            msg += "\nErrors: " + "; ".join(errors)
        self.status.setText(msg)
