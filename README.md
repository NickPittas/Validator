# Nuke Validator

A comprehensive tool to validate and fix common issues in Nuke scripts.

## Installation

1. Run the setup script to install the validator in your Nuke plugins directory:
    ```bash
    python setup.py
    ```

2. After installation, you can run the validator from the Nuke menu or by executing:
    ```bash
    nuke.load('Nuke Validator')
    ```

3. For standalone use, run:
    ```bash
    python main_window.py
    ```

## Features

- Validate Nuke projects according to defined rules
- Configure validation rules through an intuitive UI
- Check for various aspects of Nuke projects including:
  - Filename and path conventions
  - Frame range settings
  - Node integrity
  - Resolution settings
  - Color space settings
  - Channel settings
  - Render settings
  - Versioning
  - Plugins and custom nodes
  - Performance and optimization
  - Metadata and annotations
  - Viewport and viewer settings
  - Expressions and script errors

## Usage

1. Open a Nuke script you want to validate
2. Run the validator from the Nuke menu or by executing:
    ```bash
    nuke.load('Nuke Validator')
    ```
3. The validator will analyze your script and report any issues found
4. You can choose to automatically fix some issues or manually address others

## Configuration

The validator uses a rules.yaml file to define validation rules. You can customize this file to match your studio's standards.

Example rules.yaml:
```yaml
colorspaces:
  Read:
    allowed: ["srgb", "rec709", "aces2065-1"]
    severity: "warning"
  Write:
    allowed: ["srgb", "rec709", "aces2065-1"]
    severity: "warning"

write_paths:
  Write:
    path_format: "/output/path/"
    filename_format: "output_"
    severity: "error"

bounding_boxes:
  Read:
    severity: "warning"
  Write:
    severity: "warning"

performance:
  complexity_threshold: 10
  severity: "warning"

frame_range:
  allowed_ranges:
    - first: 1
      last: 100
    - first: 101
      last: 200
  severity: "warning"

resolution:
  allowed_resolutions:
    - width: 1920
      height: 1080
    - width: 3840
      height: 2160
  severity: "warning"

color_space_consistency:
  severity: "warning"

plugin_compatibility:
  allowed_plugins:
    - "Nuke"
    - "NukeX"
    - "Nuke Studio"
  severity: "warning"

node_dependencies:
  Tracker:
    required: ["Read"]
    severity: "error"
  Write:
    required: ["Tracker"]
    severity: "warning"

node_names:
  pattern: "^[a-zA-Z0-9_]+$"
  severity: "warning"

node_parameters:
  Read:
    file:
      allowed_values: [".exr", ".png", ".jpg"]
      severity: "warning"
  Write:
    file:
      allowed_values: [".exr", ".png", ".jpg"]
      severity: "warning"

node_connections:
  Merge:
    inputs:
      inputs.0:
        allowed_nodes: ["Read", "Grade", "Keyer"]
        severity: "warning"
      inputs.1:
        allowed_nodes: ["Read", "Grade", "Keyer"]
        severity: "warning"

node_metadata:
  Read:
    required_metadata:
      - "filename"
      - "width"
      - "height"
    severity: "warning"

node_expressions:
  Transform:
    expressions:
      - "translate"
      - "rotate"
      - "scale"
    allowed_values: ["0", "1", "2", "3"]
    severity: "warning"
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.