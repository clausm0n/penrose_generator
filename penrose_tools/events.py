# events.py
from threading import Event

update_event = Event()
toggle_shader_event = Event()
randomize_colors_event = Event()
shutdown_event = Event()
toggle_regions_event = Event()
toggle_gui_event = Event()
