"""Tests for the publish progress dialog: the progress bar, the rows' marks and the summary.

The dialog is tested on its own, without the panel or a real export: the tests call
the methods the export loop in ``publish_layouts`` calls, and check what the dialog
shows. Headless, widgets are never visible, so the tests check ``isHidden()`` instead
of ``isVisible()``.
"""

import pytest
from layout_publisher.export_format import ExportFormat
from layout_publisher.progress_dialog import (
    COLOR_FAIL,
    COLOR_OK,
    COLOR_PENDING,
    COLOR_RUNNING,
    MARK_DONE,
    MARK_FAILED,
    MARK_PENDING,
    MARK_RUNNING,
    MARK_SKIPPED,
    MSG_EXPORTING,
    MSG_STOPPING,
    MSG_SUMMARY,
    MSG_SUMMARY_FAILED,
    MSG_SUMMARY_SKIPPED,
    TOOLTIP_SKIPPED,
    PublishProgressDialog,
)

NAMES = ["A", "B", "C"]


@pytest.fixture
def dialog(qgis_app):  # pylint: disable=unused-argument
    """Return a progress dialog for exporting the layouts in ``NAMES`` as PDF.

    ``qgis_app`` (from pytest-qgis) makes sure the QGIS application exists, which
    any widget needs. The dialog is deleted after the test.
    """
    new_dialog = PublishProgressDialog(NAMES, ExportFormat.PDF, "/exports")
    yield new_dialog
    new_dialog.deleteLater()


def row(dialog, name):  # pylint: disable=redefined-outer-name
    """Return the mark label and the name label of the row for layout ``name``."""
    return dialog._rows[name]  # pylint: disable=protected-access


# ---------- Before the export ----------


def test_new_dialog_shows_every_layout_as_waiting(dialog):
    """Every layout gets a row with its name and a grey dot."""
    for name in NAMES:
        mark, text = row(dialog, name)
        assert text.text() == name
        assert mark.text() == MARK_PENDING
        assert COLOR_PENDING in mark.styleSheet()


def test_new_dialog_header_and_progress(dialog):
    """The header names the number of layouts and the format; the bar starts empty."""
    assert dialog.header.text() == MSG_EXPORTING.format(n_layouts=3, fmt="PDF")
    assert dialog.progress.value() == 0
    assert dialog.progress.maximum() == len(NAMES)


def test_new_dialog_offers_stop_not_close(dialog):
    """While the export runs, there is a Stop button but no Close button."""
    assert not dialog.btn_stop.isHidden()
    assert dialog.btn_close.isHidden()


# ---------- Row marks ----------


# Each case: the method to call, extra arguments after the name, and the expected
# symbol, colour and tooltip. parametrize runs the test once per case.
@pytest.mark.parametrize(
    ("method", "args", "symbol", "color", "tooltip"),
    [
        ("set_running", (), MARK_RUNNING, COLOR_RUNNING, ""),
        ("set_done", (), MARK_DONE, COLOR_OK, ""),
        ("set_failed", ("Disk full",), MARK_FAILED, COLOR_FAIL, "Disk full"),
        ("set_skipped", (), MARK_SKIPPED, COLOR_PENDING, TOOLTIP_SKIPPED),
    ],
)
def test_mark(dialog, method, args, symbol, color, tooltip):  # pylint: disable=too-many-arguments
    """Each status method shows its symbol and colour, with a tooltip on mark and name."""
    getattr(dialog, method)("B", *args)  # e.g. dialog.set_failed("B", "Disk full")

    mark, text = row(dialog, "B")
    assert mark.text() == symbol
    assert color in mark.styleSheet()
    assert mark.toolTip() == tooltip
    assert text.toolTip() == tooltip


def test_mark_changes_only_its_own_row(dialog):
    """Marking one layout leaves the other rows waiting."""
    dialog.set_done("B")

    assert row(dialog, "A")[0].text() == MARK_PENDING
    assert row(dialog, "C")[0].text() == MARK_PENDING


# ---------- Progress bar ----------


def test_advance_moves_progress_bar_by_one(dialog):
    """Each call to advance() counts one more finished layout."""
    dialog.advance()
    assert dialog.progress.value() == 1

    dialog.advance()
    assert dialog.progress.value() == 2


def test_advance_fills_progress_bar_after_all_layouts(dialog):
    """After one advance() per layout, the bar is at its maximum."""
    for _ in NAMES:
        dialog.advance()

    assert dialog.progress.value() == dialog.progress.maximum()


@pytest.mark.parametrize(
    ("n_ok", "n_failed", "n_skipped"),
    [
        (0, 0, 0),
        (1, 0, 0),
        (0, 1, 0),
        (0, 0, 1),
        (1, 0, 1),
        (0, 1, 1),
        (1, 1, 1),
        (2, 2, 2),
    ],
)
def test_progress_bar_fills_when_export_is_done(dialog, n_ok, n_failed, n_skipped):
    """finish() fills the bar, even if layouts failed or were skipped: the export is over."""
    dialog.finish(n_ok, n_failed, n_skipped)

    assert dialog.progress.value() == dialog.progress.maximum()


# ---------- Stopping ----------


def test_request_stop(dialog):
    """Stopping sets the flag, says so in the header and disables the Stop button."""
    dialog.request_stop()

    assert dialog.stop_requested
    assert dialog.header.text() == MSG_STOPPING
    assert not dialog.btn_stop.isEnabled()


def test_esc_while_running_requests_stop(dialog):
    """Esc (reject) during the export stops it instead of closing the dialog."""
    dialog.reject()

    assert dialog.stop_requested


# ---------- Finishing ----------

# The parts of the summary, filled in with the numbers used in the cases below
DONE_3 = MSG_SUMMARY.format(n_ok=3)
DONE_2 = MSG_SUMMARY.format(n_ok=2)
DONE_1 = MSG_SUMMARY.format(n_ok=1)
DONE_0 = MSG_SUMMARY.format(n_ok=0)
FAILED_1 = MSG_SUMMARY_FAILED.format(n_failed=1, mark=MARK_FAILED)
SKIPPED_2 = MSG_SUMMARY_SKIPPED.format(n_skipped=2)


@pytest.mark.parametrize(
    ("n_ok", "n_failed", "n_skipped", "expected"),
    [
        (3, 0, 0, DONE_3),
        (2, 1, 0, DONE_2 + FAILED_1),
        (1, 0, 2, DONE_1 + SKIPPED_2),
        (0, 1, 2, DONE_0 + FAILED_1 + SKIPPED_2),
    ],
)
def test_finish_summary(dialog, n_ok, n_failed, n_skipped, expected):
    """The header summarises the export, mentioning failed and skipped layouts only if any.

    The expected texts are built from the same templates as the dialog's, so the test
    checks which parts appear, in which order and with which numbers, not the wording.
    """
    dialog.finish(n_ok, n_failed, n_skipped)

    assert dialog.header.text() == expected


def test_finish_replaces_stop_with_close(dialog):
    """Once finished, Stop is hidden and Close is shown as the default button."""
    dialog.finish(3, 0, 0)

    assert dialog.btn_stop.isHidden()
    assert not dialog.btn_close.isHidden()
    assert dialog.btn_close.isDefault()


def test_esc_after_finish_does_not_request_stop(dialog):
    """After the export, Esc (reject) closes the dialog and no longer requests a stop."""
    dialog.finish(3, 0, 0)
    dialog.reject()

    assert not dialog.stop_requested
