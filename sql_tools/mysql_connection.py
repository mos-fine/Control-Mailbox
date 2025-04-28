#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta
import json

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

def create_email_tracking_table():
    """
    创建一个新表用于存储已发送邮件的跟踪信息，包括公司名称、联系人、邮箱、
    回复状态、打开状态、发送时间、打开时间和回复时间
    """
    connection = connect_to_mysql()
    if connection is None:
        return
    
    try:
        cursor = connection.cursor()
        
        # 检查表是否已存在
        cursor.execute("SHOW TABLES LIKE 'email_tracking'")
        result = cursor.fetchone()
        
        if result:
            print("表'email_tracking'已存在")
        else:
            # 创建新表
            create_table_query = """
            CREATE TABLE email_tracking (
                id INT AUTO_INCREMENT PRIMARY KEY,
                company_name VARCHAR(255) NOT NULL,
                contact_name VARCHAR(255),
                email VARCHAR(255) NOT NULL,
                is_replied BOOLEAN DEFAULT FALSE,
                is_opened BOOLEAN DEFAULT FALSE,
                sent_time DATETIME NOT NULL,
                open_time DATETIME,
                reply_time DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            """
            cursor.execute(create_table_query)
            connection.commit()
            print("成功创建'email_tracking'表")
            
        # 显示表结构
        cursor.execute("DESCRIBE email_tracking")
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

def load_task_from_db():
    """从数据库加载任务配置"""
    connection = None
    try:
        connection = connect_to_mysql()
        if connection and connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT * FROM task_scheduler WHERE is_running = TRUE LIMIT 1")
            task = cursor.fetchone()
            
            if task:
                # 处理JSON字符串
                task['target_countries'] = json.loads(task['target_countries']) if task['target_countries'] else []
                task['target_regions'] = json.loads(task['target_regions']) if task['target_regions'] else []
                task['workdays'] = json.loads(task['workdays'])
                
                # 处理时间格式
                # TIME类型转换为字符串格式
                if isinstance(task['send_time'], timedelta):
                    total_seconds = int(task['send_time'].total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    task['send_time'] = f"{hours:02d}:{minutes:02d}"
                
                # 处理日期
                task['last_run_date'] = task['last_run_date'].strftime('%Y-%m-%d') if task['last_run_date'] else None
                
                return task
    except Error as e:
        print(f"从数据库加载任务配置失败: {e}")
    finally:
        if connection and connection.is_connected():
            connection.close()
    return None

def save_task_to_db(task_config):
    """保存任务配置到数据库"""
    connection = None
    try:
        connection = connect_to_mysql()
        if connection and connection.is_connected():
            cursor = connection.cursor()
            
            # 停止所有任务
            cursor.execute("UPDATE task_scheduler SET is_running = FALSE")
            
            # 检查是否存在任务
            cursor.execute("SELECT id FROM task_scheduler WHERE task_name = 'default_task'")
            existing_task = cursor.fetchone()
            
            # 准备数据 - 处理datetime和字符串两种可能的类型
            last_run_date = None
            if task_config.get('last_run_date'):
                if isinstance(task_config['last_run_date'], str):
                    last_run_date = datetime.strptime(task_config['last_run_date'], '%Y-%m-%d')
                elif isinstance(task_config['last_run_date'], datetime):
                    last_run_date = task_config['last_run_date']
                else:
                    print(f"警告: last_run_date 类型不支持: {type(task_config['last_run_date'])}")
            
            if existing_task:
                # 更新现有任务
                update_query = """
                UPDATE task_scheduler SET
                    is_running = %s,
                    daily_count = %s,
                    target_countries = %s,
                    target_regions = %s,
                    send_time = %s,
                    workdays = %s,
                    template_name = %s,
                    last_run_date = %s,
                    last_sent_count = %s,
                    last_opened_count = %s
                WHERE task_name = 'default_task'
                """
                data = (
                    task_config['is_running'],
                    task_config['daily_count'],
                    json.dumps(task_config['target_countries']),
                    json.dumps(task_config['target_regions']),
                    task_config['send_time'],
                    json.dumps(task_config['workdays']),
                    task_config['template_name'],
                    last_run_date,
                    task_config['last_sent_count'],
                    task_config['last_opened_count']
                )
            else:
                # 创建新任务
                insert_query = """
                INSERT INTO task_scheduler (
                    task_name, is_running, daily_count, target_countries, target_regions,
                    send_time, workdays, template_name, last_run_date, last_sent_count,
                    last_opened_count
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                data = (
                    'default_task',
                    task_config['is_running'],
                    task_config['daily_count'],
                    json.dumps(task_config['target_countries']),
                    json.dumps(task_config['target_regions']),
                    task_config['send_time'],
                    json.dumps(task_config['workdays']),
                    task_config['template_name'],
                    last_run_date,
                    task_config['last_sent_count'],
                    task_config['last_opened_count']
                )
            
            cursor.execute(update_query if existing_task else insert_query, data)
            connection.commit()
            return True
            
    except Error as e:
        print(f"保存任务配置到数据库失败: {e}")
    finally:
        if connection and connection.is_connected():
            connection.close()
    return False

if __name__ == "__main__":
    create_email_tracking_table()
    create_task_scheduler_table()
