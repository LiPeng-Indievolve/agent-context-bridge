# Agent Context Bridge

[English](README.md) | **简体中文**

在 **Claude Code 与 Codex** 之间迁移工作会话。扫描本地项目，选择要迁移的对话，用精简工作上下文继续任务，完整历史留在本地按需检索。

**v0.3 alpha · macOS/Linux · Python 3.11+ · 无 Python 运行时依赖**

## 能做什么

- 扫描两端历史记录，以及指定的工作空间目录。
- 按单个对话、整个项目或全部匹配记录迁移。
- 支持双向转换；CC → Codex 默认使用不超过 48KB 的工作交接上下文。
- 完整源历史和项目记忆保留在本地，需要时再检索。
- 先预览，再迁移；实际验证模型能续接后，才归档对应的旧入口。
- 不改写已有源会话，提供迁移记录与回滚能力。

## 快速开始

迁入 Codex 前需安装 [Codex CLI](https://github.com/openai/codex)。实际模型验收和继续工作还需完成登录。

```sh
git clone https://github.com/LiPeng-Indievolve/agent-context-bridge.git
cd agent-context-bridge
python3 -m bridge serve
```

打开终端打印的本地网址，按 **扫描 → 选择 → 预览 → 迁移** 操作。

额外扫描工作空间：`python3 -m bridge --root /你的工作空间 serve`。

## 真正切换到新会话

**先在旧窗口输入 `/exit`。** 导入成功不会让已经打开的终端自动切换到新对话。

```sh
python3 -m bridge scan
python3 -m bridge migrate --to codex --id SESSION_ID --apply
python3 -m bridge verify MIGRATION_ID                 # 实际调用模型，消耗额度
python3 -m bridge finish-switch MIGRATION_ID          # 预览旧入口
python3 -m bridge finish-switch MIGRATION_ID --apply  # 归档已确认更早的对应入口
```

检查验收回答，再在新的命令行中运行结果里的 **`resume_command`**。迁移和完成切换不加 `--apply` 时都只预览；网页提供同样的操作。

若旧入口仍被占用，先 `/exit` 退出对应终端再重试。工具不会杀进程、删除写入锁或删除旧会话。

## 使用边界

- **目前是 alpha：** Codex → Claude 已支持原生会话文件转换，但尚未验证 Claude 模型实际续接。
- 图片、私有推理、执行状态和分支状态无法无损重放；不会安装 MCP、hooks、插件或凭据。
- `verify` 使用隔离的 OpenAI 配置，禁用可执行工具和 hooks，只检查会话能否续接，不代表业务工具、设备或生产环境已验收。
- 转换在本地完成；模型验收和继续工作会使用模型服务及其额度。旧历史可能含敏感信息，分享前请检查。
- 工具和状态目录应放在本机磁盘。默认状态目录：`~/.local/share/agent-context-bridge`。

[详细用法与恢复说明（英文）](docs/USAGE.md) · [验收范围（英文）](docs/VERIFICATION.md) · [版本下载](https://github.com/LiPeng-Indievolve/agent-context-bridge/releases)

## 开发与贡献

```sh
python3 -m unittest discover -s tests -v
```

欢迎贡献代码。请使用合成测试数据，不要提交真实对话或凭据。

[MIT 开源协议](LICENSE)
