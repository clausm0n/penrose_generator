from .Operations import Operations
from .Server import run_server
# from .Effects import Effects
from .Tile import Tile
from .ProceduralRenderer import ProceduralRenderer
from .GUIOverlay import GUIOverlay
from .events import (
    update_event, toggle_shader_event, randomize_colors_event,
    shutdown_event, toggle_regions_event, toggle_gui_event
)

# Only export Bluetooth components if not in local mode
import os
if not os.environ.get('PENROSE_LOCAL_MODE'):
    try:
        from .PenroseBluetoothServer import run_bluetooth_server
        __all__ = ['Operations', 'run_server', 'Effects', 'Tile',
                   'ProceduralRenderer', 'run_bluetooth_server', 'GUIOverlay']
    except ImportError:
        __all__ = ['Operations', 'run_server', 'Effects', 'Tile',
                   'ProceduralRenderer', 'GUIOverlay']
else:
    __all__ = ['Operations', 'run_server', 'Effects', 'Tile',
               'ProceduralRenderer', 'GUIOverlay']
