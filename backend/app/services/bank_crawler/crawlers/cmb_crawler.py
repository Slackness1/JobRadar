"""招商银行招聘爬虫"""
import logging
from typing import Dict, List

from app.services.bank_crawler.base_crawler import BaseBankCrawler, parse_date_str, generate_job_id

logger = logging.getLogger(__name__)


class CMBCrawler(BaseBankCrawler):
    """招商银行招聘爬虫

    官网: https://career.cmbchina.com/

    注意：招商银行可能需要处理 JavaScript 渲染，这里先尝试静态抓取
    """

    def __init__(self, config: Dict):
        super().__init__(
            bank_code="cmb",
            bank_name="招商银行",
            config=config
        )

    def test_connection(self) -> bool:
        """测试连接"""
        try:
            resp = self._get(self.base_url)
            return resp is not None and resp.status_code == 200
        except Exception as e:
            logger.error(f"[cmb] Connection test failed: {e}")
            return False

    def fetch_jobs(self, stage: str = "campus") -> List[Dict]:
        """
        获取招商银行职位列表

        招商银行的招聘页面可能需要特殊的抓取方式，这里提供一个基础框架

        Args:
            stage: 职位阶段

        Returns:
            职位列表
        """
        jobs = []

        try:
            # 尝试访问校园招聘页面
            if stage == "campus":
                url = f"{self.base_url}/campus"
            elif stage == "internship":
                url = f"{self.base_url}/intern"
            else:
                url = f"{self.base_url}/social"

            resp = self._get(url)
            if not resp:
                logger.error(f"[cmb] Failed to fetch {url}")
                return jobs

            # 解析页面
            soup = self._parse_html(resp.text)

            # 尝试查找职位列表元素
            # 这里需要根据实际页面结构调整选择器
            job_elements = soup.select(".job-list-item, .position-item, .job-item")

            if not job_elements:
                # 尝试其他选择器
                job_elements = soup.select("tr.job-item, div.job-card")

            for job_elem in job_elements:
                try:
                    # 提取职位信息
                    title = self._extract_text(job_elem, "h3, .job-title, .position-name")
                    detail_url = self._extract_attr(job_elem, "a", "href")
                    location = self._extract_text(job_elem, ".location, .city, .workplace")
                    publish_date_str = self._extract_text(job_elem, ".publish-date, .date, .time")
                    department = self._extract_text(job_elem, ".department, .dept")

                    if not title:
                        continue

                    # 补全 URL
                    if detail_url and not detail_url.startswith("http"):
                        detail_url = f"{self.base_url}{detail_url}"

                    # 生成 job_id
                    job_id = generate_job_id(detail_url, title, self.bank_name)

                    # 解析日期
                    publish_date = parse_date_str(publish_date_str)

                    job_data = {
                        "job_id": job_id,
                        "job_title": title,
                        "location": location,
                        "department": department,
                        "publish_date": publish_date,
                        "detail_url": detail_url,
                        "job_stage": stage,
                    }

                    jobs.append(self._build_job_dict(job_data))

                except Exception as e:
                    logger.warning(f"[cmb] Failed to parse job element: {e}")
                    continue

        except Exception as e:
            logger.exception(f"[cmb] Failed to fetch jobs: {e}")

        logger.info(f"[cmb] Fetched {len(jobs)} jobs for stage {stage}")
        return jobs
