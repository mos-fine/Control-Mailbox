#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
邮件发送程序：负责定时发送带有跟踪图片的邮件
"""

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
import logging
import time
import json
import uuid
import os
import schedule
import imaplib
import email
from email.header import decode_header
from datetime import datetime
import threading
import requests
import mysql.connector
from mysql.connector import Error

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/sender.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('email_sender')

# 确保日志目录存在
os.makedirs('logs', exist_ok=True)

# 邮件配置
EMAIL_CONFIG = {
    'smtp_server': 'smtp.vei-mei.com',        # 网易邮箱SMTP服务器
    'smtp_port': 465,                     # SMTP SSL端口
    'imap_server': 'imap.vei-mei.com',        # IMAP服务器
    'imap_port': 993,                     # IMAP SSL端口
    'username': 'elaine@vei-mei.com',     # 发件人邮箱
    'password': 'HVVP2Cj9JBHFNxHe',      # 授权码
    'sender_name': '艾琳',                # 发件人显示名称
    'tracker_url': 'http://localhost:5000',  # 跟踪服务器地址
    'verify_ssl': False                   # SSL验证选项，设为False以跳过证书验证
}

# 数据库配置
DB_CONFIG = {
    'host': '8.153.199.241',
    'user': 'Rex',
    'password': '3528846780Rex',
    'database': 'B2B',
    'table_name': 'companies', # 假设表名为contacts，如有不同请修改
    'batch_size': 1          # 每次从数据库获取的联系人数量
}

# 存储收件人列表和邮件模板
RECIPIENTS = []
EMAIL_TEMPLATE = None
SEND_INTERVAL = 24  # 默认发送间隔（小时）

# 全局连接对象
smtp_connection = None
imap_connection = None
connection_lock = threading.Lock()  # 用于保护连接对象的线程锁

# 创建SSL上下文
def create_ssl_context():
    context = ssl.create_default_context()
    if 'verify_ssl' in EMAIL_CONFIG and not EMAIL_CONFIG['verify_ssl']:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        logger.info("已禁用SSL证书验证")
    return context

# 初始化SMTP连接
def init_smtp_connection():
    global smtp_connection
    
    with connection_lock:
        try:
            if smtp_connection is not None:
                try:
                    # 尝试发送NOOP命令检查连接是否活跃
                    smtp_connection.noop()
                    logger.debug("SMTP连接正常")
                    return True
                except:
                    # 连接已断开，需要重新连接
                    logger.info("SMTP连接已断开，正在重新连接...")
                    try:
                        smtp_connection.quit()
                    except:
                        pass
                    smtp_connection = None
            
            # 创建新连接
            context = create_ssl_context()
            smtp_connection = smtplib.SMTP_SSL(
                EMAIL_CONFIG['smtp_server'], 
                EMAIL_CONFIG['smtp_port'], 
                context=context
            )
            smtp_connection.login(EMAIL_CONFIG['username'], EMAIL_CONFIG['password'])
            logger.info("SMTP连接已成功建立")
            return True
        except Exception as e:
            logger.error(f"建立SMTP连接失败: {e}")
            smtp_connection = None
            return False

# 初始化IMAP连接
def init_imap_connection():
    global imap_connection
    
    with connection_lock:
        try:
            if imap_connection is not None:
                try:
                    # 尝试发送NOOP命令检查连接是否活跃
                    status, _ = imap_connection.noop()
                    if status == 'OK':
                        logger.debug("IMAP连接正常")
                        return True
                except:
                    # 连接已断开，需要重新连接
                    logger.info("IMAP连接已断开，正在重新连接...")
                    try:
                        imap_connection.logout()
                    except:
                        pass
                    imap_connection = None
            
            # 创建新连接
            context = create_ssl_context()
            imap_connection = imaplib.IMAP4_SSL(
                EMAIL_CONFIG['imap_server'], 
                EMAIL_CONFIG['imap_port'], 
                ssl_context=context
            )
            imap_connection.login(EMAIL_CONFIG['username'], EMAIL_CONFIG['password'])
            imap_connection.select('INBOX')
            logger.info("IMAP连接已成功建立")
            return True
        except Exception as e:
            logger.error(f"建立IMAP连接失败: {e}")
            imap_connection = None
            return False

# 初始化所有连接
def init_connections():
    smtp_success = init_smtp_connection()
    imap_success = init_imap_connection()
    return smtp_success and imap_success

# 定期检查和维护连接的函数
def maintain_connections():
    logger.info("执行连接健康检查...")
    init_smtp_connection()
    init_imap_connection()

# 从数据库获取收件人列表
def load_recipients():
    global RECIPIENTS
    try:
        # 创建数据库连接
        connection = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database']
        )
        
        if connection.is_connected():
            # 创建游标对象
            cursor = connection.cursor(dictionary=True)
            
            # 查询尚未发送过邮件的联系人（contact_email_sent = 0）
            query = f"""
            SELECT id, company_name, company_country, contact_name, contact_email, contact_position
            FROM {DB_CONFIG['table_name']}
            WHERE contact_email IS NOT NULL
            AND contact_email != ''
            AND contact_email_sent = 0
            LIMIT {DB_CONFIG['batch_size']}
            """
            
            cursor.execute(query)
            records = cursor.fetchall()
            
            RECIPIENTS = []
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
                RECIPIENTS.append(recipient)
            
            logger.info(f"已从数据库加载 {len(RECIPIENTS)} 个收件人")
            
            # 关闭游标和连接
            cursor.close()
            connection.close()
        else:
            logger.error("无法连接到数据库")
    except Error as e:
        logger.error(f"数据库操作失败: {e}")
    except Exception as e:
        logger.error(f"加载收件人列表失败: {e}")

# 加载邮件模板
def load_template(template_name='C_template.html'):
    global EMAIL_TEMPLATE
    try:
        template_path = f'templates/{template_name}'
        if os.path.exists(template_path):
            with open(template_path, 'r', encoding='utf-8') as f:
                EMAIL_TEMPLATE = f.read()
            logger.info(f"邮件模板 {template_name} 加载成功")
        else:
            logger.warning(f"邮件模板文件 {template_name} 不存在，将使用默认模板")
            EMAIL_TEMPLATE = """
            <html>
            <body>
                <p>尊敬的{name}：</p>
                <p>您好！</p>
                <p>这是一封测试邮件。</p>
                <p>祝好，</p>
                <p>艾琳</p>
                <img src="{tracker_url}/track/{email_id}" width="1" height="1" />
            </body>
            </html>
            """
    except Exception as e:
        logger.error(f"加载邮件模板 {template_name} 失败: {e}")
        EMAIL_TEMPLATE = """
        <html>
        <body>
            <p>尊敬的{name}：</p>
            <p>您好！</p>
            <p>这是一封测试邮件。</p>
            <p>祝好，</p>
            <p>艾琳</p>
            <img src="{tracker_url}/track/{email_id}" width="1" height="1" />
        </body>
        </html>
        """

# 检查邮件是否已经发送到指定收件人
def check_email_already_sent(email):
    """
    检查邮件是否已经发送到指定邮箱地址
    """
    try:
        connection = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database']
        )
        
        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)
            
            # 查询email_tracking表
            query = """
            SELECT id FROM email_tracking
            WHERE email = %s AND sent_time IS NOT NULL
            LIMIT 1
            """
            
            cursor.execute(query, (email,))
            result = cursor.fetchone()
            
            cursor.close()
            connection.close()
            
            return result is not None
        
    except Error as e:
        logger.error(f"检查邮件是否已发送时出错: {e}")
        
    return False

# 发送单封邮件
def send_email(recipient):
    global smtp_connection
    
    name = recipient.get('name', '用户')
    to_email = recipient.get('email')
    recipient_id = recipient.get('id')
    company_name = recipient.get('company', '')
    
    if not to_email:
        logger.error(f"收件人 {name} 没有邮箱地址")
        return False
        
    # 检查是否已经给该邮箱发送过邮件
    if check_email_already_sent(to_email):
        logger.info(f"邮箱 {to_email} 已经发送过邮件，跳过发送")
        return False
    
    # 生成唯一邮件ID
    email_id = str(uuid.uuid4())
    
    # 创建邮件
    msg = MIMEMultipart('alternative')
    msg['Subject'] = recipient.get('subject', '重要信息')
    msg['From'] = formataddr((EMAIL_CONFIG['sender_name'], EMAIL_CONFIG['username']))
    msg['To'] = to_email
    msg['Message-ID'] = f"<{email_id}@{EMAIL_CONFIG['username'].split('@')[1]}>"
    
    # 填充模板
    html_content = EMAIL_TEMPLATE.format(
        name=name,
        tracker_url=EMAIL_CONFIG['tracker_url'],
        email_id=email_id
    )
    
    # 附加HTML内容
    msg.attach(MIMEText(html_content, 'html'))
    
    try:
        # 确保SMTP连接可用
        if not init_smtp_connection():
            logger.error("无法建立SMTP连接，邮件发送失败")
            return False
        
        # 使用已建立的连接发送邮件
        with connection_lock:
            smtp_connection.sendmail(EMAIL_CONFIG['username'], to_email, msg.as_string())
        
        logger.info(f"邮件已成功发送至 {to_email}，邮件ID: {email_id}")
        
        # 将邮件信息保存到跟踪服务
        try:
            response = requests.post(
                f"{EMAIL_CONFIG['tracker_url']}/track/register",
                json={
                    'email_id': email_id,
                    'recipient': to_email,
                    'name': name,
                    'sent_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            )
            if response.status_code == 200:
                logger.info(f"邮件 {email_id} 已在跟踪服务器注册")
            else:
                logger.warning(f"邮件 {email_id} 在跟踪服务器注册失败: {response.text}")
        except Exception as e:
            logger.error(f"向跟踪服务器注册邮件失败: {e}")
            
        sent_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 更新email_tracking表
        try:
            connection = mysql.connector.connect(
                host=DB_CONFIG['host'],
                user=DB_CONFIG['user'],
                password=DB_CONFIG['password'],
                database=DB_CONFIG['database']
            )
            
            if connection.is_connected():
                cursor = connection.cursor()
                
                # 将邮件信息保存到email_tracking表
                insert_query = """
                INSERT INTO email_tracking 
                (company_name, contact_name, email, is_replied, is_opened, sent_time, email_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                
                cursor.execute(
                    insert_query, 
                    (company_name, name, to_email, False, False, sent_time, email_id)
                )
                connection.commit()
                
                logger.info(f"已将邮件信息保存到email_tracking表，邮件ID: {email_id}")
                
            # 更新联系人的邮件发送状态
            if recipient_id:
                cursor = connection.cursor()
                
                # 更新联系人的邮件发送状态
                update_query = f"""
                UPDATE {DB_CONFIG['table_name']}
                SET contact_email_sent = 1
                WHERE id = %s
                """
                
                cursor.execute(update_query, (recipient_id,))
                connection.commit()
                
                logger.info(f"已更新ID为 {recipient_id} 的联系人邮件发送状态")
                
            cursor.close()
            connection.close()
        except Error as e:
            logger.error(f"更新数据库中邮件状态失败: {e}")
        
        return True
    except Exception as e:
        logger.error(f"发送邮件到 {to_email} 失败: {e}")
        # 连接可能已断开，下次将重新连接
        with connection_lock:
            try:
                smtp_connection.quit()
            except:
                pass
            smtp_connection = None
        return False

# 批量发送邮件
def send_batch():
    logger.info("开始批量发送邮件...")
    
    success_count = 0
    for recipient in RECIPIENTS:
        if send_email(recipient):
            success_count += 1
        time.sleep(5)  # 短暂延迟，避免被识别为垃圾邮件发送者
    
    logger.info(f"批量发送完成。成功: {success_count}/{len(RECIPIENTS)}")
    
    # 更新跟踪服务器的发送统计
    try:
        requests.post(
            f"{EMAIL_CONFIG['tracker_url']}/stats/update",
            json={'sent': success_count}
        )
    except Exception as e:
        logger.error(f"更新跟踪服务器统计信息失败: {e}")

# 检查邮件回复
def check_replies():
    global imap_connection
    
    logger.info("开始检查邮件回复...")
    
    try:
        # 确保IMAP连接可用
        if not init_imap_connection():
            logger.error("无法建立IMAP连接，邮件检查失败")
            return
            
        with connection_lock:
            # 刷新收件箱状态
            imap_connection.select('INBOX')
            
            # 搜索所有未读邮件
            status, data = imap_connection.search(None, 'UNSEEN')
            
            if status != 'OK':
                logger.error("无法搜索邮件")
                return
            
            message_nums = data[0].split()
        
        # 逐个处理邮件，避免长时间占用锁
        for num in message_nums:
            with connection_lock:
                status, data = imap_connection.fetch(num, '(RFC822)')
                
                if status != 'OK':
                    logger.error(f"无法获取邮件 {num}")
                    continue
                
                raw_email = data[0][1]
            
            # 在锁外处理邮件内容
            email_message = email.message_from_bytes(raw_email)
            
            # 获取主题和发件人
            subject = decode_header(email_message["Subject"])[0][0]
            if isinstance(subject, bytes):
                subject = subject.decode()
            
            from_email = email.utils.parseaddr(email_message["From"])[1]
            
            # 获取邮件内容
            body = ""
            if email_message.is_multipart():
                for part in email_message.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/plain" or content_type == "text/html":
                        try:
                            body = part.get_payload(decode=True).decode()
                            break
                        except:
                            pass
            else:
                body = email_message.get_payload(decode=True).decode()
            
            # 检查是否为回复，查找In-Reply-To或References字段
            in_reply_to = email_message.get("In-Reply-To", "")
            references = email_message.get("References", "")
            
            # 从In-Reply-To或References中提取邮件ID
            reply_to_id = None
            
            if in_reply_to:
                # 格式通常是 <id@domain>
                reply_to_id = in_reply_to.strip("<>").split("@")[0]
            elif references:
                # 可能包含多个引用，通常最早的ID是最后一个
                ids = references.split()
                if ids:
                    reply_to_id = ids[-1].strip("<>").split("@")[0]
            
            if reply_to_id:
                logger.info(f"收到邮件回复，回复ID: {reply_to_id}, 来自: {from_email}")
                
                # 向跟踪服务器报告回复
                try:
                    requests.post(
                        f"{EMAIL_CONFIG['tracker_url']}/reply",
                        json={
                            'email_id': reply_to_id,
                            'from': from_email,
                            'content': body[:200]  # 只保存前200个字符的内容
                        }
                    )
                except Exception as e:
                    logger.error(f"向跟踪服务器报告回复失败: {e}")
            
            # 标记邮件为已读
            with connection_lock:
                imap_connection.store(num, '+FLAGS', '\\Seen')
    
    except Exception as e:
        logger.error(f"检查邮件回复时出错: {e}")
        # 连接可能已断开，下次将重新连接
        with connection_lock:
            try:
                imap_connection.logout()
            except:
                pass
            imap_connection = None

# 创建配置目录和示例收件人列表
def init_config():
    os.makedirs('config', exist_ok=True)
    os.makedirs('templates', exist_ok=True)
    
    # 如果收件人列表不存在，创建示例文件
    if not os.path.exists('config/recipients.json'):
        example_recipients = [
            {
                "name": "张三",
                "email": "rongbaowei4@gmail.com",
                "subject": "项目合作邀请"
            },
            {
                "name": "李四",
                "email": "rongbaowei4@gmail.com",
                "subject": "业务洽谈"
            }
        ]
        
        with open('config/recipients.json', 'w', encoding='utf-8') as f:
            json.dump(example_recipients, f, ensure_ascii=False, indent=2)
        
        logger.info("已创建示例收件人列表")
    
    # 如果邮件模板不存在，创建示例模板
    if not os.path.exists('templates/email_template.html'):
        example_template = """
        <html>
        <body>
            <p>尊敬的{name}：</p>
            <p>您好！</p>
            <p>很高兴与您取得联系。我司正在开展新的业务项目，诚邀您参与合作。</p>
            <p>如您有兴趣，请回复此邮件，我们可以进一步沟通详情。</p>
            <p>期待您的回复！</p>
            <p>祝好，</p>
            <p>艾琳</p>
            <img src="{tracker_url}/track/{email_id}" width="1" height="1" />
        </body>
        </html>
        """
        
        with open('templates/email_template.html', 'w', encoding='utf-8') as f:
            f.write(example_template)
        
        logger.info("已创建示例邮件模板")

# 定时任务函数
def schedule_jobs():
    global SEND_INTERVAL
    
    # 配置定时发送邮件和检查回复
    schedule.every(SEND_INTERVAL).hours.do(send_batch)
    schedule.every(1).hours.do(check_replies)
    # 每30分钟检查一次连接状态
    schedule.every(30).minutes.do(maintain_connections)
    
    logger.info(f"已设置定时任务：每{SEND_INTERVAL}小时发送一次邮件，每1小时检查回复，每30分钟检查连接状态")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

# 打印当前统计信息
def print_stats():
    try:
        response = requests.get(f"{EMAIL_CONFIG['tracker_url']}/stats")
        if response.status_code == 200:
            stats = response.json()
            print("\n===== 邮件统计信息 =====")
            print(f"发送成功: {stats['sent']} 封")
            print(f"已打开: {stats['opened']} 封")
            print(f"已回复: {stats['replied']} 封")
            print("========================\n")
        else:
            logger.error(f"获取统计信息失败: {response.text}")
    except Exception as e:
        logger.error(f"获取统计信息时出错: {e}")

# 查看已发送邮件的打开情况
def view_email_status():
    try:
        # 获取详细的邮件跟踪信息
        response = requests.get(f"{EMAIL_CONFIG['tracker_url']}/stats")
        if response.status_code != 200:
            logger.error(f"获取邮件跟踪信息失败: {response.text}")
            print("无法获取邮件跟踪信息，请确保跟踪服务器正在运行")
            return
            
        stats = response.json()
        details = stats.get('details', {})
        
        if not details:
            print("目前没有发送记录，或跟踪服务器没有保存任何邮件数据")
            return
            
        print("\n===== 邮件打开情况 =====")
        print("邮件ID\t收件人\t收件人名称\t发送时间\t\t\t状态\t\t打开时间")
        print("---------------------------------------------------------------------------------------------")
        
        # 将邮件按发送时间排序（最新的在前）
        sorted_emails = sorted(
            [(email_id, info) for email_id, info in details.items()],
            key=lambda x: x[1].get('sent_time', ''),
            reverse=True
        )
        
        for email_id, info in sorted_emails:
            recipient = info.get('recipient', '未知')
            name = info.get('name', '未知')
            sent_time = info.get('sent_time', '未知')
            
            if info.get('opened', False):
                status = "已打开"
                opened_time = info.get('opened_time', '未知')
            else:
                status = "未打开"
                opened_time = "N/A"
                
            # 截断邮件ID，只显示前8位
            short_id = email_id[:8] + "..."
                
            print(f"{short_id}\t{recipient}\t{name}\t\t{sent_time}\t{status}\t{opened_time}")
            
        print("\n统计信息:")
        print(f"总共发送: {stats.get('sent', 0)} 封")
        print(f"已打开: {stats.get('opened', 0)} 封")
        print(f"已回复: {stats.get('replied', 0)} 封")
        print(f"打开率: {stats.get('opened', 0)/stats.get('sent', 1)*100:.2f}%" if stats.get('sent', 0) > 0 else "N/A")
        print("===========================\n")
        
    except Exception as e:
        logger.error(f"查看邮件状态时出错: {e}")
        print(f"查看邮件状态时出错: {e}")

if __name__ == "__main__":
    # 初始化配置和示例文件
    init_config()
    
    # 加载收件人和模板
    load_recipients()
    load_template()
    
    # 初始化持久连接
    logger.info("正在初始化邮件服务器连接...")
    if init_connections():
        logger.info("邮件服务器连接初始化成功")
    else:
        logger.warning("邮件服务器连接初始化失败，将在发送邮件时重试")
    
    # 启动定时任务线程
    scheduler_thread = threading.Thread(target=schedule_jobs)
    scheduler_thread.daemon = True
    scheduler_thread.start()
    
    logger.info("邮件发送系统已启动")
    
    # 简单的命令行界面
    while True:
        print("\n===== 邮件发送系统 =====")
        print("1. 立即发送邮件")
        print("2. 检查邮件回复")
        print("3. 显示统计信息")
        print("4. 查看邮件打开情况")
        print("5. 修改发送间隔")
        print("6. 退出")
        
        choice = input("请选择操作 [1-6]: ")
        
        if choice == '1':
            send_batch()
        elif choice == '2':
            check_replies()
        elif choice == '3':
            print_stats()
        elif choice == '4':
            view_email_status()
        elif choice == '5':
            try:
                hours = int(input("请输入新的发送间隔（小时）: "))
                if hours > 0:
                    SEND_INTERVAL = hours
                    # 重新设置定时任务
                    schedule.clear()
                    schedule.every(SEND_INTERVAL).hours.do(send_batch)
                    schedule.every(1).hours.do(check_replies)
                    print(f"发送间隔已更新为 {SEND_INTERVAL} 小时")
                else:
                    print("间隔必须大于0")
            except ValueError:
                print("请输入有效的数字")
        elif choice == '6':
            print("正在退出...")
            break
        else:
            print("无效的选择，请重试")
        
        time.sleep(1)
