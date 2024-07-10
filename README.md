# README #

pyB12SMC is a python package for interfacing with Stepper Motor Controller (BIGTREETECH SKR MINI E3 V3.0) used in Bridge 12 Technologies products.

The controller can do:

1. Move the rod (such as Iris) linearly.

2. Spin the motor (such Goniometer) rotationally. 

### Requirements ###

* Python3 (>= 3.10)
* numpy, pySerial

### Communicating with the Bridge12 SMC ###

First make sure the B12T products with a stepper motor controller installed is connected to the computer via a USB cable and the system is powered ON.

In a terminal window, start a python environment

```console
python
```

```python
import pyB12SMC

smc = pyB12SMC.SMC()
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
import pyB12SMC

smc = pyB12SMC.SMC()
smc.help() # print available commands
smc.info() # print current stepper motor details
smc.theta('X', 30) # move the X-axis plate rotationally by 30 degree
print(smc.position()) # query the current positions of all axis
smc.theta('X', -60) # move the X-axis plate rotationally by -60 degree
print(smc.position()) # query the current positions of all axis
smc.home('X') # home X-axis 
print(smc.position()) # query the current positions of all axis

```
