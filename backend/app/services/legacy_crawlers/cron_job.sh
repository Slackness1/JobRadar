#!/bin/bash
# 定时爬虫脚本

cd ~/workspace/job-crawler
python3 scripts/crawler.py >> logs/crawler.log 2>&1

# 发送 Telegram 报告
python3 scripts/reporter.py >> logs/reporter.log 2>&1
