# README #

pySMC is a python package for interfacing with Stepper Motor Controller (BIGTREETECH SKR MINI E3 V3.0) used in Bruker BioSpin products.

The stepper motor controller is used to:

1. Move the iris rod of an EPR probe linearly (Z axis)
2. Turn a goniometer (X axis) 

### Requirements ###

* Python3 (>= 3.10)
* numpy, pySerial

### Communicating with the SMC ###

First, make sure the product (e.g. probe, goniometer, etc.) is properly installed and connected to the controller. Connect the controller to the computer via a USB cable, and power ON the system.

In a terminal window (command window), start a Python environment

```console
python
```

```python
import pySMC

smc = pySMC.SMC()
```

The controller will be connected.


### Sending SMC Commands ###

Once the connection has been established, you can send commands to the controller.

```python

smc.move('Z', 0.8) # move the Z-axis rod linearly and horizontally by 0.8 mm

smc.theta('X', 15) # move the X-axis plate rotationally by 15 degree
```

### Example Script ###

```python
import pySMC

smc = pySMC.SMC()
smc.help() # print available commands
smc.info() # print current stepper motor details
smc.theta('X', 30) # move the X-axis plate rotationally by 30 degree
print(smc.position()) # query the current positions of all axis
smc.theta('X', -60) # move the X-axis plate rotationally by -60 degree
print(smc.position()) # query the current positions of all axis
smc.home('X') # home X-axis 
print(smc.position()) # query the current positions of all axis

```
