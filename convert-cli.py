#!/usr/bin/python3
import sys
import pyboard
import files
import mpy_cross
import time
import click
import argparse
import spikejsonrpc
import os
from tqdm import tqdm
import serial.tools.list_ports
import glob

def listSerial():
    """ Lists serial port names

        :raises EnvironmentError:
            On unsupported or unknown platforms
        :returns:
            A list of the serial ports available on the system
    """
    if sys.platform.startswith('win'):
        ports = ['COM%s' % (i + 1) for i in range(256)]
    elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
        # this excludes your current terminal "/dev/tty"
        ports = glob.glob('/dev/tty[A-Za-z]*')
    elif sys.platform.startswith('darwin'):
        ports = glob.glob('/dev/tty.*')
    else:
        raise EnvironmentError('Unsupported platform')

    result = []
    for port in ports:
        try:
            s = serial.Serial(port)
            s.close()
            result.append(port)
        except (OSError, serial.SerialException):
            pass
    return result

def handle_upload_rpc(port, file, slot):
    rpc = spikejsonrpc.RPC(port)
    with open(file, "rb") as f:
        size = os.path.getsize(file)
        name = file
        now = int(time.time() * 1000)
        start = rpc.start_write_program(name, size, slot, now, now)
        bs = start['blocksize']
        id = start['transferid']
        with tqdm(total=size, unit='B', unit_scale=True) as pbar:
            b = f.read(bs)
            while b:
                rpc.write_package(b, id)
                pbar.update(len(b))
                b = f.read(bs)

def main():
    parser = argparse.ArgumentParser(description='Pre-Compile a SPIKE Prime program and upload it to the hub.')

    parser.add_argument("--port", help="Serial port of the SPIKE Prime", required=True)
    parser.add_argument("--slot", help="Current slot of program/Slot to upload to", required=True)
    parser.add_argument("--file", help="(Optional, python only) Local path to micropython .py program")

    args = parser.parse_args()

    slot = int(args.slot)
    port = args.port

    mode = "hub"
    if args.file:
        mode = "file"
        handle_upload_rpc(port,args.file,slot)

    version = "0.0.1"

    print(f"SPIKE Prime MPY Compiler v{version}")


    print(f"Loading SPIKE Prime Program on port {port} at slot {slot}.")

    spike = pyboard.Pyboard(port)
    fileMan = files.Files(spike)

    fileMan.ls("/projects")

    usedSlots = eval(fileMan.get("/projects/.slots"))

    fType = usedSlots[slot]["type"]
    print(f"Program type: {fType}")
    program = str(usedSlots[slot]["id"])+".py"

    if mode == "hub":
        text = fileMan.get("/projects/"+program).decode()
    else:
        textfile = open(args.file,"r")
        text = textfile.read()

    code = "py"+program.split(".py")[0]

    loaderFile = ""
    importFile = ""

    print("Parsing....")
    if fType == "scratch":
        importCt = text.find("async")

        imports = text[0:importCt]
        loaderFile+=imports
        importFile+=imports
        loaderFile+=f"from {code}import import *\n"

        loaderCt = text.find("def setup")
        content = text[importCt:loaderCt]
        importFile+=content

        loader = text[loaderCt:]
        loaderFile+=loader
    else:
        loaderFile = f"from {code}import import *\n"
        importFile = text

    print("Compiling...")
    importFileRaw = open(code+"import.py","w")
    importFileRaw.write(importFile)
    importFileRaw.close()
    mpy_cross.run(code+"import.py")
    time.sleep(1)

    print(f"Uploading to slot {slot}")
    importFileCP = open(code+"import.mpy", "rb")
    fileMan.put(f"/{code}import.mpy", importFileCP.read())
    importFileCP.close()
    fileMan.put(f"/projects/{program}",loaderFile)
    fileMan.put(f"/projects/{code}.orig.py",text)

    print("Rebooting...")

    spike.enter_raw_repl()
    spike.exec_raw_no_follow(
"""
import machine
machine.reset()
"""
    )

    print(f"Complete...Try running program on slot {slot}")

    if mode == "file":
        textfile.close()


if __name__ == '__main__':
    main()
