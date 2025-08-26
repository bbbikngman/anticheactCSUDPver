#!/usr/bin/env python3
"""
单独测试WebSocket服务器
"""

import time
from websocket_signal import InterruptSignalServer

def test_websocket_server():
    print("🧪 测试WebSocket服务器启动...")
    
    # 创建WebSocket服务器
    server = InterruptSignalServer(host="0.0.0.0", port=31004)
    
    # 启动服务器
    server.start()
    
    # 等待启动
    print("⏳ 等待服务器启动...")
    time.sleep(3)
    
    # 检查状态
    if server.running:
        print("✅ WebSocket服务器运行中")
    else:
        print("❌ WebSocket服务器未运行")
    
    # 保持运行10秒
    print("🔄 保持运行10秒...")
    time.sleep(10)
    
    # 停止服务器
    server.stop()
    print("🛑 WebSocket服务器已停止")

if __name__ == "__main__":
    test_websocket_server()
