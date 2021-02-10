from functools import partial
import weakref
from pathlib import Path

import sd
from sd.api.sdvaluefloat3 import SDValueFloat3
from sd.api.sdbasetypes import float3
from sd.api.sdproperty import SDPropertyCategory

from PySide2 import QtGui, QtWidgets


class PluginToolBar(QtWidgets.QToolBar):
    __toolbarList = {}

    def __init__(self, graphViewID, uiMgr):
        super(PluginToolBar, self).__init__(parent=uiMgr.getMainWindow())

        self.setObjectName('output_adjust_plugin_toolbar')

        self.__graphViewID = graphViewID
        self.__uiMgr = uiMgr

        current_dir = Path(__file__).parent
        icon_path = Path.joinpath(current_dir, r'icons\output_adjust.png')

        action = self.addAction(
            QtGui.QIcon(icon_path.as_posix()),
            "output_adjust"
        )
        action.setToolTip(
            "Adjust the physical size of all packages in the explorer"
        )
        action.triggered.connect(self.output_adjust)

        self.__toolbarList[graphViewID] = weakref.ref(self)
        self.destroyed.connect(
            partial
            (PluginToolBar.__onToolbarDeleted,
             graphViewID=graphViewID
             )
        )

    def tooltip(self):
        return self.tr("Custom Plugins")

    def output_adjust(self):

        sd_context = sd.getContext()
        sd_application = sd_context.getSDApplication()
        package_manager = sd_application.getPackageMgr()

        adjust_list = []

        for pkg in package_manager.getPackages():
            file_path = pkg.getFilePath()
            if 'Allegorithmic/Substance' not in file_path:
                adjust_list.append(file_path)

        # Iterate through each package
        for package_file_path in adjust_list:
            group = package_manager.getUserPackageFromFilePath(
                package_file_path)
            name = Path(package_file_path).stem

            # Select substance in package
            comp_graph = group.findResourceFromUrl(name)
            comp_graph.compute()

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
            # phyical size is measured as a sdValuefloat3
            # output size isn't stored as absolute, is set as a power of 2.
            # i.e. in x:12, y:12, this is 4096 x 4096 because 2 ^ 12 = 4096

            tex_size = round(((2 ** output_x) / 236.22), 2)
            new_size = SDValueFloat3.sNew(float3(tex_size, tex_size, 0))

            comp_graph.setPropertyValue(physical_size, new_size)

        message = QtWidgets.QMessageBox()
        message.setWindowTitle('Physical size changed')
        message.setText(f'Changed physical size to {new_size.get()}')
        message.exec_()

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
