#!/usr/bin/env python3
"""
Progress Reporter - 进度报告
每 30 分钟运行并发送报告
"""

import sys
import io
from pathlib import Path
from datetime import datetime
from contextlib import redirect_stdout

sys.path.insert(0, str(Path(__file__).parent))

from crawler import JobCrawler


def send_telegram_report(stats: dict, report: str):
    """发送 Telegram 报告"""
    import os
    
    # 从环境变量获取 Telegram 配置
    bot_token = os.environ.get('TELEGRAM_BOT_TOKEN')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID')
    
    if not bot_token or not chat_id:
        print("⚠️ Telegram 配置缺失，跳过发送")
        return False
    
    try:
        import requests
        
        # 构建消息（Telegram 限制 4096 字符）
        message = f"""🦀 **招聘爬虫报告**
    
⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

📈 **本次统计:**
• 爬取岗位: {stats['total_crawled']}
• 新增岗位: {stats['new_jobs']}
• 已存在: {stats['updated_jobs']}
• 失败站点: {stats['failed_sites']}

📁 数据文件: `data/jobs.csv`
"""
        
        if len(message) > 4000:
            message = message[:4000] + "\n... (截断)"
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'Markdown'
        }
        
        response = requests.post(url, data=data, timeout=10)
        
        if response.status_code == 200:
            print("✅ Telegram 报告已发送")
            return True
        else:
            print(f"❌ Telegram 发送失败: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Telegram 发送错误: {e}")
        return False


def run_with_report():
    """运行爬虫并发送报告"""
    print(f"\n{'='*60}")
    print(f"🦀 招聘爬虫启动")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    # 创建爬虫实例
    crawler = JobCrawler()
    
    # 爬取所有站点
    jobs = crawler.crawl_all()
    
    # 保存数据
    if jobs:
        crawler.save_to_csv(jobs)
        crawler.save_snapshot(jobs)
    
    # 获取统计
    stats = crawler.stats
    
    # 生成报告（复用 crawler 的打印报告）
    buf = io.StringIO()
    with redirect_stdout(buf):
        crawler.print_report()
    report = buf.getvalue()
    print(report)
    
    # 保存报告
    report_dir = Path(__file__).parent.parent / 'reports'
    report_dir.mkdir(parents=True, exist_ok=True)
    
    report_path = report_dir / f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"📄 报告已保存: {report_path}")
    
    # 发送 Telegram 报告
    send_telegram_report(stats, report)
    
    return stats


if __name__ == '__main__':
    run_with_report()
