'''
This is a package to control a stepper motor using G code. The stepper motor controller has been implemented with B12T-Marlin firmware. 

Company: Bridge 12 Technologies, Inc

Author: Yen-Chun Huang

Date: 07/09/2024
'''
import serial
import serial.tools.list_ports
import time

class SMC:
    def __init__(self, port: str = None, baud_rate = 250000, write_timeout = 0, timeout = 1):
        self.autoConnectSMCSerialPort(port, baud_rate, write_timeout, timeout)
        self.axis = ['X', 'Y', 'Z', 'E']
        self.types = ['r', 'l', 'l', 'l'] # r: rotational, l: linear
        self.positions = self.position()
        self.feedrates = self.feedrate() # unit per second
        self.resolutions = self.steps_per_unit() # step per unit
        self.currents = self.current() # mA

    def help(self):
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

    def info(self):
        for axis in self.axis:
            print('%s current position: %s' %(axis, self.positions[axis]))
            print('%s feedrate: %s' %(axis, self.feedrates[axis]))
            print('%s steps/unit: %s' %(axis, self.resolutions[axis]))
            print('%s current: %s mA' %(axis, self.currents[axis]))

    def move(self, axis, position):
        '''
        Linearly control one axis
        '''
        if axis not in self.axis:
            print('Please provide correct axis.')
            return
        
        if self.types[self.axis.index(axis)] != 'l':
            print('Axis type does not match.')
            return
        
        self.send_command('G0 %s%s'%(axis, position))
        feedrate = self.feedrates[axis]
        difference = abs(self.positions[axis] - position)
        time.sleep(difference/feedrate + 1)
        self.positions = self.position()
        return

    def theta(self, axis, position):
        '''
        Rotationally control one axis
        '''
        if axis not in self.axis:
            print('Please provide correct axis.')
            return
        
        if self.types[self.axis.index(axis)]  != 'r':
            print('Axis type does not match.')
            return

        if position > 360 or position < -360:
            print('position is out of range')
            return
        
        self.send_command('G0 %s%s'%(axis, position))
        feedrate = self.feedrates[axis]
        difference = abs(self.positions[axis] - position)
        time.sleep(difference/feedrate + 0.2)
        self.positions = self.position()
        return
    
    def feedrate(self, axis = None, feedrate = None):
        '''
        Set or read current feedrate
        
        '''
        if feedrate is not None:
            if not axis or axis not in self.axis: 
                print('Please provide correct axis.')
                return
            
            if axis == 'X' and (feedrate >= 15 or feedrate <= 0):
                print('X axis feedrate cannot exceed 15 or lower than 0')
                return
            self.send_command('M203 %s%s'%(axis, feedrate))
            self.feedrates[axis] = feedrate
            
        else:
            feedrates = self.send_command('M203', True).strip().split(' ')[1:] # remove M203 as the first return element
            feedrate_detail = {axis: float(feedrate.replace(axis, '')) for axis, feedrate in zip(self.axis, feedrates)}               
            return feedrate_detail
        

    def position(self, axis = None, position = None):
        '''
        Set or read current position
        
        '''
        if position is not None:
            if not axis or axis not in self.axis: 
                print('Please provide correct axis.')
                return
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
    
    def home(self, axis = None):
        '''
        Recover to home position
        
        '''
        if not axis:
            for axis in self.axis:
                if not self.home(axis):
                    print(axis, 'homing fails')
            
        else:
            axis_type = self.types[self.axis.index(axis)]
            if axis_type == 'l':
                self.move(axis, 0)
                return True
            
            elif axis_type == 'r':
                self.theta(axis, 0)
                return True
            else:
                print('Axis type is not supported.')
                return False
    
    def set_home(self, axis = None):
        if not axis:
            for axis in self.axis:
                self.position(axis, 0)
        else:
            self.position(axis, 0)
            return
        
    def current(self, axis = None, current = None):
        '''
        Set or read stepper motor currents in milliamps units.
        '''
        if current is not None:
            if not axis or axis not in self.axis: 
                print('Please provide correct axis.')
                return
            
            self.send_command('M906 %s%s'%(axis, current))
            self.currents[axis] = current
        

        currents = self.send_command('M906', True, lines = 4).replace(' driver current: ', '').split('\n')
        currents = {axis: float(current.replace(axis, '')) for axis, current in zip(self.axis, currents)}   
        return currents

    def steps_per_unit(self, axis = None, step = None):
        '''
        This setting affects how many steps will be done for each unit of movement.

        Please be notified that the calculation for this value involves the default microsteps value of 16 in the factory settings.

        '''
        if step is not None:
            if not axis or axis not in self.axis: 
                print('Please provide correct axis.')
                return
            
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
        return

    def restore(self):
        '''
        Load all saved settings from EEPROM.
        '''
        self.send_command('M501')
        return
    
    def reset(self):
        '''
        Reset all configurable settings to their factory defaults. This only changes the settings in memory, not on EEPROM.
        '''
        self.send_command('M502')
        return

    def autoConnectSMCSerialPort(self, port, baud_rate, write_timeout, timeout):
        device_list = []
        if port:
            device_list.append(port)
        
        if not device_list:
            ports = list(serial.tools.list_ports.comports())
            for port in ports:
                if port.vid == 1155 or port.pid == 22336:
                    device_list.append(port.device)
            
        for device in device_list:
            try:
                self.ser = serial.Serial(device, baud_rate, write_timeout = write_timeout, timeout = timeout)
                self.ser.reset_input_buffer()
                return
            except:
                print('Connection fails on port %s' %port.device)
        
        raise ConnectionError('No stepper motor controller is found.')
    
    def send_command(self, command, recv = False, lines = 1):
        self.ser.reset_input_buffer()  # reset and flush buffer
        send_string = "%s\n" % command
        send_bytes = send_string.encode("utf-8")
        self.ser.write(send_bytes)
        time.sleep(0.1)
        if recv == True:
                i = 0
                from_mps_string = ''
                while i < lines:
                    from_mps_bytes = self.ser.readline()
                    try:
                        if i == 0:
                            from_mps_string += from_mps_bytes.decode("utf-8").rstrip()
                        else:
                            from_mps_string += '\n' + from_mps_bytes.decode("utf-8").rstrip()
                    except:
                        print('Warning: the decode is not working appropriately.')
                    i += 1
                return from_mps_string
    def __del__(self):
        if self.ser.is_open:
            # self.send_command('G0 X0')
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

    
    
