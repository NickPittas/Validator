# Filename Validation Consolidation Tasks

## Relevant Files

- `z:\Python\Validator\nuke_validator.py` - Contains the main validation logic for filenames including the core validation methods.
- `z:\Python\Validator\nuke_validator_ui.py` - Contains UI-related validation and regex generation logic.
- `z:\Python\Validator\Sphere.yaml` - Contains the token definitions used for validation.
- `z:\Python\Validator\tests\test_validation.py` - Tests for the validation functionality.

### Notes

- The goal is to implement a unified approach to filename validation that first uses the full regex pattern and then falls back to token-by-token validation for detailed error reporting.
- The current codebase has multiple redundant validation methods that should be consolidated.
- We should ensure the validation logic works with the existing token definitions in the YAML without requiring modifications to the YAML file.

## Tasks

- [x] 1.0 Analyze Current Validation Methods
  - [x] 1.1 Identify all methods that perform filename validation
  - [x] 1.2 Map dependencies and relationships between validation methods
  - [x] 1.3 Document the inputs and outputs of each validation method
  - [x] 1.4 Identify which methods are redundant and can be removed
  - [x] 1.5 Trace the validation flow from UI to backend processing

- [x] 2.0 Design Unified Validation Approach
  - [x] 2.1 Create a new centralized validation method that takes filename and token definitions
  - [x] 2.2 Design validation flow: full regex first, then token-by-token validation
  - [x] 2.3 Plan the error reporting structure for detailed feedback
  - [x] 2.4 Define interfaces for validation method to ensure backward compatibility
  - [ ] 2.5 Design test cases to verify the new validation approach

- [x] 3.0 Implement Token-by-Token Validation
  - [x] 3.1 Create a method to parse token definitions from YAML
  - [x] 3.2 Implement parsing of each token type (static, spinner, multiselect, etc.)
  - [x] 3.3 Create method to validate each token individually against its regex
  - [x] 3.4 Implement separator validation between tokens
  - [x] 3.5 Generate specific, detailed error messages for each validation failure
  - [x] 3.6 Handle special cases like version tokens correctly

- [x] 4.0 Remove Redundant Validation Methods
  - [x] 4.1 Replace calls to deprecated validation methods with the new unified method
  - [x] 4.2 Remove deprecated _validate_tokens method
  - [x] 4.3 Ensure backward compatibility with existing validation calls
  - [x] 4.4 Update documentation to reflect changes

- [x] 5.0 Improve Error Reporting
  - [x] 5.1 Enhance error messages with detailed token information
  - [x] 5.2 Provide specific error messages for common filename issues
  - [x] 5.3 Ensure errors are selectable and copyable in UI
  - [x] 5.4 Include suggestions for corrections in error messages

- [ ] 6.0 Testing and Integration
  - [ ] 6.1 Test with a variety of valid and invalid filenames
  - [ ] 6.2 Verify that error messages are clear and helpful
  - [ ] 6.3 Test integration with UI components
  - [ ] 6.4 Check for performance issues with large files or complex patterns
  - [ ] 6.5 Update existing tests to use the new validation methods
