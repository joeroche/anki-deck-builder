import ctypes,json,sys,os
if "--background" in sys.argv:
 os.environ["QT_MAC_DISABLE_FOREGROUND_APPLICATION_TRANSFORM"]="1"
from pathlib import Path
from PyQt6.QtWidgets import QApplication,QTableWidget,QTableWidgetItem,QAbstractItemView
from PyQt6 import sip
from PyQt6.QtCore import Qt,QEvent
import PyQt6
app=QApplication([])
root=Path(__file__).resolve().parent;guard=ctypes.CDLL(str(root/'qt_ownership_guard.dylib'))
if '--patched' in sys.argv:
 assert guard.install_qt_ownership_guard()==0
qt=ctypes.CDLL(str(Path(PyQt6.__file__).parent/'Qt6/lib/QtGui.framework/Versions/A/QtGui'))
query=getattr(qt,'_ZN11QAccessible24queryAccessibleInterfaceEP7QObject');query.argtypes=[ctypes.c_void_p];query.restype=ctypes.c_void_p
unique=getattr(qt,'_ZN11QAccessible8uniqueIdEP20QAccessibleInterface');unique.argtypes=[ctypes.c_void_p];unique.restype=ctypes.c_uint32
lookup=getattr(qt,'_ZN11QAccessible19accessibleInterfaceEj');lookup.argtypes=[ctypes.c_uint32];lookup.restype=ctypes.c_void_p
activate=getattr(qt,'_ZN11QAccessible9setActiveEb');activate.argtypes=[ctypes.c_bool];activate(True)
probe=ctypes.CDLL(str(root/'native_probe.dylib'));probe.qt_guard_probe.argtypes=[ctypes.c_uint32,ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.c_ulong)]
table=QTableWidget(3,2);table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
for row in range(3):
 for col in range(2):table.setItem(row,col,QTableWidgetItem(f'row{row}col{col}'))
table.resize(1000,500)
if "--background" in sys.argv:
 table.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating,True);table.move(-10000,-10000)
table.show();app.processEvents();tableid=unique(query(sip.unwrapinstance(table)));records=[]
for cols in [2,3,2,4,2]:
 table.setColumnCount(cols)
 for row in range(3):
  for col in range(cols):table.setItem(row,col,QTableWidgetItem(f'row{row}col{col}'))
 for row in range(3):
  table.clearSelection();table.selectRow(row);app.processEvents();count=ctypes.c_ulong();roles=ctypes.c_ulong()
  assert probe.qt_guard_probe(tableid,ctypes.byref(count),ctypes.byref(roles))==0
  record=dict(columns=cols,row=row,selected_count=count.value,cell_roles=roles.value,table_id_alive=bool(lookup(tableid)));records.append(record)
  assert record['table_id_alive'] and count.value==cols and roles.value==cols,record
table.close();table.deleteLater();app.sendPostedEvents(None,QEvent.Type.DeferredDelete);app.processEvents();assert sip.isdeleted(table)
print(json.dumps(dict(patched='--patched' in sys.argv,checks=records),indent=2))
