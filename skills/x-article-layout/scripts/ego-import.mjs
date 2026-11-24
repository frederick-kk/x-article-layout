// Import from an ego-browser nodejs round after inspecting the current editor.
// All mutations use public browser UI; page.evaluate only reads rendered state.
import fs from 'node:fs/promises';
import crypto from 'node:crypto';
import {setTimeout as delay} from 'node:timers/promises';
import {prepareImportRuntime, runSnapshotVerifier} from './import-runtime.mjs';

const COMPOSER = 'loc=css:[contenteditable="true"][data-testid="composer"]';

export async function readEditor(page) {
  return await page.evaluate(() => {
    const editor = document.querySelector('[data-testid="composer"]');
    if (!editor) throw new Error('Articles editor is not visible');
    return {
      title: document.querySelector('textarea[name="Article Title"]')?.value,
      status: [...document.querySelectorAll('main [role="heading"],main h1,main h2')].map(e=>e.textContent).find(t=>/Draft|Saving|Uploading/.test(t)),
      blocks: [...editor.querySelectorAll('[data-block="true"]')].map(e=>({
        tag:e.tagName, cls:e.className, text:e.innerText,
        tables:[...e.querySelectorAll('table')].map(t=>({
          cells:[...t.rows].map(r=>[...r.cells].map(c=>c.innerText.trim())),
          links:[...t.querySelectorAll('a')].map(a=>({text:a.textContent,href:a.getAttribute('href')}))
        })),
        images:[...e.querySelectorAll('[role="group"][aria-label="Media"] img')].map(i=>({src:i.currentSrc||i.src,width:i.naturalWidth,height:i.naturalHeight})),
        links:[...e.querySelectorAll('a')].map(a=>({text:a.textContent,href:a.getAttribute('href')})),
        html:e.outerHTML
      }))
    };
  });
}

export async function assertTarget(page, {draftUrl, account}) {
  if(typeof account!=='string'||!/^\w{1,15}$/.test(account))throw new Error('target.account must be the verified X handle without @');
  if(typeof draftUrl!=='string'||!/^https:\/\/x\.com\/compose\/articles\/edit\/\d+$/.test(draftUrl))throw new Error('target.draftUrl must be the exact verified X Articles draft URL');
  if ((await page.url()) !== draftUrl) throw new Error('Draft URL changed; inspect before continuing');
  const actual = await page.evaluate(() => document.querySelector('a[aria-label="Profile"]')?.getAttribute('href'));
  if (actual?.toLowerCase() !== `/${account}`.toLowerCase()) throw new Error('X account differs from this run');
}

export async function readEditorWithMediaFingerprints(page){
  const state=await readEditor(page);
  const fingerprints=await page.evaluate(async()=>await Promise.all([...document.querySelectorAll('[data-testid="composer"] [role="group"][aria-label="Media"] img')].map(async img=>{
    const src=img.currentSrc||img.src;
    if(!src.startsWith('blob:'))return {src};
    const bytes=await (await fetch(src)).arrayBuffer();
    const digest=await crypto.subtle.digest('SHA-256',bytes);
    return {src,rendered_sha256:[...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,'0')).join('')};
  })));
  const images=state.blocks.flatMap(b=>b.images);
  if(images.length!==fingerprints.length||images.some((img,i)=>img.src!==fingerprints[i].src))throw new Error('Media changed during fingerprint read');
  images.forEach((img,i)=>Object.assign(img,fingerprints[i]));
  return state;
}

async function tail(page) {
  // A pointer click establishes DraftJS's editable selection after media upload;
  // DOM focus alone can leave a native paste unapplied at the empty tail.
  await page.click('loc=css:[data-testid="composer"] [data-block="true"] >> nth=-1',{timeout:10000});
  await page.keyboard.press('ControlOrMeta+End');
  const end = await page.evaluate(() => {
    const nodes = [...document.querySelectorAll('[data-testid="composer"] [data-block="true"]')];
    const last = nodes.at(-1);
    return {text:last?.innerText?.trim() || '',tag:last?.tagName};
  });
  if (end.text || end.tag === 'SECTION') await page.keyboard.press('Enter');
  let current=await page.evaluate(()=>{const e=[...document.querySelectorAll('[data-testid="composer"] [data-block="true"]')].at(-1);return {tag:e?.tagName,text:e?.innerText?.trim()||''};});
  if(!current.text&&['LI','BLOCKQUOTE'].includes(current.tag)){
    await page.keyboard.press('Enter');
    current=await page.evaluate(()=>{const e=[...document.querySelectorAll('[data-testid="composer"] [data-block="true"]')].at(-1);return {tag:e?.tagName,text:e?.innerText?.trim()||''};});
  }
  if(!current.text&&['H1','H2'].includes(current.tag)){
    const label=current.tag==='H1'?'Heading':'Subheading';
    await page.click(`xpath=//main//button[normalize-space(.)="${label}"]`);
    await page.click(`xpath=//*[@role="menuitem"][normalize-space(.)="${label}"]`);
  }
  const ready=await page.evaluate(()=>{const e=[...document.querySelectorAll('[data-testid="composer"] [data-block="true"]')].at(-1);return e?.tagName==='DIV'&&e.classList.contains('longform-unstyled')&&!e.innerText.trim();});
  if(!ready)throw new Error('Tail is not an empty Body paragraph; inspect the caret before inserting');
}

export async function appendBlock(page, block, target) {
  await assertTarget(page,target);
  const before = await readEditor(page);
  const count = (state, key) => state.blocks.flatMap(b=>b[key]).length;
  await tail(page);
  if (block.kind === 'text') {
    await page.keyboard.paste({text:block.plain_text,html:block.html});
    const previous=before.blocks.filter(b=>b.tag!=='SECTION').map(b=>b.text).join('').replace(/\s/g,'');
    await page.waitForFunction(({previous,html})=>{
      const wanted=new DOMParser().parseFromString(html,'text/html').body.textContent.replace(/\s/g,'');
      const actual=[...document.querySelectorAll('[data-testid="composer"] [data-block="true"]')].filter(e=>e.tagName!=='SECTION').map(e=>e.innerText).join('').replace(/\s/g,'');
      return actual===previous+wanted;
    },{previous,html:block.html},{timeout:6000});
    // DraftJS pastes a single block using the current block type. Set an
    // isolated heading through its visible style menu after the text lands.
    const heading=await page.evaluate(html=>{
      const nodes=[...new DOMParser().parseFromString(html,'text/html').body.children];
      const expected=nodes.length===1&&['H1','H2'].includes(nodes[0].tagName)?nodes[0].tagName:null;
      const current=[...document.querySelectorAll('[data-testid="composer"] [data-block="true"]')].at(-1)?.tagName;
      return {expected,current};
    },block.html);
    if(heading.expected&&heading.current!==heading.expected){
      const currentLabel=heading.current==='H1'?'Heading':heading.current==='H2'?'Subheading':'Body';
      const expectedLabel=heading.expected==='H1'?'Heading':'Subheading';
      await page.click(`xpath=//main//button[normalize-space(.)="${currentLabel}"]`);
      await page.click(`text="${expectedLabel}"`);
    }
  } else if (block.kind === 'table') {
    await page.click('loc=css:button[aria-label="Add Media"]');
    await page.click('text="Table"');
    await page.click('loc=css:button[aria-label="Insert a 1 by 1 table"]');
    await page.click('loc=css:[data-testid="composer"] button[aria-label="Edit block"] >> nth=-1');
    await page.fill('loc=css:textarea[name="markdown-input"]',block.markdown);
    await page.click('text="Update"');
    await page.waitForFunction(({expected}) => document.querySelectorAll('[data-testid="composer"] table').length===expected, {expected:count(before,'tables')+1}, {timeout:10000});
    await page.waitForFunction(html=>{
      const expected=new DOMParser().parseFromString(html,'text/html').querySelector('table');
      const actual=[...document.querySelectorAll('[data-testid="composer"] table')].at(-1);
      const cells=t=>[...t.rows].map(r=>[...r.cells].map(c=>c.textContent.replace(/[\s\u200b]/g,'')));
      return expected&&actual&&JSON.stringify(cells(expected))===JSON.stringify(cells(actual));
    },block.html,{timeout:10000});
  } else if (block.kind === 'image') {
    const file = await fs.readFile(block.path);
    if (crypto.createHash('sha256').update(file).digest('hex') !== block.sha256) throw new Error('Image changed after preparation');
    await page.click('loc=css:button[aria-label="Add Media"]');
    await page.click('text="Media"');
    await page.setInputFiles('loc=css:[role="dialog"] input[type="file"]',[block.path]);
    await page.waitForFunction(({expected}) => {
      const images=[...document.querySelectorAll('[data-testid="composer"] section [role="group"][aria-label="Media"] img')];
      return !/Uploading media(?:\.{3}|…)/i.test(document.body.innerText) && images.length===expected && images.every(i=>i.complete&&i.naturalWidth>0);
    }, {expected:count(before,'images')+1}, {timeout:40000});
  } else if (block.kind === 'divider') {
    await page.click('loc=css:button[aria-label="Add Media"]');
    await page.click('text="Divider"');
  } else {
    throw new Error(`Unsupported prepared block: ${block.kind}`);
  }
  const after = await readEditor(page);
  if(block.kind!=='text'){
    const text=s=>s.blocks.filter(b=>b.tag!=='SECTION').map(b=>b.text).join('').replace(/\s/g,'');
    if(text(before)!==text(after))throw new Error('A special-block operation changed existing text; inspect before continuing');
  }
  if (block.kind==='table') {
    const table = after.blocks.flatMap(b=>b.tables).at(-1);
    if (!table || table.cells.length!==block.rows || table.cells.some(r=>r.length!==block.columns)) throw new Error('Inserted table dimensions differ; inspect this draft before retrying');
  }
  if (block.kind==='text' && block.plain_text.trim()) {
    const plain = after.blocks.filter(b=>b.tag!=='SECTION').map(b=>b.text).join('\n').replace(/\s/g,'');
    // Clipboard fallback includes URL destinations and list markers; rendered
    // rich text represents these as anchors/CSS and must be checked separately.
    const wanted = await page.evaluate(html => new DOMParser().parseFromString(html,'text/html').body.textContent.replace(/\s/g,''), block.html);
    const previous = before.blocks.filter(b=>b.tag!=='SECTION').map(b=>b.text).join('\n').replace(/\s/g,'');
    if (plain !== previous+wanted) throw new Error('Pasted text or append position differs; inspect this draft before retrying');
  }
  return {index:block.index,kind:block.kind,editor_blocks:after.blocks.length,images:count(after,'images'),tables:count(after,'tables'),saved:false};
}

export async function appendAndVerifySaved(page, block, target) {
  const runtime=await prepareImportRuntime(target,block);
  const {plan}=runtime;
  // Observe the saves dispatched by the public UI; never invoke its endpoint.
  await page.cdp('Network.enable');
  await page.events();
  const receipt=await appendBlock(page,block,target);
  const pending=new Set();
  let seen=0,lastEvent=Date.now(),mediaFinalized=block.kind!=='image',sequence=0,finalMediaSequence=0,saveResponseSequence=0;
  const deadline=Date.now()+25000;
  let settled=false;
  while(Date.now()<deadline){
    for(const event of await page.events()){
      sequence++;
      const p=event.params||{};
      const requestUrl=(p.request?.url||'').split('?')[0];
      if(event.method==='Network.requestWillBeSent'&&(requestUrl.endsWith('/ArticleEntityUpdateContent')||requestUrl==='https://upload.x.com/i/media/upload.json')){
        pending.add(p.requestId);
        if(requestUrl.endsWith('/ArticleEntityUpdateContent'))seen++;
        lastEvent=Date.now();
      }
      if(event.method==='Network.responseReceived'&&pending.has(p.requestId)){
        if(p.response.status<200||p.response.status>=300)throw new Error('UI draft save or media upload was rejected');
        if(p.response.url?.split('?')[0]==='https://upload.x.com/i/media/upload.json'&&p.response.status===201){mediaFinalized=true;finalMediaSequence=sequence;}
        if(p.response.url?.split('?')[0].endsWith('/ArticleEntityUpdateContent'))saveResponseSequence=sequence;
        lastEvent=Date.now();
      }
      if(event.method==='Network.loadingFailed'&&pending.has(p.requestId))throw new Error('UI draft save failed');
      if(event.method==='Network.loadingFinished'&&pending.delete(p.requestId))lastEvent=Date.now();
    }
    if(seen>0&&mediaFinalized&&(block.kind!=='image'||saveResponseSequence>finalMediaSequence)&&pending.size===0&&Date.now()-lastEvent>700){settled=true;break;}
    await delay(120);
  }
  if(!settled)throw new Error('No completed UI save was observed; inspect this draft before continuing');
  await page.reload();
  await page.waitForSelector(COMPOSER,{state:'visible',timeout:20000});
  const prefix=plan.blocks.slice(0,block.index+1);
  await page.waitForFunction(({title,html,images,tables})=>{
    const editor=document.querySelector('[data-testid="composer"]');
    if(!editor||document.querySelector('textarea[name="Article Title"]')?.value!==title)return false;
    const media=[...editor.querySelectorAll('[role="group"][aria-label="Media"] img')];
    const actual=[...editor.querySelectorAll('[data-block="true"]')].filter(e=>e.tagName!=='SECTION').map(e=>e.innerText).join('').replace(/[\s\u200b]/g,'');
    const expected=new DOMParser().parseFromString(html,'text/html').body.textContent.replace(/[\s\u200b]/g,'');
    return actual===expected&&media.length===images&&editor.querySelectorAll('table').length===tables&&media.every(i=>i.complete&&i.naturalWidth>0);
  },{title:plan.title,html:prefix.filter(b=>b.kind==='text').map(b=>b.html).join(''),images:prefix.filter(b=>b.kind==='image').length,tables:prefix.filter(b=>b.kind==='table').length},{timeout:20000});
  const after=await readEditor(page);
  // Compare the reopened document with its source, not transient DraftJS DOM
  // wrappers, captions, list reset classes, or session-specific blob URLs.
  const {prefixPath,snapshotPath}=runtime;
  await fs.writeFile(prefixPath,JSON.stringify({...plan,blocks:plan.blocks.slice(0,block.index+1)},null,2));
  await fs.writeFile(snapshotPath,JSON.stringify(after,null,2));
  const verification=runSnapshotVerifier(runtime);
  return {...receipt,saved:true,source_verified:true,ui_checks:verification.ui_checks?.map(c=>c.code)||[]};
}
