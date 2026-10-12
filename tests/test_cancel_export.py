"""Tests for cancelling an export in the publish progress dialog.

The panel's ``export_layout`` method is replaced with a fake (see ``fake_export`` below),
so the tests run fast, write no files, and can "click" Cancel while a layout is being
exported.
"""

import pytest
from layout_publisher.dock import SETTINGS_DIR
from qgis.core import QgsLayoutExporter


@pytest.fixture
def export_dir(panel, tmp_path):
    """Set a temporary export folder and PDF as the format, and return the folder.

    ``publish_layouts`` stops early without an existing export folder.
    ``tmp_path`` is a pytest fixture: a new temporary folder for each test.
    """
    panel.settings.setValue(SETTINGS_DIR, str(tmp_path))
    panel.format_combo.setCurrentText("PDF")
    return tmp_path


@pytest.fixture
def fake_export(panel, monkeypatch):
    """Return a function that replaces ``panel.export_layout`` with a fake export.

    A "factory fixture", like ``add_layout``: a test calls it before publishing, e.g.
    ``exported = fake_export(cancel_during="A")``. The fake writes no files and reports
    every layout as exported successfully. monkeypatch restores the real method after
    the test.
    """

    def _fake_export(cancel_during=None):
        """Install the fake export on the panel.

        Args:
            cancel_during (str, optional): Name of the layout during whose export
                Cancel is clicked. That layout still counts as exported. None
                (the default) never clicks Cancel.

        Returns:
            list[str]: The names of the layouts "exported", in order. It is
            filled in while ``publish_layouts`` runs.
        """
        exported = []

        def export(layout, path, fmt):  # pylint: disable=unused-argument
            """Stand-in for ``export_layout``: record the layout, maybe click Cancel.

            It replaces the method on the panel object only, so it is called
            without ``self``; the other arguments are those of ``export_layout``.
            """
            exported.append(layout.name())
            if layout.name() == cancel_during:
                panel._publish_dialog.btn_cancel.click()  # pylint: disable=protected-access
            return QgsLayoutExporter.ExportResult.Success

        monkeypatch.setattr(panel, "export_layout", export)
        return exported

    return _fake_export


@pytest.mark.usefixtures("export_dir")  # the folder must be set, but isn't used directly
def test_cancel_skips_remaining_layouts(panel, add_layout, fake_export):
    """Clicking Cancel during the first export skips the other layouts."""
    for name in ("A", "B", "C"):
        add_layout(name)
    panel.list_widget.selectAll()
    exported = fake_export(cancel_during="A")

    panel.publish_layouts()

    assert exported == ["A"]  # the layout being exported when Cancel was clicked still finishes
    assert "2 layouts cancelled" in panel.status.label.text()


@pytest.mark.usefixtures("export_dir")  # the folder must be set, but isn't used directly
def test_cancel_during_last_layout_skips_nothing(panel, add_layout, fake_export):
    """Clicking Cancel during the last export doesn't skip any layouts."""
    for name in ("A", "B", "C"):
        add_layout(name)
    panel.list_widget.selectAll()
    exported = fake_export(cancel_during="C")

    panel.publish_layouts()

    assert exported == ["A", "B", "C"]
    assert "cancelled" not in panel.status.label.text()


@pytest.mark.usefixtures("export_dir")  # the folder must be set, but isn't used directly
def test_not_cancelling_exports_all(panel, add_layout, fake_export):
    """Not clicking Cancel exports all layouts."""
    for name in ("A", "B", "C"):
        add_layout(name)
    panel.list_widget.selectAll()
    exported = fake_export(cancel_during=None)

    panel.publish_layouts()

    assert exported == ["A", "B", "C"]
    assert "cancelled" not in panel.status.label.text()
