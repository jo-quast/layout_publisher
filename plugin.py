"""Plugin class that integrates Layout Publisher into the QGIS interface.

It creates the dockable panel, adds a toggle button to the toolbar and the
Plugins menu, and cleans everything up again when the plugin is unloaded.
"""

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon

from .dock import LayoutPublisherDock


class LayoutPublisherPlugin:
    """Manages the lifecycle of the Layout Publisher plugin in QGIS."""

    # Name of the entry in the Plugins menu ("&" marks the keyboard shortcut).
    MENU = "&Layout Publisher"

    def __init__(self, iface):
        self.iface = iface
        self.dock = None
        self.action = None

    def initGui(self):
        """Create the dock panel and add its toggle action to QGIS.

        Called by QGIS after the plugin has been loaded.
        """
        self.dock = LayoutPublisherDock(self.iface.mainWindow())
        self.iface.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.dock)

        # The dock's built-in toggle action shows/hides the panel
        self.action = self.dock.toggleViewAction()
        self.action.setText("Layout Publisher panel")
        icon_path = os.path.join(os.path.dirname(__file__), "icon.svg")
        self.action.setIcon(QIcon(icon_path))
        self.iface.addPluginToMenu(self.MENU, self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        """Remove the menu entry, toolbar button and dock panel.

        Called by QGIS when the plugin is disabled or QGIS shuts down.
        """
        if self.action is not None:
            self.iface.removePluginMenu(self.MENU, self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None
        if self.dock is not None:
            # Disconnect project signals first so no callbacks reach a
            # widget that is about to be deleted.
            self.dock.disconnect_signals()
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
            self.dock = None
