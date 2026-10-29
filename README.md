# free-llm-api

一个引导你**注册并领取各平台免费大模型 API 额度**、校验 key 可用性、并一行命令接入程序或 Agent 的技能（Skill）。

不是又一份「免费 API 大全」清单——目录里的免费标注天天过期，这份工具的思路是：**实时抓目录当线索，用真实调用下结论**。

- **31 家 provider 实时目录**（数据源 [freellm.net](https://freellm.net)，每日人工验活），含 Base URL、限额、免费模型 ID、是否要信用卡/手机验证
- **key 探活**：`GET /models` 通过 ≠ 能调用，一律以真实 chat 结果判定
- **scan 子命令**：逐个试模型，找出**你这个账号**真正能调的免费模型
- **纯标准库**：单文件 `freellm.py`，不需要 `pip install` 任何东西

## 快速开始

```bash
# 1. 拉目录（约 15 秒，260+ 免费模型）
python scripts/freellm.py refresh

# 2. 看大陆可直连的平台和当前真实免费模型
python scripts/freellm.py list --cn --models

# 3. 注册后校验 key（去哪注册看下文「平台怎么选」）
python scripts/freellm.py verify --provider z-ai-zhipu-ai --key "你的key" --model glm-4-flash

# 4. 扫出这个账号真正能调的模型，并设为默认
python scripts/freellm.py scan --provider z-ai-zhipu-ai \
  --models "glm-4-flash,glm-4.5-flash,glm-4.6,glm-4.7"

# 5. 直接对话
python scripts/freellm.py chat --provider z-ai-zhipu-ai "你好，证明你在工作" --usage
```

没有注册任何平台？`pollinations` 是内置的免 key 通道，先跑通链路建立信心（慢、弱，仅此用途）：

```bash
python scripts/freellm.py chat --provider pollinations "说一句话证明你在工作"
```

## 命令一览

| 子命令 | 用途 |
|---|---|
| `refresh` | 抓 31 家 provider，重建本地目录缓存 |
| `list [--cn] [--no-card] [--no-phone] [--models]` | 按条件筛平台，可带免费模型 ID |
| `verify --provider X --key ...` | 探活：`/models` + 真实 chat 双检，区分 401 / 403 / 429 / 无额度 / 未开通 |
| `scan --provider X [--models a,b,c]` | **逐个试模型，找出该账号真能调的**，结果写回默认配置 |
| `save --provider X --key ... [--transport dashscope] [--env-file .env]` | 存 key（`~/.workbuddy/secrets/`，权限 600），可顺带写 `.env` |
| `chat --provider X "提示词"` | 用免费模型跑一次对话 |
| `status` | 一次看所有已存 key 的存活状态 |

缓存位于 `~/.workbuddy/cache/freellm-catalog.json`，超过 7 天建议先 `refresh`。

## 平台怎么选（2026-10 实测，额度会过期，注册页显示的才作准）

| # | 平台 | 一次性额度 | 有效期 | 门槛 |
|---|---|---|---|---|
| 1 | 阿里云百炼 | 每模型 100 万 tokens，合计 7000 万+ | 90 天 | 阿里云账号 + 实名 |
| 2 | 智谱 GLM | 2000 万 tokens | 永久 | 中国手机号 |
| 3 | 硅基流动 | 约 2000 万 tokens + 9B 以下永久免费 | 永久 | 手机号 + 实名 |
| 4 | 火山方舟（豆包） | 200 万 / **每天刷新** | 每日 | 实名 |
| 5 | Kimi | 约 800 万 | 新用户 | 手机号 |
| 6 | 百度千帆 | 每模型 100 万 | 3 个月 | 实名 |
| 7 | 魔搭 ModelScope | 2000 次 / 天 | 每日 | 手机号 |

国内平台详见 [references/providers-cn.md](references/providers-cn.md)，接入各端（OpenAI SDK / Claude Code / Cline / Cherry Studio / fallback 链）详见 [references/integration.md](references/integration.md)。

## 用血泪换来的四个结论

这些全是实测踩出来的，也是这个工具存在的原因：

1. **`GET /models` 通过 ≠ 能调用。** 百炼的 key 能列出 183 个模型，实际调用全部 403。判定可用性必须发一次真实 chat。
2. **目录标的「免费模型」≠ 你的账号能调的模型。** freellm.net 把智谱 `glm-4.7` 标成免费，实测 `1113 余额不足`；真正永久免费的是 `glm-4-flash`。所以拿到 key 先 `scan`。
3. **阿里 workspace key（`sk-ws-` 开头）走 OpenAI 兼容端点会假报 `403 Unpurchased`，换原生协议就通。** 同一个 key、同一个 `qwen-max`：兼容模式 403，`/api/v1/services/aigc/text-generation/generation` 200。看到 Unpurchased 先换协议，别重生成 key。
4. **火山方舟每个模型都要在控制台手动「开通」。** key 有效也调不动，报 `ModelNotOpen`，这是设计不是故障。

## 安装为 Skill

**WorkBuddy**：放到 `~/.workbuddy/skills/free-llm-api/`，重启会话即可被自动发现。

**Claude Code**：放到 `~/.claude/skills/free-llm-api/`。SKILL.md 遵循 Anthropic 的 Agent Skills 格式（YAML frontmatter + 正文指令），同样生效。

## 安全约定

- key 只存 `~/.workbuddy/secrets/freellm_keys.json`（权限 600），绝不写进代码或任何会进 git 的文件
- `.env` 永远进 `.gitignore`，`save --env-file` 写的是变量名模板不含真实 key
- 本仓库不包含、也不会包含任何真实 key

## 免责说明

免费额度是平台的营销行为，随时可能收紧或取消。本工具只做目录聚合与调用封装，请遵守各平台服务条款——注册一堆小号刷额度是自断后路。免费层适合开发测试与低频任务，别接生产流量。

## License

MIT
