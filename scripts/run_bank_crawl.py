#!/usr/bin/env python3
"""
银行招聘岗位爬取脚本

统一入口脚本，用于启动银行爬虫

使用方法:
    python run_bank_crawl.py                    # 爬取所有银行
    python run_bank_crawl.py --bank cmb          # 只爬取招商银行
    python run_bank_crawl.py --stage internship  # 只爬取实习岗位
    python run_bank_crawl.py --list              # 列出所有银行
"""
import argparse
import logging
import sys
from pathlib import Path

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "JobRadar" / "backend"))

import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import DATABASE_URL
from app.models import Job, CrawlLog
from app.services.bank_crawler.crawler_manager import BankCrawlerManager
from app.services.bank_crawler.crawlers import (
    CMBCrawler, SPDBCrawler, ICBCrawler,
    CCBCrawler, NBCBCrawler, JSBCrawler,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(PROJECT_ROOT / 'data' / 'bank_crawler.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    """加载银行配置"""
    config_path = PROJECT_ROOT / "JobRadar" / "backend" / "app" / "services" / "bank_crawler" / "bank_sites.yaml"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return {}


def create_crawlers(config: dict) -> BankCrawlerManager:
    """创建爬虫管理器"""
    manager = BankCrawlerManager()
    banks_config = config.get("banks", {})

    # 映射银行代码到爬虫类
    crawler_classes = {
        "cmb": CMBCrawler,
        "spdb": SPDBCrawler,
        "icbc": ICBCrawler,
        "ccb": CCBCrawler,
        "nbc": NBCBCrawler,
        "jsbc": JSBCrawler,
    }

    for bank_code, bank_config in banks_config.items():
        if not bank_config.get("enabled", False):
            logger.info(f"Skipping disabled bank: {bank_code}")
            continue

        if bank_code not in crawler_classes:
            logger.warning(f"Crawler not implemented for bank: {bank_code}")
            continue

        try:
            crawler = crawler_classes[bank_code](bank_config)
            manager.register_crawler(bank_code, crawler)
        except Exception as e:
            logger.error(f"Failed to create crawler for {bank_code}: {e}")

    return manager


def list_banks(manager: BankCrawlerManager):
    """列出所有银行"""
    print("\n可用的银行爬虫:")
    print("-" * 60)
    for bank_code in manager.list_crawlers():
        crawler = manager.get_crawler(bank_code)
        print(f"  {bank_code:6s} - {crawler.bank_name}")
    print("-" * 60)
    print(f"共 {len(manager.list_crawlers())} 个银行")


def run_crawl(manager: BankCrawlerManager, db_session, args):
    """运行爬取"""
    logger.info("Starting bank crawl...")

    if args.bank:
        # 单个银行
        logger.info(f"Running crawler for bank: {args.bank}")
        result = manager.run_single_bank(db_session, args.bank, args.stage)

        print("\n" + "=" * 60)
        print("爬取结果摘要")
        print("=" * 60)
        print(f"银行: {args.bank}")
        print(f"职位阶段: {args.stage}")
        print(f"成功: {'是' if result['success'] else '否'}")
        print(f"新增职位: {result['new_count']}")
        print(f"总职位数: {result['total_count']}")
        if not result['success']:
            print(f"错误: {result.get('error', 'Unknown error')}")
        print("=" * 60)
    else:
        # 所有银行
        logger.info(f"Running all bank crawlers for stage: {args.stage}")
        crawl_log = manager.run_all_banks(db_session, args.stage)

        print("\n" + "=" * 60)
        print("爬取结果摘要")
        print("=" * 60)
        print(f"数据源: bank-crawler")
        print(f"职位阶段: {args.stage}")
        print(f"状态: {crawl_log.status}")
        print(f"新增职位: {crawl_log.new_count}")
        print(f"总职位数: {crawl_log.total_count}")
        print(f"开始时间: {crawl_log.started_at}")
        print(f"结束时间: {crawl_log.finished_at}")

        if crawl_log.error_message:
            print(f"\n详细信息:")
            print(crawl_log.error_message[:500])

        print("=" * 60)

    return True


def main():
    parser = argparse.ArgumentParser(description="银行招聘岗位爬取脚本")
    parser.add_argument("--bank", type=str, help="指定银行代码（如 cmb, spdb, icbc）")
    parser.add_argument("--stage", type=str, default="campus",
                        choices=["campus", "internship", "social"],
                        help="职位阶段（campus: 校园招聘, internship: 实习岗位, social: 社会招聘）")
    parser.add_argument("--list", action="store_true", help="列出所有可用的银行")
    args = parser.parse_args()

    # 加载配置
    config = load_config()
    if not config:
        logger.error("Failed to load config, exiting...")
        return 1

    # 创建数据库连接
    try:
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(bind=engine)
        db_session = SessionLocal()
    except Exception as e:
        logger.error(f"Failed to create database connection: {e}")
        return 1

    try:
        # 创建爬虫管理器
        manager = create_crawlers(config)

        # 列出银行
        if args.list:
            list_banks(manager)
            return 0

        # 运行爬取
        if not manager.list_crawlers():
            logger.error("No crawlers available, exiting...")
            return 1

        result = run_crawl(manager, db_session, args)
        return 0 if result else 1

    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1
    finally:
        db_session.close()


if __name__ == "__main__":
    sys.exit(main())
