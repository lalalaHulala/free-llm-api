# 接入方式速查

所有主流平台的免费额度都是 **OpenAI 兼容**格式（除 Gemini 原生、Cohere v2、Cloudflare 之外）。
这意味着：只改 `base_url` + `api_key` + `model` 三个值，代码一行不用重写。

三个值从哪来：

```bash
"$PY" "$S" list --provider <slug> --models   # base_url + 免费模型 ID
"$PY" "$S" save --provider <slug> --key ... --model ... --env-file .env
```

---

## 1. Python（openai SDK）

```python
from openai import OpenAI
import os

client = OpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ["OPENAI_BASE_URL"],   # 例：https://api.siliconflow.cn/v1
)

resp = client.chat.completions.create(
    model=os.environ["OPENAI_MODEL"],          # 例：Qwen/Qwen3-8B
    messages=[{"role": "user", "content": "你好"}],
)
print(resp.choices[0].message.content)
```

## 2. Node / TypeScript

```ts
import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
  baseURL: process.env.OPENAI_BASE_URL,
});

const r = await client.chat.completions.create({
  model: process.env.OPENAI_MODEL!,
  messages: [{ role: "user", content: "你好" }],
});
console.log(r.choices[0].message.content);
```

## 3. .env 模板

```dotenv
# 主力：国内直连
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
OPENAI_MODEL=glm-4-flash

# 备份（可选）
BACKUP_API_KEY=sk-yyy
BACKUP_BASE_URL=https://api.siliconflow.cn/v1
BACKUP_MODEL=Qwen/Qwen3-8B
```

`.env` 必须进 `.gitignore`。第一行就写。

## 4. curl 冒烟测试

```bash
curl -sS "$OPENAI_BASE_URL/chat/completions" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"'"$OPENAI_MODEL"'","messages":[{"role":"user","content":"ping"}]}' \
  | head -c 400
```

## 5. 各家 CLI / 客户端

| 工具 | 怎么配 | 注意 |
|---|---|---|
| **Codex CLI** | `OPENAI_BASE_URL` + `OPENAI_API_KEY` 环境变量 | 直接吃 OpenAI 兼容端点 |
| **Aider** | `aider --openai-api-base <url> --openai-api-key <key> --model openai/<model>` | 模型名要加 `openai/` 前缀 |
| **Cline / Roo Code** | 设置里选 "OpenAI Compatible"，填 Base URL + Key + Model ID | 支持自定义 |
| **Cherry Studio / LobeChat** | 添加自定义提供商，填 Base URL + Key | 图形界面，最简单 |
| **Open WebUI** | 设置 → 连接 → OpenAI API，改 Base URL + Key | 多模型可共存 |
| **Claude Code** | ❌ 原生不支持。它只吃 Anthropic 格式 | 必须加中间层，见下 |

### Claude Code 接免费模型（需要转换层）

Claude Code 用的是 Anthropic Messages API 格式，OpenAI 兼容端点不能直连。两条路：

1. **claude-code-router**（`github.com/musistudio/claude-code-router`）—— 专门做这件事，把 Anthropic 请求转成 OpenAI 格式，支持多 provider 路由和 fallback。
2. **LiteLLM proxy** —— 起一个本地代理，`litellm --model openai/glm-4.7 --api_base ...`，然后 `ANTHROPIC_BASE_URL` 指向它（需要 LiteLLM 的 anthropic 兼容模式）。

先问用户是不是真需要：Claude Code 换免费模型通常换来更差的 agent 表现，不比省下的钱值。

## 6. WorkBuddy 里批量跑（agent 自用）

不需要任何配置。agent 直接调：

```bash
"$PY" "$S" chat --provider z-ai-zhipu-ai "把这句话翻成英文：..." --usage
```

适合：批量文本分类、抽取、翻译、摘要——几百条以内用免费模型跑完，不占主模型额度。
超过并发限制会 429，串行跑或加 `sleep`。

## 7. fallback 链（生产必备）

```python
import os, time
from openai import OpenAI, APIStatusError, APIConnectionError

PROVIDERS = [
    {"name": "zhipu",  "base": os.getenv("OPENAI_BASE_URL"),
     "key": os.getenv("OPENAI_API_KEY"),      "model": os.getenv("OPENAI_MODEL")},
    {"name": "silicon","base": os.getenv("BACKUP_BASE_URL"),
     "key": os.getenv("BACKUP_API_KEY"),      "model": os.getenv("BACKUP_MODEL")},
]

def ask(prompt: str, retries_per_provider: int = 1) -> str:
    last_err = None
    for p in PROVIDERS:
        if not (p["base"] and p["key"]):
            continue
        client = OpenAI(api_key=p["key"], base_url=p["base"], timeout=60)
        for _ in range(retries_per_provider):
            try:
                r = client.chat.completions.create(
                    model=p["model"],
                    messages=[{"role": "user", "content": prompt}],
                )
                return r.choices[0].message.content
            except (APIStatusError, APIConnectionError) as e:
                last_err = e
                code = getattr(e, "status_code", None)
                if code in (401, 403):      # key 废了，换下一家
                    break
                if code == 429:             # 限流，等一下重试
                    time.sleep(2)
                    continue
                break
    raise RuntimeError(f"所有免费 provider 都失败: {last_err}")
```

判断逻辑：`401/403` 立刻换家，`429` 退避重试，`5xx` 换家。

## 8. LangChain / LlamaIndex

```python
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model=os.environ["OPENAI_MODEL"],
                 base_url=os.environ["OPENAI_BASE_URL"],
                 api_key=os.environ["OPENAI_API_KEY"])
```

框架层不用关心是哪家，只要 OpenAI 兼容。
