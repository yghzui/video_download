#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频下载器GUI启动脚本
"""

import sys
import os

# 添加当前目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

try:
    from video_downloader_gui import main
    print("正在启动视频下载器GUI...")
    main()
except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保已安装所需的依赖包:")
    print("pip install -r requirements_gui.txt")
    input("按回车键退出...")
except Exception as e:
    print(f"启动失败: {e}")
    input("按回车键退出...") 