import os
import shutil
import subprocess
from datetime import date
from pathlib import Path


def run_git_sync_internal(today_str: str | None = None) -> dict:
    """
    同步 data/file-list/papers.db 到 git_repo 并提交推送。
    默认行为与原 /run-git-sync 接口保持一致。
    """
    if today_str is None:
        today_str = date.today().strftime("%Y-%m-%d")

    src_root = Path(os.environ.get("GIT_SYNC_SRC_ROOT", "/app"))
    git_repo = Path(os.environ.get("GIT_SYNC_REPO_PATH", "/app/git_repo"))

    src_data = src_root / "data"
    src_assets = src_root / "assets" / "file-list.txt"
    src_db = src_root / "papers.db"

    dest_data = git_repo / "data"
    dest_assets = git_repo / "assets"
    dest_db = git_repo / "papers.db"

    if not git_repo.exists():
        return {"status": "error", "message": f"git_repo 不存在: {git_repo}"}

    if src_db.exists():
        shutil.copy2(src_db, dest_db)
        print("✅ papers.db 已更新到 git_repo")

    if src_assets.exists():
        dest_assets.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_assets, dest_assets / "file-list.txt")
        print("✅ file-list.txt 已更新")

    if src_data.exists():
        dest_data.mkdir(parents=True, exist_ok=True)

        src_rel_files = set()
        for src_file in src_data.rglob("*"):
            if src_file.is_file():
                rel = src_file.relative_to(src_data)
                src_rel_files.add(rel)
                target_file = dest_data / rel
                target_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, target_file)
                print(f"✅ 已同步: data/{rel}")

        for dest_file in dest_data.rglob("*"):
            if dest_file.is_file():
                rel = dest_file.relative_to(dest_data)
                if rel not in src_rel_files:
                    dest_file.unlink()
                    print(f"🗑️ 已删除: data/{rel}")

    try:
        subprocess.run(["git", "config", "--global", "--add", "safe.directory", str(git_repo)], check=True)
        subprocess.run(["git", "config", "user.email", "bot@n8n.docker"], cwd=git_repo, check=True)
        subprocess.run(["git", "config", "user.name", "ArxivBot"], cwd=git_repo, check=True)
        subprocess.run(["git", "add", "."], cwd=git_repo, check=True)

        status = subprocess.run(["git", "status", "--porcelain"], cwd=git_repo, capture_output=True, text=True, check=True)
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

        return {"status": "warning", "message": "环境变量未配置 Token，仅完成本地提交"}
    except subprocess.CalledProcessError as e:
        print(f"❌ Git Error: {e}")
        return {"status": "error", "message": str(e)}
    except Exception as e:
        print(f"❌ Unknown Error: {e}")
        return {"status": "error", "message": str(e)}

