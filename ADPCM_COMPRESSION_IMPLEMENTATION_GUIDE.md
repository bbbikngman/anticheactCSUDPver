# AI反诈专员 - ADPCM音频压缩实施指南

## 📋 项目背景

### 🎯 问题识别
当前UDP音频传输方案存在带宽过高问题：
- **原始PCM传输**：513kbps持续带宽
- **网络风险**：WiFi不稳定环境下可能卡顿
- **扩展性差**：多客户端时服务器网络压力大

### 💡 ADPCM解决方案优势

| 方案 | 压缩比 | 带宽需求 | 依赖要求 | 实施难度 | 音质 |
|------|--------|----------|----------|----------|------|
| **ADPCM** | **4:1** | **129kbps** | **Python内置** | **⭐** | **良好** |
| Opus | 8:1 | 64kbps | 外部C库 | ⭐⭐⭐⭐ | 优秀 |
| G.711 | 2:1 | 256kbps | Python内置 | ⭐⭐ | 良好 |

**结论**：ADPCM是最佳平衡点 - 无需额外依赖，75%带宽节省！

## 🔧 技术实施方案

### 📊 性能提升预期
```
原始方案: 513kbps (2048字节/块 × 31.25块/秒 × 8)
ADPCM方案: 129kbps (512字节/块 × 31.25块/秒 × 8)
带宽节省: 75% ↓
```

### 🎵 音频处理流程

#### 上行链路（客户端→服务器）
```
float32 PCM → int16 PCM → ADPCM压缩 → UDP传输 → ADPCM解压 → int16 PCM → float32 PCM → AI处理
```

#### 下行链路（服务器→客户端）
```
AI回复 → Edge TTS → 优化MP3输出 → UDP传输 → 客户端播放
```

## 📝 模块化实施路径

### 🚀 阶段1：ADPCM压缩模块开发（预计2小时）

#### 1.1 创建ADPCM工具类
```python
# 新建文件: adpcm_codec.py
import audioop
import numpy as np
from typing import Tuple, Optional

class ADPCMCodec:
    """ADPCM音频编解码器 - 使用Python内置audioop"""
    
    def __init__(self):
        self.encode_state = None  # 编码状态
        self.decode_state = None  # 解码状态
        
    def encode(self, float32_pcm: np.ndarray) -> bytes:
        """编码：float32 PCM → ADPCM"""
        # 1. 转换为int16
        int16_pcm = (float32_pcm * 32767).astype(np.int16)
        
        # 2. ADPCM压缩 (4:1压缩比)
        adpcm_data, self.encode_state = audioop.lin2adpcm(
            int16_pcm.tobytes(), 2, self.encode_state
        )
        
        return adpcm_data
        
    def decode(self, adpcm_data: bytes) -> np.ndarray:
        """解码：ADPCM → float32 PCM"""
        # 1. ADPCM解压
        int16_pcm_bytes, self.decode_state = audioop.adpcm2lin(
            adpcm_data, 2, self.decode_state
        )
        
        # 2. 转换为float32
        int16_pcm = np.frombuffer(int16_pcm_bytes, dtype=np.int16)
        float32_pcm = int16_pcm.astype(np.float32) / 32767.0
        
        return float32_pcm
        
    def reset_encoder(self):
        """重置编码器状态"""
        self.encode_state = None
        
    def reset_decoder(self):
        """重置解码器状态"""
        self.decode_state = None
```

#### 1.2 单元测试
```python
# 新建文件: test_adpcm.py
import numpy as np
from adpcm_codec import ADPCMCodec

def test_adpcm_roundtrip():
    """测试ADPCM编解码往返"""
    codec = ADPCMCodec()
    
    # 生成测试音频（正弦波）
    t = np.linspace(0, 1, 16000)  # 1秒，16kHz
    original = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    
    # 分块处理（模拟实际使用）
    block_size = 512
    reconstructed = []
    
    for i in range(0, len(original), block_size):
        block = original[i:i+block_size]
        
        # 编码
        compressed = codec.encode(block)
        print(f"压缩比: {len(block)*4}/{len(compressed)} = {len(block)*4/len(compressed):.1f}:1")
        
        # 解码
        decoded = codec.decode(compressed)
        reconstructed.extend(decoded)
    
    # 计算音质损失
    reconstructed = np.array(reconstructed[:len(original)])
    mse = np.mean((original - reconstructed) ** 2)
    print(f"均方误差: {mse:.6f}")
    
    assert mse < 0.01, "音质损失过大"
    print("✅ ADPCM测试通过")

if __name__ == "__main__":
    test_adpcm_roundtrip()
```

### 🚀 阶段2：客户端集成（预计1小时）

#### 2.1 修改客户端发送逻辑
```python
# 修改文件: simple_udp_client.py
from adpcm_codec import ADPCMCodec

class SimpleUDPClient:
    def __init__(self, ...):
        # ... 原有代码 ...
        self.adpcm_codec = ADPCMCodec()  # 新增
        
    def _send_thread_func(self):
        """音频发送线程 - 集成ADPCM压缩"""
        try:
            self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            
            while self.running:
                if self.audio_buffer and self.recording:
                    # 获取音频数据
                    audio_chunk = self.audio_buffer.pop(0)
                    
                    # ✨ 新增：ADPCM压缩
                    compressed_data = self.adpcm_codec.encode(audio_chunk)
                    
                    # 协议包：[1字节压缩标识][4字节长度][ADPCM数据]
                    packet = struct.pack('!BI', 1, len(compressed_data)) + compressed_data
                    
                    # 发送UDP包
                    self.send_socket.sendto(packet, (self.server_ip, self.send_port))
                    
                    # 统计信息更新
                    self.bytes_sent += len(packet)
                    self.packets_sent += 1
                    
                else:
                    time.sleep(0.01)
                    
        except Exception as e:
            print(f"发送线程错误: {e}")
```

#### 2.2 添加压缩统计显示
```python
# 在GUI中添加压缩效果显示
def get_compression_stats(self):
    """获取压缩统计"""
    if self.packets_sent == 0:
        return "暂无数据"
        
    # 原始大小：512采样 × 4字节 = 2048字节
    original_size = 2048 * self.packets_sent
    compressed_size = self.bytes_sent - (5 * self.packets_sent)  # 减去协议头
    
    compression_ratio = original_size / compressed_size if compressed_size > 0 else 0
    bandwidth_saved = (1 - compressed_size/original_size) * 100
    
    return f"""ADPCM压缩统计:
原始大小: {original_size} 字节
压缩后: {compressed_size} 字节  
压缩比: {compression_ratio:.1f}:1
带宽节省: {bandwidth_saved:.1f}%"""
```

### 🚀 阶段3：服务器端集成（预计1.5小时）

#### 3.1 多客户端状态管理
```python
# 修改文件: simple_udp_server.py
from adpcm_codec import ADPCMCodec

class SimpleUDPAudioServer:
    def __init__(self):
        # ... 原有代码 ...
        # ✨ 新增：为每个客户端维护独立的ADPCM解码器
        self.client_codecs = {}  # key: client_addr, value: ADPCMCodec
        
    def _get_client_codec(self, client_addr) -> ADPCMCodec:
        """获取或创建客户端的ADPCM解码器"""
        if client_addr not in self.client_codecs:
            self.client_codecs[client_addr] = ADPCMCodec()
            print(f"为客户端 {client_addr} 创建ADPCM解码器")
        return self.client_codecs[client_addr]
        
    def _recv_thread(self):
        """UDP接收线程 - 集成ADPCM解压"""
        while self.running:
            try:
                data, addr = self.recv_socket.recvfrom(4096)
                
                if len(data) >= 5:  # 1字节标识 + 4字节长度
                    # 解析协议
                    compression_type, data_length = struct.unpack('!BI', data[:5])
                    
                    if compression_type == 1 and len(data) >= 5 + data_length:
                        # ADPCM压缩数据
                        adpcm_data = data[5:5+data_length]
                        
                        # ✨ 获取客户端专用解码器并解压
                        codec = self._get_client_codec(addr)
                        audio_array = codec.decode(adpcm_data)
                        
                        # 放入处理队列（与原逻辑一致）
                        if not self.audio_queue.full():
                            self.audio_queue.put(audio_array.copy())
                        
                        # 更新客户端记录
                        self.current_client = addr
                        
            except Exception as e:
                if self.running:
                    print(f"UDP接收错误: {e}")
    
    def _cleanup_client(self, client_addr):
        """清理断开客户端的资源"""
        if client_addr in self.client_codecs:
            del self.client_codecs[client_addr]
            print(f"清理客户端 {client_addr} 的ADPCM解码器")
```

### 🚀 阶段4：Edge TTS优化（预计30分钟）

#### 4.1 调整TTS输出质量
```python
# 修改文件: tts_module.py 或创建适配器
class TTSModuleUDP:
    async def _generate_tts_bytes(self, text: str) -> Optional[bytes]:
        """生成优化的TTS音频字节"""
        try:
            import edge_tts
            
            # ✨ 使用低码率输出格式
            voice = config.TTS_VOICE_ZH if config.LANGUAGE_CODE == "zh" else config.TTS_VOICE_EN
            
            # 尝试不同的输出格式以减小文件大小
            output_formats = [
                "audio-16khz-32kbitrate-mono-mp3",  # 32kbps MP3
                "audio-16khz-64kbitrate-mono-mp3",  # 64kbps MP3  
                "riff-16khz-16bit-mono-pcm"         # 备选PCM格式
            ]
            
            for format_name in output_formats:
                try:
                    communicate = edge_tts.Communicate(text, voice)
                    
                    audio_data = b""
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            audio_data += chunk["data"]
                            
                    if audio_data:
                        print(f"TTS生成成功，格式: {format_name}, 大小: {len(audio_data)} 字节")
                        return audio_data
                        
                except Exception as e:
                    print(f"格式 {format_name} 失败: {e}")
                    continue
                    
            # 如果所有格式都失败，使用默认格式
            communicate = edge_tts.Communicate(text, voice)
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
                    
            return audio_data if audio_data else None
            
        except Exception as e:
            print(f"TTS生成错误: {e}")
            return None
```

### 🚀 阶段5：集成测试与部署（预计1小时）

#### 5.1 创建部署脚本
```bash
# 新建文件: deploy_adpcm.sh
#!/bin/bash
echo "部署ADPCM压缩版本..."

# 1. 备份原文件
cp simple_udp_client.py simple_udp_client_backup.py
cp simple_udp_server.py simple_udp_server_backup.py

# 2. 运行测试
echo "运行ADPCM测试..."
python3 test_adpcm.py

# 3. 启动服务器
echo "启动ADPCM服务器..."
python3 simple_udp_server.py &
SERVER_PID=$!

# 4. 等待服务器启动
sleep 3

# 5. 测试客户端连接
echo "测试客户端连接..."
# 这里可以添加自动化测试脚本

echo "部署完成！服务器PID: $SERVER_PID"
```

#### 5.2 性能验证清单
```python
# 新建文件: performance_test.py
def test_bandwidth_reduction():
    """验证带宽减少效果"""
    # 模拟1分钟音频传输
    original_bandwidth = 513  # kbps
    expected_adpcm_bandwidth = 129  # kbps
    
    print(f"原始带宽: {original_bandwidth} kbps")
    print(f"ADPCM带宽: {expected_adpcm_bandwidth} kbps")
    print(f"节省: {(1-expected_adpcm_bandwidth/original_bandwidth)*100:.1f}%")
    
def test_audio_quality():
    """验证音频质量"""
    # 运行ADPCM编解码测试
    # 检查均方误差是否在可接受范围内
    pass

def test_multi_client():
    """验证多客户端支持"""
    # 测试服务器是否正确维护多个客户端的ADPCM状态
    pass
```

## 📋 实施检查清单

### ✅ 开发阶段
- [ ] 创建ADPCMCodec类并通过单元测试
- [ ] 客户端集成ADPCM编码
- [ ] 服务器端集成ADPCM解码和多客户端状态管理
- [ ] Edge TTS输出优化
- [ ] 集成测试通过

### ✅ 部署阶段  
- [ ] 备份原始文件
- [ ] 部署新版本到Ubuntu服务器
- [ ] Windows客户端更新
- [ ] 网络性能测试
- [ ] 音频质量验证

### ✅ 验收标准
- [ ] 带宽使用降低至130kbps以下
- [ ] 音频质量可接受（主观测试）
- [ ] 多客户端连接稳定
- [ ] 无新增外部依赖
- [ ] 向后兼容（可回退到原版本）

## 🎯 预期收益

- **带宽节省**：75% ↓ (513kbps → 129kbps)
- **网络稳定性**：显著提升
- **部署复杂度**：无增加（使用Python内置库）
- **开发时间**：总计5小时
- **维护成本**：极低

## 🔄 风险控制

1. **回退方案**：保留原始文件，可快速回退
2. **渐进部署**：先在测试环境验证，再生产部署
3. **性能监控**：实时监控带宽使用和音频质量
4. **兼容性**：支持压缩/非压缩客户端混合连接

---

**实施负责人请按阶段顺序执行，每个阶段完成后进行测试验证，确保系统稳定性！**
