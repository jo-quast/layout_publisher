"""Tests if the layout list is updated whenever a layout is added, removed, or renamed."""

from helpers import listed_layouts


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
