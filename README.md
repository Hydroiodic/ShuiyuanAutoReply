# ShuiyuanAutoReply

[![CI](https://github.com/Hydroiodic/ShuiyuanAutoReply/actions/workflows/ci.yml/badge.svg)](https://github.com/Hydroiodic/ShuiyuanAutoReply/actions/workflows/ci.yml)

水源社区（shuiyuan.sjtu.edu.cn）自动回复机器人。`shuiyuan_auto_reply` 包负责与水源 API 交互、监听话题和 @ 提及，并提供塔罗牌、今日运势、A 股行情、语录记录等功能；`examples/` 中是基于它搭建的“南瓜 bot”。

## 目录结构

```text
src/shuiyuan_auto_reply/   可安装的 Python 包
  shuiyuan/                水源 API 客户端、话题/提及监听基类、回复工具函数
  openrouter/              OpenRouter（OpenAI 兼容接口）客户端与图片生成工具
  database/                Postgres（语录、长期记忆）与 Neo4j（语气检索）管理器
  tarot/  fortune/  ashare/ 塔罗牌、今日运势图片、A 股行情
  assets/                  塔罗牌数据与图片、字体
examples/                  南瓜 bot：各话题/提及模型、FastAPI 对话后端
scripts/                   数据库初始化脚本
tests/                     pytest 测试
```

## 安装

需要 Python 3.12 及以上。

```bash
python -m venv .venv
source .venv/bin/activate
# 可选：只用 CPU 时先装 CPU 版 PyTorch，避免下载数 GB 的 CUDA 依赖
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[dev]"          # 运行 examples/backend.py 还需要 ".[server]"
```

## 配置与运行

1. 复制 `.env.example` 为 `.env` 并填写 OpenRouter、Postgres、Neo4j、向量模型等配置。
2. 准备登录水源后保存的 cookies 文件（默认读取当前目录下的 `cookies`）。
3. 初始化数据库（按需）：

   ```bash
   python scripts/postgres_init.py
   python scripts/neo4j_init.py   # 若存在 scripts/user_archive.csv 会一并导入
   ```

4. 在仓库根目录启动机器人，或启动对话后端：

   ```bash
   python -m examples.main
   cd examples && python backend.py
   ```

## 开发规范

- 代码格式：[black](https://black.readthedocs.io/) + [isort](https://pycqa.github.io/isort/)；静态检查：[ruff](https://docs.astral.sh/ruff/)。配置都在 `pyproject.toml` 中。
- 提交前检查：执行一次 `pre-commit install`，之后每次 `git commit` 都会自动格式化并检查；也可以手动运行 `pre-commit run --all-files`。
- 测试：`pytest`。

## 持续集成

`.github/workflows/ci.yml` 在每次推送时运行：

1. **Format and lint**：用 `.pre-commit-config.yaml` 中固定版本的工具格式化代码；如有改动，由 `github-actions[bot]` 自动提交 `style: auto-format code with pre-commit` 回推送的分支（之后本地请先 `git pull`）。无法自动修复的 lint 问题会让这一步失败。来自 fork 的 PR 只做检查，不会推送。
2. **Test**：安装依赖并运行 `pytest`。
3. **Build wheel**：用 `python -m build` 打包 sdist 和 wheel，确认资源文件已打进 wheel，并作为 `shuiyuan-auto-reply-dist` 工件上传，可在 Actions 运行页面下载。
4. **Publish GitHub release**：推送 `v*` 标签（如 `v0.1.0`）时，把打包好的文件发布到对应的 GitHub Release。

### 今日运势图片主题

塔罗回复模块中的 `【今日运势】` 支持主题选择，未指定时保持原来的洛谷样式：

- `【今日运势】` / `【今日运势】【默认】` / `【今日运势】【洛谷】`
- `【今日运势】【Phigros】`（英文主题名不区分大小写）

Python 接口：`FortuneModel(username, theme="phigros").generate_fortune()`。
`fortune/themes.py` 统一注册主题标识、名称、画布大小与绘制函数。主题只影响显示，
运势和宜忌仍共用原有抽取逻辑；塔罗牌面、正逆位以及图片缓存保持不变。
新增主题可注册新的 `FortuneTheme`，不需要复制抽取或上传流程。

Phigros 主题提取自 `Hydroiodic/phi-plugin-openclaw` 的默认视觉样式：斜切面板、
暗色半透明底、青蓝与金色强调色及 EZ/HD/IN/AT 四色条；背景资源已随本项目打包，
字体使用本项目已有字体。资源来源见 `assets/themes/phigros/SOURCE.txt`。
不需要安装或运行 phi-plugin-openclaw，也不会读写它的配置。
