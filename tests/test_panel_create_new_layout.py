"""Tests for creating a layout with the panel's New layout button (``new_layout``).

The dialog's ``exec()`` would wait for a user, so the tests replace it with a fake
(see ``answer_dialog`` below) that types a name and clicks OK or Cancel at once. The
stub ``iface`` of pytest-qgis can't open a layout designer, so its
``openLayoutDesigner`` is replaced too (see ``opened_layouts``).
"""

import pytest
from helpers import listed_layouts
from layout_publisher.new_layout_dialog import (
    HINT,
    WARNING_NAME_EXISTS,
    NewLayoutDialog,
    window_title,
)
from layout_publisher.panel import MSG_CREATED
from layout_publisher.publisher import create_layout
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QLabel, QLineEdit


def ok_button(dialog):
    """Return the OK button of a ``NewLayoutDialog``."""
    return dialog.buttonBox().button(QDialogButtonBox.StandardButton.Ok)


@pytest.fixture
def answer_dialog(monkeypatch):
    """Return a function that decides how the next New layout dialog is answered.

    A "factory fixture", like ``add_layout``: e.g. ``answer_dialog("Site plan")`` types
    "Site plan" and clicks OK, ``answer_dialog(None)`` clicks Cancel. The returned list
    gets each dialog that was shown, so a test can check it.
    """
    shown = []

    def _answer_dialog(name):
        def fake_exec(dialog):
            shown.append(dialog)
            if name is None:
                return QDialog.DialogCode.Rejected
            dialog.findChild(QLineEdit).setText(name)
            # A user can't click OK while it is disabled (e.g. for an existing name)
            if not ok_button(dialog).isEnabled():
                return QDialog.DialogCode.Rejected
            return QDialog.DialogCode.Accepted

        monkeypatch.setattr(NewLayoutDialog, "exec", fake_exec)
        return shown

    return _answer_dialog


@pytest.fixture
def opened_layouts(monkeypatch):
    """Return a list that gets the name of each layout opened in the layout designer."""
    opened = []
    # raising=False: the stub iface has no openLayoutDesigner to replace, so add it
    monkeypatch.setattr(
        "layout_publisher.panel.iface.openLayoutDesigner",
        lambda layout: opened.append(layout.name()),
        raising=False,
    )
    return opened


# ---------- creating a layout ----------


def test_new_layout_creates_and_opens_layout(panel, project, answer_dialog, opened_layouts):
    """OK with a name adds an empty layout with that name and opens it in the designer."""
    answer_dialog("Site plan")

    panel.new_layout()

    layout = project.layoutManager().layoutByName("Site plan")
    assert layout is not None
    assert layout.pageCollection().pageCount() == 1  # empty, with the default page
    assert opened_layouts == ["Site plan"]
    assert listed_layouts(panel) == ["Site plan"]
    assert panel.layout_list.selected_names() == ["Site plan"]
    assert panel.status.label.text() == MSG_CREATED.format(name="Site plan")
    assert project.isDirty()


def test_new_layout_without_name_generates_one(panel, project, answer_dialog, opened_layouts):
    """OK with an empty name creates a layout with a generated name, like QGIS does."""
    answer_dialog("")

    panel.new_layout()

    assert [lyt.name() for lyt in project.layoutManager().layouts()] == ["Layout 1"]
    assert opened_layouts == ["Layout 1"]


def test_new_layout_cancelled(panel, project, answer_dialog, opened_layouts):
    """Cancel creates and opens nothing."""
    answer_dialog(None)

    panel.new_layout()

    assert project.layoutManager().layouts() == []
    assert opened_layouts == []


def test_new_layout_existing_name_not_accepted(
    panel, project, add_layout, answer_dialog, opened_layouts
):
    """The name of an existing layout disables OK, so no second layout is created."""
    add_layout("Site plan")
    answer_dialog("Site plan")

    panel.new_layout()

    assert len(project.layoutManager().layouts()) == 1
    assert opened_layouts == []


# ---------- the dialog ----------


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


# ---------- publisher.create_layout ----------


def test_create_layout_numbers_generated_names(project):
    """Without a name, each new layout gets the next free generated name."""
    first = create_layout(project)
    second = create_layout(project)

    assert (first.name(), second.name()) == ("Layout 1", "Layout 2")
