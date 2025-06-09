#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test script for the consolidated error message format in naming convention violations.
This test verifies that the NukeValidator correctly formats the 'details' string
when a naming convention violation is detected.
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import re

# Mock the nuke module
nuke_mock = MagicMock()
nuke_mock.allNodes.return_value = []
sys.modules['nuke'] = nuke_mock

# Mock the nuke_validator_ui module
mock_filename_rule_editor = MagicMock()
mock_filename_tokens = []
sys.modules['nuke_validator_ui'] = MagicMock()
sys.modules['nuke_validator_ui'].FilenameRuleEditor = mock_filename_rule_editor
sys.modules['nuke_validator_ui'].FILENAME_TOKENS = mock_filename_tokens

# Import the NukeValidator class
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nuke_validator import NukeValidator

# Mock the get_debug_file_path function
from nuke_validator import get_debug_file_path
get_debug_file_path = MagicMock(return_value="mock_debug_file.txt")

# Mock open function to avoid file I/O
mock_open = MagicMock()
mock_file = MagicMock()
mock_file.__enter__.return_value = mock_file
mock_open.return_value = mock_file

class TestNamingConventionErrorFormat(unittest.TestCase):
    """Test the consolidated error message format for naming convention violations."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a validator instance with mock rules
        self.validator = NukeValidator()
        self.validator.rules = {
            'file_paths': {
                'filename_tokens': [
                    {"name": "sequence", "type": "range", "min_value": 3, "max_value": 4, "regex": r"[A-Z]{3,4}", "required": True},
                    {"name": "shotNumber", "type": "numeric", "digits": 4, "regex": r"\d{4}", "required": True},
                    {"name": "version", "type": "version", "regex": r"v\d{3}", "required": True}
                ],
                'naming_pattern_regex': r"^[A-Z]{3,4}\d{4}_v\d{3}\.\w+$",
                'severity_naming_pattern': 'warning'
            }
        }
        
        # Create a mock Write node
        self.mock_node = MagicMock()
        self.mock_node.Class.return_value = 'Write'
        self.mock_node.name.return_value = 'WriteNode1'
        
        # Set up file path with invalid filename
        self.invalid_filename = "AB123_v01.exr"  # Too few letters in sequence, too few digits in shot, too few digits in version
        self.mock_node.__getitem__.return_value.value.return_value = f"/path/to/{self.invalid_filename}"
        
        # Expected detailed error message
        self.expected_details = """Filename doesn't match the expected format:
- Invalid 'sequence': Expected 3-4 letters but found 'AB'
- Invalid 'shotNumber': Expected 4 digits but found '123'
- Invalid 'version': Expected format 'v001' but found 'v01'"""

    @patch('builtins.open', new_callable=MagicMock)
    @patch('re.match')
    @patch('nuke_validator.NukeValidator._validate_by_tokens')
    def test_naming_convention_error_format(self, mock_validate_by_tokens, mock_re_match, mock_open):
        """Test that the error details string is correctly formatted for naming convention violations."""
        # Configure mocks to simulate validation failure
        mock_re_match.return_value = None  # Simulate regex match failure
        
        # Mock the token validation to return specific errors
        mock_validate_by_tokens.return_value = [
            "Invalid 'sequence': Expected 3-4 letters but found 'AB'",
            "Invalid 'shotNumber': Expected 4 digits but found '123'",
            "Invalid 'version': Expected format 'v001' but found 'v01'"
        ]
        
        # Call the method that would trigger the validation
        self.validator._check_file_paths_and_naming([self.mock_node])
        
        # Verify that the validation methods were called
        mock_re_match.assert_called_once()
        mock_validate_by_tokens.assert_called_once()
        
        # Check that an issue was added with the correct format
        self.assertEqual(len(self.validator.issues), 1, "Expected one issue to be added")
        
        issue = self.validator.issues[0]
        self.assertEqual(issue['type'], 'naming_convention_violation', "Issue type should be 'naming_convention_violation'")
        self.assertEqual(issue['node'], 'WriteNode1', "Node name should match the mock")
        self.assertEqual(issue['node_type'], 'Write', "Node type should be 'Write'")
        self.assertEqual(issue['current'], self.invalid_filename, "Current value should be the invalid filename")
        self.assertEqual(issue['severity'], 'warning', "Severity should match the rule configuration")
        
        # The key test: verify the 'details' string format
        self.assertEqual(issue['details'], self.expected_details, 
                         "The 'details' string does not match the expected format")

    @patch('builtins.open', new_callable=MagicMock)
    @patch('nuke_validator.NukeValidator._validate_filename_detailed')
    @patch('re.match')
    def test_integration_with_detailed_validation(self, mock_re_match, mock_validate_filename_detailed, mock_open):
        """Test integration with the detailed validation method."""
        # Configure mocks to simulate validation failure
        mock_re_match.return_value = None  # Simulate regex match failure
        
        # Configure mock to return specific errors
        mock_validate_filename_detailed.return_value = [
            "Invalid 'sequence': Expected 3-4 letters but found 'AB'",
            "Invalid 'shotNumber': Expected 4 digits but found '123'",
            "Invalid 'version': Expected format 'v001' but found 'v01'"
        ]
        
        # Call the method that would trigger the validation
        self.validator._check_file_paths_and_naming([self.mock_node])
        
        # Verify that the validation method was called
        mock_validate_filename_detailed.assert_called_once()
        
        # Check that an issue was added with the correct format
        self.assertEqual(len(self.validator.issues), 1, "Expected one issue to be added")
        
        issue = self.validator.issues[0]
        self.assertEqual(issue['type'], 'naming_convention_violation', "Issue type should be 'naming_convention_violation'")
        
        # The key test: verify the 'details' string format
        self.assertEqual(issue['details'], self.expected_details, 
                         "The 'details' string does not match the expected format")

if __name__ == '__main__':
    unittest.main()