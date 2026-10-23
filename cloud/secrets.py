#!/usr/bin/env python3
"""Prompt without echo; send secret values only over the subprocess stdin pipe."""
import getpass
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'cost-guard'))
from config import PROJECT
from deploy import cli

def setup():
    for name,label,runtime in [
        ('lunatv-admin-password','New administrator password',True),
        ('lunatv-upstash-url','Upstash Redis REST URL',True),
        ('lunatv-upstash-token','Upstash Redis REST token',True),
        ('lunatv-tv-password','New projector user password',False),
    ]:
        # Existing values are kept; rotating credentials is a separate explicit operation.
        existing=cli('secrets','describe',name,f'--project={PROJECT}',optional=True)
        versions=cli('secrets','versions','list',name,f'--project={PROJECT}','--sort-by=~createTime','--limit=1') if existing else []
        if versions and versions[0].get('state') != 'ENABLED':
            raise RuntimeError(f'{name}: newest version is not enabled; resolve explicitly before deployment')
        if not versions:
            value=getpass.getpass(label+': ')
            if not value:raise ValueError('Empty value rejected')
            if existing is None:cli('secrets','create',name,f'--project={PROJECT}','--replication-policy=automatic')
            done=subprocess.run(['gcloud','secrets','versions','add',name,f'--project={PROJECT}','--data-file=-','--quiet'],input=value,text=True,capture_output=True)
            del value
            if done.returncode:raise RuntimeError(f'Could not store {name}; inspect Secret Manager metadata')
        if runtime:
            cli('secrets','add-iam-policy-binding',name,f'--project={PROJECT}',f'--member=serviceAccount:lunatv-runtime@{PROJECT}.iam.gserviceaccount.com','--role=roles/secretmanager.secretAccessor')
        print(name+': ready (value hidden)')
if __name__=='__main__':setup()
