#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test script for Nuke Validator
"""

import nuke
import nuke_validator
import os

def create_test_script():
    """
    Create a test Nuke script with known issues
    """
    # Clear the current script
    nuke.scriptClear()
    
    # Create a Read node with incorrect colorspace
    read_node = nuke.nodes.Read(file="test.jpg", colorspace="XYZ")
    read_node.setName("TestRead")
    
    # Create a Write node with incorrect path format
    write_node = nuke.nodes.Write(file="output/test.exr", colorspace="XYZ")
    write_node.setName("TestWrite")
    
    # Create a complex node tree
    for i in range(15):
        blur = nuke.nodes.Blur()
        blur.setName(f"Blur{i}")
    
    print("Created test script with known issues")

def test_validator():
    """
    Test the validator with the test script
    """
    # Create test script
    create_test_script()
    
    # Initialize validator
    validator = nuke_validator.NukeValidator()
    
    # Validate script
    success, issues = validator.validate_script()
    
    # Print report
    print(validator.generate_report())
    
    # Fix issues
    if issues and nuke.ask("Would you like to fix the issues automatically?"):
        fixed = validator.fix_issues()
        print(f"\nFixed {fixed} issues.")
        
        # Generate new report
        success, _ = validator.validate_script()
        print(validator.generate_report())
    
    # Exit with appropriate status
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    test_validator()