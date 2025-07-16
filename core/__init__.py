# Location: project_v2/core/__init__.py
# Usage: Core 模組初始化

from .state_machine import StateMachine, SystemState
from .camera_manager import CameraManager
from .face_detector import FaceDetector
from .esp32_controller import ESP32Controller
from .ssr_controller import SSRController

# 為了兼容性，保留ArduinoController別名
ArduinoController = ESP32Controller

__all__ = [
    'StateMachine',
    'SystemState', 
    'CameraManager',
    'FaceDetector',
    'ESP32Controller',
    'SSRController'
]