"""Dock panel for Layout Publisher.

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

from qgis.core import Qgis, QgsLayoutExporter, QgsLayoutItemMap, QgsProject, QgsSettings
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from qgis.utils import iface

from .progress_dialog import PublishProgressDialog

# Keys under which the export folder and format are stored in QgsSettings
SETTINGS_DIR = "LayoutPublisher/export_dir"
SETTINGS_FORMAT = "LayoutPublisher/export_format"

LEVEL_CRITICAL = Qgis.MessageLevel.Critical


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
        layout.addWidget(QLabel("Select layouts (double-click to open layout designer):"))

        # Multi-selection list; shared by the Update and Publish actions
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.itemDoubleClicked.connect(self.open_layout)
        self.list_widget.setToolTip("Double-click a layout to open it in the layout designer")
        layout.addWidget(self.list_widget)

        sel_row = QHBoxLayout()
        btn_all = QPushButton("All")
        btn_none = QPushButton("None")
        btn_all.clicked.connect(self.list_widget.selectAll)
        btn_none.clicked.connect(self.list_widget.clearSelection)
        sel_row.addWidget(btn_all)
        sel_row.addWidget(btn_none)

        self.btn_rename = QPushButton("Rename…")
        self.btn_rename.setToolTip("Rename the selected layout (select exactly one)")
        self.btn_rename.setEnabled(False)  # only enabled when exactly one layout is selected
        self.btn_rename.clicked.connect(self.rename_layout)
        self.list_widget.itemSelectionChanged.connect(self.update_rename_button)
        sel_row.addStretch()
        sel_row.addWidget(self.btn_rename)
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
        for sig in (
            manager.layoutAdded,
            manager.layoutRemoved,
            manager.layoutRenamed,
            project.readProject,
            project.cleared,
        ):
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
        for lyt in sorted(manager.layouts(), key=lambda lay: lay.name().lower()):
            item = QListWidgetItem(lyt.name())
            self.list_widget.addItem(item)
            if lyt.name() in previously_selected:
                item.setSelected(True)

    def open_layout(self, list_item):
        """Open the layout of ``list_item`` in the layout designer.

        Connected to a double-click in the layout list. If the layout is
        already open, QGIS brings its designer window to the front instead of
        opening a second one.

        Args:
            list_item (QListWidgetItem): The item that was double-clicked.
        """
        name = list_item.text()
        lyt = QgsProject.instance().layoutManager().layoutByName(name)
        if lyt is None:
            self.show_error(f"Layout '{name}' not found.")
            return
        iface.openLayoutDesigner(lyt)

    def update_rename_button(self):
        """Enable the Rename button only when exactly one layout is selected."""
        self.btn_rename.setEnabled(len(self.list_widget.selectedItems()) == 1)

    def select_layout(self, name):
        """Select and scroll to the list entry with the given layout name.

        Args:
            name (str): Name of the layout to select. Does nothing if no
                entry has this name.
        """
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.text() == name:
                self.list_widget.setCurrentItem(item)
                self.list_widget.scrollToItem(item)
                break

    def rename_layout(self):
        """Rename the selected layout using a small input dialog.

        Exactly one layout must be selected. The new name must not be empty
        or already used by another layout, because QGIS requires unique
        layout names.
        """
        selected = self.list_widget.selectedItems()
        if len(selected) != 1:
            self.status.setText("Please select exactly one layout to rename.")
            return

        old_name = selected[0].text()
        manager = QgsProject.instance().layoutManager()
        lyt = manager.layoutByName(old_name)
        if lyt is None:
            self.show_error(f"Layout '{old_name}' not found.")
            return

        new_name, ok = QInputDialog.getText(self, "Rename layout", "New name:", text=old_name)
        if not ok:
            return  # cancelled
        new_name = new_name.strip()
        if new_name == old_name:
            return  # unchanged
        if not new_name:
            self.show_error("The layout name cannot be empty.")
            return
        if manager.layoutByName(new_name) is not None:
            self.show_error(f"A layout named '{new_name}' already exists.")
            return

        lyt.setName(new_name)
        # Make QGIS ask to save the project when closing
        QgsProject.instance().setDirty(True)
        # The manager's layoutRenamed signal has already refreshed the list,
        # but the old name is no longer selected, so select the new one.
        self.select_layout(new_name)
        self.status.setText(f"Renamed '{old_name}' to '{new_name}'.")

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
