# FitMuse AI MVP

本地 AI 虚拟试衣 GUI（基于 Gradio）。上传人物和服装图片，通过虚拟提供商生成试衣结果，并管理标准图片。真实提供商接口已预留桩代码；后续需添加 API 密钥和提供商逻辑。

## 环境配置（Conda）

```bash
conda create -n fitmuseai310 python=3.10
conda activate fitmuseai310
pip install -r requirements.txt
```

## 配置

```bash
copy .env.example .env
# 根据需要填写 API 密钥
```

## 运行

```bash
python app.py
```

## 项目结构

本仓库是一个单进程本地应用。`app.py` 负责配置加载、本地存储、提供商注册表、元数据管理以及 Gradio UI 的构建。

```
.
├─ app.py                 # 程序入口：加载配置、确保目录存在、构建存储/提供商、启动 Gradio
├─ README.md              # 项目概述
├─ requirements.txt       # Python 依赖项
├─ .env.example           # 环境变量模板（复制为 .env）
├─ data/                  # 运行时资源和 SQLite 元数据（已被 git 忽略）
│  ├─ persons/            # 人物资源：每个人物一个文件夹（image.png + thumb.jpg）
│  ├─ garments/           # 服装资源：每件服装一个文件夹（image.png + thumb.jpg）
│  ├─ results/
│  │  ├─ images/           # 提供商保存的试衣图片
│  │  └─ videos/           # 视频输出（未来功能/预留桩代码）
│  ├─ thumbnails/         # 预留给共享缩略图（启动时创建）
│  └─ metadata.sqlite     # 用于人物、服装、结果、标准图片的 SQLite 数据库
├─ doc/
│  └─ FitMuseAI_ai_virtual_tryon_requirements_domestic_api.md
│                           # 产品需求和国内 API 规划（中文）
└─ src/
	├─ __init__.py          # 包标识文件
	├─ config.py            # 加载 .env，构建 AppConfig
	├─ storage.py           # 创建文件夹、标准化图片、保存资源、ID、相对路径
	├─ image_utils.py       # 图片工具函数（标准化、缩略图、虚拟占位符）
	├─ metadata_store.py    # SQLite 模式 + 人物/服装/结果/标准图片的 CRUD 操作
	├─ prompt_builder.py    # 试衣/视频的提示词模板和构建器
	├─ public_asset_store.py# 公共 URL 上传桩代码（用于需要公共 URL 的提供商）
	├─ providers/
	│  ├─ __init__.py        # 提供商注册表（虚拟提供商 + 占位提供商）
	│  ├─ base.py            # 提供商接口 + 请求/结果数据类
	│  ├─ dummy_provider.py  # 本地占位图片生成器（非 AI，并排显示）
	│  └─ placeholder_provider.py
	│                        # 桩提供商，验证环境变量并返回"未实现"
	└─ ui/
		└─ gradio_app.py      # Gradio UI 布局 + 事件处理器
```

## 运行时流程（高层概览）

1. `app.py` 从 `.env` 加载配置，设置工作目录，并确保 `data/` 文件夹存在。
2. `MetadataStore` 打开 `data/metadata.sqlite` 并准备数据表。
3. 构建提供商注册表（启用虚拟提供商，真实提供商为桩代码）。
4. `build_app()` 构建 Gradio UI 并绑定回调函数。
5. 用户上传资源；图片被标准化并存储在 `data/persons` 和 `data/garments` 下。
6. 试衣请求被发送到选定的提供商；结果存储在 `data/results/images` 中并记录到 SQLite。

## UI 标签页（Gradio）

- **Assets（资源管理）**：上传和管理人物及服装。
- **Single Try-On（单次试衣）**：选择一个人物 + 一件服装并生成图片。
- **Batch（批量处理）**：选择多个人物/服装并生成组合。
- **Canonical（标准图片）**：为人物 + 服装组合设置"最佳"图片。
- **History（历史记录）**：浏览过往结果（图片/视频）。
- **Admin（数据库管理）**：编辑人物/服装元数据，批量导入，删除记录（可选删除文件）。
- **Settings（设置）**：根据 `.env` 显示提供商就绪状态。

## 后台管理（Admin）

- 支持编辑人物与服装的名称、描述、分类等字段。
- 支持删除人物/服装记录，可选择同时删除对应文件夹。
- 支持从 `data/persons` 与 `data/garments` 批量注册资产（每个资产一个子目录，包含 `image.<ext>`）。

## 注意事项

- 所有数据存储在 `data/` 目录下
- `.env` 和 `data/` 已被 git 忽略