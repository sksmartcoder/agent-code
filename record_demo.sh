#!/bin/bash
# Runs the full automated demo and records it as an animated SVG
# Output: it-ticket-agent/demo_recording.svg  (open in any browser)

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT="$SCRIPT_DIR/demo_recording.svg"

echo "Starting automated demo recording..."
echo "Output will be saved to: $OUTPUT"
echo ""

termtosvg "$OUTPUT" \
  --template window_frame_js \
  --screen-geometry 220x50 \
  --min-frame-duration 0.05 \
  --loop-delay 5000 \
  -- bash -c "
    cd $SCRIPT_DIR
    python3 - << 'PYEOF'
import os, sys, time

os.environ.update({
    'AWS_DEFAULT_REGION': 'us-west-2',
    'BEDROCK_REGION':     'us-west-2',
    'BEDROCK_MODEL_ID':   'us.amazon.nova-lite-v1:0',
    'CONFIDENCE_THRESHOLD': '80',
    'TICKETS_TABLE':     'demo_it_tickets',
    'PATTERNS_TABLE':    'demo_ticket_patterns',
    'RESOLUTIONS_TABLE': 'demo_resolutions',
    'RUNBOOK_BUCKET':    'demo-runbooks',
})
sys.path.insert(0, '$SCRIPT_DIR')

# Bootstrap real Bedrock before moto
import boto3 as _rb
_real_bedrock = _rb.client('bedrock-runtime', region_name='us-west-2')

from moto import mock_aws
import boto3
_mock = mock_aws()
_mock.start()

import config, json
_ddb = boto3.resource('dynamodb', region_name='us-east-1')

def _tbl(name, pk, attrs, gsi):
    try:
        _ddb.create_table(TableName=name,
            KeySchema=[{'AttributeName': pk, 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': k, 'AttributeType': v} for k,v in attrs],
            BillingMode='PAY_PER_REQUEST', GlobalSecondaryIndexes=gsi)
    except: pass

_tbl(config.TICKETS_TABLE, 'ticket_id',
    [('ticket_id','S'),('category','S'),('status','S')],
    [{'IndexName':'category-status-index','KeySchema':[{'AttributeName':'category','KeyType':'HASH'},{'AttributeName':'status','KeyType':'RANGE'}],'Projection':{'ProjectionType':'ALL'}}])
_tbl(config.PATTERNS_TABLE, 'pattern_id',
    [('pattern_id','S'),('category','S')],
    [{'IndexName':'category-index','KeySchema':[{'AttributeName':'category','KeyType':'HASH'}],'Projection':{'ProjectionType':'ALL'}}])
_tbl(config.RESOLUTIONS_TABLE, 'resolution_id',
    [('resolution_id','S'),('ticket_id','S')],
    [{'IndexName':'ticket-index','KeySchema':[{'AttributeName':'ticket_id','KeyType':'HASH'}],'Projection':{'ProjectionType':'ALL'}}])

_s3 = boto3.client('s3', region_name='us-east-1')
try: _s3.create_bucket(Bucket=config.RUNBOOK_BUCKET)
except: pass

kb = '$SCRIPT_DIR/knowledge_base'
import os
if os.path.isdir(kb):
    for f in os.listdir(kb):
        if f.endswith('.md'):
            with open(os.path.join(kb, f)) as fh:
                _s3.put_object(Bucket=config.RUNBOOK_BUCKET, Key=f'runbooks/{f}', Body=fh.read())

_glue = boto3.client('glue', region_name=config.REGION)
for job in ['daily_claims_load', 'etl_pipeline']:
    try:
        _glue.create_job(Name=job, Role='arn:aws:iam::123:role/GlueRole',
            Command={'Name':'glueetl','ScriptLocation':f's3://mock/{job}.py','PythonVersion':'3'})
        _glue.start_job_run(JobName=job)
    except: pass

from tools.models import TicketPattern, Resolution
from tools.ticket_store import create_pattern
for pat, res in [
    (TicketPattern(pattern_id='pat-cicd-001',category='CI/CD',signature='ECS OOM',resolution_id='res-cicd-001',keywords=['codepipeline','ecs','task','memory','killed','oom','deploy','failed']),
     Resolution(resolution_id='res-cicd-001',ticket_id='h1',pattern_id='pat-cicd-001',category='CI/CD',severity='P2',description_summary='ECS OOM during deploy',applied_fix='1. Increase ECS memory to 1024MB.\n2. Create new task revision.\n3. Update ECS service.\n4. Re-run CodePipeline.')),
    (TicketPattern(pattern_id='pat-data-001',category='Data/ETL',signature='Glue timeout',resolution_id='res-data-001',keywords=['glue','job','failed','connection','timeout','jdbc','daily','load','claims']),
     Resolution(resolution_id='res-data-001',ticket_id='h2',pattern_id='pat-data-001',category='Data/ETL',severity='P2',description_summary='Glue JDBC timeout',applied_fix='1. Increase JDBC timeout to 120s.\n2. Add retry logic.\n3. Increase DPU.')),
]:
    create_pattern(pat, _ddb)
    _ddb.Table(config.RESOLUTIONS_TABLE).put_item(Item=res.to_dict())

import tools.classifier as _clf
import agent_core.base_agent as _ba

def _nova_clf(prompt):
    body = json.dumps({'system':[{'text':_clf.SYSTEM_PROMPT}],
        'messages':[{'role':'user','content':[{'text':prompt}]}],
        'inferenceConfig':{'maxTokens':256,'temperature':0.1}})
    r = _real_bedrock.invoke_model(modelId=os.environ['BEDROCK_MODEL_ID'],
        body=body, contentType='application/json', accept='application/json')
    return json.loads(r['body'].read())['output']['message']['content'][0]['text']

def _nova_ba(system_prompt, prompt):
    body = json.dumps({'system':[{'text':system_prompt}],
        'messages':[{'role':'user','content':[{'text':prompt}]}],
        'inferenceConfig':{'maxTokens':1024,'temperature':0.2}})
    r = _real_bedrock.invoke_model(modelId=os.environ['BEDROCK_MODEL_ID'],
        body=body, contentType='application/json', accept='application/json')
    return json.loads(r['body'].read())['output']['message']['content'][0]['text']

_clf._call_nova = _nova_clf
_ba._call_nova  = _nova_ba

from unittest.mock import patch
from agent_core.master_agent import MasterAgent

SCENARIOS = [
    ('CI/CD Pipeline OOM',        'CodePipeline deploy failed — ECS task OOM killed'),
    ('Data/ETL Glue Timeout',     'Glue job daily_claims_load failed with connection timeout'),
    ('Infrastructure Disk Full',  'EC2 instance i-0abc123 unreachable, disk at 98%'),
    ('Access/IAM Permission',     'Lambda function cant write to S3 bucket prod-reports'),
    ('Network API Gateway 503',   'API gateway returning 503, backend health checks failing'),
]

print('\033[96m\033[1m')
print('╔══════════════════════════════════════════════════════════╗')
print('║     IT TICKET INTELLIGENCE AGENT — AUTOMATED DEMO       ║')
print('║     Amazon Bedrock Nova · Strands SDK · AWS              ║')
print('╚══════════════════════════════════════════════════════════╝')
print('\033[0m')
time.sleep(1)

for i, (name, desc) in enumerate(SCENARIOS, 1):
    print(f'\033[93m\033[1m{"═"*60}\033[0m')
    print(f'\033[93m  SCENARIO {i}/5: {name}\033[0m')
    print(f'\033[93m{"═"*60}\033[0m')
    time.sleep(0.5)
    with patch('builtins.input', return_value='approve'):
        result = MasterAgent(dynamodb=_ddb, s3_client=_s3).process(desc)
    print(f'\n\033[92m  ✓ DONE: {result}\033[0m\n')
    time.sleep(1.5)

print('\033[96m\033[1m')
print('╔══════════════════════════════════════════════════════════╗')
print('║  ALL 5 SCENARIOS COMPLETED SUCCESSFULLY                  ║')
print('║  Dashboard: amzn-hackthon-it-ticket-system.s3-website... ║')
print('║  GitHub:    github.com/sksmartcoder/agent-code           ║')
print('╚══════════════════════════════════════════════════════════╝')
print('\033[0m')
_mock.stop()
PYEOF
"

echo ""
echo "✅ Recording saved: $OUTPUT"
echo "   Upload to S3 and open in browser to play the animated demo."
