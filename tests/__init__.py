import os
import sys

# Decky puts py_modules on sys.path, so the package imports as `tartarus`.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "py_modules"))
