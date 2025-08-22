## 确认与阶段目标

收到你的确认：

- 上行：客户端发 ADPCM（由 float32/mono/16kHz/512 采样块编码）
- 下行：服务器回 MP3 字节（Edge TTS 真实合成）
- 一阶段就走真实 TTS；LLM/TTS 不做额外测试，测试聚焦在新增环节（ADPCM+UDP）

我将按“最小改动”方案推进：不改现有核心管线文件，新增少量适配/桥接文件，把音频流从“本地麦克风/本地播放”替换为“客户端采集/服务器回传前端”。

## 最小改动的整体设计

- 新增，不改旧：
  - simple_udp_client.py：录音 →ADPCM→UDP 发；接收服务端 MP3→ 本地播放
  - simple_udp_server.py：UDP 收 →ADPCM 解码 → 投喂现有管线；TTS 输出 MP3→UDP 回发
  - tts_module_udp_adapter.py：与现有 Edge TTS 一致的生成逻辑，但不本地播放，直接返回 MP3 字节给 UDP 层
- 现有文件保持不动：audio_handler.py、vad_module.py、transcriber_module.py、brain_ai_module.py、tts_module.py
- 服务器端管线复用 main.py 流程，但用“网络音频队列”替代 sd.InputStream 回调（我会新建 main_udp_server.py，结构与 main.py 几乎一致，仅音频来源不同）

## 数据格式与协议（落地约定）

- 采样参数：16 kHz、单声道、每块 512 采样（≈32ms）
- 上行（Client→Server）：
  - float32→int16→ADPCM（4:1），按块发送
  - 包格式：1B 压缩类型 + 4B 长度（大端）+ 负载（ADPCM）
  - 压缩类型：ADPCMProtocol.COMPRESSION_ADPCM = 1
- 下行（Server→Client）：
  - Edge TTS 真实生成 MP3，整段聚合后一次性下发（最小改动）
  - 包格式：同上；类型定义为 COMPRESSION_TTS_MP3 = 2（我会在协议中新增常量）
  - 播放：客户端将 MP3 bytes 写临时文件或创建内存流交给播放器（pygame 或 web）

## 关键对接点（不改主流程，仅加桥接）

- 服务器 UDP 收包 → 解码后得到 float32[512] 块，喂给现有处理链：
  - is_speech = vad.is_speech(chunk)
  - triggered_audio = handler.process_chunk(chunk, is_speech)
  - 若触发：transcriber.transcribe_audio(full_audio) → kimi_ai.get_response_stream(text) → TTS 生成 MP3 bytes → UDP 回发
- TTS 真实合成但不本地播放：
  - 使用 tts_module_udp_adapter.py 复用 edge-tts 调用逻辑，返回音频字节 audio_bytes（MP3）
  - 不动 tts_module.py，避免影响已有演示

## 代码片段（说明桥接最小改动的方式）

- 服务器：UDP 收块 → 投喂现有管线（伪代码）

```python path=server/pseudo.py mode=EXCERPT
codec_map = {}  # (ip,port)->ADPCMCodec
while True:
    pkt, addr = sock.recvfrom(MAX_UDP)
    t, data = ADPCMProtocol.unpack_audio_packet(pkt)
    if t == ADPCMProtocol.COMPRESSION_ADPCM:
        codec = codec_map.setdefault(addr, ADPCMCodec())
        float_block = codec.decode(data)  # float32[~512]
        is_speech = vad.is_speech(float_block)
        triggered = handler.process_chunk(float_block, is_speech)
        if triggered is not None:
            text = transcriber.transcribe_audio(triggered, config.LANGUAGE_CODE, initial_prompt)
            if text:
                # 真实 LLM+TTS
                resp_stream = kimi_ai.get_response_stream(text)
                mp3_bytes = tts_udp_adapter.generate_mp3_from_stream(resp_stream)
                down = ADPCMProtocol.pack_audio_packet(mp3_bytes, COMPRESSION_TTS_MP3)
                sock.sendto(down, addr)
```

- TTS 适配器：生成 MP3 字节（复用 edge-tts 的流式产出，聚合）

```python path=tts_module_udp_adapter.py mode=EXCERPT
async def _edge_tts_bytes(text, voice, rate, volume):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate, volume=volume)
    out = b""
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            out += chunk["data"]
    return out

def generate_mp3_from_stream(self, text_stream):
    text = "".join(part for part in text_stream)
    return asyncio.run(_edge_tts_bytes(text, voice, rate, volume))
```

- 客户端：录音 →ADPCM→UDP 发；收 MP3→ 播放（伪代码）

```python path=client/pseudo.py mode=EXCERPT
def on_audio_block(float_block):
    compressed = codec.encode(float_block)
    pkt = ADPCMProtocol.pack_audio_packet(compressed, COMPRESSION_ADPCM)
    sock.sendto(pkt, server_addr)

# 收下行
pkt, _ = sock.recvfrom(MAX_UDP)
t, data = ADPCMProtocol.unpack_audio_packet(pkt)
if t == COMPRESSION_TTS_MP3:
    play_mp3_bytes(data)  # 写临时 .mp3 用 pygame 播放，或直接给前端
```

## 测试策略（仅测新增环节）

- 单元测试（保留/增强现有 test_adpcm.py）：
  - ADPCM 编解码往返（分块 512）
  - 协议打包/解包
  - 多客户端状态（不同 addr 拥有独立 codec 状态）
- 集成测试（本地 UDP）：
  - 启动 simple_udp_server.py（真实 TTS 路径），client 发送 2~3 句短语，验证能收到 MP3 并成功播放
  - 仅验证链路与类型，LLM/TTS 不做质量评测

## 落地清单与里程碑

- 交付文件（新增）：
  - simple_udp_client.py
  - simple_udp_server.py
  - tts_module_udp_adapter.py
  - test_adpcm.py（已存在，按需补充多客户端与协议用例）
  - test_udp_audio.py（端到端连通性与基本时延统计）
- 配置项：
  - 端口（默认：UDP_PORT=31000）
  - 目标 IP
  - 采样/块大小（默认与现有一致：16kHz/512）
- 预计用时：
  - 开发与单测：0.5–1 天
  - 自测联通（本机/两机）：0.5 天

## 待确认的两个参数

- UDP 端口号（默认 31000 是否可用？是否需要分上下行两个端口或同端口双向？我倾向同端口双向，简化 NAT）
- 是否需要多客户端支持（按源地址维持独立解码状态，默认就支持；如仅单客户端，也可先不开启清理逻辑）

确认后我开始实现与单测，完成后第一时间通知你对接测试人员进行测试。

## 进度打勾

- [x] 确认输入/输出格式与最小改动方案
- [x] 新增协议常量 COMPRESSION_TTS_MP3 (adpcm_codec.py)
- [x] 新增 TTS UDP 适配器（返回 MP3 字节）：tts_module_udp_adapter.py
- [x] 新增最小改动 UDP 服务器（多客户端）：simple_udp_server.py（端口 31000）
- [x] 新增最小改动 UDP 客户端：simple_udp_client.py
- [x] 新增端到端连通性与多客户端基本测试：test_udp_audio.py
- [x] 本地联调（真实 TTS）与问题清单整理
- [x] 优化客户端超时日志（静音不算错误）
- [x] 新增服务器会话重置机制（支持多客户端管理）
- [x] 修复 ADPCM 重置方法错误
- [x] 实现 MP3 分片发送机制（解决 UDP 包大小限制）
- [x] 优化开场白触发机制（客户端连接时立即发送）
- [x] 客户端智能 MP3 片段接收与拼接
- [ ] 提交给测试人员联测

### 测试结果记录

PS D:\coding\CityUProject\antiCheatHelper\demoversion\asr> whisper\venv_antifraud\Scripts\python.exe test_adpcm.py
🧪 ADPCM 编解码器测试套件
==================================================

基础往返测试:
🔄 基础往返测试...
平均压缩比: 8.0:1
均方误差: 0.000343
✅ 基础往返测试通过

协议打包测试:
📦 协议打包测试...
原始数据: 21 字节
打包后: 26 字节
协议开销: 5 字节
✅ 协议打包测试通过

多客户端模拟:
👥 多客户端模拟测试...
客户端 1: MSE=0.007714
客户端 2: MSE=0.008710
客户端 3: MSE=0.010966
❌ 多客户端模拟失败: 客户端 3 音质损失过大: 0.010966

边界情况测试:
⚠️ 边界情况测试...
✅ 空数据处理正常
✅ 极值数据处理正常
✅ 静音数据处理正常
ADPCM 编码器状态已重置
ADPCM 解码器状态已重置
ADPCM 编解码器完全重置
✅ 状态重置正常
✅ 边界情况测试通过

性能测试:
⚡ 性能测试...
ADPCM 解码器状态已重置
音频时长: 10 秒
编码时间: 0.003 秒
解码时间: 0.001 秒
总处理时间: 0.003 秒
实时倍数: 3299.5x
✅ 性能测试通过

带宽计算验证:
📊 带宽计算验证...
原始带宽: 512 kbps
ADPCM 带宽: 33 kbps
带宽节省: 93.5%
✅ 带宽计算验证通过

==================================================
测试结果: 5 通过, 1 失败
⚠️ 部分测试失败，请检查实现。
PS D:\coding\CityUProject\antiCheatHelper\demoversion\asr>
