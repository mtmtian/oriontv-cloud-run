#!/usr/bin/env python3
"""Read-only resource check plus workflow billing-readiness execution (no mutation)."""
import json
from config import PROJECT, REGION, EXPIRY, render_workflow
from deploy import cli
from test_guard import execution

def check():
    workflow=cli('workflows','describe','jmgo-tv-cost-guard',f'--project={PROJECT}',f'--location={REGION}')
    assert workflow['sourceContents']==render_workflow().read_text(), 'Deployed workflow differs from local template'
    result,_=execution({'action':'billing-check'})
    assert result['expiryUtc']==EXPIRY
    jobs={n:cli('scheduler','jobs','describe',n,f'--project={PROJECT}',f'--location={REGION}')['state'] for n in ['jmgo-tv-daily-reconcile','jmgo-tv-expiry']}
    print(json.dumps({'workflowState':workflow['state'],'billingReadiness':result,'jobs':jobs},indent=2))
if __name__=='__main__':check()
