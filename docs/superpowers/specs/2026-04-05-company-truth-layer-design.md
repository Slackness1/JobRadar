# Company Truth Layer Design

Date: 2026-04-05

## Goal

Build a spring-first company truth layer for JobRadar that can serve as the stable company-level anchor for future job tables, validation, and aggregation.

The current priority is **spring recruiting**, not fall recruiting. Fall data should still be preserved in the broader truth-layer system, but it must **not pollute the spring-focused master company layer** used as the main business baseline.

## Context

There are currently two main company truth-layer sources:

1. `data/exports/xiaozhao_full_export.csv`
2. `/mnt/d/qq_sheet_full.csv`

These two sources are complementary:

- `xiaozhao_full_export.csv`
  - broader company coverage
  - richer link fields (`公告链接`, `投递链接`)
  - mixed seasonal content: large fall component, but also substantial spring content
- `qq_sheet_full.csv`
  - stronger spring coverage
  - cleaner entity fields
  - richer company classification (`企业/单位性质`, fine-grained industry)
  - no outbound application links

The future system also needs to support additional truth-layer sources, plus crawler-derived job data.

## Design Principles

1. **Spring-first default**
   - the main company registry used by the product should reflect spring relevance
2. **Do not discard fall data**
   - fall records remain useful for history, crawling, and future expansion
3. **Company layer drives downstream job architecture**
   - future normalized/aggregated job tables should key off company truth-layer entities
4. **Keep raw richness**
   - preserve source-specific detail instead of over-collapsing too early
5. **Prefer explicit derived views over destructive filtering**
   - keep one full base layer and one spring-focused master layer

## Proposed Data Architecture

### 1. Company Truth Base Layer

File name target:

- `data/exports/company_truth_base.csv`

Purpose:

- full company-level baseline across all truth-layer sources
- one row per canonical company
- includes spring/fall/intern/public signals
- acts as the durable company anchor for future pipelines

Inclusion rule:

- any company appearing in any truth-layer source may enter this base layer

### 2. Spring Company Truth Master Layer

File name target:

- `data/exports/company_truth_spring_master.csv`

Purpose:

- the main company registry for current product use
- spring-first company baseline
- drives spring-oriented analytics, company coverage checks, and future job data products

Inclusion rule:

- only companies with **spring signal** enter this layer
- fall-only companies are excluded from this master company registry

Spring signal is defined as any company having at least one associated record whose recruiting type contains:

- `春招`
- `春招提前批`
- `春招正式批`
- `春招,实习` or equivalent spring+intern mixed labels

This rule is intentionally conservative: a company must have explicit spring evidence to become part of the main company pool.

### 3. Unified Job Truth Layer

File name target:

- `data/exports/job_truth_unified.csv`

Purpose:

- preserve all source job rows in a common schema
- include spring, fall, intern, public-recruitment, and mixed records
- keep company linkage to the canonical company entity

Important:

- this file is broader than the spring company master
- fall jobs remain here
- later UI filtering can continue to hide fall jobs when desired

## Company Truth Layer Schema

### Required identity fields

- `company_id`
- `canonical_name`
- `display_name`
- `aliases_json`

### Source coverage fields

- `source_coverage_json`
- `source_count`
- `source_priority`
- `first_seen_source`
- `last_seen_source`

### Recruiting signal fields

- `has_spring`
- `has_fall`
- `has_intern`
- `has_public_recruit`
- `spring_record_count`
- `fall_record_count`
- `intern_record_count`
- `public_recruit_record_count`
- `dominant_recruiting_season`

### Classification fields

- `company_nature`
- `industry_coarse`
- `industry_fine`
- `industry_tags_json`
- `is_state_owned`
- `is_foreign`
- `is_financial`
- `is_bank_like`
- `is_securities_like`

### Link and crawling fields

- `has_apply_link`
- `has_announce_link`
- `best_apply_link`
- `best_announce_link`
- `best_link_source`
- `is_crawlable`

### Quality fields

- `record_count_total`
- `completeness_score`
- `needs_manual_review`
- `merge_notes`

## Job Truth Layer Schema

Unified output should normalize the two current sources into one shared structure:

- `company_id`
- `company_name_raw`
- `canonical_company_name`
- `source_name`
- `recruiting_type_raw`
- `recruiting_type_normalized`
- `season_normalized`
- `job_title_raw`
- `location_raw`
- `deadline_raw`
- `target_students_raw`
- `company_nature_raw`
- `industry_raw`
- `industry_coarse`
- `industry_fine`
- `announce_url`
- `apply_url`
- `notes`
- `updated_at_raw`

This preserves raw values while making later aggregation easier.

## Company Matching Strategy

Matching should occur in stages:

1. exact normalized match
2. conservative containment match
3. manual review flag for ambiguous pairs

Normalization rules:

- trim whitespace
- normalize repeated spaces/punctuation noise
- preserve meaningful Chinese/English company names
- do not aggressively remove business qualifiers if that would merge distinct entities incorrectly

Examples that may match conservatively:

- `腾讯IEG` ↔ `腾讯`
- `阿里云-安全岗位` ↔ `阿里云`
- `万商天勤律师事务所` ↔ `万商天勤`

Examples that should be flagged instead of auto-merged if confidence is weak:

- parent company vs subsidiary
- group brand vs business unit
- generic short names that collide with many entities

## Field Precedence Rules

When sources disagree:

### Company name
- canonical name prefers the cleaner business identity form
- raw variants remain in `aliases_json`

### Company nature
- prefer `qq_sheet_full.csv` because it is systematically populated

### Industry
- keep both coarse and fine forms
- coarse can be sourced from xiaozhao
- fine can be sourced from qq_sheet
- do not force a lossy one-column merge

### Links
- prefer xiaozhao source because qq sheet lacks these fields

### Spring/fall classification
- determined from all linked source records, not from one preferred source only

## Output Files

This phase should produce:

1. `data/exports/job_truth_unified.csv`
2. `data/exports/company_truth_base.csv`
3. `data/exports/company_truth_spring_master.csv`
4. `data/exports/company_truth_merge_review.csv`

Where:

- `job_truth_unified.csv` is the all-records job truth layer
- `company_truth_base.csv` is the all-company canonical base layer
- `company_truth_spring_master.csv` is the spring-only business master layer
- `company_truth_merge_review.csv` stores ambiguous company matches for manual review

## Why This Architecture Fits the Product

The user’s near-term business goal is to output spring recruiting job tables during spring recruiting season. That requires the default company baseline to be spring-focused.

At the same time, the system should not lose fall data because:

- fall records still help with crawling entry discovery
- fall records enrich company history
- future seasonal pivots should not require rebuilding the company layer from scratch

This split resolves the tension cleanly:

- the **base company layer** preserves breadth
- the **spring master company layer** preserves business focus
- the **unified job truth layer** preserves all usable job evidence

## Future Extension

Later source files can be integrated by:

1. mapping their raw columns into the unified job schema
2. matching their companies into `company_truth_base`
3. recomputing spring/fall/intern/public signals
4. regenerating `company_truth_spring_master`

This allows the truth layer to grow incrementally without redesign.

## Implementation Scope for Next Step

The next implementation step should:

1. read the two current truth-layer CSVs
2. normalize them into a unified job-truth file
3. derive the company base layer
4. derive the spring master company layer
5. output a review file for ambiguous merges

This step should remain file-based and should not require backend schema changes.
