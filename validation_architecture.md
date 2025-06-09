# Nuke Validator Filename Validation Architecture

## Overview

This document describes the filename validation system in the Nuke Validator project, specifically how the UI and backend components integrate to provide consistent validation functionality.

## Components

### 1. UI Validation (`nuke_validator_ui.py`)

The UI component contains the primary, sophisticated validation logic in the `FilenameRuleEditor` class:

- **`_validate_filename_detailed()`**: The core validation method that performs token-by-token validation with specific error reporting.
- **Token-based approach**: Validates filenames against configurable templates composed of tokens.
- **Dynamic regex generation**: Creates regex patterns based on token configurations.
- **Detailed error reporting**: Provides specific error messages for each validation issue.

### 2. Backend Validation (`nuke_validator.py`)

The backend validator implements an integration approach:

- **Import-based design**: Imports the `FilenameRuleEditor` class from the UI module.
- **Sophisticated validation**: Uses the UI's validation logic by creating a temporary `FilenameRuleEditor` instance.
- **Fallback mechanism**: Implements `_basic_filename_validation()` for cases where UI import fails.
- **Error handling**: Robust exception handling for import failures and other issues.

### 3. FILENAME_TOKENS

The token definitions are maintained in the UI module and imported by the backend when needed:

- Each token defines a name, regex pattern, and examples.
- The backend loads these definitions to ensure consistency.

## Integration Flow

1. **UI Direct Use**:
   - User interacts with the `FilenameRuleEditor` in the UI.
   - Validation occurs directly using the `_validate_filename_detailed()` method.
   - Results are displayed in the UI.

2. **Backend Import Process**:
   - Backend needs to validate a filename.
   - It tries to import `FilenameRuleEditor` from `nuke_validator_ui`.
   - Creates a temporary editor instance.
   - Loads token configurations from rules.
   - Calls the UI's validation method.
   - Handles any errors during the process.

3. **Fallback Mechanism**:
   - If import fails or an error occurs, the backend falls back to `_basic_filename_validation()`.
   - This provides regex-based basic validation with pattern matching.

## Error Handling

1. **Import Failures**:
   - Backend catches `ImportError` and falls back to basic validation.
   - Provides diagnostic logging of import issues.

2. **Token Configuration Issues**:
   - Validates token configuration before attempting validation.
   - Handles missing or invalid token definitions.

3. **Runtime Exceptions**:
   - Catches and logs unexpected exceptions.
   - Provides user-friendly error messages.
   - Maintains stability by falling back to simple validation when needed.

## Best Practices

1. **Single Source of Truth**:
   - The UI's `_validate_filename_detailed()` is the canonical implementation.
   - Backend should always use this implementation when possible.

2. **Separation of Concerns**:
   - UI handles visual presentation and user interaction.
   - Backend focuses on node validation and issue reporting.
   - Validation logic is shared via imports, not duplication.

3. **Robustness**:
   - Always include fallback mechanisms.
   - Handle all possible error conditions.
   - Provide clear error messages for troubleshooting.

## Future Improvements

1. **Consolidate Token Definitions**:
   - Consider moving `FILENAME_TOKENS` to a shared module accessible by both UI and backend.

2. **Enhanced Error Reporting**:
   - Improve error messages to be more user-friendly and actionable.

3. **Performance Optimization**:
   - Optimize regex generation and validation for large node counts.
