'''
This is a package to control a stepper motor using G code. The stepper motor controller has been implemented with B12T-Marlin firmware. 

Company: Bridge 12 Technologies, Inc

Author: Yen-Chun Huang

Date: 07/09/2024
'''
import serial
import serial.tools.list_ports
import time

MAX_ATTEMPTS = 10
class SMC:
    def __init__(self, port: str = None, baud_rate = 250000, write_timeout = 0, timeout = 1, axis: list[str] = ['X', 'Y', 'Z', 'E'], axis_types: list[str] = ['r', 'l', 'l', 'l'], verbose = 0):
        self.__autoConnectSMCSerialPort(port, baud_rate, write_timeout, timeout)
        self.axis = axis
        self.types = axis_types # r: rotational, l: linear
        self.positions = self.position()
        self.feedrates = self.feedrate() # unit per second
        self.resolutions = self.steps_per_unit() # step per unit
        self.currents = self.current() # mA
        self.relative_mode = False # movement
        self.verbose = verbose
        if self.verbose >= 1:
            print('Stepper motor controller is connected')

    def help(self):
        """
        Print the complete list of commands
        
        """
        print('Current available commands:')
        print('move(axis, position), move an axis linearly')
        print('theta(axis, position), rotate an axis, position is between -360 to 360')
        print('feedrate(axis, feedrate (unit/second)), set a feedrate to an axis or return all axis feedrates with not input arguments')
        print('current(axis, current (mA)), set a current to an axis or return all axis current settings with not input arguments')
        print('steps_per_unit(axis, position), set a steps/unit value to an axis or return all axis steps/unit values with not input arguments')
        print('position(axis, position), set a position to an axis or return all axis current positions with not input arguments')
        print('home(axis), home an axis if the input is provided, otherwise home all axis')
        print('set_home(axis), set current position of an axis as home if the input is provided, otherwise set current positions of all axis home')
        print('save(), save all configurable settings to EEPROM')
        print('restore(), load all saved settings from EEPROM')
        print('reset(), reset all configurable settings to their factory defaults. This only changes the settings in memory, not on EEPROM')
        print('send_command(commands, recv, lines), send command to controller directly.')
        print('info(), return all information')
        print('relative(enable): change movement between relative and absolute')

    def __repr__(self):
        """
        Print the information of all axis.
        
        """
        s = ''
        s += 'Movement Mode: Relative\n' if self.relative_mode else 'Movement Mode: Absolute\n'
        # print('Movement Mode: Relative') if self.relative_mode else print('Movement Mode: Absolute')
        for axis in self.axis:
            s += '%s current position: %s\n' %(axis, self.positions[axis])
            s += '%s feedrate: %s\n' %(axis, self.feedrates[axis])
            s += '%s steps/unit: %s\n' %(axis, self.resolutions[axis])
            s += '%s current: %s mA\n' %(axis, self.currents[axis])

        return s
    
    def move(self, axis: str, position: float|int|str):
        '''
        Linearly control one axis.

        Args:
            axis (str): the axis to control
            position (str): the position to move

        '''
        # try:
        #     position = float(position)
        # except ValueError as e:
        #     #logger.error(log here)
        #     print('position needs to be a valid float')
        #     return 
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

    def theta(self, axis: str, theta: float|int):
        '''
        Rotationally control one axis

        Args:
            axis (str): the axis to control
            theta (float or int): the degree to move to

        '''
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
    
    def feedrate(self, axis: str|None = None, feedrate: float|int|None = None):
        '''
        Set or read current feedrate

        Args:
            axis (str or None): the axis to control
            feedrate (float, int or None): the maximum feedrate of an axis. If None, return feedrate_detail.

        Returns:
            feedrate_detail (dict): the maximum feedrate of all axis

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
        

    def position(self, axis: str| None = None, position: float|int|None = None):
        '''
        Set or read current position

        Args:
            axis (str or None): the axis to control
            position (float, int or None): the position of an axis in a unit. If None, return position_detail.

        Returns:
            position_detail (dict): the current position of all axis
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
    
    def home(self, axis: str|None = None):
        '''
        Recover to home position

        Args:
            axis (str or None): the axis to recover from home. If None, recover all axis.
            
        '''
        if not axis:
            for axis in self.axis:
                if not self.home(axis):
                    if self.verbose >= 1:
                        print(axis, 'homing fails')
                    return False
            
        else:
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
    
    def set_home(self, axis: str|None = None):
        '''
        Set current position as home position

        Args:
            axis (str or None): the axis to set new home. If None, set current positions as home for all axis.
            
        '''
        if not axis:
            for axis in self.axis:
                self.position(axis, 0)
            return True
        else:
            self.position(axis, 0)
            return True
        
    def current(self, axis: str|None = None, current: float|int|None = None):
        '''
        Set or read stepper motor currents in milliamps units.

        Args:
            axis (str or None): the axis to control
            current (float, int or None): the current of an axis in a mA. If None, return current settings.

        Returns:
            currents (dict): the current settings of all axis

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

    def steps_per_unit(self, axis: str|None = None, step: float|int|None = None):
        '''
        This setting affects how many steps will be done for each unit of movement.

        Please be notified that the calculation for this value involves the default microsteps value of 16 in the factory settings.

        Args:
            axis (str or None): the axis to control
            step (float, int or None): the step of an axis in unit. If None, return resolutions settings.

        Returns:
            resolutions (dict): the steps/unit settings of all axis

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
        Save all configurable settings to EEPROM.
        '''
        self.send_command('M500')
        return True

    def restore(self):
        '''
        Load all saved settings from EEPROM.
        '''
        self.send_command('M501')
        return True
    
    def reset(self):
        '''
        Reset all configurable settings to their factory defaults. This only changes the settings in memory, not on EEPROM.
        '''
        self.send_command('M502')
        return True
    
    def relative(self, enable: bool|None = None):
        '''
        Set the movement relative or absolute.

        Args:
            enable (bool): if True, the movement is relative.

        Returns:
            bool: True for relative and False for absolute

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
        Send commands to controller directly.

        Args:
            command (str): the command sent to smc
            recv (bool): if True, it will return the string

        Return:
            from_mps_string (str): the query string
        
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
                return RuntimeError('Maximum attempts reached')
        
    def __autoConnectSMCSerialPort(self, port, baud_rate, write_timeout, timeout):
        device_list = []
        if port:
            device_list.append(port)
        
        if not device_list:
            ports = list(serial.tools.list_ports.comports())
            for port in ports:
                if port.vid == 1155 or port.pid == 22336:
                    device_list.append(port.device)
            
        self.ser = None
        for device in device_list:
            try:
                self.ser = serial.Serial(device, baud_rate, write_timeout = write_timeout, timeout = timeout)
                self.ser.reset_input_buffer()
                return True
            except:
                raise ConnectionError('No stepper motor controller is found on port %s' %port.device)
        
    
    def __del__(self):
        if self.ser and self.ser.is_open:
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

    
    
