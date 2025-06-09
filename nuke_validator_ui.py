#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Nuke Validator UI - A comprehensive UI for the Nuke Validator

Public classes:
- ValidationResultsTable: Excel-like table for displaying validation results
- RulesEditorWidget: Widget for editing validation rules
- RuleItemWidget: DEPRECATED - Legacy validation result widget
- FilenameRuleEditor: Widget for editing filename validation rules
- PathRuleEditor: Widget for editing path structure rules
"""

# ===============================================================================
# IMPORTS
# ===============================================================================
# Standard library imports
import functools
import os
import re  # For regex generation
import yaml

# Type annotations
from typing import Any, Dict, Optional

# Qt imports - consolidated and organized
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel

# ===============================================================================
# CONSTANTS & CONFIGURATIONS
# ===============================================================================
# --- Constants for Dynamic Filename Regex Generation ---
DEFAULT_FILENAME_TEMPLATE = "<sequence>_<shotNumber>_<description>_(?<pixelMappingName>)?<resolution>_<colorspaceGamma>_<fps>_<version>.<extension>"
# (?<token_name>)? in the template signifies that the token (and its preceding separator if applicable) is optional.

DEFAULT_NAMING_TOKENS: Dict[str, Dict[str, Any]] = {
    "sequence": {
        "regex": "[A-Z]{4}",
        "description": "4-letter uppercase sequence abbreviation.",
        "examples": ["WTFB", "KITC", "IGBI", "LIFF", "SOME", "OLNT", "ATBM"],
        "separator": "_" # Default separator after this token if not last
    },
    "shotNumber": {
        "regex": "\\d{4}",
        "description": "4-digit shot number.",
        "examples": ["0010", "0020", "0030"],
        "separator": "_"
    },
    "description": {
        "regex": ".+?",
        "description": "Single word or hyphenated description.",
        "examples": ["concept", "layout", "comp", "previz", "roto", "dmp", "roto-main", "compFinal"],
        "separator": "_"
    },
    "pixelMappingName": { # This token is optional in the template
        "regex": "(LL180|LL360)",
        "description": "Pixel mapping (LL180, LL360).",
        "examples": ["LL180", "LL360"],
        "separator": "" # No separator after if it's followed by resolution directly
    },
    "resolution": {
        "regex": "\\d{1,2}[kK]",
        "description": "Resolution abbreviation (e.g., 2k, 4k, 12k).",
        "examples": ["1k", "2k", "4k", "8k", "12k", "16k", "19k", "32k"],
        "separator": "_"
    },
    "colorspaceGamma": {
        "regex": "(r709g22|sRGBg24|srgbg24|ap0log|ap1lin|p3g26|acescglin)",
        "description": "Colorspace and gamma (e.g., sRGBg22, ap0lin).",
        "examples": ["sRGBg22", "r709g24", "ap0lin", "ap1g22"],
        "separator": "_"
    },
    "fps": {
        "regex": "(2997|5994|24|25|30|50|60)",
        "description": "Frames per second (e.g., 2997, 24).",
        "examples": ["2997", "5994", "24", "25"],
        "separator": "_"
    },
    "version": {
        "regex": "v\\d{3}",
        "description": "Version (e.g., v001, v010).",
        "examples": ["v001", "v003", "v010"],
        "separator": "." # Separator before extension
    },
    "frame_padding": { # Typically used for image sequences like filename.####.ext
        "regex": "(?:%0[4-8]d|#{4,8})",
        "description": "Frame padding (%04d to %08d, #### to ########)",
        "examples": ["0001", "00000001"],
        "separator": "."
    },
    "extension": {
        "regex": "(?i:jpg|jpeg|png|mxf|mov|exr)",
        "description": "File extension (e.g., jpg, exr, nk).",
        "examples": ["jpg", "png", "mp4", "mov", "exr", "nk"],
        "separator": "" # No separator after extension
    }
}

FILENAME_TOKENS = [
    {
        "name": "sequence",
        "label": "<sequence>",
        "regex_template": "[A-Za-z]{MIN_VAL,MAX_VAL}",
        "control": "range_spinner",
        "min": 2,
        "max": 8,
        "default_min": 3,
        "default_max": 4,
        "desc": "Upper/lowercase sequence abbreviation (min 2 letters)"
    },
    {
        "name": "shotNumber",
        "label": "<shotNumber>",
        "regex_template": "\\d{n}",  # Using {n} as a placeholder for the spinner value
        "control": "spinner",
        "min": 2,
        "max": 8,
        "default": 4,
        "desc": "Shot number (digits)"
    },
    {
        "name": "description",
        "label": "<description>",
        "regex_template": ".+?",
        "control": "static",
        "desc": "Description (letters, numbers, hyphens)"
    },
    {
        "name": "pixelMappingName",
        "label": "<pixelMappingName>",
        "regex_template": "(?:(LL180|LL360))?",
        "control": "dropdown",
        "options": ["LL180", "LL360", "none"],
        "desc": "Pixel mapping name (optional)"
    },
    {
        "name": "resolution",
        "label": "<resolution>",
        "regex_template": "\\d{1,2}[kK]",
        "control": "static",
        "desc": "Resolution abbreviation (e.g., 1k, 4k)"
    },
    {
        "name": "colorspaceGamma",
        "label": "<colorspaceGamma>",
        "regex_template": "(r709|sRGB|acescg|ap0|ap1|p3|rec2020)(lin|log|g22|g24|g26)",
        "control": "multiselect",
        "options": ["r709g24", "sRGBg22", "acescglin", "ap0lin", "ap1g22", "p3g26", "rec2020lin"],
        "desc": "Colorspace and gamma (multi-select)"
    },
    {
        "name": "fps",
        "label": "<fps>",
        "regex_template": "(2997|5994|24|25|30|50|60)",
        "control": "dropdown",
        "options": ["2997", "5994", "24", "25", "30", "50", "60"],
        "desc": "Frames per second"
    },
    {
        "name": "version",
        "label": "<version>",
        "regex_template": "v\\d{2,3}",
        "control": "static",
        "desc": "Version (v + 2-3 digits)"
    },
    {
        "name": "frame_padding",
        "label": "<frame_padding>",
        "regex_template": "(?:%0[4-8]d|#{4,8})",
        "control": "static",
        "desc": "Frame padding (%04d to %08d, #### to ########)"
    },
    {
        "name": "extension",
        "label": "<extension>",
        "regex_template": "(?i:jpg|jpeg|png|mxf|mov|exr)",
        "control": "multiselect",
        "options": ["jpg", "jpeg", "png", "mxf", "mov", "exr", "tiff", "dpx"],
        "desc": "File extension (multi-select)"
    },
]

# ===============================================================================
# BASE WIDGETS - PRIMARY UI COMPONENTS
# ===============================================================================

class FilenameTokenWidget(QtWidgets.QWidget):
    """
    Widget for a single token in the filename template builder.
    
    This widget represents and manages a single filename token component. It displays
    the token label and, if configured, provides the appropriate control UI element
    (spinner, dropdown, etc.) based on the token definition.
    
    Attributes:
        token_def (dict): The token definition dictionary containing configuration
                         such as name, label, control type, and options.
        value: The current value of the token (type varies based on token control)
        control_widget: The UI control widget for editing the token value
    
    Signals:
        valueChanged: Emitted when the token value changes
        removeRequested: Emitted when the user requests to remove this token
    """
    def __init__(self, token_def, parent=None):
        super().__init__(parent)
        self.token_def = token_def
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(4)
        
        # Header with label and remove button
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)
        
        self.label = QtWidgets.QLabel(token_def["label"])
        self.label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4a4a4a, stop:1 #3a3a3a);
                color: #e0e0e0;
                border: 1px solid #666;
                border-radius: 4px;
                padding: 6px 8px;
                font-size: 11px;
                font-weight: bold;
                min-width: 80px;
            }
        """)
        header_layout.addWidget(self.label)
        
        self.remove_btn = QtWidgets.QToolButton()
        self.remove_btn.setText("×")
        self.remove_btn.setToolTip("Remove token")
        self.remove_btn.setFixedSize(18, 18)
        self.remove_btn.setStyleSheet("""
            QToolButton {
                background: #d32f2f;
                color: white;
                border: none;
                border-radius: 9px;
                font-size: 12px;
                font-weight: bold;
            }
            QToolButton:hover {
                background: #f44336;
            }
            QToolButton:pressed {
                background: #b71c1c;
            }
        """)
        header_layout.addWidget(self.remove_btn)
        
        self.layout.addLayout(header_layout)
        
        # Control section
        self.control = None
        if token_def["control"] == "spinner":
            self.control = QtWidgets.QSpinBox()
            self.control.setMinimum(token_def["min"])
            self.control.setMaximum(token_def["max"])
            self.control.setValue(token_def["default"])
            self.control.setFixedWidth(80)
            self.control.setStyleSheet("""
                QSpinBox {
                    background: #3a3a3a;
                    color: #e0e0e0;
                    border: 1px solid #666;
                    border-radius: 4px;
                    padding: 4px;
                    font-size: 11px;
                }
                QSpinBox:focus {
                    border: 2px solid #4a9eff;
                    background: #404040;
                }
                QSpinBox::up-button, QSpinBox::down-button {
                    background: #4a4a4a;
                    border: 1px solid #666;
                    width: 16px;
                }
                QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                    background: #5a5a5a;
                }
            """)
            self.layout.addWidget(self.control, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
            
        elif token_def["control"] == "spinner_range":
            self.control = QtWidgets.QSpinBox()
            self.control.setMinimum(token_def["min"])
            self.control.setMaximum(token_def["max"])
            self.control.setValue(token_def["default"])
            self.control.setFixedWidth(80)
            self.control.setStyleSheet("""
                QSpinBox {
                    background: #3a3a3a;
                    color: #e0e0e0;
                    border: 1px solid #666;
                    border-radius: 4px;
                    padding: 4px;
                    font-size: 11px;
                }
                QSpinBox:focus {
                    border: 2px solid #4a9eff;
                    background: #404040;
                }
                QSpinBox::up-button, QSpinBox::down-button {
                    background: #4a4a4a;
                    border: 1px solid #666;
                    width: 16px;
                }
                QSpinBox::up-button:hover, QSpinBox::down-button:hover {
                    background: #5a5a5a;
                }
            """)
            self.layout.addWidget(self.control, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
            
        elif token_def["control"] == "dropdown":
            self.control = QtWidgets.QComboBox()
            self.control.addItems(token_def["options"])
            self.control.setFixedWidth(100)
            self.control.setStyleSheet("""
                QComboBox {
                    background: #3a3a3a;
                    color: #e0e0e0;
                    border: 1px solid #666;
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 11px;
                }
                QComboBox:focus {
                    border: 2px solid #4a9eff;
                    background: #404040;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 20px;
                }
                QComboBox::down-arrow {
                    image: none;
                    border-left: 4px solid transparent;
                    border-right: 4px solid transparent;
                    border-top: 4px solid #e0e0e0;
                }
                QComboBox QAbstractItemView {
                    background: #3a3a3a;
                    color: #e0e0e0;
                    selection-background-color: #4a9eff;
                    border: 1px solid #666;
                }
            """)
            self.layout.addWidget(self.control, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
            
        elif token_def["control"] == "multiselect":
            self.control = SimpleMultiSelectWidget(token_def["options"])
            self.control.setFixedWidth(100)
            # Ensure the signal connection is set up immediately
            self.control.selectionChanged.connect(self._on_control_changed)
        # else: static, no control
        
        # Set size policy for the entire widget
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.setFixedSize(130, 90)  # Slightly larger for better spacing
        
        # Dark theme grid-based styling
        self.setStyleSheet("""
            FilenameTokenWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #383838, stop:1 #2a2a2a);
                border: 2px solid #555;
                border-radius: 8px;
                margin: 2px;
            }
            FilenameTokenWidget:hover {
                border: 2px solid #4a9eff;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #404040, stop:1 #323232);
            }
        """)

    def _on_multiselect_changed(self):
        """Handle multiselect widget changes and trigger parent updates"""
        # Find the parent FilenameRuleEditor and trigger its update
        parent = self.parent()
        while parent:
            if hasattr(parent, 'update_regex'):
                parent.update_regex()
                break
            parent = parent.parent()

    def get_token_config(self):
        # Return dict with token name and current control value (if any)
        value = None
        if self.control:
            try:
                if isinstance(self.control, QtWidgets.QSpinBox):
                    value = self.control.value()
                elif isinstance(self.control, QtWidgets.QComboBox):
                    value = self.control.currentText()
                elif isinstance(self.control, SimpleMultiSelectWidget):
                    value = self.control.get_selected_values()
            except RuntimeError:
                # Control was deleted, use None value
                value = None
        return {"name": self.token_def["name"], "value": value}

class SeparatorWidget(QtWidgets.QWidget):
    """Widget for a separator (e.g., _, ., -) in the template builder."""
    def __init__(self, sep, parent=None):
        super().__init__(parent)
        self.sep = sep
        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(4)
        
        # Header with remove button
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)
        
        # Spacer to push remove button to right
        header_layout.addStretch()
        
        self.remove_btn = QtWidgets.QToolButton()
        self.remove_btn.setText("×")
        self.remove_btn.setToolTip("Remove separator")
        self.remove_btn.setFixedSize(18, 18)
        self.remove_btn.setStyleSheet("""
            QToolButton {
                background: #d32f2f;
                color: white;
                border: none;
                border-radius: 9px;
                font-size: 12px;
                font-weight: bold;
            }
            QToolButton:hover {
                background: #f44336;
            }
            QToolButton:pressed {
                background: #b71c1c;
            }
        """)
        header_layout.addWidget(self.remove_btn)
        
        self.layout.addLayout(header_layout)
        
        # Separator label (centered)
        self.label = QtWidgets.QLabel(sep)
        self.label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("""
            QLabel {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #5a5a5a, stop:1 #4a4a4a);
                color: #ffc107;
                border: 2px solid #777;
                border-radius: 8px;
                padding: 12px;
                font-size: 18px;
                font-weight: bold;
                min-height: 20px;
                min-width: 30px;
            }
        """)
        self.layout.addWidget(self.label)
        
        # Set size policy for the entire widget
        self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.setFixedSize(70, 90)  # Match token height
        
        # Dark theme grid-based styling to match tokens
        self.setStyleSheet("""
            SeparatorWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #383838, stop:1 #2a2a2a);
                border: 2px solid #555;
                border-radius: 8px;
                margin: 2px;
            }
            SeparatorWidget:hover {
                border: 2px solid #ffc107;
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #404040, stop:1 #323232);
            }
        """)
        
    def get_token_config(self):
        return {"separator": self.sep}

class RuleItemWidget(QtWidgets.QWidget):
    """
    Widget to display a single rule with progress and status
    """
    def __init__(self, rule_name, parent=None):
        super(RuleItemWidget, self).__init__(parent)
        self.rule_name = rule_name
        
        # Main layout - more condensed
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        # Status icon (Column 1) - Smaller and more compact
        self.status_icon = QtWidgets.QLabel()
        self.status_icon.setFixedSize(24, 24)
        self.status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_icon.setScaledContents(True)
        
        # Create default icon with "pending" status
        self.set_status("pending")
        
        layout.addWidget(self.status_icon, 0)

        # Rule name label (Column 2) - Fixed width for consistency
        self.name_label = QtWidgets.QLabel()
        self.name_label.setFixedWidth(120)
        self.name_label.setWordWrap(False)
        self.name_label.setTextFormat(Qt.TextFormat.PlainText)
        self.name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.name_label.setStyleSheet("""
            QLabel {
                color: #e0e0e0;
                font-size: 11px;
                font-weight: bold;
                padding: 2px 4px;
                background: transparent;
            }
        """)
        layout.addWidget(self.name_label, 0)

        # Progress bar (conditionally visible, Column 3)
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedWidth(80)
        self.progress_bar.setFixedHeight(16)
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background: #2a2a2a;
                border: 1px solid #444;
                border-radius: 3px;
                font-size: 9px;
                color: #e0e0e0;
            }
            QProgressBar::chunk {
                background: #4a9eff;
                border-radius: 2px;
            }
        """)
        layout.addWidget(self.progress_bar, 0)
        
        # Status label/details (Column 4) - Compact with dark styling
        self.status_label = QtWidgets.QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.status_label.setStyleSheet("""
            QLabel {
                color: #cccccc;
                font-size: 10px;
                padding: 2px 4px;
                background: transparent;
                line-height: 1.2;
            }
        """)
        layout.addWidget(self.status_label, 1)
        
        # Apply dark theme styling to the widget itself
        self.setStyleSheet("""
            RuleItemWidget {
                background: #3a3a3a;
                border: 1px solid #555;
                border-radius: 3px;
                margin: 1px;
            }
            RuleItemWidget:hover {
                background: #404040;
                border: 1px solid #666;
            }
        """)
        
        # Make the widget more compact
        self.setFixedHeight(32)

    def set_status(self, status):
        """
        Set the status icon for this rule item.
        Args:
            status (str): One of 'success', 'warning', 'error', 'running', 'pending'
        """
        # Get the icons directory path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icons_dir = os.path.join(script_dir, "icons")
        
        # Map status to PNG file names
        icon_files = {
            'success': 'success.png',
            'warning': 'warning.png', 
            'error': 'error.png',
            'running': 'info.png',  # Use info.png for running state
            'pending': 'info.png'   # Use info.png for pending state
        }
        
        # Load the appropriate PNG icon
        icon_file = icon_files.get(status, 'info.png')  # Default to info.png
        icon_path = os.path.join(icons_dir, icon_file)
        
        if os.path.exists(icon_path):
            # Load PNG and scale to 24x24
            pixmap = QtGui.QPixmap(icon_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.status_icon.setPixmap(scaled_pixmap)
            else:
                # Fallback to a simple colored square if PNG fails to load
                self._create_fallback_icon(status)
        else:
            # Fallback to a simple colored square if PNG file doesn't exist
            self._create_fallback_icon(status)
    
    def _create_fallback_icon(self, status):
        """Create a simple fallback icon if PNG loading fails"""
        # Status colors - more muted for dark theme
        colors = {
            'success': QtGui.QColor(76, 175, 80, 180),    # Green with some transparency
            'warning': QtGui.QColor(255, 152, 0, 180),    # Orange with some transparency
            'error': QtGui.QColor(244, 67, 54, 180),      # Red with some transparency
            'running': QtGui.QColor(33, 150, 243, 180),   # Blue with some transparency
            'pending': QtGui.QColor(120, 120, 120, 180)   # Gray with some transparency
        }
        
        color = colors.get(status, colors['pending'])
        pixmap = QtGui.QPixmap(24, 24)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setBrush(QtGui.QBrush(color))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 20, 20)  # Draw a circle with some padding
        painter.end()
        
        self.status_icon.setPixmap(pixmap)

class RulesEditorWidget(QtWidgets.QWidget):
    """
    Widget for editing rules with a graphical interface
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Store the parent explicitly
        self.main_window_parent = parent
        
        # Default path for rules.yaml
        self.rules_yaml_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.yaml")
        # Track the currently loaded YAML file name for display purposes
        self.current_yaml_name = "rules.yaml"
        self.dropdown_yaml_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules_dropdowns.yaml")
        self.dropdown_options = self._load_yaml_file(self.dropdown_yaml_path) or {}
        
        # Initialize attributes for dynamic filename validation
        self.filename_template = DEFAULT_FILENAME_TEMPLATE
        # Deepcopy might be good here if tokens are modified and reset later
        self.filename_tokens = DEFAULT_NAMING_TOKENS.copy() # Retained for other potential uses, but FilenameRuleEditor will use dynamic tokens.
        self.filename_tokens_for_editor = [] # Will hold token definitions for FilenameRuleEditor, loaded from YAML.

        # --- Debug Prints for Dropdown Loading (can be removed later) ---
        print(f"DEBUG: RulesEditorWidget: Attempting to load dropdowns from: {self.dropdown_yaml_path}")
        print(f"DEBUG: RulesEditorWidget: File exists at path: {os.path.exists(self.dropdown_yaml_path)}")
        if self.dropdown_options:
            print(f"DEBUG: RulesEditorWidget: Loaded dropdown_options (first few keys): {{key: type(value) for key, value in list(self.dropdown_options.items())[:5]}}")
            if 'severity_options' in self.dropdown_options:
                print(f"DEBUG: RulesEditorWidget: severity_options: {self.dropdown_options['severity_options']}")
            else:
                print(f"DEBUG: RulesEditorWidget: 'severity_options' NOT FOUND in dropdown_options.")
        else:
            print("DEBUG: RulesEditorWidget: dropdown_options is EMPTY or None after loading.")
        # --- End Debug Prints ---

        # Prepare filename tokens for the editor using the global FILENAME_TOKENS master list
        # This must be done BEFORE creating the FilenameRuleEditor
        self._prepare_filename_tokens_for_editor()

        # Main layout for the entire RulesEditorWidget
        main_editor_layout = QtWidgets.QVBoxLayout(self)

        # Splitter for category list and settings stack
        self.rules_splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        main_editor_layout.addWidget(self.rules_splitter)

        # Left pane: Category List
        self.category_list = QtWidgets.QListWidget()
        self.category_list.setFixedWidth(220)
        self.category_list.setMinimumWidth(220)
        self.category_list.setMaximumWidth(220)
        self.rules_splitter.addWidget(self.category_list)
        self.rules_splitter.setStretchFactor(0, 0)  # Left panel fixed
        self.rules_splitter.setStretchFactor(1, 1)  # Right panel flexible

        # Right pane: StackedWidget for settings pages
        self.settings_stack = QtWidgets.QStackedWidget()
        self.rules_splitter.addWidget(self.settings_stack)

        # Connect list selection to stack page change
        self.category_list.currentRowChanged.connect(self.settings_stack.setCurrentIndex)
        
        # Create rule category pages (they will now add themselves to list and stack)
        self._create_all_rule_pages()

        # Set initial splitter sizes
        self.rules_splitter.setSizes([300, 600])
        
        # Set stretch factors: right panel (index 1) should expand more than left (index 0)
        self.rules_splitter.setStretchFactor(0, 0) # Left panel (category_list)
        self.rules_splitter.setStretchFactor(1, 1) # Right panel (settings_stack)

        # Buttons (Save, Reload) - Placed below the splitter
        button_layout = QtWidgets.QHBoxLayout()
        # Add a label to show which YAML file is being edited
        self.current_file_label = QtWidgets.QLabel("Editing: rules.yaml")
        self.current_file_label.setStyleSheet("QLabel { color: #4a9eff; font-weight: bold; }")
        button_layout.addWidget(self.current_file_label)
        
        save_button = QtWidgets.QPushButton("Save Rules to YAML")
        save_button.clicked.connect(self.save_rules_to_yaml)
        button_layout.addWidget(save_button)
        
        reload_button = QtWidgets.QPushButton("Reload Rules from YAML")
        reload_button.clicked.connect(self.load_rules_from_yaml)
        button_layout.addWidget(reload_button)
        
        # Add Save As New YAML button
        self.save_as_new_yaml_btn = QtWidgets.QPushButton("Save As New YAML")
        self.save_as_new_yaml_btn.clicked.connect(self._on_save_as_new_yaml)
        button_layout.addWidget(self.save_as_new_yaml_btn)
        
        # Remove debug button that was causing AttributeError
        
        main_editor_layout.addLayout(button_layout)
        
        self.load_rules_from_yaml() # Load rules on init (will populate UI elements)
        
        if self.category_list.count() > 0:
            self.category_list.setCurrentRow(0) # Select the first category by default

    def _create_all_rule_pages(self):
        """Calls all individual methods to create rule setting pages."""
        self.create_path_structure_tab()  # 1. Path Structure (moved to top)
        self.create_filepath_naming_tab()  # 2. Filename (renamed, moved up)
        self.create_color_space_tab()     # 3. Color Space (moved up)
        self.create_frame_range_tab()     # 4. Frame Range & Rate
        self.create_node_integrity_tab()  # 5. Node Integrity
        self.create_write_node_combined_tab()  # 6. Write Node Settings (combined)
        self.create_viewer_nodes_tab()    # 7. Viewer Nodes
        self.create_script_errors_tab()   # 8. Script Errors

    def _load_yaml_file(self, file_path: str) -> Optional[Dict]:
        if not os.path.exists(file_path):
            print(f"Warning: YAML file not found at {file_path}")
            return None
        try:
            with open(file_path, 'r') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading YAML file {file_path}: {e}")
            return None

    def _populate_combobox(self, combobox, options, default_value=None):
        combobox.clear()
        # Add default frame rates if not present
        if combobox.objectName() == "frame_rate_combo" or (isinstance(options, list) and all(isinstance(x, (int, float, str)) for x in options)):
            if not options or len(options) == 0:
                options = ["24", "25", "30", "50", "60", "2997", "5994"]
        if isinstance(options, dict):
            model = QStandardItemModel()
            for group, items in options.items():
                group_item = QStandardItem(group)
                group_item.setFlags(QtCore.Qt.NoItemFlags)  # Non-selectable
                model.appendRow(group_item)
                for opt in items:
                    item = QStandardItem(opt)
                    model.appendRow(item)
            combobox.setModel(model)
            # Set default if provided
            if default_value:
                for i in range(model.rowCount()):
                    if model.item(i).text() == default_value:
                        combobox.setCurrentIndex(i)
                        break
        elif isinstance(options, list):
            combobox.addItems([str(opt) for opt in options])
            if default_value and default_value in options:
                combobox.setCurrentText(str(default_value))
            elif options:
                combobox.setCurrentIndex(0)
            # Always set default to 24 if present
            if combobox.count() > 0 and combobox.findText("24") >= 0:
                combobox.setCurrentText("24")
        else:
            combobox.clear()

    def _get_combobox_value(self, combobox: QtWidgets.QComboBox, value_type=str):
        text = combobox.currentText()
        if value_type == bool:
            return text.lower() == 'true'
        if value_type == int:
            try: return int(text)
            except ValueError: return None
        if value_type == float:
            try: return float(text)
            except ValueError: return None
        return text

    def create_filepath_naming_tab(self):
        """ Create tab for Filename rules with dynamic regex generation. """
        tab = QtWidgets.QWidget()
        main_tab_layout = QtWidgets.QVBoxLayout(tab) # Main layout for the tab

        # Section for general path rules
        general_group = QtWidgets.QGroupBox("General Path Rules")
        general_layout = QtWidgets.QFormLayout()
        self.fp_relative_path_check = QtWidgets.QCheckBox("Require Relative Paths")
        general_layout.addRow("", self.fp_relative_path_check)
        self.fp_severity_relative_combo = QtWidgets.QComboBox()
        self._populate_combobox(self.fp_severity_relative_combo, self.dropdown_options.get('severity_options'))
        general_layout.addRow("Severity (Relative Path):", self.fp_severity_relative_combo)
        general_group.setLayout(general_layout)
        main_tab_layout.addWidget(general_group)

        # Section for dynamic filename convention
        convention_group = QtWidgets.QGroupBox("Dynamic Filename Convention")
        convention_layout = QtWidgets.QVBoxLayout()

        # Filename Rule Editor
        self.filename_rule_editor = FilenameRuleEditor(parent=self, available_tokens=self.filename_tokens_for_editor)
        convention_layout.addWidget(self.filename_rule_editor)

        convention_group.setLayout(convention_layout)
        main_tab_layout.addWidget(convention_group)
        
        main_tab_layout.addStretch()
        # Changed from "File Path & Naming" to "Filename"
        self.category_list.addItem("Filename")
        self.settings_stack.addWidget(tab)

    def create_frame_range_tab(self):
        """
        Create tab for frame range and frame rate rules
        """
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        
        frame_range_check = QtWidgets.QCheckBox("Check frame range consistency across all nodes")
        frame_range_check.setChecked(True) # Default, will be loaded from rules
        layout.addWidget(frame_range_check)
        self.fr_consistency_check = frame_range_check # Store for save/load

        missing_frames_check = QtWidgets.QCheckBox("Check for missing frames in input sequences")
        missing_frames_check.setChecked(True) # Default
        layout.addWidget(missing_frames_check)
        self.fr_missing_frames_check = missing_frames_check # Store

        frame_rate_check = QtWidgets.QCheckBox("Check frame rate consistency")
        frame_rate_check.setChecked(True) # Default
        layout.addWidget(frame_rate_check)
        self.fr_rate_consistency_check = frame_rate_check # Store
        
        frame_rate_layout = QtWidgets.QHBoxLayout()
        frame_rate_label = QtWidgets.QLabel("Default frame rate:")
        self.frame_rate_combo = QtWidgets.QComboBox()
        self.frame_rate_combo.setObjectName("frame_rate_combo")
        # Always populate with defaults if not present in YAML
        default_fps_options = ["24", "25", "30", "50", "60", "2997", "5994"]
        self._populate_combobox(self.frame_rate_combo, default_fps_options, "24")
        frame_rate_layout.addWidget(frame_rate_label)
        frame_rate_layout.addWidget(self.frame_rate_combo)
        layout.addLayout(frame_rate_layout)

        self.fr_severity_combo = QtWidgets.QComboBox() # General severity for this tab
        self._populate_combobox(self.fr_severity_combo, self.dropdown_options.get('severity_options'))
        form_layout = QtWidgets.QFormLayout() # For severity
        form_layout.addRow("Severity (General Frame Range):", self.fr_severity_combo)
        layout.addLayout(form_layout)
        
        layout.addStretch()
        # self.tabs.addTab(tab, "Frame Range & Rate") # Old way
        self.category_list.addItem("Frame Range & Rate")
        self.settings_stack.addWidget(tab)

    def create_node_integrity_tab(self):
        """ Create tab for node integrity rules. """
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(tab)

        self.ni_check_disabled_nodes_check = QtWidgets.QCheckBox("Warn on Disabled Nodes")
        layout.addRow("", self.ni_check_disabled_nodes_check)

        self.ni_severity_disabled_combo = QtWidgets.QComboBox()
        self._populate_combobox(self.ni_severity_disabled_combo, self.dropdown_options.get('severity_options'))
        layout.addRow("Severity (Disabled Nodes):", self.ni_severity_disabled_combo)
        
        # self.tabs.addTab(tab, "Node Integrity") # Old way
        self.category_list.addItem("Node Integrity")
        self.settings_stack.addWidget(tab)

    def create_write_node_combined_tab(self):
        """ Create tab for Write Node Settings (combined). """
        tab = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout(tab)
        
        # Resolution Section
        resolution_group = QtWidgets.QGroupBox("Write Node Resolution")
        resolution_layout = QtWidgets.QFormLayout()
        
        self.wnr_allowed_formats_edit = QtWidgets.QLineEdit()
        self.wnr_allowed_formats_edit.setPlaceholderText("Comma-separated Nuke format names (e.g., HD_1080,2K_Super_35_full-ap)")
        resolution_layout.addRow("Allowed Write Formats:", self.wnr_allowed_formats_edit)
        
        self.wnr_allowed_formats_combo = QtWidgets.QComboBox()
        self._populate_combobox(self.wnr_allowed_formats_combo, self.dropdown_options.get('write_node_resolution', {}).get('allowed_formats_options'))
        add_format_button = QtWidgets.QPushButton("Add Example Format")
        add_format_button.clicked.connect(lambda: self.wnr_allowed_formats_edit.setText(
            (self.wnr_allowed_formats_edit.text() + "," if self.wnr_allowed_formats_edit.text() else "") + self.wnr_allowed_formats_combo.currentText()
        ))
        format_selection_layout = QtWidgets.QHBoxLayout()
        format_selection_layout.addWidget(self.wnr_allowed_formats_combo)
        format_selection_layout.addWidget(add_format_button)
        resolution_layout.addRow("Format Examples:", format_selection_layout)

        self.wnr_severity_combo = QtWidgets.QComboBox()
        self._populate_combobox(self.wnr_severity_combo, self.dropdown_options.get('severity_options'))
        resolution_layout.addRow("Severity:", self.wnr_severity_combo)
        
        resolution_group.setLayout(resolution_layout)
        main_layout.addWidget(resolution_group)
        
        # Channels Section
        channels_group = QtWidgets.QGroupBox("Write Node Channels")
        channels_layout = QtWidgets.QFormLayout()
        
        self.ch_require_rgba_check = QtWidgets.QCheckBox("Require RGBA channels in Write nodes")
        channels_layout.addRow("", self.ch_require_rgba_check)

        self.ch_warn_rgb_only_check = QtWidgets.QCheckBox("Warn if only RGB channels (no Alpha) in Write nodes")
        channels_layout.addRow("", self.ch_warn_rgb_only_check)
        
        self.ch_warn_extra_channels_check = QtWidgets.QCheckBox("Warn on extra channels (beyond RGBA) in Write nodes")
        channels_layout.addRow("", self.ch_warn_extra_channels_check)

        self.ch_severity_combo = QtWidgets.QComboBox()
        self._populate_combobox(self.ch_severity_combo, self.dropdown_options.get('severity_options'))
        channels_layout.addRow("Severity (Channel Issues):", self.ch_severity_combo)
        
        channels_group.setLayout(channels_layout)
        main_layout.addWidget(channels_group)
        
        # Render Settings Section
        render_group = QtWidgets.QGroupBox("Write Node Render Settings")
        self.rs_layout = QtWidgets.QFormLayout()
        
        self.rs_file_type_combo = QtWidgets.QComboBox()
        self._populate_combobox(self.rs_file_type_combo, self.dropdown_options.get('render_settings', {}).get('file_type_options'))
        self.rs_layout.addRow("File Type to Configure:", self.rs_file_type_combo)
        self.rs_file_type_combo.currentTextChanged.connect(self._update_render_settings_ui)

        self.rs_dynamic_settings_group = QtWidgets.QGroupBox("Type-Specific Settings")
        self.rs_dynamic_settings_layout = QtWidgets.QFormLayout()
        self.rs_dynamic_settings_group.setLayout(self.rs_dynamic_settings_layout)
        self.rs_layout.addRow(self.rs_dynamic_settings_group)
        
        self.rs_severity_combo = QtWidgets.QComboBox()
        self._populate_combobox(self.rs_severity_combo, self.dropdown_options.get('severity_options'))
        self.rs_layout.addRow("Severity (General):", self.rs_severity_combo)
        
        render_group.setLayout(self.rs_layout)
        main_layout.addWidget(render_group)
        
        # Versioning Section
        versioning_group = QtWidgets.QGroupBox("Write Node Versioning")
        versioning_layout = QtWidgets.QFormLayout()
        
        self.ver_require_token_check = QtWidgets.QCheckBox("Require Version Token in Filename")
        versioning_layout.addRow(self.ver_require_token_check)

        self.ver_token_regex_edit = QtWidgets.QLineEdit()
        versioning_layout.addRow("Version Token Regex:", self.ver_token_regex_edit)
        
        self.ver_token_regex_combo = QtWidgets.QComboBox()
        self._populate_combobox(self.ver_token_regex_combo, self.dropdown_options.get('versioning', {}).get('version_token_regex_examples'))
        self.ver_token_regex_combo.activated.connect(
            lambda: self.ver_token_regex_edit.setText(self.ver_token_regex_combo.currentText())
        )
        versioning_layout.addRow("Regex Examples:", self.ver_token_regex_combo)

        self.ver_severity_require_token_combo = QtWidgets.QComboBox()
        self._populate_combobox(self.ver_severity_require_token_combo, self.dropdown_options.get('severity_options'))
        versioning_layout.addRow("Severity (Require Token):", self.ver_severity_require_token_combo)
        
        versioning_group.setLayout(versioning_layout)
        main_layout.addWidget(versioning_group)
        
        # Initialize render settings UI
        self._update_render_settings_ui(self.rs_file_type_combo.currentText())
        
        main_layout.addStretch()
        self.category_list.addItem("Write Node Settings")
        self.settings_stack.addWidget(tab)

    def create_color_space_tab(self):
        """ Create tab for color space rules for Read and Write nodes. """
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(tab)

        layout.addRow(QtWidgets.QLabel("<b>Read Node Colorspaces</b>"))
        self.cs_read_allowed_edit = QtWidgets.QLineEdit()
        self.cs_read_allowed_edit.setPlaceholderText("Comma-separated (e.g., sRGB,ACEScg)")
        layout.addRow("Allowed Read Colorspaces:", self.cs_read_allowed_edit)
        
        self.cs_read_allowed_combo = QtWidgets.QComboBox()
        self._populate_combobox(self.cs_read_allowed_combo, self.dropdown_options.get('colorspaces', {}).get('allowed_options'))
        add_read_cs_button = QtWidgets.QPushButton("Add Example")
        add_read_cs_button.clicked.connect(lambda: self.cs_read_allowed_edit.setText(
             (self.cs_read_allowed_edit.text() + "," if self.cs_read_allowed_edit.text() else "") + self.cs_read_allowed_combo.currentText()
        ))
        read_cs_layout = QtWidgets.QHBoxLayout()
        read_cs_layout.addWidget(self.cs_read_allowed_combo)
        read_cs_layout.addWidget(add_read_cs_button)
        layout.addRow("Read CS Examples:", read_cs_layout)

        self.cs_read_severity_combo = QtWidgets.QComboBox()
        self._populate_combobox(self.cs_read_severity_combo, self.dropdown_options.get('severity_options'))
        layout.addRow("Severity (Read Node):", self.cs_read_severity_combo)

        layout.addRow(QtWidgets.QLabel("<b>Write Node Colorspaces</b>"))
        self.cs_write_allowed_edit = QtWidgets.QLineEdit()
        self.cs_write_allowed_edit.setPlaceholderText("Comma-separated (e.g., sRGB,ACEScg)")
        layout.addRow("Allowed Write Colorspaces:", self.cs_write_allowed_edit)

        self.cs_write_allowed_combo = QtWidgets.QComboBox()
        self._populate_combobox(self.cs_write_allowed_combo, self.dropdown_options.get('colorspaces', {}).get('allowed_options'))
        add_write_cs_button = QtWidgets.QPushButton("Add Example")
        add_write_cs_button.clicked.connect(lambda: self.cs_write_allowed_edit.setText(
             (self.cs_write_allowed_edit.text() + "," if self.cs_write_allowed_edit.text() else "") + self.cs_write_allowed_combo.currentText()
        ))
        write_cs_layout = QtWidgets.QHBoxLayout()
        write_cs_layout.addWidget(self.cs_write_allowed_combo)
        write_cs_layout.addWidget(add_write_cs_button)
        layout.addRow("Write CS Examples:", write_cs_layout)

        self.cs_write_severity_combo = QtWidgets.QComboBox()
        self._populate_combobox(self.cs_write_severity_combo, self.dropdown_options.get('severity_options'))
        layout.addRow("Severity (Write Node):", self.cs_write_severity_combo)
        
        # self.tabs.addTab(tab, "Color Space") # Old way
        self.category_list.addItem("Color Space")
        self.settings_stack.addWidget(tab)

    def create_viewer_nodes_tab(self):
        """ Create tab for Viewer Node rules. """
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(tab)

        self.vn_warn_ip_active_check = QtWidgets.QCheckBox("Warn if 'Use GPU for Viewer Process' is Active")
        layout.addRow(self.vn_warn_ip_active_check)

        self.vn_severity_combo = QtWidgets.QComboBox()
        self._populate_combobox(self.vn_severity_combo, self.dropdown_options.get('severity_options'))
        layout.addRow("Severity:", self.vn_severity_combo)

        # self.tabs.addTab(tab, "Viewer Nodes") # Old way
        self.category_list.addItem("Viewer Nodes")
        self.settings_stack.addWidget(tab)

    def create_script_errors_tab(self):
        """ Create tab for Expressions and Read File error rules. """
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(tab)

        self.se_check_expression_errors_check = QtWidgets.QCheckBox("Check Knobs for Expression Errors")
        layout.addRow(self.se_check_expression_errors_check)
        self.se_severity_expression_combo = QtWidgets.QComboBox()
        self._populate_combobox(self.se_severity_expression_combo, self.dropdown_options.get('severity_options'))
        layout.addRow("Severity (Expression Errors):", self.se_severity_expression_combo)

        self.se_check_read_file_existence_check = QtWidgets.QCheckBox("Check Read Node File Existence (First Frame)")
        layout.addRow(self.se_check_read_file_existence_check)
        self.se_severity_read_file_combo = QtWidgets.QComboBox()
        self._populate_combobox(self.se_severity_read_file_combo, self.dropdown_options.get('severity_options'))
        layout.addRow("Severity (Read File Missing):", self.se_severity_read_file_combo)

        # self.tabs.addTab(tab, "Script Errors") # Old way
        self.category_list.addItem("Script Errors")
        self.settings_stack.addWidget(tab)

    def create_path_structure_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        # Load path_structures from rules.yaml
        rules_yaml = self._load_yaml_file(self.rules_yaml_path)
        path_structures = rules_yaml.get('path_structures', {}) if rules_yaml else {}
        
        self.path_rule_editor = PathRuleEditor(parent=self, path_structures=path_structures, token_definitions=rules_yaml.get('token_definitions', {}))
        layout.addWidget(self.path_rule_editor)
        tab.setLayout(layout)
        self.category_list.addItem("Path Structure")
        self.settings_stack.addWidget(tab)

    def save_rules_to_yaml(self):
        """ Gathers data from UI elements and saves to rules.yaml, preserving existing structure. """
        # Load existing YAML to preserve structure and fields not in UI
        existing_rules = self._load_yaml_file(self.rules_yaml_path) or {}
        
        # Merge UI changes into existing structure
        rules_data = existing_rules.copy()
        
        # --- File Paths & Naming ---
        fp_rules = rules_data.get('file_paths', {})
        fp_rules['relative_path_required'] = self.fp_relative_path_check.isChecked()
        fp_rules['severity_relative_path'] = self._get_combobox_value(self.fp_severity_relative_combo)
        # Save dynamic naming convention parts
        fp_rules['filename_template'] = self.filename_rule_editor.regex_edit.text()
        
        # Get the template configuration from the template builder
        template_config = self.filename_rule_editor.template_builder.get_template_config()
        
        # Update the token definitions with the latest from FILENAME_TOKENS
        updated_tokens = []
        for token_cfg in template_config:
            token_name = token_cfg.get("name")
            if token_name:
                # Find the current master definition for this token
                master_def = next((t for t in FILENAME_TOKENS if t["name"] == token_name), None)
                if master_def:
                    # Create a new token config with updated token_def from master
                    updated_token = {
                        "name": token_name,
                        "token_def": master_def.copy(),  # Use the current master definition
                        "value": token_cfg.get("value"),
                        "separator": token_cfg.get("separator", "")
                    }
                    
                    # ALWAYS ensure we're using the master regex_template for ALL tokens
                    if "regex_template" in master_def:
                        updated_token["token_def"]["regex_template"] = master_def["regex_template"]
                        print(f"Using master regex_template for {token_name}: {master_def['regex_template']}")
                    
                    # Special case for description token
                    if token_name == "description":
                        updated_token["token_def"]["regex_template"] = ".+?"
                        print(f"Explicitly setting description token regex_template to: {updated_token['token_def']['regex_template']}")
                    
                    updated_tokens.append(updated_token)
                else:
                    # If no master definition found, use the original but log a warning
                    print(f"Warning: No master definition found for token '{token_name}' in FILENAME_TOKENS")
                    updated_tokens.append(token_cfg)
        
        fp_rules['filename_tokens'] = updated_tokens
        
        # Force regeneration of regex with updated token definitions
        try:
            # First update the template builder with the updated token definitions
            if hasattr(self.filename_rule_editor, 'template_builder'):
                # Store the current configuration to restore after updating
                current_config = self.filename_rule_editor.template_builder.get_template_config()
                
                # Ensure separators are properly set in the token configs
                for token_cfg in updated_tokens:
                    # Find the corresponding token in the template builder
                    for i, template_token in enumerate(self.filename_rule_editor.template_builder.token_configs):
                        if template_token.get("name") == token_cfg.get("name"):
                            # Update the separator in the template builder
                            separator = token_cfg.get("separator", "")
                            self.filename_rule_editor.template_builder.token_configs[i]["separator"] = separator
                
                # Update regex with the updated token definitions
                self.filename_rule_editor.update_regex()
                constructed_regex = self.filename_rule_editor.regex_edit.text()
                if constructed_regex:
                    fp_rules['naming_pattern_regex'] = constructed_regex # This is the constructed/validated regex
                    print(f"Updated regex pattern: {constructed_regex}")
        except (RuntimeError, AttributeError) as e:
            print(f"Warning: Error updating regex during save: {e}")
            # May fail if template builder not ready, but we still want to save the updated tokens
        fp_rules['severity_naming_pattern'] = self._get_combobox_value(self.rs_severity_combo)
        rules_data['file_paths'] = fp_rules
        
        # Save path rule editor config
        if hasattr(self, 'path_rule_editor'):
            path_rules = rules_data.get('path_rules', {})
            path_rules.update({
                'base_path': self.path_rule_editor.base_path_edit.text(),
                'shot_structure': self.path_rule_editor.shot_struct_combo.currentText(),
                'relative_path': self.path_rule_editor.rel_path_edit.text(),
                'tokens': {token: combo.currentText() for token, combo in self.path_rule_editor.token_controls.items()}
            })
            rules_data['path_rules'] = path_rules

        if hasattr(self, 'fr_consistency_check'): # Frame Range Tab
            fr_rules = rules_data.get('frame_range', {})
            fr_rules.update({
                'check_consistency': self.fr_consistency_check.isChecked(),
                'check_missing_frames': self.fr_missing_frames_check.isChecked(),
                'check_rate_consistency': self.fr_rate_consistency_check.isChecked(),
                'default_fps': float(self._get_combobox_value(self.frame_rate_combo, value_type=float) or '24.0'), # Provide default if None
                'severity': self._get_combobox_value(self.fr_severity_combo)
            })
            rules_data['frame_range'] = fr_rules

        ni_rules = rules_data.get('node_integrity', {})
        ni_rules['check_disabled_nodes'] = self.ni_check_disabled_nodes_check.isChecked()
        ni_rules['severity_disabled_nodes'] = self._get_combobox_value(self.ni_severity_disabled_combo)
        rules_data['node_integrity'] = ni_rules
        
        wnr_rules = rules_data.get('write_node_resolution', {})
        allowed_formats_text = self.wnr_allowed_formats_edit.text()
        if allowed_formats_text:
            wnr_rules['allowed_formats'] = [fmt.strip() for fmt in allowed_formats_text.split(',') if fmt.strip()]
        wnr_rules['severity'] = self._get_combobox_value(self.wnr_severity_combo)
        rules_data['write_node_resolution'] = wnr_rules

        cs_rules = rules_data.get('colorspaces', {'Read': {}, 'Write': {}})
        read_allowed_text = self.cs_read_allowed_edit.text()
        if read_allowed_text:
            cs_rules['Read']['allowed'] = [cs.strip() for cs in read_allowed_text.split(',') if cs.strip()]
        cs_rules['Read']['severity'] = self._get_combobox_value(self.cs_read_severity_combo)
        
        write_allowed_text = self.cs_write_allowed_edit.text()
        if write_allowed_text:
            cs_rules['Write']['allowed'] = [cs.strip() for cs in write_allowed_text.split(',') if cs.strip()]
        cs_rules['Write']['severity'] = self._get_combobox_value(self.cs_write_severity_combo)
        rules_data['colorspaces'] = cs_rules

        ch_rules_write = rules_data.get('channels', {})
        ch_rules_write['require_rgba'] = self.ch_require_rgba_check.isChecked()
        ch_rules_write['warn_on_rgb_only'] = self.ch_warn_rgb_only_check.isChecked()
        ch_rules_write['warn_on_extra_channels'] = self.ch_warn_extra_channels_check.isChecked()
        ch_rules_write['severity'] = self._get_combobox_value(self.ch_severity_combo) 
        rules_data['channels'] = ch_rules_write

        rs_rules_root = rules_data.get('render_settings', {'Write': {}})
        rs_rules_write = rs_rules_root.get('Write', {})
        if 'file_type_rules' not in rs_rules_write:
            rs_rules_write['file_type_rules'] = {}
        selected_file_type = self._get_combobox_value(self.rs_file_type_combo)
        if selected_file_type and hasattr(self, 'rs_dynamic_widgets'): 
            type_specific_rules = {}
            for knob_name, widget_obj in self.rs_dynamic_widgets.items():
                if isinstance(widget_obj, QtWidgets.QComboBox):
                    type_specific_rules[knob_name] = [self._get_combobox_value(widget_obj)] 
            if type_specific_rules:
                 rs_rules_write['file_type_rules'][selected_file_type] = type_specific_rules
        rs_rules_write['severity'] = self._get_combobox_value(self.rs_severity_combo)
        rs_rules_root['Write'] = rs_rules_write
        rules_data['render_settings'] = rs_rules_root
        
        ver_rules = rules_data.get('versioning', {})
        ver_rules['require_version_token'] = self.ver_require_token_check.isChecked()
        if self.ver_token_regex_edit.text():
            ver_rules['version_token_regex'] = self.ver_token_regex_edit.text()
        ver_rules['severity_require_token'] = self._get_combobox_value(self.ver_severity_require_token_combo)
        rules_data['versioning'] = ver_rules

        vn_rules = rules_data.get('viewer_nodes', {})
        vn_rules['warn_if_ip_active'] = self.vn_warn_ip_active_check.isChecked()
        vn_rules['severity'] = self._get_combobox_value(self.vn_severity_combo)
        rules_data['viewer_nodes'] = vn_rules

        se_rules_exp = rules_data.get('expressions_errors', {})
        se_rules_exp['check_for_errors'] = self.se_check_expression_errors_check.isChecked()
        se_rules_exp['severity'] = self._get_combobox_value(self.se_severity_expression_combo)
        rules_data['expressions_errors'] = se_rules_exp

        se_rules_read = rules_data.get('read_file_errors', {})
        se_rules_read['check_existence'] = self.se_check_read_file_existence_check.isChecked()
        se_rules_read['severity'] = self._get_combobox_value(self.se_severity_read_file_combo)
        rules_data['read_file_errors'] = se_rules_read
        
        try:
            # Save to the current rules_yaml_path
            with open(self.rules_yaml_path, 'w') as f:
                yaml.dump(rules_data, f, sort_keys=False, indent=2)
            print(f"Rules saved to {self.rules_yaml_path}")
            
            # Update the current YAML name for display
            self.current_yaml_name = os.path.basename(self.rules_yaml_path)
            
            # Notify main window to reload validator rules if rules editor was saved
            # First try the explicitly stored parent
            main_window = None
            if hasattr(self, 'main_window_parent') and self.main_window_parent and hasattr(self.main_window_parent, 'validator'):
                main_window = self.main_window_parent
            
            # If that fails, try the Qt parent hierarchy
            if not main_window:
                parent_window = self.parent()
                temp_parent = parent_window
                while temp_parent:
                    if hasattr(temp_parent, 'validator'):
                        main_window = temp_parent
                        break
                    temp_parent = temp_parent.parent()
                
            if main_window:
                # Reload validator rules to reflect the changes immediately
                main_window.validator.set_rules_file_path(self.rules_yaml_path)
                main_window.statusBar().showMessage(f"Rules saved to {os.path.basename(self.rules_yaml_path)} and validator updated", 3000)
                
                # If the parent has a yaml_selector_combo, make sure it's updated to show the current file
                if hasattr(main_window, 'yaml_selector_combo'):
                    current_yaml = os.path.basename(self.rules_yaml_path)
                    idx = main_window.yaml_selector_combo.findText(current_yaml)
                    if idx >= 0:
                        main_window.yaml_selector_combo.setCurrentIndex(idx)
            else:
                print(f"Warning: Could not find main window with validator attribute. Rules saved to {self.rules_yaml_path} but validator not updated.")
                
        except Exception as e:
            print(f"Error saving rules to {self.rules_yaml_path}: {e}")
            QtWidgets.QMessageBox.critical(self, "Save Error", f"Could not save rules: {e}")

    def _prepare_filename_tokens_for_editor(self):
        """
        Transforms the global FILENAME_TOKENS constant into the list format required by FilenameRuleEditor.
        This method uses the master list of available tokens (FILENAME_TOKENS constant), not the 'token_definitions'
        section of the currently loaded rule set YAML. This ensures the editor's palette is always populated
        with the full set of available tokens regardless of which rule set is loaded.
        Warnings will be printed if essential UI fields (control, label, options for dropdowns) are missing from FILENAME_TOKENS items.
        """
        self.filename_tokens_for_editor = []
        if not FILENAME_TOKENS: # FILENAME_TOKENS is the global constant
            print("Warning: Global FILENAME_TOKENS constant is empty. FilenameRuleEditor will have no tokens.")
            return

        for master_def in FILENAME_TOKENS:
            if not isinstance(master_def, dict):
                print(f"Warning: Skipping token definition from master list as it's not a dictionary: {master_def}")
                continue

            token_name = master_def.get("name")
            if not token_name:
                print(f"Warning: Skipping token definition from master list as it's missing a 'name': {master_def}")
                continue

            # Create a deep copy of the master definition to avoid modifying the original
            editor_token_def = master_def.copy()
            
            # Ensure all required fields are present with defaults if needed
            if "label" not in editor_token_def:
                editor_token_def["label"] = f"<{token_name}>"
            
            if "regex_template" not in editor_token_def:
                editor_token_def["regex_template"] = ".+?"
                
            # Special handling for description token - always use .+? as the regex_template
            if token_name == "description":
                editor_token_def["regex_template"] = ".+?"
                
            if "desc" not in editor_token_def:
                editor_token_def["desc"] = "No description."
                
            if "control" not in editor_token_def:
                editor_token_def["control"] = "static"
                print(f"Warning: Token '{token_name}' from master list has no 'control' type defined. Defaulting to 'static'.")
                
            if "options" not in editor_token_def:
                editor_token_def["options"] = []
                
            # Handle "examples" - FILENAME_TOKENS items might not have this key
            if "examples" not in editor_token_def:
                # Use label as a fallback example if "examples" is not in the master definition
                editor_token_def["examples"] = [editor_token_def.get("label", token_name)]

            # Check derived editor_token_def for conditional requirements
            if editor_token_def["control"] in ["dropdown", "multiselect"] and not editor_token_def["options"]:
                print(f"Warning: Token '{token_name}' from master list is '{editor_token_def['control']}' but has no 'options'.")
                
            if editor_token_def["control"] == "spinner" and (editor_token_def.get("min") is None or editor_token_def.get("max") is None or editor_token_def.get("default") is None):
                print(f"Warning: Token '{token_name}' from master list is 'spinner' but is missing 'min', 'max', or 'default'.")
                
            if editor_token_def["control"] == "range_spinner" and (editor_token_def.get("min") is None or editor_token_def.get("max") is None or editor_token_def.get("default_min") is None or editor_token_def.get("default_max") is None):
                print(f"Warning: Token '{token_name}' from master list is 'range_spinner' but is missing 'min', 'max', 'default_min', or 'default_max'.")

            self.filename_tokens_for_editor.append(editor_token_def)
        
        if not self.filename_tokens_for_editor:
            print("Warning: Master list FILENAME_TOKENS resulted in an empty list for FilenameRuleEditor.")

    def load_rules_from_yaml(self, yaml_path=None):
        """ Loads rules from the specified YAML file and populates the UI elements.
        
        Args:
            yaml_path (str, optional): Path to the YAML file to load. If None, uses self.rules_yaml_path.
        """
        # If a specific path is provided, update the current path
        if yaml_path and os.path.exists(yaml_path):
            self.rules_yaml_path = yaml_path
            self.current_yaml_name = os.path.basename(yaml_path)
            # Update the label to show which file is being edited
            if hasattr(self, 'current_file_label'):
                self.current_file_label.setText(f"Editing: {self.current_yaml_name}")
            
        loaded_rules = self._load_yaml_file(self.rules_yaml_path) or {}
        # --- File Paths & Naming ---
        fp_rules = loaded_rules.get('file_paths', {})
        self.fp_relative_path_check.setChecked(fp_rules.get('relative_path_required', False))
        self._populate_combobox(self.fp_severity_relative_combo, self.dropdown_options.get('severity_options'), fp_rules.get('severity_relative_path'))
        # Load dynamic naming convention parts
        self.filename_rule_editor.regex_edit.setText(fp_rules.get('naming_pattern_regex', ""))
        self.filename_rule_editor.template_builder.clear()
        # Ensure filename_rule_editor and its template_builder are available
        if hasattr(self, 'filename_rule_editor') and hasattr(self.filename_rule_editor, 'template_builder'):
            for token_cfg_from_template in fp_rules.get('filename_tokens', []): # These are the tokens saved as part of a specific template
                if "name" in token_cfg_from_template:
                    # Find the full definition of this token from the available tokens for the editor
                    # First check if there's a master definition in FILENAME_TOKENS
                    master_def = next((t for t in FILENAME_TOKENS if t["name"] == token_cfg_from_template["name"]), None)
                    
                    # If found in master definitions, use that
                    if master_def:
                        # Create a copy to avoid modifying the original
                        full_token_def = master_def.copy()
                        # Add the token to the template builder using the master definition
                        self.filename_rule_editor.template_builder.add_token(full_token_def)
                        # Alias for clarity in the existing logic below
                        token_cfg = token_cfg_from_template
                    else:
                        # Fallback to the editor's token definitions if not found in master
                        full_token_def = next((t_def for t_def in self.filename_tokens_for_editor if t_def["name"] == token_cfg_from_template["name"]), None)
                        
                        if full_token_def:
                            # Before adding, check if there's a master definition for this token name
                            # This is a second check to ensure we always use master definitions
                            master_def = next((t for t in FILENAME_TOKENS if t["name"] == token_cfg_from_template["name"]), None)
                            if master_def and "regex_template" in master_def:
                                full_token_def["regex_template"] = master_def["regex_template"]
                                
                            # Add the token to the template builder using its full definition
                            self.filename_rule_editor.template_builder.add_token(full_token_def)
                            # Alias for clarity in the existing logic below
                            token_cfg = token_cfg_from_template
                    
                    # For TableBasedFilenameTemplateBuilder, we need to configure the token differently
                    if hasattr(self.filename_rule_editor.template_builder, 'token_configs'):
                        # Table-based approach - find the config we just added and update it
                        token_configs = self.filename_rule_editor.template_builder.token_configs
                        if token_configs:
                            # Get the last added token config
                            last_config = token_configs[-1]
                            
                            # Update the configuration directly
                            if token_cfg.get("value") is not None:
                                last_config["value"] = token_cfg["value"]
                            if "separator" in token_cfg:
                                last_config["separator"] = token_cfg["separator"]
                            
                            # Rebuild the table to reflect changes
                            self.filename_rule_editor.template_builder._rebuild_table()
                            
                            print(f"TABLE-BASED DEBUG: Configured token {token_cfg['name']}")
                            print(f"  Value: {last_config.get('value')}")
                            print(f"  Separator: {last_config.get('separator')}")
                    
                    # Legacy approach for widget-based builders
                    elif hasattr(self.filename_rule_editor.template_builder, 'token_widgets'):
                        token_widgets = self.filename_rule_editor.template_builder.token_widgets
                        if token_widgets:
                            widget = token_widgets[-1]
                            
                            # Set control value
                            if token_cfg.get("value") is not None:
                                if hasattr(widget, 'control') and widget.control:
                                    try:
                                        if isinstance(widget.control, QtWidgets.QSpinBox):
                                            widget.control.setValue(token_cfg["value"])
                                        elif isinstance(widget.control, QtWidgets.QComboBox):
                                            idx = widget.control.findText(str(token_cfg["value"]))
                                            if idx >= 0:
                                                widget.control.setCurrentIndex(idx)
                                        elif isinstance(widget.control, SimpleMultiSelectWidget):
                                            # Ensure value is a list for multiselect
                                            if isinstance(token_cfg["value"], list):
                                                values_to_set = token_cfg["value"]
                                            elif token_cfg["value"]:
                                                values_to_set = [str(token_cfg["value"])]
                                            else:
                                                values_to_set = []
                                            
                                            print(f"MULTISELECT DEBUG: Loading {token_cfg['name']}")
                                            print(f"  Raw value from config: {token_cfg['value']} (type: {type(token_cfg['value'])})")
                                            print(f"  Values to set: {values_to_set}")
                                            print(f"  Widget options: {list(widget.control.checkboxes.keys()) if hasattr(widget.control, 'checkboxes') else 'No checkboxes'}")
                                            
                                            widget.control.set_selected_values(values_to_set)
                                            
                                            # Verify immediately after setting
                                            actual_values = widget.control.get_selected_values()
                                            print(f"  Values after setting: {actual_values}")
                                            print(f"  Summary text: {widget.control.summary_button.text()}")
                                            print("---")
                                    except (RuntimeError, AttributeError) as e:
                                        pass  # Widget may not support the operation
                            
                            # Set separator from token config
                            if "separator" in token_cfg and hasattr(widget, 'separator_combo'):
                                separator = token_cfg["separator"]
                                if not separator:
                                    separator = "(none)"
                                try:
                                    idx = widget.separator_combo.findText(separator)
                                    if idx >= 0:
                                        widget.separator_combo.setCurrentIndex(idx)
                                    else:
                                        # If the exact separator isn't found, default to "_"
                                        default_idx = widget.separator_combo.findText("_")
                                        if default_idx >= 0:
                                            widget.separator_combo.setCurrentIndex(default_idx)
                                except (RuntimeError, AttributeError):
                                    pass  # Widget may not exist yet
            # Update regex after adding each token
            try:
                self.filename_rule_editor.update_regex()
            except (RuntimeError, AttributeError):
                pass  # May fail during initialization
        self._populate_combobox(self.fr_severity_combo, self.dropdown_options.get('severity_options'), fp_rules.get('severity'))
        # Load path rule editor config
        path_rules = loaded_rules.get('path_rules', {})
        if hasattr(self, 'path_rule_editor') and path_rules:
            self.path_rule_editor.base_path_edit.setText(path_rules.get('base_path', ""))
            self.path_rule_editor.rel_path_edit.setText(path_rules.get('relative_path', ""))
            for token, value in path_rules.get('tokens', {}).items():
                if token in self.path_rule_editor.token_controls:
                    self.path_rule_editor.token_controls[token].setCurrentText(value)
            idx = self.path_rule_editor.shot_struct_combo.findText(path_rules.get('shot_structure', ""))
            if idx >= 0:
                self.path_rule_editor.shot_struct_combo.setCurrentIndex(idx)
            self.path_rule_editor.update_preview()
        fr_rules = loaded_rules.get('frame_range', {}) # Frame Range Tab
        if hasattr(self, 'fr_consistency_check'):
            self.fr_consistency_check.setChecked(fr_rules.get('check_consistency', True))
            self.fr_missing_frames_check.setChecked(fr_rules.get('check_missing_frames', True))
            self.fr_rate_consistency_check.setChecked(fr_rules.get('check_rate_consistency', True))
            self._populate_combobox(self.frame_rate_combo, self.dropdown_options.get('frame_range', {}).get('fps_options'), str(fr_rules.get('default_fps', '24')))
            self._populate_combobox(self.fr_severity_combo, self.dropdown_options.get('severity_options'), fr_rules.get('severity'))


        ni_rules = loaded_rules.get('node_integrity', {})
        self.ni_check_disabled_nodes_check.setChecked(ni_rules.get('check_disabled_nodes', False))
        self._populate_combobox(self.ni_severity_disabled_combo, self.dropdown_options.get('severity_options'), ni_rules.get('severity_disabled_nodes'))

        wnr_rules = loaded_rules.get('write_node_resolution', {})
        self.wnr_allowed_formats_edit.setText(",".join(wnr_rules.get('allowed_formats', [])))
        self._populate_combobox(self.wnr_severity_combo, self.dropdown_options.get('severity_options'), wnr_rules.get('severity'))
        
        cs_rules = loaded_rules.get('colorspaces', {})
        cs_read_rules = cs_rules.get('Read', {})
        self.cs_read_allowed_edit.setText(",".join(cs_read_rules.get('allowed', [])))
        self._populate_combobox(self.cs_read_severity_combo, self.dropdown_options.get('severity_options'), cs_read_rules.get('severity'))
        
        cs_write_rules = cs_rules.get('Write', {})
        self.cs_write_allowed_edit.setText(",".join(cs_write_rules.get('allowed', [])))
        self._populate_combobox(self.cs_write_severity_combo, self.dropdown_options.get('severity_options'), cs_write_rules.get('severity'))

        ch_rules_data = loaded_rules.get('channels', {}) # Adjusted to load from 'channels' directly
        self.ch_require_rgba_check.setChecked(ch_rules_data.get('require_rgba', True))
        self.ch_warn_rgb_only_check.setChecked(ch_rules_data.get('warn_on_rgb_only', False))
        self.ch_warn_extra_channels_check.setChecked(ch_rules_data.get('warn_on_extra_channels', False))
        self._populate_combobox(self.ch_severity_combo, self.dropdown_options.get('severity_options'), ch_rules_data.get('severity'))

        rs_rules_root = loaded_rules.get('render_settings', {})
        rs_rules_write = rs_rules_root.get('Write', {}) # Get 'Write' sub-dictionary
        self._populate_combobox(self.rs_severity_combo, self.dropdown_options.get('severity_options'), rs_rules_write.get('severity'))
        
        current_selected_file_type = self._get_combobox_value(self.rs_file_type_combo)
        if current_selected_file_type:
            # Ensure _update_render_settings_ui is called to create widgets before trying to populate them
            self._update_render_settings_ui(current_selected_file_type) 
            
            specific_file_rules = rs_rules_write.get('file_type_rules', {}).get(current_selected_file_type, {})
            if hasattr(self, 'rs_dynamic_widgets'):
                for knob_name, widget_obj in self.rs_dynamic_widgets.items():
                    if knob_name in specific_file_rules:
                        value_to_set = specific_file_rules[knob_name]
                        if isinstance(widget_obj, QtWidgets.QComboBox):
                            # Ensure widget_obj.model() is not None before calling stringList()
                            current_items = [widget_obj.itemText(i) for i in range(widget_obj.count())] if widget_obj else []
                            val_to_set_str = str(value_to_set[0]) if isinstance(value_to_set, list) and value_to_set else str(value_to_set)
                            self._populate_combobox(widget_obj, current_items, val_to_set_str)


        ver_rules = loaded_rules.get('versioning', {})
        self.ver_require_token_check.setChecked(ver_rules.get('require_version_token', False))
        self.ver_token_regex_edit.setText(ver_rules.get('version_token_regex', ""))
        self._populate_combobox(self.ver_token_regex_combo, self.dropdown_options.get('versioning', {}).get('version_token_regex_examples'))

        vn_rules = loaded_rules.get('viewer_nodes', {})
        self.vn_warn_ip_active_check.setChecked(vn_rules.get('warn_if_ip_active', False))
        self._populate_combobox(self.vn_severity_combo, self.dropdown_options.get('severity_options'), vn_rules.get('severity'))

        se_rules_exp = loaded_rules.get('expressions_errors', {})
        self.se_check_expression_errors_check.setChecked(se_rules_exp.get('check_for_errors', False))
        self._populate_combobox(self.se_severity_expression_combo, self.dropdown_options.get('severity_options'), se_rules_exp.get('severity'))

        se_rules_read = loaded_rules.get('read_file_errors', {})
        self.se_check_read_file_existence_check.setChecked(se_rules_read.get('check_existence', False))
        self._populate_combobox(self.se_severity_read_file_combo, self.dropdown_options.get('severity_options'), se_rules_read.get('severity'))
        
        print(f"Rules loaded from {self.rules_yaml_path} ({self.current_yaml_name})")

    def _on_save_as_new_yaml(self):
        """Save current rules to a new YAML file"""
        dir_path = os.path.dirname(os.path.abspath(__file__))
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save New Rules YAML", dir_path, "YAML Files (*.yaml)")
        if path:
            # Save current rules to new YAML
            old_path = self.rules_yaml_path
            self.rules_yaml_path = path
            self.current_yaml_name = os.path.basename(path)
            self.save_rules_to_yaml()
            
            # Notify parent (main window) about the new YAML file if possible
            # Try to find the main window parent that has refresh_yaml_selector attribute
            main_window = None
            
            # First try the explicitly stored parent
            if hasattr(self, 'main_window_parent') and self.main_window_parent and hasattr(self.main_window_parent, 'refresh_yaml_selector'):
                main_window = self.main_window_parent
            
            # If that fails, try the Qt parent hierarchy
            if not main_window:
                temp_parent = self.parent()
                while temp_parent:
                    if hasattr(temp_parent, 'refresh_yaml_selector'):
                        main_window = temp_parent
                        break
                    temp_parent = temp_parent.parent()
                
            if main_window:
                main_window.refresh_yaml_selector()
                # Set the new YAML as selected
                yaml_name = os.path.basename(path)
                idx = main_window.yaml_selector_combo.findText(yaml_name)
                if idx >= 0:
                    main_window.yaml_selector_combo.setCurrentIndex(idx)
            else:
                print(f"Warning: Could not find main window with refresh_yaml_selector attribute. New YAML file saved but selector not updated.")

    def _update_render_settings_ui(self, file_type: str):
        """ Dynamically update UI for render settings based on selected file type. """
        while self.rs_dynamic_settings_layout.count():
            child = self.rs_dynamic_settings_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        self.rs_dynamic_widgets = {} 

        if not file_type or not self.dropdown_options: return

        file_type_specific_options = self.dropdown_options.get('render_settings', {}).get(file_type, {})
        
        if file_type == "exr":
            self.rs_exr_datatype_combo = QtWidgets.QComboBox()
            self._populate_combobox(self.rs_exr_datatype_combo, file_type_specific_options.get('datatype_options'))
            self.rs_dynamic_settings_layout.addRow("EXR Datatype:", self.rs_exr_datatype_combo)
            self.rs_dynamic_widgets['datatype'] = self.rs_exr_datatype_combo

            self.rs_exr_compression_combo = QtWidgets.QComboBox()
            self._populate_combobox(self.rs_exr_compression_combo, file_type_specific_options.get('compression_options'))
            self.rs_dynamic_settings_layout.addRow("EXR Compression:", self.rs_exr_compression_combo)
            self.rs_dynamic_widgets['compression'] = self.rs_exr_compression_combo

        elif file_type == "mov":
            self.rs_mov_codec_combo = QtWidgets.QComboBox()
            self._populate_combobox(self.rs_mov_codec_combo, file_type_specific_options.get('codec_options'))
            self.rs_dynamic_settings_layout.addRow("MOV Codec:", self.rs_mov_codec_combo)
            self.rs_dynamic_widgets['codec'] = self.rs_mov_codec_combo
            
        elif file_type == "jpg":
            self.rs_jpg_quality_combo = QtWidgets.QComboBox() 
            self._populate_combobox(self.rs_jpg_quality_combo, file_type_specific_options.get('_jpeg_quality_options'))
            self.rs_dynamic_settings_layout.addRow("JPG Quality:", self.rs_jpg_quality_combo)
            self.rs_dynamic_widgets['_jpeg_quality'] = self.rs_jpg_quality_combo
            
            self.rs_jpg_sub_sampling_combo = QtWidgets.QComboBox()
            self._populate_combobox(self.rs_jpg_sub_sampling_combo, file_type_specific_options.get('_jpeg_sub_sampling_options'))
            self.rs_dynamic_settings_layout.addRow("JPG Sub-sampling:", self.rs_jpg_sub_sampling_combo)
            self.rs_dynamic_widgets['_jpeg_sub_sampling'] = self.rs_jpg_sub_sampling_combo

class PathRuleEditor(QtWidgets.QWidget):
    """
    Widget for path validation rule editing with advanced path validation capabilities.
    
    This widget provides a comprehensive UI for creating and configuring path validation
    rules, including base path selection, relative path structure building, and live
    rule preview functionality.
    
    Features:
        - Base path selection with browse functionality
        - Relative path structure builder with token support
        - Path template visualization and validation
        - Live rule preview with error highlighting
        - Support for environment variable expansion
        - Path token management with custom token definitions
    
    This class works in conjunction with the FilenameRuleEditor to provide a complete
    file path validation solution for the validator system.
    """
    def __init__(self, parent=None, path_structures=None, token_definitions=None):
        super().__init__(parent)
        self.parent = parent
        self.token_definitions = token_definitions or {}
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        # Help/info button
        help_btn = QtWidgets.QPushButton("?")
        help_btn.setFixedWidth(24)
        help_btn.setToolTip("Show help and usage instructions")
        help_btn.clicked.connect(self.show_help_dialog)
        layout.addWidget(help_btn, alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        # Base path selector
        base_path_layout = QtWidgets.QHBoxLayout()
        base_path_label = QtWidgets.QLabel("Base Path:")
        base_path_label.setToolTip("The root directory for all output paths.")
        self.base_path_edit = QtWidgets.QLineEdit()
        self.base_path_edit.setPlaceholderText("e.g. V:/Project/Sequence/Shot")
        self.base_path_edit.setToolTip("Set the root directory for output paths.")
        browse_btn = QtWidgets.QPushButton("Browse")
        browse_btn.setToolTip("Browse for base path")
        browse_btn.clicked.connect(self.browse_base_path)
        base_path_layout.addWidget(base_path_label)
        base_path_layout.addWidget(self.base_path_edit)
        base_path_layout.addWidget(browse_btn)
        layout.addLayout(base_path_layout)
        # Shot structure dropdown
        shot_struct_layout = QtWidgets.QHBoxLayout()
        shot_struct_label = QtWidgets.QLabel("Shot Structure:")
        shot_struct_label.setToolTip("Select a path template for your project/shot.")
        self.shot_struct_combo = QtWidgets.QComboBox()
        self.shot_struct_combo.setToolTip("Select a shot structure template")
        shot_struct_layout.addWidget(shot_struct_label)
        shot_struct_layout.addWidget(self.shot_struct_combo)
        layout.addLayout(shot_struct_layout)
        # Token-based relative path builder
        self.token_controls = {}
        self.rel_path_tokens = ["<shot_name>", "<resolution>", "<version>"]
        rel_path_tokens_layout = QtWidgets.QHBoxLayout()
        rel_path_tokens_layout.addWidget(QtWidgets.QLabel("Tokens:"))
        for token in self.rel_path_tokens:
            combo = QtWidgets.QComboBox()
            combo.setEditable(True)
            combo.setToolTip(f"Set value for {token}")
            combo.setStyleSheet("""
                QComboBox {
                    background: #232323;
                    color: #e0e0e0;
                    border: 1px solid #444;
                    border-radius: 6px;
                    padding: 2px 8px;
                    font-size: 13px;
                }
                QComboBox QAbstractItemView {
                    background: #232323;
                    color: #e0e0e0;
                    selection-background-color: #444;
                }
            """)
            
            # Populate with default values and examples from token_definitions
            token_name = token.strip("<>")
            
            if token_name == "shot_name":
                # Map shot_name to shotNumber in token definitions for consistency
                shot_token = self.token_definitions.get("shotNumber", {})
                if shot_token and "example" in shot_token:
                    example = shot_token.get("example", "0101")
                    combo.addItems([f"SHOT_{example}", "SHOT_0010", "SHOT_0020", "SHOT_0030"])
                else:
                    combo.addItems(["SHOT_0010", "SHOT_0020", "SHOT_0030"])
                    
            elif token_name == "resolution":
                res_token = self.token_definitions.get("resolution", {})
                if res_token and "regex" in res_token:
                    # Extract values from regex like "1K|2K|4K|6K|8K|19K|12K"
                    regex_values = res_token.get("regex", "")
                    if "|" in regex_values:
                        values = regex_values.split("|")
                        combo.addItems(values)
                    else:
                        combo.addItems(["2K", "4K", "HD_1080", "1920x1080", "3840x2160"])
                else:
                    combo.addItems(["2K", "4K", "HD_1080", "1920x1080", "3840x2160"])
                    
            elif token_name == "version":
                ver_token = self.token_definitions.get("version", {})
                if ver_token and "example" in ver_token:
                    example = ver_token.get("example", "v001")
                    combo.addItems([example, "v002", "v003", "v010"])
                else:
                    combo.addItems(["v001", "v002", "v003", "v010"])
            
            self.token_controls[token] = combo
            rel_path_tokens_layout.addWidget(QtWidgets.QLabel(token))
            rel_path_tokens_layout.addWidget(combo)
            combo.currentTextChanged.connect(self.update_preview)
        autofill_btn = QtWidgets.QPushButton("Auto-fill from Script")
        autofill_btn.setToolTip("Auto-fill tokens from the current Nuke script name.")
        autofill_btn.clicked.connect(self.autofill_tokens_from_script)
        rel_path_tokens_layout.addWidget(autofill_btn)
        layout.addLayout(rel_path_tokens_layout)
        # Relative path display
        rel_path_layout = QtWidgets.QHBoxLayout()
        rel_path_label = QtWidgets.QLabel("Relative Path:")
        rel_path_label.setToolTip("The relative path, with tokens replaced by your values.")
        self.rel_path_edit = QtWidgets.QLineEdit()
        self.rel_path_edit.setReadOnly(True)
        self.rel_path_edit.setToolTip("The relative path, with tokens replaced by your values.")
        rel_path_layout.addWidget(rel_path_label)
        rel_path_layout.addWidget(self.rel_path_edit)
        layout.addLayout(rel_path_layout)
        # Live preview
        preview_layout = QtWidgets.QHBoxLayout()
        preview_layout.addWidget(QtWidgets.QLabel("Resolved Path Preview:"))
        self.preview_edit = QtWidgets.QLineEdit()
        self.preview_edit.setReadOnly(True)
        self.preview_edit.setToolTip("The full resolved output path.")
        preview_layout.addWidget(self.preview_edit)
        copy_btn = QtWidgets.QPushButton("Copy")
        copy_btn.setToolTip("Copy the resolved path to clipboard.")
        copy_btn.clicked.connect(self.copy_preview_to_clipboard)
        preview_layout.addWidget(copy_btn)
        layout.addLayout(preview_layout)
        # Save/load buttons
        btn_layout = QtWidgets.QHBoxLayout()
        self.save_btn = QtWidgets.QPushButton("Save Path Template")
        self.load_btn = QtWidgets.QPushButton("Load Path Template")
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.load_btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        # Connect
        self.base_path_edit.textChanged.connect(self.update_preview)
        self.shot_struct_combo.currentTextChanged.connect(self.on_shot_struct_changed)
        self.save_btn.clicked.connect(self.save_template)
        self.load_btn.clicked.connect(self.load_template)
        
        # Populate shot structure dropdown if provided
        if not path_structures:
            # Provide a default if missing
            path_structures = {"main": "shots/<shot_name>/comp/<version>"}
            
        # Load folder structure dropdown from path_structures in rules.yaml
        self.shot_struct_combo.clear()
        folder_structures = []
        if path_structures and isinstance(path_structures, dict):
            # Skip only the exact 'version' key, not any key containing 'version'
            folder_structures = [(k, v) for k, v in path_structures.items() if k != 'version']
            
        if not folder_structures:
            folder_structures = [("main", "shots/<shot_name>/comp/<version>")]
            
        for key, value in folder_structures:
            self.shot_struct_combo.addItem(f"{key}: {value}", value)
            
        if self.shot_struct_combo.count() > 0:
            self.shot_struct_combo.setCurrentIndex(0)
            self.on_shot_struct_changed(self.shot_struct_combo.currentText())
        # If no items added, the dropdown will remain empty
    def browse_base_path(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Base Path")
        if path:
            # Normalize path separators for consistent display
            normalized_path = os.path.normpath(path)
            self.base_path_edit.setText(normalized_path)
    def update_preview(self):
        struct_template = self.shot_struct_combo.currentData() or ""
        rel_path = struct_template
        for token, combo in self.token_controls.items():
            rel_path = rel_path.replace(token, combo.currentText())
        self.rel_path_edit.setText(rel_path)
        
        # Normalize path separators to avoid mixed slash/backslash
        base = self.base_path_edit.text().rstrip("/\\")
        rel = rel_path.lstrip("/\\")
        
        if base and rel:
            resolved = os.path.join(base, rel)
        else:
            resolved = base or rel
            
        # Normalize path separators for consistent display
        resolved = os.path.normpath(resolved)
        self.preview_edit.setText(resolved)
    def on_shot_struct_changed(self, text):
        struct_template = self.shot_struct_combo.currentData() or ""
        for token in self.rel_path_tokens:
            if token in struct_template:
                self.token_controls[token].setEnabled(True)
            else:
                self.token_controls[token].setEnabled(False)
        self.update_preview()
    def autofill_tokens_from_script(self):
        # Parse tokens from current Nuke script filename
        import nuke
        import os
        script_path = nuke.root().name()
        
        if not script_path:
            return
            
        # Extract just the filename (without path and extension)
        filename = os.path.splitext(os.path.basename(script_path))[0]
        
        # Shot name: everything before the first underscore
        # Example: "KITC0010_description_comp_LL180_v011" -> "KITC0010"
        if "_" in filename:
            shot_name = filename.split("_")[0]
            if shot_name and "<shot_name>" in self.token_controls:
                self.token_controls["<shot_name>"].setCurrentText(shot_name)
        
        # Version: find vXXX pattern anywhere in filename
        # Example: "v011" -> "v011"
        import re
        version_match = re.search(r'v(\d{2,4})', filename, re.IGNORECASE)
        if version_match and "<version>" in self.token_controls:
            version = f"v{version_match.group(1).zfill(3)}"  # Ensure 3 digits: v011
            self.token_controls["<version>"].setCurrentText(version)
        
        # Resolution: find resolution pattern (e.g., 2K, 4K, HD_1080, etc.)
        # Example: "LL180", "2K", "4K", "HD_1080"
        resolution_patterns = [
            r'(\d+K)(?=_|$)',        # 2K, 4K, etc. followed by _ or end
            r'(HD_\d+)(?=_|$)',      # HD_1080, etc. followed by _ or end
            r'(\d+x\d+)(?=_|$)',     # 1920x1080, etc. followed by _ or end
            r'(LL\d+)(?=_|$)'        # LL180, LL360, etc. followed by _ or end
        ]
        
        for pattern in resolution_patterns:
            res_match = re.search(pattern, filename, re.IGNORECASE)
            if res_match and "<resolution>" in self.token_controls:
                resolution = res_match.group(1)
                # Check if this resolution exists in the dropdown
                combo = self.token_controls["<resolution>"]
                for i in range(combo.count()):
                    if combo.itemText(i).upper() == resolution.upper():
                        combo.setCurrentText(combo.itemText(i))
                        break
                break  # Stop after first match
        
        # Update the preview after auto-filling
        self.update_preview()
    def copy_preview_to_clipboard(self):
        QtWidgets.QApplication.clipboard().setText(self.preview_edit.text())
    def show_help_dialog(self):
        QtWidgets.QMessageBox.information(self, "Path Rule Editor Help",
            """
<b>Path Rule Editor Help</b><br><br>
- <b>Base Path</b>: The root directory for all output paths.<br>
- <b>Shot Structure</b>: Select a template for your project's path structure.<br>
- <b>Tokens</b>: Fill in values for each token (e.g., &lt;shot_name&gt;, &lt;resolution&gt;, &lt;version&gt;).<br>
- <b>Auto-fill from Script</b>: Attempts to fill tokens from the current Nuke script name.<br>
- <b>Copy</b>: Copies the resolved path to your clipboard.<br>
- <b>Save/Load</b>: Save or load path templates for reuse.<br><br>
The resolved path preview updates live as you edit.<br>
            """)
    def save_template(self):
        import yaml
        config = {
            "base_path": self.base_path_edit.text(),
            "shot_structure": self.shot_struct_combo.currentText(),
            "relative_path": self.rel_path_edit.text(),
            "tokens": {token: combo.currentText() for token, combo in self.token_controls.items()}
        }
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Path Template", "", "YAML Files (*.yaml);;JSON Files (*.json)")
        if path:
            with open(path, "w") as f:
                if path.endswith(".json"):
                    import json
                    json.dump(config, f, indent=2)
                else:
                    yaml.dump(config, f, sort_keys=False)
    def load_template(self):
        import yaml
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Path Template", "", "YAML Files (*.yaml);;JSON Files (*.json)")
        if path:
            with open(path, "r") as f:
                if path.endswith(".json"):
                    import json
                    config = json.load(f)
                else:
                    config = yaml.safe_load(f)
            self.base_path_edit.setText(config.get("base_path", ""))
            self.rel_path_edit.setText(config.get("relative_path", ""))
            for token, value in config.get("tokens", {}).items():
                if token in self.token_controls:
                    self.token_controls[token].setCurrentText(value)
            idx = self.shot_struct_combo.findText(config.get("shot_structure", ""))
            if idx >= 0:
                self.shot_struct_combo.setCurrentIndex(idx)
            self.update_preview()

    # Debug method removed to resolve AttributeError

class SimpleTokenWidget(QtWidgets.QWidget):
    """
    Simple token widget with horizontal layout for the new interface
    """
    def __init__(self, token_def, parent=None):
        super().__init__(parent)
        self.token_def = token_def
        
        # Main horizontal layout
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(8)
        
        # Column 1: Token label (fixed width)
        self.label = QtWidgets.QLabel(token_def["label"])
        self.label.setFixedWidth(120)
        self.label.setStyleSheet("""
            QLabel {
                color: #e0e0e0;
                font-size: 11px;
                padding: 2px 4px;
            }
        """)
        layout.addWidget(self.label)
        
        # Column 2: Control (dropdown, multiselect, spinner, etc.)
        self.control = None
        control_width = 150
        
        if token_def["control"] == "spinner":
            self.control = QtWidgets.QSpinBox()
            self.control.setMinimum(token_def["min"])
            self.control.setMaximum(token_def["max"])
            self.control.setValue(token_def["default"])
            self.control.setFixedWidth(80)
            
        elif token_def["control"] == "dropdown":
            self.control = QtWidgets.QComboBox()
            self.control.addItems(token_def["options"])
            self.control.setFixedWidth(control_width)
            
        elif token_def["control"] == "multiselect":
            self.control = SimpleMultiSelectWidget(token_def["options"])
            self.control.setFixedWidth(control_width)
            # Ensure the signal connection is set up immediately
            self.control.selectionChanged.connect(self._on_control_changed)
            
        elif token_def["control"] == "static":
            self.control = QtWidgets.QLabel("(static)")
            self.control.setFixedWidth(control_width)
            self.control.setStyleSheet("QLabel { color: #888; font-style: italic; }")
        
        if self.control:
            self.control.setStyleSheet("""
                QWidget {
                    background: #3a3a3a;
                    color: #e0e0e0;
                    border: 1px solid #555;
                    border-radius: 3px;
                    padding: 2px 4px;
                    font-size: 11px;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 16px;
                }
                QComboBox::down-arrow {
                    image: none;
                    border-left: 3px solid transparent;
                    border-right: 3px solid transparent;
                    border-top: 3px solid #e0e0e0;
                }
                QComboBox QAbstractItemView {
                    background: #3a3a3a;
                    color: #e0e0e0;
                    selection-background-color: #4a9eff;
                }
            """)
            layout.addWidget(self.control)
        else:
            layout.addWidget(QtWidgets.QLabel(""))
        
        # Column 3: Up/Down arrows
        arrows_layout = QtWidgets.QVBoxLayout()
        arrows_layout.setContentsMargins(0, 0, 0, 0)
        arrows_layout.setSpacing(1)
        
        self.up_btn = QtWidgets.QPushButton("▲")
        self.up_btn.setFixedSize(20, 12)
        self.up_btn.setStyleSheet("""
            QPushButton {
                background: #4a4a4a;
                color: #e0e0e0;
                border: 1px solid #666;
                border-radius: 2px;
                font-size: 8px;
                padding: 0px;
            }
            QPushButton:hover { background: #5a5a5a; }
            QPushButton:pressed { background: #2a2a2a; }
        """)
        
        self.down_btn = QtWidgets.QPushButton("▼")
        self.down_btn.setFixedSize(20, 12)
        self.down_btn.setStyleSheet("""
            QPushButton {
                background: #4a4a4a;
                color: #e0e0e0;
                border: 1px solid #666;
                border-radius: 2px;
                font-size: 8px;
                padding: 0px;
            }
            QPushButton:hover { background: #5a5a5a; }
            QPushButton:pressed { background: #2a2a2a; }
        """)
        
        arrows_layout.addWidget(self.up_btn)
        arrows_layout.addWidget(self.down_btn)
        layout.addLayout(arrows_layout)
        
        # Column 4: Separator dropdown
        self.separator_combo = QtWidgets.QComboBox()
        self.separator_combo.addItems(["_", ".", "-", " ", "(none)"])
        self.separator_combo.setCurrentText("_")  # Default separator
        self.separator_combo.setFixedWidth(60)
        self.separator_combo.setStyleSheet("""
            QComboBox {
                background: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 2px 4px;
                font-size: 11px;
            }
            QComboBox::drop-down {
                border: none;
                width: 16px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-top: 3px solid #e0e0e0;
            }
            QComboBox QAbstractItemView {
                background: #3a3a3a;
                color: #e0e0e0;
                selection-background-color: #4a9eff;
            }
        """)
        layout.addWidget(self.separator_combo)
        
        # Remove button
        self.remove_btn = QtWidgets.QPushButton("×")
        self.remove_btn.setFixedSize(20, 20)
        self.remove_btn.setStyleSheet("""
            QPushButton {
                background: #d32f2f;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background: #f44336; }
            QPushButton:pressed { background: #b71c1c; }
        """)
        layout.addWidget(self.remove_btn)
        
        # Connect signals
        if self.control and hasattr(self.control, 'currentTextChanged'):
            self.control.currentTextChanged.connect(self._on_control_changed)
        elif self.control and hasattr(self.control, 'valueChanged'):
            self.control.valueChanged.connect(self._on_control_changed)
        
        self.separator_combo.currentTextChanged.connect(self._on_control_changed)
        
        # Set size policy
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.setFixedHeight(30)
        
    def _on_control_changed(self):
        """Notify parent when control values change"""
        parent = self.parent()
        while parent:
            if hasattr(parent, 'update_regex'):
                parent.update_regex()
                break
            parent = parent.parent()
    
    def get_token_config(self):
        """Return the token configuration"""
        value = None
        if self.control:
            try:
                if isinstance(self.control, QtWidgets.QSpinBox):
                    value = self.control.value()
                elif isinstance(self.control, QtWidgets.QComboBox):
                    value = self.control.currentText()
                elif isinstance(self.control, SimpleMultiSelectWidget):
                    value = self.control.get_selected_values()
                    print(f"MULTISELECT SAVE DEBUG: Token {self.token_def['name']}")
                    print(f"  Saving value: {value} (type: {type(value)})")
                    print("---")
            except RuntimeError:
                value = None
        
        # Get separator
        separator = self.separator_combo.currentText()
        if separator == "(none)":
            separator = ""
            
        return {
            "name": self.token_def["name"], 
            "value": value,
            "separator": separator
        }

class ValidationResultsTable(QtWidgets.QTableWidget):
    """
    Excel-like table for displaying validation results with resizable columns.
    
    This specialized table widget provides a standardized interface for presenting
    validation results from the Nuke Validator. It handles different result types
    (success, warning, error) with appropriate styling and provides interactive
    elements like "Go to Node" buttons for navigation.
    
    Features:
        - Status icons with color coding for success/warning/error states
        - Resizable columns with optimal default sizes
        - Support for "Go to Node" action buttons
        - Consistent Nuke-themed styling
        - Row background highlighting based on result severity
    
    Methods:
        add_validation_result: Add a new validation result row to the table
        clear_results: Remove all results from the table
        get_selected_rule: Retrieve the currently selected rule name
    """
    def __init__(self, parent=None, available_tokens=None):
        super().__init__(parent)
        
        # Set up table structure
        self.setColumnCount(4)
        self.setHorizontalHeaderLabels(["Status", "Rule", "Details", "Action"])
        
        # Configure table behavior
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(False)
        self.setWordWrap(True)
        
        # Configure headers
        header = self.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)  # Status icon - fixed
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)  # Rule - auto-size
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)  # Details - takes remaining space
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Fixed)  # Action button - fixed
        
        # Set column widths
        self.setColumnWidth(0, 40)   # Status icon
        self.setColumnWidth(1, 150)  # Rule name
        self.setColumnWidth(3, 100)  # Action button
        
        # Vertical header
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(28)  # Row height
        
        # Apply Nuke dark theme styling
        self.setStyleSheet("""
            QTableWidget {
                background-color: #393939;
                alternate-background-color: #333333;
                color: #e0e0e0;
                gridline-color: #555555;
                border: 1px solid #555555;
                selection-background-color: #4a4a4a;
                font-size: 11px;
            }
            
            QTableWidget::item {
                border: none;
                padding: 4px 6px;
                background: transparent;
            }
            
            QTableWidget::item:selected {
                background-color: #4a4a4a;
                color: #ffffff;
            }
            
            QHeaderView::section {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-left: none;
                border-right: 1px solid #555555;
                border-top: none;
                border-bottom: 1px solid #555555;
                padding: 4px 8px;
                font-weight: bold;
                font-size: 11px;
            }
            
            QHeaderView::section:first {
                border-left: 1px solid #555555;
            }
            
            QScrollBar:vertical {
                background: #2a2a2a;
                border: 1px solid #555555;
                width: 16px;
            }
            
            QScrollBar::handle:vertical {
                background: #4a4a4a;
                border: 1px solid #666666;
                border-radius: 3px;
                min-height: 20px;
            }
            
            QScrollBar::handle:vertical:hover {
                background: #5a5a5a;
            }
            
            QScrollBar:horizontal {
                background: #2a2a2a;
                border: 1px solid #555555;
                height: 16px;
            }
            
            QScrollBar::handle:horizontal {
                background: #4a4a4a;
                border: 1px solid #666666;
                border-radius: 3px;
                min-width: 20px;
            }
            
            QScrollBar::handle:horizontal:hover {
                background: #5a5a5a;
            }
        """)
    
    def add_validation_result(self, rule_name, status, details, node_name=None):
        """
        Add a validation result row to the table
        
        Args:
            rule_name (str): Name of the validation rule
            status (str): 'success', 'warning', 'error', 'running', 'pending'
            details (str): Detailed explanation of the result
            node_name (str): Optional node name for "Go to Node" button
        """
        row = self.rowCount()
        self.insertRow(row)
        
        # Column 0: Status icon
        status_widget = self._create_status_widget(status)
        self.setCellWidget(row, 0, status_widget)
        
        # Column 1: Rule name
        rule_item = QtWidgets.QTableWidgetItem(rule_name)
        rule_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable)
        rule_item.setToolTip(rule_name)
        self.setItem(row, 1, rule_item)
        
        # Column 2: Details with word wrapping - explicitly make text selectable and copyable
        details_item = QtWidgets.QTableWidgetItem(details)
        details_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsEditable)
        details_item.setToolTip("Double-click to select/copy this text: " + details)
        self.setItem(row, 2, details_item)
        
        # Column 3: Action button (if node_name provided)
        if node_name:
            action_widget = self._create_action_button(node_name)
            self.setCellWidget(row, 3, action_widget)
        else:
            # Empty cell for non-node validations
            empty_item = QtWidgets.QTableWidgetItem("")
            empty_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
            self.setItem(row, 3, empty_item)
        
        # Set row border color based on status
        self._set_row_border_color(row, status)
        
        # Auto-resize row height to fit content
        self.resizeRowToContents(row)
    
    def _create_status_widget(self, status):
        """Create status icon widget"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        icon_label = QtWidgets.QLabel()
        icon_label.setFixedSize(20, 20)
        icon_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        # Create status icon
        self._set_status_icon(icon_label, status)
        
        layout.addWidget(icon_label)
        widget.setStyleSheet("QWidget { background: transparent; }")
        return widget
    
    def _set_status_icon(self, label, status):
        """Set status icon on label"""
        # Try to load PNG icons first
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icons_dir = os.path.join(script_dir, "icons")
        
        icon_files = {
            'success': 'success.png',
            'warning': 'warning.png', 
            'error': 'error.png',
            'running': 'info.png',
            'pending': 'info.png'
        }
        
        icon_file = icon_files.get(status, 'info.png')
        icon_path = os.path.join(icons_dir, icon_file)
        
        if os.path.exists(icon_path):
            pixmap = QtGui.QPixmap(icon_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                label.setPixmap(scaled_pixmap)
                return
        
        # Fallback to colored circles
        colors = {
            'success': QtGui.QColor(76, 175, 80),
            'warning': QtGui.QColor(255, 152, 0),
            'error': QtGui.QColor(244, 67, 54),
            'running': QtGui.QColor(33, 150, 243),
            'pending': QtGui.QColor(120, 120, 120)
        }
        
        color = colors.get(status, colors['pending'])
        pixmap = QtGui.QPixmap(20, 20)
        pixmap.fill(QtCore.Qt.GlobalColor.transparent)
        
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        painter.setBrush(QtGui.QBrush(color))
        painter.setPen(QtCore.Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 16, 16)
        painter.end()
        
        label.setPixmap(pixmap)
    
    def _create_action_button(self, node_name):
        """Create 'Go to Node' button with Nuke styling"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        button = QtWidgets.QPushButton("Go to Node")
        button.setFixedSize(80, 20)
        button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #4a4a4a, stop:1 #3a3a3a);
                color: #e0e0e0;
                border: 1px solid #666666;
                border-radius: 3px;
                font-size: 9px;
                font-weight: normal;
                padding: 2px 4px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #5a5a5a, stop:1 #4a4a4a);
                border: 1px solid #777777;
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3a3a3a, stop:1 #2a2a2a);
                border: 1px solid #555555;
            }
        """)
        
        # Connect button click to select node
        button.clicked.connect(lambda: self._go_to_node(node_name))
        button.setToolTip(f"Select and focus on {node_name}")
        
        layout.addWidget(button)
        widget.setStyleSheet("QWidget { background: transparent; }")
        return widget
    
    def _go_to_node(self, node_name):
        """Navigate to the specified node in Nuke"""
        try:
            import nuke
            node = nuke.toNode(node_name)
            if node:
                # Select the node
                nuke.selectAll()
                nuke.invertSelection()
                node.setSelected(True)
                
                # Center the node in the Node Graph
                nuke.zoom(1, [node.xpos(), node.ypos()])
                
                # Open the node's properties panel
                nuke.show(node)
                
                print(f"Navigated to node: {node_name}")
            else:
                print(f"Node not found: {node_name}")
        except Exception as e:
            print(f"Error navigating to node {node_name}: {e}")
    
    def _set_row_border_color(self, row, status):
        """Set colored border for the entire row based on status"""
        border_colors = {
            'success': '#4caf50',
            'warning': '#ff9800', 
            'error': '#f44336',
            'running': '#2196f3',
            'pending': '#757575'
        }
        
        border_color = border_colors.get(status, border_colors['pending'])
        
        # Apply border styling to each cell in the row
        for col in range(self.columnCount()):
            item = self.item(row, col)
            if item:
                item.setData(QtCore.Qt.ItemDataRole.BackgroundRole, QtGui.QColor(border_color + "20"))  # Very transparent background
    
    def clear_results(self):
        """Clear all validation results"""
        self.setRowCount(0)
    
    def get_selected_rule(self):
        """Get the rule name of the currently selected row"""
        current_row = self.currentRow()
        if current_row >= 0:
            rule_item = self.item(current_row, 1)
            if rule_item:
                return rule_item.text()
        return None


class RuleItemWidget(QtWidgets.QWidget):
    """
    DEPRECATED: Legacy widget - use ValidationResultsTable instead
    Kept for backward compatibility during transition
    """
    def __init__(self, rule_name, parent=None):
        super(RuleItemWidget, self).__init__(parent)
        self.rule_name = rule_name
        
        # Simple layout for legacy support
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        
        # Just show the rule name
        self.name_label = QtWidgets.QLabel(rule_name)
        self.name_label.setStyleSheet("QLabel { color: #e0e0e0; }")
        layout.addWidget(self.name_label)
        
        # Status label
        self.status_label = QtWidgets.QLabel("Legacy widget - use ValidationResultsTable")
        self.status_label.setStyleSheet("QLabel { color: #ff9800; font-style: italic; }")
        layout.addWidget(self.status_label)
    
    def set_status(self, status):
        """Legacy method"""
        pass

class TableBasedFilenameTemplateBuilder(QtWidgets.QWidget):
    """
    Advanced table-based UI for building filename templates with rich token configuration.
    
    This widget provides an Excel-like table interface for constructing filename templates,
    with each filename token represented as a configurable row in the table. The widget
    allows users to add, remove, configure, and reorder tokens to build complex filename
    validation patterns.
    
    Features:
        - Add tokens via drag-and-drop or button clicks
        - Configure token parameters through appropriate input widgets
        - Define separators between tokens (e.g., underscore, period, hyphen)
        - Reorder tokens using up/down controls
        - Remove tokens with one-click deletion
        - Real-time template visualization
    
    This class is the primary template builder used throughout the validation system
    and serves as a replacement for older template builder implementations.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(4)
        
        # Header
        header_label = QtWidgets.QLabel("Template Order:")
        header_label.setStyleSheet("QLabel { color: #e0e0e0; font-weight: bold; font-size: 11px; }")
        main_layout.addWidget(header_label)
        
        # Create table
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Token", "Value/Control", "Separator", "Order", "Remove"])
        
        # Configure table behavior
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(False)
        self.table.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.InternalMove)
        self.table.setDefaultDropAction(QtCore.Qt.DropAction.MoveAction)
        
        # Configure headers
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)      # Token name - fixed
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)    # Control - takes space
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Fixed)      # Separator - fixed
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Fixed)      # Order buttons - fixed
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Fixed)      # Remove button - fixed
        
        # Set a larger width for column 1 (Value/Control) to prevent text cutoff
        self.table.setColumnWidth(1, 200)
        
        # Set column widths with more space
        self.table.setColumnWidth(0, 140)   # Token name - wider for better readability
        self.table.setColumnWidth(2, 90)    # Separator - wider to avoid cropping
        self.table.setColumnWidth(3, 70)    # Order buttons - wider for better visibility
        self.table.setColumnWidth(4, 70)    # Remove button - wider for better visibility
        
        # Vertical header
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(32)  # Row height
        
        # Set table height to be more flexible while still having reasonable bounds
        self.table.setMinimumHeight(150)  # Smaller minimum height to fit in scroll area
        self.table.setMaximumHeight(600)  # Larger maximum height for more flexibility
        
        # Apply dark theme styling
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #393939;
                alternate-background-color: #333333;
                color: #e0e0e0;
                gridline-color: #555555;
                border: 1px solid #555555;
                selection-background-color: #4a4a4a;
                font-size: 11px;
            }
            
            QTableWidget::item {
                border: none;
                padding: 4px 6px;
                background: transparent;
            }
            
            QTableWidget::item:selected {
                background-color: #4a4a4a;
                color: #ffffff;
            }
            
            QHeaderView::section {
                background-color: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #555555;
                border-left: none;
                border-right: 1px solid #555555;
                border-top: none;
                border-bottom: 1px solid #555555;
                padding: 4px 8px;
                font-weight: bold;
                font-size: 10px;
            }
            
            QHeaderView::section:first {
                border-left: 1px solid #555555;
            }
        """)
        
        main_layout.addWidget(self.table)
        
        # Track token configurations for easy access
        self.token_configs = []
        
        self.setStyleSheet("""
            TableBasedFilenameTemplateBuilder {
                background: #2a2a2a;
                border: 1px solid #555;
                border-radius: 4px;
            }
        """)
        
    def add_token(self, token_def):
        """Add a token as a new row in the table"""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # Store token definition
        token_config = {
            "name": token_def["name"],
            "token_def": token_def,
            "value": None,
            "separator": "_"
        }
        self.token_configs.append(token_config)
        
        # Column 0: Token name (read-only)
        token_item = QtWidgets.QTableWidgetItem(token_def["label"])
        token_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable)
        token_item.setToolTip(token_def["desc"])
        self.table.setItem(row, 0, token_item)
        
        # Column 1: Control widget (editable)
        control_widget = self._create_control_widget(token_def, row)
        self.table.setCellWidget(row, 1, control_widget)
        
        # Column 2: Separator dropdown
        separator_widget = self._create_separator_widget(row)
        self.table.setCellWidget(row, 2, separator_widget)
        
        # Column 3: Order buttons (up/down)
        order_widget = self._create_order_widget(row)
        self.table.setCellWidget(row, 3, order_widget)
        
        # Column 4: Remove button
        remove_widget = self._create_remove_widget(row)
        self.table.setCellWidget(row, 4, remove_widget)
        
        self._update_order_buttons()
        self._notify_change()
        
    def _create_control_widget(self, token_def, row):
        """Create the appropriate control widget for the token"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        
        control = None
        
        if token_def["control"] == "range_spinner":
            # Range spinner with min/max controls
            container = QtWidgets.QWidget()
            hlayout = QtWidgets.QHBoxLayout(container)
            hlayout.setContentsMargins(0, 0, 0, 0)
            hlayout.setSpacing(4)
            
            min_spinner = QtWidgets.QSpinBox()
            min_spinner.setMinimum(token_def["min"])
            min_spinner.setMaximum(token_def["max"])
            min_spinner.setValue(token_def.get("default_min", token_def["min"]))
            min_spinner.setFixedWidth(40)
            
            max_spinner = QtWidgets.QSpinBox()
            max_spinner.setMinimum(token_def["min"])
            max_spinner.setMaximum(token_def["max"])
            max_spinner.setValue(token_def.get("default_max", token_def["max"]))
            max_spinner.setFixedWidth(40)
            
            hlayout.addWidget(QtWidgets.QLabel("Min:"))
            hlayout.addWidget(min_spinner)
            hlayout.addWidget(QtWidgets.QLabel("Max:"))
            hlayout.addWidget(max_spinner)
            
            # Connect signals to update values and ensure min ≤ max
            def update_min(value):
                if value > max_spinner.value():
                    max_spinner.setValue(value)
                self._update_range_token_value(row, value, max_spinner.value())
                
            def update_max(value):
                if value < min_spinner.value():
                    min_spinner.setValue(value)
                self._update_range_token_value(row, min_spinner.value(), value)
                
            min_spinner.valueChanged.connect(update_min)
            max_spinner.valueChanged.connect(update_max)
            
            control = container
            
        elif token_def["control"] == "spinner":
            control = QtWidgets.QSpinBox()
            control.setMinimum(token_def["min"])
            control.setMaximum(token_def["max"])
            control.setValue(token_def["default"])
            control.setFixedWidth(80)
            control.valueChanged.connect(lambda v: self._update_token_value(row, v))
            
        elif token_def["control"] == "dropdown":
            control = QtWidgets.QComboBox()
            control.addItems(token_def["options"])
            # Increased width to prevent text cutoff
            control.setMinimumWidth(180)
            # Use size hint to ensure text fits
            control.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToContents)
            control.setMaxVisibleItems(10)
            control.currentTextChanged.connect(lambda t: self._update_token_value(row, t))
            
        elif token_def["control"] == "multiselect":
            control = SimpleMultiSelectWidget(token_def["options"])
            # Increased width to prevent text cutoff
            control.setMinimumWidth(180)
            control.selectionChanged.connect(lambda: self._update_token_value(row, control.get_selected_values()))
            
        elif token_def["control"] == "static":
            control = QtWidgets.QLabel("(automatic)")
            control.setStyleSheet("QLabel { color: #888; font-style: italic; }")
        
        if control:
            control.setStyleSheet("""
                QWidget {
                    background: #3a3a3a;
                    color: #e0e0e0;
                    border: 1px solid #555;
                    border-radius: 3px;
                    font-size: 10px;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 20px; /* Wider dropdown button */
                }
                QComboBox::down-arrow {
                    border-left: 4px solid transparent;
                    border-right: 4px solid transparent;
                    border-top: 4px solid #e0e0e0;
                }
                QComboBox {
                    padding-left: 6px;
                    padding-right: 20px; /* More padding for text */
                    text-align: left;
                }
                QComboBox QAbstractItemView {
                    background: #3a3a3a;
                    color: #e0e0e0;
                    selection-background-color: #4a9eff;
                    padding: 4px;
                }
                QComboBox:!editable {
                    background: #3a3a3a;
                }
            """)
            layout.addWidget(control)
        
        layout.addStretch()
        widget.setStyleSheet("QWidget { background: transparent; }")
        return widget
    
    def _create_separator_widget(self, row):
        """Create separator dropdown widget"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        separator_combo = QtWidgets.QComboBox()
        separator_combo.addItems(["_", ".", "-", " ", "(none)"])
        separator_combo.setCurrentText("_")
        separator_combo.setFixedWidth(70)
        separator_combo.setStyleSheet("""
            QComboBox {
                background: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 3px;
                font-size: 10px;
            }
            QComboBox::drop-down {
                border: none;
                width: 16px;
            }
            QComboBox::down-arrow {
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-top: 3px solid #e0e0e0;
            }
            QComboBox QAbstractItemView {
                background: #3a3a3a;
                color: #e0e0e0;
                selection-background-color: #4a9eff;
            }
        """)
        
        separator_combo.currentTextChanged.connect(lambda t: self._update_token_separator(row, t))
        layout.addWidget(separator_combo)
        
        widget.setStyleSheet("QWidget { background: transparent; }")
        return widget
    
    def _create_order_widget(self, row):
        """Create up/down movement buttons"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(1)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        up_btn = QtWidgets.QPushButton("▲")
        up_btn.setFixedSize(20, 12)
        up_btn.clicked.connect(lambda: self._move_token_up(row))
        
        down_btn = QtWidgets.QPushButton("▼")
        down_btn.setFixedSize(20, 12)
        down_btn.clicked.connect(lambda: self._move_token_down(row))
        
        for btn in [up_btn, down_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background: #4a4a4a;
                    color: #e0e0e0;
                    border: 1px solid #666;
                    border-radius: 2px;
                    font-size: 8px;
                    padding: 0px;
                }
                QPushButton:hover { background: #5a5a5a; }
                QPushButton:pressed { background: #2a2a2a; }
                QPushButton:disabled { background: #2a2a2a; color: #666; }
            """)
        
        layout.addWidget(up_btn)
        layout.addWidget(down_btn)
        
        widget.setStyleSheet("QWidget { background: transparent; }")
        return widget
    
    def _create_remove_widget(self, row):
        """Create remove button"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        
        remove_btn = QtWidgets.QPushButton("×")
        remove_btn.setFixedSize(20, 20)
        remove_btn.clicked.connect(lambda: self._remove_token(row))
        remove_btn.setStyleSheet("""
            QPushButton {
                background: #d32f2f;
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover { background: #f44336; }
            QPushButton:pressed { background: #b71c1c; }
        """)
        
        layout.addWidget(remove_btn)
        widget.setStyleSheet("QWidget { background: transparent; }")
        return widget
    
    def _update_token_value(self, row, value):
        """Update the token value in the config"""
        if 0 <= row < len(self.token_configs):
            self.token_configs[row]["value"] = value
            self._notify_change()
            
    def _update_range_token_value(self, row, min_value, max_value):
        """Update min and max values for range spinner tokens"""
        if 0 <= row < len(self.token_configs):
            self.token_configs[row]["min_value"] = min_value
            self.token_configs[row]["max_value"] = max_value
            self._notify_change()
    
    def _update_token_separator(self, row, separator):
        """Update the separator for a token at the given row"""
        if 0 <= row < len(self.token_configs):
            if separator == "(none)":
                separator = ""
            self.token_configs[row]["separator"] = separator
            self._notify_change()
    
    def _move_token_up(self, row):
        """Move token up in the order"""
        if row > 0 and row < len(self.token_configs):
            # Swap configurations
            self.token_configs[row], self.token_configs[row-1] = self.token_configs[row-1], self.token_configs[row]
            self._rebuild_table()
    
    def _move_token_down(self, row):
        """Move token down in the order"""
        if row >= 0 and row < len(self.token_configs) - 1:
            # Swap configurations
            self.token_configs[row], self.token_configs[row+1] = self.token_configs[row+1], self.token_configs[row]
            self._rebuild_table()
    
    def _remove_token(self, row):
        """Remove token at the given row"""
        if 0 <= row < len(self.token_configs):
            self.token_configs.pop(row)
            self._rebuild_table()
    
    def _rebuild_table(self):
        """Rebuild the entire table from token_configs"""
        self.table.setRowCount(0)
        
        for i, config in enumerate(self.token_configs):
            self.table.insertRow(i)
            token_def = config["token_def"]
            
            # Column 0: Token name
            token_item = QtWidgets.QTableWidgetItem(token_def["label"])
            token_item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable)
            token_item.setToolTip(token_def["desc"])
            self.table.setItem(i, 0, token_item)
            
            # Column 1: Control widget
            control_widget = self._create_control_widget(token_def, i)
            self.table.setCellWidget(i, 1, control_widget)
            
            # Set the control value from config
            self._restore_control_value(i, config)
            
            # Column 2: Separator dropdown
            separator_widget = self._create_separator_widget(i)
            self.table.setCellWidget(i, 2, separator_widget)
            
            # Set separator value
            separator_combo = separator_widget.findChild(QtWidgets.QComboBox)
            if separator_combo:
                sep_text = config["separator"] if config["separator"] else "(none)"
                idx = separator_combo.findText(sep_text)
                if idx >= 0:
                    separator_combo.setCurrentIndex(idx)
                else:
                    # If the exact separator isn't found, default to "_"
                    default_idx = separator_combo.findText("_")
                    if default_idx >= 0:
                        separator_combo.setCurrentIndex(default_idx)
            
            # Column 3: Order buttons
            order_widget = self._create_order_widget(i)
            self.table.setCellWidget(i, 3, order_widget)
            
            # Column 4: Remove button
            remove_widget = self._create_remove_widget(i)
            self.table.setCellWidget(i, 4, remove_widget)
        
        self._update_order_buttons()
        self._notify_change()
    
    def _restore_control_value(self, row, config):
        """Restore the control value from configuration"""
        control_widget = self.table.cellWidget(row, 1)
        if not control_widget:
            return
            
        # Find the actual control within the widget
        for child in control_widget.findChildren(QtWidgets.QWidget):
            if isinstance(child, QtWidgets.QSpinBox) and config["value"] is not None:
                try:
                    child.setValue(int(config["value"]))
                except (ValueError, TypeError):
                    pass
                break
            elif isinstance(child, QtWidgets.QComboBox) and config["value"] is not None:
                idx = child.findText(str(config["value"]))
                if idx >= 0:
                    child.setCurrentIndex(idx)
                break
            elif isinstance(child, SimpleMultiSelectWidget) and config["value"] is not None:
                if isinstance(config["value"], list):
                    child.set_selected_values(config["value"])
                break
    
    def _update_order_buttons(self):
        """Update enabled state of order buttons"""
        for row in range(self.table.rowCount()):
            order_widget = self.table.cellWidget(row, 3)
            if order_widget:
                buttons = order_widget.findChildren(QtWidgets.QPushButton)
                if len(buttons) >= 2:
                    up_btn, down_btn = buttons[0], buttons[1]
                    up_btn.setEnabled(row > 0)
                    down_btn.setEnabled(row < self.table.rowCount() - 1)
    
    def _notify_change(self):
        """Notify parent of changes"""
        parent = self.parent()
        while parent:
            if hasattr(parent, 'update_regex'):
                parent.update_regex()
                break
            parent = parent.parent()
    
        # Removed duplicate method
        result = []
        for config in self.token_configs:
            result.append({
                "name": config["name"],
                "value": config["value"],
                "separator": config["separator"]
            })
        return result
    
    def clear(self):
        """Clear all tokens"""
        self.table.setRowCount(0)
        self.token_configs = []
        self._notify_change()
        # Ensure table is properly reset
        self.table.viewport().update()
        
    def get_template_config(self):
        """Return the current template configuration.
        
        Returns:
            list: List of token configurations with name, value, and separator.
        """
        return self.token_configs

# ... existing code ...

class FilenameRuleEditor(QtWidgets.QWidget):
    """
    Main widget for the filename rule editor with integrated validation capabilities.
    
    This widget provides the complete UI for creating, configuring, and testing filename
    validation rules. It combines multiple components including a token palette,
    template builder, and regex preview for visualizing the validation pattern.
    
    Features:
        - Token palette with drag-and-drop support for building templates
        - Visual template builder for arranging filename components
        - Real-time regex generation and visualization
        - Test area for validating sample filenames
        - Detailed validation error reporting
        - Save/load capability for template configurations
    
    This class serves as the primary interface for the filename validation system
    and is used by both the UI module and the backend validator.
    """
    def __init__(self, parent=None, available_tokens=None):
        super().__init__(parent)
        self.available_tokens = available_tokens if available_tokens is not None else []

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Token palette (simple horizontal layout)
        palette_widget = QtWidgets.QWidget()
        palette_layout = QtWidgets.QVBoxLayout(palette_widget)
        palette_layout.setContentsMargins(0, 0, 0, 0)
        palette_layout.setSpacing(4)
        
        # Header
        header_label = QtWidgets.QLabel("Available Tokens (from YAML):")
        header_label.setStyleSheet("QLabel { color: #e0e0e0; font-weight: bold; font-size: 11px; }")
        palette_layout.addWidget(header_label)
        
        # Create scroll area for token buttons
        token_scroll_area = QtWidgets.QScrollArea()
        token_scroll_area.setWidgetResizable(True)
        token_scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        token_scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        token_scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #2a2a2a;
                width: 12px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #666666;
                min-height: 20px;
                border-radius: 6px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        
        # Container widget for token buttons
        token_container = QtWidgets.QWidget()
        button_layout = QtWidgets.QGridLayout(token_container)
        button_layout.setSpacing(4)
        
        self.token_buttons = []
        max_cols = 4  # Fewer columns to allow larger buttons
        
        if not self.available_tokens:
            no_tokens_label = QtWidgets.QLabel("No tokens available from the master FILENAME_TOKENS list.")
            no_tokens_label.setStyleSheet("QLabel { color: #ffcc00; font-style: italic; }") # Warning color
            button_layout.addWidget(no_tokens_label, 0, 0, 1, max_cols) # Span across columns

        for i, token_def in enumerate(self.available_tokens):
            row = i // max_cols
            col = i % max_cols
            
            btn = QtWidgets.QPushButton(token_def["label"])
            btn.setToolTip(token_def["desc"])
            btn.setFixedSize(90, 24)  # Larger, more readable buttons
            btn.setStyleSheet("""
                QPushButton {
                    background: #4a4a4a;
                    color: #e0e0e0;
                    border: 1px solid #666;
                    border-radius: 3px;
                    font-size: 10px;
                    padding: 2px 4px;
                }
                QPushButton:hover { 
                    background: #5a5a5a; 
                    border: 1px solid #777;
                }
                QPushButton:pressed { 
                    background: #3a3a3a; 
                    border: 1px solid #555;
                }
            """)
            btn.clicked.connect(functools.partial(self.add_token_to_template, token_def))
            button_layout.addWidget(btn, row, col)
            self.token_buttons.append(btn)
        
        # Set token container in scroll area
        token_scroll_area.setWidget(token_container)
        palette_layout.addWidget(token_scroll_area)
        
        # Set a reasonable fixed height for the token palette
        palette_widget.setMinimumHeight(120)
        palette_widget.setMaximumHeight(150)
        layout.addWidget(palette_widget)
        
        # Template builder wrapped in scroll area
        template_scroll_area = QtWidgets.QScrollArea()
        template_scroll_area.setWidgetResizable(True)
        template_scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        template_scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        template_scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: 1px solid #555;
                border-radius: 4px;
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                background: #2a2a2a;
                width: 12px;
                height: 12px;
                margin: 0px;
            }
            QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
                background: #666666;
                min-height: 20px;
                min-width: 20px;
                border-radius: 6px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                height: 0px;
                width: 0px;
            }
        """)
        
        # Create template builder
        self.template_builder = TableBasedFilenameTemplateBuilder()
        template_scroll_area.setWidget(self.template_builder)
        layout.addWidget(template_scroll_area)
        
        # Regex preview section
        regex_group = QtWidgets.QGroupBox("Generated Pattern")
        regex_group.setStyleSheet("""
            QGroupBox {
                color: #e0e0e0;
                font-weight: bold;
                font-size: 11px;
                border: 1px solid #555;
                border-radius: 3px;
                margin-top: 8px;
                padding-top: 4px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px 0 4px;
            }
        """)
        regex_layout = QtWidgets.QVBoxLayout(regex_group)
        regex_layout.setContentsMargins(8, 8, 8, 8)
        regex_layout.setSpacing(4)
        
        # Regex preview row
        regex_row_layout = QtWidgets.QHBoxLayout()
        regex_row_layout.addWidget(QtWidgets.QLabel("Regex:"))
        
        self.regex_edit = QtWidgets.QLineEdit()
        self.regex_edit.setReadOnly(False)
        self.regex_edit.setStyleSheet("""
            QLineEdit {
                background: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 4px;
                font-size: 10px;
                font-family: monospace;
            }
        """)
        regex_row_layout.addWidget(self.regex_edit)
        
        self.regex_status_icon = QtWidgets.QLabel()
        self.regex_status_icon.setFixedSize(16, 16)
        regex_row_layout.addWidget(self.regex_status_icon)
        
        regex_layout.addLayout(regex_row_layout)
        
        # Example filename row
        example_row_layout = QtWidgets.QHBoxLayout()
        example_row_layout.addWidget(QtWidgets.QLabel("Example:"))
        
        self.example_edit = QtWidgets.QLineEdit()
        self.example_edit.setReadOnly(True)
        self.example_edit.setStyleSheet("""
            QLineEdit {
                background: #2a2a2a;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 3px;
                padding: 4px;
                font-size: 10px;
                font-family: monospace;
            }
        """)
        example_row_layout.addWidget(self.example_edit)
        
        regex_layout.addLayout(example_row_layout)
        
        layout.addWidget(regex_group, 0)  # Fixed size
        
        # Save/load buttons
        btn_layout = QtWidgets.QHBoxLayout()
        
        self.save_btn = QtWidgets.QPushButton("Save Template")
        self.save_btn.setFixedHeight(24)
        self.save_btn.setStyleSheet("""
            QPushButton {
                background: #4a4a4a;
                color: #e0e0e0;
                border: 1px solid #666;
                border-radius: 3px;
                font-size: 10px;
                padding: 4px 12px;
            }
            QPushButton:hover { background: #5a5a5a; }
            QPushButton:pressed { background: #3a3a3a; }
        """)
        
        self.load_btn = QtWidgets.QPushButton("Load Template")
        self.load_btn.setFixedHeight(24)
        self.load_btn.setStyleSheet("""
            QPushButton {
                background: #4a4a4a;
                color: #e0e0e0;
                border: 1px solid #666;
                border-radius: 3px;
                font-size: 10px;
                padding: 4px 12px;
            }
            QPushButton:hover { background: #5a5a5a; }
            QPushButton:pressed { background: #3a3a3a; }
        """)
        
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.load_btn)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        
        # Create a separate panel for the Clear All button
        clear_panel = QtWidgets.QWidget()
        clear_panel.setStyleSheet("""
            QWidget {
                background: #333333;
                border: 1px solid #555;
                border-radius: 3px;
            }
        """)
        clear_layout = QtWidgets.QHBoxLayout(clear_panel)
        clear_layout.setContentsMargins(6, 6, 6, 6)
        
        # Create a prominent Clear All button
        clear_btn = QtWidgets.QPushButton("Clear All")
        clear_btn.setFixedHeight(26)
        clear_btn.clicked.connect(self.clear_and_update)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: #444;
                color: #e0e0e0;
                border: 1px solid #666;
                border-radius: 3px;
                padding: 4px 12px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { background: #555; }
            QPushButton:pressed { background: #333; }
        """)
        clear_layout.addWidget(clear_btn)
        clear_layout.addStretch()
        
        # Add spacing before the clear button panel
        layout.addSpacing(8)
        layout.addWidget(clear_panel)
        
        # Add stretch at the end to push everything up
        layout.addStretch(1)
        
        # Connect signals
        self.save_btn.clicked.connect(self.save_template)
        self.load_btn.clicked.connect(self.load_template)
        self.regex_edit.textChanged.connect(self._on_regex_edit)
        
        # Initial update
        self.update_regex()

    def add_token_to_template(self, token_def):
        """Add a token to the template builder"""
        self.template_builder.add_token(token_def)
        self.update_regex()

    def clear_and_update(self):
        """Clear the template and update the display"""
        self.template_builder.clear()
        self.regex_edit.clear()
        self.example_edit.clear()

    def update_regex(self):
        """Update the regex pattern based on the current template configuration.
        
        This method generates both regex patterns and example filenames based on the
        current token configuration in the template builder. It handles different
        token types with specialized logic:
        
        - range_spinner: Uses min/max values to generate appropriate quantifiers
        - spinner: Handles numeric values for fixed-length patterns
        - dropdown: Creates patterns for single selected values
        - multiselect: Creates alternation patterns (value1|value2) for selected values only
        - static: Uses predefined regex templates
        
        For multiselect tokens, only the values explicitly selected by the user are 
        included in the regex pattern as alternatives. If no values are selected,
        it falls back to the default regex template.
        """
        # import re # Already imported globally at the top of the file

        template_config = self.template_builder.get_template_config()
        regex_parts = ["^"]  # Start of regex
        example_parts = []

        for i, token_cfg in enumerate(template_config):
            token_name = token_cfg.get("name")
            # Ensure separator is a string, default to empty if not found or None
            separator = str(token_cfg.get("separator", ""))

            if not token_name:
                continue

            token_def = token_cfg.get("token_def") # Use the token_def stored in the template config
            if not token_def:
                print(f"Warning: Token definition not found in token_cfg for {token_name} during regex update.")
                continue

            # Get pattern and example for this token
            # Pass the full token_cfg which includes user's value/min_value/max_value
            # Special handling for description token to ensure it always uses the correct pattern
            if token_name == "description":
                # Force the token_def to use the correct regex_template
                token_def_copy = token_def.copy() if token_def else {}
                token_def_copy["regex_template"] = ".+?"
                pattern_part, example_part = self._get_token_pattern_and_example(token_def_copy, token_cfg)
            else:
                pattern_part, example_part = self._get_token_pattern_and_example(token_def, token_cfg)

            if pattern_part:  # Skip if token is optional and not present
                regex_parts.append(pattern_part)
                example_parts.append(example_part)

                # Determine if a separator should be added
                add_separator_flag = False
                # Add separator if it's defined, not the last token in the visual template,
                # and there's at least one subsequent token that will actually produce a regex pattern.
                if separator and i < len(template_config) - 1:
                    # Special handling for version and frame_padding tokens
                    if token_name == "version" and i < len(template_config) - 1:
                        next_token_cfg = template_config[i + 1]
                        next_token_name = next_token_cfg.get("name")
                        # If the next token is frame_padding, use its separator (.) instead of version's separator (_)
                        if next_token_name == "frame_padding":
                            separator = next_token_cfg.get("separator", ".")
                    
                    # Check if any subsequent token will produce a pattern
                    for next_token_idx in range(i + 1, len(template_config)):
                        next_token_cfg = template_config[next_token_idx]
                        next_token_name = next_token_cfg.get("name")
                        if not next_token_name:
                            continue
                        
                        # Use the token_def from the template config if available
                        next_token_def = next_token_cfg.get("token_def")
                        if not next_token_def:
                            # Fallback to FILENAME_TOKENS if not in template config
                            next_token_def = next((t for t in FILENAME_TOKENS if t["name"] == next_token_name), None)
                        
                        if next_token_def:
                            # Check if this next token would actually contribute to the regex
                            next_pattern_part, _ = self._get_token_pattern_and_example(next_token_def, next_token_cfg)
                            if next_pattern_part:
                                add_separator_flag = True
                                break
                
                if add_separator_flag:
                    regex_parts.append(re.escape(separator))
                    example_parts.append(separator)

        regex_parts.append("$")  # End of regex
        
        raw_regex_str = "".join(regex_parts)
        
        # Normalize regex quantifiers like \d4 to \d{4} and [A-Za-z]4 to [A-Za-z]{4}
        # This ensures consistency if any token_def["regex_template"] was written with \d4 instead of \d{4}.
        # It finds \d or character class followed by one or more digits, NOT followed by a }.
        # Example: \d4 -> \d{4}, [A-Za-z]4 -> [A-Za-z]{4}, but \d{4} -> \d{4} (no change).
        final_regex_str = re.sub(r'\\d(\d+)(?!\})', r'\\d{\1}', raw_regex_str)
        final_regex_str = re.sub(r'(\[[^\]]+\])(\d+)(?!\})', r'\1{\2}', final_regex_str)

        self.regex_edit.setText(final_regex_str)
        self.example_edit.setText("".join(example_parts))

        # Validate the generated regex and update the status icon
        try:
            re.compile(final_regex_str)
            # Assuming QtGui is available from `from PySide6 import QtGui`
            if hasattr(self, 'regex_status_icon') and self.regex_status_icon:
                 self.regex_status_icon.setPixmap(QtGui.QPixmap("icons/success.png"))
        except re.error:
            if hasattr(self, 'regex_status_icon') and self.regex_status_icon:
                self.regex_status_icon.setPixmap(QtGui.QPixmap("icons/error.png"))
        except AttributeError:
            # This might happen if regex_status_icon is not yet fully initialized,
            # though it should be by the time this method is called.
            pass

    def save_template(self):
        """Save the current template configuration"""
        # Update regex to ensure it's correct before saving
        self.update_regex()
        
        # Get the template configuration from the template builder
        template_config = []
        for row in range(self.template_builder.table.rowCount()):
            config = {}
            # Get token data from the table
            if "token_def" in self.template_builder.token_configs[row]:
                config["name"] = self.template_builder.token_configs[row]["name"]
                config["token_def"] = self.template_builder.token_configs[row]["token_def"]
                config["value"] = self.template_builder.token_configs[row]["value"]
            # Get separator data
            if "separator" in self.template_builder.token_configs[row]:
                config["separator"] = self.template_builder.token_configs[row]["separator"]
            template_config.append(config)
        
        # Open file dialog to save the template
        from PySide6 import QtWidgets
        import yaml
        import os
        
        options = QtWidgets.QFileDialog.Options()
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Save Template YAML",
            "",
            "YAML Files (*.yaml *.yml);;All Files (*)",
            options=options
        )
        
        if not file_path:
            return
            
        # Add .yaml extension if not provided
        if not file_path.endswith(('.yaml', '.yml')):
            file_path += '.yaml'
            
        # Save the template configuration to the file
        try:
            with open(file_path, "w") as f:
                yaml.dump(template_config, f, default_flow_style=False)
            QtWidgets.QMessageBox.information(
                self,
                "Template Saved",
                f"Template configuration saved to {os.path.basename(file_path)}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error Saving Template",
                f"Failed to save template: {str(e)}"
            )

    def load_template(self):
        """Load a template configuration from YAML file and update the template builder."""
        from PySide6 import QtWidgets
        import yaml
        import os

        options = QtWidgets.QFileDialog.Options()
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Open Template YAML",
            "",
            "YAML Files (*.yaml *.yml);;All Files (*)",
            options=options
        )
        if not file_path or not os.path.exists(file_path):
            return

        try:
            with open(file_path, "r") as f:
                template_config = yaml.safe_load(f)
                
            # Validate the loaded configuration
            if not isinstance(template_config, list):
                raise ValueError("Template YAML must be a list of token configurations.")
                
            # Clear the current template
            self.template_builder.clear()
            
            # Process each token/separator in the template configuration
            for config in template_config:
                if "name" in config and "token_def" in config:
                    # This is a token
                    token_name = config["name"]
                    
                    # Check if there's a master definition in FILENAME_TOKENS
                    master_def = next((t for t in FILENAME_TOKENS if t["name"] == token_name), None)
                    
                    if master_def:
                        # Use the master definition but preserve the loaded token_def's structure
                        token_def = config["token_def"].copy()
                        
                        # ALWAYS ensure we're using the master regex_template
                        if "regex_template" in master_def:
                            token_def["regex_template"] = master_def["regex_template"]
                            print(f"Using master regex_template for {token_name} during template load: {master_def['regex_template']}")
                        
                        # Special case for description token
                        if token_name == "description":
                            token_def["regex_template"] = ".+?"
                            print(f"Explicitly setting description token regex_template to: {token_def['regex_template']} during template load")
                    else:
                        # If no master definition found, use the original but log a warning
                        token_def = config["token_def"]
                        print(f"Warning: No master definition found for token '{token_name}' in FILENAME_TOKENS during template load")
                    
                    self.template_builder.add_token(token_def)
                    
                    # Set the token value if provided
                    if "value" in config:
                        row = self.template_builder.table.rowCount() - 1
                        self.template_builder._update_token_value(row, config["value"])
                        
                elif "separator" in config:
                    # This is a separator
                    row = self.template_builder.table.rowCount() - 1
                    if row >= 0:
                        self.template_builder._update_token_separator(row, config["separator"])
            
            # Update the regex pattern
            self.update_regex()
            
            QtWidgets.QMessageBox.information(
                self,
                "Template Loaded",
                f"Template configuration loaded from {os.path.basename(file_path)}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Error Loading Template",
                f"Failed to load template: {str(e)}"
            )

    def _on_regex_edit(self):
        """Validate and apply the manually edited regex, updating the status icon and showing errors if invalid."""
        # Using PySide6 for consistency (was incorrectly using PyQt5)
        from PySide6 import QtWidgets, QtGui
        import re

        regex_str = self.regex_edit.text()
        try:
            re.compile(regex_str)
            # If valid, set status icon to success (green/checkmark)
            self.regex_status_icon.setPixmap(QtGui.QPixmap("icons/success.png"))
            # Optionally, update template config or other state here
        except re.error as e:
            self.regex_status_icon.setPixmap(QtGui.QPixmap("icons/error.png"))
            QtWidgets.QMessageBox.critical(self, "Regex Error", f"Invalid regex:\n{e}")

    def get_validation_errors(self, filename):
        """
        Public method to get specific validation errors for a filename.
        Returns list of specific error messages that tell you exactly what's wrong.
        
        Args:
            filename (str): The filename to validate
            
        Returns:
            list: List of specific error messages, empty if valid
        """
        if not filename:
            return ["Empty filename"]
            
        template_config = self.template_builder.get_template_config()
        if not template_config:
            return ["No template configured"]
            
        return self._validate_filename_detailed(filename, template_config)
        
    def _validate_filename_detailed(self, filename, template_config):
        """
        Detailed filename validation that checks each token individually
        """
        errors = []
        remaining_filename = filename
        
        for i, token_cfg in enumerate(template_config):
            token_name = token_cfg["name"]
            separator = token_cfg.get("separator", "")
            
            # Find token definition from the token_cfg itself
            token_def = token_cfg.get("token_def")
            if not token_def:
                print(f"Warning: Token definition not found in token_cfg for {token_name} during validation.")
                continue
            
            # Check if there's a master definition in FILENAME_TOKENS
            master_def = next((t for t in FILENAME_TOKENS if t["name"] == token_name), None)
            
            # If master definition exists, use its regex_template
            if master_def and "regex_template" in master_def:
                # Create a copy to avoid modifying the original
                token_def_copy = token_def.copy()
                token_def_copy["regex_template"] = master_def["regex_template"]
                
                # Special case for description token
                if token_name == "description":
                    token_def_copy["regex_template"] = ".+?"
                
                # Use the updated token_def with master regex_template
                token_def = token_def_copy
                
            try:
                # Generate expected pattern for this token
                expected_pattern, example = self._get_token_pattern_and_example(token_def, token_cfg)
                
                # Try to match this token at the start of remaining filename
                import re
                pattern_with_separator = expected_pattern
                if separator and i < len(template_config) - 1:  # Don't add separator to last token
                    pattern_with_separator += re.escape(separator)
                
                match = re.match(f"^({pattern_with_separator})", remaining_filename)
                
                if not match:
                    # Specific error based on token type
                    errors.append(self._generate_token_error(token_def, token_cfg, remaining_filename, expected_pattern, example))
                    break  # Stop at first error for clarity
                else:
                    # Remove matched part and continue
                    matched_text = match.group(1)
                    remaining_filename = remaining_filename[len(matched_text):]
                    
            except Exception as e:
                errors.append(f"Error validating {token_name}: {str(e)}")
                break
        
        # Check if there's unexpected content at the end
        if not errors and remaining_filename.strip():
            errors.append(f"Unexpected content at end: '{remaining_filename}' (should end with configured extension)")
            
        return errors
    
    def _get_token_pattern_and_example(self, token_def, token_cfg):
        """
        Generate regex pattern and example for a specific token, primarily using token_def["regex_template"]
        and substituting values from token_cfg where appropriate.
        token_def comes from the YAML's 'token_definitions' (via self.available_tokens).
        token_cfg comes from the template builder's current state for that token instance.
        """
        token_name = token_def["name"]
        
        # First, check if there's a master definition in FILENAME_TOKENS
        master_def = next((t for t in FILENAME_TOKENS if t["name"] == token_name), None)
        
        # ALWAYS use the regex_template from the master definition if available
        if master_def and "regex_template" in master_def:
            # For description token, always use the explicit ".+?" pattern
            if token_name == "description":
                pattern = ".+?"  # Explicitly set to the correct pattern
                print(f"Using explicit pattern for description token: {pattern}")
            else:
                # For all other tokens, always use the master definition
                pattern = master_def["regex_template"]
                
            # Log the pattern being used for debugging
            print(f"Using pattern for {token_name}: {pattern} (from master definition)")
        else:
            # Fallback to the token_def from the template builder
            pattern = token_def.get("regex_template", ".+?") # Default to match anything if template is missing
            
        example_options = token_def.get("examples", [])
        example = example_options[0] if example_options else token_name # Default example
        
        # Store the separator for use in the pattern and example
        separator = token_cfg.get("separator", "")

        control_type = token_def.get("control")
        user_value = token_cfg.get("value") # Value from the UI for this token instance

        if control_type == "range_spinner":
            min_val = token_cfg.get("min_value", token_def.get("default_min", token_def.get("min", 1)))
            max_val = token_cfg.get("max_value", token_def.get("default_max", token_def.get("max", 10)))
            # Ensure min_val and max_val are integers for formatting
            try:
                min_val = int(min_val)
                max_val = int(max_val)
            except (ValueError, TypeError):
                min_val, max_val = 1, 10 # Fallback
            
            pattern = pattern.replace("MIN_VAL", str(min_val)).replace("MAX_VAL", str(max_val))
            # If regex_template was like '[A-Za-z]{MIN_VAL,MAX_VAL}', example should reflect that
            if "[A-Za-z]" in pattern or "[a-zA-Z]" in pattern : example = "A" * min_val
            elif "\\d" in pattern : example = "0" * min_val
            else: example = f"({min_val}-{max_val} chars)"

        elif control_type == "spinner":
            n = user_value if user_value is not None else token_def.get("default", 4)
            try:
                n = int(n)
            except (ValueError, TypeError):
                n = 4 # Fallback
            pattern = pattern.replace("{n}", str(n))
            if "\\d" in pattern: example = "0" * n
            elif "[A-Za-z]" in pattern or "[a-zA-Z]" in pattern: example = "A" * n
            else: example = f"({n} chars)"

        elif control_type == "dropdown":
            # If regex_template is meant to be dynamic based on selection (e.g. "(?:(LL180|LL360))?" )
            # and user_value is one of the options, we might want to make the pattern specific.
            # However, to keep it simple and rely on YAML, we assume regex_template is either
            # a group of options, or the user_value itself if it's not "none".
            if user_value and user_value != "none" and user_value in token_def.get("options", []):
                # If the regex_template is a generic placeholder like ".+?" or specific like "(LL180|LL360)"
                # and the user selected a specific value, use the specific value.
                # This assumes the YAML's regex_template for dropdowns is either specific or a group.
                # If it's a group like (LL180|LL360), we let it be. If it's like ".+?", then escape.
                if pattern == ".+?": # A generic placeholder, make it specific
                     pattern = re.escape(user_value)
                # If pattern is already (LL180|LL360) and user_value is LL180, we could make it just LL180
                # For now, if user_value is not "none", it implies it should be present.
                # The regex_template from YAML should handle optionality correctly (e.g. using (?:...)? )
                example = user_value
            elif user_value == "none" and "(?:" in pattern and ")?" in pattern: # Optional token, and "none" selected
                pattern = "" # Make it effectively optional by providing an empty pattern part
                example = "(optional)"
            # else, use the regex_template as is (e.g., if it's already an OR group of options)
            # and the first example from YAML.

        elif control_type == "multiselect":
            selected_options = user_value if isinstance(user_value, list) and user_value else []
            if selected_options:
                # Use the selected options to form the pattern part, overriding generic regex_template
                # Add a dot before extension if this is the extension token
                if token_name == "extension":
                    pattern = f"({'|'.join(re.escape(opt) for opt in selected_options)})"
                else:
                    pattern = f"({'|'.join(re.escape(opt) for opt in selected_options)})"
                example = selected_options[0]
            elif not selected_options and token_def.get("options"): # No selection, but options exist
                 # Fallback to a pattern matching any of the defined options if regex_template is too generic
                if pattern == ".+?": # Generic placeholder
                    all_defined_options = [re.escape(opt) for opt in token_def.get("options", [])]
                    if all_defined_options:
                        if token_name == "extension":
                            pattern = f"(\\.({'|'.join(all_defined_options)}))"
                        else:
                            pattern = f"({'|'.join(all_defined_options)})"
                example = f"({token_def.get('options',[example_options])[0]})"

            # If no options selected and no predefined options, regex_template from YAML is used as is.

        # For "static" or other control types, the regex_template from YAML is used directly.
        # The example is also taken from YAML.

        return pattern, example
    
    def _generate_token_error(self, token_def, token_cfg, remaining_filename, expected_pattern, example):
        """Generate specific error message for a token mismatch"""
        token_name = token_def["name"]
        label = token_def["label"]
        
        # Get the part of filename we're trying to match (up to next separator or end)
        preview_len = min(15, len(remaining_filename))
        filename_preview = remaining_filename[:preview_len]
        if len(remaining_filename) > preview_len:
            filename_preview += "..."
            
        # Condensed error message
        if token_name == "sequence":
            min_val = token_cfg.get("min_value", token_cfg.get("value", 2))
            max_val = token_cfg.get("max_value", token_cfg.get("value", 4))
            if min_val == max_val:
                return f"{label}: '{filename_preview}' - Expected exactly {min_val} letters (uppercase or lowercase) (e.g. {'A' * min_val})"
            else:
                return f"{label}: '{filename_preview}' - Expected {min_val} to {max_val} letters (uppercase or lowercase) (e.g. {'A' * min_val} minimum)"
            
        elif token_name == "shotNumber":
            n = token_cfg.get("value", 4)
            return f"{label}: '{filename_preview}' - Expected {n} digits (e.g. 0010, 1000)"
            
        elif token_name == "description":
            return f"{label}: '{filename_preview}' - Expected alphanumeric+hyphens (e.g. comp, roto-main)"
            
        elif token_name == "pixelMappingName":
            val = token_cfg.get("value")
            if val and val != "none":
                return f"{label}: '{filename_preview}' - Expected '{val}'"
            else:
                return f"{label}: '{filename_preview}' - Expected LL180/LL360 or skip this token"
                
        elif token_name == "resolution":
            return f"{label}: '{filename_preview}' - Expected format like 2k, 4k, 12k, HD_1080"
            
        elif token_name == "colorspaceGamma":
            val = token_cfg.get("value", [])
            if val and len(val) <= 2:
                return f"{label}: '{filename_preview}' - Expected {'/'.join(val)}"
            elif val:
                return f"{label}: '{filename_preview}' - Expected one of {len(val)} configured options"
            else:
                return f"{label}: '{filename_preview}' - Expected r709g24, sRGBg22, ap0lin, etc."
                
        elif token_name == "fps":
            val = token_cfg.get("value")
            if val:
                return f"{label}: '{filename_preview}' - Expected '{val}'"
            else:
                return f"{label}: '{filename_preview}' - Expected 24, 25, 2997, etc."
                
        elif token_name == "version":
            return f"{label}: '{filename_preview}' - Expected v001, v010, v114, etc."
            
        elif token_name == "frame_padding":
            return f"{label}: '{filename_preview}' - Expected %04d to %08d or #### to ########"
            
        elif token_name == "extension":
            val = token_cfg.get("value", [])
            if val and len(val) <= 3:
                return f"{label}: '{filename_preview}' - Expected .{' or .'.join(val)}"
            elif val:
                return f"{label}: '{filename_preview}' - Expected one of {len(val)} configured extensions"
            else:
                return f"{label}: '{filename_preview}' - Expected .exr, .jpg, .png, etc."
                
        else:
            return f"{label}: '{filename_preview}' - Expected {example}"

    def get_validation_summary(self, filename):
        """
        Get a concise validation summary for error reporting.
        
        Args:
            filename (str): The filename to validate
            
        Returns:
            str: Concise error message or empty string if valid
        """
        errors = self.get_validation_errors(filename)
        if not errors:
            return ""
            
        # Return the first (most specific) error
        return errors[0]

    def _update_example_from_regex(self):
        """Generate an example filename from the current regex pattern"""
        try:
            # Get current template config for a proper example
            config = self.template_builder.get_template_config()
            if config:
                # If we have template config, use the normal update method
                self.update_regex()
            else:
                # If no template, try to generate a simple example from regex
                regex_text = self.regex_edit.text()
                if regex_text and regex_text != "^$":
                    # Simple example generation - replace common patterns
                    example = regex_text.replace("^", "").replace("$", "")
                    example = example.replace("[A-Z]{4}", "DEMO")
                    example = example.replace("\\d{4}", "0010")
                    example = example.replace("\\d{1,2}k", "2k")
                    example = example.replace("v\\d{3}", "v001")
                    example = example.replace("(?i)(jpg|jpeg|png|mxf|mov|exr)", "jpg")
                    self.example_edit.setText(example)
                else:
                    self.example_edit.clear()
        except Exception:
            # If anything fails, just clear the example
            self.example_edit.clear()

class CompactTokenWidget(QtWidgets.QWidget):
    """
    Compact token widget for grid layout
    """
    def __init__(self, token_def, parent=None):
        super().__init__(parent)
        self.token_def = token_def
        
        # Main layout - more compact
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        
        # Header with token name and remove button
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(2)
        
        # Token label
        self.label = QtWidgets.QLabel(token_def["label"])
        self.label.setStyleSheet("""
            QLabel {
                background: #4a4a4a;
                color: #e0e0e0;
                border: 1px solid #666;
                border-radius: 3px;
                padding: 2px 4px;
                font-size: 9px;
                font-weight: bold;
                min-width: 70px;
            }
        """)
        self.label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(self.label)
        
        # Remove button
        self.remove_btn = QtWidgets.QPushButton("×")
        self.remove_btn.setFixedSize(16, 16)
        self.remove_btn.setStyleSheet("""
            QPushButton {
                background: #d32f2f;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover { background: #f44336; }
            QPushButton:pressed { background: #b71c1c; }
        """)
        header_layout.addWidget(self.remove_btn)
        
        layout.addLayout(header_layout)
        
        # Control and separator row
        controls_layout = QtWidgets.QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(2)
        
        # Control (dropdown, multiselect, etc.)
        self.control = None
        if token_def["control"] == "spinner":
            self.control = QtWidgets.QSpinBox()
            self.control.setMinimum(token_def["min"])
            self.control.setMaximum(token_def["max"])
            self.control.setValue(token_def["default"])
            self.control.setFixedWidth(50)
            
        elif token_def["control"] == "dropdown":
            self.control = QtWidgets.QComboBox()
            self.control.addItems(token_def["options"])
            self.control.setFixedWidth(60)
            
        elif token_def["control"] == "multiselect":
            self.control = SimpleMultiSelectWidget(token_def["options"])
            self.control.setFixedWidth(60)
            self.control.selectionChanged.connect(self._on_control_changed)
            
        elif token_def["control"] == "static":
            self.control = QtWidgets.QLabel("(auto)")
            self.control.setFixedWidth(60)
            self.control.setStyleSheet("QLabel { color: #888; font-style: italic; font-size: 8px; }")
        
        if self.control:
            self.control.setStyleSheet("""
                QWidget {
                    background: #3a3a3a;
                    color: #e0e0e0;
                    border: 1px solid #555;
                    border-radius: 2px;
                    font-size: 8px;
                }
                QComboBox::drop-down {
                    border: none;
                    width: 12px;
                }
                QComboBox::down-arrow {
                    border-left: 2px solid transparent;
                    border-right: 2px solid transparent;
                    border-top: 2px solid #e0e0e0;
                }
            """)
            controls_layout.addWidget(self.control)
        
        # Separator dropdown
        self.separator_combo = QtWidgets.QComboBox()
        self.separator_combo.addItems(["_", ".", "-", " ", "(none)"])
        self.separator_combo.setCurrentText("_")
        self.separator_combo.setFixedWidth(40)
        self.separator_combo.setStyleSheet("""
            QComboBox {
                background: #3a3a3a;
                color: #e0e0e0;
                border: 1px solid #555;
                border-radius: 2px;
                font-size: 8px;
            }
        """)
        controls_layout.addWidget(self.separator_combo)
        
        layout.addLayout(controls_layout)
        
        # Movement buttons
        move_layout = QtWidgets.QHBoxLayout()
        move_layout.setContentsMargins(0, 0, 0, 0)
        move_layout.setSpacing(2)
        
        self.up_btn = QtWidgets.QPushButton("↑")
        self.up_btn.setFixedSize(15, 15)
        self.down_btn = QtWidgets.QPushButton("↓")
        self.down_btn.setFixedSize(15, 15)
        
        for btn in [self.up_btn, self.down_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background: #4a4a4a;
                    color: #e0e0e0;
                    border: 1px solid #666;
                    border-radius: 2px;
                    font-size: 8px;
                    padding: 0px;
                }
                QPushButton:hover { background: #5a5a5a; }
                QPushButton:pressed { background: #2a2a2a; }
                QPushButton:disabled { background: #2a2a2a; color: #666; }
            """)
        
        move_layout.addWidget(self.up_btn)
        move_layout.addWidget(self.down_btn)
        move_layout.addStretch()
        
        layout.addLayout(move_layout)
        
        # Connect signals
        if self.control and hasattr(self.control, 'currentTextChanged'):
            self.control.currentTextChanged.connect(self._on_control_changed)
        elif self.control and hasattr(self.control, 'valueChanged'):
            self.control.valueChanged.connect(self._on_control_changed)
        
        self.separator_combo.currentTextChanged.connect(self._on_control_changed)
        
        # Widget styling
        self.setFixedSize(90, 65)  # Compact size
        self.setStyleSheet("""
            CompactTokenWidget {
                background: #383838;
                border: 1px solid #555;
                border-radius: 4px;
                margin: 1px;
            }
            CompactTokenWidget:hover {
                border: 1px solid #4a9eff;
                background: #404040;
            }
        """)
        
    def _on_control_changed(self):
        """Notify parent when control values change"""
        parent = self.parent()
        while parent:
            if hasattr(parent, 'update_regex'):
                parent.update_regex()
                break
            parent = parent.parent()
    
    def get_token_config(self):
        """Return the token configuration"""
        value = None
        if self.control:
            try:
                if isinstance(self.control, QtWidgets.QSpinBox):
                    value = self.control.value()
                elif isinstance(self.control, QtWidgets.QComboBox):
                    value = self.control.currentText()
                elif isinstance(self.control, SimpleMultiSelectWidget):
                    value = self.control.get_selected_values()
            except RuntimeError:
                value = None
        
        # Get separator
        separator = self.separator_combo.currentText()
        if separator == "(none)":
            separator = ""
            
        return {
            "name": self.token_def["name"], 
            "value": value,
            "separator": separator
        }

class SimpleMultiSelectWidget(QtWidgets.QWidget):
    """
    Simplified multiselect widget for the new interface
    """
    selectionChanged = QtCore.Signal()
    
    def __init__(self, options, parent=None):
        super().__init__(parent)
        self.options = options
        self.selected_values = []
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        
        # Summary button
        self.summary_button = QtWidgets.QPushButton("None selected")
        self.summary_button.clicked.connect(self._show_popup)
        layout.addWidget(self.summary_button)
        
        # Create popup
        self.popup = QtWidgets.QWidget(None, Qt.WindowType.Popup)
        self.popup.setFixedSize(200, min(300, len(options) * 25 + 20))
        
        popup_layout = QtWidgets.QVBoxLayout(self.popup)
        popup_layout.setContentsMargins(5, 5, 5, 5)
        
        self.checkboxes = {}
        for option in options:
            if option != "none":
                checkbox = QtWidgets.QCheckBox(option)
                checkbox.setStyleSheet("""
                    QCheckBox {
                        color: #333;
                        font-size: 10px;
                        background: white;
                        padding: 2px;
                    }
                    QCheckBox::indicator {
                        width: 12px;
                        height: 12px;
                    }
                    QCheckBox::indicator:unchecked {
                        background: white;
                        border: 1px solid #ccc;
                    }
                    QCheckBox::indicator:checked {
                        background: #0078d4;
                        border: 1px solid #0078d4;
                    }
                """)
                checkbox.stateChanged.connect(self._on_checkbox_changed)
                self.checkboxes[option] = checkbox
                popup_layout.addWidget(checkbox)
        
        self.popup.setStyleSheet("""
            QWidget {
                background: white;
                border: 2px solid #ccc;
                border-radius: 4px;
            }
        """)
        
    def _show_popup(self):
        global_pos = self.summary_button.mapToGlobal(QtCore.QPoint(0, self.summary_button.height()))
        self.popup.move(global_pos)
        self.popup.show()
        
    def _on_checkbox_changed(self):
        self.selected_values = [option for option, checkbox in self.checkboxes.items() if checkbox.isChecked()]
        self._update_summary()
        self.selectionChanged.emit()
        
    def _update_summary(self):
        if not self.selected_values:
            self.summary_button.setText("None")
        elif len(self.selected_values) == 1:
            text = self.selected_values[0]
            if len(text) > 10:
                text = text[:7] + "..."
            self.summary_button.setText(text)
        else:
            self.summary_button.setText(f"{len(self.selected_values)} items")
    
    def get_selected_values(self):
        """Return list of selected values"""
        return self.selected_values.copy()
    
    def set_selected_values(self, values):
        """Set the selected values"""
        self.selected_values = values.copy() if values else []
        # Temporarily disconnect signals to prevent _on_checkbox_changed from being called
        # while we're setting multiple checkboxes
        for option, checkbox in self.checkboxes.items():
            checkbox.stateChanged.disconnect()
        
        # Set all checkboxes
        for option, checkbox in self.checkboxes.items():
            checkbox.setChecked(option in self.selected_values)
        
        # Reconnect signals
        for option, checkbox in self.checkboxes.items():
            checkbox.stateChanged.connect(self._on_checkbox_changed)
            
        self._update_summary()

class SimpleFilenameTemplateBuilder(QtWidgets.QWidget):
    """
    Vertically-oriented list-based template builder for filename validation patterns.
    
    This widget provides a straightforward, vertically-scrollable interface for building
    filename templates. Each token is presented as a distinct row with clear controls for
    configuration, reordering, and removal.
    
    Features:
        - Scrollable vertical layout for handling many tokens
        - Individual row controls for each token
        - Up/down movement controls for token reordering
        - Simple one-click token removal
        - Intuitive visualization of token sequence
    
    This builder offers a middle ground between the comprehensive TableBasedFilenameTemplateBuilder
    and the space-efficient CompactFilenameTemplateBuilder, emphasizing simplicity and clarity
    while still supporting all token configuration options.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(4)
        
        # Header
        header_label = QtWidgets.QLabel("Template Order:")
        header_label.setStyleSheet("QLabel { color: #e0e0e0; font-weight: bold; }")
        main_layout.addWidget(header_label)
        
        # Scroll area for tokens
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.scroll_area.setMinimumHeight(200)
        self.scroll_area.setMaximumHeight(400)
        
        # Container for token widgets
        self.container = QtWidgets.QWidget()
        self.container_layout = QtWidgets.QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(4, 4, 4, 4)
        self.container_layout.setSpacing(2)
        self.container_layout.addStretch()  # Push tokens to top
        
        self.scroll_area.setWidget(self.container)
        main_layout.addWidget(self.scroll_area)
        
        # Clear button
        clear_btn = QtWidgets.QPushButton("Clear All")
        clear_btn.setFixedHeight(25)
        clear_btn.clicked.connect(self.clear)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: #444;
                color: #e0e0e0;
                border: 1px solid #666;
                border-radius: 3px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QPushButton:hover { background: #555; }
            QPushButton:pressed { background: #333; }
        """)
        main_layout.addWidget(clear_btn)
        
        # Track token widgets
        self.token_widgets = []
        
        self.setStyleSheet("""
            SimpleFilenameTemplateBuilder {
                background: #2a2a2a;
                border: 1px solid #555;
                border-radius: 4px;
            }
            QScrollArea {
                background: transparent;
                border: none;
            }
        """)
        
    def add_token(self, token_def):
        """Add a token to the template"""
        widget = SimpleTokenWidget(token_def)
        
        # Connect signals
        widget.remove_btn.clicked.connect(lambda: self.remove_token(widget))
        widget.up_btn.clicked.connect(lambda: self.move_token_up(widget))
        widget.down_btn.clicked.connect(lambda: self.move_token_down(widget))
        
        # Insert before the stretch
        self.container_layout.insertWidget(len(self.token_widgets), widget)
        self.token_widgets.append(widget)
        
        self._update_arrow_states()
        self._notify_change()
        
    def remove_token(self, widget):
        """Remove a token from the template"""
        if widget in self.token_widgets:
            self.token_widgets.remove(widget)
            self.container_layout.removeWidget(widget)
            widget.deleteLater()
            self._update_arrow_states()
            self._notify_change()
            
    def move_token_up(self, widget):
        """Move token up in the list"""
        if widget not in self.token_widgets:
            return
            
        index = self.token_widgets.index(widget)
        if index > 0:
            # Swap in list
            self.token_widgets[index], self.token_widgets[index-1] = self.token_widgets[index-1], self.token_widgets[index]
            
            # Remove and re-add widgets in new order
            for w in self.token_widgets:
                self.container_layout.removeWidget(w)
            
            for i, w in enumerate(self.token_widgets):
                self.container_layout.insertWidget(i, w)
                
            self._update_arrow_states()
            self._notify_change()
            
    def move_token_down(self, widget):
        """Move token down in the list"""
        if widget not in self.token_widgets:
            return
            
        index = self.token_widgets.index(widget)
        if index < len(self.token_widgets) - 1:
            # Swap in list
            self.token_widgets[index], self.token_widgets[index+1] = self.token_widgets[index+1], self.token_widgets[index]
            
            # Remove and re-add widgets in new order
            for w in self.token_widgets:
                self.container_layout.removeWidget(w)
            
            for i, w in enumerate(self.token_widgets):
                self.container_layout.insertWidget(i, w)
                
            self._update_arrow_states()
            self._notify_change()
            
    def _update_arrow_states(self):
        """Update the enabled state of up/down arrows"""
        for i, widget in enumerate(self.token_widgets):
            widget.up_btn.setEnabled(i > 0)
            widget.down_btn.setEnabled(i < len(self.token_widgets) - 1)
            
    def _notify_change(self):
        """Notify parent of changes"""
        parent = self.parent()
        while parent:
            if hasattr(parent, 'update_regex'):
                parent.update_regex()
                break
            parent = parent.parent()
            
        # Removed duplicate method
        result = []
        for widget in self.token_widgets:
            try:
                config = widget.get_token_config()
                result.append(config)
            except RuntimeError:
                continue
        return result
        
    def clear(self):
        """Clear all tokens"""
        for widget in self.token_widgets:
            self.container_layout.removeWidget(widget)
            widget.deleteLater()
        self.token_widgets.clear()
        self._notify_change()

# Replace the old FilenameTemplateBuilder class completely
FilenameTemplateBuilder = TableBasedFilenameTemplateBuilder

class RuleItemWidget(QtWidgets.QWidget):
    """
    DEPRECATED: Legacy widget - use ValidationResultsTable instead
    Kept for backward compatibility during transition
    """
    def __init__(self, rule_name, parent=None):
        super(RuleItemWidget, self).__init__(parent)
        self.rule_name = rule_name
        
        # Simple layout for legacy support
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        
        # Just show the rule name
        self.name_label = QtWidgets.QLabel(rule_name)
        self.name_label.setStyleSheet("QLabel { color: #e0e0e0; }")
        layout.addWidget(self.name_label)
        
        # Status label
        self.status_label = QtWidgets.QLabel("Legacy widget - use ValidationResultsTable")
        self.status_label.setStyleSheet("QLabel { color: #ff9800; font-style: italic; }")
        layout.addWidget(self.status_label)
    
    def set_status(self, status):
        """Legacy method"""
        pass

class CompactFilenameTemplateBuilder(QtWidgets.QWidget):
    """
    Compact grid-based template builder for filename validation patterns.
    
    This widget provides a space-efficient grid layout for building filename templates
    without requiring scroll areas. It dynamically resizes based on content and offers
    an alternative to the table-based template builder for situations where screen
    real estate is limited.
    
    Features:
        - Compact grid layout for space efficiency
        - Dynamic resizing based on content
        - Simplified token configuration
        - Direct visual representation of the final filename
        - Lightweight alternative to more complex builders
    
    This class provides the same core functionality as TableBasedFilenameTemplateBuilder
    but with emphasis on a simpler, more compact UI design.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(4)
        
        # Header
        header_label = QtWidgets.QLabel("Template Order:")
        header_label.setStyleSheet("QLabel { color: #e0e0e0; font-weight: bold; font-size: 11px; }")
        main_layout.addWidget(header_label)
        
        # Grid container for tokens - no scroll area
        self.tokens_container = QtWidgets.QWidget()
        self.tokens_layout = QtWidgets.QGridLayout(self.tokens_container)
        self.tokens_layout.setContentsMargins(4, 4, 4, 4)
        self.tokens_layout.setSpacing(4)
        self.tokens_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        
        main_layout.addWidget(self.tokens_container)
        
        # Control buttons
        controls_layout = QtWidgets.QHBoxLayout()
        
        clear_btn = QtWidgets.QPushButton("Clear All")
        clear_btn.setFixedHeight(22)
        clear_btn.clicked.connect(self.clear)
        clear_btn.setStyleSheet("""
            QPushButton {
                background: #444;
                color: #e0e0e0;
                border: 1px solid #666;
                border-radius: 2px;
                padding: 2px 8px;
                font-size: 10px;
            }
            QPushButton:hover { background: #555; }
            QPushButton:pressed { background: #333; }
        """)
        controls_layout.addWidget(clear_btn)
        controls_layout.addStretch()
        
        main_layout.addLayout(controls_layout)
        
        # Track token widgets and grid position
        self.token_widgets = []
        self.grid_columns = 3  # Number of columns in grid
        
        self.setStyleSheet("""
            CompactFilenameTemplateBuilder {
                background: #2a2a2a;
                border: 1px solid #555;
                border-radius: 4px;
            }
        """)
        
    def add_token(self, token_def):
        """Add a token to the grid layout"""
        widget = CompactTokenWidget(token_def)
        
        # Connect signals
        widget.remove_btn.clicked.connect(lambda: self.remove_token(widget))
        widget.up_btn.clicked.connect(lambda: self.move_token_up(widget))
        widget.down_btn.clicked.connect(lambda: self.move_token_down(widget))
        
        # Add to widgets list and update grid
        self.token_widgets.append(widget)
        self._update_grid_layout()
        self._update_arrow_states()
        self._notify_change()
        
    def remove_token(self, widget):
        """Remove a token from the grid"""
        if widget in self.token_widgets:
            self.token_widgets.remove(widget)
            self.tokens_layout.removeWidget(widget)
            widget.deleteLater()
            self._update_grid_layout()
            self._update_arrow_states()
            self._notify_change()
            
    def move_token_up(self, widget):
        """Move token up in the order"""
        if widget not in self.token_widgets:
            return
            
        index = self.token_widgets.index(widget)
        if index > 0:
            # Swap in list
            self.token_widgets[index], self.token_widgets[index-1] = self.token_widgets[index-1], self.token_widgets[index]
            self._update_grid_layout()
            self._update_arrow_states()
            self._notify_change()
            
    def move_token_down(self, widget):
        """Move token down in the order"""
        if widget not in self.token_widgets:
            return
            
        index = self.token_widgets.index(widget)
        if index < len(self.token_widgets) - 1:
            # Swap in list
            self.token_widgets[index], self.token_widgets[index+1] = self.token_widgets[index+1], self.token_widgets[index]
            self._update_grid_layout()
            self._update_arrow_states()
            self._notify_change()
            
    def _update_grid_layout(self):
        """Update the grid layout with current widgets"""
        # Clear existing layout
        for i in reversed(range(self.tokens_layout.count())):
            item = self.tokens_layout.itemAt(i)
            if item and item.widget():
                self.tokens_layout.removeWidget(item.widget())
        
        # Re-add widgets in grid pattern
        for i, widget in enumerate(self.token_widgets):
            row = i // self.grid_columns
            col = i % self.grid_columns
