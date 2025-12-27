#!/usr/bin/env python3

import argparse
import subprocess
from pathlib import Path
import shutil
import sys
import json

SELF_DIR = Path(__file__).parent.resolve()
SRC_DIR = SELF_DIR / Path("src")
BUILD_DIR = SELF_DIR / Path("build")
MPY_CROSS = "mpy-cross"
MPREMOTE = "mpremote"


# Eveything but the main.py is compiled into mpy.
# Destination is build/nodex
# if node.json doesn't already exists, copy the node index into it.
def compile_all(node_index:int) -> Path:
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    build_folder = BUILD_DIR / Path(f"node{node_index}")

    print(f"Building with src: {SRC_DIR} to dest {build_folder}")

    for src_path in SRC_DIR.rglob("*.py"):
        rel_path = src_path.relative_to(SRC_DIR)

        dest_path = build_folder /  rel_path
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        if rel_path == Path("main.py"):
            # Special handling for main.py (copy instead of compile)
            print(f"Copying main.py → {dest_path}")
            shutil.copy2(src_path, dest_path)
        else: 
            dest_path=dest_path.with_suffix(".mpy")
            print(f"Compiling {src_path}")
            try:
                subprocess.run([MPY_CROSS, str(src_path), "-o", str(dest_path)], check=True)
            except subprocess.CalledProcessError:
                print(f"E: Failed to compile {src_path}")
            except Exception as e:
                print(f"E: Unexpected error while compiling: {e}")

    # Create special Node config file.
    node_info_file = build_folder/Path("node.json")
    if node_info_file.exists : 
        print(f"Node info {node_info_file} already exists, skipping")
    else:
        print(f"Genering node info file")
        with open(node_info_file, 'w') as f:
            json.dump( {"node_index": node_index } , f)
        
    return build_folder

def upload_all(serial_port: str , build_folder:Path):
    print(f"\n📤 Uploading build/ to ESP32 on {serial_port}")


    # TODO do I even need to check anything?
    for file in build_folder.iterdir():
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
        "-n" , "--node" , 
        type=int , required=True,  
        help="the node index."
    )
    parser.add_argument(
        "--no-upload", action="store_true",
        help="Skip upload even if port is provided"
    )

    args = parser.parse_args()
    port = args.port or args.serial_port

    node_index = args.node

    if node_index is None:
        print("E: Did not supply a node index!")
        exit(1)
    
    build_folder = compile_all(node_index)

    if port and not args.no_upload:
        upload_all(port , build_folder)
    elif port and args.no_upload:
        print("⚠️  Upload skipped due to --no-upload flag.")
    else:
        print("ℹ️  No port provided. Skipping upload.")

if __name__ == "__main__":
    main()
