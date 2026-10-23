#!/usr/bin/env python3
"""Exercise deployed decision logic without changing any cloud resources."""
import base64, concurrent.futures, copy, datetime, json, time
from deploy import api, PROJECT, REGION, ACCOUNT, BUDGET
from config import STATE_DIR, EXPIRY
ENDPOINT=f'https://workflowexecutions.googleapis.com/v1/projects/{PROJECT}/locations/{REGION}/workflows/jmgo-tv-cost-guard/executions'

def event(cost=5, start='2026-10-01T07:00:00Z'):
    data={'costAmount':cost,'costIntervalStart':start,'budgetAmount':5,'budgetAmountType':'SPECIFIED_AMOUNT','currencyCode':'USD'}
    return {'type':'google.cloud.pubsub.topic.v1.messagePublished','source':f'//pubsub.googleapis.com/projects/{PROJECT}/topics/jmgo-tv-budget','data':{'message':{'attributes':{'billingAccountId':ACCOUNT,'budgetId':BUDGET,'schemaVersion':'1.0'},'data':base64.b64encode(json.dumps(data).encode()).decode()}}}

def execution(argument):
    launched=api('POST', ENDPOINT, {'argument':json.dumps(argument),'callLogLevel':'LOG_NONE'})
    for _ in range(40):
        result=api('GET','https://workflowexecutions.googleapis.com/v1/'+launched['name'])
        if result['state'] not in ('ACTIVE','QUEUED'):
            if result['state']!='SUCCEEDED': raise RuntimeError(json.dumps(result.get('error',result)))
            return json.loads(result['result']),launched['name']
        time.sleep(1)
    raise TimeoutError(launched['name'])

def run_tests():
    assert EXPIRY == "2027-10-21T16:00:00Z", "These boundary fixtures target the shipped deadline; update fixtures for a different deadline"
    auto={'labels':{'keep-me':'yes'},'scaling':{'maxInstanceCount':1}}
    paused={'labels':{'keep-me':'yes','tv-guard-reason':'budget','tv-guard-month':'2026-10'},'scaling':{'scalingMode':'MANUAL','manualInstanceCount':0,'maxInstanceCount':1}}
    invalid=event();invalid['data']['message']['attributes']['budgetId']='wrong'
    malformed=event();malformed['data']['message']['data']='bad-base64'
    manual={'labels':{},'scaling':{'scalingMode':'MANUAL','manualInstanceCount':0,'maxInstanceCount':1}}
    cases=[
      ('below-threshold',event(4.99),auto,'2026-10-24T00:00:00Z','none'),
      ('exact-threshold',event(5),auto,'2026-10-24T00:00:00Z','pause'),
      ('above-threshold',event(6),auto,'2026-10-24T00:00:00Z','pause'),
      ('other-budget',invalid,auto,'2026-10-24T00:00:00Z','none'),
      ('malformed',malformed,auto,'2026-10-24T00:00:00Z','none'),
      ('previous-month-event',event(6,'2026-09-01T07:00:00Z'),auto,'2026-10-24T00:00:00Z','none'),
      ('same-month-keeps-paused',{'action':'reconcile'},paused,'2026-10-24T00:00:00Z','none'),
      ('new-month-resumes',{'action':'reconcile'},paused,'2026-11-01T07:10:00Z','resume'),
      ('taipei-month-start-before-pacific',{'action':'reconcile'},paused,'2026-10-31T16:10:00Z','none'),
      ('budget-does-not-claim-manual-pause',event(5),manual,'2026-10-24T00:00:00Z','none'),
      ('duplicate-event',event(5),paused,'2026-10-24T00:00:00Z','none'),
      ('current-month-reached-before-resume',event(5,'2026-11-01T07:00:00Z'),paused,'2026-11-01T07:10:00Z','pause'),
      ('manual-pause-preserved',{'action':'reconcile'},manual,'2026-11-01T07:10:00Z','none'),
      ('before-expiry',{'action':'reconcile'},auto,'2027-10-21T15:59:59Z','none'),
      ('expiry-label-before-deadline',{'action':'reconcile'},{'labels':{'tv-guard-reason':'expired'},'scaling':{'maxInstanceCount':1}},'2026-10-24T00:00:00Z','pause'),
      ('expiry-exact',{'action':'reconcile'},auto,'2027-10-21T16:00:00Z','pause'),
      ('expiry-prevents-month-reset',{'action':'reconcile'},paused,'2027-11-01T08:10:00Z','pause'),
      ('stale-message-after-expiry',event(0),auto,'2027-10-22T00:00:00Z','pause'),
    ]
    def test(case):
        name,ev,service,now,expected=case
        result,execution_name=execution({'dryRun':True,'testNow':now,'testService':service,'event':ev})
        assert result['action']==expected,(name,result)
        if expected in ('pause','resume'):
            assert result['scaling']['maxInstanceCount']==1,(name,result)
            assert result['labels'].get('keep-me')==service['labels'].get('keep-me'),(name,result)
        if expected=='resume':
            assert 'manualInstanceCount' not in result['scaling'],(name,result)
            assert result['scaling']['minInstanceCount']==0,(name,result)
        if 'expiry' in name and expected=='pause': assert result['reason']=='expired',(name,result)
        if expected=='pause':
            want_unlink = now >= '2027-10-21T16:00:00Z' and result['reason']=='expired'
            assert result['disableBilling']==want_unlink,(name,result)
        return {'case':name,'passed':True,'result':result,'execution':execution_name}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(test,cases))
    (STATE_DIR/'decision-tests.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps({'passed':len(results),'cases':[r['case'] for r in results]}))
if __name__=='__main__':run_tests()
