"""The dialog asking for the name of a new print layout.

It is set up like the dialog QGIS shows for Project > New Print Layout and for
Create in the Layout Manager (``QgisApp::uniqueLayoutTitle`` in the QGIS source).
The panel uses it both to create and to duplicate a layout.
"""

from qgis.core import QgsProject, QgsStringUtils
from qgis.gui import QgsGui, QgsHelp, QgsNewNameDialog
from qgis.PyQt.QtWidgets import QDialogButtonBox

LAYOUT_TYPE = "print layout"
HINT = (
    f"Enter a unique {LAYOUT_TYPE} title\n"
    "(a title will be automatically generated if left empty)"
)
WARNING_NAME_EXISTS = "Title already exists!"
# The page of the QGIS user manual opened by the Help button
HELP_PAGE = "print_composer/overview_composer.html#the-layout-manager"


def window_title():
    """Return the dialog's window title, capitalized like QGIS's own dialog titles.

    QGIS uses title case for dialog titles where its interface guidelines ask for it
    (in English, "Create Print Layout"), and sentence case otherwise.

    Returns:
        str: The window title.
    """
    title = f"Create {LAYOUT_TYPE}"
    if QgsGui.higFlags() & QgsGui.HigFlag.HigDialogTitleIsTitleCase:
        return QgsStringUtils.capitalize(title, QgsStringUtils.Capitalization.TitleCase)
    return title


class NewLayoutDialog(QgsNewNameDialog):
    """Asks for the name of a new print layout, with OK, Cancel and Help buttons.

    The name may be left empty (the caller then generates one), but must not be the
    name of an existing layout: OK is disabled and a warning shown while it is.
    """

    def __init__(self, parent=None, name=""):
        """Set up the dialog for the current project's layouts.

        Args:
            parent (QWidget, optional): Parent widget.
            name (str, optional): Name filled in when the dialog opens, e.g. a
                suggestion for a copy. Empty by default.
        """
        existing = [lyt.name() for lyt in QgsProject.instance().layoutManager().layouts()]
        super().__init__(LAYOUT_TYPE, name, [], existing, parent=parent)
        self.setWindowTitle(window_title())
        self.setHintString(HINT)
        self.setOverwriteEnabled(False)
        self.setAllowEmptyName(True)
        self.setConflictingNameWarning(WARNING_NAME_EXISTS)

        self.buttonBox().addButton(QDialogButtonBox.StandardButton.Help)
        self.buttonBox().helpRequested.connect(lambda: QgsHelp.openHelp(HELP_PAGE))
