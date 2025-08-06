#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版视频下载器
快速下载视频的简单脚本
"""

import re
import json
import hashlib
import requests
import os
from pathlib import Path

def download_video(url, save_dir="downloads"):
    """
    下载视频的简化函数
    
    Args:
        url (str): 视频链接
        save_dir (str): 保存目录
    """
    # 创建保存目录
    Path(save_dir).mkdir(exist_ok=True)
    
    # 服务器配置
    server_url = "https://www.bestvideow.com/"
    salt = "bf5941f27ee14d9ba9ebb72d89de5dea"
    
    # 平台识别规则
    platforms = {
        "bilibili": [".bilibili.com", "b23.tv"],
        "douyin": ["douyin.com"],
        "kuaishou": ["kuaishou.com"],
        "xhs": ["xiaohongshu.com", "xhslink.com"],
        "tiktok": ["tiktok.com"],
        "youtube": ["youtube.com", "youtu.be"],
        "weibo": ["weibo.com"]
    }
    
    # 提取URL
    url_match = re.search(r'https?://[^\s,，]+', url)
    if not url_match:
        print("❌ 未找到有效的URL")
        return False
    
    extracted_url = url_match.group()
    print(f"🔗 提取URL: {extracted_url}")
    
    # 识别平台
    platform = None
    for p, patterns in platforms.items():
        if any(pattern in extracted_url.lower() for pattern in patterns):
            platform = p
            break
    
    if not platform:
        print("❌ 不支持的平台")
        return False
    
    print(f"📱 识别平台: {platform}")
    
    # 加密参数
    data = salt + extracted_url + platform
    encrypted = hashlib.sha256(data.encode('utf-8')).hexdigest()
    
    # 准备请求数据
    json_data = {
        "url": extracted_url,
        "platform": platform,
        "params": encrypted
    }
    
    # 请求头
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Content-Type': 'application/json'
    }
    
    try:
        print("⏳ 正在解析...")
        response = requests.post(
            f"{server_url}video/parseVideoUrl",
            json=json_data,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 200:
                data = result.get('data', {})
                video_list = data.get('voideDeatilVoList', [])
                
                if not video_list:
                    print("❌ 未找到可下载的文件")
                    return False
                
                # 获取视频标题
                video_title = data.get('title', '')
                if not video_title:
                    # 尝试从第一个视频项中获取标题
                    if video_list and len(video_list) > 0:
                        video_title = video_list[0].get('title', '')
                
                print(f"✅ 解析成功！找到 {len(video_list)} 个文件")
                if video_title:
                    print(f"📝 视频标题: {video_title}")
                
                # 下载文件
                for i, item in enumerate(video_list):
                    file_url = item.get('url')
                    file_type = item.get('type', 'video')
                    
                    if not file_url:
                        continue
                    
                    # 生成文件名
                    extension = '.jpg' if file_type == 'image' else '.mp4'
                    
                    # 使用视频标题命名文件（如果可用）
                    if video_title and video_title.strip():
                        # 清理标题中的非法字符
                        safe_title = sanitize_filename(video_title)
                        if len(video_list) == 1:
                            # 单个文件，直接使用标题
                            filename = f"{safe_title}{extension}"
                        else:
                            # 多个文件，添加索引
                            filename = f"{safe_title}_{i+1}{extension}"
                    else:
                        # 使用平台名和索引
                        filename = f"{platform}_{i+1}{extension}"
                    
                    file_path = Path(save_dir) / filename
                    
                    print(f"📥 下载中: {filename}")
                    
                    # 下载文件
                    try:
                        file_response = requests.get(file_url, stream=True, timeout=30)
                        file_response.raise_for_status()
                        
                        with open(file_path, 'wb') as f:
                            for chunk in file_response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                        
                        print(f"✅ 下载完成: {file_path}")
                        
                    except Exception as e:
                        print(f"❌ 下载失败: {e}")
                        return False
                
                return True
            else:
                print(f"❌ 解析失败: {result.get('message', '未知错误')}")
                return False
        else:
            print(f"❌ 请求失败，状态码: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 网络错误: {e}")
        return False

def sanitize_filename(filename):
    """
    清理文件名，移除或替换非法字符
    
    Args:
        filename (str): 原始文件名
        
    Returns:
        str: 清理后的文件名
    """
    import re
    # Windows文件系统不允许的字符
    illegal_chars = r'[<>:"/\\|?*]'
    # 替换为下划线
    safe_name = re.sub(illegal_chars, '_', filename)
    # 移除首尾空格和点
    safe_name = safe_name.strip(' .')
    # 限制长度（Windows路径限制）
    if len(safe_name) > 200:
        safe_name = safe_name[:200]
    return safe_name

def main():
    """主函数"""
    print("🎬 视频下载器")
    print("=" * 40)
    
    while True:
        url = input("\n请输入视频链接 (输入 'q' 退出): ").strip()
        
        if url.lower() in ['q', 'quit', 'exit']:
            print("👋 再见！")
            break
        
        if not url:
            continue
        
        # 下载视频
        success = download_video(url)
        
        if success:
            print("\n🎉 所有文件下载完成！")
        else:
            print("\n💡 下载失败，请检查链接或重试")
        
        print("-" * 40)

if __name__ == "__main__":
    main() 