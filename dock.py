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

SETTINGS_DIR = "LayoutPublisher/export_dir"
SETTINGS_FORMAT = "LayoutPublisher/export_format"
# Keys used before the plugin was renamed (migrated on first start)
OLD_SETTINGS_DIR = "UpdateLayoutMaps/export_dir"
OLD_SETTINGS_FORMAT = "UpdateLayoutMaps/export_format"

try:
    LEVEL_CRITICAL = Qgis.MessageLevel.Critical
except AttributeError:  # older QGIS
    LEVEL_CRITICAL = Qgis.Critical

COLOR_PENDING = "#8a97a6"
COLOR_RUNNING = "#d08a00"
COLOR_OK = "#2e8b57"
COLOR_FAIL = "#c0392b"


class StatusLabel(QWidget):
    """Status text with a small x button. Hidden whenever the text is empty."""

    def __init__(self, parent=None):
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
        self.label.setText(text)
        self.setVisible(bool(text))

    def clear(self):
        self.setText("")


class PublishProgressDialog(QDialog):
    """Shows one row per layout; a green check appears once it is exported."""

    def __init__(self, names, fmt, export_dir, parent=None):
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
        mark, text = self._rows[name]
        mark.setText(symbol)
        mark.setStyleSheet(f"color: {color}; font-weight: bold;")
        mark.setToolTip(tooltip)
        text.setToolTip(tooltip)

    def set_running(self, name):
        self._set_mark(name, "…", COLOR_RUNNING)

    def set_done(self, name):
        self._set_mark(name, "✓", COLOR_OK)

    def set_failed(self, name, message):
        self._set_mark(name, "✗", COLOR_FAIL, message)

    def advance(self):
        self.progress.setValue(self.progress.value() + 1)

    def finish(self, n_ok, n_failed):
        self._running = False
        text = f"Done: {n_ok} exported"
        if n_failed:
            text += f", {n_failed} failed (hover over ✗ for details)"
        self.header.setText(text)
        self.btn_close.setEnabled(True)

    # Don't allow closing while an export is still running
    def closeEvent(self, event):
        if self._running:
            event.ignore()
        else:
            super().closeEvent(event)

    def reject(self):
        if not self._running:
            super().reject()


class LayoutPublisherDock(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Layout Publisher", parent)
        self.setObjectName("LayoutPublisherDock")  # lets QGIS remember its position
        self.settings = QgsSettings()
        self.migrate_old_settings()
        self._publish_dialog = None

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.addWidget(QLabel("Select layouts:"))

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
        self.chk_layout_refresh = QCheckBox("Also refresh whole layout")
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
        self.dir_edit.setReadOnly(True)
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

    def migrate_old_settings(self):
        for old, new in ((OLD_SETTINGS_DIR, SETTINGS_DIR), (OLD_SETTINGS_FORMAT, SETTINGS_FORMAT)):
            if not self.settings.contains(new) and self.settings.contains(old):
                self.settings.setValue(new, self.settings.value(old))

    def disconnect_signals(self):
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
        """Fill the list, keeping the current selection where possible."""
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
        return str(self.settings.value(SETTINGS_DIR, "") or "")

    def refresh_dir_display(self):
        path = self.export_dir()
        self.dir_edit.setText(path)
        self.dir_edit.setToolTip(path)
        self.btn_dir.setText("Change…" if path else "Set…")

    def choose_export_dir(self):
        start = self.export_dir() or os.path.expanduser("~")
        path = QFileDialog.getExistingDirectory(self, "Select export location", start)
        if path:
            self.settings.setValue(SETTINGS_DIR, path)
            self.refresh_dir_display()
            self.status.setText("")

    # ---------- messages ----------

    def show_error(self, text):
        self.status.setText(text)
        iface.messageBar().pushMessage("Layout Publisher", text, level=LEVEL_CRITICAL, duration=6)

    # ---------- actions ----------

    def update_maps(self):
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
                    errors.append(f"'{name}': {e}")
                QApplication.processEvents()
        finally:
            QApplication.restoreOverrideCursor()

        msg = f"Updated {n_maps} map(s) in {n_layouts} layout(s)."
        if errors:
            msg += "\nErrors: " + "; ".join(errors)
        self.status.setText(msg)

    def publish_layouts(self):
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
        QApplication.processEvents()

        for name in names:
            dialog.set_running(name)
            QApplication.processEvents()

            lyt = manager.layoutByName(name)
            if lyt is None:
                errors.append(f"'{name}' not found")
                dialog.set_failed(name, "Layout not found")
            else:
                safe_name = re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "layout"
                path = os.path.join(export_dir, f"{safe_name}.{fmt.lower()}")
                try:
                    exporter = QgsLayoutExporter(lyt)
                    if fmt == "PDF":
                        result = exporter.exportToPdf(path, QgsLayoutExporter.PdfExportSettings())
                    else:
                        result = exporter.exportToImage(path, QgsLayoutExporter.ImageExportSettings())
                    if result == QgsLayoutExporter.ExportResult.Success:
                        n_ok += 1
                        dialog.set_done(name)
                    else:
                        errors.append(f"'{name}': export failed")
                        dialog.set_failed(name, "Export failed")
                except Exception as e:
                    errors.append(f"'{name}': {e}")
                    dialog.set_failed(name, str(e))

            dialog.advance()
            QApplication.processEvents()

        dialog.finish(n_ok, len(errors))

        msg = f"Published {n_ok} layout(s) as {fmt} to {export_dir}."
        if errors:
            msg += "\nErrors: " + "; ".join(errors)
        self.status.setText(msg)
