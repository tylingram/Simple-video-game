# PyInstaller spec for RTS Game
# Run from the repo root:  pyinstaller game.spec
#
# Output: dist/RTS Game/
#   RTS Game.exe        — double-click to launch
#   config_editor.exe   — launched automatically by the game; can also be run standalone
#   config.json         — created on first save; lives next to the exe (writable)
#
# Size/speed notes:
#   upx=False  — UPX compresses binaries but decompresses them at every launch,
#                adding 1-3 s of startup time for no benefit in a zipped bundle.
#   excludes   — strips stdlib modules the game never uses; saves ~15-25 MB
#                from the bundle before zipping.

_COMMON_EXCLUDES = [
    # web / network / email — not used by a local game
    'email', 'html', 'http', 'xml', 'xmlrpc',
    'ftplib', 'imaplib', 'poplib', 'smtplib', 'ssl',
    # database
    'sqlite3',
    # async / parallel
    'asyncio', 'concurrent', 'multiprocessing',
    # dev / test tooling
    'unittest', 'doctest', 'pydoc', 'test', 'lib2to3',
]

# ── Main game ─────────────────────────────────────────────────────────────────
main_a = Analysis(
    ['rts-game/main.py'],
    pathex=['rts-game'],
    datas=[('rts-game/config.defaults.json', '.')],
    hiddenimports=[],
    excludes=_COMMON_EXCLUDES + ['tkinter'],  # editor handles tkinter separately
    noarchive=False,
)

# ── Config editor (tkinter GUI, launched as sibling process) ──────────────────
editor_a = Analysis(
    ['rts-game/config_editor.py'],
    pathex=['rts-game'],
    datas=[],
    hiddenimports=['tkinter', '_tkinter', 'tkinter.ttk'],
    excludes=_COMMON_EXCLUDES + ['pygame'],   # game handles pygame separately
    noarchive=False,
)

main_pyz   = PYZ(main_a.pure)
editor_pyz = PYZ(editor_a.pure)

main_exe = EXE(
    main_pyz,
    main_a.scripts,
    [],
    exclude_binaries=True,
    name='RTS Game',
    console=False,   # no terminal window
    upx=False,       # UPX decompresses at launch — slower startup, no benefit here
)

editor_exe = EXE(
    editor_pyz,
    editor_a.scripts,
    [],
    exclude_binaries=True,
    name='config_editor',
    console=False,
    upx=False,
)

# Collect both executables and all their shared libraries into one folder
coll = COLLECT(
    main_exe,   main_a.binaries,   main_a.datas,
    editor_exe, editor_a.binaries, editor_a.datas,
    name='RTS Game',
    upx=False,
)
