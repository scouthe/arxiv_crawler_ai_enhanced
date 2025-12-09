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

def crawl_only(all=False, date_set=None):
    """
    仅运行arxiv爬虫，生成标准JSONL文件，不执行AI增强
    
    Args:
        all (bool): 是否全量更新，默认为False
        date_set (str): 要爬取的日期，格式为YYYY-MM-DD，默认为今天的日期
    """
    # 从环境变量读取配置
    env_all = os.environ.get("CRAWL_ALL", "false").lower()
    env_date = os.environ.get("CRAWL_DATE", "")
    env_category_blacklist = os.environ.get("CATEGORY_BLACKLIST", "")
    env_category_whitelist = os.environ.get("CATEGORY_WHITELIST", "")
    env_optional_keywords = os.environ.get("OPTIONAL_KEYWORDS", "")
    env_trans_to = os.environ.get("TRANS_TO", "")
    env_proxy = os.environ.get("PROXY", "")
    env_step = os.environ.get("STEP", "")
    
    # 打印环境变量，隐藏敏感信息
    print("\n--- 环境变量配置 ---")
    print(f"CRAWL_ALL: {env_all}")
    print(f"CRAWL_DATE: {env_date}")
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
    
    print(f"开始爬取 {crawl_date} 的论文数据，模式：{'全量更新' if crawl_all else '增量更新'}")
    
    # 创建ArxivScraper实例
    scraper = ArxivScraper(
        date_from=crawl_date,
        date_until=crawl_date
    )
    
    try:
        if crawl_all:
            # 当月全量更新
            import asyncio
            asyncio.run(scraper.fetch_all())
        else:
            # 当天增量更新
            scraper.fetch_update()
        
            print(f"生成markdown文件...")
            scraper.to_markdown(meta=True)

            # 生成标准JSONL文件
            print(f"生成标准JSONL文件...")
            scraper.to_jsonl(output_dir="./data", filename_format="%Y-%m-%d")
            
            # 更新assets/file-list.txt（仅添加标准JSONL文件）
            print(f"更新assets/file-list.txt...")
            update_file_list(crawl_date)
        
        print(f"爬取完成！")
        return True
    except Exception as e:
        print(f"爬取过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def ai_enhance_only(date_set=None):
    """
    仅对现有数据库中的论文数据执行AI增强，生成AI增强的JSONL文件
    
    Args:
        date_set (str): 要处理的日期，格式为YYYY-MM-DD，默认为今天的日期
    """
    # 从环境变量读取配置
    env_date = os.environ.get("CRAWL_DATE", "")
    env_max_workers = os.environ.get("MAX_WORKERS", "4")
    env_api_key = os.environ.get("OPENAI_API_KEY", "")
    env_base_url = os.environ.get("OPENAI_BASE_URL", "")
    env_model_name = os.environ.get("MODEL_NAME", "")
    env_provider = os.environ.get("PROVIDER", "official")
    
    # 打印环境变量，隐藏敏感信息
    print("\n--- 环境变量配置 ---")
    print(f"CRAWL_DATE: {env_date}")
    print(f"MAX_WORKERS: {env_max_workers}")
    print(f"OPENAI_API_KEY: {'[SET]' if env_api_key else '[NOT SET]'}")
    print(f"OPENAI_BASE_URL: {env_base_url if env_base_url else '[NOT SET]'}")
    print(f"MODEL_NAME: {env_model_name if env_model_name else '[NOT SET]'}")
    print(f"PROVIDER: {env_provider}")
    print("------------------\n")
    
    # 优先使用函数参数，其次使用环境变量，最后使用默认值
    crawl_date = date_set if date_set is not None else (env_date if env_date else date.today().strftime("%Y-%m-%d"))
    max_workers = int(env_max_workers) if env_max_workers.isdigit() else 4
    
    print(f"开始对 {crawl_date} 的论文数据执行AI增强，并行数：{max_workers}")
    
    try:
        # 创建ArxivScraper实例，直接从数据库获取数据
        scraper = ArxivScraper(
            date_from=crawl_date,
            date_until=crawl_date
        )
        
        # 生成AI增强的JSONL文件
        print(f"生成AI增强的JSONL文件...")
        scraper.to_ai_enhanced_jsonl(output_dir="./data", filename_format="%Y-%m-%d", max_workers=max_workers,provider=env_provider)
        
        # 更新assets/file-list.txt（添加AI增强的JSONL文件）
        print(f"更新assets/file-list.txt...")
        update_file_list(crawl_date)
        
        print(f"AI增强完成！")
        return True
    except Exception as e:
        print(f"生成AI增强的JSONL文件失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_crawler(all=False, date_set=None):
    """
    运行完整流程：arxiv爬虫 + AI增强 + 文件列表更新
    
    Args:
        all (bool): 是否全量更新，默认为False
        date_set (str): 要爬取的日期，格式为YYYY-MM-DD，默认为今天的日期
    """
    # 从环境变量读取配置
    env_all = os.environ.get("CRAWL_ALL", "false").lower()
    env_date = os.environ.get("CRAWL_DATE", "")
    env_max_workers = os.environ.get("MAX_WORKERS", "4")
    
    # 优先使用函数参数，其次使用环境变量，最后使用默认值
    crawl_all = all if all is not None else (env_all == "true" or env_all == "1")
    crawl_date = date_set if date_set is not None else (env_date if env_date else date.today().strftime("%Y-%m-%d"))
    max_workers = int(env_max_workers) if env_max_workers.isdigit() else 4
    
    print(f"开始完整流程：爬取 + AI增强，日期：{crawl_date}，模式：{'全量更新' if crawl_all else '增量更新'}")
    
    # 首先执行爬取
    if not crawl_only(all=crawl_all, date_set=crawl_date):
        print("爬取失败，终止完整流程")
        return False
    
    # 然后执行AI增强
    if not ai_enhance_only(date_set=crawl_date):
        print("AI增强失败，但爬取已完成")
        return True
    
    print(f"完整流程完成！")
    return True

def update_file_list(date_str):
    """
    更新assets/file-list.txt文件，添加新生成的JSONL文件路径
    
    Args:
        date_str (str): 日期，格式为YYYY-MM-DD
    """
    # 定义文件路径
    file_list_path = Path("./assets/file-list.txt")
    data_dir = Path("./data")
    
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
    if (data_dir / standard_jsonl).exists():
        new_files.append(standard_jsonl)
    
    # 检查并添加实际存在的AI增强JSONL文件
    # 先检查中文版本（默认生成的）
    chinese_ai_jsonl = f"{date_str}_AI_enhanced_Chinese.jsonl"
    if (data_dir / chinese_ai_jsonl).exists():
        new_files.append(chinese_ai_jsonl)
    
    # 再检查英文版本（如果有生成的话）
    english_ai_jsonl = f"{date_str}_AI_enhanced_English.jsonl"
    if (data_dir / english_ai_jsonl).exists():
        new_files.append(english_ai_jsonl)
    
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
    # success = crawl_only(args.all, args.date)
    success = ai_enhance_only( args.date)
    
    # 设置退出码
    sys.exit(0 if success else 1)
