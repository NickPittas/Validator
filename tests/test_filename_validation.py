#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test cases for the unified filename validation implementation.
These tests verify that the new validation approach correctly validates filenames
and provides detailed, actionable error messages.

Note: This test is designed to be run inside Nuke or with the MockValidator class
which simulates the validation logic without requiring the full Nuke environment.
"""

import sys
import os
import re
import yaml

# Add parent directory to path to import mock modules if needed
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Define a mock validator class for testing filename validation
class MockValidator:
    """
    A mock validator class that implements just the filename validation functionality
    from NukeValidator for testing purposes. This avoids the need for the actual Nuke API.
    """
    
    def __init__(self):
        self.rules = self._load_rules()
    
    def _load_rules(self):
        """
        Load validation rules from the default YAML file or provide test defaults
        """
        rules_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Sphere.yaml')
        if not os.path.exists(rules_path):
            print(f"Rules file not found at: {rules_path}, using test defaults")
            # Provide default test rules
            return {
                'file_paths': {
                    'filename_template': r'^[A-Za-z]{3,4}\d{4}_[a-zA-Z0-9]+(?:[-a-zA-Z0-9]+)*_(?:(LL180|LL360))?\d{1,2}k_(r709|sRGB|acescg|ap0|ap1|p3|rec2020)(lin|log|g22|g24|g26)_(2997|5994|24|25|30|50|60)_v\d{2,3}\.(?:%0[4-8]d|#{4,8})\.(exr)$',
                    'filename_tokens': [
                        {
                            "name": "sequence",
                            "type": "range",
                            "min_value": 3,
                            "max_value": 4,
                            "regex": "[A-Z]{MIN_VAL,MAX_VAL}",
                            "required": True,
                            "label": "Sequence"
                        },
                        {
                            "name": "shotNumber",
                            "type": "numeric",
                            "digits": 4,
                            "regex": r"\d{4}",
                            "required": True,
                            "label": "Shot Number"
                        },
                        {
                            "name": "separator",
                            "type": "static",
                            "regex": r"_",
                            "required": True,
                            "separator": "_"
                        },
                        {
                            "name": "department",
                            "type": "enum",
                            "values": ["comp", "grade", "roto"],
                            "required": True,
                            "label": "Department"
                        },
                        {
                            "name": "separator",
                            "type": "static",
                            "regex": r"_",
                            "required": True,
                            "separator": "_"
                        },
                        {
                            "name": "task",
                            "type": "enum",
                            "values": ["main", "cleanup", "grade"],
                            "required": True,
                            "label": "Task"
                        },
                        {
                            "name": "separator",
                            "type": "static",
                            "regex": r"_",
                            "required": True,
                            "separator": "_"
                        },
                        {
                            "name": "version",
                            "type": "version",
                            "regex": r"v\d{3}",
                            "required": True,
                            "label": "Version"
                        },
                        {
                            "name": "extension",
                            "type": "enum",
                            "values": ["nk", "mov", "exr"],
                            "regex": "\\.\w+",
                            "required": True,
                            "label": "Extension"
                        }
                    ]
                }
            }
            
        try:
            with open(rules_path, 'r') as f:
                rules = yaml.safe_load(f)
                if not rules.get('file_paths', {}).get('filename_tokens'):
                    print("Warning: No filename_tokens found in rules, using test defaults")
                    rules = self._get_default_test_rules()
                return rules
        except Exception as e:
            print(f"Error loading rules: {e}, using test defaults")
            return self._get_default_test_rules()
    
    def _get_default_test_rules(self):
        """Provide default rules for testing"""
        return {
            'file_paths': {
                'filename_template': r'^[A-Za-z]{3,4}\d{4}_[a-zA-Z0-9]+(?:[-a-zA-Z0-9]+)*_(?:(LL180|LL360))?\d{1,2}k_(r709|sRGB|acescg|ap0|ap1|p3|rec2020)(lin|log|g22|g24|g26)_(2997|5994|24|25|30|50|60)_v\d{2,3}\.(?:%0[4-8]d|#{4,8})\.(exr)$',
                'filename_tokens': [
                    {
                        "name": "sequence",
                        "type": "range",
                        "min_value": 3,
                        "max_value": 4,
                        "regex": "[A-Z]{MIN_VAL,MAX_VAL}",
                        "required": True,
                        "label": "Sequence"
                    },
                    {
                        "name": "shotNumber",
                        "type": "numeric",
                        "digits": 4,
                        "regex": r"\d{4}",
                        "required": True,
                        "label": "Shot Number"
                    },
                    {
                        "name": "separator",
                        "type": "static",
                        "regex": r"_",
                        "required": True,
                        "separator": "_"
                    },
                    {
                        "name": "department",
                        "type": "enum",
                        "values": ["comp", "grade", "roto"],
                        "required": True,
                        "label": "Department"
                    },
                    {
                        "name": "separator",
                        "type": "static",
                        "regex": r"_",
                        "required": True,
                        "separator": "_"
                    },
                    {
                        "name": "task",
                        "type": "enum",
                        "values": ["main", "cleanup", "grade"],
                        "required": True,
                        "label": "Task"
                    },
                    {
                        "name": "separator",
                        "type": "static",
                        "regex": r"_",
                        "required": True,
                        "separator": "_"
                    },
                    {
                        "name": "version",
                        "type": "version",
                        "regex": r"v\d{3}",
                        "required": True,
                        "label": "Version"
                    },
                    {
                        "name": "extension",
                        "type": "enum",
                        "values": ["nk", "mov", "exr"],
                        "regex": "\\.\w+",
                        "required": True,
                        "label": "Extension"
                    }
                ]
            }
        }
    
    def _validate_by_tokens(self, filename, token_definitions):
        """
        Validates a filename by individually checking each token based on the token definitions from YAML.
        This method is called when the full regex match fails and provides detailed error messages.
        
        Args:
            filename (str): The filename to validate
            token_definitions (list): List of token definitions from YAML
            
        Returns:
            list: List of validation errors, empty if all tokens are valid
        """
        if not filename or not token_definitions:
            return ["Cannot validate: Missing filename or token definitions"]
            
        errors = []
        remaining_filename = filename
        
        # Keep track of separators between tokens
        separator = ""
        
        for i, token_def in enumerate(token_definitions):
            # Get the token configuration
            token_name = token_def.get("name")
            token_type = token_def.get("type", "static")
            token_required = token_def.get("required", True)
            token_pattern = token_def.get("regex", "")
            
            # If there's a custom separator, use it
            try:
                match = re.match(fr"^{pattern_to_match}", remaining_filename)
            except re.error:
                match = re.match(r"^" + pattern_to_match, remaining_filename)
            if not match:
                display_name = token_def.get("label", token_name)
                prev_token_name = token_definitions[i-1]["name"] if i > 0 else None
                if token_type == "range" and token_name == "sequence":
                    errors.append(f"Invalid sequence format: Expected {min_val}-{max_val} letters at position {i+1}")
                elif token_type == "numeric" and token_name == "shotNumber":
                    errors.append(f"Invalid shot number: Expected {digits} digits at position {i+1}")
                elif token_type == "enum":
                    errors.append(f"Invalid {display_name}: Expected one of [{', '.join(options)}] at position {i+1}")
                else:
                    errors.append(f"Invalid {display_name} format at position {i+1}")
                # Improved separator check
                if separator:
                    # If the next character is not the expected separator, report missing separator
                    if not remaining_filename.startswith(separator):
                        if prev_token_name:
                            errors.append(f"Missing separator '{separator}' between {prev_token_name} and {token_name}")
                        else:
                            errors.append(f"Missing separator '{separator}' before {token_name}")
                break
            # Check if there's anything left in the filename that wasn't matched
        if not errors and remaining_filename:
            errors.append(f"Unexpected content at the end: '{remaining_filename}'")
        
        return errors
        
    def _basic_filename_validation(self, filename, pattern_str=None):

        """
        Basic filename validation using regex patterns and token-based validation
        
        This method implements a two-step validation approach:
        1. First, it attempts a full regex match against the complete pattern
        2. If that fails, it performs token-by-token validation for detailed error reporting
        
        Args:
            filename: The filename to validate
            pattern_str: Optional regex pattern override
            
        Returns:
            List of validation errors, empty if validation passed
        """
        errors = []
        
        if not filename:
            return ["Filename is empty"]
            
        # Get the pattern and tokens configuration
        if not pattern_str:
            pattern_str = self.rules.get('file_paths', {}).get('filename_template', '')
            if not pattern_str:
                return ["No filename pattern defined in rules"]
        # Write the pattern to a debug file for analysis
        with open('pattern_debug.txt', 'w', encoding='utf-8') as dbg:
            dbg.write(f"PATTERN DEBUG: pattern_str={pattern_str!r}\n")
        
        # Fix any quantifiers that might not have proper syntax (e.g., \d4 -> \d{4})
        # This matches \d followed by digits not in curly braces
        pattern_str = re.sub(r'\\d(\d+)(?!\})', r'\\d{\1}', pattern_str)
        
        # Handle sequence token with MIN_VAL,MAX_VAL format
        # Replace with specific values to match the regex
        pattern_str = pattern_str.replace("MIN_VAL,MAX_VAL", "3,4")  # Default to 3-4 characters
        
        # Get token definitions for detailed validation if needed
        filename_tokens = self.rules.get('file_paths', {}).get('filename_tokens', [])
        
        try:
            # Step 1: Try full regex match first for quick validation
            pattern = re.compile(pattern_str)
            match = pattern.match(filename)
            if match:
                # Full regex match succeeded
                # Check for version formatting issues
                version_match = re.search(r'v(\d+)', filename, re.IGNORECASE)
                if version_match:
                    version_num = version_match.group(1)
                    # Check if version number is properly zero-padded
                    if len(version_num) < 3:  # Standard is at least 3 digits (v001)
                        errors.append(f"Version number '{version_num}' should be zero-padded to at least 3 digits (e.g., v001)")
                
                # If no version issues, filename is valid
                if not errors:
                    return []  # No errors, validation passed
            else:
                # Step 2: Full regex match failed, perform token-by-token validation
                errors.append("Filename doesn't match expected format")
                
                # Only proceed with detailed validation if we have token definitions
                if filename_tokens:
                    # Use token-by-token validation for detailed error messages
                    token_errors = self._validate_by_tokens(filename, filename_tokens)
                    if token_errors:
                        errors.extend(token_errors)
                    
                    # No need for additional checks if token validation gave us details
                    return errors
                
                # If we don't have token definitions, fall back to general checks
                # Check for common separator issues
                if '_' in pattern_str and '_' not in filename:
                    errors.append("Missing underscores between tokens (e.g., 'abc123' should be 'abc_123')")
                
                # Check for sequence+shot format issues
                seq_shot_pattern = re.search(r'\[A-Za-z\]{([\d,]+)}\\d{(\d+)}', pattern_str)
                if seq_shot_pattern:
                    # Extract the sequence and shot number constraints
                    seq_range = seq_shot_pattern.group(1)  # e.g., "3,4"
                    shot_digits = seq_shot_pattern.group(2)  # e.g., "4"
                    
                    # Create a specific regex to match at the start of the filename
                    seq_shot_regex = fr"^[A-Za-z]{{{seq_range}}}\d{{{shot_digits}}}"
                    seq_shot_match = re.search(seq_shot_regex, filename)
                    
                    if not seq_shot_match:
                        # Check if they might be wrongly separated
                        seq_only_match = re.search(fr"^[A-Za-z]{{{seq_range}}}", filename)
                        if seq_only_match:
                            errors.append(f"Sequence format correct but shot number format incorrect or missing")
                        else:
                            errors.append(f"Invalid sequence format - should be {seq_range} letters followed by {shot_digits} digits")
                
                # Check for file extension issues
                if '.' in pattern_str:
                    ext_match = re.search(r'\.([a-zA-Z0-9]+)$', filename)
                    pattern_ext_match = re.search(r'\.([a-zA-Z0-9]+)', pattern_str)
                    
                    if not ext_match:
                        errors.append("Missing file extension")
                    elif pattern_ext_match and ext_match.group(1).lower() != pattern_ext_match.group(1).lower():
                        errors.append(f"Incorrect file extension: found '.{ext_match.group(1)}', expected '.{pattern_ext_match.group(1)}'")
                
                # For cases where token-by-token validation didn't find specific issues
                # but the filename still doesn't match the expected pattern
                if not errors:
                    # Try to provide more specific guidance based on pattern structure
                    pattern_parts = pattern_str.replace('^', '').replace('$', '').split('_')
                    filename_parts = filename.split('_')
                    
                    # Compare number of parts
                    if len(pattern_parts) != len(filename_parts):
                        errors.append(f"Expected {len(pattern_parts)} parts separated by '_', found {len(filename_parts)} parts")
                    
                    # Compare each part individually
                    for i, (pattern_part, filename_part) in enumerate(zip(pattern_parts, filename_parts)):
                        try:
                            # Fix any quantifier syntax issues in individual parts
                            pattern_part = re.sub(r'\\d(\d+)(?!\})', r'\\d{\1}', pattern_part)
                            if not re.match(fr"^{pattern_part}$", filename_part):
                                errors.append(f"Part {i+1} '{filename_part}' doesn't match expected format '{pattern_part}'")
                        except Exception:
                            # Skip problematic part comparisons without printing
                            pass
                
                # If still no specific errors detected, provide a general message
                if not errors:
                    errors.append(f"Filename '{filename}' doesn't match the expected pattern. Check format and separators.")
            
            return errors
            
        except re.error as e:
            return [f"Regex validation error: {str(e)}", "Check the pattern configuration in rules.yaml"]
        except Exception as e:
            return [f"Validation error: {str(e)}"]

import pytest

# ... (MockValidator definition remains unchanged) ...

# Test cases grouped by category
valid_cases = [
    ("ABCD1234_comp_LL18010k_r709lin_24_v001.%04d.exr", "Standard valid filename (comp)"),
    ("KITC1000_grade_LL3608k_acescglog_25_v099.%06d.exr", "Valid with different department, lens, res, colorspace, gamma, fps, version, padding"),
    ("XYZ9876_roto_LL18012k_ap0g24_60_v123.%08d.exr", "Valid with 3-letter sequence and other valid values"),
    ("ABCD1234_main_LL18010k_r709lin_24_v999.%04d.exr", "Valid with task 'main'"),
]

invalid_sequence_shot_cases = [
    ("AB1234_comp_LL18010k_r709lin_24_v001.%04d.exr", "Invalid sequence (too short)"),
    ("ABCDE1234_comp_LL18010k_r709lin_24_v001.%04d.exr", "Invalid sequence (too long)"),
    ("ABCD123_comp_LL18010k_r709lin_24_v001.%04d.exr", "Invalid shot number (too few digits)"),
    ("ABCD12345_comp_LL18010k_r709lin_24_v001.%04d.exr", "Invalid shot number (too many digits)"),
    ("ABCD_1234_comp_LL18010k_r709lin_24_v001.%04d.exr", "Invalid separator in sequence+shot"),
    ("1234ABCD_comp_LL18010k_r709lin_24_v001.%04d.exr", "Reversed sequence and shot"),
]

invalid_separators_cases = [
    ("ABCD1234comp_LL18010k_r709lin_24_v001.%04d.exr", "Missing separator '_' after shot number"),
    ("ABCD1234_compLL18010k_r709lin_24_v001.%04d.exr", "Missing separator '_' between department and lens"),
    ("ABCD1234_comp_LL18010k_r709lin_24v001.%04d.exr", "Missing separator '_' before version"),
]

invalid_version_cases = [
    ("ABCD1234_comp_LL18010k_r709lin_24_v1.%04d.exr", "Version not zero-padded"),
    ("ABCD1234_comp_LL18010k_r709lin_24_001.%04d.exr", "Missing 'v' in version"),
    ("ABCD1234_comp_LL18010k_r709lin_24_.%04d.exr", "Missing version entirely"),
]

invalid_extension_cases = [
    ("ABCD1234_comp_LL18010k_r709lin_24_v001.%04d", "Missing extension"),
    ("ABCD1234_comp_LL18010k_r709lin_24_v001.%04d.txt", "Wrong extension"),
]

edge_cases = [
    ("", "Empty filename"),
    ("ABCD1234.exr", "Missing required parts"),
    ("abcd1234_comp_LL18010k_r709lin_24_v001.%04d.exr", "Lowercase sequence"),
    ("ABCD1234_COMP_LL18010K_R709LIN_24_V001.%04D.EXR", "All uppercase"),
    ("ABCD1234__comp_LL18010k_r709lin_24_v001.%04d.exr", "Double separator"),
]

invalid_sequence_shot_cases = [
    ("AB1234_comp_main_LL18010k_r709lin_24_v001.%04d.exr", "Invalid sequence (too short)"),
    ("ABCDE1234_comp_main_LL18010k_r709lin_24_v001.%04d.exr", "Invalid sequence (too long)"),
    ("ABCD123_comp_main_LL18010k_r709lin_24_v001.%04d.exr", "Invalid shot number (too few digits)"),
    ("ABCD12345_comp_main_LL18010k_r709lin_24_v001.%04d.exr", "Invalid shot number (too many digits)"),
    ("ABCD_1234_comp_main_LL18010k_r709lin_24_v001.%04d.exr", "Invalid separator in sequence+shot"),
    ("1234ABCD_comp_main_LL18010k_r709lin_24_v001.%04d.exr", "Reversed sequence and shot"),
]

invalid_separators_cases = [
    ("ABCD1234comp_main_LL18010k_r709lin_24_v001.%04d.exr", "Missing separator '_' after shot number"),
    ("ABCD1234_compmain_LL18010k_r709lin_24_v001.%04d.exr", "Missing separator '_' between department and task"),
    ("ABCD1234_comp_mainLL18010k_r709lin_24_v001.%04d.exr", "Missing separator '_' before lens"),
]

invalid_version_cases = [
    ("ABCD1234_comp_main_LL18010k_r709lin_24_v1.%04d.exr", "Version not zero-padded"),
    ("ABCD1234_comp_main_LL18010k_r709lin_24_001.%04d.exr", "Missing 'v' in version"),
    ("ABCD1234_comp_main_LL18010k_r709lin_24_.%04d.exr", "Missing version entirely"),
]

invalid_extension_cases = [
    ("ABCD1234_comp_main_LL18010k_r709lin_24_v001.%04d", "Missing extension"),
    ("ABCD1234_comp_main_LL18010k_r709lin_24_v001.%04d.txt", "Wrong extension"),
]

edge_cases = [
    ("", "Empty filename"),
    ("ABCD1234.exr", "Missing required parts"),
    ("abcd1234_comp_main_LL18010k_r709lin_24_v001.%04d.exr", "Lowercase sequence"),
    ("ABCD1234_COMP_MAIN_LL18010K_R709LIN_24_V001.%04D.EXR", "All uppercase"),
    ("ABCD1234__comp_main_LL18010k_r709lin_24_v001.%04d.exr", "Double separator"),
]

def get_validator():
    return MockValidator()

@pytest.mark.parametrize("filename,desc", valid_cases)
def test_valid_filenames(filename, desc):

    validator = get_validator()
    errors = validator._basic_filename_validation(filename)
    assert not errors, f"{desc}: Expected no errors, got {errors}"

@pytest.mark.parametrize("filename,desc", invalid_sequence_shot_cases)
def test_invalid_sequence_shot(filename, desc):
    validator = get_validator()
    errors = validator._basic_filename_validation(filename)
    assert errors, f"{desc}: Expected errors, got none"

@pytest.mark.parametrize("filename,desc", invalid_separators_cases)
def test_invalid_separators(filename, desc):
    validator = get_validator()
    errors = validator._basic_filename_validation(filename)
    assert errors, f"{desc}: Expected errors, got none"

@pytest.mark.parametrize("filename,desc", invalid_version_cases)
def test_invalid_version(filename, desc):
    validator = get_validator()
    errors = validator._basic_filename_validation(filename)
    assert errors, f"{desc}: Expected errors, got none"

@pytest.mark.parametrize("filename,desc", invalid_extension_cases)
def test_invalid_extension(filename, desc):
    validator = get_validator()
    errors = validator._basic_filename_validation(filename)
    assert errors, f"{desc}: Expected errors, got none"

@pytest.mark.parametrize("filename,desc", edge_cases)
def test_edge_cases(filename, desc):
    validator = get_validator()
    errors = validator._basic_filename_validation(filename)
    assert errors, f"{desc}: Expected errors, got none"

def test_token_by_token_valid():
    validator = get_validator()
    filename_tokens = validator.rules.get('file_paths', {}).get('filename_tokens', [])
    if filename_tokens:
        errors = validator._validate_by_tokens("KITC1000", filename_tokens)
        assert not errors, "Sequence + Shot only: Expected no errors, got some"
    else:
        pytest.skip("No token definitions found in rules")

def test_token_by_token_invalid_sequence():
    validator = get_validator()
    filename_tokens = validator.rules.get('file_paths', {}).get('filename_tokens', [])
    if filename_tokens:
        errors = validator._validate_by_tokens("KIC1000", filename_tokens)
        assert errors, "Invalid sequence: Expected errors, got none"
    else:
        pytest.skip("No token definitions found in rules")

def test_token_by_token_invalid_shot():
    validator = get_validator()
    filename_tokens = validator.rules.get('file_paths', {}).get('filename_tokens', [])
    if filename_tokens:
        errors = validator._validate_by_tokens("KITC100", filename_tokens)
        assert errors, "Invalid shot number: Expected errors, got none"
    else:
        pytest.skip("No token definitions found in rules")

if __name__ == "__main__":
    test = TestFilenameValidation()
    test.run_tests()
