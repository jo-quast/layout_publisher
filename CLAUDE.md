# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this
repository. Personal preferences go in `CLAUDE.local.md` (gitignored).

## Project

Layout Publisher is a QGIS plugin (QGIS >= 3.30, Python, no extra packages) that adds a dockable
panel listing the current project's print layouts, so several can be refreshed, renamed, or
exported (PDF/PNG/SVG) at once. The repo root *is* the plugin folder; QGIS loads it as the package
`layout_publisher`.

## Commands

There is no build step. `qgis` is not pip-installable; it ships with QGIS, so tests and anything
importing `qgis` must use QGIS's bundled Python wrapper (not the `python3.12` binary next to it,
which fails without the wrapper's `PYTHONHOME`).

Tests (pytest + pytest-qgis, installed with `pip install --user` for QGIS's Python; config in
`pyproject.toml`, which runs QGIS headless with a stub `iface`). Paths are for macOS; on Windows
and Linux use the Python that comes with the QGIS installation:

```bash
/Applications/QGIS.app/Contents/MacOS/python -m pytest              # all tests
/Applications/QGIS.app/Contents/MacOS/python -m pytest tests/test_publisher.py::test_export_pdf
```

- `tests/conftest.py` has the fixtures `project` (fresh project per test), `panel` (the panel,
  disconnected afterwards) and `add_layout(name)`; `tests/helpers.py` reads the panel state.
- Imports work as `layout_publisher.…` because `pythonpath = [".."]`: this relies on the repo
  folder being named `layout_publisher`.
- pytest-qgis keeps test settings in `.qgis-settings/` (gitignored), not in the user's profile.

Linting: Ruff (line length 100) and Pylint, configured in `pyproject.toml`. Pylint uses
`ignored-modules` for `qgis`/`PyQt5`; `extension-pkg-allow-list` made it hang in VS Code.

UI behaviour still needs a manual check in QGIS, e.g. with the repo symlinked into the QGIS
profile's plugin folder and reloaded with Plugin Reloader.

Packaging (the ZIP must contain a single top-level `layout_publisher/` folder):

```bash
git archive --format=zip --prefix=layout_publisher/ -o layout_publisher.zip HEAD
```

`git archive` packs the last commit only (uncommitted changes are not included) and skips files
marked `export-ignore` in `.gitattributes` (`.gitignore`, `.gitattributes`, `docs/`,
`pyproject.toml`, `tests/`, `CLAUDE.md`); add new non-plugin files there. Untracked/ignored files
such as `CLAUDE.local.md`, `.vscode/` and caches are never included. Don't use `zip -r` on the
folder: it would pack `.git` and editor files. `*.zip` is gitignored.

## Architecture

- `__init__.py`: `classFactory(iface)`, the QGIS entry point; imports `plugin` lazily.
- `plugin.py`: `LayoutPublisherPlugin` lifecycle. `initGui` creates the panel and reuses its
  `toggleViewAction()` as the toolbar/menu action; `unload` must call `panel.disconnect_signals()`
  before deleting the panel so project signals don't reach a deleted widget.
- `panel.py`: `LayoutPublisherPanel` (a `QDockWidget`; QGIS calls dock widgets "panels") puts
  the parts together and carries out the actions on the selected layouts (open, rename, refresh,
  publish). Its object name stays `"LayoutPublisherDock"`: QGIS saves the panel's position under it.
  - `__init__` only outlines the panel; the groups are built in `_build_*` methods. Create the
    `LayoutList` before the selection row (the row connects to its `list_widget`).
  - Export folder and format persist in `QgsSettings` (`LayoutPublisher/export_dir`,
    `LayoutPublisher/export_format`), i.e. per QGIS profile, not per project.
  - Publishing runs synchronously on the main thread; `QApplication.processEvents()` between
    layouts keeps `PublishProgressDialog` repainting and lets its Stop button be clicked.
    Per-layout failures are collected and reported, not raised.
  - Feedback: `self.status` (`StatusLabel`) for normal messages, `show_error()` for errors
    (status line + QGIS message bar). Message texts are `MSG_*` constants that tests import.
- `layout_list.py`: `LayoutList`, the hint, list and empty-state message.
  - Stays in sync via `populate`, connected to every signal returned by `_project_signals()`;
    that single tuple is used for both connecting and disconnecting, so add new project signals
    there only. The panel's `disconnect_signals()` delegates to it.
  - When there are no layouts, `populate` shows a message instead of the list; `project_in_use()`
    decides which one (QGIS always has a project, so "in use" = has a file name or is dirty).
  - List items hold only the layout **name** (`selected_names()`); actions look layouts up again
    via `layoutManager().layoutByName()` and must handle `None`.
- `publisher.py`: work on one layout without UI: `create_layout`, `duplicate_layout`,
  `refresh_layout`, `export_path`, `export_layout`.
  Tests that fake the export patch `layout_publisher.panel.export_layout` (where it's used).
- `new_layout_dialog.py`: `NewLayoutDialog` (a `QgsNewNameDialog` set up like QGIS's own
  "Create Print Layout" dialog), used by both New layout and Duplicate (with a prefilled name)
  via the panel's `_ask_layout_name`. Tests replace its `exec` to answer it headlessly.
- `icons/`: the plugin's own SVG icons, only for buttons without a matching QGIS theme icon
  (`open_layout.svg`, loaded via `panel.ICONS_DIR`). Prefer `QgsApplication.getThemeIcon()`.
- `export_format.py`: the `ExportFormat` enum (value = shown/saved name, `extension` property).
- `progress_dialog.py`: `PublishProgressDialog`, one row per layout with a status mark.
- `status_label.py`: `StatusLabel`, the status line with a clear button.

## Conventions

- PEP 8, max line length 100; Google-style docstrings (`Args:` / `Returns:`) on classes and methods.
- Import Qt via `qgis.PyQt`, and use fully qualified enums (e.g. `Qt.AlignmentFlag.AlignTop`,
  `QgsLayoutExporter.ExportResult.Success`) to stay compatible with a future Qt6/QGIS 4 port.
- UI text is English only.

## Releases

On a version change, update `version=` and the `changelog=` entry in `metadata.txt`. When behaviour
changes, keep the README's "Features", "Known limitations" and "Possible future features" sections
in sync, since they document exactly what the plugin does and doesn't do.
