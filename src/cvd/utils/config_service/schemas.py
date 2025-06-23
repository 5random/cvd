# Schemas for configuration validation

SENSOR_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "type": {
            "type": "string",
            "enum": ["temperature", "pressure", "flow", "level", "ph"],
        },
        "interface": {
            "type": "string",
            "enum": ["serial", "usb", "ethernet", "modbus"],
        },
        "enabled": {"type": "boolean"},
        "source": {"type": "string"},
        "port": {"type": "string"},
        "channel": {"type": "integer"},
        "address": {"type": "string"},
        "baudrate": {"type": "integer", "default": 9600},
        "timeout": {"type": "number", "default": 2.0},
        "poll_interval_ms": {"type": "integer"},
        "algorithm": {"type": "array"},
        "state_output": {"type": "array"},
        "show_on_dashboard": {"type": "boolean"},
    },
    "required": ["name", "type", "interface", "source", "enabled"],
    "allOf": [
        {
            "if": {
                "properties": {"interface": {"const": "serial"}},
                "required": ["interface"],
            },
            "then": {
                "properties": {
                    "port": {"type": "string"},
                    "channel": {"type": "integer"},
                },
                "required": ["port", "channel"],
            },
        },
        {
            "if": {
                "properties": {"interface": {"const": "modbus"}},
                "required": ["interface"],
            },
            "then": {
                "properties": {
                    "port": {"type": "string"},
                    "address": {"type": "string"},
                },
                "required": ["port", "address"],
            },
        },
    ],
}

CONTROLLER_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "type": {
            "type": "string",
            "enum": [
                "motion_detection",
                "camera_capture",
                "reactor_state",
            ],
        },
        "interface": {
            "type": "string",
            "enum": ["usb_camera", "network_camera", "virtual"],
        },
        "enabled": {"type": "boolean"},
        "device_index": {"type": "integer"},
        "capture_backend": {"type": ["integer", "null"]},
        "ip_address": {"type": "string"},
        "port": {"type": "integer"},
        "parameters": {"type": "object"},
        "settings": {"type": "object"},
        "algorithm": {"type": "array"},
        "state_output": {"type": "array"},
        "show_on_dashboard": {"type": "boolean"},
        "cam_id": {"type": "string"},
    },
    "required": ["name", "type", "enabled"],
    "allOf": [
        {
            "if": {
                "properties": {"interface": {"const": "usb_camera"}},
                "required": ["interface"],
            },
            "then": {"required": ["device_index"]},
        },
        {
            "if": {
                "properties": {"interface": {"const": "network_camera"}},
                "required": ["interface"],
            },
            "then": {"required": ["ip_address", "port"]},
        },
        {
            "if": {"properties": {"type": {"const": "motion_detection"}}},
            "then": {
                "properties": {
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "algorithm": {
                                "type": "string",
                                "enum": ["MOG2", "KNN"],
                            },
                            "var_threshold": {"type": "number"},
                            "dist2_threshold": {"type": "number"},
                            "history": {"type": "integer"},
                            "detect_shadows": {"type": "boolean"},
                        },
                        "additionalProperties": True,
                    }
                }
            },
        },
    ],
}

WEBCAM_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "device_index": {"type": "integer"},
        "capture_backend": {"type": ["integer", "null"]},
        "resolution": {"type": "array"},
        "fps": {"type": "integer"},
        "rotation": {"type": "integer", "enum": [0, 90, 180, 270]},
        "uvc": {
            "type": "object",
            "properties": {
                "brightness": {"type": "number"},
                "hue": {"type": "number"},
                "contrast": {"type": "number"},
                "saturation": {"type": "number"},
                "sharpness": {"type": "number"},
                "gamma": {"type": "number"},
                "white_balance": {"type": "number"},
                "white_balance_auto": {"type": "boolean"},
                "gain": {"type": "number"},
                "backlight_compensation": {"type": "number"},
                "exposure": {"type": "number"},
                "exposure_auto": {"type": "boolean"},
            },
            "additionalProperties": False,
        },
        "uvc_settings": {"type": "object"},
        "webcam_id": {"type": "string"},
    },
    "required": ["name", "device_index"],
}

ALGORITHM_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "type": {
            "type": "string",
            "enum": [
                "smoothing",
                "motion_detection",
                "state_detection",
                "filtering",
            ],
        },
        "enabled": {"type": "boolean"},
        "settings": {"type": "object"},
    },
    "required": ["name", "type", "enabled"],
}
