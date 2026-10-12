"""Tests for stopping an export in the publish progress dialog.

The panel's ``export_layout`` method is replaced with a fake (see ``fake_export`` below),
so the tests run fast, write no files, and can "click" Stop while a layout is being
exported.
"""

import pytest
from layout_publisher.panel import MSG_PUBLISH_SKIPPED, MSG_PUBLISHED, SETTINGS_DIR
from layout_publisher.export_format import ExportFormat
from qgis.core import QgsLayoutExporter


@pytest.fixture
def export_dir(panel, tmp_path):
    """Set a temporary export folder and PDF as the format, and return the folder.

    ``publish_layouts`` stops early without an existing export folder.
    ``tmp_path`` is a pytest fixture: a new temporary folder for each test.
    """
    panel.settings.setValue(SETTINGS_DIR, str(tmp_path))
    panel.format_combo.setCurrentText(ExportFormat.PDF.value)
    return tmp_path


@pytest.fixture
def fake_export(panel, monkeypatch):
    """Return a function that replaces ``panel.export_layout`` with a fake export.

    A "factory fixture", like ``add_layout``: a test calls it before publishing, e.g.
    ``exported = fake_export(stop_during="A")``. The fake writes no files and reports
    every layout as exported successfully. monkeypatch restores the real method after
    the test.
    """

    def _fake_export(stop_during=None):
        """Install the fake export on the panel.

        Args:
            stop_during (str, optional): Name of the layout during whose export
                Stop is clicked. That layout still counts as exported. None
                (the default) never clicks Stop.

        Returns:
            list[str]: The names of the layouts "exported", in order. It is
            filled in while ``publish_layouts`` runs.
        """
        exported = []

        def export(layout, path, fmt):  # pylint: disable=unused-argument
            """Stand-in for ``export_layout``: record the layout, maybe click Stop.

            It replaces the method on the panel object only, so it is called
            without ``self``; the other arguments are those of ``export_layout``.
            """
            exported.append(layout.name())
            if layout.name() == stop_during:
                panel._publish_dialog.btn_stop.click()  # pylint: disable=protected-access
            return QgsLayoutExporter.ExportResult.Success

        monkeypatch.setattr(panel, "export_layout", export)
        return exported

    return _fake_export


@pytest.mark.usefixtures("export_dir")  # the folder must be set, but isn't used directly
def test_stop_skips_remaining_layouts(panel, add_layout, fake_export):
    """Clicking Stop during the first export skips the other layouts."""
    for name in ("A", "B", "C"):
        add_layout(name)
    panel.list_widget.selectAll()
    exported = fake_export(stop_during="A")

    panel.publish_layouts()

    assert exported == ["A"]  # the layout being exported when Stop was clicked still finishes
    assert MSG_PUBLISH_SKIPPED.format(n_skipped=2) in panel.status.label.text()


def test_stop_during_last_layout_skips_nothing(panel, add_layout, fake_export, export_dir):
    """Clicking Stop during the last export doesn't skip any layouts."""
    for name in ("A", "B", "C"):
        add_layout(name)
    panel.list_widget.selectAll()
    exported = fake_export(stop_during="C")

    panel.publish_layouts()

    assert exported == ["A", "B", "C"]
    # Only the "Published" line: no line about skipped layouts (or errors) follows it
    assert panel.status.label.text() == MSG_PUBLISHED.format(
        n_ok=3, fmt="PDF", export_dir=export_dir
    )


def test_not_stopping_exports_all(panel, add_layout, fake_export, export_dir):
    """Not clicking Stop exports all layouts."""
    for name in ("A", "B", "C"):
        add_layout(name)
    panel.list_widget.selectAll()
    exported = fake_export(stop_during=None)

    panel.publish_layouts()

    assert exported == ["A", "B", "C"]
    # Only the "Published" line: no line about skipped layouts (or errors) follows it
    assert panel.status.label.text() == MSG_PUBLISHED.format(
        n_ok=3, fmt="PDF", export_dir=export_dir
    )
