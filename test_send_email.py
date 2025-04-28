#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
邮件发送测试客户端
用于测试邮件发送API的功能
"""

import requests
import json
from typing import List, Optional

def send_test_email(
    emails: List[str],
    count: int = 1,
    template_name: str = "C_template.html",
    target_countries: Optional[List[str]] = None,
    target_regions: Optional[List[str]] = None
) -> dict:
    """
    发送测试邮件
    
    Args:
        emails: 要测试的邮箱地址列表
        count: 要发送的邮件数量，默认为1
        template_name: 邮件模板名称，默认为C_template.html
        target_countries: 目标国家列表，可选
        target_regions: 目标区域列表，可选
    
    Returns:
        dict: API响应结果
    """
    # API服务器地址
    API_URL = "http://localhost:8000"
    
    # 构建请求数据
    data = {
        "count": count,
        "template_name": template_name,
        "target_countries": target_countries or [],
        "target_regions": target_regions or []
    }
    
    try:
        # 发送POST请求到/send-temp接口
        response = requests.post(f"{API_URL}/send-temp", json=data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"发送成功！{result['message']}")
            return result
        else:
            print(f"发送失败！状态码：{response.status_code}")
            print(f"错误信息：{response.text}")
            return {"error": response.text}
            
    except Exception as e:
        print(f"请求发生错误：{str(e)}")
        return {"error": str(e)}

def get_email_stats(date: Optional[str] = None, all_data: bool = False) -> dict:
    """
    获取邮件统计数据
    
    Args:
        date: 指定日期，格式为YYYY-MM-DD，默认为当天
        all_data: 是否获取所有数据的统计
    
    Returns:
        dict: 统计数据
    """
    API_URL = "http://localhost:8000"
    
    try:
        # 构建请求参数
        params = {}
        if date:
            params['date'] = date
        if all_data:
            params['all_data'] = 'true'
        
        # 发送GET请求到/stats接口
        response = requests.get(f"{API_URL}/stats", params=params)
        
        if response.status_code == 200:
            stats = response.json()
            print("\n邮件统计数据:")
            print(f"日期: {stats['date']}")
            print(f"发送数量: {stats['sent_count']}")
            print(f"打开数量: {stats['opened_count']}")
            print(f"打开率: {stats['open_rate']:.2f}%")
            return stats
        else:
            print(f"获取统计数据失败！状态码：{response.status_code}")
            print(f"错误信息：{response.text}")
            return {"error": response.text}
            
    except Exception as e:
        print(f"请求发生错误：{str(e)}")
        return {"error": str(e)}

if __name__ == "__main__":
    # 测试邮件发送
    test_emails = [
        "test@example.com",  # 替换为你要测试的邮箱地址
    ]
    
    # 发送测试邮件
    print("开始发送测试邮件...")
    result = send_test_email(
        emails=test_emails,
        count=1,  # 发送1封测试邮件
        template_name="C_template.html",  # 使用C模板
        target_countries=[]  # 不指定国家，将使用默认设置
    )
    
    # 获取最新的统计数据
    if 'error' not in result:
        stats = get_email_stats(all_data=True)
