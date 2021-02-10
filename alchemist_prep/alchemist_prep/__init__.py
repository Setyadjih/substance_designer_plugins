from functools import partial
import weakref
from pathlib import Path

import sd
from sd.api.sdproperty import SDPropertyCategory
from sd.api.sdvaluefloat import SDValueFloat
from sd.api.sdvaluefloat3 import SDValueFloat3
from sd.api.sdbasetypes import float2, float3
from sd.api.sdvaluebool import SDValueBool
from sd.api.sdvaluestring import SDValueString
from sd.api.sdvaluearray import SDValueArray
from sd.api.sdvalueusage import SDValueUsage
from sd.api.sdvalueint import SDValueInt
from sd.api.sdusage import SDUsage

from sd.api.sdapplication import SDApplicationPath

from PySide2 import QtGui, QtWidgets


class PluginToolBar(QtWidgets.QToolBar):
    __toolbarList = {}

    def __init__(self, graphViewID, uiMgr):
        super(PluginToolBar, self).__init__(parent=uiMgr.getMainWindow())

        self.setObjectName('output_adjust_plugin_toolbar')

        self.__graphViewID = graphViewID
        self.__uiMgr = uiMgr

        current_dir = Path(__file__).parent
        icon_path = Path.joinpath(current_dir, r'icons\DPD_icon.png')

        action = self.addAction(
            QtGui.QIcon(icon_path.as_posix()),
            "output_adjust"
        )
        action.setToolTip(
            """ Various fixes for alchemist to designer exports:
            *Delete unused outputs
            *Delete transformation 2D nodes
            *Adjust the physical size of all packages in the explorer
            *Set normal to height nodes and transform normal to displacement
            *set new output and name as DISP
            *set up safe transform node to nearest scale of real fabric
            """
        )
        action.triggered.connect(self.lifung_alchemist_prep)

        self.__toolbarList[graphViewID] = weakref.ref(self)
        self.destroyed.connect(
            partial
            (PluginToolBar.__onToolbarDeleted,
             graphViewID=graphViewID
             )
        )

    def tooltip(self):
        return self.tr("Custom Plugins")

    def lifung_alchemist_prep(self):
        try:
            sd_context = sd.getContext()
            sd_application = sd_context.getSDApplication()
            package_manager = sd_application.getPackageMgr()
            ui_manager = sd_application.getUIMgr()

            comp_graph = ui_manager.getCurrentGraph()
            comp_graph.compute()

            self.physical_size_adjust(comp_graph)
            height_pos = self.node_cleanup(
                comp_graph,
                sd_application,
                package_manager
            )
            self.displacement_setup(
                comp_graph,
                sd_application,
                package_manager,
                height_pos
            )
            self.output_setup(comp_graph)
            comp_graph.compute()

        except Exception as error:
            message = QtWidgets.QMessageBox()
            message.setStyleSheet(
                "QLabel{min-width: 200px; min-height: 30px}");

            message.setWindowTitle('Plugin Error!')
            message.setText(f'Error: {error}')
            message.exec_()

    def physical_size_adjust(self, comp_graph):
        # Physical Size Adjust
        for node in comp_graph.getNodes():
            if node.getDefinition().getLabel() == 'Bitmap':
                value_int = node.getPropertyValueFromId(
                    '$outputsize',
                    SDPropertyCategory.Input
                )

        output_x = value_int.get().x
        physical_size = comp_graph.getPropertyFromId(
            'physical_size',
            SDPropertyCategory.Annotation
        )
        # physical size is measured as a sdValuefloat3
        # output size isn't stored as absolute, is set as a power of 2.
        # i.e. in x:12, y:12, this is 4096 x 4096 because 2 ^ 12 = 4096

        tex_size = round(((2 ** output_x) / 236.22), 2)
        new_size = SDValueFloat3.sNew(float3(tex_size, tex_size, 0))

        comp_graph.setPropertyValue(physical_size, new_size)

    def node_cleanup(self, comp_graph, application, package_manager):
        """Remove unneeded nodes and outputs, store height position"""
        height_pos = float2(100, 100)
        source_to_delete = ['Height', 'Specular Level', 'Ambient Occlusion']
        resource_path = application.getPath(
            SDApplicationPath.DefaultResourcesDir
        )

        safe_trans_pack = package_manager.loadUserPackage(
            Path(resource_path).joinpath(
                'packages',
                'safe_transform.sbs'
            ).as_posix()
        )
        safe_trans_pack_name = 'safe_transform'

        for node in comp_graph.getNodes():
            node_label = node.getDefinition().getLabel()

            # We want to specifically remove the source of these maps
            if node_label in source_to_delete:

                # We access the bitmap by going upstream the node connections
                transform_node = node.getPropertyConnections(
                    node.getProperties(
                        SDPropertyCategory.Input
                    )[0]
                )[0].getInputPropertyNode()

                transform_prop = transform_node.getPropertyFromId(
                    'input1',
                    SDPropertyCategory.Input
                )

                bit_node = transform_node.getPropertyConnections(
                    transform_prop
                )[0].getInputPropertyNode()

                # Delete the nodes
                comp_graph.deleteNode(transform_node)
                comp_graph.deleteNode(bit_node)

                # We use the height node for placement later
                if node.getDefinition().getLabel() == 'Height':
                    height_pos = node.getPosition()

                comp_graph.deleteNode(node)

        # We finished searching through the nodes, so no longer need the
        # Transform2D nodes. Make sure to iterate after previous loop
        for node in comp_graph.getNodes():
            node_label = node.getDefinition().getLabel()
            if node_label == 'Transformation 2D':
                node_pos = node.getPosition()

                # Setup our node variables
                input_prop = node.getPropertyConnections(
                    node.getPropertyFromId(
                        'input1',
                        SDPropertyCategory.Input
                    )
                )[0].getInputProperty()

                input_node = node.getPropertyConnections(
                    node.getPropertyFromId(
                        'input1',
                        SDPropertyCategory.Input
                    )
                )[0].getInputPropertyNode()

                output_node = node.getPropertyConnections(
                    node.getPropertyFromId(
                        'unique_filter_output',
                        SDPropertyCategory.Output
                    )
                )[0].getInputPropertyNode()

                # Delete the transform 2D nodes
                comp_graph.deleteNode(node)

                # Create and setup the safe transforms
                new_safe = comp_graph.newInstanceNode(
                    safe_trans_pack.findResourceFromUrl(safe_trans_pack_name)
                )
                new_safe.setPosition(node_pos)
                new_safe.setInputPropertyValueFromId(
                    'tile',
                    SDValueInt.sNew(4)
                )

                new_safe_input = new_safe.getPropertyFromId(
                    'input',
                    SDPropertyCategory.Input
                )

                # Insert a gradient map for conversion when needed
                color_mode = input_node.getPropertyValueFromId(
                    'colorswitch',
                    SDPropertyCategory.Input
                ).get()
                if not color_mode:
                    gradient_map = comp_graph.newNode(
                        'sbs::compositing::gradient')
                    gradient_map.setPosition(node_pos)

                    input_node.newPropertyConnectionFromId(
                        'unique_filter_output', gradient_map, 'input1')
                    gradient_map.newPropertyConnectionFromId(
                        'unique_filter_output', new_safe, 'input')
                else:
                    input_node.newPropertyConnection(input_prop, new_safe,
                                                     new_safe_input)

                new_safe.newPropertyConnectionFromId('output', output_node,
                                                     'inputNodeOutput')
        return height_pos

    def displacement_setup(self, comp_graph, sd_application,
                           package_manager, height_pos):
        """Setup the displacement output node from normals"""
        current_dir = Path(__file__).parent
        resource_path = Path(sd_application.getPath(
            SDApplicationPath.DefaultResourcesDir
            )
        )
        normal_to_height_file_path = Path.joinpath(
            current_dir,
            'normal_to_height_hq_cust.sbs'
        ).as_posix()

        # Use custom normal to height with quality set to 'high' as default
        normal_to_height = package_manager.loadUserPackage(
            normal_to_height_file_path
        )
        normal_intensity = package_manager.loadUserPackage(
            resource_path.joinpath(
                'packages',
                'normal_intensity.sbs'
                ).as_posix()
            )

        normal_height_node = comp_graph.newInstanceNode(
            normal_to_height.findResourceFromUrl('normal_to_height_hq')
        )
        normal_intensity_node = comp_graph.newInstanceNode(
            normal_intensity.findResourceFromUrl('normal_intensity')
        )
        normal_output = ''
        trans = ''

        # Setup displacement output node
        displacement_usage = SDValueUsage.sNew(
            SDUsage.sNew('displacement', 'RGBA', ''))
        disp_sdarray = SDValueArray.sNew(displacement_usage.getType(), 0)
        disp_sdarray.pushBack(displacement_usage)

        disp_output = comp_graph.newNode('sbs::compositing::output')
        disp_output.setAnnotationPropertyValueFromId(
            'label', SDValueString.sNew('Displacement')
        )
        disp_output.setAnnotationPropertyValueFromId(
            'identifier', SDValueString.sNew('DISP')
        )
        disp_output.setAnnotationPropertyValueFromId(
            'group', SDValueString.sNew('Material')
        )
        disp_output.setAnnotationPropertyValueFromId('usages', disp_sdarray)

        # Find transform 2D node
        for node in comp_graph.getOutputNodes():
            if node.getDefinition().getLabel() == 'Normal':
                normal_output = node
                trans = node.getPropertyConnections(
                    node.getPropertyFromId(
                     'inputNodeOutput', SDPropertyCategory.Input
                    )
                )[0].getInputPropertyNode()

        # reconnect the nodes
        trans.newPropertyConnectionFromId(
            'output', normal_intensity_node, 'input'
        )
        normal_intensity_node.newPropertyConnectionFromId(
            'output', normal_height_node, 'normal'
        )
        normal_intensity_node.newPropertyConnectionFromId(
            'output', normal_output, 'inputNodeOutput'
        )
        normal_height_node.newPropertyConnectionFromId(
            'height', disp_output, 'inputNodeOutput'
        )
        normal_height_node.setInputPropertyValueFromId(
            'relief_balance',
            SDValueFloat.sNew(1)
        )
        normal_height_node.setInputPropertyValueFromId(
            'height_normalize',
            SDValueBool.sNew(True)
        )

        # Move nodes for user
        disp_output.setPosition(height_pos)
        normal_intensity_node.setPosition(
            normal_output.getPosition()
        )
        normal_output.setPosition(
            float2(normal_output.getPosition().x + 150, trans.getPosition().y)
        )
        normal_height_node.setPosition(
            float2(height_pos.x - 150, height_pos.y)
        )

    def output_setup(self, comp_graph):
        """Setup output nodes for naming convention"""
        output_dictionary = {
            "Base Color": "BASE",
            "Metallic": "MTL",
            "Displacement": "DISP",
            "Normal": "NRM",
            "Roughness": "ROUGH",
            "Opacity": "ALPHA"
        }
        for node in comp_graph.getOutputNodes():
            node_label = node.getDefinition().getLabel()
            if node_label in output_dictionary.keys():
                node.setAnnotationPropertyValueFromId(
                    'label',
                    SDValueString.sNew(output_dictionary[node_label])
                )


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
