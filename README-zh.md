# SkyVEx

**光遇模型可视化便捷导出**（Convenient Visualization and Export of Sky: Children of the Light Models）

《光·遇》地图 3D 数据导出工具 — 可视化界面。

[中文](./README-zh.md) | [English](./README.md)

## 这个项目是什么

一个自包含的图形化工具，把光遇游戏数据导出成 Wavefront OBJ。**界面、地图→OBJ
导出引擎、`.bin`/`.mesh` 解析器、3D 预览、纹理管线全部是 SkyVEx 原创代码**。仅
地形解码器（`Sky_Bstbake.py`）和一个可选的备用后端（`meshes2obj_json.py`）为
第三方，且**原样使用**，保留原作者署名与许可。

功能：

- **一键扫描游戏目录** — 选择游戏安装路径，自动识别所有地图和 Mesh 文件
- **APK 提取** — 直接打开光遇 APK 安装包，无需 PC 端游戏即可提取资源
- **分页资源浏览** — 三个标签页（地形 / 模型库 / 图片资源），按场景分组的地图树、按前缀分组的 4000+ 独立模型、KTX 纹理图库
- **3D 预览** — 实时 OpenGL 预览，支持地形顶点着色（材质混合 + AO）和顶部柔光；点击任意地图或模型即可预览
- **2D 图片预览** — 在图片资源标签页点击任意 KTX 纹理即可解码预览（BC1/BC3/BC4/BC5/BC6H/BC7）
- **按材质分组地形导出** — 地形 OBJ 按材质 ID 拆分，共享材质表（MTL），可直接在 Blender 中分配材质
- **独立模型导出** — 浏览并批量导出单个 `.mesh` 模型（道具、角色、物件）为 OBJ，不限于地形地图
- **标记类名扫描** — 从 `.bin` 文件扫描标记类名，自由勾选要导出的标记类型
- **纹理提取** — KTX → PNG，按格式分别解码（BC1/BC3/BC4/BC5/BC6H/BC7），OBJ 内 UV 映射，MTL 内 `map_Kd` 材质引用
- **可插拔后端系统** — 运行时切换原生 / 纯 Python 解析器
- **高 DPI 适配** — 高分屏 / 缩放显示下界面清晰不模糊
- **光遇风格暗色主题** — 深蓝配色，还原游戏视觉风格

> **来源标注：** 每个源文件顶部都写有归属头，说明它由谁编写、来自哪个仓库、
> 什么许可。第三方许可见 [NOTICE](./NOTICE)。

## 截图

![SkyVEx GUI](./screenshot.png)

## 依赖

Python 3.8+

```bash
pip install -r tool/scripts/requirements.txt
# lz4  Pillow  texture2ddecoder  PyOpenGL
```

- `lz4` — 地形（LOD0）解压**必需**。
- `Pillow` + `texture2ddecoder` — 纹理（KTX→PNG）导出和 2D 图片预览需要。
- `PyOpenGL` — 3D 预览面板需要（`PyOpenGL_accelerate` 可选）。

用于精细地形的 `meshoptimizer` 原生解码库已**预编译随附**于
`tool/scripts/_meshopt/lib/meshoptimizer.dll`（由
[zeux/meshoptimizer](https://github.com/zeux/meshoptimizer)(MIT) 官方源码自行
编译），**不是** pip 依赖。

## 使用方法

### GUI（推荐）

**Windows：** 双击项目根目录的 `SkyVEx.exe` 即可启动。

或通过命令行运行：

```bash
cd tool/scripts
python gui.py
```

1. **浏览** 选择游戏安装目录，点击 **扫描** — 或点击 **APK** 直接打开 APK 安装包
2. 通过标签页浏览资源：**地形** 查看地图、**模型库** 查看独立模型、**图片资源** 查看 KTX 纹理
3. 勾选 **3D 预览** 实时查看任意地图或模型的 OpenGL 渲染效果；点击图片可查看 2D 预览
4. 点击 **扫描标记类名** 发现标记类型，按需开关标记、纹理导出，设置输出目录
5. 点击 **开始导出** — 同时导出选中的地图和独立模型

### 命令行

```bash
cd tool/scripts
python bintojson.py Objects.level.bin                        # bin → json
python Sky_Bstbake.py --unpack BstBaked.meshes --export-obj  # 仅地形（上游工具）
```

地图/模型导出由 GUI 驱动；引擎在 `exporter.py`，由 `gui.py` 导入调用，不单独运行。

## 文件结构

```
SkyVEx.exe                         # Windows 启动器（由 SkyVEx.py 构建）
SkyVEx.py                          # 启动器入口脚本
│
tool/scripts/
│  [原创 — lingyunalingyun]
├── gui.py                     # 可视化界面 & 纹理管线
├── exporter.py                # 地图 → OBJ/MTL 组装引擎
├── backends.py                # 可插拔后端注册层
├── mesh_parser.py             # 纯 Python .mesh 解析器（全版本）
├── preview3d.py               # OpenGL 3D 预览面板
├── bintojson.py               # TGCL .bin → dict/JSON 解析器（格式参考 Miau）
│
│  [第三方 — 原样，详见各文件头]
├── Sky_Bstbake.py             # 地形 .meshes 解码器 — ThatSkyOldServer/SkyBstbake (MIT)
├── meshes2obj_json.py         # 可选备用 .meshes 后端 — 县小威 移植自 that-sky-project (LGPL-2.1)
└── _meshopt/
    └── lib/
        └── meshoptimizer.dll  # zeux/meshoptimizer (MIT)，自行编译
```

每个脚本文件头部都写有归属头。第三方许可明细见 [NOTICE](./NOTICE)。

## 第三方文件

两个第三方源文件均**原样**取自各自上游仓库（仅在顶部加了 SkyVEx 归属头注释）：

| 文件 | 上游 | 许可 |
|------|------|------|
| `Sky_Bstbake.py` | [ThatSkyOldServer/SkyBstbake](https://github.com/ThatSkyOldServer/SkyBstbake) — checion (雨人) & Heriel (落秋) | MIT |
| `meshes2obj_json.py` | 县小威 — 移植自 [that-sky-project](https://github.com/that-sky-project/that-sky-level) | LGPL-2.1 |

`meshoptimizer.dll` 由 [zeux/meshoptimizer](https://github.com/zeux/meshoptimizer)
(MIT) 官方源码编译。

## OBJ 输出内容

| 数据 | 说明 |
|------|------|
| 地形 | 地面网格按材质 ID 拆分，共享 MTL 材质表，顶点着色 + AO |
| 模型（地图内） | 场景物体，已按实例应用变换矩阵，X/Z 轴翻转适配 Blender |
| 模型（独立） | 单个 `.mesh` 文件导出至 `Meshes/` 子文件夹，含 UV |
| 标记 | 交互点位置的小八面体标记（可选），按类名着色 |
| 纹理 | PNG 文件 + `map_Kd` 材质引用（可选） |

## 构建 exe

需要 [PyInstaller](https://pyinstaller.org/)：

```bash
pip install pyinstaller
pyinstaller --onefile --noconsole --icon=icon.ico --name SkyVEx SkyVEx.py
```

生成的 `dist/SkyVEx.exe` 放到项目根目录即可。目标机器仍需安装 Python — exe 只是启动器，不是独立打包。

## 常见问题

| 问题 | 解决 |
|------|------|
| 缺少 `lz4` | `pip install lz4`（地形必需） |
| 地形 0 顶点 | 确认 `_meshopt/lib/meshoptimizer.dll` 存在且已装 `lz4` |
| 模型缺失 | 需从游戏资源包 `Data/Meshes/Bin` 提取 `.mesh` 文件 |
| 纹理导出失败 | `pip install texture2ddecoder Pillow` |
| 3D 预览不可用 | `pip install PyOpenGL` |

## 致谢

- **GUI、导出引擎、`.bin`/`.mesh` 解析器、3D 预览、纹理管线、后端系统** — lingyunalingyun（本项目原创代码）。
- **地形解码器** `Sky_Bstbake.py` — checion (雨人) & Heriel (落秋)，[ThatSkyOldServer/SkyBstbake](https://github.com/ThatSkyOldServer/SkyBstbake) (MIT)。
- **可选 `.meshes` 后端** `meshes2obj_json.py` — 县小威 (XiaoWei)，移植自 [that-sky-project](https://github.com/that-sky-project/that-sky-level) (LGPL-2.1)。
- **原生解码库** `meshoptimizer.dll` — [Arseny Kapoulkine (zeux)](https://github.com/zeux/meshoptimizer) (MIT)。
- **格式参考（公开字节布局，非代码）：** Miau — [Sky-.bin-reader](https://github.com/Miau0x1/Sky-.bin-reader)；kfhammond — [SkyModelViewer](https://github.com/kfhammond/SkyModelViewer)。

## 许可证

SkyVEx 自身代码以 **MIT 许可证** 发布 — 见 [LICENSE](./LICENSE)。

`meshes2obj_json.py` 以 **LGPL-2.1** 发布（仅该文件）— 详见文件头，完整许可证
全文见 [licenses/LGPL-2.1.txt](./licenses/LGPL-2.1.txt)。第三方组件
保留各自原始许可，见 [NOTICE](./NOTICE)。
