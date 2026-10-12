"""Tests for the message shown when there are no layouts."""

from helpers import listed_layouts, shown_message

from layout_publisher.dock import MSG_NO_LAYOUTS, MSG_NO_PROJECT


def test_untouched_project_asks_to_open_a_project(panel):
    """Right after QGIS starts, the panel asks to open a project and hides the list and hint."""
    assert shown_message(panel) == MSG_NO_PROJECT
    assert listed_layouts(panel) is None
    assert panel.hint_label.isHidden()


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
    assert not panel.hint_label.isHidden()


def test_deleting_last_layout_aks_to_add_layout(panel, add_layout, delete_layout):
    """Deleting the last layout shows a message asking to add a layout."""
    layout = add_layout("Site plan")
    delete_layout(layout)

    assert shown_message(panel) == MSG_NO_LAYOUTS


def test_panel_ignores_project_after_disconnect(panel, add_layout):
    """After ``disconnect_signals()`` (called on unload), project changes no longer reach the panel.

    Otherwise QGIS would call into a panel that has already been deleted.
    """
    panel.disconnect_signals()

    add_layout("Site plan")

    # The panel no longer reacts, so it still shows the message from before
    assert shown_message(panel) == MSG_NO_PROJECT
