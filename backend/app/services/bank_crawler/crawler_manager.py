"""银行爬虫管理器"""
import logging
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.models import Job, CrawlLog
from app.services.bank_crawler.base_crawler import BaseBankCrawler

logger = logging.getLogger(__name__)


class BankCrawlerManager:
    """银行爬虫管理器"""

    def __init__(self):
        self.crawlers: Dict[str, BaseBankCrawler] = {}

    def register_crawler(self, bank_code: str, crawler: BaseBankCrawler):
        """注册爬虫"""
        self.crawlers[bank_code] = crawler
        logger.info(f"Registered crawler for bank: {bank_code}")

    def get_crawler(self, bank_code: str) -> Optional[BaseBankCrawler]:
        """获取爬虫"""
        return self.crawlers.get(bank_code)

    def list_crawlers(self) -> List[str]:
        """列出所有爬虫"""
        return list(self.crawlers.keys())

    def run_single_bank(self, db: Session, bank_code: str, stage: str = "campus") -> Dict[str, any]:
        """
        运行单个银行爬虫

        Args:
            db: 数据库会话
            bank_code: 银行代码
            stage: 职位阶段

        Returns:
            结果字典
        """
        crawler = self.get_crawler(bank_code)
        if not crawler:
            logger.error(f"Crawler not found for bank: {bank_code}")
            return {
                "success": False,
                "error": f"Crawler not found for bank: {bank_code}",
                "new_count": 0,
                "total_count": 0,
            }

        # 测试连接
        if not crawler.test_connection():
            logger.error(f"Connection test failed for bank: {bank_code}")
            return {
                "success": False,
                "error": f"Connection test failed for bank: {bank_code}",
                "new_count": 0,
                "total_count": 0,
            }

        # 获取职位列表
        try:
            jobs = crawler.fetch_jobs(stage)
        except Exception as e:
            logger.exception(f"Failed to fetch jobs from {bank_code}: {e}")
            return {
                "success": False,
                "error": str(e),
                "new_count": 0,
                "total_count": 0,
            }

        # 去重和保存
        new_count = 0
        total_count = len(jobs)

        # 加载现有 job_id
        existing_jobs = set()
        for job in db.query(Job).filter(Job.source == f"bank-{bank_code}").all():
            existing_jobs.add(job.job_id)

        for job_data in jobs:
            job_id = job_data.get("job_id", "")
            if not job_id:
                continue

            if job_id not in existing_jobs:
                try:
                    job = Job(**job_data)
                    db.add(job)
                    existing_jobs.add(job_id)
                    new_count += 1
                except Exception as e:
                    logger.error(f"Failed to save job {job_id}: {e}")

        return {
            "success": True,
            "new_count": new_count,
            "total_count": total_count,
        }

    def run_all_banks(self, db: Session, stage: str = "campus") -> CrawlLog:
        """
        运行所有银行爬虫

        Args:
            db: 数据库会话
            stage: 职位阶段

        Returns:
            CrawlLog 对象
        """
        log = CrawlLog(source="bank-crawler", status="running")
        db.add(log)
        db.commit()
        db.refresh(log)

        total_new = 0
        total_fetched = 0
        errors: List[str] = []
        success_banks: List[str] = []

        bank_codes = self.list_crawlers()
        logger.info(f"Starting crawl for {len(bank_codes)} banks")

        for bank_code in bank_codes:
            logger.info(f"Crawling bank: {bank_code}")
            result = self.run_single_bank(db, bank_code, stage)

            if result["success"]:
                total_new += result["new_count"]
                total_fetched += result["total_count"]
                success_banks.append(bank_code)
                logger.info(f"{bank_code}: new={result['new_count']}, total={result['total_count']}")
            else:
                error_msg = f"{bank_code}: {result.get('error', 'Unknown error')}"
                errors.append(error_msg)
                logger.error(error_msg)

        # 提交更改
        try:
            db.commit()
            log.status = "success"
            log.new_count = total_new
            log.total_count = total_fetched
        except Exception as e:
            db.rollback()
            log.status = "failed"
            log.error_message = str(e)[:500]
            logger.exception(f"Failed to commit database changes: {e}")

        # 记录详细信息
        notes = []
        notes.append(f"Success banks: {', '.join(success_banks)}")
        if errors:
            notes.append(f"Failed banks: {'; '.join(errors)}")
        log.error_message = "; ".join(notes)[:500]

        log.finished_at = log.finished_at or datetime.utcnow()

        try:
            db.commit()
            db.refresh(log)
        except Exception as e:
            logger.exception(f"Failed to update crawl log: {e}")

        logger.info(f"Crawl completed: new={total_new}, total={total_fetched}, success={len(success_banks)}/{len(bank_codes)}")
        return log
