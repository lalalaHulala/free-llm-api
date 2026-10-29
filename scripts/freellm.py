#!/usr/bin/env python3
"""free-llm-api skill 的核心工具：抓免费 provider 目录 / 校验 key / 保存 key / 直接调模型。

只依赖标准库。数据源 freellm.net（每日自动验活），所以模型 ID 永远是最新的，
不要在别处硬编码模型名。
"""
import argparse
import concurrent.futures as cf
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HOME = Path.home()
SKILL_HOME = HOME / ".workbuddy"
CACHE = SKILL_HOME / "cache" / "freellm-catalog.json"
SECRETS = SKILL_HOME / "secrets" / "freellm_keys.json"
SRC = "https://freellm.net"

# 中国大陆可直连（无需代理）的 provider slug。这是手工领域知识，freellm 不提供。
CN_DIRECT = {
    "z-ai-zhipu-ai",
    "siliconflow",
    "modelscope",
    "alibaba-cloud-model-studio",
    "deepseek",
    "openrouter",  # 可访问但部分地区需代理，标记为 half
}
CN_HALF = {"openrouter"}

# 不需要任何 key 的匿名 OpenAI 兼容端点。用于「用户还没注册任何平台」时先跑通链路，
# 不作为长期方案（有隐藏限流、能力有限）。实测 2026-10-29 可用。
BUILTIN = [{
    "slug": "pollinations",
    "name": "Pollinations (免 key 匿名)",
    "page": "https://pollinations.ai",
    "base_url": "https://text.pollinations.ai/openai",
    "openai_compatible": True,
    "phone_required": False,
    "card_required": False,
    "rate_limit": "匿名档隐藏限流，仅用于验证链路",
    "context_range": "—",
    "updated": "builtin",
    "models": [{"id": "openai", "name": "GPT-OSS 20B (匿名)", "context": "—",
                "status": "online"}],
    "cn_direct": True,
    "cn_half": False,
    "keyless": True,
    "builtin": True,
}, {
    "slug": "volcengine-ark",
    "name": "火山方舟 (豆包)",
    "page": "https://console.volcengine.com/ark/region:ark+cn-beijing/openManagement",
    "base_url": "https://ark.cn-beijing.volces.com/api/v3",
    "openai_compatible": True,
    "phone_required": False,
    "card_required": False,
    "rate_limit": "每模型 50 万 tokens + 每天 200 万；必须先在控制台逐个开通模型",
    "context_range": "—",
    "updated": "builtin",
    "models": [
        {"id": "doubao-seed-2-1-lite-260915", "name": "豆包 Seed 2.1 Lite",
         "context": "—", "status": "online"},
        {"id": "doubao-seed-2-1-pro-260915", "name": "豆包 Seed 2.1 Pro",
         "context": "—", "status": "online"},
        {"id": "deepseek-v4-1-flash-261017", "name": "DeepSeek V4.1 Flash",
         "context": "—", "status": "online"},
        {"id": "glm-5-3-flash-260828", "name": "GLM 5.3 Flash",
         "context": "—", "status": "online"},
    ],
    "cn_direct": True,
    "cn_half": False,
    "builtin": True,
}]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# 429 里混着两种完全不同的情况：真的只是限流（能用），还是账号没额度（不能用）。
# 判定错会让用户以为有 key 就能跑，实际一次都发不出去。
NO_QUOTA_HINTS = ("余额不足", "可用资源包", "insufficient", "arrears", "欠费",
                  "no credit", "quota exhausted", "exceeded your current quota",
                  "accessdenied.unpurchased", "无权调用")


def classify_error(code, body):
    """把 HTTP 错误归成「未开通 / 无额度 / 限流 / 无权限 / 其他」，供话术使用。"""
    low = (body or "").lower()
    if "has not activated the model" in low or "modelnotopen" in low:
        return "未开通"
    if any(k in low for k in NO_QUOTA_HINTS):
        return "无额度"
    if code == 429:
        return "限流"
    if code in (401, 403):
        return "无权限"
    return f"HTTP {code}"


# ---------------------------------------------------------------- 抓取 & 解析

def fetch(url, timeout=30, headers=None):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
        "Accept-Encoding": "identity",
        **(headers or {}),
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        ctype = r.headers.get("Content-Type", "")
    enc = "utf-8"
    m = re.search(r"charset=([\w-]+)", ctype)
    if m:
        enc = m.group(1)
    return raw.decode(enc, "replace")


def to_tokens(page):
    """HTML -> 去标签的文本 token 列表，跳过空串。"""
    page = re.sub(r"<script[\s\S]*?</script>", " ", page)
    page = re.sub(r"<style[\s\S]*?</style>", " ", page)
    out = []
    for part in re.split(r"<[^>]+>", page):
        t = html.unescape(part).replace("\xa0", " ").strip()
        if t:
            out.append(t)
    return out


def after(tokens, label):
    """取 label 之后紧邻的那个 token。"""
    low = label.lower()
    for i, t in enumerate(tokens):
        if t.strip().lower() == low and i + 1 < len(tokens):
            return tokens[i + 1]
    return ""


def pick_base_url(tokens):
    v = after(tokens, "Base URL")
    if v.startswith("http"):
        return v.rstrip("/")
    m = re.search(r"Base URL:\s*(https?://[^\s\"'<>]+)", " ".join(tokens))
    if m:
        return m.group(1).rstrip("/")
    m = re.search(r"https://api[-.][^\s\"'<>,)]+", " ".join(tokens))
    return m.group(0).rstrip("/") if m else ""


HEADER_WORDS = {
    "model id", "developer", "context", "availability", "use cases", "all", "free",
    "trial", "paid", "chat", "vision", "reasoning", "text", "coding", "models",
    "—", "-", "yes", "no", "online", "offline",
}
STATUS_WORDS = ("online", "offline", "limited trial", "preview", "beta",
                "deprecated", "unavailable", "coming soon")
TAG_WORDS = {"chat", "vision", "reasoning", "text", "code", "coding", "embedding",
             "rerank", "image", "audio", "video", "pdf", "function calling",
             "tool use", "json", "streaming"}
HEADER_TAIL = ("availability", "use cases", "context", "developer")
CTX_RE = re.compile(r"^\d+(\.\d+)?[KM]?$|^—$|^-$")
ID_RE = re.compile(r"[A-Za-z0-9._:/+\-]{2,90}")


def parse_models(tokens):
    """从「Model ID」表头之后按行分组还原免费模型表。

    行尾锚点：'Free tier' / 'Limited trial'；表头里也含这两个词，靠前一个 token 区分。
    行内标签（chat/vision/...）在锚点后跳过。比固定偏移抗页面改版。
    """
    start = 0
    for i, t in enumerate(tokens):
        if t.strip().lower() == "model id":
            start = i + 1
            break
    models, seen, buf = [], set(), []
    i = start
    while i < len(tokens):
        cur = tokens[i].strip()
        low = cur.lower()
        if low in ("free tier", "limited trial"):
            prev = buf[-1].lower() if buf else ""
            if prev in HEADER_TAIL:
                buf = []                      # 表头行，丢弃并吞掉其后的列名
                i += 1
                while i < len(tokens) and tokens[i].strip().lower() in (
                        "use cases", "free tier", "trial", "paid", "all"):
                    i += 1
                continue
            elif buf and len(buf) <= 8:
                mid = buf[0]
                if (mid.lower() not in HEADER_WORDS and ID_RE.fullmatch(mid)
                        and any(c.isalpha() for c in mid) and mid not in seen
                        and (any(c in mid for c in "-/:.") or any(c.isdigit() for c in mid))):
                    ctx = next((g for g in buf if CTX_RE.match(g)), "")
                    status = next((g for g in buf if g.lower() in STATUS_WORDS), "")
                    name = ""
                    for g in buf[1:]:
                        if g != ctx and g.lower() not in STATUS_WORDS and len(g) > len(name):
                            name = g
                    seen.add(mid)
                    models.append({"id": mid, "name": name or mid,
                                   "context": ctx, "status": status or "unknown"})
                buf = []
                i += 1
                while i < len(tokens) and tokens[i].strip().lower() in TAG_WORDS:
                    i += 1
                continue
            else:
                buf = []
            i += 1
            continue
        buf.append(cur)
        i += 1
    return models


def parse_provider(slug, page):
    tk = to_tokens(page)
    phone_raw = (after(tk, "Phone Verification") + " " + after(tk, "Phone Required")).lower()
    card_raw = after(tk, "Credit Card").lower()
    return {
        "slug": slug,
        "name": (tk[0].split(" Free ")[0].replace("Free ", "") if tk else slug),
        "page": f"{SRC}/providers/{slug}",
        "base_url": pick_base_url(tk),
        "openai_compatible": after(tk, "OpenAI Compatible").lower().startswith("yes"),
        "phone_required": ("required" in phone_raw and "not required" not in phone_raw) or "yes" in phone_raw,
        "card_required": bool(card_raw) and "not required" not in card_raw and card_raw != "no",
        "rate_limit": after(tk, "Primary Limit"),
        "context_range": after(tk, "Context Range"),
        "updated": after(tk, "Last Updated"),
        "models": parse_models(tk),
        "cn_direct": slug in CN_DIRECT and slug not in CN_HALF,
        "cn_half": slug in CN_HALF,
    }


def cmd_refresh(args):
    listing = fetch(f"{SRC}/providers/")
    slugs = sorted(set(re.findall(r'href="/providers/([a-z0-9\-]+)"', listing)) - {"", None})
    print(f"发现 {len(slugs)} 个 provider，开始抓取…", file=sys.stderr)
    out, fails = [], []

    def one(slug):
        try:
            return parse_provider(slug, fetch(f"{SRC}/providers/{slug}"))
        except Exception as e:  # noqa: BLE001
            fails.append(f"{slug}: {e}")
            return None

    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for rec in ex.map(one, slugs):
            if rec:
                out.append(rec)
    out.sort(key=lambda r: (-len(r["models"]), r["slug"]))
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps({
        "source": SRC,
        "fetched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "providers": out,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    total_m = sum(len(p["models"]) for p in out)
    print(f"✅ 已写入 {CACHE}")
    print(f"   {len(out)} 家 provider / {total_m} 个免费模型 / 失败 {len(fails)}")
    for f in fails:
        print("   ✗ " + f)


def load_catalog(auto_refresh=True):
    if not CACHE.exists() and auto_refresh:
        cmd_refresh(None)
    if not CACHE.exists():
        sys.exit("没有目录缓存，先跑：freellm.py refresh")
    cat = json.loads(CACHE.read_text(encoding="utf-8"))
    have = {p["slug"] for p in cat["providers"]}
    cat["providers"] = [p for p in BUILTIN if p["slug"] not in have] + cat["providers"]
    return cat


# ---------------------------------------------------------------- 目录查询

def cmd_list(args):
    cat = load_catalog()
    rows = cat["providers"]
    if args.cn:
        rows = [p for p in rows if p["cn_direct"] or p["cn_half"]]
    if args.no_card:
        rows = [p for p in rows if not p["card_required"]]
    if args.no_phone:
        rows = [p for p in rows if not p["phone_required"]]
    if args.provider:
        rows = [p for p in rows if p["slug"] == args.provider]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    print(f"数据抓取时间 {cat['fetched_at']}  ·  源 {cat['source']}\n")
    print(f"{'provider':<28}{'模型':>4}  {'国内':<4}{'要卡':<4}{'要手机':<6}限额")
    print("-" * 96)
    for p in rows:
        cn = "直连" if p["cn_direct"] else ("半" if p["cn_half"] else "-")
        print(f"{p['slug']:<28}{len(p['models']):>4}  {cn:<4}"
              f"{'是' if p['card_required'] else '否':<4}"
              f"{'是' if p['phone_required'] else '否':<6}{p['rate_limit'][:34]}")
    if args.models and rows:
        for p in rows:
            print(f"\n▼ {p['slug']}  {p['base_url']}  取 key: {p['page']}")
            for m in p["models"]:
                print(f"   - {m['id']:<52}{m['context']:>8}  {m['name']}")


# ---------------------------------------------------------------- key 管理

def load_keys():
    if SECRETS.exists():
        try:
            return json.loads(SECRETS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


def cmd_save(args):
    keys = load_keys()
    entry = keys.setdefault(args.provider, {})
    entry["key"] = args.key.strip()
    entry["saved_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    if args.model:
        entry["default_model"] = args.model
    if args.base_url:
        entry["base_url"] = args.base_url.rstrip("/")
    if getattr(args, "transport", None):
        entry["transport"] = args.transport
    SECRETS.parent.mkdir(parents=True, exist_ok=True)
    SECRETS.write_text(json.dumps(keys, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        os.chmod(SECRETS, 0o600)
    except OSError:
        pass
    print(f"✅ 已保存 {args.provider} 的 key 到 {SECRETS}")

    if args.env_file:
        p = Path(args.env_file).expanduser()
        base = args.base_url or ""
        line_id = re.sub(r"[^A-Za-z0-9]", "_", args.provider).upper()
        block = (f"# {args.provider}\n"
                 f"{line_id}_API_KEY={args.key.strip()}\n"
                 f"OPENAI_API_KEY={args.key.strip()}\n"
                 f"OPENAI_BASE_URL={base}\n"
                 f"OPENAI_MODEL={args.model or ''}\n")
        old = p.read_text(encoding="utf-8") if p.exists() else ""
        p.write_text((old + ("\n" if old else "") + block), encoding="utf-8")
        print(f"✅ 已追加写入 {p}")


def call_text(base, key, model, prompt, transport="openai", max_tokens=None,
              temperature=0.3, timeout=180):
    """调一次文本模型，返回 (text, usage)。

    transport="dashscope" 走阿里云原生协议 /api/v1/services/aigc/text-generation/generation。
    这不是可有可无的选项：阿里 workspace key（sk-ws- 开头）在 OpenAI 兼容端点上会报
    403 AccessDenied.Unpurchased，但同一个 key、同一个模型走原生协议就是 200。
    实测 qwen-max：compatible-mode/v1 → 403，api/v1 → 200。
    """
    base = base.rstrip("/")
    if transport == "dashscope":
        url = f"{base}/api/v1/services/aigc/text-generation/generation"
        params = {"result_format": "message", "temperature": temperature}
        if max_tokens:
            params["max_tokens"] = max_tokens
        payload = {"model": model,
                   "input": {"messages": [{"role": "user", "content": prompt}]},
                   "parameters": params}
    else:
        url = f"{base}/chat/completions"
        payload = {"model": model, "temperature": temperature, "stream": False,
                   "messages": [{"role": "user", "content": prompt}]}
        if max_tokens:
            payload["max_tokens"] = max_tokens

    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8", "replace"))

    if transport == "dashscope":
        out = data.get("output", {}) or {}
        choices = out.get("choices") or []
        text = choices[0].get("message", {}).get("content", "") if choices else ""
        return (text or out.get("text", "")), (data.get("usage") or {})
    msg = (data.get("choices") or [{}])[0].get("message", {}) or {}
    return (msg.get("content") or msg.get("reasoning_content") or ""), (data.get("usage") or {})


def _probe(base, key, model, transport="openai"):
    """返回 (ok, detail, models)。

    /models 只能证明 key 有效，证明不了有模型权限——阿里百炼就是典型：
    key 能列出 183 个模型，实际调用全是 403 AccessDenied.Unpurchased。
    所以只要给了 model，最终判定以 chat 的真实结果为准。
    """
    hdr = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    base = base.rstrip("/")
    ids, models_ok, prefix = [], False, ""
    try:
        req = urllib.request.Request(f"{base}/models", headers={**hdr, "User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        ids = [m.get("id") for m in data.get("data", []) if isinstance(m, dict)]
        models_ok = True
    except urllib.error.HTTPError as e:
        code, body = e.code, e.read()[:300].decode("utf-8", "replace")
        if code in (401, 403):
            return False, f"key 无效或无权限（/models HTTP {code}）: {body}", []
        if code == 429:
            return True, "限流，key 本身有效（HTTP 429）", []
        prefix = f"/models HTTP {code}；"
    except Exception as e:  # noqa: BLE001
        prefix = f"/models 失败({e})；"

    if not model:
        if models_ok:
            return True, f"可见 {len(ids)} 个模型（未验证调用权限，建议指定 --model 复测）", ids
        return False, prefix + "未提供 model，无法继续探测", []

    try:
        msg, usage = call_text(base, key, model, "ping, reply with: pong",
                               transport=transport, max_tokens=16, timeout=60)
        note = f"（/models 见 {len(ids)} 个）" if ids else ""
        return True, f"chat 可用（{model}）→ {msg[:40]!r} usage={usage}{note}", ids or [model]
    except urllib.error.HTTPError as e:
        body = e.read()[:400].decode("utf-8", "replace")
        kind = classify_error(e.code, body)
        if kind == "无额度":
            return False, f"key 有效，但账号无额度/余额不足（{model}）: {body[:180]}", ids
        if kind == "限流":
            return True, f"限流但 key 有效（{model}）: {body[:100]}", ids
        if kind == "无权限" and models_ok:
            return False, f"key 有效，但 {model} 无权调用（HTTP {e.code}）: {body}", ids
        return False, f"chat {kind}: {body}", ids
    except Exception as e:  # noqa: BLE001
        return False, f"chat 失败: {e}", ids


def _pick_model(p, override):
    if override:
        return override
    keys = load_keys()
    dm = keys.get(p["slug"], {}).get("default_model")
    if dm:
        return dm
    return p["models"][0]["id"] if p["models"] else ""


def cmd_verify(args):
    cat = load_catalog()
    by_slug = {p["slug"]: p for p in cat["providers"]}
    jobs = []
    if args.all:
        for slug, rec in load_keys().items():
            if rec.get("key") and slug in by_slug:
                jobs.append((by_slug[slug], rec["key"], rec.get("default_model")))
    else:
        if args.provider not in by_slug:
            sys.exit(f"未知 provider: {args.provider}（先跑 list 看可用值）")
        key = args.key or load_keys().get(args.provider, {}).get("key")
        if not key:
            if by_slug[args.provider].get("keyless"):
                key = "no-key-needed"
            else:
                sys.exit("没有 key，用 --key 传入或先跑 save")
        jobs.append((by_slug[args.provider], key, args.model))

    if not jobs:
        sys.exit("没有已保存的 key 可校验，先跑 save")

    fail = 0
    for p, key, model in jobs:
        m = _pick_model(p, model)
        base = (getattr(args, "base_url", None)
                or load_keys().get(p["slug"], {}).get("base_url")
                or p["base_url"])
        tp = load_keys().get(p["slug"], {}).get("transport") or "openai"
        t0 = time.time()
        ok, detail, ids = _probe(base, key, m, transport=tp)
        dt = int((time.time() - t0) * 1000)
        print(f"{'✅' if ok else '❌'} {p['slug']:<28}{base}")
        print(f"   {detail}   [{dt}ms]")
        if ids:
            print(f"   可见模型: {', '.join(ids[:8])}{' …' if len(ids) > 8 else ''}")
        if not ok:
            fail += 1
    sys.exit(1 if fail else 0)


def cmd_chat(args):
    cat = load_catalog()
    by_slug = {p["slug"]: p for p in cat["providers"]}
    p = by_slug.get(args.provider)
    if not p:
        sys.exit(f"未知 provider: {args.provider}")
    key = args.key or load_keys().get(args.provider, {}).get("key")
    if not key:
        if p.get("keyless"):
            key = "no-key-needed"
        else:
            sys.exit(f"{args.provider} 没有 key，先用 save 保存")
    model = _pick_model(p, args.model)
    if not model:
        sys.exit("没有可用模型，用 --model 指定")
    store = load_keys().get(args.provider, {})
    base = getattr(args, "base_url", None) or store.get("base_url") or p["base_url"]
    transport = getattr(args, "transport", None) or store.get("transport") or "openai"
    prompt = args.prompt
    if prompt == "-":
        prompt = sys.stdin.read()
    t0 = time.time()
    try:
        text, u = call_text(base, key, model, prompt, transport=transport,
                            max_tokens=args.max_tokens or None,
                            temperature=args.temperature)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read()[:500].decode('utf-8', 'replace')}")
    if args.json:
        print(json.dumps({"text": text, "usage": u}, ensure_ascii=False, indent=2))
        return
    print(text)
    if args.usage:
        print(f"\n[{p['slug']}/{model} · {transport} · {int((time.time()-t0)*1000)}ms · "
              f"in={u.get('prompt_tokens') or u.get('input_tokens')} "
              f"out={u.get('completion_tokens') or u.get('output_tokens')}]", file=sys.stderr)


def cmd_scan(args):
    """逐个试目录里的模型，找出真正能调用的那些。

    必要环节：目录标的「免费模型」经常不等于「这个账号能免费调的模型」。
    实测智谱 glm-4.7 在 freellm 上标着免费，真实返回 1113 余额不足；
    真正免费的是 glm-4-flash / glm-4.5-flash。
    """
    cat = load_catalog()
    by_slug = {p["slug"]: p for p in cat["providers"]}
    p = by_slug.get(args.provider)
    if not p:
        sys.exit(f"未知 provider: {args.provider}")
    store = load_keys().get(args.provider, {})
    key = args.key or store.get("key")
    if not key:
        if p.get("keyless"):
            key = "no-key-needed"
        else:
            sys.exit(f"{args.provider} 没有 key，先 save")
    base = (args.base_url or store.get("base_url") or p["base_url"]).rstrip("/")
    tp = getattr(args, "transport", None) or store.get("transport") or "openai"
    if args.models:
        models = [m.strip() for m in args.models.split(",") if m.strip()]
    else:
        models = [m["id"] for m in p["models"]][:args.limit]
    if not models:
        sys.exit("没有要测的模型：目录里这家是空的，或者用 --models 显式指定")
    print(f"扫 {len(models)} 个模型 @ {base}\n")

    def one(mid):
        t0 = time.time()
        try:
            call_text(base, key, mid, "hi", transport=tp, max_tokens=8, timeout=45)
            return mid, True, "OK", int((time.time() - t0) * 1000)
        except urllib.error.HTTPError as e:
            body = e.read()[:300].decode("utf-8", "replace")
            kind = classify_error(e.code, body)
            short = body
            try:
                j = json.loads(body)
                short = (j.get("error") or {}).get("message") or j.get("message") or body
            except Exception:  # noqa: BLE001
                pass
            return mid, kind == "限流", f"{kind} {short[:70]}", int((time.time() - t0) * 1000)
        except Exception as e:  # noqa: BLE001
            return mid, False, f"失败 {e}", int((time.time() - t0) * 1000)

    results = []
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        for r in ex.map(one, models):
            results.append(r)
            print(f"{'✅' if r[1] else '❌'} {r[0]:<42}{r[3]:>6}ms  {r[2]}")
    ok = [r[0] for r in results if r[1]]
    print(f"\n可用 {len(ok)}/{len(results)}")
    if ok:
        print("可用模型: " + ", ".join(ok[:12]) + (" …" if len(ok) > 12 else ""))
        if not args.no_save and not args.key:
            keys = load_keys()
            ent = keys.setdefault(args.provider, {})
            ent["available_models"] = ok
            ent["default_model"] = ok[0]
            SECRETS.parent.mkdir(parents=True, exist_ok=True)
            SECRETS.write_text(json.dumps(keys, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"已写回 secrets：默认模型改为 {ok[0]}")


def cmd_status(args):
    keys = load_keys()
    if not keys:
        print("还没有保存任何 key。")
        return
    cat = load_catalog()
    by_slug = {p["slug"]: p for p in cat["providers"]}
    for slug, rec in keys.items():
        p = by_slug.get(slug)
        if not p:
            print(f"⚠️  {slug}: 有 key 但不在当前目录里")
            continue
        base = rec.get("base_url") or p["base_url"]
        ok, detail, _ = _probe(base, rec["key"],
                               rec.get("default_model") or _pick_model(p, None),
                               transport=rec.get("transport") or "openai")
        print(f"{'✅' if ok else '❌'} {slug:<28}{detail[:110]}")


def main():
    ap = argparse.ArgumentParser(description="免费 LLM API 目录 / key 校验 / 接入工具")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("refresh", help="从 freellm.net 重新抓取 provider 目录")
    r.set_defaults(func=cmd_refresh)

    l = sub.add_parser("list", help="列出 provider（默认按免费模型数排序）")
    l.add_argument("--cn", action="store_true", help="只看中国大陆可直连")
    l.add_argument("--no-card", action="store_true", help="只看不需要信用卡")
    l.add_argument("--no-phone", action="store_true", help="只看不需要手机验证")
    l.add_argument("--provider", help="只看某一家")
    l.add_argument("--models", action="store_true", help="同时列出免费模型 ID")
    l.add_argument("--json", action="store_true")
    l.set_defaults(func=cmd_list)

    s = sub.add_parser("save", help="保存某家的 API key")
    s.add_argument("--provider", required=True)
    s.add_argument("--key", required=True)
    s.add_argument("--model", help="默认模型 ID")
    s.add_argument("--base-url", help="配合 --env-file 写入 OPENAI_BASE_URL")
    s.add_argument("--env-file", help="顺便追加写成 .env")
    s.add_argument("--transport", choices=["openai", "dashscope"],
                   help="openai=兼容协议（默认）；dashscope=阿里原生协议，workspace key 必须用这个")
    s.set_defaults(func=cmd_save)

    v = sub.add_parser("verify", help="校验 key 是否可用")
    v.add_argument("--provider")
    v.add_argument("--key", help="临时传入，不读已保存的")
    v.add_argument("--model", help="chat 探测用的模型 ID")
    v.add_argument("--all", action="store_true", help="校验所有已保存的 key")
    v.add_argument("--base-url", help="覆盖目录里的 base_url（国内外站地址不同时用）")
    v.set_defaults(func=cmd_verify)

    c = sub.add_parser("chat", help="用免费 API 直接发一次对话（给 agent 自己用）")
    c.add_argument("--provider", required=True)
    c.add_argument("--model")
    c.add_argument("--key")
    c.add_argument("--base-url", help="覆盖目录里的 base_url")
    c.add_argument("--transport", choices=["openai", "dashscope"], help="协议，默认读 secrets")
    c.add_argument("prompt", help="提示词，传 - 从 stdin 读")
    c.add_argument("--temperature", type=float, default=0.3)
    c.add_argument("--max-tokens", type=int, default=0)
    c.add_argument("--json", action="store_true")
    c.add_argument("--usage", action="store_true", help="在 stderr 打印耗时和 token")
    c.set_defaults(func=cmd_chat)

    st = sub.add_parser("status", help="看已保存 key 的可用状态")
    st.set_defaults(func=cmd_status)

    sc = sub.add_parser("scan", help="逐个试目录里的模型，找出这个账号真正能调的")
    sc.add_argument("--provider", required=True)
    sc.add_argument("--key")
    sc.add_argument("--base-url")
    sc.add_argument("--limit", type=int, default=15, help="最多测几个模型，默认 15")
    sc.add_argument("--models", help="显式指定模型，逗号分隔；不填则用目录里的。目录标的免费模型经常不准")
    sc.add_argument("--workers", type=int, default=3, help="并发数，默认 3，调高容易触发限流")
    sc.add_argument("--no-save", action="store_true", help="不写回 secrets")
    sc.add_argument("--transport", choices=["openai", "dashscope"], help="协议，默认读 secrets")
    sc.set_defaults(func=cmd_scan)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
