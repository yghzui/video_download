#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
历史记录管理模块
负责管理下载历史记录的数据库操作
"""

import sqlite3
import os
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime

class HistoryManager:
    """历史记录管理器"""
    
    def __init__(self, db_path: str = "config/download_history.db"):
        """初始化历史记录管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_database()
    
    def _ensure_db_dir(self):
        """确保数据库目录存在"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
    
    def _init_database(self):
        """初始化数据库表结构"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 创建历史记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS download_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    title TEXT,
                    file_path TEXT,
                    file_name TEXT,
                    thumbnail_path TEXT,
                    download_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    file_size INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'success',
                    platform TEXT,
                    duration TEXT,
                    error_msg TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 检查并添加 error_msg 字段（为了兼容旧数据库）
            try:
                cursor.execute("ALTER TABLE download_history ADD COLUMN error_msg TEXT")
                print("已添加 error_msg 字段到数据库")
            except sqlite3.OperationalError:
                # 字段已存在，忽略错误
                pass
            
            # 创建索引以提高查询性能
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_download_time 
                ON download_history(download_time DESC)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_platform 
                ON download_history(platform)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_status 
                ON download_history(status)
            """)
            
            conn.commit()
            print("数据库初始化完成")
    
    def add_record(self, url: str, title: str = None, file_path: str = None, 
                   file_name: str = None, thumbnail_path: str = None, 
                   file_size: int = 0, status: str = 'success', 
                   platform: str = None, duration: str = None, 
                   force_create: bool = False) -> int:
        """添加下载记录
        
        Args:
            url: 下载链接
            title: 视频标题
            file_path: 文件完整路径
            file_name: 文件名
            thumbnail_path: 缩略图路径
            file_size: 文件大小（字节）
            status: 下载状态
            platform: 平台类型
            duration: 视频时长
            force_create: 是否强制创建新记录（忽略URL重复检查）
            
        Returns:
            int: 记录ID，如果URL已存在且force_create=False则返回现有记录ID
        """
        # 检查URL是否已存在（除非强制创建）
        if not force_create:
            existing_record = self.url_exists(url)
            if existing_record:
                print(f"URL已存在，返回现有记录ID: {existing_record['id']}")
                return existing_record['id']
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO download_history 
                (url, title, file_path, file_name, thumbnail_path, file_size, 
                 status, platform, duration, download_time, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                url, title, file_path, file_name, thumbnail_path, file_size,
                status, platform, duration, datetime.now(), datetime.now()
            ))
            
            record_id = cursor.lastrowid
            conn.commit()
            
            print(f"添加历史记录成功，ID: {record_id}")
            return record_id
    
    def get_records(self, limit: int = 100, offset: int = 0, 
                    search_keyword: str = None, platform: str = None,
                    sort_by: str = 'download_time', sort_order: str = 'DESC') -> List[Dict]:
        """获取历史记录列表
        
        Args:
            limit: 限制返回数量
            offset: 偏移量
            search_keyword: 搜索关键词（搜索标题和URL）
            platform: 平台筛选
            sort_by: 排序字段
            sort_order: 排序方向（ASC/DESC）
            
        Returns:
            List[Dict]: 历史记录列表
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row  # 使返回结果可以像字典一样访问
            cursor = conn.cursor()
            
            # 构建查询条件
            where_conditions = []
            params = []
            
            if search_keyword:
                where_conditions.append("(title LIKE ? OR url LIKE ?)")
                params.extend([f"%{search_keyword}%", f"%{search_keyword}%"])
            
            if platform:
                where_conditions.append("platform = ?")
                params.append(platform)
            
            where_clause = ""
            if where_conditions:
                where_clause = "WHERE " + " AND ".join(where_conditions)
            
            # 验证排序字段
            valid_sort_fields = ['download_time', 'file_size', 'title', 'platform']
            if sort_by not in valid_sort_fields:
                sort_by = 'download_time'
            
            if sort_order.upper() not in ['ASC', 'DESC']:
                sort_order = 'DESC'
            
            # 使用子查询去重，保留每个URL+文件路径组合的最新记录
            query = f"""
                SELECT * FROM download_history 
                WHERE id IN (
                    SELECT MAX(id) FROM download_history 
                    {where_clause}
                    GROUP BY url, COALESCE(file_path, '')
                )
                ORDER BY {sort_by} {sort_order}
                LIMIT ? OFFSET ?
            """
            
            params.extend([limit, offset])
            
            cursor.execute(query, params)
            records = [dict(row) for row in cursor.fetchall()]
            
            return records
    
    def get_record_by_id(self, record_id: int) -> Optional[Dict]:
        """根据ID获取单条记录
        
        Args:
            record_id: 记录ID
            
        Returns:
            Optional[Dict]: 记录信息，不存在则返回None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM download_history WHERE id = ?", (record_id,))
            row = cursor.fetchone()
            
            return dict(row) if row else None
    
    def update_record(self, record_id: int, **kwargs) -> bool:
        """更新记录
        
        Args:
            record_id: 记录ID
            **kwargs: 要更新的字段
            
        Returns:
            bool: 是否更新成功
        """
        if not kwargs:
            return False
        
        # 添加更新时间
        kwargs['updated_at'] = datetime.now()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 构建更新语句
            set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
            values = list(kwargs.values()) + [record_id]
            
            cursor.execute(f"""
                UPDATE download_history 
                SET {set_clause}
                WHERE id = ?
            """, values)
            
            success = cursor.rowcount > 0
            conn.commit()
            
            return success
    
    def delete_record(self, record_id: int) -> bool:
        """删除记录
        
        Args:
            record_id: 记录ID
            
        Returns:
            bool: 是否删除成功
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM download_history WHERE id = ?", (record_id,))
            
            success = cursor.rowcount > 0
            conn.commit()
            
            return success
    
    def delete_records_by_ids(self, record_ids: List[int]) -> int:
        """批量删除记录
        
        Args:
            record_ids: 记录ID列表
            
        Returns:
            int: 删除的记录数量
        """
        if not record_ids:
            return 0
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            placeholders = ",".join(["?"] * len(record_ids))
            cursor.execute(f"""
                DELETE FROM download_history 
                WHERE id IN ({placeholders})
            """, record_ids)
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            return deleted_count
    
    def clear_all_records(self) -> int:
        """清空所有记录
        
        Returns:
            int: 删除的记录数量
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM download_history")
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            return deleted_count
    
    def clear_all_records_and_reset_id(self) -> int:
        """清空所有记录并重置自增ID
        
        Returns:
            int: 删除的记录数量
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 获取删除前的记录数量
            cursor.execute("SELECT COUNT(*) FROM download_history")
            deleted_count = cursor.fetchone()[0]
            
            # 删除所有记录
            cursor.execute("DELETE FROM download_history")
            
            # 重置自增ID计数器
            cursor.execute("DELETE FROM sqlite_sequence WHERE name='download_history'")
            
            conn.commit()
            print(f"已清空所有记录({deleted_count}条)并重置ID计数器")
            
            return deleted_count
    
    def get_statistics(self) -> Dict:
        """获取统计信息（应用去重逻辑）
        
        Returns:
            Dict: 统计信息
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 使用去重逻辑获取统计信息
            # 总记录数（去重后）
            cursor.execute("""
                SELECT COUNT(*) FROM (
                    SELECT MAX(id) FROM download_history 
                    GROUP BY url, COALESCE(file_path, '')
                )
            """)
            total_count = cursor.fetchone()[0]
            
            # 成功下载数（去重后）
            cursor.execute("""
                SELECT COUNT(*) FROM download_history 
                WHERE id IN (
                    SELECT MAX(id) FROM download_history 
                    GROUP BY url, COALESCE(file_path, '')
                ) AND status = 'success'
            """)
            success_count = cursor.fetchone()[0]
            
            # 总文件大小（去重后）
            cursor.execute("""
                SELECT SUM(file_size) FROM download_history 
                WHERE id IN (
                    SELECT MAX(id) FROM download_history 
                    GROUP BY url, COALESCE(file_path, '')
                ) AND status = 'success'
            """)
            total_size = cursor.fetchone()[0] or 0
            
            # 各平台统计（去重后）
            cursor.execute("""
                SELECT platform, COUNT(*) as count 
                FROM download_history 
                WHERE id IN (
                    SELECT MAX(id) FROM download_history 
                    GROUP BY url, COALESCE(file_path, '')
                )
                GROUP BY platform 
                ORDER BY count DESC
            """)
            platform_stats = dict(cursor.fetchall())
            
            return {
                'total_count': total_count,
                'success_count': success_count,
                'failed_count': total_count - success_count,
                'total_size': total_size,
                'platform_stats': platform_stats
            }
    
    def file_exists(self, file_path: str) -> bool:
        """检查文件是否存在
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 文件是否存在
        """
        return os.path.exists(file_path) if file_path else False
    
    def url_exists(self, url: str) -> Optional[Dict]:
        """检查URL是否已存在于历史记录中
        
        Args:
            url: 要检查的URL
            
        Returns:
            Optional[Dict]: 如果存在返回记录信息，否则返回None
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, url, title, status, download_time, platform
                FROM download_history 
                WHERE url = ? 
                ORDER BY download_time DESC 
                LIMIT 1
            """, (url,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'url': row[1],
                    'title': row[2],
                    'status': row[3],
                    'download_time': row[4],
                    'platform': row[5]
                }
            return None
    
    def file_path_exists(self, file_path: str) -> Optional[Dict]:
        """检查文件路径是否已存在于历史记录中
        
        Args:
            file_path: 要检查的文件路径
            
        Returns:
            Optional[Dict]: 如果存在返回记录信息，否则返回None
        """
        if not file_path:
            return None
            
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, url, title, status, download_time, platform, file_path
                FROM download_history 
                WHERE file_path = ? 
                ORDER BY download_time DESC 
                LIMIT 1
            """, (file_path,))
            
            row = cursor.fetchone()
            if row:
                return {
                    'id': row[0],
                    'url': row[1],
                    'title': row[2],
                    'status': row[3],
                    'download_time': row[4],
                    'platform': row[5],
                    'file_path': row[6]
                }
            return None
    
    def check_duplicate_by_file_path(self, url: str, potential_file_path: str = None) -> Optional[Dict]:
        """基于文件路径检查重复下载
        
        Args:
            url: 视频URL
            potential_file_path: 潜在的文件路径（如果已知）
            
        Returns:
            Optional[Dict]: 如果存在重复返回记录信息，否则返回None
        """
        # 如果提供了潜在文件路径，直接检查
        if potential_file_path:
            return self.file_path_exists(potential_file_path)
        
        # 否则，查找该URL的所有成功下载记录，检查文件是否仍然存在
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, url, title, status, download_time, platform, file_path
                FROM download_history 
                WHERE url = ? AND status = 'success' AND file_path IS NOT NULL
                ORDER BY download_time DESC
            """, (url,))
            
            rows = cursor.fetchall()
            for row in rows:
                file_path = row[6]
                if file_path and os.path.exists(file_path):
                    return {
                        'id': row[0],
                        'url': row[1],
                        'title': row[2],
                        'status': row[3],
                        'download_time': row[4],
                        'platform': row[5],
                        'file_path': row[6]
                    }
            
            return None
    
    def get_platforms(self) -> List[str]:
        """获取所有平台列表
        
        Returns:
            List[str]: 平台列表
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT DISTINCT platform 
                FROM download_history 
                WHERE platform IS NOT NULL 
                ORDER BY platform
            """)
            
            platforms = [row[0] for row in cursor.fetchall()]
            return platforms

# 全局历史记录管理器实例
history_manager = HistoryManager()