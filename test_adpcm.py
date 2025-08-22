#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ADPCM编解码器测试套件
验证压缩效果、音质和性能
"""

import numpy as np
import time
from adpcm_codec import ADPCMCodec, ADPCMProtocol

def test_basic_roundtrip():
    """基础往返测试"""
    print("🔄 基础往返测试...")
    
    codec = ADPCMCodec()
    
    # 生成测试音频（正弦波）
    sample_rate = 16000
    duration = 1.0  # 1秒
    t = np.linspace(0, duration, int(sample_rate * duration))
    original = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    
    # 分块处理（模拟实际使用）
    block_size = 512
    reconstructed = []
    compression_ratios = []
    
    for i in range(0, len(original), block_size):
        block = original[i:i+block_size]
        if len(block) < block_size:
            # 填充最后一块到完整大小
            padded_block = np.zeros(block_size, dtype=np.float32)
            padded_block[:len(block)] = block
            block = padded_block
        
        # 编码
        compressed = codec.encode(block)
        original_size = len(block) * 4  # float32 = 4 bytes
        compressed_size = len(compressed)
        
        if compressed_size > 0:
            ratio = original_size / compressed_size
            compression_ratios.append(ratio)
        
        # 解码
        decoded = codec.decode(compressed)
        reconstructed.extend(decoded)
    
    # 计算音质损失
    reconstructed = np.array(reconstructed[:len(original)])
    mse = np.mean((original - reconstructed) ** 2)
    avg_compression = np.mean(compression_ratios) if compression_ratios else 0
    
    print(f"  平均压缩比: {avg_compression:.1f}:1")
    print(f"  均方误差: {mse:.6f}")
    
    # 验证结果
    assert avg_compression > 3.5, f"压缩比过低: {avg_compression:.1f}"
    assert mse < 0.01, f"音质损失过大: {mse:.6f}"
    
    print("  ✅ 基础往返测试通过")
    return True

def test_protocol_packing():
    """协议打包测试"""
    print("📦 协议打包测试...")
    
    # 测试数据
    test_data = b"ADPCM_TEST_DATA_12345"
    
    # 打包
    packet = ADPCMProtocol.pack_audio_packet(test_data, ADPCMProtocol.COMPRESSION_ADPCM)
    
    # 解包
    compression_type, audio_data = ADPCMProtocol.unpack_audio_packet(packet)
    
    # 验证
    assert compression_type == ADPCMProtocol.COMPRESSION_ADPCM
    assert audio_data == test_data
    
    print(f"  原始数据: {len(test_data)} 字节")
    print(f"  打包后: {len(packet)} 字节")
    print(f"  协议开销: {len(packet) - len(test_data)} 字节")
    print("  ✅ 协议打包测试通过")
    return True

def test_multi_client_simulation():
    """多客户端模拟测试"""
    print("👥 多客户端模拟测试...")
    
    # 创建3个独立的编解码器（模拟3个客户端）
    clients = [ADPCMCodec() for _ in range(3)]
    
    # 为每个客户端生成不同的测试音频
    sample_rate = 16000
    block_size = 512
    test_blocks = []
    
    for i in range(3):
        # 不同频率的正弦波
        freq = 440 * (i + 1)  # 440Hz, 880Hz, 1320Hz
        t = np.linspace(0, block_size/sample_rate, block_size)
        audio = np.sin(2 * np.pi * freq * t).astype(np.float32)
        test_blocks.append(audio)
    
    # 模拟并发编解码
    results = []
    for i, (client, audio) in enumerate(zip(clients, test_blocks)):
        # 编码
        compressed = client.encode(audio)
        
        # 解码
        decoded = client.decode(compressed)
        
        # 验证
        mse = np.mean((audio - decoded) ** 2)
        results.append(mse)
        
        print(f"  客户端{i+1}: MSE={mse:.6f}")
    
    # 验证所有客户端都正常工作
    for i, mse in enumerate(results):
        assert mse < 0.01, f"客户端{i+1}音质损失过大: {mse:.6f}"
    
    print("  ✅ 多客户端模拟测试通过")
    return True

def test_edge_cases():
    """边界情况测试"""
    print("⚠️ 边界情况测试...")
    
    codec = ADPCMCodec()
    
    # 测试1: 空数据
    try:
        empty_audio = np.array([], dtype=np.float32)
        compressed = codec.encode(empty_audio)
        decoded = codec.decode(compressed)
        print("  ✅ 空数据处理正常")
    except Exception as e:
        print(f"  ❌ 空数据处理失败: {e}")
        return False
    
    # 测试2: 极值数据
    try:
        extreme_audio = np.array([1.0, -1.0, 1.0, -1.0] * 128, dtype=np.float32)
        compressed = codec.encode(extreme_audio)
        decoded = codec.decode(compressed)
        print("  ✅ 极值数据处理正常")
    except Exception as e:
        print(f"  ❌ 极值数据处理失败: {e}")
        return False
    
    # 测试3: 静音数据
    try:
        silence = np.zeros(512, dtype=np.float32)
        compressed = codec.encode(silence)
        decoded = codec.decode(compressed)
        print("  ✅ 静音数据处理正常")
    except Exception as e:
        print(f"  ❌ 静音数据处理失败: {e}")
        return False
    
    # 测试4: 状态重置
    try:
        codec.reset_all()
        print("  ✅ 状态重置正常")
    except Exception as e:
        print(f"  ❌ 状态重置失败: {e}")
        return False
    
    print("  ✅ 边界情况测试通过")
    return True

def test_performance():
    """性能测试"""
    print("⚡ 性能测试...")
    
    codec = ADPCMCodec()
    
    # 生成较长的测试音频（10秒）
    sample_rate = 16000
    duration = 10
    block_size = 512
    
    # 生成复杂音频信号（多频率混合）
    t = np.linspace(0, duration, sample_rate * duration)
    audio = (
        0.3 * np.sin(2 * np.pi * 440 * t) +
        0.2 * np.sin(2 * np.pi * 880 * t) +
        0.1 * np.sin(2 * np.pi * 220 * t)
    ).astype(np.float32)
    
    # 编码性能测试
    encode_start = time.time()
    compressed_blocks = []
    
    for i in range(0, len(audio), block_size):
        block = audio[i:i+block_size]
        if len(block) == block_size:
            compressed = codec.encode(block)
            compressed_blocks.append(compressed)
    
    encode_time = time.time() - encode_start
    
    # 解码性能测试
    codec.reset_decoder()  # 重置解码器状态
    decode_start = time.time()
    
    for compressed in compressed_blocks:
        decoded = codec.decode(compressed)
    
    decode_time = time.time() - decode_start
    
    # 计算性能指标
    total_time = encode_time + decode_time
    realtime_factor = duration / total_time
    
    print(f"  音频时长: {duration}秒")
    print(f"  编码时间: {encode_time:.3f}秒")
    print(f"  解码时间: {decode_time:.3f}秒")
    print(f"  总处理时间: {total_time:.3f}秒")
    print(f"  实时倍数: {realtime_factor:.1f}x")
    
    # 验证性能要求（至少要能实时处理）
    assert realtime_factor > 1.0, f"处理速度过慢: {realtime_factor:.1f}x"
    
    print("  ✅ 性能测试通过")
    return True

def test_bandwidth_calculation():
    """带宽计算验证"""
    print("📊 带宽计算验证...")
    
    # 模拟实际使用场景
    sample_rate = 16000
    block_size = 512
    blocks_per_second = sample_rate / block_size  # 31.25 blocks/sec
    
    # 原始PCM带宽
    original_bytes_per_block = block_size * 4  # float32 = 4 bytes
    original_bandwidth_bps = original_bytes_per_block * blocks_per_second * 8
    original_bandwidth_kbps = original_bandwidth_bps / 1000
    
    # ADPCM压缩后带宽（理论值）
    adpcm_bytes_per_block = block_size // 4  # 4:1压缩
    protocol_overhead = 5  # 1字节压缩标识 + 4字节长度
    total_bytes_per_block = adpcm_bytes_per_block + protocol_overhead
    
    adpcm_bandwidth_bps = total_bytes_per_block * blocks_per_second * 8
    adpcm_bandwidth_kbps = adpcm_bandwidth_bps / 1000
    
    bandwidth_reduction = (1 - adpcm_bandwidth_kbps / original_bandwidth_kbps) * 100
    
    print(f"  原始带宽: {original_bandwidth_kbps:.0f} kbps")
    print(f"  ADPCM带宽: {adpcm_bandwidth_kbps:.0f} kbps")
    print(f"  带宽节省: {bandwidth_reduction:.1f}%")
    
    # 验证带宽节省效果
    assert bandwidth_reduction > 70, f"带宽节省不足: {bandwidth_reduction:.1f}%"
    assert adpcm_bandwidth_kbps < 150, f"ADPCM带宽过高: {adpcm_bandwidth_kbps:.0f} kbps"
    
    print("  ✅ 带宽计算验证通过")
    return True

def run_all_tests():
    """运行所有测试"""
    print("🧪 ADPCM编解码器测试套件")
    print("=" * 50)
    
    tests = [
        ("基础往返测试", test_basic_roundtrip),
        ("协议打包测试", test_protocol_packing),
        ("多客户端模拟", test_multi_client_simulation),
        ("边界情况测试", test_edge_cases),
        ("性能测试", test_performance),
        ("带宽计算验证", test_bandwidth_calculation),
    ]
    
    passed = 0
    failed = 0
    
    for test_name, test_func in tests:
        try:
            print(f"\n{test_name}:")
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"  ❌ {test_name}失败: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"测试结果: {passed}通过, {failed}失败")
    
    if failed == 0:
        print("🎉 所有测试通过！ADPCM编解码器可以部署。")
        return True
    else:
        print("⚠️ 部分测试失败，请检查实现。")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
