# Codebase Cleanup Task List

## Overview
This document outlines the systematic cleanup of duplicated code in the Nuke Validator codebase. The cleanup will eliminate 4 duplicate template builders, 2 duplicate multiselect widgets, duplicate validation methods, and other redundancies.

## ⚡ EMERGENCY FIXES (Applied)

### ✅ Fixed: Duplicate FilenameRuleEditor Classes 
- **Issue:** Two `FilenameRuleEditor` classes exist (lines ~800 and ~4455)
- **Problem:** Both classes had incomplete method implementations causing AttributeError
- **Fix Applied:** 
  - ✅ **First class (line ~800):** Already had complete method implementations
  - ✅ **Second class (line ~4455):** Added ALL missing methods:
    - `add_token_to_template()` - adds tokens to template builder
    - `update_regex()` - generates regex from template config  
    - `save_template()` / `load_template()` - template persistence
    - `on_regex_edit()` - manual regex editing handler
    - `get_validation_errors()` - comprehensive filename validation
    - `_validate_filename_detailed()` - token-by-token validation
    - `_get_token_pattern_and_example()` - pattern generation
    - `_generate_token_error()` - specific error messages
    - `get_validation_summary()` - concise error reporting
- **Status:** ✅ **FULLY RESOLVED** - Application should now start and run without errors

### ✅ Fixed: TableBasedFilenameTemplateBuilder Compatibility
- **Issue:** `load_rules_from_yaml()` trying to access `token_widgets` attribute on `TableBasedFilenameTemplateBuilder`
- **Problem:** `TableBasedFilenameTemplateBuilder` uses `token_configs` list, not `token_widgets` attribute like older builders
- **Fix Applied:** 
  - ✅ Added compatibility layer in `load_rules_from_yaml()` method
  - ✅ Detects builder type and uses appropriate configuration method
  - ✅ Table-based: Updates `token_configs` directly and rebuilds table
  - ✅ Widget-based: Uses legacy widget configuration approach
- **Status:** ✅ **RESOLVED** - Rules loading now works with both builder types

**Note:** These are comprehensive fixes. Both FilenameRuleEditor classes are now fully functional and compatible with YAML loading. The permanent solution is still to remove one duplicate class in Phase 2.

## Phase 1: Analysis and Preparation

### Task 1.1: Audit Current Usage
- [ ] **1.1.1** Search for all references to `FilenameTemplateBuilder` in the codebase
- [ ] **1.1.2** Search for all references to `SimpleFilenameTemplateBuilder` in the codebase
- [ ] **1.1.3** Search for all references to `CompactFilenameTemplateBuilder` in the codebase  
- [ ] **1.1.4** Search for all references to `TableBasedFilenameTemplateBuilder` in the codebase
- [ ] **1.1.5** Document which classes are actively used vs. legacy/unused
- [ ] **1.1.6** Identify all instantiation points and their context

### Task 1.1.5: Identify ALL Duplicate Classes (CRITICAL)
- [ ] **1.1.5a** 🚨 **FilenameRuleEditor** - TWO classes found (lines ~800 and ~4455)
- [ ] **1.1.5b** Search for any other duplicate class definitions in the entire file
- [ ] **1.1.5c** Use `grep "^class "` to find all class definitions
- [ ] **1.1.5d** Identify which duplicate classes are being used vs. orphaned
- [ ] **1.1.5e** Document the impact of each duplicate (working vs. broken)

### Task 1.2: Analyze MultiSelect Widget Usage
- [ ] **1.2.1** Find all references to `MultiSelectWidget` class
- [ ] **1.2.2** Find all references to `SimpleMultiSelectWidget` class
- [ ] **1.2.3** Compare functionality and identify which is more robust
- [ ] **1.2.4** Document API differences between the two widgets

### Task 1.3: Map Validation Method Dependencies
- [ ] **1.3.1** Identify all calls to `_validate_filename_detailed()` in backend
- [ ] **1.3.2** Identify all calls to `_validate_filename_detailed()` in UI
- [ ] **1.3.3** Verify current import relationship between backend and UI validation
- [ ] **1.3.4** Document validation flow and dependencies

## Phase 2: Template Builder Consolidation

### Task 2.0: FilenameRuleEditor Deduplication (HIGH PRIORITY)
- [ ] **2.0.1** **DECISION:** Keep the SECOND `FilenameRuleEditor` class (line ~4455)
  - **Reason:** Uses TableBasedFilenameTemplateBuilder, more recent implementation
- [ ] **2.0.2** **Remove** the FIRST `FilenameRuleEditor` class (lines ~800-1469)
- [ ] **2.0.3** Verify the second class has all necessary methods (emergency fix already applied)
- [ ] **2.0.4** Update any references to point to the remaining class
- [ ] **2.0.5** Test that FilenameRuleEditor works correctly after deduplication

### Task 2.1: Choose Primary Template Builder
- [ ] **2.1.1** **DECISION:** Keep `TableBasedFilenameTemplateBuilder` as the primary implementation
  - **Reason:** Most recent, Excel-like interface, best user experience
- [ ] **2.1.2** **DECISION:** Remove all other template builders in order of safety:
  1. `CompactFilenameTemplateBuilder` (newest duplicate)
  2. `SimpleFilenameTemplateBuilder` (middle generation)  
  3. `FilenameTemplateBuilder` (original, but replaced)

### Task 2.2: Update All References to Use TableBasedFilenameTemplateBuilder
- [ ] **2.2.1** Find the line: `FilenameTemplateBuilder = SimpleFilenameTemplateBuilder` (line ~3391)
- [ ] **2.2.2** Replace with: `FilenameTemplateBuilder = TableBasedFilenameTemplateBuilder`
- [ ] **2.2.3** Update `FilenameRuleEditor.__init__()` to ensure it uses the table-based version
- [ ] **2.2.4** Search for any hardcoded instantiations of old template builders
- [ ] **2.2.5** Replace all found instantiations with `TableBasedFilenameTemplateBuilder()`

### Task 2.3: Remove Duplicate Template Builder Classes
- [ ] **2.3.1** **Remove** `CompactFilenameTemplateBuilder` class definition (lines ~3731-3930)
- [ ] **2.3.2** **Remove** `CompactTokenWidget` class definition (lines immediately after CompactFilenameTemplateBuilder)
- [ ] **2.3.3** **Remove** `SimpleFilenameTemplateBuilder` class definition (lines ~3223-3390)
- [ ] **2.3.4** **Remove** original `FilenameTemplateBuilder` class definition (lines ~463-735)
- [ ] **2.3.5** **Remove** any associated styling CSS blocks for removed classes

### Task 2.4: Consolidate Template Configuration Methods
- [ ] **2.4.1** Keep only the `get_template_config()` method from `TableBasedFilenameTemplateBuilder`
- [ ] **2.4.2** Ensure the remaining method handles all configuration scenarios
- [ ] **2.4.3** Remove duplicate `get_template_config()` methods from removed classes
- [ ] **2.4.4** Verify template loading/saving still works with single implementation

## Phase 3: MultiSelect Widget Consolidation

### Task 3.1: Choose Primary MultiSelect Widget
- [ ] **3.1.1** **DECISION:** Keep `SimpleMultiSelectWidget` as primary implementation
  - **Reason:** More robust, has the signal disconnect fix for save/load bug
- [ ] **3.1.2** **DECISION:** Remove `MultiSelectWidget` class

### Task 3.2: Replace All MultiSelectWidget References
- [ ] **3.2.1** Search for all instantiations of `MultiSelectWidget`
- [ ] **3.2.2** Replace with `SimpleMultiSelectWidget` instantiations
- [ ] **3.2.3** Update any method calls that might have different APIs
- [ ] **3.2.4** Test multiselect functionality after replacement

### Task 3.3: Remove Duplicate MultiSelect Class
- [ ] **3.3.1** **Remove** `MultiSelectWidget` class definition (lines ~2722-3117)
- [ ] **3.3.2** **Remove** any CSS styling specific to the old `MultiSelectWidget`
- [ ] **3.3.3** Verify all multiselect functionality still works

## Phase 4: Validation Method Cleanup

### Task 4.1: Consolidate Validation Logic
- [ ] **4.1.1** Keep the sophisticated `_validate_filename_detailed()` method in UI (`nuke_validator_ui.py`)
- [ ] **4.1.2** Keep the import-based approach in backend (`nuke_validator.py`) that uses UI validation
- [ ] **4.1.3** Verify the backend successfully imports and uses UI validation
- [ ] **4.1.4** Remove any redundant validation logic if found

### Task 4.2: Improve Backend-UI Integration
- [ ] **4.2.1** Add error handling for import failures in backend validation
- [ ] **4.2.2** Add fallback validation logic in case UI import fails
- [ ] **4.2.3** Test validation works both in UI and backend contexts
- [ ] **4.2.4** Document the validation architecture clearly

## Phase 5: Cleanup and Optimization

### Task 5.1: Remove Dead Code
- [ ] **5.1.1** Search for any remaining references to removed classes
- [ ] **5.1.2** Remove unused imports related to removed classes
- [ ] **5.1.3** Remove unused utility methods that were only used by removed classes
- [ ] **5.1.4** Clean up any orphaned CSS styles

### Task 5.2: Code Organization
- [ ] **5.2.1** Group related classes together in the file
- [ ] **5.2.2** Move `SimpleMultiSelectWidget` near other widget definitions
- [ ] **5.2.3** Ensure consistent naming patterns
- [ ] **5.2.4** Add clear section comments to organize the file

### Task 5.3: Update Constants and Imports
- [ ] **5.3.1** Verify `FILENAME_TOKENS` is defined only once
- [ ] **5.3.2** Check for any duplicate constant definitions
- [ ] **5.3.3** Organize imports alphabetically and remove unused ones
- [ ] **5.3.4** Add proper docstrings to remaining classes

## Phase 6: Testing and Validation

### Task 6.1: Functional Testing
- [ ] **6.1.1** Test filename template creation with table interface
- [ ] **6.1.2** Test multiselect functionality (save/load bug should be fixed)
- [ ] **6.1.3** Test validation works for both valid and invalid filenames
- [ ] **6.1.4** Test backend validation can import and use UI validation
- [ ] **6.1.5** Test rules editor UI still functions correctly

### Task 6.2: Integration Testing
- [ ] **6.2.1** Test full workflow: create template → validate files → show results
- [ ] **6.2.2** Test template save/load functionality
- [ ] **6.2.3** Test that removed classes don't cause import errors
- [ ] **6.2.4** Verify Excel-like validation results table still works

### Task 6.3: Performance Verification
- [ ] **6.3.1** Measure file size reduction after cleanup
- [ ] **6.3.2** Test UI responsiveness with single template builder
- [ ] **6.3.3** Verify validation speed hasn't decreased
- [ ] **6.3.4** Check memory usage with fewer class definitions

## Phase 7: Documentation and Finalization

### Task 7.1: Update Documentation
- [ ] **7.1.1** Update any code comments referencing removed classes
- [ ] **7.1.2** Document the final architecture (single template builder, single multiselect)
- [ ] **7.1.3** Update method docstrings where APIs changed
- [ ] **7.1.4** Add comments explaining validation system architecture

### Task 7.2: Final Cleanup Report
- [ ] **7.2.1** Document classes removed and lines of code eliminated
- [ ] **7.2.2** Document file size reduction percentage
- [ ] **7.2.3** List any breaking changes (should be none if done correctly)
- [ ] **7.2.4** Create summary of cleanup benefits

## Risk Mitigation

### Backup Strategy
- [ ] **Backup current working state** before starting any removal
- [ ] **Test each phase independently** before proceeding to next
- [ ] **Keep removed code in comments temporarily** for easy rollback if needed

### Testing Strategy  
- [ ] **Test after each major removal** (not just at the end)
- [ ] **Verify both UI and backend functionality** after each phase
- [ ] **Test edge cases** especially multiselect save/load functionality

## Success Criteria

### Primary Goals
- [ ] **File size reduced by ~30-40%** from removing duplicate classes
- [ ] **Single template builder implementation** (TableBasedFilenameTemplateBuilder)
- [ ] **Single multiselect widget implementation** (SimpleMultiSelectWidget)  
- [ ] **Unified validation system** (UI-based validation used by backend)
- [ ] **No functional regressions** in existing features

### Secondary Goals
- [ ] **Improved code maintainability** with less duplication
- [ ] **Consistent user experience** with single implementations
- [ ] **Better performance** with fewer class definitions
- [ ] **Cleaner architecture** with clear separation of concerns

## Estimated Impact
- **Lines of Code Removed:** ~1000-1200 lines (was ~800-1000)
- **File Size Reduction:** ~40-45% (was ~35-40%)
- **Classes Removed:** 6 major classes (was 5)
  - 4 template builders (FilenameTemplateBuilder, SimpleFilenameTemplateBuilder, CompactFilenameTemplateBuilder + 1 duplicate FilenameRuleEditor)
  - 1 multiselect widget (MultiSelectWidget)  
  - 1 duplicate FilenameRuleEditor class
- **Maintenance Burden:** Significantly reduced
- **User Experience:** Improved consistency, no functional changes 