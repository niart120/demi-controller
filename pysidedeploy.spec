[app]
title = demi
project_dir = packaging
input_file = packaging/launcher.py
exec_directory = dist/standalone
project_file = demi.pyproject
icon =

[python]
python_path =
packages = Nuitka==4.0

[qt]
qml_files =
excluded_qml_plugins =
modules = Core,Gui,Widgets
plugins = platforms

[nuitka]
macos.permissions =
mode = standalone
extra_args = --quiet --noinclude-qt-translations --assume-yes-for-downloads --include-qt-plugins=platforms --noinclude-qt-plugins=imageformats --noinclude-qt-plugins=iconengines --noinclude-qt-plugins=mediaservice --noinclude-qt-plugins=printsupport --noinclude-qt-plugins=platformthemes --noinclude-qt-plugins=styles --noinclude-qt-plugins=wayland-shell-integration --noinclude-qt-plugins=wayland-decoration-client --noinclude-qt-plugins=egldeviceintegrations --noinclude-qt-plugins=xcbglintegrations --noinclude-qt-plugins=tls
