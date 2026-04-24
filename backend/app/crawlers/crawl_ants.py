#!/usr/bin/env python3
"""
专门针对蚂蚁集团招聘网站的爬虫
"""

import requests
import json
import hashlib
from datetime import datetime
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Job

ANT_GROUP_URLS = [
    "https://talent.antgroup.com/campus",
    "https://talent.antgroup.com/campus-full-list?search=",
    "https://talent.antgroup.com/campus-position"
]

def crawl_ant_group(db: Session):
    """
    爬取蚂蚁集团岗位
    """
    jobs_added = 0

    try:
        print(f"[INFO] 开始爬取蚂蚁集团岗位...")

        # 尝试获取蚂蚁集团的岗位列表
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }

        # 尝试不同的URL
        for url in ANT_GROUP_URLS:
            print(f"[INFO] 尝试URL: {url}")

            try:
                response = requests.get(url, headers=headers, timeout=15)
                print(f"[INFO] 状态码: {response.status_code}")
                print(f"[INFO] 内容长度: {len(response.text)}")

                if response.status_code == 200:
                    # 尝试解析JSON响应
                    try:
                        data = response.json()
                        print(f"[INFO] JSON响应: {str(data)[:500]}")

                        # 处理JSON数据
                        if 'data' in data:
                            job_list = data['data']
                            print(f"[INFO] 找到 {len(job_list)} 个岗位")

                            for job_data in job_list[:50]:  # 限制50个
                                try:
                                    job_id = job_data.get('id', '')
                                    title = job_data.get('title', '')
                                    location = job_data.get('location', '')
                                    department = job_data.get('department', '')
                                    url = f"https://talent.antgroup.com/campus-position?positionId={job_id}"

                                    if not title:
                                        continue

                                    # 生成唯一ID
                                    unique_id = hashlib.md5(f"蚂蚁集团:{title}:{url}".encode()).hexdigest()[:12]

                                    # 检查是否已存在
                                    existing = db.query(Job).filter(Job.job_id == unique_id).first()
                                    if existing:
                                        continue

                                    # 创建新岗位
                                    job = Job(
                                        job_id=unique_id,
                                        source="antgroup",
                                        company="蚂蚁科技",
                                        company_type_industry="互联网",
                                        department=department,
                                        job_title=title,
                                        location=location,
                                        job_stage="campus",
                                        detail_url=url,
                                        scraped_at=datetime.utcnow()
                                    )

                                    db.add(job)
                                    db.commit()
                                    jobs_added += 1
                                    print(f"[INFO] 新增岗位: {title}")

                                except Exception as e:
                                    db.rollback()
                                    print(f"[WARN] 处理岗位时出错: {str(e)}")
                                    continue

                    except json.JSONDecodeError:
                        print(f"[INFO] 不是JSON响应，检查HTML内容...")

                        # 查找可能的API端点
                        import re
                        api_patterns = [
                            r'https://[^\s"\']*api[^\s"\']*',
                            r'/api/[^\s"\']*job[^\s"\']*'
                        ]

                        for pattern in api_patterns:
                            matches = re.findall(pattern, response.text, re.IGNORECASE)
                            if matches:
                                print(f"[INFO] 找到的API模式: {matches[:3]}")

                        break  # 如果能访问就不继续尝试其他URL

            except Exception as e:
                print(f"[WARN] 访问URL时出错: {str(e)}")
                continue

    except Exception as e:
        print(f"[ERROR] 爬取蚂蚁集团时出错: {str(e)}")

    return jobs_added


if __name__ == "__main__":
    db = SessionLocal()
    try:
        new_count = crawl_ant_group(db)
        print(f"\\n[INFO] 爬取完成，新增 {new_count} 个岗位")
    finally:
        db.close()
