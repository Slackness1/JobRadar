from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Job
from app.routers.jobs import list_jobs


def _new_db_session():
    engine = create_engine('sqlite:///:memory:', connect_args={'check_same_thread': False})
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def test_company_search_only_matches_company_name():
    db = _new_db_session()
    try:
        db.add_all([
            Job(
                job_id='job_1',
                source='tatawangshen',
                company='北京抖音信息服务有限公司',
                job_title='模型运营',
                job_req='内容策略分析',
                detail_url='https://example.com/1',
                publish_date=datetime(2026, 3, 1),
                job_stage='campus',
            ),
            Job(
                job_id='job_2',
                source='tatawangshen',
                company='字节跳动',
                job_title='AI产品实习生-抖音生活服务',
                job_req='抖音生态分析',
                detail_url='https://example.com/2',
                publish_date=datetime(2026, 3, 1),
                job_stage='campus',
            ),
        ])
        db.commit()

        result = list_jobs(page=1, page_size=20, company_search='抖音', job_stage='all', db=db)

        assert {item.company for item in result.items} == {'北京抖音信息服务有限公司', '字节跳动'}
    finally:
        db.close()


def test_job_title_search_only_matches_job_title():
    db = _new_db_session()
    try:
        db.add_all([
            Job(
                job_id='job_1',
                source='tatawangshen',
                company='广东茉莉数字科技集团股份有限公司',
                job_title='直播运营',
                job_req='负责抖音平台账号运营',
                detail_url='https://example.com/1',
                publish_date=datetime(2026, 3, 1),
                job_stage='campus',
            ),
            Job(
                job_id='job_2',
                source='tatawangshen',
                company='北京抖音信息服务有限公司',
                job_title='3D生成基座算法工程师-抖音直播',
                job_req='负责直播推荐优化',
                detail_url='https://example.com/2',
                publish_date=datetime(2026, 3, 1),
                job_stage='campus',
            ),
        ])
        db.commit()

        result = list_jobs(page=1, page_size=20, job_title_search='抖音', job_stage='all', db=db)

        assert [item.company for item in result.items] == ['北京抖音信息服务有限公司']
    finally:
        db.close()


def test_company_search_matches_truth_layer_aliases():
    db = _new_db_session()
    try:
        db.add_all([
            Job(
                job_id='job_1',
                source='tatawangshen',
                company='北京抖音信息服务有限公司',
                job_title='模型运营',
                job_req='内容策略分析',
                detail_url='https://example.com/1',
                publish_date=datetime(2026, 3, 1),
                job_stage='campus',
            ),
            Job(
                job_id='job_2',
                source='tatawangshen',
                company='字节跳动',
                job_title='产品经理',
                job_req='增长分析',
                detail_url='https://example.com/2',
                publish_date=datetime(2026, 3, 1),
                job_stage='campus',
            ),
        ])
        db.commit()

        result = list_jobs(page=1, page_size=20, company_search='字节', job_stage='all', db=db)

        assert {item.company for item in result.items} == {'北京抖音信息服务有限公司', '字节跳动'}
    finally:
        db.close()
