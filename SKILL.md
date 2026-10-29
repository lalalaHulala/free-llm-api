---
name: free-llm-api
description: 引导用户注册并领取各平台免费大模型 API 额度，校验 key 是否可用，并把 key 接入到用户的程序或 agent 工作流。当用户提到「免费 API」「白嫖 token」「薅大模型羊毛」「领免费额度」「免费的大模型 key」「没有 API key 怎么办」「Gemini / Groq / OpenRouter / 智谱 / 硅基流动 免费额度」「国产免费模型接入」时使用。内置 31 家 provider 的实时目录（每日验活，含 Base URL、限额、免费模型 ID、是否要信用卡/手机验证）、key 探活、key 安全保存，以及直接用免费模型跑对话的命令行工具。
agent_created: true
---

# 免费 LLM API 领取与接入（free-llm-api）

把「想用大模型但不想付钱」变成「10 分钟内拿到能跑通的 key」。

## 五条铁律

1. **不凭记忆报额度、报模型名。** 免费清单每月都在缩水（Groq 的 `llama-3.3-70b` 曾是免费主力，2026-10 已不在免费名单，只剩 whisper / allam / prompt-guard）。先跑 `list`，用实时数据说话。
2. **注册必须用户本人在场。** 邮箱验证码、短信验证、Google/GitHub OAuth 都无法代劳。agent 的职责是把路径压到最短：给直达链接 + 说清要填什么 + 提前告知坑，然后等用户回贴 key。
3. **key 只进 `~/.workbuddy/secrets/`。** 绝不写进代码、`.env.example`、README 或任何会进 git 的文件。
4. **目录标的「免费模型」不等于「这个账号能调的模型」。** freellm 上智谱 `glm-4.7` 标着免费，实测返回 `1113 余额不足`；
   真正能调的是 `glm-4-flash`。拿到 key 后先跑 `scan`，用真实结果定默认模型。
5. **阿里云 workspace key（`sk-ws-` 开头）必须走原生协议。** 同一个 key、同一个 `qwen-max`：
   `/compatible-mode/v1/chat/completions` → `403 AccessDenied.Unpurchased`，
   `/api/v1/services/aigc/text-generation/generation` → `200`。
   看到 Unpurchased 先换协议（`--transport dashscope`），别急着重生成 key、更别让用户去实名。

## 工具

脚本 `scripts/freellm.py`，纯标准库，不用 pip install：

```bash
PY=python   # 任意 Python ≥ 3.9，纯标准库，不用 pip install
S=~/.workbuddy/skills/free-llm-api/scripts/freellm.py   # 按你的安装路径调整
```

| 子命令 | 用途 |
|---|---|
| `refresh` | 抓 freellm.net 的 31 家 provider，重建本地目录缓存（约 15 秒，260+ 免费模型） |
| `list --cn --models` | 中国大陆可直连的平台 + 其免费模型 ID |
| `list --no-card --no-phone` | 只要不绑卡、不验手机的 |
| `verify --provider X --key ...` | 探活：`GET /models` + 真实 chat 双检，分辨 401/403/429/无额度 |
| `scan --provider X --models a,b,c` | **逐个试模型，找出这个账号真能调的**，并把结果写回 secrets 当默认模型 |
| `save --provider X --key ... --model M --transport dashscope --env-file .env` | 存入 secrets，可顺带写 `.env`；阿里 key 必须带 `--transport dashscope` |
| `chat --provider X "提示词"` | 用免费模型直接跑一次对话（agent 自用，省主模型额度） |
| `status` | 一次看所有已存 key 的存活状态 |

目录缓存 `~/.workbuddy/cache/freellm-catalog.json`，超过 7 天先 `refresh`。

### 免 key 的应急通路

`pollinations` 是内置的匿名 OpenAI 兼容端点（`https://text.pollinations.ai/openai`，模型 `openai`），
不需要注册、不需要 key，实测 2026-10-29 可用。用途只有一个：**用户还没注册任何平台时，先证明链路能跑通**。

```bash
"$PY" "$S" chat --provider pollinations "说一句话证明你在工作"
```

它慢（单次 10 秒以上）、能力弱、有限流，**绝不能当主力**。跑通一次建立信心后立刻转到正式平台。

## 标准流程

### Phase 1 · 摸清用途（只问一句）

不同用途对应完全不同的选型，一句话问清，别问第二遍：

- **写进自己的程序/产品** → 要稳定 + 高额度，优先国内直连（延迟低、支付宝充值、不过墙）
- **给 agent / 批量文本处理用** → 要便宜耐造，多注册几家做 fallback
- **只想试试大模型能力** → 挑不绑卡不验手机的，5 分钟拿 key

### Phase 2 · 选平台，给最短注册路径

**默认按「到账额度」从多到少推进，一家一家来，不要一次弹 4 个页面。**

| # | 平台 | 额度 | 有效期 | 门槛 | 备注 |
|---|---|---|---|---|---|
| 1 | 阿里云百炼 | 每模型 100 万，合计 **7000 万+** | 90 天 | 阿里云账号 + 实名 | 只在华北2（北京）地域生效 |
| 2 | 智谱 GLM | **2000 万** | 永久 | 手机号 | 另有 `glm-4.7` 永久免费模型，长期兜底首选 |
| 3 | 硅基流动 | **2000 万**（≈14 元） | 永久 | 实名 | 9B 以下模型长期免费 |
| 4 | 火山方舟 | 200 万 / **每天刷新** | 每日 | 实名 | 长期累计最大，但必须手动开通模型 |
| 5 | Kimi | 约 800 万 | 新用户 | 手机号 | 256K 上下文 |
| 6 | 百度千帆 | 每模型 100 万 | 3 个月 | 实名 | `ERNIE-Speed` 长期免费 |
| 7 | 魔搭 ModelScope | 2000 次 / 天 | 每日 | 手机号 | 模型最多 |

排序依据是**一次性到账额度**。如果用户明确要「长期免费、不想反复注册」，直接跳到 #2 智谱（额度少但永久 + 有永久免费模型）；
如果用户要「跑批量、量越大越好」，优先 #4 火山（每天刷新，用不完不累积）。
海外平台（Google AI Studio / Groq / OpenRouter）额度更慷慨，但需要梯子，用户明确说能翻墙时再推。

选定后**先跑 `list --provider <slug> --models`**，把当前真实可用的模型 ID 抄给用户，别让他猜。

### Phase 2.5 · 直接开页面，不要给清单（硬要求）

**绝不输出「第一步打开…第二步点击…」这种步骤清单。** 用户要的是页面自己弹出来，不是读文档。

执行流程：

1. `mcp__browser__browsers_list` 取当前可用浏览器。默认用内置 `WorkBuddy Browser`（`type: desktop`）；
   需要借用户的 Google/微信登录态时才用扩展浏览器（Edge / Chrome）。
2. `mcp__browser__tabs_new` 直接打开该平台的注册页或控制台页。一次只开一家，别一次弹 4 个页面。
3. `mcp__browser__dom_cua_get_visible_dom` 读页面，判断当前落在哪一步：
   登录页 / 实名认证 / 开通协议 / 控制台 / API Key 页。不同落点决定下一步动作。
4. 能代填的就代填（邮箱、手机号、企业名）用 `dom_cua_type`；
   **验证码、扫码登录、人脸实名、短信确认一律停下来交给用户**——这些 agent 不能也不应该代做。
5. 页面停在需要用户动手的位置后，只说**一句话**：「页面已打开，验证码发到 138xxxx 了，填完跟我说一声」。
   不列步骤、不解释界面、不复述页面文字。
6. 用户说「登录好了」之后，**剩下的事全部由 agent 做完，不许再把用户叫回来**：
   关弹窗 → 点「新建 API Key」→ 填名称 → 点「确定」→ 从弹出的 input 里读出 key → 关闭提示 →
   进 Phase 3 校验 → 进 Phase 4 接入。全程不要让用户复制粘贴 key，也不要让他点任何按钮。
7. 拿到 key 立刻进 Phase 3 校验，别攒着。

### 登录之后的标准操作序列（智谱实测，其他平台同理）

```
tabs_new  →  https://bigmodel.cn/usercenter/proj-mgmt/apikeys
dom 读    →  找到 aria-label="Close" 的按钮，点掉邀请弹窗
dom 读    →  点「新建API Key」
dom 读    →  点 input[placeholder="请输入API key名称"]，dom_cua_type 填个名字（如 workbuddy-free）
dom 读    →  点「确定」
dom 读    →  key 就在 input 的 value 里，形如 32位hex.密钥串，直接读出来
dom 读    →  点「我已妥善保存」收尾
```

要点：
- 智谱 API Key 页是 `bigmodel.cn/usercenter/proj-mgmt/apikeys`，**不是** `open.bigmodel.cn/usercenter/apikeys`（后者 404）
- 一进来会有邀请弹窗盖住按钮，必须先 `aria-label="Close"` 点掉，否则点不到「新建」
- 名称填完「确定」才会从 disabled 变可点，填之前点没反应
- key 只在创建弹窗里显示一次，读不到就白建了，读完再关

页面打不开、被墙、或平台要求必须下载 App 的，退回给直达链接并说明原因，不要硬撑。
浏览器工具报 `stale_tab` / `extension_disconnected` 时，从 `browsers_list` 重新开始，不复用旧标识。

### 浏览器能力：两个坑，别误判成"工具坏了"

**坑 1：DOM 读出来是空的，不等于读不到。**

`dom_cua_get_visible_dom` 在页面还没渲染完时返回 `snapshot: ""`。第一次踩到时很容易误判成「内置浏览器不支持 DOM」，
于是退化成让用户自己点——这是错的。正确做法：**读空就再读一次，最多 3 次**，SPA 页面首次加载通常要 1–3 秒。
2026-10-29 实测：智谱控制台第一次读是空，第二次读出了完整的 12 个节点，之后按钮、input、弹窗全都能点。

**坑 2：`tab_screenshot` 会报「超过 10 MiB」，但 `cua_execute` 里的 screenshot 动作正常。**

大屏/高分屏下整页截图会超限。要看画面就用：

```json
{"type":"screenshot","clip":{"x":0,"y":0,"width":1000,"height":800},"format":"jpeg","quality":45}
```

放进 `cua_execute` 的 `actions` 数组里执行，能正常出图。DOM 能用时优先 DOM，截图只用于确认页面状态。

**坑 3：扩展浏览器要用户先开着窗口。** `browsers_list` 里有 Edge/Chrome 不代表能用，
`tabs_new` 会直接回 `No current window`。这种情况下用内置 `WorkBuddy Browser`，别要求用户去装扩展或开窗口——
用户的目标是"注册完就不管了"，不是配合调试。

**坑 4：阿里云控制台这类重页面，DOM 和 CDP 都会失效。** 实测 `bailian.console.aliyun.com`：
DOM 快照持续为空（重试 3 次无效）、`cua_execute` 的 click 报 `CDP Input.dispatchMouseEvent timed out`、
screenshot 报超 10 MiB 或 provider timeout。**别在这个页面上硬耗**，换成 API 层验证（直接 curl 打接口）比操作界面快得多。
只有智谱这类轻页面能稳定跑全自动。

**坑 5：`tabs_new` 返回 `selected: false` 时，DOM 和截图都拿不到。** 说明前台被别的 tab 占着。
先用 `user_open_tabs` 看用户在开什么，对目标页 `tabs_claim` 拿控制权，或 `tab_focus` 后再操作。
用户手动开着的页面（`state: observed`）在 claim 之前完全不可操作。

把坑提前说：智谱要中国手机号、Gemini 要梯子且免费版数据参与训练、NVIDIA NIM 要手机验证、Cerebras 现在只送 30 天 $5 试用且要绑卡。

**用户想要 agent 代填注册表单时**：可以用浏览器控制打开注册页、填邮箱、点「发送验证码」，
然后**停下来**把验证码交给用户——短信/邮箱验证码这一步 agent 不能也不应该代收。
注册完成后再接管：建 key、复制、校验。别承诺"全自动注册"，做不到。

### Phase 3 · 校验（拿到 key 的第一件事）

```bash
"$PY" "$S" verify --provider z-ai-zhipu-ai --key "贴进来的key" --model glm-4.7
```

**判定口径：`GET /models` 通过 ≠ 能用。** 必须发一次真实 chat 才算验证通过（阿里百炼的 key 能列出 183 个模型，实际调用全是 403）。

五种结果，对应五种话说：

- `✅ chat 可用 → 'pong'` → 真能用，进 Phase 4
- `❌ key 无效或无权限（/models HTTP 401/403）` → key 复制错了或已失效，让用户回控制台**重新生成**（不是重新复制）。
  **把原始报错贴给用户看**，别翻译成"失败了"
- `❌ key 有效，但 <model> 无权调用（HTTP 403 AccessDenied）` → **key 没问题**，是账号里没开通该模型。
  去控制台「模型广场」开通，或换一个已开通的模型。别说成"key 失效"
- `✅ 限流但 key 有效（429）` → 能用但被限流：额度耗尽 / QPS 配额低 / 并发超限。提醒控并发，并让用户去查免费额度剩余
- `❌ 未开通（ModelNotOpen / has not activated the model）` → **key 没问题，账号没开通这个模型**。
  火山方舟每一家模型都要单独开通（控制台「开通管理」逐个勾选），开通前任何调用都是这个错。
  别说成"key 失效"，也别让人重建 key。
- 网络超时 → 先判断是不是需要梯子（`cn_direct` 为 false 的平台）

遇到 403/429 别只报一个"失败"就结束，要落到具体动作：**重新生成 key**、还是**开通模型**、还是**等额度**。

**单个模型通了还不算完，扫一遍才知道哪批能用：**

```bash
"$PY" "$S" scan --provider z-ai-zhipu-ai --models "glm-4-flash,glm-4.5-flash,glm-4.6,glm-4.7" --workers 2
```

scan 会把可用列表和第一个可用模型写回 secrets 当默认值。不显式给 `--models` 就扫目录里的，
但目录标注不可信（智谱那 4 个标着免费的全是无额度），所以拿到新平台时优先显式指定候选。

通过后立刻保存：

```bash
"$PY" "$S" save --provider z-ai-zhipu-ai --key "..." --model glm-4.7 \
  --base-url "https://open.bigmodel.cn/api/paas/v4" --env-file <项目>/.env
```

### Phase 4 · 接入

按目标选择，片段见 `references/integration.md`：

- **用户自己的程序** → 写 `.env`（`OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL`），代码用 OpenAI SDK 不用改
- **Claude Code / Cline / Aider / Codex** → 改对应 `BASE_URL` + `AUTH_TOKEN` 环境变量
- **Cherry Studio / LobeChat / Open WebUI** → 填 Base URL + key
- **WorkBuddy 里做批量任务** → 用 `chat` 子命令循环调用，不占主模型额度

接入后必须跑一次真实调用，别只交配置：

```bash
"$PY" "$S" chat --provider z-ai-zhipu-ai "用一句话证明你在工作" --usage
```

### Phase 5 · 兜底设计

只注册一家的方案迟早翻车（限流、额度耗尽、模型下线）。给两条建议：

- 至少 2 家：一家国内直连当主力，一家海外当备份
- 程序里做 fallback 链：主 provider 返回 429/5xx 就切下一个，代码见 `references/integration.md`

## 百炼 CLI（图像 / 视频 / 语音，纯文本用不上）

阿里云的图、视频、语音能力不在 OpenAI 兼容体系里，要用 `bl`：

```bash
npm i -g bailian-cli          # 需 Node ≥ 18.17
bl skill init                 # 注册 12 个 bailian-* skills
bl auth login --console       # 浏览器 OAuth，必须用户本人点「确认授权」（唯一不能代劳的一步）
bl usage free                 # 查免费额度余额——能一锤定音解决「到底有没有额度」
bl usage free --all | grep -i image   # 查哪些图像/视频模型在免费额度内
bl quota list                 # 查 QPM/TPM 限流
bl image generate --prompt "..." --model qwen-image-2.0 --size 16:9 --out-dir ./out
```

**默认模型不一定是免费的。** `bl image generate` 默认 `qwen-image-3.0`，而免费额度只覆盖 `qwen-image-2.0`。
动手前先对一遍 `bl usage free`，再显式 `--model`，否则会走付费。

纯文本优先走 `freellm.py chat`（轻、快、不用 OAuth）；要图要视频才用 `bl`。

## 注意事项

- **免费额度不等于能跑生产。** 明确说：免费层用于开发测试和低频任务，别接付费客户。
- **别滥用。** 平台随时可能收紧，注册一堆小号刷额度是自断后路。
- **目录里的 Model ID 不一定等于真实 API 模型名。** 部分平台（硅基流动）页面展示 slug 化名字，实际调用以 `GET /models` 返回为准——`verify` 会打印出来。
- **额度信息会过期。** 交付时把「数据抓取时间」一起告诉用户。
- **国内平台清单**（freellm.net 未收录的火山、百度、Kimi、混元）见 `references/providers-cn.md`。
