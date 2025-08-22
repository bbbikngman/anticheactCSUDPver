#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速更新服务器IP配置工具
"""

import json
import sys
import os

def update_server_ip(new_ip, config_file="client_config.json"):
    """更新配置文件中的服务器IP"""
    try:
        # 读取现有配置
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            # 创建默认配置
            config = {
                "server": {"ip": "127.0.0.1", "port": 31000},
                "audio": {"sample_rate": 16000, "channels": 1, "chunk_size": 512, "device_id": None},
                "network": {"max_udp_size": 65507, "timeout": 5.0},
                "ui": {"window_title": "反作弊语音客户端", "window_size": "600x500", "log_lines": 20},
                "logging": {"level": "INFO", "file": "logs/client.log", "console": True}
            }
        
        # 更新IP
        old_ip = config["server"]["ip"]
        config["server"]["ip"] = new_ip
        
        # 保存配置
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
        
        print(f"✅ 服务器IP已更新: {old_ip} -> {new_ip}")
        print(f"📁 配置文件: {config_file}")
        print(f"🌐 服务器地址: {new_ip}:{config['server']['port']}")
        
    except Exception as e:
        print(f"❌ 更新失败: {e}")
        return False
    
    return True

def main():
    if len(sys.argv) != 2:
        print("用法: python update_server_ip.py <新IP地址>")
        print("示例: python update_server_ip.py 47.239.226.21")
        sys.exit(1)
    
    new_ip = sys.argv[1]
    
    # 简单的IP格式验证
    parts = new_ip.split('.')
    if len(parts) != 4:
        print("❌ IP地址格式错误")
        sys.exit(1)
    
    try:
        for part in parts:
            num = int(part)
            if not (0 <= num <= 255):
                raise ValueError()
    except ValueError:
        print("❌ IP地址格式错误")
        sys.exit(1)
    
    # 更新配置
    if update_server_ip(new_ip):
        print("\n🚀 现在可以运行客户端:")
        print("   python gui_udp_client.py")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
