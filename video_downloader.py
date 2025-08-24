#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频解析下载器
支持抖音、B站、快手、小红书、YouTube等平台的视频下载
"""

import re
import json
import hashlib
import requests
import os
import time
from urllib.parse import urlparse
from pathlib import Path
import urllib3
import argparse
import sys

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class VideoDownloader:
    def __init__(self, download_dir="downloads"):
        """
        初始化下载器
        
        Args:
            download_dir (str): 下载目录
        """
        self.server_url = "https://www.bestvideow.com/"
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        
        # 平台识别规则
        self.platform_rules = {
            "bilibili": [".bilibili.com", "b23.tv", "bili2233.cn"],
            "douyin": ["douyin.com"],
            "kuaishou": ["kuaishou.com"],
            "pipix": ["pipix.com"],
            "xhs": ["www.xiaohongshu.com", "xhslink.com"],
            "tiktok": ["tiktok.com"],
            "xigua": ["ixigua.com"],
            "weishi": ["weishi.qq.com"],
            "weibo": ["weibo.com"],
            "jingdong": ["jd.com", "3.cn"],
            "youtube": ["youtu.be", "youtube.com"],
            "haokan": ["hao123.com", "haokan.baidu.com"],
            "facebook": ["fb.watch", "facebook.com"],
            "twitter": ["x.com", "twitter.com"],
            "instagram": ["instagram.com"]
        }
        
        # 请求头
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Content-Type': 'application/json',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        # 加密盐值
        self.salt = "bf5941f27ee14d9ba9ebb72d89de5dea"
        
    def extract_url(self, text):
        """
        从文本中提取URL链接
        
        Args:
            text (str): 包含URL的文本
            
        Returns:
            str: 提取的URL，如果没有找到则返回None
        """
        # 匹配HTTP/HTTPS链接的正则表达式，排除常见的分隔符和标点符号
        url_pattern = r'https?://[^\s,，`\'"\]\)\}]+'
        matches = re.findall(url_pattern, text)
        
        if matches:
            # 清理URL末尾可能的标点符号
            url = matches[0]
            # 移除末尾的标点符号
            url = url.rstrip('`\'"\]\)\}.,;:!?')
            return url
        return None
    
    def identify_platform(self, url):
        """
        根据URL识别视频平台
        
        Args:
            url (str): 视频URL
            
        Returns:
            str: 平台名称，如果不支持则返回None
        """
        url_lower = url.lower()
        
        for platform, patterns in self.platform_rules.items():
            for pattern in patterns:
                if pattern in url_lower:
                    # 特殊处理：抖音搜索链接不支持
                    if platform == "douyin" and "douyin.com/search" in url_lower:
                        print("暂不支持抖音搜索链接下载，请重新输入！")
                        return None
                    return platform
        
        return None
    
    def encrypt_params(self, url, platform):
        """
        使用SHA-256加密请求参数
        
        Args:
            url (str): 视频URL
            platform (str): 平台名称
            
        Returns:
            str: 加密后的参数
        """
        # 拼接盐值+URL+平台
        data = self.salt + url + platform
        # 使用SHA-256加密
        hash_object = hashlib.sha256(data.encode('utf-8'))
        return hash_object.hexdigest()
    
    def parse_video(self, url, token=None):
        """
        解析视频链接
        
        Args:
            url (str): 视频URL
            token (str, optional): 用户token
            
        Returns:
            dict: 解析结果
        """
        # 提取URL
        extracted_url = self.extract_url(url)
        if not extracted_url:
            print("解析失败：未找到有效的URL链接")
            return None
        
        # 识别平台
        platform = self.identify_platform(extracted_url)
        if not platform:
            print("解析失败：不支持的视频平台")
            return None
        
        print(f"识别平台: {platform}")
        print(f"解析URL: {extracted_url}")
        
        # 准备请求数据
        json_data = {
            "url": extracted_url,
            "platform": platform
        }
        
        # 添加用户token（如果有）
        if token:
            json_data["token"] = token
        
        # 加密参数
        encrypted_params = self.encrypt_params(extracted_url, platform)
        json_data["params"] = encrypted_params
        
        # 添加时间戳
        headers = self.headers.copy()
        headers['timestamg'] = str(int(time.time() * 1000))
        
        if token:
            headers['Authorization'] = token
        
        try:
            # 发送请求
            print("正在解析视频...")
            response = requests.post(
                f"{self.server_url}video/parseVideoUrl",
                json=json_data,
                headers=headers,
                timeout=30,
                verify=False
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 200:
                    print("解析成功！")
                    return result.get('data')
                else:
                    print(f"解析失败: {result.get('message', '未知错误')}")
                    return None
            else:
                print(f"请求失败，状态码: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"网络请求错误: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"JSON解析错误: {e}")
            return None
    
    def download_file(self, url, filename, chunk_size=8192, max_retries=3):
        """
        下载文件
        
        Args:
            url (str): 文件URL
            filename (str): 保存的文件名
            chunk_size (int): 分块大小
            max_retries (int): 最大重试次数
            
        Returns:
            bool: 下载是否成功
        """
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"第 {attempt + 1} 次重试下载: {filename}")
                else:
                    print(f"正在下载: {filename}")
                
                # 为不同平台设置特定的请求头
                download_headers = self.headers.copy()
                
                # 检测是否为B站链接，如果是则添加特定的请求头
                if 'bilivideo.com' in url or 'bilibili.com' in url:
                    download_headers.update({
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Referer': 'https://www.bilibili.com/',
                        'Origin': 'https://www.bilibili.com',
                        'Accept': '*/*',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                        'Accept-Encoding': 'identity;q=1, *;q=0',
                        'Range': 'bytes=0-',
                        'Sec-Fetch-Dest': 'video',
                        'Sec-Fetch-Mode': 'cors',
                        'Sec-Fetch-Site': 'cross-site',
                        'Connection': 'keep-alive',
                        'Cache-Control': 'no-cache',
                        'Pragma': 'no-cache'
                    })
                # 检测是否为抖音链接
                elif 'douyin.com' in url or 'amemv.com' in url:
                    download_headers.update({
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Referer': 'https://www.douyin.com/',
                        'Accept': '*/*',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                        'Accept-Encoding': 'identity;q=1, *;q=0',
                        'Range': 'bytes=0-'
                    })
                # 检测是否为快手链接
                elif 'kuaishou.com' in url or 'gifshow.com' in url:
                    download_headers.update({
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Referer': 'https://www.kuaishou.com/',
                        'Accept': '*/*',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                        'Accept-Encoding': 'identity;q=1, *;q=0',
                        'Range': 'bytes=0-'
                    })
                # 检测是否为小红书链接
                elif 'xiaohongshu.com' in url or 'xhslink.com' in url:
                    download_headers.update({
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Referer': 'https://www.xiaohongshu.com/',
                        'Accept': '*/*',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                        'Accept-Encoding': 'identity;q=1, *;q=0',
                        'Range': 'bytes=0-'
                    })
                # 检测是否为YouTube链接
                elif 'youtube.com' in url or 'youtu.be' in url:
                    download_headers.update({
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Referer': 'https://www.youtube.com/',
                        'Accept': '*/*',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                        'Accept-Encoding': 'identity;q=1, *;q=0',
                        'Range': 'bytes=0-'
                    })
                else:
                    # 通用下载请求头
                    download_headers.update({
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': '*/*',
                        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                        'Accept-Encoding': 'identity;q=1, *;q=0',
                        'Range': 'bytes=0-'
                    })
                
                # 发送请求
                response = requests.get(url, stream=True, timeout=30, verify=False, headers=download_headers)
                response.raise_for_status()
                
                file_path = self.download_dir / filename
                total_size = int(response.headers.get('content-length', 0))
                downloaded_size = 0
                
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=chunk_size):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            
                            # 显示下载进度
                            if total_size > 0:
                                progress = (downloaded_size / total_size) * 100
                                print(f"\r下载进度: {progress:.1f}%", end='', flush=True)
                
                print(f"\n下载完成: {file_path}")
                return True
                
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 403:
                    print(f"\n下载失败: 403 Forbidden - 服务器拒绝访问")
                    if attempt < max_retries - 1:
                        print(f"等待 2 秒后重试...")
                        time.sleep(2)
                        continue
                    else:
                        print(f"错误详情: {e}")
                        print(f"建议: 链接可能已过期或需要特殊的认证信息")
                        # 检查是否是链接过期问题
                        if 'deadline' in url or 'expires' in url:
                            print(f"检测到链接可能包含过期参数，建议重新解析视频获取最新链接")
                elif e.response.status_code == 404:
                    print(f"\n下载失败: 404 Not Found - 文件不存在或链接已失效")
                    return False
                elif e.response.status_code == 410:
                    print(f"\n下载失败: 410 Gone - 资源已被删除或链接已过期")
                    return False
                else:
                    print(f"\n下载失败: HTTP {e.response.status_code} - {e}")
                    if attempt < max_retries - 1:
                        print(f"等待 2 秒后重试...")
                        time.sleep(2)
                        continue
                    else:
                        return False
            except requests.exceptions.Timeout:
                print(f"\n下载失败: 请求超时")
                if attempt < max_retries - 1:
                    print(f"等待 2 秒后重试...")
                    time.sleep(2)
                    continue
                else:
                    return False
            except requests.exceptions.ConnectionError:
                print(f"\n下载失败: 连接错误，请检查网络连接")
                if attempt < max_retries - 1:
                    print(f"等待 2 秒后重试...")
                    time.sleep(2)
                    continue
                else:
                    return False
            except Exception as e:
                print(f"\n下载失败: {e}")
                if attempt < max_retries - 1:
                    print(f"等待 2 秒后重试...")
                    time.sleep(2)
                    continue
                else:
                    return False
        
        return False
    
    def download_video(self, url, token=None):
        """
        下载视频的主函数
        
        Args:
            url (str): 视频URL
            token (str, optional): 用户token
        """
        print("=" * 50)
        print("视频解析下载器")
        print("=" * 50)
        
        # 解析视频
        result = self.parse_video(url, token)
        if not result:
            return
        
        # 获取视频列表
        video_list = result.get('voideDeatilVoList', [])
        if not video_list:
            print("未找到可下载的视频")
            return
        
        # 获取视频标题
        video_title = result.get('title', '')
        if not video_title:
            # 尝试从第一个视频项中获取标题
            if video_list and len(video_list) > 0:
                video_title = video_list[0].get('title', '')
        
        print(f"找到 {len(video_list)} 个文件")
        if video_title:
            print(f"视频标题: {video_title}")
        
        # 下载文件
        for i, item in enumerate(video_list):
            file_url = item.get('url')
            file_type = item.get('type', 'video')
            
            if not file_url:
                continue
            
            # 生成文件名
            if file_type == 'image':
                extension = '.jpg'
            else:
                extension = '.mp4'
            
            # 使用视频标题命名文件（如果可用）
            if video_title and video_title.strip():
                # 清理标题中的非法字符
                safe_title = self._sanitize_filename(video_title)
                if len(video_list) == 1:
                    # 单个文件，直接使用标题
                    filename = f"{safe_title}{extension}"
                else:
                    # 多个文件，添加索引
                    filename = f"{safe_title}_{i+1}{extension}"
            else:
                # 从URL中提取文件名，如果没有则使用默认名称
                parsed_url = urlparse(file_url)
                original_filename = os.path.basename(parsed_url.path)
                
                if original_filename and '.' in original_filename:
                    filename = f"{i+1}_{original_filename}"
                else:
                    filename = f"{i+1}_file{extension}"
            
            # 特殊处理B站视频链接
            if 'bilivideo.com' in file_url or 'bilibili.com' in file_url:
                print(f"检测到B站视频链接，使用特殊下载策略...")
                # 尝试不同的下载策略
                success = self._download_bilibili_video(file_url, filename)
                if not success:
                    print(f"B站特殊下载策略失败，尝试普通下载...")
                    self.download_file(file_url, filename)
            else:
                # 普通下载
                self.download_file(file_url, filename)
            
            print("-" * 30)
    
    def download_video_once(self, url, token=None):
        """
        单次下载入口：解析并下载，返回是否至少成功下载一个文件。
        保留打印日志（不移除原有调试输出）。
        
        Args:
            url (str): 视频URL
            token (str, optional): 用户token
        
        Returns:
            bool: 是否成功下载至少一个文件
        """
        print("=" * 50)
        print("视频解析下载器")
        print("=" * 50)
        
        # 解析视频
        result = self.parse_video(url, token)
        if not result:
            return False
        
        # 获取视频列表
        video_list = result.get('voideDeatilVoList', [])
        if not video_list:
            print("未找到可下载的视频")
            return False
        
        # 获取视频标题
        video_title = result.get('title', '')
        if not video_title:
            # 尝试从第一个视频项中获取标题
            if video_list and len(video_list) > 0:
                video_title = video_list[0].get('title', '')
        
        print(f"找到 {len(video_list)} 个文件")
        if video_title:
            print(f"视频标题: {video_title}")
        
        success_count = 0
        # 下载文件
        for i, item in enumerate(video_list):
            file_url = item.get('url')
            file_type = item.get('type', 'video')
            
            if not file_url:
                continue
            
            # 生成文件名
            if file_type == 'image':
                extension = '.jpg'
            else:
                extension = '.mp4'
            
            # 使用视频标题命名文件（如果可用）
            if video_title and video_title.strip():
                # 清理标题中的非法字符
                safe_title = self._sanitize_filename(video_title)
                if len(video_list) == 1:
                    # 单个文件，直接使用标题
                    filename = f"{safe_title}{extension}"
                else:
                    # 多个文件，添加索引
                    filename = f"{safe_title}_{i+1}{extension}"
            else:
                # 从URL中提取文件名，如果没有则使用默认名称
                parsed_url = urlparse(file_url)
                original_filename = os.path.basename(parsed_url.path)
                
                if original_filename and '.' in original_filename:
                    filename = f"{i+1}_{original_filename}"
                else:
                    filename = f"{i+1}_file{extension}"
            
            # 特殊处理B站视频链接
            if 'bilivideo.com' in file_url or 'bilibili.com' in file_url:
                print(f"检测到B站视频链接，使用特殊下载策略...")
                # 尝试不同的下载策略
                success = self._download_bilibili_video(file_url, filename)
                if not success:
                    print(f"B站特殊下载策略失败，尝试普通下载...")
                    success = self.download_file(file_url, filename)
            else:
                # 普通下载
                success = self.download_file(file_url, filename)
            
            if success:
                success_count += 1
            
            print("-" * 30)
        
        return success_count > 0
    
    def _sanitize_filename(self, filename):
        """
        清理文件名，移除或替换非法字符
        
        Args:
            filename (str): 原始文件名
            
        Returns:
            str: 清理后的文件名
        """
        # 首先移除所有换行符、制表符等空白字符
        safe_name = re.sub(r'[\r\n\t\f\v]', '', filename)
        
        # Windows文件系统不允许的字符
        illegal_chars = r'[<>:"/\\|?*]'
        # 替换为下划线
        safe_name = re.sub(illegal_chars, '_', safe_name)
        
        # 移除首尾空格和点
        safe_name = safe_name.strip(' .')
        
        # 如果文件名为空或只有空格，使用默认名称
        if not safe_name or safe_name.isspace():
            safe_name = 'untitled'
        
        # 限制长度（Windows路径限制）
        if len(safe_name) > 200:
            safe_name = safe_name[:200]
        
        return safe_name
    
    def _download_bilibili_video(self, url, filename):
        """
        专门处理B站视频下载的方法
        
        Args:
            url (str): B站视频URL
            filename (str): 保存的文件名
            
        Returns:
            bool: 下载是否成功
        """
        try:
            print(f"正在使用B站专用下载器下载: {filename}")
            
            # B站专用的请求头
            bili_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.bilibili.com/',
                'Origin': 'https://www.bilibili.com',
                'Accept': '*/*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Accept-Encoding': 'identity;q=1, *;q=0',
                'Range': 'bytes=0-',
                'Sec-Fetch-Dest': 'video',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Site': 'cross-site',
                'Connection': 'keep-alive',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache',
                'DNT': '1',
                'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"'
            }
            
            # 尝试不同的下载策略
            strategies = [
                # 策略1: 直接下载
                lambda: requests.get(url, stream=True, timeout=30, verify=False, headers=bili_headers),
                # 策略2: 添加更多头部信息
                lambda: requests.get(url, stream=True, timeout=30, verify=False, headers={**bili_headers, 'X-Requested-With': 'XMLHttpRequest'}),
                # 策略3: 使用不同的User-Agent
                lambda: requests.get(url, stream=True, timeout=30, verify=False, headers={**bili_headers, 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'})
            ]
            
            for strategy_idx, strategy in enumerate(strategies, 1):
                try:
                    print(f"尝试B站下载策略 {strategy_idx}...")
                    response = strategy()
                    response.raise_for_status()
                    
                    file_path = self.download_dir / filename
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded_size = 0
                    
                    with open(file_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                downloaded_size += len(chunk)
                                
                                # 显示下载进度
                                if total_size > 0:
                                    progress = (downloaded_size / total_size) * 100
                                    print(f"\r下载进度: {progress:.1f}%", end='', flush=True)
                    
                    print(f"\nB站视频下载完成: {file_path}")
                    return True
                    
                except requests.exceptions.HTTPError as e:
                    if e.response.status_code == 403:
                        print(f"策略 {strategy_idx} 失败: 403 Forbidden")
                        if strategy_idx < len(strategies):
                            print("尝试下一个策略...")
                            continue
                        else:
                            print("所有B站下载策略都失败了")
                            return False
                    else:
                        print(f"策略 {strategy_idx} 失败: HTTP {e.response.status_code}")
                        if strategy_idx < len(strategies):
                            print("尝试下一个策略...")
                            continue
                        else:
                            return False
                except Exception as e:
                    print(f"策略 {strategy_idx} 失败: {e}")
                    if strategy_idx < len(strategies):
                        print("尝试下一个策略...")
                        continue
                    else:
                        return False
            
            return False
            
        except Exception as e:
            print(f"B站专用下载器失败: {e}")
            return False

def main():
    """
    主函数
    """
    parser = argparse.ArgumentParser(description="视频解析下载器")
    parser.add_argument('--url', help='要下载的视频链接')
    parser.add_argument('--dir', dest='download_dir', default='downloads', help='下载目录')
    parser.add_argument('--token', help='用户token，可选', default=None)
    args, unknown = parser.parse_known_args()
    
    # 如果提供了URL，执行单次下载并以退出码表示结果
    if args.url:
        downloader = VideoDownloader(args.download_dir)
        success = downloader.download_video_once(args.url, args.token)
        sys.exit(0 if success else 1)
    
    # 否则进入交互模式（保持原有行为）
    # 创建下载器实例
    downloader = VideoDownloader("downloads")
    
    while True:
        print("\n请输入视频链接（输入 'quit' 退出）：")
        user_input = input().strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("再见！")
            break
        
        if not user_input:
            continue
        
        # 可选：输入用户token（如果有的话）
        print("请输入用户token（可选，直接回车跳过）：")
        token = input().strip()
        if not token:
            token = None
        
        # 开始下载（沿用原方法）
        downloader.download_video(user_input, token)

if __name__ == "__main__":
    main()