#!/usr/bin/env python3
"""Create a private image repository, runtime/build identities and source bucket."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'cost-guard'))
from config import PROJECT, REGION
from deploy import cli

def setup():
    cli('services','enable','run.googleapis.com','artifactregistry.googleapis.com','cloudbuild.googleapis.com',
        'secretmanager.googleapis.com','iam.googleapis.com','cloudbilling.googleapis.com',f'--project={PROJECT}')
    if cli('artifacts','repositories','describe','home-tv',f'--project={PROJECT}',f'--location={REGION}',optional=True) is None:
        cli('artifacts','repositories','create','home-tv',f'--project={PROJECT}',f'--location={REGION}','--repository-format=docker')
    for name in ['lunatv-runtime','lunatv-builder']:
        address=f'{name}@{PROJECT}.iam.gserviceaccount.com'
        if cli('iam','service-accounts','describe',address,f'--project={PROJECT}',optional=True) is None:
            cli('iam','service-accounts','create',name,f'--project={PROJECT}')
    builder=f'serviceAccount:lunatv-builder@{PROJECT}.iam.gserviceaccount.com'
    cli('artifacts','repositories','add-iam-policy-binding','home-tv',f'--project={PROJECT}',f'--location={REGION}',f'--member={builder}','--role=roles/artifactregistry.writer')
    cli('projects','add-iam-policy-binding',PROJECT,f'--member={builder}','--role=roles/logging.logWriter','--condition=None')
    bucket=f'gs://{PROJECT}-home-tv-build'
    if cli('storage','buckets','describe',bucket,f'--project={PROJECT}',optional=True) is None:
        cli('storage','buckets','create',bucket,f'--project={PROJECT}',f'--location={REGION}','--uniform-bucket-level-access')
    cli('storage','buckets','add-iam-policy-binding',bucket,f'--member={builder}','--role=roles/storage.objectViewer')
    print('Image repository, build bucket and scoped service accounts ready')
if __name__=='__main__':setup()
