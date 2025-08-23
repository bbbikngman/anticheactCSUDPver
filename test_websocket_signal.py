#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试WebSocket信令通道功能
"""

import time
import threading
from websocket_signal import InterruptSignalServer, InterruptSignalClient, SignalMessage

def test_signal_message():
    """测试信令消息数据结构"""
    print("🧪 测试信令消息数据结构...")
    
    # 创建打断信号
    interrupt_msg = SignalMessage("interrupt", {
        "session_id": "test123",
        "interrupt_after_chunk": 3
    })
    
    # 转换为JSON
    json_str = interrupt_msg.to_json()
    print(f"JSON: {json_str}")
    
    # 从JSON恢复
    restored_msg = SignalMessage.from_json(json_str)
    
    # 验证
    assert restored_msg.type == "interrupt"
    assert restored_msg.data["session_id"] == "test123"
    assert restored_msg.data["interrupt_after_chunk"] == 3
    
    print("✅ 信令消息测试通过")
    return True

def test_websocket_server_basic():
    """测试WebSocket服务器基本功能"""
    print("\n🧪 测试WebSocket服务器基本功能...")
    
    # 创建服务器
    server = InterruptSignalServer(host="127.0.0.1", port=31002)  # 使用不同端口避免冲突
    server.set_log_callback(lambda msg: print(f"[服务器] {msg}"))
    
    # 启动服务器
    server.start()
    
    # 等待服务器启动
    time.sleep(2)
    
    # 检查服务器状态
    if server.running:
        print("✅ WebSocket服务器启动成功")
        success = True
    else:
        print("❌ WebSocket服务器启动失败")
        success = False
    
    # 停止服务器
    server.stop()
    
    # 等待服务器停止
    time.sleep(1)
    
    print("✅ WebSocket服务器基本功能测试完成")
    return success

def test_websocket_client_basic():
    """测试WebSocket客户端基本功能"""
    print("\n🧪 测试WebSocket客户端基本功能...")
    
    # 创建客户端
    client = InterruptSignalClient(server_host="127.0.0.1", server_port=31003)  # 使用不存在的端口测试连接失败
    client.set_log_callback(lambda msg: print(f"[客户端] {msg}"))
    
    # 设置回调
    interrupt_received = threading.Event()
    session_received = threading.Event()
    
    def on_interrupt(session_id, interrupt_after_chunk):
        print(f"[回调] 收到打断信号: {session_id}, {interrupt_after_chunk}")
        interrupt_received.set()
    
    def on_start_session(session_id):
        print(f"[回调] 收到新session: {session_id}")
        session_received.set()
    
    client.set_interrupt_callback(on_interrupt)
    client.set_start_session_callback(on_start_session)
    
    # 启动客户端（会连接失败，但不会崩溃）
    client.start("127.0.0.1", 31000)
    
    # 等待一段时间
    time.sleep(3)
    
    # 停止客户端
    client.stop()
    
    print("✅ WebSocket客户端基本功能测试完成")
    return True

def test_server_client_integration():
    """测试服务器-客户端集成"""
    print("\n🧪 测试服务器-客户端集成...")
    
    # 创建服务器
    server = InterruptSignalServer(host="127.0.0.1", port=31004)
    server.set_log_callback(lambda msg: print(f"[服务器] {msg}"))
    
    # 创建客户端
    client = InterruptSignalClient(server_host="127.0.0.1", server_port=31004)
    client.set_log_callback(lambda msg: print(f"[客户端] {msg}"))
    
    # 设置客户端回调
    interrupt_received = threading.Event()
    session_received = threading.Event()
    received_data = {}
    
    def on_interrupt(session_id, interrupt_after_chunk):
        print(f"[回调] 收到打断信号: {session_id}, {interrupt_after_chunk}")
        received_data['interrupt'] = (session_id, interrupt_after_chunk)
        interrupt_received.set()
    
    def on_start_session(session_id):
        print(f"[回调] 收到新session: {session_id}")
        received_data['session'] = session_id
        session_received.set()
    
    client.set_interrupt_callback(on_interrupt)
    client.set_start_session_callback(on_start_session)
    
    try:
        # 启动服务器
        server.start()
        time.sleep(1)
        
        # 启动客户端
        client.start("127.0.0.1", 31000)  # 模拟UDP地址
        time.sleep(3)  # 等待连接建立
        
        # 发送打断信号
        server.send_interrupt_signal(("127.0.0.1", 31000), "test_session", 5)
        
        # 等待接收
        if interrupt_received.wait(timeout=5):
            print("✅ 打断信号传输成功")
            assert received_data['interrupt'] == ("test_session", 5)
        else:
            print("❌ 打断信号传输失败")
            return False
        
        # 发送新session信号
        server.send_start_session_signal(("127.0.0.1", 31000), "new_session")
        
        # 等待接收
        if session_received.wait(timeout=5):
            print("✅ 新session信号传输成功")
            assert received_data['session'] == "new_session"
        else:
            print("❌ 新session信号传输失败")
            return False
        
        print("✅ 服务器-客户端集成测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 集成测试异常: {e}")
        return False
    finally:
        # 清理
        client.stop()
        server.stop()
        time.sleep(1)

if __name__ == "__main__":
    print("=" * 50)
    print("WebSocket信令通道测试")
    print("=" * 50)
    
    try:
        success1 = test_signal_message()
        success2 = test_websocket_server_basic()
        success3 = test_websocket_client_basic()
        success4 = test_server_client_integration()
        
        if success1 and success2 and success3 and success4:
            print("\n🎉 所有WebSocket信令测试通过！")
        else:
            print("\n❌ WebSocket信令测试失败！")
            
    except Exception as e:
        print(f"\n❌ 测试过程中出现异常: {e}")
        import traceback
        traceback.print_exc()
