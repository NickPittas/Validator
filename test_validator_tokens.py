#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test script for token validation functionality in nuke_validator.py
"""

import os
import sys
import tempfile
import re

# Create a simplified version of the _validate_by_tokens function for testing
def validate_by_tokens(filename, token_definitions):
    """
    Validates a filename by individually checking each token based on the token definitions.
    This is a simplified version of the function from nuke_validator.py for testing purposes.
    
    Args:
        filename (str): The filename to validate
        token_definitions (list): List of token definitions
        
    Returns:
        list: List of validation errors, empty if all tokens are valid
    """
    print(f"Validating filename: '{filename}'")
    print(f"Token definitions count: {len(token_definitions) if token_definitions else 0}")
    
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
        print(f"Token required: {token_required}")
        print(f"Initial pattern: '{token_pattern}'")
        
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
            print(f"Range token: min={min_val}, max={max_val}")
            print(f"Updated pattern: '{token_pattern}'")
        elif token_type == "numeric":
            # Numeric tokens (like shot number) need to handle padding
            digits = token_def.get("digits", 4)
            # Ensure \d{n} format for digit matching
            if not re.search(r'\\d\{\d+\}', token_pattern):
                token_pattern = f"\\d{{{digits}}}"
                print(f"Numeric token with {digits} digits")
                print(f"Updated pattern: '{token_pattern}'")
        elif token_type == "enum":
            # Enum tokens (dropdown or multiselect)
            options = token_def.get("values", [])
            if options:
                # Create regex pattern for alternatives
                token_pattern = f"({'|'.join(re.escape(opt) for opt in options)})"
                print(f"Enum token with options: {options}")
                print(f"Updated pattern: '{token_pattern}'")
        
        try:
            # Build the part of the pattern to match against the remaining filename
            pattern_to_match = token_pattern
            
            # Add separator to the pattern if available and not the last token
            if separator and i < len(token_definitions) - 1:
                pattern_to_match += re.escape(separator)
                print(f"Added separator to pattern: '{pattern_to_match}'")
            
            # Try to match against the start of the remaining filename
            print(f"Attempting to match pattern '{pattern_to_match}' against '{remaining_filename}'")
            try:
                match_pattern = f"^{pattern_to_match}"
                print(f"Full match pattern: '{match_pattern}'")
                match = re.match(match_pattern, remaining_filename)
            except re.error as e:
                print(f"Regex error: {str(e)}")
                print(f"Trying alternate pattern format")
                match_pattern = r"^" + pattern_to_match
                print(f"Alternate match pattern: '{match_pattern}'")
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
                    # Use the first part of remaining_filename up to the next separator or end
                    actual_content = remaining_filename
                    if separator and separator in actual_content:
                        actual_content = actual_content.split(separator)[0]
                    
                    # Limit the actual content to a reasonable length for display
                    if len(actual_content) > 20:
                        actual_content = actual_content[:20] + "..."
                    
                    # Generate more specific error messages based on token type
                    if token_type == "range":
                        error_msg = f"Invalid '{display_name}': Expected {min_val}-{max_val} letters but found '{actual_content}'"
                        print(f"Adding error: {error_msg}")
                        errors.append(error_msg)
                    elif token_type == "numeric":
                        error_msg = f"Invalid '{display_name}': Expected {digits} digits but found '{actual_content}'"
                        print(f"Adding error: {error_msg}")
                        errors.append(error_msg)
                    elif token_type == "enum":
                        error_msg = f"Invalid '{display_name}': Expected one of [{', '.join(options)}] but found '{actual_content}'"
                        print(f"Adding error: {error_msg}")
                        errors.append(error_msg)
                    elif token_type == "static" and "value" in token_def:
                        expected_value = token_def.get("value", "")
                        error_msg = f"Invalid '{display_name}': Expected '{expected_value}' but found '{actual_content}'"
                        print(f"Adding error: {error_msg}")
                        errors.append(error_msg)
                    else:
                        # Include the expected pattern in the error message if available
                        if expected_pattern:
                            error_msg = f"Invalid '{display_name}': Expected format '{expected_pattern}' but found '{actual_content}'"
                        else:
                            error_msg = f"Invalid '{display_name}' format: Found '{actual_content}'"
                        print(f"Adding error: {error_msg}")
                        errors.append(error_msg)
                        
                    if separator:
                        # Improved separator check: if the next character is not the expected separator, report missing separator
                        prev_token_name = token_definitions[i-1]["name"] if i > 0 else None
                        print(f"Checking for separator '{separator}' in '{remaining_filename}'")
                        if not remaining_filename.startswith(separator):
                            prev_display_name = token_definitions[i-1].get("label", prev_token_name) if i > 0 else None
                            current_display_name = token_def.get("label", token_name)
                            
                            if prev_display_name:
                                error_msg = f"Missing separator '{separator}' between '{prev_display_name}' and '{current_display_name}'"
                                print(f"Adding error: {error_msg}")
                                errors.append(error_msg)
                            else:
                                error_msg = f"Missing separator '{separator}' before '{current_display_name}'"
                                print(f"Adding error: {error_msg}")
                                errors.append(error_msg)
                    break
                else:
                    # Token is optional, skip it
                    print(f"Token '{token_name}' is optional, skipping")
                    continue
            else:
                # Matched successfully, remove the matched part and continue
                matched_part = match.group(0)
                print(f"Successfully matched: '{matched_part}'")
                remaining_filename = remaining_filename[len(matched_part):]
                print(f"Remaining filename: '{remaining_filename}'")
                
                # Remove separator from remaining if it was part of the match
                if separator and i < len(token_definitions) - 1 and remaining_filename.startswith(separator):
                    print(f"Removing separator '{separator}' from remaining filename")
                    remaining_filename = remaining_filename[len(separator):]
                    print(f"Remaining filename after separator removal: '{remaining_filename}'")
                
        except re.error as e:
            error_msg = f"Error in regex pattern for {token_name}: {str(e)}"
            print(f"Regex error: {error_msg}")
            errors.append(error_msg)
            break
        except Exception as e:
            error_msg = f"Validation error for {token_name}: {str(e)}"
            print(f"Exception: {error_msg}")
            errors.append(error_msg)
            break
    
    # After processing all tokens, check for unexpected trailing content
    # Check if there's anything left in the filename that wasn't matched
    print(f"Token validation complete. Remaining filename: '{remaining_filename}'")
    if not errors and remaining_filename:
        # Try to identify what the unexpected content might be
        if '.' in remaining_filename:
            # It might be a file extension or something with an extension
            file_ext = remaining_filename.split('.')[-1]
            error_msg = f"Unexpected content at the end: '{remaining_filename}' (possibly incorrect file extension '{file_ext}')"
        else:
            error_msg = f"Unexpected content at the end: '{remaining_filename}'"
        print(f"Adding error: {error_msg}")
        errors.append(error_msg)
    
    print(f"Validation result: {len(errors)} errors")
    if errors:
        print(f"Errors: {errors}")
    
    return errors

def test_token_validation():
    """Test the token validation functionality with various filenames"""
    # Sample token definitions
    token_definitions = [
        {
            "name": "sequence",
            "label": "Sequence",
            "type": "range",
            "regex": "[A-Z]{MIN_VAL,MAX_VAL}",
            "min": 3,
            "max": 4,
            "required": True,
            "description": "3-4 uppercase letters"
        },
        {
            "name": "shotNumber",
            "label": "Shot Number",
            "type": "numeric",
            "regex": "\\d{4}",
            "digits": 4,
            "required": True,
            "description": "4-digit shot number",
            "separator": "_"
        },
        {
            "name": "version",
            "label": "Version",
            "type": "static",
            "regex": "v\\d{3}",
            "required": True,
            "description": "Version (e.g., v001)",
            "separator": "_"
        }
    ]
    
    # Test cases
    test_cases = [
        # Valid filename
        ("ABCD0123_v001", "Valid filename"),
        # Missing sequence
        ("0123_v001", "Missing sequence"),
        # Invalid sequence (too short)
        ("AB0123_v001", "Invalid sequence (too short)"),
        # Invalid shot number (too few digits)
        ("ABCD123_v001", "Invalid shot number (too few digits)"),
        # Missing version
        ("ABCD0123", "Missing version"),
        # Invalid version format
        ("ABCD0123_v1", "Invalid version format"),
        # Missing separator
        ("ABCD0123v001", "Missing separator")
    ]
    
    print("\n=== Testing token validation functionality ===\n")
    
    for filename, description in test_cases:
        print(f"\nTest case: {description}")
        print(f"Filename: '{filename}'")
        
        # Call the function
        errors = validate_by_tokens(filename, token_definitions)
        
        # Print results
        if errors:
            print(f"Validation failed with {len(errors)} errors:")
            for i, error in enumerate(errors, 1):
                print(f"  {i}. {error}")
        else:
            print("Validation passed - no errors found")
    
    print("\n=== Test completed ===")

if __name__ == "__main__":
    test_token_validation()