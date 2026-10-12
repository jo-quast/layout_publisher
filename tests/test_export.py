"""Tests for exporting a single layout with ``export_layout``, in every format.

Unlike the tests in ``test_stop_export.py``, these run the real QGIS export and write
files, into pytest's temporary folder ``tmp_path``.
"""

from layout_publisher.export_format import ExportFormat
from qgis.core import QgsLayoutExporter


def test_export_pdf(panel, add_layout, tmp_path):
    """Exporting a layout as PDF writes a PDF file to the given path."""
    layout = add_layout("Site plan")
    path = tmp_path / "Site plan.pdf"  # tmp_path is a new, empty folder for each test

    result = panel.export_layout(layout, str(path), ExportFormat.PDF)

    assert result == QgsLayoutExporter.ExportResult.Success
    assert path.exists()
    # Every PDF file starts with "%PDF", so this checks it really is a PDF
    assert path.read_bytes().startswith(b"%PDF")


def test_export_png(panel, add_layout, tmp_path):
    """Exporting a layout as PNG writes a PNG file to the given path."""
    layout = add_layout("Site plan")
    path = tmp_path / "Site plan.png"  # tmp_path is a new, empty folder for each test

    result = panel.export_layout(layout, str(path), ExportFormat.PNG)

    assert result == QgsLayoutExporter.ExportResult.Success
    assert path.exists()
    # Every PNG file starts with the same 8 bytes, so this checks it really is a PNG
    assert path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
