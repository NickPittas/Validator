#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Nuke Validator Setup Script
"""

import os
import sys
import shutil
from pathlib import Path

def install():
    """
    Install the Nuke Validator
    """
    # Get the current directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Get the Nuke plugins directory
    nuke_plugins_dir = os.path.join(os.path.expanduser("~"), "NukePlugins")
    
    # Create the Nuke plugins directory if it doesn't exist
    if not os.path.exists(nuke_plugins_dir):
        os.makedirs(nuke_plugins_dir)
    
    # Copy the validator files to the Nuke plugins directory
    for file in ["nuke_validator.py", "nuke_validator_ui.py", "rules.yaml", "README.md"]:
        src = os.path.join(current_dir, file)
        dst = os.path.join(nuke_plugins_dir, file)
        
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"Copied {src} to {dst}")
    
    # Create a shortcut in the Nuke menu
    menu_script = """#!/usr/bin/env python
# -*- coding: utf-8 -*-

import nuke
from nuke_validator_ui import create_validator_ui

def main():
    create_validator_ui()

if __name__ == '__main__':
    main()
"""
    
    with open(os.path.join(nuke_plugins_dir, "Nuke Validator.py"), "w") as f:
        f.write(menu_script)
    
    print(f"Installed Nuke Validator to {nuke_plugins_dir}")
    print("You can now run the validator from the Nuke menu or by executing 'nuke.load('Nuke Validator')' in the script editor.")

def uninstall():
    """
    Uninstall the Nuke Validator
    """
    # Get the Nuke plugins directory
    nuke_plugins_dir = os.path.join(os.path.expanduser("~"), "NukePlugins")
    
    # Remove the validator files
    for file in ["nuke_validator.py", "nuke_validator_ui.py", "rules.yaml", "README.md", "Nuke Validator.py"]:
        dst = os.path.join(nuke_plugins_dir, file)
        
        if os.path.exists(dst):
            os.remove(dst)
            print(f"Removed {dst}")
    
    # Remove the Nuke plugins directory if it's empty
    if os.path.exists(nuke_plugins_dir) and not os.listdir(nuke_plugins_dir):
        os.rmdir(nuke_plugins_dir)
        print(f"Removed empty directory {nuke_plugins_dir}")
    
    print("Uninstalled Nuke Validator.")

def main():
    """
    Main function to handle installation and uninstallation
    """
    if len(sys.argv) > 1 and sys.argv[1] == "uninstall":
        uninstall()
    else:
        install()

if __name__ == '__main__':
    main()