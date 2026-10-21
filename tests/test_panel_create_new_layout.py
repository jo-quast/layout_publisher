"""Tests for creating a layout with the panel's New layout button (``new_layout``).

The fixtures ``answer_dialog`` (answers the name dialog) and ``opened_layouts``
(records layouts opened in the designer) are in ``conftest.py``; the dialog itself is
tested in ``test_new_layout_dialog.py``.
"""

from helpers import listed_layouts
from layout_publisher.panel import MSG_CREATED
from layout_publisher.publisher import create_layout


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


def test_create_layout_numbers_generated_names(project):
    """Without a name, each new layout gets the next free generated name."""
    first = create_layout(project)
    second = create_layout(project)

    assert (first.name(), second.name()) == ("Layout 1", "Layout 2")
