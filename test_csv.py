#!/usr/bin/env python3
"""
video_history.csv 功能测试脚本
"""

import os
import csv
import sys
from datetime import datetime

# 导入 main 模块
sys.path.insert(0, os.path.dirname(__file__))
import main

def test_save_and_read():
    """测试保存和读取视频历史"""
    print("\n🧪 开始测试视频历史 CSV 功能...\n")
    
    # 测试用户
    test_username = "test_user"
    test_task_id = "test_task_123"
    test_prompt = "测试提示词：一只跳舞的猫"
    test_filename = "test_video.mp4"
    test_size = 1024 * 1024  # 1MB
    
    print(f"📝 测试 1: 保存视频历史")
    print(f"   - 用户名: {test_username}")
    print(f"   - 任务ID: {test_task_id}")
    print(f"   - 提示词: {test_prompt}")
    print(f"   - 文件名: {test_filename}")
    print(f"   - 大小: {test_size} 字节")
    
    # 保存视频信息
    main.save_video_to_history(
        task_id=test_task_id,
        username=test_username,
        prompt=test_prompt,
        video_filename=test_filename,
        size=test_size,
        status="completed"
    )
    print(f"   ✅ 已保存到 CSV\n")
    
    # 创建虚拟视频文件（用于测试）
    test_video_path = os.path.join(main.VIDEO_FOLDER, test_filename)
    with open(test_video_path, 'wb') as f:
        f.write(b'fake video content' * 1000)
    print(f"   ✅ 创建虚拟视频文件: {test_video_path}\n")
    
    # 读取视频历史
    print(f"📖 测试 2: 读取用户的视频历史")
    videos = main.get_user_videos_from_csv(test_username)
    print(f"   ✅ 读取成功，找到 {len(videos)} 个视频")
    
    if videos:
        print(f"\n   📹 视频详情:")
        for i, video in enumerate(videos, 1):
            print(f"      {i}. Task ID: {video['task_id']}")
            print(f"         Filename: {video['filename']}")
            print(f"         Prompt: {video['prompt']}")
            print(f"         Size: {video['size']} 字节")
            print(f"         Created: {video['created_at']}")
            print(f"         Status: {video['status']}")
    
    # 检查 CSV 文件内容
    print(f"\n📋 测试 3: 直接检查 CSV 文件内容")
    print(f"   CSV 文件路径: {main.VIDEO_HISTORY_CSV}\n")
    
    with open(main.VIDEO_HISTORY_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        print(f"   📊 CSV 文件包含 {len(rows)} 条记录 (不含表头)")
        
        if rows:
            print(f"\n   最后一条记录:")
            last_row = rows[-1]
            for key, value in last_row.items():
                print(f"      {key}: {value}")
    
    # 测试用户隔离
    print(f"\n🔐 测试 4: 用户隔离（另一个用户应看不到该视频）")
    other_user_videos = main.get_user_videos_from_csv("other_user")
    print(f"   其他用户看到的视频数: {len(other_user_videos)}")
    if len(other_user_videos) == 0:
        print(f"   ✅ 用户隔离正常！\n")
    else:
        print(f"   ❌ 用户隔离失败！\n")
    
    print("✨ 所有测试完成！")

if __name__ == "__main__":
    test_save_and_read()
