#!/usr/bin/env python3
"""Create/reconcile the two USD5 budgets in the dedicated project."""
import json
from deploy import api, cli
from config import PROJECT, REGION, ACCOUNT, STATE, STATE_PATH

def setup():
    cli('services','enable','cloudbilling.googleapis.com','billingbudgets.googleapis.com',
        'cloudresourcemanager.googleapis.com','run.googleapis.com','workflows.googleapis.com',
        'workflowexecutions.googleapis.com','eventarc.googleapis.com','pubsub.googleapis.com',
        'cloudscheduler.googleapis.com','iam.googleapis.com',f'--project={PROJECT}')
    billing=api('GET',f'https://cloudbilling.googleapis.com/v1/projects/{PROJECT}/billingInfo')
    assert billing.get('billingEnabled') and billing.get('billingAccountName')==f'billingAccounts/{ACCOUNT}', 'Billing account mismatch'
    project=cli('projects','describe',PROJECT)
    project_filter=['projects/'+str(project['projectNumber'])]
    if cli('pubsub','topics','describe','jmgo-tv-budget',f'--project={PROJECT}',optional=True) is None:
        cli('pubsub','topics','create','jmgo-tv-budget',f'--project={PROJECT}')
    endpoint=f'https://billingbudgets.googleapis.com/v1/billingAccounts/{ACCOUNT}/budgets'
    budgets=[];page=''
    while True:
        result=api('GET',endpoint+('?pageToken='+page if page else ''))
        budgets.extend(result.get('budgets',[]));page=result.get('nextPageToken','')
        if not page:break
    for key,title,native in [('budget_id','Home TV project USD5',False),('native_cap_id','Home TV Cloud Run USD5 cap',True)]:
        spec={'displayName':title,'budgetFilter':{'projects':project_filter,'calendarPeriod':'MONTH','creditTypesTreatment':'EXCLUDE_ALL_CREDITS'},'amount':{'specifiedAmount':{'currencyCode':'USD','units':'5'}}}
        if native:
            spec['budgetFilter']['services']=['services/152E-C115-5142']
            spec['spendCap']={}
            spec['thresholdRules']=[{'thresholdPercent':v,'spendBasis':'CURRENT_SPEND'} for v in [.5,.8,1]]
            spec['notificationsRule']={'enableProjectLevelRecipients':True}
        else:
            spec['thresholdRules']=[]
            spec['notificationsRule']={'disableDefaultIamRecipients':True,'pubsubTopic':f'projects/{PROJECT}/topics/jmgo-tv-budget','schemaVersion':'1.0'}
        matches=[b for b in budgets if b['budgetFilter'].get('projects')==project_filter and (b.get('displayName')==title or b['name'].endswith('/'+STATE.get(key,'__none__')))]
        assert len(matches)<=1,'Ambiguous budgets: inspect the billing console'
        if matches:
            existing=matches[0];spec['etag']=existing['etag']
            mask='displayName,budgetFilter,amount,thresholdRules,notificationsRule'+(',spendCap' if native else '')
            saved=api('PATCH','https://billingbudgets.googleapis.com/v1/'+existing['name']+'?updateMask='+mask,spec)
        else:saved=api('POST',endpoint,spec)
        STATE[key]=saved['name'].rsplit('/',1)[1]
        STATE_PATH.write_text(json.dumps(STATE,indent=2)+'\n')
        if native:assert saved.get('spendCap',{}).get('outputState') in ('CONFIGURED','PENDING'), 'Native cap was not accepted'
        print(title+' configured')
if __name__=='__main__':setup()
