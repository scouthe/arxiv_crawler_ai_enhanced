# 使用 Python 官方镜像作为基础
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制你的代码和爬虫子目录
# 注意：需要确保 run_crawler.py, api_server.py, arxiv_crawler 都在当前目录或子目录
COPY . /app

# 暴露 FastAPI 端口
EXPOSE 8000

# 定义启动命令
CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000"]