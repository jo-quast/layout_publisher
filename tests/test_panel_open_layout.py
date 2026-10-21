"""Tests for opening a layout with the panel's Open button.

The fixture ``opened_layouts`` (records layouts opened in the designer) is in
``conftest.py``.
"""


def test_open_button_opens_selected_layout(panel, add_layout, opened_layouts):
    """Open opens exactly the selected layout, not another one, and only once."""
    add_layout("Overview")
    add_layout("Site plan")
    add_layout("Detail")
    panel.layout_list.select_layout("Site plan")

    panel.btn_open.click()

    assert opened_layouts == ["Site plan"]
