#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADPCM音频编解码器
使用Python内置audioop模块，无需额外依赖
实现4:1压缩比，带宽从513kbps降至129kbps
"""

import audioop
import numpy as np
from typing import Tuple, Optional
import struct

class ADPCMCodec:
    """ADPCM音频编解码器 - 使用Python内置audioop"""
    
    def __init__(self):
        """初始化编解码器"""
        self.encode_state = None  # 编码状态
        self.decode_state = None  # 解码状态
        
        # 统计信息
        self.total_original_bytes = 0
        self.total_compressed_bytes = 0
        self.encode_count = 0
        self.decode_count = 0
        
    def encode(self, float32_pcm: np.ndarray) -> bytes:
        """
        编码：float32 PCM → ADPCM
        
        Args:
            float32_pcm: 输入的float32 PCM数据，范围[-1.0, 1.0]
            
        Returns:
            bytes: ADPCM压缩数据，大小约为输入的1/4
        """
        try:
            # 1. 转换为int16 PCM
            # 确保数据在有效范围内
            clipped_pcm = np.clip(float32_pcm, -1.0, 1.0)
            int16_pcm = (clipped_pcm * 32767).astype(np.int16)
            
            # 2. ADPCM压缩 (4:1压缩比)
            # audioop.lin2adpcm(fragment, width, state)
            # fragment: 音频数据字节
            # width: 每个采样的字节数 (2 for 16-bit)
            # state: 编码器状态 (None for first call)
            adpcm_data, self.encode_state = audioop.lin2adpcm(
                int16_pcm.tobytes(), 2, self.encode_state
            )
            
            # 3. 更新统计信息
            self.total_original_bytes += len(int16_pcm) * 2  # int16 = 2 bytes per sample
            self.total_compressed_bytes += len(adpcm_data)
            self.encode_count += 1
            
            return adpcm_data
            
        except Exception as e:
            print(f"ADPCM编码错误: {e}")
            # 返回空数据，让上层处理
            return b""
        
    def decode(self, adpcm_data: bytes) -> np.ndarray:
        """
        解码：ADPCM → float32 PCM
        
        Args:
            adpcm_data: ADPCM压缩数据
            
        Returns:
            np.ndarray: 解码后的float32 PCM数据，范围[-1.0, 1.0]
        """
        try:
            if not adpcm_data:
                return np.array([], dtype=np.float32)
                
            # 1. ADPCM解压缩
            # audioop.adpcm2lin(fragment, width, state)
            int16_pcm_bytes, self.decode_state = audioop.adpcm2lin(
                adpcm_data, 2, self.decode_state
            )
            
            # 2. 转换为float32 PCM
            int16_pcm = np.frombuffer(int16_pcm_bytes, dtype=np.int16)
            float32_pcm = int16_pcm.astype(np.float32) / 32767.0
            
            # 3. 更新统计信息
            self.decode_count += 1
            
            return float32_pcm
            
        except Exception as e:
            print(f"ADPCM解码错误: {e}")
            # 返回静音数据，避免程序崩溃
            return np.zeros(512, dtype=np.float32)  # 假设512采样的静音
        
    def reset_encoder(self):
        """重置编码器状态"""
        self.encode_state = None
        print("ADPCM编码器状态已重置")
        
    def reset_decoder(self):
        """重置解码器状态"""
        self.decode_state = None
        print("ADPCM解码器状态已重置")
        
    def reset_all(self):
        """重置所有状态和统计"""
        self.reset_encoder()
        self.reset_decoder()
        self.total_original_bytes = 0
        self.total_compressed_bytes = 0
        self.encode_count = 0
        self.decode_count = 0
        print("ADPCM编解码器完全重置")
        
    def get_compression_ratio(self) -> float:
        """获取压缩比"""
        if self.total_compressed_bytes == 0:
            return 0.0
        return self.total_original_bytes / self.total_compressed_bytes
        
    def get_bandwidth_savings(self) -> float:
        """获取带宽节省百分比"""
        if self.total_original_bytes == 0:
            return 0.0
        return (1 - self.total_compressed_bytes / self.total_original_bytes) * 100
        
    def get_statistics(self) -> str:
        """获取详细统计信息"""
        compression_ratio = self.get_compression_ratio()
        bandwidth_savings = self.get_bandwidth_savings()
        
        return f"""ADPCM编解码统计:
编码次数: {self.encode_count}
解码次数: {self.decode_count}
原始数据: {self.total_original_bytes} 字节
压缩数据: {self.total_compressed_bytes} 字节
压缩比: {compression_ratio:.2f}:1
带宽节省: {bandwidth_savings:.1f}%
理论带宽: {513 * (1 - bandwidth_savings/100):.0f} kbps"""


class ADPCMProtocol:
    """ADPCM协议处理器 - 处理网络传输协议"""

    COMPRESSION_NONE = 0
    COMPRESSION_ADPCM = 1
    COMPRESSION_TTS_MP3 = 2
    CONTROL_RESET = 100
    CONTROL_HELLO = 101
    
    @staticmethod
    def pack_audio_packet(audio_data: bytes, compression_type: int = COMPRESSION_ADPCM) -> bytes:
        """
        打包音频数据为网络传输格式
        
        格式: [1字节压缩类型][4字节数据长度][音频数据]
        
        Args:
            audio_data: 音频数据（原始PCM或ADPCM压缩）
            compression_type: 压缩类型标识
            
        Returns:
            bytes: 打包后的网络数据包
        """
        return struct.pack('!BI', compression_type, len(audio_data)) + audio_data
        
    @staticmethod
    def unpack_audio_packet(packet: bytes) -> Tuple[int, bytes]:
        """
        解包网络音频数据包
        
        Args:
            packet: 网络数据包
            
        Returns:
            Tuple[int, bytes]: (压缩类型, 音频数据)
        """
        if len(packet) < 5:  # 最小包大小
            raise ValueError("数据包太小")
            
        compression_type, data_length = struct.unpack('!BI', packet[:5])
        
        if len(packet) < 5 + data_length:
            raise ValueError("数据包不完整")
            
        audio_data = packet[5:5+data_length]
        return compression_type, audio_data

    @staticmethod
    def pack_control(cmd: int) -> bytes:
        """打包控制命令（无负载）"""
        return struct.pack('!BI', cmd, 0)


def benchmark_adpcm():
    """ADPCM性能基准测试"""
    import time
    
    print("🔧 ADPCM性能基准测试")
    print("=" * 40)
    
    # 创建测试数据
    sample_rate = 16000
    duration = 10  # 10秒音频
    t = np.linspace(0, duration, sample_rate * duration)
    
    # 混合频率的测试信号（更接近真实语音）
    test_audio = (
        0.3 * np.sin(2 * np.pi * 440 * t) +  # 440Hz
        0.2 * np.sin(2 * np.pi * 880 * t) +  # 880Hz
        0.1 * np.sin(2 * np.pi * 1320 * t)   # 1320Hz
    ).astype(np.float32)
    
    codec = ADPCMCodec()
    block_size = 512
    
    # 编码测试
    print("📤 编码测试...")
    encode_start = time.time()
    compressed_blocks = []
    
    for i in range(0, len(test_audio), block_size):
        block = test_audio[i:i+block_size]
        if len(block) == block_size:  # 只处理完整块
            compressed = codec.encode(block)
            compressed_blocks.append(compressed)
            
    encode_time = time.time() - encode_start
    
    # 解码测试
    print("📥 解码测试...")
    decode_start = time.time()
    decoded_blocks = []
    
    # 重置解码器状态
    codec.reset_decoder()
    
    for compressed in compressed_blocks:
        decoded = codec.decode(compressed)
        decoded_blocks.append(decoded)
        
    decode_time = time.time() - decode_start
    
    # 重建完整音频
    reconstructed = np.concatenate(decoded_blocks)
    original_trimmed = test_audio[:len(reconstructed)]
    
    # 计算音质指标
    mse = np.mean((original_trimmed - reconstructed) ** 2)
    snr = 10 * np.log10(np.mean(original_trimmed ** 2) / mse) if mse > 0 else float('inf')
    
    # 输出结果
    print(f"\n📊 性能结果:")
    print(f"测试音频: {duration}秒, {len(test_audio)}采样点")
    print(f"编码时间: {encode_time:.3f}秒")
    print(f"解码时间: {decode_time:.3f}秒")
    print(f"总处理时间: {encode_time + decode_time:.3f}秒")
    print(f"实时倍数: {duration / (encode_time + decode_time):.1f}x")
    
    print(f"\n📈 压缩效果:")
    print(codec.get_statistics())
    
    print(f"\n🎵 音质指标:")
    print(f"均方误差: {mse:.6f}")
    print(f"信噪比: {snr:.1f} dB")
    
    # 判断测试结果
    if snr > 20 and codec.get_compression_ratio() > 3.5:
        print("\n✅ ADPCM性能测试通过！")
        return True
    else:
        print("\n❌ ADPCM性能测试未达标")
        return False


if __name__ == "__main__":
    # 运行基准测试
    benchmark_adpcm()
