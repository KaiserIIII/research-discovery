"""Export and validate a portable Discovery Dossier for CS Nature Paper V4.1."""
from __future__ import annotations
import json
import subprocess
import sys
import shutil
import urllib.parse
from pathlib import Path
from .core import DiscoveryError, Project, contained, digest, read_json, sha, write_json
from .registry import invoke_v41

FILES = ('discovery_manifest.json','hypotheses.json','prior_art_matrix.md','pilot_protocol.json',
         'pilot_results.json','evidence_index.json','rival_explanations.md','limitations.md',
         'discovery_dossier.md','handoff_to_v4_1.md')
PORTABLE_EVIDENCE_LIMIT = 4 * 1024 * 1024

def _safe_text(value):
    return str(value).replace('\r','').replace('\x00','')

def export_dossier(project: Project, output: Path):
    if project.audit(): raise DiscoveryError('Cannot export a tampered project')
    output=Path(output).resolve()
    if output.exists() and any(output.iterdir()): raise DiscoveryError('Refusing to overwrite dossier')
    output.mkdir(parents=True,exist_ok=True)
    events=project.events(); evidence=project.evidence()
    candidate_event=project.latest('candidates') or {}
    if not candidate_event:
        host_event = project.latest('host_response') or {}
        if isinstance(host_event.get('candidates'), list):
            candidate_event = dict(candidates=host_event['candidates'], assessments=[],
                                  snapshot_sha256=digest(host_event['candidates']))
    pilot_events=[e['payload'] for e in events if e['kind']=='pilot_result']
    protocols=[e['payload'] for e in events if e['kind']=='pilot_registered']
    assessments=candidate_event.get('assessments',[])
    hypotheses=[dict(item,assessment=next((a for a in assessments if a.get('id')==item.get('id')),None))
                for item in candidate_event.get('candidates',[])]
    prior=[]
    for assessment in assessments: prior.extend(assessment.get('prior_art_matrix',[]))
    index={}
    portability=[]
    evidence_dir=output/'evidence'; evidence_dir.mkdir(parents=True,exist_ok=True)
    for evidence_id, value in evidence.items():
        item=dict(value)
        try:
            source_path=contained(project.root,item['path'])
            if not source_path.is_file() or sha(source_path)!=item['sha256']:
                raise DiscoveryError('missing or changed source evidence')
            if source_path.stat().st_size <= PORTABLE_EVIDENCE_LIMIT:
                target=evidence_dir/(item['sha256']+source_path.suffix.lower())
                if not target.exists(): shutil.copyfile(source_path,target)
                if sha(target)!=item['sha256']: raise DiscoveryError('portable copy hash mismatch')
                item.update(portable=True,portable_path='evidence/'+target.name,
                            portability_status='EMBEDDED_CONTENT_ADDRESSED')
            else:
                item.update(portable=False,portability_status='STABLE_REFERENCE_REQUIRED',
                            portability_reason='artifact exceeds portable evidence size limit')
        except (OSError,DiscoveryError) as exc:
            item.update(portable=False,portability_status='INCOMPLETE',portability_reason=str(exc))
        index[evidence_id]=item
        portability.append({'evidence_id':evidence_id,'portable':item['portable'],'status':item['portability_status']})
    manifest=dict(schema_version='1.0',skill_version='1.0.1',project_schema='1.0',
                  exported_utc=project.manifest['created_utc'],domain=project.manifest['domain'],
                  stage_labels=['DISCOVERY','PILOT','EXPLORATORY_POST_HOC'],
                  scientific_status='EXPLORATORY_HANDOFF_REQUIRES_V4_1_REVIEW',
                  audit_findings=[],evidence_count=len(evidence),event_count=len(events),
                  evidence_portability=portability,
                  candidate_snapshot=candidate_event.get('snapshot_sha256'))
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
    index={}
    try:
        index=read_json(path/'evidence_index.json')
        if not isinstance(index,dict): findings.append('Evidence index must be an object'); index={}
        for evidence_id,item in index.items():
            if not isinstance(item,dict): findings.append(f'Invalid evidence entry {evidence_id}'); continue
            if item.get('portable'):
                try:
                    artifact=contained(path,item.get('portable_path',''))
                    if not artifact.is_file() or sha(artifact)!=item.get('sha256'):
                        findings.append(f'Portable evidence hash mismatch {evidence_id}')
                except DiscoveryError: findings.append(f'Portable evidence path escapes dossier {evidence_id}')
            elif item.get('portability_status') not in {'STABLE_REFERENCE_REQUIRED','INCOMPLETE'}:
                findings.append(f'Unclassified nonportable evidence {evidence_id}')
            elif item.get('portability_status')=='STABLE_REFERENCE_REQUIRED':
                parsed = urllib.parse.urlparse(str(item.get('origin','')))
                if parsed.scheme not in {'https', 'http'} or not parsed.hostname or parsed.username or parsed.password:
                    findings.append(f'Nonportable evidence has no stable URI {evidence_id}')
    except DiscoveryError as exc: findings.append(str(exc))
    portable_count=sum(1 for item in index.values() if isinstance(item,dict) and item.get('portable'))
    evidence_count=len(index)
    completeness='COMPLETE_PORTABLE' if portable_count==evidence_count else ('PARTIAL_EXTERNAL' if evidence_count else 'COMPLETE_PORTABLE')
    return {'status':'PASS' if not findings else 'FAIL','findings':findings,'files':len(FILES),
            'evidence_completeness':completeness,'portable_evidence':portable_count,
            'evidence_count':evidence_count}

def compatibility(path: Path, v41: Path):
    result=validate_dossier(path); findings=list(result.get('findings',[]))
    format_status = 'FORMAT_COMPATIBLE' if result.get('status') == 'PASS' else 'FORMAT_INVALID'
    if not Path(v41,'scripts','evidence_anchor.py').exists(): findings.append('V4.1 evidence anchor script missing')
    if not Path(v41,'scripts','experiment_planner.py').exists(): findings.append('V4.1 experiment planner script missing')
    inventory = None
    admission_probe = None
    try:
        probe_dir = Path(path)/'.v41-probe'
        inventory = invoke_v41('inventory', v41, [], probe_dir)
        if inventory.get('status') != 'OK': findings.append('V4.1 read-only inventory adapter failed')
        admission_probe = invoke_v41('research_state', v41, [], probe_dir)
        if admission_probe.get('status') != 'OK': findings.append('V4.1 research-state admission probe failed')
    except DiscoveryError as exc:
        findings.append(str(exc))
    # Validate any supplied anchors/plans without altering V4.1 state.
    for filename,command in [('evidence_index.json','anchor'),('pilot_protocol.json','plan')]:
        try:
            value=read_json(Path(path)/filename)
            if filename=='evidence_index.json' and not isinstance(value,dict): findings.append('Evidence index must be object')
            if filename=='pilot_protocol.json' and not isinstance(value,list): findings.append('Pilot protocol must be list')
        except DiscoveryError as exc: findings.append(str(exc))
    tools_status = 'TOOLS_VERIFIED' if inventory and inventory.get('status') == 'OK' and admission_probe and admission_probe.get('status') == 'OK' and not any(
        item.startswith('V4.1') for item in findings) else 'TOOLS_UNVERIFIED'
    # V4.1 has no machine-facing scientific admission endpoint in this release.
    # Keep the handoff explicit so format/tool success cannot be mistaken for
    # a scientific acceptance decision.
    scientific_status = 'SCIENTIFIC_REVIEW_REQUIRED'
    admission = 'NEEDS_EVIDENCE' if findings or result.get('evidence_completeness') != 'COMPLETE_PORTABLE' else 'SCIENTIFIC_REVIEW_REQUIRED'
    return {'status':'PASS' if not findings else 'CONDITIONAL','findings':findings,
            'format_compatibility': format_status,
            'tool_verification': tools_status,
            'scientific_review': scientific_status,
            'admission_decision': admission,
            'v41_inventory_status': inventory.get('status') if inventory else 'NOT_RUN',
            'v41_admission_probe_status': admission_probe.get('status') if admission_probe else 'NOT_RUN',
            'v41_admission_probe': admission_probe,
            'authority':'V4.1 independently accepts or rejects; this adapter never upgrades evidence'}
