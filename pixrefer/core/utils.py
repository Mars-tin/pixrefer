"""Utility functions for loading data and configurations."""

import json
import os
import yaml
import re
from typing import Any, Dict, Optional


def load_env_file(env_file_path: str) -> None:
    """ Load the environment variables from the .env file.
    
    Args:
        env_file_path: The path to the .env file.
    """
    if os.path.exists(env_file_path):
        with open(env_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    # Set the environment variables
                    os.environ[key.strip()] = value.strip()


def load_data(data_path: str) -> Any:
    """Load data from a JSON / JSONL file.
    
    Args:
        data_path: Path to the JSON file.

    Returns:
        The loaded data.
    """
    if data_path.endswith('.jsonl'):
        with open(data_path, 'r', encoding='utf-8') as f:
            return [json.loads(line) for line in f]
    else:
        with open(data_path, 'r', encoding='utf-8') as f:
            return json.load(f)


def _replace_env_vars(obj: Any) -> Any:
    """Replace environment variables in the object.
    
    Args:
        obj: The object to process, which can be a dictionary, list, or basic type.
        
    Returns:
        The object with environment variables replaced.
    """
    if isinstance(obj, dict):
        return {k: _replace_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_replace_env_vars(item) for item in obj]
    elif isinstance(obj, str):
        # Find environment variable references in the format ${VAR}
        pattern = r'\$\{([A-Za-z0-9_]+)\}'
        matches = re.findall(pattern, obj)
        
        # If environment variable references are found, replace them
        if matches:
            result = obj
            for var_name in matches:
                env_value = os.environ.get(var_name)
                if env_value is not None:
                    placeholder = f'${{{var_name}}}'
                    result = result.replace(placeholder, env_value)
            return result
        return obj
    else:
        return obj


def load_yaml_file(file_path: str, key_path: Optional[str] = None) -> Any:
    """Load data from a YAML file, optionally accessing a nested key.
    
    Args:
        file_path: Path to the YAML file.
        key_path: Dot-separated path to a nested key.

    Returns:
        The loaded data or the specific key's value.
    
    Raises:
        FileNotFoundError: If the file doesn't exist.
        ValueError: If the YAML file cannot be parsed.
        KeyError: If the specified key doesn't exist.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)
        
        # Replace all environment variable references
        data = _replace_env_vars(data)
        
        if key_path:
            for key in key_path.split('.'):  # Navigate through nested keys
                data = data[key]
        return data
    except FileNotFoundError:
        raise FileNotFoundError(f"File not found: {file_path}")
    except yaml.YAMLError as e:
        raise ValueError(f"YAML parsing error: {e}")
    except KeyError:
        raise KeyError(f"Key '{key_path}' not found in file")


# Wrapper functions for specific configurations
def get_project_prompt(config_path: Optional[str] = None, prompt_name: Optional[str] = None) -> Any:
    package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    prompts_path = os.path.join(package_root, 'core', 'prompt.yaml')
    return load_yaml_file(prompts_path, prompt_name)


def get_project_config(config_path: Optional[str] = None, config_name: Optional[str] = None) -> Any:
    if config_path is None:
        package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        project_root = os.path.dirname(package_root)
        config_path = os.path.join(project_root, 'config.yaml')
        
        # Check if the .env file exists, and load it if it does
        env_file_path = os.path.join(project_root, '.env')
        load_env_file(env_file_path)
        
    return load_yaml_file(config_path, config_name)


# Alias functions for backward compatibility
def load_config(config_path: Optional[str] = None, config_name: Optional[str] = None) -> Dict[str, Any]:
    return get_project_config(config_path, config_name)


def load_prompt(prompt_name: str, prompts_path: Optional[str] = None) -> str:
    return get_project_prompt(prompts_path, prompt_name)


def ensure_dir_exists(directory_path):
    """Ensure that the specified directory exists, creating it if necessary.
    
    Args:
        directory_path: Path to the directory to ensure exists.
    """
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)