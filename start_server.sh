#!/bin/bash
# 智能启动UDP服务器脚本

PORT=31000
SCRIPT="simple_udp_server.py"

echo "🚀 启动UDP语音服务器..."
echo "================================"

# 检查端口占用
check_port() {
    if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 || lsof -Pi :$PORT -sUDP:LISTEN -t >/dev/null 2>&1; then
        return 0  # 端口被占用
    else
        return 1  # 端口空闲
    fi
}

# 杀死占用进程
kill_existing() {
    echo "🔍 检测到端口 $PORT 被占用，正在清理..."
    
    # 方法1: 通过端口杀死
    PID=$(lsof -ti:$PORT 2>/dev/null)
    if [ ! -z "$PID" ]; then
        echo "🎯 找到占用进程: $PID"
        kill -9 $PID 2>/dev/null
        sleep 1
    fi
    
    # 方法2: 通过进程名杀死
    pkill -9 -f "$SCRIPT" 2>/dev/null
    sleep 1
    
    # 方法3: 强制清理Python进程
    pkill -9 -f "python.*$SCRIPT" 2>/dev/null
    sleep 1
    
    echo "✅ 进程清理完成"
}

# 启动服务器
start_server() {
    echo "🎯 激活虚拟环境..."
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    elif [ -d "venv" ]; then
        source venv/bin/activate
    else
        echo "⚠️ 未找到虚拟环境，使用系统Python"
    fi
    
    echo "🚀 启动服务器..."
    python $SCRIPT
}

# 主逻辑
if check_port; then
    kill_existing
    sleep 2
    
    # 再次检查
    if check_port; then
        echo "❌ 端口清理失败，请手动执行:"
        echo "   sudo lsof -ti:$PORT | xargs kill -9"
        echo "   或者重启系统"
        exit 1
    fi
fi

echo "✅ 端口 $PORT 可用"
start_server
