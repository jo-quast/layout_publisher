"""Tests for the panel's Refresh group: the Refresh button state and which items get refreshed."""

import pytest
from layout_publisher.panel import (
    MSG_REFRESHED,
    MSG_REFRESHED_MAPS,
    MSG_REFRESHED_OTHERS,
    MSG_REFRESHED_SEPARATOR,
)
from qgis.core import (
    QgsLayoutFrame,
    QgsLayoutItemAttributeTable,
    QgsLayoutItemLabel,
    QgsLayoutItemMap,
)


@pytest.fixture
def layout(add_layout):
    """Return a layout with one map, one label and one attribute table (with one frame).

    Together with its page, ``layout.items()`` then also contains a frame and the
    page, which must not be counted as "other items".
    """
    lyt = add_layout("Site plan")
    lyt.addLayoutItem(QgsLayoutItemMap(lyt))
    lyt.addLayoutItem(QgsLayoutItemLabel(lyt))
    table = QgsLayoutItemAttributeTable.create(lyt)
    lyt.addMultiFrame(table)
    table.addFrame(QgsLayoutFrame(lyt, table))
    return lyt


@pytest.fixture
def map_redraws(layout):
    """Return a list that gets an entry whenever the layout's map item is redrawn."""
    redraws = []
    map_item = next(i for i in layout.items() if isinstance(i, QgsLayoutItemMap))
    map_item.changed.connect(lambda: redraws.append(True))
    return redraws


def select_all(panel):
    """Select all layouts in the panel's list, like clicking **All**."""
    panel.layout_list.list_widget.selectAll()


def set_options(panel, maps, other):
    """Tick or untick the Maps and Other items checkboxes."""
    panel.chk_refresh_maps.setChecked(maps)
    panel.chk_refresh_other.setChecked(other)


# ---------- Refresh button state ----------


@pytest.mark.parametrize(
    ("maps", "other", "expected_button_enabled"),
    [
        (True, True, True),
        (True, False, True),
        (False, True, True),
        (False, False, False),
    ],
)
@pytest.mark.usefixtures("layout")  # the layout must exist, but isn't used directly
def test_refresh_button_states(panel, maps, other, expected_button_enabled):
    """Refresh is enabled when at least one option is ticked, without needing a selection."""
    set_options(panel, maps=maps, other=other)

    assert panel.btn_refresh.isEnabled() == expected_button_enabled


# ---------- refreshed items ----------


def refreshed(*parts, n_layouts=1):
    """Return the status message after a refresh, built from the panel's own templates.

    Args:
        *parts (str): The counted parts, e.g. ``MAPS_1``, in the order the panel lists them.
        n_layouts (int, optional): Number of refreshed layouts.

    Returns:
        str: The expected status message.
    """
    return MSG_REFRESHED.format(items=MSG_REFRESHED_SEPARATOR.join(parts), n_layouts=n_layouts)


MAPS_1 = MSG_REFRESHED_MAPS.format(n_maps=1)
OTHERS_2 = MSG_REFRESHED_OTHERS.format(n_others=2)


@pytest.mark.parametrize(
    ("maps", "other", "expected_message", "map_redrawn"),
    [
        (True, True, refreshed(MAPS_1, OTHERS_2), True),
        (True, False, refreshed(MAPS_1), True),
        (False, True, refreshed(OTHERS_2), False),
    ],
)
def test_refresh_options(panel, map_redraws, maps, other, expected_message, map_redrawn):
    """Each checkbox combination refreshes and counts the right items.

    The layout has 1 map and 2 other items (a label and an attribute table); its
    page and the table's frame must not be counted. ``map_redrawn`` checks that the
    map is really skipped when Maps is unticked, since that is the slow part.
    """
    select_all(panel)
    set_options(panel, maps, other)

    panel.refresh_layout_items()

    assert panel.status.label.text() == expected_message
    assert bool(map_redraws) == map_redrawn
