from maya import cmds
from maya import OpenMaya as om
from maya import OpenMayaUI as omui

try:
    from PySide2.QtCore import *
    from PySide2.QtGui import *
    from PySide2.QtWidgets import *
    from PySide2 import __version__
    from shiboken2 import wrapInstance
except ImportError:
    from PySide.QtCore import *
    from PySide.QtGui import *
    from PySide import __version__
    from shiboken import wrapInstance


def maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(long(ptr), QWidget)


class CustomTableWidget(QTableWidget):

    def __init__(self, parent=None):
        super(CustomTableWidget, self).__init__(parent)

        self.sel_item = None
        self.enter_key_pressed = False

    def set_sel_item_text(self):
        if self.sel_item:
            if self.sel_item.row() != 0:
                self.blockSignals(True)
                text = self.sel_item.text()
                self.sel_item.setText("  {}".format(text))
                self.blockSignals(False)
                self.sel_item = None
    
    def set_item_editable(self):
        self.selected_items = self.selectedItems()

        if self.selected_items:
            self.sel_item = self.selected_items[-1]

            self.blockSignals(True)
            text = self.sel_item.text().lstrip()
            self.sel_item.setText(text)
            self.blockSignals(False)

            self.setEditTriggers(QAbstractItemView.AllEditTriggers)
            self.setCurrentItem(self.horizontalHeaderItem(0))
            self.setCurrentItem(self.sel_item)
            for item in self.selected_items:
                self.setItemSelected(item, True)

        self.setEditTriggers(QAbstractItemView.DoubleClicked)

    def closeEditor(self, editor, hint):
        if hint in (QItemDelegate.EditNextItem, QItemDelegate.EditPreviousItem):
            new_hint = QItemDelegate.NoHint
        else:
            new_hint = hint

        super(CustomTableWidget, self).closeEditor(editor, new_hint)

        _row = self.currentIndex().row()

        if hint == QItemDelegate.EditNextItem:
            index = self.moveCursor(self.MoveDown, Qt.NoModifier)
        elif hint == QItemDelegate.EditPreviousItem:
            index = self.moveCursor(self.MoveUp, Qt.NoModifier)
        else:
            return

        row = index.row()
        column = index.column()

        if column == 0:
            column = 1

            if row == 0:
                row = self.rowCount() - 1

        else:
            if _row == row:
                row = 1

        item = self.item(row, column)

        self.clearSelection()
        self.set_sel_item_text()
        self.setCurrentItem(item)
        self.set_item_editable()
    
    def keyPressEvent(self, event):
        super(CustomTableWidget, self).keyPressEvent(event)

        selected_items = self.selected_items

        key = event.key()

        if key in (Qt.Key_Enter, Qt.Key_Return):
            if key == Qt.Key_Enter:
                self.enter_key_pressed = True

            self.setCurrentItem(self.horizontalHeaderItem(0))

            if self.sel_item is not None:
                text = self.sel_item.text()

                self.blockSignals(True)
                self.sel_item.setText("")
                self.blockSignals(False)

                self.sel_item.setText(text)

            for item in selected_items:
                    self.setItemSelected(item, True)

            if self.enter_key_pressed:
                self.set_item_editable()
                self.enter_key_pressed = False

    def mousePressEvent(self, event):
        super(CustomTableWidget, self).mousePressEvent(event)

        if self.itemAt(event.pos()) is None:
            self.clearSelection()
            self.setFocus()
            self.clearFocus()

        self.set_sel_item_text()

    def mouseReleaseEvent(self, event):
        super(CustomTableWidget, self).mouseReleaseEvent(event)

        self.set_item_editable()


class ChannelBox(QWidget):

    VERSION = "0.0.1"

    TITLE = "Channel Box"

    NAME_FONT = QFont("Gulim", 8, QFont.Bold)
    ATTR_FONT = QFont("Gulim")

    VALUE_BG_COLOR = QColor(43, 43, 43)
    VIS_BG_COLOR = QColor(51, 51, 51)

    TABLE_WGT_STYLE_SHEET = """
        QTableWidget {
            background-color: rgb(68, 68, 68);
            border: none;
            padding-left: 6px;
            padding-top: 2px;
            padding-right: 1px;
        }
        QTableWidget::item {
            color: rgb(187, 187, 187);
        }
        QTableWidget::item:selected {
            color: white;
        }
        QTableWidget::item:focus {
            border-width: 1px;
            border-style: solid;
        }
    """

    def __init__(self, parent=maya_main_window()):
        super(ChannelBox, self).__init__(parent)
        
        self.setWindowTitle(ChannelBox.TITLE)
        self.setWindowFlags(Qt.WindowType.Window)
        self.setMinimumSize(250, 350)

        self.sel_changed_callback_ids = []
        self.attr_changed_callback_ids = []

        self.init_ui()
        self.installEventFilter(self)

    def init_ui(self):
        # WIDGET
        self.table_wgt = CustomTableWidget()
        self.table_wgt.setColumnCount(2)
        self.table_wgt.setColumnWidth(1, 80)
        v_header = self.table_wgt.verticalHeader()
        v_header.setMinimumSectionSize(18)
        v_header.setVisible(False)
        h_header = self.table_wgt.horizontalHeader()
        h_header.setSectionResizeMode(0, QHeaderView.Stretch)
        h_header.setVisible(False)
        self.table_wgt.setFocusPolicy(Qt.NoFocus)
        self.table_wgt.setStyleSheet(ChannelBox.TABLE_WGT_STYLE_SHEET)

        # LAYOUT
        self.main_layout = QStackedLayout(self)
        self.main_layout.addWidget(QWidget())
        self.main_layout.addWidget(self.table_wgt)

        # CONNECTION
        self.table_wgt.itemChanged.connect(self.on_item_changed)

    def block_item_changed_signal(func):
        def wrapper(self, *args, **kwargs):
            self.table_wgt.itemChanged.disconnect(self.on_item_changed)
            func(self, *args, **kwargs)
            self.table_wgt.itemChanged.connect(self.on_item_changed)
        return wrapper

    def block_attr_changed_callback(func):
        def wrapper(self, *args, **kwargs):
            self.delete_attr_changed_callback()
            func(self, *args, **kwargs)
            self.create_attr_changed_callback()
        return wrapper

    @block_attr_changed_callback
    @block_item_changed_signal
    def on_item_changed(self, item):
        self.table_wgt.sel_item = None

        row = item.row()
        col = item.column()

        text = item.text().lstrip()

        cmds.undoInfo(openChunk=True)

        if row == 0:
            try:
                cmds.rename(self.sel, text)
            except:
                pass
            
            self.set_name_item_text()

        elif col == 1:
            for sel_item in reversed(self.table_wgt.selected_items):
                if sel_item.row() == 0:
                    continue

                attr = sel_item.data(Qt.UserRole)
                try:
                    if attr == "visibility":
                        if text in ("1", "on", "yes", "true"):
                            value = True
                        elif text in ("0", "off", "no", "false"):
                            value = False
                        else:
                            raise Exception
                    else:
                        value = float(text)
                    
                    for uuid in self.sels:
                        sel = cmds.ls(uuid, l=True)[0]
                        attr_name = "{}.{}".format(sel, attr)
                        cmds.setAttr(attr_name, value)
                except:
                    break
                finally:
                    self.set_value_item_text(sel_item)

        cmds.undoInfo(closeChunk=True)

    @block_item_changed_signal
    def refresh(self):
        self.sels = cmds.ls(sl=True, uuid=True, tr=True)
        
        if not self.sels:
            self.main_layout.setCurrentIndex(0)
            self.table_wgt.sel_item = None
            return
        
        self.main_layout.setCurrentIndex(1)
        
        self.table_wgt.clearSelection()
        self.table_wgt.setRowCount(0)

        self.create_name_item()
        self.set_name_item_text()

        attr_list = cmds.listAttr(self.sel, k=True, s=True)
        try:
            idx = attr_list.index("visibility")
        except:
            pass
        else:
            attr_list.append(attr_list.pop(idx))

        self.table_wgt.setRowCount(len(attr_list) + 1)

        for row, attr in enumerate(attr_list, 1):
            self.table_wgt.setRowHeight(row, 18)
            item = self.create_value_item(row, attr)
            self.set_value_item_text(item)

    @block_attr_changed_callback
    def sel_changed_refresh(self, *args):
        self.refresh()
    
    def create_name_item(self):
        self.table_wgt.setRowCount(1)
        self.table_wgt.setSpan(0, 0, 1, 2)
        self.table_wgt.setRowHeight(0, 20)
        self.name_item = QTableWidgetItem()
        self.name_item.setTextAlignment(Qt.AlignBottom)
        self.name_item.setFont(ChannelBox.NAME_FONT)
        self.table_wgt.setItem(0, 0, self.name_item)
    
    def set_name_item_text(self):
        self.sel = cmds.ls(self.sels[-1], l=True)[0]
        name = self.sel.rsplit("|", 1)[-1]
        if len(self.sels) > 1:
            name = "{} . . .".format(name)
        self.name_item.setText(name)
    
    def create_attr_item(self, row, attr):
        nice_name = cmds.attributeName("{}.{}".format(self.sel, attr))
        item = QTableWidgetItem("{} ".format(nice_name))
        item.setFont(ChannelBox.ATTR_FONT)
        item.setFlags(item.flags() ^ Qt.ItemIsEditable)
        item.setTextAlignment(Qt.AlignRight | Qt.AlignBottom)
        self.table_wgt.setItem(row, 0, item)

    def create_value_item(self, row, attr):
        self.create_attr_item(row, attr)
        item = QTableWidgetItem()
        item.setData(Qt.UserRole, attr)
        color = ChannelBox.VALUE_BG_COLOR
        if attr == "visibility":
            color = ChannelBox.VIS_BG_COLOR
        item.setBackgroundColor(color)
        self.table_wgt.setItem(row, 1, item)

        return item
    
    def set_value_item_text(self, item):
        attr = item.data(Qt.UserRole)
        value = cmds.getAttr("{}.{}".format(self.sel, attr))

        if isinstance(value, bool):
            if value:
                value = "on"
            else:
                value = "off"
        else:
            value = round(value, 3)
            if value.is_integer():
                value = int(value)
        
        item.setText("  {}".format(str(value)))
    
    def create_sel_changed_callback(self):
        self.sel_changed_callback_ids.append(
            om.MEventMessage.addEventCallback("SelectionChanged", self.sel_changed_refresh)
        )

    def delete_sel_changed_callback(self):
        for i in self.sel_changed_callback_ids:
            om.MMessage.removeCallback(i)
        self.sel_changed_callback_ids = []

    def on_attr_changed(self, msg, plug, otherplug, clientData):
        if msg & om.MNodeMessage.kAttributeSet:
            self.refresh()
    
    def on_name_changed(self, obj, prev_name, clientData):
        self.refresh()
 
    def create_attr_changed_callback(self):
        if not self.sels:
            return

        sel_list = om.MSelectionList()
        om.MGlobal.getSelectionListByName(self.sel, sel_list)
        obj = om.MObject()
        sel_list.getDependNode(0, obj)
        self.attr_changed_callback_ids.append(
            om.MNodeMessage.addAttributeChangedCallback(obj, self.on_attr_changed)
        )
        self.attr_changed_callback_ids.append(
            om.MNodeMessage.addNameChangedCallback(obj, self.on_name_changed)
        )

    def delete_attr_changed_callback(self):
        for i in self.attr_changed_callback_ids:
            om.MNodeMessage.removeCallback(i)
        self.attr_changed_callback_ids = []

    def on_window_deactivated(self):
        if not self.table_wgt.sel_item:
            return

        self.table_wgt.setCurrentItem(self.table_wgt.horizontalHeaderItem(0))
        for item in self.table_wgt.selected_items:
                self.table_wgt.setItemSelected(item, True)
        self.table_wgt.set_sel_item_text()

    def showEvent(self, event):
        self.resize(250, 350)

        self.create_sel_changed_callback()
        self.sel_changed_refresh()

    def closeEvent(self, event):
        self.delete_sel_changed_callback()
        self.delete_attr_changed_callback()
    
    def keyPressEvent(self, event):
        super(ChannelBox, self).keyPressEvent(event)
        event.accept()

    def eventFilter(self, object, event):
        if event.type() == QEvent.WindowDeactivate:
            self.on_window_deactivated()

        return False


def show_ui():
    global channel_box

    try:
        channel_box.close()
        channel_box.deleteLater()
    except:
        pass

    channel_box = ChannelBox()
    channel_box.show()


if __name__ == "__main__":
    show_ui()