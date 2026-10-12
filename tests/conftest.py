"""Shared fixtures for the Layout Publisher tests.

pytest runs these tests with QGIS's own Python. pytest-qgis starts a headless
QGIS application and replaces ``qgis.utils.iface`` with a stub, so the panel can
be created without the QGIS main window.

Fixtures are injected by name: pytest looks at a test's parameter names and
passes in the result of the fixture with that name. A test function with a
parameter called ``panel`` receives the panel created by the ``panel`` fixture
below. Fixtures can request other fixtures the same way.
"""

import pytest
from layout_publisher.panel import LayoutPublisherPanel
from qgis.core import QgsPrintLayout


@pytest.fixture
def project(qgis_new_project):
    """Return a fresh, empty QGIS project (cleared before every test).

    ``qgis_new_project`` is provided by pytest-qgis.
    """
    return qgis_new_project


@pytest.fixture
def panel(project):  # pylint: disable=unused-argument
    """Create the Layout Publisher panel, and clean it up after the test.

    Requesting ``project`` makes pytest reset the QGIS project first, so every
    panel starts from an empty project. The panel itself reads the project via
    ``QgsProject.instance()``, so the argument isn't used here.

    Everything before ``yield`` runs before the test, everything after it runs
    after the test, even if the test failed.
    """
    new_panel = LayoutPublisherPanel()
    yield new_panel  # the test runs here
    new_panel.disconnect_signals()
    new_panel.deleteLater()


@pytest.fixture
def add_layout(project):
    """Return a function that adds a print layout with the given name to the project.

    A "factory fixture": it returns a function rather than a layout, so a test
    can add as many layouts as it needs, e.g. ``add_layout("Site plan")``.
    """

    def _add_layout(name):
        layout = QgsPrintLayout(project)
        layout.initializeDefaults()  # adds a page
        layout.setName(name)
        project.layoutManager().addLayout(layout)
        return layout

    return _add_layout


@pytest.fixture
def delete_layout():
    """Return a function that removes the given layout from the project.

    A "factory fixture": it returns a function rather than a layout, so a test
    can remove any layout it needs, e.g. ``delete_layout(layout)``.
    """

    def _delete_layout(layout):
        layout.project().layoutManager().removeLayout(layout)

    return _delete_layout
