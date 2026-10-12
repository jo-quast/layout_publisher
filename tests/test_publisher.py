"""Tests for exporting a single layout with ``publisher.export_layout``, in every format.

Unlike the tests in ``test_panel_publish.py``, these run the real QGIS export and write
files, into pytest's temporary folder ``tmp_path``.
"""

from layout_publisher.export_format import ExportFormat
from layout_publisher.publisher import export_layout
from qgis.core import QgsLayoutExporter


def test_export_pdf(add_layout, tmp_path):
    """Exporting a layout as PDF writes a PDF file to the given path."""
    layout = add_layout("Site plan")
    path = tmp_path / "Site plan.pdf"  # tmp_path is a new, empty folder for each test

    result = export_layout(layout, str(path), ExportFormat.PDF)

    assert result == QgsLayoutExporter.ExportResult.Success
    assert path.exists()
    # Every PDF file starts with "%PDF", so this checks it really is a PDF
    assert path.read_bytes().startswith(b"%PDF")


def test_export_png(add_layout, tmp_path):
    """Exporting a layout as PNG writes a PNG file to the given path."""
    layout = add_layout("Site plan")
    path = tmp_path / "Site plan.png"  # tmp_path is a new, empty folder for each test

    result = export_layout(layout, str(path), ExportFormat.PNG)

    assert result == QgsLayoutExporter.ExportResult.Success
    assert path.exists()
    # Every PNG file starts with the same 8 bytes, so this checks it really is a PNG
    assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


def test_export_svg(add_layout, tmp_path):
    """Exporting a layout as SVG writes an SVG file to the given path."""
    layout = add_layout("Site plan")
    path = tmp_path / "Site plan.svg"  # tmp_path is a new, empty folder for each test

    result = export_layout(layout, str(path), ExportFormat.SVG)

    assert result == QgsLayoutExporter.ExportResult.Success
    assert path.exists()
    # Every SVG file contains an "<svg>" tag, so this checks it really is an SVG
    assert b"<svg" in path.read_bytes()
