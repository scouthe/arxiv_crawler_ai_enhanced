import os
import json
import sys
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
from queue import Queue
from threading import Lock
import requests

import dotenv
import argparse
from tqdm import tqdm
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import SystemMessage, AIMessage
import langchain_core.exceptions
from langchain_openai import ChatOpenAI
from langchain_core.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
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

def _extract_json(text: str) -> dict:
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
    # 兼容 ```json ... ```
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, flags=re.S)
    if m:
        text = m.group(1)
    # 兼容夹杂文本
    if not text.startswith("{"):
        m = re.search(r"(\{.*\})", text, flags=re.S)
        if m:
            text = m.group(1)
    return json.loads(text)

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


def _fetch_local_model_ids(base_url: str, api_key: str) -> List[str]:
    if not base_url:
        return []

    base = base_url.rstrip("/")
    models_url = f"{base}/models" if base.endswith("/v1") else f"{base}/v1/models"
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    try:
        resp = requests.get(models_url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        return [m.get("id") for m in data if isinstance(m, dict) and m.get("id")]
    except Exception as e:
        print(f"Failed to query local model list from {models_url}: {e}", file=sys.stderr)
        return []

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
    default_ai_fields = {
        "tldr": "Task description failed",
        "motivation": "Motivation analysis unavailable",
        "method": "Method extraction failed",
        "result": "Result analysis unavailable",
        "conclusion": "Conclusion extraction failed"
    }
    
    try:
        response = None
        last_invoke_error = None
        max_attempts = 3 if provider == "local" else 1
        for attempt in range(1, max_attempts + 1):
            try:
                response = chain.invoke({
                    "language": language,
                    "title": item['title'],
                    "abstract": item['summary']
                })
                break
            except Exception as invoke_error:
                last_invoke_error = invoke_error
                if (
                    provider == "local"
                    and _is_local_model_unloaded_error(invoke_error)
                    and attempt < max_attempts
                ):
                    wait_seconds = attempt * 2
                    print(
                        f"Local model not loaded for {item.get('id', 'unknown')}, retrying in {wait_seconds}s "
                        f"({attempt}/{max_attempts})",
                        file=sys.stderr,
                    )
                    time.sleep(wait_seconds)
                    continue
                raise

        if response is None and last_invoke_error is not None:
            raise last_invoke_error

        if isinstance(response, Structure):
            item["AI"] = response.model_dump()
            return item

        # 走到这里说明本地 parser response 是 AIMessage/str
        response_text = response.content if isinstance(response, AIMessage) else str(response)
        data = _extract_json(response_text)

        obj = Structure.model_validate({**default_ai_fields, **data})
        item["AI"] = obj.model_dump()
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
        - "local"   : 用你自建/LmStudio
   
    Returns:
        List[Dict]: 带有AI增强内容的论文数据列表
    """
    # 从环境变量获取API配置

    if provider == "official":
        api_key  = os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com")
        # model_name 继续用 env/参数传入的官方模型名，比如 gpt-4o-mini
    elif provider == "local":
        api_key  = os.environ.get("OPENAI_API_KEY", "lm-studio")  # LM Studio 一般不校验，给个占位
        base_url = os.environ.get("OPENAI_BASE_URL")  # 例如 http://127.0.0.1:1234/v1
        # model_name 用你本地模型的名字，比如 "qwen2.5-32b-instruct"
        local_model_ids = _fetch_local_model_ids(base_url, api_key)
        if local_model_ids and model_name not in local_model_ids:
            print(
                f"Configured MODEL_NAME '{model_name}' not found on local server. "
                f"Fallback to '{local_model_ids[0]}'.",
                file=sys.stderr,
            )
            model_name = local_model_ids[0]
    else:
        raise ValueError(f"Unknown provider: {provider}")
    # 创建ChatOpenAI实例，传递API密钥和基础URL
    llm_base = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url
    )
    print('Connect to:',base_url,":", model_name, file=sys.stderr)

    prompt_template = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(system),
        HumanMessagePromptTemplate.from_template(template=template)
    ])


    parser = PydanticOutputParser(pydantic_object=Structure)
    if provider == "official":
        # 官方模型支持结构化输出和函数调用
        llm = llm_base.with_structured_output(Structure, method="function_calling")
        chain = prompt_template | llm
    else:
        fmt = parser.get_format_instructions()
        fmt_escaped = fmt.replace("{", "{{").replace("}", "}}")

        system_with_format = system + "\n\n" + fmt_escaped

        # ✅ system 用纯 SystemMessage，不走模板解析
        prompt_template_local = ChatPromptTemplate.from_messages([
            SystemMessage(content=system_with_format),
            HumanMessagePromptTemplate.from_template(template=template),
        ])

        chain = prompt_template_local | llm_base | parser



    
    # 使用线程池并行处理
    processed_data = [None] * len(data)  # 预分配结果列表
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_idx = {
            executor.submit(process_single_item, chain, item, language,provider): idx
            for idx, item in enumerate(data)
        }
        
        # 使用tqdm显示进度
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
                # Add default AI fields to ensure consistency
                processed_data[idx] = data[idx]
                processed_data[idx]['AI'] = {
                    "tldr": "Processing failed",
                    "motivation": "Processing failed",
                    "method": "Processing failed",
                    "result": "Processing failed",
                    "conclusion": "Processing failed"
                }
    
    return processed_data

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
