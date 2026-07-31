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
pySMC> move IRIS 0.8
pySMC> theta Goniometer 15
pySMC> feedrate IRIS 5
pySMC> set_axis_alias Z Probe
pySMC> homing_sensitivity IRIS 120
pySMC> relative true
pySMC> send_command M114 true
pySMC> help
pySMC> exit
```

Argument values such as numbers, `true`, `false`, and `none` are converted to
Python values automatically.

Axis aliases are display names only. By default, `Z` is shown as `IRIS` and
`X` is shown as `Goniometer`; commands sent to the controller still use the
underlying `X`, `Y`, `Z`, or `E` axis letters.

## Graphical Control Panel

pySMC also includes a Tkinter GUI. Start it with:

```console
pySMC-gui
```

You can pre-fill the connection settings from the command line:

```console
pySMC-gui -p COM3 -b 96000
```

The GUI attempts to connect automatically when it opens. By default, the port
selector uses `Auto`, which lets pySMC detect the controller. To open the GUI
without connecting automatically:

```console
pySMC-gui --no-auto-connect
```

The GUI provides controls for:

- Top tabs for IRIS, Goniometer, Y, E, Connection, Advanced, and Raw command.
- A bottom log window for status and command output.
- Connecting and disconnecting from the controller.
- Selecting a motion axis directly from the top-level tabs.
- Moving a linear axis.
- Rotating a rotational axis.
- Homing a selected linear axis.
- Setting home position.
- Reading current status.
- Switching relative movement mode.
- Using the Advanced tab to choose an axis independently and edit display name, feedrate, homing sensitivity, motor current, and steps per unit.
- Saving, restoring, and resetting controller settings.
- Sending raw G-code commands.

Display names changed in the GUI are saved automatically and loaded the next
time the GUI starts. The config is stored in the package directory at
`pySMC/config/config.json`.

The selected axis controls are type-aware: linear axes enable the Move control,
and rotational axes enable the Rotate control.

In relative mode, the motion entry becomes a step-size dropdown. Linear axes
allow 0.1, 0.5, or 1 mm steps. Rotational axes allow 0.1, 0.5, 1, 5, or 10
degree steps.

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
smc.move("IRIS", 0.8)          # Move the Z-axis rod linearly by 0.8 mm.
smc.theta("Goniometer", 15)    # Rotate the X-axis plate by 15 degrees.
```

Useful status and setup methods:

```python
print(smc.status())      # Print cached controller status.
print(smc.position())    # Query current positions from the controller.
smc.feedrate("IRIS", 5)  # Set Z-axis feedrate.
smc.homing_sensitivity("IRIS", 120)
smc.relative(True)       # Enable relative movement mode.
smc.home("IRIS")         # Home a linear axis.
smc.save()               # Save configurable settings to EEPROM.
```

To change display names later, update aliases after creating the controller:

```python
smc.set_axis_alias("Z", "Probe")
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
