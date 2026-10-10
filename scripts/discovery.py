#!/usr/bin/env python3
"""Research Discovery V1.0 command line entrypoint."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0,str(Path(__file__).resolve()))
from rd.core import DiscoveryError, Project, doctor, read_json, write_json
from rd.discovery import mine, validate_candidates, admit, next_action, request_host, receive_host
from rd.handoff import export_dossier, validate_dossier, compatibility
from rd.registry import discover as discover_registry
from rd.literature import search as search_literature
from rd.pilot import preregister, run_pilot

def out(value): print(json.dumps(value,ensure_ascii=False,indent=2)); return 0
def parser():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    i=sub.add_parser('init',help='create a private project'); i.add_argument('project',type=Path); i.add_argument('--domain',required=True)
    d=sub.add_parser('doctor',help='probe host resources'); d.add_argument('--root',type=Path,default=Path.cwd())
    m=sub.add_parser('mine',help='create route-separated opportunities from extracted observations'); m.add_argument('input',type=Path); m.add_argument('--output',type=Path,required=True)
    a=sub.add_parser('admit',help='validate and compare at least three candidates'); a.add_argument('project',type=Path); a.add_argument('input',type=Path); a.add_argument('--actor',required=True)
    n=sub.add_parser('next',help='show bounded next action'); n.add_argument('project',type=Path)
    h=sub.add_parser('host-request',help='record work requiring actual host reasoning'); h.add_argument('project',type=Path); h.add_argument('capability'); h.add_argument('input',type=Path); h.add_argument('--role',default='Sol')
    r=sub.add_parser('host-receive',help='record a typed host response'); r.add_argument('project',type=Path); r.add_argument('response',type=Path)
    e=sub.add_parser('export',help='export portable dossier'); e.add_argument('project',type=Path); e.add_argument('output',type=Path)
    v=sub.add_parser('validate',help='validate project or dossier'); v.add_argument('path',type=Path)
    c=sub.add_parser('compatibility',help='read-only V4.1 handoff check'); c.add_argument('dossier',type=Path); c.add_argument('--v41',type=Path,required=True)
    g=sub.add_parser('registry',help='index real skill files without executing them'); g.add_argument('root',type=Path,nargs='+'); g.add_argument('--output',type=Path)
    l=sub.add_parser('search',help='bounded public metadata search'); l.add_argument('project',type=Path); l.add_argument('--provider',required=True,choices=['crossref','openalex','semantic_scholar']); l.add_argument('--query',required=True); l.add_argument('--limit',type=int,default=5); l.add_argument('--public',action='store_true')
    pr=sub.add_parser('pilot-register',help='freeze a pilot protocol before execution'); pr.add_argument('project',type=Path); pr.add_argument('protocol',type=Path)
    px=sub.add_parser('pilot-run',help='run one previously frozen built-in pilot'); px.add_argument('project',type=Path); px.add_argument('protocol',type=Path)
    return p
def main(argv=None):
    args=parser().parse_args(argv)
    try:
        if args.command=='doctor': return out(doctor(args.root))
        if args.command=='init': return out(dict(status='PASS',project=str(Project.create(args.project,args.domain).root)))
        if args.command=='mine': write_json(args.output,mine(read_json(args.input))); return out(dict(status='PASS',output=str(args.output)))
        if args.command=='admit': return out(dict(status='PASS',assessments=admit(Project(args.project),read_json(args.input),'actor:'+args.actor)))
        if args.command=='next': return out(next_action(Project(args.project)))
        if args.command=='host-request': return out(request_host(Project(args.project),args.capability,read_json(args.input),args.role))
        if args.command=='host-receive': return out(receive_host(Project(args.project),read_json(args.response)))
        if args.command=='export': return out(export_dossier(Project(args.project),args.output))
        if args.command=='validate':
            return out(validate_dossier(args.path) if (args.path/'discovery_manifest.json').exists() else dict(status='PASS' if not Project(args.path).audit() else 'FAIL',findings=Project(args.path).audit()))
        if args.command=='compatibility': return out(compatibility(args.dossier,args.v41))
        if args.command=='registry':
            result=discover_registry(args.root)
            if args.output: write_json(args.output,result)
            return out(result)
        if args.command=='search': return out(search_literature(Project(args.project),args.provider,args.query,args.limit,args.public))
        if args.command=='pilot-register': return out(dict(status='PASS',protocol=preregister(Project(args.project),read_json(args.protocol))))
        if args.command=='pilot-run': return out(run_pilot(Project(args.project),read_json(args.protocol)))
    except DiscoveryError as exc:
        print(json.dumps({'status':'ERROR','error':str(exc)},ensure_ascii=False,indent=2)); return 2
    return 2
if __name__=='__main__': sys.exit(main())
