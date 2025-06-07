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
        
        Args:
            nodes: List of Nuke nodes
        """
        if 'colorspaces' not in self.rules:
            return
            
        for node in nodes:
            if node.Class() == 'Read' and 'Read' in self.rules['colorspaces']:
                colorspace = node['colorspace'].value()
                if not self._is_colorspace_allowed(colorspace, self.rules['colorspaces']['Read']['allowed']):
                    issue = {
                        'type': 'colorspace',
                        'node': node.name(),
                        'node_type': 'Read',
                        'current': colorspace,
                        'allowed': self.rules['colorspaces']['Read']['allowed'],
                        'severity': self.rules['colorspaces']['Read'].get('severity', 'warning')
                    }
                    self.issues.append(issue)
                    
            elif node.Class() == 'Write' and 'Write' in self.rules['colorspaces']:
                colorspace = node['colorspace'].value()
                if not self._is_colorspace_allowed(colorspace, self.rules['colorspaces']['Write']['allowed']):
                    issue = {
                        'type': 'colorspace',
                        'node': node.name(),
                        'node_type': 'Write',
                        'current': colorspace,
                        'allowed': self.rules['colorspaces']['Write']['allowed'],
                        'severity': self.rules['colorspaces']['Write'].get('severity', 'warning')
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
        
        # Define colorspace aliases and patterns
        colorspace_patterns = {
            'acescg': ['acescg', 'aces', 'acesCg', 'aces-acescg', 'acesapplied'],
            'linear': ['linear', 'scenelinear', 'scene_linear', 'scenereferred', 'lin'],
            'srgb': ['srgb', 'sRGB', 'inputsrgb', 'input-srgb', 'outputsrgb', 'output-srgb'],
            'rec709': ['rec709', 'rec.709', 'inputrec709', 'input-rec709', 'outputrec709', 'output-rec709', 'r709'],
            'log': ['log', 'logc', 'alog', 'arri'],
            'p3': ['p3', 'p3d65', 'displayp3', 'dci-p3'],
            'rec2020': ['rec2020', 'rec.2020', 'bt2020', 'bt.2020']
        }
        
        # Check if current colorspace matches any pattern group
        for pattern_group, patterns in colorspace_patterns.items():
            if any(pattern in current_norm for pattern in patterns):
                # Check if any allowed colorspace also matches this pattern group
                for allowed in allowed_colorspaces:
                    allowed_norm = normalize_colorspace(allowed)
                    if any(pattern in allowed_norm for pattern in patterns):
                        return True
        
        # Check for partial matches with key terms
        key_terms = ['acescg', 'linear', 'srgb', 'rec709', 'log', 'p3', 'rec2020']
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
        """
        try:
            # Import the sophisticated validation from the UI
            from nuke_validator_ui import FilenameRuleEditor
            
            # Check if we have filename tokens in the rules (from the UI system)
            filename_tokens = self.rules.get('file_paths', {}).get('filename_tokens', [])
            
            if filename_tokens:
                # Create a temporary FilenameRuleEditor to use its validation logic
                temp_editor = FilenameRuleEditor()
                
                # Load the token configuration from rules
                for token_cfg in filename_tokens:
                    if "name" in token_cfg:
                        # Find the token definition
                        from nuke_validator_ui import FILENAME_TOKENS
                        token_def = next((t for t in FILENAME_TOKENS if t["name"] == token_cfg["name"]), None)
                        if token_def:
                            temp_editor.template_builder.add_token(token_def)
                            
                            # Set the control values from the saved configuration
                            if temp_editor.template_builder.token_widgets:
                                widget = temp_editor.template_builder.token_widgets[-1]
                                if hasattr(widget, 'token_configs') and len(widget.token_configs) > 0:
                                    # Update the token config with saved values
                                    config = widget.token_configs[-1]
                                    config["value"] = token_cfg.get("value")
                                    config["separator"] = token_cfg.get("separator", "_")
                
                # Generate the regex pattern
                temp_editor.update_regex()
                
                # Use the sophisticated validation from the UI
                detailed_errors = temp_editor.get_validation_errors(filename)
                
                if detailed_errors:
                    return detailed_errors
                else:
                    return []  # No errors found
            
            # Fallback to basic validation if no template configuration available
            return self._basic_filename_validation(filename, pattern_str)
            
        except ImportError:
            # If UI components aren't available, fall back to basic validation
            return self._basic_filename_validation(filename, pattern_str)
        except Exception as e:
            return [f"Validation system error: {str(e)}"]
    
    def _basic_filename_validation(self, filename, pattern_str):
        """
        Basic fallback validation for when the sophisticated UI validation isn't available.
        """
        import re
        errors = []
        
        if not pattern_str or not filename:
            return ["No regex pattern defined"]
            
        try:
            # First try full match
            if re.match(pattern_str, filename):
                return []  # No errors
                
            # Basic pattern analysis
            print(f"[BasicValidation] Analyzing filename: {filename}")
            print(f"[BasicValidation] Against pattern: {pattern_str}")
            
            # Common issue 1: LL18012k should be LL180_12k
            ll_resolution_match = re.search(r'LL(\d+)(\d+k)', filename)
            if ll_resolution_match:
                ll_part = ll_resolution_match.group(1)
                res_part = ll_resolution_match.group(2)
                if ll_part in ['180', '360'] and res_part in ['1k', '2k', '4k', '6k', '8k', '12k', '16k', '19k']:
                    full_match = ll_resolution_match.group(0)
                    suggested = f"LL{ll_part}_{res_part}"
                    errors.append(f"Pixel mapping format: '{full_match}' should be '{suggested}' (needs separator)")
                    return errors  # Return early with this specific error
            
            # If no specific pattern detected, provide general feedback
            errors.append(f"Filename '{filename}' doesn't match expected pattern. Check token order and separators.")
            return errors
            
        except re.error as e:
            return [f"Regex error: {str(e)}"]
        except Exception as e:
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
                    print(f"[Validator] Checking filename '{filename}' against regex: {pattern_str}")
                    if not re.match(pattern_str, filename):
                        # Use detailed validation instead of generic regex error
                        detailed_errors = self._validate_filename_detailed(filename, pattern_str)
                        
                        if detailed_errors:
                            # Create specific error for the most important issues
                            primary_error = detailed_errors[0]  # Take the first/most important error
                            self.issues.append({
                                'type': 'naming_convention_violation',
                                'node': node.name(),
                                'node_type': 'Write',
                                'current': filename,
                                'expected': primary_error,
                                'severity': severity_naming,
                                'details': detailed_errors  # Include all errors for detailed view
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
    def _validate_tokens(self, filename, token_defs):
        """
        Validate tokens in the filename using token_definitions from rules.yaml.
        Returns a list of issues (with type, current, expected, token, and optionally auto_fix info).
        """
        issues = []
        # Example: parse tokens from filename using regexes from token_defs
        # This assumes tokens are separated by underscores or known delimiters
        # You may want to make this more robust for your actual template
        for token, tdef in token_defs.items():
            regex = tdef.get('regex')
            if not regex:
                continue
            m = re.search(regex, filename)
            if not m:
                issues.append({
                    'type': f'token_{token}_invalid',
                    'token': token,
                    'current': filename,
                    'expected': tdef.get('description', ''),
                    'auto_fix': tdef.get('auto_fix', False),
                    'pad_to': tdef.get('pad_to', None),
                    'tooltip': tdef.get('tooltip', ''),
                })
            else:
                # If padding is required, check it
                if tdef.get('auto_fix', False) and tdef.get('pad_to'):
                    val = m.group(0)
                    if val.isdigit() and len(val) != tdef['pad_to']:
                        issues.append({
                            'type': f'token_{token}_padding',
                            'token': token,
                            'current': val,
                            'expected': f"{token} should be zero-padded to {tdef['pad_to']} digits",
                            'auto_fix': True,
                            'pad_to': tdef['pad_to'],
                            'tooltip': tdef.get('tooltip', ''),
                        })
        return issues
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
                    node['colorspace'].setValue(self.rules['colorspaces']['Read']['allowed'][0])
                    fixed += 1
                elif issue['node_type'] == 'Write':
                    node = nuke.toNode(issue['node'])
                    node['colorspace'].setValue(self.rules['colorspaces']['Write']['allowed'][0])
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