# SpecMPC

SpecMPC is a Python package for interfacing with a Motorized Probe Controller
(BIGTREETECH SKR MINI E3 V3.0) used in Bruker BioSpin products.
The name combines “spec,” short for spectrometer, with “MPC,” short for
Motorized Probe Controller.

The controller is used to:

1. Move the iris rod of an EPR probe linearly on the Z axis.
2. Turn a goniometer on the X axis.

## Requirements

- Python 3.8 or later
- numpy
- pySerial

## Installation
Install through PyPI:
```console
python -m pip install SpecMPC
```

From the project root, install SpecMPC with pip:

```console
python -m pip install .
```

For development, install it in editable mode:

```console
python -m pip install -e .
```

## Terminal Control Panel

After installation, the `SpecMPC` command opens an interactive control panel.

Use auto-detection:

```console
SpecMPC
```

Or specify the serial port and baud rate:

```console
SpecMPC -p COM3 -b 96000
```

All connection arguments are optional. If an argument is skipped, SpecMPC uses
the default value from `MPC`.

Available startup options:

```console
SpecMPC [-h] [-p PORT] [-b BAUD_RATE] [--write-timeout WRITE_TIMEOUT] [--timeout TIMEOUT] [-v VERBOSE]
```

Inside the control panel, call public `MPC` methods by typing the method name
followed by arguments:

```text
SpecMPC> status
SpecMPC> move IRIS 0.8
SpecMPC> theta Goniometer 15
SpecMPC> feedrate IRIS 5
SpecMPC> set_axis_alias Z Probe
SpecMPC> homing_sensitivity IRIS 120
SpecMPC> relative true
SpecMPC> send_command M114 true
SpecMPC> help
SpecMPC> exit
```

Argument values such as numbers, `true`, `false`, and `none` are converted to
Python values automatically.

Axis aliases are display names only. By default, `Z` is shown as `IRIS` and
`X` is shown as `Goniometer`; commands sent to the controller still use the
underlying `X`, `Y`, `Z`, or `E` axis letters.

## Graphical Control Panel

SpecMPC also includes a Tkinter GUI. Start it with:

```console
SpecMPC-gui
```

You can pre-fill the connection settings from the command line:

```console
SpecMPC-gui -p COM3 -b 96000
```

The GUI attempts to connect automatically when it opens. By default, the port
selector uses `Auto`, which lets SpecMPC detect the controller. To open the GUI
without connecting automatically:

```console
SpecMPC-gui --no-auto-connect
```

The GUI provides controls for:

- Top tabs for IRIS, Goniometer, Y, E, Connection, Advanced, and Raw command.
- A bottom log window for status and command output.
- Connecting and disconnecting from the controller.
- A connection LED: red for disconnected, green for connected, and orange while busy.
- Selecting a motion axis directly from the top-level tabs.
- Moving a linear axis.
- Rotating a rotational axis.
- Viewing a live vertical position rail or rotation dial for the selected axis.
- Homing a selected linear axis.
- Setting home position.
- Reading current status.
- Automatically switching between absolute text-entry moves and relative arrow-step moves.
- Using the Advanced tab to choose an axis independently and edit display name, motion type, motion limits, feedrate, homing sensitivity, motor current, and steps per unit.
- Saving, restoring, and resetting controller settings.
- Sending raw G-code commands.

Display names, motion types, and motion limits changed in the GUI are saved
automatically and loaded the next time the GUI starts. Repository defaults are
stored in `SpecMPC/config/default_config.json`; local GUI changes are saved to
`SpecMPC/config/config.json`, which is ignored by git. IRIS defaults to a linear
range of 0 to 8. The Advanced tab also has an Override motion limits checkbox
for deliberate out-of-range moves on the selected axis only.

The GUI checks the connected serial port periodically. If the controller is
physically disconnected, the connection LED turns red and motion controls are
disabled.

The selected axis controls are type-aware: linear axes enable position arrows,
and rotational axes enable angle arrows. Linear axis tabs show only position
controls, and rotational axis tabs show only angle controls.

The motion text box shows the current position or angle. Edit the value and
press Enter to move in absolute mode. Use the arrow buttons to move by the
selected step; arrow moves automatically switch the controller to relative
mode. Linear axes allow 0.1, 0.5, or 1 mm steps. Rotational axes allow 0.1,
0.5, 1, 5, or 10 degree steps.

## Python API

First, make sure the product is properly installed and connected to the
controller. Connect the controller to the computer with a USB cable and power
on the system.

Then create an `MPC` instance:

```python
import SpecMPC

mpc = SpecMPC.MPC()
```

To specify a port and baud rate:

```python
import SpecMPC

mpc = SpecMPC.MPC(port="COM3", baud_rate=96000)
```

## Sending Commands

Once the connection has been established, send movement commands through the
`MPC` object:

```python
mpc.move("IRIS", 0.8)          # Move the Z-axis rod linearly by 0.8 mm.
mpc.theta("Goniometer", 15)    # Rotate the X-axis plate by 15 degrees.
```

Useful status and setup methods:

```python
print(mpc.status())      # Print cached controller status.
print(mpc.position())    # Query current positions from the controller.
mpc.feedrate("IRIS", 5)  # Set Z-axis feedrate.
mpc.homing_sensitivity("IRIS", 120)
mpc.relative(True)       # Enable relative movement mode.
mpc.home("IRIS")         # Home a linear axis.
mpc.save()               # Save configurable settings to EEPROM.
```

To change display names later, update aliases after creating the controller:

```python
mpc.set_axis_alias("Z", "Probe")
```

## Example Script

```python
import SpecMPC

mpc = SpecMPC.MPC()

mpc.help()
print(mpc.status())

mpc.theta("X", 30)
print(mpc.position())

mpc.theta("X", -60)
print(mpc.position())

mpc.home("X")
print(mpc.position())
```
