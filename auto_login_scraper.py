#!/usr/bin/env python3
"""
auto_login_scraper.py - 自动登录并爬取 tatawangshen.com 岗位数据

使用方法:
1. 安装依赖: pip install playwright && playwright install chromium
2. 设置环境变量:
   - Windows PowerShell: $env:TATA_USERNAME='你的账号'; $env:TATA_PASSWORD='你的密码'
   - Linux/Mac: export TATA_USERNAME='你的账号'; export TATA_PASSWORD='你的密码'
3. 运行: python auto_login_scraper.py
"""
import asyncio
import csv
import hashlib
import json
import os
import random
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

# Playwright 可选依赖
try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    async_playwright = None
    Browser = Any
    Page = Any
    PLAYWRIGHT_AVAILABLE = False

import requests
from requests.exceptions import RequestException

# ============ 配置 ============
LOGIN_URL = "https://www.tatawangshen.com/login"
API_URL = "https://www.tatawangshen.com/api/recruit/position/exclusive"
DEFAULT_CONFIG_ID = "687d079c70ccc5e36315f4ba"  # 可通过环境变量覆盖
OUTPUT_DIR = "D:/金融知识/爬虫"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "jobs.csv")

DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://www.tatawangshen.com",
    "Referer": "https://www.tatawangshen.com/manage?tab=vip",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

OUTPUT_FIELDS = [
    "job_id", "company", "company_type_industry", "company_tags",
    "department", "job_title", "location", "major_req",
    "job_req", "job_duty", "referral_code", "publish_date",
    "deadline", "detail_url", "apply_url", "scraped_at",
    "job_stage", "source_config_id",
]


# ============ Token 获取 ============

def get_credentials(args=None) -> tuple:
    """从环境变量或命令行参数获取账号密码"""
    if args and args.username:
        return args.username, args.password
    username = os.environ.get("TATA_USERNAME", "")
    password = os.environ.get("TATA_PASSWORD", "")
    return username, password


async def get_token_via_browser(headless: bool = False, args=None) -> Optional[str]:
    """通过浏览器自动登录获取 token"""
    if not PLAYWRIGHT_AVAILABLE or async_playwright is None:
        print("[ERROR] Playwright 未安装，请运行: pip install playwright && playwright install chromium")
        return None
    
    username, password = get_credentials(args)
    if not username or not password:
        print("[ERROR] 请设置环境变量 TATA_USERNAME 和 TATA_PASSWORD")
        return None
    
    print(f"[INFO] 使用账号: {username[:3]}*** 登录...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context()
        page = await context.new_page()
        
        try:
            # 1. 打开登录页
            print("[INFO] 打开登录页面...")
            await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
            
            # 2. 等待网络空闲
            print("[INFO] 等待页面完全加载...")
            try:
                await page.wait_for_load_state("networkidle", timeout=30000)
            except:
                print("[WARN] networkidle 超时，继续尝试...")
            
            # 3. 额外等待确保动态内容加载完成
            await page.wait_for_timeout(3000)
            
            # 常见的登录框选择器
            # 常见的登录框选择器
            username_selectors = [
                'input[placeholder*="账号"]',
                'input[placeholder*="用户名"]',
                'input[placeholder*="手机"]',
                'input[placeholder*="邮箱"]',
                'input[type="text"]',
                'input[name="username"]',
                'input[name="account"]',
                'input[name="phone"]',
                '#username',
                '#account',
            ]
            
            password_selectors = [
                'input[placeholder*="密码"]',
                'input[type="password"]',
                'input[name="password"]',
                '#password',
            ]
            
            login_btn_selectors = [
                # Ant Design 按钮选择器（最常见）
                'button.ant-btn-primary',
                '.ant-btn-primary',
                'button.ant-btn.ant-btn-primary',
                # 通用按钮选择器
                'button:has-text("登录")',
                'button:has-text("登 录")',
                'button:has-text("登  录")',
                'button:has-text("Login")',
                'button:has-text("login")',
                'button[type="submit"]',
                'input[type="submit"]',
                'input[value*="登录"]',
                'input[value*="登 录"]',
                '.login-btn',
                '#login-btn',
                '.ant-btn-primary',
                'button.ant-btn-primary',
                '.btn-login',
                'button.btn-primary',
                'a:has-text("登录")',
                'div[role="button"]:has-text("登录")',
                'span[role="button"]:has-text("登录")',
                '.el-button:has-text("登录")',
                '.submit-btn',
                '.form-submit',
                'button.ant-btn',
                'a.ant-btn',
                '.ivu-btn-primary',
                'button.ivu-btn-primary',
            ]
            
            # 查找用户名输入框
            username_input = None
            for selector in username_selectors:
                try:
                    username_input = await page.wait_for_selector(selector, timeout=2000)
                    if username_input:
                        print(f"[INFO] 找到用户名输入框: {selector}")
                        break
                except:
                    continue
            
            if not username_input:
                print("[ERROR] 未找到用户名输入框，请检查页面结构")
                await page.screenshot(path=os.path.join(OUTPUT_DIR, "login_page.png"))
                print("[INFO] 已保存页面截图: login_page.png")
                return None
            
            # 查找密码输入框
            password_input = None
            for selector in password_selectors:
                try:
                    password_input = await page.wait_for_selector(selector, timeout=2000)
                    if password_input:
                        print(f"[INFO] 找到密码输入框: {selector}")
                        break
                except:
                    continue
            
            if not password_input:
                print("[ERROR] 未找到密码输入框")
                return None
            
            # 4. 点击同意协议
            print("[INFO] 查找并点击同意协议...")
            agreement_selectors = [
                'input[type="checkbox"]',
                '.ant-checkbox-input',
                '.el-checkbox__input',
                'input[name="agreement"]',
                'input[name="agree"]',
                '.checkbox input',
                '[role="checkbox"]',
            ]
            
            for selector in agreement_selectors:
                try:
                    checkbox = await page.wait_for_selector(selector, timeout=1000)
                    if checkbox:
                        # Check if already checked
                        is_checked = await checkbox.is_checked()
                        if not is_checked:
                            await checkbox.click()
                            print(f"[INFO] 已勾选同意协议: {selector}")
                        else:
                            print(f"[INFO] 同意协议已勾选")
                        break
                except:
                    continue
            
            await page.wait_for_timeout(500)
            
            # 5. 填写账号密码
            print("[INFO] 填写账号密码...")
            await username_input.fill(username)
            await password_input.fill(password)
            
            await page.wait_for_timeout(500)
            
            # Take screenshot for debugging
            await page.screenshot(path=os.path.join(OUTPUT_DIR, "after_fill.png"))
            print("[DEBUG] 已保存截图: after_fill.png")
            
            # 6. 点击登录按钮 - 使用 Playwright Locator API
            print("[INFO] 查找登录按钮...")
            login_btn = None
            login_frame = None  # 记录按钮在哪个 frame
            # 方法 1: 使用 Playwright 的 get_by_role (最可靠)
            try:
                login_btn = page.get_by_role("button", name="登录")
                if await login_btn.count() > 0:
                    print("[INFO] 找到登录按钮: get_by_role")
                else:
                    login_btn = None
            except Exception as e:
                print(f"[DEBUG] get_by_role 失败: {e}")
                login_btn = None
            
            # 方法 1.5: 直接用 text 定位（适用于 div 做按钮的情况）
            if not login_btn:
                try:
                    # 这个网站的登录按钮是 div 不是 button
                    # 需要找到 class 包含 bg-[#165DFF] 和 cursor-pointer 的 div，文本精确为 "登录"
                    login_btn = page.locator("div[class*='bg-'][class*='rounded-'][class*='cursor-pointer']").filter(has_text="登录").first
                    if await login_btn.count() > 0:
                        text = await login_btn.inner_text()
                        if text.strip() == "登录":
                            print("[INFO] 找到登录按钮: div with bg/rounded/cursor-pointer")
                        else:
                            login_btn = None
                    else:
                        login_btn = None
                except Exception as e:
                    print(f"[DEBUG] div 选择器失败: {e}")
                    login_btn = None
            
            # 方法 2: 使用 locator + text
            if not login_btn:
                try:
                    login_btn = page.locator("button:has-text('登录')")
                    if await login_btn.count() > 0:
                        print("[INFO] 找到登录按钮: locator button:has-text")
                    else:
                        login_btn = None
                except Exception as e:
                    print(f"[DEBUG] locator 失败: {e}")
                    login_btn = None
            
            # 方法 3: 使用 Ant Design 选择器
            if not login_btn:
                try:
                    login_btn = page.locator(".ant-btn-primary")
                    if await login_btn.count() > 0:
                        print("[INFO] 找到登录按钮: .ant-btn-primary")
                    else:
                        login_btn = None
                except Exception as e:
                    print(f"[DEBUG] .ant-btn-primary 失败: {e}")
                    login_btn = None
            
            # 方法 4: 查找所有按钮并选择包含 "登录" 文字的
            if not login_btn:
                try:
                    all_buttons = page.locator("button")
                    count = await all_buttons.count()
                    print(f"[DEBUG] 找到 {count} 个 button 元素")
                    for i in range(count):
                        btn = all_buttons.nth(i)
                        text = await btn.inner_text()
                        print(f"[DEBUG] 按钮 {i+1}: '{text[:30]}'")
                        if "登录" in text:
                            login_btn = btn
                            print(f"[INFO] 找到登录按钮: button[{i}] with text '{text}'")
                            break
                except Exception as e:
                    print(f"[DEBUG] 遍历按钮失败: {e}")
            
            # 方法 5: 查找所有可点击元素
            if not login_btn:
                try:
                    all_clickable = page.locator("button, [role='button'], input[type='submit'], .ant-btn, .btn")
                    count = await all_clickable.count()
                    print(f"[DEBUG] 找到 {count} 个可点击元素")
                    for i in range(min(count, 20)):  # 限制最多20个
                        el = all_clickable.nth(i)
                        try:
                            text = await el.inner_text()
                            if "登录" in text or "Login" in text.lower():
                                login_btn = el
                                print(f"[INFO] 找到登录按钮: 可点击元素[{i}] '{text[:20]}'")
                                break
                        except:
                            pass
                except Exception as e:
                    print(f"[DEBUG] 遍历可点击元素失败: {e}")
            
            # 方法 5.5: 直接查找包含 "登录" 文字的 div 元素（这个网站的登录按钮是 div）
            if not login_btn:
                try:
                    divs_with_login = page.locator("div")
                    count = await divs_with_login.count()
                    print(f"[DEBUG] 找到 {count} 个 div 元素，查找包含 '登录' 的可点击 div...")
                    for i in range(min(count, 200)):  # 限制最多200个
                        div = divs_with_login.nth(i)
                        try:
                            text = await div.inner_text()
                            if text.strip() == "登录":  # 精确匹配
                                # 检查是否有 cursor-pointer 样式
                                class_name = await div.get_attribute("class") or ""
                                if "cursor-pointer" in class_name or "bg-" in class_name:
                                    login_btn = div
                                    print(f"[INFO] 找到登录按钮: div[{i}] class='{class_name[:50]}'")
                                    break
                        except:
                            pass
                except Exception as e:
                    print(f"[DEBUG] 遍历 div 失败: {e}")
            # 方法 6: 在所有 frame 中查找登录按钮
            if not login_btn:
                print("[DEBUG] 在所有 frame 中查找登录按钮...")
                for i, frame in enumerate(page.frames):
                    try:
                        frame_btn = frame.get_by_role("button", name="登录")
                        if await frame_btn.count() > 0:
                            login_btn = frame_btn.first
                            login_frame = frame
                            print(f"[INFO] 在 frame {i} 中找到登录按钮: get_by_role")
                            break
                    except:
                        pass
                    
                    # 也尝试其他选择器
                    if not login_btn:
                        try:
                            frame_btns = frame.locator("button")
                            count = await frame_btns.count()
                            if count > 0:
                                print(f"[DEBUG] Frame {i} 有 {count} 个 button")
                                for j in range(count):
                                    btn = frame_btns.nth(j)
                                    text = await btn.inner_text()
                                    if "登录" in text:
                                        login_btn = btn
                                        login_frame = frame
                                        print(f"[INFO] 在 frame {i} 中找到登录按钮: '{text}'")
                                        break
                                if login_btn:
                                    break
                        except Exception as e:
                            print(f"[DEBUG] Frame {i} 查找失败: {e}")
            if not login_btn:
                # Fallback: try multiple approaches
                print("[WARN] 未找到标准登录按钮，尝试其他方式...")
                
                # Method 1: Use JavaScript to find and click login button
                try:
                    print("[INFO] 尝试用 JavaScript 查找登录按钮...")
                    clicked = await page.evaluate("""
                        () => {
                            // Try to find login-related elements
                            const keywords = ['登录', '登 录', 'login', 'Login', 'LOGIN', '提交', '确定'];
                            const elements = document.querySelectorAll('button, input[type="submit"], [role="button"], a.btn, div.btn, span.btn, .ant-btn, .ivu-btn, .el-button');
                            for (let el of elements) {
                                const text = el.innerText || el.value || '';
                                for (let kw of keywords) {
                                    if (text.includes(kw)) {
                                        el.click();
                                        return text;
                                    }
                                }
                            }
                            return null;
                        }
                    """)
                    if clicked:
                        print(f"[SUCCESS] JavaScript 点击了: '{clicked}'")
                        await page.wait_for_timeout(3000)
                        
                        # Check if login succeeded
                        token = await page.evaluate("""() => {
                            return localStorage.getItem('token');
                        }""")
                        if token:
                            print(f"[SUCCESS] 登录成功")
                            return token
                except Exception as e:
                    print(f"[DEBUG] JavaScript 方法失败: {e}")
                
                # Method 2: Try pressing Enter
                try:
                    print("[INFO] 尝试按 Enter 键提交...")
                    await page.keyboard.press('Enter')
                    await page.wait_for_timeout(3000)
                    
                    # Check if login succeeded
                    token = await page.evaluate("""() => {
                        return localStorage.getItem('token');
                    }""")
                    if token:
                        print(f"[SUCCESS] 按 Enter 登录成功")
                        return token
                except Exception as e:
                    print(f"[DEBUG] Enter 键方法失败: {e}")
                
                # Method 3: Find any button and click the last one (usually login is at bottom)
                try:
                    buttons = await page.query_selector_all('button, input[type="submit"], [role="button"], .ant-btn, .ivu-btn')
                    if buttons:
                        print(f"[INFO] 找到 {len(buttons)} 个按钮元素")
                        for i, btn in enumerate(buttons):
                            try:
                                text = await btn.inner_text()
                                print(f"  {i+1}. '{text[:40] if text else '(empty)'}")
                            except:
                                pass
                        
                        # Try clicking each button that might be login
                        for btn in reversed(buttons):
                            try:
                                text = await btn.inner_text()
                                if text and ('登录' in text or 'Login' in text.lower() or 'login' in text.lower()):
                                    print(f"[INFO] 点击按钮: '{text}'")
                                    await btn.click()
                                    await page.wait_for_timeout(2000)
                                    
                                    token = await page.evaluate("""() => {
                                        return localStorage.getItem('token');
                                    }""")
                                    if token:
                                        print(f"[SUCCESS] 登录成功")
                                        return token
                            except:
                                pass
                        
                        # If still no luck, try the last button
                        login_btn = buttons[-1]
                        print(f"[INFO] 尝试最后一个按钮")
                    else:
                        await page.screenshot(path=os.path.join(OUTPUT_DIR, "login_page.png"))
                        print("[ERROR] 未找到任何按钮，已保存截图: login_page.png")
                        return None
                except Exception as e:
                    print(f"[ERROR] 查找按钮失败: {e}")
                    return None
            
            print("[INFO] 点击登录...")
            await login_btn.click()
            
            # 7. 等待登录完成
            print("[INFO] 等待登录完成...")
            await page.wait_for_timeout(3000)
            
            # 等待跳转或 token 出现
            try:
                await page.wait_for_url("**/manage**", timeout=10000)
            except:
                pass
            
            # 8. 从 localStorage 获取 token
            print("[INFO] 获取 token...")
            token = await page.evaluate("""() => {
                return localStorage.getItem('token');
            }""")
            
            if token:
                print(f"[SUCCESS] 获取 token 成功: {token[:20]}...")
            else:
                print("[ERROR] 未获取到 token，登录可能失败")
                await page.screenshot(path=os.path.join(OUTPUT_DIR, "login_result.png"))
                print("[INFO] 已保存截图: login_result.png")
            
            return token
            
        except Exception as e:
            print(f"[ERROR] 登录过程出错: {e}")
            await page.screenshot(path=os.path.join(OUTPUT_DIR, "error.png"))
            return None
        finally:
            await browser.close()


# ============ 数据处理 ============

def find_records(obj: Any) -> List[Dict]:
    """递归查找返回数据中的记录数组"""
    if isinstance(obj, list):
        if all(isinstance(item, dict) for item in obj):
            return obj
        return []
    if isinstance(obj, dict):
        for key in ["results", "data", "list", "records", "rows", "items", "positions"]:
            if key in obj:
                result = find_records(obj[key])
                if result:
                    return result
        for value in obj.values():
            result = find_records(value)
            if result:
                return result
    return []


def join_list(items: Any, sep: str = ",") -> str:
    """将列表或字符串转换为逗号分隔的字符串"""
    if not items:
        return ""
    if isinstance(items, list):
        return sep.join(str(x) for x in items if x)
    return str(items)


def map_record(record: Dict) -> Dict:
    """映射单条记录到输出格式"""
    org_type = record.get("org_type") or []
    industry = record.get("industry") or []
    company_type_industry = "/".join(filter(None, [
        join_list(org_type, "/"),
        join_list(industry, "/")
    ]))
    
    position_req = record.get("position_require_new") or {}
    location = join_list(record.get("address_str") or position_req.get("address") or [])
    major_req = join_list(record.get("major_str") or position_req.get("major") or [])
    
    return {
        "job_id": record.get("position_id") or record.get("_id") or "",
        "company": record.get("company_alias") or record.get("main_company_name") or "",
        "company_type_industry": company_type_industry,
        "company_tags": join_list(record.get("tags") or []),
        "department": record.get("company_name") or "",
        "job_title": record.get("job_title") or "",
        "location": location,
        "major_req": major_req,
        "job_req": record.get("raw_position_require") or "",
        "job_duty": record.get("responsibility") or "",
        "referral_code": "",
        "publish_date": record.get("publish_date") or record.get("spider_time") or "",
        "deadline": record.get("expire_date") or "",
        "detail_url": record.get("position_web_url") or "",
        "apply_url": "",
        "scraped_at": datetime.now().isoformat(),
        "job_stage": "campus",
        "source_config_id": "",
    }


def split_csv(value: str) -> List[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def split_int_csv(value: str) -> List[int]:
    result: List[int] = []
    for item in split_csv(value):
        try:
            result.append(int(item))
        except ValueError:
            continue
    return result


def resolve_stage(
    config_id: str,
    sheet_index: int,
    target_index: int,
    total_targets: int,
    internship_ids: Set[str],
    internship_sheet_indexes: Set[int],
) -> str:
    if sheet_index in internship_sheet_indexes:
        return "internship"
    if config_id in internship_ids:
        return "internship"
    if internship_ids or internship_sheet_indexes:
        return "campus"
    if total_targets >= 4 and target_index >= 2:
        return "internship"
    return "campus"


def load_existing_job_ids(filepath: str) -> Set[str]:
    """加载已存在的 job_id 集合"""
    if not os.path.exists(filepath):
        return set()
    job_ids = set()
    try:
        with open(filepath, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if "job_id" in row and row["job_id"]:
                    job_ids.add(row["job_id"])
    except Exception as e:
        print(f"[WARN] 读取已有文件失败: {e}")
    return job_ids


# ============ 爬虫逻辑 ============

def fetch_page(
    session: requests.Session,
    token: str,
    config_id: str,
    sheet_index: int,
    page: int,
    page_size: int,
    max_retries: int = 3,
    sleep_range: tuple = (0.5, 1.5),
) -> Optional[Dict]:
    """抓取单页数据"""
    headers = {**DEFAULT_HEADERS, "Authorization": f"Bearer {token}"}
    body = {
        "position_export_config_id": config_id,
        "sheet_index": sheet_index,
        "company_id": "",
        "job_title": "",
        "major_ids": [],
        "address_ids": [],
        "tags": [],
        "industry": [],
        "org_type": [],
        "degree_ids": [],
        "english_ids": [],
        "school_ids": [],
        "personal_ids": [],
        "other_ids": [],
        "page": page,
        "page_size": page_size,
    }
    
    for attempt in range(max_retries):
        try:
            resp = session.post(API_URL, headers=headers, json=body, timeout=30)
            
            if resp.status_code == 401:
                print("[ERROR] 401 Unauthorized - Token 失效")
                return None
            elif resp.status_code == 403:
                print("[ERROR] 403 Forbidden - 无权限")
                return None
            elif resp.status_code == 429:
                wait = (attempt + 1) * 5
                print(f"[WARN] 429 Too Many Requests, 等待 {wait}s...")
                time.sleep(wait)
                continue
            elif resp.status_code >= 500:
                wait = (attempt + 1) * 3
                print(f"[WARN] {resp.status_code} Server Error, 等待 {wait}s...")
                time.sleep(wait)
                continue
            
            resp.raise_for_status()
            data = resp.json()
            
            sleep_time = random.uniform(*sleep_range)
            time.sleep(sleep_time)
            
            return data
            
        except RequestException as e:
            print(f"[ERROR] 请求失败 (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                return None
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON 解析失败: {e}")
            return None
    
    return None


def run_scraper(
    token: str,
    config_ids: List[str],
    sheet_indexes: List[int],
    output_file: str,
    page_size: int = 50,
    max_pages: int = 100,
    internship_ids: Optional[Set[str]] = None,
    internship_sheet_indexes: Optional[Set[int]] = None,
) -> int:
    """运行爬虫，返回抓取的记录数"""
    session = requests.Session()
    all_records: List[Dict] = []
    existing_ids = load_existing_job_ids(output_file)
    
    internship_ids = internship_ids or set()
    internship_sheet_indexes = internship_sheet_indexes or set()
    config_ids = [item for item in config_ids if item]
    sheet_indexes = [idx for idx in sheet_indexes if isinstance(idx, int) and idx >= 0]
    if not sheet_indexes:
        sheet_indexes = [0]

    crawl_targets: List[tuple[str, int]] = []
    seen_targets = set()
    for current_config_id in config_ids:
        for current_sheet_index in sheet_indexes:
            target = (current_config_id, current_sheet_index)
            if target in seen_targets:
                continue
            seen_targets.add(target)
            crawl_targets.append(target)

    for target_index, (config_id, sheet_index) in enumerate(crawl_targets):
        stage = resolve_stage(
            config_id,
            sheet_index,
            target_index,
            len(crawl_targets),
            internship_ids,
            internship_sheet_indexes,
        )
        print(
            f"[INFO] 抓取分支 {target_index + 1}/{len(crawl_targets)}: "
            f"config={config_id}, sheet={sheet_index} ({stage})"
        )

        for page in range(1, max_pages + 1):
            print(f"[INFO] 抓取第 {page} 页...")

            data = fetch_page(session, token, config_id, sheet_index, page, page_size)

            if data is None:
                print("[ERROR] 获取数据失败，停止当前分支抓取")
                break

            records = find_records(data)

            if not records:
                print("[INFO] 没有更多数据")
                break

            new_count = 0
            for record in records:
                mapped = map_record(record)
                mapped["job_stage"] = stage
                mapped["source_config_id"] = config_id
                if mapped["job_id"] not in existing_ids:
                    all_records.append(mapped)
                    existing_ids.add(mapped["job_id"])
                    new_count += 1

            print(f"[INFO] 第 {page} 页: {len(records)} 条记录, 新增 {new_count} 条")

            if len(records) < page_size:
                print("[INFO] 已到最后一页")
                break
    
    if all_records:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        write_header = not os.path.exists(output_file)
        with open(output_file, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS)
            if write_header:
                writer.writeheader()
            writer.writerows(all_records)
        
        print(f"[SUCCESS] 写入 {len(all_records)} 条记录到 {output_file}")
    
    return len(all_records)


# ============ 主程序 ============

async def main_async(
    headless: bool = True,
    max_pages: int = 100,
    page_size: int = 50,
    config_id: Optional[str] = None,
    config_ids: Optional[str] = None,
    sheet_indexes: Optional[str] = None,
    args=None,
):
    """异步主函数"""
    # 检查环境变量
    username, password = get_credentials(args)
    if not username or not password:
        print("=" * 50)
        print("[ERROR] 请先设置环境变量:")
        print("")
        print("  Windows PowerShell:")
        print("    $env:TATA_USERNAME = '你的账号'")
        print("    $env:TATA_PASSWORD = '你的密码'")
        print("")
        print("  Linux/Mac:")
        print("    export TATA_USERNAME='你的账号'")
        print("    export TATA_PASSWORD='你的密码'")
        print("=" * 50)
        return
    
    # 获取 config_ids
    raw_config_ids = config_ids or os.environ.get("TATA_EXPORT_CONFIG_IDS", "")
    if raw_config_ids:
        selected_config_ids = split_csv(raw_config_ids)
    else:
        fallback_config_ids = config_id if config_id is not None else (os.environ.get("TATA_EXPORT_CONFIG_ID") or DEFAULT_CONFIG_ID)
        selected_config_ids = split_csv(fallback_config_ids)

    raw_sheet_indexes = sheet_indexes or os.environ.get("TATA_EXPORT_SHEET_INDEXES", "")
    if raw_sheet_indexes:
        selected_sheet_indexes = split_int_csv(raw_sheet_indexes)
    else:
        selected_sheet_indexes = [0]

    internship_ids = set(split_csv(os.environ.get("TATA_INTERNSHIP_CONFIG_IDS", "")))
    internship_sheet_indexes = set(split_int_csv(os.environ.get("TATA_INTERNSHIP_SHEET_INDEXES", "")))
    
    # 1. 自动登录获取 token
    print("\n[STEP 1] 自动登录获取 Token...")
    token = await get_token_via_browser(headless=headless, args=args)
    
    if not token:
        print("[ERROR] 获取 Token 失败")
        return
    
    # 2. 执行爬虫
    print("\n[STEP 2] 开始爬取数据...")
    count = run_scraper(
        token=token,
        config_ids=selected_config_ids,
        sheet_indexes=selected_sheet_indexes,
        output_file=OUTPUT_FILE,
        page_size=page_size,
        max_pages=max_pages,
        internship_ids=internship_ids,
        internship_sheet_indexes=internship_sheet_indexes,
    )
    
    print(f"\n[DONE] 共抓取 {count} 条新记录")


def main():
    """主入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="tatawangshen.com 自动登录爬虫")
    parser.add_argument("--show-browser", action="store_true", help="显示浏览器窗口（默认隐藏）")
    parser.add_argument("--max-pages", type=int, default=100, help="最大抓取页数")
    parser.add_argument("--page-size", type=int, default=50, help="每页记录数")
    parser.add_argument("--config-ids", default=None, help="多个 position_export_config_id，逗号分隔")
    parser.add_argument("--config-id", default=None, help="position_export_config_id")
    parser.add_argument("--sheet-indexes", default=None, help="多个 sheet_index，逗号分隔")
    parser.add_argument("--username", default=None, help="登录账号")
    parser.add_argument("--password", default=None, help="登录密码")
    
    args = parser.parse_args()
    
    asyncio.run(main_async(
        headless=not args.show_browser,
        max_pages=args.max_pages,
        page_size=args.page_size,
        config_id=args.config_id,
        config_ids=args.config_ids,
        sheet_indexes=args.sheet_indexes,
        args=args,
    ))


if __name__ == "__main__":
    main()
