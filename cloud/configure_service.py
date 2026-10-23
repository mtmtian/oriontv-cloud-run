#!/usr/bin/env python3
"""Import public source settings and create a non-admin projector user."""
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

def configure():
    saved=json.loads((REPO/'.local/service.json').read_text())
    base=saved['service_url']
    # Discover the trusted service URL instead of sending credentials to a user-entered URL.
    service=cli('run','services','describe','lunatv',f'--project={PROJECT}',f'--region={CONFIG["region"]}')
    assert base==service['status']['url'] and base.startswith('https://')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    client=urllib.request.build_opener(NoRedirect(),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    def request(path,data=None):
        req=urllib.request.Request(base+path,data=None if data is None else json.dumps(data).encode(),headers={'Content-Type':'application/json'})
        try:
            with client.open(req,timeout=65) as response:return json.load(response)
        except urllib.error.HTTPError as e:raise RuntimeError(f'{path.split("?")[0]} returned HTTP {e.code}') from None
    assert request('/api/login',{'username':CONFIG['admin_username'],'password':secret('lunatv-admin-password')}).get('ok')
    # Use an ignored local copy for private sources/subscriptions.
    source_path=REPO/'.local/sources.json'
    sources=json.loads((source_path if source_path.exists() else REPO/'cloud/sources.example.json').read_text())
    assert request('/api/admin/config_file',{'configFile':json.dumps(sources,ensure_ascii=False),'subscriptionUrl':'','autoUpdate':False,'lastCheckTime':''}).get('success')
    config=request('/api/admin/config')['Config']
    if not any(u['username']=='projector' for u in config['UserConfig']['Users']):
        request('/api/admin/user',{'action':'add','targetUsername':'projector','targetPassword':secret('lunatv-tv-password')})
    print('Source settings imported; projector user exists. Credentials were not printed or saved locally.')
if __name__=='__main__':configure()
