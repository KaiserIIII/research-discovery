"""Export and validate a portable Discovery Dossier for CS Nature Paper V4.1."""
from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path
from .core import DiscoveryError, Project, digest, read_json, sha, write_json
from .registry import invoke_v41

FILES = ('discovery_manifest.json','hypotheses.json','prior_art_matrix.md','pilot_protocol.json',
         'pilot_results.json','evidence_index.json','rival_explanations.md','limitations.md',
         'discovery_dossier.md','handoff_to_v4_1.md')

def _safe_text(value):
    return str(value).replace('\r','').replace('\x00','')

def export_dossier(project: Project, output: Path):
    if project.audit(): raise DiscoveryError('Cannot export a tampered project')
    output=Path(output).resolve()
    if output.exists() and any(output.iterdir()): raise DiscoveryError('Refusing to overwrite dossier')
    output.mkdir(parents=True,exist_ok=True)
    events=project.events(); evidence=project.evidence()
    candidate_event=project.latest('candidates') or {}
    pilot_events=[e['payload'] for e in events if e['kind']=='pilot_result']
    protocols=[e['payload'] for e in events if e['kind']=='pilot_registered']
    assessments=candidate_event.get('assessments',[])
    manifest=dict(schema_version='1.0',skill_version='1.0.0',project_schema='1.0',
                  exported_utc=project.manifest['created_utc'],domain=project.manifest['domain'],
                  stage_labels=['DISCOVERY','PILOT','EXPLORATORY_POST_HOC'],
                  scientific_status='EXPLORATORY_HANDOFF_REQUIRES_V4_1_REVIEW',
                  audit_findings=[],evidence_count=len(evidence),event_count=len(events),
                  candidate_snapshot=candidate_event.get('snapshot_sha256'))
    hypotheses=[dict(item,assessment=next((a for a in assessments if a.get('id')==item.get('id')),None))
                for item in candidate_event.get('candidates',[])]
    prior=[]
    for assessment in assessments: prior.extend(assessment.get('prior_art_matrix',[]))
    index={k:v for k,v in evidence.items()}
    limitations=['No component claims exhaustive literature coverage or proves originality.',
                 'Metadata-only results and abstracts cannot support load-bearing claims.',
                 'Pilot outputs are exploratory and cannot be promoted to formal evidence.',
                 'Host reasoning and external APIs require independent review and may be unavailable.',
                 'The stdlib runner is bounded but not a security sandbox; it does not isolate networks or arbitrary native code.']
    payloads={
      'discovery_manifest.json':manifest,
      'hypotheses.json':hypotheses,
      'pilot_protocol.json':protocols,
      'pilot_results.json':pilot_events,
      'evidence_index.json':index,
    }
    for name,value in payloads.items(): write_json(output/name,value)
    matrix=['# Prior-art matrix','', '| Claim | Relation | Source | Exact region | Objection | Unresolved |','|---|---|---|---|---|---|']
    for item in prior:
        matrix.append('| {claim} | {relation} | {evidence_id} | lines {lines[0]}-{lines[1]} | {objection} | {unresolved} |'.format(
            claim=_safe_text(item.get('claim','')),relation=_safe_text(item.get('relation','UNVERIFIED')),
            evidence_id=_safe_text(item.get('evidence_id','')),lines=item.get('lines',[0,0]),
            objection=_safe_text(item.get('objection','')),unresolved=_safe_text(item.get('unresolved',''))))
    (output/'prior_art_matrix.md').write_text('\n'.join(matrix)+'\n',encoding='utf-8')
    rivals=['# Rival explanations','']
    for h in hypotheses: rivals.extend([f"## {h.get('id')}: {h.get('question')}",
                                        'Rivals: '+', '.join(map(str,h.get('rivals',[]))),
                                        'Falsifier: '+_safe_text(h.get('falsifier')), ''])
    (output/'rival_explanations.md').write_text('\n'.join(rivals),encoding='utf-8')
    (output/'limitations.md').write_text('# Limitations\n\n'+'\n'.join('- '+x for x in limitations)+'\n',encoding='utf-8')
    lines=['# Discovery Dossier', '',f"Domain: {project.manifest['domain']}",
           '', 'This dossier contains exploratory artifacts and a traceable handoff. It does not declare a paper-ready result.', '',
           '## Candidate decisions']
    for a in assessments: lines.append(f"- `{a.get('id')}`: **{a.get('status')}** — {'; '.join(a.get('findings',[]))}")
    lines.extend(['','## Evidence','Each item in `evidence_index.json` has a local SHA-256 and origin.','', '## Boundaries']+['- '+x for x in limitations])
    (output/'discovery_dossier.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    handoff=['# Handoff to CS Nature Paper V4.1','',
             'Handoff status: `EXPLORATORY_REVIEW_REQUIRED`',
             '', 'V4.1 retains authority to reject novelty, feasibility, evidence, protocol, statistics and publication claims.',
             'All pilot results must be treated as discovery/pilot evidence; they are not formal confirmation samples.',
             '', 'Required next checks: independent literature full-text verification, formal protocol admission, feasibility, statistical design, reproducibility and adversarial review.',
             '', 'No Sol/Luna split is claimed unless the host response records actual actor/model execution.']
    (output/'handoff_to_v4_1.md').write_text('\n'.join(handoff)+'\n',encoding='utf-8')
    # A manifest cannot contain its own hash without recursive self-reference;
    # its journal/project source remains the integrity root. All payload files
    # are content-addressed here.
    hashes={name:sha(output/name) for name in FILES if name!='discovery_manifest.json'}
    manifest['files']=hashes; write_json(output/'discovery_manifest.json',manifest)
    return dict(status='PASS',output=str(output),files=hashes,candidates=len(hypotheses),pilots=len(pilot_events))

def validate_dossier(path: Path):
    path=Path(path).resolve(); findings=[]
    if not path.is_dir(): return {'status':'FAIL','findings':['Dossier directory missing']}
    try: manifest=read_json(path/'discovery_manifest.json')
    except DiscoveryError as exc: return {'status':'FAIL','findings':[str(exc)]}
    for name in FILES:
        target=path/name
        if not target.exists(): findings.append('Missing '+name); continue
        expected=manifest.get('files',{}).get(name)
        if expected and sha(target)!=expected: findings.append('Hash mismatch '+name)
    if manifest.get('scientific_status')!='EXPLORATORY_HANDOFF_REQUIRES_V4_1_REVIEW': findings.append('Unsafe scientific status')
    return {'status':'PASS' if not findings else 'FAIL','findings':findings,'files':len(FILES)}

def compatibility(path: Path, v41: Path):
    result=validate_dossier(path); findings=list(result.get('findings',[]))
    if not Path(v41,'scripts','evidence_anchor.py').exists(): findings.append('V4.1 evidence anchor script missing')
    if not Path(v41,'scripts','experiment_planner.py').exists(): findings.append('V4.1 experiment planner script missing')
    inventory = None
    try:
        probe_dir = Path(path)/'.v41-probe'
        inventory = invoke_v41('inventory', v41, [], probe_dir)
        if inventory.get('status') != 'OK': findings.append('V4.1 read-only inventory adapter failed')
    except DiscoveryError as exc:
        findings.append(str(exc))
    # Validate any supplied anchors/plans without altering V4.1 state.
    for filename,command in [('evidence_index.json','anchor'),('pilot_protocol.json','plan')]:
        try:
            value=read_json(Path(path)/filename)
            if filename=='evidence_index.json' and not isinstance(value,dict): findings.append('Evidence index must be object')
            if filename=='pilot_protocol.json' and not isinstance(value,list): findings.append('Pilot protocol must be list')
        except DiscoveryError as exc: findings.append(str(exc))
    return {'status':'PASS' if not findings else 'CONDITIONAL','findings':findings,
            'v41_inventory_status': inventory.get('status') if inventory else 'NOT_RUN',
            'authority':'V4.1 independently accepts or rejects; this adapter never upgrades evidence'}
