#!/usr/bin/env python3
"""
能源公司招聘入口快速发现脚本
按照 ATS 家族探测常见入口，快速标记 entry_missing 或推荐 crawler 路径
"""
import re
import json
import requests
import time
from urllib.parse import urlparse, urljoin
from typing import Dict, List, Tuple, Optional
from pathlib import Path

# 代理配置
REQUEST_PROXIES = {
    'http': 'http://127.0.0.1:7890',
    'https': 'http://127.0.0.1:7890',
}

# 请求头
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 目标公司列表
ENERGY_TARGETS = [
    # 风电 / 综合新能源 / 电力装备
    {"name": "运达股份", "category": "风电整机"},
    {"name": "三一重能", "category": "风电整机"},
    {"name": "中国中车", "category": "电力装备"},
    {"name": "电气风电", "category": "风电整机"},
    {"name": "东方电气", "category": "电力装备"},
    {"name": "联合动力", "category": "风电整机"},
    {"name": "卧龙集团", "category": "电机电气"},

    # 光伏 / 逆变器 / 光储链条
    {"name": "隆基绿能", "category": "光伏组件"},
    {"name": "晶澳能源", "category": "光伏组件"},
    {"name": "TCL中环", "category": "光伏硅片"},
    {"name": "晶盛机电", "category": "光伏设备"},
    {"name": "爱旭太阳能", "category": "光伏电池"},
    {"name": "锦浪科技", "category": "光伏逆变器"},
    {"name": "爱士惟", "category": "光伏逆变器"},

    # 储能 / 电池 / 电力电子 / 能源数字化
    {"name": "派能科技", "category": "储能系统"},
    {"name": "瑞浦兰钧", "category": "动力电池"},
    {"name": "国轩高科", "category": "动力电池"},
    {"name": "融和元储", "category": "储能系统"},
    {"name": "采日能源", "category": "储能系统"},
    {"name": "美克生能源", "category": "储能系统"},
    {"name": "南都电源", "category": "储能电池"},
    {"name": "蜂巢能源", "category": "动力电池"},
    {"name": "孚能科技", "category": "动力电池"},
    {"name": "星恒电源", "category": "动力电池"},
    {"name": "远景动力", "category": "动力电池"},

    # 工控 / 电气自动化 / 电网相关
    {"name": "汇川", "category": "工控自动化"},
    {"name": "南瑞继保", "category": "电力自动化"},
    {"name": "先导智能", "category": "光伏设备"},

    # 车企 / 整车
    {"name": "蔚来", "category": "新能源汽车"},
    {"name": "理想", "category": "新能源汽车"},
    {"name": "赛力斯", "category": "新能源汽车"},
    {"name": "吉利", "category": "传统车企"},
    {"name": "比亚迪", "category": "新能源汽车"},
    {"name": "长安汽车", "category": "传统车企"},
    {"name": "零跑", "category": "新能源汽车"},
    {"name": "奇瑞", "category": "传统车企"},
    {"name": "北汽", "category": "传统车企"},
    {"name": "上汽", "category": "传统车企"},
]


def _safe_request(url: str, timeout: int = 10) -> Tuple[int, Optional[str], Optional[dict]]:
    """安全请求，返回 (status_code, final_url, headers)"""
    try:
        resp = requests.get(
            url,
            headers=DEFAULT_HEADERS,
            proxies=REQUEST_PROXIES,
            timeout=timeout,
            allow_redirects=True
        )
        return resp.status_code, resp.url, dict(resp.headers)
    except requests.exceptions.RequestException as e:
        return -1, None, {"error": str(e)}


def _detect_ats_family(url: str, html: str) -> Optional[str]:
    """从页面中检测 ATS 家族"""
    if not html:
        return None

    # Moka 指纹
    if "mokahr.com" in url or "app.mokahr.com" in html:
        return "moka"
    if re.search(r'<input[^>]*id=["\']init-data["\'][^>]*>', html):
        return "moka_embedded"
    if re.search(r'mokahr\.com/campus[-_]recruitment', html):
        return "moka"

    # zhiye 指纹
    if "zhiye.com" in url:
        return "zhiye"
    if re.search(r'/api/Jobad/GetJobAdPageList', html):
        return "zhiye"

    # 北森/51job campus 指纹
    if "51job.com" in url or "campus.51job.com" in html:
        return "51job_campus"

    # Hotjob 指纹
    if "hotjob.cn" in url or "hotjob" in html:
        return "hotjob"

    # Workday 指纹
    if "workday.com" in url or "workday" in html:
        return "workday"

    # Greenhouse 指纹
    if "greenhouse.io" in url or "greenhouse" in html:
        return "greenhouse"

    # Lever 指纹
    if "lever.co" in url or "lever" in html:
        return "lever"

    # 自建 SPA 指纹
    if re.search(r'__NEXT_DATA__|__NUXT__|React\.hydrate|Vue\.mount', html):
        return "custom_spa"

    return None


def discover_company(company: dict) -> dict:
    """发现单个公司的招聘入口"""
    name = company["name"]
    category = company["category"]

    print(f"\n{'='*60}")
    print(f"[Discovery] {name} ({category})")
    print(f"{'='*60}")

    result = {
        "name": name,
        "category": category,
        "candidates": [],
        "detected_family": None,
        "entry_url": None,
        "status": "entry_missing",  # 默认为缺失
        "failure_tags": [],
        "next_step": "人工确认入口",
    }

    # 常见域名的变体
    common_domains = [
        f"{name}.zhiye.com",
        f"{name}.zhaopin.com",
        f"www.{name}.com",
        f"{name}.com",
        f"{name}.cn",
        f"{name}-power.com",
        f"{name}-group.com",
        f"{name}energy.com",
        f"{name}tech.com",
        f"hr.{name}.com",
        f"jobs.{name}.com",
        f"career.{name}.com",
        f"careers.{name}.com",
    ]

    # 特殊映射
    special_mappings = {
        "运达股份": ["windey.zhiye.com", "windeyenergy.com"],
        "三一重能": ["sanyrenew.com", "sanygroup.com"],
        "电气风电": ["sec.shanghai-electric.com", "shanghai-electric.com"],
        "东方电气": ["dongfang.com", "dfem.com.cn"],
        "联合动力": ["guodianup.com", "chng.com.cn"],
        "卧龙集团": ["wulong.com", "wulongdrive.com"],
        "隆基绿能": ["longi.com", "longisolar.com"],
        "晶澳能源": ["jasolar.com", "jinkosolar.com"],  # 修正：晶科是 jinko，晶澳是 jaso
        "TCL中环": ["tclzhonghuan.com", "tjsemi.com"],
        "晶盛机电": ["jsjd.com", "jinghuatech.com"],
        "爱旭太阳能": ["aikosolar.com", "aikosolar.cn"],
        "锦浪科技": ["goodwe.com", "jinlang.com"],  # 修正：goodwe 是固德威
        "爱士惟": ["aishawei.com", "aishwei.com"],
        "派能科技": ["pylon-tech.com", "pylontech.com"],
        "瑞浦兰钧": ["reptbattery.com", "rise-solar.com"],
        "国轩高科": ["gotion.com", "gotion-inc.com"],
        "融和元储": ["rhenergy.com", "rhpower.com"],
        "采日能源": ["cairi-energy.com", "cairi.com"],
        "美克生能源": ["mksheng.com", "mksheng-energy.com"],
        "南都电源": ["narada.com", "naradabattery.com"],
        "蜂巢能源": ["svolt.com", "svoltbattery.com"],
        "孚能科技": ["farasis.com", "farasisenergy.com"],
        "星恒电源": ["xingheng.com", "starlak.com"],
        "远景动力": ["aesccorporation.com", "envision-group.com"],
        "汇川": ["inovance.com", "inovance.cn"],
        "南瑞继保": ["nari-relays.com", "nari.com"],
        "先导智能": ["leadintelligent.com", "leadint.com"],
        "蔚来": ["nio.com", "nio.cn"],
        "理想": ["lixiang.com", "li-auto.com"],
        "赛力斯": ["seres.com", "seresgroup.com"],
        "吉利": ["geely.com", "geelyauto.com"],
        "比亚迪": ["byd.com", "bydauto.com"],
        "长安汽车": ["changan.com", "changan.com.cn"],
        "零跑": ["leapmotor.com", "leapmotor.cn"],
        "奇瑞": ["chery.com", "chery.cn"],
        "北汽": ["baicgroup.com", "baicmotor.com"],
        "上汽": ["saicmotor.com", "saic.com"],
    }

    # 合并候选列表
    candidates = common_domains
    if name in special_mappings:
        candidates = special_mappings[name] + candidates

    # 添加 https 前缀
    candidates = [f"https://{domain}" for domain in candidates]

    # 快速探测
    for candidate in candidates[:15]:  # 限制探测数量
        domain = urlparse(candidate).netloc
        print(f"  探测: {candidate}")

        status, final_url, headers = _safe_request(candidate, timeout=5)

        if status == 200:
            print(f"    ✓ 可访问 (200): {final_url}")

            # 尝试获取 HTML 检测 ATS
            try:
                resp = requests.get(
                    final_url,
                    headers=DEFAULT_HEADERS,
                    proxies=REQUEST_PROXIES,
                    timeout=5
                )
                html = resp.text[:10000]  # 只读前 10KB 用于检测
                ats_family = _detect_ats_family(final_url, html)

                # 寻找招聘相关路径
                career_paths = ["/campus", "/jobs", "/careers", "/career", "/recruitment", "/joinus", "/zhao", "/zhaopin"]

                for path in career_paths:
                    career_url = urljoin(final_url, path)
                    c_status, c_final_url, _ = _safe_request(career_url, timeout=3)
                    if c_status == 200:
                        print(f"      ✓ 招聘入口: {c_final_url}")
                        c_resp = requests.get(
                            c_final_url,
                            headers=DEFAULT_HEADERS,
                            proxies=REQUEST_PROXIES,
                            timeout=5
                        )
                        c_html = c_resp.text[:10000]
                        c_ats = _detect_ats_family(c_final_url, c_html)

                        result["candidates"].append({
                            "url": c_final_url,
                            "ats_family": c_ats,
                            "status": 200,
                        })

                        # 如果找到明确招聘入口，优先使用
                        if c_ats:
                            result["detected_family"] = c_ats
                            result["entry_url"] = c_final_url
                            result["status"] = "discovered"
                            result["next_step"] = "提取岗位"
                            break

                if ats_family and not result["entry_url"]:
                    result["detected_family"] = ats_family
                    result["entry_url"] = final_url
                    result["status"] = "discovered"
                    result["next_step"] = "提取岗位"

            except Exception as e:
                print(f"    ✗ 检测失败: {e}")
                pass

        elif status in [403, 401]:
            print(f"    ✗ 访问拒绝 ({status}): {final_url}")
            result["failure_tags"].append("ACCESS_DENIED")

        elif status in [404]:
            print(f"    ✗ 不存在 (404)")
            # 404 是正常的探测结果，不加入失败标签

        elif status == -1:
            print(f"    ✗ 请求失败: {headers.get('error', 'unknown')}")
            result["failure_tags"].append("CONNECTION_ERROR")

        else:
            print(f"    ✗ HTTP {status}")

        # 如果已经发现明确的招聘入口，停止探测
        if result["entry_url"]:
            break

        # 短暂延迟避免过于频繁
        time.sleep(0.3)

    # 总结
    print(f"\n[结果总结]")
    print(f"  detected_family: {result['detected_family']}")
    print(f"  entry_url: {result['entry_url']}")
    print(f"  status: {result['status']}")
    print(f"  failure_tags: {result['failure_tags']}")
    print(f"  next_step: {result['next_step']}")

    return result


def main():
    """主函数"""
    print("="*60)
    print("能源公司招聘入口 Discovery")
    print("="*60)

    results = []

    for company in ENERGY_TARGETS:
        try:
            result = discover_company(company)
            results.append(result)
        except Exception as e:
            print(f"\n[ERROR] {company['name']} Discovery 失败: {e}")
            results.append({
                "name": company["name"],
                "category": company["category"],
                "status": "failed",
                "error": str(e),
            })

    # 保存结果
    output_file = Path("/home/ubuntu/.openclaw/workspace-projecta/data/energy_discovery_2026-03-24.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"Discovery 完成，结果保存到: {output_file}")
    print(f"{'='*60}")

    # 统计
    total = len(results)
    discovered = sum(1 for r in results if r['status'] == 'discovered')
    entry_missing = sum(1 for r in results if r['status'] == 'entry_missing')
    failed = sum(1 for r in results if r['status'] == 'failed')

    print(f"\n统计:")
    print(f"  总计: {total}")
    print(f"  已发现入口: {discovered}")
    print(f"  入口缺失: {entry_missing}")
    print(f"  失败: {failed}")


if __name__ == "__main__":
    main()
