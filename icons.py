"""Icons drawn by the plugin from QGIS theme icons."""

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QRect, Qt
from qgis.PyQt.QtGui import QIcon, QPainter, QPixmap

# Sizes (in pixels) at which the composite icons are drawn; QIcon picks the closest
# one, so the larger sizes keep the icon sharp on high-resolution screens
ICON_SIZES = (16, 24, 32, 48, 64, 96)


def badged_icon(base_name, badge_name):
    """Combine two QGIS theme icons: the badge sits on the bottom right corner of the base.

    Built like QGIS's own "Add Layer" icon (``mActionAddLayer.svg``). Theme icons are
    used, so the result follows the user's QGIS icon theme.

    Args:
        base_name (str): File name of the theme icon drawn as the background,
            e.g. ``"mActionFileNew.svg"``.
        badge_name (str): File name of the theme icon drawn over its bottom right corner,
            e.g. ``"mActionAdd.svg"``.

    Returns:
        QIcon: The combined icon, drawn at each of the ``ICON_SIZES``.
    """
    base = QgsApplication.getThemeIcon(base_name)
    badge = QgsApplication.getThemeIcon(badge_name)
    icon = QIcon()
    for size in ICON_SIZES:
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        # The base fills most of the icon, moved slightly to the top left to make room
        base_size = round(size * 0.9)
        base.paint(painter, QRect(0, 0, base_size, base_size))
        # The badge covers the bottom right half. Theme icons have a small transparent
        # margin, so the badge is shifted by that margin to reach the corner.
        badge_size = round(size * 0.5)
        offset = size - badge_size + round(badge_size * 0.0625)
        badge.paint(painter, QRect(offset, offset, badge_size, badge_size))
        painter.end()
        icon.addPixmap(pixmap)
    return icon


def new_layout_icon():
    """Return the icon of the button that creates a new print layout: a sheet with a plus.

    Returns:
        QIcon: A blank sheet (``mActionFileNew.svg``) with a green plus
        (``mActionAdd.svg``) on its bottom right corner.
    """
    return badged_icon("mActionFileNew.svg", "mActionAdd.svg")
