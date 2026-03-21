#!/usr/bin/env python3

import csv
import fcntl
import glob
import os
import re
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

MAP_FILE = "/etc/device-map.csv"
LOCK_FILE = "/etc/device-map.csv.lock"

# keyword seen in lsusb description -> (class_name, prefix)
KEYWORD_MAP = {
    "Adafruit SHT4x": ("sht45", "sht45"),
    "Adafruit QT Py RP2040": ("temp", "temp"),
    "U-Blox AG": ("gnss", "gnss"),
}

CSV_FIELDS = ["class", "vendor_id", "model_id", "id_model", "id_path", "assigned_name"]


def run_cmd(cmd: List[str], check: bool = True) -> str:
    result = subprocess.run(
        cmd,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout


def ensure_root() -> None:
    if os.geteuid() != 0:
        print("This script must be run as root.", file=sys.stderr)
        sys.exit(1)


def ensure_map_file() -> None:
    if not os.path.exists(MAP_FILE):
        with open(MAP_FILE, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()


def parse_lsusb_targets() -> Dict[Tuple[str, str], Tuple[str, str, str]]:
    """
    Return:
      (vendor_id, product_id) -> (class_name, prefix, matched_keyword)
    based on lsusb description text.
    """
    out = run_cmd(["lsusb"])
    targets: Dict[Tuple[str, str], Tuple[str, str, str]] = {}

    for line in out.splitlines():
        # Example:
        # Bus 003 Device 004: ID 1546:01a9 U-Blox AG ...
        m = re.search(r"\bID\s+([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\s+(.*)$", line)
        if not m:
            continue

        vendor_id = m.group(1).lower()
        product_id = m.group(2).lower()
        desc = m.group(3).strip()

        for keyword, (class_name, prefix) in KEYWORD_MAP.items():
            if keyword.lower() in desc.lower():
                targets[(vendor_id, product_id)] = (class_name, prefix, keyword)
                break

    return targets


def get_udev_properties(devnode: str) -> Dict[str, str]:
    out = run_cmd(["udevadm", "info", "-q", "property", "-n", devnode])
    props: Dict[str, str] = {}

    for line in out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            props[k.strip()] = v.strip()

    return props


def read_map() -> List[Dict[str, str]]:
    ensure_map_file()
    with open(MAP_FILE, "r", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def write_row(row: Dict[str, str]) -> None:
    file_exists = os.path.exists(MAP_FILE)
    with open(MAP_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not file_exists or os.path.getsize(MAP_FILE) == 0:
            writer.writeheader()
        writer.writerow(row)


def find_existing_assignment(
    rows: List[Dict[str, str]],
    class_name: str,
    vendor_id: str,
    model_id: str,
    id_model: str,
    id_path: str,
) -> Optional[str]:
    for row in rows:
        if (
            row.get("class", "") == class_name
            and row.get("vendor_id", "").lower() == vendor_id.lower()
            and row.get("model_id", "").lower() == model_id.lower()
            and row.get("id_model", "") == id_model
            and row.get("id_path", "") == id_path
        ):
            return row.get("assigned_name", "")
    return None


def next_assigned_name(rows: List[Dict[str, str]], class_name: str, prefix: str) -> str:
    used = set()

    for row in rows:
        if row.get("class", "") != class_name:
            continue
        name = row.get("assigned_name", "")
        m = re.fullmatch(rf"{re.escape(prefix)}_(\d+)", name)
        if m:
            used.add(int(m.group(1)))

    n = 0
    while n in used:
        n += 1

    return f"{prefix}_{n}"


def make_symlink(devnode: str, assigned_name: str) -> None:
    link_path = os.path.join("/dev", assigned_name)

    try:
        if os.path.islink(link_path) or os.path.exists(link_path):
            os.remove(link_path)
        os.symlink(devnode, link_path)
    except OSError as e:
        raise RuntimeError(f"Failed to create symlink {link_path} -> {devnode}: {e}") from e


def reload_and_trigger(devnode: str) -> None:
    # Reload rules
    subprocess.run(["udevadm", "control", "--reload-rules"], check=True)

    # Trigger the actual tty device, not the /dev/<assigned_name> symlink.
    basename = os.path.basename(devnode)
    subprocess.run(
        ["udevadm", "trigger", "--action=add", f"--name-match={basename}"],
        check=True,
    )


def process_device(devnode: str, targets: Dict[Tuple[str, str], Tuple[str, str, str]]) -> None:
    props = get_udev_properties(devnode)

    vendor_id = props.get("ID_VENDOR_ID", "").lower()
    model_id = props.get("ID_MODEL_ID", "").lower()
    id_model = props.get("ID_MODEL", "")
    id_path = props.get("ID_PATH", "")

    if not vendor_id or not model_id or not id_path:
        return

    key = (vendor_id, model_id)
    if key not in targets:
        return

    class_name, prefix, matched_keyword = targets[key]

    # Lock while reading/updating the map
    with open(LOCK_FILE, "w") as lockf:
        fcntl.flock(lockf, fcntl.LOCK_EX)

        rows = read_map()

        assigned_name = find_existing_assignment(
            rows=rows,
            class_name=class_name,
            vendor_id=vendor_id,
            model_id=model_id,
            id_model=id_model,
            id_path=id_path,
        )

        is_new = False
        if not assigned_name:
            assigned_name = next_assigned_name(rows, class_name, prefix)
            row = {
                "class": class_name,
                "vendor_id": vendor_id,
                "model_id": model_id,
                "id_model": id_model,
                "id_path": id_path,
                "assigned_name": assigned_name,
            }
            write_row(row)
            is_new = True

    make_symlink(devnode, assigned_name)

    if is_new:
        reload_and_trigger(devnode)

    print(
        f"{devnode}: matched '{matched_keyword}', "
        f"class={class_name}, assigned_name={assigned_name}"
    )


def main() -> None:
    ensure_root()
    ensure_map_file()

    targets = parse_lsusb_targets()
    if not targets:
        print("No matching lsusb devices found for configured keywords.")
        return

    tty_devices = sorted(glob.glob("/dev/ttyACM*"))
    if not tty_devices:
        print("No /dev/ttyACM* devices found.")
        return

    for devnode in tty_devices:
        try:
            process_device(devnode, targets)
        except subprocess.CalledProcessError as e:
            print(f"Command failed while processing {devnode}: {e}", file=sys.stderr)
        except Exception as e:
            print(f"Error while processing {devnode}: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()