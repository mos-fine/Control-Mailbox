import requests
import json
from typing import Optional, List, Union

def main(
    suffix: str,
    target_regions: Optional[Union[str, List[str]]] = None,
    target_countries: Optional[Union[str, List[str]]] = None,
    send_time: Optional[str] = None,
    template_name: Optional[str] = None,
    date: Optional[str] = None,
    daily_count: Optional[int] = 20
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
            注意: 仅在启动任务(suffix="start")时需要

        date (str, 可选): 查询统计数据的具体日期，格式为"YYYY-MM-DD"
            例如: "2025-04-15"
            注意: 仅在获取统计数据(suffix="stats")时可用
            
        daily_count (int, 可选): 每日发送邮件数量，默认为20
            注意: 仅在启动任务(suffix="start")时可用

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

        # 获取指定日期的统计数据
        stats = email_api_request(suffix="stats", date="2025-04-15")
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
        if date:
            url = f"{url}?date={date}"
        response = requests.get(url)
    
    elif suffix == "send-now":
        # POST请求 - 立即发送邮件
        url = f"{base_url}/send-now"
        response = requests.post(url)
    
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
