import os
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel

# 确保 run_crawler.py 在同一目录下
from run_crawler import run_crawler

app = FastAPI(title="Arxiv Crawler API")

# 定义请求的数据模型
class CrawlRequest(BaseModel):
    all_mode: bool = False
    date_set: Optional[str] = None # 格式 YYYY-MM-DD

@app.get("/")
def health_check():
    return {"status": "online", "system": "Docker Container"}

@app.post("/run-crawler")
def trigger_crawler(request: CrawlRequest):
    """
    同步执行爬虫。
    """
    print(f"收到爬虫请求: {request}")
    
    # 获取日期，如果没有提供则默认为今天
    target_date = request.date_set if request.date_set else date.today().strftime("%Y-%m-%d")
    
    try:
        # 调用你原来的 run_crawler 函数
        success = run_crawler(all=request.all_mode, date_set=target_date)
        
        if success:
            return {
                "status": "success", 
                "message": f"爬取完成: {target_date}",
                "generated_files_path": os.path.abspath("./data")
            }
        else:
            raise HTTPException(status_code=500, detail="爬虫执行内部错误")
            
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