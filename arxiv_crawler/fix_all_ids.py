#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复数据库中所有记录的id字段
"""

import sqlite3

def fix_all_ids():
    """修复数据库中所有记录的id字段"""
    # 连接到数据库
    conn = sqlite3.connect("papers.db")
    
    print("修复所有记录的id字段...")
    # 更新所有记录的id字段
    cursor = conn.execute("UPDATE papers SET id = SUBSTR(url, INSTR(url, 'abs/') + 4)")
    print(f"已更新 {cursor.rowcount} 条记录")
    
    # 提交更改
    conn.commit()
    
    # 检查修复结果
    cursor = conn.execute("SELECT url, id FROM papers LIMIT 3")
    print("\n修复结果示例:")
    for row in cursor.fetchall():
        print(f"  - URL: {row[0]}")
        print(f"    ID: {row[1]}")
    
    # 关闭数据库连接
    conn.close()

if __name__ == "__main__":
    fix_all_ids()
