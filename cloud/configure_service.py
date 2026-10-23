#!/usr/bin/env python3
"""Import public source settings and create a non-admin projector user."""
import argparse
import http.cookiejar
import json
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'cost-guard'))
from config import PROJECT, CONFIG, REPO
from deploy import cli

def secret(name):
    p=subprocess.run(['gcloud','secrets','versions','access','latest','--secret='+name,'--project='+PROJECT],capture_output=True,text=True)
    if p.returncode:raise RuntimeError('Cannot read required secret: '+name)
    return p.stdout

# api_site and lives use different admin endpoints, link fields and success flags.
KINDS=[('api_site','SourceConfig','api','/api/admin/source','ok'),
       ('lives','LiveConfig','url','/api/admin/live','success')]

def add_sources(request, sources):
    """Add missing VOD and live sources; never replace configuration or change existing entries."""
    kinds=[kind for kind in KINDS if sources.get(kind[0]) is not None]
    if not kinds or any(not isinstance(sources[kind[0]],dict) or not sources[kind[0]] for kind in kinds):
        raise ValueError('Expected a non-empty api_site or lives object')
    config=request('/api/admin/config')['Config']
    pending=[]
    for field,section,link,path,flag in kinds:
        by_key={item['key']:item for item in config.get(section) or []}
        for key, source in sources[field].items():
            if not isinstance(source,dict) or not all(isinstance(v,str) and v.strip() for v in (key,source.get('name'),source.get(link))):
                raise ValueError(f'Every {field} entry needs a non-empty key, name and {link}')
            if not source[link].startswith('https://'):
                raise ValueError('Source additions require HTTPS')
            if key in by_key:
                if by_key[key][link] != source[link]:
                    raise ValueError(f'An existing {field} key has a different {link}; no changes made')
                continue
            body={'action':'add','key':key,'name':source['name'],link:source[link]}
            body.update({k:source[k] for k in ('ua','epg') if field=='lives' and source.get(k)})
            pending.append((field,path,flag,body))
    # Validate the entire batch before the first write. Retry safely skips additions
    # already completed if a later request fails; it never resets existing sources.
    for field,path,flag,body in pending:
        if not request(path,body).get(flag):
            raise RuntimeError('Source addition failed; recheck current configuration before retrying')
    added=', '.join(f'{sum(p[0]==field for p in pending)} {field}' for field,*_ in kinds)
    print(f'Added {added} entries; existing entries and other settings were preserved.')

def service_url():
    # Discover the trusted service URL instead of sending credentials to a file-supplied URL.
    service=cli('run','services','describe','lunatv',f'--project={PROJECT}',f'--region={CONFIG["region"]}')
    base=service['status']['url']
    assert base.startswith('https://')
    return base

def configure(additions=None):
    base=service_url()
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    client=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def request(path,data=None):
        req=urllib.request.Request(base+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
        try:
            with client.open(req,timeout=65) as response:return json.load(response)
        except urllib.error.HTTPError as e:raise RuntimeError(f'{path.split("?")[0]} returned HTTP {e.code}') from None
    assert request('/api/login',{'username':CONFIG['admin_username'],'password':secret('lunatv-admin-password')}).get('ok')
    if additions is not None:
        add_sources(request,json.loads(additions.read_text()))
        return
    # Use an ignored local copy for private sources/subscriptions.
    source_path=REPO/'.local/sources.json'
    sources=json.loads((source_path if source_path.exists() else REPO/'cloud/sources.example.json').read_text())
    assert request('/api/admin/config_file',{'configFile':json.dumps(sources,ensure_ascii=False),'subscriptionUrl':'','autoUpdate':False,'lastCheckTime':''}).get('success')
    config=request('/api/admin/config')['Config']
    if not any(u['username']=='projector' for u in config['UserConfig']['Users']):
        request('/api/admin/user',{'action':'add','targetUsername':'projector','targetPassword':secret('lunatv-tv-password')})
    print('Source settings imported; projector user exists. Credentials were not printed or saved locally.')
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group()
    mode.add_argument('--add-sources',type=Path,help='Add missing api_site and lives entries from this JSON without replacing other settings')
    mode.add_argument('--live-url',action='store_true',help='Print the merged live playlist URL for OrionTV; it contains an access token')
    args=parser.parse_args()
    if args.live_url:
        print(service_url()+'/api/live/playlist?token='+urllib.parse.quote(secret('lunatv-live-token').strip()))
    else:
        configure(args.add_sources)
