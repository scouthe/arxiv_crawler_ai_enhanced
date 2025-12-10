import asyncio
import csv
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, fields
from datetime import datetime, timedelta, UTC
from pathlib import Path

from rich.console import Console
from typing_extensions import Iterable

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from async_translator import async_translate
from categories import parse_categories



@dataclass
class Paper:
    first_submitted_date: datetime
    title: str
    categories: list
    url: str
    authors: str
    abstract: str
    comments: str
    title_translated: str | None = None
    abstract_translated: str | None = None
    first_announced_date: datetime | None = None
    ai_content: dict | None = None  # AI生成的内容
    
    @property
    def id(self):
        """从URL提取论文ID"""
        return self.url.split("/")[-1]
    
    @property
    def pdf(self):
        """生成PDF链接"""
        return self.url.replace("https://arxiv.org/abs", "https://arxiv.org/pdf")
    
    @property
    def summary(self):
        """摘要的别名，与JSONL字段名一致"""
        return self.abstract
    
    @property
    def comment(self):
        """评论的别名，与JSONL字段名一致"""
        return self.comments
    
    @property
    def abs(self):
        """arXiv链接的别名，与JSONL字段名一致"""
        return self.url
    
    def to_jsonl_dict(self):
        """转换为JSONL格式的字典"""
        import re
        
        # 修复作者字段：处理不同格式的作者字符串
        authors_str = self.authors
        if authors_str == "No authors":
            authors_list = []
        else:
            # 移除可能的空格，并正确分割作者列表
            authors_list = [author.strip() for author in re.split(r',\s*', authors_str)]
        
        # 处理评论字段：如果是"No comments"则转换为None，与daily项目格式一致
        comment_value = self.comments if self.comments != "No comments" else None
        
        # 构建JSON结构
        json_data = {
            "id": self.id,
            "pdf": self.pdf,
            "abs": self.abs,
            "authors": authors_list,
            "title": self.title,
            "categories": self.categories,
            "comment": comment_value,
            "summary": self.summary
        }
        
        # 如果有AI内容，添加到JSON中
        if self.ai_content:
            json_data["AI"] = self.ai_content
        
        return json_data

    @classmethod
    def from_row(cls, row: sqlite3.Row):
        import json
        
        # 处理ai_content字段
        ai_content = None
        ai_content_value = row["ai_content"] if "ai_content" in dict(row) else None
        if ai_content_value:
            try:
                ai_content = json.loads(ai_content_value)
            except json.JSONDecodeError:
                ai_content = None
        
        # 使用dict(row)将Row对象转换为普通字典，然后检查字段是否存在
        row_dict = dict(row)
        
        # 处理可能缺失的字段
        title_translated = row_dict.get("title_translated")
        abstract_translated = row_dict.get("abstract_translated")
        
        return cls(
            first_submitted_date=datetime.strptime(row_dict["first_submitted_date"], "%Y-%m-%d"),
            title=row_dict["title"],
            categories=row_dict["categories"].split(","),
            url=row_dict["url"],
            authors=row_dict["authors"],
            abstract=row_dict["abstract"],
            comments=row_dict["comments"],
            title_translated=title_translated,
            abstract_translated=abstract_translated,
            first_announced_date=datetime.strptime(row_dict["first_announced_date"], "%Y-%m-%d"),
            ai_content=ai_content,
        )
    @property
    def papers_cool_url(self):
        return self.url.replace("https://arxiv.org/abs", "https://papers.cool/arxiv")
    
    @property
    def pdf_url(self):
        return self.url.replace("https://arxiv.org/abs", "https://arxiv.org/pdf")

    def to_markdown(self):
        return f"""【{self.id}】{self.title}
- **标题**: {self.title_translated if self.title_translated else self.title}
- **链接**: {self.url}
> **作者**: {self.authors}
> **摘要**: {self.abstract_translated if self.abstract_translated else self.abstract}
> **Abstract**: {self.abstract}

"""

    async def translate(self, langto="zh-CN"):
        self.title_translated = await async_translate(self.title, langto=langto)
        self.abstract_translated = await async_translate(self.abstract, langto=langto)


@dataclass
class PaperRecord:
    paper: Paper
    comment: str

    def to_markdown(self):
        if self.comment != "-":
            return f"""- [{self.paper.title}]({self.paper.url})
  - **标题**: {self.paper.title_translated}
  - **Filtered Reason**: {self.comment}
"""
        else:
            return self.paper.to_markdown()


class PaperDatabase:
    def __init__(self, db_path="papers.db"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = self._row_factory
        self._create_table()

    @staticmethod
    def _row_factory(cursor, row):
        row = sqlite3.Row(cursor, row)
        # 检查是否是论文数据行
        # 论文数据行应该包含url字段，而表结构查询结果包含cid字段
        row_keys = list(row.keys())
        if 'cid' in row_keys and 'name' in row_keys:  # 这是表结构查询结果
            return row
        elif 'url' in row_keys and 'title' in row_keys:  # 这是论文数据行
            try:
                return Paper.from_row(row)
            except Exception as e:
                # 如果转换失败，返回原始行并输出详细错误信息
                print(f"Warning: Failed to convert row to Paper: {e}, row keys: {row_keys}")
                return row
        else:  # 其他类型的查询结果
            return row

    def _create_table(self):
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS papers (
                    url TEXT PRIMARY KEY,
                    id TEXT NOT NULL,  -- 论文ID，与JSONL字段一致
                    pdf TEXT NOT NULL,  -- PDF链接，与JSONL字段一致
                    authors TEXT NOT NULL,  -- 作者列表，JSON格式存储
                    title_translated TEXT,
                    first_submitted_date DATE NOT NULL,
                    first_announced_date DATE NOT NULL,
                    update_time DATETIME NOT NULL,
                    categories TEXT NOT NULL,
                    title TEXT NOT NULL,
                    comments TEXT,  -- 评论，与JSONL字段一致
                    abstract TEXT NOT NULL,  -- 摘要
                    summary TEXT NOT NULL,  -- 摘要，与JSONL字段一致
                    abstract_translated TEXT,
                    ai_content TEXT  -- AI生成的内容，JSON格式存储
                )
            """
            )
            
            # 检查并添加缺失的列
            self._add_missing_columns()
    
    def _add_missing_columns(self):
        """
        检查并添加缺失的列，确保数据库表结构与代码一致
        """
        with self.conn:
            # 获取当前表结构
            cursor = self.conn.execute("PRAGMA table_info(papers)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # 处理ID列
            if "id" not in columns:
                # 添加允许NULL的列，然后更新现有数据
                self.conn.execute("ALTER TABLE papers ADD COLUMN id TEXT")
                # 更新现有数据，使用正确的SQLite函数提取URL的最后一部分作为论文ID
                self.conn.execute("UPDATE papers SET id = SUBSTR(url, INSTR(url, 'abs/') + 4)")
                print("Added missing column: id")
            
            # 处理pdf列
            if "pdf" not in columns:
                # 添加允许NULL的列，然后更新现有数据
                self.conn.execute("ALTER TABLE papers ADD COLUMN pdf TEXT")
                # 更新现有数据
                self.conn.execute("UPDATE papers SET pdf = REPLACE(url, 'https://arxiv.org/abs', 'https://arxiv.org/pdf')")
                print("Added missing column: pdf")
            
            # 处理summary列
            if "summary" not in columns:
                # 添加允许NULL的列，然后更新现有数据
                self.conn.execute("ALTER TABLE papers ADD COLUMN summary TEXT")
                # 更新现有数据
                self.conn.execute("UPDATE papers SET summary = abstract")
                print("Added missing column: summary")
            
            # 处理其他普通列
            other_columns = {
                "title_translated": "TEXT",
                "abstract_translated": "TEXT",
                "ai_content": "TEXT"
            }
            
            for column_name, column_type in other_columns.items():
                if column_name not in columns:
                    self.conn.execute(
                        f"ALTER TABLE papers ADD COLUMN {column_name} {column_type}"
                    )
                    print(f"Added missing column: {column_name}")

    def add_papers(self, papers: Iterable[Paper]):
        import json
        
        assert all([paper.first_announced_date is not None for paper in papers])
        with self.conn:
            data_to_insert = [
                (
                    paper.url,
                    paper.id,  # 论文ID
                    paper.pdf,  # PDF链接
                    paper.authors,
                    paper.title_translated,  # 标题翻译
                    paper.first_submitted_date.strftime("%Y-%m-%d"),  # 首次提交日期
                    paper.first_announced_date.strftime("%Y-%m-%d"),  # 首次公布日期
                    datetime.now(UTC).replace(tzinfo=None),  # 更新时间
                    ",".join(paper.categories),  # 类别列表
                    paper.title,  # 标题
                    paper.comments,  # 评论
                    paper.abstract,  # 摘要
                    paper.summary,  # 摘要，与JSONL字段一致
                    paper.abstract_translated,  # 摘要翻译
                    json.dumps(paper.ai_content) if paper.ai_content else None  # AI内容
                )
                for paper in papers
            ]
            self.conn.executemany(
                """
                INSERT OR REPLACE INTO papers 
                (url, id, pdf, authors, title_translated, first_submitted_date, first_announced_date, update_time, categories, title, comments, abstract, summary, abstract_translated, ai_content)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                data_to_insert,
            )

    def count_new_papers(self, papers: Iterable[Paper]) -> int:
        cnt = 0
        for paper in papers:
            with self.conn:
                cursor = self.conn.execute(
                    """
                    SELECT * FROM papers WHERE url = ?
                    """,
                    (paper.url,),
                )
                if cursor.fetchone():
                    break
                else:
                    cnt += 1
        return cnt

    def fetch_papers_on_date(self, date: datetime) -> list[Paper]:
        with self.conn:
            cursor = self.conn.execute(
                """
                SELECT * FROM papers WHERE first_announced_date = ?
                """,
                (date.strftime("%Y-%m-%d"),),
            )
            return cursor.fetchall()
    
    def fetch_jsonl_data_on_date(self, date: datetime) -> list[dict]:
        """
        直接从数据库获取符合JSONL格式的数据，不需要转换
        
        Args:
            date (datetime): 日期
            
        Returns:
            list[dict]: 符合JSONL格式的数据列表
        """
        import re
        
        with self.conn:
            cursor = self.conn.execute(
                """
                SELECT * FROM papers WHERE first_announced_date = ?
                """,
                (date.strftime("%Y-%m-%d"),),
            )
            papers = cursor.fetchall()
            
            jsonl_data = []
            for paper in papers:
                # 修复作者字段：处理不同格式的作者字符串
                authors_str = paper.authors
                if authors_str == "No authors":
                    authors_list = []
                else:
                    # 移除可能的空格，并正确分割作者列表
                    authors_list = [author.strip() for author in re.split(r',\s*', authors_str)]
                
                # 处理评论字段：如果是"No comments"则转换为None，与daily项目格式一致
                comment_value = paper.comments if paper.comments != "No comments" else None
                
                # 构建JSONL格式的数据
                json_data = {
                    "id": paper.url.split("/")[-1],
                    "pdf": paper.url.replace("https://arxiv.org/abs", "https://arxiv.org/pdf"),
                    "abs": paper.url,
                    "authors": authors_list,
                    "title": paper.title,
                    "categories": paper.categories.split(","),
                    "comment": comment_value,
                    "summary": paper.abstract
                }
                jsonl_data.append(json_data)
            
            return jsonl_data

    def fetch_all(self) -> list[Paper]:
        with self.conn:
            cursor = self.conn.execute(
                """
                SELECT * FROM papers ORDER BY url DESC
                """
            )
            return cursor.fetchall()

    def newest_update_time(self) -> datetime:
        """
        最新更新时间是“上一次爬取最新论文的时间”
        由于数据库可能补充爬取过去的论文，所以先选最新论文，再从其中选最新的爬取时间
        """
        with self.conn:
            # 先检查数据库中是否有论文
            cursor = self.conn.execute("SELECT COUNT(*) as count FROM papers")
            count_result = cursor.fetchone()
            if count_result and count_result["count"] == 0:
                # 数据库为空，返回当前时间减去30天，确保能爬取最近的论文
                return datetime.now(UTC).replace(tzinfo=None) - timedelta(days=30)
            
            # 尝试获取所有论文中的最新update_time
            cursor = self.conn.execute("SELECT MAX(update_time) as max_updated_time FROM papers")
            result = cursor.fetchone()
            
            if result and result["max_updated_time"]:
                time = result["max_updated_time"].split(".")[0]
                return datetime.strptime(time, "%Y-%m-%d %H:%M:%S")
            else:
                # 当没有有效的update_time时，返回当前时间减去30天
                return datetime.now(UTC).replace(tzinfo=None) - timedelta(days=30)

    async def translate_missing(self, langto="zh-CN"):
        with self.conn:
            cursor = self.conn.execute(
                "SELECT url, title, abstract FROM papers WHERE title_translated IS NULL OR abstract_translated IS NULL"
            )
            papers = cursor.fetchall()

        async def worker(url, title, abstract):
            title_translated = await async_translate(title, langto=langto) if title else None
            abstract_translated = await async_translate(abstract, langto=langto) if abstract else None
            with self.conn:
                self.conn.execute(
                    "UPDATE papers SET title_translated = ?, abstract_translated = ? WHERE url = ?",
                    (title_translated, abstract_translated, url),
                )

        await asyncio.gather(*[worker(url, title, abstract) for url, title, abstract in papers])


class PaperExporter:
    def __init__(
        self,
        date_from: str,
        date_until: str,
        categories_blacklist: list[str] = [],
        categories_whitelist: list[str] = ["cs.CV", "cs.AI", "cs.LG", "cs.CL", "cs.IR", "cs.MA"],
        database_path="papers.db",
    ):
        self.db = PaperDatabase(database_path)
        self.date_from = datetime.strptime(date_from, "%Y-%m-%d")
        self.date_until = datetime.strptime(date_until, "%Y-%m-%d")
        self.date_range_days = (self.date_until - self.date_from).days + 1
        self.categories_blacklist = set(categories_blacklist)
        self.categories_whitelist = set(categories_whitelist)
        self.console = Console()

    def filter_papers(self, papers: list[Paper]) -> tuple[list[PaperRecord], list[PaperRecord]]:
        filtered_paper_records = []
        chosen_paper_records = []
        for paper in papers:
            categories = set(paper.categories)
            if not (self.categories_whitelist & categories):
                categories_str = ",".join(categories)
                filtered_paper_records.append(PaperRecord(paper, f"none of {categories_str} in whitelist"))
            elif black := self.categories_blacklist & categories:
                black_str = ",".join(black)
                filtered_paper_records.append(PaperRecord(paper, f"cat:{black_str} in blacklist"))
            else:
                chosen_paper_records.append(PaperRecord(paper, "-"))
        return chosen_paper_records, filtered_paper_records

    def to_markdown(self, output_dir="./output_md", filename_format="%Y-%m-%d", metadata=None):
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True, parents=True)
        for i in range(self.date_range_days):
            current = self.date_from + timedelta(days=i)
            current_filename = current.strftime(filename_format)

            with open(output_dir / f"{current_filename}.md", "w", encoding="utf-8") as file:
                papers = self.db.fetch_papers_on_date(current)
                chosen_records, filtered_records = self.filter_papers(papers)
                papers_str = f"# 论文全览：{current_filename}\n\n共有{len(chosen_records)}篇相关领域论文, 另有{len(filtered_records)}篇其他\n\n"

                chosen_dict = defaultdict(list)
                for record in chosen_records:
                    # 检查paper是否是Paper对象
                    if hasattr(record.paper, 'categories'):
                        # 如果是Paper对象，使用categories[0]
                        category = record.paper.categories[0]
                    else:
                        # 如果是原始行，从categories字符串中提取第一个类别
                        category = record.paper["categories"].split(",")[0] if "categories" in record.paper else "unknown"
                    chosen_dict[category].append(record)
                
                for category in sorted(chosen_dict.keys()):
                    category_en = parse_categories([category], lang="en")[0]
                    category_zh = parse_categories([category], lang="zh-CN")[0]
                    papers_str += f"## {category_zh}({category}:{category_en})\n\n"
                    for idx, record in enumerate(chosen_dict[category], 1):
                        # 检查paper是否是Paper对象
                        if hasattr(record.paper, 'to_markdown'):
                            # 如果是Paper对象，直接调用to_markdown方法
                            paper_md = record.to_markdown()
                            paper_md = paper_md.replace(f"【{record.paper.id}】", f"【{idx}】")
                            papers_str += paper_md
                        else:
                            # 如果是原始行，手动构建markdown格式
                            paper = record.paper
                            url = paper["url"]
                            id = paper["id"]
                            title = paper["title"]
                            title_translated = paper["title_translated"] if "title_translated" in paper else None
                            abstract = paper["abstract"]
                            abstract_translated = paper["abstract_translated"] if "abstract_translated" in paper else None
                            authors = paper["authors"]
                            
                            # 构建markdown格式
                            paper_md = f"""【{idx}】{title}
- **标题**: {title_translated if title_translated else title}
- **链接**: {url}
> **作者**: {authors}
> **摘要**: {abstract_translated if abstract_translated else abstract}
> **Abstract**: {abstract}

"""
                            papers_str += paper_md

                file.write(papers_str)

            self.console.log(
                f"[bold green]Output {current_filename}.md completed. {len(chosen_records)} papers chosen, {len(filtered_records)} papers filtered"
            )

    def to_csv(self, output_dir="./output_md", filename_format="%Y-%m-%d", header=True, csv_config={}):
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True, parents=True)

        csv_table = {
            "Title": lambda record: record.paper.title,
            "Interest": lambda record: ("chosen" if record.comment == "-" else "filtered"),
            "Title Translated": lambda record: (
                record.paper.title_translated if record.paper.title_translated else "-"
            ),
            "Categories": lambda record: ",".join(record.paper.categories),
            "Authors": lambda record: record.paper.authors,
            "URL": lambda record: record.paper.url,
            "PapersCool": lambda record: record.paper.url.replace("https://arxiv.org/abs", "https://papers.cool/arxiv"),
            "First Submitted Date": lambda record: record.paper.first_submitted_date.strftime("%Y-%m-%d"),
            "First Announced Date": lambda record: record.paper.first_announced_date.strftime("%Y-%m-%d"),
            "Abstract": lambda record: record.paper.abstract,
            "Abstract Translated": lambda record: (
                record.paper.abstract_translated if record.paper.abstract_translated else "-"
            ),
            "Comments": lambda record: record.paper.comments,
            "Note": lambda record: record.comment,
        }

        headers = list(csv_table.keys())

        for i in range(self.date_range_days):
            current = self.date_from + timedelta(days=i)
            current_filename = current.strftime(filename_format)

            with open(output_dir / f"{current_filename}.csv", "w", encoding="utf-8") as file:
                if "lineterminator" not in csv_config:
                    csv_config["lineterminator"] = "\n"
                writer = csv.writer(file, **csv_config)
                if header:
                    writer.writerow(headers)

                papers = self.db.fetch_papers_on_date(current)
                chosen_records, filtered_records = self.filter_papers(papers)
                for record in chosen_records + filtered_records:
                    writer.writerow([fn(record) for fn in csv_table.values()])

                self.console.log(
                    f"[bold green]Output {current_filename}.csv completed. {len(chosen_records)} papers chosen, {len(filtered_records)} papers filtered"
                )
    
    def to_jsonl(self, output_dir="./data", filename_format="%Y-%m-%d"):
        """
        导出论文数据为JSONL格式，与daily-arXiv-ai-enhanced项目兼容
        
        Args:
            output_dir (str, optional): 输出目录. Defaults to "./data".
            filename_format (str, optional): 文件名格式. Defaults to "%Y-%m-%d".
        """
        import json
        
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True, parents=True)

        for i in range(self.date_range_days):
            current = self.date_from + timedelta(days=i)
            current_filename = current.strftime(filename_format)

            with open(output_dir / f"{current_filename}.jsonl", "w", encoding="utf-8") as file:
                papers = self.db.fetch_papers_on_date(current)
                # 应用过滤逻辑，只导出符合白名单条件的论文
                chosen_records, filtered_records = self.filter_papers(papers)
                # 只使用符合白名单条件的论文
                chosen_papers = [record.paper for record in chosen_records]
                
                for paper in chosen_papers:
                    # 使用Paper对象的to_jsonl_dict方法直接生成JSON数据
                    json_data = paper.to_jsonl_dict()
                    # 写入JSONL格式
                    file.write(json.dumps(json_data, ensure_ascii=False) + "\n")

                self.console.log(
                    f"[bold green]Output {current_filename}.jsonl completed. {len(chosen_papers)} papers exported"
                )
    
    def to_ai_enhanced_jsonl(self, output_dir="./data", filename_format="%Y-%m-%d", model_name="deepseek-chat", language="Chinese", max_workers=1, provider=None):
        """
        导出AI增强的论文数据为JSONL格式
        
        Args:
            output_dir (str, optional): 输出目录. Defaults to "./data".
            filename_format (str, optional): 文件名格式. Defaults to "%Y-%m-%d".
            model_name (str, optional): 大模型名称. Defaults to "deepseek-chat".
            language (str, optional): 生成语言. Defaults to "Chinese".
            max_workers (int, optional): 最大并行数. Defaults to 1.
        """
        from ai.enhance import enhance_jsonl_data
        
        import json
        
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True, parents=True)

        for i in range(self.date_range_days):
            current = self.date_from + timedelta(days=i)
            current_filename = current.strftime(filename_format)
            
            # 先导出原始JSONL数据（应用过滤逻辑）
            temp_file = output_dir / f"{current_filename}.jsonl"
            with open(temp_file, "w", encoding="utf-8") as file:
                papers = self.db.fetch_papers_on_date(current)
                # 应用过滤逻辑，只导出符合白名单条件的论文
                chosen_records, filtered_records = self.filter_papers(papers)
                # 只使用符合白名单条件的论文
                chosen_papers = [record.paper for record in chosen_records]
                
                for paper in chosen_papers:
                    json_data = paper.to_jsonl_dict()
                    file.write(json.dumps(json_data, ensure_ascii=False) + "\n")
            
            # 使用AI增强数据
            target_file = output_dir / f"{current_filename}_AI_enhanced_{language}.jsonl"
            # 读取临时文件，指定UTF-8编码
            with open(temp_file, "r", encoding="utf-8") as f:
                data = [json.loads(line) for line in f]
            
            # 增强数据
            enhanced_data = enhance_jsonl_data(data, model_name, language, max_workers, provider)
            
            # 保存结果
            with open(target_file, "w", encoding="utf-8") as f:
                for item in enhanced_data:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
            
            # 删除临时文件
            if temp_file.exists():
                temp_file.unlink()

            
            # 更新数据库中的AI内容
            self._update_ai_content(enhanced_data)
            
            self.console.log(
                f"[bold green]Output {target_file.name} completed. {len(enhanced_data)} papers enhanced"
            )
    
    def _update_ai_content(self, enhanced_data):
        """
        更新数据库中的AI内容
        
        Args:
            enhanced_data (list[dict]): 增强后的论文数据列表
        """
        import json
        
        with self.db.conn:
            for item in enhanced_data:
                if "AI" in item:
                    url = item["abs"]
                    ai_content = item["AI"]
                    self.db.conn.execute(
                        """
                        UPDATE papers 
                        SET ai_content = ? 
                        WHERE url = ?
                        """,
                        (json.dumps(ai_content), url),
                    )


if __name__ == "__main__":
    from datetime import date, timedelta

    today = date.today()

    exporter = PaperExporter(today.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d"))
    exporter.to_markdown()
    #exporter.to_csv(csv_config=dict(delimiter="\t"), header=False)
