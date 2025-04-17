#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置加载器：从.env文件加载环境变量
"""

import os
import logging
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('config_loader')

# 加载.env文件
env_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path=env_path)

# 数据库配置
DB_CONFIG = {
    'host': os.getenv('DB_HOST'),
    'user': os.getenv('DB_USER'),
    'password': os.getenv('DB_PASSWORD'),
    'database': os.getenv('DB_NAME'),
    'table_name': 'companies'  # 表名不是敏感信息，保留在代码中
}

# 邮件配置
EMAIL_CONFIG = {
    'smtp_server': os.getenv('SMTP_SERVER'),
    'smtp_port': int(os.getenv('SMTP_PORT', '465')),
    'imap_server': os.getenv('IMAP_SERVER'),
    'imap_port': int(os.getenv('IMAP_PORT', '993')),
    'username': os.getenv('EMAIL_USERNAME'),
    'password': os.getenv('EMAIL_PASSWORD'),
    'sender_name': os.getenv('SENDER_NAME'),
    'tracker_url': os.getenv('TRACKER_URL', 'http://localhost:5000'),
    'verify_ssl': False  # 不是敏感信息，保留在代码中
}

def get_db_config():
    """获取数据库配置"""
    return DB_CONFIG

def get_email_config():
    """获取邮件配置"""
    return EMAIL_CONFIG

# 验证配置是否完整
def validate_config():
    """验证配置是否完整，如果有缺失则打印警告"""
    missing_db_config = [key for key, value in DB_CONFIG.items() if value is None and key != 'table_name']
    missing_email_config = [key for key, value in EMAIL_CONFIG.items() if value is None and key not in ['verify_ssl']]
    
    if missing_db_config:
        logger.warning(f"数据库配置缺失: {', '.join(missing_db_config)}")
    
    if missing_email_config:
        logger.warning(f"邮件配置缺失: {', '.join(missing_email_config)}")
    
    return len(missing_db_config) == 0 and len(missing_email_config) == 0

# 当模块被导入时验证配置
if not validate_config():
    logger.warning("请确保.env文件存在并包含所有必要的环境变量")
