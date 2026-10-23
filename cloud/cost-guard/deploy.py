#!/usr/bin/env python3
"""Idempotent resource setup for the dedicated TV project; no credential files."""
import json, pathlib, subprocess, urllib.request, urllib.error
ROOT = pathlib.Path(__file__).resolve().parent
from config import PROJECT, REGION, ACCOUNT, BUDGET, RUNTIME, INVOKER, EXPIRY, STATE_DIR, render_workflow
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

def cli(*args, optional=False):
    p=subprocess.run(['gcloud', *args, '--quiet', '--format=json'], text=True,capture_output=True)
    if p.returncode:
        if optional and ('NOT_FOUND' in p.stderr or 'does not exist' in p.stderr): return None
        raise RuntimeError(p.stderr)
    return json.loads(p.stdout) if p.stdout.strip() else {}

def api(method,url,data=None):
    token=subprocess.check_output(['gcloud','auth','print-access-token'],text=True).strip()
    req=urllib.request.Request(url,method=method,data=None if data is None else json.dumps(data).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json','x-goog-user-project':PROJECT})
    try:
        with urllib.request.urlopen(req,timeout=60) as r: return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'{e.code}: {e.read().decode()}') from None

def setup():
    assert datetime.now(timezone.utc) < datetime.fromisoformat(EXPIRY.replace('Z','+00:00')), 'Deadline is past: choose a future deadline before deploying'
    billing=api('GET',f'https://cloudbilling.googleapis.com/v1/projects/{PROJECT}/billingInfo')
    assert billing.get('billingEnabled') and billing.get('billingAccountName') == f'billingAccounts/{ACCOUNT}', 'Billing account does not match the target project'
    workflow_path=render_workflow()
    for name, desc in [('tv-cost-guard','TV cost guard runtime'),('tv-guard-trigger','TV cost guard invocation')]:
        if cli('iam','service-accounts','describe',f'{name}@{PROJECT}.iam.gserviceaccount.com',f'--project={PROJECT}',optional=True) is None:
            cli('iam','service-accounts','create',name,f'--display-name={desc}',f'--project={PROJECT}')
    print('Service accounts ready',flush=True)
    from configure_iam import configure
    configure()
    cli('run','services','add-iam-policy-binding','lunatv',f'--project={PROJECT}',f'--region={REGION}',f'--member=serviceAccount:{RUNTIME}',f'--role=projects/{PROJECT}/roles/tvRunScaleGuard')
    print('Scoped runtime roles ready',flush=True)
    cli('workflows','deploy','jmgo-tv-cost-guard',f'--project={PROJECT}',f'--location={REGION}',f'--source={workflow_path}',f'--service-account={RUNTIME}','--call-log-level=log-none',f'--description=USD5 monthly guard; project billing unlink after {EXPIRY}')
    print('Workflow deployed',flush=True)
    if cli('pubsub','topics','describe','jmgo-tv-budget',f'--project={PROJECT}',optional=True) is None:
        cli('pubsub','topics','create','jmgo-tv-budget',f'--project={PROJECT}')
    # Billing Budgets API grants its managed publisher when linking the topic.
    if cli('eventarc','triggers','describe','jmgo-tv-budget',f'--project={PROJECT}',f'--location={REGION}',optional=True) is None:
        cli('eventarc','triggers','create','jmgo-tv-budget',f'--project={PROJECT}',f'--location={REGION}','--destination-workflow=jmgo-tv-cost-guard',f'--destination-workflow-location={REGION}','--event-filters=type=google.cloud.pubsub.topic.v1.messagePublished','--transport-topic=jmgo-tv-budget',f'--service-account={INVOKER}')
    print('Budget event transport ready',flush=True)
    uri=f'https://workflowexecutions.googleapis.com/v1/projects/{PROJECT}/locations/{REGION}/workflows/jmgo-tv-cost-guard/executions'
    expiry_local=datetime.fromisoformat(EXPIRY.replace('Z','+00:00')).astimezone(ZoneInfo('Asia/Taipei'))
    assert expiry_local.minute == 0 and expiry_local.second == 0, 'Expiry must fall on an hour'
    expiry_schedule=f'0 * {expiry_local.day} {expiry_local.month} *'
    for name,schedule,tz in [('jmgo-tv-daily-reconcile','10 0 * * *','America/Los_Angeles'),('jmgo-tv-expiry',expiry_schedule,'Asia/Taipei')]:
        existing=cli('scheduler','jobs','describe',name,f'--project={PROJECT}',f'--location={REGION}',optional=True)
        cli('scheduler','jobs','create' if existing is None else 'update','http',name,f'--project={PROJECT}',f'--location={REGION}',f'--schedule={schedule}',f'--time-zone={tz}',f'--uri={uri}','--http-method=POST','--headers=Content-Type=application/json',f'--oauth-service-account-email={INVOKER}','--message-body='+json.dumps({'argument':json.dumps({'action':'reconcile'})}),'--max-retry-attempts=5','--max-retry-duration=3600s','--min-backoff=30s','--max-backoff=300s')
    print('Recovery and expiry schedules ready',flush=True)
    url=f'https://billingbudgets.googleapis.com/v1/billingAccounts/{ACCOUNT}/budgets/{BUDGET}'
    budget=api('GET',url)
    budget['budgetFilter']['creditTypesTreatment']='EXCLUDE_ALL_CREDITS'
    budget['notificationsRule']={'disableDefaultIamRecipients':True,'pubsubTopic':f'projects/{PROJECT}/topics/jmgo-tv-budget','schemaVersion':'1.0'}
    budget['thresholdRules']=[]
    updated=api('PATCH',url+'?updateMask=budgetFilter,notificationsRule,thresholdRules',budget)
    (STATE_DIR/'project-budget.json').write_text(json.dumps(updated,indent=2)+'\n')
    print('Project-wide budget linked',flush=True)
if __name__=='__main__': setup()
