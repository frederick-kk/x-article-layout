import test from 'node:test';
import assert from 'node:assert/strict';
import {assertBodyUnchanged} from './cover-ui.mjs';

function baseline(){return {title:'Article',blocks:[
  {tag:'DIV',text:'Example draft',cls:'old',links:[],tables:[],images:[]},
  {tag:'SECTION',text:'caption control',links:[],tables:[{cells:[['A','B']],links:[{text:'source',href:'https://example.com/original'}]}],images:[]},
  {tag:'SECTION',text:'',links:[],tables:[],images:[{src:'blob:old-1',rendered_sha256:'one',width:500,height:800}]},
  {tag:'SECTION',text:'',links:[],tables:[],images:[{src:'blob:old-2',rendered_sha256:'two',width:500,height:800}]}
]};}

test('reopening blob URLs and runtime classes do not rewrite the body',()=>{
 const before=baseline(),after=structuredClone(before);after.blocks[0].cls='new';after.blocks[2].images[0].src='blob:new';
 assert.equal(assertBodyUnchanged(before,after),true);
});
test('meaningful English word spacing must remain intact',()=>{
 const before=baseline(),after=structuredClone(before);after.blocks[0].text='AppleID tutorial';
 assert.throws(()=>assertBodyUnchanged(before,after),/differs/);
});
test('body table link destinations must remain intact',()=>{
 const before=baseline(),after=structuredClone(before);after.blocks[1].tables[0].links[0].href='https://example.com/replaced';
 assert.throws(()=>assertBodyUnchanged(before,after),/differs/);
});
test('body media identity and sequence must remain intact',()=>{
 const before=baseline(),after=structuredClone(before);[after.blocks[2].images,after.blocks[3].images]=[after.blocks[3].images,after.blocks[2].images];
 assert.throws(()=>assertBodyUnchanged(before,after),/differs/);
});
test('a user-edited draft sentence is preserved as the comparison baseline',()=>{
 const before=baseline();before.blocks[0].text='My hand-edited sentence';const after=structuredClone(before);
 after.blocks[0].text='Example draft';assert.throws(()=>assertBodyUnchanged(before,after),/differs/);
});
test('stable HTTPS body media URLs identify images when no rendered hash exists',()=>{
 const before=baseline(),after=structuredClone(before);
 delete before.blocks[2].images[0].rendered_sha256;delete after.blocks[2].images[0].rendered_sha256;
 before.blocks[2].images[0].src='https://example.com/a.png';after.blocks[2].images[0].src='https://example.com/b.png';
 assert.throws(()=>assertBodyUnchanged(before,after),/differs/);
});
test('blob media without rendered fingerprints is not silently treated as proven',()=>{
 const before=baseline(),after=structuredClone(before);
 delete before.blocks[2].images[0].rendered_sha256;delete after.blocks[2].images[0].rendered_sha256;
 assert.throws(()=>assertBodyUnchanged(before,after),/identity.*unproven/);
});
