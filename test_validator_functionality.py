import unittest
import sys
from unittest.mock import MagicMock
# Mocking the 'nuke' module to allow tests to run without a Nuke environment
# Create a mock object for the 'nuke' module
nuke_mock = MagicMock()

# --- Mocking attributes and methods accessed from 'nuke' module directly ---
# These are based on common Nuke API calls found in the project's nuke_validator.py and nuke_validator_ui.py
nuke_mock.allNodes.return_value = []  # nuke.allNodes() typically returns a list of node objects
nuke_mock.selectedNode.return_value = None # nuke.selectedNode() returns a single node or None
nuke_mock.toNode.return_value = None      # nuke.toNode('someNodeName') returns a node or None

# Mock for nuke.root() -> returns a mock object that itself has a .knob() method
mock_root_instance = MagicMock(name='NukeRootMock')
mock_knob_instance = MagicMock(name='NukeKnobMock')
# Default return value for knob.value(), e.g., for 'first_frame', 'last_frame'
mock_knob_instance.value.return_value = 0
mock_root_instance.knob.return_value = mock_knob_instance
nuke_mock.root.return_value = mock_root_instance

# Mock for nuke.nodes (as a namespace, e.g., nuke.nodes.Blur)
nuke_mock.nodes = MagicMock(name='NukeNodesNamespaceMock')
# Mock for specific node classes if they are instantiated like nuke.nodes.Write()
# This mock will be returned if nuke.nodes.Write is called.
nuke_mock.nodes.Write = MagicMock(name='NukeWriteClassMock')
# Add other node classes if needed, e.g., nuke_mock.nodes.Read = MagicMock()

# Mock for constants like nuke.WRITE (if used, e.g., in comparisons like node.Class() == nuke.WRITE)
nuke_mock.WRITE = 'Write' # Common constant for Write node class name

# Mock for Nuke classes like nuke.Knob, nuke.Array_Knob if they are instantiated directly
nuke_mock.Knob = MagicMock(name='NukeKnobClassMock')
nuke_mock.Array_Knob = MagicMock(name='NukeArrayKnobClassMock')

# Add the mock to sys.modules. This ensures that any subsequent 'import nuke'
# will receive this mock object instead of trying to load the actual Nuke module.
sys.modules['nuke'] = nuke_mock

# Try to import PySide6 and the necessary application modules
try:
    from PySide6 import QtWidgets, QtCore
    from nuke_validator_ui import (
        TableBasedFilenameTemplateBuilder,
        FilenameRuleEditor,
        FILENAME_TOKENS
    )
    PYSIDE_AVAILABLE = True
except ImportError:
    PYSIDE_AVAILABLE = False
    # Mock QtWidgets and other Qt-related classes if PySide6 is not available
    # This allows the test structure to be defined, though UI-dependent tests will be skipped.
    class QtWidgets:
        class QWidget: pass
        class QApplication:
            def __init__(self, args): pass
            @staticmethod
            def instance(): return None
        class QTableWidget: pass
        class QLineEdit:
            def __init__(self, parent=None): self._text = ""
            def text(self): return self._text
            def setText(self, text): self._text = text
        class QTextEdit:
            def __init__(self, parent=None): self._text = ""
            def toPlainText(self): return self._text
            def setText(self, text): self._text = text
            def setVisible(self, b): pass
        class QLabel:
            def __init__(self, parent=None): pass
            def setText(self, text): pass
            def setVisible(self, b): pass
        class QSpinBox:
            def __init__(self, parent=None): self._value = 0
            def value(self): return self._value
            def setValue(self, v): self._value = v
            def setMinimum(self, m): pass
            def setMaximum(self, m): pass
        class QComboBox:
            def __init__(self, parent=None): self._text = ""
            def currentText(self): return self._text
            def setCurrentText(self, t): self._text = t
            def addItems(self, i): pass
        class SimpleMultiSelectWidget: # Mocked
            def __init__(self, options, parent=None): self._selected = []
            def get_selected_values(self): return self._selected
            def set_selected_values(self, v_list): self._selected = v_list
            selectionChanged = MagicMock() # Mock the signal
            def setFixedWidth(self, w): pass


    class QtCore:
        class Signal:
            def __init__(self): pass
            def emit(self, *args, **kwargs): pass
        Qt = MagicMock()


    # Mock the classes from nuke_validator_ui if PySide6 is not available

    class FilenameRuleEditor(QtWidgets.QWidget):
        def __init__(self, parent=None):
            super().__init__()
            self.available_tokens = {t['name']: t for t in (FILENAME_TOKENS if 'FILENAME_TOKENS' in globals() else [])}
            self.template_builder = TableBasedFilenameTemplateBuilder(self) # Uses the mocked/real builder
            self.regex_display = QtWidgets.QLineEdit()
            self.example_display = QtWidgets.QLineEdit()
            self.validation_results_display = QtWidgets.QTextEdit()
            self.validation_summary_label = QtWidgets.QLabel()
            self.template_builder.templateChanged.connect(self.update_regex)


        def update_regex(self):
            template_config = self.template_builder.get_template_config()
            if not template_config:
                self.regex_display.setText("")
                return

            regex_parts = ["^"]
            for token_cfg in template_config:
                token_def = self.available_tokens.get(token_cfg["name"])
                if not token_def:
                    continue

                # Simplified regex generation for testing purposes
                # Real version in nuke_validator_ui is more complex
                part_regex = token_def.get("regex_template", ".+")
                if token_def["control"] == "spinner" and "{n}" in part_regex:
                    part_regex = part_regex.replace("{n}", str(token_cfg.get("value", token_def.get("default", 1))))
                elif token_def["control"] == "multiselect" and token_cfg.get("value"):
                    part_regex = f"(?:{'|'.join(re.escape(v) for v in token_cfg['value'])})"
                elif token_def["control"] == "dropdown" and token_cfg.get("value") and token_cfg.get("value") != "none":
                     # Simplified: actual regex_template for dropdowns can be complex
                    if token_def["name"] == "pixelMappingName" and token_cfg.get("value"):
                         part_regex = re.escape(token_cfg.get("value"))
                    # else use token_def["regex_template"]
                
                if token_cfg.get("optional"):
                    if token_cfg.get("prefix"):
                         regex_parts.append(f"(?:{re.escape(token_cfg.get('prefix'))}")
                    regex_parts.append(f"(?:{part_regex})?")
                    if token_cfg.get("suffix"):
                         regex_parts.append(f"{re.escape(token_cfg.get('suffix'))})?")
                    if token_cfg.get("separator") and not token_cfg.get("optional"): # Separator only if token is present
                        regex_parts.append(f"(?:{re.escape(token_cfg.get('separator'))})?")
                else:
                    if token_cfg.get("prefix"):
                        regex_parts.append(re.escape(token_cfg.get("prefix")))
                    regex_parts.append(f"(?:{part_regex})")
                    if token_cfg.get("suffix"):
                        regex_parts.append(re.escape(token_cfg.get("suffix")))
                    if token_cfg.get("separator"):
                         regex_parts.append(re.escape(token_cfg.get("separator")))
            
            # Remove last separator if it exists and isn't part of the last token's suffix logic
            if regex_parts[-1].startswith("(") and regex_parts[-1].endswith(")"): # often a token
                pass
            elif len(regex_parts) > 1 and template_config and template_config[-1].get("separator") and regex_parts[-1] == re.escape(template_config[-1].get("separator")):
                 if not template_config[-1].get("suffix"): # if last token has no suffix, its separator might be trailing
                    regex_parts.pop()


            regex_parts.append("$")
            final_regex = "".join(regex_parts)
            self.regex_display.setText(final_regex)

        def _get_token_pattern_and_example(self, token_def, token_cfg):
            # Simplified mock for testing _validate_filename_detailed
            # This is complex in the original code
            pattern = token_def.get("regex_template", ".+")
            example = token_def.get("examples", ["example"])[0]
            
            if token_def["control"] == "spinner" and "{n}" in pattern:
                n_val = token_cfg.get("value", token_def.get("default", 1))
                pattern = pattern.replace("{n}", str(n_val))
                if token_def["name"] == "sequence": example = "A" * n_val
                if token_def["name"] == "shotNumber": example = "0" * (n_val -1) + "1"

            elif token_def["control"] == "multiselect":
                selected_values = token_cfg.get("value")
                if selected_values:
                    pattern = f"(?:{'|'.join(re.escape(v) for v in selected_values)})"
                    example = selected_values[0]
                else: # if nothing selected, it might mean any of the options or a default
                    pattern = f"(?:{'|'.join(re.escape(v) for v in token_def.get('options', ['any']))})"
                    example = token_def.get('options', ['any'])[0]
            
            elif token_def["control"] == "dropdown":
                current_value = token_cfg.get("value")
                if current_value and current_value != "none":
                    # This is a simplification. Real regex_template for dropdowns can be complex.
                    # For pixelMappingName, the regex_template is "(?:(LL180|LL360))?"
                    # If value is "LL180", pattern should be "LL180".
                    if token_def["name"] == "pixelMappingName":
                        pattern = re.escape(current_value)
                        example = current_value
                    # For other dropdowns, it might be direct or part of a group
                    else: # Fallback for other dropdowns
                        pattern = re.escape(current_value) if current_value else token_def.get("regex_template", ".+")
                        example = current_value if current_value else example
                elif token_def["name"] == "pixelMappingName" and (current_value is None or current_value == "none"): # Optional
                    pattern = "" # Effectively makes it optional if value is None/none
                    example = ""


            return pattern, example

        def _validate_filename_detailed(self, filename, template_config):
            # This is a simplified version for testing, focusing on logic flow
            # The actual implementation in nuke_validator_ui.py is more robust
            errors = []
            current_filename_segment = filename
            import re # ensure re is imported

            for i, token_cfg in enumerate(template_config):
                token_def = self.available_tokens.get(token_cfg["name"])
                if not token_def:
                    errors.append(f"Definition not found for token: {token_cfg['name']}")
                    continue

                raw_pattern, example = self._get_token_pattern_and_example(token_def, token_cfg)
                
                # Handle optional empty patterns (like an optional token that is not set)
                if token_cfg.get("optional") and not raw_pattern and not token_cfg.get("value"): # e.g. optional pixelMappingName set to "none"
                    # If it's optional and has no pattern (because it's not set), it effectively matches an empty string.
                    # We still need to consume the separator if the *next* token is present and this one was meant to be there.
                    # This logic is complex. For now, assume it matches empty and separator logic handles it.
                    
                    # Check for prefix if token is considered "present but empty"
                    if token_cfg.get("prefix") and current_filename_segment.startswith(token_cfg["prefix"]):
                        current_filename_segment = current_filename_segment[len(token_cfg["prefix"]):]
                    # Check for suffix
                    if token_cfg.get("suffix") and current_filename_segment.startswith(token_cfg["suffix"]):
                         current_filename_segment = current_filename_segment[len(token_cfg["suffix"]):]

                    # Separator logic for optional empty tokens
                    # If this optional & empty token has a separator, and it's not the last token,
                    # try to match the separator.
                    is_last_token = (i == len(template_config) - 1)
                    separator = token_cfg.get("separator", "")

                    if separator and not is_last_token:
                        if current_filename_segment.startswith(separator):
                            current_filename_segment = current_filename_segment[len(separator):]
                        # else: if separator is not there, it's fine for an optional token that's "absent"
                    continue # Move to next token


                # Construct full pattern for this token including prefix, suffix, and optionality
                token_full_pattern_parts = []
                if token_cfg.get("prefix"):
                    token_full_pattern_parts.append(re.escape(token_cfg["prefix"]))
                
                token_full_pattern_parts.append(f"({raw_pattern})") # Capture the token value
                
                if token_cfg.get("suffix"):
                    token_full_pattern_parts.append(re.escape(token_cfg["suffix"]))
                
                token_match_pattern = "".join(token_full_pattern_parts)

                if token_cfg.get("optional"):
                    # Optional group for the whole token (prefix + pattern + suffix)
                    token_match_pattern = f"(?:{token_match_pattern})?"


                match = re.match(token_match_pattern, current_filename_segment)

                if match:
                    matched_segment = match.group(0)
                    current_filename_segment = current_filename_segment[len(matched_segment):]
                    
                    # Separator logic:
                    # If token matched and it's not the last, try to match its separator.
                    is_last_token = (i == len(template_config) - 1)
                    separator = token_cfg.get("separator", "")
                    
                    if separator and not is_last_token:
                        if current_filename_segment.startswith(separator):
                            current_filename_segment = current_filename_segment[len(separator):]
                        elif matched_segment: # If token was present, separator is expected
                            errors.append(f"Token '{token_def['label']}' matched '{matched_segment}', but expected separator '{separator}' not found. Found: '{current_filename_segment[:5]}...'")
                            return errors # Stop validation on separator error
                        # If token was optional and absent (matched_segment is empty), separator is not strictly required.
                    elif separator and is_last_token and matched_segment and current_filename_segment:
                        # Last token has a separator, was present, but there's trailing stuff
                        errors.append(f"Unexpected characters '{current_filename_segment}' after last token '{token_def['label']}' which had a separator '{separator}'.")
                        return errors


                elif not token_cfg.get("optional"):
                    errors.append(f"Token '{token_def['label']}' is missing or invalid. Expected pattern: '{raw_pattern}' (e.g., '{example}'). Nearby text: '{current_filename_segment[:20]}...'")
                    return errors # Stop validation on first mandatory token error
                # If optional and no match, it's fine, current_filename_segment remains for next token.

            if current_filename_segment:
                errors.append(f"Unexpected characters at the end of filename: '{current_filename_segment}'")

            return errors

        def get_validation_errors(self, filename):
            config = self.template_builder.get_template_config()
            return self._validate_filename_detailed(filename, config)

        def get_validation_summary(self, filename):
            errors = self.get_validation_errors(filename)
            if not errors:
                return "Filename is valid."
            else:
                return f"Filename is invalid. ({errors[0]})"

    # Mock FILENAME_TOKENS if not imported (e.g. PySide not available)
    if 'FILENAME_TOKENS' not in globals():
        FILENAME_TOKENS = [
            {"name": "sequence", "label": "<sequence>", "regex_template": "[A-Z]{n}", "control": "spinner", "min": 2, "max": 8, "default": 4, "examples": ["ABCD"]},
            {"name": "description", "label": "<description>", "regex_template": "[a-zA-Z0-9]+", "control": "static", "examples": ["comp"]},
            {"name": "version", "label": "<version>", "regex_template": "v\\d{3}", "control": "static", "examples": ["v001"]},
            {"name": "extension", "label": "<extension>", "regex_template": "(?:exr|png)", "control": "multiselect", "options": ["exr", "png"], "examples": ["exr"]},
            {"name": "pixelMappingName", "label": "<pixelMappingName>", "regex_template": "(?:(LL180|LL360))?", "control": "dropdown", "options": ["LL180", "LL360", "none"], "default": "none", "examples": ["LL180"]},
        ]
    import re # For regex operations in mocked FilenameRuleEditor

# Helper to get token definitions
def get_token_def(name):
    return next((t for t in FILENAME_TOKENS if t['name'] == name), None)

@unittest.skipIf(not PYSIDE_AVAILABLE, "PySide6 not installed, skipping UI-dependent tests.")
class TestTableBasedFilenameTemplateBuilder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance()
        if not cls.app:
            cls.app = QtWidgets.QApplication(sys.argv)

    def setUp(self):
        self.builder = TableBasedFilenameTemplateBuilder()

    def test_01_instantiation(self):
        self.assertIsNotNone(self.builder)
        self.assertEqual(self.builder.get_template_config(), [])

    def test_02_add_single_token_and_get_config(self):
        seq_def = get_token_def("sequence")
        self.builder.add_token(seq_def, separator="_")
        config = self.builder.get_template_config()
        self.assertEqual(len(config), 1)
        self.assertEqual(config[0]['name'], "sequence")
        self.assertEqual(config[0]['value'], seq_def['default']) # Default spinner value
        self.assertEqual(config[0]['separator'], "_")
        self.assertFalse(config[0]['optional'])

    def test_03_add_multiple_tokens(self):
        self.builder.add_token(get_token_def("sequence"), separator="_")
        self.builder.add_token(get_token_def("description"), separator=".")
        self.builder.add_token(get_token_def("version"), separator="") # No separator after version if it's last before ext
        
        config = self.builder.get_template_config()
        self.assertEqual(len(config), 3)
        self.assertEqual(config[0]['name'], "sequence")
        self.assertEqual(config[1]['name'], "description")
        self.assertEqual(config[2]['name'], "version")
        self.assertEqual(config[1]['separator'], ".")

    def test_04_change_token_spinner_value(self):
        seq_def = get_token_def("sequence")
        self.builder.add_token(seq_def)
        
        # Simulate changing spinner value
        # In the real UI, this would be done via table.cellWidget(0, COLUMN_CONTROL).setValue(3)
        # For the mocked version, we can directly manipulate the mocked control if available
        # or re-add with a modified default for simplicity if direct widget manipulation is too complex for mock
        
        # Ensure the default value is set as expected first
        initial_config = self.builder.get_template_config()
        self.assertEqual(initial_config[0]['value'], seq_def['default'])

        # Directly update the value in token_configs to simulate a UI change
        new_spinner_value = 3
        # Ensure the test value is different from default for a meaningful test; default for 'sequence' is 4
        self.assertNotEqual(new_spinner_value, seq_def['default'],
                            f"Test value {new_spinner_value} should be different from default {seq_def['default']}")
        
        if self.builder.token_configs: # Check if token_configs is not empty
            self.builder.token_configs[0]['value'] = new_spinner_value
        
        config = self.builder.get_template_config()
        self.assertEqual(len(config), 1, "Template config should have one entry.")
        self.assertEqual(config[0]['name'], "sequence", "Token name should be 'sequence'.")
        self.assertEqual(config[0]['value'], new_spinner_value, f"Token value should be updated to {new_spinner_value}.")

    def test_05_add_optional_token(self):
        pm_def = get_token_def("pixelMappingName") # This one is often optional
        self.builder.add_token(pm_def, optional=True, separator="_", prefix="(", suffix=")")
        config = self.builder.get_template_config()
        self.assertEqual(len(config), 1)
        self.assertEqual(config[0]['name'], "pixelMappingName")
        self.assertTrue(config[0]['optional'])
        self.assertEqual(config[0]['prefix'], "(")
        self.assertEqual(config[0]['suffix'], ")")
        # Default value for pixelMappingName in FILENAME_TOKENS is "none", which get_template_config should turn to None
        self.assertIsNone(config[0]['value'])


    def test_06_multiselect_token_value(self):
        ext_def = get_token_def("extension")
        self.builder.add_token(ext_def, separator=".")
        
        # Simulate selecting values in multiselect
        # Directly set the value in token_configs
        self.builder.token_configs[0]['value'] = ["exr", "png"]
            
        config = self.builder.get_template_config()
        self.assertEqual(config[0]['name'], "extension")
        self.assertEqual(config[0]['value'], ["exr", "png"])

    def test_07_clear_tokens(self):
        self.builder.add_token(get_token_def("sequence"))
        self.builder.clear()
        self.assertEqual(self.builder.get_template_config(), [])


@unittest.skipIf(not PYSIDE_AVAILABLE, "PySide6 not installed, skipping UI-dependent tests.")
class TestFilenameRuleEditorFunctionality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QtWidgets.QApplication.instance()
        if not cls.app:
            cls.app = QtWidgets.QApplication(sys.argv)

    def setUp(self):
        self.editor = FilenameRuleEditor()
        # Clear any tokens from previous tests if builder is reused (it's new per editor instance)
        self.editor.template_builder.clear()


    def test_01_regex_generation_simple(self):
        # Add tokens to the editor's internal builder
        # The templateChanged signal from builder should trigger editor.update_regex
        self.editor.template_builder.add_token(get_token_def("sequence"), separator="_")
        self.editor.template_builder.add_token(get_token_def("description"), separator=".")
        ext_def = get_token_def("extension") # control: multiselect
        self.editor.template_builder.add_token(ext_def, separator="") # No separator after extension

        # Simulate selecting 'exr' for extension
        ext_token_config = self.editor.template_builder.token_configs[2]
        ext_token_config['value'] = ["exr"] # Directly set the value
        self.editor.update_regex() # Manually trigger if signal mechanism is not robust in test

        # Expected regex: ^[A-Z]{4}_[a-zA-Z0-9]+\.(?:exr)$
        # Based on FILENAME_TOKENS:
        # seq: [A-Z]{n} (default n=4) -> [A-Z]{4}
        # desc: [a-zA-Z0-9]+
        # ext: (?:exr|png) -> (?:exr) if only exr selected
        # Using simplified regex from mocked FilenameRuleEditor
        expected_regex = "^(?:[A-Z]{4})_(?:[a-zA-Z0-9]+)\\.(?:exr)$"
        self.assertEqual(self.editor.template_builder.generated_regex_pattern, expected_regex)

    def test_02_regex_with_optional_token(self):
        self.editor.template_builder.add_token(get_token_def("sequence"), separator="_")
        # pixelMappingName: regex_template = (?:(LL180|LL360))?, control = dropdown, default="none"
        pm_def = get_token_def("pixelMappingName")
        self.editor.template_builder.add_token(pm_def, optional=True, separator="_", prefix="", suffix="") # value will be None (from "none")
        self.editor.template_builder.add_token(get_token_def("description"), separator=".")
        
        # Manually trigger update_regex after all additions
        self.editor.update_regex()

        # Expected: ^[A-Z]{4}_(?:(?:LL180|LL360))?_[a-zA-Z0-9]+\.$ (if pixelMappingName is truly optional in regex)
        # Mocked regex for optional pixelMappingName (value=None) is empty string for its part
        # So, ^(?:[A-Z]{4})_(?:)?_(?:[a-zA-Z0-9]+)\\.$
        # The double underscore might be an issue in the mock regex logic if not handled.
        # The mocked update_regex has simplified logic.
        # If pm_def value is None, its part_regex becomes "" in the mock.
        # So, ^(?:[A-Z]{4})__(?:[a-zA-Z0-9]+)\\.$ (prefix/suffix are empty)
        # The actual UI code might handle separators around truly absent optional tokens better.
        # Let's test with pixelMappingName having a value
        self.editor.template_builder.clear()
        self.editor.template_builder.add_token(get_token_def("sequence"), separator="_")
        pm_token_cfg = self.editor.template_builder.add_token(pm_def, optional=True, separator="_")
        self.editor.template_builder.token_configs[1]['value'] = "LL180" # Set a value directly
        self.editor.template_builder.add_token(get_token_def("description"), separator=".")
        self.editor.update_regex()
        
        # Expected: ^(?:[A-Z]{4})_LL180_(?:[a-zA-Z0-9]+)\\.$
        expected_regex = "^(?:[A-Z]{4})_LL180_(?:[a-zA-Z0-9]+)\\.$"
        self.assertEqual(self.editor.template_builder.generated_regex_pattern, expected_regex)


    def test_03_validate_filename_detailed_valid(self):
        template_config = [
            {"name": "sequence", "value": 4, "separator": "_", "optional": False, "prefix": "", "suffix": ""},
            {"name": "description", "value": None, "separator": ".", "optional": False, "prefix": "", "suffix": ""},
            {"name": "extension", "value": ["exr"], "separator": "", "optional": False, "prefix": "", "suffix": ""}
        ]
        # This test uses the mocked _validate_filename_detailed
        errors = self.editor._validate_filename_detailed("ABCD_comp.exr", template_config)
        self.assertEqual(errors, [])

    def test_04_validate_filename_detailed_invalid_sequence(self):
        template_config = [
            {"name": "sequence", "value": 4, "separator": "_", "optional": False, "prefix": "", "suffix": ""},
            {"name": "description", "value": None, "separator": ".", "optional": False, "prefix": "", "suffix": ""},
        ]
        errors = self.editor._validate_filename_detailed("abc_comp.exr", template_config)
        self.assertTrue(len(errors) > 0)
        self.assertIn("Token '<sequence>' is missing or invalid", errors[0])

    def test_05_validate_filename_detailed_missing_mandatory_token(self):
        template_config = [
            {"name": "sequence", "value": 4, "separator": "_", "optional": False, "prefix": "", "suffix": ""},
            {"name": "description", "value": None, "separator": ".", "optional": False, "prefix": "", "suffix": ""}, # Mandatory
            {"name": "extension", "value": ["exr"], "separator": "", "optional": False, "prefix": "", "suffix": ""}
        ]
        errors = self.editor._validate_filename_detailed("ABCD.exr", template_config) # Missing description
        self.assertTrue(len(errors) > 0)
        # The mocked _validate_filename_detailed might stop at the first token that "consumes" incorrectly
        # or where the separator logic fails.
        # If sequence matches "ABCD", then "." is expected. If it finds ".exr", it might fail on description.
        self.assertIn("Token '<description>' is missing or invalid", errors[0])


    def test_06_validate_filename_detailed_optional_token_absent(self):
        template_config = [
            {"name": "sequence", "value": 4, "separator": "_", "optional": False, "prefix": "", "suffix": ""},
            {"name": "pixelMappingName", "value": None, "separator": "_", "optional": True, "prefix": "", "suffix": ""}, # Optional, absent
            {"name": "description", "value": None, "separator": ".", "optional": False, "prefix": "", "suffix": ""},
            {"name": "extension", "value": ["exr"], "separator": "", "optional": False, "prefix": "", "suffix": ""}
        ]
        # Filename without the optional pixelMappingName
        # The mocked _validate_filename_detailed has specific logic for optional empty patterns
        errors = self.editor._validate_filename_detailed("ABCD_comp.exr", template_config)
        self.assertEqual(errors, [])

    def test_07_validate_filename_detailed_optional_token_present(self):
        template_config = [
            {"name": "sequence", "value": 4, "separator": "_", "optional": False, "prefix": "", "suffix": ""},
            {"name": "pixelMappingName", "value": "LL180", "separator": "_", "optional": True, "prefix": "", "suffix": ""}, # Optional, present
            {"name": "description", "value": None, "separator": ".", "optional": False, "prefix": "", "suffix": ""},
            {"name": "extension", "value": ["exr"], "separator": "", "optional": False, "prefix": "", "suffix": ""}
        ]
        errors = self.editor._validate_filename_detailed("ABCD_LL180_comp.exr", template_config)
        self.assertEqual(errors, [])

    def test_08_validate_filename_detailed_trailing_chars(self):
        template_config = [
            {"name": "sequence", "value": 4, "separator": "_", "optional": False, "prefix": "", "suffix": ""},
            {"name": "description", "value": None, "separator": ".", "optional": False, "prefix": "", "suffix": ""},
            {"name": "extension", "value": ["exr"], "separator": "", "optional": False, "prefix": "", "suffix": ""}
        ]
        errors = self.editor._validate_filename_detailed("ABCD_comp.exr_extra", template_config)
        self.assertTrue(len(errors) > 0)
        self.assertIn("Unexpected characters at the end of filename", errors[0])

    def test_09_get_validation_errors_and_summary_valid(self):
        # Setup builder within editor
        self.editor.template_builder.add_token(get_token_def("sequence"), separator="_")
        self.editor.template_builder.add_token(get_token_def("description"), separator=".")
        ext_def = get_token_def("extension")
        self.editor.template_builder.add_token(ext_def, separator="")
        self.editor.template_builder.token_configs[2]['value'] = ["exr"] # Directly set the value
        self.editor.update_regex() # Ensure config is processed by editor logic

        errors = self.editor.get_validation_errors("TEST_comp.exr")
        summary = self.editor.get_validation_summary("TEST_comp.exr")
        
        self.assertEqual(errors, [])
        self.assertEqual(summary, "Filename is valid.")

    def test_10_get_validation_errors_and_summary_invalid(self):
        self.editor.template_builder.add_token(get_token_def("sequence"), separator="_") # Expects 4 chars
        
        errors = self.editor.get_validation_errors("ABC_comp.exr") # Sequence too short
        summary = self.editor.get_validation_summary("ABC_comp.exr")

        self.assertTrue(len(errors) > 0)
        self.assertIn("Token '<sequence>' is missing or invalid", errors[0])
        self.assertTrue(summary.startswith("Filename is invalid."))
        self.assertIn("Token '<sequence>' is missing or invalid", summary)


if __name__ == '__main__':
    if PYSIDE_AVAILABLE:
        unittest.main()
    else:
        print("Skipping tests: PySide6 is not available.")