import os
import re
import sys
import textwrap
import threading
from typing import Any

import requests
from openai import OpenAI


XHS_MODEL_NAME = "qwen/Qwen3-14B-FP8"
_XHS_STYLE_EXAMPLE = """标题：IEEE/CAA JAS：自动化人的“国刊之光”。
正文：作为 IEEE 和中国自动化学会联合主办的牌面，JAS 已经是 中科院1区 Top 的常客。它不排斥 AI，反而非常欢迎用 AI 解决控制问题 的好文章！ 
📝 地位：国产期刊的骄傲，稳居 1区 Top，认可度极高。
📝 影响力：IF 持续走高，是 AI 与控制交叉领域的“流量担当”。
📝 完全OA：Gold OA 模式，传播速度快，引用涨得飞快。

✅ 收什么？（理论+智能）
交叉融合：最爱“控制理论”与“人工智能（深度学习/强化学习）”结合的文章。
数学严谨：虽然拥抱AI，但控制领域的“稳定性证明”和“收敛性分析”不能丢。
复杂系统：多智能体（Multi-agent）、网络化系统、人机协同是热门方向。

❌ 拒什么？（精准避雷）
纯工程实现：只搭了个硬件或跑了个代码，没有理论建模和推导（建议投应用类刊）。
简单仿真：只有Matlab简单仿真，缺乏对比实验和鲁棒性分析。
生搬硬套：强行用AI算法做控制，但解释不清物理机制和安全性。"""


def _is_true(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _looks_local_url(url: str) -> bool:
    lowered = (url or "").strip().lower()
    return (
        "127.0.0.1" in lowered
        or "localhost" in lowered
        or ":8900" in lowered
        or ":9202" in lowered
    )


def _is_placeholder_api_key(api_key: str) -> bool:
    lowered = (api_key or "").strip().lower()
    return lowered in {"", "vllm-local", "local", "test", "dummy", "none"}


def _resolve_midplatform_base_url() -> str:
    api_base = os.environ.get("MIDPLATFORM_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or "http://127.0.0.1:8900"
    api_base = api_base.rstrip("/")
    if api_base.endswith("/v1"):
        api_base = api_base[:-3]
    return api_base.rstrip("/")


def _build_official_fallback_config(current_model_name: str) -> dict[str, str]:
    env_base_url = os.environ.get("OPENAI_BASE_URL", "").strip()
    env_api_key = os.environ.get("OPENAI_API_KEY", "").strip()

    official_base_url = (
        os.environ.get("OFFICIAL_OPENAI_BASE_URL")
        or os.environ.get("CLOUD_OPENAI_BASE_URL")
        or (env_base_url if env_base_url and not _looks_local_url(env_base_url) else "")
    )
    official_api_key = (
        os.environ.get("OFFICIAL_OPENAI_API_KEY")
        or os.environ.get("CLOUD_OPENAI_API_KEY")
        or (env_api_key if not _is_placeholder_api_key(env_api_key) else "")
    )
    official_model_name = (
        os.environ.get("OFFICIAL_MODEL_NAME")
        or os.environ.get("CLOUD_MODEL_NAME")
        or current_model_name
        or "deepseek-chat"
    )
    return {
        "base_url": official_base_url.strip(),
        "api_key": official_api_key.strip(),
        "model_name": official_model_name.strip(),
    }


def _fetch_midplatform_models(api_base: str) -> list[dict[str, Any]]:
    models_url = f"{api_base}/api/models"
    try:
        resp = requests.get(models_url, timeout=10)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return [x for x in items if isinstance(x, dict) and x.get("model_name")]
    except Exception:
        return []


def _allocate_midplatform_lease(api_base: str, model_name: str) -> dict[str, Any]:
    allocate_url = f"{api_base}/api/allocate"
    payload = {
        "model_name": model_name,
        "ctx": int(os.environ.get("LLM_CTX", "8000")),
        "wait": True,
        "max_wait_seconds": int(os.environ.get("LLM_MAX_WAIT_SECONDS", "1200")),
        "owner_type": "manual",
        "owner_id": os.environ.get("LLM_OWNER_ID") or f"wechat-xhs-{os.getpid()}",
    }
    resp = requests.post(allocate_url, json=payload, timeout=payload["max_wait_seconds"] + 30)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("lease_id") or not data.get("base_url"):
        raise RuntimeError(f"Invalid allocate response: {data}")
    return data


def _release_midplatform_lease(api_base: str, lease_id: str) -> None:
    try:
        resp = requests.post(f"{api_base}/api/release", json={"lease_id": lease_id}, timeout=15)
        resp.raise_for_status()
    except Exception:
        # best effort
        pass


class _LeaseHeartbeatManager:
    """Lease renew loop for long-running generation."""

    def __init__(self, api_base: str, lease_id: str, interval_seconds: int = 20):
        self.api_base = api_base.rstrip("/")
        self.lease_id = lease_id
        self.interval_seconds = max(5, interval_seconds)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if not self.lease_id or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="xhs-lease-heartbeat", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None:
            return
        self._stop_event.set()
        self._thread.join(timeout=5)
        self._thread = None

    def _renew_once(self) -> None:
        try:
            renew_url = f"{self.api_base}/api/leases/{self.lease_id}/renew"
            requests.post(renew_url, json={}, timeout=10)
        except Exception:
            # best effort
            pass

    def _loop(self) -> None:
        while not self._stop_event.wait(self.interval_seconds):
            if self._stop_event.is_set():
                return
            self._renew_once()


def _build_xhs_prompt(journal_markdown: str) -> str:
    source = journal_markdown.strip()
    if len(source) > 6000:
        source = source[:6000]
    return textwrap.dedent(
        f"""
        你是科研内容运营编辑，请根据“期刊介绍原文”产出一篇中文小红书文案。
        你必须模仿“参考示例”的风格和结构，但内容要贴合期刊介绍原文。

        输出要求：
        1. 先输出“标题：...”
        2. 再输出“正文：...”
        3. 再输出“✅ 收什么？（理论+智能）”
        4. 再输出“❌ 拒什么？（精准避雷）”
        5. 不要输出解释，不要加代码块。
        6. 文风要有传播感，信息准确，不要编造原文没有的信息。

        参考示例：
        {_XHS_STYLE_EXAMPLE}

        期刊介绍原文：
        {source}
        """
    ).strip()


def clean_xiaohongshu_content(text: str) -> str:
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.S | re.I).strip()
    cleaned = cleaned.replace("```markdown", "").replace("```text", "").replace("```", "").strip()

    title_markers = ("标题：", "标题:")
    start_idx = -1
    for marker in title_markers:
        idx = cleaned.find(marker)
        if idx >= 0:
            start_idx = idx
            break
    if start_idx >= 0:
        cleaned = cleaned[start_idx:].strip()
    return cleaned


def _chat_completion(base_url: str, api_key: str, model_name: str, prompt: str) -> str:
    client = OpenAI(base_url=base_url, api_key=api_key)
    resp = client.chat.completions.create(
        model=model_name,
        temperature=0.6,
        messages=[
            {"role": "system", "content": "你是一个严谨但会写爆款文案的科研内容编辑。"},
            {"role": "user", "content": prompt},
        ],
    )
    return clean_xiaohongshu_content(resp.choices[0].message.content or "")


def _generate_local(journal_markdown: str, model_name: str) -> dict[str, Any]:
    api_base = _resolve_midplatform_base_url()
    models = _fetch_midplatform_models(api_base)
    status_map = {m.get("model_name"): m for m in models}
    model_info = status_map.get(model_name)
    if model_info and model_info.get("status") != "ready":
        raise RuntimeError(
            f"local model not ready: model={model_name}, status={model_info.get('status')}, "
            f"last_error={model_info.get('last_error')}"
        )

    lease = _allocate_midplatform_lease(api_base, model_name)
    lease_id = lease["lease_id"]
    base_url = lease["base_url"].rstrip("/")
    api_key = os.environ.get("OPENAI_API_KEY", "vllm-local")
    prompt = _build_xhs_prompt(journal_markdown)
    heartbeat = _LeaseHeartbeatManager(
        api_base=api_base,
        lease_id=lease_id,
        interval_seconds=int(os.environ.get("LLM_LEASE_HEARTBEAT_SECONDS", "20")),
    )
    try:
        heartbeat.start()
        content = _chat_completion(base_url=base_url, api_key=api_key, model_name=model_name, prompt=prompt)
        if not content:
            raise RuntimeError("empty xiaohongshu content")
        return {
            "status": "success",
            "provider": "local",
            "model_name": model_name,
            "lease_id": lease_id,
            "content": content,
        }
    finally:
        heartbeat.stop()
        _release_midplatform_lease(api_base, lease_id)


def _generate_official(journal_markdown: str, model_name: str) -> dict[str, Any]:
    fallback_cfg = _build_official_fallback_config(model_name)
    fallback_base_url = fallback_cfg["base_url"]
    fallback_api_key = fallback_cfg["api_key"]
    fallback_model_name = fallback_cfg["model_name"]

    if not fallback_base_url or _looks_local_url(fallback_base_url):
        raise RuntimeError("未配置有效云端地址，请设置 OFFICIAL_OPENAI_BASE_URL（或 CLOUD_OPENAI_BASE_URL）")
    if _is_placeholder_api_key(fallback_api_key):
        raise RuntimeError("未配置有效云端密钥，请设置 OFFICIAL_OPENAI_API_KEY（或 CLOUD_OPENAI_API_KEY）")

    prompt = _build_xhs_prompt(journal_markdown)
    content = _chat_completion(
        base_url=fallback_base_url,
        api_key=fallback_api_key,
        model_name=fallback_model_name,
        prompt=prompt,
    )
    if not content:
        raise RuntimeError("empty xiaohongshu content")
    return {
        "status": "success",
        "provider": "official",
        "model_name": fallback_model_name,
        "content": content,
    }


def generate_xiaohongshu_copy_from_journal(
    journal_markdown: str,
    model_name: str = XHS_MODEL_NAME,
) -> dict[str, Any]:
    provider = (os.environ.get("XHS_PROVIDER") or os.environ.get("PROVIDER") or "local").strip().lower()
    auto_fallback = _is_true(os.environ.get("AUTO_FALLBACK_TO_OFFICIAL"), True)

    if provider == "official":
        return _generate_official(journal_markdown, model_name)

    if provider != "local":
        raise ValueError(f"Unknown XHS provider: {provider}")

    try:
        return _generate_local(journal_markdown, model_name)
    except Exception as local_error:
        if not auto_fallback:
            raise
        print(
            f"[xhs] local generation failed, fallback to official. error={local_error}",
            file=sys.stderr,
        )
        result = _generate_official(journal_markdown, model_name)
        result["fallback_from"] = "local"
        result["local_error"] = str(local_error)
        return result
