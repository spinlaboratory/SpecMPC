'''
This is a package to control a stepper motor using G code. The stepper motor controller has been implemented with customized Marlin firmware. 

Company: Bruker BioSpin

Author: Yen-Chun Huang

Date: 06/24/2026
'''
import serial
import serial.tools.list_ports
import time
import re
from typing import List, Optional, Union

MAX_ATTEMPTS = 50


def _to_float(value, name):
    """
    Convert a numeric input value to ``float``.

    Args:
        value: Value supplied by the caller.
        name: Argument name used in the error message.

    Returns:
        Converted floating-point value.

    Raises:
        ValueError: If the value cannot be converted to ``float``.
    """
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f'{name} must be a number') from error


def _parse_homing_sensitivity_response(response, axes):
    """
    Parse an ``M914`` homing sensitivity response.

    Args:
        response: Controller response text, for example
            ``"Y homing sensitivity: 8\\r\\nZ homing sensitivity: 25"``.
        axes: Axis names expected by this controller.

    Returns:
        A dictionary containing all expected axes. Axes missing from the
        response are assigned ``0``.
    """
    sensitivities = {axis: 0 for axis in axes}
    for line in response.splitlines():
        match = re.search(r'^\s*([A-Za-z])\s+homing sensitivity:\s*([-+]?\d+(?:\.\d+)?)', line)
        if match:
            axis = match.group(1).upper()
            if axis in sensitivities:
                sensitivities[axis] = float(match.group(2))
    return sensitivities


class SMC:
    """
    Serial interface for a Stepper Motor Controller running Marlin G-code.

    The class wraps common controller operations such as movement, homing,
    status queries, and EEPROM settings. It opens a serial connection during
    initialization and keeps cached copies of axis position, feedrate,
    resolution, current, and movement mode.
    """

    def __init__(self, port: str = None, baud_rate = 250000, write_timeout = 0, timeout = 1, axis: Optional[List[str]] = None, axis_types: Optional[List[str]] = None, verbose = 0):
        """
        Connect to the controller and initialize cached axis settings.

        Args:
            port: Serial port name such as ``"COM3"``. If omitted, pySMC
                attempts to auto-detect the controller.
            baud_rate: Serial baud rate used for the connection.
            write_timeout: Serial write timeout in seconds.
            timeout: Serial read timeout in seconds.
            axis: Axis names managed by the controller.
            axis_types: Axis type for each axis, where ``"r"`` is rotational
                and ``"l"`` is linear.
            verbose: Console output level. Values greater than or equal to 1
                print connection and validation messages.

        Raises:
            ConnectionError: If no controller can be found or opened.
        """
        self.ser = None
        if axis is None:
            axis = ['X', 'Y', 'Z', 'E']
        if axis_types is None:
            axis_types = ['r', 'l', 'l', 'l']
        if len(axis) != len(axis_types):
            raise ValueError('axis and axis_types must have the same length')

        self.__autoConnectSMCSerialPort(port, baud_rate, write_timeout, timeout)
        self.axis = axis
        self.types = axis_types # r: rotational, l: linear
        self.positions = self.position()
        self.feedrates = self.feedrate() # unit per second
        self.homing_sensitivities = self.homing_sensitivity()
        self.resolutions = self.steps_per_unit() # step per unit
        self.currents = self.current() # mA
        self.relative_mode = False # movement
        self.verbose = verbose
        if self.verbose >= 1:
            print('Stepper motor controller is connected')

    def help(self):
        """
        Print a compact command reference for the interactive control panel.

        The output uses the same command syntax accepted by the ``pySMC``
        terminal command, for example ``move Z 0.8`` or ``relative true``.
        """
        commands = [
            ('status', 'Show movement mode, position, feedrate, steps/unit, and current.'),
            ('info', 'Alias for status.'),
            ('move AXIS POSITION', 'Move a linear axis.'),
            ('theta AXIS DEGREE', 'Rotate an axis.'),
            ('feedrate [AXIS FEEDRATE]', 'Read or set feedrate.'),
            ('homing_sensitivity [AXIS VALUE]', 'Read or set homing sensitivity.'),
            ('current [AXIS CURRENT_MA]', 'Read or set motor current.'),
            ('steps_per_unit [AXIS STEPS]', 'Read or set steps per unit.'),
            ('position [AXIS POSITION]', 'Read or set position.'),
            ('home [AXIS]', 'Home all axes or one axis.'),
            ('set_home [AXIS]', 'Set current position as home.'),
            ('relative [true|false]', 'Read or set relative movement mode.'),
            ('send_command COMMAND [RECV]', 'Send raw G-code.'),
            ('save', 'Save settings to EEPROM.'),
            ('restore', 'Load settings from EEPROM.'),
            ('reset', 'Reset settings in memory.'),
            ('exit', 'Leave the control panel.'),
        ]
        examples = [
            'move Z 0.8',
            'theta X 15',
            'feedrate Z 5',
            'send_command M114 true',
        ]

        print('pySMC control panel')
        print('')
        print('Usage:')
        print('  command [arguments]')
        print('')
        print('Commands:')
        for command, description in commands:
            print(f'  {command:<31} {description}')
        print('')
        print('Examples:')
        for example in examples:
            print(f'  {example}')

    def __repr__(self):
        """
        Return a human-readable summary of the current cached controller state.

        Returns:
            A multi-line string containing movement mode, position, feedrate,
            steps/unit, and current for each configured axis.
        """
        s = ''
        s += 'Movement Mode: Relative\n' if self.relative_mode else 'Movement Mode: Absolute\n'
        # print('Movement Mode: Relative') if self.relative_mode else print('Movement Mode: Absolute')
        for axis in self.axis:
            s += '%s current position: %s\n' %(axis, self.positions[axis])
            s += '%s feedrate: %s\n' %(axis, self.feedrates[axis])
            s += '%s homing sensitivity: %s\n' %(axis, self.homing_sensitivities[axis])
            s += '%s steps/unit: %s\n' %(axis, self.resolutions[axis])
            s += '%s current: %s mA\n' %(axis, self.currents[axis])

        return s

    def status(self):
        """
        Return the current cached controller status.

        Returns:
            The same multi-line string produced by ``repr(smc)``.
        """
        return str(self)

    def info(self):
        """
        Return the current cached controller status.

        This is an alias for :meth:`status`.

        Returns:
            The same multi-line string produced by ``status()``.
        """
        return self.status()
    
    def move(self, axis: str, position: Union[float, int, str]):
        '''
        Move a linear axis to a target position.

        Args:
            axis: Axis name to move.
            position: Target position. In absolute mode this is the controller
                coordinate to move to; in relative mode this is the distance to
                move from the current position.

        Returns:
            ``True`` when the command is accepted, or ``False`` when the axis
            is invalid or not configured as linear.

        '''
        try:
            position = _to_float(position, 'position')
        except ValueError as error:
            if self.verbose >= 1:
                print(error)
            return False

        self.relative(self.relative_mode)

        if axis not in self.axis:
            if self.verbose >= 1:
                print('Please provide correct axis.')
            return False
        
        if self.types[self.axis.index(axis)] != 'l':
            if self.verbose >= 1:
                print('Axis type does not match.')
            return False
        
        self.send_command('G0 %s%s'%(axis, position))
        feedrate = self.feedrates[axis]
        difference = abs(position) if self.relative_mode else abs(self.positions[axis] - position)
        time.sleep(difference/feedrate + 0.2)
        self.positions = self.position()
        return True

    def theta(self, axis: str, theta: Union[float, int, str]):
        '''
        Rotate a rotational axis to a target angle.

        Args:
            axis: Axis name to rotate.
            theta: Target angle in degrees. In absolute mode, values must be
                between -360 and 360. In relative mode, this is the angle to
                move from the current position.

        Returns:
            ``True`` when the command is accepted, or ``False`` when the axis
            is invalid, not rotational, or outside the allowed range.

        '''
        try:
            theta = _to_float(theta, 'theta')
        except ValueError as error:
            if self.verbose >= 1:
                print(error)
            return False

        self.relative(self.relative_mode)

        if axis not in self.axis:
            if self.verbose >= 1:
                print('Please provide correct axis.')
            return False
        
        if self.types[self.axis.index(axis)]  != 'r':
            if self.verbose >= 1:
                print('Axis type does not match.')
            return False

        if not self.relative_mode and (theta < -360 or theta > 360):
            if self.verbose >= 1:
                print('position is out of range')
            return False
         
        self.send_command('G0 %s%s'%(axis, theta))
        feedrate = self.feedrates[axis]
        difference = abs(theta) if self.relative_mode else abs(self.positions[axis] - theta)
        time.sleep(difference/feedrate + 0.2)
        if self.relative_mode:
            self.positions[axis] += theta 
            self.position(axis, self.positions[axis])
        self.positions = self.position()

        return True
    
    def feedrate(self, axis: Optional[str] = None, feedrate: Optional[Union[float, int]] = None):
        '''
        Read all feedrates or set the feedrate for one axis.

        Args:
            axis: Axis name to update. Required when ``feedrate`` is provided.
            feedrate: Maximum feedrate to set in controller units per second.
                If omitted, all feedrates are queried from the controller.

        Returns:
            A dictionary of feedrates when reading values, ``False`` for an
            invalid axis or invalid X-axis feedrate, otherwise ``None`` after a
            successful write.

        '''
        if feedrate is not None:
            if not axis or axis not in self.axis: 
                if self.verbose >= 1:
                    print('Please provide correct axis.')
                return False
             
            if axis == 'X' and (feedrate >= 15 or feedrate <= 0):
                if self.verbose >= 1:
                    print('X axis feedrate cannot exceed 15 or lower than 0')
                return False
            self.send_command('M203 %s%s'%(axis, feedrate))
            self.feedrates[axis] = feedrate
            
        else:
            feedrates = self.send_command('M203', True).strip().split(' ')[1:] # remove M203 as the first return element
            feedrate_detail = {axis: float(feedrate.replace(axis, '')) for axis, feedrate in zip(self.axis, feedrates)}               
            return feedrate_detail
        
    def homing_sensitivity(self, axis: Optional[str] = None, sensitivity: Optional[Union[float, int]] = None):
        '''
        Read all homing sensitivities or set the value for one axis.

        Args:
            axis: Axis name to update. Required when ``sensitivity`` is provided.
            sensitivity: Homing sensitivity value to set. If omitted, all
                homing sensitivities are queried from the controller.

        Returns:
            A dictionary of homing sensitivities when reading values, ``False``
            for an invalid axis, otherwise ``None`` after a successful write.

        '''
        if sensitivity is not None:
            if not axis or axis not in self.axis:
                if self.verbose >= 1:
                    print('Please provide correct axis.')
                return False
            self.send_command('M914 %s%s'%(axis, sensitivity))
            self.homing_sensitivities[axis] = sensitivity

        else:
            return _parse_homing_sensitivity_response(self.send_command('M914', True), self.axis)


    def position(self, axis: Optional[str] = None, position: Optional[Union[float, int]] = None):
        '''
        Read all axis positions or set the current position of one axis.

        Args:
            axis: Axis name to update. Required when ``position`` is provided.
            position: Coordinate to assign to the current axis position. If
                omitted, positions are queried from the controller.

        Returns:
            A dictionary of current positions when reading values, ``False``
            for an invalid axis, otherwise ``None`` after a successful write.
        '''
        if position is not None:
            if not axis or axis not in self.axis: 
                if self.verbose >= 1:
                    print('Please provide correct axis.')
                return False
            self.send_command('G92 %s%s'%(axis, position))
            time.sleep(0.2)
            self.positions[axis] = position

        else:
            positions = self.send_command('M114', True).split(' ')
            position_detail = {}
            for position in positions:
                axis = position.split(':')[0]
                if axis in self.axis:
                    val = position.split(':')[1]
                    position_detail[axis] = float(val)
                if axis == 'Count':
                    break
            time.sleep(0.2)
            return position_detail
    
    def home(self, axis: Optional[str] = None):
        '''
        Move one or all axes back to their configured home position.

        Args:
            axis: Axis name to home. If omitted, all configured axes are homed.

        Returns:
            ``True`` when homing succeeds, or ``False`` if an axis is invalid
            or has an unsupported axis type.
            
        '''
        if not axis:
            for axis in self.axis:
                if not self.home(axis):
                    if self.verbose >= 1:
                        print(axis, 'homing fails')
                    return False
            return True
            
        else:
            if axis not in self.axis:
                if self.verbose >= 1:
                    print('Please provide correct axis.')
                return False

            axis_type = self.types[self.axis.index(axis)]
            if axis_type == 'l':
                self.move(axis, 0)
                return True
            
            elif axis_type == 'r':
                self.theta(axis, 0)
                return True
            else:
                if self.verbose >= 1:
                    print('Axis type is not supported.')
                return False
    
    def set_home(self, axis: Optional[str] = None):
        '''
        Set the current position as home for one or all axes.

        Args:
            axis: Axis name to update. If omitted, all configured axes are set
                to position zero.

        Returns:
            ``True`` after the position reset command is sent, or ``False`` if
            an invalid axis is supplied.
            
        '''
        if not axis:
            for axis in self.axis:
                if self.position(axis, 0) is False:
                    return False
            return True
        else:
            return self.position(axis, 0) is not False
        
    def current(self, axis: Optional[str] = None, current: Optional[Union[float, int]] = None):
        '''
        Read all motor currents or set the current for one axis.

        Args:
            axis: Axis name to update. Required when ``current`` is provided.
            current: Motor current in milliamps. If omitted, all motor currents
                are queried from the controller.

        Returns:
            A dictionary of motor currents after reading or writing values, or
            ``False`` for an invalid axis.

        '''
        if current is not None:
            if not axis or axis not in self.axis: 
                if self.verbose >= 1:
                    print('Please provide correct axis.')
                return False
            
            self.send_command('M906 %s%s'%(axis, current))
            self.currents[axis] = current
        
        currents = self.send_command('M906', True).replace(' driver current: ', '').split('\n')
        currents = {axis: float(current.replace(axis, '')) for axis, current in zip(self.axis, currents)}   
        return currents

    def steps_per_unit(self, axis: Optional[str] = None, step: Optional[Union[float, int]] = None):
        '''
        Read all resolutions or set steps per unit for one axis.

        This setting controls how many stepper motor steps are used for each
        unit of motion. The value should account for the controller firmware's
        microstep setting.

        Args:
            axis: Axis name to update. Required when ``step`` is provided.
            step: Steps per unit to write. If omitted, all resolutions are
                queried from the controller.

        Returns:
            A dictionary of steps/unit values when reading values, ``False``
            for an invalid axis, otherwise ``None`` after a successful write.

        '''
        if step is not None:
            if not axis or axis not in self.axis: 
                if self.verbose >= 1:
                    print('Please provide correct axis.')
                return False
             
            self.send_command('M92 %s%s'%(axis, step))
            self.resolutions[axis] = step

        else:
            steps = self.send_command('M92', True).strip().split(' ')[1:] # remove M203 as the first return element
            resolutions = {axis: float(step.replace(axis, '')) for axis, step in zip(self.axis, steps)}   
            return resolutions
        
    def save(self):
        '''
        Save current configurable settings to controller EEPROM.

        Returns:
            ``True`` after the save command is sent.
        '''
        self.send_command('M500')
        return True

    def restore(self):
        '''
        Reload saved configurable settings from controller EEPROM.

        Returns:
            ``True`` after the restore command is sent.
        '''
        self.send_command('M501')
        return True
    
    def reset(self):
        '''
        Reset configurable settings in memory to firmware defaults.

        This does not write to EEPROM. Use :meth:`save` after resetting if the
        defaults should persist after power cycling.

        Returns:
            ``True`` after the reset command is sent.
        '''
        self.send_command('M502')
        return True
    
    def relative(self, enable: Optional[bool] = None):
        '''
        Read or set the controller movement mode.

        Args:
            enable: ``True`` enables relative movement, ``False`` enables
                absolute movement, and ``None`` returns the cached mode without
                sending a command.

        Returns:
            ``True`` when relative mode is active, or ``False`` when absolute
            mode is active.

        '''
        if enable is None:
            return self.relative_mode
         
        if enable:
            self.send_command("G91")
            self.relative_mode = True
            return self.relative_mode
        else:
            self.send_command("G90")
            self.relative_mode = False
            return self.relative_mode
    
    def send_command(self, command: str, recv: bool = False):
        """
        Send a raw command string to the controller.

        Args:
            command: G-code or controller command to send.
            recv: If ``True``, read and return controller response lines until
                an ``ok`` response is received or the retry limit is reached.

        Returns:
            The controller response string when ``recv`` is ``True``. Returns
            ``None`` when no response is requested.

        Raises:
            RuntimeError: If the retry limit is reached while waiting for a
                controller response.
        
        """
        self.ser.reset_input_buffer()  # reset and flush buffer
        send_string = "%s\n" % command
        send_bytes = send_string.encode("utf-8")
        self.ser.write(send_bytes)
        time.sleep(0.1)
        if recv == True:
                attempts = 0
                from_mps_string = ''
                while attempts < MAX_ATTEMPTS:
                    from_mps_bytes = self.ser.readline()
                    try:
                        if attempts == 0:
                            from_mps_string += from_mps_bytes.decode("utf-8").rstrip()
                        else:
                            if 'ok' in from_mps_bytes.decode("utf-8").rstrip():
                                return from_mps_string
                            from_mps_string += '\n' + from_mps_bytes.decode("utf-8").rstrip()
                    except:
                        print('Warning: the decode is not working appropriately.')
                    attempts += 1
                raise RuntimeError('Maximum attempts reached')

    def specman_connect(self, initval: float):
        """
        Return a simple acknowledgement for SpecMan integration checks.

        Args:
            initval: Initial value supplied by the external SpecMan caller.

        Returns:
            A tuple containing an acknowledgement message and ``True``.
        """
        return 'Acknowledged specman connection',True
        
    def __autoConnectSMCSerialPort(self, port, baud_rate, write_timeout, timeout):
        """
        Open the serial connection to the controller.

        Args:
            port: Serial port name or port object. If ``None``, connected ports
                are scanned for the expected controller USB identifiers.
            baud_rate: Serial baud rate.
            write_timeout: Serial write timeout in seconds.
            timeout: Serial read timeout in seconds.

        Returns:
            ``True`` when the serial port opens successfully.

        Raises:
            ConnectionError: If no controller port is found or the serial port
            cannot be opened.
        """
        
        if port is None: # auto detection
            ports = list(serial.tools.list_ports.comports())
            for p in ports:
                if p.vid == 1155 or p.pid == 22336:
                    port = p.device
        
        if port is None:
            raise ConnectionError('Please connect stepper motor controller or specify the port')

        try:
            self.ser = serial.Serial(port, baud_rate, write_timeout = write_timeout, timeout = timeout)
            self.ser.reset_input_buffer()
            return True
        except Exception as error:
            port_name = getattr(port, 'device', port)
            raise ConnectionError('No stepper motor controller is found on port %s' %port_name) from error
        
        
    
    def __del__(self):
        """
        Close the serial port when the object is garbage-collected.
        """
        if getattr(self, 'ser', None) and self.ser.is_open:
            self.ser.close()
                
if __name__ == "__main__":
    smc = SMC()
    print('===========================')
    smc.help()
    print('===========================')
    print('Current information:')
    smc.info()
    print('===========================')
    print('move X to 30 degree')
    smc.theta('X', 30)
    print('get current position')
    print(smc.position())
    print('move X to -60 degree')
    smc.theta('X', -60)
    print('get current position')
    print(smc.position())
    print('home X axis')
    smc.home('X')
    print('get current position')
    print(smc.position())
    print('Done')

    
    
