"""Tests for the panel itself (``LayoutPublisherPanel``), apart from Refresh and Publish.

Those are tested in ``test_panel_refresh.py`` and ``test_panel_publish.py``.
"""

from helpers import shown_message

from layout_publisher.layout_list import MSG_NO_PROJECT
from layout_publisher.panel import LayoutPublisherPanel

# ---------- Selection buttons: All / None ----------


def selection_buttons_enabled(panel):
    """Return whether the All and None buttons are enabled, as a pair of booleans."""
    return panel.btn_all.isEnabled(), panel.btn_none.isEnabled()


def test_selection_buttons_disabled_without_layouts(panel):
    """With no layouts to list, there is nothing to select, so All and None are disabled.

    This also checks the starting state: the list is filled before the panel connects
    to ``LayoutList.populated``, so the panel must set the buttons once itself.
    """
    assert selection_buttons_enabled(panel) == (False, False)


def test_selection_buttons_enabled_after_adding_layout(panel, add_layout):
    """Adding a layout enables All and None (via the list's ``populated`` signal)."""
    add_layout("Site plan")

    assert selection_buttons_enabled(panel) == (True, True)


def test_selection_buttons_disabled_after_deleting_last_layout(panel, add_layout, delete_layout):
    """Deleting the last layout disables All and None again."""
    layout = add_layout("Site plan")
    # Precondition: without it, the test would also pass if the buttons were never enabled
    assert selection_buttons_enabled(panel) == (True, True)

    delete_layout(layout)

    assert selection_buttons_enabled(panel) == (False, False)


def test_selection_buttons_enabled_with_layouts_at_start(add_layout):
    """A panel created for a project that already has layouts starts with All and None enabled.

    Creates its own panel instead of using the ``panel`` fixture, which is created before
    the test can add layouts.
    """
    add_layout("Site plan")

    new_panel = LayoutPublisherPanel()
    try:
        assert selection_buttons_enabled(new_panel) == (True, True)
    finally:
        # Like the panel fixture: stop project signals reaching the panel once it's deleted
        new_panel.disconnect_signals()
        new_panel.deleteLater()


# ---------- Unload ----------


def test_panel_ignores_project_after_disconnect(panel, add_layout):
    """After ``disconnect_signals()`` (called on unload), project changes no longer reach the panel.

    Otherwise QGIS would call into a panel that has already been deleted.
    """
    panel.disconnect_signals()

    add_layout("Site plan")

    # The panel no longer reacts, so it still shows the message from before
    assert shown_message(panel) == MSG_NO_PROJECT
