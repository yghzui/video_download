# 视频解析下载器

这是一个基于Python的视频解析下载工具，支持多个主流视频平台的视频下载。

## 支持的平台

- **抖音** (douyin.com)
- **哔哩哔哩** (bilibili.com, b23.tv)
- **快手** (kuaishou.com)
- **小红书** (xiaohongshu.com, xhslink.com)
- **TikTok** (tiktok.com)
- **西瓜视频** (ixigua.com)
- **微视** (weishi.qq.com)
- **微博** (weibo.com)
- **YouTube** (youtube.com, youtu.be)
- **好看视频** (haokan.baidu.com)
- **Facebook** (facebook.com, fb.watch)
- **Twitter** (twitter.com, x.com)
- **Instagram** (instagram.com)
- **皮皮虾** (pipix.com)
- **京东** (jd.com)

## 安装依赖

```bash
pip install -r requirements.txt
```

## 使用方法

### 1. 基本使用

```bash
python video_downloader.py
```

### 2. 程序运行流程

1. 运行程序后，会提示输入视频链接
2. 可以输入包含中文的网址，程序会自动提取URL
3. 可选择输入用户token（可选）
4. 程序会自动识别平台并解析视频
5. 解析成功后会自动下载到 `downloads` 文件夹

### 3. 示例

```
请输入视频链接（输入 'quit' 退出）:
https://www.douyin.com/video/1234567890

请输入用户token（可选，直接回车跳过）:
[直接回车跳过]

识别平台: douyin
解析URL: https://www.douyin.com/video/1234567890
正在解析视频...
解析成功！
找到 1 个文件
正在下载: 1_file.mp4
下载进度: 100.0%
下载完成: downloads/1_file.mp4
```

## 功能特点

### 1. URL提取
- 支持从包含中文的文本中自动提取URL
- 使用正则表达式匹配HTTP/HTTPS链接

### 2. 平台识别
- 自动识别视频平台
- 支持多个平台的URL格式
- 特殊处理（如抖音搜索链接不支持）

### 3. 参数加密
- 使用SHA-256算法加密请求参数
- 与网站前端保持一致的加密方式

### 4. 文件下载
- 支持视频和图片下载
- 显示下载进度
- 自动生成文件名
- 分块下载，支持大文件

### 5. 错误处理
- 网络请求异常处理
- JSON解析错误处理
- 文件下载失败处理

## 代码结构

### VideoDownloader类

#### 主要方法：

- `extract_url(text)`: 从文本中提取URL
- `identify_platform(url)`: 识别视频平台
- `encrypt_params(url, platform)`: 加密请求参数
- `parse_video(url, token)`: 解析视频链接
- `download_file(url, filename)`: 下载单个文件
- `download_video(url, token)`: 主下载函数

#### 配置参数：

- `server_url`: 服务器地址
- `download_dir`: 下载目录
- `platform_rules`: 平台识别规则
- `headers`: 请求头
- `salt`: 加密盐值

## 注意事项

1. **网络连接**: 需要稳定的网络连接
2. **服务器限制**: 受服务器解析能力限制
3. **文件大小**: 大文件下载可能需要较长时间
4. **平台更新**: 各平台可能会更新反爬虫机制
5. **法律合规**: 请遵守相关法律法规，仅用于个人学习

## 错误处理

### 常见错误及解决方案：

1. **"解析失败：未找到有效的URL链接"**
   - 检查输入的链接格式是否正确
   - 确保链接包含 `http://` 或 `https://`

2. **"解析失败：不支持的视频平台"**
   - 检查是否在支持的平台列表中
   - 确认链接格式是否正确

3. **"网络请求错误"**
   - 检查网络连接
   - 确认服务器是否可访问

4. **"下载失败"**
   - 检查磁盘空间
   - 确认文件URL是否有效
   - 检查网络连接

## 扩展功能

可以根据需要扩展以下功能：

1. **批量下载**: 支持多个链接批量处理
2. **代理支持**: 添加代理服务器支持
3. **断点续传**: 支持下载中断后继续
4. **GUI界面**: 添加图形用户界面
5. **多线程下载**: 提高下载速度

## 许可证

本项目仅供学习和研究使用，请勿用于商业用途。 