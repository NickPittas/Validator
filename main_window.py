#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Main window for the Nuke Validator UI
"""

import sys
import os
import nuke # For Nuke specific operations if needed directly
from PySide6 import QtWidgets, QtCore, QtGui
from functools import partial

# Assuming Validator package is in sys.path or PYTHONPATH
from nuke_validator_ui import RulesEditorWidget, RuleItemWidget
from nuke_validator import NukeValidator

# Helper to create simple colored pixmaps for status icons
def create_colored_pixmap(color, size=20):
    pixmap = QtGui.QPixmap(size, size)
    pixmap.fill(color)
    return pixmap

class MainWindow(QtWidgets.QMainWindow):
    """
    Main window for the Nuke Validator UI
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint, True)
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.rules_file_path = os.path.join(script_dir, "rules.yaml")

        if not os.path.exists(self.rules_file_path):
            # If rules.yaml is not found next to the script, print a warning.
            # Nuke's pluginPath can be complex, so we rely on co-location.
            print(f"Warning: MainWindow could not locate 'rules.yaml'. Expected at: {self.rules_file_path}")
            # self.validator will be initialized but might not have rules if the file is missing.
            # The NukeValidator class itself might handle a missing rules file gracefully or error.
        
        self.validator = NukeValidator(rules_file=self.rules_file_path)
        # NukeValidator's __init__ already sets self.rules from rules_file.
        # We need to ensure self.validator.rules_file_path is correctly set for reloads.
        self.validator.rules_file_path = self.rules_file_path

        self.setWindowTitle("Nuke Validator - Integrated")
        self.setMinimumSize(1000, 700)
        
        main_widget = QtWidgets.QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QtWidgets.QVBoxLayout(main_widget)

        # --- Controls Layout (Top Buttons) ---
        controls_layout = QtWidgets.QHBoxLayout()
        self.run_validation_button = QtWidgets.QPushButton("Run Validation")
        self.run_validation_button.clicked.connect(self.run_validation)
        controls_layout.addWidget(self.run_validation_button)

        self.edit_rules_button = QtWidgets.QPushButton("Edit Rules")
        self.edit_rules_button.setCheckable(True) # Make it a toggle button
        self.edit_rules_button.clicked.connect(self.toggle_rules_editor)
        controls_layout.addWidget(self.edit_rules_button)
        
        controls_layout.addStretch()
        main_layout.addLayout(controls_layout)

        # --- Main Content Splitter ---
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        main_layout.addWidget(self.splitter)

        # Rules Editor (Left Pane of Splitter)
        self.rules_editor_widget = RulesEditorWidget()
        # Ensure RulesEditorWidget uses the same rules file path
        self.rules_editor_widget.rules_yaml_path = self.rules_file_path
        self.rules_editor_widget.load_rules_from_yaml() # Load its content
        self.splitter.addWidget(self.rules_editor_widget)
        self.rules_editor_widget.setVisible(False) # Initially hidden

        results_container = QtWidgets.QWidget()
        results_layout = QtWidgets.QVBoxLayout(results_container)
        results_layout.setContentsMargins(0,0,0,0)
        
        results_label = QtWidgets.QLabel("Validation Results:")
        results_layout.addWidget(results_label)
        
        self.results_list_widget = QtWidgets.QListWidget()
        results_layout.addWidget(self.results_list_widget)
        
        self.splitter.addWidget(results_container)
        self.splitter.setSizes([400, 600])

        self.statusBar().showMessage("Ready")

        # Define status icons using PNGs
        icon_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")
        def load_png_icon(path, size=16):
            pixmap = QtGui.QPixmap(path)
            if not pixmap.isNull():
                return pixmap.scaled(size, size, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation)
            return QtGui.QPixmap(size, size)
        self.status_icons = {
            "success": load_png_icon(os.path.join(icon_dir, "success.png")),
            "warning": load_png_icon(os.path.join(icon_dir, "warning.png")),
            "error": load_png_icon(os.path.join(icon_dir, "error.png")),
            "info": load_png_icon(os.path.join(icon_dir, "info.png")),
            "default": load_png_icon(os.path.join(icon_dir, "info.png")),
        }

    def toggle_rules_editor(self, checked):
        """Shows or hides the rules editor panel."""
        self.rules_editor_widget.setVisible(checked)
        if checked:
            self.edit_rules_button.setText("Hide Rules Editor")
            # Optional: reload rules in editor when shown, in case of external changes
            # self.rules_editor_widget.load_rules_from_yaml()
        else:
            self.edit_rules_button.setText("Edit Rules")
            # Optional: ensure splitter restores space to results if editor was wide
            # This might need adjustment based on desired behavior
            # current_sizes = self.splitter.sizes()
            # if len(current_sizes) == 2 and current_sizes[0] > 0 : # if editor was visible
            #    self.splitter.setSizes([0, current_sizes[0] + current_sizes[1]])


    def run_validation(self):
        self.statusBar().showMessage("Running validation...")
        self.results_list_widget.clear()

        # Always reload rules from YAML before validating
        if hasattr(self.validator, 'rules_file_path') and self.validator.rules_file_path:
            self.validator.rules = self.validator._load_rules(self.validator.rules_file_path)
        elif not self.validator.rules:
            print("Warning: No rules loaded in validator and no rules file path set for reloading.")
            self.statusBar().showMessage("Validation failed: No rules loaded.")
            list_item = QtWidgets.QListWidgetItem()
            rule_item_widget = RuleItemWidget("Setup Error")
            rule_item_widget.name_label.setText("<b style='color:#b00020;'>Validator Setup</b>")
            rule_item_widget.status_label.setText("No rules loaded and no rules file path set.")
            rule_item_widget.status_icon.setPixmap(self.status_icons.get("error"))
            rule_item_widget.status_icon.setFixedSize(18, 18)
            rule_item_widget.setStyleSheet("background:#fff; border-left:5px solid #b00020; border-radius:6px; padding:6px 6px 6px 12px; margin-bottom:4px;")
            rule_item_widget.name_label.setStyleSheet("font-weight:bold; font-size:13px; color:#222;")
            rule_item_widget.status_label.setStyleSheet("color:#222; font-size:11px;")
            self.results_list_widget.addItem(list_item)
            self.results_list_widget.setItemWidget(list_item, rule_item_widget)
            list_item.setSizeHint(rule_item_widget.sizeHint())
            return

        try:
            pass
        except RuntimeError as e:
            QtWidgets.QMessageBox.warning(self, "Script Not Saved", f"Could not save the Nuke script: {e}\nValidation will proceed but some checks might be affected.")

        success, issues = self.validator.validate_script()

        if not issues:
            list_item = QtWidgets.QListWidgetItem()
            rule_item_widget = RuleItemWidget("Overall Status")
            rule_item_widget.name_label.setText("<b style='color:#388e3c;'>Validation Status</b>")
            rule_item_widget.status_label.setText("<span style='color:#388e3c;'>No issues found!</span>")
            rule_item_widget.status_icon.setPixmap(self.status_icons.get("success"))
            rule_item_widget.status_icon.setFixedSize(18, 18)
            rule_item_widget.progress_bar.setVisible(False)
            rule_item_widget.setStyleSheet("background:#fff; border-left:5px solid #388e3c; border-radius:6px; padding:6px 6px 6px 12px; margin-bottom:4px;")
            rule_item_widget.name_label.setStyleSheet("font-weight:bold; font-size:13px; color:#222;")
            rule_item_widget.status_label.setStyleSheet("color:#222; font-size:11px;")
            self.results_list_widget.addItem(list_item)
            self.results_list_widget.setItemWidget(list_item, rule_item_widget)
            list_item.setSizeHint(rule_item_widget.sizeHint())
            self.statusBar().showMessage("Validation complete: No issues found.", 5000)
        else:
            for issue_data in issues:
                list_item = QtWidgets.QListWidgetItem()
                severity = issue_data.get('severity', 'info').lower()
                border_color = {
                    'error': '#b00020',
                    'warning': '#ff9800',
                    'success': '#388e3c',
                    'info': '#1976d2'
                }.get(severity, '#1976d2')
                node_color = border_color
                node_name = issue_data.get('node', 'N/A')
                rule_type = issue_data.get('type', 'Issue')
                # Show token name if present
                token = issue_data.get('token')
                rule_name = f"{rule_type} on <b style='color:{node_color};'>{node_name}</b>"
                if token:
                    rule_name = f"<b>{token}</b> - {rule_name}"
                rule_item_widget = RuleItemWidget(rule_name)
                rule_item_widget.name_label.setText(rule_name)
                details = f"<div style='text-align:justify; line-height:1.4;'><b>Current:</b> <span style='color:{node_color};'>{issue_data.get('current', '')}</span>"
                if 'expected' in issue_data:
                    details += f"<br><b>Expected:</b> <span style='color:#222;'>{issue_data.get('expected')}</span>"
                elif 'allowed' in issue_data:
                    details += f"<br><b>Allowed:</b> <span style='color:#222;'>{issue_data.get('allowed')}</span>"
                details += "</div>"
                rule_item_widget.status_label.setText(details)
                rule_item_widget.status_icon.setPixmap(self.status_icons.get(severity, self.status_icons["default"]))
                rule_item_widget.status_icon.setFixedSize(18, 18)
                rule_item_widget.progress_bar.setVisible(False)
                rule_item_widget.setStyleSheet(f"background:#fff; border-left:5px solid {border_color}; border-radius:6px; padding:6px 6px 6px 12px; margin-bottom:4px;")
                rule_item_widget.name_label.setStyleSheet("font-weight:bold; font-size:13px; color:#222;")
                rule_item_widget.status_label.setStyleSheet("color:#222; font-size:11px;")
                # Tooltip for token issues
                if token and 'tooltip' in issue_data:
                    rule_item_widget.setToolTip(issue_data['tooltip'])
                if node_name and node_name != 'N/A':
                    goto_btn = QtWidgets.QPushButton("Go to Node")
                    goto_btn.setStyleSheet(f"padding:1px 8px; border-radius:5px; background:{node_color}; color:white; font-weight:bold; font-size:10px;")
                    goto_btn.clicked.connect(partial(self.goto_node, node_name))
                    rule_item_widget.layout().addWidget(goto_btn)
                # Auto-Fix button for token issues
                if issue_data.get('auto_fix'):
                    autofix_btn = QtWidgets.QPushButton("Auto-Fix")
                    autofix_btn.setStyleSheet("padding:1px 8px; border-radius:5px; background:#388e3c; color:white; font-weight:bold; font-size:10px;")
                    autofix_btn.clicked.connect(self.run_autofix)
                    rule_item_widget.layout().addWidget(autofix_btn)
                self.results_list_widget.addItem(list_item)
                self.results_list_widget.setItemWidget(list_item, rule_item_widget)
                list_item.setSizeHint(rule_item_widget.sizeHint())
            self.statusBar().showMessage(f"Validation complete: {len(issues)} issues found.", 5000)
        
    def goto_node(self, node_name):
        try:
            node = nuke.toNode(node_name)
            if node:
                # Deselect all, select this node
                for n in nuke.allNodes():
                    n['selected'].setValue(False)
                node['selected'].setValue(True)
                # Center and zoom node graph on this node
                if hasattr(nuke, 'zoomToNode'):
                    nuke.zoomToNode(node)
                if hasattr(nuke, 'zoomToFitSelected'):
                    nuke.zoomToFitSelected()
                if hasattr(nuke, 'centerOnNode'):
                    nuke.centerOnNode(node)
                if hasattr(nuke, 'showDag'):
                    nuke.showDag(node)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Node Navigation Error", f"Could not navigate to node '{node_name}': {e}")

    def run_autofix(self):
        fixed = self.validator.fix_issues()
        self.run_validation()
        QtWidgets.QMessageBox.information(self, "Auto-Fix", f"Auto-fix applied to {fixed} issues.")

_main_window_instance = None
# This function will be called by your menu.py as "Validator.launch_validator_for_nuke()"
# after this main_window.py module has registered itself as 'Validator' in sys.modules.
def launch_validator_for_nuke(for_nuke=True): # Renamed from launch_main_validator_window
    global _main_window_instance

    if _main_window_instance is not None and _main_window_instance.isVisible(): # Check isVisible
        _main_window_instance.show()
        _main_window_instance.raise_()
        _main_window_instance.activateWindow()
        return _main_window_instance

    if for_nuke:
        app_instance = QtWidgets.QApplication.instance()
        if app_instance is None:
            print("Error: QApplication instance not found. Cannot launch UI in Nuke.")
            if 'nuke' in sys.modules and hasattr(sys.modules['nuke'], 'critical') and sys.modules['nuke'].GUI:
                sys.modules['nuke'].critical("Error: QApplication instance not found. Cannot launch UI in Nuke.")
            return None
        
        if _main_window_instance and not _main_window_instance.isVisible():
            _main_window_instance.deleteLater()
            _main_window_instance = None

        _main_window_instance = MainWindow()
        _main_window_instance.show()
        return _main_window_instance
    else:
        # Standalone execution logic (for testing outside Nuke)
        app = QtWidgets.QApplication.instance()
        if not app:
            app = QtWidgets.QApplication(sys.argv)
        
        if _main_window_instance and not _main_window_instance.isVisible():
            _main_window_instance.deleteLater()
            _main_window_instance = None
            
        _main_window_instance = MainWindow()
        _main_window_instance.show()
        if not for_nuke:
            sys.exit(app.exec())
        return _main_window_instance

if __name__ == "__main__":
    # This allows running main_window.py directly for testing (outside Nuke)
    launch_validator_for_nuke(for_nuke=False)
else:
    # --- Module Registration ---
    # When Nuke imports/executes this main_window.py file (because its directory
    # is in a Nuke plugin path and __init__.py exists there), this 'else' block will run.
    # We register this main_window.py module object as 'Validator' in sys.modules.
    # This makes `launch_validator_for_nuke` (defined in this file) callable as
    # `Validator.launch_validator_for_nuke()` from your menu.py.
    
    # Ensure this module (main_window.py) is correctly identified.
    # __name__ will be 'main_window' when imported.
    if __name__ == 'main_window': # Or whatever Nuke names it when it loads it.
        # Only set sys.modules['Validator'] if __name__ is in sys.modules
        if __name__ in sys.modules:
            current_module_object = sys.modules[__name__]
            sys.modules['Validator'] = current_module_object
        # print(f"DEBUG: main_window.py (module '{__name__}') has registered itself as 'Validator' in sys.modules.")
        # print(f"DEBUG: 'Validator' in sys.modules: {'Validator' in sys.modules}")
        # print(f"DEBUG: sys.modules['Validator']: {sys.modules.get('Validator')}")
        # print(f"DEBUG: launch_validator_for_nuke available: {hasattr(sys.modules.get('Validator'), 'launch_validator_for_nuke')}")
    else:
        # This case might occur if Nuke loads it under a different name, or if __init__.py itself
        # was more complex and imported main_window. With a minimal __init__.py, Nuke should
        # load main_window.py as a module named 'main_window'.
        # If your menu.py is trying to `import main_window as Validator`, then this registration
        # might not be strictly necessary, but having it makes `Validator.launch_validator_for_nuke()`
        # work if Nuke just loads all .py files from the plugin path directory.
        print(f"DEBUG: main_window.py loaded, but __name__ is '{__name__}'. 'Validator' alias not set from here if name doesn't match expected.")
        # Fallback: if __name__ is not 'main_window' but this code is run (e.g. Nuke loads all .py files),
        # we can still try to register it.
        current_module_object = sys.modules[__name__]
        if 'Validator' not in sys.modules:
            sys.modules['Validator'] = current_module_object
            # print(f"DEBUG: Fallback registration: main_window.py (module '{__name__}') registered as 'Validator'.")
        # else:
            # print(f"DEBUG: 'Validator' already in sys.modules. Skipping registration by '{__name__}'.")