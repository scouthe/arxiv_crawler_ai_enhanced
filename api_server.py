import os
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import date
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

# 定义请求的数据模型
class CrawlRequest(BaseModel):
    all_mode: bool = False
    date_set: Optional[str] = None # 格式 YYYY-MM-DD

# 定义环境变量更新请求的数据模型
class EnvVarUpdate(BaseModel):
    env_vars: Dict[str, str]

# 定义单个环境变量更新请求的数据模型
class SingleEnvVarUpdate(BaseModel):
    value: str

@app.get("/")
def health_check():
    return {"status": "online", "system": "Docker Container"}

@app.get("/env-manager")
def env_manager():
    """
    提供环境变量管理的HTML页面
    """
    return FileResponse("env_manager.html")

@app.get("/env-vars")
def get_env_vars():
    """
    获取所有环境变量
    """
    # 读取.env文件中的环境变量
    env_vars = dotenv_values(ENV_FILE_PATH)
    return {"env_vars": env_vars}

@app.get("/env-vars/example")
def get_env_vars_example():
    """
    获取环境变量示例
    """
    # 读取.env.example文件中的示例环境变量
    example_env_path = Path(".env.example")
    if example_env_path.exists():
        example_vars = dotenv_values(example_env_path)
        return {"example_env_vars": example_vars}
    else:
        raise HTTPException(status_code=404, detail=".env.example file not found")

@app.post("/run-crawler")
def trigger_crawler(request: CrawlRequest):
    """
    同步执行完整流程：爬取 + AI增强
    """
    print(f"收到完整流程请求: {request}")
    
    # 获取日期，如果没有提供则默认为今天
    target_date = request.date_set if request.date_set else date.today().strftime("%Y-%m-%d")
    
    try:
        # 调用完整流程函数
        success = run_crawler(all=request.all_mode, date_set=target_date)
        
        if success:
            return {
                "status": "success", 
                "message": f"完整流程完成: {target_date}",
                "generated_files_path": os.path.abspath("./data")
            }
        else:
            raise HTTPException(status_code=500, detail="完整流程执行内部错误")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/crawl-only")
def trigger_crawl_only(request: CrawlRequest):
    """
    仅执行爬取，不进行AI增强
    """
    print(f"收到仅爬取请求: {request}")
    
    # 获取日期，如果没有提供则默认为今天
    target_date = request.date_set if request.date_set else date.today().strftime("%Y-%m-%d")
    
    try:
        # 调用仅爬取函数
        success = crawl_only(all=request.all_mode, date_set=target_date)
        
        if success:
            return {
                "status": "success", 
                "message": f"仅爬取完成: {target_date}",
                "generated_files_path": os.path.abspath("./data")
            }
        else:
            raise HTTPException(status_code=500, detail="仅爬取执行内部错误")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ai-enhance-only")
def trigger_ai_enhance_only(request: CrawlRequest):
    """
    仅执行AI增强，对已有的爬取结果
    """
    print(f"收到仅AI增强请求: {request}")
    
    # 获取日期，如果没有提供则默认为今天
    target_date = request.date_set if request.date_set else date.today().strftime("%Y-%m-%d")
    
    try:
        # 调用仅AI增强函数
        success = ai_enhance_only(date_set=target_date)
        
        if success:
            return {
                "status": "success", 
                "message": f"仅AI增强完成: {target_date}",
                "generated_files_path": os.path.abspath("./data")
            }
        else:
            raise HTTPException(status_code=500, detail="仅AI增强执行内部错误")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/env-vars")
def update_env_vars(env_update: EnvVarUpdate):
    """
    批量更新环境变量
    """
    try:
        # 确保.env文件存在
        if not ENV_FILE_PATH.exists():
            with open(ENV_FILE_PATH, 'w') as f:
                pass
        
        # 读取现有的环境变量
        existing_env_vars = dotenv_values(ENV_FILE_PATH)
        
        # 更新环境变量
        updated_vars = []
        for key, value in env_update.env_vars.items():
            # 更新.env文件，确保使用字符串路径
            set_key(str(ENV_FILE_PATH), key, value)
            # 更新系统环境变量（使当前进程生效）
            os.environ[key] = value
            updated_vars.append(key)
        
        return {
            "status": "success",
            "message": f"成功更新 {len(updated_vars)} 个环境变量",
            "updated_vars": updated_vars
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/env-vars/{var_name}")
def update_single_env_var(var_name: str, env_update: SingleEnvVarUpdate):
    """
    更新单个环境变量
    """
    try:
        # 确保.env文件存在
        if not ENV_FILE_PATH.exists():
            with open(ENV_FILE_PATH, 'w') as f:
                pass
        
        # 更新.env文件，确保使用字符串路径
        set_key(str(ENV_FILE_PATH), var_name, env_update.value)
        
        # 更新系统环境变量（使当前进程生效）
        os.environ[var_name] = env_update.value
        
        return {
            "status": "success",
            "message": f"成功更新环境变量 {var_name}",
            "updated_var": var_name,
            "value": env_update.value
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/run-git-sync")
def run_git_sync():
    """
    触发文件同步和 Git 上传
    """
    today_str = date.today().strftime("%Y-%m-%d")
    print(f"🚀 开始执行 Git 同步任务: {today_str}")

    # --- 1. 定义路径 ---
    src_data = Path("/app/data")
    src_assets = Path("/app/assets/file-list.txt")
    
    # Git 仓库的地方
    git_repo = Path("/app/git_repo")
    dest_data = git_repo / "data"
    dest_assets = git_repo / "assets"

    # --- 2. 搬运文件 ---
    # 2.1 搬运 file-list.txt
    if src_assets.exists():
        dest_assets.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_assets, dest_assets / "file-list.txt")
        print("✅ file-list.txt 已更新")

    # 2.2 搬运今天的 jsonl 文件
    if src_data.exists():
        dest_data.mkdir(parents=True, exist_ok=True)
        # 查找文件名包含今天日期的文件
        for file in src_data.glob(f"*{today_str}*.jsonl"):
            shutil.copy2(file, dest_data / file.name)
            print(f"✅ 已复制: {file.name}")

    # --- 3. 执行 Git 命令 ---
    try:
        # A. 解决 Docker 挂载 Windows 目录的安全报错
        subprocess.run(["git", "config", "--global", "--add", "safe.directory", "/app/git_repo"], check=True)
        
        # B. 配置用户信息
        subprocess.run(["git", "config", "user.email", "bot@n8n.docker"], cwd=git_repo)
        subprocess.run(["git", "config", "user.name", "ArxivBot"], cwd=git_repo)

        # C. Git Add & Commit
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True)
        
        # 检查是否有变动
        status = subprocess.run(["git", "status", "--porcelain"], cwd=git_repo, capture_output=True, text=True)
        if not status.stdout.strip():
            return {"status": "skipped", "message": "没有文件变化，无需提交"}

        subprocess.run(["git", "commit", "-m", f"Auto-update: {today_str}"], cwd=git_repo, check=True)

        # D. Git Push
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

# --- 移动到最后 ---
if __name__ == "__main__":
    import uvicorn
    # host="0.0.0.0" 极其重要，允许外部（包括 Docker 容器）访问
    uvicorn.run(app, host="0.0.0.0", port=8000)