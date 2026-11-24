// Public DOM observation for the article-level cover, separate from body media.
export async function readCover(page){
  return await page.evaluate(()=>{
    const title=document.querySelector('textarea[name="Article Title"]');
    if(!title)throw new Error('Article title is not visible');
    let owner=title.parentElement;
    while(owner&&!owner.querySelector('[data-testid="composer"]'))owner=owner.parentElement;
    if(!owner)throw new Error('Article body container is not identifiable');
    const beforeTitle=e=>!!(e.compareDocumentPosition(title)&Node.DOCUMENT_POSITION_FOLLOWING);
    const covers=[...owner.querySelectorAll('img')].filter(i=>!i.closest('[data-testid="composer"]')&&beforeTitle(i));
    const inputs=[...owner.querySelectorAll('input[type="file"]')].filter(i=>!i.closest('[data-testid="composer"],[role="dialog"]')&&beforeTitle(i));
    return {present:covers.length>0,crop_dialog_open:!!document.querySelector('[role="dialog"][aria-label="Edit media"]'),candidates:covers.map(i=>({src:i.currentSrc||i.src,width:i.naturalWidth,height:i.naturalHeight,display_width:i.getBoundingClientRect().width,display_height:i.getBoundingClientRect().height})),upload_input_count:inputs.length};
  });
}

export function bodyCanonical(state){
  const clean=s=>s.replace(/\u200b/g,'').replace(/\s+/g,' ').trim();
  const identity=i=>{
    if(i.rendered_sha256)return 'sha256:'+i.rendered_sha256;
    if(i.src?.startsWith('https://'))return 'url:'+i.src;
    throw new Error('Body media identity is unproven; capture rendered fingerprints before comparing.');
  };
  return JSON.stringify({title:state.title,blocks:state.blocks.filter(b=>b.tag==='SECTION'||clean(b.text)).map(b=>({
    tag:b.tag,text:b.tag==='SECTION'?'':clean(b.text),links:b.links,
    tables:b.tables.map(t=>({cells:t.cells.map(r=>r.map(clean)),links:t.links})),
    images:b.images.map(i=>({identity:identity(i),width:i.width,height:i.height}))
  }))});
}

export function assertBodyUnchanged(before,after){
  if(bodyCanonical(before)!==bodyCanonical(after))throw new Error('Current draft body differs from the pre-cover snapshot; preserve it and inspect, do not rewrite it.');
  return true;
}
