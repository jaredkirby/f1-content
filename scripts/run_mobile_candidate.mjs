// One-shot credential pickup. Secrets use hidden stdin and optional native Keychain storage.
import fs from 'node:fs';
import {storageOperationId} from '../f1_pipeline/resources/mobile-review-site/lib/credential-operation.mjs';
import path from 'node:path';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

const project=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const python=process.env.F1_PYTHON||path.join(project,'.venv/bin/python');
const input=await new Promise((resolve,reject)=>{
  let text='';
  if(process.stdin.isTTY)process.stdin.setRawMode(true);
  process.stdout.write('Ready for mobile credential execution input (hidden).\n');
  process.stdin.resume();
  process.stdin.on('data',chunk=>{
    text+=chunk.toString();
    if(text.length>20000){process.stdin.removeAllListeners('data');if(process.stdin.isTTY)process.stdin.setRawMode(false);process.stdin.pause();reject(new Error('input_limit'));return;}
    if(!text.includes('\n'))return;
    process.stdin.removeAllListeners('data');
    if(process.stdin.isTTY)process.stdin.setRawMode(false);
    process.stdin.pause();
    try{resolve(JSON.parse(text));}catch{reject(new Error('invalid_input'));}
  });
}).catch(()=>null);

try {
  if(!input)throw new Error('Invalid execution input.');
  const origin=new URL(input.siteUrl);
  const local=origin.protocol==='http:'&&origin.hostname==='127.0.0.1';
  const hosted=origin.protocol==='https:'&&origin.hostname.endsWith('.chatgpt.site');
  if(origin.username||origin.password||origin.search||origin.hash||(!local&&!hosted))throw new Error('Invalid Site origin.');
  if(input.mode==='verify-local') {
    if(!local)throw new Error('Local verification cannot use a hosted Site.');
  } else if(!['execute','verify-execution','execute-plan','verify-plan'].includes(input.mode)||!hosted)throw new Error('Execution requires the private hosted Site.');

  let root, state, authorization, requestPath, workId, promptVersion, rubricVersion;
  const planMode=['execute-plan','verify-plan'].includes(input.mode);
  if(planMode) {
    if(!path.isAbsolute(input.workspace)||typeof input.planPath!=='string')throw new Error('Explicit workspace and plan required.');
    root=path.resolve(input.workspace);requestPath=path.resolve(root,input.planPath);
    if(!fs.realpathSync(requestPath).startsWith(fs.realpathSync(root)+path.sep))throw new Error('Plan is outside workspace.');
    const sha=crypto.createHash('sha256').update(fs.readFileSync(requestPath)).digest('hex');
    const preview=spawnSync(python,['-B','-m','f1_pipeline','--workspace',root,
      'model-run','--request',requestPath],{cwd:project,encoding:'utf8',timeout:20000,maxBuffer:4000000});
    if(preview.status!==0)throw new Error('Plan preflight failed.');
    const result=JSON.parse(preview.stdout);
    if(sha!==input.requestSha256||input.operationId!==storageOperationId(sha.slice(0,24),input.persistKeychain)||result.budget_usd!==input.budgetUsd||
       result.max_calls!==input.maxCalls||result.preflight_ceiling_usd>input.budgetUsd)throw new Error('Plan handoff bindings changed.');
    if(fs.existsSync(path.join(root,'runs/model-plans',result.plan_id)))throw new Error('Plan already attempted.');
    const plan=JSON.parse(fs.readFileSync(requestPath,'utf8'));
    for(const job of plan.jobs){
      const base=path.join(root,'runs/model-evaluations',plan.comparison_id,job.id);
      if(fs.existsSync(base+'.assets')||fs.existsSync(base+'.json'))throw new Error('Job already attempted.');
    }
    if(input.mode==='verify-plan'){
      process.stdout.write(JSON.stringify({status:'verified_plan_bindings',request_sha256:sha,
        max_calls:result.max_calls,budget_usd:result.budget_usd,inference_attempted:false})+'\n');
      process.exit(0);
    }
  } else if(input.mode!=='verify-local') {
    if(!path.isAbsolute(input.workspace))throw new Error('An absolute event workspace is required.');
    root=path.resolve(input.workspace);
    const within=relative=>{const file=path.resolve(root,relative);if(!file.startsWith(root+path.sep))throw new Error('Invalid workspace binding.');return file;};
    const hash=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
    state=JSON.parse(fs.readFileSync(within('runs/pilot/pilot-state.json'),'utf8'));
    const active=state.active_hosted_candidate;
    if(hash(within(active.request.path))!==active.request.sha256||hash(within(active.spending_authorization.path))!==active.spending_authorization.sha256)
      throw new Error('Authorized request bindings changed.');
    authorization=JSON.parse(fs.readFileSync(within(active.spending_authorization.path),'utf8'));
    if(authorization.source?.kind!=='human'||authorization.max_calls!==1||authorization.provider!=='openrouter'||
       authorization.model!==active.model||authorization.request_binding.sha256!==active.request.sha256||authorization.budget_usd!==input.budgetUsd)
      throw new Error('A current bounded human authorization is required.');
    if(input.operationId!==storageOperationId(active.spending_authorization.sha256.slice(0,24),input.persistKeychain))throw new Error('The operation changed.');
    workId=active.work_id??'openrouter-candidate-v1';
    if(!/^[a-z0-9][a-z0-9_-]{0,99}$/.test(workId)||!/^[a-z0-9][a-z0-9_-]{0,99}$/.test(state.comparison_id))
      throw new Error('Invalid work identity.');
    const assets=within(`runs/model-evaluations/${state.comparison_id}/${workId}.assets`);
    const receipt=within(`runs/model-evaluations/${state.comparison_id}/${workId}.json`);
    if(fs.existsSync(assets)||fs.existsSync(receipt))throw new Error('This work already has execution evidence; do not retry it.');
    if(hash(within('outputs/manifest.json'))!==state.manifest_sha256||hash(within(state.video.path))!==state.video.sha256)
      throw new Error('The reference output changed.');
    if(hash(within(state.reference_receipt.path))!==state.reference_receipt.sha256)
      throw new Error('The reference model receipt changed.');
    const reference=JSON.parse(fs.readFileSync(within(state.reference_receipt.path),'utf8'));
    promptVersion=active.prompt_version??reference.prompt_version;
    rubricVersion=active.rubric_version??reference.rubric_version;
    if([promptVersion,rubricVersion].some(value=>typeof value!=='string'||!value.trim()||value.length>200))
      throw new Error('Explicit prompt and rubric versions are required.');
    if(authorization.work_id!==workId||authorization.comparison_id!==state.comparison_id||
       authorization.prompt_version!==promptVersion||authorization.rubric_version!==rubricVersion)
      throw new Error('Every executable work identity must match its authorization.');
    requestPath=within(active.request.path);
    const preview=spawnSync(python,['-B','-m','f1_pipeline','--workspace',root,
      'model-infer','--request',requestPath,'--budget-usd',String(input.budgetUsd)],{cwd:project,encoding:'utf8'});
    if(preview.status!==0)throw new Error('Candidate preflight failed.');
    const preflight=JSON.parse(preview.stdout);
    if(preflight.request_sha256!==input.requestSha256||preflight.requested_model!==authorization.model||
       preflight.cost.preflight_ceiling_usd>input.budgetUsd)throw new Error('The sent request changed.');
    if(input.mode==='verify-execution') {
      process.stdout.write(JSON.stringify({status:'verified_execution_bindings',work_id:workId,
        request_sha256:preflight.request_sha256,budget_usd:input.budgetUsd,inference_attempted:false})+'\n');
      process.exit(0);
    }
  }
  const response=await fetch(new URL('/api/operator/credential',origin),{
    method:'POST',redirect:'manual',signal:AbortSignal.timeout(20000),headers:{
      'Authorization':'Bearer '+input.operatorToken,
      ...(input.serviceToken?{'OAI-Sites-Authorization':'Bearer '+input.serviceToken}:{})}});
  if(response.status===202){process.stdout.write(JSON.stringify({status:'awaiting_key',inference_attempted:false})+'\n');}
  else {
    if(response.status!==200)throw new Error('Private credential collection failed.');
    const body=await response.text();if(body.length>4096)throw new Error('Invalid credential response.');
    const handoff=JSON.parse(body);
    if(handoff.operationId!==input.operationId||handoff.requestSha256!==input.requestSha256||
       handoff.budgetUsd!==input.budgetUsd||(planMode&&handoff.maxCalls!==input.maxCalls)||typeof handoff.key!=='string'||!handoff.key||
       handoff.key.length>512||! /^[!-~]+$/.test(handoff.key))throw new Error('Credential handoff bindings changed.');
    if(typeof input.persistKeychain!=='boolean'||handoff.persistKeychain!==input.persistKeychain)throw new Error('Storage consent binding changed.');
    if(input.mode==='verify-local') {
      if(handoff.key!=='synthetic-mobile-key')throw new Error('Local verification accepts only its synthetic fixture.');
      process.stdout.write(JSON.stringify({status:'verified_local_handoff',inference_attempted:false})+'\n');
    } else {
      const childEnv={...process.env,PYTHONDONTWRITEBYTECODE:'1'};
      if(input.persistKeychain===true){
        const saved=spawnSync(python,['-B','-m','f1_pipeline.credentials','store'],{
          cwd:project,input:handoff.key,encoding:'utf8',timeout:20000,maxBuffer:4096});
        if(saved.status!==0||JSON.parse(saved.stdout).status!=='stored')throw new Error('Keychain storage failed.');
        delete childEnv.OPENROUTER_API_KEY;delete childEnv.F1_DISABLE_KEYCHAIN;
        process.stdout.write(JSON.stringify({status:'credential_saved',storage:'macos_login_keychain'})+'\n');
      } else childEnv.OPENROUTER_API_KEY=handoff.key;
      const executionArgs=planMode ? ['-B','-m','f1_pipeline','--workspace',root,
        'model-run','--request',requestPath,'--expected-plan-sha256',input.requestSha256,'--execute','--budget-usd',String(input.budgetUsd),'--timeout-seconds','300'] : ['-B','-m','f1_pipeline','--workspace',root,
        'model-infer','--request',requestPath,'--execute','--budget-usd',String(input.budgetUsd),
        '--timeout-seconds','300','--comparison-id',state.comparison_id,'--work-id',workId,
        '--format','vertical','--task','story_script','--prompt-version',promptVersion,
        '--rubric-version',rubricVersion,'--evidence','runs/pilot/frozen-brief.json',
        '--evidence','research/event/sector_comparison.json','--evidence','research/event/event_bundle.json',
        '--evidence','research/media/clip_review.json','--evidence','outputs/manifest.json'];
      const result=spawnSync(python,executionArgs,{
        cwd:project,encoding:'utf8',timeout:planMode ? input.maxCalls*305000+20000 : 320000,maxBuffer:4000000,
        env:childEnv});
      const safe=value=>(value||'').split(handoff.key).join('[redacted]');
      const stdout=safe(result.stdout),stderr=safe(result.stderr);
      handoff.key='';
      process.stdout.write(stdout);process.stderr.write(stderr);
      process.exitCode=result.status??1;
    }
  }
} catch {process.stderr.write('Mobile credential execution could not complete. Inspect the saved handoff and run evidence; no automatic retry.\n');process.exitCode=1;}
