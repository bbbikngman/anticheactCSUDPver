#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebSocket信令通道模块
用于打断信号的可靠传输
"""

import asyncio
import websockets
import json
import threading
import time
import logging
from typing import Dict, Optional, Callable, Tuple
from dataclasses import dataclass

@dataclass
class SignalMessage:
    """信令消息数据结构"""
    type: str
    data: dict
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    def to_json(self) -> str:
        """转换为JSON字符串"""
        return json.dumps({
            "type": self.type,
            "timestamp": self.timestamp,
            **self.data
        })
    
    @classmethod
    def from_json(cls, json_str: str) -> 'SignalMessage':
        """从JSON字符串创建"""
        data = json.loads(json_str)
        msg_type = data.pop("type")
        timestamp = data.pop("timestamp", time.time())
        return cls(type=msg_type, data=data, timestamp=timestamp)

class InterruptSignalServer:
    """WebSocket信令服务器"""
    
    def __init__(self, host="0.0.0.0", port=31001):
        self.host = host
        self.port = port
        self.clients: Dict[str, websockets.WebSocketServerProtocol] = {}  # {addr_str: websocket}
        self.udp_bindings: Dict[Tuple[str, int], str] = {}  # {(ip, port): addr_str}
        self.running = False
        self.server = None
        self.server_thread = None
        self.loop = None
        
        # 日志回调
        self.log_callback: Optional[Callable[[str], None]] = None
        
    def set_log_callback(self, callback: Callable[[str], None]):
        """设置日志回调函数"""
        self.log_callback = callback
        
    def log(self, message: str):
        """记录日志"""
        if self.log_callback:
            self.log_callback(message)
        else:
            print(f"[WebSocket服务器] {message}")
    
    def start(self):
        """启动WebSocket服务器"""
        if self.running:
            self.log("WebSocket服务器已在运行")
            return
            
        self.running = True
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        self.log(f"WebSocket服务器启动中... {self.host}:{self.port}")
    
    def stop(self):
        """停止WebSocket服务器"""
        self.running = False
        if self.loop and self.server:
            # 在事件循环中停止服务器
            asyncio.run_coroutine_threadsafe(self._stop_server(), self.loop)
        
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=2.0)
        
        self.log("WebSocket服务器已停止")
    
    def _run_server(self):
        """在独立线程中运行WebSocket服务器"""
        try:
            # 创建新的事件循环
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # 启动WebSocket服务器
            self.loop.run_until_complete(self._start_server())
        except Exception as e:
            self.log(f"WebSocket服务器运行错误: {e}")
        finally:
            if self.loop:
                self.loop.close()
    
    async def _start_server(self):
        """启动WebSocket服务器协程"""
        try:
            self.server = await websockets.serve(
                self._handle_client,
                self.host,
                self.port,
                ping_interval=30,  # 30秒ping间隔
                ping_timeout=10    # 10秒ping超时
            )
            self.log(f"✅ WebSocket服务器已启动: ws://{self.host}:{self.port}")
            
            # 保持服务器运行
            await self.server.wait_closed()
            
        except Exception as e:
            self.log(f"❌ WebSocket服务器启动失败: {e}")
    
    async def _stop_server(self):
        """停止WebSocket服务器协程"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
    
    async def _handle_client(self, websocket, path=None):
        """处理WebSocket客户端连接"""
        client_addr = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        self.log(f"🔗 WebSocket客户端连接: {client_addr}")
        
        try:
            # 等待客户端发送UDP地址绑定信息
            auth_msg = await asyncio.wait_for(websocket.recv(), timeout=10.0)
            auth_data = json.loads(auth_msg)
            
            if auth_data.get("type") == "bind_udp":
                udp_ip = auth_data["udp_ip"]
                udp_port = auth_data["udp_port"]
                udp_addr = (udp_ip, udp_port)
                
                # 绑定UDP地址到WebSocket连接
                self.clients[client_addr] = websocket
                self.udp_bindings[udp_addr] = client_addr
                
                self.log(f"✅ UDP地址绑定成功: {udp_addr} -> {client_addr}")
                
                # 发送绑定确认
                confirm_msg = SignalMessage("bind_confirm", {"status": "success"})
                await websocket.send(confirm_msg.to_json())
                
                # 处理后续消息
                await self._handle_client_messages(websocket, client_addr, udp_addr)
            else:
                self.log(f"❌ 无效的绑定消息: {auth_data}")
                await websocket.close(code=4000, reason="Invalid bind message")
                
        except asyncio.TimeoutError:
            self.log(f"⏰ 客户端绑定超时: {client_addr}")
        except websockets.exceptions.ConnectionClosed:
            self.log(f"🔌 客户端连接已关闭: {client_addr}")
        except Exception as e:
            self.log(f"❌ 处理客户端连接错误: {e}")
        finally:
            # 清理连接
            self._cleanup_client(client_addr)
    
    async def _handle_client_messages(self, websocket, client_addr: str, udp_addr: Tuple[str, int]):
        """处理客户端消息"""
        try:
            async for message in websocket:
                try:
                    signal_msg = SignalMessage.from_json(message)
                    
                    if signal_msg.type == "ping":
                        # 响应ping
                        pong_msg = SignalMessage("pong", {})
                        await websocket.send(pong_msg.to_json())
                    else:
                        self.log(f"📨 收到客户端消息: {signal_msg.type} from {client_addr}")
                        
                except json.JSONDecodeError:
                    self.log(f"⚠️ 无效的JSON消息: {message}")
                    
        except websockets.exceptions.ConnectionClosed:
            self.log(f"🔌 客户端消息循环结束: {client_addr}")
    
    def _cleanup_client(self, client_addr: str):
        """清理客户端连接"""
        # 移除客户端连接
        if client_addr in self.clients:
            del self.clients[client_addr]
        
        # 移除UDP绑定
        udp_addr_to_remove = None
        for udp_addr, addr_str in self.udp_bindings.items():
            if addr_str == client_addr:
                udp_addr_to_remove = udp_addr
                break
        
        if udp_addr_to_remove:
            del self.udp_bindings[udp_addr_to_remove]
        
        self.log(f"🧹 客户端连接已清理: {client_addr}")
    
    def bind_udp_address(self, udp_addr: Tuple[str, int]) -> bool:
        """检查UDP地址是否已绑定"""
        return udp_addr in self.udp_bindings

    def update_udp_binding(self, old_addr: Tuple[str, int], new_addr: Tuple[str, int]) -> bool:
        """更新UDP地址绑定"""
        # 查找对应的WebSocket连接
        client_addr = None
        for addr, ws_addr in self.udp_bindings.items():
            if addr == old_addr:
                client_addr = ws_addr
                break

        if client_addr:
            # 更新绑定
            del self.udp_bindings[old_addr]
            self.udp_bindings[new_addr] = client_addr
            self.log(f"🔄 更新UDP绑定: {old_addr} -> {new_addr}")
            return True

        return False
    
    async def send_to_udp_client(self, udp_addr: Tuple[str, int], signal_msg: SignalMessage) -> bool:
        """向指定UDP客户端发送信令消息"""
        if udp_addr not in self.udp_bindings:
            self.log(f"⚠️ UDP地址未绑定: {udp_addr}")
            return False
        
        client_addr = self.udp_bindings[udp_addr]
        if client_addr not in self.clients:
            self.log(f"⚠️ 客户端连接不存在: {client_addr}")
            return False
        
        try:
            websocket = self.clients[client_addr]
            await websocket.send(signal_msg.to_json())
            self.log(f"📤 信令已发送: {signal_msg.type} -> {udp_addr}")
            return True
        except Exception as e:
            self.log(f"❌ 发送信令失败: {e}")
            return False
    
    def send_interrupt_signal(self, udp_addr: Tuple[str, int], session_id: str, interrupt_after_chunk: int):
        """发送打断信号（同步接口）"""
        if not self.loop:
            self.log("⚠️ WebSocket服务器未运行")
            return
        
        interrupt_msg = SignalMessage("interrupt", {
            "session_id": session_id,
            "interrupt_after_chunk": interrupt_after_chunk
        })
        
        # 在事件循环中执行异步发送
        asyncio.run_coroutine_threadsafe(
            self.send_to_udp_client(udp_addr, interrupt_msg),
            self.loop
        )
    
    def send_start_session_signal(self, udp_addr: Tuple[str, int], session_id: str):
        """发送新session开始信号（同步接口）"""
        if not self.loop:
            self.log("⚠️ WebSocket服务器未运行")
            return
        
        start_msg = SignalMessage("start_session", {
            "session_id": session_id
        })
        
        # 在事件循环中执行异步发送
        asyncio.run_coroutine_threadsafe(
            self.send_to_udp_client(udp_addr, start_msg),
            self.loop
        )

class InterruptSignalClient:
    """WebSocket信令客户端"""

    def __init__(self, server_host="127.0.0.1", server_port=31001):
        self.server_url = f"ws://{server_host}:{server_port}"
        self.websocket = None
        self.running = False
        self.client_thread = None
        self.loop = None

        # UDP地址信息
        self.udp_ip = ""
        self.udp_port = 0

        # 回调函数
        self.log_callback: Optional[Callable[[str], None]] = None
        self.interrupt_callback: Optional[Callable[[str, int], None]] = None
        self.start_session_callback: Optional[Callable[[str], None]] = None

    def set_log_callback(self, callback: Callable[[str], None]):
        """设置日志回调函数"""
        self.log_callback = callback

    def set_interrupt_callback(self, callback: Callable[[str, int], None]):
        """设置打断信号回调函数 callback(session_id, interrupt_after_chunk)"""
        self.interrupt_callback = callback

    def set_start_session_callback(self, callback: Callable[[str], None]):
        """设置新session开始回调函数 callback(session_id)"""
        self.start_session_callback = callback

    def log(self, message: str):
        """记录日志"""
        if self.log_callback:
            self.log_callback(message)
        else:
            print(f"[WebSocket客户端] {message}")

    def start(self, udp_ip: str, udp_port: int):
        """启动WebSocket客户端"""
        if self.running:
            self.log("WebSocket客户端已在运行")
            return

        self.udp_ip = udp_ip
        self.udp_port = udp_port
        self.running = True

        self.client_thread = threading.Thread(target=self._run_client, daemon=True)
        self.client_thread.start()
        self.log(f"WebSocket客户端启动中... {self.server_url}")

    def stop(self):
        """停止WebSocket客户端"""
        self.running = False

        if self.loop and self.websocket and not self.loop.is_closed():
            try:
                # 在事件循环中关闭连接
                asyncio.run_coroutine_threadsafe(self._close_connection(), self.loop)
            except RuntimeError:
                # 事件循环已关闭，忽略
                pass

        if self.client_thread and self.client_thread.is_alive():
            self.client_thread.join(timeout=2.0)

        self.log("WebSocket客户端已停止")

    def _run_client(self):
        """在独立线程中运行WebSocket客户端"""
        try:
            # 创建新的事件循环
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

            # 启动客户端连接
            self.loop.run_until_complete(self._connect_and_run())
        except Exception as e:
            self.log(f"WebSocket客户端运行错误: {e}")
        finally:
            if self.loop:
                self.loop.close()

    async def _connect_and_run(self):
        """连接并运行客户端"""
        retry_count = 0
        max_retries = 5

        while self.running and retry_count < max_retries:
            try:
                self.log(f"尝试连接WebSocket服务器... (第{retry_count + 1}次)")

                async with websockets.connect(
                    self.server_url,
                    ping_interval=30,
                    ping_timeout=10
                ) as websocket:
                    self.websocket = websocket
                    self.log("✅ WebSocket连接成功")

                    # 发送UDP地址绑定信息
                    bind_msg = SignalMessage("bind_udp", {
                        "udp_ip": self.udp_ip,
                        "udp_port": self.udp_port
                    })
                    await websocket.send(bind_msg.to_json())

                    # 等待绑定确认
                    confirm_msg = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    confirm_data = SignalMessage.from_json(confirm_msg)

                    if confirm_data.type == "bind_confirm" and confirm_data.data.get("status") == "success":
                        self.log("✅ UDP地址绑定成功")

                        # 启动心跳和消息处理
                        await asyncio.gather(
                            self._heartbeat_loop(),
                            self._message_loop()
                        )
                    else:
                        self.log("❌ UDP地址绑定失败")
                        break

            except asyncio.TimeoutError:
                self.log("⏰ 连接超时")
                retry_count += 1
            except websockets.exceptions.ConnectionClosed:
                self.log("🔌 WebSocket连接已关闭")
                break
            except Exception as e:
                self.log(f"❌ 连接错误: {e}")
                retry_count += 1

            if self.running and retry_count < max_retries:
                await asyncio.sleep(2 ** retry_count)  # 指数退避

        if retry_count >= max_retries:
            self.log("❌ 达到最大重试次数，停止连接")

    async def _close_connection(self):
        """关闭WebSocket连接"""
        if self.websocket:
            await self.websocket.close()

    async def _heartbeat_loop(self):
        """心跳循环"""
        while self.running:
            try:
                if self.websocket:
                    ping_msg = SignalMessage("ping", {})
                    await self.websocket.send(ping_msg.to_json())
                    self.log("💓 发送心跳")

                await asyncio.sleep(25)  # 25秒发送一次心跳
            except Exception as e:
                self.log(f"❌ 心跳发送失败: {e}")
                break

    async def _message_loop(self):
        """消息处理循环"""
        try:
            async for message in self.websocket:
                try:
                    signal_msg = SignalMessage.from_json(message)
                    await self._handle_signal_message(signal_msg)
                except json.JSONDecodeError:
                    self.log(f"⚠️ 无效的JSON消息: {message}")
        except websockets.exceptions.ConnectionClosed:
            self.log("🔌 消息循环结束")

    async def _handle_signal_message(self, signal_msg: SignalMessage):
        """处理信令消息"""
        if signal_msg.type == "pong":
            self.log("💓 收到心跳响应")

        elif signal_msg.type == "interrupt":
            session_id = signal_msg.data.get("session_id", "")
            interrupt_after_chunk = signal_msg.data.get("interrupt_after_chunk", 0)
            self.log(f"🛑 收到打断信号: session={session_id}, after_chunk={interrupt_after_chunk}")

            if self.interrupt_callback:
                # 在主线程中执行回调
                threading.Thread(
                    target=self.interrupt_callback,
                    args=(session_id, interrupt_after_chunk),
                    daemon=True
                ).start()

        elif signal_msg.type == "start_session":
            session_id = signal_msg.data.get("session_id", "")
            self.log(f"🎵 收到新session信号: session={session_id}")

            if self.start_session_callback:
                # 在主线程中执行回调
                threading.Thread(
                    target=self.start_session_callback,
                    args=(session_id,),
                    daemon=True
                ).start()
        else:
            self.log(f"📨 收到未知信令: {signal_msg.type}")
