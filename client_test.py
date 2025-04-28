import requests
import json
from typing import Optional, List, Union

def main(
    suffix: str,
    target_regions: Optional[Union[str, List[str]]] = None,
    target_countries: Optional[Union[str, List[str]]] = None,
    send_time: Optional[str] = None,
    template_name: Optional[str] = None,
    date: Optional[Union[str, List[str]]] = None,  # 更新为支持字符串或字符串列表
    daily_count: Optional[int] = 20,
    workdays: Optional[Union[str, List[int]]] = None,  # 发送邮件的工作日，0-6表示周一到周日
    count: Optional[int] = None,  # 临时发送邮件数量参数
    all_data: Optional[bool] = False  # 新增是否获取所有数据统计参数
) -> dict:
    """
    统一处理邮件发送系统的API请求接口函数。

    参数:
        suffix (str): API端点后缀，可选值包括:
            - "": 获取API状态
            - "status": 获取当前任务状态
            - "start": 启动邮件发送任务
            - "stop": 停止邮件发送任务
            - "stats": 获取统计数据
            - "send-now": 立即执行一次邮件发送任务
            - "send-temp": 临时发送指定数量的邮件到指定国家或区域

        target_regions (Union[str, List[str]], 可选): 目标区域列表或单个区域字符串，用于按区域发送邮件
            例如: ["南美洲", "东南亚"] 或 "南美洲"
            注意: 与target_countries互斥，启动任务时必须指定其中之一

        target_countries (Union[str, List[str]], 可选): 目标国家列表或单个国家字符串，用于按国家发送邮件
            例如: ["中国", "美国", "日本"] 或 "中国"
            注意: 与target_regions互斥，启动任务时必须指定其中之一

        send_time (str, 可选): 计划发送时间，格式为"HH:MM"
            例如: "09:00"
            注意: 仅在启动任务(suffix="start")时需要

        template_name (str, 可选): 邮件模板名称，可选值:
            - "A_template.html"
            - "B_template.html"
            - "C_template.html"
            注意: 用于启动任务(suffix="start")或临时发送(suffix="send-temp")时

        date (Union[str, List[str]], 可选): 查询统计数据的日期
            可以是单个日期字符串，格式为"YYYY-MM-DD"，例如: "2025-04-15"
            也可以是多个日期的列表，例如: ["2025-04-15", "2025-04-16"]
            或者是以逗号分隔的多个日期字符串，例如: "2025-04-15,2025-04-16"
            注意: 仅在获取统计数据(suffix="stats")时可用
            
        daily_count (int, 可选): 每日发送邮件数量，默认为20
            注意: 仅在启动任务(suffix="start")时可用
            
        workdays (Union[str, List[int]], 可选): 发送邮件的工作日，0-6分别代表周一到周日
            例如: [0,1,2,3,4] 表示周一到周五发送，[5,6] 表示周末发送
            注意: 仅在启动任务(suffix="start")时可用，若不提供则默认每天都发送
            
        count (int, 可选): 临时发送的邮件数量
            注意: 仅在临时发送(suffix="send-temp")时需要
            
        all_data (bool, 可选): 是否获取所有统计数据，默认为False
            注意: 仅在获取统计数据(suffix="stats")时可用，若为True则忽略date参数

    返回:
        dict: API响应的JSON数据

    异常:
        ValueError: 当参数验证失败时抛出
        Exception: 当API请求失败时抛出

    示例:
        # 获取API状态
        status = email_api_request("")

        # 按区域启动任务
        result = email_api_request(
            suffix="start",
            target_regions=["南美洲", "东南亚"],
            send_time="09:00",
            template_name="A_template.html",
            daily_count=30
        )
        
        # 使用字符串形式的target_countries启动任务
        result = email_api_request(
            suffix="start",
            target_countries="中国",
            send_time="09:00",
            template_name="A_template.html"
        )

        # 获取指定单个日期的统计数据
        stats = email_api_request(suffix="stats", date="2025-04-15")
        
        # 获取多个日期的统计数据（使用列表）
        stats = email_api_request(suffix="stats", date=["2025-04-15", "2025-04-16"])
        
        # 获取多个日期的统计数据（使用逗号分隔的字符串）
        stats = email_api_request(suffix="stats", date="2025-04-15,2025-04-16")
    """
    base_url = "http://101.126.19.137:8000"
    headers = {"Content-Type": "application/json"}
    
    # 验证template_name
    valid_templates = ["A_template.html", "B_template.html", "C_template.html"]
    if template_name and template_name not in valid_templates:
        raise ValueError(f"template_name must be one of {valid_templates}")
        
    # 处理字符串形式的target_regions
    if target_regions and isinstance(target_regions, str):
        target_regions = [target_regions]
        
    # 处理字符串形式的target_countries
    if target_countries and isinstance(target_countries, str):
        target_countries = [target_countries]

    # 根据不同的suffix处理不同的请求
    if suffix in ["", "status"]:
        # 只有这两个是GET请求的endpoints
        url = f"{base_url}/{suffix}"
        response = requests.get(url)
    
    elif suffix == "stats":
        # GET请求 - 获取统计数据
        url = f"{base_url}/stats"
        params = {}
        
        if date:
            # 处理不同格式的日期参数
            if isinstance(date, list):
                # 列表格式转成逗号分隔的字符串
                params["date"] = ",".join(date)
            elif isinstance(date, str):
                # 字符串格式直接传递
                params["date"] = date
            
        if all_data:
            params["all_data"] = "true"
        
        # 构建查询参数
        if params:
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            url = f"{url}?{query_string}"
            
        response = requests.get(url)
    
    elif suffix == "send-now":
        # POST请求 - 立即发送邮件
        url = f"{base_url}/send-now"
        response = requests.post(url)
    
    elif suffix == "send-temp":
        # POST请求 - 临时发送指定数量的邮件
        url = f"{base_url}/send-temp"
        payload = {
            "count": count
        }
        
        # 根据提供的参数选择target_regions或target_countries
        if target_regions:
            payload["target_regions"] = target_regions
        elif target_countries:
            payload["target_countries"] = target_countries
            
        if template_name:
            payload["template_name"] = template_name
            
        response = requests.post(url, headers=headers, json=payload)
    
    elif suffix == "start":
        # POST请求 - 启动邮件发送任务
        url = f"{base_url}/start"
        payload = {
            "daily_count": daily_count,
            "send_time": send_time
        }
        
        # 根据提供的参数选择target_regions或target_countries
        if target_regions:
            payload["target_regions"] = target_regions
        elif target_countries:
            payload["target_countries"] = target_countries
        else:
            raise ValueError("Either target_regions or target_countries must be provided")
            
        if template_name:
            payload["template_name"] = template_name
            
        # 处理工作日参数
        if workdays is not None:
            # 如果传入的是字符串，将其转换为列表
            if isinstance(workdays, str):
                # 处理可能的格式，例如："0,1,2,3,4" 或 "[0,1,2,3,4]"
                if workdays.startswith('[') and workdays.endswith(']'):
                    workdays = workdays[1:-1]  # 移除方括号
                workdays_list = [int(day.strip()) for day in workdays.split(',') if day.strip().isdigit()]
                payload["workdays"] = workdays_list
            else:
                # 已经是列表形式
                payload["workdays"] = workdays
            
        response = requests.post(url, headers=headers, json=payload)
    
    elif suffix == "stop":
        # POST请求 - 停止邮件发送任务
        url = f"{base_url}/stop"
        response = requests.post(url)
    
    else:
        raise ValueError(f"Invalid suffix: {suffix}")

    # 检查响应状态
    if response.status_code != 200:
        raise Exception(f"API request failed with status code {response.status_code}: {response.text}")

    response_data = json.dumps(response.json(), ensure_ascii=False)
    return {
        "result": response_data
    }
