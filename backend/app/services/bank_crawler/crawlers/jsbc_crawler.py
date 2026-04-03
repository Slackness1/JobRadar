"""江苏银行招聘爬虫"""
import logging
from typing import Dict, List

from app.services.bank_crawler.base_crawler import BaseBankCrawler, parse_date_str, generate_job_id

logger = logging.getLogger(__name__)


class JSBCrawler(BaseBankCrawler):
    """江苏银行招聘爬虫

    官网: https://job.jsbchina.cn/
    """

    def __init__(self, config: Dict):
        super().__init__(
            bank_code="jsbc",
            bank_name="江苏银行",
            config=config
        )

    def test_connection(self) -> bool:
        """测试连接"""
        try:
            resp = self._get(self.base_url)
            return resp is not None and resp.status_code == 200
        except Exception as e:
            logger.error(f"[jsbc] Connection test failed: {e}")
            return False

    def fetch_jobs(self, stage: str = "campus") -> List[Dict]:
        """
        获取江苏银行职位列表

        Args:
            stage: 职位阶段

        Returns:
            职位列表
        """
        jobs = []

        try:
            url = self.base_url
            resp = self._get(url)
            if not resp:
                logger.error(f"[jsbc] Failed to fetch {url}")
                return jobs

            soup = self._parse_html(resp.text)

            # 查找职位列表
            job_elements = soup.select(".job-list-item, .position-item, .job-item, tr")

            for job_elem in job_elements:
                try:
                    title = self._extract_text(job_elem, "h3, .job-title, .position-name, .title")
                    detail_url = self._extract_attr(job_elem, "a", "href")
                    location = self._extract_text(job_elem, ".location, .city, .workplace, .place")
                    publish_date_str = self._extract_text(job_elem, ".publish-date, .date, .time")
                    department = self._extract_text(job_elem, ".department, .dept")

                    if not title:
                        continue

                    if detail_url and not detail_url.startswith("http"):
                        detail_url = f"{self.base_url}{detail_url}"

                    job_id = generate_job_id(detail_url, title, self.bank_name)
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
                    logger.warning(f"[jsbc] Failed to parse job element: {e}")
                    continue

        except Exception as e:
            logger.exception(f"[jsbc] Failed to fetch jobs: {e}")

        logger.info(f"[jsbc] Fetched {len(jobs)} jobs for stage {stage}")
        return jobs
