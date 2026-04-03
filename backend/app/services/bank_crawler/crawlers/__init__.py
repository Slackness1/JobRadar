"""具体银行爬虫实现"""
from .cmb_crawler import CMBCrawler
from .spdb_crawler import SPDBCrawler
from .icbc_crawler import ICBCrawler
from .ccb_crawler import CCBCrawler
from .nbc_crawler import NBCBCrawler
from .jsbc_crawler import JSBCrawler

__all__ = [
    'CMBCrawler',
    'SPDBCrawler',
    'ICBCrawler',
    'CCBCrawler',
    'NBCBCrawler',
    'JSBCrawler',
]
