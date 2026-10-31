/* Offline unsealed assessment drafts. Never operator access or semantic approval. */
(function () {
  'use strict';
  const copy = x => JSON.parse(JSON.stringify(x));
  const stable = x => JSON.stringify(x, (k,v) => v && typeof v === 'object' && !Array.isArray(v)
    ? Object.keys(v).sort().reduce((out,key) => {out[key]=v[key];return out;},{}) : v);
  const exact = (x,y) => {
    if (!x || typeof x !== 'object' || Array.isArray(x) || stable(Object.keys(x).sort()) !== stable(Object.keys(y).sort())) throw Error('Unexpected assessment fields');
  };
  function validate(doc,template,availability) {
    exact(doc,template);
    const meta=new Set(['assessor_identity','assessed_at_utc','measured_review_seconds','blinding_attested','human_attested','items']);
    Object.keys(template).forEach(k=>{if(!meta.has(k)&&stable(doc[k])!==stable(template[k]))throw Error('Wrong source, kind or approval scope');});
    if(!Array.isArray(doc.items)||doc.items.length!==12)throw Error('Keep all twelve pairs');
    let worked=false;
    doc.items.forEach((record,i)=>{
      const expected=template.items[i];exact(record,expected);
      if(record.job!==expected.job)throw Error('Changed source pair order');
      if(!['not_reviewed','no_concern_identified','concern','uncertain'].includes(record.source_reasoning_review)||typeof record.source_reasoning_note!=='string')throw Error('Invalid separate source review');
      const sourceWork=record.source_reasoning_review!=='not_reviewed';
      if((record.source_reasoning_note&&!sourceWork)||(['concern','uncertain'].includes(record.source_reasoning_review)&&!record.source_reasoning_note.trim()))throw Error('Explain source concerns separately');
      worked=worked||sourceWork;exact(record.outputs,expected.outputs);
      for(const label of ['A','B']){
        const d=record.outputs[label],base=expected.outputs[label],original=availability[i][label];exact(d,base);
        if(d.candidate_sha256!==base.candidate_sha256)throw Error('Changed original candidate');
        if(!['pending','faithful','translation_error','uncertain'].includes(d.decision)||typeof d.explanation!=='string'||
          !Array.isArray(d.categories)||new Set(d.categories).size!==d.categories.length||d.categories.some(c=>typeof c!=='string'||!['operation','relation','entity','interval','grammar','mathematics','numerical_fidelity','reasoning_boundary','language','other'].includes(c)))throw Error('Invalid candidate decision/categories');
        if(d.decision==='pending'){
          if(stable(d)!==stable(base))throw Error('Pending outputs cannot acquire invented judgments');
          continue;
        }
        if(!original.available)throw Error('Unavailable output stays pending');
        worked=true;if(!d.explanation.trim())throw Error('Explain each non-pending judgment');
        if(d.decision==='translation_error'){
          if(!['minor','major','critical'].includes(d.severity)||!d.categories.length)throw Error('Error requires severity and categories');
        }else if(d.severity!==null||(d.decision==='faithful'&&(d.categories.length||d.correction!==null)))throw Error('Faithful/uncertain severity or faithful correction is invalid');
        if(d.decision==='faithful'&&original.status!=='accepted')throw Error('Hard-rejected output cannot become faithful');
        if(d.correction!==null&&(typeof d.correction!=='string'||!d.correction.trim()))throw Error('Correction must be a separate nonempty draft proposal');
      }
    });
    if(worked){
      if(typeof doc.assessor_identity!=='string'||doc.assessor_identity.length<2||doc.assessor_identity.length>160||doc.assessor_identity!==doc.assessor_identity.trim()||/[\x00-\x1f\x7f]/.test(doc.assessor_identity))throw Error('Record the actual assessor identity');
      if(typeof doc.assessed_at_utc!=='string'||!doc.assessed_at_utc.endsWith('Z')||!Number.isFinite(Date.parse(doc.assessed_at_utc)))throw Error('Record actual UTC time');
      if(doc.blinding_attested!==true||doc.human_attested!==(template.assessor_kind==='human'))throw Error('Fresh blinding/personal attestation required; AI is not human');
      if(doc.measured_review_seconds!==null&&(typeof doc.measured_review_seconds!=='number'||!Number.isFinite(doc.measured_review_seconds)||doc.measured_review_seconds<0))throw Error('Measured seconds must be actual, finite and nonnegative or unknown');
    }else for(const k of meta){if(k!=='items'&&stable(doc[k])!==stable(template[k]))throw Error('Pending task has no actual identity/time/attestation/duration');}
    return doc;
  }
  function makeDocument(template,availability,values,previous,clock){
    const doc=copy(template);doc.items=copy(values.items);doc.measured_review_seconds=values.measured_review_seconds;
    if(previous&&previous.assessor_identity===values.assessor_identity&&stable(previous.items)===stable(doc.items)&&previous.measured_review_seconds===doc.measured_review_seconds){
      return copy(validate(previous,template,availability));
    }
    const worked=doc.items.some(r=>r.source_reasoning_review!=='not_reviewed'||Object.values(r.outputs).some(d=>d.decision!=='pending'));
    if(worked){doc.assessor_identity=values.assessor_identity;doc.assessed_at_utc=clock();doc.blinding_attested=values.blinding_attested;doc.human_attested=template.assessor_kind==='human'?values.human_attested:false;}
    return validate(doc,template,availability);
  }
  const api={validate,makeDocument};if(typeof module!=='undefined'&&module.exports)module.exports=api;
  if(typeof document==='undefined')return;
  const template=PACKET.template,availability=PACKET.availability,el=id=>document.getElementById(id);
  const categories=['entity','grammar','interval','language','mathematics','numerical_fidelity','operation','other','reasoning_boundary','relation'];
  let previous=null;
  function state(i,label,clear){
    const key=i+'-'+label,decision=el('decision-'+key).value,available=availability[i][label].available;
    if(clear){
      if(['pending','faithful','uncertain'].includes(decision))el('severity-'+key).value='';
      if(['pending','faithful'].includes(decision)){categories.forEach(c=>el('category-'+key+'-'+c).checked=false);el('correction-'+key).value='';}
      if(decision==='pending')el('explanation-'+key).value='';
    }
    el('decision-'+key).disabled=!available;
    el('severity-'+key).disabled=!available||decision!=='translation_error';
    categories.forEach(c=>el('category-'+key+'-'+c).disabled=!available||['pending','faithful'].includes(decision));
    el('explanation-'+key).disabled=!available||decision==='pending';
    el('correction-'+key).disabled=!available||['pending','faithful'].includes(decision);
  }
  function values(){
    const doc=copy(template);
    doc.items.forEach((r,i)=>{
      r.source_reasoning_review=el('source-'+i).value;r.source_reasoning_note=el('source-note-'+i).value;
      for(const label of ['A','B']){
        const key=i+'-'+label,d=r.outputs[label];d.decision=el('decision-'+key).value;
        if(d.decision==='pending')continue;
        d.severity=el('severity-'+key).value||null;d.explanation=el('explanation-'+key).value;
        d.correction=el('correction-'+key).value===''?null:el('correction-'+key).value;
        const selected=categories.filter(c=>el('category-'+key+'-'+c).checked);
        const prior=previous?previous.items[i].outputs[label].categories:[];
        d.categories=prior.filter(c=>selected.includes(c)).concat(selected.filter(c=>!prior.includes(c)));
      }
    });
    doc.assessor_identity=el('identity').value;doc.measured_review_seconds=el('seconds').value===''?null:Number(el('seconds').value);
    doc.blinding_attested=el('blinding').checked;doc.human_attested=el('human').checked;
    return doc;
  }
  function progress(){
    let available=0,decided=0;
    availability.forEach((r,i)=>{for(const label of ['A','B']){if(r[label].available)available++;if(el('decision-'+i+'-'+label).value!=='pending')decided++;}});
    el('progress').textContent='All24 planned observations: '+available+' available; '+(24-available)+' unavailable; '+decided+' draft judgments. '+(available===0?'No generated translation is available; do not invent candidate judgments.':'Judgments remain unsealed until Python validation.');
  }
  template.items.forEach((r,i)=>{for(const label of ['A','B']){el('decision-'+i+'-'+label).addEventListener('change',()=>{state(i,label,true);progress();});state(i,label,false);}});
  el('save').addEventListener('click',()=>{
    try{
      const current=values(),doc=makeDocument(template,availability,current,previous,()=>new Date().toISOString());
      const unchanged=previous&&stable(doc)===stable(previous);
      const url=URL.createObjectURL(new Blob([JSON.stringify(doc,null,2)+'\n'],{type:'application/json;charset=utf-8'}));
      const link=document.createElement('a');link.href=url;link.download='ArabicPRM_Blinded_Assessment_'+template.assessor_kind+'.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
      previous=copy(doc);el('blinding').checked=false;el('human').checked=false;
      el('record-time').textContent='Original recorded time: '+(doc.assessed_at_utc||'none')+'. Unchanged copies preserve it; changed decisions need fresh attestation.';
      el('status').textContent=(unchanged?'Unchanged original identity/time preserved. ':'Saved separate unsealed draft. ')+'Mandatory Python Arabic/math/number/boundary validation and sealing remain; no human QC or requests authorized.';
    }catch(error){el('status').textContent=error.message;}
  });
  el('resume').addEventListener('change',async()=>{
    try{
      const file=el('resume').files[0];if(!file)return;
      const doc=validate(JSON.parse(await file.text()),template,availability);previous=copy(doc);
      doc.items.forEach((r,i)=>{
        el('source-'+i).value=r.source_reasoning_review;el('source-note-'+i).value=r.source_reasoning_note;
        for(const label of ['A','B']){const key=i+'-'+label,d=r.outputs[label];el('decision-'+key).value=d.decision;el('severity-'+key).value=d.severity||'';el('explanation-'+key).value=d.explanation;el('correction-'+key).value=d.correction===null?'':d.correction;categories.forEach(c=>el('category-'+key+'-'+c).checked=d.categories.includes(c));state(i,label,false);}
      });
      el('identity').value=doc.assessor_identity||'';el('seconds').value=doc.measured_review_seconds===null?'':String(doc.measured_review_seconds);
      el('blinding').checked=false;el('human').checked=false;
      el('record-time').textContent='Original recorded time: '+(doc.assessed_at_utc||'none')+'. Unchanged copies preserve it; changed decisions need fresh attestation.';
      el('status').textContent='Loaded the exact-source record; original saved file preserved. No mapping read and no record sealed.';progress();
    }catch(error){el('status').textContent=error.message;}
  });
  progress();
}());
