# -*- coding: utf-8 -*-
"""
缩略图提取器
用于从视频文件中提取缩略图
"""

import os
import sys
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import tempfile


class ThumbnailExtractor:
    """视频缩略图提取器"""
    
    def __init__(self, thumbnail_dir="thumbnails"):
        """
        初始化缩略图提取器
        
        Args:
            thumbnail_dir (str): 缩略图保存目录
        """
        self.thumbnail_dir = Path(thumbnail_dir)
        self.thumbnail_dir.mkdir(exist_ok=True)
        
        # 支持的视频格式
        self.video_extensions = {
            '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', 
            '.webm', '.m4v', '.3gp', '.ts', '.m2ts'
        }
        
        # 检查ffmpeg是否可用
        self.ffmpeg_available = self._check_ffmpeg()
        
    def _check_ffmpeg(self):
        """检查ffmpeg是否可用"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'], 
                capture_output=True, 
                text=True, 
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            return False
            
    def extract_thumbnail(self, video_path, output_path=None, timestamp="00:00:05"):
        """
        从视频文件提取缩略图
        
        Args:
            video_path (str): 视频文件路径
            output_path (str): 输出缩略图路径，如果为None则自动生成
            timestamp (str): 提取时间点，格式为HH:MM:SS
            
        Returns:
            str: 缩略图文件路径，失败返回None
        """
        try:
            video_path = Path(video_path)
            
            # 检查视频文件是否存在
            if not video_path.exists():
                print(f"视频文件不存在: {video_path}")
                return None
                
            # 检查是否为支持的视频格式
            if video_path.suffix.lower() not in self.video_extensions:
                print(f"不支持的视频格式: {video_path.suffix}")
                return self._create_default_thumbnail(video_path.name, output_path)
                
            # 生成输出路径
            if output_path is None:
                output_path = self.thumbnail_dir / f"{video_path.stem}_thumb.jpg"
            else:
                output_path = Path(output_path)
                
            # 确保输出目录存在
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 使用ffmpeg提取缩略图
            if self.ffmpeg_available:
                return self._extract_with_ffmpeg(video_path, output_path, timestamp)
            else:
                print("ffmpeg不可用，创建默认缩略图")
                return self._create_default_thumbnail(video_path.name, output_path)
                
        except Exception as e:
            print(f"提取缩略图时出错: {e}")
            return self._create_default_thumbnail(video_path.name if 'video_path' in locals() else "unknown", output_path)
            
    def _extract_with_ffmpeg(self, video_path, output_path, timestamp):
        """
        使用ffmpeg提取缩略图
        
        Args:
            video_path (Path): 视频文件路径
            output_path (Path): 输出路径
            timestamp (str): 时间点
            
        Returns:
            str: 缩略图路径
        """
        try:
            # ffmpeg命令
            cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-ss', timestamp,
                '-vframes', '1',
                '-vf', 'scale=320:240:force_original_aspect_ratio=decrease,pad=320:240:(ow-iw)/2:(oh-ih)/2',
                '-y',  # 覆盖输出文件
                str(output_path)
            ]
            
            # 执行命令
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30  # 30秒超时
            )
            
            if result.returncode == 0 and output_path.exists():
                print(f"成功提取缩略图: {output_path}")
                return str(output_path)
            else:
                print(f"ffmpeg提取失败: {result.stderr}")
                return self._create_default_thumbnail(video_path.name, output_path)
                
        except subprocess.TimeoutExpired:
            print("ffmpeg提取超时")
            return self._create_default_thumbnail(video_path.name, output_path)
        except Exception as e:
            print(f"ffmpeg提取出错: {e}")
            return self._create_default_thumbnail(video_path.name, output_path)
            
    def _create_default_thumbnail(self, filename, output_path=None):
        """
        创建默认缩略图
        
        Args:
            filename (str): 文件名
            output_path (Path): 输出路径
            
        Returns:
            str: 缩略图路径
        """
        try:
            if output_path is None:
                output_path = self.thumbnail_dir / f"default_thumb.jpg"
            else:
                output_path = Path(output_path)
                
            # 确保输出目录存在
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 创建默认图片 (320x240)
            img = Image.new('RGB', (320, 240), color='#f8f9fa')
            draw = ImageDraw.Draw(img)
            
            # 绘制边框
            draw.rectangle([0, 0, 319, 239], outline='#dee2e6', width=2)
            
            # 绘制视频图标
            # 播放按钮三角形
            triangle_points = [(140, 100), (140, 140), (180, 120)]
            draw.polygon(triangle_points, fill='#6c757d')
            
            # 绘制文件名（如果有字体的话）
            try:
                # 尝试使用系统字体
                if sys.platform == 'win32':
                    font_path = 'C:/Windows/Fonts/msyh.ttc'  # 微软雅黑
                else:
                    font_path = None
                    
                if font_path and os.path.exists(font_path):
                    font = ImageFont.truetype(font_path, 12)
                else:
                    font = ImageFont.load_default()
                    
                # 截断文件名
                display_name = filename[:25] + '...' if len(filename) > 25 else filename
                
                # 计算文本位置
                bbox = draw.textbbox((0, 0), display_name, font=font)
                text_width = bbox[2] - bbox[0]
                text_x = (320 - text_width) // 2
                
                draw.text((text_x, 160), display_name, fill='#495057', font=font)
                
            except Exception:
                # 如果字体加载失败，使用默认字体
                display_name = filename[:20] + '...' if len(filename) > 20 else filename
                draw.text((80, 160), display_name, fill='#495057')
                
            # 保存图片
            img.save(output_path, 'JPEG', quality=85)
            print(f"创建默认缩略图: {output_path}")
            return str(output_path)
            
        except Exception as e:
            print(f"创建默认缩略图失败: {e}")
            return None
            
    def extract_multiple_thumbnails(self, video_files, progress_callback=None):
        """
        批量提取缩略图
        
        Args:
            video_files (list): 视频文件路径列表
            progress_callback (callable): 进度回调函数
            
        Returns:
            dict: {video_path: thumbnail_path} 映射
        """
        results = {}
        total = len(video_files)
        
        for i, video_file in enumerate(video_files):
            try:
                thumbnail_path = self.extract_thumbnail(video_file)
                results[video_file] = thumbnail_path
                
                if progress_callback:
                    progress_callback(i + 1, total, video_file)
                    
            except Exception as e:
                print(f"处理文件 {video_file} 时出错: {e}")
                results[video_file] = None
                
        return results
        
    def get_thumbnail_path(self, video_path):
        """
        获取视频对应的缩略图路径（不创建）
        
        Args:
            video_path (str): 视频文件路径
            
        Returns:
            str: 缩略图路径
        """
        video_path = Path(video_path)
        return str(self.thumbnail_dir / f"{video_path.stem}_thumb.jpg")
        
    def cleanup_orphaned_thumbnails(self, video_files):
        """
        清理孤立的缩略图文件
        
        Args:
            video_files (list): 当前存在的视频文件列表
        """
        try:
            # 获取所有缩略图文件
            thumbnail_files = list(self.thumbnail_dir.glob("*_thumb.jpg"))
            
            # 构建视频文件名集合
            video_stems = {Path(vf).stem for vf in video_files}
            
            # 删除孤立的缩略图
            for thumb_file in thumbnail_files:
                thumb_stem = thumb_file.stem.replace('_thumb', '')
                if thumb_stem not in video_stems:
                    try:
                        thumb_file.unlink()
                        print(f"删除孤立缩略图: {thumb_file}")
                    except Exception as e:
                        print(f"删除缩略图失败 {thumb_file}: {e}")
                        
        except Exception as e:
            print(f"清理缩略图时出错: {e}")


def main():
    """测试函数"""
    extractor = ThumbnailExtractor()
    
    # 测试提取缩略图
    test_video = "test_video.mp4"
    if os.path.exists(test_video):
        thumbnail = extractor.extract_thumbnail(test_video)
        print(f"缩略图路径: {thumbnail}")
    else:
        print("测试视频文件不存在")
        # 创建默认缩略图进行测试
        default_thumb = extractor._create_default_thumbnail("test_video.mp4")
        print(f"默认缩略图: {default_thumb}")


if __name__ == "__main__":
    main()