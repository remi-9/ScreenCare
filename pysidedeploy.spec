/ pyside6-deploy configuration for ScreenCare.
/
/ Produces a standalone Windows build via Nuitka (pyside6-deploy wraps
/ Nuitka; see ``ScreenCare — Technical.md``'s "Final Recommended Stack":
/ "pyside6-deploy and Nuitka"). Build with:
/
/     pyside6-deploy -c pysidedeploy.spec
/
/ See DEVELOPMENT.md's "Building a standalone Windows executable" section
/ for prerequisites and the manual smoke-test checklist -- this can only be
/ run and verified on a real Windows machine with PySide6 installed, never
/ in the cloud sandbox this project has otherwise been built in.
/
/ Comment prefix note (learned the hard way -- see the engineering log):
/ pyside6-deploy reads this file with Python's configparser, constructed
/ by PySide6's own deploy_lib/config.py `BaseConfig.__init__` as
/ `ConfigParser(comment_prefixes=comment_prefixes, ...)`, whose
/ `comment_prefixes` parameter *defaults to "/"* and is never overridden
/ for the desktop deploy path. Neither `#` nor `;` -- the two prefixes
/ every general-purpose INI-like format normally accepts -- are
/ recognized here. A line here that does not start with `/` and is not a
/ `key = value` line or a `[section]` header breaks parsing immediately
/ with `configparser.MissingSectionHeaderError`, even deep inside an
/ already-open section. Verified directly against PySide6's own
/ `deploy_lib/config.py` source, and reproduced locally against Python's
/ `configparser` using this exact constructor call, before writing this
/ comment style back into the file a third time.

[app]
title = ScreenCare
project_dir = .
input_file = src/screencare/main.py
exec_directory = dist
icon = packaging/icon.ico

[python]
python_path = python
packages = nuitka,ordered_set,zstandard

[qt]
qml_files = src/screencare/ui/qml/Main.qml,src/screencare/ui/qml/FocusView.qml,src/screencare/ui/qml/BreakView.qml,src/screencare/ui/qml/DashboardView.qml,src/screencare/ui/qml/SettingsView.qml
excluded_qml_plugins =
modules = Core,Gui,Qml,Quick,QuickControls2,QuickLayouts,Widgets
plugins = platforms,styles

[nuitka]
/ "standalone" (a folder of files launched directly), not the tool's
/ default "onefile" (a single exe that self-extracts to a temp directory
/ on *every* launch). ScreenCare is a long-running background app that
/ may also be set to launch at login (Phase 5's autostart), so avoiding
/ per-launch self-extraction overhead and antivirus false-positive risk
/ matters more here than shipping a single file (Technical.md's
/ resource-usage priority; Implementation Standards.md's priority order
/ puts "minimal interference" and "low resource usage" ahead of
/ distribution convenience). Switch to `mode = onefile` if a single
/ distributable file is preferred instead.
mode = standalone
/ Hide the console window (this is a GUI app, not a CLI tool) --
/ `--windows-console-mode=disable` verified against Nuitka's own current
/ issue tracker/user manual rather than guessed.
extra_args = --windows-console-mode=disable --assume-yes-for-downloads
