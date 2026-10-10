"""Durable local state. Integrity checks are not signatures or scientific proof."""
from __future__ import annotations
import hashlib
import json
import math
import os
import platform
import shutil
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_CONFIG = dict(max_pilots=3, max_rounds=3, total_seconds=120,
                      network_requests=20, max_download_bytes=8_000_000,
                      max_memory_mb=512, max_disk_mb=32, max_cpu_seconds=30)

class DiscoveryError(RuntimeError):
    pass

def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''): h.update(block)
    return h.hexdigest()

def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'),
                          parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except (OSError, ValueError) as exc:
        raise DiscoveryError('Invalid or missing JSON: ' + str(path)) from exc

def write_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.' + os.urandom(6).hex() + '.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8') + b'\n')
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

def contained(root, relative):
    root = Path(root).resolve(); path = (root / relative).resolve()
    if not path.is_relative_to(root): raise DiscoveryError('Path escapes project')
    return path

@contextmanager
def lock(root):
    path = Path(root)/'.write.lock'
    try: handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc: raise DiscoveryError('Project is locked; inspect stale writer before recovery') from exc
    try:
        os.write(handle, str(os.getpid()).encode()); os.close(handle)
        yield
    finally: path.unlink(missing_ok=True)

def validate_config(patch):
    if not isinstance(patch, dict) or set(patch)-set(DEFAULT_CONFIG): raise DiscoveryError('Unknown config fields')
    result = DEFAULT_CONFIG | patch
    for key, value in result.items():
        if isinstance(value, bool) or not isinstance(value, (int,float)) or not math.isfinite(value) or value <= 0:
            raise DiscoveryError('Budget must be finite and positive: ' + key)
        if key in {'max_pilots','max_rounds','network_requests','max_download_bytes'} and not isinstance(value,int):
            raise DiscoveryError('Count budget must be integer: ' + key)
    return result

class Project:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.manifest = read_json(self.root/'project.json')
        if self.manifest.get('schema_version') != '1.0': raise DiscoveryError('Unsupported project schema')
        self.config = validate_config(self.manifest['config'])
        events = self.events()
        if not events or events[0]['kind'] != 'init' or events[0]['payload']['manifest_sha256'] != digest(self.manifest):
            raise DiscoveryError('Project manifest differs from initialization')

    @classmethod
    def create(cls, root, domain, config=None):
        if not isinstance(domain,str) or not domain.strip(): raise DiscoveryError('Domain must be nonempty')
        cfg = validate_config(config or {})
        root=Path(root).resolve()
        if root.exists() and any(root.iterdir()): raise DiscoveryError('Refusing to overwrite project')
        root.mkdir(parents=True, exist_ok=True)
        manifest=dict(schema_version='1.0', version='1.0.0', domain=domain, created_utc=now(), config=cfg)
        write_json(root/'project.json', manifest)
        for name in ('evidence','snapshots','runs','host'): (root/name).mkdir()
        instance=object.__new__(cls); instance.root=root; instance.config=cfg; instance.manifest=manifest
        instance.record('init',dict(manifest_sha256=digest(manifest)))
        return cls(root)

    def events(self):
        path=self.root/'events.jsonl'
        if not path.exists(): return []
        events=[]; previous='0'*64
        try:
            for line in path.read_text(encoding='utf-8').splitlines():
                item=json.loads(line); claimed=item.pop('hash')
                if item['seq'] != len(events)+1 or item['previous'] != previous or digest(item) != claimed:
                    raise DiscoveryError('Journal integrity failure')
                item['hash']=claimed; events.append(item); previous=claimed
        except (ValueError,KeyError) as exc: raise DiscoveryError('Corrupt journal; preserve original before repair') from exc
        return events

    def _append(self, kind, payload):
        events=self.events()
        item=dict(seq=len(events)+1, utc=now(), kind=kind, payload=payload,
                  previous=events[-1]['hash'] if events else '0'*64)
        item['hash']=digest(item)
        with (self.root/'events.jsonl').open('ab') as stream:
            stream.write(canonical(item)+b'\n'); stream.flush(); os.fsync(stream.fileno())
        return item

    def record(self,kind,payload):
        with lock(self.root): return self._append(kind,payload)

    def latest(self,kind,default=None):
        return next((e['payload'] for e in reversed(self.events()) if e['kind']==kind),default)

    def freeze(self,kind,data):
        key=digest(data); path=self.root/'snapshots'/(key+'.json')
        with lock(self.root):
            if not path.exists(): write_json(path,data)
            elif digest(read_json(path)) != key: raise DiscoveryError('Snapshot integrity failure')
            self._append('snapshot',dict(kind=kind,sha256=key,path=str(path.relative_to(self.root)).replace('\\','/')))
        return key

    def evidence(self):
        return {e['payload']['id']:e['payload'] for e in self.events() if e['kind']=='evidence'}

    def add_evidence(self,path,origin,kind):
        source=Path(path)
        if not source.is_file() or not origin or not kind: raise DiscoveryError('Evidence needs a real file, origin and kind')
        if source.stat().st_size > self.config['max_download_bytes']: raise DiscoveryError('Evidence file exceeds size cap')
        key=sha(source); eid='E-'+key[:20]
        suffix=source.suffix.lower() if len(source.suffix)<=10 else '.bin'
        target=self.root/'evidence'/(key+suffix)
        with lock(self.root):
            old=self.evidence().get(eid)
            if old:
                if sha(contained(self.root,old['path'])) != key: raise DiscoveryError('Existing evidence tampered')
                return eid
            if target.exists() and sha(target)!=key: raise DiscoveryError('Evidence target tampered')
            shutil.copyfile(source,target)
            if sha(target)!=key: raise DiscoveryError('Evidence source changed during acquisition')
            entry=dict(id=eid,path=str(target.relative_to(self.root)).replace('\\','/'),sha256=key,
                       bytes=target.stat().st_size,origin=origin,kind=kind,acquired_utc=now())
            self._append('evidence',entry)
        return eid

    def remaining(self,resource):
        if resource not in self.config: raise DiscoveryError('Unknown budget')
        return self.config[resource]-sum(e['payload']['amount'] for e in self.events()
                                      if e['kind']=='budget' and e['payload']['resource']==resource)

    def consume(self,resource,amount):
        if isinstance(amount,bool) or not isinstance(amount,(int,float)) or not math.isfinite(amount) or amount<0:
            raise DiscoveryError('Invalid budget amount')
        with lock(self.root):
            if amount>self.remaining(resource): raise DiscoveryError('Budget exhausted: '+resource)
            return self._append('budget',dict(resource=resource,amount=amount))

    def audit(self):
        errors=[]
        for e in self.events():
            if e['kind'] not in {'evidence','snapshot'}: continue
            item=e['payload']
            try:
                path=contained(self.root,item['path'])
                actual=sha(path) if e['kind']=='evidence' else digest(read_json(path))
                if actual != item['sha256']: errors.append('Hash mismatch: '+item['path'])
            except (OSError,DiscoveryError): errors.append('Missing/invalid artifact: '+item['path'])
        return errors

def doctor(root=None):
    import subprocess
    root=Path(root or Path.cwd()); disk=shutil.disk_usage(root)
    gpu=[]
    tool=shutil.which('nvidia-smi')
    if tool:
        try:
            result=subprocess.run([tool,'--query-gpu=name,memory.total,memory.free','--format=csv,noheader'],
                                  capture_output=True,text=True,timeout=4)
            if result.returncode==0: gpu=result.stdout.strip().splitlines()
        except (OSError,subprocess.TimeoutExpired): pass
    return dict(python=sys.version,executable=sys.executable,platform=platform.platform(),
                cpu_count=os.cpu_count(),disk_free_bytes=disk.free,gpu=gpu,
                gpu_used=False,determinism='Seeded stdlib CPU; cross-version floating point not guaranteed')
