"""The Layout Publisher panel, docked in the QGIS main window.

The panel lists all print layouts of the current QGIS project and offers two
actions on the selected layouts:

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
    QVBoxLayout,
    QWidget,
)
from qgis.utils import iface

from .export_format import ExportFormat
from .progress_dialog import PublishProgressDialog
from .publisher import export_layout, export_path, refresh_layout
from .status_label import StatusLabel

# Keys under which the export folder and format are stored in QgsSettings
SETTINGS_DIR = "LayoutPublisher/export_dir"
SETTINGS_FORMAT = "LayoutPublisher/export_format"

LEVEL_CRITICAL = Qgis.MessageLevel.Critical

# Shown in place of the layout list when there is nothing to list
MSG_NO_PROJECT = "No layouts yet. Open a project, or create a layout to get started."
MSG_NO_LAYOUTS = (
    "This project doesn't contain any layouts yet. Once created, layouts will be listed here."
)

# Status line texts; the {placeholders} are filled in with str.format()
MSG_SELECT_LAYOUT = "Please select at least one layout."
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


def project_in_use(qgs_project):
    """Return whether the user is working in a project.

    QGIS always has a project, even right after start. A project counts as
    in use once it was opened or saved (it has a file name) or has unsaved
    changes, so a new, unsaved project the user is working in counts too.

    Args:
        qgs_project (QgsProject): The project to check.

    Returns:
        bool: True if the project has a file name or unsaved changes.
    """
    return bool(qgs_project.fileName()) or qgs_project.isDirty()


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
        # QGIS saves the panel's position and visibility under this name. Keep it unchanged
        # (it dates from when the class was called LayoutPublisherDock), or users' panels
        # would go back to the default position after an update.
        self.setObjectName("LayoutPublisherDock")
        self.settings = QgsSettings()
        self._publish_dialog = None  # reference so the dialog isn't garbage-collected

        body = QWidget()
        layout = QVBoxLayout(body)
        # The list must be built first: the selection row connects to it
        self._build_layout_list(layout)
        layout.addLayout(self._build_selection_row())
        layout.addWidget(self._build_refresh_group())
        layout.addWidget(self._build_publish_group())
        self.status = StatusLabel()
        layout.addWidget(self.status)
        self.setWidget(body)

        self.refresh_dir_display()
        self._connect_signals()
        self.populate()

    # ---------- building the panel ----------

    def _build_layout_list(self, layout):
        """Add the hint, the layout list and the empty-list message to ``layout``.

        Args:
            layout (QVBoxLayout): The panel's main layout.
        """
        self.hint_label = QLabel("Select layouts (double-click to open layout designer):")
        self.hint_label.setWordWrap(True)
        layout.addWidget(self.hint_label)

        # Multi-selection list; shared by the Refresh and Publish actions
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list_widget.itemDoubleClicked.connect(self.open_layout)
        self.list_widget.setToolTip("Double-click a layout to open it in the layout designer")
        layout.addWidget(self.list_widget)

        # Shown instead of the list when there are no layouts to list
        self.empty_label = QLabel()
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()
        layout.addWidget(self.empty_label, 1)  # stretch: takes the list's space

    def _build_selection_row(self):
        """Create the All / None / Rename buttons below the layout list.

        Returns:
            QHBoxLayout: The row of buttons.
        """
        row = QHBoxLayout()
        btn_all = QPushButton("All")
        btn_none = QPushButton("None")
        btn_all.clicked.connect(self.list_widget.selectAll)
        btn_none.clicked.connect(self.list_widget.clearSelection)
        row.addWidget(btn_all)
        row.addWidget(btn_none)

        self.btn_rename = QPushButton("Rename…")
        self.btn_rename.setToolTip("Rename the selected layout (select exactly one)")
        self.btn_rename.setEnabled(False)  # only enabled when exactly one layout is selected
        self.btn_rename.clicked.connect(self.rename_layout)
        self.list_widget.itemSelectionChanged.connect(self.update_rename_button)
        self.list_widget.itemSelectionChanged.connect(self.update_refresh_button)
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
        self.btn_refresh.setEnabled(False)  # enabled by update_refresh_button
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

    # ---------- project signals ----------

    def _project_signals(self):
        """Return the project signals after which the layout list is refreshed.

        Used both to connect and to disconnect them, so the two always match.

        Returns:
            tuple: The signals of the project and its layout manager.
        """
        project = QgsProject.instance()
        manager = project.layoutManager()
        return (
            manager.layoutAdded,
            manager.layoutRemoved,
            manager.layoutRenamed,
            project.readProject,
            project.cleared,
            # Saving a new project for the first time changes which message is shown
            project.fileNameChanged,
            # A new, unsaved project counts as in use once it has changes
            project.isDirtyChanged,
        )

    def _connect_signals(self):
        """Refresh the layout list whenever one of the project signals fires."""
        for sig in self._project_signals():
            sig.connect(self.populate)

    def disconnect_signals(self):
        """Disconnect the project signals that refresh the layout list.

        Called by the plugin before the panel is deleted on unload.
        """
        for sig in self._project_signals():
            try:
                sig.disconnect(self.populate)
            except (TypeError, RuntimeError):
                pass

    # ---------- list handling ----------

    def populate(self, *args):
        """Fill the list, keeping the current selection where possible.

        If there are no layouts, a message is shown instead of the list.

        Connected to several project signals, which pass different
        arguments, hence ``*args`` (ignored).
        """
        previously_selected = {i.text() for i in self.list_widget.selectedItems()}
        self.list_widget.clear()
        project = QgsProject.instance()
        layouts = project.layoutManager().layouts()
        for lyt in sorted(layouts, key=lambda lay: lay.name().lower()):
            item = QListWidgetItem(lyt.name())
            self.list_widget.addItem(item)
            if lyt.name() in previously_selected:
                item.setSelected(True)

        if layouts:
            self.show_empty_message("")
        elif project_in_use(project):
            self.show_empty_message(MSG_NO_LAYOUTS)
        else:
            self.show_empty_message(MSG_NO_PROJECT)

    def show_empty_message(self, text):
        """Show ``text`` in place of the layout list, or the list if ``text`` is empty.

        Args:
            text (str): The message to display.
        """
        self.empty_label.setText(text)
        self.empty_label.setVisible(bool(text))
        self.list_widget.setVisible(not text)
        self.hint_label.setVisible(not text)

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

    def update_refresh_button(self):
        """Enable the Refresh button only if a layout is selected and an option is checked.

        Connected to the list's selection and to both refresh checkboxes; ``toggled``
        passes the new state, which is ignored here.
        """
        is_enabled = bool(self.list_widget.selectedItems()) and (
            self.chk_refresh_maps.isChecked() or self.chk_refresh_other.isChecked()
        )
        self.btn_refresh.setEnabled(is_enabled)

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

    def refresh_layout_items(self):
        """Refresh the items of the selected layouts.

        Depending on the checkboxes, refreshes the map items, all other items
        (legends, labels, scale bars, tables, ...) or both, using
        ``publisher.refresh_layout``. A summary, including any errors, is shown
        in the status line.
        """
        selected = self.list_widget.selectedItems()
        if not selected:
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
            for list_item in selected:
                name = list_item.text()
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

        selected = self.list_widget.selectedItems()
        if not selected:
            self.status.setText(MSG_SELECT_LAYOUT)
            return

        fmt = self.format_combo.currentData()
        names = [i.text() for i in selected]
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
