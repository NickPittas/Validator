import os
import sys
from PySide6 import QtWidgets
from nuke_validator_ui import RulesEditorWidget

# Mock the nuke module
class MockNuke:
    def __init__(self):
        self.GUI = True
    
    def root(self):
        return MockNode()

class MockNode:
    def name(self):
        return "test_script.nk"

# Add mock nuke to sys.modules
sys.modules['nuke'] = MockNuke()

def test_save_as_new_yaml():
    app = QtWidgets.QApplication(sys.argv)
    
    # Create a simple parent window with the refresh_yaml_selector method
    class MockMainWindow(QtWidgets.QMainWindow):
        def refresh_yaml_selector(self):
            print("refresh_yaml_selector called")
        
        def __init__(self):
            super().__init__()
            self.yaml_selector_combo = QtWidgets.QComboBox()
            self.yaml_selector_combo.addItem("rules.yaml")
    
    main_window = MockMainWindow()
    
    # Create the RulesEditorWidget with the mock main window as parent
    rules_editor = RulesEditorWidget(parent=main_window)
    
    # Set up the rules_yaml_path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    rules_editor.rules_yaml_path = os.path.join(script_dir, "rules.yaml")
    
    # Load the rules
    rules_editor.load_rules_from_yaml()
    
    # Test the _on_save_as_new_yaml method
    # We'll monkey patch the QFileDialog.getSaveFileName method to return a predefined path
    original_getSaveFileName = QtWidgets.QFileDialog.getSaveFileName
    
    def mock_getSaveFileName(*args, **kwargs):
        test_path = os.path.join(script_dir, "test_save_as_new.yaml")
        return test_path, "YAML Files (*.yaml)"
    
    QtWidgets.QFileDialog.getSaveFileName = mock_getSaveFileName
    
    try:
        # Call the method
        print("Calling _on_save_as_new_yaml...")
        rules_editor._on_save_as_new_yaml()
        
        # Check if the file was created
        test_path = os.path.join(script_dir, "test_save_as_new.yaml")
        if os.path.exists(test_path):
            print(f"Success! File created at: {test_path}")
            # Clean up the test file
            os.remove(test_path)
            print("Test file removed.")
        else:
            print(f"Error: File not created at: {test_path}")
    
    finally:
        # Restore the original method
        QtWidgets.QFileDialog.getSaveFileName = original_getSaveFileName

if __name__ == "__main__":
    test_save_as_new_yaml()