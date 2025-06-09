#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Nuke Validator - A tool to validate and fix common issues in Nuke scripts
"""

import os
import sys
import json
import yaml
import nuke
from typing import Dict, List, Optional, Tuple
import time
import psutil
import re
import tempfile

from PySide6 import QtWidgets
# Global instance to keep track of the panel
_rules_editor_panel_instance = None

def launch_rules_editor_panel():
    global _rules_editor_panel_instance
    if _rules_editor_panel_instance is not None and _rules_editor_panel_instance.isVisible():
        _rules_editor_panel_instance.activateWindow()
        _rules_editor_panel_instance.raise_()
        return

    # If no instance exists or it's not visible, create a new one
    from nuke_validator_ui import RulesEditorWidget
    _rules_editor_panel_instance = RulesEditorWidget() # Assuming RulesEditorWidget can be parentless for a top-level window
    _rules_editor_panel_instance.setWindowTitle("Nuke Rules Editor")
    _rules_editor_panel_instance.show()

def get_debug_file_path(filename):
    """
    Get a path to a debug file in the system's temporary directory.
    
    Args:
        filename: Base filename for the debug file
        
    Returns:
        Full path to the debug file in the temp directory
    """
    return os.path.join(tempfile.gettempdir(), filename)

class NukeValidator:
    def __init__(self, rules_file: str = None):
        """
        Initialize the validator with rules from a file
        
        Args:
            rules_file: Path to rules file (JSON or YAML)
        """
        self.rules_file_path = rules_file
        self.rules = self._load_rules(rules_file) if rules_file else {}
        self.issues = []
        self.fixes = []
        self.node_stats = {}
        
    def set_rules_file_path(self, rules_file_path: str):
        """
        Set a new rules file path and reload the rules
        
        Args:
            rules_file_path: Path to the new rules file
        """
        self.rules_file_path = rules_file_path
        self.rules = self._load_rules(rules_file_path)
        print(f"Validator rules updated from: {rules_file_path}")
        
    def _load_rules(self, rules_file: str) -> Dict:
        """
        Load rules from a JSON or YAML file
        
        Args:
            rules_file: Path to rules file
            
        Returns:
            Dictionary of rules
        """
        try:
            with open(rules_file, 'r') as f:
                if rules_file.endswith('.json'):
                    return json.load(f)
                elif rules_file.endswith('.yaml') or rules_file.endswith('.yml'):
                    return yaml.safe_load(f)
                else:
                    raise ValueError("Unsupported file format. Use JSON or YAML.")
        except Exception as e:
            print(f"Error loading rules: {e}")
            return {}
            
    def validate_script(self) -> Tuple[bool, List[Dict]]:
        """
        Validate the current Nuke script against the loaded rules
        
        Returns:
            Tuple of (success, issues)
        """
        self.issues = [] # Reset issues for this validation run
        self.fixes = []  # Reset fixes for this validation run
        
        # Reload rules every time validation is run
        # Assuming self.rules_file_path is set during __init__ or by a setter
        if hasattr(self, 'rules_file_path') and self.rules_file_path:
            self.rules = self._load_rules(self.rules_file_path)
        elif not self.rules: # If rules were not loaded at init and no path is set
            print("Warning: No rules loaded and no rules file path set for reloading.")


        # Get all nodes in the script
        nodes = nuke.allNodes()
        
        # Analyze nodes
        self._analyze_nodes(nodes)
        
        # Check for issues
        self._check_file_paths_and_naming(nodes) # Enhanced version of _check_write_paths
        self._check_frame_range(nodes) # No changes requested by user
        self._check_node_integrity(nodes) # New group for disabled nodes
        self._check_write_node_resolution(nodes) # Modified from _check_resolution
        self._check_colorspaces(nodes) # Checks Read and Write nodes
        self._check_write_node_channels(nodes) # New check
        self._check_render_settings(nodes) # New check for file-type specific settings
        self._check_versioning(nodes) # New or enhanced check
        # _check_plugin_compatibility REMOVED
        # _check_node_performance REMOVED
        # _check_node_metadata REMOVED
        self._check_node_dependencies(nodes) # Kept as per re-evaluation
        self._check_node_names(nodes)
        self._check_node_parameters(nodes) # Will be used for some render settings too
        self._check_node_connections(nodes)
        self._check_viewer_ip(nodes) # New check
        self._check_expressions_and_read_errors(nodes) # Enhanced from _check_node_expressions

        # Bounding box check was present, let's keep it unless specified for removal
        self._check_bounding_boxes(nodes)
        
        return len(self.issues) == 0, self.issues

    def _get_rule_severity(self, rule_category: str, rule_name: Optional[str] = None, default_severity: str = "warning") -> str:
        """Helper to get severity from rules, with fallback."""
        if rule_category in self.rules:
            if rule_name and rule_name in self.rules[rule_category]:
                return self.rules[rule_category][rule_name].get('severity', default_severity)
            return self.rules[rule_category].get('severity', default_severity)
        return default_severity
    def _analyze_nodes(self, nodes: List[nuke.Node]):
        """
        Analyze nodes and collect statistics
        
        Args:
            nodes: List of Nuke nodes
        """
        self.node_stats = {
            'total': len(nodes),
            'read_nodes': 0,
            'write_nodes': 0,
            'composite_nodes': 0,
            'effect_nodes': 0,
            'other_nodes': 0
        }
        
        for node in nodes:
            node_class = node.Class()
            if node_class == 'Read':
                self.node_stats['read_nodes'] += 1
            elif node_class == 'Write':
                self.node_stats['write_nodes'] += 1
            elif node_class in ['Merge', 'Grade', 'Keyer', 'Tracker']:
                self.node_stats['composite_nodes'] += 1
            elif node_class in ['Blur', 'Transform', 'Crop', 'Roto']:
                self.node_stats['effect_nodes'] += 1
            else:
                self.node_stats['other_nodes'] += 1
                
    def _check_colorspaces(self, nodes: List[nuke.Node]):
        """
        Check colorspace settings for Read and Write nodes with intelligent matching
        using dedicated lists from YAML configuration
        
        Args:
            nodes: List of Nuke nodes
        """
        # Check if we have the required configuration
        read_colorspaces = self.rules.get('read_node_allowed_colorspaces', [])
        write_colorspaces = self.rules.get('write_node_allowed_colorspaces', [])
        
        # Get severity settings
        read_severity = self.rules.get('colorspaces', {}).get('Read', {}).get('severity', 'warning')
        write_severity = self.rules.get('colorspaces', {}).get('Write', {}).get('severity', 'warning')
        
        for node in nodes:
            if node.Class() == 'Read' and read_colorspaces:
                colorspace = node['colorspace'].value()
                if not self._is_colorspace_allowed(colorspace, read_colorspaces):
                    issue = {
                        'type': 'colorspace',
                        'node': node.name(),
                        'node_type': 'Read',
                        'current': colorspace,
                        'allowed': read_colorspaces,
                        'severity': read_severity
                    }
                    self.issues.append(issue)
                    
            elif node.Class() == 'Write' and write_colorspaces:
                colorspace = node['colorspace'].value()
                if not self._is_colorspace_allowed(colorspace, write_colorspaces):
                    issue = {
                        'type': 'colorspace',
                        'node': node.name(),
                        'node_type': 'Write',
                        'current': colorspace,
                        'allowed': write_colorspaces,
                        'severity': write_severity
                    }
                    self.issues.append(issue)
    
    def _is_colorspace_allowed(self, current_colorspace: str, allowed_colorspaces: List[str]) -> bool:
        """
        Intelligent colorspace matching that understands similar colorspace names
        
        Args:
            current_colorspace: The current colorspace string
            allowed_colorspaces: List of allowed colorspace strings
            
        Returns:
            bool: True if current colorspace is considered allowed
        """
        # Exact match first
        if current_colorspace in allowed_colorspaces:
            return True
        
        # Normalize strings for comparison (lowercase, remove spaces/dashes)
        def normalize_colorspace(cs):
            return cs.lower().replace(' ', '').replace('-', '').replace('_', '')
        
        current_norm = normalize_colorspace(current_colorspace)
        
        # Define colorspace aliases and patterns with expanded mappings for Nuke's verbose names
        colorspace_patterns = {
            'acescg': ['acescg', 'aces', 'acesCg', 'aces-acescg', 'acesapplied', 'acescglin'],
            'aces2065': ['aces2065', 'aces20651', 'aces-2065-1'],
            'linear': ['linear', 'scenelinear', 'scene_linear', 'scenereferred', 'lin'],
            'srgb': ['srgb', 'sRGB', 'inputsrgb', 'input-srgb', 'outputsrgb', 'output-srgb'],
            'rec709': ['rec709', 'rec.709', 'inputrec709', 'input-rec709', 'outputrec709', 'output-rec709', 'r709'],
            'log': ['log', 'logc', 'alog', 'arri', 'log3g10'],
            'p3': ['p3', 'p3d65', 'displayp3', 'dci-p3'],
            'rec2020': ['rec2020', 'rec.2020', 'bt2020', 'bt.2020'],
            'sgamut': ['sgamut', 'sgamut3', 'sgamut3cine', 'slog3']
        }
        
        # Map from Nuke's verbose colorspace names to their short codes
        verbose_to_short = {
            # ACEScg variants
            'aces - acescg': 'acescglin',
            'acescg': 'acescglin',
            'scene_linear (aces - acescg)': 'acescglin',
            'compositing_linear (aces - acescg)': 'acescglin',
            'rendering (aces - acescg)': 'acescglin',
            'utility - linear - acescg': 'acescglin',
            
            # ACES2065-1 variants
            'aces - aces2065-1': 'aces2065',
            'aces2065-1': 'aces2065',
            
            # Other colorspaces
            'input - arri - v3 logc (ei800) - alexa': 'logc',
            'input - red - log3g10 - redwidegamutrgb': 'log3g10',
            'input - sony - slog3 - sgamut3.cine': 'slog3',
            'input - srgb': 'srgb',
            'input - rec.709': 'rec709',
            'output - srgb': 'srgb',
            'output - rec.709': 'rec709',
            'output - rec.2020': 'rec2020',
            'output - p3-dci': 'p3',
            'utility - linear - srgb': 'linear',
            'utility - raw': 'raw',
            'utility - log': 'log'
        }
        
        # Check if the current colorspace is a verbose name with a known short code
        current_norm_lower = current_colorspace.lower()
        if current_norm_lower in verbose_to_short:
            short_code = verbose_to_short[current_norm_lower]
            # Check if any allowed colorspace matches this short code
            for allowed in allowed_colorspaces:
                allowed_norm = normalize_colorspace(allowed)
                if short_code == allowed_norm or short_code in allowed_norm:
                    return True
        
        # Check if current colorspace matches any pattern group
        for pattern_group, patterns in colorspace_patterns.items():
            if any(pattern in current_norm for pattern in patterns):
                # Check if any allowed colorspace also matches this pattern group
                for allowed in allowed_colorspaces:
                    allowed_norm = normalize_colorspace(allowed)
                    if any(pattern in allowed_norm for pattern in patterns):
                        return True
        
        # Check for partial matches with key terms
        key_terms = ['acescg', 'aces2065', 'linear', 'srgb', 'rec709', 'log', 'p3', 'rec2020', 'sgamut']
        current_terms = [term for term in key_terms if term in current_norm]
        
        if current_terms:
            for allowed in allowed_colorspaces:
                allowed_norm = normalize_colorspace(allowed)
                # If they share at least one key term, consider it a match
                allowed_terms = [term for term in key_terms if term in allowed_norm]
                if any(term in allowed_terms for term in current_terms):
                    return True
        
        return False
    def _validate_filename_detailed(self, filename, pattern_str):
        """
        Provide detailed validation feedback using the sophisticated template-based validation
        from the UI system instead of basic regex checking.
        
        Args:
            filename: The filename to validate
            pattern_str: The regex pattern to validate against (used as fallback)
            
        Returns:
            list: List of validation errors, empty if valid
        """
        # First check if filename is empty to avoid unnecessary processing
        if not filename:
            return ["Empty filename provided"]
            
        try:
            # DEBUG: Log validation attempt with more details
            print(f"[DEBUG] ===== DETAILED VALIDATION START =====")
            print(f"[DEBUG] Validating filename: '{filename}'")
            print(f"[DEBUG] Using pattern: '{pattern_str}'")
            
            # Write to debug file for persistent logging
            with open(get_debug_file_path("validator_received_filename.txt"), "a") as f:
                f.write(f"DETAILED VALIDATION:\nFilename: '{filename}'\nPattern: '{pattern_str}'\n\n")
            
            # Import the sophisticated validation from the UI
            try:
                from nuke_validator_ui import FilenameRuleEditor, FILENAME_TOKENS
                print(f"[Validator] Successfully imported UI validation components")
            except ImportError as import_err:
                print(f"[Validator] UI import failed: {import_err}")
                print(f"[Validator] Falling back to basic validation")
                # Make sure to return all errors from basic validation
                basic_errors = self._basic_filename_validation(filename, pattern_str)
                print(f"[Validator] Basic validation returned {len(basic_errors)} errors")
                return basic_errors
            
            # Check if we have filename tokens in the rules (from the UI system)
            filename_tokens = self.rules.get('file_paths', {}).get('filename_tokens', [])
            
            if not filename_tokens:
                print(f"[Validator] No filename tokens found in rules, falling back to basic validation")
                # Make sure to return all errors from basic validation
                basic_errors = self._basic_filename_validation(filename, pattern_str)
                print(f"[Validator] Basic validation returned {len(basic_errors)} errors")
                return basic_errors
            
            try:
                # Create a temporary FilenameRuleEditor to use its validation logic
                temp_editor = FilenameRuleEditor()
                
                # Load the token configuration from rules
                token_loaded = False
                for token_cfg in filename_tokens:
                    if "name" in token_cfg:
                        # Find the token definition
                        token_def = next((t for t in FILENAME_TOKENS if t["name"] == token_cfg["name"]), None)
                        if token_def:
                            temp_editor.template_builder.add_token(token_def)
                            token_loaded = True
                            
                            # Set the control values from the saved configuration
                            if temp_editor.template_builder.token_widgets:
                                widget = temp_editor.template_builder.token_widgets[-1]
                                if hasattr(widget, 'token_configs') and len(widget.token_configs) > 0:
                                    # Update the token config with saved values
                                    config = widget.token_configs[-1]
                                    config["value"] = token_cfg.get("value")
                                    config["separator"] = token_cfg.get("separator", "_")
                
                if not token_loaded:
                    print(f"[Validator] Failed to load any tokens, falling back to basic validation")
                    return self._basic_filename_validation(filename, pattern_str)
                    
                # Generate the regex pattern
                temp_editor.update_regex()
                
                # Use the sophisticated validation from the UI
                detailed_errors = temp_editor.get_validation_errors(filename)
                print(f"[DEBUG] Completed detailed validation with {len(detailed_errors)} errors")
                if detailed_errors:
                    print(f"[DEBUG] Errors found: {detailed_errors}")
                else:
                    print(f"[DEBUG] No errors found - filename is valid")
                
                print(f"[DEBUG] ===== DETAILED VALIDATION END =====")
                
                # Write results to debug file
                with open(get_debug_file_path("validator_received_filename.txt"), "a") as f:
                    f.write(f"Validation result: {len(detailed_errors)} errors\n")
                    if detailed_errors:
                        f.write(f"Errors: {detailed_errors}\n\n")
                    else:
                        f.write("No errors - filename is valid\n\n")
                
                if detailed_errors:
                    # Ensure we return the detailed errors for display to the user
                    print(f"[DEBUG] Returning {len(detailed_errors)} detailed errors to caller")
                    return detailed_errors
                else:
                    return []  # No errors found
                    
            except AttributeError as attr_err:
                # Specific handling for common attribute errors (e.g., missing methods)
                print(f"[Validator] UI attribute error: {attr_err}")
                # Make sure to return all errors from basic validation
                basic_errors = self._basic_filename_validation(filename, pattern_str)
                print(f"[Validator] Basic validation returned {len(basic_errors)} errors")
                return basic_errors
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"[Validator] Unexpected error in validation: {e}")
            print(f"[Validator] Error details: {error_details}")
            # Still provide some feedback rather than crashing
            return [f"Validation system error: {str(e)}", 
                    "Contact administrator if this error persists"]
    
    def _basic_filename_validation(self, filename, pattern_str=None):
        """
        Basic filename validation using regex patterns and token-based validation.
            pattern_str: Optional regex pattern override
        
        Returns:
            List of validation errors, empty if validation passed
        """
        import re
        errors = []
        
        print(f"[DEBUG] ===== BASIC VALIDATION START =====")
        print(f"[DEBUG] Validating filename: '{filename}'")
        
        # Write to debug file
        with open(get_debug_file_path("validator_received_filename.txt"), "a") as f:
            f.write(f"BASIC VALIDATION:\nFilename: '{filename}'\n")
        
        if not filename:
            print(f"[DEBUG] Filename is empty")
            return ["Filename is empty"]
        
        # Get the pattern and tokens configuration
        if not pattern_str:
            pattern_str = self.rules.get('file_paths', {}).get('filename_template', '')
            if not pattern_str:
                print(f"[DEBUG] No filename pattern defined in rules")
                return ["No filename pattern defined in rules"]
                
        print(f"[DEBUG] Original pattern: '{pattern_str}'")
        
        # Fix any quantifiers that might not have proper syntax (e.g., \d4 -> \d{4})
        pattern_str = re.sub(r'\\d(\d+)(?!\\})', r'\\d{\1}', pattern_str)
        # Fix character class quantifiers (e.g., [A-Za-z]4 -> [A-Za-z]{4})
        pattern_str = re.sub(r'(\[[^\]]+\])(\d+)(?!\})', r'\1{\2}', pattern_str)
        # Handle sequence token with MIN_VAL,MAX_VAL format
        pattern_str = pattern_str.replace("MIN_VAL,MAX_VAL", "3,4")  # Default to 3-4 characters
        
        print(f"[DEBUG] Processed pattern: '{pattern_str}'")
        
        # Write pattern to debug file
        with open(get_debug_file_path("validator_received_filename.txt"), "a") as f:
            f.write(f"Original pattern: '{pattern_str}'\n")
            f.write(f"Processed pattern: '{pattern_str}'\n")
        # Get token definitions for detailed validation if needed
        filename_tokens = self.rules.get('file_paths', {}).get('filename_tokens', [])
        try:
            # Step 1: Try full regex match first for quick validation
            pattern = re.compile(pattern_str)
            match = pattern.match(filename)
            
            print(f"[DEBUG] Attempting regex match: '{filename}' against pattern '{pattern_str}'")
            print(f"[DEBUG] Match result: {match is not None}")
            
            # Write match result to debug file
            with open(get_debug_file_path("validator_received_filename.txt"), "a") as f:
                f.write(f"Regex match result: {match is not None}\n")
            
            if match:
                # Full regex match succeeded
                print(f"[DEBUG] Full regex match succeeded")
                # Check for version formatting issues
                version_match = re.search(r'v(\d+)', filename, re.IGNORECASE)
                if version_match:
                    version_num = version_match.group(1)
                    print(f"[DEBUG] Found version number: '{version_num}'")
                    # Check if version number is properly zero-padded
                    if len(version_num) < 3:  # Standard is at least 3 digits (v001)
                        print(f"[DEBUG] Version number '{version_num}' not properly zero-padded")
                        errors.append(f"Version number '{version_num}' should be zero-padded to at least 3 digits (e.g., v001)")
                # If no version issues, filename is valid
                if not errors:
                    print(f"[DEBUG] No errors, validation passed")
                    print(f"[DEBUG] ===== BASIC VALIDATION END =====")
                    return []  # No errors, validation passed
            else:
                # Step 2: Full regex match failed, perform token-by-token validation
                print(f"[DEBUG] Full regex match failed")
                # Only proceed with detailed validation if we have token definitions
                if filename_tokens:
                    # Use token-by-token validation for detailed error messages
                    token_errors = self._validate_by_tokens(filename, filename_tokens)
                    if token_errors:
                        print(f"[DEBUG] Token validation returned {len(token_errors)} specific errors")
                        errors.extend(token_errors)
                    else:
                        print(f"[DEBUG] Token validation returned no specific errors")
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
                            if not re.match(f"^{pattern_part}$", filename_part):
                                errors.append(f"Part {i+1} '{filename_part}' doesn't match expected format '{pattern_part}'")
                        except Exception:
                            # Skip problematic part comparisons without printing
                            pass
                
                # If still no specific errors detected, provide a general message
                if not errors:
                    errors.append(f"Filename '{filename}' doesn't match the expected pattern. Check format and separators.")
                
                return errors
            
        except re.error as e:
            print(f"[DEBUG] Regex error: {str(e)}")
            print(f"[DEBUG] ===== BASIC VALIDATION END =====")
            
            # Write error to debug file
            with open(get_debug_file_path("validator_received_filename.txt"), "a") as f:
                f.write(f"Regex error: {str(e)}\n\n")
                
            return [f"Regex validation error: {str(e)}", "Check the pattern configuration in rules.yaml"]
        except Exception as e:
            print(f"[DEBUG] Validation error: {str(e)}")
            print(f"[DEBUG] ===== BASIC VALIDATION END =====")
            
            # Write error to debug file
            with open(get_debug_file_path("validator_received_filename.txt"), "a") as f:
                f.write(f"Validation error: {str(e)}\n\n")
                
            return [f"Validation error: {str(e)}"]
    
    def _check_file_paths_and_naming(self, nodes: List[nuke.Node]):
        """
        Check file paths (relative/absolute) and naming conventions for Write nodes.
        Implements dynamic regex checking for naming patterns and per-token validation.
        """
        if 'file_paths' not in self.rules:
            return

        path_rules = self.rules['file_paths']
        severity_relative = path_rules.get('severity_relative_path', 'warning')
        severity_naming = path_rules.get('severity_naming_pattern', 'warning')
        token_defs = self.rules.get('token_definitions', {})

        for node in nodes:
            if node.Class() == 'Write':
                file_path = node['file'].value()
                if not file_path:
                    self.issues.append({
                        'type': 'missing_file_path',
                        'node': node.name(),
                        'node_type': 'Write',
                        'current': 'None',
                        'expected': 'A valid file path',
                        'severity': 'error'
                    })
                    continue

                # 1. Check for relative paths
                if path_rules.get('relative_path_required', False):
                    is_relative = not os.path.isabs(file_path)
                    if not is_relative:
                        self.issues.append({
                            'type': 'absolute_path_detected',
                            'node': node.name(),
                            'node_type': 'Write',
                            'current': file_path,
                            'expected': 'A relative path',
                            'severity': severity_relative
                        })
                # 2. Dynamic Naming Convention Check (using regex)
                pattern_str = path_rules.get('naming_pattern_regex')
                filename = os.path.basename(file_path)
                if not pattern_str:
                    self.issues.append({
                        'type': 'missing_naming_pattern_regex',
                        'node': node.name(),
                        'node_type': 'Write',
                        'current': filename,
                        'expected': 'A naming_pattern_regex in rules.yaml',
                        'severity': 'error'
                    })
                    continue
                try:
                    print(f"[DEBUG] ===== VALIDATION CHECK IN _check_file_paths_and_naming =====")
                    print(f"[DEBUG] Checking filename '{filename}' against regex: {pattern_str}")
                    
                    # Write to debug file
                    with open(get_debug_file_path("regex_debug.txt"), "a") as f:
                        f.write(f"Checking filename: '{filename}'\n")
                        f.write(f"Against pattern: '{pattern_str}'\n")
                    
                    match_result = re.match(pattern_str, filename)
                    print(f"[DEBUG] Match result: {match_result is not None}")
                    
                    # Write match result to debug file
                    with open(get_debug_file_path("regex_debug.txt"), "a") as f:
                        f.write(f"Match result: {match_result is not None}\n\n")
                    
                    if not match_result:
                        print(f"[DEBUG] No match - proceeding to detailed validation")
                        # Use detailed validation instead of generic regex error
                        detailed_errors = self._validate_filename_detailed(filename, pattern_str)
                        
                        if detailed_errors:
                            # Create specific error for the most important issues
                            primary_error = detailed_errors[0]  # Take the first/most important error
                            
                            # Extract token name from error message if possible
                            token_name = "unknown"
                            for error in detailed_errors:
                                if "Invalid '" in error and "': " in error:
                                    # Extract the token name from error messages like "Invalid 'TokenName': ..."
                                    # This correctly identifies which token has the validation error
                                    token_name = error.split("Invalid '")[1].split("': ")[0]
                                    print(f"[DEBUG] Extracted token name from error: '{token_name}'")
                                    break
                            
                            # Ensure we have a clear primary message that indicates this is a filename issue
                            # We don't need to add the redundant placeholder message anymore
                            # The base message in the details string will serve this purpose
                            
                            # Create a more descriptive primary error message
                            primary_message = f"Filename format error: {primary_error}"
                            
                            # Log the detailed errors for debugging
                            print(f"[DEBUG] Detailed validation errors: {detailed_errors}")
                            
                            # Directly construct the details string to include base message and all token errors
                            # Start with a base message about filename format
                            base_message = "Filename doesn't match the expected format:"
                            
                            # Filter out the redundant placeholder message
                            filtered_errors = [error for error in detailed_errors if error != "Filename doesn't match the expected format - see specific token errors below"]
                            
                            # Ensure we're using all errors from _validate_by_tokens
                            # This is critical for displaying the correct token-specific error messages
                            details = base_message + "\n" + "\n".join([f"- {error}" for error in filtered_errors]) if filtered_errors else base_message
                            
                            self.issues.append({
                                'type': 'naming_convention_violation',
                                'node': node.name(),
                                'node_type': 'Write',
                                'current': filename,
                                'expected': primary_message,
                                'severity': severity_naming,
                                'details': details,  # Directly constructed details string with base message and all token errors
                                'token_name': token_name  # Add the token name that caused the failure
                            })
                        else:
                            # Fallback if detailed validation doesn't catch anything
                            self.issues.append({
                                'type': 'naming_convention_violation',
                                'node': node.name(),
                                'node_type': 'Write',
                                'current': filename,
                                'expected': "Filename format validation issues",
                                'severity': severity_naming
                            })
                except re.error as e:
                    self.issues.append({
                        'type': 'regex_error',
                        'node': node.name(),
                        'node_type': 'Write',
                        'current': f"Regex: {pattern_str}",
                        'expected': f"Valid regex pattern. Error: {e}",
                        'severity': 'error'
                    })
    # The deprecated _validate_tokens method has been removed in favor of the new _validate_by_tokens method
    # that provides detailed token-by-token validation with better error reporting
        
    def _validate_by_tokens(self, filename, token_definitions):
        """
        Validates a filename by individually checking each token based on the token definitions from YAML.
        This method is called when the full regex match fails and provides detailed error messages.
        
        Args:
            filename (str): The filename to validate
            token_definitions (list): List of token definitions from YAML
            
        Returns:
            list: List of validation errors, empty if all tokens are valid
            
        Note:
            This function ONLY returns error strings and does NOT create separate validation issues.
            The returned error strings will be used in the 'details' field of a single
            'naming_convention_violation' issue created by the calling function.
        """
        print(f"[DEBUG] ===== TOKEN VALIDATION START =====")
        print(f"[DEBUG] Validating filename: '{filename}'")
        print(f"[DEBUG] Token definitions count: {len(token_definitions) if token_definitions else 0}")
        
        # Write to debug file
        with open(get_debug_file_path("pattern_debug.txt"), "a") as f:
            f.write(f"TOKEN VALIDATION:\nFilename: '{filename}'\n")
            f.write(f"Token definitions: {token_definitions}\n\n")
        
        if not filename or not token_definitions:
            error_msg = "Cannot validate: Missing filename or token definitions"
            print(f"[DEBUG] {error_msg}")
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
            
            print(f"[DEBUG] Processing token {i+1}: {token_name} (type: {token_type})")
            print(f"[DEBUG] Token required: {token_required}")
            print(f"[DEBUG] Initial pattern: '{token_pattern}'")
            
            # If there's a custom separator, use it
            if "separator" in token_def:
                separator = token_def["separator"]
                print(f"[DEBUG] Using separator: '{separator}'")

            
            # Special handling for different token types
            if token_type == "static":
                # Static tokens have fixed regex patterns
                pass
            elif token_type == "range":
                # Range tokens (like sequence) need to replace MIN_VAL,MAX_VAL placeholders
                min_val = token_def.get("min_value", token_def.get("min", 2))
                max_val = token_def.get("max_value", token_def.get("max", 4))
                token_pattern = token_pattern.replace("MIN_VAL,MAX_VAL", f"{min_val},{max_val}")
                print(f"[DEBUG] Range token: min={min_val}, max={max_val}")
                print(f"[DEBUG] Updated pattern: '{token_pattern}'")
            elif token_type == "numeric":
                # Numeric tokens (like shot number) need to handle padding
                digits = token_def.get("digits", 4)
                # Ensure \d{n} format for digit matching
                if not re.search(r'\\d\{\d+\}', token_pattern):
                    token_pattern = f"\\d{{{digits}}}"
                    print(f"[DEBUG] Numeric token with {digits} digits")
                    print(f"[DEBUG] Updated pattern: '{token_pattern}'")
            elif token_type == "enum":
                # Enum tokens (dropdown or multiselect)
                options = token_def.get("values", [])
                if options:
                    # Create regex pattern for alternatives
                    token_pattern = f"({'|'.join(re.escape(opt) for opt in options)})"
                    print(f"[DEBUG] Enum token with options: {options}")
                    print(f"[DEBUG] Updated pattern: '{token_pattern}'")
            
            try:
                # Build the part of the pattern to match against the remaining filename
                pattern_to_match = token_pattern
                
                # Add separator to the pattern if available and not the last token
                if separator and i < len(token_definitions) - 1:
                    pattern_to_match += re.escape(separator)
                    print(f"[DEBUG] Added separator to pattern: '{pattern_to_match}'")
                
                # Try to match against the start of the remaining filename
                print(f"[DEBUG] Attempting to match pattern '{pattern_to_match}' against '{remaining_filename}'")
                try:
                    match_pattern = f"^{pattern_to_match}"
                    print(f"[DEBUG] Full match pattern: '{match_pattern}'")
                    match = re.match(match_pattern, remaining_filename)
                except re.error as e:
                    print(f"[DEBUG] Regex error: {str(e)}")
                    print(f"[DEBUG] Trying alternate pattern format")
                    match_pattern = r"^" + pattern_to_match
                    print(f"[DEBUG] Alternate match pattern: '{match_pattern}'")
                    match = re.match(match_pattern, remaining_filename)
                
                print(f"[DEBUG] Match result: {match is not None}")
                
                if not match:
                    # If the token is required, report an error
                    if token_required:
                        # If there's no match and the token is required, add a specific error
                        display_name = token_def.get("label", token_name)
                        print(f"[DEBUG] No match for required token '{display_name}'")
                        
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
                        
                        # Generate more specific error messages based on token type and name
                        # Generate more specific error messages based on token type, not token name
                        if token_type == "range":
                            error_msg = f"Invalid '{display_name}': Expected {min_val}-{max_val} letters but found '{actual_content}'"
                            print(f"[DEBUG] Adding error: {error_msg}")
                            errors.append(error_msg)
                        elif token_type == "numeric":
                            error_msg = f"Invalid '{display_name}': Expected {digits} digits but found '{actual_content}'"
                            print(f"[DEBUG] Adding error: {error_msg}")
                            errors.append(error_msg)
                        elif token_type == "enum":
                            error_msg = f"Invalid '{display_name}': Expected one of [{', '.join(options)}] but found '{actual_content}'"
                            print(f"[DEBUG] Adding error: {error_msg}")
                            errors.append(error_msg)
                        elif token_type == "static" and "value" in token_def:
                            expected_value = token_def.get("value", "")
                            error_msg = f"Invalid '{display_name}': Expected '{expected_value}' but found '{actual_content}'"
                            print(f"[DEBUG] Adding error: {error_msg}")
                            errors.append(error_msg)
                        else:
                            # Include the expected pattern in the error message if available
                            if expected_pattern:
                                error_msg = f"Invalid '{display_name}': Expected format '{expected_pattern}' but found '{actual_content}'"
                            else:
                                error_msg = f"Invalid '{display_name}' format: Found '{actual_content}'"
                            print(f"[DEBUG] Adding error: {error_msg}")
                            errors.append(error_msg)
                            
                        if separator:
                            # Improved separator check: if the next character is not the expected separator, report missing separator
                            prev_token_name = token_definitions[i-1]["name"] if i > 0 else None
                            print(f"[DEBUG] Checking for separator '{separator}' in '{remaining_filename}'")
                            if not remaining_filename.startswith(separator):
                                prev_display_name = token_definitions[i-1].get("label", prev_token_name) if i > 0 else None
                                current_display_name = token_def.get("label", token_name)
                                
                                if prev_display_name:
                                    error_msg = f"Missing separator '{separator}' between '{prev_display_name}' and '{current_display_name}'"
                                    print(f"[DEBUG] Adding error: {error_msg}")
                                    errors.append(error_msg)
                                else:
                                    error_msg = f"Missing separator '{separator}' before '{current_display_name}'"
                                    print(f"[DEBUG] Adding error: {error_msg}")
                                    errors.append(error_msg)
                        break
                    else:
                        # Token is optional, skip it
                        print(f"[DEBUG] Token '{token_name}' is optional, skipping")
                        continue
                else:
                    # Matched successfully, remove the matched part and continue
                    matched_part = match.group(0)
                    print(f"[DEBUG] Successfully matched: '{matched_part}'")
                    remaining_filename = remaining_filename[len(matched_part):]
                    print(f"[DEBUG] Remaining filename: '{remaining_filename}'")
                    
                    # Remove separator from remaining if it was part of the match
                    if separator and i < len(token_definitions) - 1 and remaining_filename.startswith(separator):
                        print(f"[DEBUG] Removing separator '{separator}' from remaining filename")
                        remaining_filename = remaining_filename[len(separator):]
                        print(f"[DEBUG] Remaining filename after separator removal: '{remaining_filename}'")
                    
            except re.error as e:
                error_msg = f"Error in regex pattern for {token_name}: {str(e)}"
                print(f"[DEBUG] Regex error: {error_msg}")
                errors.append(error_msg)
                break
            except Exception as e:
                error_msg = f"Validation error for {token_name}: {str(e)}"
                print(f"[DEBUG] Exception: {error_msg}")
                errors.append(error_msg)
                break
        
        # After processing all tokens, check for unexpected trailing content
        # Check if there's anything left in the filename that wasn't matched
        print(f"[DEBUG] Token validation complete. Remaining filename: '{remaining_filename}'")
        if not errors and remaining_filename:
            # Try to identify what the unexpected content might be
            if '.' in remaining_filename:
                # It might be a file extension or something with an extension
                file_ext = remaining_filename.split('.')[-1]
                error_msg = f"Unexpected content at the end: '{remaining_filename}' (possibly incorrect file extension '{file_ext}')"
            else:
                error_msg = f"Unexpected content at the end: '{remaining_filename}'"
            print(f"[DEBUG] Adding error: {error_msg}")
            errors.append(error_msg)
        
        print(f"[DEBUG] Validation result: {len(errors)} errors")
        if errors:
            print(f"[DEBUG] Errors: {errors}")
        
        # Write results to debug file
        with open(get_debug_file_path("pattern_debug.txt"), "a") as f:
            f.write(f"Validation result: {len(errors)} errors\n")
            if errors:
                f.write(f"Errors: {errors}\n\n")
            else:
                f.write("No errors - filename is valid\n\n")
                
        print(f"[DEBUG] ===== TOKEN VALIDATION END =====")
            
        # This function ONLY returns error strings and does NOT create validation issues
        return errors
    def _check_bounding_boxes(self, nodes: List[nuke.Node]):
        """
        Check bounding boxes for Read and Write nodes
        
        Args:
            nodes: List of Nuke nodes
        """
        if 'bounding_boxes' not in self.rules:
            return
            
        for node in nodes:
            node_class = node.Class()
            # Check if there are bounding_box rules defined for this specific node class
            if node_class in self.rules.get('bounding_boxes', {}):
                bbox_knob = node.knob('bbox') # Attempt to get the 'bbox' knob
                
                if bbox_knob: # Proceed only if the 'bbox' knob exists on this node
                    bbox = bbox_knob.value()
                    min_x, min_y, max_x, max_y = bbox
                    
                    # Check if bbox is empty
                    if min_x == max_x or min_y == max_y:
                        issue = {
                            'type': 'empty_bbox',
                            'node': node.name(),
                            'node_type': node_class,
                            'current': f"x:{min_x} y:{min_y} r:{max_x} t:{max_y}",
                            'expected': 'Non-empty bounding box',
                            'severity': self.rules['bounding_boxes'][node_class].get('severity', 'warning')
                        }
                        self.issues.append(issue)
                # else:
                    # If rules exist for this node_class in bounding_boxes, but it has no 'bbox' knob (e.g., a Write node),
                    # this specific check for an empty 'bbox' knob is not applicable.
                    # A different rule/logic would be needed to check a Write node's effective bbox.
                    # print(f"DEBUG: Node {node.name()} ({node_class}) listed in bounding_box rules but has no 'bbox' knob.")
                    pass
    # _check_node_performance REMOVED as per user feedback
    def _check_frame_range(self, nodes: List[nuke.Node]):
        """
        Check frame range settings
        
        Args:
            nodes: List of Nuke nodes
        """
        if 'frame_range' not in self.rules:
            return
            
        # Get script frame range
        script_frame_range = nuke.root().knob('first_frame').value(), nuke.root().knob('last_frame').value()
        
        # Check if frame range matches requirements
        if 'min_frames' in self.rules['frame_range']:
            min_frames = self.rules['frame_range']['min_frames']
            if (script_frame_range[1] - script_frame_range[0] + 1) < min_frames:
                issue = {
                    'type': 'frame_range',
                    'node': 'Root',
                    'node_type': 'Root',
                    'current': f"{script_frame_range[0]}-{script_frame_range[1]}",
                    'expected': f"at least {min_frames} frames",
                    'severity': self.rules['frame_range'].get('severity', 'warning')
                }
                self.issues.append(issue)
                
        # Check if frame range matches specific values
        if 'start_frame' in self.rules['frame_range'] or 'end_frame' in self.rules['frame_range']:
            current_start = script_frame_range[0]
            current_end = script_frame_range[1]
            
            if 'start_frame' in self.rules['frame_range']:
                expected_start = self.rules['frame_range']['start_frame']
                if current_start != expected_start:
                    issue = {
                        'type': 'frame_range_start',
                        'node': 'Root',
                        'node_type': 'Root',
                        'current': current_start,
                        'expected': expected_start,
                        'severity': self.rules['frame_range'].get('severity', 'warning')
                    }
                    self.issues.append(issue)
                    
            if 'end_frame' in self.rules['frame_range']:
                expected_end = self.rules['frame_range']['end_frame']
                if current_end != expected_end:
                    issue = {
                        'type': 'frame_range_end',
                        'node': 'Root',
                        'node_type': 'Root',
                        'current': current_end,
                        'expected': expected_end,
                        'severity': self.rules['frame_range'].get('severity', 'warning')
                    }
                    self.issues.append(issue)
                    
    def _check_write_node_resolution(self, nodes: List[nuke.Node]):
        """
        Check resolution settings for Write nodes.
        """
        if 'write_node_resolution' not in self.rules:
            return
        
        resolution_rules = self.rules['write_node_resolution']
        allowed_formats = resolution_rules.get('allowed_formats', [])
        severity = self._get_rule_severity('write_node_resolution')

        if not allowed_formats:
            return

        for node in nodes:
            if node.Class() == 'Write':
                # Nuke Write nodes don't have a direct 'format' knob like the root.
                # The output format is determined by the 'file_type' and potentially
                # knobs specific to that file_type, or inherited from input.
                # This check might be better if it checks the actual output resolution
                # if possible, or specific knobs if they exist for common file types.
                # For now, we'll check the 'format' knob if it exists,
                # or rely on a 'file_type' specific check if that's how rules are defined.
                
                # A more robust check would involve checking the format of the input to the Write node,
                # or specific knobs like 'render_format' if available.
                # For simplicity in Stage 1, if a Write node has a 'format' knob (unlikely for standard Write),
                # we'd check it. Otherwise, this rule needs more specific definition for Write nodes.
                # Let's assume for now the rule implies checking the input format to the Write node.
                
                try:
                    # Get format from the input of the Write node
                    input_node = node.input(0) # Get the first input
                    if input_node:
                        # Get format from the input node at the current frame
                        # This requires rendering a single frame, which can be slow.
                        # A simpler check might be to look for a Reformat node immediately upstream.
                        # For now, let's check the 'format' knob of the Write node itself, if it exists,
                        # or the format of its input if easily accessible without rendering.
                        
                        # Nuke's Python API doesn't directly give the output format of a Write node
                        # without rendering or complex graph traversal.
                        # A common practice is to ensure a Reformat node is used before a Write node
                        # to explicitly set the output resolution.
                        
                        # Let's check the 'format' knob of the Write node's input if it's a Read node
                        # or if the Write node itself has a format knob (less common).
                        node_format_knob = node.knob('format')
                        current_format_name = ""

                        if node_format_knob:
                             current_format_name = node_format_knob.value().name() \
                                if hasattr(node_format_knob.value(), 'name') else str(node_format_knob.value())
                        elif input_node and input_node.knob('format'):
                            current_format_name = input_node.knob('format').value().name() \
                                if hasattr(input_node.knob('format').value(), 'name') else str(input_node.knob('format').value())
                        else:
                            # Could try to get format from input node's metadata if available
                            # This is becoming complex for a direct check.
                            # For now, we'll skip if not easily found.
                            # A better rule might be "Write node must be preceded by a Reformat node with allowed format"
                            pass


                        if current_format_name and current_format_name not in allowed_formats:
                            self.issues.append({
                                'type': 'write_node_resolution_mismatch',
                                'node': node.name(),
                                'node_type': 'Write',
                                'current': current_format_name,
                                'expected': f"One of: {', '.join(allowed_formats)}",
                                'severity': severity
                            })
                    # else:
                        # Write node has no input, which is an issue itself but handled by _check_node_connections
                except Exception as e:
                    self.issues.append({
                        'type': 'resolution_check_error',
                        'node': node.name(),
                        'node_type': 'Write',
                        'current': f"Error checking resolution: {e}",
                        'expected': "N/A",
                        'severity': 'error'
                    })
    def _check_color_space_consistency(self, nodes: List[nuke.Node]):
        """
        Check for consistent color space usage across the script
        
        Args:
            nodes: List of Nuke nodes
        """
        if 'color_space_consistency' not in self.rules:
            return
            
        # Get all Read nodes
        read_nodes = [node for node in nodes if node.Class() == 'Read']
        
        # Check if all Read nodes have the same color space
        if read_nodes:
            first_colorspace = read_nodes[0]['colorspace'].value()
            for node in read_nodes[1:]:
                colorspace = node['colorspace'].value()
                if colorspace != first_colorspace:
                    issue = {
                        'type': 'color_space_consistency',
                        'node': node.name(),
                        'node_type': 'Read',
                        'current': colorspace,
                        'expected': first_colorspace,
                        'severity': self.rules['color_space_consistency'].get('severity', 'warning')
                    }
                    self.issues.append(issue)
                    
    # _check_plugin_compatibility REMOVED
    def _check_node_dependencies(self, nodes: List[nuke.Node]):
        """
        Check for node dependencies
        
        Args:
            nodes: List of Nuke nodes
        """
        if 'node_dependencies' not in self.rules:
            return
            
        # Get all nodes that have dependencies
        dependent_nodes = [node for node in nodes if node.Class() in self.rules['node_dependencies']]
        
        for node in dependent_nodes:
            # Check if node has all required dependencies
            if node.Class() in self.rules['node_dependencies']:
                required_dependencies = self.rules['node_dependencies'][node.Class()]
                for dependency in required_dependencies:
                    if not any(n.Class() == dependency for n in nodes):
                        issue = {
                            'type': 'missing_dependency',
                            'node': node.name(),
                            'node_type': node.Class(),
                            'missing': dependency,
                            'severity': self.rules['node_dependencies'].get('severity', 'warning')
                        }
                        self.issues.append(issue)
                        
    def _check_node_names(self, nodes: List[nuke.Node]):
        """
        Check for valid node names
        
        Args:
            nodes: List of Nuke nodes
        """
        if 'node_names' not in self.rules:
            return
            
        # Get all nodes
        for node in nodes:
            # Check if node name matches the required pattern
            if 'pattern' in self.rules['node_names']:
                pattern = self.rules['node_names']['pattern']
                if not re.match(pattern, node.name()):
                    issue = {
                        'type': 'invalid_node_name',
                        'node': node.name(),
                        'node_type': node.Class(),
                        'current': node.name(),
                        'expected': pattern,
                        'severity': self.rules['node_names'].get('severity', 'warning')
                    }
                    self.issues.append(issue)
                    
    def _check_node_parameters(self, nodes: List[nuke.Node]):
        """
        Check for valid node parameters
        
        Args:
            nodes: List of Nuke nodes
        """
        if 'node_parameters' not in self.rules:
            return
            
        for node in nodes:
            node_class_str = node.Class()
            if node_class_str in self.rules.get('node_parameters', {}):
                class_rules = self.rules['node_parameters'].get(node_class_str, {})
                if not isinstance(class_rules, dict):
                    # print(f"Warning: Rules for node class '{node_class_str}' under 'node_parameters' are not a dictionary. Skipping. Value: {class_rules}")
                    continue # Skip if not a dictionary

                for param, rules in class_rules.items():
                    if 'allowed_values' in rules:
                        current_value = node[param].value()
                        if current_value not in rules['allowed_values']:
                            issue = {
                                'type': 'invalid_parameter',
                                'node': node.name(),
                                'node_type': node.Class(),
                                'parameter': param,
                                'current': current_value,
                                'allowed': rules['allowed_values'],
                                'severity': rules.get('severity', 'warning')
                            }
                            self.issues.append(issue)
                            
    def _check_node_connections(self, nodes: List[nuke.Node]):
        """
        Check for valid node connections
        
        Args:
            nodes: List of Nuke nodes
        """
        if 'node_connections' not in self.rules:
            return
            
        for node in nodes:
            if node.Class() in self.rules['node_connections']:
                for input_port, rules in self.rules['node_connections'][node.Class()].items():
                    if 'allowed_nodes' in rules:
                        connected_node = node[input_port].node()
                        if connected_node and connected_node.Class() not in rules['allowed_nodes']:
                            issue = {
                                'type': 'invalid_connection',
                                'node': node.name(),
                                'node_type': node.Class(),
                                'input_port': input_port,
                                'current': connected_node.name() if connected_node else 'None',
                                'allowed': rules['allowed_nodes'],
                                'severity': rules.get('severity', 'warning')
                            }
                            self.issues.append(issue)
                            
    # _check_node_metadata REMOVED
    def _check_expressions_and_read_errors(self, nodes: List[nuke.Node]):
        """
        Strict check for errors in expressions and Read node file existence.
        """
        # Check for expression errors in knobs
        if self.rules.get('expressions_errors', {}).get('check_for_errors', False):
            severity = self._get_rule_severity('expressions_errors')
            for node in nodes:
                for knob_name in node.knobs():
                    try:
                        knob = node[knob_name]
                        if knob.hasExpression():
                            # Check for Nuke's built-in error reporting on the knob
                            # Only call hasError() if the method exists for this knob type
                            if hasattr(knob, 'hasError') and knob.hasError():
                                 self.issues.append({
                                    'type': 'expression_error',
                                    'node': node.name(),
                                    'node_type': node.Class(),
                                    'knob': knob_name,
                                    'current': knob.expression(),
                                    'expected': 'No error in expression',
                                    'severity': severity
                                })
                            # A more aggressive check could try to evaluate, but this is risky
                            # try:
                            #     knob.value() # Evaluating might trigger errors
                            # except Exception as e:
                            #     self.issues.append(...)
                    except (RuntimeError, ValueError, AttributeError) as e:
                        # Skip knobs that can't be accessed or don't support the operations
                        continue

        # Check Read node file existence
        if self.rules.get('read_file_errors', {}).get('check_existence', False):
            severity = self._get_rule_severity('read_file_errors')
            for node in nodes:
                if node.Class() == 'Read':
                    file_path_knob = node.knob('file')
                    if file_path_knob:
                        file_path = file_path_knob.value()
                        if file_path:
                            # Nuke might have sequences like /path/to/img.####.exr
                            # A simple os.path.exists won't work for sequences directly.
                            # We need to check the first frame of the sequence.
                            # This is a simplification; full sequence check is harder.
                            
                            # Try to get a single frame path
                            try:
                                # If it's a sequence, get the path for the first frame of the node
                                first_frame = int(node.firstFrame())
                                # Use knob.evaluate(frame) to get the resolved path for the specific frame
                                actual_file_path = node['file'].evaluate(first_frame)
                                # If filenameFilter doesn't resolve %V, %v, etc., this might still be an issue.
                                # For paths with %V (view), it's even more complex.
                                # A simple approach for now:
                                if '%' in actual_file_path: # If unresolved sequence/view placeholders
                                     # Check if the directory exists as a fallback
                                    if not os.path.isdir(os.path.dirname(actual_file_path)):
                                        self.issues.append({
                                            'type': 'read_file_path_unresolved_or_dir_missing',
                                            'node': node.name(),
                                            'node_type': 'Read',
                                            'current': file_path, # Show original path
                                            'expected': 'Resolvable file path and existing directory',
                                            'severity': severity
                                        })
                                elif not os.path.exists(actual_file_path):
                                    self.issues.append({
                                        'type': 'read_file_missing',
                                        'node': node.name(),
                                        'node_type': 'Read',
                                        'current': actual_file_path,
                                        'expected': 'File to exist on disk',
                                        'severity': severity
                                    })
                            except ValueError: # If firstFrame is not an int (e.g. expression)
                                 if not os.path.exists(file_path) and not ('%' in file_path or '#' in file_path) : # If not a sequence pattern
                                    self.issues.append({
                                        'type': 'read_file_missing_non_sequence',
                                        'node': node.name(),
                                        'node_type': 'Read',
                                        'current': file_path,
                                        'expected': 'File to exist on disk',
                                        'severity': severity
                                    })
                        else:
                            self.issues.append({
                                'type': 'read_file_path_empty',
                                'node': node.name(),
                                'node_type': 'Read',
                                'current': 'Empty file path',
                                'expected': 'A valid file path',
                                'severity': severity
                            })
    def fix_issues(self):
        """
        Attempt to fix identified issues, including per-token auto-fix.
        """
        fixed = 0
        for issue in self.issues:
            if issue['type'] == 'colorspace':
                if issue['node_type'] == 'Read':
                    node = nuke.toNode(issue['node'])
                    read_colorspaces = self.rules.get('read_node_allowed_colorspaces', [])
                    if read_colorspaces:
                        node['colorspace'].setValue(read_colorspaces[0])
                        fixed += 1
                elif issue['node_type'] == 'Write':
                    node = nuke.toNode(issue['node'])
                    write_colorspaces = self.rules.get('write_node_allowed_colorspaces', [])
                    if write_colorspaces:
                        node['colorspace'].setValue(write_colorspaces[0])
                        fixed += 1
            elif issue['type'] == 'path_format':
                node = nuke.toNode(issue['node'])
                current_path = node['file'].value()
                new_path = self.rules['write_paths']['Write']['path_format'] + current_path[len(issue['expected']):]
                node['file'].setValue(new_path)
                fixed += 1
            elif issue['type'] == 'filename_format':
                node = nuke.toNode(issue['node'])
                current_path = node['file'].value()
                filename = os.path.basename(current_path)
                new_filename = self.rules['write_paths']['Write']['filename_format'] + filename[len(issue['expected']):]
                new_path = os.path.join(os.path.dirname(current_path), new_filename)
                node['file'].setValue(new_path)
                fixed += 1
            elif issue['type'].startswith('token_') and issue.get('auto_fix'):
                # Per-token auto-fix (e.g., padding)
                node = nuke.toNode(issue['node'])
                file_path = node['file'].value()
                filename = os.path.basename(file_path)
                token = issue['token']
                pad_to = issue.get('pad_to')
                if pad_to and issue['type'].endswith('_padding'):
                    # Find the token in the filename and pad it
                    regex = self.rules['token_definitions'][token]['regex']
                    m = re.search(regex, filename)
                    if m:
                        val = m.group(0)
                        padded = val.zfill(pad_to)
                        new_filename = filename.replace(val, padded, 1)
                        new_path = os.path.join(os.path.dirname(file_path), new_filename)
                        node['file'].setValue(new_path)
                        fixed += 1
        return fixed
        
    def generate_report(self) -> str:
        """
        Generate a report of validation results
        
        Returns:
            String containing the report
        """
        report = []
        report.append("NUKE VALIDATOR REPORT")
        report.append("=====================")
        report.append(f"Total nodes: {self.node_stats['total']}")
        report.append(f"Read nodes: {self.node_stats['read_nodes']}")
        report.append(f"Write nodes: {self.node_stats['write_nodes']}")
        report.append(f"Composite nodes: {self.node_stats['composite_nodes']}")
        report.append(f"Effect nodes: {self.node_stats['effect_nodes']}")
        report.append(f"Other nodes: {self.node_stats['other_nodes']}")
        report.append("\nISSUES FOUND:")
        
        if not self.issues:
            report.append("No issues found!")
        else:
            for i, issue in enumerate(self.issues, 1):
                report.append(f"{i}. {issue['type'].upper()} in {issue['node']} ({issue['node_type']})")
                report.append(f"   Current: {issue['current']}")
                if 'allowed' in issue:
                    report.append(f"   Allowed: {', '.join(issue['allowed'])}")
                if 'expected' in issue:
                    report.append(f"   Expected: {issue['expected']}")
                report.append(f"   Severity: {issue['severity']}")
                
                # Display detailed errors if available
                if 'details' in issue and issue['details']:
                    report.append(f"   Details: {issue['details']}")
                    
                    # If this is a naming convention violation, highlight the token name that caused the failure
                    if issue['type'] == 'naming_convention_violation' and 'token_name' in issue:
                        report.append(f"   Problem token: {issue['token_name']}")

        return "\n".join(report)


    def _check_node_integrity(self, nodes: List[nuke.Node]):
        """Checks for disabled nodes."""
        node_integrity_rules = self.rules.get('node_integrity', {})
        if node_integrity_rules.get('check_disabled_nodes', False):
            severity = node_integrity_rules.get('severity_disabled_nodes', 'warning') # Direct access
            disabled_nodes_found = []
            for node in nodes:
                disable_knob = node.knob('disable')
                if disable_knob and disable_knob.value():
                    disabled_nodes_found.append(node.name())
            
            if disabled_nodes_found:
                self.issues.append({
                    'type': 'disabled_nodes_found',
                    'node': 'Script', # General issue
                    'node_type': 'N/A',
                    'current': f"Disabled nodes: {', '.join(disabled_nodes_found)}",
                    'expected': 'No critical nodes should be disabled (or user review)',
                    'severity': severity
                })

    def _check_write_node_channels(self, nodes: List[nuke.Node]):
        """Checks channels for Write nodes: requires RGBA, warns on extra or RGB only."""
        if 'channels' not in self.rules:
            return

        channel_rules = self.rules['channels']
        severity = self._get_rule_severity('channels') # General severity for this category

        for node in nodes:
            if node.Class() == 'Write':
                # The 'channels' knob value is a string like 'rgba', 'rgb', 'all', or specific layers
                # Nuke's actual output channels can be complex to determine without rendering.
                # We'll check the 'channels' knob value.
                channels_knob_value = node.knob('channels').value() # e.g., "rgba", "rgb", "custom_layer"
                
                # This is a simplified check. A full check would need to know all available layers
                # from the input stream and see which ones are selected by the 'channels' knob.
                
                is_rgba = channels_knob_value == 'rgba'
                is_rgb = channels_knob_value == 'rgb'
                # "Extra channels" would mean something other than 'rgba' or 'rgb' is selected,
                # or if 'all' is selected and there are more than just rgba.
                # This simplified check might not catch all cases of "extra channels" perfectly.
                
                if channel_rules.get('require_rgba', True) and not is_rgba:
                     self.issues.append({
                        'type': 'channel_issue_not_rgba',
                        'node': node.name(),
                        'node_type': 'Write',
                        'current': f"Channels set to: {channels_knob_value}",
                        'expected': 'RGBA channels',
                        'severity': severity
                    })
                elif is_rgb and channel_rules.get('warn_on_rgb_only', False):
                    self.issues.append({
                        'type': 'channel_issue_rgb_only',
                        'node': node.name(),
                        'node_type': 'Write',
                        'current': f"Channels set to: {channels_knob_value}",
                        'expected': 'RGBA (alpha channel recommended)',
                        'severity': severity
                    })
                # A more robust "extra channels" check would be:
                # if channels_knob_value not in ['rgba', 'rgb'] and channel_rules.get('warn_on_extra_channels', False):
                # This assumes 'all' or custom layers are "extra".
                elif channels_knob_value != 'rgba' and channels_knob_value != 'rgb' and channel_rules.get('warn_on_extra_channels', False):
                     self.issues.append({
                        'type': 'channel_issue_extra_channels',
                        'node': node.name(),
                        'node_type': 'Write',
                        'current': f"Channels set to: {channels_knob_value}",
                        'expected': 'Typically RGBA unless specific AOVs are intended',
                        'severity': severity
                    })


    def _check_render_settings(self, nodes: List[nuke.Node]):
        """Checks Write node render settings based on file type."""
        render_settings_rules = self.rules.get('render_settings', {})
        write_rules = render_settings_rules.get('Write', {}) # Get the 'Write' sub-dictionary

        if not write_rules: # If 'Write' key or 'render_settings' doesn't exist or is empty
            return

        file_type_rules = write_rules.get('file_type_rules', {})
        severity_general = write_rules.get('severity', 'warning') # Access severity from 'write_rules'

        for node in nodes:
            if node.Class() == 'Write':
                file_type_knob = node.knob('file_type')
                if not file_type_knob:
                    continue
                
                current_file_type = file_type_knob.value()
                if current_file_type in file_type_rules:
                    specific_rules = file_type_rules[current_file_type]
                    for knob_name, expected_values in specific_rules.items():
                        target_knob = node.knob(knob_name)
                        if target_knob:
                            current_value = target_knob.value()
                            # Ensure expected_values is a list for 'in' check
                            if not isinstance(expected_values, list):
                                expected_values_list = [expected_values]
                            else:
                                expected_values_list = expected_values

                            if current_value not in expected_values_list:
                                self.issues.append({
                                    'type': f'render_setting_mismatch_{knob_name}',
                                    'node': node.name(),
                                    'node_type': 'Write',
                                    'current': f"{knob_name}: {current_value}",
                                    'expected': f"{knob_name} to be one of: {', '.join(map(str,expected_values_list))} for file type {current_file_type}",
                                    'severity': specific_rules.get(f'{knob_name}_severity', severity_general)
                                })
                        # else:
                            # self.issues.append({ 'type': 'missing_render_knob', ... }) # If knob itself is missing

    def _check_versioning(self, nodes: List[nuke.Node]):
        """Checks for version token in Write node filenames."""
        if 'versioning' not in self.rules:
            return

        version_rules = self.rules['versioning']
        require_token = version_rules.get('require_version_token', False)
        token_regex_str = version_rules.get('version_token_regex')
        severity_missing = version_rules.get('severity_require_token', 'error') # Direct access
        # severity_mismatch = self._get_rule_severity('versioning', 'match_nuke_script_version', 'warning') # For later

        if not require_token or not token_regex_str:
            return

        try:
            token_regex = re.compile(token_regex_str)
        except re.error as e:
            self.issues.append({
                'type': 'version_regex_error',
                'node': 'Script',
                'node_type': 'N/A',
                'current': f"Regex: {token_regex_str}",
                'expected': f"Valid regex pattern. Error: {e}",
                'severity': 'error'
            })
            return

        for node in nodes:
            if node.Class() == 'Write':
                file_path_knob = node.knob('file')
                if file_path_knob:
                    filename = os.path.basename(file_path_knob.value())
                    if not token_regex.search(filename):
                        self.issues.append({
                            'type': 'missing_version_token',
                            'node': node.name(),
                            'node_type': 'Write',
                            'current': filename,
                            'expected': f"Filename to contain version token matching regex: {token_regex_str}",
                            'severity': severity_missing
                        })
                    # else:
                        # version_match = token_regex.search(filename)
                        # file_version_str = version_match.group(1) # Assuming regex has one capture group for version number
                        # TODO: Implement comparison with Nuke script version if 'match_nuke_script_version' is true
                        # This requires getting Nuke script filename and parsing its version.
                        # nuke_script_path = nuke.root().name()
                        # ... parse nuke_script_path for version ...
                        # if nuke_script_version != file_version_str: self.issues.append(...)

    def _check_viewer_ip(self, nodes: List[nuke.Node]):
        """Checks if 'ip' (use GPU for Viewer process) knob is active on Viewer nodes."""
        if 'viewer_nodes' not in self.rules or not self.rules['viewer_nodes'].get('warn_if_ip_active', False):
            return
        
        viewer_rules = self.rules.get('viewer_nodes', {})
        severity = viewer_rules.get('severity', 'warning') # Direct access to category-level severity

        for node in nodes:
            if node.Class() == 'Viewer':
                ip_knob = node.knob('ip') # 'ip' is the knob for "use GPU for Viewer process"
                if ip_knob and ip_knob.value(): # .value() is True if checked
                    self.issues.append({
                        'type': 'viewer_ip_active',
                        'node': node.name(),
                        'node_type': 'Viewer',
                        'current': "GPU for Viewer process is ON ('ip' knob is True)",
                        'expected': "GPU for Viewer process to be OFF for consistency or specific pipeline needs.",
                        'severity': severity
                    })

def main():
    # Check if running inside Nuke
    if not nuke.NUKE_VERSION_MAJOR: # A more robust check for running in Nuke
        print("This script must be run inside Nuke.")
        return
        
    # Determine the path to rules.yaml relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    rules_file = os.path.join(script_dir, "rules.yaml")

    if not os.path.exists(rules_file):
        print(f"Error: Rules file not found at {rules_file}")
        # Try to find it in Nuke's plugin path if that's where it's expected
        for path_dir in nuke.pluginPath():
            potential_rules_file = os.path.join(path_dir, "rules.yaml")
            if os.path.exists(potential_rules_file):
                rules_file = potential_rules_file
                break
        if not os.path.exists(rules_file): # Still not found
             print(f"Error: Could not locate rules.yaml in script directory or Nuke plugin paths.")
             return


    # Create validator instance
    validator = NukeValidator(rules_file=rules_file)
    validator.rules_file_path = rules_file # Store for reloading
    
    # Validate script
    success, issues = validator.validate_script()
    
    # Generate report
    report = validator.generate_report()
    print(report)
    
    # Fix issues if requested
    if issues and nuke.ask("Would you like to fix the issues automatically?"):
        fixed_count = validator.fix_issues()
        print(f"\nAttempted to fix {fixed_count} issues.")
        
        # Re-validate and generate new report
        print("\nRe-validating after fixes:")
        success, issues_after_fix = validator.validate_script()
        report_after_fix = validator.generate_report()
        print(report_after_fix)
        
    # Exit with appropriate status
    # sys.exit(0 if success else 1) # sys.exit can close Nuke if not careful.
    if not success:
        print("\nValidation finished with errors.")
    else:
        print("\nValidation finished successfully.")


if __name__ == '__main__':
    # This allows running from script editor in Nuke.
    # For UI integration, the UI will call these methods.
    main()