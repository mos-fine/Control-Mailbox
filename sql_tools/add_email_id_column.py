#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
向email_tracking表添加email_id列
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

def add_email_id_column():
    """
    向email_tracking表添加email_id列
    """
    connection = connect_to_mysql()
    if connection is None:
        return
    
    try:
        cursor = connection.cursor()
        
        # 检查email_id列是否已存在
        cursor.execute("DESCRIBE email_tracking")
        columns = cursor.fetchall()
        column_names = [column[0] for column in columns]
        
        if 'email_id' in column_names:
            print("列'email_id'已存在")
        else:
            # 添加email_id列
            alter_query = """
            ALTER TABLE email_tracking 
            ADD COLUMN email_id VARCHAR(255) AFTER email
            """
            cursor.execute(alter_query)
            connection.commit()
            print("成功添加'email_id'列")
            
        # 显示更新后的表结构
        cursor.execute("DESCRIBE email_tracking")
        table_structure = cursor.fetchall()
        print("\n更新后的表结构:")
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
    add_email_id_column()
