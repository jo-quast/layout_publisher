"""The file formats Layout Publisher can export layouts to."""

from enum import Enum


class ExportFormat(Enum):
    """An export format, offered in the panel's Format list in this order.

    The value is the name shown in the panel and stored in the settings.
    """

    PDF = "PDF"
    PNG = "PNG"
    SVG = "SVG"

    @property
    def extension(self):
        """str: The file name extension without the dot, e.g. ``"pdf"``."""
        return self.value.lower()
