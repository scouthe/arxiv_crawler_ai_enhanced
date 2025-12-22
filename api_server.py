import os
import sys
import shutil
import subprocess
import requests  # 新增
import json
from pathlib import Path
from datetime import date, datetime, timedelta # 修改引入
from urllib.parse import urlencode # 新增
from typing import Optional, Dict

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from dotenv import dotenv_values, set_key

# 确保 run_crawler.py 在同一目录下
from run_crawler import run_crawler, crawl_only, ai_enhance_only

# 定义.env文件路径
ENV_FILE_PATH = Path(".env")

app = FastAPI(title="Arxiv Crawler API")

# ================= AI News 配置区 (来自 ai-news.py) =================
FOLO_COOKIE = '_ga=GA1.1.1065032222.1765972037; __Secure-better-auth.session_token=Tm8GbaPfpjm76RdIfisLzH9fDCZXmtui.WMHV0N8Zl4g5QZcusOcPPrgMiYEOM42NUSIuMuYIoG4%3D; better-auth.last_used_login_method=google; _ga_DZMBZBW3EC=GS2.1.s1766148703$o5$g0$t1766148703$j60$l0$h0$dkQvIXXsKrhPb70OcEyGDXV57OjqJ1j9j8A; ph_phc_EZGEvBt830JgBHTiwpHqJAEbWnbv63m5UpreojwEWNL_posthog=%7B%22distinct_id%22%3A%22224082579282124800%22%2C%22%24sesid%22%3A%5B1766151439162%2C%22019b36aa-6466-7704-a3df-773ccc4c93b8%22%2C1766148695141%5D%2C%22%24epp%22%3Atrue%2C%22%24initial_person_info%22%3A%7B%22r%22%3A%22https%3A%2F%2Fgithub.com%2Fjustlovemaki%2FCloudFlare-AI-Insight-Daily%22%2C%22u%22%3A%22https%3A%2F%2Fapp.folo.is%2F%22%7D%7D'

HEADERS_FOLO = {
    'Cookie': FOLO_COOKIE,
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://app.folo.is/',
    'Origin': 'https://app.folo.is',
    'Content-Type': 'application/json',
    'Accept': 'application/json'
}

HEADERS_GITHUB = {
    'User-Agent': 'python-requests/n8n-debugger'
}

# ================= 数据模型定义 =================
class CrawlRequest(BaseModel):
    all_mode: bool = False
    date_set: Optional[str] = None # 格式 YYYY-MM-DD

class EnvVarUpdate(BaseModel):
    env_vars: Dict[str, str]

class SingleEnvVarUpdate(BaseModel):
    value: str

# ================= 原有接口 =================

@app.get("/")
def health_check():
    return {"status": "online", "system": "Docker Container"}

@app.get("/env-manager")
def env_manager():
    return FileResponse("env_manager.html")

@app.get("/env-vars")
def get_env_vars():
    env_vars = dotenv_values(ENV_FILE_PATH)
    return {"env_vars": env_vars}

@app.get("/env-vars/example")
def get_env_vars_example():
    example_env_path = Path(".env.example")
    if example_env_path.exists():
        example_vars = dotenv_values(example_env_path)
        return {"example_env_vars": example_vars}
    else:
        raise HTTPException(status_code=404, detail=".env.example file not found")

@app.post("/run-crawler")
def trigger_crawler(request: CrawlRequest):
    print(f"收到完整流程请求: {request}")
    target_date = request.date_set if request.date_set else date.today().strftime("%Y-%m-%d")
    try:
        success = run_crawler(all=request.all_mode, date_set=target_date)
        if success:
            return {"status": "success", "message": f"完整流程完成: {target_date}", "generated_files_path": os.path.abspath("./data")}
        else:
            raise HTTPException(status_code=500, detail="完整流程执行内部错误")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/crawl-only")
def trigger_crawl_only(request: CrawlRequest):
    print(f"收到仅爬取请求: {request}")
    target_date = request.date_set if request.date_set else date.today().strftime("%Y-%m-%d")
    try:
        success = crawl_only(all=request.all_mode, date_set=target_date)
        if success:
            return {"status": "success", "message": f"仅爬取完成: {target_date}", "generated_files_path": os.path.abspath("./data")}
        else:
            raise HTTPException(status_code=500, detail="仅爬取执行内部错误")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ai-enhance-only")
def trigger_ai_enhance_only(request: CrawlRequest):
    print(f"收到仅AI增强请求: {request}")
    target_date = request.date_set if request.date_set else date.today().strftime("%Y-%m-%d")
    try:
        success = ai_enhance_only(date_set=target_date)
        if success:
            return {"status": "success", "message": f"仅AI增强完成: {target_date}", "generated_files_path": os.path.abspath("./data")}
        else:
            raise HTTPException(status_code=500, detail="仅AI增强执行内部错误")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/env-vars")
def update_env_vars(env_update: EnvVarUpdate):
    try:
        if not ENV_FILE_PATH.exists():
            with open(ENV_FILE_PATH, 'w') as f: pass
        existing_env_vars = dotenv_values(ENV_FILE_PATH)
        updated_vars = []
        for key, value in env_update.env_vars.items():
            set_key(str(ENV_FILE_PATH), key, value)
            os.environ[key] = value
            updated_vars.append(key)
        return {"status": "success", "message": f"成功更新 {len(updated_vars)} 个环境变量", "updated_vars": updated_vars}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/env-vars/{var_name}")
def update_single_env_var(var_name: str, env_update: SingleEnvVarUpdate):
    try:
        if not ENV_FILE_PATH.exists():
            with open(ENV_FILE_PATH, 'w') as f: pass
        set_key(str(ENV_FILE_PATH), var_name, env_update.value)
        os.environ[var_name] = env_update.value
        return {"status": "success", "message": f"成功更新环境变量 {var_name}", "updated_var": var_name, "value": env_update.value}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/run-git-sync")
def run_git_sync():
    today_str = date.today().strftime("%Y-%m-%d")
    print(f"🚀 开始执行 Git 同步任务: {today_str}")
    src_data = Path("/app/data")
    src_assets = Path("/app/assets/file-list.txt")
    git_repo = Path("/app/git_repo")
    dest_data = git_repo / "data"
    dest_assets = git_repo / "assets"

    if src_assets.exists():
        dest_assets.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_assets, dest_assets / "file-list.txt")
        print("✅ file-list.txt 已更新")

    if src_data.exists():
        dest_data.mkdir(parents=True, exist_ok=True)
        for file in src_data.glob(f"*{today_str}*.jsonl"):
            shutil.copy2(file, dest_data / file.name)
            print(f"✅ 已复制: {file.name}")

    try:
        subprocess.run(["git", "config", "--global", "--add", "safe.directory", "/app/git_repo"], check=True)
        subprocess.run(["git", "config", "user.email", "bot@n8n.docker"], cwd=git_repo)
        subprocess.run(["git", "config", "user.name", "ArxivBot"], cwd=git_repo)
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True)
        status = subprocess.run(["git", "status", "--porcelain"], cwd=git_repo, capture_output=True, text=True)
        if not status.stdout.strip():
            return {"status": "skipped", "message": "没有文件变化，无需提交"}
        subprocess.run(["git", "commit", "-m", f"Auto-update: {today_str}"], cwd=git_repo, check=True)
        env_token = os.environ.get("GIT_TOKEN")
        env_user = os.environ.get("GIT_USERNAME")
        env_repo = os.environ.get("GIT_REPO_URL")
        if env_token and env_repo:
            clean_repo = env_repo.replace("https://", "")
            auth_url = f"https://{env_user}:{env_token}@{clean_repo}"
            print("📤 正在推送到远程仓库...")
            subprocess.run(["git", "push", auth_url, "main"], cwd=git_repo, check=True)
            return {"status": "success", "message": "Git Push 成功！"}
        else:
            return {"status": "warning", "message": "环境变量未配置 Token，仅完成本地提交"}
    except subprocess.CalledProcessError as e:
        print(f"❌ Git Error: {e}")
        return {"status": "error", "message": str(e)}
    except Exception as e:
        print(f"❌ Unknown Error: {e}")
        return {"status": "error", "message": str(e)}

# ================= 新增 AI News 接口 (集成 ai-news.py) =================

@app.get("/fetch-ai-news")
def fetch_ai_news():
    """
    抓取 AI News (GitHub, Folo, Twitter, Reddit) 并返回 JSON
    """
    print("🚀 收到抓取 AI News 请求...")
    
    tasks = [
        {
            'name': 'GitHub Trending',
            'url': f"https://api.github.com/search/repositories?q=created:>{(datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')}&sort=stars&order=desc&per_page=10",
            'method': 'GET',
            'type': 'project',
            'headers': HEADERS_GITHUB,
            'body': None
        },
        {
            'name': 'News Aggregator',
            'url': 'https://api.follow.is/entries',
            'method': 'POST',
            'type': 'news',
            'headers': HEADERS_FOLO,
            'body': {"listId": "158437828119024640", "view": 1, "withContent": True}
        },
        {
            'name': 'HGPapers',
            'url': 'https://api.follow.is/entries',
            'method': 'POST',
            'type': 'paper',
            'headers': HEADERS_FOLO,
            'body': {"listId": "158437917409783808", "view": 1, "withContent": True}
        },
        {
            'name': 'Twitter',
            'url': 'https://api.follow.is/entries',
            'method': 'POST',
            'type': 'socialMedia',
            'headers': HEADERS_FOLO,
            'body': {"listId": "153028784690326528", "view": 1, "withContent": True}
        },
        {
            'name': 'Reddit',
            'url': 'https://api.follow.is/entries',
            'method': 'POST',
            'type': 'socialMedia',
            'headers': HEADERS_FOLO,
            'body': {"listId": "167576006499975168", "view": 1, "withContent": True}
        }
    ]

    all_results = []
    
    for task in tasks:
        print(f"📡 正在抓取: {task['name']} [{task['method']}]")
        try:
            if task['method'] == 'GET':
                resp = requests.get(task['url'], headers=task['headers'], timeout=15)
            else:
                resp = requests.post(task['url'], headers=task['headers'], json=task['body'], timeout=15)
            
            if resp.status_code != 200:
                print(f"   ❌ 失败 (Status: {resp.status_code}): {resp.text[:100]}")
                continue
                
            data = resp.json()
            items_found = 0

            # 1. GitHub 处理
            if task['name'] == 'GitHub Trending' and 'items' in data:
                for repo in data['items']:
                    all_results.append({
                        'title': repo.get('full_name'),
                        'url': repo.get('html_url'),
                        'desc': repo.get('description'),
                        'source': 'GitHub',
                        'tag': '🛠️ Project',
                        'stars': f"⭐ {repo.get('stargazers_count')}"
                    })
                    items_found += 1

            # 2. Folo 处理
            elif 'data' in data and isinstance(data['data'], list):
                for item in data['data']:
                    # Folo 返回的数据通常包裹在 'entries' 对象里，或者直接在 items 里
                    entry = item.get('entries') or item
                    
                    all_results.append({
                        'title': entry.get('title', 'No Title'),
                        'url': entry.get('url', '#'),
                        'desc': (entry.get('content') or entry.get('contentSnippet') or '')[:200],
                        'source': task['name'],
                        'tag': '📄 Paper' if task['type'] == 'paper' else '📰 News'
                    })
                    items_found += 1
            
            print(f"   ✅ 成功抓取 {items_found} 条数据")

        except Exception as e:
            print(f"   ❌ 异常: {e}")
            # 不抛出异常，继续执行其他任务

    # 构造最终结果
    result_data = {
        "selectedItems": all_results[:50],
        "date": datetime.now().strftime('%Y-%m-%d')
    }
    
    return result_data

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)