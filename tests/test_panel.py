"""Tests for the panel itself (``LayoutPublisherPanel``), apart from Refresh and Publish.

Those are tested in ``test_panel_refresh.py`` and ``test_panel_publish.py``.
"""

from helpers import shown_message

from layout_publisher.layout_list import MSG_NO_PROJECT

# ---------- Unload ----------


def test_panel_ignores_project_after_disconnect(panel, add_layout):
    """After ``disconnect_signals()`` (called on unload), project changes no longer reach the panel.

    Otherwise QGIS would call into a panel that has already been deleted.
    """
    panel.disconnect_signals()

    add_layout("Site plan")

    # The panel no longer reacts, so it still shows the message from before
    assert shown_message(panel) == MSG_NO_PROJECT
