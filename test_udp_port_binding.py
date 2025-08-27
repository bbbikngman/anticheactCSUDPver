#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试UDP端口绑定的脚本
"""

import socket
import time

def test_udp_port_binding():
    """测试UDP端口绑定行为"""
    print("🧪 测试UDP端口绑定行为")
    
    server_addr = ("127.0.0.1", 31000)
    
    print(f"\n1. 测试传统sendto方式（可能导致端口变化）:")
    sock1 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    for i in range(5):
        test_data = f"test_message_{i}".encode()
        try:
            sock1.sendto(test_data, server_addr)
            local_addr = sock1.getsockname()
            print(f"   发送 {i+1}: 本地端口 = {local_addr[1]}")
        except Exception as e:
            print(f"   发送 {i+1} 失败: {e}")
        time.sleep(0.1)
    
    sock1.close()
    
    print(f"\n2. 测试connect方式（应该固定端口）:")
    sock2 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    try:
        sock2.connect(server_addr)
        local_addr = sock2.getsockname()
        print(f"   连接后本地端口: {local_addr[1]}")
        
        for i in range(5):
            test_data = f"test_message_{i}".encode()
            try:
                sock2.send(test_data)
                current_addr = sock2.getsockname()
                print(f"   发送 {i+1}: 本地端口 = {current_addr[1]} (应该保持不变)")
            except Exception as e:
                print(f"   发送 {i+1} 失败: {e}")
            time.sleep(0.1)
            
    except Exception as e:
        print(f"   connect失败: {e}")
    finally:
        sock2.close()
    
    print(f"\n3. 测试bind方式（绑定到系统分配的端口）:")
    sock3 = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    try:
        sock3.bind(('', 0))  # 绑定到系统分配的端口
        local_addr = sock3.getsockname()
        print(f"   绑定后本地端口: {local_addr[1]}")
        
        for i in range(5):
            test_data = f"test_message_{i}".encode()
            try:
                sock3.sendto(test_data, server_addr)
                current_addr = sock3.getsockname()
                print(f"   发送 {i+1}: 本地端口 = {current_addr[1]} (应该保持不变)")
            except Exception as e:
                print(f"   发送 {i+1} 失败: {e}")
            time.sleep(0.1)
            
    except Exception as e:
        print(f"   bind失败: {e}")
    finally:
        sock3.close()
    
    print(f"\n✅ UDP端口绑定测试完成")

if __name__ == "__main__":
    test_udp_port_binding()
