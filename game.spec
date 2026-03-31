# PyInstaller spec for RTS Game
# Run from the repo root:  pyinstaller game.spec
#
# Output: dist/RTS Game/
#   RTS Game.exe        — double-click to launch
#   config_editor.exe   — launched automatically by the game; can also be run standalone
#   config.json         — created on first save; lives next to the exe (writable)

# ── Main game ─────────────────────────────────────────────────────────────────
main_a = Analysis(
    ['rts-game/main.py'],
    pathex=['rts-game'],
    datas=[],
    hiddenimports=[],
    noarchive=False,
)

# ── Config editor (tkinter GUI, launched as sibling process) ──────────────────
editor_a = Analysis(
    ['rts-game/config_editor.py'],
    pathex=['rts-game'],
    datas=[],
    hiddenimports=['tkinter', '_tkinter', 'tkinter.ttk'],
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
    upx=True,
)

editor_exe = EXE(
    editor_pyz,
    editor_a.scripts,
    [],
    exclude_binaries=True,
    name='config_editor',
    console=False,
    upx=True,
)

# Collect both executables and all their shared libraries into one folder
coll = COLLECT(
    main_exe,   main_a.binaries,   main_a.datas,
    editor_exe, editor_a.binaries, editor_a.datas,
    name='RTS Game',
    upx=True,
)
