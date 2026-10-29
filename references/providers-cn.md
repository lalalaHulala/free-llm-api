# 国内免费额度平台（freellm.net 未收录的部分）

freellm.net 的目录偏海外。下面这些是**中国大陆可直接访问、支付宝/微信付款、不需要梯子**的平台，
线上目录（`freellm.py list`）查不到，靠这份文档补。

> 数据核对时间 **2026-10**，来源：各平台控制台活动页 + 阿里云开发者社区官方文章。
> 额度天天变，**注册页显示的才是准的**——把这句话一起告诉用户。

## 优先级排序

### 1. 智谱 GLM —— 长期兜底首选

| 项 | 值 |
|---|---|
| 入口 | https://open.bigmodel.cn |
| API Key 页 | https://open.bigmodel.cn/usercenter/apikeys |
| Base URL | `https://open.bigmodel.cn/api/paas/v4`（OpenAI 兼容） |
| 新用户额度 | 2000 万 tokens，永久有效（**未实名/老账号可能不到账**） |
| 长期免费模型 | **`glm-4-flash`、`glm-4.5-flash`**（2026-10-29 实测可调） |
| 门槛 | 中国手机号验证，不绑卡 |
| 坑 | 免费档并发极低，跑批量要串行 |

**必须知道的实测结论（2026-10-29）：**

freellm.net 把 `glm-4.7`、`glm-4.6`、`glm-4.5`、`glm-4.5-air` 都标成免费，**实测全部返回 `1113 余额不足或无可用资源包`**。
同一个 key 下，只有 `glm-4-flash`（871ms）和 `glm-4.5-flash`（约 29 秒，思考模型）能真正调通。

所以别信目录的免费标注，直接扫：

```bash
freellm.py scan --provider z-ai-zhipu-ai \
  --models "glm-4-flash,glm-4.5-flash,glm-4.6,glm-4.7"
```

`1113` 不是限流、不是 key 失效，是**账号没有该模型的额度**。看到这个码，要么换成 `glm-4-flash`，要么去控制台充值/领资源包，别浪费时间重生成 key。

key 格式也要注意：现在有效的是 `32位hex.密钥串`（带一个点），纯 32 位 hex 的老 key 会直接 401。

### 2. 硅基流动 SiliconFlow —— 国内低延迟

| 项 | 值 |
|---|---|
| 入口 | https://cloud.siliconflow.cn |
| API Key 页 | https://cloud.siliconflow.cn/account/ak |
| Base URL | `https://api.siliconflow.cn/v1` |
| 新用户额度 | 约 2000 万 tokens（≈14 元） |
| 长期免费 | 9B 参数以下的模型 |
| 门槛 | 手机号注册；**调用前需完成实名认证** |
| 坑 | 页面展示的模型名可能是 slug 化的，真实 ID 以 `GET /models` 为准 |

**2026-10-29 实测（新账号，实名后）6/6 可用：**

| 模型 | 延迟 | 备注 |
|---|---|---|
| `THUDM/GLM-4-9B-0414` | ~0.8s | 最快，适合高频短任务 |
| `tencent/Hunyuan-MT-7B` | ~0.5s | 翻译专用 |
| `Qwen/Qwen2.5-7B-Instruct` | ~1–2s | 通用首选，设成默认 |
| `Qwen/Qwen3.5-4B` | ~7s | 小模型但偏慢 |
| `deepseek-ai/DeepSeek-R1-0528-Qwen3-8B` | ~10s | 推理模型，慢 |
| `Qwen/Qwen3-8B` | ~13s | **思考模型，先吐几百 token 的 reasoning，别当默认** |

这家是目前最省心的一家：额度真实到账、模型全可用、不用人脸。要"能立刻跑起来"就选它。

### 3. 阿里云百炼 —— 模型最全，且能出图出视频

| 项 | 值 |
|---|---|
| 入口 | https://bailian.console.aliyun.com |
| Base URL（原生协议） | `https://dashscope.aliyuncs.com` → `/api/v1/services/aigc/text-generation/generation` |
| Base URL（兼容模式） | `https://dashscope.aliyuncs.com/compatible-mode/v1`（**workspace key 会 403**） |
| 新用户额度 | 226 个模型有免费额度，文本每模型 100 万 tokens，图像/视频按次 |
| 门槛 | 阿里云账号 + 实名 |
| 坑 | 只有华北2（北京）地域有免费额度 |

**最重要的坑：同一个 key、同一个模型，换端点结果相反（2026-10-29 实测）**

| 端点 | qwen-max 结果 |
|---|---|
| `/compatible-mode/v1/chat/completions` | ❌ 403 `AccessDenied.Unpurchased` |
| `/api/v1/services/aigc/text-generation/generation` | ✅ 200 |

`sk-ws-` 开头的是 workspace key，它在 OpenAI 兼容端点上没有模型授权，但原生协议可以。
看到 `Unpurchased` 先换协议（`freellm.py save ... --transport dashscope`），不要重生成 key，更不要让人去实名。

**实测可用的免费模型：**

| 类型 | 模型 | 延迟 | 额度 |
|---|---|---|---|
| 文本 | `qwen-max` | 514ms | 100 万 |
| 文本 | `qwen-mt-flash` | 312ms | 100 万（翻译专用） |
| 文本 | `glm-5` | 3s | 100 万 |
| 文本 | `qwen3.7-max` | 4s | 100 万 |
| 图像 | `qwen-image-2.0` | ~60s | 100 次 |
| 图像 | `wanx-v1` / `wanx2.0-t2i-turbo` | — | 500 次 |
| 视频 | `wanx2.1-t2v-turbo` | — | 200 次 |
| 视频 | `wan2.6-t2v` | — | 50 次 |
| 视频 | `happyhorse-1.1-i2v` | — | 10 次 |

`qwen3.7-plus` / `qwen3.6-flash` / `qwen3.8-*` 在原生协议下报 `400 url error`（协议不匹配，非权限），
要调它们得走兼容模式或 `bl` CLI。

**`qwen-image-3.0`（CLI 默认模型）不在免费额度内**，生图必须显式 `--model qwen-image-2.0`。
查额度用 `bl usage free`，这比从错误码反推靠谱得多。

### 4. 火山方舟（豆包）—— 唯一每日真实刷新的

| 项 | 值 |
|---|---|
| 入口 | https://console.volcengine.com/ark |
| Base URL | `https://ark.cn-beijing.volces.com/api/v3` |
| 新用户额度 | **每天 200 万 tokens，每天重置**（另每模型 50 万一次性） |
| 门槛 | 实名认证 |
| 坑 | **必须在控制台手动"开通"对应模型**，不开通连 key 都调不动——这是最高频的踩坑点 |

按天刷新的额度对长期跑的任务最有价值，用不完也不累积，别囤。

### 5. 百度千帆

| 项 | 值 |
|---|---|
| 入口 | https://console.bce.baidu.com/qianfan |
| Base URL | `https://qianfan.baidubce.com/v2` |
| 额度 | 每模型 100 万 tokens / 3 个月；`ERNIE-Speed` 等轻量模型长期免费 |
| 门槛 | 百度账号 + 实名 |

### 6. Moonshot Kimi —— 长上下文

| 项 | 值 |
|---|---|
| 入口 | https://platform.moonshot.cn |
| Base URL | `https://api.moonshot.cn/v1` |
| 额度 | 新用户约 800 万 tokens |
| 适用 | 256K 上下文，整本书/长合同/会议记录 |

### 7. 其他可顺带注册的

| 平台 | 入口 | 额度 |
|---|---|---|
| 魔搭 ModelScope | https://modelscope.cn/my/myaccesstoken | 每日 2000 次调用（单模型约 500），阿里系开源模型 |
| 腾讯混元 | https://cloud.tencent.com/product/hunyuan | 100 万 tokens + 100 万 embedding，1 年；混元 Lite 长期免费 |
| 讯飞星火 | https://xinghuo.xfyun.cn | Spark Lite 永久免费 API |
| 商汤 SenseNova | https://platform.sensenova.cn | 长期免费公测，每 5 小时刷新配额 |
| MiniMax | https://platform.minimaxi.com | 新用户代金券 |

## 组合建议

**日常主力（0 成本长期跑）**：智谱 `glm-4-flash`（永久免费）+ 火山方舟豆包（每天 200 万）→ 一个兜底一个高频，覆盖 95% 场景。

**做产品原型**：百炼（模型最全，一次对齐多家评测）+ 硅基流动（国内延迟最低）。

**长文档处理**：Kimi（256K 上下文）+ 智谱（200K，免费）。

**批量数据处理**：火山（每日刷新，不怕烧）→ 智谱（永久免费兜底）。

## 持续跟踪源

免费额度是动态的，隔一阵就得重新核对：

- **freellm.net**——每日验活，`freellm.py refresh` 的数据源，海外平台为主
- **github.com/cheahjs/free-llm-api-resources**——社区维护的清单，按 provider 分组
- **github.com/open-free-llm-api/awesome-freellm-apis**——带一键配置片段（Claude Code / Cursor / Codex）
- **allagent.wiki/blog**——每日速递国内限免活动，国内平台变动看这里最快

用户问"还有没有别家"时，先 `refresh`，再去这几个源查增量，别凭印象答。
