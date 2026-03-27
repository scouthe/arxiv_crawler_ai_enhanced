import os
import shutil
import subprocess
from datetime import date
from pathlib import Path

from dotenv import load_dotenv


_PROJECT_ROOT = Path(__file__).resolve().parent
_DOTENV_PATH = _PROJECT_ROOT / ".env"
if _DOTENV_PATH.exists():
    # 不覆盖进程中已注入的环境变量，保证外部显式配置优先。
    load_dotenv(_DOTENV_PATH, override=False)


def run_git_sync_internal(today_str: str | None = None) -> dict:
    """
    同步 data/file-list 到 git_repo 并提交推送。
    默认行为与原 /run-git-sync 接口保持一致，但显式排除 papers.db。
    """
    if today_str is None:
        today_str = date.today().strftime("%Y-%m-%d")

    src_root_raw = os.environ.get("GIT_SYNC_SRC_ROOT")
    git_repo_raw = os.environ.get("GIT_SYNC_REPO_PATH")
    missing_keys = []
    if not src_root_raw:
        missing_keys.append("GIT_SYNC_SRC_ROOT")
    if not git_repo_raw:
        missing_keys.append("GIT_SYNC_REPO_PATH")
    if missing_keys:
        return {"status": "error", "message": f"缺少必要环境变量: {', '.join(missing_keys)}"}

    src_root = Path(src_root_raw).expanduser().resolve()
    git_repo = Path(git_repo_raw).expanduser().resolve()
    same_repo_mode = src_root == git_repo

    src_data = src_root / "data"
    src_assets = src_root / "assets" / "file-list.txt"
    dest_data = git_repo / "data"
    dest_assets = git_repo / "assets"
    stage_targets = ["data", "assets/file-list.txt"]

    if not src_root.exists():
        return {"status": "error", "message": f"src_root 不存在: {src_root}"}

    if not git_repo.exists():
        return {"status": "error", "message": f"git_repo 不存在: {git_repo}"}

    if same_repo_mode:
        print("ℹ️ GIT_SYNC_SRC_ROOT 与 GIT_SYNC_REPO_PATH 相同，跳过镜像复制，直接在当前仓库提交。")
    else:
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
        # papers.db 已被 .gitignore 忽略，但如果用户此前手动 stage 过，也要在自动提交里剔除。
        subprocess.run(["git", "restore", "--staged", "--", "papers.db"], cwd=git_repo, check=False)
        # 仅提交数据相关路径，避免将仓库中其他改动一起提交。
        subprocess.run(["git", "add", "-A", "--", *stage_targets], cwd=git_repo, check=True)

        staged = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            cwd=git_repo,
            capture_output=True,
            text=True,
            check=True,
        )
        if not staged.stdout.strip():
            return {
                "status": "skipped",
                "message": "目标路径无变化，无需提交",
                "targets": stage_targets,
            }

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
        # 兼容历史行为：未配置 GIT_* 时，尝试使用本机已登录凭据推送 origin。
        try:
            print("📤 未配置 GIT_TOKEN，尝试使用 origin 凭据推送...")
            subprocess.run(["git", "push", "origin", "main"], cwd=git_repo, check=True)
            return {"status": "success", "message": "Git Push 成功！（origin）"}
        except subprocess.CalledProcessError:
            return {"status": "warning", "message": "未配置 GIT_TOKEN 或 origin 凭据不可用，仅完成本地提交"}
    except subprocess.CalledProcessError as e:
        print(f"❌ Git Error: {e}")
        return {"status": "error", "message": str(e)}
    except Exception as e:
        print(f"❌ Unknown Error: {e}")
        return {"status": "error", "message": str(e)}
