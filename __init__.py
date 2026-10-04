"""Layout Publisher - QGIS plugin entry point."""

def classFactory(iface):
    """Create the plugin instance. Called by QGIS when the plugin is loaded.
 
    Args:
        iface (QgsInterface): The QGIS interface, giving access to the main
            window, menus, toolbars and message bar.
 
    Returns:
        LayoutPublisherPlugin: The plugin object managed by QGIS.
    """
    # Imported here (as in the standard QGIS plugin template) so the Qt
    # modules are only loaded once the plugin is actually started.
    from .plugin import LayoutPublisherPlugin
    return LayoutPublisherPlugin(iface)
