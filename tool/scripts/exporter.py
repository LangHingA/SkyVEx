#!/usr/bin/env python3
# ============================================================================
#  SkyVEx · exporter.py  —  Sky level -> OBJ/MTL assembly engine
#  PROVENANCE : ORIGINAL. Every line written by LANGHINGA for SkyVEx.
#               No code taken from any other repository.
#  AUTHOR     : LANGHINGA · https://github.com/LangHingA
#  LICENSE    : MIT (see LICENSE)
# ============================================================================
#
# Reads an Objects.level.bin (via bintojson) plus its BstBaked.meshes terrain,
# resolves every LevelMesh instance to a .mesh model, bakes per-instance
# transforms, and emits a single Wavefront OBJ/MTL with optional KTX textures
# and node markers. Terrain / model geometry is produced by the pluggable
# backends layer; this module only orchestrates and writes the scene.

import os
import math
import struct
import hashlib
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
import sys
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import bintojson
from backends import (
    get_available_meshes_backends, get_available_mesh_backends,
    get_meshes_backends, get_mesh_backends,
    MATERIAL_NAMES, MATERIAL_COLORS, MATERIAL_COLOR_DEFAULT,
)

# Optional KTX decoder — only needed when textures are requested.
try:
    import texture2ddecoder
    from PIL import Image as _Image
    _HAS_KTX = True
except ImportError:
    _HAS_KTX = False


# ---------------------------------------------------------------------------
# Backend selection (state consumed by the GUI: _active_*_backend)
# ---------------------------------------------------------------------------
_active_meshes_backend = None
_active_mesh_backend = None

_MESHES_PREFERENCE = ("bstbake", "meshes2obj_json")


def _pick(available, preferred, preference_order=()):
    """Choose a backend from `available`: explicit request first, then the
    ordered preference list, then whatever is left."""
    if not available:
        return None
    if preferred and preferred in available:
        return available[preferred]
    for name in preference_order:
        if name in available:
            return available[name]
    return next(iter(available.values()))


def _init_backends(preferred_meshes=None, preferred_mesh=None):
    global _active_meshes_backend, _active_mesh_backend
    _active_meshes_backend = _pick(
        get_available_meshes_backends(), preferred_meshes, _MESHES_PREFERENCE)
    _active_mesh_backend = _pick(
        get_available_mesh_backends(), preferred_mesh)

    if _active_meshes_backend:
        print(f"[OK] .meshes 后端: {_active_meshes_backend.name} "
              f"({_active_meshes_backend.description})")
    else:
        print("[WARN] 无可用 .meshes 后端，地形导出将不可用")
    if _active_mesh_backend:
        print(f"[OK] .mesh 后端: {_active_mesh_backend.name} "
              f"({_active_mesh_backend.description})")
    else:
        print("[WARN] 无可用 .mesh 后端，模型导出将不可用")


_init_backends()


def parse_meshes_to_obj_data(meshes_file):
    """Terrain: (verts, faces, colors, mat_ids). Empty tuple on any failure."""
    if _active_meshes_backend is None:
        return [], [], [], []
    try:
        return _active_meshes_backend.parse_to_obj_data(meshes_file)
    except Exception as exc:
        print(f"    地形解析失败 ({_active_meshes_backend.name}): {exc}")
        return [], [], [], []


def parse_mesh_file(mesh_path):
    """Single model: (verts, uvs, faces). Empty tuple on any failure."""
    if _active_mesh_backend is None:
        return [], [], []
    try:
        return _active_mesh_backend.parse_mesh_file(mesh_path)
    except Exception:
        return [], [], []


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------
# Sky stores positions in a left-handed frame; exports flip X and Z so the
# result lines up with the terrain the backends already emit in that space.
def _to_export_space(x, y, z):
    return (-x, y, -z)


def transform_vertices(verts, matrix):
    """Apply a 4x4 column-major transform (16 floats) to model-local verts,
    then move into export space. Falls back to a plain flip if the matrix is
    unusable."""
    if not matrix or len(matrix) < 16:
        return [_to_export_space(v[0], v[1], v[2]) for v in verts]
    m = [float(c) for c in matrix[:16]]
    out = []
    for x, y, z in ((v[0], v[1], v[2]) for v in verts):
        wx = m[0] * x + m[4] * y + m[8] * z + m[12]
        wy = m[1] * x + m[5] * y + m[9] * z + m[13]
        wz = m[2] * x + m[6] * y + m[10] * z + m[14]
        out.append(_to_export_space(wx, wy, wz))
    return out


def octahedron_marker(cx, cy, cz, radius=0.5):
    """A tiny 6-vertex diamond used to pin a node's location in the scene."""
    cx, cy, cz = _to_export_space(cx, cy, cz)
    verts = [
        (cx, cy + radius, cz), (cx, cy - radius, cz),
        (cx + radius, cy, cz), (cx - radius, cy, cz),
        (cx, cy, cz + radius), (cx, cy, cz - radius),
    ]
    # top fan (0), bottom fan (1), around the equator ring 2..5
    faces = [
        (0, 2, 4), (0, 4, 3), (0, 3, 5), (0, 5, 2),
        (1, 4, 2), (1, 3, 4), (1, 5, 3), (1, 2, 5),
    ]
    return verts, faces


def color_for_label(label):
    """Stable, reasonably bright RGB derived from a label string."""
    digest = hashlib.md5(label.encode("utf-8")).digest()
    return tuple(round(0.30 + digest[i] / 255.0 * 0.65, 4) for i in range(3))


def _sanitize(name):
    out = name
    for ch in " ()<>/\\":
        out = out.replace(ch, "_")
    return out


# ---------------------------------------------------------------------------
# level.bin traversal
# ---------------------------------------------------------------------------
def _deep_find(props, needle):
    """Depth-first search of a class-data dict for the first key that contains
    `needle` (case-insensitive); returns its value."""
    for key, value in props.items():
        if needle in key.lower():
            return value
    for value in props.values():
        if isinstance(value, dict):
            hit = _deep_find(value, needle)
            if hit is not None:
                return hit
    return None


def _resource_name(props):
    value = _deep_find(props, "resourcename")
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        for sub in value.values():
            if isinstance(sub, str) and sub.strip():
                return sub.strip()
    return None


def _transform_floats(props):
    """Return the 16 raw floats of the node's transform, or None."""
    value = _deep_find(props, "transform")
    if isinstance(value, dict):
        floats = value.get("_raw_floats")
        if floats and len(floats) >= 16:
            return floats
    elif isinstance(value, list) and len(value) >= 16:
        return value
    return None


_DIFFUSE_UNIFORMS = ("u_diffuseTex", "u_diffuse1Tex", "u_diffuse2Tex")
_PLACEHOLDER_TEX = {"White", "Black", "Gray", "Normal", "Clear",
                    "UpNormal", "Orange", "OrangeL1"}


def _diffuse_texture(props):
    params = props.get("shaderParams", [])
    if not isinstance(params, list):
        return None
    fallback = None
    for entry in params:
        shader = entry.get("LevelMeshShaderParam", {}) if isinstance(entry, dict) else {}
        tex = shader.get("texValue", "")
        if not tex:
            continue
        if shader.get("uniformName", "") in _DIFFUSE_UNIFORMS:
            return tex
        if fallback is None and tex not in _PLACEHOLDER_TEX:
            fallback = tex
    return fallback


def collect_instances(bst_nodes):
    """Walk every BST node, splitting them into LevelMesh instances (things we
    place a model for) and plain markers (positioned nodes we pin)."""
    instances = []
    markers = []
    for node_name, node in bst_nodes.items():
        if not isinstance(node, dict):
            continue
        for cls_name, props in node.items():
            if not isinstance(props, dict):
                continue
            floats = _transform_floats(props)
            if floats is None:
                continue
            tx, ty, tz = (float(floats[12]), float(floats[13]), float(floats[14]))
            if "LevelMesh" in cls_name:
                resource = _resource_name(props)
                if not resource:
                    continue
                instances.append({
                    "resource": resource,
                    "matrix": floats,
                    "texture": _diffuse_texture(props),
                })
            else:
                markers.append({
                    "cls": cls_name, "x": tx, "y": ty, "z": tz,
                })
    return instances, markers


# ---------------------------------------------------------------------------
# Textures (KTX BC6H → PNG)
# ---------------------------------------------------------------------------
# glInternalFormat → texture2ddecoder function name. Sky ships map diffuse
# textures in several BC variants, so dispatch on the KTX format field rather
# than assuming one codec.
_KTX_DECODERS = {
    0x8E8F: "decode_bc6", 0x8E8E: "decode_bc6",   # BPTC float  (BC6H)
    0x8E8C: "decode_bc7", 0x8E8D: "decode_bc7",   # BPTC unorm  (BC7 / sRGB)
    0x83F0: "decode_bc1", 0x83F1: "decode_bc1",   # DXT1
    0x83F3: "decode_bc3",                         # DXT5
    0x8DBB: "decode_bc4", 0x8DBD: "decode_bc5",   # RGTC
}


def _decode_ktx(ktx_path, png_path):
    if not _HAS_KTX:
        return False
    try:
        with open(ktx_path, "rb") as f:
            f.read(28)                  # identifier .. glFormat
            gl_format = struct.unpack("<I", f.read(4))[0]
            f.read(4)                   # glBaseInternalFormat
            width = struct.unpack("<I", f.read(4))[0]
            height = struct.unpack("<I", f.read(4))[0]
            f.read(4 * 4)               # depth / array / face / level counts
            kvd_len = struct.unpack("<I", f.read(4))[0]
            f.read((kvd_len + 3) & ~3)  # skip padded key/value data
            img_size = struct.unpack("<I", f.read(4))[0]
            blob = f.read(img_size)
        decoder = _KTX_DECODERS.get(gl_format)
        if not decoder:
            return False
        pixels = getattr(texture2ddecoder, decoder)(blob, width, height)
        img = _Image.frombytes("RGBA", (width, height), pixels)
        b, g, r, a = img.split()        # texture2ddecoder returns BGRA
        _Image.merge("RGBA", (r, g, b, a)).save(png_path)
        return True
    except Exception:
        return False


def _locate_ktx(image_dirs, tex_name):
    for folder in image_dirs:
        candidate = os.path.join(folder, f"{tex_name}.ktx")
        if os.path.exists(candidate):
            return candidate
    return None


def _bake_textures(textures, image_dirs, out_dir):
    """Convert the KTX referenced by each unique texture name to PNG.
    Returns {tex_name: relative_png_path}."""
    baked = {}
    if not (image_dirs and textures and _HAS_KTX):
        return baked
    tex_dir = os.path.join(out_dir, "textures")
    os.makedirs(tex_dir, exist_ok=True)
    for tex_name in textures:
        png_path = os.path.join(tex_dir, f"{tex_name}.png")
        if not os.path.exists(png_path):
            ktx = _locate_ktx(image_dirs, tex_name)
            if not ktx or not _decode_ktx(ktx, png_path):
                continue
        if os.path.exists(png_path):
            baked[tex_name] = os.path.join("textures", f"{tex_name}.png")
    return baked


# ---------------------------------------------------------------------------
# .mesh lookup
# ---------------------------------------------------------------------------
def find_mesh_file(mesh_folder, resource):
    if not os.path.isdir(mesh_folder):
        return None
    exact = os.path.join(mesh_folder, f"{resource}.mesh")
    if os.path.exists(exact):
        return exact
    try:
        for name in os.listdir(mesh_folder):
            if name.endswith(".mesh") and resource in name:
                return os.path.join(mesh_folder, name)
    except OSError:
        pass
    return None


# ---------------------------------------------------------------------------
# OBJ / MTL writer
# ---------------------------------------------------------------------------
class ObjScene:
    """Accumulates named objects (verts / faces / optional uvs / material) and
    the materials they reference, then serialises the whole thing as one
    OBJ + MTL pair with a shared vertex/texcoord counter."""

    def __init__(self, name):
        self.name = name
        self.objects = []          # list of dicts
        self.plain_mats = {}       # mtl_name -> (r, g, b)
        self.textured_mats = {}    # mtl_name -> relative png path

    def add_material(self, mtl_name, rgb):
        self.plain_mats.setdefault(mtl_name, rgb)

    def add_textured_material(self, mtl_name, png_rel):
        self.textured_mats.setdefault(mtl_name, png_rel)

    def add_object(self, name, mtl_name, verts, faces, uvs=None):
        if not verts or not faces:
            return
        self.objects.append({
            "name": name, "mtl": mtl_name,
            "verts": verts, "faces": faces, "uvs": uvs,
        })

    def write(self, obj_path, mtl_path):
        with open(mtl_path, "w", encoding="utf-8") as mf:
            mf.write(f"# Materials for {self.name}\n\n")
            for mtl_name, (r, g, b) in self.plain_mats.items():
                mf.write(f"newmtl {mtl_name}\n")
                mf.write(f"Kd {r:.4f} {g:.4f} {b:.4f}\n")
                mf.write("Ka 0.1 0.1 0.1\nKs 0.0 0.0 0.0\nd 1.0\n\n")
            for mtl_name, png_rel in self.textured_mats.items():
                mf.write(f"newmtl {mtl_name}\n")
                mf.write("Kd 1.0 1.0 1.0\nKa 0.1 0.1 0.1\n")
                mf.write(f"map_Kd {png_rel}\nd 1.0\n\n")

        v_base = 1
        vt_base = 1
        with open(obj_path, "w", encoding="utf-8") as of:
            of.write(f"# Sky map: {self.name}\n")
            of.write(f"mtllib {os.path.basename(mtl_path)}\n\n")
            for obj in self.objects:
                verts, faces, uvs = obj["verts"], obj["faces"], obj["uvs"]
                of.write(f"o {obj['name']}\n")
                of.write(f"usemtl {obj['mtl']}\n")
                for v in verts:
                    of.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
                if uvs:
                    for uv in uvs:
                        of.write(f"vt {uv[0]:.6f} {uv[1]:.6f}\n")
                    for a, b, c in faces:
                        of.write(
                            f"f {a+v_base}/{a+vt_base} "
                            f"{b+v_base}/{b+vt_base} {c+v_base}/{c+vt_base}\n")
                    vt_base += len(uvs)
                else:
                    for a, b, c in faces:
                        of.write(f"f {a+v_base} {b+v_base} {c+v_base}\n")
                v_base += len(verts)
                of.write("\n")


def _terrain_face_material(faces, mat_ids):
    """Assign each triangle the material shared by the majority of its three
    vertices."""
    result = []
    for tri in faces:
        votes = {}
        for vi in tri:
            mid = mat_ids[vi] if vi < len(mat_ids) else -1
            votes[mid] = votes.get(mid, 0) + 1
        result.append(max(votes, key=votes.get))
    return result


# ---------------------------------------------------------------------------
# Single-map export
# ---------------------------------------------------------------------------
def _find_map_files(map_folder):
    """Return (level_bin, terrain_meshes) inside a map folder."""
    level_bin = terrain = None
    try:
        for name in os.listdir(map_folder):
            full = os.path.join(map_folder, name)
            if name.endswith(".meshes"):
                terrain = full
            elif name.endswith(".bin"):
                level_bin = full
    except OSError:
        pass
    return level_bin, terrain


def export_single_map(map_folder, mesh_folder, output_base_dir,
                      export_markers, enabled_classes, log_entry,
                      image_dirs=None):
    map_name = os.path.basename(map_folder)
    out_dir = os.path.join(output_base_dir, map_name)
    os.makedirs(out_dir, exist_ok=True)

    log_entry.update({
        "map_name": map_name, "map_path": map_folder,
        "output_path": out_dir, "export_markers": export_markers,
        "start_time": datetime.now().isoformat(),
    })

    level_bin, terrain_file = _find_map_files(map_folder)
    if not level_bin:
        log_entry["status"] = "failed"
        log_entry["error"] = "未找到 .bin 文件"
        return False
    log_entry["bin_file"] = os.path.basename(level_bin)
    log_entry["meshes_file"] = os.path.basename(terrain_file) if terrain_file else None

    # 1. Parse the level definition straight from the .bin (no temp JSON).
    try:
        level = bintojson.parse_bin(level_bin)
    except Exception as exc:
        log_entry["status"] = "failed"
        log_entry["error"] = f"level.bin 解析失败: {exc}"
        return False
    instances, markers = collect_instances(level.get("BSTNodes", {}))

    # De-duplicate the resources we actually need to load, and remember the
    # texture each resource wants.
    resource_texture = {}
    for inst in instances:
        if inst["texture"]:
            resource_texture.setdefault(inst["resource"], inst["texture"])
    log_entry["levelmesh_count"] = len(instances)
    log_entry["unique_resources"] = len({i["resource"] for i in instances})

    if export_markers and enabled_classes is not None:
        keep = set(enabled_classes)
        markers = [m for m in markers if m["cls"] in keep]
    elif not export_markers:
        markers = []
    log_entry["markers_count"] = len(markers)

    scene = ObjScene(map_name)

    # 2. Terrain.
    terrain_verts, terrain_faces, _colors, terrain_mat_ids = ([], [], [], [])
    if terrain_file and _active_meshes_backend:
        terrain_verts, terrain_faces, _colors, terrain_mat_ids = \
            parse_meshes_to_obj_data(terrain_file)
    log_entry["terrain_verts"] = len(terrain_verts)
    log_entry["terrain_tris"] = len(terrain_faces)

    if terrain_verts and terrain_faces:
        if terrain_mat_ids:
            face_mat = _terrain_face_material(terrain_faces, terrain_mat_ids)
            groups = {}
            for tri, mid in zip(terrain_faces, face_mat):
                groups.setdefault(mid, []).append(tri)
            for mid, tris in sorted(groups.items()):
                mtl_name = MATERIAL_NAMES.get(mid, f"terrain_{mid}")
                rgb = MATERIAL_COLORS.get(mid, MATERIAL_COLOR_DEFAULT)
                scene.add_material(mtl_name, rgb)
                scene.add_object(f"Terrain_{mtl_name}", mtl_name,
                                 terrain_verts, tris)
        else:
            scene.add_material("terrain", (0.45, 0.42, 0.38))
            scene.add_object("Terrain", "terrain",
                             terrain_verts, terrain_faces)

    # 3. Load each unique model once, then bake every instance's transform.
    scene.add_material("model", (0.75, 0.73, 0.68))
    loaded = {}
    stats = {"ok": 0, "empty": 0, "missing": 0}
    if _active_mesh_backend and os.path.isdir(mesh_folder):
        for resource in {i["resource"] for i in instances}:
            path = find_mesh_file(mesh_folder, resource)
            if not path:
                stats["missing"] += 1
                continue
            verts, uvs, faces = parse_mesh_file(path)
            if verts and faces:
                loaded[resource] = (verts, uvs, faces)
                stats["ok"] += 1
            else:
                stats["empty"] += 1

    baked_textures = _bake_textures(
        {t for t in resource_texture.values()}, image_dirs, out_dir)

    placed = 0
    for inst in instances:
        model = loaded.get(inst["resource"])
        if not model:
            continue
        verts, uvs, faces = model
        world_verts = transform_vertices(verts, inst["matrix"])

        tex_name = resource_texture.get(inst["resource"])
        if tex_name and tex_name in baked_textures:
            mtl_name = f"tex_{tex_name}"
            scene.add_textured_material(mtl_name, baked_textures[tex_name])
        else:
            mtl_name = "model"
        scene.add_object(inst["resource"], mtl_name, world_verts, faces,
                         uvs if uvs else None)
        placed += 1

    log_entry["models_success"] = stats["ok"]
    log_entry["models_empty"] = stats["empty"]
    log_entry["models_missing"] = stats["missing"]
    log_entry["models_count"] = len(loaded)
    log_entry["models_instances"] = placed
    log_entry["textures_count"] = len(baked_textures)

    # 4. Markers, grouped by class into one object each.
    if export_markers and markers:
        by_class = {}
        for m in markers:
            by_class.setdefault(m["cls"], []).append(m)
        for cls_name, nodes in sorted(by_class.items()):
            mtl_name = _sanitize(cls_name)
            scene.add_material(mtl_name, color_for_label(cls_name))
            verts, faces = [], []
            for node in nodes:
                v, f = octahedron_marker(node["x"], node["y"], node["z"])
                base = len(verts)
                verts.extend(v)
                faces.extend((a + base, b + base, c + base) for a, b, c in f)
            scene.add_object(f"{mtl_name}_Markers", mtl_name, verts, faces)

    # 5. Serialise.
    obj_path = os.path.join(out_dir, f"{map_name}.obj")
    mtl_path = os.path.join(out_dir, f"{map_name}.mtl")
    try:
        scene.write(obj_path, mtl_path)
    except Exception as exc:
        log_entry["status"] = "failed"
        log_entry["error"] = str(exc)
        return False

    log_entry["status"] = "success"
    log_entry["obj_path"] = obj_path
    return True
