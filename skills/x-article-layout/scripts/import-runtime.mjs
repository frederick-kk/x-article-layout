// Portable local verifier setup; call before any browser mutation.
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';

export function pythonExecutable(target={}, env=process.env, platform=process.platform) {
  const executable=target.pythonExecutable||env.X_ARTICLE_PYTHON||(platform==='win32'?'python':'python3');
  if(typeof executable!=='string'||!executable.trim())throw new Error('pythonExecutable must name one executable, without shell arguments');
  return executable;
}

// Resolve existing ancestors too, so a not-yet-created child of a symlink
// cannot accidentally put run data inside the read-only Vault.
async function canonical(value) {
  let current=path.resolve(value);
  const suffix=[];
  for(;;){
    try{return path.join(await fs.realpath(current),...suffix.reverse());}
    catch(error){
      if(error.code!=='ENOENT')throw error;
      const parent=path.dirname(current);
      if(parent===current)throw error;
      suffix.push(path.basename(current));current=parent;
    }
  }
}

function within(root, value) {
  const relative=path.relative(root,value);
  return relative===''||(!relative.startsWith(`..${path.sep}`)&&relative!=='..'&&!path.isAbsolute(relative));
}

function absolute(value, label) {
  if(typeof value!=='string'||!path.isAbsolute(value))throw new Error(`${label} must be an absolute path`);
}

export async function prepareImportRuntime(target, block) {
  if(!target)throw new Error('Saved import requires a target');
  absolute(target.planPath,'target.planPath');
  absolute(target.runDir,'target.runDir');
  const planPath=await canonical(target.planPath);
  const plan=JSON.parse(await fs.readFile(planPath,'utf8'));
  absolute(plan.source_path,'plan.source_path');
  const vaultValue=plan.vault_path||target.vaultPath;
  absolute(vaultValue,'plan.vault_path (or target.vaultPath for a legacy plan)');
  const vaultPath=await fs.realpath(vaultValue);
  const sourcePath=await fs.realpath(plan.source_path);
  if(!within(vaultPath,sourcePath))throw new Error('Source must be inside its declared Vault');
  if(within(vaultPath,planPath))throw new Error('Prepared plan must be outside the read-only Vault');
  if(!Array.isArray(plan.blocks)||!Number.isInteger(block?.index)||JSON.stringify(plan.blocks[block.index])!==JSON.stringify(block))throw new Error('Block does not match the prepared plan');
  if(crypto.createHash('sha256').update(await fs.readFile(sourcePath)).digest('hex')!==plan.source_sha256)throw new Error('Source changed after preparation');
  const runDir=await canonical(target.runDir);
  const rawTemp=target.tempDir||path.join(os.tmpdir(),'x-article-layout');
  absolute(rawTemp,'target.tempDir');
  const tempDir=await canonical(rawTemp);
  if(within(vaultPath,runDir)||within(vaultPath,tempDir))throw new Error('Run and temp directories must be outside the read-only Vault');
  const prefixPath=path.join(runDir,'current-prefix-plan.json');
  const snapshotPath=path.join(runDir,'current-snapshot.json');
  for(const output of [prefixPath,snapshotPath]){
    const resolved=await canonical(output);
    if(within(vaultPath,resolved)||resolved===planPath||resolved===sourcePath)throw new Error('Verification output would overwrite a protected input');
  }
  await fs.mkdir(runDir,{recursive:true});
  await fs.mkdir(tempDir,{recursive:true});
  const executable=pythonExecutable(target);
  const env={...process.env,TEMP:tempDir,TMP:tempDir,PYTHONDONTWRITEBYTECODE:'1'};
  const check=spawnSync(executable,['-X','utf8','-c','import sys; assert sys.version_info >= (3,10), "Python 3.10+ required"; import bs4'],{encoding:'utf8',env,timeout:15000});
  if(check.error||check.status!==0)throw new Error('Python verifier is unavailable. Set target.pythonExecutable or X_ARTICLE_PYTHON to Python 3.10+ and install requirements.txt with that interpreter. '+(check.error?.code||check.stderr||'').slice(0,350));
  return {plan,runDir,tempDir,prefixPath,snapshotPath,pythonExecutable:executable,env};
}

export function runSnapshotVerifier(runtime) {
  const result=spawnSync(runtime.pythonExecutable,['-X','utf8',fileURLToPath(new URL('./verify_snapshot.py',import.meta.url)),'--plan',runtime.prefixPath,'--snapshot',runtime.snapshotPath],{encoding:'utf8',env:runtime.env,timeout:30000});
  if(result.error)throw new Error('Snapshot verifier failed to start or timed out: '+result.error.code);
  let verification;
  try{verification=JSON.parse(result.stdout);}catch{throw new Error('Snapshot verifier did not return JSON: '+(result.stderr||'').slice(0,350));}
  if(![0,3].includes(result.status)||verification.errors?.length)throw new Error('Reopened draft differs from source: '+JSON.stringify(verification.errors||verification).slice(0,1500));
  return verification;
}
