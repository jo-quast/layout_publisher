"""The Layout Publisher panel, docked in the QGIS main window.

The panel lists all print layouts of the current QGIS project, has a button above the
list to create a new layout, and offers two actions on the selected layouts:

* **Refresh** - refresh the map items, the other items, or both.
* **Publish** - export the layouts as PDF, PNG or SVG into a default export
  location, showing per-layout progress in a small dialog.

The export folder and format are stored with ``QgsSettings`` so they persist
across sessions and projects.
"""

import os

from qgis.core import Qgis, QgsLayoutExporter, QgsProject, QgsSettings
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDockWidget,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
from qgis.utils import iface

from .export_format import ExportFormat
from .icons import new_layout_icon
from .layout_list import LayoutList
from .new_layout_dialog import NewLayoutDialog
from .progress_dialog import PublishProgressDialog
from .publisher import create_layout, export_layout, export_path, refresh_layout
from .status_label import StatusLabel

# Keys under which the export folder and format are stored in QgsSettings
SETTINGS_DIR = "LayoutPublisher/export_dir"
SETTINGS_FORMAT = "LayoutPublisher/export_format"

LEVEL_CRITICAL = Qgis.MessageLevel.Critical

# Status line texts; the {placeholders} are filled in with str.format()
MSG_SELECT_LAYOUT = "Please select at least one layout."
MSG_CREATED = "Created layout '{name}'."
# Added on its own line below a refresh or publish summary if any layout failed
MSG_ERRORS = "Errors: {errors}"
# Entry in that error list for a layout that no longer exists
ERROR_NOT_FOUND = "'{name}' not found"

# Summary in the status line after refreshing, e.g. "Refreshed 1 map(s) and 2 other
# item(s) in 1 layout(s)."; {items} is the parts below joined by the separator
MSG_REFRESHED = "Refreshed {items} in {n_layouts} layout(s)."
MSG_REFRESHED_MAPS = "{n_maps} map(s)"
MSG_REFRESHED_OTHERS = "{n_others} other item(s)"
MSG_REFRESHED_SEPARATOR = " and "

# Summary in the status line after publishing; each part goes on its own line
MSG_PUBLISHED = "Published {n_ok} layout(s) as {fmt} to {export_dir}."
MSG_PUBLISH_SKIPPED = "{n_skipped} layout(s) skipped."
# A layout whose export failed: its entry in the error list, and its tooltips in the dialog
ERROR_EXPORT_FAILED = "'{name}': export failed"
TOOLTIP_NOT_FOUND = "Layout not found"
TOOLTIP_EXPORT_FAILED = "Export failed"


def make_group(title):
    """Create a group box with a vertical layout.

    Args:
        title (str): Title shown on the group box.

    Returns:
        tuple[QGroupBox, QVBoxLayout]: The group box and its layout, to add
        widgets to.
    """
    box = QGroupBox(title)
    return box, QVBoxLayout(box)


class LayoutPublisherPanel(QDockWidget):
    """Dockable panel to refresh and publish the project's print layouts.

    The panel puts together the toolbar row, the layout list (``LayoutList``), the Refresh
    and Publish groups and the status line, and carries out the actions on the layouts.
    """

    def __init__(self, parent=None):
        """Build the panel; the layout list connects to the project and fills itself.

        Args:
            parent (QWidget, optional): Parent widget, usually the QGIS
                main window.
        """
        super().__init__("Layout Publisher", parent)
        # QGIS saves the panel's position and visibility under this name. Keep it unchanged
        # (it dates from when the class was called LayoutPublisherDock), or users' panels
        # would go back to the default position after an update.
        self.setObjectName("LayoutPublisherDock")
        self.settings = QgsSettings()
        self._publish_dialog = None  # reference so the dialog isn't garbage-collected

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.addLayout(self._build_toolbar_row())
        # The list must be built before the selection row, which connects to it
        self.layout_list = LayoutList()
        self.layout_list.list_widget.itemDoubleClicked.connect(self.open_layout)
        layout.addWidget(self.layout_list, 1)  # stretch: the list takes the free space
        layout.addLayout(self._build_selection_row())
        layout.addWidget(self._build_refresh_group())
        layout.addWidget(self._build_publish_group())
        self.status = StatusLabel()
        layout.addWidget(self.status)
        self.setWidget(body)

        self.refresh_dir_display()
        self.update_selection_buttons()
        self.update_refresh_button()

    # ---------- building the panel ----------

    def _build_toolbar_row(self):
        """Create the row of tool buttons above the layout list (so far only "New layout").

        Returns:
            QHBoxLayout: The row of buttons.
        """
        row = QHBoxLayout()
        self.btn_new = QToolButton()
        self.btn_new.setIcon(new_layout_icon())
        self.btn_new.setToolTip("Create a new print layout")
        self.btn_new.setAutoRaise(True)  # flat until hovered, like the tool buttons of QGIS panels
        self.btn_new.clicked.connect(self.new_layout)
        row.addWidget(self.btn_new)
        row.addStretch()
        return row

    def _build_selection_row(self):
        """Create the All / None / Rename buttons below the layout list.

        Returns:
            QHBoxLayout: The row of buttons.
        """
        list_widget = self.layout_list.list_widget
        row = QHBoxLayout()
        self.btn_all = QPushButton("All")
        self.btn_none = QPushButton("None")
        self.btn_all.clicked.connect(list_widget.selectAll)
        self.btn_none.clicked.connect(list_widget.clearSelection)
        self.layout_list.populated.connect(self.update_selection_buttons)

        row.addWidget(self.btn_all)
        row.addWidget(self.btn_none)

        self.btn_rename = QPushButton("Rename…")
        self.btn_rename.setToolTip("Rename the selected layout (select exactly one)")
        self.btn_rename.setEnabled(False)  # only enabled when exactly one layout is selected
        self.btn_rename.clicked.connect(self.rename_layout)
        list_widget.itemSelectionChanged.connect(self.update_rename_button)
        row.addStretch()
        row.addWidget(self.btn_rename)
        return row

    def _build_refresh_group(self):
        """Create the Refresh group: the Maps / Other items options and the Refresh button.

        Returns:
            QGroupBox: The group box.
        """
        box, box_layout = make_group("Refresh")

        self.chk_refresh_maps = QCheckBox("Maps")
        self.chk_refresh_maps.setToolTip(
            "Refresh all map items in the selected layouts. This might take a bit longer."
        )
        self.chk_refresh_maps.setChecked(True)
        self.chk_refresh_maps.toggled.connect(self.update_refresh_button)

        self.chk_refresh_other = QCheckBox("Other items (legends, labels…)")
        self.chk_refresh_other.setToolTip(
            "Refresh all other items in the selected layouts, like legends, labels, scale bars, "
            "tables…. This should be quick."
        )
        self.chk_refresh_other.setChecked(True)
        self.chk_refresh_other.toggled.connect(self.update_refresh_button)

        box_layout.addWidget(self.chk_refresh_maps)
        box_layout.addWidget(self.chk_refresh_other)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh_layout_items)
        box_layout.addWidget(self.btn_refresh)
        return box

    def _build_publish_group(self):
        """Create the Publish group: format, export location and the Publish button.

        The last used format is restored from the settings, and saved again
        whenever it changes.

        Returns:
            QGroupBox: The group box.
        """
        box, box_layout = make_group("Publish")

        fmt_row = QHBoxLayout()
        fmt_row.addWidget(QLabel("Format:"))
        self.format_combo = QComboBox()
        for fmt in ExportFormat:
            # Show the format's name; keep the ExportFormat itself as the item's data
            self.format_combo.addItem(fmt.value, fmt)
        # Restore the last used format, falling back to PDF if none or an unknown one is saved
        try:
            saved_fmt = ExportFormat(self.settings.value(SETTINGS_FORMAT, ExportFormat.PDF.value))
        except ValueError:
            saved_fmt = ExportFormat.PDF
        self.format_combo.setCurrentIndex(self.format_combo.findText(saved_fmt.value))
        self.format_combo.currentIndexChanged.connect(
            lambda: self.settings.setValue(SETTINGS_FORMAT, self.format_combo.currentData().value)
        )
        fmt_row.addWidget(self.format_combo, 1)
        box_layout.addLayout(fmt_row)

        box_layout.addWidget(QLabel("Export location:"))
        loc_row = QHBoxLayout()
        self.dir_edit = QLineEdit()
        self.dir_edit.setReadOnly(True)  # changed only via the folder dialog
        self.dir_edit.setPlaceholderText("Not set")
        loc_row.addWidget(self.dir_edit, 1)
        self.btn_dir = QPushButton("Set…")
        self.btn_dir.clicked.connect(self.choose_export_dir)
        loc_row.addWidget(self.btn_dir)
        box_layout.addLayout(loc_row)

        btn_publish = QPushButton("Publish")
        btn_publish.clicked.connect(self.publish_layouts)
        box_layout.addWidget(btn_publish)
        return box

    def disconnect_signals(self):
        """Disconnect the layout list from the project's signals.

        Called by the plugin before the panel is deleted on unload.
        """
        self.layout_list.disconnect_signals()

    # ---------- layout actions ----------

    def new_layout(self):
        """Ask for a name, then create an empty print layout and open it in the layout designer.

        Uses the same dialog as QGIS's Layout Manager. If the name is left empty, a
        unique one such as "Layout 1" is generated; names of existing layouts can't be
        confirmed in the dialog. The new layout is selected in the list.
        """
        dialog = NewLayoutDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return  # cancelled
        lyt = create_layout(QgsProject.instance(), dialog.name())
        # Make QGIS ask to save the project when closing
        QgsProject.instance().setDirty(True)
        # The manager's layoutAdded signal has already added it to the list
        self.layout_list.select_layout(lyt.name())
        self.status.setText(MSG_CREATED.format(name=lyt.name()))
        iface.openLayoutDesigner(lyt)

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

    def update_selection_buttons(self):
        """Enable the All / None buttons only when the layout list isn't empty.

        Connected to ``LayoutList.populated``, and called once in ``__init__``, because
        the list is first filled before this connection exists.
        """
        enabled = not self.layout_list.is_empty()
        self.btn_all.setEnabled(enabled)
        self.btn_none.setEnabled(enabled)

    def update_rename_button(self):
        """Enable the Rename button only when exactly one layout is selected."""
        self.btn_rename.setEnabled(len(self.layout_list.selected_names()) == 1)

    def update_refresh_button(self):
        """Enable the Refresh button only if an option is checked.

        Connected to both refresh checkboxes, and called once in ``__init__`` for the
        starting state; ``toggled`` passes the new state, which is ignored here.
        """
        is_enabled = self.chk_refresh_maps.isChecked() or self.chk_refresh_other.isChecked()
        self.btn_refresh.setEnabled(is_enabled)

    def rename_layout(self):
        """Rename the selected layout using a small input dialog.

        Exactly one layout must be selected. The new name must not be empty
        or already used by another layout, because QGIS requires unique
        layout names.
        """
        selected = self.layout_list.selected_names()
        if len(selected) != 1:
            self.status.setText("Please select exactly one layout to rename.")
            return

        old_name = selected[0]
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
        self.layout_list.select_layout(new_name)
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

    def refresh_layout_items(self):
        """Refresh the items of the selected layouts.

        Depending on the checkboxes, refreshes the map items, all other items
        (legends, labels, scale bars, tables, ...) or both, using
        ``publisher.refresh_layout``. A summary, including any errors, is shown
        in the status line.
        """
        names = self.layout_list.selected_names()
        if not names:
            self.status.setText(MSG_SELECT_LAYOUT)
            return

        manager = QgsProject.instance().layoutManager()
        maps_checked = self.chk_refresh_maps.isChecked()
        others_checked = self.chk_refresh_other.isChecked()
        n_layouts = 0
        n_maps = 0
        n_others = 0
        errors = []

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            for name in names:
                lyt = manager.layoutByName(name)
                if lyt is None:
                    errors.append(ERROR_NOT_FOUND.format(name=name))
                    continue
                try:
                    layout_maps, layout_others = refresh_layout(lyt, maps_checked, others_checked)
                    n_maps += layout_maps
                    n_others += layout_others
                    n_layouts += 1
                except Exception as e:
                    # Report the failure but keep going with the other layouts
                    errors.append(f"'{name}': {e}")
                QApplication.processEvents()
        finally:
            # Always restore the cursor, even if something unexpected fails
            QApplication.restoreOverrideCursor()

        msg_parts = []
        if maps_checked:
            msg_parts.append(MSG_REFRESHED_MAPS.format(n_maps=n_maps))
        if others_checked:
            msg_parts.append(MSG_REFRESHED_OTHERS.format(n_others=n_others))
        msg = MSG_REFRESHED.format(
            items=MSG_REFRESHED_SEPARATOR.join(msg_parts), n_layouts=n_layouts
        )
        if errors:
            msg += "\n" + MSG_ERRORS.format(errors="; ".join(errors))
        self.status.setText(msg)

    def publish_layouts(self):
        """Export the selected layouts to the export folder in the selected format.

        Shows an error if no export folder is set (or it no longer exists)
        and nothing is exported. Otherwise a progress dialog is opened and
        each layout is exported as ``<layout name>.<extension>``; existing
        files with the same name are overwritten.

        The user can stop the export in the progress dialog. The layout being
        exported is finished first (the export can't be interrupted), and the
        remaining layouts are skipped. A summary, including any errors and
        skipped layouts, is shown in the status line afterwards.
        """
        export_dir = self.export_dir()
        if not export_dir:
            self.show_error("Please set an export location.")
            return
        if not os.path.isdir(export_dir):
            self.show_error(f"Export location does not exist: {export_dir}")
            return

        names = self.layout_list.selected_names()
        if not names:
            self.status.setText(MSG_SELECT_LAYOUT)
            return

        fmt = self.format_combo.currentData()
        manager = QgsProject.instance().layoutManager()
        n_ok = 0
        n_skipped = 0
        errors = []

        dialog = PublishProgressDialog(names, fmt, export_dir, iface.mainWindow())
        self._publish_dialog = dialog  # keep a reference
        dialog.show()
        # Each export blocks the main thread, so let Qt repaint the dialog
        # between layouts to keep the marks and progress bar up to date.
        QApplication.processEvents()

        for name in names:
            if dialog.stop_requested:
                dialog.set_skipped(name)
                n_skipped += 1
                continue

            dialog.set_running(name)
            QApplication.processEvents()

            lyt = manager.layoutByName(name)
            if lyt is None:
                errors.append(ERROR_NOT_FOUND.format(name=name))
                dialog.set_failed(name, TOOLTIP_NOT_FOUND)
            else:
                try:
                    result = export_layout(lyt, export_path(export_dir, name, fmt), fmt)
                    if result == QgsLayoutExporter.ExportResult.Success:
                        n_ok += 1
                        dialog.set_done(name)
                    else:
                        errors.append(ERROR_EXPORT_FAILED.format(name=name))
                        dialog.set_failed(name, TOOLTIP_EXPORT_FAILED)
                except Exception as e:
                    # Report the failure but keep going with the other layouts
                    errors.append(f"'{name}': {e}")
                    dialog.set_failed(name, str(e))

            dialog.advance()
            QApplication.processEvents()

        dialog.finish(n_ok, len(errors), n_skipped)

        msg = MSG_PUBLISHED.format(n_ok=n_ok, fmt=fmt.value, export_dir=export_dir)
        if errors:
            msg += "\n" + MSG_ERRORS.format(errors="; ".join(errors))
        if n_skipped:
            msg += "\n" + MSG_PUBLISH_SKIPPED.format(n_skipped=n_skipped)
        self.status.setText(msg)
