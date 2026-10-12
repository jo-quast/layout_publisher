"""Tests for stopping an export in the publish progress dialog.

The ``export_layout`` function the panel uses is replaced with a fake (see
``fake_export`` below), so the tests run fast, write no files, and can "click" Stop
while a layout is being exported.
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
    """Return a function that replaces the panel's ``export_layout`` with a fake export.

    A "factory fixture", like ``add_layout``: a test calls it before publishing, e.g.
    ``exported = fake_export(stop_during="A")``. The fake writes no files and reports
    every layout as exported successfully. monkeypatch restores the real function after
    the test.
    """

    def _fake_export(stop_during=None):
        """Install the fake export.

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
            """Stand-in for ``publisher.export_layout``: record the layout, maybe click Stop."""
            exported.append(layout.name())
            if layout.name() == stop_during:
                panel._publish_dialog.btn_stop.click()  # pylint: disable=protected-access
            return QgsLayoutExporter.ExportResult.Success

        # Replace the name where it is used: panel.py imported export_layout into its own
        # module, so replacing it in publisher.py would not affect the panel
        monkeypatch.setattr("layout_publisher.panel.export_layout", export)
        return exported

    return _fake_export


@pytest.mark.usefixtures("export_dir")  # the folder must be set, but isn't used directly
def test_stop_skips_remaining_layouts(panel, add_layout, fake_export):
    """Clicking Stop during the first export skips the other layouts."""
    for name in ("A", "B", "C"):
        add_layout(name)
    panel.layout_list.list_widget.selectAll()
    exported = fake_export(stop_during="A")

    panel.publish_layouts()

    assert exported == ["A"]  # the layout being exported when Stop was clicked still finishes
    assert MSG_PUBLISH_SKIPPED.format(n_skipped=2) in panel.status.label.text()


def test_stop_during_last_layout_skips_nothing(panel, add_layout, fake_export, export_dir):
    """Clicking Stop during the last export doesn't skip any layouts."""
    for name in ("A", "B", "C"):
        add_layout(name)
    panel.layout_list.list_widget.selectAll()
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
    panel.layout_list.list_widget.selectAll()
    exported = fake_export(stop_during=None)

    panel.publish_layouts()

    assert exported == ["A", "B", "C"]
    # Only the "Published" line: no line about skipped layouts (or errors) follows it
    assert panel.status.label.text() == MSG_PUBLISHED.format(
        n_ok=3, fmt="PDF", export_dir=export_dir
    )
