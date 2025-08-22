#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建简单的图标文件（开源/自制）
- 使用 PIL 创建简洁现代的图标
- 避免版权问题，使用几何图形和 Unicode 符号
"""

import os
from PIL import Image, ImageDraw, ImageFont

def create_start_icon(size=32):
    """创建开始按钮图标（播放三角形）"""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 绿色播放三角形
    margin = size // 6
    points = [
        (margin, margin),
        (size - margin, size // 2),
        (margin, size - margin)
    ]
    draw.polygon(points, fill=(34, 197, 94, 255))  # 现代绿色
    
    return img

def create_reset_icon(size=32):
    """创建重置按钮图标（循环箭头）"""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 蓝色循环箭头
    center = size // 2
    radius = size // 3
    
    # 绘制圆弧
    bbox = [center - radius, center - radius, center + radius, center + radius]
    draw.arc(bbox, start=45, end=315, fill=(59, 130, 246, 255), width=3)  # 现代蓝色
    
    # 绘制箭头头部
    arrow_size = size // 8
    arrow_x = center + radius - 2
    arrow_y = center - radius + 6
    arrow_points = [
        (arrow_x, arrow_y),
        (arrow_x - arrow_size, arrow_y - arrow_size),
        (arrow_x - arrow_size, arrow_y + arrow_size)
    ]
    draw.polygon(arrow_points, fill=(59, 130, 246, 255))
    
    return img

def create_app_icon(size=64):
    """创建应用图标（盾牌 + 麦克风）"""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 背景圆形
    draw.ellipse([2, 2, size-2, size-2], fill=(99, 102, 241, 255))  # 现代紫色
    
    # 盾牌形状（简化）
    shield_points = [
        (size//2, size//6),
        (size//6*5, size//3),
        (size//6*5, size//3*2),
        (size//2, size//6*5),
        (size//6, size//3*2),
        (size//6, size//3)
    ]
    draw.polygon(shield_points, fill=(255, 255, 255, 200))
    
    # 麦克风（简化）
    mic_x = size // 2
    mic_y = size // 2
    mic_w = size // 8
    mic_h = size // 6
    draw.rectangle([mic_x - mic_w, mic_y - mic_h, mic_x + mic_w, mic_y + mic_h], 
                   fill=(99, 102, 241, 255))
    draw.rectangle([mic_x - 1, mic_y + mic_h, mic_x + 1, mic_y + mic_h + size//12], 
                   fill=(99, 102, 241, 255))
    
    return img

def main():
    # 创建 assets 目录
    assets_dir = 'assets'
    os.makedirs(assets_dir, exist_ok=True)
    
    # 创建图标
    start_icon = create_start_icon(32)
    reset_icon = create_reset_icon(32)
    app_icon = create_app_icon(64)
    
    # 保存 PNG 文件
    start_icon.save(os.path.join(assets_dir, 'start.png'))
    reset_icon.save(os.path.join(assets_dir, 'reset.png'))
    
    # 保存 ICO 文件（多尺寸）
    app_icon_sizes = []
    for size in [16, 32, 48, 64]:
        app_icon_sizes.append(create_app_icon(size))
    
    app_icon_sizes[0].save(
        os.path.join(assets_dir, 'app.ico'),
        format='ICO',
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64)]
    )
    
    print("✅ 图标创建完成:")
    print(f"  - {assets_dir}/start.png (开始按钮)")
    print(f"  - {assets_dir}/reset.png (重置按钮)")
    print(f"  - {assets_dir}/app.ico (应用图标)")

if __name__ == "__main__":
    main()
