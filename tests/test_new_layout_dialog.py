"""Tests for the dialog asking for a new layout's name (``NewLayoutDialog``).

Both the New layout and the Duplicate button use this dialog; their own tests are in
``test_panel_create_new_layout.py`` and ``test_panel_duplicate_layout.py``.
"""

from helpers import ok_button
from layout_publisher.new_layout_dialog import WARNING_NAME_EXISTS, NewLayoutDialog
from qgis.PyQt.QtWidgets import QLabel, QLineEdit


def test_dialog_ok_enabled_for_empty_name(project):  # pylint: disable=unused-argument
    """An empty name is allowed: QGIS then generates one."""
    dialog = NewLayoutDialog()

    dialog.findChild(QLineEdit).setText("")

    assert ok_button(dialog).isEnabled()


def test_dialog_warns_about_existing_name(add_layout):
    """Typing the name of an existing layout disables OK and shows a warning."""
    add_layout("Site plan")
    dialog = NewLayoutDialog()

    dialog.findChild(QLineEdit).setText("Site plan")

    assert not ok_button(dialog).isEnabled()
    assert any(WARNING_NAME_EXISTS in label.text() for label in dialog.findChildren(QLabel))


def test_dialog_prefills_name(add_layout):
    """A name passed to the dialog is filled in, and can be confirmed if it is unused."""
    add_layout("Site plan")

    dialog = NewLayoutDialog(name="Site plan copy")

    assert dialog.findChild(QLineEdit).text() == "Site plan copy"
    assert ok_button(dialog).isEnabled()
