#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调用arxiv crawler爬虫，生成JSONL文件并更新assets/file-list.txt

这个脚本会：
1. 调用arxiv crawler爬取指定日期的论文
2. 生成标准JSONL文件和AI增强的JSONL文件
3. 将生成的文件路径添加到assets/file-list.txt
"""

import os
import sys
from datetime import date, timedelta
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
if os.path.exists('.env'):
    load_dotenv(override=False)

# 添加arxiv_crawler目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'arxiv_crawler'))

from arxiv_crawler import ArxivScraper

def run_crawler(all=False, date_set=None):
    """
    运行arxiv爬虫，生成JSONL文件并更新assets/file-list.txt
    
    Args:
        all (bool): 是否全量更新，默认为False
        date_set (str): 要爬取的日期，格式为YYYY-MM-DD，默认为今天的日期
    """
    # 从环境变量读取配置
    env_all = os.environ.get("CRAWL_ALL", "false").lower()
    env_date = os.environ.get("CRAWL_DATE", "")
    env_max_workers = os.environ.get("MAX_WORKERS", "4")
    env_category_blacklist = os.environ.get("CATEGORY_BLACKLIST", "")
    env_category_whitelist = os.environ.get("CATEGORY_WHITELIST", "")
    env_optional_keywords = os.environ.get("OPTIONAL_KEYWORDS", "")
    env_trans_to = os.environ.get("TRANS_TO", "")
    env_proxy = os.environ.get("PROXY", "")
    env_step = os.environ.get("STEP", "")
    
    # 打印环境变量
    print("\n--- 环境变量配置 ---")
    print(f"CRAWL_ALL: {env_all}")
    print(f"CRAWL_DATE: {env_date}")
    print(f"MAX_WORKERS: {env_max_workers}")
    print(f"CATEGORY_BLACKLIST: {env_category_blacklist}")
    print(f"CATEGORY_WHITELIST: {env_category_whitelist}")
    print(f"OPTIONAL_KEYWORDS: {env_optional_keywords}")
    print(f"TRANS_TO: {env_trans_to}")
    print(f"PROXY: {env_proxy}")
    print(f"STEP: {env_step}")
    print("------------------\n")
    
    # 优先使用函数参数，其次使用环境变量，最后使用默认值
    crawl_all = all if all is not None else (env_all == "true" or env_all == "1")
    crawl_date = date_set if date_set is not None else (env_date if env_date else date.today().strftime("%Y-%m-%d"))
    max_workers = int(env_max_workers) if env_max_workers.isdigit() else 4
    
    print(f"开始爬取 {crawl_date} 的论文数据，模式：{'全量更新' if crawl_all else '增量更新'}，AI并行数：{max_workers}")
    
    # 创建ArxivScraper实例
    # 大部分参数已从环境变量读取，这里只需要传递日期范围
    scraper = ArxivScraper(
        date_from=crawl_date,
        date_until=crawl_date
    )
    if crawl_all:
        # 当月全量更新
        import asyncio
        asyncio.run(scraper.fetch_all())
        
        print(f"生成markdown文件...")
        scraper.to_markdown(meta=True)

        # 生成JSONL文件
        print(f"生成标准JSONL文件...")
        scraper.to_jsonl(output_dir="./data", filename_format="%Y-%m-%d")
        
        # 生成AI增强的JSONL文件（如果失败，继续执行）
        print(f"生成AI增强的JSONL文件...")
        try:
            scraper.to_ai_enhanced_jsonl(output_dir="./data", filename_format="%Y-%m-%d", max_workers=max_workers)
        except Exception as e:
            print(f"生成AI增强的JSONL文件失败，但将继续执行: {e}")
        
        # 更新assets/file-list.txt
        print(f"更新assets/file-list.txt...")
        update_file_list(crawl_date)
        
        print(f"爬取和生成完成！")
    else:
        # 当天增量更新
        try:
            # fetch_update()是同步方法，不需要使用asyncio.run
            scraper.fetch_update()
            
            print(f"生成markdown文件...")
            scraper.to_markdown(meta=True)

            # 生成JSONL文件
            print(f"生成标准JSONL文件...")
            scraper.to_jsonl(output_dir="./data", filename_format="%Y-%m-%d")
            
            # 生成AI增强的JSONL文件（如果失败，继续执行）
            print(f"生成AI增强的JSONL文件...")
            try:
                scraper.to_ai_enhanced_jsonl(output_dir="./data", filename_format="%Y-%m-%d", max_workers=max_workers)
            except Exception as e:
                print(f"生成AI增强的JSONL文件失败，但将继续执行: {e}")
            
            # 更新assets/file-list.txt
            print(f"更新assets/file-list.txt...")
            update_file_list(crawl_date)
            
            print(f"爬取和生成完成！")
            
        except Exception as e:
            print(f"爬取过程中发生错误: {e}")
            import traceback
            traceback.print_exc()
            return False
            
    return True

def update_file_list(date_str):
    """
    更新assets/file-list.txt文件，添加新生成的JSONL文件路径
    
    Args:
        date_str (str): 日期，格式为YYYY-MM-DD
    """
    # 定义文件路径
    file_list_path = Path("./assets/file-list.txt")
    
    # 确保assets目录存在
    file_list_path.parent.mkdir(exist_ok=True)
    
    # 读取现有文件列表
    existing_files = set()
    if file_list_path.exists():
        with open(file_list_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    existing_files.add(line)
    
    # 添加新生成的文件
    new_files = []
    
    # 添加标准JSONL文件
    standard_jsonl = f"{date_str}.jsonl"
    new_files.append(standard_jsonl)
    
    # 添加AI增强的JSONL文件（英文和中文）
    for lang in ["English", "Chinese"]:
        ai_enhanced_jsonl = f"{date_str}_AI_enhanced_{lang}.jsonl"
        new_files.append(ai_enhanced_jsonl)
    
    # 将新文件添加到现有集合中
    existing_files.update(new_files)
    
    # 按日期排序（最新的在前面）
    sorted_files = sorted(existing_files, reverse=True)
    
    # 写回文件
    with open(file_list_path, 'w', encoding='utf-8') as f:
        for file_name in sorted_files:
            f.write(f"{file_name}\n")
    
    print(f"已更新file-list.txt，添加了 {len(new_files)} 个新文件")

if __name__ == "__main__":
    # 解析命令行参数
    import argparse
    
    parser = argparse.ArgumentParser(description="运行arxiv crawler爬虫，生成JSONL文件并更新assets/file-list.txt")
    parser.add_argument('--all', action='store_true', default=False, help='爬取当月全部信息，还是只爬取当天信息')
    parser.add_argument('--date', type=str, help='指定要爬取的日期，格式为YYYY-MM-DD。')
    
    args = parser.parse_args()
    
    # 运行爬虫
    success = run_crawler(args.all, args.date)
    
    # 设置退出码
    sys.exit(0 if success else 1)
