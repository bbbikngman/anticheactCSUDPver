#!/bin/bash
# 一键杀死UDP服务器进程

echo "🔍 查找占用端口31000的进程..."

# 查找进程
PID=$(lsof -ti:31000)

if [ -z "$PID" ]; then
    echo "✅ 端口31000未被占用"
else
    echo "🎯 找到进程: $PID"
    echo "💀 正在杀死进程..."
    kill -9 $PID
    sleep 1
    
    # 验证是否成功
    if lsof -ti:31000 > /dev/null 2>&1; then
        echo "❌ 进程仍在运行，尝试强制杀死..."
        pkill -9 -f "python.*simple_udp_server.py"
        sleep 1
    fi
    
    if lsof -ti:31000 > /dev/null 2>&1; then
        echo "❌ 无法杀死进程，请手动处理"
        lsof -i:31000
    else
        echo "✅ 进程已成功杀死"
    fi
fi

echo "🚀 现在可以启动服务器了:"
echo "   python simple_udp_server.py"
