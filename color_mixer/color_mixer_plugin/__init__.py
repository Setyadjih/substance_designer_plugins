from functools import partial
import weakref
from pathlib import Path
from colorsys import hsv_to_rgb

import sd
from sd.api import SDValueBool
from sd.api.sdvaluestring import SDValueString
from sd.api.sbs.sdsbscompgraph import SDSBSCompGraph
from sd.api.sdapplication import SDApplicationPath
from sd.api.sdvalueint import SDValueInt
from sd.api.sdvaluefloat import SDValueFloat
from sd.api.sdbasetypes import float2
from sd.api.sdvaluecolorrgba import SDValueColorRGBA
from sd.api.sdvaluearray import SDValueArray
from sd.api.sdvaluestruct import SDValueStruct
from sd.api.sdtypestruct import SDTypeStruct
from sd.api.sdbasetypes import ColorRGBA

from PySide2 import QtGui, QtWidgets
from PySide2.QtCore import Qt
from PySide2.QtGui import QPixmap, QIcon, QColor
from PySide2.QtWidgets import QDialog, QVBoxLayout, QCheckBox, QPushButton, \
    QHBoxLayout, QLabel, QComboBox, QFrame, QListWidget, QListWidgetItem, \
    QLineEdit, QAction, QColorDialog, QErrorMessage, QMessageBox, QInputDialog


PANTONE_COLOR_BOOKS = [
    "PANTONE Color Bridge Coated-V4",
    "PANTONE Color Bridge Uncoated-V4",
    "PANTONE FHI Cotton TCX",
    "PANTONE FHI Metallic Shimmers TPM",
    "PANTONE FHI Nylon Brights TN",
    "PANTONE FHI Paper TPG",
    "PANTONE FHI Polyester TSX",
    "PANTONE Skin Tone Guide",
    "PANTONE solid coated",
    "PANTONE solid uncoated",
    "PANTONE+ Extended Gamut Coated",
    "PANTONE+ Metallic Coated",
    "PANTONE+ Pastels _Neons Coated",
    "PANTONE+ Pastels _Neons Uncoated",
    "PANTONE+ Premium Metallics Coated",
    "PANTONE+ Solid Coated",
    "PANTONE+ Solid Uncoated",
]


class ColorModeDialog(QDialog):
    def __init__(self, parent=None):
        super(ColorModeDialog, self).__init__(parent)

        self.setWindowTitle("Options")

        self.pantone_check = QCheckBox("Pantone colors only")
        self.custom_check = QCheckBox("Custom color selection")
        color_mode_button = QPushButton("Accept")

        # Pantone book selection setup
        dropdown_layout = QHBoxLayout()

        # dropdown and label setup
        dropdown_label = QLabel("Color Book: ")
        self.book_dropdown = QComboBox()
        self.book_dropdown.addItems(PANTONE_COLOR_BOOKS)

        dropdown_frame = QFrame()
        dropdown_layout.addWidget(dropdown_label)
        dropdown_layout.addWidget(self.book_dropdown)
        dropdown_frame.setLayout(dropdown_layout)

        vlayout = QVBoxLayout()
        vlayout.addWidget(self.pantone_check)
        vlayout.addWidget(dropdown_frame)
        vlayout.addWidget(self.custom_check)
        vlayout.addWidget(color_mode_button)
        self.setLayout(vlayout)

        # defaults
        dropdown_frame.hide()

        # Signal/Slots
        self.pantone_check.stateChanged.connect(
            lambda x: dropdown_frame.show() if x else dropdown_frame.hide()
        )

        color_mode_button.clicked.connect(self.accept)


class CustomSelectionDialog(QDialog):
    def __init__(self, spotlib, pantone_mode, book_index=0, parent=None):
        super(CustomSelectionDialog, self).__init__(parent)

        self.setWindowTitle("Custom Color Pick")
        self.spotlib = spotlib

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
        custom_vlayout.addWidget(custom_accept)
        custom_vlayout.addWidget(self.color_list)

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

        col = self.spotlib.findSpotColorByName(
            spotColorBookName=book,
            spotColorName=color_name
        )
        if col:
            col_rgb = col.get()
            col_name = self.spotlib.getSpotColorName(col)
            if not self.color_list.findItems(col_name, Qt.MatchFixedString):
                color = QColor()
                color.setRgbF(col_rgb.r, col_rgb.g, col_rgb.b,)

                print(f"R: {col_rgb.r*255} G: {col_rgb.g*255} B: {col_rgb.b*255}")
                pixmap = QPixmap(25, 25)
                pixmap.fill(color)
                icon = QIcon(pixmap)
                color_list_item = QListWidgetItem(icon, col_name)
                color_list_item.setData(Qt.UserRole, col)
                self.color_list.addItem(color_list_item)
        else:
            error_message = QErrorMessage()
            error_message.setWindowTitle("Bad Color")
            error_message.showMessage(
                "Failed to find color. "
                "Please check selected book or color name"
            )


class PluginToolBar(QtWidgets.QToolBar):
    __toolbarList = {}

    def __init__(self, graphViewID, uiMgr):
        super(PluginToolBar, self).__init__(parent=uiMgr.getMainWindow())

        self.setObjectName('color_mixer_plugin_toolbar')

        self.__graphViewID = graphViewID
        self.__uiMgr = uiMgr

        current_dir = Path(__file__).parent
        icon_path = Path.joinpath(current_dir, r'icons\color_mixer.png')

        action = self.addAction(
            QtGui.QIcon(icon_path.as_posix()),
            "color_mixer"
        )
        action.setToolTip(
            "Setup Node structure for color adjustment. The nodes are "
            "given default values for manual adjustment"
        )
        action.triggered.connect(self.color_mixer)

        self.__toolbarList[graphViewID] = weakref.ref(self)
        self.destroyed.connect(
            partial
            (PluginToolBar.__onToolbarDeleted,
             graphViewID=graphViewID
             )
        )

    def tooltip(self):
        return self.tr("Custom Plugins")

    def color_mixer(self):
        sd_context = sd.getContext()
        sd_application = sd_context.getSDApplication()
        package_manager = sd_application.getPackageMgr()
        uimgr = sd_application.getUIMgr()
        mainWin = sd_application.getQtForPythonUIMgr().getMainWindow()
        spotLib = sd_application.getSpotColorLibrary()

        # Init error message
        dialog = QMessageBox()
        dialog.setWindowTitle("Plugin Error!")

        comp_graph: SDSBSCompGraph = uimgr.getCurrentGraph()
        if not comp_graph:
            dialog.setText("Failed to find graph.")
            dialog.exec_()
            return

        comp_graph.compute()

        levels_id = 'sbs::compositing::levels'
        gradient_id = 'sbs::compositing::gradient'
        uniform_id = 'sbs::compositing::uniform'
        output_id = 'sbs::compositing::output'

        graph_select = uimgr.getCurrentGraphSelection()
        if graph_select.getSize() != 1:
            dialog.setText("Please select only 1 Color node")
            dialog.exec_()
            return

        col_map_node = graph_select[0]
        if not col_map_node:
            dialog.setText("Please select a node!")
            dialog.exec_()
            return

        color_mode_window = ColorModeDialog(parent=mainWin)
        result = color_mode_window.exec_()
        if not result:
            return

        is_pantone = color_mode_window.pantone_check.isChecked()
        custom_col = color_mode_window.custom_check.isChecked()
        book_index = color_mode_window.book_dropdown.currentIndex()

        # InputDialog to find how many outputs
        if custom_col:
            # Window setup
            custom_window = CustomSelectionDialog(
                spotLib,
                is_pantone,
                book_index,
                mainWin
            )
            result = custom_window.exec_()
            col_count = custom_window.color_list.count()
        else:
            col_count, result = QInputDialog().getInt(
                self, "Colors Spread", "Number of Colors:", 6, 0, 200, 1
            )

        if not result:
            print("EXITING")
            return

        # Load instance sbs files
        resource_path = sd_application.getPath(
            SDApplicationPath.DefaultResourcesDir
        )

        color_match_name = 'color_match'
        color_match_pack = package_manager.loadUserPackage(
            Path(resource_path).joinpath(
                'packages',
                'color_match.sbs'
            ).as_posix()
        )

        # Map -> Output node with type label
        for node in comp_graph.getNodes():
            node_label = node.getDefinition().getLabel()
            if node_label == 'Bitmap' and node != col_map_node:
                # Connect other maps to output and label
                file_path = Path(node.getReferencedResource().getFilePath())
                map_type = file_path.stem.split('-')[-1]
                map_out = comp_graph.newNode(output_id)

                npos = node.getPosition()
                new_pos = float2(npos.x+200, npos.y)
                map_out.setPosition(new_pos)

                node.newPropertyConnectionFromId(
                    "unique_filter_output", map_out, "inputNodeOutput"
                )
                map_out.setAnnotationPropertyValueFromId(
                    "identifier", SDValueString.sNew(f"{map_type.upper()}")
                )

        # Currently unused, should check if this would ever be used again
        advanced_mode = False
        if advanced_mode:
            # Load packages
            gray_conv_name = 'grayscale_conversion_advanced'
            gray_conv_pack = package_manager.loadUserPackage(
                Path(resource_path).joinpath(
                    'packages',
                    'grayscale_conversion_advanced.sbs'
                ).as_posix()
            )

            auto_lvl_name = 'auto_levels'
            auto_lvl_pack = package_manager.loadUserPackage(
                Path(resource_path).joinpath(
                    'packages',
                    'auto_levels.sbs'
                ).as_posix()
            )

            gray_conv = comp_graph.newInstanceNode(
                gray_conv_pack.findResourceFromUrl(gray_conv_name)
            )

            auto_lvl = comp_graph.newInstanceNode(
                auto_lvl_pack.findResourceFromUrl(auto_lvl_name)
            )

            # Get positioning
            col_pos: float2 = col_map_node.getPosition()
            gray_pos = float2(col_pos.x+200, col_pos.y)
            alvl_pos = float2(col_pos.x+400, col_pos.y)
            lvl_pos = float2(col_pos.x+600, col_pos.y)

            lvl_node = comp_graph.newNode(levels_id)

            # Arranging nodes
            gray_conv.setPosition(gray_pos)
            auto_lvl.setPosition(alvl_pos)
            lvl_node.setPosition(lvl_pos)

            # Creating connections
            col_map_node.newPropertyConnectionFromId(
                "unique_filter_output", gray_conv, "input"
            )
            gray_conv.newPropertyConnectionFromId(
                "output", auto_lvl, "Input"
            )
            auto_lvl.newPropertyConnectionFromId(
                "Output", lvl_node, "input1"
            )

            top_y = col_pos.y - (col_count*200/2)

            hue_interval = 360 / col_count

            # iterate over all colors
            for i in range(col_count):
                x_pos = lvl_pos.x + 400
                y_pos = top_y + (200 * i)

                # count_pos = float2(x_pos, y_pos)

                grad_pos = float2(x_pos+200, y_pos)
                out_pos = float2(x_pos+400, y_pos)

                count_grad = comp_graph.newNode(gradient_id)
                count_grad.setPosition(grad_pos)

                # grad nodes start with no value
                # Add grad points to array
                # bot
                val_struct = SDValueStruct.sNew(
                    SDTypeStruct.sNew("sbs::compositing::gradient_key_rgba")
                )

                hue = i * hue_interval
                # Converting to percentage
                hue /= 360
                rgb = hsv_to_rgb(hue, .25, .75)
                new_rgb = ColorRGBA(rgb[0], rgb[1], rgb[2], 1)

                val_rgb = SDValueColorRGBA.sNew(new_rgb)
                val_struct.setPropertyValueFromId("value", val_rgb)
                val_struct.setPropertyValueFromId("position", SDValueFloat.sNew(1))
                val_struct.setPropertyValueFromId("midpoint", SDValueFloat.sNew(-1))

                # Top
                val_struct2 = SDValueStruct.sNew(
                    SDTypeStruct.sNew("sbs::compositing::gradient_key_rgba")
                )
                rgb2 = hsv_to_rgb(hue, .5, .25)
                new_rgb2 = ColorRGBA(rgb2[0], rgb2[1], rgb2[2], 1)

                val_rgb2 = SDValueColorRGBA.sNew(new_rgb2)
                val_struct2.setPropertyValueFromId("value", val_rgb2)
                val_struct2.setPropertyValueFromId("position", SDValueFloat.sNew(0))
                val_struct2.setPropertyValueFromId("midpoint", SDValueFloat.sNew(-1))

                # Setup value array and add gradient points
                val_arr = SDValueArray.sNew(
                    SDTypeStruct.sNew("sbs::compositing::gradient_key_rgba"), 0
                )
                val_arr.pushBack(val_struct)
                val_arr.pushBack(val_struct2)

                count_grad.setInputPropertyValueFromId(
                    'gradientrgba', val_arr
                )

                lvl_node.newPropertyConnectionFromId(
                    "unique_filter_output", count_grad, "input1"
                )

                count_out = comp_graph.newNode(output_id)
                count_out.setPosition(out_pos)
                count_grad.newPropertyConnectionFromId(
                    "unique_filter_output", count_out, "inputNodeOutput"
                )
                count_out.setAnnotationPropertyValueFromId(
                    "identifier", SDValueString.sNew(f"COL_{i+1}")
                )
                comp_graph.compute()
                return

        # Get initial positions
        col_pos = col_map_node.getPosition()
        top_y = col_pos.y - (col_count * 200 / 2)

        for i in range(col_count):
            x_pos = col_pos.x + 400
            y_pos = top_y + (200 * i)
            uniform_node = comp_graph.newNode(uniform_id)
            uniform_node.setPosition(float2(x_pos, y_pos))

            # Get colors from user assigned list
            if custom_col:
                color = custom_window.color_list.item(i).data(Qt.UserRole)

                # Convert to substance color if coming from QColorPicker
                # QColor(0-255) -> ColorRGBA(0.0-1.0)
                sd_color = color if is_pantone else SDValueColorRGBA.sNew(
                    ColorRGBA(
                        color.red()/255,
                        color.green()/255,
                        color.blue()/255,
                        1)
                )

            # Get colors from spread
            else:
                hue_interval = 360 / col_count
                hue = i * hue_interval

                # Converting to percentage
                hue /= 360
                rgb = hsv_to_rgb(hue, .25, .75)
                sd_color = SDValueColorRGBA.sNew(
                    ColorRGBA(rgb[0], rgb[1], rgb[2], 1)
                )

                if is_pantone:
                    # convert to pantone colors
                    sd_color = spotLib.findClosestSpotColor(
                        color_mode_window.book_dropdown.currentText(),
                        r=rgb[0],
                        g=rgb[1],
                        b=rgb[2]
                    )

            # Node setup
            uniform_node.setInputPropertyValueFromId('outputcolor', sd_color)

            col_match = comp_graph.newInstanceNode(
                color_match_pack.findResourceFromUrl(color_match_name)
            )
            col_match.setPosition(float2(x_pos+200, y_pos))
            col_match.setInputPropertyValueFromId(
                "target_color_mode",
                SDValueInt.sNew(1)
            )
            col_match.setInputPropertyValueFromId(
                "use_mask",
                SDValueBool.sNew(False)
            )

            # Connect source color, target color to color match
            col_map_node.newPropertyConnectionFromId(
                "unique_filter_output", col_match, "input"
            )
            uniform_node.newPropertyConnectionFromId(
                "unique_filter_output", col_match, "input_target_color"
            )

            # Connect color match to output
            count_out = comp_graph.newNode(output_id)
            out_pos = float2(x_pos + 400, y_pos)
            count_out.setPosition(out_pos)

            col_match.newPropertyConnectionFromId(
                "output", count_out, "inputNodeOutput"
            )
            count_out.setAnnotationPropertyValueFromId(
                "identifier", SDValueString.sNew(f"COL_{i + 1}")
            )

        # Compute the new nodes
        comp_graph.compute()

    @classmethod
    def __onToolbarDeleted(cls, graphViewID):
        del cls.__toolbarList[graphViewID]

    @classmethod
    def removeAllToolbars(cls):
        for toolbar in cls.__toolbarList.values():
            if toolbar():
                toolbar().deleteLater()


def onNewGraphViewCreated(graphViewID, uiMgr):
    toolbar = PluginToolBar(graphViewID, uiMgr)
    uiMgr.addToolbarToGraphView(
        graphViewID,
        toolbar,
        tooltip=toolbar.tooltip())


graphViewCreatedCallbackID = 0


def initializeSDPlugin():
    ctx = sd.getContext()
    app = ctx.getSDApplication()
    uiMgr = app.getQtForPythonUIMgr()

    if uiMgr:
        global graphViewCreatedCallbackID
        graphViewCreatedCallbackID = uiMgr.registerGraphViewCreatedCallback(
            partial(onNewGraphViewCreated, uiMgr=uiMgr))


def uninitializeSDPlugin():
    ctx = sd.getContext()
    app = ctx.getSDApplication()
    uiMgr = app.getQtForPythonUIMgr()

    if uiMgr:
        global graphViewCreatedCallbackID
        uiMgr.unregisterCallback(graphViewCreatedCallbackID)
        PluginToolBar.removeAllToolbars()
