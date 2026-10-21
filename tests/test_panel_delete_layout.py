"""Tests for deleting layouts with the panel's Delete button, and its confirmation dialog.

The confirmation is a ``QMessageBox.question``, which would wait for a user, so the
tests replace it with a fake (see ``answer_confirmation`` below) that clicks Yes or No
at once and records the dialog's text.
"""

import pytest
from helpers import listed_layouts
from layout_publisher.panel import MAX_LISTED_NAMES, MSG_DELETED, MSG_MORE_LAYOUTS
from qgis.PyQt.QtWidgets import QMessageBox


@pytest.fixture
def answer_confirmation(monkeypatch):
    """Return a function that decides how the delete confirmation is answered.

    A "factory fixture", like ``add_layout``: ``answer_confirmation(True)`` clicks Yes,
    ``answer_confirmation(False)`` clicks No. The function returns a list that gets the
    text of each confirmation dialog shown, so a test can check the listed names.
    """
    texts = []

    def _answer_confirmation(confirm):
        def fake_question(*args):
            # Called like QMessageBox.question(parent, title, text, buttons, default_button)
            texts.append(args[2])
            if confirm:
                return QMessageBox.StandardButton.Yes
            return QMessageBox.StandardButton.No

        monkeypatch.setattr(QMessageBox, "question", fake_question)
        return texts

    return _answer_confirmation


def select(panel, *names):
    """Select exactly the given layouts in the panel's list."""
    list_widget = panel.layout_list.list_widget
    list_widget.clearSelection()
    for i in range(list_widget.count()):
        if list_widget.item(i).text() in names:
            list_widget.item(i).setSelected(True)


def add_numbered_layouts(add_layout, count):
    """Add ``count`` layouts named "Sheet 01", "Sheet 02", … and return their names."""
    names = [f"Sheet {i:02d}" for i in range(1, count + 1)]
    for name in names:
        add_layout(name)
    return names


# ---------- deleting ----------


def test_delete_after_confirmation(panel, project, add_layout, answer_confirmation):
    """Yes deletes exactly the selected layouts; the others stay."""
    for name in ("Overview", "Site plan", "Detail"):
        add_layout(name)
    answer_confirmation(True)
    select(panel, "Overview", "Detail")

    panel.btn_delete.click()

    assert [lyt.name() for lyt in project.layoutManager().layouts()] == ["Site plan"]
    assert listed_layouts(panel) == ["Site plan"]
    assert panel.status.label.text() == MSG_DELETED.format(n_deleted=2)
    assert project.isDirty()


def test_delete_cancelled(panel, project, add_layout, answer_confirmation):
    """No deletes nothing and keeps the selection."""
    for name in ("Overview", "Site plan"):
        add_layout(name)
    texts = answer_confirmation(False)
    select(panel, "Overview")

    panel.btn_delete.click()

    assert len(texts) == 1  # the confirmation was shown
    assert len(project.layoutManager().layouts()) == 2
    assert listed_layouts(panel) == ["Overview", "Site plan"]
    assert panel.layout_list.selected_names() == ["Overview"]


# ---------- the confirmation dialog ----------


def test_confirmation_lists_selected_layouts(panel, add_layout, answer_confirmation):
    """The confirmation lists every selected layout, and no other."""
    for name in ("Overview", "Site plan", "Detail"):
        add_layout(name)
    texts = answer_confirmation(False)
    select(panel, "Overview", "Detail")

    panel.btn_delete.click()

    assert "• Overview" in texts[0]
    assert "• Detail" in texts[0]
    assert "Site plan" not in texts[0]
    # Within the limit, so there is no "… other layout(s)" line
    assert MSG_MORE_LAYOUTS.split("{", maxsplit=1)[0] not in texts[0]


def test_confirmation_lists_all_names_up_to_limit(panel, add_layout, answer_confirmation):
    """With exactly ``MAX_LISTED_NAMES`` layouts selected, all are listed, with no extra line."""
    names = add_numbered_layouts(add_layout, MAX_LISTED_NAMES)
    texts = answer_confirmation(False)
    panel.layout_list.list_widget.selectAll()

    panel.btn_delete.click()

    for name in names:
        assert f"• {name}" in texts[0]
    assert MSG_MORE_LAYOUTS.split("{", maxsplit=1)[0] not in texts[0]


def test_confirmation_caps_listed_names(panel, add_layout, answer_confirmation):
    """Beyond ``MAX_LISTED_NAMES`` layouts, the rest are counted in a last line instead."""
    n_more = 3
    add_numbered_layouts(add_layout, MAX_LISTED_NAMES + n_more)
    texts = answer_confirmation(False)
    panel.layout_list.list_widget.selectAll()
    selected = panel.layout_list.selected_names()  # in the order the dialog lists them

    panel.btn_delete.click()

    for name in selected[:MAX_LISTED_NAMES]:
        assert f"• {name}" in texts[0]
    for name in selected[MAX_LISTED_NAMES:]:
        assert name not in texts[0]
    assert MSG_MORE_LAYOUTS.format(n_more=n_more) in texts[0]
