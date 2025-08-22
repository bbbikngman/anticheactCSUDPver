#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新功能演示脚本 - 展示多轮对话、上下文管理、部分模式等功能
"""

import time

def demo_context_management():
    """演示上下文管理功能"""
    print("🔍 演示上下文管理功能")
    print("=" * 50)
    
    from brain_ai_module import BrainAIModule
    
    # 创建AI实例，限制上下文为5条消息
    ai = BrainAIModule()
    ai.kimi.max_context_messages = 5
    
    print("设置上下文限制为5条消息")
    
    # 模拟多轮对话
    test_inputs = [
        "我叫张三，今年25岁",
        "我住在北京",
        "我是程序员",
        "我喜欢打篮球",
        "我有一只猫",
        "我的猫叫小白",
        "你还记得我的名字吗？",  # 测试长期记忆
        "我住在哪里？",         # 测试中期记忆
        "我的猫叫什么名字？"     # 测试短期记忆
    ]
    
    for i, user_input in enumerate(test_inputs, 1):
        print(f"\n轮次 {i}: {user_input}")
        print("AI: ", end="")
        
        response = ""
        for chunk in ai.get_response_stream(user_input):
            response += chunk
            print(chunk, end="", flush=True)
        
        print()
        print(f"📊 {ai.kimi.get_conversation_summary()}")
        
        time.sleep(1)

def demo_partial_mode():
    """演示部分模式功能"""
    print("\n🎭 演示部分模式功能")
    print("=" * 50)
    
    from brain_ai_module import BrainAIModule
    
    ai = BrainAIModule()
    
    # 测试客服模式
    print("\n1. 客服模式演示 - 每句话以'亲爱的客户，您好'开头")
    
    test_queries = [
        "我想咨询一下产品信息",
        "价格是多少？",
        "有什么优惠吗？"
    ]
    
    for query in test_queries:
        print(f"\n用户: {query}")
        print("客服: ", end="")
        
        # 使用部分模式，强制以客服用语开头
        response = ""
        for chunk in ai.get_response_stream(
            query, 
            use_partial_mode=True, 
            partial_content="亲爱的客户，您好，"
        ):
            response += chunk
            print(chunk, end="", flush=True)
        
        print()
        time.sleep(1)
    
    # 测试角色扮演模式
    print("\n2. 角色扮演模式演示 - AI扮演反诈专员")
    
    ai.kimi.clear_conversation_history()
    
    role_queries = [
        "有人给我打电话说我中奖了",
        "他们要我提供银行卡号",
        "我应该怎么办？"
    ]
    
    for query in role_queries:
        print(f"\n用户: {query}")
        print("反诈专员: ", end="")
        
        # 使用部分模式，强制以反诈专员身份回复
        response = ""
        for chunk in ai.get_response_stream(
            query, 
            use_partial_mode=True, 
            partial_name="反诈专员",
            partial_content=""
        ):
            response += chunk
            print(chunk, end="", flush=True)
        
        print()
        time.sleep(1)

def demo_retry_mechanism():
    """演示重试机制"""
    print("\n🔄 演示重试机制")
    print("=" * 50)
    
    from brain_ai_module import BrainAIModule
    from brain_ai_websocket import BrainAIWebSocketModule
    
    print("测试HTTP和WebSocket版本的重试机制...")
    
    # 测试正常情况
    print("\n1. 正常请求测试")
    
    http_ai = BrainAIModule()
    websocket_ai = BrainAIWebSocketModule()
    
    test_query = "你好"
    
    print("HTTP版本: ", end="")
    start_time = time.time()
    for chunk in http_ai.get_response_stream(test_query):
        print(chunk, end="", flush=True)
    http_time = time.time() - start_time
    print(f" (耗时: {http_time:.2f}s)")
    
    print("WebSocket版本: ", end="")
    start_time = time.time()
    for chunk in websocket_ai.get_response_stream(test_query):
        print(chunk, end="", flush=True)
    websocket_time = time.time() - start_time
    print(f" (耗时: {websocket_time:.2f}s)")
    
    print(f"\n性能对比: HTTP {http_time:.2f}s vs WebSocket {websocket_time:.2f}s")

def demo_conversation_continuity():
    """演示对话连续性"""
    print("\n💬 演示对话连续性")
    print("=" * 50)
    
    from brain_ai_module import BrainAIModule
    
    ai = BrainAIModule()
    
    # 模拟被打断的对话
    print("模拟对话被打断的场景...")
    
    print("\n用户: 请详细介绍一下电信诈骗的常见手段")
    print("AI: ", end="")
    
    # 模拟长回复被打断
    response_chunks = []
    chunk_count = 0
    
    for chunk in ai.get_response_stream("请详细介绍一下电信诈骗的常见手段"):
        response_chunks.append(chunk)
        print(chunk, end="", flush=True)
        chunk_count += 1
        
        # 模拟在第10个chunk后被打断
        if chunk_count == 10:
            print("\n[模拟用户打断]")
            break
    
    # 使用部分模式继续之前的回复
    partial_content = "".join(response_chunks)
    
    print(f"\n用户: 继续说")
    print("AI: ", end="")
    
    # 从被打断的地方继续
    for chunk in ai.get_response_stream(
        "继续说", 
        use_partial_mode=True, 
        partial_content=partial_content
    ):
        print(chunk, end="", flush=True)
    
    print()

def main():
    """主演示函数"""
    print("🚀 新功能演示")
    print("=" * 60)
    
    try:
        # 演示各种功能
        demo_context_management()
        demo_partial_mode()
        demo_retry_mechanism()
        demo_conversation_continuity()
        
        print("\n" + "=" * 60)
        print("✅ 所有功能演示完成！")
        print("\n新功能总结:")
        print("1. 🧠 智能上下文管理 - 自动控制对话历史长度")
        print("2. 🎭 部分模式支持 - 客服模式、角色扮演")
        print("3. 🔄 重试机制 - 网络异常自动重试")
        print("4. 💬 对话连续性 - 支持打断后继续")
        print("5. 📊 性能监控 - 实时响应时间统计")
        
    except Exception as e:
        print(f"❌ 演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
