# Standalone license inventory

`packaging/build.py` copies the project MIT license and the license files found in installed runtime distributions into the standalone artifact.

The generated `LICENSES.txt` records the package version and copied file names. The generated `LICENSES/` directory contains the corresponding text files. The build fails when a runtime distribution has no discoverable license file.

The inventory covers the direct runtime packages and the Bluetooth transport dependency used by the adapter:

- demi-controller
- platformdirs
- pyglet
- swbt-python
- tomli-w
- bumble
