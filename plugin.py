import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon

from .dock import LayoutPublisherDock


class LayoutPublisherPlugin:
    MENU = "&Layout Publisher"

    def __init__(self, iface):
        self.iface = iface
        self.dock = None
        self.action = None

    def initGui(self):
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
        if self.action is not None:
            self.iface.removePluginMenu(self.MENU, self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action = None
        if self.dock is not None:
            self.dock.disconnect_signals()
            self.iface.removeDockWidget(self.dock)
            self.dock.deleteLater()
            self.dock = None
