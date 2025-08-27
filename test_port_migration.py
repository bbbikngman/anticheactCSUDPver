#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试端口迁移功能的脚本
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from simple_udp_server import UDPVoiceServer

def test_port_migration():
    """测试端口迁移逻辑"""
    print("🧪 测试端口迁移功能")
    
    # 创建服务器实例（不启动网络服务）
    server = UDPVoiceServer()
    
    # 模拟客户端地址变化
    addr1 = ("127.0.0.1", 37215)
    addr2 = ("127.0.0.1", 54160)
    
    print(f"\n1. 模拟第一次连接: {addr1}")
    result_addr1 = server._handle_client_address_change(addr1)
    print(f"   返回地址: {result_addr1}")
    print(f"   IP映射: {server.client_ip_to_current_addr}")
    
    # 模拟一些客户端状态
    server.client_last_activity[addr1] = 1234567890
    server.client_sessions[addr1] = "test_session_123"
    server.client_chunk_counters[addr1] = 5
    
    print(f"\n2. 模拟端口变化: {addr1} -> {addr2}")
    result_addr2 = server._handle_client_address_change(addr2)
    print(f"   返回地址: {result_addr2}")
    print(f"   IP映射: {server.client_ip_to_current_addr}")
    
    # 检查状态是否正确迁移
    print(f"\n3. 检查状态迁移:")
    print(f"   旧地址状态存在: {addr1 in server.client_sessions}")
    print(f"   新地址状态存在: {addr2 in server.client_sessions}")
    if addr2 in server.client_sessions:
        print(f"   新地址session: {server.client_sessions[addr2]}")
    if addr2 in server.client_chunk_counters:
        print(f"   新地址chunk计数: {server.client_chunk_counters[addr2]}")
    
    print(f"\n4. 测试welcomed逻辑:")
    # 测试IP级别的welcomed检查
    client_ip = "127.0.0.1"
    print(f"   IP {client_ip} welcomed状态: {client_ip in server.client_welcomed_ips}")
    
    # 添加到welcomed
    server.client_welcomed_ips.add(client_ip)
    print(f"   添加后welcomed状态: {client_ip in server.client_welcomed_ips}")
    
    # 模拟再次端口变化
    addr3 = ("127.0.0.1", 12345)
    print(f"\n5. 模拟再次端口变化: {addr2} -> {addr3}")
    result_addr3 = server._handle_client_address_change(addr3)
    print(f"   返回地址: {result_addr3}")
    print(f"   IP映射: {server.client_ip_to_current_addr}")
    print(f"   IP welcomed状态: {client_ip in server.client_welcomed_ips}")
    
    print(f"\n✅ 端口迁移测试完成")

if __name__ == "__main__":
    test_port_migration()
