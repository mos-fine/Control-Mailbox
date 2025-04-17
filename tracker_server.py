#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
邮件追踪服务器：用于监测邮件打开状态和接收回复
"""

from flask import Flask, request, send_file
import os
import logging
import json
from datetime import datetime
import threading
import time

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/tracker.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('email_tracker')

# 创建Flask应用
app = Flask(__name__)

# 存储邮件状态的数据结构
email_stats = {
    'sent': 0,        # 发送的邮件数
    'opened': set(),  # 打开的邮件ID集合
    'replied': set(), # 回复的邮件ID集合
    'details': {}     # 存储每封邮件的详细信息
}

# 确保日志目录存在
os.makedirs('logs', exist_ok=True)
os.makedirs('static', exist_ok=True)

# 创建一个1x1的透明跟踪像素图
if not os.path.exists('static/tracker.png'):
    with open('static/tracker.png', 'wb') as f:
        # 最小的透明PNG图像
        f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x00\x00\x02\x00\x01\x9a\x00\xe3\x99\x00\x00\x00\x00IEND\xaeB`\x82')

@app.route('/track/<email_id>')
def track_open(email_id):
    """记录邮件打开事件"""
    if email_id not in email_stats['opened']:
        email_stats['opened'].add(email_id)
        logger.info(f"邮件 {email_id} 已被打开")
        
        # 更新邮件详情
        if email_id in email_stats['details']:
            email_stats['details'][email_id]['opened'] = True
            email_stats['details'][email_id]['opened_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 保存统计数据
        save_stats()
    
    # 返回透明像素图
    return send_file('static/tracker.png', mimetype='image/png')

@app.route('/reply', methods=['POST'])
def track_reply():
    """记录邮件回复事件"""
    data = request.json
    email_id = data.get('email_id')
    reply_content = data.get('content', '')
    
    if email_id and email_id not in email_stats['replied']:
        email_stats['replied'].add(email_id)
        logger.info(f"邮件 {email_id} 已收到回复")
        
        # 更新邮件详情
        if email_id in email_stats['details']:
            email_stats['details'][email_id]['replied'] = True
            email_stats['details'][email_id]['reply_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            email_stats['details'][email_id]['reply_content'] = reply_content
        
        # 保存统计数据
        save_stats()
        
    return {'status': 'success'}

@app.route('/stats')
def get_stats():
    """获取当前统计数据"""
    return {
        'sent': email_stats['sent'],
        'opened': len(email_stats['opened']),
        'replied': len(email_stats['replied']),
        'details': email_stats['details']
    }

def save_stats():
    """保存统计数据到文件"""
    stats_to_save = {
        'sent': email_stats['sent'],
        'opened': list(email_stats['opened']),
        'replied': list(email_stats['replied']),
        'details': email_stats['details']
    }
    
    with open('logs/email_stats.json', 'w', encoding='utf-8') as f:
        json.dump(stats_to_save, f, ensure_ascii=False, indent=2)

def load_stats():
    """从文件加载统计数据"""
    if os.path.exists('logs/email_stats.json'):
        with open('logs/email_stats.json', 'r', encoding='utf-8') as f:
            stats = json.load(f)
            email_stats['sent'] = stats['sent']
            email_stats['opened'] = set(stats['opened'])
            email_stats['replied'] = set(stats['replied'])
            email_stats['details'] = stats['details']
            logger.info("已加载邮件统计数据")

def print_stats_periodically():
    """定期打印统计信息"""
    while True:
        logger.info(f"当前统计: 已发送 {email_stats['sent']} 封, "
                   f"已打开 {len(email_stats['opened'])} 封, "
                   f"已回复 {len(email_stats['replied'])} 封")
        time.sleep(3600)  # 每小时打印一次

if __name__ == '__main__':
    # 加载之前的统计数据
    load_stats()
    
    # 启动打印统计信息的线程
    stats_thread = threading.Thread(target=print_stats_periodically, daemon=True)
    stats_thread.start()
    
    # 启动Flask应用
    app.run(host='0.0.0.0', port=5000)
