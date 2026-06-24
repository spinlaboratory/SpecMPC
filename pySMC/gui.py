import argparse
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

import serial.tools.list_ports

from .pySMC import SMC
from .version import __version__


DEFAULT_BAUD_RATE = 250000
DEFAULT_WRITE_TIMEOUT = 0
DEFAULT_TIMEOUT = 1


class SMCGui(tk.Tk):
    """
    Tkinter desktop control panel for a Stepper Motor Controller.

    The GUI owns one optional ``SMC`` instance and runs serial operations in a
    background thread so long-running moves do not block the interface.
    """

    def __init__(self, port=None, baud_rate=DEFAULT_BAUD_RATE, write_timeout=DEFAULT_WRITE_TIMEOUT, timeout=DEFAULT_TIMEOUT):
        """
        Create the GUI and optionally pre-fill connection settings.

        Args:
            port: Optional serial port name to pre-fill.
            baud_rate: Initial baud rate value.
            write_timeout: Initial serial write timeout in seconds.
            timeout: Initial serial read timeout in seconds.
        """
        super().__init__()
        self.title('pySMC Control Panel')
        self.geometry('900x620')
        self.minsize(840, 520)

        self.smc = None
        self.busy = False
        self.advanced_window = None

        self.port_var = tk.StringVar(value=port or '')
        self.baud_var = tk.StringVar(value=str(baud_rate))
        self.write_timeout_var = tk.StringVar(value=str(write_timeout))
        self.timeout_var = tk.StringVar(value=str(timeout))
        self.connection_var = tk.StringVar(value='Disconnected')
        self.relative_var = tk.BooleanVar(value=False)

        self.axis_var = tk.StringVar(value='Z')
        self.advanced_axis_var = tk.StringVar(value='Z')
        self.position_var = tk.StringVar(value='0')
        self.theta_var = tk.StringVar(value='0')
        self.feedrate_var = tk.StringVar(value='5')
        self.homing_sensitivity_var = tk.StringVar(value='0')
        self.current_var = tk.StringVar(value='800')
        self.steps_var = tk.StringVar(value='400')
        self.raw_command_var = tk.StringVar(value='M114')
        self.raw_recv_var = tk.BooleanVar(value=True)

        self._build_ui()
        self._refresh_ports()
        self._set_controls_enabled(False)

    def _build_ui(self):
        """
        Build all Tkinter widgets for the control panel.
        """
        self.columnconfigure(0, weight=0)
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left = ttk.Frame(self, padding=12)
        left.grid(row=0, column=0, sticky='nsew')
        left.columnconfigure(0, weight=1)
        left.columnconfigure(1, weight=1)

        right = ttk.Frame(self, padding=(0, 12, 12, 12))
        right.grid(row=0, column=1, sticky='nsew')
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        self._build_connection_panel(left, row=0, column=0, columnspan=2)
        self._build_axis_panel(left, row=1, column=0, columnspan=2)
        self._build_raw_panel(left, row=2, column=0, columnspan=2)
        self._build_status_panel(right)

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

    def _build_axis_panel(self, parent, row=0, column=0, columnspan=1, padx=0):
        """
        Build axis movement and settings controls.

        Args:
            parent: Parent Tkinter widget.
        """
        frame = ttk.LabelFrame(parent, text='Axis Control', padding=10)
        self.axis_frame = frame
        frame.grid(row=row, column=column, columnspan=columnspan, sticky='nsew', padx=padx, pady=(0, 8))
        frame.columnconfigure(1, weight=1)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text='Axis').grid(row=0, column=0, sticky='w')
        self.axis_combo = ttk.Combobox(frame, textvariable=self.axis_var, values=('X', 'Y', 'Z', 'E'), width=8, state='readonly')
        self.axis_combo.grid(row=0, column=1, sticky='ew', padx=(8, 0))
        self.axis_combo.bind('<<ComboboxSelected>>', lambda event: self._on_axis_changed())

        self.position_label = ttk.Label(frame, text='Position')
        self.position_label.grid(row=1, column=0, sticky='w', pady=(8, 0))
        self.position_entry = ttk.Entry(frame, textvariable=self.position_var, width=12)
        self.position_entry.grid(row=1, column=1, sticky='ew', padx=(8, 0), pady=(8, 0))
        self.move_button = ttk.Button(frame, text='Move', command=self._move)
        self.move_button.grid(row=1, column=2, padx=(8, 0), pady=(8, 0))

        self.theta_label = ttk.Label(frame, text='Angle deg')
        self.theta_label.grid(row=2, column=0, sticky='w', pady=(8, 0))
        self.theta_entry = ttk.Entry(frame, textvariable=self.theta_var, width=12)
        self.theta_entry.grid(row=2, column=1, sticky='ew', padx=(8, 0), pady=(8, 0))
        self.theta_button = ttk.Button(frame, text='Rotate', command=self._theta)
        self.theta_button.grid(row=2, column=2, padx=(8, 0), pady=(8, 0))

        row = ttk.Frame(frame)
        row.grid(row=3, column=0, columnspan=3, sticky='ew', pady=(10, 0))
        row.columnconfigure((0, 1, 2, 3), weight=1)
        self.home_axis_button = ttk.Button(row, text='Home Axis', command=self._home_axis)
        self.home_axis_button.grid(row=0, column=0, sticky='ew', padx=(0, 4))
        self.home_all_button = ttk.Button(row, text='Home All', command=self._home_all)
        self.home_all_button.grid(row=0, column=1, sticky='ew', padx=4)
        self.set_home_button = ttk.Button(row, text='Set Home', command=self._set_home)
        self.set_home_button.grid(row=0, column=2, sticky='ew', padx=4)
        self.current_status_button = ttk.Button(row, text='Current Status', command=self._refresh_status)
        self.current_status_button.grid(row=0, column=3, sticky='ew', padx=(4, 0))

        self.relative_check = ttk.Checkbutton(frame, text='Relative mode', variable=self.relative_var, command=self._set_relative)
        self.relative_check.grid(row=4, column=0, columnspan=3, sticky='w', pady=(10, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=3, sticky='ew', pady=(10, 0))
        buttons.columnconfigure(0, weight=1)
        self.advanced_button = ttk.Button(buttons, text='Advanced', command=self._open_advanced_settings)
        self.advanced_button.grid(row=0, column=0, sticky='ew')

    def _open_advanced_settings(self):
        """
        Open the advanced settings window.
        """
        if self.advanced_window and self.advanced_window.winfo_exists():
            self.advanced_window.lift()
            self.advanced_window.focus_force()
            return

        window = tk.Toplevel(self)
        window.title('pySMC Advanced Settings')
        window.geometry('420x300')
        window.minsize(380, 260)
        window.columnconfigure(0, weight=1)
        self.advanced_window = window

        frame = ttk.LabelFrame(window, text='Axis Settings', padding=12)
        self.advanced_settings_frame = frame
        frame.grid(row=0, column=0, sticky='nsew', padx=12, pady=12)
        frame.columnconfigure(1, weight=1)
        window.rowconfigure(0, weight=1)

        ttk.Label(frame, text='Axis').grid(row=0, column=0, sticky='w')
        self.advanced_axis_combo = ttk.Combobox(frame, textvariable=self.advanced_axis_var, width=8, state='readonly')
        if self.smc:
            self.advanced_axis_combo.configure(values=tuple(self.smc.axis))
        self.advanced_axis_combo.grid(row=0, column=1, sticky='ew', padx=(8, 0))
        self.advanced_axis_combo.bind('<<ComboboxSelected>>', lambda event: self._update_setting_values())

        rows = (
            ('Feedrate unit/s', self.feedrate_var, self._set_feedrate),
            ('Homing sensitivity', self.homing_sensitivity_var, self._set_homing_sensitivity),
            ('Current mA', self.current_var, self._set_current),
            ('Steps/unit', self.steps_var, self._set_steps),
        )
        for index, (label, variable, command) in enumerate(rows, start=1):
            ttk.Label(frame, text=label).grid(row=index, column=0, sticky='w', pady=(8, 0))
            ttk.Entry(frame, textvariable=variable, width=14).grid(row=index, column=1, sticky='ew', padx=(8, 0), pady=(8, 0))
            ttk.Button(frame, text='Set', command=command).grid(row=index, column=2, padx=(8, 0), pady=(8, 0))

        buttons = ttk.Frame(frame)
        buttons.grid(row=5, column=0, columnspan=3, sticky='ew', pady=(12, 0))
        buttons.columnconfigure((0, 1, 2), weight=1)
        ttk.Button(buttons, text='Save', command=self._save).grid(row=0, column=0, sticky='ew', padx=(0, 4))
        ttk.Button(buttons, text='Restore', command=self._restore).grid(row=0, column=1, sticky='ew', padx=4)
        ttk.Button(buttons, text='Reset', command=self._reset).grid(row=0, column=2, sticky='ew', padx=(4, 0))

        self.advanced_close_button = ttk.Button(window, text='Close', command=window.destroy)
        self.advanced_close_button.grid(row=1, column=0, sticky='e', padx=12, pady=(0, 12))

        if not self.smc:
            self._set_widget_state(frame, 'disabled', 'disabled')

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

        self.log = scrolledtext.ScrolledText(parent, height=20, wrap='word', state='disabled')
        self.log.grid(row=1, column=0, sticky='nsew')

    def _refresh_ports(self):
        """
        Refresh the serial port dropdown from currently available ports.
        """
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if not self.port_var.get() and ports:
            self.port_var.set(ports[0])

    def _connect(self):
        """
        Connect to the configured serial port.
        """
        if self.busy:
            return
        if self.smc:
            self._disconnect()

        try:
            port = self.port_var.get() or None
            baud_rate = int(self.baud_var.get())
            write_timeout = float(self.write_timeout_var.get())
            timeout = float(self.timeout_var.get())
        except ValueError as error:
            messagebox.showerror('Invalid connection setting', str(error))
            return

        def task():
            return SMC(port=port, baud_rate=baud_rate, write_timeout=write_timeout, timeout=timeout)

        def done(smc):
            self.smc = smc
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

    def _load_axis_configuration(self):
        """
        Load axis names from the connected controller into GUI dropdowns.
        """
        axes = tuple(self.smc.axis)
        self.axis_combo.configure(values=axes)
        if hasattr(self, 'advanced_axis_combo') and self.advanced_axis_combo.winfo_exists():
            self.advanced_axis_combo.configure(values=axes)

        if self.axis_var.get() not in axes:
            self.axis_var.set(axes[0] if axes else '')
        if self.advanced_axis_var.get() not in axes:
            self.advanced_axis_var.set(axes[0] if axes else '')

    def _selected_axis_type(self):
        """
        Return the configured type for the selected motion axis.

        Returns:
            ``"l"`` for linear axes, ``"r"`` for rotational axes, or ``None``
            when no matching axis is selected.
        """
        if not self.smc:
            return None

        axis = self.axis_var.get()
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
        self._update_motion_labels()
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

        axis = self.axis_var.get()
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
            self.position_label.configure(text='Move by')
            self.theta_label.configure(text='Rotate by deg')
        else:
            self.position_label.configure(text='Position')
            self.theta_label.configure(text='Angle deg')

    def _update_setting_values(self):
        """
        Update feedrate, current, and steps/unit text for the settings axis.
        """
        if not self.smc:
            return

        axis = self.advanced_axis_var.get()
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

        self.position_entry.configure(state='normal' if can_move else 'disabled')
        self.move_button.configure(state='normal' if can_move else 'disabled')
        self.theta_entry.configure(state='normal' if can_rotate else 'disabled')
        self.theta_button.configure(state='normal' if can_rotate else 'disabled')
        self._update_motion_labels()
        self._update_motion_values_for_axis_change()
        self._update_setting_values()

    def _on_axis_changed(self):
        """
        Update all axis-dependent controls after the selected axis changes.
        """
        self._update_axis_controls()
        self._update_setting_values()

    def _move(self):
        """
        Move the selected axis linearly.
        """
        axis = self.axis_var.get()
        old_value = self.smc.positions.get(axis)
        self._call_smc(
            lambda: self.smc.move(axis, self.position_var.get()),
            'Move complete.',
            update_values=True,
            change_message=lambda: self._change_message(axis, 'position', old_value, self.smc.positions.get(axis)),
        )

    def _theta(self):
        """
        Rotate the selected axis.
        """
        axis = self.axis_var.get()
        old_value = self.smc.positions.get(axis)
        self._call_smc(
            lambda: self.smc.theta(axis, self.theta_var.get()),
            'Rotation complete.',
            update_values=True,
            change_message=lambda: self._change_message(axis, 'angle', old_value, self.smc.positions.get(axis)),
        )

    def _home_axis(self):
        """
        Home the selected motion axis.
        """
        axis = self.axis_var.get()
        old_value = self.smc.positions.get(axis)
        self._call_smc(
            lambda: self.smc.home(axis),
            'Axis homed.',
            update_values=True,
            change_message=lambda: self._change_message(axis, 'position', old_value, self.smc.positions.get(axis)),
        )

    def _home_all(self):
        """
        Home all configured axes.
        """
        old_values = dict(self.smc.positions)
        self._call_smc(
            lambda: self.smc.home(),
            'All axes homed.',
            update_values=True,
            change_message=lambda: self._multi_axis_change_message('position', old_values, self.smc.positions),
        )

    def _set_home(self):
        """
        Set the selected axis current position as home.
        """
        axis = self.axis_var.get()
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
        self._call_smc(
            lambda: self.smc.relative(self.relative_var.get()),
            'Movement mode updated.',
            refresh_status=False,
            false_is_error=False,
            update_values=True,
            change_message=lambda: self._change_message('', 'relative mode', old_value, self.smc.relative()),
        )

    def _set_feedrate(self):
        """
        Set feedrate for the selected settings axis.
        """
        axis = self.advanced_axis_var.get()
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
        axis = self.advanced_axis_var.get()
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
        axis = self.advanced_axis_var.get()
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
        axis = self.advanced_axis_var.get()
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
        for widget in (self.axis_frame, self.raw_frame, self.refresh_status_button):
            self._set_widget_state(widget, state, readonly_state)

        self.axis_combo.configure(state=readonly_state)
        self.advanced_button.configure(state=state)
        self.disconnect_button.configure(state='normal' if enabled else 'disabled')
        self._set_advanced_window_enabled(enabled)
        if enabled:
            self._update_axis_controls()

    def _set_advanced_window_enabled(self, enabled):
        """
        Enable or disable controls in the advanced settings window.

        Args:
            enabled: Whether advanced settings controls should be enabled.
        """
        if not self.advanced_window or not self.advanced_window.winfo_exists():
            return
        state = 'normal' if enabled else 'disabled'
        if hasattr(self, 'advanced_settings_frame'):
            self._set_widget_state(self.advanced_settings_frame, state, state)

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
        prefix = f'{axis} ' if axis else ''
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
    )
    app.mainloop()


if __name__ == '__main__':
    main()
