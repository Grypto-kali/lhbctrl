#!/usr/bin/env python3
"""
SteamVR Base Station (Lighthouse 2.0) power control via Bluetooth LE.
Requirements:
    pip install bleak colorama
Usage:
    python lhbctrl.py scan    [-t SECONDS]
    python lhbctrl.py on      [-t SECONDS] [MAC ...]
    python lhbctrl.py standby [-t SECONDS] [MAC ...]
    python lhbctrl.py sleep   [-t SECONDS] [MAC ...]
    python lhbctrl.py toggle  [-t SECONDS] [MAC ...]
"""
import asyncio
import sys
import re
import os
from bleak import BleakScanner, BleakClient
from colorama import init, Fore, Style

init(autoreset=True)

POWER_CHAR_UUID = "00001525-1212-efde-1523-785feabcd124"

STATE_BYTES = {
    "standby": bytearray([0x00]),
    "on":      bytearray([0x01]),
    "sleep":   bytearray([0x02]),
    "booting": bytearray([0x03]),
    "running": bytearray([0x0B]),
}

STATE_LABELS = {
    "standby": "STANDBY",
    "on":      "ONLINE",
    "sleep":   "SLEEP",
    "booting": "BOOTING",
    "running": "RUNNING",
}

STATE_COLORS = {
    "standby": Fore.YELLOW,
    "on":      Fore.GREEN,
    "sleep":   Fore.CYAN,
    "booting": Fore.MAGENTA,
    "running": Fore.GREEN,
}

SCAN_TIMEOUT   = 2.0
BS_NAME_PREFIX = "LHB-"
COMMANDS       = ("scan", "on", "standby", "sleep", "toggle")

C_CYAN    = Fore.CYAN
C_GREEN   = Fore.GREEN
C_YELLOW  = Fore.YELLOW
C_RED     = Fore.RED
C_MAGENTA = Fore.MAGENTA
C_WHITE   = Fore.WHITE
C_DIM     = Style.DIM
C_BRIGHT  = Style.BRIGHT
C_RESET   = Style.RESET_ALL

BOOT_LOGO = f"""
{C_CYAN}{C_BRIGHT}
  ██╗     ██╗  ██╗██████╗     ██████╗████████╗██████╗ ██╗
  ██║     ██║  ██║██╔══██╗   ██╔════╝╚══██╔══╝██╔══██╗██║
  ██║     ███████║██████╔╝   ██║        ██║   ██████╔╝██║
  ██║     ██╔══██║██╔══██╗   ██║        ██║   ██╔══██╗██║
  ███████╗██║  ██║██████╔╝   ╚██████╗   ██║   ██║  ██║███████╗
  ╚══════╝╚═╝  ╚═╝╚═════╝     ╚═════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝
{C_RESET}{C_DIM}  Lighthouse 2.0 Power Control System  //  BLE Interface v1.0
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{C_RESET}"""

def log_info(msg: str) -> None:
    print(f"  {C_CYAN}[{C_RESET} {C_WHITE}{msg}{C_RESET} {C_CYAN}]{C_RESET}")

def log_ok(msg: str) -> None:
    print(f"  {C_GREEN}[+]{C_RESET} {C_WHITE}{msg}{C_RESET}")

def log_warn(msg: str) -> None:
    print(f"  {C_YELLOW}[!]{C_RESET} {C_YELLOW}{msg}{C_RESET}")

def log_err(msg: str) -> None:
    print(f"  {C_RED}[X]{C_RESET} {C_RED}{msg}{C_RESET}")

def log_dim(msg: str) -> None:
    print(f"  {C_DIM}{msg}{C_RESET}")

def separator() -> None:
    print(f"  {C_DIM}{'─' * 56}{C_RESET}")

def format_state(state: str) -> str:
    color = STATE_COLORS.get(state, C_WHITE)
    label = STATE_LABELS.get(state, state.upper())
    return f"{color}{label}{C_RESET}"

async def animated_scan(label: str, timeout: float) -> None:
    frames = ["[ ·  · ]", "[ ·· · ]", "[ ··· ]", "[· ··· ]", "[ ···  ]"]
    end_time = asyncio.get_event_loop().time() + timeout
    i = 0
    while asyncio.get_event_loop().time() < end_time:
        frame = frames[i % len(frames)]
        print(f"\r  {C_CYAN}{frame}{C_RESET}  {C_DIM}{label}...{C_RESET}", end="", flush=True)
        await asyncio.sleep(0.15)
        i += 1
    print("\r" + " " * 60 + "\r", end="", flush=True)

def is_valid_mac(mac: str) -> bool:
    return bool(re.match(r"^[0-9a-fA-F]{2}(:[0-9a-fA-F]{2}){5}$", mac))

async def find_base_stations(scan_timeout: float) -> list[tuple[str, str]]:
    separator()
    log_info(f"Initiating BLE scan  [{scan_timeout:.0f}s window]")
    separator()

    scan_task = asyncio.create_task(animated_scan("Scanning for Lighthouse units", scan_timeout))
    devices   = await BleakScanner.discover(timeout=scan_timeout)
    scan_task.cancel()

    found = []
    for d in devices:
        if isinstance(d.name, str) and d.name.startswith(BS_NAME_PREFIX):
            found.append((d.address, d.name))

    if found:
        log_ok(f"Detected {len(found)} base station(s):")
        for addr, name in found:
            print(f"      {C_MAGENTA}{name}{C_RESET}  {C_DIM}{addr}{C_RESET}")
    else:
        log_warn("No base stations found in range.")

    separator()
    return found

async def get_power_state(client: BleakClient) -> str:
    raw  = await client.read_gatt_char(POWER_CHAR_UUID)
    byte = raw[0]
    for state, data in STATE_BYTES.items():
        if data[0] == byte:
            return state
    return f"unknown(0x{byte:02x})"

async def set_power_state(address: str, target: str) -> None:
    separator()
    log_info(f"Target  {address}")

    connect_task = asyncio.create_task(animated_scan("Establishing BLE link", 3.0))
    try:
        async with BleakClient(address) as client:
            connect_task.cancel()
            log_ok("BLE link established.")

            current = await get_power_state(client)
            log_dim(f"Current state  >>  {format_state(current)}")

            if target == "toggle":
                target = "standby" if current in ("on", "running") else "on"
                log_dim(f"Toggle resolved >>  {format_state(target)}")

            if target not in STATE_BYTES:
                log_err(f"Unknown target state: {target}")
                return

            desired_bytes = STATE_BYTES[target]

            for attempt in range(1, 4):
                await client.write_gatt_char(POWER_CHAR_UUID, desired_bytes)
                await asyncio.sleep(0.5)
                new_state = await get_power_state(client)

                if new_state == target:
                    log_ok(f"State confirmed  >>  {format_state(new_state)}")
                    return

                log_warn(f"Attempt {attempt}/3 unconfirmed — retrying...")

            log_warn("State change could not be confirmed after 3 attempts.")

    except asyncio.CancelledError:
        pass
    except Exception as e:
        connect_task.cancel()
        log_err(f"Connection failed: {e}")

    separator()

async def main() -> None:
    print(BOOT_LOGO)

    args = sys.argv[1:]

    # Parse -t flag
    scan_timeout = SCAN_TIMEOUT
    for i, arg in enumerate(args):
        if arg == "-t" and i + 1 < len(args):
            try:
                scan_timeout = float(args[i + 1])
                args = args[:i] + args[i + 2:]
            except ValueError:
                log_err(f"Invalid scan timeout value: {args[i + 1]}")
                sys.exit(1)
            break

    if len(args) < 1 or args[0] not in COMMANDS:
        print(f"  {C_WHITE}Usage:{C_RESET}")
        print(f"    {C_CYAN}python lhbctrl.py{C_RESET} {C_MAGENTA}scan{C_RESET}    {C_DIM}[-t SECONDS]{C_RESET}")
        print(f"    {C_CYAN}python lhbctrl.py{C_RESET} {C_MAGENTA}on{C_RESET}      {C_DIM}[-t SECONDS] [MAC ...]{C_RESET}")
        print(f"    {C_CYAN}python lhbctrl.py{C_RESET} {C_MAGENTA}standby{C_RESET} {C_DIM}[-t SECONDS] [MAC ...]{C_RESET}")
        print(f"    {C_CYAN}python lhbctrl.py{C_RESET} {C_MAGENTA}sleep{C_RESET}   {C_DIM}[-t SECONDS] [MAC ...]{C_RESET}")
        print(f"    {C_CYAN}python lhbctrl.py{C_RESET} {C_MAGENTA}toggle{C_RESET}  {C_DIM}[-t SECONDS] [MAC ...]{C_RESET}")
        print()
        sys.exit(1)

    command  = args[0]
    mac_args = [a for a in args[1:] if is_valid_mac(a)]

    for bad in [a for a in args[1:] if not is_valid_mac(a)]:
        log_warn(f"Ignoring invalid argument: {bad}")

    if command == "scan":
        await find_base_stations(scan_timeout)
        return

    targets = mac_args
    if not targets:
        found   = await find_base_stations(scan_timeout)
        targets = [addr for addr, _ in found]

    if not targets:
        log_err("No base stations to control. Aborting.")
        sys.exit(1)

    cmd_color = C_GREEN if command == "on" else C_YELLOW if command == "standby" else C_CYAN
    print(f"\n  {C_DIM}Dispatching command  [{cmd_color}{command.upper()}{C_RESET}{C_DIM}]  to {len(targets)} unit(s){C_RESET}\n")

    for addr in targets:
        await set_power_state(addr, command)
        await asyncio.sleep(1.0)

    separator()
    log_ok("All operations complete.")
    separator()
    print()

if __name__ == "__main__":
    asyncio.run(main())