import sys
import os
import importlib # For more controlled mocking if needed later
import pytest
import importlib.util

# --- Configuration ---
# Assuming 'Validator' is a package directory.
# This script aims to test importing 'Validator'.
# For 'import Validator' to work, the directory *containing* 'Validator' must be in sys.path.

SCRIPT_LOCATION_DIR = os.path.dirname(os.path.abspath(__file__))
# If this script is in 'z:/Python/', then PARENT_OF_VALIDATOR_PACKAGE_DIR is 'z:/Python/'.
# If this script is in 'z:/Python/Validator/', then PARENT_OF_VALIDATOR_PACKAGE_DIR is 'z:/Python/'.
if os.path.basename(SCRIPT_LOCATION_DIR).lower() == "validator":
    # Script is likely inside the Validator package, so parent is one level up
    PARENT_OF_VALIDATOR_PACKAGE_DIR = os.path.abspath(os.path.join(SCRIPT_LOCATION_DIR, ".."))
else:
    # Script is likely in the same directory as the Validator package folder (e.g., z:/Python/)
    PARENT_OF_VALIDATOR_PACKAGE_DIR = SCRIPT_LOCATION_DIR

if PARENT_OF_VALIDATOR_PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PARENT_OF_VALIDATOR_PACKAGE_DIR)

print(f"--- Running Validator Import Test ---")
print(f"Script location directory: {SCRIPT_LOCATION_DIR}")
print(f"Deduced parent directory of 'Validator' package (added to sys.path): {PARENT_OF_VALIDATOR_PACKAGE_DIR}")
print(f"Python version: {sys.version}")
print(f"Effective sys.path for import 'Validator' (first few entries): {sys.path[:5]}")
print(f"Target Validator package location: {os.path.join(PARENT_OF_VALIDATOR_PACKAGE_DIR, 'Validator')}")
print("-----\n")

# Mock Nuke and PySide6 for basic import testing if not available
# This allows testing the Python-level imports and file access without a full Nuke/Qt environment.
try:
    import nuke
    print("INFO: Genuine 'nuke' module imported.")
except ImportError:
    print("INFO: 'nuke' module not found. Mocking for import tests.")
    class MockNukeModule:
        def __init__(self):
            self.GUI = False
            self.EXE_PATH = "/fake/nuke/path"
            self.NUKE_VERSION_MAJOR = 15 # Example version
            self.callbacks = self._MockCallbacks()
            self.Node = self._MockNode # Expose _MockNode as nuke.Node

        def critical(self, msg): print(f"NUKE_CRITICAL_MOCK: {msg}")
        def error(self, msg): print(f"NUKE_ERROR_MOCK: {msg}")
        def warning(self, msg): print(f"NUKE_WARNING_MOCK: {msg}")
        def ask(self, msg): print(f"NUKE_ASK_MOCK: '{msg}' - Answering False"); return False
        def message(self, msg): print(f"NUKE_MESSAGE_MOCK: {msg}")
        def allNodes(self): return []
        def selectedNodes(self): return []
        def toNode(self, name): return None # Or a MockNode instance
        def root(self): return self._MockRootNode()
        def pluginPath(self): return [] # Mock pluginPath

        class _MockKnob:
            def __init__(self, name="mock_knob", value=None): self._name = name; self._value = value
            def value(self): return self._value
            def setValue(self, val): self._value = val
            def name(self): return self._name # For format().name()
            def hasExpression(self): return False
            def hasError(self): return False
            def expression(self): return ""

        class _MockNode:
            def __init__(self, name="mock_node", node_class="MockClass"):
                self._name = name
                self._class = node_class
                self._knobs = {'file': MockNukeModule._MockKnob('file', ''), 'colorspace': MockNukeModule._MockKnob('colorspace', 'sRGB'), 'format': MockNukeModule._MockKnob('format', self._MockFormat())}
            def name(self): return self._name
            def Class(self): return self._class
            def knob(self, name): return self._knobs.get(name)
            def __getitem__(self, key): return self.knob(key) # Allow node['knob_name']
            def input(self, i): return None
            def firstFrame(self): return 1
            def lastFrame(self): return 100
        
        class _MockRootNode(_MockNode):
            def __init__(self):
                super().__init__("root", "Root")
                self._knobs['first_frame'] = MockNukeModule._MockKnob('first_frame', 1)
                self._knobs['last_frame'] = MockNukeModule._MockKnob('last_frame', 100)

        class _MockFormat: # For knob('format').value().name()
            def name(self): return "HD_1080"

        class _MockCallbacks:
            def filenameFilter(self, path, frame=None): return path # Simplistic mock

    sys.modules['nuke'] = MockNukeModule()
    nuke = sys.modules['nuke']

try:
    from PySide6 import QtWidgets, QtCore, QtGui
    print("INFO: Genuine 'PySide6' modules imported.")
except ImportError:
    print("INFO: 'PySide6' not found. Mocking for import tests.")
    class MockQtMeta(type):
        def __getattr__(cls, name):
            if name.startswith("Q"): return MockQtWidget # Return base mock for any QClass
            raise AttributeError(name)

    class MockQtWidget(metaclass=MockQtMeta):
        def __init__(self, parent=None, *args, **kwargs): self._parent = parent; self._visible=False
        def show(self): self._visible=True; print(f"MOCK {self.__class__.__name__}.show() called")
        def setWindowTitle(self, title): pass
        def setMinimumSize(self, w, h): pass
        def setLayout(self, layout): pass
        def centralWidget(self): return None
        def setCentralWidget(self, widget): pass
        def addWidget(self, widget): pass
        def addLayout(self, layout): pass
        def addItem(self, item): pass
        def setItemWidget(self, item, widget): pass
        def clear(self): pass
        def setContentsMargins(self, *args): pass
        def setFixedSize(self, w, h): pass
        def setAlignment(self, align): pass
        def setPixmap(self, pixmap): pass
        def setStyleSheet(self, sheet): pass
        def setWordWrap(self, wrap): pass
        def setText(self, text): pass
        def setValue(self, val): pass
        def setRange(self, min_val, max_val): pass
        def setFixedWidth(self, w): pass
        def setVisible(self, visible): self._visible=visible
        def isVisible(self): return self._visible
        def deleteLater(self): print(f"MOCK {self.__class__.__name__}.deleteLater() called")
        def raise_(self): pass
        def activateWindow(self): pass
        def sizeHint(self): return MockQtCoreModule.QSize(0,0) if 'MockQtCoreModule' in sys.modules and hasattr(sys.modules['MockQtCoreModule'], 'QSize') else (0,0)
        def currentText(self): return "mock_dropdown_item"
        def addItems(self, items): pass
        def setCurrentIndex(self, idx): pass
        def setCurrentText(self, text): pass
        def model(self): return None # Critical for _populate_combobox
        def setPlaceholderText(self, text): pass
        def text(self): return ""
        def isChecked(self): return False
        def setChecked(self, state): pass
        def setSizes(self, sizes): pass
        def setAttribute(self, attr, on=True): pass
        def clicked(self): return self._MockSignal()
        def activated(self): return self._MockSignal()
        def currentTextChanged(self): return self._MockSignal()
        def count(self): return 0 # For QFormLayout
        def takeAt(self, index): return self._MockLayoutItem() # For QFormLayout.takeAt()
        def statusBar(self): return self._MockStatusBar()
        class _MockSignal:
            def connect(self, slot): pass
        class _MockLayoutItem: # For QFormLayout.takeAt()
            def widget(self): return None
        class _MockStatusBar:
            def showMessage(self, msg, timeout=0): print(f"MOCK StatusBar: {msg}")

    class MockQtWidgetsModule:
        QWidget = MockQtWidget
        QMainWindow = MockQtWidget
        QDialog = MockQtWidget
        QLabel = MockQtWidget
        QPushButton = MockQtWidget
        QListWidget = MockQtWidget
        QListWidgetItem = lambda: None # Mock QListWidgetItem as a simple object
        QProgressBar = MockQtWidget
        QSplitter = MockQtWidget
        QTabWidget = MockQtWidget
        QComboBox = MockQtWidget
        QLineEdit = MockQtWidget
        QCheckBox = MockQtWidget
        QFormLayout = MockQtWidget
        QHBoxLayout = MockQtWidget
        QVBoxLayout = MockQtWidget
        QGroupBox = MockQtWidget
        QApplication = None
        QMessageBox = MockQtWidget # For critical, warning etc.
        @staticmethod
        def QApplication(args_or_instance=None):
            if MockQtWidgetsModule.QApplication is None or isinstance(args_or_instance, list):
                class MockApp:
                    def __init__(self, args=None): pass
                    @staticmethod
                    def instance(): return MockQtWidgetsModule.QApplication
                    def exec_(self): print("MOCK App.exec_() called"); return 0
                    exec = exec_
                MockQtWidgetsModule.QApplication = MockApp()
            return MockQtWidgetsModule.QApplication

    class MockQtCoreModule:
        Qt = type('Qt', (), {'Horizontal': 1, 'AlignCenter': 0x0084, 'WA_DeleteOnClose': 121}) # Mock Qt namespace & attributes
        QSize = type('QSize', (), lambda w,h: (w,h))
        Signal = lambda *args, **kwargs: MockQtWidget._MockSignal() # Mock Signal
        Slot = lambda *args, **kwargs: (lambda func: func) # Mock Slot as a simple decorator

    class MockQtGuiModule:
        QPixmap = lambda w=0, h=0: None
        QColor = lambda *args: None
        QFont = lambda: None

    sys.modules['PySide6.QtWidgets'] = MockQtWidgetsModule
    sys.modules['PySide6.QtCore'] = MockQtCoreModule
    sys.modules['PySide6.QtGui'] = MockQtGuiModule
    QtWidgets = MockQtWidgetsModule
    QtCore = MockQtCoreModule
    QtGui = MockQtGuiModule

print("-----\n")
test_results = {}

# Test 1: Importing the main package 'Validator'
try:
    import Validator
    test_results['import_Validator_package'] = "SUCCESS"
except Exception as e:
    test_results['import_Validator_package'] = f"FAILED: {e}"
print(f"Test 'import Validator': {test_results['import_Validator_package']}")

# Test 2: Calling Validator.launch_validator_for_nuke()
# This tests __init__.py's ability to import main_window and launch the UI (mocked)
if test_results.get('import_Validator_package') == "SUCCESS":
    try:
        print(f"\n--- Attempting to call Validator.launch_validator_for_nuke() ---")
        Validator.launch_validator_for_nuke() # This will use mocked QApplication if PySide6 is mocked
        test_results['call_launch_validator_for_nuke'] = "SUCCESS (function called, check output for internal errors/debug info from RulesEditorWidget)"
    except Exception as e:
        import traceback
        test_results['call_launch_validator_for_nuke'] = f"FAILED: {e}\n{traceback.format_exc()}"
else:
    test_results['call_launch_validator_for_nuke'] = "SKIPPED (Validator package import failed)"
print(f"Test 'Validator.launch_validator_for_nuke()': {test_results['call_launch_validator_for_nuke']}")

# Test 3: Direct import and instantiation of nuke_validator.NukeValidator
try:
    from Validator import nuke_validator
    test_results['import_nuke_validator_module'] = "SUCCESS"
    try:
        rules_yaml_path = os.path.join(PARENT_OF_VALIDATOR_PACKAGE_DIR, "Validator", "rules.yaml")
        if not os.path.exists(rules_yaml_path):
             print(f"WARNING: rules.yaml not found at {rules_yaml_path} for NukeValidator instantiation test.")
             validator_instance = nuke_validator.NukeValidator()
        else:
            print(f"Attempting to instantiate NukeValidator with rules: {rules_yaml_path}")
            validator_instance = nuke_validator.NukeValidator(rules_file=rules_yaml_path)
        test_results['instantiate_NukeValidator'] = "SUCCESS"
    except Exception as e:
        test_results['instantiate_NukeValidator'] = f"FAILED: {e}"
except Exception as e:
    test_results['import_nuke_validator_module'] = f"FAILED: {e}"
    test_results['instantiate_NukeValidator'] = "SKIPPED (nuke_validator module import failed)"
print(f"Test 'from Validator import nuke_validator': {test_results['import_nuke_validator_module']}")
print(f"Test 'instantiate NukeValidator': {test_results['instantiate_NukeValidator']}")

# Test 4: Direct import and instantiation of nuke_validator_ui.RulesEditorWidget
try:
    from Validator import nuke_validator_ui
    test_results['import_nuke_validator_ui_module'] = "SUCCESS"
    try:
        # Ensure a QApplication (mocked or real) exists before creating a QWidget
        if QtWidgets.QApplication.instance() is None:
            print("INFO: Test 4 - Creating mock QApplication instance for RulesEditorWidget direct instantiation.")
            QtWidgets.QApplication([]) # Create a mock app instance

        print(f"\n--- Attempting to instantiate RulesEditorWidget directly ---")
        # This will trigger loading of rules.yaml and rules_dropdowns.yaml from its own directory
        # The debug prints for dropdowns.yaml should appear here.
        editor_widget = nuke_validator_ui.RulesEditorWidget()
        test_results['instantiate_RulesEditorWidget'] = "SUCCESS (check output for DEBUG prints regarding dropdowns.yaml)"
    except Exception as e:
        import traceback
        test_results['instantiate_RulesEditorWidget'] = f"FAILED: {e}\n{traceback.format_exc()}"
except Exception as e:
    test_results['import_nuke_validator_ui_module'] = f"FAILED: {e}"
    test_results['instantiate_RulesEditorWidget'] = "SKIPPED (nuke_validator_ui module import failed)"
print(f"Test 'from Validator import nuke_validator_ui': {test_results['import_nuke_validator_ui_module']}")
print(f"Test 'instantiate RulesEditorWidget': {test_results['instantiate_RulesEditorWidget']}")

print("\n--- Test Summary ---")
for test_name, result in test_results.items():
    # Print only the first line of the result for a cleaner summary
    summary_line = result.splitlines()[0] if isinstance(result, str) else str(result)
    print(f"{test_name}: {summary_line}")

print("\n--- End of Validator Import Test ---")

MODULES = [
    # skip local files as modules
    'PySide6.QtWidgets',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtSvg',
    'PySide6.QtSvgWidgets',
    'yaml',
    'json',
]

@pytest.mark.parametrize('module_name', MODULES)
def test_import_module(module_name):
    try:
        importlib.import_module(module_name)
    except ImportError as e:
        pytest.fail(f"Failed to import {module_name}: {e}")

# nuke is only available in Nuke environment, so we check it optionally

def test_import_nuke_optional():
    try:
        importlib.import_module('nuke')
    except ImportError:
        pass  # Acceptable if not in Nuke environment

LOCAL_MODULES = [
    "main_window.py",
    "nuke_validator_ui.py",
    "nuke_validator.py",
]

@pytest.mark.parametrize('filename', LOCAL_MODULES)
def test_import_local_module(filename):
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    path = os.path.join(os.path.dirname(__file__), filename)
    module_name = os.path.splitext(filename)[0]
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        pytest.fail(f"Failed to import {filename}: {e}")