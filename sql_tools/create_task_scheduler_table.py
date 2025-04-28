#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
创建定时任务表,用于记录邮件发送的定时任务配置
"""
import mysql.connector
from mysql.connector import Error

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config_loader import get_db_config

def connect_to_mysql():
    """
    连接到MySQL数据库
    """
    db_config = get_db_config()
    try:
        connection = mysql.connector.connect(
            host=db_config['host'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database']
        )
        if connection.is_connected():
            print("成功连接到MySQL数据库")
            return connection
    except Error as e:
        print(f"连接MySQL时出错: {e}")
        return None

def create_task_scheduler_table():
    """
    创建定时任务表,用于存储邮件发送的定时任务配置
    """
    connection = connect_to_mysql()
    if connection is None:
        return
    
    try:
        cursor = connection.cursor()
        
        # 检查表是否已存在
        cursor.execute("SHOW TABLES LIKE 'task_scheduler'")
        result = cursor.fetchone()
        
        if result:
            print("表'task_scheduler'已存在")
        else:
            # 创建新表
            create_table_query = """
            CREATE TABLE task_scheduler (
                id INT AUTO_INCREMENT PRIMARY KEY,
                task_name VARCHAR(255) NOT NULL,
                is_running BOOLEAN DEFAULT FALSE,
                daily_count INT NOT NULL,
                target_countries TEXT,
                target_regions TEXT,
                send_time TIME NOT NULL,
                workdays VARCHAR(50) NOT NULL,
                template_name VARCHAR(255) NOT NULL,
                last_run_date DATETIME,
                last_sent_count INT DEFAULT 0,
                last_opened_count INT DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            """
            cursor.execute(create_table_query)
            connection.commit()
            print("成功创建'task_scheduler'表")
            
        # 显示表结构
        cursor.execute("DESCRIBE task_scheduler")
        table_structure = cursor.fetchall()
        print("\n表结构:")
        for column in table_structure:
            print(column)
            
    except Error as e:
        print(f"执行操作时出错: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
            print("MySQL连接已关闭")

if __name__ == "__main__":
    create_task_scheduler_table()