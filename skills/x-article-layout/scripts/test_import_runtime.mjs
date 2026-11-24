import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import crypto from 'node:crypto';
import {pythonExecutable,prepareImportRuntime,runSnapshotVerifier} from './import-runtime.mjs';
import {appendAndVerifySaved,assertTarget} from './ego-import.mjs';

const python=process.env.X_ARTICLE_TEST_PYTHON||pythonExecutable();

async function fixture(t) {
  const root=await fs.mkdtemp(path.join(os.tmpdir(),'x-layout-runtime-test-'));
  t.after(()=>fs.rm(root,{recursive:true,force:true}));
  const vault=path.join(root,'vault');
  await fs.mkdir(vault);
  const source=path.join(vault,'article.md');
  await fs.writeFile(source,'# Example\n\nDraft text.\n','utf8');
  const block={index:0,kind:'text',html:'<p>Draft text.</p>\n',plain_text:'Draft text.',markdown:'Draft text.\n'};
  const plan={schema_version:1,vault_path:vault,source_path:source,source_sha256:crypto.createHash('sha256').update(await fs.readFile(source)).digest('hex'),title:'Example',blocks:[block]};
  const target={planPath:path.join(root,'plan.json'),runDir:path.join(root,'run'),tempDir:path.join(root,'temp'),pythonExecutable:python};
  await fs.writeFile(target.planPath,JSON.stringify(plan));
  return {root,vault,source,block,plan,target};
}

test('interpreter selection supports explicit path and environment with portable defaults',()=>{
  assert.equal(pythonExecutable({pythonExecutable:'chosen-python'},{X_ARTICLE_PYTHON:'env-python'},'win32'),'chosen-python');
  assert.equal(pythonExecutable({},{X_ARTICLE_PYTHON:'env-python'},'linux'),'env-python');
  assert.equal(pythonExecutable({}, {}, 'win32'),'python');
  assert.equal(pythonExecutable({}, {}, 'darwin'),'python3');
});

test('saved import preflights a configured Python and runs the actual verifier',async t=>{
  const {target,block}=await fixture(t);
  const runtime=await prepareImportRuntime(target,block);
  await fs.writeFile(runtime.prefixPath,JSON.stringify({...runtime.plan,blocks:[]}));
  await fs.writeFile(runtime.snapshotPath,JSON.stringify({title:'Example',blocks:[]}));
  const result=runSnapshotVerifier(runtime);
  assert.deepEqual(result.errors,[]);
  assert.equal(runtime.pythonExecutable,python);
});

test('source changes stop saved import before the first browser operation',async t=>{
  const {target,block,source}=await fixture(t);
  await fs.appendFile(source,'User edit\n');
  await assert.rejects(appendAndVerifySaved({},block,target),/Source changed/);
});

test('run directory inside the Vault is rejected without touching source',async t=>{
  const {target,block,vault,source}=await fixture(t);
  const original=await fs.readFile(source);
  target.runDir=path.join(vault,'run');
  await assert.rejects(prepareImportRuntime(target,block),/outside the read-only Vault/);
  assert.deepEqual(await fs.readFile(source),original);
});

test('verification output cannot overwrite its own input plan',async t=>{
  const {target,block}=await fixture(t);
  target.runDir=path.dirname(target.planPath);
  const protectedPlan=path.join(target.runDir,'current-prefix-plan.json');
  await fs.rename(target.planPath,protectedPlan);
  target.planPath=protectedPlan;
  const original=await fs.readFile(protectedPlan);
  await assert.rejects(prepareImportRuntime(target,block),/overwrite a protected input/);
  assert.deepEqual(await fs.readFile(protectedPlan),original);
});

test('symlinked run output inside Vault is rejected',async t=>{
  const {target,block,vault,root}=await fixture(t);
  const alias=path.join(root,'vault-alias');
  try{await fs.symlink(vault,alias,process.platform==='win32'?'junction':'dir');}
  catch(error){if(error.code==='EPERM'){t.skip('directory symlinks unavailable');return;}throw error;}
  target.runDir=path.join(alias,'not-created');
  await assert.rejects(prepareImportRuntime(target,block),/outside the read-only Vault/);
});

test('legacy plan is supported through an explicit Vault root',async t=>{
  const {target,block,plan,vault}=await fixture(t);
  delete plan.vault_path;
  await fs.writeFile(target.planPath,JSON.stringify(plan));
  await assert.rejects(prepareImportRuntime(target,block),/plan.vault_path/);
  target.vaultPath=vault;
  const runtime=await prepareImportRuntime(target,block);
  assert.equal(runtime.plan.source_path,plan.source_path);
});

test('mismatched block and relative run path fail before browser changes',async t=>{
  const {target,block}=await fixture(t);
  await assert.rejects(prepareImportRuntime(target,{...block,markdown:'different'}),/does not match/);
  await assert.rejects(prepareImportRuntime({...target,runDir:'relative'},block),/absolute path/);
});

test('missing Python reports configuration steps before browser changes',async t=>{
  const {target,block,root}=await fixture(t);
  target.pythonExecutable=path.join(root,'missing-python-executable');
  await assert.rejects(appendAndVerifySaved({},block,target),/X_ARTICLE_PYTHON.*requirements.txt/);
});

test('account and draft URL must be explicit before inspecting a page',async()=>{
  await assert.rejects(assertTarget({}, {account:'@someone',draftUrl:'https://x.com/compose/articles/edit/123'}),/without @/);
  await assert.rejects(assertTarget({}, {account:'someone',draftUrl:'https://x.com/home'}),/exact verified/);
});
