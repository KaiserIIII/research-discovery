"""Structured discovery routes and evidence-gated scientific decisions.

These rules assess supplied, reviewable arguments; they do not prove originality.
"""
from __future__ import annotations
from copy import deepcopy
from itertools import combinations
from .core import DiscoveryError, contained, digest, read_json, sha

ROUTES = {'contradiction','boundary','transfer','failure','mechanism'}
INCREMENTS = {'confirmation','parameter_change','application','boundary_evidence',
              'mechanism','new_capability','scientific_regularities'}
TEXT_FIELDS = ('id','question','significance','ideal_result','claim','prediction','falsifier',
               'pilot','failure_information','followup')

def mine(seed):
    """Generate grounded investigation tasks from extracted observations, not titles."""
    if not isinstance(seed,dict): raise DiscoveryError('Seed must be an object')
    out=[]
    def add(route, question, premises, **extra):
        out.append(dict(id='gap-'+str(len(out)+1), route=route, question=question,
                        premises=premises, status='HOST_REVIEW_REQUIRED', **extra))
    claims=seed.get('claims',[])
    for a,b in combinations(claims,2):
        if a.get('phenomenon') and a.get('phenomenon')==b.get('phenomenon') and a.get('direction')!=b.get('direction'):
            same=bool(a.get('context')) and a.get('context')==b.get('context')
            add('contradiction',f"Why do observations {a.get('id')} and {b.get('id')} disagree on {a['phenomenon']}?",
                [a,b],comparability='COMPARABLE' if same else 'CONFOUNDED',
                experiment='Hold dataset, outcome definition and evaluation protocol fixed; test rival explanations.',
                warning='Direction differences under unmatched conditions are surface contradictions.')
    for claim in claims:
        for assumption in claim.get('assumptions',[]):
            add('boundary',f"When {assumption} fails, which prediction for {claim.get('phenomenon')} changes?",
                [claim],experiment='Intervene on the assumption while retaining the original comparison unit.',
                falsifier='No predicted interaction within the preregistered boundary.')
    for item in seed.get('transfers',[]):
        if not all(item.get(k) for k in ('method','target','basis','failure')):
            raise DiscoveryError('Transfer needs method, target, theoretical basis and failure condition')
        add('transfer',f"Can {item['method']} distinguish explanations for {item['target']}?",[item],
            experiment='Compare the transferred mechanism with its closest existing alternative.',
            warning='Combination or object substitution alone is not a contribution.')
    for item in seed.get('anomalies',[]):
        if not item.get('observation') or not item.get('alternative'): raise DiscoveryError('Anomaly needs a rival')
        add('failure',f"What explains {item['observation']} versus {item['alternative']}?",[item],
            experiment='Retain failed cohort and add a diagnostic control; label new predictions post-hoc.')
    for item in seed.get('mechanisms',[]):
        if not item.get('observation') or len(set(item.get('rivals',[])))<2:
            raise DiscoveryError('Mechanism needs observation and two distinct rivals')
        add('mechanism',f"Which mechanism explains {item['observation']}?",[item],
            experiment='Specify a variable whose predictions differ under the rival mechanisms.',
            causal_status='NOT_IDENTIFIED; require interventions or defended identification assumptions')
    return out

def _evidence(project,eid,allowed=None):
    entry=project.evidence().get(eid)
    if not entry: raise DiscoveryError('Missing evidence: '+str(eid))
    path=contained(project.root,entry['path'])
    if not path.is_file() or sha(path)!=entry['sha256']: raise DiscoveryError('Evidence changed: '+eid)
    if allowed and entry['kind'] not in allowed: raise DiscoveryError('Evidence kind cannot support this claim: '+eid)
    return entry,path

def validate_candidates(project,candidates, minimum=3):
    if not isinstance(candidates,list) or len(candidates)<minimum: raise DiscoveryError('Need at least three competing candidates')
    ids=set(); questions=set(); routes=set()
    for c in candidates:
        if not isinstance(c,dict) or any(not isinstance(c.get(k),str) or not c[k].strip() for k in TEXT_FIELDS):
            raise DiscoveryError('Candidate is missing a substantive text field')
        if c.get('route') not in ROUTES or c.get('increment_kind') not in INCREMENTS:
            raise DiscoveryError('Unknown discovery route or increment category')
        if c['id'] in ids: raise DiscoveryError('Duplicate candidate id')
        question=' '.join(c['question'].lower().split())
        if question in questions: raise DiscoveryError('Duplicate research question')
        if len(set(c.get('rivals',[])))<2: raise DiscoveryError('Two rival explanations required')
        resources=c.get('resources',{})
        for key,cap in (('seconds','total_seconds'),('memory_mb','max_memory_mb'),('disk_mb','max_disk_mb')):
            value=resources.get(key)
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not 0<value<=project.config[cap]:
                raise DiscoveryError('Candidate exceeds resource cap: '+key)
        for eid in c.get('evidence_ids',[]): _evidence(project,eid)
        if not isinstance(c.get('nearest'),list) or not isinstance(c.get('search_ids'),list):
            raise DiscoveryError('Candidate needs nearest and search_ids lists')
        ids.add(c['id']); questions.add(question); routes.add(c['route'])
    if len(routes)<min(3,minimum): raise DiscoveryError('Candidates need different discovery routes')
    return candidates

def assess(project,candidate):
    c=candidate
    result=dict(id=c['id'],status='UNVERIFIED',ideal_result=c['ideal_result'],
                novelty_proven=False,findings=[],prior_art_matrix=[])
    if c['increment_kind'] in {'confirmation','parameter_change','application'}:
        result.update(status='INCREMENTAL_APPLICATION',findings=['Ideal result adds limited stated knowledge; revise the contribution argument.'])
        return result
    if not c.get('search_ids'):
        result['findings'].append('No actual nearest-neighbor search record'); return result
    search_ok=False
    for eid in c['search_ids']:
        try:
            _,path=_evidence(project,eid,{'literature_query'})
            query=read_json(path)
            if query.get('status')=='OK' and query.get('query') and query.get('provider'):
                search_ok=True
            else: result['findings'].append('Unsuccessful/incomplete provider: '+eid)
        except DiscoveryError as exc: result['findings'].append(str(exc))
    if not search_ok or not c.get('nearest'): return result
    relations=[]
    for mapping in c['nearest']:
        try:
            _,path=_evidence(project,mapping['evidence_id'],{'fulltext','public_primary_source'})
            for key in ('conclusion','increment','objection','unresolved','reviewer','quote'):
                if not isinstance(mapping.get(key),str) or not mapping[key].strip(): raise DiscoveryError('Missing prior-art argument: '+key)
            start,end=mapping['lines']; lines=path.read_text(encoding='utf-8').splitlines()
            if not isinstance(start,int) or not isinstance(end,int) or not 1<=start<=end<=len(lines):
                raise DiscoveryError('Exact region outside source')
            quote='\n'.join(lines[start-1:end])
            if mapping['quote'] not in quote: raise DiscoveryError('Quoted evidence not present in exact region')
            if mapping.get('relation') not in {'COVERED','PARTIAL','DISTINCT','CONTRADICTS'}:
                raise DiscoveryError('Unknown nearest-work relation')
            relations.append(mapping['relation'])
            result['prior_art_matrix'].append(dict(claim=c['claim'],**mapping))
        except (DiscoveryError,KeyError,ValueError,TypeError) as exc:
            result['findings'].append(str(exc)); return result
    if relations and all(x=='COVERED' for x in relations):
        result.update(status='COVERED',findings=result['findings']+['Reviewed nearest work already covers the stated ideal-result claim.'])
    elif len(set(c.get('rivals',[])))<2 or not c.get('falsifier'):
        result['findings'].append('No discriminating prediction or rival explanations')
    else:
        result.update(status='PILOT_WORTHY_CONDITIONAL',findings=result['findings']+[
            'Bounded source review leaves a testable increment; no exhaustive novelty proof.',
            'Host reviewer attribution is a recorded assertion, not independent scientific validation.'])
    return result

def compete(project,candidates):
    assessed=[assess(project,c) for c in candidates]
    order={'PILOT_WORTHY_CONDITIONAL':0,'UNVERIFIED':1,'INCREMENTAL_APPLICATION':2,'COVERED':3}
    # Qualitative gates, not a fabricated novelty probability or publication score.
    assessed.sort(key=lambda x:(order[x['status']], x['id']))
    return assessed

def admit(project,candidates,actor):
    validate_candidates(project,candidates)
    if not actor: raise DiscoveryError('Record the actual producing actor')
    key=project.freeze('candidates',candidates)
    result=compete(project,candidates)
    project.record('candidates',dict(snapshot_sha256=key,candidates=candidates,actor=actor,assessments=result))
    return result

def revise(project,candidate,result,new_question):
    if not new_question or new_question==candidate['question']: raise DiscoveryError('Revision needs a new question')
    project.consume('max_rounds',1)
    revised=deepcopy(candidate)
    revised.update(id=candidate['id']+'-r'+str(int(project.config['max_rounds']-project.remaining('max_rounds'))),
                   parent_id=candidate['id'],question=new_question,stage='EXPLORATORY_POST_HOC',
                   trigger=result,search_ids=[],nearest=[])
    project.freeze('revision',revised); project.record('revision',revised)
    return revised

def next_action(project):
    if project.audit(): return dict(action='STOP_INTEGRITY',reason='Evidence or snapshot failed verification')
    if project.remaining('max_rounds')<=0 or project.remaining('total_seconds')<=0:
        return dict(action='STOP_BUDGET',reason='Exploration budget exhausted')
    admitted=project.latest('candidates')
    if not admitted: return dict(action='HOST_REQUIRED',capability='frontier-and-three-candidates')
    rankings=compete(project,admitted['candidates'])
    if all(x['status']=='COVERED' for x in rankings): return dict(action='STOP_COVERED',candidates=rankings)
    if project.remaining('max_pilots')<=0: return dict(action='REVIEW_OR_HANDOFF',reason='Pilot budget exhausted')
    tested={e['payload'].get('candidate_id') for e in project.events() if e['kind']=='pilot_result'}
    selected=next((x for x in rankings if x['status']=='PILOT_WORTHY_CONDITIONAL' and x['id'] not in tested),None)
    if selected: return dict(action='DESIGN_MINIMAL_PILOT',candidate_id=selected['id'],reason=selected['findings'])
    result=project.latest('pilot_result')
    if result: return dict(action='HOST_REQUIRED',capability='surprise-failure-review',result=result,
                           rule='Retain frozen cohort; any new prediction is EXPLORATORY_POST_HOC')
    return dict(action='HOST_REQUIRED',capability='nearest-work-review',candidates=rankings)

def request_host(project,capability,inputs,role='Sol'):
    if role not in {'Sol','Luna','host'} or not capability: raise DiscoveryError('Invalid host request')
    key=project.freeze('host_input',inputs)
    rid='H-'+str(len([e for e in project.events() if e['kind']=='host_request'])+1)
    payload=dict(request_id=rid,capability=capability,input_sha256=key,role=role,
                 status='HOST_REQUIRED',inputs=inputs,
                 output_contract='request_id,input_sha256,actor,model,findings,artifact_ids')
    project.record('host_request',payload)
    return payload


def request_hypotheses(project, domain, context, actor='Sol'):
    """Request host-generated, competing questions with an explicit actor/model.

    The host is a reasoning provider, so this function records the frozen input
    and returns a request. It never fabricates candidate questions locally.
    """
    if not isinstance(domain, str) or not domain.strip():
        raise DiscoveryError('Hypothesis domain must be nonempty')
    if not isinstance(context, list):
        raise DiscoveryError('Hypothesis context must be a list')
    request = request_host(project, 'frontier-and-three-candidates',
                           {'domain': domain, 'context': context}, actor)
    request['actor'] = actor
    request['output_contract'] = ('request_id,input_sha256,actor,model,findings,artifact_ids,'
                                  'candidates[>=3 with distinct routes, rivals, falsifier]')
    return request

def receive_host(project,response):
    request=next((e['payload'] for e in project.events() if e['kind']=='host_request'
                  and e['payload']['request_id']==response.get('request_id')),None)
    if not request or request['input_sha256']!=response.get('input_sha256'): raise DiscoveryError('Unknown or stale host response')
    if any(e['kind']=='host_response' and e['payload']['request_id']==response['request_id'] for e in project.events()):
        raise DiscoveryError('Host request already received')
    for key in ('actor','model','findings','artifact_ids'):
        if key in {'actor','model'}:
            if not isinstance(response.get(key), str) or not response[key].strip():
                raise DiscoveryError('Missing actual host record: '+key)
        elif not isinstance(response.get(key), list):
            raise DiscoveryError('Missing actual host record: '+key)
    for eid in response['artifact_ids']: _evidence(project,eid)
    request_capability = request.get('capability')
    candidates = response.get('candidates')
    if request_capability == 'frontier-and-three-candidates':
        if not isinstance(candidates, list) or len(candidates) < 3:
            raise DiscoveryError('Host must return at least three candidates')
        validate_candidates(project, candidates, minimum=3)
        # Require substantive route and increment diversity beyond duplicate wording.
        if len({c['route'] for c in candidates}) < 3 or len({c['increment_kind'] for c in candidates}) < 3:
            raise DiscoveryError('Host candidates are not materially distinct')
        response = dict(response, candidates=deepcopy(candidates),
                        candidate_status='HOST_GENERATED_REQUIRES_ADMISSION')
        project.freeze('host_candidates', candidates)
    elif candidates is not None:
        raise DiscoveryError('Candidates are only valid for a hypothesis request')
    project.record('host_response',dict(**response,status='RECORDED_NOT_SCIENTIFICALLY_QUALIFIED'))
    return dict(status='RECEIVED', independent_validation=False,
                candidate_count=len(candidates) if isinstance(candidates, list) else 0,
                scientific_status='HOST_GENERATED_REQUIRES_ADMISSION' if candidates is not None else 'RECORDED_NOT_SCIENTIFICALLY_QUALIFIED')
