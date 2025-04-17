#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
客户端反馈接收服务：用于接收邮件打开和回复的反馈
"""

from flask import Flask, request, jsonify
import os
import logging
import json
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/feedback.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('feedback_server')

# 创建Flask应用
app = Flask(__name__)

# 确保日志目录存在
os.makedirs('logs', exist_ok=True)

# 存储邮件详情的数据结构
email_database = {}
email_stats = {'sent': 0, 'opened': 0, 'replied': 0}

@app.route('/track/register', methods=['POST'])
def register_email():
    """注册新发送的邮件"""
    data = request.json
    email_id = data.get('email_id')
    
    if not email_id:
        return jsonify({'error': 'Missing email_id'}), 400
    
    email_database[email_id] = {
        'recipient': data.get('recipient'),
        'name': data.get('name'),
        'sent_time': data.get('sent_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
        'opened': False,
        'replied': False
    }
    
    email_stats['sent'] += 1
    save_data()
    
    logger.info(f"注册了新邮件: {email_id}, 发送给: {data.get('recipient')}")
    return jsonify({'status': 'success', 'email_id': email_id})

@app.route('/track/<email_id>')
def track_open(email_id):
    """记录邮件打开事件"""
    # 更新本地缓存
    if email_id in email_database and not email_database[email_id]['opened']:
        email_database[email_id]['opened'] = True
        opened_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        email_database[email_id]['opened_time'] = opened_time
        email_stats['opened'] += 1
        save_data()
        
        logger.info(f"邮件 {email_id} 已被打开")
        
        # 更新数据库中的邮件打开状态
        try:
            import mysql.connector
            from mysql.connector import Error
            
            connection = mysql.connector.connect(
                host="8.153.199.241",
                user="Rex",
                password="3528846780Rex",
                database="B2B"
            )
            
            if connection.is_connected():
                cursor = connection.cursor()
                
                # 更新email_tracking表中对应邮件的打开状态
                update_query = """
                UPDATE email_tracking 
                SET is_opened = TRUE, open_time = %s
                WHERE email_id = %s
                """
                
                cursor.execute(update_query, (opened_time, email_id))
                connection.commit()
                
                rows_affected = cursor.rowcount
                if rows_affected > 0:
                    logger.info(f"已更新数据库中邮件 {email_id} 的打开状态")
                else:
                    logger.warning(f"未找到数据库中邮件 {email_id} 的记录")
                
                cursor.close()
                connection.close()
        except Error as e:
            logger.error(f"更新数据库中邮件打开状态时出错: {e}")
        except Exception as e:
            logger.error(f"处理邮件打开事件时出错: {e}")
    
    # 返回1x1透明像素
    response = app.send_static_file('tracker.png')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/reply', methods=['POST'])
def track_reply():
    """记录邮件回复事件"""
    data = request.json
    email_id = data.get('email_id')
    
    if not email_id:
        return jsonify({'error': 'Missing email_id'}), 400
    
    # 更新本地缓存
    if email_id in email_database and not email_database[email_id]['replied']:
        email_database[email_id]['replied'] = True
        reply_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        email_database[email_id]['reply_time'] = reply_time
        email_database[email_id]['reply_from'] = data.get('from')
        email_database[email_id]['reply_content'] = data.get('content', '')
        email_stats['replied'] += 1
        save_data()
        
        logger.info(f"邮件 {email_id} 已收到回复")
        
        # 更新数据库中的邮件回复状态
        try:
            import mysql.connector
            from mysql.connector import Error
            
            connection = mysql.connector.connect(
                host="8.153.199.241",
                user="Rex",
                password="3528846780Rex",
                database="B2B"
            )
            
            if connection.is_connected():
                cursor = connection.cursor()
                
                # 更新email_tracking表中对应邮件的回复状态
                update_query = """
                UPDATE email_tracking 
                SET is_replied = TRUE, reply_time = %s
                WHERE email_id = %s
                """
                
                cursor.execute(update_query, (reply_time, email_id))
                connection.commit()
                
                rows_affected = cursor.rowcount
                if rows_affected > 0:
                    logger.info(f"已更新数据库中邮件 {email_id} 的回复状态")
                else:
                    logger.warning(f"未找到数据库中邮件 {email_id} 的记录")
                
                cursor.close()
                connection.close()
        except Error as e:
            logger.error(f"更新数据库中邮件回复状态时出错: {e}")
        except Exception as e:
            logger.error(f"处理邮件回复事件时出错: {e}")
    
    return jsonify({'status': 'success'})

@app.route('/stats', methods=['GET'])
def get_stats():
    """获取统计信息"""
    return jsonify({
        'sent': email_stats['sent'],
        'opened': email_stats['opened'],
        'replied': email_stats['replied'],
        'details': email_database
    })

@app.route('/stats/update', methods=['POST'])
def update_stats():
    """更新统计信息"""
    data = request.json
    
    if 'sent' in data:
        # 增量更新已发送数量
        email_stats['sent'] += int(data['sent'])
        save_data()
        
    return jsonify({'status': 'success'})

def save_data():
    """保存数据到文件"""
    with open('logs/email_database.json', 'w', encoding='utf-8') as f:
        json.dump(email_database, f, ensure_ascii=False, indent=2)
    
    with open('logs/email_stats.json', 'w', encoding='utf-8') as f:
        json.dump(email_stats, f, ensure_ascii=False, indent=2)

def load_data():
    """从文件加载数据"""
    global email_database, email_stats
    
    if os.path.exists('logs/email_database.json'):
        with open('logs/email_database.json', 'r', encoding='utf-8') as f:
            email_database = json.load(f)
    
    if os.path.exists('logs/email_stats.json'):
        with open('logs/email_stats.json', 'r', encoding='utf-8') as f:
            email_stats = json.load(f)

if __name__ == '__main__':
    # 加载历史数据
    load_data()
    
    # 启动服务器
    app.run(host='0.0.0.0', port=5000)
