import argparse
import json
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext, ttk

import serial.tools.list_ports

from .pySMC import DEFAULT_AXIS_ALIASES, SMC
from .version import __version__


DEFAULT_BAUD_RATE = 250000
DEFAULT_WRITE_TIMEOUT = 0
DEFAULT_TIMEOUT = 1
AUTO_PORT_LABEL = 'Auto'
LINEAR_STEP_VALUES = ('0.1', '0.5', '1')
ROTATION_STEP_VALUES = ('0.1', '0.5', '1', '5', '10')
DEFAULT_AXIS_ORDER = ('Z', 'X', 'Y', 'E')
CONFIG_DIR = Path(__file__).resolve().parent / 'config'
CONFIG_PATH = CONFIG_DIR / 'config.json'


def _load_saved_axis_aliases():
    """
    Load saved GUI axis aliases from the user config file.

    Returns:
        Saved aliases keyed by controller axis, or an empty dictionary when no
        valid config file exists.
    """
    try:
        with CONFIG_PATH.open('r', encoding='utf-8') as config_file:
            config = json.load(config_file)
    except (OSError, json.JSONDecodeError):
        return {}

    aliases = config.get('axis_aliases', {})
    if not isinstance(aliases, dict):
        return {}
    return {str(axis).upper(): str(alias) for axis, alias in aliases.items()}


def _save_axis_aliases(axis_aliases):
    """
    Save GUI axis aliases to the user config file.

    Args:
        axis_aliases: Mapping of controller axis to display alias.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    config = {'axis_aliases': axis_aliases}
    with CONFIG_PATH.open('w', encoding='utf-8') as config_file:
        json.dump(config, config_file, indent=2, sort_keys=True)
        config_file.write('\n')


class SMCGui(tk.Tk):
    """
    Tkinter desktop control panel for a Stepper Motor Controller.

    The GUI owns one optional ``SMC`` instance and runs serial operations in a
    background thread so long-running moves do not block the interface.
    """

    def __init__(self, port=None, baud_rate=DEFAULT_BAUD_RATE, write_timeout=DEFAULT_WRITE_TIMEOUT, timeout=DEFAULT_TIMEOUT, auto_connect=True, axis_aliases=None):
        """
        Create the GUI and optionally pre-fill connection settings.

        Args:
            port: Optional serial port name to pre-fill.
            baud_rate: Initial baud rate value.
            write_timeout: Initial serial write timeout in seconds.
            timeout: Initial serial read timeout in seconds.
            auto_connect: If ``True``, attempt to connect after the GUI opens.
            axis_aliases: Optional display aliases keyed by controller axis.
        """
        super().__init__()
        self.title('pySMC Control Panel')
        self.geometry('560x460')
        self.minsize(520, 380)

        self.smc = None
        self.busy = False
        self.axis_aliases = dict(DEFAULT_AXIS_ALIASES)
        self.axis_aliases.update(_load_saved_axis_aliases())
        if axis_aliases:
            self.axis_aliases.update(axis_aliases)
        self.axis_label_to_axis = {}
        self.axis_to_label = {}
        self.axis_tab_frames = {}
        self.axis_page_widgets = {}
        self._axis_labels(DEFAULT_AXIS_ORDER)

        self.port_var = tk.StringVar(value=port or AUTO_PORT_LABEL)
        self.baud_var = tk.StringVar(value=str(baud_rate))
        self.write_timeout_var = tk.StringVar(value=str(write_timeout))
        self.timeout_var = tk.StringVar(value=str(timeout))
        self.connection_var = tk.StringVar(value='Disconnected')
        self.relative_var = tk.BooleanVar(value=False)

        self.axis_var = tk.StringVar(value=self._axis_label('Z'))
        self.advanced_axis_var = tk.StringVar(value=self._axis_label('Z'))
        self.position_var = tk.StringVar(value='0')
        self.theta_var = tk.StringVar(value='0')
        self.feedrate_var = tk.StringVar(value='5')
        self.homing_sensitivity_var = tk.StringVar(value='0')
        self.current_var = tk.StringVar(value='800')
        self.steps_var = tk.StringVar(value='400')
        self.axis_alias_var = tk.StringVar(value='')
        self.raw_command_var = tk.StringVar(value='M114')
        self.raw_recv_var = tk.BooleanVar(value=True)

        self._build_ui()
        self._refresh_ports()
        self._set_controls_enabled(False)
        self._update_all_motion_button_layouts()
        if auto_connect:
            self.after(200, self._connect)

    def _build_ui(self):
        """
        Build all Tkinter widgets for the control panel.
        """
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0)
        self.rowconfigure(1, weight=1)

        self.tabs = ttk.Notebook(self)
        self.tabs.grid(row=0, column=0, sticky='ew', padx=12, pady=(12, 6))

        self.connection_tab = ttk.Frame(self.tabs, padding=12)
        self.advanced_tab = ttk.Frame(self.tabs, padding=12)
        self.raw_tab = ttk.Frame(self.tabs, padding=12)
        for axis in DEFAULT_AXIS_ORDER:
            tab = ttk.Frame(self.tabs, padding=12)
            tab.columnconfigure(0, weight=1)
            self.axis_tab_frames[axis] = tab
            self.tabs.add(tab, text=self._axis_label(axis))
            self._build_axis_panel(tab, axis=axis)
        self._use_axis_page_widgets(self._selected_motion_axis())

        for tab in (self.connection_tab, self.advanced_tab, self.raw_tab):
            tab.columnconfigure(0, weight=1)

        self.tabs.add(self.connection_tab, text='Connection')
        self.tabs.add(self.advanced_tab, text='Advanced')
        self.tabs.add(self.raw_tab, text='Raw command')
        self.tabs.bind('<<NotebookTabChanged>>', lambda event: self._on_main_tab_changed())

        self._build_connection_panel(self.connection_tab)
        self._build_advanced_panel(self.advanced_tab)
        self._build_raw_panel(self.raw_tab)

        bottom = ttk.Frame(self, padding=(12, 0, 12, 12))
        bottom.grid(row=1, column=0, sticky='nsew')
        bottom.rowconfigure(1, weight=1)
        bottom.columnconfigure(0, weight=1)
        self._build_status_panel(bottom)

    def _build_connection_panel(self, parent, row=0, column=0, columnspan=1, padx=0):
        """
        Build connection controls.

        Args:
            parent: Parent Tkinter widget.
        """
        frame = ttk.LabelFrame(parent, text='Connection', padding=10)
        self.connection_frame = frame
        frame.grid(row=row, column=column, columnspan=columnspan, sticky='ew', padx=padx, pady=(0, 8))
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text='Port').grid(row=0, column=0, sticky='w')
        self.port_combo = ttk.Combobox(frame, textvariable=self.port_var, width=18)
        self.port_combo.grid(row=0, column=1, sticky='ew', padx=(8, 0))

        ttk.Button(frame, text='Refresh', command=self._refresh_ports).grid(row=0, column=2, padx=(8, 0))

        ttk.Label(frame, text='Baud').grid(row=1, column=0, sticky='w', pady=(8, 0))
        ttk.Entry(frame, textvariable=self.baud_var, width=12).grid(row=1, column=1, sticky='ew', padx=(8, 0), pady=(8, 0))

        ttk.Label(frame, text='Write timeout').grid(row=2, column=0, sticky='w', pady=(8, 0))
        ttk.Entry(frame, textvariable=self.write_timeout_var, width=12).grid(row=2, column=1, sticky='ew', padx=(8, 0), pady=(8, 0))

        ttk.Label(frame, text='Read timeout').grid(row=3, column=0, sticky='w', pady=(8, 0))
        ttk.Entry(frame, textvariable=self.timeout_var, width=12).grid(row=3, column=1, sticky='ew', padx=(8, 0), pady=(8, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=4, column=0, columnspan=3, sticky='ew', pady=(10, 0))
        buttons.columnconfigure((0, 1), weight=1)
        self.connect_button = ttk.Button(buttons, text='Connect', command=self._connect)
        self.connect_button.grid(row=0, column=0, sticky='ew', padx=(0, 4))
        self.disconnect_button = ttk.Button(buttons, text='Disconnect', command=self._disconnect)
        self.disconnect_button.grid(row=0, column=1, sticky='ew', padx=(4, 0))

        ttk.Label(frame, textvariable=self.connection_var).grid(row=5, column=0, columnspan=3, sticky='w', pady=(10, 0))

    def _build_axis_panel(self, parent, row=0, column=0, columnspan=1, padx=0, axis=None):
        """
        Build axis movement and settings controls.

        Args:
            parent: Parent Tkinter widget.
        """
        frame = ttk.LabelFrame(parent, text='Motion', padding=10)
        frame.grid(row=row, column=column, columnspan=columnspan, sticky='nsew', padx=padx, pady=(0, 8))
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(1, weight=1)

        self.position_label = ttk.Label(frame, text='Position')
        self.position_label.grid(row=0, column=0, sticky='w', pady=(0, 0))
        self.position_entry = ttk.Entry(frame, textvariable=self.position_var, width=12)
        self.position_entry.grid(row=0, column=1, sticky='ew', padx=(8, 0), pady=(0, 0))
        self.position_step_combo = ttk.Combobox(frame, textvariable=self.position_var, values=LINEAR_STEP_VALUES, width=12, state='readonly')
        self.move_button_frame = ttk.Frame(frame)
        self.move_button_frame.grid(row=0, column=2, padx=(8, 0), pady=(0, 0))
        self.move_down_button = ttk.Button(self.move_button_frame, text='↓', width=3, command=lambda: self._move_step(-1))
        self.move_down_button.grid(row=0, column=0)
        self.move_button = ttk.Button(self.move_button_frame, text='Move', command=self._move)
        self.move_button.grid(row=0, column=1)
        self.move_up_button = ttk.Button(self.move_button_frame, text='↑', width=3, command=lambda: self._move_step(1))
        self.move_up_button.grid(row=0, column=2)

        self.theta_label = ttk.Label(frame, text='Angle deg')
        self.theta_label.grid(row=1, column=0, sticky='w', pady=(8, 0))
        self.theta_entry = ttk.Entry(frame, textvariable=self.theta_var, width=12)
        self.theta_entry.grid(row=1, column=1, sticky='ew', padx=(8, 0), pady=(8, 0))
        self.theta_step_combo = ttk.Combobox(frame, textvariable=self.theta_var, values=ROTATION_STEP_VALUES, width=12, state='readonly')
        self.theta_button_frame = ttk.Frame(frame)
        self.theta_button_frame.grid(row=1, column=2, padx=(8, 0), pady=(8, 0))
        self.theta_ccw_button = ttk.Button(self.theta_button_frame, text='↶', width=3, command=lambda: self._theta_step(-1))
        self.theta_ccw_button.grid(row=0, column=0)
        self.theta_button = ttk.Button(self.theta_button_frame, text='Rotate', command=self._theta)
        self.theta_button.grid(row=0, column=1)
        self.theta_cw_button = ttk.Button(self.theta_button_frame, text='↷', width=3, command=lambda: self._theta_step(1))
        self.theta_cw_button.grid(row=0, column=2)

        row = ttk.Frame(frame)
        row.grid(row=2, column=0, columnspan=3, sticky='ew', pady=(10, 0))
        row.columnconfigure((0, 1, 2), weight=1)
        self.home_axis_button = ttk.Button(row, text='Home Axis', command=self._home_axis)
        self.home_axis_button.grid(row=0, column=0, sticky='ew', padx=(0, 4))
        self.set_home_button = ttk.Button(row, text='Set Home', command=self._set_home)
        self.set_home_button.grid(row=0, column=1, sticky='ew', padx=4)
        self.current_status_button = ttk.Button(row, text='Current Status', command=self._refresh_status)
        self.current_status_button.grid(row=0, column=2, sticky='ew', padx=(4, 0))

        self.relative_check = ttk.Checkbutton(frame, text='Relative mode', variable=self.relative_var, command=self._set_relative)
        self.relative_check.grid(row=3, column=0, columnspan=3, sticky='w', pady=(10, 0))

        widgets = {
            'axis_frame': frame,
            'position_label': self.position_label,
            'position_entry': self.position_entry,
            'position_step_combo': self.position_step_combo,
            'move_button_frame': self.move_button_frame,
            'move_down_button': self.move_down_button,
            'move_button': self.move_button,
            'move_up_button': self.move_up_button,
            'theta_label': self.theta_label,
            'theta_entry': self.theta_entry,
            'theta_step_combo': self.theta_step_combo,
            'theta_button_frame': self.theta_button_frame,
            'theta_ccw_button': self.theta_ccw_button,
            'theta_button': self.theta_button,
            'theta_cw_button': self.theta_cw_button,
            'home_axis_button': self.home_axis_button,
            'set_home_button': self.set_home_button,
            'current_status_button': self.current_status_button,
            'relative_check': self.relative_check,
        }
        if axis:
            self.axis_page_widgets[axis] = widgets
            if axis == self._selected_motion_axis():
                self._use_axis_page_widgets(axis)

    def _build_advanced_panel(self, parent, row=0, column=0, columnspan=1, padx=0):
        """
        Build advanced per-axis settings controls.

        Args:
            parent: Parent Tkinter widget.
        """
        frame = ttk.LabelFrame(parent, text='Axis Settings', padding=10)
        self.advanced_frame = frame
        frame.grid(row=row, column=column, columnspan=columnspan, sticky='nsew', padx=padx, pady=(0, 8))
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text='Axis').grid(row=0, column=0, sticky='w')
        self.advanced_axis_combo = ttk.Combobox(frame, textvariable=self.advanced_axis_var, width=14, state='readonly')
        self.advanced_axis_combo.configure(values=self._axis_labels(DEFAULT_AXIS_ORDER))
        self.advanced_axis_combo.grid(row=0, column=1, sticky='ew', padx=(8, 0))
        self.advanced_axis_combo.bind('<<ComboboxSelected>>', lambda event: self._update_setting_values())

        ttk.Label(frame, text='Display name').grid(row=1, column=0, sticky='w', pady=(8, 0))
        ttk.Entry(frame, textvariable=self.axis_alias_var, width=14).grid(row=1, column=1, sticky='ew', padx=(8, 0), pady=(8, 0))
        ttk.Button(frame, text='Set', command=self._set_axis_alias).grid(row=1, column=2, padx=(8, 0), pady=(8, 0))

        rows = (
            ('Feedrate unit/s', self.feedrate_var, self._set_feedrate),
            ('Homing sensitivity', self.homing_sensitivity_var, self._set_homing_sensitivity),
            ('Current mA', self.current_var, self._set_current),
            ('Steps/unit', self.steps_var, self._set_steps),
        )
        for index, (label, variable, command) in enumerate(rows, start=2):
            ttk.Label(frame, text=label).grid(row=index, column=0, sticky='w', pady=(8, 0))
            ttk.Entry(frame, textvariable=variable, width=14).grid(row=index, column=1, sticky='ew', padx=(8, 0), pady=(8, 0))
            ttk.Button(frame, text='Set', command=command).grid(row=index, column=2, padx=(8, 0), pady=(8, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=6, column=0, columnspan=3, sticky='ew', pady=(12, 0))
        buttons.columnconfigure((0, 1, 2), weight=1)
        ttk.Button(buttons, text='Save', command=self._save).grid(row=0, column=0, sticky='ew', padx=(0, 4))
        ttk.Button(buttons, text='Restore', command=self._restore).grid(row=0, column=1, sticky='ew', padx=4)
        ttk.Button(buttons, text='Reset', command=self._reset).grid(row=0, column=2, sticky='ew', padx=(4, 0))

    def _build_raw_panel(self, parent, row=0, column=0, columnspan=1, padx=0):
        """
        Build raw G-code controls.

        Args:
            parent: Parent Tkinter widget.
        """
        frame = ttk.LabelFrame(parent, text='Raw Command', padding=10)
        self.raw_frame = frame
        frame.grid(row=row, column=column, columnspan=columnspan, sticky='ew', padx=padx)
        frame.columnconfigure(0, weight=1)

        ttk.Entry(frame, textvariable=self.raw_command_var).grid(row=0, column=0, sticky='ew')
        row = ttk.Frame(frame)
        row.grid(row=1, column=0, sticky='ew', pady=(8, 0))
        row.columnconfigure(1, weight=1)
        ttk.Checkbutton(row, text='Read response', variable=self.raw_recv_var).grid(row=0, column=0, sticky='w')
        ttk.Button(row, text='Send', command=self._send_raw).grid(row=0, column=1, sticky='e')

    def _build_status_panel(self, parent):
        """
        Build status and log output controls.

        Args:
            parent: Parent Tkinter widget.
        """
        top = ttk.Frame(parent)
        top.grid(row=0, column=0, sticky='ew', pady=(0, 8))
        top.columnconfigure(0, weight=1)

        ttk.Label(top, text='Status and Log').grid(row=0, column=0, sticky='w')
        self.refresh_status_button = ttk.Button(top, text='Refresh Status', command=self._refresh_status)
        self.refresh_status_button.grid(row=0, column=1, sticky='e', padx=(0, 8))
        self.clear_log_button = ttk.Button(top, text='Clear', command=self._clear_log)
        self.clear_log_button.grid(row=0, column=2, sticky='e')

        self.log = scrolledtext.ScrolledText(parent, height=8, wrap='word', state='disabled')
        self.log.grid(row=1, column=0, sticky='nsew')

    def _refresh_ports(self):
        """
        Refresh the serial port dropdown from currently available ports.
        """
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo['values'] = [AUTO_PORT_LABEL] + ports
        if not self.port_var.get():
            self.port_var.set(AUTO_PORT_LABEL)

    def _connect(self):
        """
        Connect to the configured serial port.
        """
        if self.busy:
            return
        if self.smc:
            self._disconnect()

        try:
            port = self.port_var.get()
            if not port or port == AUTO_PORT_LABEL:
                port = None
            baud_rate = int(self.baud_var.get())
            write_timeout = float(self.write_timeout_var.get())
            timeout = float(self.timeout_var.get())
        except ValueError as error:
            messagebox.showerror('Invalid connection setting', str(error))
            return

        def task():
            return SMC(port=port, baud_rate=baud_rate, write_timeout=write_timeout, timeout=timeout, axis_aliases=self.axis_aliases)

        def done(smc):
            self.smc = smc
            self.axis_aliases = dict(self.smc.axis_aliases)
            self._load_axis_configuration()
            self.relative_var.set(self.smc.relative())
            self.connection_var.set('Connected')
            self._set_controls_enabled(True)
            self._update_value_fields()
            self._update_axis_controls()
            self._log('Connected to SMC.')
            self._log(self.smc.status())

        self._run_task(task, done, 'Connection failed')

    def _disconnect(self):
        """
        Close the current serial connection.
        """
        if self.smc and getattr(self.smc, 'ser', None) and self.smc.ser.is_open:
            self.smc.ser.close()
        self.smc = None
        self.connection_var.set('Disconnected')
        self._set_controls_enabled(False)
        self._log('Disconnected.')

    def _axis_labels(self, axes):
        """
        Return display labels for controller axes and refresh lookup tables.
        """
        self.axis_label_to_axis = {}
        self.axis_to_label = {}
        labels = []
        for axis in axes:
            label = self.axis_aliases.get(axis, axis)
            if label in self.axis_label_to_axis:
                label = f'{label} ({axis})'
            labels.append(label)
            self.axis_label_to_axis[label] = axis
            self.axis_to_label[axis] = label
        return tuple(labels)

    def _axis_label(self, axis):
        """
        Return the GUI label for a controller axis.
        """
        return self.axis_to_label.get(axis, self.axis_aliases.get(axis, axis))

    def _refresh_axis_tabs(self, axes):
        """
        Rename and select top-level motion-axis tabs for the current axes.
        """
        if not hasattr(self, 'tabs'):
            return

        selected_axis = self._selected_motion_axis()
        active_axes = set(axes)

        for axis in axes:
            tab = self.axis_tab_frames.get(axis)
            if tab is not None:
                self.tabs.tab(tab, text=self._axis_label(axis))

        for axis, tab in list(self.axis_tab_frames.items()):
            if axis not in active_axes and str(tab) in self.tabs.tabs():
                self.tabs.hide(tab)

        if selected_axis not in active_axes:
            selected_axis = axes[0] if axes else ''
        current_tab = self.tabs.select()
        current_tab_is_axis = any(str(tab) == current_tab for tab in self.axis_tab_frames.values())

        if selected_axis:
            self.axis_var.set(self._axis_label(selected_axis))
            self._use_axis_page_widgets(selected_axis)
            tab = self.axis_tab_frames.get(selected_axis)
            if current_tab_is_axis and tab is not None and str(tab) in self.tabs.tabs():
                self.tabs.select(tab)
        else:
            self.axis_var.set('')

    def _use_axis_page_widgets(self, axis):
        """
        Point shared widget references at the selected axis page.
        """
        widgets = self.axis_page_widgets.get(axis)
        if not widgets:
            return
        for name, widget in widgets.items():
            setattr(self, name, widget)

    def _update_all_motion_button_layouts(self):
        """
        Apply the current relative/absolute layout to every axis page.
        """
        selected_axis = self._selected_motion_axis()
        for axis in self.axis_page_widgets:
            self._use_axis_page_widgets(axis)
            self._update_motion_labels()
        self._use_axis_page_widgets(selected_axis)

    def _selected_motion_axis(self):
        """
        Return the controller axis selected in the motion tab.
        """
        return self.axis_label_to_axis.get(self.axis_var.get(), self.axis_var.get())

    def _selected_settings_axis(self):
        """
        Return the controller axis selected in the advanced settings tab.
        """
        return self.axis_label_to_axis.get(self.advanced_axis_var.get(), self.advanced_axis_var.get())

    def _load_axis_configuration(self):
        """
        Load display axis names from the connected controller into GUI dropdowns.
        """
        motion_axis = self._selected_motion_axis()
        settings_axis = self._selected_settings_axis()
        axes = tuple(self.smc.axis)
        labels = self._axis_labels(axes)
        self._refresh_axis_tabs(axes)
        if hasattr(self, 'advanced_axis_combo') and self.advanced_axis_combo.winfo_exists():
            self.advanced_axis_combo.configure(values=labels)

        if motion_axis not in axes:
            motion_axis = axes[0] if axes else ''
        if settings_axis not in axes:
            settings_axis = axes[0] if axes else ''
        self.axis_var.set(self._axis_label(motion_axis) if motion_axis else '')
        self.advanced_axis_var.set(self._axis_label(settings_axis) if settings_axis else '')

    def _selected_axis_type(self):
        """
        Return the configured type for the selected motion axis.

        Returns:
            ``"l"`` for linear axes, ``"r"`` for rotational axes, or ``None``
            when no matching axis is selected.
        """
        if not self.smc:
            return None

        axis = self._selected_motion_axis()
        if axis not in self.smc.axis:
            return None
        return self.smc.types[self.smc.axis.index(axis)]

    def _format_value(self, value):
        """
        Format a controller value for display in an entry field.

        Args:
            value: Numeric or string value to display.

        Returns:
            Compact string representation of the value.
        """
        if isinstance(value, float):
            return f'{value:g}'
        return str(value)

    def _update_value_fields(self):
        """
        Update motion and settings entry fields from cached controller values.
        """
        if self.smc:
            self.relative_var.set(self.smc.relative())
        self._update_all_motion_button_layouts()
        self._update_motion_values()
        self._update_setting_values()

    def _update_motion_values(self):
        """
        Update position or angle entry text for the selected motion axis.
        """
        if not self.smc:
            return

        self._update_motion_labels()
        if self.relative_var.get():
            return

        axis = self._selected_motion_axis()
        if axis not in self.smc.axis or axis not in self.smc.positions:
            return

        value = self._format_value(self.smc.positions[axis])
        axis_type = self._selected_axis_type()

        if axis_type == 'l':
            self.position_var.set(value)
            self.theta_var.set('')
        elif axis_type == 'r':
            self.theta_var.set(value)
            self.position_var.set('')

    def _update_motion_values_for_axis_change(self):
        """
        Update motion entry text after selecting a different axis.

        In relative mode, the active motion entry is treated as a movement
        delta and is left alone. The inactive entry is cleared so a disabled
        box does not show a stale value from the previous axis.
        """
        if not self.smc:
            return

        self._update_motion_labels()
        axis_type = self._selected_axis_type()

        if not self.relative_var.get():
            self._update_motion_values()
        elif axis_type == 'l':
            self.theta_var.set('')
        elif axis_type == 'r':
            self.position_var.set('')

    def _update_motion_labels(self):
        """
        Update motion labels to reflect absolute or relative movement mode.
        """
        if self.relative_var.get():
            self.position_label.configure(text='Step')
            self.theta_label.configure(text='Step deg')
        else:
            self.position_label.configure(text='Position')
            self.theta_label.configure(text='Angle deg')
        self._update_motion_button_layout()

    def _update_motion_button_layout(self):
        """
        Show target buttons in absolute mode and direction buttons in relative mode.
        """
        if self.relative_var.get():
            if self.position_var.get() not in LINEAR_STEP_VALUES:
                self.position_var.set(LINEAR_STEP_VALUES[0])
            if self.theta_var.get() not in ROTATION_STEP_VALUES:
                self.theta_var.set(ROTATION_STEP_VALUES[0])

            self.position_entry.grid_remove()
            self.theta_entry.grid_remove()
            self.position_step_combo.grid(row=0, column=1, sticky='ew', padx=(8, 0), pady=(0, 0))
            self.theta_step_combo.grid(row=1, column=1, sticky='ew', padx=(8, 0), pady=(8, 0))
            self.move_button.grid_remove()
            self.theta_button.grid_remove()
            self.move_down_button.grid()
            self.move_up_button.grid()
            self.theta_ccw_button.grid()
            self.theta_cw_button.grid()
        else:
            self.position_step_combo.grid_remove()
            self.theta_step_combo.grid_remove()
            self.position_entry.grid(row=0, column=1, sticky='ew', padx=(8, 0), pady=(0, 0))
            self.theta_entry.grid(row=1, column=1, sticky='ew', padx=(8, 0), pady=(8, 0))
            self.move_down_button.grid_remove()
            self.move_up_button.grid_remove()
            self.theta_ccw_button.grid_remove()
            self.theta_cw_button.grid_remove()
            self.move_button.grid()
            self.theta_button.grid()

    def _update_setting_values(self):
        """
        Update feedrate, current, and steps/unit text for the settings axis.
        """
        if not self.smc:
            return

        axis = self._selected_settings_axis()
        self.axis_alias_var.set(self._axis_label(axis))
        if axis in self.smc.feedrates:
            self.feedrate_var.set(self._format_value(self.smc.feedrates[axis]))
        if axis in self.smc.homing_sensitivities:
            self.homing_sensitivity_var.set(self._format_value(self.smc.homing_sensitivities[axis]))
        if axis in self.smc.currents:
            self.current_var.set(self._format_value(self.smc.currents[axis]))
        if axis in self.smc.resolutions:
            self.steps_var.set(self._format_value(self.smc.resolutions[axis]))

    def _update_axis_controls(self):
        """
        Enable motion controls that match the selected axis type.
        """
        if not self.smc or self.busy:
            return

        axis_type = self._selected_axis_type()
        can_move = axis_type == 'l'
        can_rotate = axis_type == 'r'
        position_state = 'normal' if can_move else 'disabled'
        theta_state = 'normal' if can_rotate else 'disabled'
        position_readonly_state = 'readonly' if can_move else 'disabled'
        theta_readonly_state = 'readonly' if can_rotate else 'disabled'

        self.position_entry.configure(state=position_state)
        self.position_step_combo.configure(state=position_readonly_state)
        self.move_button.configure(state='normal' if can_move else 'disabled')
        self.move_down_button.configure(state='normal' if can_move else 'disabled')
        self.move_up_button.configure(state='normal' if can_move else 'disabled')
        self.theta_entry.configure(state=theta_state)
        self.theta_step_combo.configure(state=theta_readonly_state)
        self.theta_button.configure(state='normal' if can_rotate else 'disabled')
        self.theta_ccw_button.configure(state='normal' if can_rotate else 'disabled')
        self.theta_cw_button.configure(state='normal' if can_rotate else 'disabled')
        self.home_axis_button.configure(state='normal' if can_move else 'disabled')
        self._update_motion_labels()
        self._update_motion_values_for_axis_change()
        self._update_setting_values()

    def _on_axis_changed(self):
        """
        Update all axis-dependent controls after the selected axis changes.
        """
        self._update_motion_labels()
        self._update_axis_controls()
        self._update_setting_values()

    def _on_main_tab_changed(self):
        """
        Update the selected motion axis after a top-level tab is selected.
        """
        selected_tab = self.tabs.select()
        for axis, tab in self.axis_tab_frames.items():
            if str(tab) == selected_tab:
                self.axis_var.set(self._axis_label(axis))
                self._use_axis_page_widgets(axis)
                self._update_motion_labels()
                self._on_axis_changed()
                break

    def _move(self):
        """
        Move the selected axis linearly.
        """
        axis = self._selected_motion_axis()
        old_value = self.smc.positions.get(axis)
        self._call_smc(
            lambda: self.smc.move(axis, self.position_var.get()),
            'Move complete.',
            update_values=True,
            change_message=lambda: self._change_message(axis, 'position', old_value, self.smc.positions.get(axis)),
        )

    def _move_step(self, direction):
        """
        Move the selected linear axis by a signed relative step.

        Args:
            direction: ``1`` for the up direction and ``-1`` for the down direction.
        """
        axis = self._selected_motion_axis()
        old_value = self.smc.positions.get(axis)
        try:
            step = abs(float(self.position_var.get())) * direction
        except ValueError:
            messagebox.showerror('Invalid step', 'Step must be a number.')
            return

        self._call_smc(
            lambda: self.smc.move(axis, step),
            'Move complete.',
            update_values=True,
            change_message=lambda: self._change_message(axis, 'position', old_value, self.smc.positions.get(axis)),
        )

    def _theta(self):
        """
        Rotate the selected axis.
        """
        axis = self._selected_motion_axis()
        old_value = self.smc.positions.get(axis)
        self._call_smc(
            lambda: self.smc.theta(axis, self.theta_var.get()),
            'Rotation complete.',
            update_values=True,
            change_message=lambda: self._change_message(axis, 'angle', old_value, self.smc.positions.get(axis)),
        )

    def _theta_step(self, direction):
        """
        Rotate the selected axis by a signed relative step.

        Args:
            direction: ``1`` for clockwise and ``-1`` for counterclockwise.
        """
        axis = self._selected_motion_axis()
        old_value = self.smc.positions.get(axis)
        try:
            step = abs(float(self.theta_var.get())) * direction
        except ValueError:
            messagebox.showerror('Invalid step', 'Step must be a number.')
            return

        self._call_smc(
            lambda: self.smc.theta(axis, step),
            'Rotation complete.',
            update_values=True,
            change_message=lambda: self._change_message(axis, 'angle', old_value, self.smc.positions.get(axis)),
        )

    def _home_axis(self):
        """
        Home the selected motion axis.
        """
        axis = self._selected_motion_axis()
        old_value = self.smc.positions.get(axis)
        self._call_smc(
            lambda: self.smc.home(axis),
            'Axis homed.',
            update_values=True,
            change_message=lambda: self._change_message(axis, 'position', old_value, self.smc.positions.get(axis)),
        )

    def _set_home(self):
        """
        Set the selected axis current position as home.
        """
        axis = self._selected_motion_axis()
        old_value = self.smc.positions.get(axis)
        self._call_smc(
            lambda: self.smc.set_home(axis),
            'Home position set.',
            update_values=True,
            change_message=lambda: self._change_message(axis, 'position', old_value, self.smc.positions.get(axis)),
        )

    def _set_relative(self):
        """
        Apply the relative movement checkbox state to the controller.
        """
        old_value = self.smc.relative()
        self._update_all_motion_button_layouts()
        self._call_smc(
            lambda: self.smc.relative(self.relative_var.get()),
            'Movement mode updated.',
            refresh_status=False,
            false_is_error=False,
            update_values=True,
            change_message=lambda: self._change_message('', 'relative mode', old_value, self.smc.relative()),
        )

    def _set_axis_alias(self):
        """
        Update the display-only alias for the selected settings axis.
        """
        if not self.smc:
            messagebox.showerror('Not connected', 'Connect to the SMC first.')
            return

        axis = self._selected_settings_axis()
        alias = self.axis_alias_var.get().strip()
        if not alias:
            messagebox.showerror('Invalid name', 'Display name cannot be empty.')
            return

        old_label = self._axis_label(axis)
        if self.smc.set_axis_alias(axis, alias) is False:
            self._log('Command rejected.')
            return

        self.axis_aliases = dict(self.smc.axis_aliases)
        try:
            _save_axis_aliases(self.axis_aliases)
        except OSError as error:
            messagebox.showerror('Alias not saved', f'Display name changed for this session, but could not save it:\n{error}')
            self._log(f'Alias save failed: {error}')
        self._load_axis_configuration()
        self.axis_alias_var.set(self._axis_label(axis))
        self._update_axis_controls()
        self._log(f'{axis} display name: {old_label} -> {self._axis_label(axis)}')

    def _set_feedrate(self):
        """
        Set feedrate for the selected settings axis.
        """
        axis = self._selected_settings_axis()
        old_value = self.smc.feedrates.get(axis)
        self._call_smc(
            lambda: self.smc.feedrate(axis, float(self.feedrate_var.get())),
            'Feedrate updated.',
            update_values=True,
            change_message=lambda: self._change_message(axis, 'feedrate', old_value, self.smc.feedrates.get(axis)),
        )

    def _set_current(self):
        """
        Set motor current for the selected settings axis.
        """
        axis = self._selected_settings_axis()
        old_value = self.smc.currents.get(axis)
        self._call_smc(
            lambda: self.smc.current(axis, float(self.current_var.get())),
            'Current updated.',
            update_values=True,
            change_message=lambda: self._change_message(axis, 'current', old_value, self.smc.currents.get(axis)),
        )

    def _set_homing_sensitivity(self):
        """
        Set homing sensitivity for the selected axis.
        """
        axis = self._selected_settings_axis()
        old_value = self.smc.homing_sensitivities.get(axis)
        self._call_smc(
            lambda: self.smc.homing_sensitivity(axis, float(self.homing_sensitivity_var.get())),
            'Homing sensitivity updated.',
            update_values=True,
            change_message=lambda: self._change_message(axis, 'homing sensitivity', old_value, self.smc.homing_sensitivities.get(axis)),
        )

    def _set_steps(self):
        """
        Set steps per unit for the selected settings axis.
        """
        axis = self._selected_settings_axis()
        old_value = self.smc.resolutions.get(axis)
        self._call_smc(
            lambda: self.smc.steps_per_unit(axis, float(self.steps_var.get())),
            'Steps/unit updated.',
            update_values=True,
            change_message=lambda: self._change_message(axis, 'steps/unit', old_value, self.smc.resolutions.get(axis)),
        )

    def _save(self):
        """
        Save controller settings to EEPROM.
        """
        self._call_smc(self.smc.save, 'Settings saved.', refresh_status=False)

    def _restore(self):
        """
        Restore controller settings from EEPROM.
        """
        self._call_smc(self.smc.restore, 'Settings restored.')

    def _reset(self):
        """
        Reset controller settings in memory.
        """
        self._call_smc(self.smc.reset, 'Settings reset.')

    def _send_raw(self):
        """
        Send the raw command text to the controller.
        """
        command = self.raw_command_var.get().strip()
        if not command:
            messagebox.showerror('Missing command', 'Enter a command to send.')
            return
        recv = self.raw_recv_var.get()
        self._call_smc(lambda: self.smc.send_command(command, recv), 'Command sent.', refresh_status=False)

    def _refresh_status(self):
        """
        Query current positions and print the cached controller status.
        """
        def task():
            self.smc.positions = self.smc.position()
            self.smc.feedrates = self.smc.feedrate()
            self.smc.homing_sensitivities = self.smc.homing_sensitivity()
            self.smc.resolutions = self.smc.steps_per_unit()
            self.smc.currents = self.smc.current()
            return self.smc.status()

        self._call_smc(task, 'Status refreshed.', refresh_status=False, update_values=True)

    def _call_smc(self, task, success_message, refresh_status=True, false_is_error=True, update_values=False, change_message=None):
        """
        Run an SMC operation if connected.

        Args:
            task: Callable that executes the controller operation.
            success_message: Log message printed when the operation succeeds.
            refresh_status: Whether to log ``smc.status()`` after success.
            false_is_error: Whether a ``False`` result means the operation was
                rejected. Some methods, such as ``relative(False)``, return
                ``False`` as a valid state.
            update_values: Whether to update GUI entry fields from cached
                controller values after success.
            change_message: Optional callable returning a concise old-to-new
                message for the operation log.
        """
        if not self.smc:
            messagebox.showerror('Not connected', 'Connect to the SMC first.')
            return

        def done(result):
            if result is False and false_is_error:
                self._log('Command rejected.')
                return
            if change_message:
                self._log(change_message())
            elif result is not None:
                self._log(str(result))
            if not change_message and success_message:
                self._log(success_message)
            if update_values:
                self._update_value_fields()
            if refresh_status and not change_message and self.smc:
                self._log(self.smc.status())

        self._run_task(task, done, 'Command failed')

    def _run_task(self, task, done, error_title):
        """
        Run a callable in a background thread.

        Args:
            task: Callable to run outside the Tkinter event loop.
            done: Callable invoked on the Tkinter thread with the task result.
            error_title: Message box title used when the task raises.
        """
        if self.busy:
            return
        self.busy = True
        self._set_busy(True)

        def worker():
            try:
                result = task()
            except Exception as error:
                self.after(0, lambda error=error: self._task_failed(error_title, error))
            else:
                self.after(0, lambda result=result: self._task_done(done, result))

        threading.Thread(target=worker, daemon=True).start()

    def _task_done(self, done, result):
        """
        Finish a successful background task on the Tkinter thread.

        Args:
            done: Completion callback.
            result: Task result.
        """
        self.busy = False
        self._set_busy(False)
        done(result)

    def _task_failed(self, title, error):
        """
        Finish a failed background task on the Tkinter thread.

        Args:
            title: Message box title.
            error: Exception raised by the task.
        """
        self.busy = False
        self._set_busy(False)
        self._log(f'{type(error).__name__}: {error}')
        messagebox.showerror(title, str(error))

    def _set_busy(self, busy):
        """
        Update the visible busy state.

        Args:
            busy: Whether a background operation is running.
        """
        if busy:
            self.connection_var.set('Busy')
            self.connect_button.configure(state='disabled')
            self.disconnect_button.configure(state='disabled')
            self._set_controls_enabled(False)
        elif self.smc:
            self.connection_var.set('Connected')
            self.connect_button.configure(state='normal')
            self._set_controls_enabled(True)
        else:
            self.connection_var.set('Disconnected')
            self.connect_button.configure(state='normal')
            self._set_controls_enabled(False)

    def _set_controls_enabled(self, enabled):
        """
        Enable or disable controller-operation widgets.

        Args:
            enabled: Whether controls that require a connection are enabled.
        """
        state = 'normal' if enabled else 'disabled'
        readonly_state = 'readonly' if enabled else 'disabled'
        axis_frames = [widgets['axis_frame'] for widgets in self.axis_page_widgets.values()]
        for widget in (*axis_frames, self.advanced_frame, self.raw_frame, self.refresh_status_button):
            self._set_widget_state(widget, state, readonly_state)

        self.advanced_axis_combo.configure(state=readonly_state)
        self.disconnect_button.configure(state='normal' if enabled else 'disabled')
        if enabled:
            self._update_axis_controls()

    def _set_widget_state(self, widget, state, readonly_state):
        """
        Recursively update widget state where supported.

        Args:
            widget: Widget to update.
            state: Normal widget state.
            readonly_state: State for readonly comboboxes.
        """
        try:
            if isinstance(widget, ttk.Combobox):
                widget.configure(state=readonly_state)
            elif isinstance(widget, (ttk.Button, ttk.Checkbutton, ttk.Entry, ttk.Combobox)):
                widget.configure(state=state)
        except tk.TclError:
            pass

        for child in widget.winfo_children():
            try:
                if isinstance(child, ttk.Combobox):
                    child.configure(state=readonly_state)
                elif isinstance(child, (ttk.Button, ttk.Checkbutton, ttk.Entry, ttk.Combobox)):
                    child.configure(state=state)
            except tk.TclError:
                pass
            self._set_widget_state(child, state, readonly_state)

    def _log(self, message):
        """
        Append text to the status log.

        Args:
            message: Text to append.
        """
        self.log.configure(state='normal')
        self.log.insert('end', f'{message}\n')
        self.log.see('end')
        self.log.configure(state='disabled')

    def _clear_log(self):
        """
        Clear all text from the status log.
        """
        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        self.log.configure(state='disabled')

    def _change_message(self, axis, name, old_value, new_value):
        """
        Format an old-to-new change message for one value.

        Args:
            axis: Axis name, or an empty string for global settings.
            name: Setting name.
            old_value: Value before the operation.
            new_value: Value after the operation.

        Returns:
            Formatted log message.
        """
        prefix = f'{self._axis_label(axis)} ' if axis else ''
        return f'{prefix}{name}: {self._format_value(old_value)} -> {self._format_value(new_value)}'

    def _multi_axis_change_message(self, name, old_values, new_values):
        """
        Format old-to-new change messages for all axes.

        Args:
            name: Setting name.
            old_values: Mapping of axis to old value.
            new_values: Mapping of axis to new value.

        Returns:
            Multi-line formatted log message.
        """
        lines = []
        for axis in self.smc.axis:
            lines.append(self._change_message(axis, name, old_values.get(axis), new_values.get(axis)))
        return '\n'.join(lines)


def build_parser():
    """
    Build the command-line parser for ``pySMC-gui``.

    Returns:
        Configured ``argparse.ArgumentParser`` instance.
    """
    parser = argparse.ArgumentParser(
        prog='pySMC-gui',
        description='Open the pySMC graphical control panel.',
    )
    parser.add_argument('-p', '--port', default=None, help='Serial port to pre-fill, such as COM3.')
    parser.add_argument('-b', '--baud-rate', type=int, default=DEFAULT_BAUD_RATE, help='Serial baud rate. Defaults to 250000.')
    parser.add_argument('--write-timeout', type=float, default=DEFAULT_WRITE_TIMEOUT, help='Serial write timeout in seconds. Defaults to 0.')
    parser.add_argument('--timeout', type=float, default=DEFAULT_TIMEOUT, help='Serial read timeout in seconds. Defaults to 1.')
    parser.add_argument('--no-auto-connect', action='store_true', help='Open the GUI without automatically connecting.')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    return parser


def main(argv=None):
    """
    Run the ``pySMC-gui`` command.

    Args:
        argv: Optional argument list. When omitted, arguments are read from
            ``sys.argv`` by ``argparse``.
    """
    args = build_parser().parse_args(argv)
    app = SMCGui(
        port=args.port,
        baud_rate=args.baud_rate,
        write_timeout=args.write_timeout,
        timeout=args.timeout,
        auto_connect=not args.no_auto_connect,
    )
    app.mainloop()


if __name__ == '__main__':
    main()
