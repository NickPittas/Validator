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

FILENAME_TOKENS = [
    {
        "name": "sequence",
        "label": "<sequence>",
        "regex_template": "[A-Z]{{{n}}}",
        "control": "spinner",
        "min": 2,
        "max": 8,
        "default": 4,
        "desc": "Uppercase sequence abbreviation"
    },
    {
        "name": "shotNumber",
        "label": "<shotNumber>",
        "regex_template": "\\d{{{n}}}",
        "control": "spinner",
        "min": 2,
        "max": 8,
        "default": 4,
        "desc": "Shot number (digits)"
    },
    {
        "name": "description",
        "label": "<description>",
        "regex_template": "[a-zA-Z0-9]+(?:[-a-zA-Z0-9]+)*",
        "control": "static",
        "desc": "Description (letters, numbers, hyphens)"
    },
    {
        "name": "pixelMappingName",
        "label": "<pixelMappingName>",
        "regex_template": "(LL180|LL360)",
        "control": "dropdown",
        "options": ["LL180", "LL360", "none"],
        "desc": "Pixel mapping name"
    },
    {
        "name": "resolution",
        "label": "<resolution>",
        "regex_template": "\\d{1,2}k",
        "control": "static",
        "desc": "Resolution abbreviation (e.g., 1k, 4k)"
    },
    {
        "name": "colorspaceGamma",
        "label": "<colorspaceGamma>",
        "regex_template": "(r709|sRGB|ap0|ap1|p3|rec2020)(lin|log|g22|g24|g26)",
        "control": "dropdown",
        "options": ["r709g22", "sRGBg24", "ap0log", "ap1lin", "p3g26", "none"],
        "desc": "Colorspace and gamma"
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
        "regex_template": "v\\d{{{n}}}",
        "control": "spinner",
        "min": 2,
        "max": 9,
        "default": 3,
        "desc": "Version (v + digits)"
    },
    {
        "name": "frame_padding",
        "label": "<frame_padding>",
        "regex_template": "\\d{{{min,max}}}",
        "control": "spinner_range",
        "min": 4,
        "max": 8,
        "default": 4,
        "desc": "Frame number padding"
    },
    {
        "name": "extension",
        "label": "<extension>",
        "regex_template": "(?i)(jpg|jpeg|png|mxf|mov|exr)",
        "control": "dropdown",
        "options": ["jpg", "jpeg", "png", "mxf", "mov", "exr"],
        "desc": "File extension"
    },
]

class FilenameTokenWidget(QtWidgets.QWidget):
    """
    Widget for a single token in the template builder.
    Shows the token label and, if needed, a control (spinner/dropdown).
    """
    def __init__(self, token_def, parent=None):
        super().__init__(parent)
        self.token_def = token_def
        self.layout = QtWidgets.QHBoxLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.label = QtWidgets.QLabel(token_def["label"])
        self.layout.addWidget(self.label)
        self.control = None
        if token_def["control"] == "spinner":
            self.control = QtWidgets.QSpinBox()
            self.control.setMinimum(token_def["min"])
            self.control.setMaximum(token_def["max"])
            self.control.setValue(token_def["default"])
            self.layout.addWidget(self.control)
        elif token_def["control"] == "spinner_range":
            self.control = QtWidgets.QSpinBox()
            self.control.setMinimum(token_def["min"])
            self.control.setMaximum(token_def["max"])
            self.control.setValue(token_def["default"])
            self.layout.addWidget(self.control)
        elif token_def["control"] == "dropdown":
            self.control = QtWidgets.QComboBox()
            self.control.addItems(token_def["options"])
            self.layout.addWidget(self.control)
        # else: static, no control
        self.remove_btn = QtWidgets.QToolButton()
        self.remove_btn.setText("✕")
        self.remove_btn.setToolTip("Remove token")
        self.layout.addWidget(self.remove_btn)
        self.setLayout(self.layout)

    def get_token_config(self):
        # Return dict with token name and current control value (if any)
        value = None
        if self.control:
            if isinstance(self.control, QtWidgets.QSpinBox):
                value = self.control.value()
            elif isinstance(self.control, QtWidgets.QComboBox):
                value = self.control.currentText()
        return {"name": self.token_def["name"], "value": value}

class SeparatorWidget(QtWidgets.QWidget):
    """Widget for a separator (e.g., _, ., -) in the template builder."""
    def __init__(self, sep, parent=None):
        super().__init__(parent)
        self.sep = sep
        self.layout = QtWidgets.QHBoxLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.label = QtWidgets.QLabel(sep)
        self.label.setStyleSheet("font-weight: bold; font-size: 16px;")
        self.layout.addWidget(self.label)
        self.remove_btn = QtWidgets.QToolButton()
        self.remove_btn.setText("✕")
        self.remove_btn.setToolTip("Remove separator")
        self.layout.addWidget(self.remove_btn)
        self.setLayout(self.layout)
    def get_token_config(self):
        return {"separator": self.sep}

class FilenameTemplateBuilder(QtWidgets.QWidget):
    """
    Widget for building the filename template as a sequence of tokens and separators.
    Supports drag-and-drop reordering.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QtWidgets.QHBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(4)
        self.token_widgets: List[QtWidgets.QWidget] = []
        self.setAcceptDrops(True)
        self.setStyleSheet("background: #f7f7fa; border: 1px solid #b0b0b0; border-radius: 6px;")
        self.setLayout(self.layout)
    def add_token(self, token_def):
        widget = FilenameTokenWidget(token_def)
        widget.remove_btn.clicked.connect(lambda: self.remove_token(widget))
        widget.setToolTip(token_def["desc"])
        self.token_widgets.append(widget)
        self.layout.addWidget(widget)
        self.update()
        widget.installEventFilter(self)
    def add_separator(self, sep):
        widget = SeparatorWidget(sep)
        widget.remove_btn.clicked.connect(lambda: self.remove_token(widget))
        widget.setToolTip(f"Separator '{sep}'")
        self.token_widgets.append(widget)
        self.layout.addWidget(widget)
        self.update()
        widget.installEventFilter(self)
    def remove_token(self, widget):
        self.layout.removeWidget(widget)
        widget.deleteLater()
        self.token_widgets.remove(widget)
        self.update()
    def get_template_config(self):
        result = []
        for w in self.token_widgets:
            if isinstance(w, FilenameTokenWidget):
                result.append(w.get_token_config())
            elif isinstance(w, SeparatorWidget):
                result.append(w.get_token_config())
        return result
    def clear(self):
        for w in self.token_widgets:
            self.layout.removeWidget(w)
            w.deleteLater()
        self.token_widgets.clear()
        self.update()
    # Drag-and-drop support
    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Type.MouseButtonPress:
            self._drag_start_pos = event.pos()
        elif event.type() == QtCore.QEvent.Type.MouseMove and hasattr(self, '_drag_start_pos'):
            if (event.pos() - self._drag_start_pos).manhattanLength() > QtWidgets.QApplication.startDragDistance():
                mime = QtCore.QMimeData()
                idx = self.token_widgets.index(obj)
                mime.setData("application/x-tokenwidget-index", str(idx).encode())
                drag = QtGui.QDrag(obj)
                drag.setMimeData(mime)
                drag.exec()
        return super().eventFilter(obj, event)
    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-tokenwidget-index"):
            event.acceptProposedAction()
    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-tokenwidget-index"):
            event.acceptProposedAction()
    def dropEvent(self, event):
        if event.mimeData().hasFormat("application/x-tokenwidget-index"):
            from_idx = int(bytes(event.mimeData().data("application/x-tokenwidget-index")).decode())
            to_pos = event.position().toPoint() if hasattr(event, 'position') else event.pos()
            to_idx = 0
            for i, w in enumerate(self.token_widgets):
                if w.geometry().contains(to_pos):
                    to_idx = i
                    break
            if from_idx != to_idx:
                widget = self.token_widgets.pop(from_idx)
                self.token_widgets.insert(to_idx, widget)
                # Remove all widgets and re-add in new order
                for w in self.token_widgets:
                    self.layout.removeWidget(w)
                for w in self.token_widgets:
                    self.layout.addWidget(w)
                self.update()
            event.acceptProposedAction()

class FilenameRuleEditor(QtWidgets.QWidget):
    """
    Main widget for the filename rule editor, including token palette, template builder, and regex preview.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        # Token palette (now multi-row grid)
        palette_widget = QtWidgets.QWidget()
        palette_grid = QtWidgets.QGridLayout(palette_widget)
        palette_grid.setSpacing(4)
        palette_grid.setContentsMargins(0,0,0,0)
        palette_grid.addWidget(QtWidgets.QLabel("Tokens:"), 0, 0, 1, 2)
        max_cols = 5
        row = 1
        col = 0
        self.token_buttons = []
        for i, token_def in enumerate(FILENAME_TOKENS):
            btn = QtWidgets.QPushButton(token_def["label"])
            btn.setToolTip(token_def["desc"])
            btn.setMinimumWidth(90)
            btn.setMinimumHeight(32)
            btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
            btn.clicked.connect(lambda _, td=token_def: self.add_token_to_template(td))
            palette_grid.addWidget(btn, row, col)
            self.token_buttons.append(btn)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        # Separator buttons
        sep_row = row + 1
        sep_col = 0
        for sep in ["_", ".", "-", " "]:
            sep_btn = QtWidgets.QPushButton(f"'{sep}'")
            sep_btn.setToolTip(f"Insert separator '{sep}'")
            sep_btn.setMinimumWidth(40)
            sep_btn.setMinimumHeight(32)
            sep_btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
            sep_btn.clicked.connect(lambda _, s=sep: self.add_separator_to_template(s))
            palette_grid.addWidget(sep_btn, sep_row, sep_col)
            sep_col += 1
        layout.addWidget(palette_widget)
        # Template builder
        self.template_builder = FilenameTemplateBuilder()
        layout.addWidget(self.template_builder)
        # Clear button
        clear_btn = QtWidgets.QPushButton("Clear Template")
        clear_btn.setToolTip("Remove all tokens and separators from the template")
        clear_btn.clicked.connect(self.clear_and_update)
        layout.addWidget(clear_btn)
        # Regex preview with validation
        regex_layout = QtWidgets.QHBoxLayout()
        regex_layout.addWidget(QtWidgets.QLabel("Regex Preview:"))
        self.regex_edit = QtWidgets.QLineEdit()
        self.regex_edit.setReadOnly(False)
        regex_layout.addWidget(self.regex_edit)
        self.regex_status_icon = QtWidgets.QLabel()
        self.regex_status_icon.setFixedSize(20, 20)
        regex_layout.addWidget(self.regex_status_icon)
        layout.addLayout(regex_layout)
        # Example filename preview
        example_layout = QtWidgets.QHBoxLayout()
        example_layout.addWidget(QtWidgets.QLabel("Example Filename:"))
        self.example_edit = QtWidgets.QLineEdit()
        self.example_edit.setReadOnly(True)
        example_layout.addWidget(self.example_edit)
        layout.addLayout(example_layout)
        # Save/load buttons
        btn_layout = QtWidgets.QHBoxLayout()
        self.save_btn = QtWidgets.QPushButton("Save Template")
        self.load_btn = QtWidgets.QPushButton("Load Template")
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.load_btn)
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        # Connect
        self.template_builder.layout.setSpacing(4)
        self.template_builder.layout.setContentsMargins(4,4,4,4)
        self.template_builder.layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self.save_btn.clicked.connect(self.save_template)
        self.load_btn.clicked.connect(self.load_template)
        # Update regex and example when template changes
        self.template_builder.layout.installEventFilter(self)
        self.regex_edit.textChanged.connect(self.on_regex_edit)
        self.template_builder.layout.parentWidget().installEventFilter(self)
        # Initial update
        self.update_regex()
    def add_token_to_template(self, token_def):
        self.template_builder.add_token(token_def)
        self.update_regex()
    def add_separator_to_template(self, sep):
        self.template_builder.add_separator(sep)
        self.update_regex()
    def clear_and_update(self):
        self.template_builder.clear()
        self.update_regex()
    def update_regex(self):
        regex_parts = []
        example_parts = []
        # Get allowed resolution from Resolution rule (single value)
        allowed_resolution = None
        try:
            from nuke_validator_ui import RulesEditorWidget
            rules_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rules.yaml")
            with open(rules_path, 'r') as f:
                rules = yaml.safe_load(f)
                allowed = rules.get('write_node_resolution', {}).get('allowed_formats', [])
                if allowed:
                    allowed_resolution = allowed[0]
        except Exception:
            allowed_resolution = "2K"
        for token_cfg in self.template_builder.get_template_config():
            if "separator" in token_cfg:
                regex_parts.append(re.escape(token_cfg["separator"]))
                example_parts.append(token_cfg["separator"])
            else:
                token = next((t for t in FILENAME_TOKENS if t["name"] == token_cfg["name"]), None)
                if not token:
                    continue
                if token["name"] == "resolution":
                    regex = re.escape(allowed_resolution) if allowed_resolution else token["regex_template"]
                    example = allowed_resolution or "2K"
                elif token["control"] == "spinner":
                    n = token_cfg["value"] or token["default"]
                    regex = token["regex_template"].replace("{n}", str(n))
                    example = ("A" * n) if token["name"] == "sequence" else ("0" * n)
                elif token["control"] == "spinner_range":
                    minv = token_cfg["value"] or token["min"]
                    regex = token["regex_template"].replace("{min,max}", f"{minv},{token['max']}")
                    example = "0" * minv
                elif token["control"] == "dropdown":
                    val = token_cfg["value"]
                    if val and val != "none":
                        regex = f"({val})"
                        example = val
                    else:
                        regex = token["regex_template"]
                        example = token["options"][0] if token["options"] else ""
                else:
                    regex = token["regex_template"]
                    example = token.get("examples", ["demo"])[0]
                regex_parts.append(regex)
                example_parts.append(str(example))
        regex_str = "^" + "".join(regex_parts) + "$"
        self.regex_edit.setText(regex_str)
        self.validate_regex(regex_str)
        self.example_edit.setText("".join(example_parts))
    def validate_regex(self, regex_str):
        import re
        try:
            re.compile(regex_str)
            self.regex_edit.setStyleSheet("border: 2px solid #4caf50;")
            self.regex_status_icon.setPixmap(QtGui.QPixmap(20, 20))
            self.regex_status_icon.setStyleSheet("background: #4caf50; border-radius: 10px;")
        except re.error:
            self.regex_edit.setStyleSheet("border: 2px solid #e53935;")
            self.regex_status_icon.setPixmap(QtGui.QPixmap(20, 20))
            self.regex_status_icon.setStyleSheet("background: #e53935; border-radius: 10px;")
    def eventFilter(self, obj, event):
        if event.type() in (QtCore.QEvent.Type.ChildRemoved, QtCore.QEvent.Type.ChildAdded, QtCore.QEvent.Type.LayoutRequest):
            self.update_regex()
        return super().eventFilter(obj, event)
    def save_template(self):
        import yaml
        config = {
            "template": self.template_builder.get_template_config(),
            "regex": self.regex_edit.text()
        }
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Template", "", "YAML Files (*.yaml);;JSON Files (*.json)")
        if path:
            with open(path, "w") as f:
                if path.endswith(".json"):
                    import json
                    json.dump(config, f, indent=2)
                else:
                    yaml.dump(config, f, sort_keys=False)
    def load_template(self):
        import yaml
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Template", "", "YAML Files (*.yaml);;JSON Files (*.json)")
        if path:
            with open(path, "r") as f:
                if path.endswith(".json"):
                    import json
                    config = json.load(f)
                else:
                    config = yaml.safe_load(f)
            self.template_builder.clear()
            for token_cfg in config.get("template", []):
                if "separator" in token_cfg:
                    self.template_builder.add_separator(token_cfg["separator"])
                else:
                    token = next((t for t in FILENAME_TOKENS if t["name"] == token_cfg["name"]), None)
                    if token:
                        self.template_builder.add_token(token)
                        widget = self.template_builder.token_widgets[-1]
                        if widget.control and token_cfg.get("value") is not None:
                            if isinstance(widget.control, QtWidgets.QSpinBox):
                                widget.control.setValue(token_cfg["value"])
                            elif isinstance(widget.control, QtWidgets.QComboBox):
                                idx = widget.control.findText(token_cfg["value"])
                                if idx >= 0:
                                    widget.control.setCurrentIndex(idx)
            self.update_regex()
    def on_regex_edit(self):
        # Optionally, validate regex or update preview
        self.validate_regex(self.regex_edit.text())

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
        self.create_path_structure_tab()

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

        # Filename Rule Editor
        self.filename_rule_editor = FilenameRuleEditor()
        convention_layout.addWidget(self.filename_rule_editor)

        convention_group.setLayout(convention_layout)
        main_tab_layout.addWidget(convention_group)
        
        main_tab_layout.addStretch()
        # self.tabs.addTab(tab, "File Path & Naming") # Old way
        self.category_list.addItem("File Path & Naming")
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

    def create_path_structure_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        # Load path_structures from rules.yaml
        path_structures = self._load_yaml_file(self.rules_yaml_path).get('path_structures', {})
        self.path_rule_editor = PathRuleEditor(path_structures=path_structures)
        layout.addWidget(self.path_rule_editor)
        tab.setLayout(layout)
        self.category_list.addItem("Path Structure")
        self.settings_stack.addWidget(tab)

    def save_rules_to_yaml(self):
        """ Gathers data from UI elements and saves to rules.yaml. """
        rules_data = {}
        # --- File Paths & Naming ---
        fp_rules = {}
        fp_rules['relative_path_required'] = self.fp_relative_path_check.isChecked()
        fp_rules['severity_relative_path'] = self._get_combobox_value(self.fp_severity_relative_combo)
        # Save dynamic naming convention parts
        fp_rules['filename_template'] = self.filename_rule_editor.regex_edit.text()
        fp_rules['filename_tokens'] = self.filename_rule_editor.template_builder.get_template_config()
        # Ensure regex is generated before saving if user hasn't clicked the button recently
        self.filename_rule_editor.update_regex()
        constructed_regex = self.filename_rule_editor.regex_edit.text()
        if constructed_regex:
            fp_rules['naming_pattern_regex'] = constructed_regex # This is the constructed/validated regex
        fp_rules['severity_naming_pattern'] = self._get_combobox_value(self.rs_severity_combo)
        rules_data['file_paths'] = fp_rules
        # Save path rule editor config
        if hasattr(self, 'path_rule_editor'):
            rules_data['path_rules'] = {
                'base_path': self.path_rule_editor.base_path_edit.text(),
                'shot_structure': self.path_rule_editor.shot_struct_combo.currentText(),
                'relative_path': self.path_rule_editor.rel_path_edit.text(),
                'tokens': {token: combo.currentText() for token, combo in self.path_rule_editor.token_controls.items()}
            }

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
        self.filename_rule_editor.regex_edit.setText(fp_rules.get('naming_pattern_regex', ""))
        self.filename_rule_editor.template_builder.clear()
        for token_cfg in fp_rules.get('filename_tokens', []):
            token = next((t for t in FILENAME_TOKENS if t["name"] == token_cfg["name"]), None)
            if token:
                self.filename_rule_editor.template_builder.add_token(token)
                if token_cfg.get("value") is not None:
                    widget = self.filename_rule_editor.template_builder.token_widgets[-1]
                    if isinstance(widget.control, QtWidgets.QSpinBox):
                        widget.control.setValue(token_cfg["value"])
                    elif isinstance(widget.control, QtWidgets.QComboBox):
                        idx = widget.control.findText(token_cfg["value"])
                        if idx >= 0:
                            widget.control.setCurrentIndex(idx)
            self.filename_rule_editor.update_regex()
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

class PathRuleEditor(QtWidgets.QWidget):
    """
    Widget for path validation rule editing: base path selector, relative path builder, live preview.
    """
    def __init__(self, parent=None, path_structures=None):
        super().__init__(parent)
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
            combo.setStyleSheet("background: #f0f7ff; border: 1px solid #b0c4de; border-radius: 4px; padding: 2px 6px;")
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
        if path_structures:
            for key, value in path_structures.items():
                self.shot_struct_combo.addItem(f"{key}: {value}", value)
        self.shot_struct_combo.setCurrentIndex(0)
        self.on_shot_struct_changed(self.shot_struct_combo.currentText())
    def browse_base_path(self):
        path = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Base Path")
        if path:
            self.base_path_edit.setText(path)
    def update_preview(self):
        struct_template = self.shot_struct_combo.currentData() or ""
        rel_path = struct_template
        for token, combo in self.token_controls.items():
            rel_path = rel_path.replace(token, combo.currentText())
        self.rel_path_edit.setText(rel_path)
        base = self.base_path_edit.text().rstrip("/\\")
        rel = rel_path.lstrip("/\\")
        resolved = os.path.join(base, rel) if base and rel else base or rel
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
        # Example: parse <shot_name> from script name, fill other tokens as needed
        import nuke
        script_name = nuke.root().name()
        # Simple pattern: SHOT_0010_description_comp_v01.nk
        import re
        m = re.search(r"([A-Za-z]+_\d{4})", script_name)
        if m:
            self.token_controls["<shot_name>"].setCurrentText(m.group(1))
        # Optionally parse <version> from vXX or vXXX
        m2 = re.search(r"v(\d{2,4})", script_name)
        if m2:
            self.token_controls["<version>"].setCurrentText(f"v{m2.group(1)}")
        # You can add more parsing logic for <resolution> if needed
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