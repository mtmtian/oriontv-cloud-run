"""Non-secret deployment settings. Real values and receipts remain in .local/."""
import datetime as dt
import json
import os
from pathlib import Path
import re
REPO = Path(__file__).resolve().parents[2]
CONFIG_PATH = Path(os.environ.get('TV_CLOUD_CONFIG', REPO / '.local/cloud.json'))
CONFIG = json.loads(CONFIG_PATH.read_text())
PROJECT = CONFIG['project_id']
REGION = CONFIG['region']
ACCOUNT = CONFIG['billing_account']
EXPIRY = CONFIG['expiry_utc']
assert re.fullmatch(r'[a-z][a-z0-9-]{4,28}[a-z0-9]', PROJECT), 'Invalid project ID'
assert re.fullmatch(r'[a-z]+-[a-z]+[0-9]', REGION), 'Invalid region'
assert re.fullmatch(r'[A-Z0-9]{6}-[A-Z0-9]{6}-[A-Z0-9]{6}', ACCOUNT), 'Invalid billing account'
assert re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', EXPIRY), 'UTC timestamp required'
dt.datetime.fromisoformat(EXPIRY.replace('Z', '+00:00'))
assert CONFIG['monthly_usd'] == 5, 'This verified profile is fixed at USD 5'
assert CONFIG['service'] == 'lunatv', 'This profile controls only lunatv'
STATE_DIR = REPO / '.local/cost-guard'
STATE_DIR.mkdir(parents=True, exist_ok=True)
STATE_PATH = STATE_DIR / 'state.json'
STATE = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}
BUDGET = STATE.get('budget_id', '')
RUNTIME = f'tv-cost-guard@{PROJECT}.iam.gserviceaccount.com'
INVOKER = f'tv-guard-trigger@{PROJECT}.iam.gserviceaccount.com'

def render_workflow():
    assert re.fullmatch(r'[a-f0-9-]{36}', BUDGET), 'Run budgets.py first'
    template = (Path(__file__).parent / 'workflow.yaml.template').read_text()
    for key, value in {'PROJECT': PROJECT, 'REGION': REGION, 'ACCOUNT': ACCOUNT, 'BUDGET': BUDGET, 'EXPIRY': EXPIRY}.items():
        template = template.replace('@@' + key + '@@', value)
    assert '@@' not in template, 'Unresolved workflow placeholder'
    target = STATE_DIR / 'workflow.yaml'
    target.write_text(template)
    return target
