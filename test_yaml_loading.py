import yaml
import os

def load_path_structures(yaml_path):
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)
    path_structures = data.get('path_structures', {})
    # Skip metadata keys (e.g., keys starting with 'version')
    return {k: v for k, v in path_structures.items() if not k.lower().startswith('version')}

if __name__ == '__main__':
    yaml_file = os.path.join(os.path.dirname(__file__), 'rules.yaml')
    structures = load_path_structures(yaml_file)
    print('Loaded path structures:')
    for key, value in structures.items():
        print(f"{key}: {value}") 