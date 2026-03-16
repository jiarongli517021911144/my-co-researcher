# coresearcher

[English](README.en.md)

`coresearcher` 是一个基于 `asyncio` 的个人 AI 助手框架，提供命令行代理、本地 Web UI、工作区上下文、工具系统、记忆、规划、定时任务，以及飞书和 QQ 渠道接入能力。

它的目标不是再包一层聊天接口，而是提供一个可以直接运行、扩展和演示的 assistant runtime。

![前端概览](image/overview.png)

## 功能特性

- 命令行对话入口和本地多页面 Web UI
- 可引导初始化的 workspace，上下文文件可直接编辑
- 文件系统、Shell、Web fetch/search、MCP、Cron、Subagent、Memory Search 等工具
- Planning、Reflexion、RAG 和会话历史管理
- 统一 Provider 抽象，并提供离线 `mock` provider 方便 demo
- CLI、飞书、QQ 三种渠道接入
- 内置 demo 与评测骨架

## 快速开始

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
python demos/open_source_demo.py
```

默认 demo 完全离线运行。它会在 `.demo/open_source_demo/` 下创建独立 config 和 workspace，用 mock provider 跑几个完整回合，并打印后续可执行命令。

如果要基于这份 demo 配置启动本地 Web UI：

```bash
CORESEARCHER_CONFIG=$(pwd)/.demo/open_source_demo/config.json python -m coresearcher web
```

然后访问 `http://127.0.0.1:8765`。

## 使用真实模型

你可以选择两种方式：

1. 从示例配置开始：

```bash
cp config.example.json ~/.coresearcher/config.json
```

2. 或直接运行交互式初始化：

```bash
python -m coresearcher onboard
```

然后尝试：

```bash
python -m coresearcher agent -m "Hello"
python -m coresearcher status
```

## 公开渠道能力

项目公开保留以下渠道接入：

- 飞书
- QQ

这两类接入需要你自己配置平台凭证和应用信息。做本地开发时，建议先从 CLI 和 Web UI 开始。

## 仓库结构

```text
coresearcher/              核心包
providers/            被 coresearcher 复用的 provider 兼容层
demos/                可直接运行的 demo
eval/datasets/        对外公开的评测数据集
config.example.json   最小配置模板
```

## 打包说明

- 对外文档以 `README.md` 和 `README.en.md` 为主。
- 本地运行状态、日志、评测输出和内部笔记默认不进入公开仓库。
- workspace 初始化模板已经收口到 `coresearcher/workspace/templates/`，不再依赖你本地的私有 `workspace/` 目录内容。

## 补充文档

- `docs/architecture.md`
- `docs/channels.md`

## 参与贡献

开发环境和回归命令见 `CONTRIBUTING.md`。
