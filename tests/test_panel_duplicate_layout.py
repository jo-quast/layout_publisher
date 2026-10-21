"""Tests for duplicating a layout with the panel's Duplicate button.

The fixtures ``answer_dialog`` (answers the name dialog) and ``opened_layouts``
(records layouts opened in the designer) are in ``conftest.py``; the dialog itself is
tested in ``test_new_layout_dialog.py``.
"""

import pytest
from layout_publisher.panel import MSG_DUPLICATED
from qgis.core import (
    QgsLayoutItem,
    QgsLayoutItemLabel,
    QgsLayoutItemMap,
    QgsLayoutPoint,
    QgsLayoutSize,
)
from qgis.PyQt.QtCore import Qt


@pytest.fixture
def original(add_layout):
    """Return a layout "Site plan" with a map and a title label, each with an ID and position."""
    lyt = add_layout("Site plan")

    map_item = QgsLayoutItemMap(lyt)
    map_item.setId("Main map")
    map_item.attemptMove(QgsLayoutPoint(10, 20))
    map_item.attemptResize(QgsLayoutSize(200, 150))
    lyt.addLayoutItem(map_item)

    label = QgsLayoutItemLabel(lyt)
    label.setId("Title")
    label.setText("Site plan")
    label.attemptMove(QgsLayoutPoint(10, 5))
    lyt.addLayoutItem(label)
    return lyt


def item_summary(layout):
    """Return the type, ID, position and size of each item of a layout, in a fixed order.

    Two layouts with equal summaries have the same items in the same places. Qt helper
    graphics that aren't layout items are left out.
    """
    summary = []
    for item in layout.items():
        if not isinstance(item, QgsLayoutItem):
            continue
        pos = item.positionWithUnits()
        size = item.sizeWithUnits()
        summary.append(
            (type(item).__name__, item.id(), pos.x(), pos.y(), size.width(), size.height())
        )
    return sorted(summary)


def select(panel, *names):
    """Select exactly the given layouts in the panel's list."""
    list_widget = panel.layout_list.list_widget
    list_widget.clearSelection()
    for name in names:
        list_widget.findItems(name, Qt.MatchFlag.MatchExactly)[0].setSelected(True)


# ---------- the button state ----------


@pytest.mark.usefixtures("original")
def test_duplicate_button_enabled_only_for_one_selected_layout(panel, add_layout):
    """Duplicate is enabled only while exactly one layout is selected."""
    add_layout("Overview")
    assert not panel.btn_duplicate.isEnabled()  # nothing selected

    select(panel, "Site plan")
    assert panel.btn_duplicate.isEnabled()

    select(panel, "Site plan", "Overview")
    assert not panel.btn_duplicate.isEnabled()


# ---------- duplicating ----------


@pytest.mark.usefixtures("original")
def test_duplicate_creates_and_opens_copy(panel, project, answer_dialog, opened_layouts):
    """OK in the dialog (prefilled with "<name> copy") adds the copy and opens it."""
    prefilled = answer_dialog("Site plan copy")
    select(panel, "Site plan")

    panel.btn_duplicate.click()

    assert prefilled == ["Site plan copy"]
    assert project.layoutManager().layoutByName("Site plan copy") is not None
    assert project.layoutManager().layoutByName("Site plan") is not None  # original kept
    assert opened_layouts == ["Site plan copy"]
    assert panel.layout_list.selected_names() == ["Site plan copy"]
    assert panel.status.label.text() == MSG_DUPLICATED.format(
        original="Site plan", name="Site plan copy"
    )
    assert project.isDirty()


@pytest.mark.usefixtures("opened_layouts")
def test_duplicate_copies_items(panel, project, original, answer_dialog):
    """The copy has the same items as the original, in the same places."""
    answer_dialog("Site plan copy")
    select(panel, "Site plan")

    panel.btn_duplicate.click()

    copy = project.layoutManager().layoutByName("Site plan copy")
    assert item_summary(copy) == item_summary(original)
    # Item settings are copied too, e.g. the label's text
    labels = [item for item in copy.items() if isinstance(item, QgsLayoutItemLabel)]
    assert [label.text() for label in labels] == ["Site plan"]


@pytest.mark.usefixtures("original")
def test_duplicate_cancelled(panel, project, answer_dialog, opened_layouts):
    """Cancel creates and opens nothing."""
    answer_dialog(None)
    select(panel, "Site plan")

    panel.btn_duplicate.click()

    assert [lyt.name() for lyt in project.layoutManager().layouts()] == ["Site plan"]
    assert opened_layouts == []
