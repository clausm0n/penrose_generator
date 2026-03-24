from .Operations import Operations
from .Server import run_server
from .ProceduralRenderer import ProceduralRenderer
from .GUIOverlay import GUIOverlay
from .DemoController import DemoController
from .events import (
    update_event, toggle_shader_event, randomize_colors_event,
    shutdown_event, toggle_regions_event, toggle_gui_event,
    reset_viewport_event, randomize_gamma_event
)

# Optional: Camera capture (requires opencv-python)
try:
    from .CameraManager import CameraManager
except ImportError:
    CameraManager = None

# Optional: Depth camera capture (uses OpenNI2)
try:
    from .DepthCameraManager import DepthCameraManager
except ImportError:
    DepthCameraManager = None

# Optional: Audio feedback (requires signalflow)
try:
    from .AudioManager import AudioManager, SIGNALFLOW_AVAILABLE as AUDIO_AVAILABLE
except ImportError:
    AudioManager = None
    AUDIO_AVAILABLE = False

# Only export Bluetooth components if not in local mode
import os
if not os.environ.get('PENROSE_LOCAL_MODE'):
    try:
        from .PenroseBluetoothServer import run_bluetooth_server
        __all__ = ['Operations', 'run_server',
                   'ProceduralRenderer', 'run_bluetooth_server',
                   'GUIOverlay', 'CameraManager', 'DepthCameraManager']
    except ImportError:
        __all__ = ['Operations', 'run_server',
                   'ProceduralRenderer', 'GUIOverlay', 'CameraManager', 'DepthCameraManager']
else:
    __all__ = ['Operations', 'run_server',
               'ProceduralRenderer', 'GUIOverlay', 'CameraManager', 'DepthCameraManager']
