# lhbctrl

Command-line tool for controlling SteamVR Base Stations (Lighthouse 2.0) via Bluetooth LE.

## Requirements

- Python 3.10+
- Linux (tested on Kali), Windows and macOS should work too
- Bluetooth adapter with BLE support

```
pip install bleak colorama
```

## Usage

```
python lhbctrl.py scan              # discover base stations
python lhbctrl.py on                # turn on all discovered stations
python lhbctrl.py standby           # set all to standby
python lhbctrl.py sleep             # set all to sleep
python lhbctrl.py toggle            # toggle all on/standby

python lhbctrl.py on      AA:BB:CC:DD:EE:FF [...]   # target specific stations
python lhbctrl.py standby AA:BB:CC:DD:EE:FF [...]
python lhbctrl.py sleep   AA:BB:CC:DD:EE:FF [...]
python lhbctrl.py toggle  AA:BB:CC:DD:EE:FF [...]
```

### Options

| Flag | Description | Default |
|------|-------------|---------|
| `-t SECONDS` | BLE scan duration | `2` |

```
python lhbctrl.py scan -t 5
python lhbctrl.py on -t 10 AA:BB:CC:DD:EE:FF
```

## Power States

Lighthouse 2.0 supports the following states over BLE:

| State | Byte | Description |
|-------|------|-------------|
| `standby` | `0x00` | Low power, fast wake |
| `on` | `0x01` | Powering on |
| `sleep` | `0x02` | Very low power, slower wake |
| `booting` | `0x03` | Read-only, station is booting |
| `running` | `0x0B` | Fully operational |

`toggle` switches between `standby` and `on`. If the station is already in `on` or `running` state it will be set to `standby`, otherwise it will be set to `on`.

## Notes

- Lighthouse 2.0 cannot be fully powered off via BLE — `standby` and `sleep` are the lowest reachable states wirelessly.
- MAC addresses can be found with `python lhbctrl.py scan`.
- Multiple MAC addresses can be passed to control several stations in one command.
