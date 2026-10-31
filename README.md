# 项目札记 · Folio Relay

轻量的本地项目记录与交接工具。集中展示项目结构、目标、逻辑周日进度和下一步，让人和外部 agent 能连续接手。

应用提供存储与展示，不内置 agent，不设置登录，也不依赖云端服务。不同项目的工作方式、角色和内容保存在各自资料中。

## 工程与个人资料分开

本仓库只包含通用软件工程。真实项目、备份、用户设置、私人开发笔记和真实截图独立保存，不参与源码提交或应用打包。新取得的源码从空项目开始，不附带任何人的学习记录。

```text
本地工作目录/
├── 工程文件/                 此源码仓库
├── 项目札记.app              Mac 构建产物
├── 项目札记/                 Windows 构建产物目录
├── 项目资料/                 用户选择的资料目录，不入库
│   └── projects/<项目ID>/
│       ├── 正在使用文件/
│       └── 备份资料/
└── 本地开发资料/              私人笔记、截图等本地工作材料，不入库
```

目录名称可改变。源码、程序和用户资料的职责及模块依赖见 [架构与文件边界](docs/architecture.md)。

## 使用应用

Mac 上双击构建得到的 `项目札记.app`，可在独立窗口操作，不需要另外安装 Python。关闭窗口时会结束应用自己启动的本地服务。

窗口右上角“使用说明”按开始与交接、首次设置、续接与换周、查看与补记、资料与迁移说明操作、目的和完成标志。日常闭环是：确认起点、开展工作、管理者保存交接、在页面核对、下次从最新记录继续。

应用默认识别程序旁边的“项目资料”；Windows 文件夹版也检查程序目录上一级。可通过系统菜单“资料 → 选择资料目录…”指定另一份包含 `projects/` 的资料根目录。同一程序位置下会记住该选择；仅有程序而没有旁边资料时，使用用户 Documents 下的“项目札记/项目资料”。

## 从源码运行

建议使用 Python 3.12。在源码根目录建立独立环境：

```sh
python3.12 -m venv .venv
```

Mac 激活环境后启动独立窗口：

```sh
source .venv/bin/activate
python -m pip install -r requirements-desktop.txt
python desktop.py
```

Windows 使用 `.venv\Scripts\activate` 激活环境，再执行相同的安装与启动命令；桌面窗口需要 Microsoft WebView2 Runtime。

仅使用浏览器界面和本地接口时，标准库即可运行：

```sh
python local_server.py --open
```

默认本机地址为 `http://127.0.0.1:4173`，端口占用时选择后续空闲端口。可用 `--data-dir "资料根目录"` 指定独立资料，使用 `--stop` 停止浏览器开发服务。程序只监听本机。

## 构建

先退出正在更新的应用。分别在目标系统安装构建依赖并运行：

```sh
python -m pip install -r requirements-build.txt
python build_app.py
```

也可以使用 `构建Mac应用.command` 或 `构建Windows应用.cmd`。默认输出源码目录的上一级，`--output "程序输出目录"` 可另行指定。构建只收集程序、前端、通用记录说明和运行依赖；中间文件在临时目录完成后清理。

| 平台 | 产物 | 验证范围 |
| --- | --- | --- |
| macOS | `项目札记.app` | Apple Silicon 已构建和运行；其他架构需分别构建验证 |
| Windows | `项目札记/项目札记.exe`，保留同目录 `_internal/` | 保留构建入口及平台适配，仍需 Windows 实机构建和验证 |

图标的唯一设计源为 `assets/app.svg`；修改后运行 `python assets/create_icon.py`，统一生成 PNG、Mac ICNS、Windows ICO 和应用内的 `dist/brand.svg`。生成器不依赖系统字体，resvg-py 与 Pillow 仅用于开发工具，不进入应用运行依赖。Mac 对外分发时按目标系统要求处理签名与发布验证。

## 源码导航

| 位置 | 职责 |
| --- | --- |
| `desktop.py` | 原生窗口、应用生命周期、系统对话框及资料选择 |
| `local_server.py` | 本机 HTTP 接口与静态资源 |
| `storage.py` | 通用 JSON 校验、保存、版本检查、备份和归档 |
| `app_paths.py` / `platform_support.py` | 路径定位与系统差异 |
| `dist/` | 页面、样式、角色读取清单和给人的使用说明 |
| `assets/` | 程序图标与生成工具 |
| `build_app.py` / `project_notes.spec` | Mac 与 Windows 打包 |
| `test_*.py` / `test_reading_plan.js` | 临时资料和虚构项目验证 |
| `AGENTS.md` | 软件开发约定 |
| `记录读写说明.md` | 被管理项目共用的记录格式及保存协议 |

## 项目资料与交接

每个项目的“正在使用文件”保存项目概况 `project.json`、目标 `roadmap.json`、当前周 `current/` 及正式历史周 `history/`。“备份资料”保存该项目的旧副本，按用途和时间分类，由使用者手动清理，不自动删除。

项目的技术限制、协作规则和角色职责来自它自己的 JSON。软件的开发约定不决定被管理项目的业务要求。格式及写入时机见 [记录读写说明](记录读写说明.md)。

单文件接口从“正在使用文件”目录起算相对文件名：

- `GET /api/projects/<ID>/files/<文件名>` 获取 JSON 和 ETag。
- `PUT` 同一路径，提交完整 JSON、`Content-Type: application/json` 和读取到的 `If-Match`。
- `GET /api/projects/<ID>/locations` 获取当前机器上的实际文件位置。
- `POST /api/projects` 创建空项目；`POST /api/import` 导入项目 JSON 包。
- `POST /api/projects/<ID>/next-week` 在记录满足归档条件后建立下一周。

项目 JSON 导出只包含正式记录。连同备份一起迁移时复制整个项目目录；整体搬迁时复制应用与资料，打开后核对实际路径和最新记录，再重新复制接续清单。外部代码仓库、数据库和开发环境按需另行迁移。

## 验证

测试自行创建临时目录和虚构记录，不需要真实项目：

```sh
python -m unittest discover -s . -p 'test_*.py'
node --test test_reading_plan.js
```

Node 只用于此项前端逻辑检查，应用运行不依赖 Node。资料和打包资源检查可显式选择独立资料目录：

```sh
python desktop.py --check --data-dir "独立资料目录"
```

提交和发布范围只限工程文件。真实资料、私人工作记录和旧站点历史不进入源码或 Git 历史；运行包作为单独的构建产物交付。
