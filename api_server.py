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
import logging
import logging.handlers
from typing import List, Dict, Optional, Union
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import uvicorn
from pydantic import BaseModel
import requests
import schedule
import mysql.connector
from mysql.connector import Error

from email_sender import EMAIL_CONFIG, load_template, init_connections
from email_sender import send_email, maintain_connections, check_replies
from sql_tools.mysql_connection import load_task_from_db, save_task_to_db

# 定义IP白名单
ALLOWED_IPS = ["47.122.61.247", "127.0.0.1", "localhost"]

# 创建IP白名单中间件
class IPWhitelistMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 获取客户端IP地址
        client_ip = request.client.host if request.client else None
        
        # 检查是否在白名单中
        if client_ip not in ALLOWED_IPS:
            return JSONResponse(
                status_code=403,
                content={"detail": f"禁止访问：IP {client_ip} 不在白名单中"}
            )
        
        # 如果在白名单中，则继续处理请求
        return await call_next(request)

# 创建FastAPI应用
app = FastAPI(
    title="邮件发送系统API",
    description="提供邮件发送系统的API接口，支持定时发送邮件、查看统计数据等功能",
    version="1.0.0"
)

# 添加IP白名单中间件
app.add_middleware(IPWhitelistMiddleware)

# 导入数据库配置
from config_loader import get_db_config

# 数据库配置
DB_CONFIG = get_db_config()

# 全局配置
EMAIL_TASK_CONFIG = {
    'daily_count': 50,          # 每天发送的邮件数量
    'target_countries': [],     # 目标国家列表，为空表示所有国家
    'target_regions': [],       # 目标区域列表，为空表示所有区域
    'send_time': '09:00',       # 每天发送邮件的时间，24小时制
    'workdays': [0, 1, 2, 3, 4, 5, 6],  # 发送邮件的工作日(0-6分别代表周一到周日)，默认每天发送
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

# 配置日志
def setup_logging():
    """配置日志系统"""
    logger = logging.getLogger('email_tracker')
    logger.setLevel(logging.INFO)
    
    # 添加系统日志处理器
    syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    syslog_handler.setFormatter(formatter)
    logger.addHandler(syslog_handler)
    
    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

# 创建日志记录器
logger = setup_logging()

# 添加数据库操作错误记录
def log_db_error(operation: str, error: Exception):
    """记录数据库操作错误"""
    error_msg = f"数据库操作[{operation}]失败: {str(error)}"
    logger.error(error_msg)
    print(error_msg)

# API请求和响应模型
class EmailTaskConfig(BaseModel):
    daily_count: int
    target_countries: List[str] = []
    target_regions: List[str] = []  # 新增区域字段
    send_time: str
    workdays: List[int] = [0, 1, 2, 3, 4, 5, 6]  # 发送邮件的工作日(0-6分别代表周一到周日)，默认每天发送
    template_name: str = "C_template.html"  # 默认使用C模板

class TempSendConfig(BaseModel):
    count: int  # 要发送的邮件数量
    target_countries: List[str] = []  # 目标国家列表，为空表示所有国家
    target_regions: List[str] = []  # 目标区域列表，为空表示所有区域
    template_name: str = "C_template.html"  # 使用的邮件模板

class EmailTaskStatus(BaseModel):
    is_running: bool
    daily_count: int
    target_countries: List[str]
    target_regions: List[str] = []  # 新增区域字段
    send_time: str
    workdays: List[int] = []  # 发送邮件的工作日(0-6分别代表周一到周日)
    template_name: str
    last_run_date: Optional[str] = None
    last_sent_count: int = 0
    last_opened_count: int = 0

class EmailStats(BaseModel):
    date: str  # 可以是单个日期或逗号分隔的多个日期
    sent_count: int
    opened_count: int
    open_rate: float
    replied_count: int = 0
    reply_rate: float = 0
    is_all_data: bool = False
    dates: List[str] = []  # 新增字段，存储已处理的日期列表

# 保存和加载配置
def save_config():
    """保存配置到JSON文件，处理datetime对象转换为字符串"""
    config_dir = os.path.join(os.path.dirname(__file__), 'config')
    os.makedirs(config_dir, exist_ok=True)
    
    # 创建配置的副本，处理datetime对象
    config_copy = {}
    for key, value in EMAIL_TASK_CONFIG.items():
        # 如果是datetime对象，转换为字符串
        if isinstance(value, datetime.datetime):
            config_copy[key] = value.strftime('%Y-%m-%d %H:%M:%S')
        # 如果是date对象，也转换为字符串
        elif isinstance(value, datetime.date):
            config_copy[key] = value.strftime('%Y-%m-%d')
        else:
            config_copy[key] = value
    
    config_path = os.path.join(config_dir, 'api_config.json')
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config_copy, f, ensure_ascii=False, indent=2)

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
def get_email_stats(date=None, get_all=False):
    """
    获取邮件统计数据
    
    参数:
        date: 可以是单个日期字符串(YYYY-MM-DD)或多个日期的列表/逗号分隔字符串
        get_all: 是否获取所有数据，如为True，则忽略date参数
    """
    # 初始化返回统计结果
    stats = {
        'sent_count': 0,
        'opened_count': 0,
        'replied_count': 0,  # 新增回复统计字段
        'open_rate': 0,
        'reply_rate': 0,     # 新增回复率字段
        'is_all_data': get_all,
        'dates': []          # 新增处理的日期列表
    }

    # 如果既没有提供日期也没有设置获取所有数据，则默认为当天
    if not date and not get_all:
        date = datetime.datetime.now().strftime('%Y-%m-%d')
        
    # 处理传入的日期参数，将其转化为日期列表
    dates_to_query = []
    if not get_all and date:
        # 处理传入的是逗号分隔的日期字符串
        if isinstance(date, str) and ',' in date:
            dates_to_query = [d.strip() for d in date.split(',') if d.strip()]
        # 如果已经是一个列表
        elif isinstance(date, list):
            dates_to_query = date
        # 单个日期字符串
        else:
            dates_to_query = [date]
    
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
            
            # 查询邮件数量
            if get_all:
                # 查询所有邮件数量
                sent_query = """
                SELECT COUNT(*) as count
                FROM email_tracking
                """
                
                cursor.execute(sent_query)
                sent_result = cursor.fetchone()  # 立即读取第一个查询的结果
                stats['sent_count'] = sent_result['count'] if sent_result else 0
                
                # 查询所有被打开的邮件数量
                opened_query = """
                SELECT COUNT(*) as count
                FROM email_tracking
                WHERE is_opened = TRUE
                """
                
                cursor.execute(opened_query)  # 执行第二个查询
                opened_result = cursor.fetchone()
                stats['opened_count'] = opened_result['count'] if opened_result else 0
                
                # 查询所有被回复的邮件数量
                replied_query = """
                SELECT COUNT(*) as count
                FROM email_tracking
                WHERE is_replied = TRUE
                """
                
                cursor.execute(replied_query)  # 执行第三个查询
                replied_result = cursor.fetchone()
                stats['replied_count'] = replied_result['count'] if replied_result else 0
                
                print(f"从数据库获取到全部统计信息: 总共发送 {stats['sent_count']} 封，已打开 {stats['opened_count']} 封，已回复 {stats['replied_count']} 封")
            else:
                # 处理一个或多个日期的查询
                for single_date in dates_to_query:
                    # 将当前日期添加到处理的日期列表
                    stats['dates'].append(single_date)
                    
                    # 构建查询的日期范围条件
                    date_start = f"{single_date} 00:00:00"
                    date_end = f"{single_date} 23:59:59"
                    
                    # 查询当天发送的邮件数量
                    sent_query = """
                    SELECT COUNT(*) as count
                    FROM email_tracking
                    WHERE sent_time BETWEEN %s AND %s
                    """
                    
                    cursor.execute(sent_query, (date_start, date_end))
                    sent_result = cursor.fetchone()
                    daily_sent = sent_result['count'] if sent_result else 0
                    stats['sent_count'] += daily_sent
                    
                    # 查询当天被打开的邮件数量
                    opened_query = """
                    SELECT COUNT(*) as count
                    FROM email_tracking
                    WHERE is_opened = TRUE AND open_time BETWEEN %s AND %s
                    """
                    
                    cursor.execute(opened_query, (date_start, date_end))
                    opened_result = cursor.fetchone()
                    daily_opened = opened_result['count'] if opened_result else 0
                    stats['opened_count'] += daily_opened
                    
                    # 查询当天被回复的邮件数量
                    replied_query = """
                    SELECT COUNT(*) as count
                    FROM email_tracking
                    WHERE is_replied = TRUE AND reply_time BETWEEN %s AND %s
                    """
                    
                    cursor.execute(replied_query, (date_start, date_end))
                    replied_result = cursor.fetchone()
                    daily_replied = replied_result['count'] if replied_result else 0
                    stats['replied_count'] += daily_replied
                    
                    print(f"从数据库获取到指定日期({single_date})统计信息: 已发送 {daily_sent} 封，已打开 {daily_opened} 封，已回复 {daily_replied} 封")
            
            # 计算打开率和回复率
            stats['open_rate'] = (stats['opened_count'] / stats['sent_count'] * 100) if stats['sent_count'] > 0 else 0
            stats['reply_rate'] = (stats['replied_count'] / stats['sent_count'] * 100) if stats['sent_count'] > 0 else 0
            
            cursor.close()
            connection.close()
            
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
                'open_rate': open_rate,
                'replied_count': 0,
                'reply_rate': 0,
                'is_all_data': get_all,
                'dates': dates_to_query if not get_all else []
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
async def email_sending_task():
    """执行邮件发送任务"""
    print(f"开始执行邮件发送任务...")
    
    if not EMAIL_TASK_CONFIG['is_running']:
        print("任务未启动")
        return
        
    # 检查是否是今天已经运行过
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    if EMAIL_TASK_CONFIG['last_run_date'] == today:
        print("今天已经运行过任务")
        return

    # 发送邮件
    success_count = await send_email_batch()
    
    # 更新任务状态
    EMAIL_TASK_CONFIG['last_run_date'] = today
    EMAIL_TASK_CONFIG['last_sent_count'] = success_count
    
    # 保存到数据库
    if save_task_to_db(EMAIL_TASK_CONFIG):
        print("成功更新任务状态到数据库")
    else:
        print("保存任务状态到数据库失败")
        
    # 保存到配置文件作为备份
    save_config()
    
    print(f"邮件发送任务完成，成功发送: {success_count} 封邮件")

# 临时发送邮件任务
def temp_email_sending_task(count: int, target_countries: List[str] = None, target_regions: List[str] = None, template_name: str = "C_template.html"):
    """临时发送指定数量的邮件到目标国家或区域"""
    print(f"开始执行临时邮件发送任务 - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 处理区域或国家
    countries_to_send = []
    
    # 优先使用区域（如果指定了区域，则忽略国家设置）
    if target_regions and len(target_regions) > 0:
        # 如果指定了区域，将区域扩展为对应的国家列表
        countries_to_send = expand_regions_to_countries(target_regions)
        print(f"按区域发送邮件: {', '.join(target_regions)}")
    elif target_countries and len(target_countries) > 0:
        # 如果只指定了国家列表，则直接使用
        countries_to_send = list(target_countries)
        print(f"按国家发送邮件: {', '.join(target_countries)}")
    else:
        print(f"未指定目标区域或国家，将发送给所有国家")
    
    print(f"目标国家列表：{countries_to_send}")
    
    # 获取所有可能满足条件的收件人（多获取一些以应对发送失败的情况）
    all_potential_recipients = get_recipients_from_db(count * 3, countries_to_send)
    
    if not all_potential_recipients:
        print("没有符合条件的收件人")
        return {"success": False, "sent_count": 0, "message": "没有符合条件的收件人"}
    
    print(f"找到 {len(all_potential_recipients)} 个潜在收件人")
    
    # 获取要使用的模板名称
    print(f"使用邮件模板: {template_name}")
    
    # 加载邮件模板
    load_template(template_name)
    
    # 初始化连接
    init_connections()
    
    # 发送邮件
    success_count = 0
    target_success_count = count  # 目标成功发送数量
    processed_emails = set()  # 用于跟踪已处理的邮箱地址
    
    # 尝试发送邮件给获取的收件人
    for recipient in all_potential_recipients:
        # 检查是否已达到目标数量
        if success_count >= target_success_count:
            break
            
        # 检查是否已处理过该邮箱
        recipient_email = recipient.get('email', '').strip().upper()
        if not recipient_email or recipient_email in processed_emails:
            continue
            
        # 标记该邮箱已处理
        processed_emails.add(recipient_email)
        
        # 尝试发送邮件
        if send_email(recipient):
            success_count += 1
            print(f"成功发送至 {recipient_email}，当前进度: {success_count}/{target_success_count}")
        else:
            print(f"发送至 {recipient_email} 失败或已经发送过，跳过")
            
        # 短暂延迟，避免被识别为垃圾邮件发送者
        time.sleep(5)
    
    # 如果处理完所有收件人后仍未达到目标数量
    if success_count < target_success_count:
        print(f"已处理所有可用的收件人，但未达到目标数量。成功数量: {success_count}/{target_success_count}")
        print(f"请检查数据库中是否有足够的未发送邮件的联系人")
    else:
        print(f"成功完成发送目标: {success_count}/{target_success_count}")
    
    print(f"邮件发送完成。成功: {success_count}/{target_success_count}")
    
    # 更新跟踪服务器的发送统计
    try:
        requests.post(
            f"{EMAIL_CONFIG['tracker_url']}/stats/update",
            json={'sent': success_count}
        )
    except Exception as e:
        print(f"更新跟踪服务器统计信息失败: {e}")
    
    return {
        "success": True, 
        "sent_count": success_count, 
        "message": f"已发送 {success_count} 封邮件"
    }

def get_next_run_time():
    """获取下一次任务执行的时间"""
    if not EMAIL_TASK_CONFIG['is_running']:
        return "未知"

    now = datetime.datetime.now()
    
    # 获取当前小时和分钟
    current_hour = now.hour
    current_minute = now.minute
    
    # 解析设置的发送时间
    send_time_parts = EMAIL_TASK_CONFIG['send_time'].split(':')
    send_hour = int(send_time_parts[0])
    send_minute = int(send_time_parts[1])
    
    # 获取今天的发送时间
    today_send_time = now.replace(hour=send_hour, minute=send_minute, second=0, microsecond=0)
    
    # 检查今天是否是工作日
    is_today_workday = now.weekday() in EMAIL_TASK_CONFIG['workdays']
    
    # 判断下一次发送时间
    next_run = None
    
    # 如果今天是工作日且当前时间小于发送时间，则下一次发送时间是今天
    if is_today_workday and now < today_send_time:
        next_run = today_send_time
    else:
        # 否则寻找下一个工作日
        next_day = now.date() + datetime.timedelta(days=1)
        days_to_add = 1
        
        # 寻找下一个工作日
        while days_to_add < 8:  # 最多循环7天，避免无限循环
            if next_day.weekday() in EMAIL_TASK_CONFIG['workdays']:
                next_run = datetime.datetime.combine(
                    next_day,
                    datetime.time(hour=send_hour, minute=send_minute)
                )
                break
            next_day = next_day + datetime.timedelta(days=1)
            days_to_add += 1
    
    if not next_run:
        return "未知"
    
    weekday_names = {0: "星期一", 1: "星期二", 2: "星期三", 3: "星期四", 
                    4: "星期五", 5: "星期六", 6: "星期日"}
    current_weekday = weekday_names[now.weekday()]
    next_weekday = weekday_names[next_run.weekday()]

    # 计算时间差
    time_diff = next_run - now
    days = time_diff.days
    hours = time_diff.seconds // 3600
    minutes = (time_diff.seconds % 3600) // 60
    seconds = time_diff.seconds % 60

    # 构建时间差描述
    if days > 0:
        time_desc = f"{days}天{hours}小时{minutes}分钟{seconds}秒"
    else:
        time_desc = f"{hours}小时{minutes}分钟{seconds}秒"

    # 如果是不同的日期，显示下一次执行的具体日期和时间
    if next_run.date() != now.date():
        result = f"当前{current_weekday} {now.strftime('%H:%M')}，下次任务将在{next_weekday} {next_run.strftime('%Y-%m-%d %H:%M')}执行，还有{time_desc}"
    else:
        result = f"当前{current_weekday} {now.strftime('%H:%M')}，距离下次发送任务还有: {time_desc}"
    
    return result

# 修改定时任务调度器
def run_scheduler():
    """运行定时任务调度器，并显示倒计时"""
    last_print_time = 0
    print_interval = 300  # 每5分钟打印一次倒计时

    while EMAIL_TASK_CONFIG['is_running']:
        current_time = time.time()
        
        # 每隔5分钟显示一次倒计时
        if current_time - last_print_time >= print_interval:
            next_run_time = get_next_run_time()
            log_message = f"距离下次发送任务还有: {next_run_time}"
            logger.info(log_message)
            last_print_time = current_time
            
        schedule.run_pending()
        time.sleep(1)  # 改为1秒检查一次，提高定时任务的准确性

# 修改邮件发送任务完成后的处理
def update_task_status(success_count: int):
    """更新任务状态到数据库"""
    EMAIL_TASK_CONFIG['last_sent_count'] = success_count
    stats = get_email_stats()
    EMAIL_TASK_CONFIG['last_opened_count'] = stats['opened_count']
    
    # 保存到数据库
    try:
        if not save_task_to_db(EMAIL_TASK_CONFIG):
            log_db_error("更新任务状态", Exception("保存失败"))
    except Exception as e:
        log_db_error("更新任务状态", e)

# API路由
@app.get("/", tags=["根路径"])
async def root():
    return {"message": "邮件发送系统API服务已启动"}

@app.get("/status", response_model=EmailTaskStatus, tags=["任务状态"])
async def get_status():
    """获取当前邮件发送任务的状态"""
    status = {
        "is_running": EMAIL_TASK_CONFIG['is_running'],
        "daily_count": EMAIL_TASK_CONFIG['daily_count'],
        "target_countries": EMAIL_TASK_CONFIG['target_countries'],
        "target_regions": EMAIL_TASK_CONFIG['target_regions'],
        "send_time": EMAIL_TASK_CONFIG['send_time'],
        "workdays": EMAIL_TASK_CONFIG['workdays'],
        "template_name": EMAIL_TASK_CONFIG['template_name'],
        "last_run_date": EMAIL_TASK_CONFIG['last_run_date'],
        "last_sent_count": EMAIL_TASK_CONFIG['last_sent_count'],
        "last_opened_count": EMAIL_TASK_CONFIG['last_opened_count']
    }
    
    # 添加状态描述
    weekdays_names = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
    workdays_str = ", ".join([weekdays_names[day] for day in EMAIL_TASK_CONFIG['workdays']])
    countries_str = ", ".join(EMAIL_TASK_CONFIG['target_countries']) if EMAIL_TASK_CONFIG['target_countries'] else "所有国家"
    regions_str = ", ".join(EMAIL_TASK_CONFIG['target_regions']) if EMAIL_TASK_CONFIG['target_regions'] else "无指定区域"
    
    status_description = f"任务状态：{'运行中' if EMAIL_TASK_CONFIG['is_running'] else '已停止'}\n"
    status_description += f"每日发送数量：{EMAIL_TASK_CONFIG['daily_count']}\n"
    status_description += f"发送时间：{workdays_str} {EMAIL_TASK_CONFIG['send_time']}\n"
    status_description += f"目标国家：{countries_str}\n"
    status_description += f"目标区域：{regions_str}\n"
    status_description += f"使用模板：{EMAIL_TASK_CONFIG['template_name']}\n"
    
    if EMAIL_TASK_CONFIG['last_run_date']:
        status_description += f"上次运行日期：{EMAIL_TASK_CONFIG['last_run_date']}\n"
        status_description += f"上次发送数量：{EMAIL_TASK_CONFIG['last_sent_count']}\n"
        status_description += f"上次打开数量：{EMAIL_TASK_CONFIG['last_opened_count']}"
    
    if EMAIL_TASK_CONFIG['is_running']:
        next_run = get_next_run_time()
        status_description += f"\n{next_run}"
    
    print(f"状态详情:\n{status_description}")
    return status

@app.post("/start", response_model=EmailTaskStatus, tags=["任务控制"])
async def start_task(config: EmailTaskConfig, background_tasks: BackgroundTasks):
    """启动邮件发送任务"""
    global scheduler_thread
    
    if EMAIL_TASK_CONFIG['is_running']:
        raise HTTPException(status_code=400, detail="任务已在运行中")
    
    # 更新配置
    EMAIL_TASK_CONFIG['daily_count'] = config.daily_count
    EMAIL_TASK_CONFIG['target_countries'] = config.target_countries
    EMAIL_TASK_CONFIG['target_regions'] = config.target_regions
    EMAIL_TASK_CONFIG['send_time'] = config.send_time
    EMAIL_TASK_CONFIG['workdays'] = config.workdays
    EMAIL_TASK_CONFIG['template_name'] = config.template_name
    EMAIL_TASK_CONFIG['is_running'] = True
    
    # 保存配置到数据库
    if not save_task_to_db(EMAIL_TASK_CONFIG):
        raise HTTPException(status_code=500, detail="保存任务配置到数据库失败")
    
    # 保存配置到文件（作为备份）
    save_config()
    
    # 清除之前的调度
    schedule.clear()
    
    # 设置定时任务，只在指定工作日运行
    workday_map = {
        0: schedule.every().monday,
        1: schedule.every().tuesday,
        2: schedule.every().wednesday,
        3: schedule.every().thursday,
        4: schedule.every().friday,
        5: schedule.every().saturday,
        6: schedule.every().sunday
    }
    
    # 添加邮件发送任务
    for workday in config.workdays:
        if workday in workday_map:
            workday_map[workday].at(config.send_time).do(email_sending_task)
    
    # 设置其他定时任务
    schedule.every(1).hours.do(check_replies)
    schedule.every(30).minutes.do(maintain_connections)
    
    # 启动调度器线程
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    # 立即显示第一次倒计时信息
    next_run_time = get_next_run_time()
    logger.info(f"距离下次发送任务还有: {next_run_time}")
    
    # 计算并显示距离下次执行的时间
    next_run_time = get_next_run_time()
    countries_info = f"目标国家: {', '.join(config.target_countries)}" if config.target_countries else "所有国家"
    workdays_names = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}
    workdays_info = ", ".join([workdays_names[day] for day in config.workdays])
    print(f"已启动邮件发送任务，使用模板 {config.template_name}，在 {workdays_info} {config.send_time} 发送 {config.daily_count} 封邮件，{countries_info}")
    print(f"距离下次任务执行还有: {next_run_time}")
    
    return await get_status()

@app.post("/stop", response_model=EmailTaskStatus, tags=["任务控制"])
async def stop_task():
    """停止邮件发送任务"""
    EMAIL_TASK_CONFIG['is_running'] = False
    
    # 保存配置到数据库
    if not save_task_to_db(EMAIL_TASK_CONFIG):
        raise HTTPException(status_code=500, detail="保存任务配置到数据库失败")
    
    # 保存配置到文件（作为备份）
    save_config()
    
    # 清除调度
    schedule.clear()
    
    print("已停止邮件发送任务")
    
    return await get_status()

@app.get("/stats", response_model=EmailStats, tags=["统计数据"])
async def get_stats(date: Optional[str] = None, all_data: bool = False):
    """
    获取邮件统计数据
    - date: 日期，格式为"YYYY-MM-DD"，默认为当天。也可以传入多个日期，格式为"YYYY-MM-DD,YYYY-MM-DD"（逗号分隔）
    - all_data: 是否获取所有数据的统计，如果为True，则忽略date参数，统计所有邮件记录
    """
    stats = get_email_stats(date, all_data)
    
    return {
        "date": ",".join(stats['dates']) if 'dates' in stats and stats['dates'] else ("all" if all_data else (date or datetime.datetime.now().strftime('%Y-%m-%d'))),
        "sent_count": stats['sent_count'],
        "opened_count": stats['opened_count'],
        "open_rate": stats['open_rate'],
        "replied_count": stats['replied_count'],
        "reply_rate": stats.get('reply_rate', 0),
        "is_all_data": all_data
    }

@app.post("/send-now", tags=["任务控制"])
async def send_now(background_tasks: BackgroundTasks):
    """立即执行一次邮件发送任务，不影响原有的定时任务"""
    background_tasks.add_task(email_sending_task)
    return {"message": "邮件发送任务已在后台启动，请稍后查看统计数据"}

@app.post("/send-temp", tags=["任务控制"])
async def send_temp(config: TempSendConfig):
    """
    临时发送指定数量的邮件到指定国家或区域
    
    - count: 要发送的邮件数量
    - target_countries: 目标国家列表，为空表示所有国家。请使用中文国家名称，例如["中国", "美国", "日本"]
    - target_regions: 目标区域列表，如["南美洲", "东南亚", "非洲"]。系统会自动发送邮件到这些区域的所有国家
    - template_name: 要使用的邮件模板名称，默认为"C_template.html"
    
    注意: 请只使用target_regions或target_countries中的一个，不要同时使用。如果两者都提供，系统将优先使用target_regions并忽略target_countries。
    """
    result = temp_email_sending_task(
        count=config.count,
        target_countries=config.target_countries,
        target_regions=config.target_regions,
        template_name=config.template_name
    )
    
    if result["success"]:
        return {"message": result["message"], "sent_count": result["sent_count"]}
    else:
        raise HTTPException(status_code=400, detail=result["message"])

# 修改启动事件处理函数
@app.on_event("startup")
async def startup_event():
    """启动事件处理函数"""
    global scheduler_thread
    
    # 只从数据库加载配置
    task_config = load_task_from_db()
    if task_config:
        # 更新全局配置
        EMAIL_TASK_CONFIG.update(task_config)
        logger.info("从数据库加载任务配置成功")
        
        # 如果任务正在运行，则启动调度器
        if EMAIL_TASK_CONFIG['is_running']:
            # 设置定时任务
            workday_map = {
                0: schedule.every().monday,
                1: schedule.every().tuesday,
                2: schedule.every().wednesday,
                3: schedule.every().thursday,
                4: schedule.every().friday,
                5: schedule.every().saturday,
                6: schedule.every().sunday
            }
            
            # 添加邮件发送任务
            for workday in EMAIL_TASK_CONFIG['workdays']:
                if workday in workday_map:
                    workday_map[workday].at(EMAIL_TASK_CONFIG['send_time']).do(email_sending_task)
            
            # 设置其他定时任务
            schedule.every(1).hours.do(check_replies)
            schedule.every(30).minutes.do(maintain_connections)
            
            # 启动调度器线程
            scheduler_thread = threading.Thread(target=run_scheduler)
            scheduler_thread.daemon = True
            scheduler_thread.start()
            
            # 显示下次执行时间
            next_run_time = get_next_run_time()
            logger.info(f"距离下次发送任务还有: {next_run_time}")
    else:
        # 如果没有运行中的任务，初始化一个空配置
        EMAIL_TASK_CONFIG.update({
            'is_running': False,
            'daily_count': 50,
            'target_countries': [],
            'target_regions': [],
            'send_time': '09:00',
            'workdays': [0, 1, 2, 3, 4, 5, 6],
            'template_name': 'C_template.html',
            'last_run_date': None,
            'last_sent_count': 0,
            'last_opened_count': 0
        })
        logger.info("没有运行中的任务")
    
    logger.info("邮件发送系统启动")

# 主函数
if __name__ == "__main__":
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)
