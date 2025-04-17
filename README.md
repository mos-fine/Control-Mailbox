# Email Tracker 邮件追踪系统

[English](#overview) | [中文](#概述)

## Overview

Email Tracker is a comprehensive email tracking system designed for B2B marketing campaigns. It enables users to send bulk emails with tracking functionality, monitor email opens and replies, and analyze engagement statistics. The system uses a combination of Python services for email sending, tracking, and statistical analysis.

### Key Features

- **Email Sending**: Automated bulk email sending with personalized templates
- **Email Tracking**: Real-time tracking of email opens through tracking pixels
- **Reply Detection**: Automatic detection of email replies
- **Statistics and Analytics**: Detailed reporting of email campaign performance
- **API Server**: RESTful API for managing email tasks and viewing statistics
- **Database Integration**: MySQL database integration for storing contact information and tracking data
- **Region/Country Targeting**: Send emails to contacts based on geographic regions or specific countries

### System Architecture

The system consists of the following components:

1. **Email Sender (`email_sender.py`)**: Handles the email delivery process, connects to SMTP and IMAP servers
2. **Tracker Server (`tracker_server.py`)**: Records email opens using tracking pixels
3. **Feedback Server (`feedback_server.py`)**: Processes and records email replies
4. **API Server (`api_server.py`)**: Provides RESTful API for system management
5. **SQL Tools**: Utilities for database operations
   - `add_email_id_column.py`: Adds an email_id column to the email_tracking table
   - `mysql_connection.py`: Handles database connection and table creation

### Templates

The system includes multiple customizable email templates:
- `A_template.html`: Product offering with detailed vegetable lists
- `B_template.html`: Product offering with product images
- `C_template.html`: Cooperation opportunity with certification information

## Installation

### Requirements

- Python 3.6+
- MySQL Server
- SMTP/IMAP mail server access

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/email_tracker.git
   cd email_tracker
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure database connection in the SQL tools files

4. Initialize the tracking table:
   ```bash
   python sql_tools/mysql_connection.py
   ```

5. Add email_id column to the tracking table:
   ```bash
   python sql_tools/add_email_id_column.py
   ```

## Usage

### Starting the Services

1. Start the tracking server:
   ```bash
   python tracker_server.py
   ```

2. Start the feedback server:
   ```bash
   python feedback_server.py
   ```

3. Start the API server:
   ```bash
   python api_server.py
   ```

### Using the Email Sender

Run the email sender to start interactive mode:
```bash
python email_sender.py
```

This will present a menu with options to:
1. Send emails immediately
2. Check for email replies
3. View statistics
4. View email open status
5. Modify send interval

### Using the API

The API server runs on port 8000 and offers endpoints for:

- Starting email campaigns: `POST /start`
- Stopping email campaigns: `POST /stop`
- Checking campaign status: `GET /status`
- Viewing statistics: `GET /stats`
- Triggering immediate sending: `POST /send-now`

Example API request to start a campaign:
```bash
curl -X POST http://localhost:8000/start \
  -H "Content-Type: application/json" \
  -d '{"daily_count": 50, "target_regions": ["南美洲", "东南亚"], "send_time": "09:00", "template_name": "A_template.html"}'
```

## Configuration

Configuration files are stored in the `config` directory:

- `api_config.json`: API server configuration
- `recipients.json`: Test recipients list
- `regions.json`: Region to country mappings

## Security Considerations

- This system stores SMTP/IMAP credentials and database connection details in plaintext within the code. For production use, please implement secure credential management.
- Consider implementing rate limiting to avoid being flagged as spam.

## License

[Your License Here]

---

## 概述

Email Tracker是一个全面的电子邮件追踪系统，专为B2B营销活动设计。它使用户能够发送带有追踪功能的批量电子邮件，监控邮件打开和回复情况，并分析互动统计数据。该系统结合使用多个Python服务来实现邮件发送、追踪和统计分析功能。

### 核心功能

- **邮件发送**：使用个性化模板自动批量发送邮件
- **邮件追踪**：通过追踪像素实时监控邮件打开情况
- **回复检测**：自动检测邮件回复
- **统计和分析**：提供电子邮件活动效果的详细报告
- **API服务器**：用于管理邮件任务和查看统计数据的RESTful API
- **数据库集成**：与MySQL数据库集成，用于存储联系人信息和追踪数据
- **区域/国家定向**：根据地理区域或特定国家向目标联系人发送邮件

### 系统架构

系统由以下组件组成：

1. **邮件发送器 (`email_sender.py`)**：处理邮件投递过程，连接SMTP和IMAP服务器
2. **追踪服务器 (`tracker_server.py`)**：使用追踪像素记录邮件打开情况
3. **反馈服务器 (`feedback_server.py`)**：处理和记录邮件回复
4. **API服务器 (`api_server.py`)**：提供系统管理的RESTful API
5. **SQL工具**：用于数据库操作的实用工具
   - `add_email_id_column.py`：向email_tracking表添加email_id列
   - `mysql_connection.py`：处理数据库连接和表创建

### 模板

系统包含多个可自定义的电子邮件模板：
- `A_template.html`：产品报价，含详细的蔬菜列表
- `B_template.html`：产品报价，含产品图片
- `C_template.html`：合作机会，含认证信息

## 安装

### 要求

- Python 3.6+
- MySQL 服务器
- SMTP/IMAP邮件服务器访问权限

### 设置

1. 克隆仓库：
   ```bash
   git clone https://github.com/yourusername/email_tracker.git
   cd email_tracker
   ```

2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 在SQL工具文件中配置数据库连接

4. 初始化追踪表：
   ```bash
   python sql_tools/mysql_connection.py
   ```

5. 向追踪表添加email_id列：
   ```bash
   python sql_tools/add_email_id_column.py
   ```

## 使用方法

### 启动服务

1. 启动追踪服务器：
   ```bash
   python tracker_server.py
   ```

2. 启动反馈服务器：
   ```bash
   python feedback_server.py
   ```

3. 启动API服务器：
   ```bash
   python api_server.py
   ```

### 使用邮件发送器

运行邮件发送器以启动交互模式：
```bash
python email_sender.py
```

这将显示一个菜单，提供以下选项：
1. 立即发送邮件
2. 检查邮件回复
3. 显示统计信息
4. 查看邮件打开情况
5. 修改发送间隔

### 使用API

API服务器运行在8000端口，提供以下端点：

- 启动邮件活动：`POST /start`
- 停止邮件活动：`POST /stop`
- 检查活动状态：`GET /status`
- 查看统计数据：`GET /stats`
- 触发立即发送：`POST /send-now`

启动活动的API请求示例：
```bash
curl -X POST http://localhost:8000/start \
  -H "Content-Type: application/json" \
  -d '{"daily_count": 50, "target_regions": ["南美洲", "东南亚"], "send_time": "09:00", "template_name": "A_template.html"}'
```

## 配置

配置文件存储在`config`目录中：

- `api_config.json`：API服务器配置
- `recipients.json`：测试收件人列表
- `regions.json`：区域到国家的映射关系

## 安全考虑

- 本系统在代码中以明文存储SMTP/IMAP凭据和数据库连接详情。对于生产环境使用，请实现安全的凭据管理。
- 考虑实现速率限制以避免被标记为垃圾邮件。

## 许可证

[您的许可证信息]
