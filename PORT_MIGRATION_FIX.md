# UDP 端口变化问题修复

## 问题描述

在 AI 对话系统中发现客户端 UDP 端口频繁变化的问题，导致服务器误认为是新客户端而重复发送开场白。

### 问题现象

- 客户端 UDP 端口在每次数据发送时都可能变化（如：52498 -> 36105 -> 57772 -> 51202...）
- 变化频率极高，几乎每个数据包都使用不同端口
- 即使在本地回环地址（127.0.0.1）也出现此问题

### 根本原因分析

经过深入分析发现，问题不在网络层面，而在于**客户端 UDP socket 没有绑定到固定端口**：

1. **Windows UDP 端口分配行为**：

   - 客户端创建 UDP socket 但未调用 bind()或 connect()
   - Windows 系统在每次 sendto()调用时可能分配新的源端口
   - 高频发送（音频数据每秒约 31 次）加剧了端口变化

2. **UDP 无连接特性**：
   - 每次 sendto()都是独立操作
   - 操作系统可能为每次发送分配新端口
   - 这是 Windows 特有的 UDP 端口分配策略

## 问题根源

1. **服务器使用 UDP 地址元组作为客户端标识**：`(IP, port)`
2. **UDP 端口在网络层面会变化**：这是网络栈的正常行为
3. **两个触发开场白的地方**：
   - 处理`CONTROL_HELLO`控制包时
   - 处理`COMPRESSION_ADPCM`音频数据时
4. **端口变化导致重复开场白**：新端口被认为是新客户端

## 解决方案

### 1. 使用 IP 作为客户端唯一标识

- 添加`client_welcomed_ips`集合，使用 IP 而不是`(IP, port)`
- 添加`client_ip_to_current_addr`映射，跟踪每个 IP 的当前地址

### 2. 端口变化检测和状态迁移

添加了两个关键方法：

#### `_handle_client_address_change(new_addr)`

- 检测同一 IP 的端口变化
- 触发状态迁移
- 更新 IP 到地址的映射

#### `_migrate_client_state(old_addr, new_addr)`

- 迁移所有客户端状态：
  - `client_codecs` - ADPCM 编解码器状态
  - `client_queues` - 音频队列
  - `client_handlers` - 音频处理器
  - `client_ai` - AI 对话历史
  - `client_last_activity` - 最后活动时间
  - `client_sessions` - 会话 ID
  - `client_chunk_counters` - chunk 计数器
  - `client_interrupt_cooldown` - 打断冷却
  - `client_states` - 统一状态管理
  - `fragment_cache` - 分片缓存
- 更新 WebSocket 绑定

### 3. 修改关键逻辑

#### 在`_recv_loop`中的 ADPCM 处理：

```python
# 处理地址变化（端口可能变化）
addr = self._handle_client_address_change(addr)

# 使用IP作为客户端标识
client_ip = addr[0]
if client_ip not in self.client_welcomed_ips:
    self.client_welcomed_ips.add(client_ip)
    self._send_opening_statement(addr)
```

#### 在`_recv_loop`中的 HELLO 处理：

```python
# 处理地址变化（端口可能变化）
addr = self._handle_client_address_change(addr)

# 使用IP作为客户端标识
client_ip = addr[0]
if client_ip not in self.client_welcomed_ips:
    self.client_welcomed_ips.add(client_ip)
    self._send_opening_statement(addr)
```

### 4. 清理逻辑更新

- `reset_client_session`：同时清理 IP 级别的 welcomed 标记
- `cleanup_inactive_clients`：清理 IP 映射和 welcomed 标记

## 测试验证

创建了`test_port_migration.py`测试脚本，验证：

- ✅ 端口变化检测
- ✅ 状态迁移完整性
- ✅ IP 级别 welcomed 逻辑
- ✅ 多次端口变化处理

## 预期效果

1. **解决重复开场白问题**：同一 IP 的端口变化不会触发新的开场白
2. **保持会话连续性**：所有客户端状态在端口变化时无缝迁移
3. **支持网络环境变化**：适应 NAT、代理等网络环境的端口变化
4. **向后兼容**：不影响现有的单端口客户端

## 关键改进点

- 🎯 **根本解决**：使用 IP 而不是端口作为客户端标识
- 🔄 **无缝迁移**：端口变化时自动迁移所有状态
- 🛡️ **会话保护**：保持 AI 对话的连续性
- 📡 **网络适应**：适应各种网络环境的端口变化行为
