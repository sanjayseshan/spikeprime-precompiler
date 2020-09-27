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
from gooey import Gooey, GooeyParser
import serial.tools.list_ports
import glob

def listSerial():
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

@Gooey(program_name="SPIKE Prime RAM Saver ", tabbed_groups=True, navigation='Tabbed')
def main():
    parser = GooeyParser(description='Pre-Compile a SPIKE Prime program and upload it to the hub.')

    group1 = parser.add_argument_group('Required Settings ')
    group1.add_argument("--port", help="USB port SPIKE Prime is connected to. (Note: hub must be connected and turned on. Rerun this RAM Saver Tool after you have connected hub. )", required=True, widget='Dropdown', #choices=['1','2'])
    choices=listSerial())

    # groupM = parser.add_mutually_exclusive_group(required = True)
    group2 = parser.add_argument_group('If program is on hub ')
    group2.add_argument('--slot', help = 'What slot is your program currently stored in? (note: it will be overwritten with a new compiled version) ',widget='Dropdown', choices=["0","1","2","3","4","5","6","7","8","9","10","11","12","13","14","15","16","17","18","19"])

    group3 = parser.add_argument_group('If program is local python file ')
    group3.add_argument('--file', help = 'Local path to micropython .py program', widget='FileChooser')
    group3.add_argument('--upload_slot', help = 'Which slot do you want your program uploaded to?',widget='Dropdown', choices=["0","1","2","3","4","5","6","7","8","9","10","11","12","13","14","15","16","17","18","19"])


    # parser.add_argument()
    # parser.add_argument("--slot", help="Current slot of program/Slot to upload to", required=True, widget='Dropdown',choices=["0","1","2","3","4","5","6","7","8","9","10","11","12","13","14","15","16","17","18","19"])
    # parser.add_argument("--file", help="(Optional, python only) Local path to micropython .py program", widget="FileChooser")

    args = parser.parse_args()
    print(args)

    port = args.port

    mode = "hub"
    if args.file:
        mode = "file"
        slot = int(args.upload_slot)
        handle_upload_rpc(port,args.file,slot)
    else:
        slot = int(args.slot)

    version = "0.0.2"

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
