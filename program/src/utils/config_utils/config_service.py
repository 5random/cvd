"""
Configuration service for centralized config management with type safety and schema validation.
"""
import json
import copy
import logging
import re

from typing import Dict, Any, Optional, Type, TypeVar, Union, List, Set
from pathlib import Path
from dataclasses import dataclass
import sys

# Use standard logging for configuration service to avoid circular dependencies
info = logging.info
warning = logging.warning
error = logging.error
debug = logging.debug

T = TypeVar('T')

@dataclass
class ConfigSection:
    """Represents a configuration section"""
    section_name: str
    data: Dict[str, Any]
    schema: Optional[Dict[str, Any]] = None

class ConfigurationError(Exception):
    """Raised when configuration operations fail"""
    pass

class ValidationError(ConfigurationError):
    """Raised when configuration validation fails"""
    pass

class ConfigurationService:
    """Centralized configuration management with type safety, persistence and schema validation"""
    
    # Schema definitions for validation
    SENSOR_SCHEMA = {
        "required_fields": ["name", "type", "interface", "enabled"],
        "optional_fields": ["source", "port", "channel", "poll_interval_ms", "algorithm", "state_output"],
        "field_types": {
            "name": str,
            "type": str,
            "interface": str,
            "enabled": bool,
            "port": str,
            "channel": int,
            "address": str,
            "poll_interval_ms": int,
            "algorithm": list,
            "state_output": list
        },
        "valid_interfaces": ["serial", "usb", "ethernet", "modbus"],
        "valid_types": ["temperature", "pressure", "flow", "level", "ph"],
        "interface_requirements": {
            "serial": ["port", "channel"],
            "modbus": ["port", "address"]
        }
    }
    
    CONTROLLER_SCHEMA = {
        "required_fields": ["name", "type", "enabled"],
        "optional_fields": ["interface", "device_index", "settings", "algorithm", "state_output"],
        "field_types": {
            "name": str,
            "type": str,
            "interface": str,
            "enabled": bool,
            "device_index": int,
            "ip_address": str,
            "settings": dict,
            "algorithm": list,
            "state_output": list
        },
        "valid_interfaces": ["usb_camera", "network_camera", "virtual"],
        "valid_types": [
            "camera",
            "reactor_state",
            "motion_detector",
            "camera_capture",
            "motion_detection",
        ],
        "interface_requirements": {
            "usb_camera": ["device_index"],
            "network_camera": ["ip_address", "port"]
        }
    }

    WEBCAM_SCHEMA = {
        "required_fields": ["name", "device_index"],
        "optional_fields": ["resolution", "fps", "rotation", "uvc"],
        "field_types": {
            "name": str,
            "device_index": int,
            "resolution": list,
            "fps": int,
            "rotation": int,
            "uvc": dict,
        },
        "valid_rotations": [0, 90, 180, 270],
        "uvc_field_types": {
            "brightness": (int, float),
            "hue": (int, float),
            "contrast": (int, float),
            "saturation": (int, float),
            "sharpness": (int, float),
            "gamma": (int, float),
            "white_balance": (int, float),
            "white_balance_auto": bool,
            "gain": (int, float),
            "backlight_comp": (int, float),
            "exposure": (int, float),
            "exposure_auto": bool,
        },
    }
    
    ALGORITHM_SCHEMA = {
        "required_fields": ["name", "type", "enabled"],
        "optional_fields": ["settings"],
        "field_types": {
            "name": str,
            "type": str,
            "enabled": bool,
            "settings": dict
        },
        "valid_types": ["smoothing", "motion_detection", "state_detection", "filtering"]
    }
    
    def __init__(self, config_path: Path, default_config_path: Path):
        self.config_path = Path(config_path)
        self.default_config_path = Path(default_config_path)
        self._config_cache: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from files"""
        try:
            # Load default config
            default_config = {}
            if self.default_config_path.exists():
                with open(self.default_config_path, 'r', encoding='utf-8') as f:
                    default_config = json.load(f)
            
            # Load user config
            user_config = {}
            if self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
            
            # Merge configs
            self._config_cache = self._deep_merge(default_config, user_config)
            # Validate loaded configuration
            validation_errors = self.validate_all_configs()
            if validation_errors:
                raise ConfigurationError(f"Configuration validation failed: {validation_errors}")
            info(f"Configuration loaded successfully from {self.config_path}")
            
        except Exception as e:
            error(f"Failed to load configuration: {e}")
            raise ConfigurationError(f"Failed to load configuration: {e}")
    
    def _deep_merge(self, default: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries"""
        result = default.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _validate_config(self, config: Dict[str, Any], schema: Dict[str, Any], config_type: str) -> List[str]:
        """Validate configuration against schema and return list of errors"""
        errors = []
        
        # Check required fields
        for field in schema.get("required_fields", []):
            if field not in config:
                errors.append(f"Missing required field: {field}")
        
        # Check field types
        field_types = schema.get("field_types", {})
        for field, expected_type in field_types.items():
            if field in config:
                if not isinstance(config[field], expected_type):
                    errors.append(f"Field '{field}' should be of type {expected_type.__name__}, got {type(config[field]).__name__}")
        
        # Check valid values for specific fields
        if "interface" in config:
            valid_interfaces = schema.get("valid_interfaces", [])
            if valid_interfaces and config["interface"] not in valid_interfaces:
                errors.append(f"Invalid interface '{config['interface']}'. Valid options: {valid_interfaces}")
        
        if "type" in config:
            valid_types = schema.get("valid_types", [])
            if valid_types and config["type"] not in valid_types:
                errors.append(f"Invalid type '{config['type']}'. Valid options: {valid_types}")
        
        # Check interface-specific requirements
        if "interface" in config:
            interface_reqs = schema.get("interface_requirements", {})
            if config["interface"] in interface_reqs:
                required_fields = interface_reqs[config["interface"]]
                for field in required_fields:
                    if field not in config:
                        errors.append(f"Interface '{config['interface']}' requires field: {field}")
        
        # Check for unknown fields (warnings, not errors)
        all_known_fields = set(schema.get("required_fields", [])) | set(schema.get("optional_fields", []))
        unknown_fields = set(config.keys()) - all_known_fields - {"sensor_id", "controller_id", "algorithm_id"}
        for field in unknown_fields:
            warning(f"Unknown field in {config_type} config: {field}")
        
        return errors
    
    def _validate_sensor_config(self, sensor_config: Dict[str, Any]) -> None:
        """Validate sensor configuration"""
        errors = self._validate_config(sensor_config, self.SENSOR_SCHEMA, "sensor")
        if errors:
            raise ValidationError(f"Sensor validation failed: {'; '.join(errors)}")
    
    def _validate_controller_config(self, controller_config: Dict[str, Any]) -> None:
        """Validate controller configuration"""
        errors = self._validate_config(controller_config, self.CONTROLLER_SCHEMA, "controller")
        if errors:
            raise ValidationError(f"Controller validation failed: {'; '.join(errors)}")
    
    def _validate_algorithm_config(self, algorithm_config: Dict[str, Any]) -> None:
        """Validate algorithm configuration"""
        errors = self._validate_config(algorithm_config, self.ALGORITHM_SCHEMA, "algorithm")
        if errors:
            raise ValidationError(f"Algorithm validation failed: {'; '.join(errors)}")

    def _validate_webcam_config(self, webcam_config: Dict[str, Any]) -> None:
        """Validate webcam configuration"""
        errors = self._validate_config(webcam_config, self.WEBCAM_SCHEMA, "webcam")
        rotation = webcam_config.get("rotation")
        if rotation is not None and rotation not in self.WEBCAM_SCHEMA["valid_rotations"]:
            errors.append(f"Invalid rotation '{rotation}'. Valid options: {self.WEBCAM_SCHEMA['valid_rotations']}")
        uvc = webcam_config.get("uvc")
        if uvc is not None:
            if not isinstance(uvc, dict):
                errors.append("'uvc' must be a dictionary")
            else:
                for field, expected in self.WEBCAM_SCHEMA["uvc_field_types"].items():
                    if field in uvc and not isinstance(uvc[field], expected):
                        exp_names = (
                            expected.__name__ if isinstance(expected, type) else '/'.join(t.__name__ for t in expected)
                        )
                        errors.append(
                            f"UVC field '{field}' should be of type {exp_names}, got {type(uvc[field]).__name__}"
                        )
                # warn about unknown fields
                unknown = set(uvc.keys()) - set(self.WEBCAM_SCHEMA["uvc_field_types"].keys())
                for field in unknown:
                    warning(f"Unknown field in UVC settings: {field}")
        if errors:
            raise ValidationError(f"Webcam validation failed: {'; '.join(errors)}")
    
    def get(self, path: str, expected_type: Optional[Type[T]] = None, default: Optional[T] = None) -> Any:
        """Get configuration value by dot notation path"""
        keys = path.split('.')
        value = self._config_cache
        
        try:
            for key in keys:
                value = value[key]
            
            if expected_type is not None and not isinstance(value, expected_type):
                warning(f"Config value at {path} is not of expected type {expected_type}")
                return default
            
            return value
        except (KeyError, TypeError):
            return default
    
    def set(self, path: str, value: Any) -> None:
        """Set configuration value by dot notation path"""
        try:
            keys = path.split('.')
            current = self._config_cache
            
            # Navigate to the parent
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            
            # Set the value
            current[keys[-1]] = value
            self._save_config()
            
        except Exception as e:
            error(f"Failed to set config value at {path}: {e}")
            raise ConfigurationError(f"Failed to set config value: {e}")
    
    def get_ids(self, section_name: str, interface_type: str) -> List[str]:
        """Get all IDs from a config section filtered by interface type."""
        entries = self.get_section(section_name)
        # Normalize to list of entry dicts
        if isinstance(entries, list):
            iterable = entries
        elif isinstance(entries, dict):
            iterable = [entries]
        else:
            return []
            
        ids: List[str] = []
        for entry in iterable:
            if isinstance(entry, dict):
                for entry_id, config in entry.items():
                    if isinstance(config, dict) and config.get('interface') == interface_type:
                        ids.append(entry_id)
        return ids
    
    def _save_config(self) -> None:
        """Save configuration to file"""
        try:
            # ensure the directory for the config file exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config_cache, f, indent=2, ensure_ascii=False)
            debug(f"Configuration saved to {self.config_path}")
        except Exception as e:
            error(f"Failed to save configuration: {e}")
            raise ConfigurationError(f"Failed to save configuration: {e}")
    
    def get_section(self, section_name: str) -> Any:
        """Get raw configuration section value (dict, list, or other types)"""
        return self._config_cache.get(section_name, {})

    def get_configuration(self) -> Dict[str, Any]:
        """Return the entire configuration cache as a dictionary"""
        return copy.deepcopy(self._config_cache)

    def _extract_entries(self, section_name: str) -> List[tuple[str, Dict[str, Any]]]:
        """Yield (id, cfg dict) pairs for a config section, handling list and dict formats"""
        entries = self.get_section(section_name)
        items: List[tuple[str, Dict[str, Any]]] = []
        if isinstance(entries, dict):
            # Direct dict format like: {"entry_id": {...}}
            for entry_id, config in entries.items():
                if isinstance(config, dict):
                    items.append((entry_id, config))
        elif isinstance(entries, list):
            # List format like: [{"entry_id": {...}}, ...]
            for entry in entries:
                if isinstance(entry, dict):
                    for entry_id, config in entry.items():
                        if isinstance(config, dict):
                            items.append((entry_id, config))
        return items

    def _generate_next_id(self, section: str, prefix: str, padding: int = 3) -> str:
        """Generate the next sequential ID for a given section."""
        ids = [entry_id for entry_id, _ in self._extract_entries(section) if entry_id.startswith(prefix)]
        max_num = 0
        for entry_id in ids:
            match = re.search(r"(\d+)$", entry_id)
            if match:
                num = int(match.group(1))
                max_num = max(max_num, num)
        return f"{prefix}{max_num + 1:0{padding}d}"

    def generate_next_sensor_id(self, prefix: str = "sen", padding: int = 3) -> str:
        """Return the next available sensor ID."""
        return self._generate_next_id("sensors", prefix, padding)

    def generate_next_controller_id(self, prefix: str = "con", padding: int = 3) -> str:
        """Return the next available controller ID."""
        return self._generate_next_id("controllers", prefix, padding)

    def generate_next_webcam_id(self, prefix: str = "cam", padding: int = 3) -> str:
        """Return the next available webcam ID."""
        return self._generate_next_id("webcams", prefix, padding)

    def get_sensor_configs(self, interface_type: Optional[str] = None) -> List[tuple[str, Dict[str, Any]]]:
        """Get sensor configs as list of (sensor_id, config_dict), optionally filtered by interface_type"""
        result: List[tuple[str, Dict[str, Any]]] = []
        for sensor_id, cfg in self._extract_entries('sensors'):
            if interface_type is None or cfg.get('interface') == interface_type:
                config_with_id = cfg.copy()
                config_with_id['sensor_id'] = sensor_id
                result.append((sensor_id, config_with_id))
        return result

    def get_webcam_configs(self) -> List[tuple[str, Dict[str, Any]]]:
        """Get webcam configs as list of (webcam_id, config_dict)."""
        result: List[tuple[str, Dict[str, Any]]] = []
        for cam_id, cfg in self._extract_entries('webcams'):
            config_with_id = cfg.copy()
            config_with_id['webcam_id'] = cam_id
            result.append((cam_id, config_with_id))
        return result

    def add_sensor_config(self, sensor_config: Dict[str, Any]) -> None:
        """Add a new sensor configuration with validation"""
        if 'sensor_id' not in sensor_config:
            raise ConfigurationError("Sensor configuration must include 'sensor_id'")
        # Validate configuration
        self._validate_sensor_config(sensor_config)
        
        sensor_id = sensor_config['sensor_id']
        
        # Validate that sensor_id in config matches the extracted sensor_id
        if sensor_config['sensor_id'] != sensor_id:
            raise ConfigurationError(f"Sensor ID mismatch: config contains '{sensor_config['sensor_id']}' but expected '{sensor_id}'")
        
        # Check if sensor already exists
        existing_configs = self.get_sensor_configs()
        for existing_id, _ in existing_configs:
            if existing_id == sensor_id:
                raise ConfigurationError(f"Sensor with ID '{sensor_id}' already exists")
        
        # Add to sensors, preserving existing dict or list
        raw = self._config_cache.get('sensors')
        # Remove sensor_id before storing
        config_to_store = sensor_config.copy()
        del config_to_store['sensor_id']
        if isinstance(raw, dict):
            # convert dict entries to list then append
            sensors_list = [{sid: cfg} for sid, cfg in raw.items()]
            sensors_list.append({sensor_id: config_to_store})
            self._config_cache['sensors'] = sensors_list
        elif isinstance(raw, list):
            raw.append({sensor_id: config_to_store})
            self._config_cache['sensors'] = raw
        else:
            # no existing entries
            self._config_cache['sensors'] = [{sensor_id: config_to_store}]
        self._save_config()
        info(f"Added sensor configuration: {sensor_id}")

    def add_webcam_config(self, webcam_config: Dict[str, Any]) -> None:
        """Add a new webcam configuration with validation"""
        if 'webcam_id' not in webcam_config:
            raise ConfigurationError("Webcam configuration must include 'webcam_id'")

        self._validate_webcam_config(webcam_config)

        webcam_id = webcam_config['webcam_id']

        for existing_id, _ in self.get_webcam_configs():
            if existing_id == webcam_id:
                raise ConfigurationError(f"Webcam with ID '{webcam_id}' already exists")

        raw = self._config_cache.get('webcams')
        entry = webcam_config.copy()
        del entry['webcam_id']

        if isinstance(raw, dict):
            cams = [{wid: cfg} for wid, cfg in raw.items()]
            cams.append({webcam_id: entry})
            self._config_cache['webcams'] = cams
        elif isinstance(raw, list):
            raw.append({webcam_id: entry})
            self._config_cache['webcams'] = raw
        else:
            self._config_cache['webcams'] = [{webcam_id: entry}]

        self._save_config()
        info(f"Added webcam configuration: {webcam_id}")

    def get_webcam_config(self, webcam_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a specific webcam configuration by ID."""
        webcams = self.get_section('webcams')
        if isinstance(webcams, dict):
            cfg = webcams.get(webcam_id)
            if isinstance(cfg, dict):
                data = cfg.copy()
                data['webcam_id'] = webcam_id
                return data
            return None
        if isinstance(webcams, list):
            for entry in webcams:
                if isinstance(entry, dict) and webcam_id in entry:
                    cfg = entry[webcam_id]
                    if isinstance(cfg, dict):
                        data = cfg.copy()
                        data['webcam_id'] = webcam_id
                        return data
        return None
    
    def update_sensor_config(self, sensor_id: str, updates: Dict[str, Any]) -> bool:
        """Update existing sensor configuration with validation"""
        sensors = self.get_section('sensors')
        # Support dict format
        if isinstance(sensors, dict):
            if sensor_id not in sensors:
                return False
            current = sensors[sensor_id].copy()
            current.update(updates)
            current['sensor_id'] = sensor_id
            self._validate_sensor_config(current)
            # store without sensor_id field
            cfg = current.copy()
            del cfg['sensor_id']
            sensors[sensor_id] = cfg
            self._save_config()
            info(f"Updated sensor configuration: {sensor_id}")
            return True
        # Support list format
        if isinstance(sensors, list):
            for idx, sensor_entry in enumerate(sensors):
                if isinstance(sensor_entry, dict) and sensor_id in sensor_entry:
                    entry = sensor_entry[sensor_id].copy()
                    entry.update(updates)
                    entry['sensor_id'] = sensor_id
                    self._validate_sensor_config(entry)
                    # remove sensor_id before storing
                    cfg = entry.copy()
                    del cfg['sensor_id']
                    sensors[idx][sensor_id] = cfg
                    self._save_config()
                    info(f"Updated sensor configuration: {sensor_id}")
                    return True
        # Unsupported format
        raise ConfigurationError("Unsupported format for sensors config: expected list or dict.")
    
    def remove_sensor_config(self, sensor_id: str) -> bool:
        """Remove sensor configuration"""
        sensors = self.get_section('sensors')
        # dict format
        if isinstance(sensors, dict):
            if sensor_id in sensors:
                sensors.pop(sensor_id)
                self._save_config()
                info(f"Removed sensor configuration: {sensor_id}")
                return True
            return False
        # list format
        if isinstance(sensors, list):
            for idx, sensor_entry in enumerate(sensors):
                if isinstance(sensor_entry, dict) and sensor_id in sensor_entry:
                    sensors.pop(idx)
                    self._save_config()
                    info(f"Removed sensor configuration: {sensor_id}")
                    return True
            return False
        # unsupported format
        raise ConfigurationError("Unsupported format for sensors config: expected list or dict.")
    
    def get_controller_configs(self, interface_type: Optional[str] = None) -> List[tuple[str, Dict[str, Any]]]:
        """Get controller configs as list of (controller_id, config_dict), optionally filtered by interface_type"""
        result: List[tuple[str, Dict[str, Any]]] = []
        for controller_id, cfg in self._extract_entries('controllers'):
            if interface_type is None or cfg.get('interface') == interface_type:
                config_with_id = cfg.copy()
                config_with_id['controller_id'] = controller_id
                result.append((controller_id, config_with_id))
        return result
    
    def add_controller_config(self, controller_config: Dict[str, Any]) -> None:
        """Add a new controller configuration with validation"""
        if 'controller_id' not in controller_config:
            raise ConfigurationError("Controller configuration must include 'controller_id'")
        
        # Validate configuration        
        self._validate_controller_config(controller_config)
        
        controller_id = controller_config['controller_id']
        
        # Check if controller already exists
        existing_configs = self.get_controller_configs()
        for existing_id, _ in existing_configs:
            if existing_id == controller_id:
                raise ConfigurationError(f"Controller with ID '{controller_id}' already exists")
        
        # Add controller, preserving existing dict or list format
        raw = self._config_cache.get('controllers')
        # Prepare entry
        entry = controller_config.copy()
        del entry['controller_id']
        if isinstance(raw, dict):
            raw[controller_id] = entry
            self._config_cache['controllers'] = raw
        elif isinstance(raw, list):
            raw.append({controller_id: entry})
            self._config_cache['controllers'] = raw
        else:
            # no existing, default to list
            self._config_cache['controllers'] = [{controller_id: entry}]
        self._save_config()
        info(f"Added controller configuration: {controller_id}")
    
    def update_controller_config(self, controller_id: str, updates: Dict[str, Any]) -> bool:
        """Update existing controller configuration with validation"""
        controllers = self.get_section('controllers')
        # Support dict format for controllers
        if isinstance(controllers, dict):
            if controller_id not in controllers:
                return False
            # Update dict entry
            current = controllers[controller_id].copy()
            updated = current.copy()
            updated.update(updates)
            updated['controller_id'] = controller_id
            self._validate_controller_config(updated)
            # Remove id before storing
            del updated['controller_id']
            controllers[controller_id] = updated
            self._save_config()
            info(f"Updated controller configuration: {controller_id}")
            return True
        controller_index = None
        current_config = None
        # Existing list format handling
        if isinstance(controllers, list):
            for i, controller_entry in enumerate(controllers):
                if isinstance(controller_entry, dict) and controller_id in controller_entry:
                    current_config = controller_entry[controller_id].copy()
                    controller_index = i
                    break
        
        if current_config is None:
            return False
        
        # Apply updates
        updated_config = current_config.copy()
        updated_config.update(updates)
        updated_config['controller_id'] = controller_id
        
        # Validate updated config
        self._validate_controller_config(updated_config)
        
        # Remove controller_id before storing
        del updated_config['controller_id']
        
        # Update in list
        if controller_index is not None:
            controllers[controller_index][controller_id] = updated_config
            self._save_config()
            info(f"Updated controller configuration: {controller_id}")
            return True
        
        return False
    
    def remove_controller_config(self, controller_id: str) -> bool:
        """Remove controller configuration"""
        controllers = self.get_section('controllers')
        # Support dict format for controllers
        if isinstance(controllers, dict):
            if controller_id in controllers:
                controllers.pop(controller_id)
                self._save_config()
                info(f"Removed controller configuration: {controller_id}")
                return True
        if isinstance(controllers, list):
            for i, controller_entry in enumerate(controllers):
                if isinstance(controller_entry, dict) and controller_id in controller_entry:
                    controllers.pop(i)
                    self._save_config()
                    info(f"Removed controller configuration: {controller_id}")
                    return True
        return False
    
    def get_controller_settings(self, controller_id: str) -> Optional[Dict[str, Any]]:
        """Get settings for a specific controller"""
        controller_configs = self.get_controller_configs()
        for cid, config in controller_configs:
            if cid == controller_id:
                return config.get('settings', {})
        return None
    
    def update_controller_settings(self, controller_id: str, settings_updates: Dict[str, Any]) -> bool:
        """Update settings for a specific controller"""
        current_settings = self.get_controller_settings(controller_id)
        if current_settings is None:
            return False
            
        current_settings.update(settings_updates)
        return self.update_controller_config(controller_id, {'settings': current_settings})
    
    # Algorithm management methods
    def get_algorithm_configs(self, algorithm_type: Optional[str] = None) -> List[tuple[str, Dict[str, Any]]]:
        """Get algorithm configs as list of (algorithm_id, config_dict), optionally filtered by algorithm_type"""
        result: List[tuple[str, Dict[str, Any]]] = []
        for algorithm_id, cfg in self._extract_entries('algorithms'):
            if algorithm_type is None or cfg.get('type') == algorithm_type:
                config_with_id = cfg.copy()
                config_with_id['algorithm_id'] = algorithm_id
                result.append((algorithm_id, config_with_id))
        return result
    
    def get_algorithm_config(self, algorithm_id: str) -> Optional[Dict[str, Any]]:
        """Get configuration for a specific algorithm"""
        algorithm_configs = self.get_algorithm_configs()
        for aid, config in algorithm_configs:
            if aid == algorithm_id:
                return config
        return None
    
    def get_algorithm_settings(self, algorithm_id: str) -> Optional[Dict[str, Any]]:
        """Get settings for a specific algorithm"""
        algorithm_config = self.get_algorithm_config(algorithm_id)
        if algorithm_config:
            return algorithm_config.get('settings', {})
        return None
    
    def update_algorithm_settings(self, algorithm_id: str, settings_updates: Dict[str, Any]) -> bool:
        """Update settings for a specific algorithm"""
        current_settings = self.get_algorithm_settings(algorithm_id)
        if current_settings is None:
            return False
            
        current_settings.update(settings_updates)
        return self.update_algorithm_config(algorithm_id, {'settings': current_settings})
    
    def add_algorithm_config(self, algorithm_config: Dict[str, Any]) -> None:
        """Add a new algorithm configuration with validation"""
        if 'algorithm_id' not in algorithm_config:
            raise ConfigurationError("Algorithm configuration must include 'algorithm_id'")
        # Validate configuration
        self._validate_algorithm_config(algorithm_config)
        
        algorithm_id = algorithm_config['algorithm_id']
        
        # Check if algorithm already exists
        existing_configs = self.get_algorithm_configs()
        for existing_id, _ in existing_configs:
            if existing_id == algorithm_id:
                raise ConfigurationError(f"Algorithm with ID '{algorithm_id}' already exists")
        
        # Add algorithm, preserving existing dict or list format
        raw = self._config_cache.get('algorithms')
        # Validate id consistency and prepare entry
        entry = algorithm_config.copy()
        del entry['algorithm_id']
        if isinstance(raw, dict):
            # convert existing dict to list of entries
            items = [{aid: cfg} for aid, cfg in raw.items()]
            items.append({algorithm_id: entry})
            self._config_cache['algorithms'] = items
        elif isinstance(raw, list):
            raw.append({algorithm_id: entry})
            self._config_cache['algorithms'] = raw
        else:
            self._config_cache['algorithms'] = [{algorithm_id: entry}]
        self._save_config()
        info(f"Added algorithm configuration: {algorithm_id}")
    
    def update_algorithm_config(self, algorithm_id: str, updates: Dict[str, Any]) -> bool:
        """Update existing algorithm configuration with validation"""
        # Get current config
        current_config = None
        algorithms = self.get_section('algorithms')
        algorithm_index = None
        
        if isinstance(algorithms, list):
            for i, algorithm_entry in enumerate(algorithms):
                if isinstance(algorithm_entry, dict) and algorithm_id in algorithm_entry:
                    current_config = algorithm_entry[algorithm_id].copy()
                    algorithm_index = i
                    break
        
        if current_config is None:
            return False
        
        # Apply updates
        updated_config = current_config.copy()
        updated_config.update(updates)
        updated_config['algorithm_id'] = algorithm_id
        
        # Validate updated config
        self._validate_algorithm_config(updated_config)
        
        # Remove algorithm_id before storing
        del updated_config['algorithm_id']
        
        # Update in list
        if algorithm_index is not None:
            algorithms[algorithm_index][algorithm_id] = updated_config
            self._save_config()
            info(f"Updated algorithm configuration: {algorithm_id}")
            return True
        
        return False
    
    def remove_algorithm_config(self, algorithm_id: str) -> bool:
        """Remove algorithm configuration"""
        algorithms = self.get_section('algorithms')
        if isinstance(algorithms, list):
            for i, algorithm_entry in enumerate(algorithms):
                if isinstance(algorithm_entry, dict) and algorithm_id in algorithm_entry:
                    algorithms.pop(i)
                    self._save_config()
                    info(f"Removed algorithm configuration: {algorithm_id}")
                    return True
        return False
    
    def get_algorithms_by_type(self, algorithm_type: str) -> List[tuple[str, Dict[str, Any]]]:
        """Get all algorithms of a specific type"""
        return self.get_algorithm_configs(algorithm_type=algorithm_type)
    
    def get_enabled_algorithms(self) -> List[tuple[str, Dict[str, Any]]]:
        """Get all enabled algorithms"""
        result = []
        for algorithm_id, config in self.get_algorithm_configs():
            if config.get('enabled', False):
                result.append((algorithm_id, config))
        return result
    
    def get_algorithms_for_entity(self, entity_type: str, entity_id: str) -> List[str]:
        """Get algorithm IDs referenced by a sensor or controller"""
        if entity_type == 'sensor':
            configs = self.get_sensor_configs()
        elif entity_type == 'controller':
            configs = self.get_controller_configs()
        else:
            return []
        
        for eid, config in configs:
            if eid == entity_id:
                return config.get('algorithm', [])
        return []
    
    def validate_all_configs(self) -> Dict[str, List[str]]:
        """Validate all configurations and return errors by section"""
        validation_errors = {}
        
        # Validate sensors
        sensor_errors = []
        for sensor_id, config in self.get_sensor_configs():
            try:
                self._validate_sensor_config(config)
            except ValidationError as e:
                sensor_errors.append(f"{sensor_id}: {str(e)}")
        if sensor_errors:
            validation_errors['sensors'] = sensor_errors

        # Validate webcams
        webcam_errors = []
        for cam_id, config in self.get_webcam_configs():
            try:
                self._validate_webcam_config(config)
            except ValidationError as e:
                webcam_errors.append(f"{cam_id}: {str(e)}")
        if webcam_errors:
            validation_errors['webcams'] = webcam_errors
        
        # Validate controllers
        controller_errors = []
        for controller_id, config in self.get_controller_configs():
            try:
                self._validate_controller_config(config)
            except ValidationError as e:
                controller_errors.append(f"{controller_id}: {str(e)}")
        if controller_errors:
            validation_errors['controllers'] = controller_errors
        
        # Validate algorithms
        algorithm_errors = []
        for algorithm_id, config in self.get_algorithm_configs():
            try:
                self._validate_algorithm_config(config)
            except ValidationError as e:
                algorithm_errors.append(f"{algorithm_id}: {str(e)}")
        if algorithm_errors:
            validation_errors['algorithms'] = algorithm_errors
        
        return validation_errors
    
    def get_raw_config_as_json(self) -> str:
        """Get raw configuration as JSON string"""
        return json.dumps(self._config_cache, indent=2, ensure_ascii=False)
    
    def reload(self) -> None:
        """Reload configuration from files"""
        self._load_config()
    
    def reset_to_defaults(self) -> None:
        """Reset configuration to defaults"""
        if self.default_config_path.exists():
            with open(self.default_config_path, 'r', encoding='utf-8') as f:
                self._config_cache = json.load(f)
            self._save_config()

# Global configuration service instance
_config_service_instance: Optional[ConfigurationService] = None

def get_config_service() -> Optional[ConfigurationService]:
    """Get the global configuration service instance"""
    return _config_service_instance

def set_config_service(service: ConfigurationService) -> None:
    """Set the global configuration service instance"""
    global _config_service_instance
    _config_service_instance = service

# Ensure this module is accessible via both ``src.utils.config_service`` and
# ``program.src.utils.config_service`` so that globals are shared regardless of
# import style used by callers.
module = sys.modules[__name__]
sys.modules.setdefault('src.utils.config_service', module)
sys.modules.setdefault('program.src.utils.config_service', module)