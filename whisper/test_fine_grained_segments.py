#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试细粒度语音片段分割
"""

import re

def extract_playable_segments(text: str) -> tuple:
    """提取可播放的语音片段（包括逗号分割）"""
    # 更细粒度的分割：逗号、句号、问号、感叹号等
    segment_endings = r'[，。！？,;；.!?]'
    
    # 找到所有分割点
    end_positions = []
    for match in re.finditer(segment_endings, text):
        end_positions.append(match.end())
    
    if not end_positions:
        return [], text
    
    # 提取所有可播放片段
    segments = []
    start = 0
    for end_pos in end_positions:
        segment = text[start:end_pos].strip()
        if segment and len(segment) > 2:  # 至少3个字符才播放
            segments.append(segment)
        start = end_pos
    
    # 剩余文本
    remaining = text[start:].strip() if start < len(text) else ""
    
    return segments, remaining

def test_segment_extraction():
    """测试片段提取功能"""
    print("🔍 测试细粒度片段提取...")
    
    test_cases = [
        {
            "input": "好的，您别急，咱们慢慢说——那您当时跟对方说了哪一句？",
            "expected_segments": ["好的，", "您别急，", "咱们慢慢说——那您当时跟对方说了哪一句？"],
            "expected_remaining": ""
        },
        {
            "input": "您先别急，这个验证码是要发给您的银行卡还是手机号的？千万不要给陌生人！",
            "expected_segments": ["您先别急，", "这个验证码是要发给您的银行卡还是手机号的？", "千万不要给陌生人！"],
            "expected_remaining": ""
        },
        {
            "input": "好的",
            "expected_segments": [],
            "expected_remaining": "好的"
        },
        {
            "input": "您好！我是",
            "expected_segments": ["您好！"],
            "expected_remaining": "我是"
        }
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\n测试用例 {i}:")
        print(f"   输入: '{case['input']}'")
        
        segments, remaining = extract_playable_segments(case['input'])
        
        print(f"   实际片段: {segments}")
        print(f"   实际剩余: '{remaining}'")
        print(f"   预期片段: {case['expected_segments']}")
        print(f"   预期剩余: '{case['expected_remaining']}'")
        
        segments_match = segments == case['expected_segments']
        remaining_match = remaining == case['expected_remaining']
        
        if segments_match and remaining_match:
            print("   ✅ 测试通过")
        else:
            print("   ❌ 测试失败")
            if not segments_match:
                print(f"      片段不匹配")
            if not remaining_match:
                print(f"      剩余文本不匹配")

def simulate_streaming_processing():
    """模拟流式处理过程"""
    print("\n🎵 模拟流式处理过程...")
    
    # 模拟AI逐字返回
    full_text = "好的，您别急，咱们慢慢说——那您当时跟对方说了哪一句？"
    
    buffer = ""
    segment_count = 0
    
    print("逐字符处理:")
    for char in full_text:
        buffer += char
        print(f"   buffer: '{buffer}'")
        
        # 检查是否有新的可播放片段
        segments, remaining = extract_playable_segments(buffer)
        
        if segments:
            # 找出新增的片段
            new_segments = segments[segment_count:]
            for segment in new_segments:
                segment_count += 1
                print(f"   🎯 检测到片段 #{segment_count}: '{segment}' -> 立即播放!")
            
            # 更新buffer
            buffer = remaining
    
    # 处理最后剩余的文本
    if buffer.strip():
        segment_count += 1
        print(f"   🎯 最后片段 #{segment_count}: '{buffer}' -> 播放!")
    
    print(f"\n📊 总共生成 {segment_count} 个播放片段")

def compare_with_traditional():
    """对比传统方式和细粒度方式"""
    print("\n📊 传统方式 vs 细粒度方式对比...")
    
    text = "好的，您别急，咱们慢慢说——那您当时跟对方说了哪一句？"
    
    # 传统方式：等完整句子
    traditional_pattern = r'[。！？.!?]'
    traditional_match = re.search(traditional_pattern, text)
    if traditional_match:
        traditional_first = text[:traditional_match.end()]
        traditional_delay = "等待完整句子完成"
    else:
        traditional_first = "无完整句子"
        traditional_delay = "需要等待更多内容"
    
    # 细粒度方式：遇到逗号就播放
    segments, _ = extract_playable_segments(text)
    fine_grained_first = segments[0] if segments else "无可播放片段"
    
    print(f"原文: '{text}'")
    print(f"\n传统方式:")
    print(f"   第一个播放内容: '{traditional_first}'")
    print(f"   播放时机: {traditional_delay}")
    
    print(f"\n细粒度方式:")
    print(f"   第一个播放内容: '{fine_grained_first}'")
    print(f"   播放时机: 遇到第一个逗号立即播放")
    
    if segments:
        print(f"   所有片段: {segments}")
        print(f"   优势: 用户更早听到回复，体验更流畅")

def main():
    """主测试函数"""
    print("🧪 细粒度语音片段分割测试")
    print("=" * 50)
    
    # 测试片段提取
    test_segment_extraction()
    
    # 模拟流式处理
    simulate_streaming_processing()
    
    # 对比分析
    compare_with_traditional()
    
    print("\n" + "=" * 50)
    print("✅ 测试完成！")
    print("\n💡 关键改进:")
    print("1. 🎯 遇到逗号立即播放 - 不等完整句子")
    print("2. 🚀 用户体验更快 - 更早听到回复")
    print("3. 🔄 真正的流式播放 - 边生成边播放")
    print("4. 📝 细粒度分割 - 逗号、分号、句号等都是分割点")

if __name__ == "__main__":
    main()
