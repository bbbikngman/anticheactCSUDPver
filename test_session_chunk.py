#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试Session和Chunk ID功能
"""

import struct
from adpcm_codec import ADPCMProtocol

def test_session_chunk_protocol():
    """测试新的session和chunk协议"""
    print("🧪 测试Session和Chunk ID协议...")
    
    # 测试数据
    test_mp3_data = b"FAKE_MP3_DATA_FOR_TESTING_12345"
    test_session_id = "abc12345"
    test_chunk_id = 42
    
    print(f"原始数据:")
    print(f"  MP3数据: {len(test_mp3_data)} 字节")
    print(f"  Session ID: {test_session_id}")
    print(f"  Chunk ID: {test_chunk_id}")
    
    # 打包
    try:
        packet = ADPCMProtocol.pack_audio_with_session(
            test_mp3_data, test_session_id, test_chunk_id
        )
        print(f"✅ 打包成功，包大小: {len(packet)} 字节")
        
        # 解包
        compression_type, session_id, chunk_id, audio_data = ADPCMProtocol.unpack_audio_with_session(packet)
        
        print(f"解包结果:")
        print(f"  压缩类型: {compression_type}")
        print(f"  Session ID: '{session_id}'")
        print(f"  Chunk ID: {chunk_id}")
        print(f"  音频数据: {len(audio_data)} 字节")
        
        # 验证
        assert compression_type == ADPCMProtocol.COMPRESSION_TTS_MP3
        assert session_id == test_session_id
        assert chunk_id == test_chunk_id
        assert audio_data == test_mp3_data
        
        print("✅ 协议测试通过！")
        return True
        
    except Exception as e:
        print(f"❌ 协议测试失败: {e}")
        return False

def test_session_id_edge_cases():
    """测试Session ID的边界情况"""
    print("\n🧪 测试Session ID边界情况...")
    
    test_cases = [
        ("", "空字符串"),
        ("a", "单字符"),
        ("12345678", "8字符"),
        ("123456789", "9字符（应截断）"),
        ("中文测试", "中文字符"),
    ]
    
    for session_id, description in test_cases:
        try:
            packet = ADPCMProtocol.pack_audio_with_session(
                b"test", session_id, 1
            )
            _, decoded_session, _, _ = ADPCMProtocol.unpack_audio_with_session(packet)
            print(f"  {description}: '{session_id}' -> '{decoded_session}'")
        except Exception as e:
            print(f"  {description}: 失败 - {e}")

if __name__ == "__main__":
    print("=" * 50)
    print("Session和Chunk ID协议测试")
    print("=" * 50)
    
    success = test_session_chunk_protocol()
    test_session_id_edge_cases()
    
    if success:
        print("\n🎉 所有测试通过！")
    else:
        print("\n❌ 测试失败！")
