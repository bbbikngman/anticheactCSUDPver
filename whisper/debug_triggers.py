#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
调试重复触发问题的测试脚本
"""

import time
from brain_ai_module import BrainAIModule

def test_single_call():
    """测试单次调用是否正常"""
    print("=== 测试单次调用 ===")
    
    brain = BrainAIModule()
    
    print("1. 测试开场白生成...")
    opening_stream = brain.generate_opening_statement()
    opening_text = ""
    for chunk in opening_stream:
        opening_text += chunk
        print(chunk, end="", flush=True)
    print(f"\n开场白完整内容: {opening_text}")
    
    print("\n2. 测试用户回复...")
    user_input = "我没有接到这样的电话"
    response_stream = brain.get_response_stream(user_input)
    response_text = ""
    for chunk in response_stream:
        response_text += chunk
        print(chunk, end="", flush=True)
    print(f"\n回复完整内容: {response_text}")
    
    print("\n3. 检查对话历史...")
    print(f"对话历史长度: {len(brain.kimi.conversation_history)}")
    for i, msg in enumerate(brain.kimi.conversation_history):
        print(f"  {i+1}. {msg['role']}: {msg['content'][:50]}...")

def test_multiple_calls():
    """测试多次调用是否会重复"""
    print("\n=== 测试多次调用 ===")
    
    brain = BrainAIModule()
    
    # 第一次调用
    print("第一次调用开场白...")
    opening1 = "".join(brain.generate_opening_statement())
    print(f"第一次结果: {opening1[:50]}...")
    
    # 第二次调用（不应该重复）
    print("第二次调用开场白...")
    opening2 = "".join(brain.generate_opening_statement())
    print(f"第二次结果: {opening2[:50]}...")
    
    # 检查是否相同
    if opening1 == opening2:
        print("⚠️ 警告：两次调用结果完全相同，可能存在缓存问题")
    else:
        print("✅ 正常：两次调用结果不同（包含随机元素）")

def test_conversation_flow():
    """测试完整对话流程"""
    print("\n=== 测试完整对话流程 ===")
    
    brain = BrainAIModule()
    
    # 开场白
    print("AI: ", end="")
    opening = "".join(brain.generate_opening_statement())
    print(opening)
    
    # 模拟用户回复
    user_inputs = [
        "我没有接到这样的电话",
        "那我应该怎么办？",
        "好的，我知道了"
    ]
    
    for i, user_input in enumerate(user_inputs, 1):
        print(f"\n用户{i}: {user_input}")
        print("AI: ", end="")
        response = "".join(brain.get_response_stream(user_input))
        print(response)
    
    print(f"\n最终对话历史长度: {len(brain.kimi.conversation_history)}")

def main():
    """主测试函数"""
    print("🔍 重复触发问题调试工具")
    print("=" * 50)
    
    try:
        test_single_call()
        test_multiple_calls()
        test_conversation_flow()
        
        print("\n" + "=" * 50)
        print("✅ 所有测试完成")
        
    except Exception as e:
        print(f"❌ 测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
