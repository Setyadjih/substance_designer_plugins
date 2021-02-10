from PySide2.QtCore import Qt
from PySide2.QtGui import QPixmap, QIcon
from PySide2.QtWidgets import QDialog, QVBoxLayout, QCheckBox, QPushButton, \
    QHBoxLayout, QLabel, QComboBox, QFrame, QListWidget, QListWidgetItem, \
    QLineEdit, QAction, QColorDialog, QErrorMessage

from constants import PANTONE_COLOR_BOOKS


class ColorModeDialog(QDialog):
    def __init__(self, parent=None):
        super(ColorModeDialog, self).__init__(parent)

        self.setWindowTitle("Options")
        vlayout = QVBoxLayout()

        pantone_check = QCheckBox("Pantone colors only")
        custom_check = QCheckBox("Custom color selection")
        color_mode_button = QPushButton("Accept")

        # Pantone book selection setup
        dropdown_layout = QHBoxLayout()

        # dropdown and label setup
        dropdown_label = QLabel("Color Book: ")
        book_dropdown = QComboBox()
        book_dropdown.addItems(PANTONE_COLOR_BOOKS)

        dropdown_frame = QFrame()
        dropdown_layout.addWidget(dropdown_label)
        dropdown_layout.addWidget(book_dropdown)
        dropdown_frame.setLayout(dropdown_layout)

        vlayout.addWidget(pantone_check)
        vlayout.addWidget(dropdown_frame)
        vlayout.addWidget(custom_check)
        vlayout.addWidget(color_mode_button)

        self.setLayout(vlayout)

        # defaults
        dropdown_frame.hide()

        # Signal/Slots
        pantone_check.stateChanged.connect(
            lambda x: dropdown_frame.show() if x else dropdown_frame.hide()
        )

        color_mode_button.clicked.connect(self.accept)


class CustomSelectionDialog(QDialog):
    def __init__(self, spotlib, pantone_mode, book_index=0, parent=None):
        super(CustomSelectionDialog, self).__init__(parent)

        self.setWindowTitle("Custom Color Pick")
        self.self.spotlib = spotlib

        # Base window setup
        self.book_dropdown = QComboBox()
        self.book_dropdown.addItems(PANTONE_COLOR_BOOKS)
        self.book_dropdown.setCurrentIndex(book_index)

        custom_vlayout = QVBoxLayout()
        custom_accept = QPushButton("Confirm Colors")
        self.color_list = QListWidget()
        self.color_list.setContextMenuPolicy(Qt.ActionsContextMenu)

        # Color input Setup
        color_pick_confirm_btn = QPushButton("Pick Color")

        # Pantone Section
        pantone_frame = QFrame()
        pantone_layout = QVBoxLayout()
        pantone_frame.setLayout(pantone_layout)
        book_label = QLabel(f"Pantone Book: ")
        color_pick_label = QLabel("Input Pantone Color:")

        # Input layout
        pantone_input_hlayout = QHBoxLayout()
        self.pantone_label = QLabel("PANTONE")
        self.middle_line = QLineEdit()
        self.end_line = QLineEdit()

        self.middle_line.setPlaceholderText("536")
        self.end_line.setPlaceholderText("CP")

        pantone_input_hlayout.addWidget(self.pantone_label)
        pantone_input_hlayout.addWidget(self.middle_line)
        pantone_input_hlayout.addWidget(self.end_line)

        # add to layout
        pantone_layout.addWidget(book_label)
        pantone_layout.addWidget(self.book_dropdown)
        pantone_layout.addWidget(color_pick_label)
        pantone_layout.addLayout(pantone_input_hlayout)
        pantone_layout.addWidget(color_pick_confirm_btn)

        # Item removal Action in context menu for color list
        delete_item = QAction("Remove Color")
        self.color_list.addAction(delete_item)

        # Default color picker
        default_color_frame = QFrame()
        default_color_layout = QVBoxLayout()
        default_color_frame.setLayout(default_color_layout)

        add_color_btn = QPushButton("Add Color")
        default_color_layout.addWidget(add_color_btn)
        default_color_layout.addWidget(self.color_list)
        default_color_layout.addWidget(custom_accept)
        
        custom_vlayout.addWidget(pantone_frame)
        custom_vlayout.addWidget(default_color_frame)
        
        # Default show
        pantone_frame.hide()
        default_color_frame.show()
        
        if pantone_mode:
            pantone_frame.show()
            default_color_frame.hide()
        
        self.setLayout(custom_vlayout)
        
        # Signals/Slots
        custom_accept.clicked.connect(self.accept)
        color_pick_confirm_btn.clicked.connect(self.find_pantone_color)
        add_color_btn.clicked.connect(self.add_custom_color)
        
        delete_item.triggered.connect(
            lambda x: self.color_list.takeItem(self.color_list.currentRow())
        )

    def add_custom_color(self):
        color_dialog = QColorDialog()
        color = color_dialog.getColor()
        if color:
            # Get color from picker, save with a pixmap
            pixmap = QPixmap(25, 25)
            pixmap.fill(color)
            icon = QIcon(pixmap)

            color_list_item = QListWidgetItem(
                icon,
                color.name() + f" | R: {color.red()}, "
                               f"G: {color.green()}, "
                               f"B: {color.blue()}"
            )
            color_list_item.setData(Qt.UserRole, color)
            self.color_list.addItem(color_list_item)

    def find_pantone_color(self):
        """Find the input color, add to list if exist"""
        book = self.book_dropdown.currentText()
        color_name = f"PANTONE " \
                     f"{self.middle_line.text().strip()} " \
                     f"{self.end_line.text().strip()}"
        print(f"INPUT: {color_name}")
        col = self.spotlib.findSpotColorByName(
            spotColorBookName=book,
            spotColorName=color_name
        )
        if col:
            print(col)
            print(col.get())
            col_name = self.spotlib.getSpotColorName(col)
            if not self.color_list.findItems(col_name, Qt.MatchFixedString):
                color_list_item = QListWidgetItem(col_name)
                color_list_item.setData(Qt.UserRole, col)
                self.color_list.addItem(color_list_item)
        else:
            error_message = QErrorMessage()
            error_message.setWindowTitle("Bad Color")
            error_message.showMessage(
                "Failed to find color. "
                "Please check selected book or color name"
            )
