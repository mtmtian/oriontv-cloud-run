"""Use service IAM for Cloud Run; Workflows/Scheduler IAM is project-level."""
import json,os,tempfile
from deploy import PROJECT,RUNTIME,INVOKER,cli
from config import EXPIRY

def configure():
    role_specs=[('tvGuardExecutionCreate','workflows.executions.create'),('tvGuardRunOperationRead','run.operations.get'),('tvRunScaleGuard','run.services.get,run.services.update'),('tvProjectBillingRead','resourcemanager.projects.get'),('tvBillingUnlink','resourcemanager.projects.deleteBillingAssignment')]
    for name,permissions in role_specs:
        existing=cli('iam','roles','describe',name,f'--project={PROJECT}',optional=True)
        cli('iam','roles','create' if existing is None else 'update',name,f'--project={PROJECT}',f'--title={name}',f'--permissions={permissions}','--stage=GA')
    policy=cli('projects','get-iam-policy',PROJECT)
    managed_titles={'tv-guard-workflow-only','tv-guard-operations','tv-guard-own-schedules'}
    policy['bindings']=[b for b in policy['bindings'] if b.get('condition',{}).get('title') not in managed_titles and not (b['role']==f'projects/{PROJECT}/roles/tvGuardSchedulePause' and b['members']==['serviceAccount:'+RUNTIME]) and b.get('condition',{}).get('title') != 'tv-billing-unlink-after-expiry']
    for sa,role in [(INVOKER,'tvGuardExecutionCreate'),(RUNTIME,'tvGuardRunOperationRead'),(RUNTIME,'tvProjectBillingRead')]:
        binding={'role':f'projects/{PROJECT}/roles/{role}','members':['serviceAccount:'+sa]}
        if binding not in policy['bindings']:policy['bindings'].append(binding)
    policy['bindings'].append({'role':f'projects/{PROJECT}/roles/tvBillingUnlink','members':['serviceAccount:'+RUNTIME],'condition':{'title':'tv-billing-unlink-after-expiry','expression':f'request.time >= timestamp("{EXPIRY}")'}})
    fd,path=tempfile.mkstemp(prefix='tv-guard-iam-',suffix='.json')
    try:
        with os.fdopen(fd,'w') as f:json.dump(policy,f)
        cli('projects','set-iam-policy',PROJECT,path)
    finally:os.unlink(path)
    cli('iam','service-accounts','add-iam-policy-binding',f'lunatv-runtime@{PROJECT}.iam.gserviceaccount.com',f'--project={PROJECT}',f'--member=serviceAccount:{RUNTIME}','--role=roles/iam.serviceAccountUser')
    print('Minimal project-specific invocation, operation read and time-gated billing unlink permissions configured',flush=True)
if __name__=='__main__':configure()
