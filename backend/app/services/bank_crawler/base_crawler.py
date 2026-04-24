"""银行爬虫基类"""
import hashlib
import logging
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)


def generate_job_id(url: str, title: str, company: str) -> str:
    """生成唯一的 job_id"""
    data = f"{url}_{title}_{company}".encode('utf-8')
    return hashlib.md5(data).hexdigest()


def clean_text(text: Any) -> str:
    """清理文本"""
    if not text:
        return ""
    return str(text).strip()


def parse_date_str(date_str: str) -> Optional[datetime]:
    """解析日期字符串"""
    if not date_str:
        return None

    date_str = clean_text(date_str)

    # 常见日期格式
    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y年%m月%d日",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


class BaseBankCrawler(ABC):
    """银行爬虫基类"""

    def __init__(self, bank_code: str, bank_name: str, config: Dict[str, Any]):
        """
        初始化爬虫

        Args:
            bank_code: 银行代码（如 "cmb", "spdb"）
            bank_name: 银行全名（如 "招商银行"）
            config: 配置字典
        """
        self.bank_code = bank_code
        self.bank_name = bank_name
        self.config = config
        self.base_url = config.get("base_url", "")
        self.session = requests.Session()

        # 设置默认请求头
        self.session.headers.update({
            "User-Agent": self._get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
        })

        # 延迟配置
        self.min_delay = config.get("min_delay", 1.0)
        self.max_delay = config.get("max_delay", 3.0)

    def _get_random_user_agent(self) -> str:
        """获取随机 User-Agent"""
        agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        ]
        return random.choice(agents)

    def _random_delay(self):
        """随机延迟"""
        delay = random.uniform(self.min_delay, self.max_delay)
        time.sleep(delay)

    def _get(self, url: str, **kwargs) -> Optional[requests.Response]:
        """发送 GET 请求"""
        for attempt in range(3):
            try:
                self._random_delay()
                resp = self.session.get(url, timeout=30, **kwargs)
                resp.raise_for_status()
                return resp
            except RequestException as e:
                logger.warning(f"[{self.bank_code}] GET {url} failed (attempt {attempt + 1}): {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"[{self.bank_code}] GET {url} failed after 3 attempts")
                    return None
        return None

    def _post(self, url: str, **kwargs) -> Optional[requests.Response]:
        """发送 POST 请求"""
        for attempt in range(3):
            try:
                self._random_delay()
                resp = self.session.post(url, timeout=30, **kwargs)
                resp.raise_for_status()
                return resp
            except RequestException as e:
                logger.warning(f"[{self.bank_code}] POST {url} failed (attempt {attempt + 1}): {e}")
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"[{self.bank_code}] POST {url} failed after 3 attempts")
                    return None
        return None

    def _parse_html(self, html: str) -> BeautifulSoup:
        """解析 HTML"""
        return BeautifulSoup(html, 'html.parser')

    def _extract_text(self, element, selector: str, default: str = "") -> str:
        """从元素中提取文本"""
        if not element:
            return default

        try:
            target = element.select_one(selector)
            if target:
                return clean_text(target.get_text())
        except Exception as e:
            logger.warning(f"[{self.bank_code}] Extract text failed: {e}")

        return default

    def _extract_attr(self, element, selector: str, attr: str, default: str = "") -> str:
        """从元素中提取属性"""
        if not element:
            return default

        try:
            target = element.select_one(selector)
            if target:
                return clean_text(target.get(attr, default))
        except Exception as e:
            logger.warning(f"[{self.bank_code}] Extract attr failed: {e}")

        return default

    def _build_job_dict(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """构建标准化的职位字典"""
        return {
            "job_id": job_data.get("job_id", ""),
            "source": f"bank-{self.bank_code}",
            "company": self.bank_name,
            "company_type_industry": "银行",
            "company_tags": "银行",
            "department": job_data.get("department", ""),
            "job_title": job_data.get("job_title", ""),
            "location": job_data.get("location", ""),
            "major_req": job_data.get("major_req", ""),
            "job_req": job_data.get("job_req", ""),
            "job_duty": job_data.get("job_duty", ""),
            "application_status": "待申请",
            "job_stage": job_data.get("job_stage", "campus"),  # campus/internship/social
            "source_config_id": self.bank_code,
            "publish_date": job_data.get("publish_date"),
            "deadline": job_data.get("deadline"),
            "detail_url": job_data.get("detail_url", ""),
            "scraped_at": datetime.now(timezone.utc),
        }

    @abstractmethod
    def fetch_jobs(self, stage: str = "campus") -> List[Dict[str, Any]]:
        """
        获取职位列表

        Args:
            stage: 职位阶段（campus/internship/social）

        Returns:
            职位列表，每个职位是一个字典
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """测试连接"""
        pass
