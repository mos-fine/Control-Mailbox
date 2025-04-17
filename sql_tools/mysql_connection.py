import mysql.connector
from mysql.connector import Error
from datetime import datetime

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

if __name__ == "__main__":
    create_email_tracking_table()
