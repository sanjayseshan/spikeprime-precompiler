# spikeprime-precompiler

Use this tool to pre-compile SPIKE Prime programs and re-upload them to the hub. This helps to mitigate the RAM issue when large programs are run (and crash due to the memory running out).

See releases tab for more information/downloads.

Requirements:
```
pip3 install click argparse tqdm pyserial gooey mpy_cross gooey
python3 convert.py
```
