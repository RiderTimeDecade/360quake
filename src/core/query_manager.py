"""
Query manager for the Quake Query tool.
"""
import requests
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from ..config.settings import settings
from ..utils.logger import logger
import os
import json
import time

class QueryManager:
    def __init__(self, cookies: Optional[Dict[str, str]] = None):
        """Initialize query manager with authentication"""
        self.base_url = settings.get('api.base_url')
        self.headers = settings.get('api.headers').copy()
        self.cookies = cookies or {}
        self.device_info = settings.get('device_info')
        self.progress_callback = None
        
        # 创建不使用代理的session
        self.session = requests.Session()
        self.session.trust_env = False  # 禁用系统代理
        
    def build_query_data(self, query: str, size: int = None, start: int = 0) -> Dict[str, Any]:
        """Build query data with device information"""
        if size is None:
            size = settings.get('query.default_size')

        # 清理查询语句
        query = self._clean_query(query)
        logger.debug(f"Cleaned query: {query}")

        device_info = self.device_info.copy()
        device_info.update({
            "user_agent": self.headers["User-Agent"],
            "date": datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        })

        data = {
            "query": query,
            "size": min(size, 100),  # 每页最大100条
            "latest": True,
            "ignore_cache": False,
            "shortcuts": ["63734bfa9c27d4249ca7261c"],
            "start": start,
            "device": device_info
        }
        
        logger.debug(f"Built query data: {data}")
        return data

    def _clean_query(self, query: str) -> str:
        """Clean and format query string"""
        # 移除开头和结尾的引号
        query = query.strip().strip('"')
        
        # 如果查询以 "服务数据 |" 开头，移除它
        if query.startswith("服务数据 |"):
            query = query[len("服务数据 |"):].strip()
            
        # 移除末尾多余的括号
        while query.endswith(')') and query.count('(') < query.count(')'):
            query = query[:-1]
            
        # 规范化域名查询格式
        if query.startswith('domain:'):
            # 确保domain查询有正确的引号
            domain_part = query[7:].strip().strip('"')  # 移除domain:后的内容中的引号
            query = f'domain:"{domain_part}"'  # 重新添加正确的引号
        elif query.startswith('app:'):
            # 确保app查询有正确的引号
            app_part = query[4:].strip().strip('"')  # 移除app:后的内容中的引号
            query = f'app:"{app_part}"'  # 重新添加正确的引号
        
        logger.debug(f"Original query: {query}")
        return query.strip()

    def execute_paged_query(self, query: str, total_size: int) -> Dict[str, Any]:
        """Execute query with pagination support"""
        try:
            logger.info(f"Executing paged query: {query}, total size: {total_size}")
            all_results = []
            pages = (total_size + 99) // 100  # 向上取整
            
            for page in range(pages):
                # 检查是否取消
                if self.progress_callback and not self.progress_callback(page + 1, pages):
                    logger.info("Query cancelled by user")
                    break

                # 添加延迟，避免请求过快
                if page > 0:  # 第一页不延迟
                    time.sleep(0.1)  # 延迟100毫秒

                start = page * 100
                size = min(100, total_size - start)
                
                logger.info(f"Fetching page {page + 1}/{pages} (start: {start}, size: {size})")
                data = self.build_query_data(query, size, start)
                
                # 使用session发送请求而不是直接使用requests
                response = self.session.post(
                    self.base_url,
                    headers=self.headers,
                    json=data,
                    cookies=self.cookies
                )
                
                logger.debug(f"Response status code: {response.status_code}")
                response.raise_for_status()
                
                result = response.json()
                page_results = result.get('data', [])
                all_results.extend(page_results)
                
                logger.info(f"Retrieved {len(page_results)} results from page {page + 1}")
                
                if len(page_results) < size:
                    logger.warning(f"Received fewer results than requested ({len(page_results)} < {size})")
                    break
            
            # 构建最终结果
            final_result = {
                "code": 0,
                "data": all_results,
                "message": "Success",
                "timestamp": int(datetime.now().timestamp())
            }
            
            total = len(all_results)
            logger.info(f"Query completed. Total results: {total}")
            
            if total == 0:
                logger.warning("No results found for the query")
            
            return final_result

        except requests.exceptions.RequestException as e:
            logger.error(f"Query failed: {str(e)}")
            if hasattr(e.response, 'text'):
                logger.error(f"Error response: {e.response.text}")
            raise ValueError(f"查询失败: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            raise ValueError(f"未知错误: {str(e)}")

    def execute_query(self, query: str, size: int = None) -> Optional[Dict[str, Any]]:
        """Execute query and return results"""
        if size is None:
            size = settings.get('query.default_size')
        
        if size <= 100:
            # 对于小于等于100的查询使用单次请求
            try:
                logger.info(f"Executing single query: {query}")
                data = self.build_query_data(query, size)
                
                # 打印详细的请求信息
                logger.debug(f"Request URL: {self.base_url}")
                logger.debug(f"Request Headers: {json.dumps(self.headers, ensure_ascii=False, indent=2)}")
                logger.debug(f"Request Data: {json.dumps(data, ensure_ascii=False, indent=2)}")
                
                # 使用session发送请求而不是直接使用requests
                response = self.session.post(
                    self.base_url,
                    headers=self.headers,
                    json=data,
                    cookies=self.cookies
                )
                
                logger.debug(f"Response status code: {response.status_code}")
                logger.debug(f"Response headers: {dict(response.headers)}")
                logger.debug(f"Response content: {response.text[:1000]}...")  # 只打印前1000个字符
                
                response.raise_for_status()
                
                result = response.json()
                total = len(result.get('data', []))
                logger.info(f"Query successful. Found {total} results")
                
                if total == 0:
                    logger.warning("No results found for the query")
                
                return result

            except requests.exceptions.RequestException as e:
                logger.error(f"Query failed: {str(e)}")
                if hasattr(e.response, 'text'):
                    logger.error(f"Error response: {e.response.text}")
                raise ValueError(f"查询失败: {str(e)}")
            except Exception as e:
                logger.error(f"Unexpected error: {str(e)}")
                raise ValueError(f"未知错误: {str(e)}")
        else:
            # 对于大于100的查询使用分页
            return self.execute_paged_query(query, size)

    def validate_auth(self) -> bool:
        """Validate authentication credentials"""
        return bool(self.cookies)

    def update_auth(self, cookies: Optional[Dict[str, str]] = None):
        """Update authentication credentials"""
        if cookies:
            self.cookies = cookies