#!/usr/bin/env python3

import argparse
import subprocess
from pathlib import Path
import shutil
import sys

SRC_DIR = Path("src")
BUILD_DIR = Path("build")
MPY_CROSS = "mpy-cross"
MPREMOTE = "mpremote"

def flatten_name(path: Path) -> str:
    parts = path.relative_to(SRC_DIR).with_suffix("").parts
    return "_".join(parts) + ".mpy"

def compile_all():
    BUILD_DIR.mkdir(parents=True, exist_ok=True)

    print("🔨 Compiling .py files to flattened .mpy (except main.py)")

    for src_path in SRC_DIR.rglob("*.py"):
        rel_path = src_path.relative_to(SRC_DIR)

        # Special handling for main.py (copy instead of compile)
        if rel_path == Path("main.py"):
            dst_path = BUILD_DIR / "main.py"
            print(f"\n📄 Copying main.py → {dst_path}")
            shutil.copy2(src_path, dst_path)
            continue

        out_name = flatten_name(src_path)
        dst_path = BUILD_DIR / out_name

        print(f"\n🛠️  Compiling {src_path} → {dst_path}")
        try:
            subprocess.run([MPY_CROSS, str(src_path), "-o", str(dst_path)], check=True)
        except subprocess.CalledProcessError:
            print(f"❌ Failed to compile {src_path}")
        except Exception as e:
            print(f"❌ Unexpected error: {e}")

def upload_all(serial_port: str):
    print(f"\n📤 Uploading build/ to ESP32 on {serial_port}")
    for file in BUILD_DIR.iterdir():
        if file.is_file():
            # upload main.py/boot.py with correct name
            if file.name == "main.py":
                dst = ":/main.py"
            elif file.name == "boot.py":
                dst = ":/boot.py"
            elif file.name == "boot.py":
                dst = ":/boot.py"
            else:
                dst = f":/{file.name}"

            print(f"⬆️  Uploading {file} → {dst}")
            try:
                subprocess.run([MPREMOTE, "connect", serial_port, "fs", "cp", str(file), dst], check=True)
            except subprocess.CalledProcessError:
                print(f"❌ Failed to upload {file.name}")

    print("\n🔁 Rebooting device...")
    subprocess.run(["mpremote", "connect", serial_port, "reset"], check=True)

def main():
    parser = argparse.ArgumentParser(
        description="Compile and optionally upload MicroPython .py files as flattened .mpy files."
    )
    parser.add_argument(
        "serial_port",
        nargs="?",
        help="Serial port for mpremote (e.g. /dev/ttyUSB0) — optional positional"
    )
    parser.add_argument(
        "-p", "--port",
        dest="port",
        help="Serial port for mpremote (e.g. /dev/ttyUSB0)"
    )
    parser.add_argument(
        "--no-upload", action="store_true",
        help="Skip upload even if port is provided"
    )

    args = parser.parse_args()
    port = args.port or args.serial_port

    compile_all()

    if port and not args.no_upload:
        upload_all(port)
    elif port and args.no_upload:
        print("⚠️  Upload skipped due to --no-upload flag.")
    else:
        print("ℹ️  No port provided. Skipping upload.")

if __name__ == "__main__":
    main()
