"""Small helpers for reading the panel's state in tests."""


def listed_layouts(panel):
    """Return the layout names shown in the panel's list, or None if the list is hidden."""
    if panel.list_widget.isHidden():
        return None
    return [panel.list_widget.item(i).text() for i in range(panel.list_widget.count())]


def shown_message(panel):
    """Return the message shown instead of the list, or None if no message is shown."""
    if panel.empty_label.isHidden():
        return None
    return panel.empty_label.text()
