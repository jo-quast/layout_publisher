def classFactory(iface):
    from .plugin import LayoutPublisherPlugin
    return LayoutPublisherPlugin(iface)
