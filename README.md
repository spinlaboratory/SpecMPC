# pySMC

pySMC is a Python package for interfacing with a Stepper Motor Controller
(BIGTREETECH SKR MINI E3 V3.0) used in Bruker BioSpin products.

The controller is used to:

1. Move the iris rod of an EPR probe linearly on the Z axis.
2. Turn a goniometer on the X axis.

## Requirements

- Python 3.8 or later
- numpy
- pySerial

## Installation

From the project root, install pySMC with pip:

```console
python -m pip install .
```

For development, install it in editable mode:

```console
python -m pip install -e .
```

## Terminal Control Panel

After installation, the `pySMC` command opens an interactive control panel.

Use auto-detection:

```console
pySMC
```

Or specify the serial port and baud rate:

```console
pySMC -p COM3 -b 96000
```

All connection arguments are optional. If an argument is skipped, pySMC uses
the default value from `SMC`.

Available startup options:

```console
pySMC [-h] [-p PORT] [-b BAUD_RATE] [--write-timeout WRITE_TIMEOUT] [--timeout TIMEOUT] [-v VERBOSE]
```

Inside the control panel, call public `SMC` methods by typing the method name
followed by arguments:

```text
pySMC> status
pySMC> move Z 0.8
pySMC> theta X 15
pySMC> feedrate Z 5
pySMC> homing_sensitivity Z 120
pySMC> relative true
pySMC> send_command M114 true
pySMC> help
pySMC> exit
```

Argument values such as numbers, `true`, `false`, and `none` are converted to
Python values automatically.

## Graphical Control Panel

pySMC also includes a Tkinter GUI. Start it with:

```console
pySMC-gui
```

You can pre-fill the connection settings from the command line:

```console
pySMC-gui -p COM3 -b 96000
```

The GUI provides controls for:

- Connecting and disconnecting from the controller.
- Selecting one axis and controlling its motion/settings from a single Axis Control panel.
- Moving a linear axis.
- Rotating a rotational axis.
- Homing one axis or all axes.
- Setting home position.
- Reading current status.
- Switching relative movement mode.
- Opening Advanced Settings to choose an axis independently and edit feedrate, homing sensitivity, motor current, and steps per unit.
- Saving, restoring, and resetting controller settings.
- Sending raw G-code commands.
- Viewing status and command output.

The selected axis controls are type-aware: linear axes enable the Move control,
and rotational axes enable the Rotate control.

## Python API

First, make sure the product is properly installed and connected to the
controller. Connect the controller to the computer with a USB cable and power
on the system.

Then create an `SMC` instance:

```python
import pySMC

smc = pySMC.SMC()
```

To specify a port and baud rate:

```python
import pySMC

smc = pySMC.SMC(port="COM3", baud_rate=96000)
```

## Sending Commands

Once the connection has been established, send movement commands through the
`SMC` object:

```python
smc.move("Z", 0.8)   # Move the Z-axis rod linearly by 0.8 mm.
smc.theta("X", 15)   # Rotate the X-axis plate by 15 degrees.
```

Useful status and setup methods:

```python
print(smc.status())      # Print cached controller status.
print(smc.position())    # Query current positions from the controller.
smc.feedrate("Z", 5)     # Set Z-axis feedrate.
smc.homing_sensitivity("Z", 120)
smc.relative(True)       # Enable relative movement mode.
smc.home("X")            # Home X-axis.
smc.save()               # Save configurable settings to EEPROM.
```

## Example Script

```python
import pySMC

smc = pySMC.SMC()

smc.help()
print(smc.status())

smc.theta("X", 30)
print(smc.position())

smc.theta("X", -60)
print(smc.position())

smc.home("X")
print(smc.position())
```
