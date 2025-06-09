#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test module for validation integration between UI and backend.
This test verifies that the backend successfully imports and uses UI validation logic,
and that both UI and backend validation methods work correctly.
"""

import unittest
import sys
import re
import os
from unittest.mock import MagicMock, patch

# ====================================================================
# Setup mock environment
# ====================================================================

# Mocking the 'nuke' module to allow tests to run without a Nuke environment
nuke_mock = MagicMock()

# Setup common mock attributes and methods
nuke_mock.allNodes.return_value = []
nuke_mock.selectedNode.return_value = None
nuke_mock.toNode.return_value = None

# Mock for nuke.root()
mock_root_instance = MagicMock(name='NukeRootMock')
mock_knob_instance = MagicMock(name='NukeKnobMock')
mock_knob_instance.value.return_value = 0
mock_root_instance.knob.return_value = mock_knob_instance
nuke_mock.root.return_value = mock_root_instance
nuke_mock.WRITE = 'Write'

# Add the mock to sys.modules
sys.modules['nuke'] = nuke_mock

# Define FILENAME_TOKENS for testing - this represents the tokens from UI
FILENAME_TOKENS = [
    {"name": "project", "label": "Project", "regex_template": "[a-zA-Z0-9]+", "examples": ["project"]},
    {"name": "sequence", "label": "Sequence", "regex_template": "seq\\d{3}", "examples": ["seq001"]},
    {"name": "shot", "label": "Shot", "regex_template": "shot\\d{3}", "examples": ["shot010"]},
    {"name": "layer", "label": "Layer", "regex_template": "[a-zA-Z0-9]+", "examples": ["comp"]},
    {"name": "version", "label": "Version", "regex_template": "v\\d{3}", "examples": ["v001"]},
]

# ====================================================================
# Mock UI Components for validation
# ====================================================================

# This mock recreates the core validation logic of FilenameRuleEditor without UI dependencies
class MockFilenameRuleEditor:
    """
    A mock implementation of FilenameRuleEditor that focuses only on validation logic
    without UI dependencies
    """
    def __init__(self):
        self.template_builder = MagicMock()
        self.template_builder.token_widgets = []
        self.template_config = []
        
    def add_token(self, token_def):
        """Add a token to the template"""
        token_widget = MagicMock()
        token_widget.token_configs = [{
            "name": token_def["name"],
            "value": "",
            "separator": "_"
        }]
        self.template_builder.token_widgets.append(token_widget)
        self.template_config.append({
            "name": token_def["name"],
            "separator": "_"
        })
        
    def update_regex(self):
        """Update regex pattern (mock implementation)"""
        pass
        
    def _validate_filename_detailed(self, filename, template_config):
        """Core validation logic without UI dependencies"""
        if not filename:
            return ["Filename is empty"]
            
        # Use regex matching to validate each part of the filename
        expected_pattern = ""
        remaining_filename = filename
        errors = []
        
        for i, token_cfg in enumerate(template_config):
            token_name = token_cfg.get("name")
            separator = token_cfg.get("separator", "_")
            
            # Find the token definition
            token_def = next((t for t in FILENAME_TOKENS if t["name"] == token_name), None)
            if not token_def:
                continue
                
            # Build the pattern for this token
            token_pattern = token_def["regex_template"]
            
            # Add separator if not the last token
            if i < len(template_config) - 1 and separator:
                expected_pattern = f"({token_pattern})({re.escape(separator)})"
            else:
                expected_pattern = f"({token_pattern})"
                
            # Try to match at the start of remaining filename
            match = re.match(f"^{expected_pattern}", remaining_filename)
            if not match:
                errors.append(f"Failed to match '{token_name}' token at position {i+1}")
                break
            else:
                # Remove the matched part and continue
                matched_text = match.group(0)
                remaining_filename = remaining_filename[len(matched_text):]
        
        # Check if anything remains after all tokens processed
        if not errors and remaining_filename and not remaining_filename.startswith("."):
            errors.append(f"Unexpected content at end: '{remaining_filename}'")
        elif not errors and remaining_filename.startswith("."):
            # Check file extension
            if not re.match(r"\.[a-zA-Z0-9]+$", remaining_filename):
                errors.append(f"Invalid file extension: '{remaining_filename}'")
        
        return errors
        
    def get_validation_errors(self, filename):
        """Public method for getting validation errors"""
        return self._validate_filename_detailed(filename, self.template_config)

# Try to import UI components - fallback to our mock if not available
try:
    from nuke_validator_ui import FilenameRuleEditor, FILENAME_TOKENS as UI_FILENAME_TOKENS
    # If imported successfully, make our constants match the imported ones
    FILENAME_TOKENS = UI_FILENAME_TOKENS
    UI_COMPONENTS_AVAILABLE = True
except ImportError:
    # Use our mock implementation if UI components aren't available
    FilenameRuleEditor = MockFilenameRuleEditor
    # FILENAME_TOKENS already defined above
    UI_COMPONENTS_AVAILABLE = False
        {"name": "project", "regex_template": "[a-zA-Z0-9]+", "examples": ["project"]},
        {"name": "sequence", "regex_template": "seq\\d{3}", "examples": ["seq001"]},
        {"name": "shot", "regex_template": "shot\\d{3}", "examples": ["shot010"]},
        {"name": "layer", "regex_template": "[a-zA-Z0-9]+", "examples": ["comp"]},
        {"name": "version", "regex_template": "v\\d{3}", "examples": ["v001"]},
    ]

# Try to import backend validator
try:
    from nuke_validator import NukeValidator
    BACKEND_AVAILABLE = True
except ImportError:
    BACKEND_AVAILABLE = False
    # Mock the backend validator if not available
    class NukeValidator:
        def __init__(self):
            self.rules = {
                'file_paths': {
                    'filename_tokens': [
                        {"name": "project", "value": "", "separator": "_"},
                        {"name": "sequence", "value": "", "separator": "_"},
                        {"name": "shot", "value": "", "separator": "_"},
                        {"name": "layer", "value": "", "separator": "_"},
                        {"name": "version", "value": "", "separator": "_"}
                    ],
                    'filename_pattern': 'project_seq\\d{3}_shot\\d{3}_[a-zA-Z0-9]+_v\\d{3}\\.exr',
                    'severity_naming_pattern': 'warning'
                }
            }
            
        def _validate_filename_detailed(self, filename, pattern_str):
            # Simple mock implementation
            if filename == "project_seq001_shot010_comp_v001.exr":
                return []
            return ["Invalid filename format"]

        def _basic_filename_validation(self, filename, pattern_str):
            # Simple mock implementation
            if filename == "project_seq001_shot010_comp_v001.exr":
                return []
            return ["Filename doesn't match pattern"]


class TestValidationIntegration(unittest.TestCase):
    """Test validation integration between UI and backend components."""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        # Skip all tests if either UI or backend components aren't available
        if not UI_COMPONENTS_AVAILABLE or not BACKEND_AVAILABLE:
            print("Skipping validation integration tests: UI components or backend not available")
        
    def setUp(self):
        """Set up test fixtures before each test."""
        if not UI_COMPONENTS_AVAILABLE or not BACKEND_AVAILABLE:
            self.skipTest("UI components or backend not available")
            
        # Create test rules
        self.test_rules = {
            'file_paths': {
                'filename_tokens': [
                    {"name": "project", "value": "", "separator": "_"},
                    {"name": "sequence", "value": "", "separator": "_"},
                    {"name": "shot", "value": "", "separator": "_"},
                    {"name": "layer", "value": "", "separator": "_"},
                    {"name": "version", "value": "", "separator": "_"}
                ],
                'filename_pattern': 'project_seq\\d{3}_shot\\d{3}_[a-zA-Z0-9]+_v\\d{3}\\.exr',
                'severity_naming_pattern': 'warning'
            }
        }
        
        # Initialize UI validator
        self.ui_validator = FilenameRuleEditor()
        
        # Initialize backend validator with test rules
        self.backend_validator = NukeValidator()
        self.backend_validator.rules = self.test_rules
            
    def test_01_ui_validation_works(self):
        """Test that UI validation works as expected."""
        # Valid filename
        valid_filename = "project_seq001_shot010_comp_v001.exr"
        token_config = [
            {"name": "project", "value": "", "separator": "_"},
            {"name": "sequence", "value": "", "separator": "_"},
            {"name": "shot", "value": "", "separator": "_"},
            {"name": "layer", "value": "", "separator": "_"},
            {"name": "version", "value": "", "separator": "_"}
        ]
        
        errors = self.ui_validator._validate_filename_detailed(valid_filename, token_config)
        self.assertEqual(len(errors), 0, f"Expected no errors for valid filename, got: {errors}")
        
        # Invalid filename (missing shot)
        invalid_filename = "project_seq001_comp_v001.exr"
        errors = self.ui_validator._validate_filename_detailed(invalid_filename, token_config)
        self.assertGreater(len(errors), 0, "Expected errors for invalid filename")
    
    def test_02_backend_validation_works(self):
        """Test that backend validation works as expected."""
        pattern_str = self.test_rules['file_paths']['filename_pattern']
        
        # Valid filename
        valid_filename = "project_seq001_shot010_comp_v001.exr"
        errors = self.backend_validator._basic_filename_validation(valid_filename, pattern_str)
        self.assertEqual(len(errors), 0, f"Expected no errors for valid filename, got: {errors}")
        
        # Invalid filename (missing shot)
        invalid_filename = "project_seq001_comp_v001.exr"
        errors = self.backend_validator._basic_filename_validation(invalid_filename, pattern_str)
        self.assertGreater(len(errors), 0, "Expected errors for invalid filename")
    
    def test_03_backend_imports_ui_validation(self):
        """Test that backend successfully imports and uses UI validation."""
        # Mock the UI import to verify it's being called
        with patch('nuke_validator.FilenameRuleEditor') as mock_editor:
            # Setup the mock
            mock_instance = MagicMock()
            mock_instance.update_regex.return_value = None
            mock_instance.get_validation_errors.return_value = []
            mock_editor.return_value = mock_instance
            
            # Call the backend validation method
            pattern_str = self.test_rules['file_paths']['filename_pattern']
            valid_filename = "project_seq001_shot010_comp_v001.exr"
            errors = self.backend_validator._validate_filename_detailed(valid_filename, pattern_str)
            
            # Verify the UI validator was imported and used
            mock_editor.assert_called_once()
            mock_instance.update_regex.assert_called()
    
    def test_04_integration_valid_filename(self):
        """Test integration with a valid filename."""
        # This test verifies the end-to-end validation
        # from backend through to UI components
        valid_filename = "project_seq001_shot010_comp_v001.exr"
        pattern_str = self.test_rules['file_paths']['filename_pattern']
        
        errors = self.backend_validator._validate_filename_detailed(valid_filename, pattern_str)
        self.assertEqual(len(errors), 0, f"Expected no errors for valid filename, got: {errors}")
    
    def test_05_integration_invalid_filename(self):
        """Test integration with an invalid filename."""
        # Invalid filename (incorrect shot format)
        invalid_filename = "project_seq001_shot10_comp_v001.exr"
        pattern_str = self.test_rules['file_paths']['filename_pattern']
        
        errors = self.backend_validator._validate_filename_detailed(invalid_filename, pattern_str)
        self.assertGreater(len(errors), 0, "Expected errors for invalid filename")
    
    def test_06_backend_fallback_if_import_fails(self):
        """Test that backend falls back to basic validation if import fails."""
        # Force an ImportError when trying to import UI components
        with patch('nuke_validator.FilenameRuleEditor', side_effect=ImportError("Forced import error")):
            valid_filename = "project_seq001_shot010_comp_v001.exr"
            pattern_str = self.test_rules['file_paths']['filename_pattern']
            
            # The backend should catch the ImportError and fall back to basic validation
            errors = self.backend_validator._validate_filename_detailed(valid_filename, pattern_str)
            
            # Since we're using a valid filename, the fallback validation should work
            self.assertEqual(len(errors), 0, f"Expected no errors with fallback validation, got: {errors}")
    
    def test_07_error_handling_with_invalid_token_config(self):
        """Test error handling with invalid token configuration."""
        # Create invalid token configuration
        invalid_rules = {
            'file_paths': {
                'filename_tokens': [
                    {"name": "invalid_token", "value": "", "separator": "_"},
                ],
                'filename_pattern': 'invalid.*',
                'severity_naming_pattern': 'warning'
            }
        }
        
        self.backend_validator.rules = invalid_rules
        filename = "project_seq001_shot010_comp_v001.exr"
        pattern_str = invalid_rules['file_paths']['filename_pattern']
        
        # This should trigger the error handling in _validate_filename_detailed
        errors = self.backend_validator._validate_filename_detailed(filename, pattern_str)
        
        # We expect errors but the function shouldn't crash
        self.assertIsInstance(errors, list, "Error handling failed, expected errors list")


if __name__ == '__main__':
    unittest.main()
