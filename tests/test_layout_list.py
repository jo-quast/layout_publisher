"""Tests for the layout list (``LayoutList``): the empty state and keeping in sync.

The tests use the ``panel`` fixture, which contains the list, and read it with the
helpers in ``helpers.py``.
"""

from helpers import listed_layouts, shown_message

from layout_publisher.layout_list import MSG_NO_LAYOUTS, MSG_NO_PROJECT

# ---------- Empty state: the message shown instead of the list ----------


def test_untouched_project_asks_to_open_a_project(panel):
    """Right after QGIS starts, the panel asks to open a project and hides the list and hint."""
    assert shown_message(panel) == MSG_NO_PROJECT
    assert listed_layouts(panel) is None
    assert panel.layout_list.hint_label.isHidden()


def test_unsaved_project_with_changes_counts_as_in_use(panel, project, add_layout):
    """A new project that was never saved but has changes counts as in use.

    So the panel says the project has no layouts, rather than asking to open a project.
    """
    # Deleting the last layout leaves an unsaved project with changes
    layout = add_layout("Site plan")
    project.layoutManager().removeLayout(layout)

    assert project.isDirty()
    assert shown_message(panel) == MSG_NO_LAYOUTS


def test_saved_project_without_layouts(panel, project, tmp_path):
    """After saving a project without layouts, the panel says it has no layouts."""
    # tmp_path is a pytest fixture: a new temporary folder for each test
    project.write(str(tmp_path / "test.qgz"))

    assert shown_message(panel) == MSG_NO_LAYOUTS


def test_new_project_asks_to_open_a_project_again(panel, project, add_layout):
    """Project > New brings back the message asking to open a project."""
    add_layout("Site plan")

    project.clear()  # what Project > New does

    assert shown_message(panel) == MSG_NO_PROJECT


def test_reopened_project_lists_its_layouts(panel, project, add_layout, tmp_path):
    """Opening a saved project lists the layouts stored in it."""
    path = str(tmp_path / "test.qgz")
    add_layout("Site plan")
    project.write(path)
    project.clear()

    project.read(path)

    assert listed_layouts(panel) == ["Site plan"]


def test_existing_layouts_are_shown_instead_of_message(panel, add_layout):
    """Layouts are listed and no message is shown when the project has layouts."""
    add_layout("a plan")

    assert listed_layouts(panel) == ["a plan"]
    assert shown_message(panel) is None
    assert not panel.layout_list.hint_label.isHidden()


def test_deleting_last_layout_asks_to_add_layout(panel, add_layout, delete_layout):
    """Deleting the last layout shows a message asking to add a layout."""
    layout = add_layout("Site plan")
    delete_layout(layout)

    assert shown_message(panel) == MSG_NO_LAYOUTS


# ---------- Synchronisation: layouts added, removed or renamed in QGIS ----------


def test_layouts_are_listed_alphabetically(panel, add_layout):
    """Layouts are listed sorted by name, ignoring upper/lower case."""
    add_layout("b plan")
    add_layout("A plan")

    assert listed_layouts(panel) == ["A plan", "b plan"]
    assert not panel.layout_list.hint_label.isHidden()


def test_renamed_layout_is_updated_in_list(panel, add_layout):
    """Renaming a layout in QGIS updates its name in the list."""
    layout = add_layout("Old name")

    layout.setName("New name")

    assert listed_layouts(panel) == ["New name"]


def test_added_layout_is_listed(panel, add_layout):
    """Adding a layout in QGIS adds it to the list."""
    add_layout("Existing layout")
    assert listed_layouts(panel) == ["Existing layout"]

    add_layout("New layout")
    assert "Existing layout" in listed_layouts(panel)
    assert "New layout" in listed_layouts(panel)


def test_added_layout_is_listed_alphabetically(panel, add_layout):
    """Adding a layout in QGIS adds it to the list, sorted by name."""
    add_layout("b plan")
    assert listed_layouts(panel) == ["b plan"]

    add_layout("A plan")
    assert listed_layouts(panel) == ["A plan", "b plan"]


def test_removed_layout_is_removed_from_list(panel, add_layout, delete_layout):
    """Removing a layout in QGIS removes it from the list."""
    layout = add_layout("Layout to stay")
    layout = add_layout("Layout to remove")
    assert "Layout to stay" in listed_layouts(panel)
    assert "Layout to remove" in listed_layouts(panel)

    delete_layout(layout)
    assert listed_layouts(panel) == ["Layout to stay"]
