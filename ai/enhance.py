import os
import ast
import json
import sys
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
import threading
import requests

import dotenv
import argparse
from tqdm import tqdm
from langchain_core.messages import SystemMessage, AIMessage
import langchain_core.exceptions
from langchain_openai import ChatOpenAI
from langchain_core.prompts import (
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
)
from .structure import Structure

# 加载环境变量
if os.path.exists('.env'):
    dotenv.load_dotenv(override=False)



# 获取当前目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 读取模板文件
template = open(os.path.join(current_dir, "template.txt"), "r").read()
system = open(os.path.join(current_dir, "system.txt"), "r").read()

DEFAULT_AI_FIELDS = {
    "tldr": "Task description failed",
    "motivation": "Motivation analysis unavailable",
    "method": "Method extraction failed",
    "result": "Result analysis unavailable",
    "conclusion": "Conclusion extraction failed",
}
REQUIRED_AI_FIELDS = tuple(DEFAULT_AI_FIELDS.keys())


def _render_system_prompt(language: str) -> str:
    return system.replace("{language}", language)


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
        or ":9201" in lowered
        or ":9202" in lowered
    )


def _is_placeholder_api_key(api_key: str) -> bool:
    lowered = (api_key or "").strip().lower()
    return lowered in {"", "vllm-local", "local", "test", "dummy", "none"}


def _build_official_fallback_config(current_model_name: str) -> Dict[str, str]:
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


def _inspect_ai_payload(ai_payload: Dict | None) -> Dict[str, List[str]]:
    missing_fields = []
    placeholder_fields = []

    if not isinstance(ai_payload, dict):
        return {
            "missing_fields": list(REQUIRED_AI_FIELDS),
            "placeholder_fields": [],
        }

    for field in REQUIRED_AI_FIELDS:
        value = ai_payload.get(field)
        if not isinstance(value, str) or not value.strip():
            missing_fields.append(field)
        elif value == DEFAULT_AI_FIELDS[field]:
            placeholder_fields.append(field)

    return {
        "missing_fields": missing_fields,
        "placeholder_fields": placeholder_fields,
    }


def collect_invalid_ai_items(enhanced_data: List[Dict]) -> List[Dict]:
    invalid_items = []

    for idx, item in enumerate(enhanced_data):
        item_id = item.get("id", "unknown")
        details = _inspect_ai_payload(item.get("AI"))
        if details["missing_fields"] or details["placeholder_fields"]:
            invalid_items.append(
                {
                    "index": idx,
                    "id": item_id,
                    "missing_fields": details["missing_fields"],
                    "placeholder_fields": details["placeholder_fields"],
                }
            )

    return invalid_items


def summarize_ai_quality(enhanced_data: List[Dict]) -> Dict:
    invalid_items = collect_invalid_ai_items(enhanced_data)
    total = len(enhanced_data)
    invalid_count = len(invalid_items)
    return {
        "total": total,
        "valid_count": total - invalid_count,
        "invalid_count": invalid_count,
        "invalid_ratio": (invalid_count / total) if total else 0.0,
        "invalid_items": invalid_items,
        "sample_invalid_items": invalid_items[:5],
    }


def ensure_ai_enhancement_quality(enhanced_data: List[Dict], context: str = "") -> Dict:
    stats = summarize_ai_quality(enhanced_data)
    if stats["invalid_count"] > 0:
        sample_text = "; ".join(
            [
                (
                    f"{item['id']}"
                    f"(missing={item['missing_fields']}, placeholders={item['placeholder_fields']})"
                )
                for item in stats["sample_invalid_items"]
            ]
        )
        prefix = f"[{context}] " if context else ""
        raise RuntimeError(
            f"{prefix}AI enhancement quality check failed: "
            f"{stats['invalid_count']}/{stats['total']} items contain default placeholder or missing AI fields. "
            f"sample={sample_text}"
        )
    return stats


def retry_invalid_items_with_official(
    enhanced_data: List[Dict],
    model_name: str,
    language: str,
    max_workers: int,
) -> List[Dict]:
    invalid_items = collect_invalid_ai_items(enhanced_data)
    if not invalid_items:
        return enhanced_data

    fallback_cfg = _build_official_fallback_config(model_name)
    fallback_base_url = fallback_cfg["base_url"]
    fallback_api_key = fallback_cfg["api_key"]
    fallback_model_name = fallback_cfg["model_name"]

    if not fallback_base_url or _looks_local_url(fallback_base_url):
        print(
            "Local AI enhancement produced invalid items, but no valid cloud base URL is configured. "
            "Skip partial cloud repair.",
            file=sys.stderr,
        )
        return enhanced_data

    if _is_placeholder_api_key(fallback_api_key):
        print(
            "Local AI enhancement produced invalid items, but no valid cloud API key is configured. "
            "Skip partial cloud repair.",
            file=sys.stderr,
        )
        return enhanced_data

    invalid_ids = [item["id"] for item in invalid_items]
    print(
        "Local AI enhancement produced "
        f"{len(invalid_items)} invalid items; retrying only these items via cloud provider. "
        f"ids={invalid_ids[:10]}{'...' if len(invalid_ids) > 10 else ''}",
        file=sys.stderr,
    )

    invalid_input_items = []
    for invalid in invalid_items:
        repaired_input = dict(enhanced_data[invalid["index"]])
        repaired_input.pop("AI", None)
        invalid_input_items.append(repaired_input)

    repair_workers = max(1, min(max_workers, len(invalid_input_items)))
    original_openai_base_url = os.environ.get("OPENAI_BASE_URL")
    original_openai_api_key = os.environ.get("OPENAI_API_KEY")
    original_provider = os.environ.get("PROVIDER")

    try:
        os.environ["OPENAI_BASE_URL"] = fallback_base_url
        os.environ["OPENAI_API_KEY"] = fallback_api_key
        os.environ["PROVIDER"] = "official"
        repaired_items = process_all_items(
            invalid_input_items,
            fallback_model_name,
            language,
            repair_workers,
            provider="official",
        )
    finally:
        if original_openai_base_url is None:
            os.environ.pop("OPENAI_BASE_URL", None)
        else:
            os.environ["OPENAI_BASE_URL"] = original_openai_base_url

        if original_openai_api_key is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = original_openai_api_key

        if original_provider is None:
            os.environ.pop("PROVIDER", None)
        else:
            os.environ["PROVIDER"] = original_provider

    repaired_by_id = {
        item.get("id"): item
        for item in repaired_items
        if item is not None and item.get("id")
    }

    merged_count = 0
    for invalid in invalid_items:
        repaired_item = repaired_by_id.get(invalid["id"])
        if repaired_item is None:
            continue
        enhanced_data[invalid["index"]] = repaired_item
        merged_count += 1

    remaining_stats = summarize_ai_quality(enhanced_data)
    print(
        "Partial cloud repair finished: "
        f"merged={merged_count}/{len(invalid_items)}, "
        f"remaining_invalid={remaining_stats['invalid_count']}",
        file=sys.stderr,
    )
    return enhanced_data

def _extract_json_object_text(text: str) -> str:
    text = text.strip()
    # 兼容内容被整体 JSON 转义（如 "\"{...}\""）
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        try:
            text = json.loads(text)
        except Exception:
            pass
    # 兼容直接返回 OpenAI/本地服务的完整响应 JSON
    try:
        if text.lstrip().startswith("{") and '"choices"' in text:
            obj = json.loads(text)
            msg = obj.get("choices", [{}])[0].get("message", {}).get("content")
            if msg:
                text = msg
    except Exception:
        pass
    # 兼容 ```json ... ``` 或 ``` ... ```
    m = re.search(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.S | re.I)
    if m:
        text = m.group(1)
    # 兼容夹杂文本
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
    return text.strip()


def _iter_repaired_json_candidates(text: str):
    seen = set()

    def _remember(candidate: str):
        candidate = candidate.strip()
        if not candidate or candidate in seen:
            return None
        seen.add(candidate)
        return candidate

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    stripped_control = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", normalized)
    escaped_backslashes = re.sub(r'\\([A-Za-z]{2,})', r"\\\\\1", stripped_control)
    escaped_backslashes = re.sub(r'\\(?!["\\/bfnrtu])', r"\\\\", escaped_backslashes)

    candidate = _remember(escaped_backslashes)
    if candidate:
        yield candidate

    candidate = _remember(stripped_control)
    if candidate:
        yield candidate

    candidate = _remember(normalized)
    if candidate:
        yield candidate

    without_trailing_commas = re.sub(r",(\s*[}\]])", r"\1", escaped_backslashes)
    candidate = _remember(without_trailing_commas)
    if candidate:
        yield candidate

    normalized_quotes = (
        without_trailing_commas.replace("“", '"')
        .replace("”", '"')
        .replace("’", "'")
        .replace("‘", "'")
    )
    candidate = _remember(normalized_quotes)
    if candidate:
        yield candidate


def _extract_json(text: str) -> dict:
    text = _extract_json_object_text(text)
    last_error = None

    for candidate in _iter_repaired_json_candidates(text):
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except Exception as exc:
            last_error = exc

        try:
            data = ast.literal_eval(candidate)
            if isinstance(data, dict):
                return data
        except Exception as exc:
            last_error = exc

    if last_error is not None:
        raise last_error

    raise ValueError("No JSON object found in model response")


def _coerce_response_to_ai_payload(response, default_ai_fields: Dict[str, str]) -> Dict[str, str]:
    if isinstance(response, Structure):
        return response.model_dump()

    response_text = response.content if isinstance(response, AIMessage) else str(response)
    data = _extract_json(response_text)
    obj = Structure.model_validate({**default_ai_fields, **data})
    return obj.model_dump()


def _should_retry_local_error(exc: Exception) -> bool:
    if isinstance(exc, (json.JSONDecodeError, ValueError, SyntaxError)):
        return True
    if isinstance(exc, langchain_core.exceptions.OutputParserException):
        return True
    msg = str(exc).lower()
    markers = [
        "failed to parse",
        "invalid json",
        "expecting property name",
        "invalid \\escape",
        "unterminated string",
        "json",
    ]
    return any(marker in msg for marker in markers)

def is_sensitive(content: str) -> bool:
    """
    调用 spam.dw-dengwei.workers.dev 接口检测内容是否包含敏感词。
    返回 True 表示触发敏感词，False 表示未触发。
    """
    try:
        resp = requests.post(
            "https://spam.dw-dengwei.workers.dev",
            json={"text": content},
            timeout=15
        )
        if resp.status_code == 200:
            result = resp.json()
            # 约定接口返回 {"sensitive": true/false, ...}
            return result.get("sensitive", True)
        else:
            # 如果接口异常，默认不触发敏感词
            print(f"Sensitive check failed with status {resp.status_code}", file=sys.stderr)
            return True
    except Exception as e:
        print(f"Sensitive check error: {e}", file=sys.stderr)
        return True


def _is_local_model_unloaded_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    markers = [
        "no models loaded",
        "please load a model",
        "lms load",
        "model is not loaded",
    ]
    return any(marker in msg for marker in markers)


def _resolve_midplatform_base_url() -> str:
    """
    解析中台地址，优先 MIDPLATFORM_BASE_URL，其次兼容 OPENAI_BASE_URL。
    若给到的是 .../v1，则去掉 /v1 得到中台根地址。
    """
    api_base = os.environ.get("MIDPLATFORM_BASE_URL") or os.environ.get("OPENAI_BASE_URL") or "http://127.0.0.1:8900"
    api_base = api_base.rstrip("/")
    if api_base.endswith("/v1"):
        api_base = api_base[:-3]
    return api_base.rstrip("/")


def _fetch_midplatform_models(api_base: str) -> List[Dict]:
    models_url = f"{api_base}/api/models"

    try:
        resp = requests.get(models_url, timeout=10)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return [m for m in items if isinstance(m, dict) and m.get("model_name")]
    except Exception as e:
        print(f"Failed to query midplatform model list from {models_url}: {e}", file=sys.stderr)
        return []


def _allocate_midplatform_lease(api_base: str, model_name: str) -> Dict:
    allocate_url = f"{api_base}/api/allocate"
    ctx = int(os.environ.get("LLM_CTX", "8000"))
    max_wait_seconds = int(os.environ.get("LLM_MAX_WAIT_SECONDS", "300"))
    owner_id = os.environ.get("LLM_OWNER_ID") or f"arxiv-crawler-{os.getpid()}"

    payload = {
        "model_name": model_name,
        "ctx": ctx,
        "wait": True,
        "max_wait_seconds": max_wait_seconds,
        "owner_type": "manual",
        "owner_id": owner_id,
    }
    resp = requests.post(allocate_url, json=payload, timeout=max_wait_seconds + 30)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("lease_id") or not data.get("base_url"):
        raise RuntimeError(f"Invalid allocate response: {data}")
    return data


def _release_midplatform_lease(api_base: str, lease_id: str) -> None:
    release_url = f"{api_base}/api/release"
    try:
        resp = requests.post(release_url, json={"lease_id": lease_id}, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"Failed to release lease {lease_id}: {e}", file=sys.stderr)


class _LeaseHeartbeatManager:
    """
    持有租约期间定时续租：
    POST /api/leases/{lease_id}/renew
    """

    def __init__(self, api_base: str, lease_ids: List[str], interval_seconds: int = 30):
        self.api_base = api_base.rstrip("/")
        self.lease_ids = [x for x in lease_ids if x]
        self.interval_seconds = max(5, interval_seconds)
        self._stop_event = threading.Event()
        self._thread = None

    def start(self) -> None:
        if not self.lease_ids:
            return
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._loop, name="lease-heartbeat", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None:
            return
        self._stop_event.set()
        self._thread.join(timeout=5)
        self._thread = None

    def _renew_once(self, lease_id: str) -> None:
        renew_url = f"{self.api_base}/api/leases/{lease_id}/renew"
        try:
            resp = requests.post(renew_url, json={}, timeout=10)
            if resp.status_code != 200:
                print(
                    f"Lease renew failed for {lease_id}: status={resp.status_code}, body={resp.text[:300]}",
                    file=sys.stderr,
                )
        except Exception as e:
            print(f"Lease renew error for {lease_id}: {e}", file=sys.stderr)

    def _loop(self) -> None:
        # 约定每 30 秒续租一次；先等待一个间隔再续租，避免请求风暴
        while not self._stop_event.wait(self.interval_seconds):
            for lease_id in self.lease_ids:
                if self._stop_event.is_set():
                    return
                self._renew_once(lease_id)


def _process_batch(
    chain,
    provider: str,
    language: str,
    indexed_items: List[tuple],
    batch_workers: int = 2,
) -> List[tuple]:
    """
    处理一个数据分片，返回 (原始索引, 处理结果) 列表。
    """
    results = []
    with ThreadPoolExecutor(max_workers=batch_workers) as executor:
        future_to_item = {
            executor.submit(process_single_item, chain, item, language, provider): (idx, item)
            for idx, item in indexed_items
        }
        for future in as_completed(future_to_item):
            idx, item = future_to_item[future]
            try:
                result = future.result()
                results.append((idx, result))
            except Exception as e:
                print(f"Item at index {idx} generated an exception: {e}", file=sys.stderr)
                item['AI'] = DEFAULT_AI_FIELDS.copy()
                results.append((idx, item))
    return results

def process_single_item(chain, item: Dict, language: str,provider) -> Dict:
    """
    处理单个数据项，使用大模型生成AI增强内容
    
    Args:
        chain: LangChain调用链
        item (Dict): 论文数据
        language (str): 生成语言
        
    Returns:
        Dict: 带有AI增强内容的论文数据
    """
    # 检查 summary 字段
    # if is_sensitive(item.get("summary", "")):
    #     print(f"Sensitive summary detected for {item.get('id', 'unknown')},summary:{item.get("summary", "")}", file=sys.stderr)
    #     return None

    # Default structure with meaningful fallback values
    default_ai_fields = DEFAULT_AI_FIELDS.copy()
    
    try:
        last_error = None
        max_attempts = 3 if provider == "local" else 1
        for attempt in range(1, max_attempts + 1):
            try:
                response = chain.invoke({
                    "language": language,
                    "title": item['title'],
                    "abstract": item['summary']
                })
                item["AI"] = _coerce_response_to_ai_payload(response, default_ai_fields)
                return item
            except Exception as invoke_error:
                last_error = invoke_error
                should_retry = False

                if provider == "local" and attempt < max_attempts:
                    if _is_local_model_unloaded_error(invoke_error):
                        should_retry = True
                    elif _should_retry_local_error(invoke_error):
                        should_retry = True

                if should_retry:
                    wait_seconds = attempt * 2
                    print(
                        f"Local AI parse/invoke retry for {item.get('id', 'unknown')} in {wait_seconds}s "
                        f"({attempt}/{max_attempts}): {invoke_error}",
                        file=sys.stderr,
                    )
                    time.sleep(wait_seconds)
                    continue
                raise

        if last_error is not None:
            raise last_error
    except langchain_core.exceptions.OutputParserException as e:
        # 尝试从错误信息中提取 JSON 字符串并修复
        error_msg = getattr(e, "llm_output", None) or str(e)
        partial_data = {}
        
        if "Function Structure arguments:" in error_msg:
            try:
                # 提取 JSON 字符串
                json_str = error_msg.split("Function Structure arguments:", 1)[1].strip().split('are not valid JSON')[0].strip()
                # 预处理 LaTeX 数学符号 - 使用四个反斜杠来确保正确转义
                json_str = json_str.replace('\\', '\\\\')
                # 尝试解析修复后的 JSON
                partial_data = json.loads(json_str)
            except Exception as json_e:
                print(f"Failed to parse JSON for {item.get('id', 'unknown')}: {json_e}", file=sys.stderr)
        else:
            try:
                partial_data = _extract_json(error_msg)
            except Exception as json_e:
                print(f"Failed to parse JSON for {item.get('id', 'unknown')}: {json_e}", file=sys.stderr)
        
        # Merge partial data with defaults to ensure all fields exist
        item['AI'] = {**default_ai_fields, **partial_data}
        print(f"Using partial AI data for {item.get('id', 'unknown')}: {list(partial_data.keys())}", file=sys.stderr)
    except Exception as e:
        # Catch any other exceptions and provide default values
        print(f"Unexpected error for {item.get('id', 'unknown')}: {e}", file=sys.stderr)
        item['AI'] = default_ai_fields
    
    # Final validation to ensure all required fields exist
    for field in default_ai_fields.keys():
        if field not in item['AI']:
            item['AI'][field] = default_ai_fields[field]

    # 检查 AI 生成的所有字段
    # for v in item.get("AI", {}).values():
    #     if is_sensitive(str(v)):
    #         return None
    return item

def process_all_items(data: List[Dict], model_name: str = "deepseek-chat", language: str = "Chinese", max_workers: int = 1, provider: str = "official") -> List[Dict]:
    """
    并行处理所有数据项，使用大模型生成AI增强内容
    
    Args:
        data (List[Dict]): 论文数据列表
        model_name (str, optional): 大模型名称. Defaults to "deepseek-chat".
        language (str, optional): 生成语言. Defaults to "Chinese".
        max_workers (int, optional): 最大并行数. Defaults to 1.
        provider:
        - "official": 用官方 OpenAI
        - "local"   : 用本地 LLM 中台（allocate/release）
   
    Returns:
        List[Dict]: 带有AI增强内容的论文数据列表
    """
    # 从环境变量获取API配置
    lease_ids = []
    lease_heartbeat = None
    if provider == "official":
        api_key  = os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com")
        # model_name 继续用 env/参数传入的官方模型名，比如 gpt-4o-mini
    elif provider == "local":
        api_key = os.environ.get("OPENAI_API_KEY", "vllm-local")
        api_base = _resolve_midplatform_base_url()
        models = _fetch_midplatform_models(api_base)
        ready_models = [m["model_name"] for m in models if m.get("status") == "ready"]

        if not ready_models:
            raise RuntimeError(
                f"No ready models found from midplatform {api_base}/api/models. "
                "Please ensure model is loaded."
            )

        if model_name not in ready_models:
            fallback_model = ready_models[0]
            print(
                f"Configured MODEL_NAME '{model_name}' is not ready on midplatform. "
                f"Fallback to '{fallback_model}'.",
                file=sys.stderr,
            )
            model_name = fallback_model

        # 固定并发申请两个 lease，最大化利用中台双实例能力
        with ThreadPoolExecutor(max_workers=2) as alloc_executor:
            alloc_futures = [
                alloc_executor.submit(_allocate_midplatform_lease, api_base, model_name),
                alloc_executor.submit(_allocate_midplatform_lease, api_base, model_name),
            ]
            leases = [f.result() for f in alloc_futures]

        for lease in leases:
            lease_ids.append(lease["lease_id"])

        base_urls = [lease["base_url"] for lease in leases]
        model_name = leases[0].get("model_name", model_name)
        print(
            "Allocated 2 leases: "
            + ", ".join(
                [f"{lease['lease_id']}@{lease['base_url']}" for lease in leases]
            ),
            file=sys.stderr
        )
        # 按中台要求：租约持有期间每 30 秒续租一次
        lease_heartbeat = _LeaseHeartbeatManager(api_base=api_base, lease_ids=lease_ids, interval_seconds=30)
        lease_heartbeat.start()
    else:
        raise ValueError(f"Unknown provider: {provider}")

    try:
        processed_data = [None] * len(data)  # 预分配结果列表

        system_prompt = _render_system_prompt(language)
        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_prompt),
            HumanMessagePromptTemplate.from_template(template=template)
        ])

        if provider == "official":
            # 创建ChatOpenAI实例，传递API密钥和基础URL
            llm_base = ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url=base_url
            )
            print('Connect to:', base_url, ":", model_name, file=sys.stderr)

            # 官方模型支持结构化输出和函数调用
            llm = llm_base.with_structured_output(Structure, method="function_calling")
            chain = prompt_template | llm

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_idx = {
                    executor.submit(process_single_item, chain, item, language, provider): idx
                    for idx, item in enumerate(data)
                }

                for future in tqdm(
                    as_completed(future_to_idx),
                    total=len(data),
                    desc="Processing items"
                ):
                    idx = future_to_idx[future]
                    try:
                        result = future.result()
                        processed_data[idx] = result
                    except Exception as e:
                        print(f"Item at index {idx} generated an exception: {e}", file=sys.stderr)
                        processed_data[idx] = data[idx]
                        processed_data[idx]['AI'] = DEFAULT_AI_FIELDS.copy()
        else:
            # 本地模式固定两路：两个 lease + 两个 chain + 数据二分并行
            local_batch_workers = 6  # 固定每个实例并发为6
            chain_a = prompt_template | ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url=base_urls[0],
            )
            chain_b = prompt_template | ChatOpenAI(
                model=model_name,
                api_key=api_key,
                base_url=base_urls[1],
            )
            print('Connect to:', base_urls[0], ":", model_name, file=sys.stderr)
            print('Connect to:', base_urls[1], ":", model_name, file=sys.stderr)

            midpoint = len(data) // 2
            batch_a = list(enumerate(data[:midpoint]))
            batch_b = [(i + midpoint, item) for i, item in enumerate(data[midpoint:])]

            with ThreadPoolExecutor(max_workers=2) as split_executor:
                future_a = split_executor.submit(
                    _process_batch, chain_a, provider, language, batch_a, local_batch_workers
                )
                future_b = split_executor.submit(
                    _process_batch, chain_b, provider, language, batch_b, local_batch_workers
                )

                with tqdm(total=len(data), desc="Processing items") as pbar:
                    for future in as_completed([future_a, future_b]):
                        batch_results = future.result()
                        for idx, result in batch_results:
                            processed_data[idx] = result
                        pbar.update(len(batch_results))

        return processed_data
    finally:
        if lease_heartbeat is not None:
            lease_heartbeat.stop()
        if provider == "local" and lease_ids:
            api_base = _resolve_midplatform_base_url()
            for lease_id in lease_ids:
                _release_midplatform_lease(api_base, lease_id)

def enhance_jsonl_data(jsonl_data: List[Dict], model_name: str = "deepseek-chat",
                         language: str = "Chinese", max_workers: int = 1, 
                         provider="official") -> List[Dict]:
    """
    增强JSONL数据，添加AI生成的内容
    
    Args:
        jsonl_data (List[Dict]): JSONL格式的论文数据列表
        model_name (str, optional): 大模型名称. Defaults to "deepseek-chat".
        language (str, optional): 生成语言. Defaults to "Chinese".
        max_workers (int, optional): 最大并行数. Defaults to 1.
        provider (str, optional): 模型提供商，"official"或"local". Defaults to "official".
        
    Returns:
        List[Dict]: 增强后的论文数据列表
    """

    # 去重
    seen_ids = set()
    unique_data = []
    for item in jsonl_data:
        if item['id'] not in seen_ids:
            seen_ids.add(item['id'])
            unique_data.append(item)
    
    # 并行处理所有数据
    processed_data = process_all_items(
        unique_data,
        model_name,
        language,
        max_workers,
        provider
    )

    if provider == "local" and _is_true(os.environ.get("AUTO_FALLBACK_TO_OFFICIAL"), True):
        processed_data = retry_invalid_items_with_official(
            processed_data,
            model_name,
            language,
            max_workers,
        )
    
    # 过滤掉None值
    return [item for item in processed_data if item is not None]

if __name__ == "__main__":
    # 命令行参数解析
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, required=True, help="jsonline data file")
    parser.add_argument("--max_workers", type=int, default=1, help="Maximum number of parallel workers")
    args = parser.parse_args()
    
    model_name = os.environ.get("MODEL_NAME", 'deepseek-chat')
    language = os.environ.get("LANGUAGE", 'Chinese')

    # 检查并删除目标文件
    target_file = args.data.replace('.jsonl', f'_AI_enhanced_{language}.jsonl')
    if os.path.exists(target_file):
        os.remove(target_file)
        print(f'Removed existing file: {target_file}', file=sys.stderr)

    # 读取数据
    data = []
    with open(args.data, "r") as f:
        for line in f:
            data.append(json.loads(line))

    # 增强数据
    enhanced_data = enhance_jsonl_data(data, model_name, language, args.max_workers)
    
    # 保存结果
    with open(target_file, "w") as f:
        for item in enhanced_data:
            if item is not None:
                f.write(json.dumps(item) + "\n")
