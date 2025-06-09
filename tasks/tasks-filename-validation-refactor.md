## Relevant Files

- `nuke_validator.py` – Main application logic; contains all filename validation methods to be refactored.
- `nuke_validator_backup_before_filename_refactor.py` – Backup of the original file before any changes.
- `tests/test_filename_validation.py` – Contains the robust unit tests and expected behaviors for filename validation.

### Notes

- Unit tests should typically be placed alongside the code files they are testing (e.g., `MyComponent.tsx` and `MyComponent.test.tsx` in the same directory).
- Use `npx jest [optional/path/to/test/file]` to run tests. Running without a path executes all tests found by the Jest configuration.

## Tasks

- [ ] 1.0 Analyze Current Filename Validation Logic
  - [x] 1.1 Identify all methods in `nuke_validator.py` that perform filename validation
  - [x] 1.2 Document where and how filename tokens are used in the app
  - [x] 1.3 Map current error reporting and output structure for filename validation
- [ ] 2.0 Refactor `_basic_filename_validation` and `_validate_by_tokens` Methods
  - [x] 2.1 Replace existing logic with robust, unit-tested logic from `MockValidator`
  - [x] 2.2 Ensure new logic works with the app’s token definitions and config loading
  - [x] 2.3 Remove or refactor any redundant or flawed code related to filename validation
- [ ] 3.0 Update All Usages of Filename Validation in App
  - [x] 3.1 Search for all calls to `_basic_filename_validation` and `_validate_by_tokens`
  - [x] 3.2 Update these usages to ensure they receive new, user-friendly error messages
  - [x] 3.3 Confirm that only filename validation logic is affected (not other validators)
- [x] 4.0 Ensure User-Friendly Error Reporting Everywhere
   - [x] 4.1 Review all UI and logging outputs related to filename validation
   - [x] 4.2 Update UI and logs to display actionable, user-friendly error messages
- [ ] 5.0 Validate Refactor Against Unit Tests
  - [x] 5.1 Run all filename validation unit tests in `tests/test_filename_validation.py` (2 failures remain for separator handling)
  - [x] 5.2 Fix any issues or mismatches between app and test results (remaining failures are genuine validation logic errors)
  - [x] 5.3 Document the refactor and update developer notes as needed
