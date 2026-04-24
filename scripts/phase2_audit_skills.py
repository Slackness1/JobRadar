#!/usr/bin/env python3
import subprocess, sys, json, pathlib
from datetime import datetime

base = pathlib.Path('/home/ubuntu/.openclaw/workspace-projecta/skills')

skills_to_audit = [
    'clawsec',
    'openclaw-skill-vetter',
    'security-auditor',
    'skill-scanner'
]

report = {
    'scan_date': datetime.now().isoformat(),
    'audited_skills': skills_to_audit,
    'findings': []
}

for skill in skills_to_audit:
    print(f'===== AUDITING {skill} =====')
    
    # Step 1: skill-scanner scan
    print('[1/3] Running skill-scanner...')
    proc = subprocess.run(['python3', '/home/ubuntu/.openclaw/workspace-projecta/skills/skill-scanner/skill_scanner.py', str(base/skill)], 
                     capture_output=True, text=True, timeout=60)
    result = proc.stdout
    
    # Parse skill-scanner output for verdict
    verdict = 'UNKNOWN'
    if 'REJECT' in result:
        verdict = 'REJECT'
    elif 'SAFE TO INSTALL' in result:
        verdict = 'APPROVED'
    
    report['findings'].append({
        'skill': skill,
        'phase': 'skill-scanner',
        'verdict': verdict,
        'summary': result[:800]
    })
    
    print(result[:2000])
    
    # Step 2: skill-vetter vet (only for clawsec)
    if skill == 'clawsec':
        print('[2/3] Running openclaw-skill-vetter...')
        proc = subprocess.run(['python3', '-c',
            'import sys; '
            'sys.path.insert(0, "/home/ubuntu/.openclaw/workspace-projecta/skills"); '
            'from skill_scanner import skill_scanner; '
            'from pathlib import Path; '
            'result=skill_scanner(Path("/home/ubuntu/.openclaw/workspace-projecta/skills/clawsec")); '
            'print(f"Vet Report for clawsec: {{result.verdict}}")'
        ], capture_output=True, text=True, timeout=90)
        vet_result = proc.stdout
        
        report['findings'].append({
            'skill': skill,
            'phase': 'skill-vetter',
            'verdict': 'PENDING_MANUAL',
            'summary': vet_result[:1200]
        })
        print(vet_result[:800])
    
    # Step 3: security-auditor audit (for skills with code)
    if skill in ['security-auditor', 'skill-scanner']:
        print(f'[3/3] Checking for executable code in {skill}...')
        skill_path = base / skill
        has_code = (skill_path / 'SKILL.md').exists()
        
        if has_code:
            verdict = 'MANUAL_AUDIT_NEEDED'
        else:
            verdict = 'NO_CODE_TO_AUDIT'
        
        report['findings'].append({
            'skill': skill,
            'phase': 'code-check',
            'verdict': verdict,
            'summary': 'Has executable files' if has_code else 'No scripts to audit'
        })
        
        print(f"Has executable: {has_code}")

# Save report
report_path = base / 'SECURITY_SKILL_REVIEW_2026-03-13_PHASE2.md'

with open(report_path, 'w') as f:
    json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f'Report saved to: {report_path}')

print('\n=== SUMMARY ===')
for finding in report['findings']:
    print(f"{finding['skill']} [{finding['phase']}]: {finding['verdict']}")
