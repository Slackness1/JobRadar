"""
Build Company Truth Layer: unified job truth + company base + spring master + merge review.

Usage: python3 /tmp/build_truth_layer.py
Outputs: data/exports/job_truth_unified.csv, company_truth_base.csv, company_truth_spring_master.csv, company_truth_merge_review.csv
"""
import csv, io, re, json, hashlib
from pathlib import Path
from collections import Counter, defaultdict

from app.services.company_truth_merge import apply_parent_rollup_overrides, infer_parent_company, is_spring_master_job, normalize_company_for_matching, partition_review_pairs

PROJECT = Path('/home/chuanbo/projects/JobRadar')
DATA_DIR = PROJECT / 'data' / 'exports'
DATA_DIR.mkdir(parents=True, exist_ok=True)

CSV1 = DATA_DIR / 'xiaozhao_full_export.csv'
CSV2 = Path('/mnt/d/qq_sheet_full.csv')
PARENT_OVERRIDE_CSV = DATA_DIR / 'company_truth_parent_rollup_overrides.csv'

# ── Helpers ──────────────────────────────────────────────

def norm(s):
    return re.sub(r'\s+', '', (s or '').strip())

def classify_season(recruit_type):
    t = (recruit_type or '').strip()
    if not t: return 'unknown'
    if '春招' in t: return 'spring'
    if '秋招' in t: return 'fall'
    if '实习' in t or '暑期' in t: return 'intern'
    if '公开' in t or '专场' in t: return 'public'
    if '校招' in t: return 'campus'
    if '人才计划' in t: return 'talent_program'
    if '26届' in t or '提前批' in t: return 'fall'
    return 'other'

COARSE_MAP = {
    '国央企': 'state_owned', '金融': 'finance', '互联网': 'internet',
    '制造业': 'manufacturing', '科技': 'tech', '事业单位': 'public_institution',
    '半导体': 'semiconductor', '外企': 'foreign', '生物医药': 'biopharma',
    '快消零售': 'consumer_retail', '汽车新能源': 'auto_energy', '教育': 'education',
    '游戏': 'gaming', '能源': 'energy', '建筑': 'construction',
    '咨询法律': 'consulting_legal', '农业': 'agriculture',
}

def map_coarse(industry_raw):
    if not industry_raw: return ''
    for key, val in COARSE_MAP.items():
        if key in industry_raw: return val
    return 'other'

def clean_suffix(name):
    for sfx in ['（第二批）','（第二批次）','【第二批】','（第一批）','【急招】',
                '（社招+校招）','-急招岗位','-空缺岗位','-扩招','-剩余岗位',
                '-岗位上新','【校招+社招】']:
        name = name.replace(sfx, '')
    return name.strip()

def detect_platform(url):
    if not url: return ''
    u = url.lower()
    for pat, name in [('mokahr.com','Moka'),('moka.com','Moka'),('wd5.','Workday'),
                       ('zhiye.com','Zhiye'),('hotjob.cn','HotJob'),('51job','51job'),
                       ('zhaopin','ZhaoPin'),('boss','BOSS'),('mp.weixin.qq.com','WeChat'),
                       ('feishu','Feishu'),('iguopin','iGuoPin'),('liepin','Liepin')]:
        if pat in u: return name
    return 'Other'


def load_parent_rollup_overrides():
    if not PARENT_OVERRIDE_CSV.exists():
        return []
    with open(PARENT_OVERRIDE_CSV, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

# ── Step 1: Load + Build unified job truth ───────────────

print("Step 1: Loading sources...")
parent_rollup_overrides = load_parent_rollup_overrides()
with open(CSV1, encoding='utf-8-sig') as f:
    r1 = list(csv.DictReader(f))
with open(CSV2, encoding='utf-8-sig') as f:
    lines = f.readlines()
r2 = list(csv.DictReader(io.StringIO(''.join(lines[2:]))))
print(f"  xiaozhao: {len(r1)} rows, qq_sheet: {len(r2)} rows")

JOB_COLS = [
    'job_id','source_name','company_name_raw','norm_company_name',
    'recruiting_type_raw','season_normalized','job_title_raw',
    'location_raw','deadline_raw','target_students_raw',
    'company_nature_raw','industry_raw','industry_coarse',
    'announce_url','apply_url','link_platform',
    'is_pen_exempt','notes','updated_at_raw',
]

def make_job_id(prefix, *parts):
    payload = '|'.join(parts)
    return hashlib.md5(f"{prefix}_{payload}".encode()).hexdigest()[:16]

unified_jobs = []

for r in r1:
    comp = r.get('公司','').strip()
    recruit = r.get('招聘类型','').strip()
    apply_url = r.get('投递链接','').strip()
    announce_url = r.get('公告链接','').strip()
    industry = r.get('公司行业','').strip()
    unified_jobs.append({
        'job_id': make_job_id('xz', comp, recruit, r.get('岗位','')[:60], r.get('工作地点','')),
        'source_name': 'xiaozhao_export',
        'company_name_raw': comp,
        'norm_company_name': normalize_company_for_matching(comp),
        'recruiting_type_raw': recruit,
        'season_normalized': classify_season(recruit),
        'job_title_raw': r.get('岗位','').strip(),
        'location_raw': r.get('工作地点','').strip(),
        'deadline_raw': r.get('截止日期','').strip(),
        'target_students_raw': r.get('对象','').strip(),
        'company_nature_raw': '',
        'industry_raw': industry,
        'industry_coarse': map_coarse(industry),
        'announce_url': announce_url,
        'apply_url': apply_url,
        'link_platform': detect_platform(apply_url),
        'is_pen_exempt': r.get('是否免笔试','').strip(),
        'notes': r.get('备注','').strip(),
        'updated_at_raw': r.get('更新时间','').strip(),
    })

for r in r2:
    comp = r.get('企业/招聘单位名称','').strip()
    recruit = r.get('招聘类型/批次','').strip()
    industry = r.get('行业分类','').strip()
    unified_jobs.append({
        'job_id': make_job_id('qq', comp, recruit, r.get('招聘岗位','')[:60], r.get('工作地点','')),
        'source_name': 'qq_sheet',
        'company_name_raw': comp,
        'norm_company_name': normalize_company_for_matching(comp),
        'recruiting_type_raw': recruit,
        'season_normalized': classify_season(recruit),
        'job_title_raw': r.get('招聘岗位','').strip(),
        'location_raw': r.get('工作地点','').strip(),
        'deadline_raw': r.get('网申截止时间','').strip(),
        'target_students_raw': r.get('招聘对象','').strip(),
        'company_nature_raw': r.get('企业/单位性质','').strip(),
        'industry_raw': industry,
        'industry_coarse': map_coarse(industry),
        'announce_url': '',
        'apply_url': '',
        'link_platform': '',
        'is_pen_exempt': '',
        'notes': '',
        'updated_at_raw': '',
    })

# Drop rows without usable company identity
unified_jobs = [j for j in unified_jobs if j['norm_company_name']]

out_jobs = DATA_DIR / 'job_truth_unified.csv'
with open(out_jobs, 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=JOB_COLS)
    w.writeheader()
    w.writerows(unified_jobs)

season_dist = Counter(j['season_normalized'] for j in unified_jobs)
print(f"\n  job_truth_unified.csv: {len(unified_jobs)} rows")
print(f"  By season: {dict(season_dist)}")

# ── Step 2: Company matching ────────────────────────────

print("\nStep 2: Matching companies...")

# Group rows by norm_company_name
company_rows = defaultdict(list)
for j in unified_jobs:
    if not j['norm_company_name']:
        continue
    company_rows[j['norm_company_name']].append(j)

all_names = set(company_rows.keys())
print(f"  Unique norm names: {len(all_names)}")

# Exact match first (different raw names that normalize to same)
exact_groups = defaultdict(set)
for name in all_names:
    # strip more aggressively for a second-pass exact key
    key = re.sub(r'[（）()【】\[\]]', '', name)
    exact_groups[key].add(name)

# Containment matching
matched = {}  # smaller_name -> canonical_name
unmatched = set(all_names)
fuzzy_pairs = []

# First pass: exact overlap across sources
for name in sorted(all_names, key=len, reverse=True):
    if name not in unmatched:
        continue
    candidates = []
    for other in sorted(unmatched):
        if other == name:
            continue
        if len(name) < 2 or len(other) < 2:
            continue
        if name in other or other in name:
            shorter = min(name, other, key=len)
            longer = max(name, other, key=len)
            # skip if shorter is generic (len <= 3)
            if len(shorter) <= 3:
                continue
            candidates.append((other, len(longer) - len(shorter)))
    if candidates:
        best, diff = min(candidates, key=lambda x: x[1])
        # Use the longer/cleaner name as canonical
        canonical = name if len(name) >= len(best) else best
        alias = best if canonical == name else name
        matched[alias] = canonical
        matched[name] = canonical
        unmatched.discard(name)
        unmatched.discard(best)
        fuzzy_pairs.append((name, best, canonical))

auto_merged_pairs, review_pairs = partition_review_pairs(fuzzy_pairs)

parent_resolved_review_pairs = []
remaining_review_pairs = []
for a, b, c in review_pairs:
    parent_a = infer_parent_company(a)
    parent_b = infer_parent_company(b)
    if parent_a and parent_a == parent_b:
        parent_resolved_review_pairs.append((a, b, parent_a))
    else:
        remaining_review_pairs.append((a, b, c))

# Build canonical entity map
# canonical_name -> aggregated info
entities = defaultdict(lambda: {
    'aliases': set(),
    'rows': [],
    'sources': set(),
    'spring': 0, 'fall': 0, 'intern': 0, 'public': 0, 'campus': 0,
    'talent': 0, 'other': 0, 'unknown': 0,
    'industry_coarse': '', 'industry_fine': '',
    'industry_tags': set(),
    'company_nature': '',
    'apply_links': [], 'announce_links': [],
    'needs_review': False, 'merge_notes': [],
})

# Map each name -> canonical
name_to_canonical = {}
for name in all_names:
    if name in matched:
        name_to_canonical[name] = matched[name]
    else:
        name_to_canonical[name] = name

# Aggregate
for j in unified_jobs:
    cname = name_to_canonical[j['norm_company_name']]
    e = entities[cname]
    e['aliases'].add(j['company_name_raw'])
    e['aliases'].add(j['norm_company_name'])
    e['rows'].append(j)
    e['sources'].add(j['source_name'])

    season = j['season_normalized']
    if season == 'spring':    e['spring'] += 1
    elif season == 'fall':    e['fall'] += 1
    elif season == 'intern':  e['intern'] += 1
    elif season == 'public':  e['public'] += 1
    elif season == 'campus':  e['campus'] += 1
    elif season == 'talent_program': e['talent'] += 1
    elif season == 'other':   e['other'] += 1
    else:                     e['unknown'] += 1

    ind_c = j['industry_coarse']
    ind_r = j['industry_raw']
    if ind_c and not e['industry_coarse']:
        e['industry_coarse'] = ind_c
    if ind_r and not e['industry_fine'] and j['source_name'] == 'qq_sheet':
        e['industry_fine'] = ind_r
    if ind_r:
        e['industry_tags'].add(ind_r)

    nature = j.get('company_nature_raw', '').strip()
    if nature and not e['company_nature']:
        e['company_nature'] = nature

    apply_url = j.get('apply_url', '').strip()
    announce_url = j.get('announce_url', '').strip()
    if apply_url:   e['apply_links'].append(apply_url)
    if announce_url: e['announce_links'].append(announce_url)

for a, b, c in auto_merged_pairs:
    entities[c]['merge_notes'].append(f"auto-merged: '{a}' ↔ '{b}'")

for a, b, c in parent_resolved_review_pairs:
    parent_name = infer_parent_company(c)
    entities[parent_name]['merge_notes'].append(f"parent-grouped: '{a}' ↔ '{b}'")

for a, b, c in remaining_review_pairs:
    entities[c]['needs_review'] = True
    entities[c]['merge_notes'].append(f"fuzzy: '{a}' ↔ '{b}'")

print(f"  Canonical companies: {len(entities)}")
print(f"  Auto-merged pairs: {len(auto_merged_pairs)}")
print(f"  Parent-grouped review pairs: {len(parent_resolved_review_pairs)}")
print(f"  Review pairs: {len(remaining_review_pairs)}")

# ── Step 3: Write company_truth_base.csv ─────────────────

print("\nStep 3: Writing company_truth_base.csv...")

BASE_COLS = [
    'company_id','canonical_name','display_name','aliases_json',
    'entity_members_json','child_entity_count',
    'source_coverage_json','source_count','source_priority',
    'first_seen_source','last_seen_source',
    'has_spring','has_fall','has_intern','has_public_recruit',
    'spring_record_count','fall_record_count','intern_record_count','public_recruit_record_count',
    'has_spring_at_parent_level','has_spring_at_any_child_level',
    'spring_parent_record_count','spring_child_record_count',
    'dominant_season','record_count_total',
    'company_nature','industry_coarse','industry_fine','industry_tags_json',
    'is_state_owned','is_foreign','is_financial','is_bank_like','is_securities_like',
    'has_apply_link','has_announce_link',
    'best_apply_link','best_announce_link','best_link_source',
    'is_crawlable','completeness_score','needs_manual_review','merge_notes_json',
]

parent_groups = defaultdict(lambda: {
    'member_names': set(),
    'aliases': set(),
    'rows': [],
    'sources': set(),
    'spring': 0, 'fall': 0, 'intern': 0, 'public': 0, 'campus': 0,
    'talent': 0, 'other': 0, 'unknown': 0,
    'spring_parent': 0, 'spring_child': 0,
    'industry_coarse': '', 'industry_fine': '',
    'industry_tags': set(),
    'company_nature': '',
    'apply_links': [], 'announce_links': [],
    'needs_review': False, 'merge_notes': [],
})

for cname, e in entities.items():
    parent_name = apply_parent_rollup_overrides(cname, parent_rollup_overrides) or infer_parent_company(cname)
    pg = parent_groups[parent_name]
    pg['member_names'].add(cname)
    pg['aliases'].update(e['aliases'])
    pg['rows'].extend(e['rows'])
    pg['sources'].update(e['sources'])
    pg['spring'] += e['spring']
    pg['fall'] += e['fall']
    pg['intern'] += e['intern']
    pg['public'] += e['public']
    pg['campus'] += e['campus']
    pg['talent'] += e['talent']
    pg['other'] += e['other']
    pg['unknown'] += e['unknown']
    if cname == parent_name:
        pg['spring_parent'] += e['spring']
    else:
        pg['spring_child'] += e['spring']
    if not pg['industry_coarse'] and e['industry_coarse']:
        pg['industry_coarse'] = e['industry_coarse']
    if not pg['industry_fine'] and e['industry_fine']:
        pg['industry_fine'] = e['industry_fine']
    if not pg['company_nature'] and e['company_nature']:
        pg['company_nature'] = e['company_nature']
    pg['industry_tags'].update(e['industry_tags'])
    pg['apply_links'].extend(e['apply_links'])
    pg['announce_links'].extend(e['announce_links'])
    pg['needs_review'] = pg['needs_review'] or e['needs_review']
    pg['merge_notes'].extend(e['merge_notes'])

base_rows = []
for idx, (cname, e) in enumerate(sorted(parent_groups.items()), 1):
    total = e['spring'] + e['fall'] + e['intern'] + e['public'] + e['campus'] + e['talent'] + e['other'] + e['unknown']
    seasons = {'spring': e['spring'], 'fall': e['fall'], 'intern': e['intern'],
               'public': e['public'], 'campus': e['campus'], 'talent_program': e['talent']}
    dominant = max(seasons, key=seasons.get) if total > 0 else 'unknown'

    # Best links: prefer non-wechat
    best_apply = ''
    if e['apply_links']:
        non_wx = [l for l in e['apply_links'] if 'mp.weixin.qq.com' not in l]
        best_apply = (non_wx or e['apply_links'])[0]

    best_announce = ''
    if e['announce_links']:
        non_wx = [l for l in e['announce_links'] if 'mp.weixin.qq.com' not in l]
        best_announce = (non_wx or e['announce_links'])[0]

    is_crawlable = bool(best_apply and 'mp.weixin.qq.com' not in best_apply)

    nature_lower = e['company_nature'].lower()
    is_state = any(k in nature_lower for k in ['国企','央企','事业单位','政府'])
    is_foreign = any(k in nature_lower for k in ['外企','合资','港澳'])
    all_ind = (e['industry_coarse'] + e['industry_fine']).lower()
    is_financial = any(k in all_ind for k in ['金融','银行','证券','基金','保险','投资','finance','fund'])
    is_bank = '银行' in all_ind or 'bank' in all_ind
    is_securities = '证券' in all_ind or 'securit' in all_ind

    # completeness
    score = 0
    if e['company_nature']: score += 15
    if e['industry_coarse'] or e['industry_fine']: score += 15
    if best_apply: score += 25
    if best_announce: score += 10
    if e['spring'] > 0: score += 20
    if len(e['sources']) >= 2: score += 15
    completeness = round(score / 100 * 100, 1)

    base_rows.append({
        'company_id': f"C{idx:05d}",
        'canonical_name': cname,
        'display_name': cname,
        'aliases_json': json.dumps(sorted(e['aliases']), ensure_ascii=False),
        'entity_members_json': json.dumps(sorted(e['member_names']), ensure_ascii=False),
        'child_entity_count': len(e['member_names']),
        'source_coverage_json': json.dumps(sorted(e['sources']), ensure_ascii=False),
        'source_count': len(e['sources']),
        'source_priority': 'both' if len(e['sources']) >= 2 else sorted(e['sources'])[0],
        'first_seen_source': e['rows'][0]['source_name'] if e['rows'] else '',
        'last_seen_source': e['rows'][-1]['source_name'] if e['rows'] else '',
        'has_spring': e['spring'] > 0,
        'has_fall': e['fall'] > 0,
        'has_intern': e['intern'] > 0,
        'has_public_recruit': e['public'] > 0,
        'spring_record_count': e['spring'],
        'fall_record_count': e['fall'],
        'intern_record_count': e['intern'],
        'public_recruit_record_count': e['public'],
        'has_spring_at_parent_level': e['spring_parent'] > 0,
        'has_spring_at_any_child_level': e['spring_child'] > 0,
        'spring_parent_record_count': e['spring_parent'],
        'spring_child_record_count': e['spring_child'],
        'dominant_season': dominant,
        'record_count_total': total,
        'company_nature': e['company_nature'],
        'industry_coarse': e['industry_coarse'],
        'industry_fine': e['industry_fine'],
        'industry_tags_json': json.dumps(sorted(e['industry_tags']), ensure_ascii=False),
        'is_state_owned': is_state,
        'is_foreign': is_foreign,
        'is_financial': is_financial,
        'is_bank_like': is_bank,
        'is_securities_like': is_securities,
        'has_apply_link': bool(e['apply_links']),
        'has_announce_link': bool(e['announce_links']),
        'best_apply_link': best_apply[:500],
        'best_announce_link': best_announce[:500],
        'best_link_source': 'xiaozhao' if best_apply else '',
        'is_crawlable': is_crawlable,
        'completeness_score': completeness,
        'needs_manual_review': e['needs_review'],
        'merge_notes_json': json.dumps(e['merge_notes'], ensure_ascii=False),
    })

with open(DATA_DIR / 'company_truth_base.csv', 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=BASE_COLS)
    w.writeheader()
    w.writerows(base_rows)

print(f"  company_truth_base.csv: {len(base_rows)} companies")

# ── Step 4: Spring master ────────────────────────────────

print("\nStep 4: Writing company_truth_spring_master.csv...")
spring_rows = [r for r in base_rows if r['has_spring'] or r['has_fall'] or r['has_intern']]

SPRING_COLS = BASE_COLS  # same schema
with open(DATA_DIR / 'company_truth_spring_master.csv', 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=SPRING_COLS)
    w.writeheader()
    w.writerows(spring_rows)

print(f"  company_truth_spring_master.csv: {len(spring_rows)} companies")

# ── Step 4.5: Spring job master ───────────────────────────

print("\nStep 4.5: Writing job_truth_spring_master.csv...")
spring_company_ids = {r['canonical_name']: r['company_id'] for r in spring_rows}

SPRING_JOB_COLS = [
    'job_id',
    'company_id',
    'canonical_company_name',
    'parent_company_name',
    'company_name_raw',
    'norm_company_name',
    'source_name',
    'recruiting_type_raw',
    'season_normalized',
    'job_title_raw',
    'location_raw',
    'deadline_raw',
    'target_students_raw',
    'company_nature_raw',
    'industry_raw',
    'industry_coarse',
    'announce_url',
    'apply_url',
    'link_platform',
    'is_pen_exempt',
    'notes',
    'updated_at_raw',
]

spring_job_rows = []
for j in unified_jobs:
    canonical_leaf_name = name_to_canonical[j['norm_company_name']]
    parent_company_name = apply_parent_rollup_overrides(canonical_leaf_name, parent_rollup_overrides) or infer_parent_company(canonical_leaf_name)
    company_id = spring_company_ids.get(parent_company_name, '')
    if not is_spring_master_job(j['season_normalized'], bool(company_id)):
        continue

    spring_job_rows.append({
        'job_id': j['job_id'],
        'company_id': company_id,
        'canonical_company_name': parent_company_name,
        'parent_company_name': parent_company_name,
        'company_name_raw': j['company_name_raw'],
        'norm_company_name': j['norm_company_name'],
        'source_name': j['source_name'],
        'recruiting_type_raw': j['recruiting_type_raw'],
        'season_normalized': j['season_normalized'],
        'job_title_raw': j['job_title_raw'],
        'location_raw': j['location_raw'],
        'deadline_raw': j['deadline_raw'],
        'target_students_raw': j['target_students_raw'],
        'company_nature_raw': j['company_nature_raw'],
        'industry_raw': j['industry_raw'],
        'industry_coarse': j['industry_coarse'],
        'announce_url': j['announce_url'],
        'apply_url': j['apply_url'],
        'link_platform': j['link_platform'],
        'is_pen_exempt': j['is_pen_exempt'],
        'notes': j['notes'],
        'updated_at_raw': j['updated_at_raw'],
    })

with open(DATA_DIR / 'job_truth_spring_master.csv', 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=SPRING_JOB_COLS)
    w.writeheader()
    w.writerows(spring_job_rows)

print(f"  job_truth_spring_master.csv: {len(spring_job_rows)} jobs")

# ── Step 5: Merge review ─────────────────────────────────

print("\nStep 5: Writing company_truth_merge_review.csv...")
REVIEW_COLS = ['pair_a','pair_b','canonical_name','needs_review','merge_notes']
review_rows = []
for a, b, c in remaining_review_pairs:
    e = entities[c]
    review_rows.append({
        'pair_a': a, 'pair_b': b, 'canonical_name': c,
        'needs_review': True,
        'merge_notes': '; '.join(e['merge_notes']),
    })

with open(DATA_DIR / 'company_truth_merge_review.csv', 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=REVIEW_COLS)
    w.writeheader()
    w.writerows(review_rows)

print(f"  company_truth_merge_review.csv: {len(review_rows)} pairs")

# ── Summary ──────────────────────────────────────────────

print("\n" + "="*60)
print("BUILD COMPLETE")
print("="*60)
print(f"  job_truth_unified.csv:      {len(unified_jobs):>6} rows")
print(f"  company_truth_base.csv:     {len(base_rows):>6} companies (all)")
print(f"  company_truth_spring_master:{len(spring_rows):>6} companies (spring + fall/intern evidence)")
print(f"  job_truth_spring_master:    {len(spring_job_rows):>6} jobs")
print(f"  company_truth_merge_review: {len(review_rows):>6} fuzzy pairs to review")

print(f"\n  Season breakdown (base):")
print(f"    has_spring:  {sum(1 for r in base_rows if r['has_spring'])}")
print(f"    has_fall:    {sum(1 for r in base_rows if r['has_fall'])}")
print(f"    has_intern:  {sum(1 for r in base_rows if r['has_intern'])}")
print(f"    fall-only:   {sum(1 for r in base_rows if r['has_fall'] and not r['has_spring'])}")
print(f"    spring-only: {sum(1 for r in base_rows if r['has_spring'] and not r['has_fall'])}")
print(f"    both:        {sum(1 for r in base_rows if r['has_spring'] and r['has_fall'])}")

print(f"\n  Crawlability (base):")
print(f"    has direct apply link: {sum(1 for r in base_rows if r['has_apply_link'])}")
print(f"    is_crawlable:          {sum(1 for r in base_rows if str(r['is_crawlable'])=='True')}")
