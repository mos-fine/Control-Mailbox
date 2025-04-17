#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FastAPI服务器：提供API接口管理邮件发送系统
"""

import os
import json
import datetime
import threading
import time
from typing import List, Dict, Optional, Union
from fastapi import FastAPI, HTTPException, BackgroundTasks
import uvicorn
from pydantic import BaseModel
import mysql.connector
from mysql.connector import Error
import requests
import schedule
from email_sender import EMAIL_CONFIG, load_template, init_connections
from email_sender import send_email, maintain_connections, check_replies

# 创建FastAPI应用
app = FastAPI(
    title="邮件发送系统API",
    description="提供邮件发送系统的API接口，支持定时发送邮件、查看统计数据等功能",
    version="1.0.0"
)

# 数据库配置
DB_CONFIG = {
    'host': '8.153.199.241',
    'user': 'Rex',
    'password': '3528846780Rex',
    'database': 'B2B',
    'table_name': 'companies'
}

# 全局配置
EMAIL_TASK_CONFIG = {
    'daily_count': 50,          # 每天发送的邮件数量
    'target_countries': [],     # 目标国家列表，为空表示所有国家
    'target_regions': [],       # 目标区域列表，为空表示所有区域
    'send_time': '09:00',       # 每天发送邮件的时间，24小时制
    'template_name': 'C_template.html', # 使用的邮件模板
    'is_running': False,        # 是否正在运行定时任务
    'last_run_date': None,      # 上次运行日期
    'last_sent_count': 0,       # 上次发送数量
    'last_opened_count': 0,     # 上次打开数量
}

# 任务线程
scheduler_thread = None

# 加载区域和国家对应关系
def load_regions():
    regions_path = os.path.join(os.path.dirname(__file__), 'config', 'regions.json')
    if os.path.exists(regions_path):
        with open(regions_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

# 区域到国家的映射关系
REGION_COUNTRIES = load_regions()

# API请求和响应模型
class EmailTaskConfig(BaseModel):
    daily_count: int
    target_countries: List[str] = []
    target_regions: List[str] = []  # 新增区域字段
    send_time: str
    template_name: str = "C_template.html"  # 默认使用C模板

class EmailTaskStatus(BaseModel):
    is_running: bool
    daily_count: int
    target_countries: List[str]
    target_regions: List[str] = []  # 新增区域字段
    send_time: str
    template_name: str
    last_run_date: Optional[str] = None
    last_sent_count: int = 0
    last_opened_count: int = 0

class EmailStats(BaseModel):
    date: str
    sent_count: int
    opened_count: int
    open_rate: float

# 保存和加载配置
def save_config():
    config_dir = os.path.join(os.path.dirname(__file__), 'config')
    os.makedirs(config_dir, exist_ok=True)
    
    config_path = os.path.join(config_dir, 'api_config.json')
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(EMAIL_TASK_CONFIG, f, ensure_ascii=False, indent=2)

def load_config():
    config_dir = os.path.join(os.path.dirname(__file__), 'config')
    config_path = os.path.join(config_dir, 'api_config.json')
    
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
            # 更新全局配置
            for key, value in config.items():
                if key in EMAIL_TASK_CONFIG:
                    EMAIL_TASK_CONFIG[key] = value

# 从数据库获取收件人列表
def get_recipients_from_db(count: int, countries: List[str] = None) -> List[Dict]:
    recipients = []
    
    try:
        # 创建数据库连接
        connection = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database']
        )
        
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            
            # 构建查询条件
            query = f"""
            SELECT id, company_name, company_country, contact_name, contact_email, contact_position
            FROM {DB_CONFIG['table_name']}
            WHERE contact_email IS NOT NULL
            AND contact_email != ''
            AND contact_email_sent = 0
            """
            
            # 添加国家过滤条件
            if countries and len(countries) > 0:
                country_list = ", ".join([f"'{country}'" for country in countries])
                query += f" AND company_country IN ({country_list})"
            
            query += f" LIMIT {count}"
            
            cursor.execute(query)
            records = cursor.fetchall()
            
            for record in records:
                recipient = {
                    "id": record['id'],
                    "name": record['contact_name'] if record['contact_name'] else '客户',
                    "email": record['contact_email'],
                    "company": record['company_name'],
                    "country": record['company_country'] if record['company_country'] else '',
                    "position": record['contact_position'] if record['contact_position'] else '',
                    "subject": "Frozen Vegetable Product Offering"
                }
                recipients.append(recipient)
            
            cursor.close()
            connection.close()
    
    except Error as e:
        print(f"数据库操作失败: {e}")
    except Exception as e:
        print(f"加载收件人列表失败: {e}")
    
    return recipients

# 获取统计数据
def get_email_stats(date=None):
    if not date:
        date = datetime.datetime.now().strftime('%Y-%m-%d')
    
    stats = {
        'sent_count': 0,
        'opened_count': 0,
        'open_rate': 0
    }
    
    # 首先尝试从数据库获取统计数据
    try:
        connection = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database']
        )
        
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            
            # 构建查询的日期范围条件
            date_start = f"{date} 00:00:00"
            date_end = f"{date} 23:59:59"
            
            # 查询当天发送的邮件数量
            sent_query = """
            SELECT COUNT(*) as count
            FROM email_tracking
            WHERE sent_time BETWEEN %s AND %s
            """
            
            cursor.execute(sent_query, (date_start, date_end))
            sent_result = cursor.fetchone()
            stats['sent_count'] = sent_result['count'] if sent_result else 0
            
            # 查询当天被打开的邮件数量
            opened_query = """
            SELECT COUNT(*) as count
            FROM email_tracking
            WHERE is_opened = TRUE AND open_time BETWEEN %s AND %s
            """
            
            cursor.execute(opened_query, (date_start, date_end))
            opened_result = cursor.fetchone()
            stats['opened_count'] = opened_result['count'] if opened_result else 0
            
            # 计算打开率
            stats['open_rate'] = (stats['opened_count'] / stats['sent_count'] * 100) if stats['sent_count'] > 0 else 0
            
            cursor.close()
            connection.close()
            
            print(f"从数据库获取到统计信息: 已发送 {stats['sent_count']} 封，已打开 {stats['opened_count']} 封")
            return stats
            
    except Error as e:
        print(f"从数据库获取统计信息失败: {e}")
    
    # 如果从数据库获取失败，则尝试从跟踪服务器获取
    try:
        response = requests.get(f"{EMAIL_CONFIG['tracker_url']}/stats")
        if response.status_code == 200:
            server_stats = response.json()
            
            sent_count = server_stats.get('sent', 0)
            opened_count = server_stats.get('opened', 0)
            open_rate = (opened_count / sent_count * 100) if sent_count > 0 else 0
            
            stats = {
                'sent_count': sent_count,
                'opened_count': opened_count,
                'open_rate': open_rate
            }
            
            print(f"从跟踪服务器获取到统计信息: 已发送 {stats['sent_count']} 封，已打开 {stats['opened_count']} 封")
            return stats
    except Exception as e:
        print(f"从跟踪服务器获取统计信息失败: {e}")
    
    return stats

# 将区域转换为国家列表
def expand_regions_to_countries(regions: List[str]) -> List[str]:
    """将区域列表转换为对应的国家列表"""
    countries = []
    for region in regions:
        if region in REGION_COUNTRIES:
            countries.extend(REGION_COUNTRIES[region])
    return countries

# 发送邮件任务
def email_sending_task():
    print(f"开始执行每日邮件发送任务 - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 更新上次运行日期
    EMAIL_TASK_CONFIG['last_run_date'] = datetime.datetime.now().strftime('%Y-%m-%d')
    
    # 获取前一天的统计数据
    stats = get_email_stats()
    EMAIL_TASK_CONFIG['last_sent_count'] = stats['sent_count']
    EMAIL_TASK_CONFIG['last_opened_count'] = stats['opened_count']
    
    # 保存配置
    save_config()
    
    # 获取收件人列表
    daily_count = EMAIL_TASK_CONFIG['daily_count']
    
    # 处理区域或国家
    target_countries = []
    
    # 优先使用区域（如果指定了区域，则忽略国家设置）
    if EMAIL_TASK_CONFIG['target_regions']:
        # 如果指定了区域，将区域扩展为对应的国家列表
        target_countries = expand_regions_to_countries(EMAIL_TASK_CONFIG['target_regions'])
        print(f"按区域发送邮件: {', '.join(EMAIL_TASK_CONFIG['target_regions'])}")
    elif EMAIL_TASK_CONFIG['target_countries']:
        # 如果只指定了国家列表，则直接使用
        target_countries = list(EMAIL_TASK_CONFIG['target_countries'])
        print(f"按国家发送邮件")
    else:
        print(f"未指定目标区域或国家，将发送给所有国家")
        
    print(f"目标国家列表：{target_countries}")
    recipients = get_recipients_from_db(daily_count, target_countries)
    
    if not recipients:
        print("没有符合条件的收件人")
        return
    
    print(f"找到 {len(recipients)} 个收件人")
    
    # 获取要使用的模板名称
    template_name = EMAIL_TASK_CONFIG['template_name']
    print(f"使用邮件模板: {template_name}")
    
    # 加载邮件模板
    load_template(template_name)
    
    # 初始化连接
    init_connections()
    
    # 发送邮件
    success_count = 0
    for recipient in recipients:
        if send_email(recipient):
            success_count += 1
        time.sleep(5)  # 短暂延迟，避免被识别为垃圾邮件发送者
    
    print(f"邮件发送完成。成功: {success_count}/{len(recipients)}")
    
    # 更新跟踪服务器的发送统计
    try:
        requests.post(
            f"{EMAIL_CONFIG['tracker_url']}/stats/update",
            json={'sent': success_count}
        )
    except Exception as e:
        print(f"更新跟踪服务器统计信息失败: {e}")

# 定时任务调度器
def run_scheduler():
    while EMAIL_TASK_CONFIG['is_running']:
        schedule.run_pending()
        time.sleep(60)

# API路由
@app.get("/", tags=["根路径"])
async def root():
    return {"message": "邮件发送系统API服务已启动"}

@app.get("/status", response_model=EmailTaskStatus, tags=["任务状态"])
async def get_status():
    """获取当前邮件发送任务的状态"""
    return {
        "is_running": EMAIL_TASK_CONFIG['is_running'],
        "daily_count": EMAIL_TASK_CONFIG['daily_count'],
        "target_countries": EMAIL_TASK_CONFIG['target_countries'],
        "target_regions": EMAIL_TASK_CONFIG['target_regions'],
        "send_time": EMAIL_TASK_CONFIG['send_time'],
        "template_name": EMAIL_TASK_CONFIG['template_name'],
        "last_run_date": EMAIL_TASK_CONFIG['last_run_date'],
        "last_sent_count": EMAIL_TASK_CONFIG['last_sent_count'],
        "last_opened_count": EMAIL_TASK_CONFIG['last_opened_count']
    }

@app.post("/start", response_model=EmailTaskStatus, tags=["任务控制"])
async def start_task(config: EmailTaskConfig, background_tasks: BackgroundTasks):
    """
    启动邮件发送任务
    - daily_count: 每天发送的邮件数量
    - target_countries: 目标国家列表，为空表示所有国家。请使用中文国家名称，例如["中国", "美国", "日本"]
    - target_regions: 目标区域列表，如["南美洲", "东南亚", "非洲"]。系统会自动发送邮件到这些区域的所有国家
    
    注意: 请只使用target_regions或target_countries中的一个，不要同时使用。如果两者都提供，系统将优先使用target_regions并忽略target_countries。
    
    - send_time: 每天发送邮件的时间，格式为"HH:MM"，24小时制
    - template_name: 要使用的邮件模板名称，默认为"C_template.html"
    """
    global scheduler_thread
    
    if EMAIL_TASK_CONFIG['is_running']:
        raise HTTPException(status_code=400, detail="任务已在运行中")
    
    # 更新配置
    EMAIL_TASK_CONFIG['daily_count'] = config.daily_count
    EMAIL_TASK_CONFIG['target_countries'] = config.target_countries
    EMAIL_TASK_CONFIG['target_regions'] = config.target_regions
    EMAIL_TASK_CONFIG['send_time'] = config.send_time
    EMAIL_TASK_CONFIG['template_name'] = config.template_name
    EMAIL_TASK_CONFIG['is_running'] = True
    
    # 保存配置
    save_config()
    
    # 清除之前的调度
    schedule.clear()
    
    # 设置定时任务
    schedule.every().day.at(config.send_time).do(email_sending_task)
    schedule.every(1).hours.do(check_replies)
    schedule.every(30).minutes.do(maintain_connections)
    
    # 启动调度器线程
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    countries_info = f"目标国家: {', '.join(config.target_countries)}" if config.target_countries else "所有国家"
    print(f"已启动邮件发送任务，使用模板 {config.template_name}，每天 {config.send_time} 发送 {config.daily_count} 封邮件，{countries_info}")
    
    return await get_status()

@app.post("/stop", response_model=EmailTaskStatus, tags=["任务控制"])
async def stop_task():
    """停止邮件发送任务"""
    EMAIL_TASK_CONFIG['is_running'] = False
    save_config()
    
    # 清除调度
    schedule.clear()
    
    print("已停止邮件发送任务")
    
    return await get_status()

@app.get("/stats", response_model=EmailStats, tags=["统计数据"])
async def get_stats(date: Optional[str] = None):
    """
    获取指定日期的邮件统计数据
    - date: 日期，格式为"YYYY-MM-DD"，默认为当天
    """
    if not date:
        date = datetime.datetime.now().strftime('%Y-%m-%d')
    
    stats = get_email_stats(date)
    
    return {
        "date": date,
        "sent_count": stats['sent_count'],
        "opened_count": stats['opened_count'],
        "open_rate": stats['open_rate']
    }

@app.post("/send-now", tags=["任务控制"])
async def send_now(background_tasks: BackgroundTasks):
    """立即执行一次邮件发送任务，不影响原有的定时任务"""
    background_tasks.add_task(email_sending_task)
    return {"message": "邮件发送任务已在后台启动，请稍后查看统计数据"}

# 启动时加载配置
@app.on_event("startup")
async def startup_event():
    # 加载配置
    load_config()

# 主函数
if __name__ == "__main__":
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
