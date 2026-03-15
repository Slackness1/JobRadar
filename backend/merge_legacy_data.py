#!/usr/bin/env python3
"""
将 job-crawler 项目的 jobs.csv 合并到 JobRadar 数据库
"""

import csv
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional

# 配置
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "jobradar.db"
LEGACY_DIR = BASE_DIR / "data" / "legacy"

LEGACY_CSVS = [
    LEGACY_DIR / "jobs_legacy_jobcrawler.csv",      # 13,526 条
    LEGACY_DIR / "jobs_jobcrawler_workspace.csv",    # 22,620 条
]


def generate_job_id(company: str, title: str, url: str) -> str:
    """生成 job_id（与 job-crawler 一致）"""
    text = f"{company}:{title}:{url}"
    return hashlib.md5(text.encode()).hexdigest()[:12]


def normalize_job_stage(job_type: str) -> str:
    """标准化 job_stage"""
    if not job_type:
        return "campus"
    job_type = job_type.lower()
    if 'campus' in job_type or '校招' in job_type or 'fresh' in job_type:
        return "campus"
    elif 'intern' in job_type or '实习' in job_type:
        return "internship"
    else:
        return "campus"  # 默认


def parse_datetime(date_str: Optional[str]) -> Optional[datetime]:
    """解析日期时间"""
    if not date_str:
        return None
    date_str = date_str.strip()

    # 尝试 ISO 格式
    for fmt in ['%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S']:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    # 尝试日期格式
    for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y年%m月%d日']:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


def load_existing_job_ids(conn: sqlite3.Connection) -> set:
    """加载已存在的 job_id"""
    cursor = conn.cursor()
    cursor.execute("SELECT job_id FROM jobs")
    return {row[0] for row in cursor.fetchall()}


def import_jobs_from_csv(csv_path: Path, source: str, existing_ids: set, conn: sqlite3.Connection) -> int:
    """从 CSV 导入岗位数据"""
    if not csv_path.exists():
        print(f"⚠️  文件不存在: {csv_path}")
        return 0

    print(f"\n📄 处理: {csv_path.name}")
    print(f"   来源: {source}")

    imported = 0
    skipped = 0
    errors = 0

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)

        for i, row in enumerate(reader, 1):
            try:
                # 跳过空行
                if not row.get('id'):
                    continue

                # 获取字段
                job_id = row.get('id', '')

                # 检查是否已存在
                if job_id in existing_ids:
                    skipped += 1
                    continue

                company = row.get('company', '')
                title = row.get('title', '')
                location = row.get('location', '')
                department = row.get('department', '')
                job_type = row.get('job_type', '')
                url = row.get('url', '')
                publish_date = parse_datetime(row.get('publish_date'))
                deadline = parse_datetime(row.get('deadline'))
                description = row.get('description', '')
                requirements = row.get('requirements', '')
                crawled_at = parse_datetime(row.get('crawled_at')) or datetime.utcnow()
                salary = row.get('salary', '')
                company_type_industry = row.get('company_type_industry', '')
                company_tags = row.get('company_tags', '')
                major_req = row.get('major_req', '')
                total_score = row.get('total_score', '')
                matched_tracks = row.get('matched_tracks', '')

                # 标准化 job_stage
                job_stage = normalize_job_stage(job_type)

                # 检查必需字段
                if not company or not title:
                    skipped += 1
                    continue

                # 插入数据库
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO jobs (
                        job_id, source, company, company_type_industry, company_tags,
                        department, job_title, location, major_req, job_req, job_duty,
                        application_status, job_stage, source_config_id,
                        publish_date, deadline, detail_url, scraped_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    job_id, source, company, company_type_industry, company_tags,
                    department, title, location, major_req, requirements, description,
                    '待申请', job_stage, '',
                    publish_date, deadline, url, crawled_at, crawled_at
                ))

                imported += 1
                existing_ids.add(job_id)
                cursor.close()

                # 每 1000 条提交一次
                if imported % 1000 == 0:
                    conn.commit()
                    print(f"   已导入: {imported}")

                if i % 5000 == 0:
                    print(f"   已处理: {i} 行")

            except Exception as e:
                errors += 1
                if errors <= 10:  # 只打印前 10 个错误
                    print(f"   ❌ 错误 (行 {i}): {e}")

    print(f"   ✅ 导入: {imported}, 跳过: {skipped}, 错误: {errors}")
    return imported


def main():
    print("=" * 60)
    print("JobRadar - Legacy Data Import")
    print("=" * 60)

    # 连接数据库
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        # 加载已存在的 job_id
        print("\n📊 加载现有数据...")
        existing_ids = load_existing_job_ids(conn)
        print(f"   现有岗位数: {len(existing_ids)}")

        # 导入数据
        total_imported = 0
        for csv_path in LEGACY_CSVS:
            source = csv_path.stem.replace('jobs_', 'job-crawler-')
            imported = import_jobs_from_csv(csv_path, source, existing_ids, conn)
            total_imported += imported

        # 提交所有更改
        conn.commit()

        # 统计结果
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM jobs")
        total_jobs = cursor.fetchone()[0]

        cursor.execute('''
            SELECT source, COUNT(*) as count
            FROM jobs
            GROUP BY source
            ORDER BY count DESC
        ''')
        by_source = cursor.fetchall()

        print("\n" + "=" * 60)
        print("📊 导入完成")
        print("=" * 60)
        print(f"✅ 新导入: {total_imported} 条")
        print(f"📈 总岗位数: {total_jobs} 条")
        print("\n按来源统计:")
        for source, count in by_source:
            print(f"   {source}: {count} 条")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ 导入失败: {e}")
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    main()
