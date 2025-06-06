#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Nuke Validator UI - A comprehensive UI for the Nuke Validator
"""

import nuke
import os
import yaml
import json
from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtCore import Qt
from typing import Dict, List, Optional, Tuple, Any # Added Any
import re # For regex generation
from PySide6.QtGui import QStandardItemModel, QStandardItem

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
        "regex": "[a-zA-Z0-9]+(?:[-a-zA-Z0-9]+)*",
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
        "regex": "\\d{1,2}k",
        "description": "Resolution abbreviation (e.g., 1k, 4k, 19k).",
        "examples": ["1k", "2k", "4k", "8k", "12k", "16k", "19k", "32k"],
        "separator": "_"
    },
    "colorspaceGamma": {
        "regex": "(r709|sRGB|ap0|ap1|p3|rec2020)(lin|log|g22|g24|g26)",
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
        "regex": "\\d{4,8}",
        "description": "Frame number padding (e.g., 0001 for ####). Not usually in the main template.",
        "examples": ["0001", "00000001"],
        "separator": "."
    },
    "extension": {
        "regex": "(?i)(jpg|jpeg|png|mp4|mov|exr|nk)",
        "description": "File extension (e.g., jpg, exr, nk).",
        "examples": ["jpg", "png", "mp4", "mov", "exr", "nk"],
        "separator": "" # No separator after extension
    }
}


class RuleItemWidget(QtWidgets.QWidget):
    """
    Widget to display a single rule with progress and status
    """
    def __init__(self, rule_name, parent=None):
        super(RuleItemWidget, self).__init__(parent)
        self.rule_name = rule_name
        
        # Main layout
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        # layout.setSpacing(10) # Optional: add some spacing between elements

        # Status icon (Column 1)
        self.status_icon = QtWidgets.QLabel()
        self.status_icon.setFixedSize(20, 20)
        self.status_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Placeholder, will be set by MainWindow. Create a default transparent one.
        default_pixmap = QtGui.QPixmap(20,20)
        default_pixmap.fill(Qt.GlobalColor.transparent)
        self.status_icon.setPixmap(default_pixmap)
        self.status_icon.setStyleSheet("border: 1px solid #555555;") # Darker border for visibility
        layout.addWidget(self.status_icon, 0) # Stretch factor 0 for icon

        # Rule name label (Column 2)
        self.name_label = QtWidgets.QLabel()
        self.name_label.setWordWrap(True)
        self.name_label.setTextFormat(Qt.TextFormat.RichText)
        self.name_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        # self.name_label.setMinimumWidth(150) # Optional: give it a minimum width
        layout.addWidget(self.name_label, 1) # Stretch factor 1 for name

        # Progress bar (conditionally visible, Column 3 - if used for active validation)
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedWidth(100)
        self.progress_bar.setVisible(False) # Typically hidden for results display
        layout.addWidget(self.progress_bar, 0) # Stretch factor 0 for progress bar
        
        # Status label/details (Column 4 - takes remaining space)
        self.status_label = QtWidgets.QLabel()
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(Qt.TextFormat.RichText)
        self.status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        # self.status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.status_label, 3) # Stretch factor 3 for details, allowing it to expand most
        
        # No final layout.addStretch() needed if using stretch factors on widgets.

class RulesEditorWidget(QtWidgets.QWidget):
    """
    Widget for editing rules with a graphical interface
    """
    def __init__(self, parent=None):
        super(RulesEditorWidget, self).__init__(parent)
        
        self.rules_yaml_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.yaml")
        self.dropdown_yaml_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules_dropdowns.yaml")
        self.dropdown_options = self._load_yaml_file(self.dropdown_yaml_path) or {}
        
        # Initialize attributes for dynamic filename validation
        self.filename_template = DEFAULT_FILENAME_TEMPLATE
        # Deepcopy might be good here if tokens are modified and reset later
        self.filename_tokens = DEFAULT_NAMING_TOKENS.copy()

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

        # Main layout for the entire RulesEditorWidget
        main_editor_layout = QtWidgets.QVBoxLayout(self)

        # Splitter for category list and settings stack
        self.rules_splitter = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        main_editor_layout.addWidget(self.rules_splitter)

        # Left pane: Category List
        self.category_list = QtWidgets.QListWidget()
        # self.category_list.setMaximumWidth(300) # Let's remove fixed max width, splitter will handle
        self.rules_splitter.addWidget(self.category_list)

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
        save_button = QtWidgets.QPushButton("Save Rules to YAML")
        save_button.clicked.connect(self.save_rules_to_yaml)
        button_layout.addWidget(save_button)
        
        reload_button = QtWidgets.QPushButton("Reload Rules from YAML")
        reload_button.clicked.connect(self.load_rules_from_yaml)
        button_layout.addWidget(reload_button)
        main_editor_layout.addLayout(button_layout)
        
        self.load_rules_from_yaml() # Load rules on init (will populate UI elements)
        
        if self.category_list.count() > 0:
            self.category_list.setCurrentRow(0) # Select the first category by default

    def _create_all_rule_pages(self):
        """Calls all individual methods to create rule setting pages."""
        self.create_filepath_naming_tab()
        self.create_frame_range_tab()
        self.create_node_integrity_tab()
        self.create_write_node_resolution_tab()
        self.create_color_space_tab()
        self.create_channels_tab_write_node()
        self.create_render_settings_tab_write_node()
        self.create_versioning_tab()
        self.create_viewer_nodes_tab()
        self.create_script_errors_tab()

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
        """ Create tab for File Path and Naming rules with dynamic regex generation. """
        tab = QtWidgets.QWidget()
        main_tab_layout = QtWidgets.QVBoxLayout(tab) # Main layout for the tab

        # Section for general path rules
        general_group = QtWidgets.QGroupBox("General Path Rules")
        general_layout = QtWidgets.QFormLayout()
        self.fp_relative_path_check = QtWidgets.QCheckBox("Require Relative Paths")
        general_layout.addRow(self.fp_relative_path_check)
        self.fp_severity_relative_combo = QtWidgets.QComboBox()
        self._populate_combobox(self.fp_severity_relative_combo, self.dropdown_options.get('severity_options'))
        general_layout.addRow("Severity (Relative Path):", self.fp_severity_relative_combo)
        general_group.setLayout(general_layout)
        main_tab_layout.addWidget(general_group)

        # Section for dynamic filename convention
        convention_group = QtWidgets.QGroupBox("Dynamic Filename Convention")
        convention_layout = QtWidgets.QVBoxLayout()

        # Template Editor
        template_form_layout = QtWidgets.QFormLayout()
        self.fp_template_edit = QtWidgets.QLineEdit(self.filename_template)
        self.fp_template_edit.setToolTip(
            "Define the filename structure using tokens like <sequence> or (?<optional_token>)?. "
            "Separators like _ or . should be included directly in the template."
        )
        template_form_layout.addRow("Filename Template:", self.fp_template_edit)
        convention_layout.addLayout(template_form_layout)

        # Token Editor Table
        convention_layout.addWidget(QtWidgets.QLabel("Filename Tokens:"))
        self.fp_token_table = QtWidgets.QTableWidget()
        self.fp_token_table.setColumnCount(4) # Token, Regex, Description, Separator After
        self.fp_token_table.setHorizontalHeaderLabels(["Token", "Regex Pattern", "Description", "Separator After"])
        self._populate_token_table() # Populate with default/loaded tokens
        self.fp_token_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.fp_token_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Interactive) # Token name
        self.fp_token_table.horizontalHeader().setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Interactive) # Separator
        self.fp_token_table.setMinimumHeight(200)
        convention_layout.addWidget(self.fp_token_table)
        
        # Regex Generation and Display
        regex_gen_layout = QtWidgets.QHBoxLayout()
        self.fp_generate_regex_button = QtWidgets.QPushButton("Generate/Update Regex from Template & Tokens")
        self.fp_generate_regex_button.clicked.connect(self._generate_regex_from_template_and_tokens)
        regex_gen_layout.addWidget(self.fp_generate_regex_button)
        convention_layout.addLayout(regex_gen_layout)

        constructed_regex_form_layout = QtWidgets.QFormLayout()
        self.fp_naming_pattern_regex_edit = QtWidgets.QLineEdit()
        self.fp_naming_pattern_regex_edit.setReadOnly(True) # Display only, generated from template
        self.fp_naming_pattern_regex_edit.setToolTip("This regex is constructed from the template and tokens above.")
        constructed_regex_form_layout.addRow("Constructed Regex:", self.fp_naming_pattern_regex_edit)
        
        self.fp_severity_naming_combo = QtWidgets.QComboBox()
        self._populate_combobox(self.fp_severity_naming_combo, self.dropdown_options.get('severity_options'))
        constructed_regex_form_layout.addRow("Severity (Naming Pattern):", self.fp_severity_naming_combo)
        convention_layout.addLayout(constructed_regex_form_layout)
        
        convention_group.setLayout(convention_layout)
        main_tab_layout.addWidget(convention_group)
        
        main_tab_layout.addStretch()
        # self.tabs.addTab(tab, "File Path & Naming") # Old way
        self.category_list.addItem("File Path & Naming")
        self.settings_stack.addWidget(tab)

    def _populate_token_table(self, tokens_data: Optional[Dict[str, Dict[str, Any]]] = None):
        """Populates the token editor table with token data."""
        if tokens_data is None:
            tokens_data = self.filename_tokens

        self.fp_token_table.setRowCount(0) # Clear existing rows
        self.fp_token_table.setRowCount(len(tokens_data))

        for row, (token_name, token_info) in enumerate(tokens_data.items()):
            # Token Name (not editable by default, it's the key)
            name_item = QtWidgets.QTableWidgetItem(token_name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable) # Make non-editable
            self.fp_token_table.setItem(row, 0, name_item)

            # Regex Pattern
            regex_item = QtWidgets.QTableWidgetItem(token_info.get("regex", ""))
            self.fp_token_table.setItem(row, 1, regex_item)

            # Description
            desc_item = QtWidgets.QTableWidgetItem(token_info.get("description", ""))
            self.fp_token_table.setItem(row, 2, desc_item)
            
            # Separator After
            separator_item = QtWidgets.QTableWidgetItem(token_info.get("separator", ""))
            self.fp_token_table.setItem(row, 3, separator_item)
        
        self.fp_token_table.resizeColumnsToContents()
        self.fp_token_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch) # Regex
        self.fp_token_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch) # Description


    def _get_tokens_from_table(self) -> Dict[str, Dict[str, Any]]:
        """Extracts token definitions from the QTableWidget."""
        tokens_data = {}
        for row in range(self.fp_token_table.rowCount()):
            try:
                token_name = self.fp_token_table.item(row, 0).text()
                regex_pattern = self.fp_token_table.item(row, 1).text()
                description = self.fp_token_table.item(row, 2).text()
                separator = self.fp_token_table.item(row, 3).text()
                tokens_data[token_name] = {
                    "regex": regex_pattern,
                    "description": description,
                    "separator": separator
                    # 'examples' are not directly edited in the table for now
                }
            except AttributeError: # Catch if a cell item is None
                print(f"Warning: Row {row} in token table might be incomplete.")
                continue
        return tokens_data

    def _generate_regex_from_template_and_tokens(self):
        """
        Generates a regex string from the filename template and token definitions.
        Updates the 'Constructed Regex' field.
        """
        template = self.fp_template_edit.text()
        self.filename_tokens = self._get_tokens_from_table() # Update internal tokens from table

        final_regex_parts = []
        
        # Regex to find tokens: <token_name> or (?<token_name>)?
        # It captures the optional marker '(?< >)?' and the token name itself.
        token_finder_regex = re.compile(r"(?P<optional_marker>\(\?\<\s*)?(?P<token_name>\w+)(?(optional_marker)\s*\>\)?)")

        last_index = 0
        for match in token_finder_regex.finditer(template):
            # Add literal part before the token
            literal_part = template[last_index:match.start()]
            if literal_part:
                final_regex_parts.append(re.escape(literal_part))

            token_name = match.group("token_name")
            is_optional_syntax = bool(match.group("optional_marker")) # Checks if '(?< >)?' syntax was used

            if token_name in self.filename_tokens:
                token_info = self.filename_tokens[token_name]
                token_regex = token_info.get("regex", "")
                
                # Separator logic:
                # The separator is part of the token's group if the token is optional.
                # If the token is mandatory, the separator is handled by the next literal part or end of string.
                # For simplicity, we'll assume separators in the template are literal characters for now.
                # The 'separator' field in token_info is more for documentation or more complex generation.

                if is_optional_syntax:
                    # For optional tokens like (?<pixelMappingName>)?, make the group optional
                    # We need to be careful if a separator is *part* of the optional group.
                    # Example: _(?<pixelMappingName>)? means the underscore is also optional with the token.
                    # If template is ...<token1>_(?<token2>)?<token3>...
                    # The _ before (?<token2>)? needs to be handled.
                    # The current token_finder_regex doesn't capture separators associated with optional tokens.
                    # We'll assume for now that separators are outside the (?< >)? optional markers.
                    # A more robust parser would look at characters immediately before/after the optional token.
                    
                    # Simple optional group for the token's regex:
                    final_regex_parts.append(f"(?:{token_regex})?")
                else:
                    final_regex_parts.append(f"({token_regex})") # Capture group for mandatory tokens
            else:
                # Token not found, treat as literal but warn
                print(f"Warning: Token '{token_name}' found in template but not defined in tokens table. Treating as literal.")
                final_regex_parts.append(re.escape(match.group(0)))
            
            last_index = match.end()

        # Add any remaining literal part after the last token
        remaining_literal = template[last_index:]
        if remaining_literal:
            final_regex_parts.append(re.escape(remaining_literal))
        
        full_regex = "".join(final_regex_parts)
        
        # Anchor the regex
        if full_regex and not full_regex.startswith("^"):
            full_regex = "^" + full_regex
        if full_regex and not full_regex.endswith("$"):
            full_regex = full_regex + "$"
            
        self.fp_naming_pattern_regex_edit.setText(full_regex)
        print(f"DEBUG: Generated Regex: {full_regex}")

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
        self._populate_combobox(self.frame_rate_combo, self.dropdown_options.get('frame_range', {}).get('fps_options'), "24")
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
        layout.addRow(self.ni_check_disabled_nodes_check)

        self.ni_severity_disabled_combo = QtWidgets.QComboBox()
        self._populate_combobox(self.ni_severity_disabled_combo, self.dropdown_options.get('severity_options'))
        layout.addRow("Severity (Disabled Nodes):", self.ni_severity_disabled_combo)
        
        # self.tabs.addTab(tab, "Node Integrity") # Old way
        self.category_list.addItem("Node Integrity")
        self.settings_stack.addWidget(tab)

    def create_write_node_resolution_tab(self):
        """ Create tab for Write Node resolution rules. """
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(tab)

        self.wnr_allowed_formats_edit = QtWidgets.QLineEdit()
        self.wnr_allowed_formats_edit.setPlaceholderText("Comma-separated Nuke format names (e.g., HD_1080,2K_Super_35_full-ap)")
        layout.addRow("Allowed Write Formats:", self.wnr_allowed_formats_edit)
        
        self.wnr_allowed_formats_combo = QtWidgets.QComboBox()
        self._populate_combobox(self.wnr_allowed_formats_combo, self.dropdown_options.get('write_node_resolution', {}).get('allowed_formats_options'))
        add_format_button = QtWidgets.QPushButton("Add Example Format")
        add_format_button.clicked.connect(lambda: self.wnr_allowed_formats_edit.setText(
            (self.wnr_allowed_formats_edit.text() + "," if self.wnr_allowed_formats_edit.text() else "") + self.wnr_allowed_formats_combo.currentText()
        ))
        format_selection_layout = QtWidgets.QHBoxLayout()
        format_selection_layout.addWidget(self.wnr_allowed_formats_combo)
        format_selection_layout.addWidget(add_format_button)
        layout.addRow("Format Examples:", format_selection_layout)

        self.wnr_severity_combo = QtWidgets.QComboBox()
        self._populate_combobox(self.wnr_severity_combo, self.dropdown_options.get('severity_options'))
        layout.addRow("Severity:", self.wnr_severity_combo)

        # self.tabs.addTab(tab, "Write Node Resolution") # Old way
        self.category_list.addItem("Write Node Resolution")
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

    def create_channels_tab_write_node(self):
        """ Create tab for Write Node Channels and Layer Management rules. """
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(tab)

        self.ch_require_rgba_check = QtWidgets.QCheckBox("Require RGBA channels in Write nodes")
        layout.addRow(self.ch_require_rgba_check)

        self.ch_warn_rgb_only_check = QtWidgets.QCheckBox("Warn if only RGB channels (no Alpha) in Write nodes")
        layout.addRow(self.ch_warn_rgb_only_check)
        
        self.ch_warn_extra_channels_check = QtWidgets.QCheckBox("Warn on extra channels (beyond RGBA) in Write nodes")
        layout.addRow(self.ch_warn_extra_channels_check)

        self.ch_severity_combo = QtWidgets.QComboBox()
        self._populate_combobox(self.ch_severity_combo, self.dropdown_options.get('severity_options'))
        layout.addRow("Severity (Channel Issues):", self.ch_severity_combo)

        # self.tabs.addTab(tab, "Write Node Channels") # Old way
        self.category_list.addItem("Write Node Channels")
        self.settings_stack.addWidget(tab)

    def create_render_settings_tab_write_node(self):
        """ Create tab for Write Node Render Settings rules. """
        tab = QtWidgets.QWidget()
        self.rs_layout = QtWidgets.QFormLayout(tab) 

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

        self._update_render_settings_ui(self.rs_file_type_combo.currentText())

        # self.tabs.addTab(tab, "Write Node Render Settings") # Old way
        self.category_list.addItem("Write Node Render Settings")
        self.settings_stack.addWidget(tab)

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

    def create_versioning_tab(self):
        """ Create tab for Write Node Versioning rules. """
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(tab)

        self.ver_require_token_check = QtWidgets.QCheckBox("Require Version Token in Filename")
        layout.addRow(self.ver_require_token_check)

        self.ver_token_regex_edit = QtWidgets.QLineEdit()
        layout.addRow("Version Token Regex:", self.ver_token_regex_edit)
        
        self.ver_token_regex_combo = QtWidgets.QComboBox()
        self._populate_combobox(self.ver_token_regex_combo, self.dropdown_options.get('versioning', {}).get('version_token_regex_examples'))
        self.ver_token_regex_combo.activated.connect(
            lambda: self.ver_token_regex_edit.setText(self.ver_token_regex_combo.currentText())
        )
        layout.addRow("Regex Examples:", self.ver_token_regex_combo)

        self.ver_severity_require_token_combo = QtWidgets.QComboBox()
        self._populate_combobox(self.ver_severity_require_token_combo, self.dropdown_options.get('severity_options'))
        layout.addRow("Severity (Require Token):", self.ver_severity_require_token_combo)
        
        # self.tabs.addTab(tab, "Write Node Versioning") # Old way
        self.category_list.addItem("Write Node Versioning")
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
    
    def generate_filename_convention(self): # This method seems out of place for RulesEditorWidget
        """
        Generate a filename convention based on the current settings.
        NOTE: This method's UI elements (sequence_combo, shot_spin, etc.) are not defined
        within RulesEditorWidget's __init__ or its tab creation methods.
        This suggests it might be from a previous version or intended for a different UI context.
        """
        # The following attributes are not defined in this class:
        # self.sequence_combo, self.shot_spin, self.desc_combo, self.pixel_combo, 
        # self.res_combo, self.color_combo, self.gamma_combo, self.fps_combo, 
        # self.version_spin, self.frame_spin, self.ext_combo, self.convention_label
        # This method will raise AttributeErrors if called.
        # For now, commenting out the problematic parts.
        print("generate_filename_convention called, but its UI elements are not defined in RulesEditorWidget.")
        return
        # sequence = self.sequence_combo.currentText()
        # shot = f"{self.shot_spin.value():04d}"
        # ... (rest of the original method) ...
        # self.convention_label.setText(f"Generated Convention: {convention}")


    def save_rules_to_yaml(self):
        """ Gathers data from UI elements and saves to rules.yaml. """
        rules_data = {}

        # --- File Paths & Naming ---
        fp_rules = {}
        fp_rules['relative_path_required'] = self.fp_relative_path_check.isChecked()
        fp_rules['severity_relative_path'] = self._get_combobox_value(self.fp_severity_relative_combo)
        
        # Save dynamic naming convention parts
        fp_rules['filename_template'] = self.fp_template_edit.text()
        fp_rules['filename_tokens'] = self._get_tokens_from_table() # Get current tokens from UI
        # Ensure regex is generated before saving if user hasn't clicked the button recently
        self._generate_regex_from_template_and_tokens()
        constructed_regex = self.fp_naming_pattern_regex_edit.text()
        if constructed_regex:
            fp_rules['naming_pattern_regex'] = constructed_regex # This is the constructed/validated regex
        
        fp_rules['severity_naming_pattern'] = self._get_combobox_value(self.fp_severity_naming_combo)
        rules_data['file_paths'] = fp_rules

        if hasattr(self, 'fr_consistency_check'): # Frame Range Tab
            fr_rules = {
                'check_consistency': self.fr_consistency_check.isChecked(),
                'check_missing_frames': self.fr_missing_frames_check.isChecked(),
                'check_rate_consistency': self.fr_rate_consistency_check.isChecked(),
                'default_fps': float(self._get_combobox_value(self.frame_rate_combo, value_type=float) or '24.0'), # Provide default if None
                'severity': self._get_combobox_value(self.fr_severity_combo)
            }
            rules_data['frame_range'] = fr_rules


        ni_rules = {}
        ni_rules['check_disabled_nodes'] = self.ni_check_disabled_nodes_check.isChecked()
        ni_rules['severity_disabled_nodes'] = self._get_combobox_value(self.ni_severity_disabled_combo)
        rules_data['node_integrity'] = ni_rules
        
        wnr_rules = {}
        allowed_formats_text = self.wnr_allowed_formats_edit.text()
        if allowed_formats_text:
            wnr_rules['allowed_formats'] = [fmt.strip() for fmt in allowed_formats_text.split(',') if fmt.strip()]
        wnr_rules['severity'] = self._get_combobox_value(self.wnr_severity_combo)
        rules_data['write_node_resolution'] = wnr_rules

        cs_rules = {'Read': {}, 'Write': {}}
        read_allowed_text = self.cs_read_allowed_edit.text()
        if read_allowed_text:
            cs_rules['Read']['allowed'] = [cs.strip() for cs in read_allowed_text.split(',') if cs.strip()]
        cs_rules['Read']['severity'] = self._get_combobox_value(self.cs_read_severity_combo)
        
        write_allowed_text = self.cs_write_allowed_edit.text()
        if write_allowed_text:
            cs_rules['Write']['allowed'] = [cs.strip() for cs in write_allowed_text.split(',') if cs.strip()]
        cs_rules['Write']['severity'] = self._get_combobox_value(self.cs_write_severity_combo)
        rules_data['colorspaces'] = cs_rules

        ch_rules_write = {} # Changed from {'Write':{}} to directly store for 'channels' key
        ch_rules_write['require_rgba'] = self.ch_require_rgba_check.isChecked()
        ch_rules_write['warn_on_rgb_only'] = self.ch_warn_rgb_only_check.isChecked()
        ch_rules_write['warn_on_extra_channels'] = self.ch_warn_extra_channels_check.isChecked()
        ch_rules_write['severity'] = self._get_combobox_value(self.ch_severity_combo) 
        rules_data['channels'] = ch_rules_write # Store under 'channels' directly

        rs_rules_write = {'file_type_rules': {}} # Changed from {'Write':{...}}
        selected_file_type = self._get_combobox_value(self.rs_file_type_combo)
        if selected_file_type and hasattr(self, 'rs_dynamic_widgets'): 
            type_specific_rules = {}
            for knob_name, widget_obj in self.rs_dynamic_widgets.items():
                if isinstance(widget_obj, QtWidgets.QComboBox):
                    type_specific_rules[knob_name] = [self._get_combobox_value(widget_obj)] 
            if type_specific_rules:
                 rs_rules_write['file_type_rules'][selected_file_type] = type_specific_rules
        rs_rules_write['severity'] = self._get_combobox_value(self.rs_severity_combo)
        rules_data['render_settings'] = {'Write': rs_rules_write} # Keep 'Write' key here as per nuke_validator.py
        
        ver_rules = {}
        ver_rules['require_version_token'] = self.ver_require_token_check.isChecked()
        if self.ver_token_regex_edit.text():
            ver_rules['version_token_regex'] = self.ver_token_regex_edit.text()
        ver_rules['severity_require_token'] = self._get_combobox_value(self.ver_severity_require_token_combo)
        rules_data['versioning'] = ver_rules

        vn_rules = {}
        vn_rules['warn_if_ip_active'] = self.vn_warn_ip_active_check.isChecked()
        vn_rules['severity'] = self._get_combobox_value(self.vn_severity_combo)
        rules_data['viewer_nodes'] = vn_rules

        se_rules_exp = {}
        se_rules_exp['check_for_errors'] = self.se_check_expression_errors_check.isChecked()
        se_rules_exp['severity'] = self._get_combobox_value(self.se_severity_expression_combo)
        rules_data['expressions_errors'] = se_rules_exp

        se_rules_read = {}
        se_rules_read['check_existence'] = self.se_check_read_file_existence_check.isChecked()
        se_rules_read['severity'] = self._get_combobox_value(self.se_severity_read_file_combo)
        rules_data['read_file_errors'] = se_rules_read
        
        try:
            with open(self.rules_yaml_path, 'w') as f:
                yaml.dump(rules_data, f, sort_keys=False, indent=2)
            print(f"Rules saved to {self.rules_yaml_path}")
        except Exception as e:
            print(f"Error saving rules to {self.rules_yaml_path}: {e}")
            QtWidgets.QMessageBox.critical(self, "Save Error", f"Could not save rules: {e}")

    def load_rules_from_yaml(self):
        """ Loads rules from rules.yaml and populates the UI elements. """
        loaded_rules = self._load_yaml_file(self.rules_yaml_path) or {}

        # --- File Paths & Naming ---
        fp_rules = loaded_rules.get('file_paths', {})
        self.fp_relative_path_check.setChecked(fp_rules.get('relative_path_required', False))
        self._populate_combobox(self.fp_severity_relative_combo, self.dropdown_options.get('severity_options'), fp_rules.get('severity_relative_path'))

        # Load dynamic naming convention parts
        self.filename_template = fp_rules.get('filename_template', DEFAULT_FILENAME_TEMPLATE)
        self.fp_template_edit.setText(self.filename_template)
        
        loaded_tokens = fp_rules.get('filename_tokens')
        if loaded_tokens and isinstance(loaded_tokens, dict):
             # Ensure all default tokens are present, update with loaded if they exist
            self.filename_tokens = DEFAULT_NAMING_TOKENS.copy() # Start with defaults
            for token_name, token_data in loaded_tokens.items():
                if token_name in self.filename_tokens: # Update existing default token
                    self.filename_tokens[token_name].update(token_data)
                else: # Add new custom token if not in defaults (less common for this design)
                    self.filename_tokens[token_name] = token_data
        else: # Fallback to defaults if not found or invalid format
            self.filename_tokens = DEFAULT_NAMING_TOKENS.copy()
            
        self._populate_token_table(self.filename_tokens) # Populate table from loaded/default tokens
        
        # Load or generate the constructed regex
        constructed_regex = fp_rules.get('naming_pattern_regex', "") # This key now stores the constructed one
        if constructed_regex:
            self.fp_naming_pattern_regex_edit.setText(constructed_regex)
        else:
            # If no pre-constructed regex, generate it from loaded template and tokens
            self._generate_regex_from_template_and_tokens()
            
        self._populate_combobox(self.fp_severity_naming_combo, self.dropdown_options.get('severity_options'), fp_rules.get('severity_naming_pattern'))

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
        self._populate_combobox(self.ver_severity_require_token_combo, self.dropdown_options.get('severity_options'), ver_rules.get('severity_require_token'))

        vn_rules = loaded_rules.get('viewer_nodes', {})
        self.vn_warn_ip_active_check.setChecked(vn_rules.get('warn_if_ip_active', False))
        self._populate_combobox(self.vn_severity_combo, self.dropdown_options.get('severity_options'), vn_rules.get('severity'))

        se_rules_exp = loaded_rules.get('expressions_errors', {})
        self.se_check_expression_errors_check.setChecked(se_rules_exp.get('check_for_errors', False))
        self._populate_combobox(self.se_severity_expression_combo, self.dropdown_options.get('severity_options'), se_rules_exp.get('severity'))

        se_rules_read = loaded_rules.get('read_file_errors', {})
        self.se_check_read_file_existence_check.setChecked(se_rules_read.get('check_existence', False))
        self._populate_combobox(self.se_severity_read_file_combo, self.dropdown_options.get('severity_options'), se_rules_read.get('severity'))
        
        print(f"Rules loaded from {self.rules_yaml_path}")