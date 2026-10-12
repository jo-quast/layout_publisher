"""Status line shown at the bottom of the Layout Publisher panel."""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget


class StatusLabel(QWidget):
    """Status text with a small x button. Hidden whenever the text is empty."""

    def __init__(self, parent=None):
        """Build the label and close button; the widget starts hidden.

        Args:
            parent (QWidget, optional): Parent widget.
        """
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel("")
        self.label.setWordWrap(True)
        row.addWidget(self.label, 1)

        self.btn_close = QToolButton()
        self.btn_close.setText("✕")
        self.btn_close.setAutoRaise(True)
        self.btn_close.setToolTip("Clear message")
        self.btn_close.clicked.connect(self.clear)
        row.addWidget(self.btn_close, 0, Qt.AlignmentFlag.AlignTop)

        self.hide()

    def setText(self, text):
        """Show ``text``, or hide the whole widget if it is empty.

        Args:
            text (str): The message to display.
        """
        self.label.setText(text)
        self.setVisible(bool(text))

    def clear(self):
        """Clear the message and hide the widget."""
        self.setText("")
