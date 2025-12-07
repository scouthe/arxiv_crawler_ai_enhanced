# api_server.py
import os
import sys
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from datetime import date

# 导入你原本的爬虫逻辑
# 确保 run_crawler.py 在同一目录下
from run_crawler import run_crawler

app = FastAPI(title="Arxiv Crawler API")

# 定义请求的数据模型
class CrawlRequest(BaseModel):
    all_mode: bool = False
    date_set: Optional[str] = None # 格式 YYYY-MM-DD

@app.get("/")
def health_check():
    return {"status": "online", "system": "Windows Host"}

@app.post("/run-crawler")
def trigger_crawler(request: CrawlRequest):
    """
    同步执行爬虫。
    注意：如果爬虫运行时间超过 n8n 的 HTTP 超时时间（默认 5分钟），
    n8n 可能会报错 Timeout。
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
                "generated_files_path": os.path.abspath("./data") # 告诉 n8n 文件在哪
            }
        else:
            raise HTTPException(status_code=500, detail="爬虫执行内部错误")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 可选：如果你怕 n8n 超时，可以使用后台任务模式
@app.post("/run-crawler-background")
def trigger_crawler_bg(request: CrawlRequest, background_tasks: BackgroundTasks):
    """
    异步后台执行。n8n 会立刻收到 'Started' 响应，不会等待爬虫结束。
    """
    target_date = request.date_set if request.date_set else date.today().strftime("%Y-%m-%d")
    
    # 将任务加入后台队列
    background_tasks.add_task(run_crawler, all=request.all_mode, date_set=target_date)
    
    return {"status": "started", "message": "爬虫已在后台开始运行"}

if __name__ == "__main__":
    import uvicorn
    # host="0.0.0.0" 极其重要，允许外部（包括 Docker 容器）访问
    uvicorn.run(app, host="0.0.0.0", port=8000)