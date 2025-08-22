#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复prompts.py中的**强调**格式，避免TTS读出星号
"""

import re

def fix_prompts():
    """修复prompts.py文件"""
    
    # 读取原文件
    with open('prompts.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("🔧 开始修复prompts.py中的**强调**格式...")
    
    # 统计修复前的**数量
    before_count = content.count('**')
    print(f"修复前发现 {before_count} 个星号")
    
    # 替换所有的**文本**格式
    # 匹配 **任何内容** 的模式
    pattern = r'\*\*(.*?)\*\*'
    
    def replace_emphasis(match):
        text = match.group(1)
        # 如果是标题或重要内容，保留【】格式
        if any(keyword in text for keyword in ['第一原则', '第二原则', '第三原则', '口语化', '简洁为王', '善用语气词']):
            return f'【{text}】'
        # 如果是示范内容，保留原文
        elif '正确示范' in text or '错误示范' in text:
            return text
        # 其他情况直接去掉星号
        else:
            return text
    
    # 执行替换
    fixed_content = re.sub(pattern, replace_emphasis, content)
    
    # 统计修复后的**数量
    after_count = fixed_content.count('**')
    print(f"修复后剩余 {after_count} 个星号")
    
    # 写入修复后的文件
    with open('prompts.py', 'w', encoding='utf-8') as f:
        f.write(fixed_content)
    
    print(f"✅ 修复完成！共处理了 {(before_count - after_count) // 2} 个强调格式")
    
    # 显示修复的关键部分
    print("\n📋 修复示例:")
    print("修复前: **绝对不要给！**")
    print("修复后: 绝对不要给！")
    print("\n修复前: **【口语化】**")
    print("修复后: 【口语化】")

if __name__ == "__main__":
    fix_prompts()
