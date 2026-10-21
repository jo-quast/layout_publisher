"""The list of the project's print layouts at the top of the Layout Publisher panel."""

from qgis.core import QgsProject
from qgis.PyQt.QtCore import QItemSelectionModel, Qt, pyqtSignal
from qgis.PyQt.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

# Shown in place of the layout list when there is nothing to list
MSG_NO_PROJECT = "No layouts yet. Open a project, or create a layout to get started."
MSG_NO_LAYOUTS = (
    "This project doesn't contain any layouts yet. Once created, layouts will be listed here."
)


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


class LayoutList(QWidget):
    """The list of the project's layouts, and a message shown instead if there are none.

    The list stays in sync with the project: it is refreshed whenever layouts are
    added, removed or renamed, or another project is opened. It holds only the
    layouts' names; whoever acts on a layout looks it up again by name.

    The panel connects to ``list_widget`` for the selection and double-clicks, and to
    ``populated``, which is emitted after each refresh of the list.
    """

    populated = pyqtSignal()

    def __init__(self, parent=None):
        """Build the widgets, connect the project signals and fill the list.

        Args:
            parent (QWidget, optional): Parent widget.
        """
        super().__init__(parent)
        box_layout = QVBoxLayout(self)
        box_layout.setContentsMargins(0, 0, 0, 0)

        # Multi-selection list; shared by the Refresh and Publish actions
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        box_layout.addWidget(self.list_widget)

        # Shown instead of the list when there are no layouts to list
        self.empty_label = QLabel()
        self.empty_label.setWordWrap(True)
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()
        box_layout.addWidget(self.empty_label, 1)  # stretch: takes the list's space

        self._connect_signals()
        self.populate()

    # ---------- project signals ----------

    def _project_signals(self):
        """Return the project signals after which the list is refreshed.

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
        """Refresh the list whenever one of the project signals fires."""
        for sig in self._project_signals():
            sig.connect(self.populate)

    def disconnect_signals(self):
        """Disconnect the project signals that refresh the list.

        Must be called before the widget is deleted (the panel does this on
        unload), so no project signal reaches a deleted widget.
        """
        for sig in self._project_signals():
            try:
                sig.disconnect(self.populate)
            except (TypeError, RuntimeError):
                pass

    # ---------- list contents ----------

    def populate(self, *args):
        """Fill the list, keeping the current selection where possible.

        If there are no layouts, a message is shown instead of the list.

        Connected to several project signals, which pass different
        arguments, hence ``*args`` (ignored).
        """
        previously_selected = set(self.selected_names())
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

        self.populated.emit()

    def is_empty(self):
        """Return whether the list is empty.

        Returns:
            bool: True if there are no layouts to list.
        """
        return self.list_widget.count() == 0

    def show_empty_message(self, text):
        """Show ``text`` in place of the list, or the list if ``text`` is empty.

        Args:
            text (str): The message to display.
        """
        self.empty_label.setText(text)
        self.empty_label.setVisible(bool(text))
        self.list_widget.setVisible(not text)

    # ---------- selection ----------

    def selected_names(self):
        """Return the names of the selected layouts.

        Returns:
            list[str]: The names, in the order ``QListWidget.selectedItems()`` returns them.
        """
        return [item.text() for item in self.list_widget.selectedItems()]

    def select_layout(self, name):
        """Select only the entry with the given layout name, and scroll to it.

        Any other selected entries are deselected.

        Args:
            name (str): Name of the layout to select. Does nothing if no
                entry has this name.
        """
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.text() == name:
                self.list_widget.setCurrentItem(
                    item, QItemSelectionModel.SelectionFlag.ClearAndSelect
                )
                self.list_widget.scrollToItem(item)
                break
