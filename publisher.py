"""Creating, refreshing and exporting single layouts, without any user interface.

The panel decides which layouts to process and reports the results; the functions
here do the work for one layout at a time. They can be tested without creating
the panel.
"""

import os
import re

from qgis.core import (
    QgsLayoutExporter,
    QgsLayoutFrame,
    QgsLayoutItem,
    QgsLayoutItemMap,
    QgsLayoutItemPage,
    QgsMasterLayoutInterface,
    QgsPrintLayout,
)

from .export_format import ExportFormat

# Characters that are not allowed in file names on Windows (the strictest system)
UNSAFE_FILENAME_CHARS = r'[\\/:*?"<>|]'


def create_layout(project, name=""):
    """Create an empty print layout with one page (A4 landscape) and add it to the project.

    Does what QGIS does for Project > New Print Layout.

    Args:
        project (QgsProject): The project to add the layout to.
        name (str, optional): The layout's name. If empty, a unique name such as
            "Layout 1" is generated.

    Returns:
        QgsPrintLayout: The new layout, now owned by the project's layout manager.
    """
    manager = project.layoutManager()
    if not name:
        name = manager.generateUniqueTitle(QgsMasterLayoutInterface.Type.PrintLayout)
    layout = QgsPrintLayout(project)
    layout.initializeDefaults()  # adds the default page
    layout.setName(name)
    manager.addLayout(layout)
    return layout


def duplicate_layout(project, layout, name=""):
    """Copy a layout, with all its items and settings, and add the copy to the project.

    Does what Duplicate in QGIS's Layout Manager does.

    Args:
        project (QgsProject): The project the layout belongs to; the copy is added to it.
        layout (QgsPrintLayout): The layout to copy.
        name (str, optional): The copy's name. If empty, a unique name such as
            "Layout 1" is generated.

    Returns:
        QgsPrintLayout: The copy, now owned by the project's layout manager, or None
        if QGIS couldn't copy the layout.
    """
    manager = project.layoutManager()
    if not name:
        name = manager.generateUniqueTitle(QgsMasterLayoutInterface.Type.PrintLayout)
    return manager.duplicateLayout(layout, name)


def refresh_layout(layout, maps, others):
    """Refresh the map items, the other items or both in a layout.

    Pages and the frames of tables/HTML items are skipped; tables and HTML items
    are refreshed once via ``multiFrames()`` instead.

    Args:
        layout (QgsPrintLayout): The layout to refresh.
        maps (bool): Whether to refresh the map items.
        others (bool): Whether to refresh all other items (legends, labels,
            scale bars, tables, ...).

    Returns:
        tuple[int, int]: The number of refreshed map items and other items.
    """
    n_maps = 0
    n_others = 0
    for item in layout.items():
        # Skip Qt helper graphics, pages and table/HTML frames (tables are refreshed
        # via multiFrames)
        if not isinstance(item, QgsLayoutItem) or isinstance(
            item, (QgsLayoutItemPage, QgsLayoutFrame)
        ):
            continue
        if isinstance(item, QgsLayoutItemMap):
            if maps:
                item.refresh()
                n_maps += 1
        elif others:
            item.refresh()
            n_others += 1
    if others:
        for item in layout.multiFrames():
            item.refresh()
            n_others += 1
    return n_maps, n_others


def export_path(export_dir, name, fmt):
    """Return the file path a layout is exported to.

    The file is named after the layout, with characters that aren't allowed in
    file names replaced by ``_``.

    Args:
        export_dir (str): The export folder.
        name (str): The layout's name.
        fmt (ExportFormat): The export format, which gives the file extension.

    Returns:
        str: The path, e.g. ``<export_dir>/Site plan.pdf``.
    """
    safe_name = re.sub(UNSAFE_FILENAME_CHARS, "_", name).strip() or "layout"
    return os.path.join(export_dir, f"{safe_name}.{fmt.extension}")


def export_layout(layout, path, fmt):
    """Export a layout to the given path in the given format.

    Args:
        layout (QgsLayout): The layout to export.
        path (str): The file path to export to.
        fmt (ExportFormat): The format to export in.

    Returns:
        QgsLayoutExporter.ExportResult: The result of the export operation.

    Raises:
        ValueError: If the format is unsupported.
    """
    exporter = QgsLayoutExporter(layout)
    if fmt == ExportFormat.PDF:
        return exporter.exportToPdf(path, QgsLayoutExporter.PdfExportSettings())
    if fmt == ExportFormat.PNG:
        return exporter.exportToImage(path, QgsLayoutExporter.ImageExportSettings())
    if fmt == ExportFormat.SVG:
        return exporter.exportToSvg(path, QgsLayoutExporter.SvgExportSettings())
    raise ValueError(f"Unsupported format: {fmt.value}")
