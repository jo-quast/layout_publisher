"""Small helpers for reading the panel's and dialogs' state in tests."""

from qgis.PyQt.QtWidgets import QDialogButtonBox


def listed_layouts(panel):
    """Return the layout names shown in the panel's list, or None if the list is hidden."""
    list_widget = panel.layout_list.list_widget
    if list_widget.isHidden():
        return None
    return [list_widget.item(i).text() for i in range(list_widget.count())]


def shown_message(panel):
    """Return the message shown instead of the list, or None if no message is shown."""
    if panel.layout_list.empty_label.isHidden():
        return None
    return panel.layout_list.empty_label.text()


def ok_button(dialog):
    """Return the OK button of a ``NewLayoutDialog``."""
    return dialog.buttonBox().button(QDialogButtonBox.StandardButton.Ok)
