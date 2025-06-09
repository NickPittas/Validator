#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test script to verify the fix for token validation in nuke_validator.py
"""

import re
import os
import tempfile

def get_debug_file_path(filename):
    """Mock function to avoid dependency on tempfile"""
    return os.path.join(tempfile.gettempdir(), filename)

def validate_by_tokens(filename, token_definitions):
    """
    Simplified version of _validate_by_tokens from nuke_validator.py
    with our fix applied
    """
    print(f"Validating filename: '{filename}'")
    print(f"Token definitions count: {len(token_definitions) if token_definitions else 0}")
    
    # Mock debug file writing
    print(f"TOKEN VALIDATION: Filename: '{filename}'")
    
    if not filename or not token_definitions:
        error_msg = "Cannot validate: Missing filename or token definitions"
        print(f"{error_msg}")
        return [error_msg]
        
    errors = []
    remaining_filename = filename
    expected_pattern = ""
    
    # Keep track of separators between tokens
    separator = ""
    
    for i, token_def in enumerate(token_definitions):
        # Get the token configuration
        token_name = token_def.get("name")
        token_type = token_def.get("type", "static")
        token_required = token_def.get("required", True)
        token_pattern = token_def.get("regex", "")
        
        print(f"Processing token {i+1}: {token_name} (type: {token_type})")
        
        # If there's a custom separator, use it
        if "separator" in token_def:
            separator = token_def["separator"]
            print(f"Using separator: '{separator}'")

        # Special handling for different token types
        if token_type == "static":
            # Static tokens have fixed regex patterns
            pass
        elif token_type == "range":
            # Range tokens (like sequence) need to replace MIN_VAL,MAX_VAL placeholders
            min_val = token_def.get("min_value", token_def.get("min", 2))
            max_val = token_def.get("max_value", token_def.get("max", 4))
            token_pattern = token_pattern.replace("MIN_VAL,MAX_VAL", f"{min_val},{max_val}")
        elif token_type == "numeric":
            # Numeric tokens (like shot number) need to handle padding
            digits = token_def.get("digits", 4)
            # Ensure \d{n} format for digit matching
            if not re.search(r'\\d\{\d+\}', token_pattern):
                token_pattern = f"\\d{{{digits}}}"
        
        try:
            # Build the pattern to match against the remaining filename
            pattern_to_match = token_pattern
            
            # Add separator to the pattern if available and not the last token
            if separator and i < len(token_definitions) - 1:
                pattern_to_match += re.escape(separator)
            
            # Try to match against the start of the remaining filename
            print(f"Attempting to match '{pattern_to_match}' against '{remaining_filename}'")
            match_pattern = f"^{pattern_to_match}"
            match = re.match(match_pattern, remaining_filename)
            
            print(f"Match result: {match is not None}")
            
            if not match:
                # If the token is required, report an error
                if token_required:
                    # If there's no match and the token is required, add a specific error
                    display_name = token_def.get("label", token_name)
                    print(f"No match for required token '{display_name}'")
                    
                    # Get the expected pattern for better error messages
                    expected_pattern = token_def.get("description", "")
                    
                    # Extract the actual content that failed to match
                    actual_content = remaining_filename
                    if separator and separator in actual_content:
                        actual_content = actual_content.split(separator)[0]
                    
                    # Generate more specific error messages based on token type
                    # THIS IS THE KEY FIX: Using token_type instead of token_name
                    if token_type == "range":
                        error_msg = f"Invalid '{display_name}': Expected {min_val}-{max_val} letters but found '{actual_content}'"
                        errors.append(error_msg)
                    elif token_type == "numeric":
                        error_msg = f"Invalid '{display_name}': Expected {digits} digits but found '{actual_content}'"
                        errors.append(error_msg)
                    else:
                        # Include the expected pattern in the error message if available
                        if expected_pattern:
                            error_msg = f"Invalid '{display_name}': Expected format '{expected_pattern}' but found '{actual_content}'"
                        else:
                            error_msg = f"Invalid '{display_name}' format: Found '{actual_content}'"
                        errors.append(error_msg)
                    break
                else:
                    # Token is optional, skip it
                    continue
            else:
                # Matched successfully, remove the matched part and continue
                matched_part = match.group(0)
                print(f"Successfully matched: '{matched_part}'")
                remaining_filename = remaining_filename[len(matched_part):]
                print(f"Remaining filename: '{remaining_filename}'")
        except Exception as e:
            error_msg = f"Validation error for {token_name}: {str(e)}"
            errors.append(error_msg)
            break
    
    # After processing all tokens, check for unexpected trailing content
    if not errors and remaining_filename:
        error_msg = f"Unexpected content at the end: '{remaining_filename}'"
        errors.append(error_msg)
    
    print(f"Validation result: {len(errors)} errors")
    if errors:
        print(f"Errors: {errors}")
    
    return errors

def test_token_validation_fix():
    """Test the token validation fix with a specific case that would have failed before"""
    # Define token definitions similar to those in Sphere.yaml
    token_definitions = [
        {
            "name": "sequence",
            "type": "range",
            "min": 3,
            "max": 4,
            "regex": "[A-Z]{3,4}",
            "required": True
        },
        {
            "name": "shotNumber",
            "type": "numeric",
            "digits": 4,
            "regex": "\\d{4}",
            "required": True,
            "separator": "_"
        },
        {
            "name": "version",
            "type": "static",
            "regex": "v\\d{3}",
            "required": True,
            "description": "Version (e.g., v001)",
            "separator": "_"
        }
    ]
    
    # Test case: Valid filename
    print("\n=== Testing with valid filename ===")
    errors = validate_by_tokens("ABCD0123_v001", token_definitions)
    print(f"Valid filename test result: {'PASS' if not errors else 'FAIL'}")
    
    # Test case: Invalid version (this would have been misidentified before)
    print("\n=== Testing with invalid version ===")
    errors = validate_by_tokens("ABCD0123_v01", token_definitions)
    
    # Check if the error correctly identifies the version token
    version_error = any("Invalid 'version'" in error.lower() or "version" in error.lower() for error in errors)
    print(f"Invalid version test result: {'PASS' if version_error else 'FAIL - Version error not correctly identified'}")
    
    # Test case: Invalid shot number
    print("\n=== Testing with invalid shot number ===")
    errors = validate_by_tokens("ABCD123_v001", token_definitions)
    
    # Check if the error correctly identifies the shot number token
    shot_error = any("Invalid 'shotNumber'" in error.lower() or "shot" in error.lower() for error in errors)
    print(f"Invalid shot number test result: {'PASS' if shot_error else 'FAIL - Shot number error not correctly identified'}")

if __name__ == "__main__":
    test_token_validation_fix()