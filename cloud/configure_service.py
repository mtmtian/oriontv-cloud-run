#!/usr/bin/env python3
"""Import public source settings and create a non-admin projector user."""
import argparse
import http.cookiejar
import json
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'cost-guard'))
from config import PROJECT, CONFIG, REPO
from deploy import cli

def secret(name):
    p=subprocess.run(['gcloud','secrets','versions','access','latest','--secret='+name,'--project='+PROJECT],capture_output=True,text=True)
    if p.returncode:raise RuntimeError('Cannot read required secret: '+name)
    return p.stdout

def add_sources(request, sources):
    """Add missing sources; never replace configuration or change existing entries."""
    candidates=sources.get('api_site')
    if not isinstance(candidates,dict) or not candidates:
        raise ValueError('Expected a non-empty api_site object')
    current=request('/api/admin/config')['Config']['SourceConfig']
    by_key={source['key']:source for source in current}
    pending=[]
    for key, source in candidates.items():
        if not isinstance(source,dict) or not all(isinstance(v,str) and v.strip() for v in (key,source.get('name'),source.get('api'))):
            raise ValueError('Every source needs a non-empty key, name and api')
        if not source['api'].startswith('https://'):
            raise ValueError('Source additions require HTTPS')
        if key in by_key:
            if by_key[key]['api'] != source['api']:
                raise ValueError('An existing source key has a different API; no changes made')
            continue
        pending.append({'action':'add','key':key,'name':source['name'],'api':source['api']})
    # Validate the entire batch before the first write. Retry safely skips additions
    # already completed if a later request fails; it never resets existing sources.
    for body in pending:
        if not request('/api/admin/source',body).get('ok'):
            raise RuntimeError('Source addition failed; recheck current configuration before retrying')
    print(f'Added {len(pending)} sources; existing entries and other settings were preserved.')

def configure(additions=None):
    # Discover the trusted service URL instead of sending credentials to a file-supplied URL.
    service=cli('run','services','describe','lunatv',f'--project={PROJECT}',f'--region={CONFIG["region"]}')
    base=service['status']['url']
    assert base.startswith('https://')
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
    parser.add_argument('--add-sources',type=Path,help='Add missing api_site entries from this JSON without replacing other settings')
    configure(parser.parse_args().add_sources)
