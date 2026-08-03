# SkyVEx

**Convenient Visualization and Export of Sky: Children of the Light Models**

GUI tool for batch-exporting 3D map data from *Sky: Children of the Light*.

[中文](./README-zh.md) | [English](./README.md)

## What this project is

A self-contained graphical tool for turning Sky game data into Wavefront OBJ.
The GUI, the level→OBJ export engine, the `.bin` and `.mesh` parsers, the 3D
preview and the texture pipeline are all **original SkyVEx code**. Only the
terrain decoder (`Sky_Bstbake.py`) and one optional alternate backend
(`meshes2obj_json.py`) are third-party, and they are used **unmodified** with
their original authorship and licenses intact.

Features:

- **One-click game directory scanning** — point at your game install, auto-discover all maps and mesh files
- **APK extraction** — open a Sky APK directly and extract game assets without a PC install
- **Tabbed resource browser** — three-tab layout (Terrain / Models / Images) with scene-grouped map tree, 4000+ individual meshes grouped by prefix, and KTX texture gallery
- **3D preview** — real-time OpenGL preview with vertex colors (terrain material blending) and top-down soft lighting; click any map or model to preview
- **2D image preview** — click any KTX texture in the Images tab to decode and preview (BC1/BC3/BC4/BC5/BC6H/BC7)
- **Per-material terrain export** — terrain OBJ split by material ID with a shared material table (MTL), ready for Blender material assignment
- **Individual mesh export** — browse and batch-export standalone `.mesh` models (props, characters, items) to OBJ, not just terrain maps
- **Marker class scanning** — scan marker class names from `.bin` files, pick which marker types to export
- **Texture extraction** — KTX → PNG with per-format decoding (BC1/BC3/BC4/BC5/BC6H/BC7), UV mapping in OBJ, `map_Kd` material references in MTL
- **Pluggable backend system** — swap between native and pure-Python parsers at runtime
- **DPI-aware rendering** — crisp UI on high-DPI / scaled displays
- **Sky-styled dark theme** — deep navy palette inspired by the game's visual identity

> **Attribution:** every source file carries a provenance header stating who
> wrote it, which repository it came from, and under which license. See
> [NOTICE](./NOTICE) for the third-party licenses.

## Screenshot

![SkyVEx GUI](./screenshot.png)

## Requirements

Python 3.8+

```bash
pip install -r tool/scripts/requirements.txt
# lz4  Pillow  texture2ddecoder  PyOpenGL
```

- `lz4` — **required** for terrain (LOD0) decompression.
- `Pillow` + `texture2ddecoder` — needed for texture (KTX→PNG) export and 2D image preview.
- `PyOpenGL` — needed for the 3D preview panel (`PyOpenGL_accelerate` optional).

The `meshoptimizer` native decoder used for fine terrain is **shipped prebuilt**
at `tool/scripts/_meshopt/lib/meshoptimizer.dll` (self-compiled from
[zeux/meshoptimizer](https://github.com/zeux/meshoptimizer), MIT). It is **not**
a pip dependency.

## Usage

### GUI (recommended)

**Windows:** Double-click `SkyVEx.exe` in the project root.

Or run from the command line:

```bash
cd tool/scripts
python gui.py
```

1. **Browse** to your game install directory, click **Scan** — or click **APK** to open an APK file directly
2. Browse resources using tabs: **Terrain** for maps, **Models** for individual meshes, **Images** for KTX textures
3. Toggle **3D Preview** to preview any map or model with real-time OpenGL rendering; click any image for a 2D preview
4. Click **Scan Marker Classes** to discover marker types, then toggle markers, textures, and adjust the output directory
5. Click **Start Export** — exports both selected maps and individual models

### CLI

```bash
cd tool/scripts
python bintojson.py Objects.level.bin                        # bin → json
python Sky_Bstbake.py --unpack BstBaked.meshes --export-obj  # terrain only (upstream tool)
```

Map/model export is driven by the GUI; the engine lives in `exporter.py` and is
imported by `gui.py` rather than run standalone.

## File structure

```
SkyVEx.exe                         # Windows launcher (build from SkyVEx.py)
SkyVEx.py                          # Launcher entry point
│
tool/scripts/
│  [Original — lingyunalingyun]
├── gui.py                     # GUI frontend & texture pipeline
├── exporter.py                # Level → OBJ/MTL assembly engine
├── backends.py                # Pluggable backend registry
├── mesh_parser.py             # Pure-Python .mesh parser (all versions)
├── preview3d.py               # OpenGL 3D preview panel
├── bintojson.py               # TGCL .bin → dict/JSON parser (format ref: Miau)
│
│  [Third-party — verbatim, see each file's header]
├── Sky_Bstbake.py             # Terrain .meshes decoder — ThatSkyOldServer/SkyBstbake (MIT)
├── meshes2obj_json.py         # Optional alt .meshes backend — that-sky-project (LGPL-2.1)
└── _meshopt/
    └── lib/
        └── meshoptimizer.dll  # zeux/meshoptimizer (MIT), self-compiled
```

Every script file begins with a provenance header. See [NOTICE](./NOTICE) for
third-party license details.

## Third-party files

Both third-party source files are used **unmodified** from their upstream
repositories (only a SkyVEx attribution header is prepended):

| File | Upstream | License |
|------|----------|---------|
| `Sky_Bstbake.py` | [ThatSkyOldServer/SkyBstbake](https://github.com/ThatSkyOldServer/SkyBstbake) — checion (雨人) & Heriel (落秋) | MIT |
| `meshes2obj_json.py` | [that-sky-project](https://github.com/that-sky-project/that-sky-level-meshes) | LGPL-2.1 |

`meshoptimizer.dll` is compiled from [zeux/meshoptimizer](https://github.com/zeux/meshoptimizer)
(MIT) official source.

## OBJ output

| Data | Description |
|------|-------------|
| Terrain | Ground mesh split by material ID, shared MTL material table, vertex colors and AO |
| Models (in-map) | Scene objects with per-instance transforms applied, X/Z-flipped for Blender |
| Models (standalone) | Individual `.mesh` files exported to `Meshes/` subfolder with UVs |
| Markers | Small octahedron pins at interaction points (optional), colored per class |
| Textures | PNG files + `map_Kd` material references (optional) |

## Building the exe

Requires [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --icon=icon.ico --name SkyVEx SkyVEx.py
```

The output `dist/SkyVEx.exe` can be placed in the project root. Python must
still be installed on the target machine — the exe is just a launcher, not a
standalone bundle.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `lz4` not found | `pip install lz4` (required for terrain) |
| Terrain 0 vertices | Ensure `_meshopt/lib/meshoptimizer.dll` is present and `lz4` installed |
| Models missing | Need `.mesh` files extracted from the game's `Data/Meshes/Bin` |
| Texture export fails | `pip install texture2ddecoder Pillow` |
| 3D preview not available | `pip install PyOpenGL` |

## Credits

- **GUI, export engine, `.bin`/`.mesh` parsers, 3D preview, texture pipeline, backend system** — lingyunalingyun (this project's original code).
- **Terrain decoder** `Sky_Bstbake.py` — checion (雨人) & Heriel (落秋), [ThatSkyOldServer/SkyBstbake](https://github.com/ThatSkyOldServer/SkyBstbake) (MIT).
- **Optional `.meshes` backend** `meshes2obj_json.py` — [that-sky-project](https://github.com/that-sky-project/that-sky-level-meshes) (LGPL-2.1).
- **Native decoder** `meshoptimizer.dll` — [Arseny Kapoulkine (zeux)](https://github.com/zeux/meshoptimizer) (MIT).
- **Format references (public byte layouts, no code):** Miau — [Sky-.bin-reader](https://github.com/Miau0x1/Sky-.bin-reader); kfhammond — [SkyModelViewer](https://github.com/kfhammond/SkyModelViewer).

## License

SkyVEx's own code is released under the **MIT License** — see [LICENSE](./LICENSE).

`meshes2obj_json.py` is licensed under **LGPL-2.1** (that file only) — see its
header. Third-party components retain their original licenses; see
[NOTICE](./NOTICE).
