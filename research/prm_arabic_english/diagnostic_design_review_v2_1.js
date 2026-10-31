/* Offline design review only. No model, HTTP, budget or human-QC approval path. */
(function () {
  'use strict';
  const copy = value => JSON.parse(JSON.stringify(value));
  const canonical = value => JSON.stringify(value, (key, item) => item && typeof item === 'object' && !Array.isArray(item)
    ? Object.keys(item).sort().reduce((out, k) => { out[k] = item[k]; return out; }, {}) : item);
  const exact = (value, expected) => {
    if (!value || Array.isArray(value) || typeof value !== 'object' ||
        canonical(Object.keys(value).sort()) !== canonical(Object.keys(expected).sort())) throw Error('Unexpected review fields');
  };
  function validate(doc, template) {
    exact(doc, template);
    const mutable = new Set(['reviewer_identity', 'reviewed_at_utc', 'timestamp_source', 'human_attested', 'decision',
      'summary', 'checks', 'slots', 'disclosures', 'question_answers', 'acknowledgements']);
    Object.keys(template).forEach(k => {
      if (!mutable.has(k) && canonical(doc[k]) !== canonical(template[k])) throw Error('Wrong package, scope or human-review identity');
    });
    if (!['pending', 'approve_design', 'request_changes'].includes(doc.decision) || typeof doc.summary !== 'string') throw Error('Invalid design decision');
    exact(doc.checks, template.checks);
    if (!Array.isArray(doc.slots) || doc.slots.length !== 12) throw Error('Keep all twelve slots');
    const rows = Object.values(doc.checks);
    doc.slots.forEach((slot, i) => {
      exact(slot, template.slots[i]);
      if (slot.job !== template.slots[i].job) throw Error('Changed slot identity or order');
      rows.push({status: slot.status, note: slot.note});
    });
    rows.forEach(row => {
      exact(row, {status: '', note: ''});
      if (!['pending', 'reviewed', 'changes_requested'].includes(row.status) || typeof row.note !== 'string' ||
          (row.status === 'changes_requested' && !row.note.trim())) throw Error('Explain checklist changes');
    });
    exact(doc.disclosures, template.disclosures);
    Object.values(doc.disclosures).forEach(row => {
      exact(row, {status: '', details: ''});
      if (!['not_disclosed', 'none', 'declared'].includes(row.status) || typeof row.details !== 'string' ||
          (row.status === 'declared' && !row.details.trim())) throw Error('Explain declared exposure/conflict');
    });
    exact(doc.question_answers, template.question_answers);
    if (Object.values(doc.question_answers).some(v => typeof v !== 'string')) throw Error('Invalid design answer');
    exact(doc.acknowledgements, template.acknowledgements);
    if (Object.values(doc.acknowledgements).some(v => typeof v !== 'boolean')) throw Error('Explicit scope acknowledgements required');
    if (doc.decision === 'pending') {
      ['reviewer_identity', 'reviewed_at_utc', 'timestamp_source', 'human_attested'].forEach(k => {
        if (canonical(doc[k]) !== canonical(template[k])) throw Error('Pending drafts have no completed human metadata');
      });
    } else {
      if (typeof doc.reviewer_identity !== 'string' || doc.reviewer_identity.length < 2 || doc.reviewer_identity.length > 160 ||
          doc.reviewer_identity !== doc.reviewer_identity.trim() || /[\x00-\x1f\x7f]/.test(doc.reviewer_identity) ||
          typeof doc.reviewed_at_utc !== 'string' || !doc.reviewed_at_utc.endsWith('Z') || !Number.isFinite(Date.parse(doc.reviewed_at_utc)) ||
          doc.timestamp_source !== 'reviewer_supplied_utc_clock_assertion' || doc.human_attested !== true || !doc.summary.trim()) {
        throw Error('Actual human identity, UTC clock assertion, rationale and personal attestation are required');
      }
      if (doc.decision === 'approve_design' && (rows.some(r => r.status !== 'reviewed') ||
          Object.values(doc.disclosures).some(r => r.status === 'not_disclosed') ||
          Object.values(doc.question_answers).some(v => !v.trim()) || !Object.values(doc.acknowledgements).every(Boolean))) {
        throw Error('Review every slot/check, disclose conflicts, answer questions and acknowledge the limits');
      }
    }
    return doc;
  }
  function makeDocument(template, values, clock) {
    const doc = copy(template);
    ['decision', 'summary', 'checks', 'slots', 'disclosures', 'question_answers', 'acknowledgements'].forEach(k => { doc[k] = copy(values[k]); });
    if (doc.decision !== 'pending') {
      doc.reviewer_identity = values.reviewer_identity;
      doc.reviewed_at_utc = clock();
      doc.timestamp_source = 'reviewer_supplied_utc_clock_assertion';
      doc.human_attested = values.human_attested;
    }
    return validate(doc, template);
  }
  const api = {validate, makeDocument};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof document === 'undefined') return;
  const template = DESIGN.template;
  const el = id => document.getElementById(id);
  const status = text => { el('status').textContent = text; };
  function values() {
    const doc = copy(template);
    doc.reviewer_identity = el('reviewer').value;
    doc.human_attested = el('human-attestation').checked;
    doc.decision = el('decision').value;
    doc.summary = el('summary').value;
    Object.keys(doc.checks).forEach(k => { doc.checks[k] = {status: el('check-' + k).value, note: el('check-note-' + k).value}; });
    doc.slots.forEach((r, i) => { r.status = el('slot-' + i).value; r.note = el('slot-note-' + i).value; });
    Object.keys(doc.disclosures).forEach(k => { doc.disclosures[k] = {status: el('disclosure-' + k).value, details: el('disclosure-note-' + k).value}; });
    Object.keys(doc.question_answers).forEach(k => { doc.question_answers[k] = el('question-' + k).value; });
    Object.keys(doc.acknowledgements).forEach(k => { doc.acknowledgements[k] = el('ack-' + k).checked; });
    return doc;
  }
  el('save').addEventListener('click', () => {
    try {
      const doc = makeDocument(template, values(), () => new Date().toISOString());
      const url = URL.createObjectURL(new Blob([JSON.stringify(doc, null, 2) + '\n'], {type: 'application/json;charset=utf-8'}));
      const link = document.createElement('a');
      link.href = url; link.download = 'ArabicPRM_Diagnostic24_Design_Review.json'; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      status('Saved design review only. No requests or translation QC approved / تم الحفظ دون السماح بأي توليد.');
    } catch (error) { status(error.message); }
  });
  el('resume').addEventListener('change', async () => {
    try {
      const file = el('resume').files[0];
      if (!file) return;
      const doc = validate(JSON.parse(await file.text()), template);
      Object.keys(doc.checks).forEach(k => { el('check-' + k).value = doc.checks[k].status; el('check-note-' + k).value = doc.checks[k].note; });
      doc.slots.forEach((r, i) => { el('slot-' + i).value = r.status; el('slot-note-' + i).value = r.note; });
      Object.keys(doc.disclosures).forEach(k => { el('disclosure-' + k).value = doc.disclosures[k].status; el('disclosure-note-' + k).value = doc.disclosures[k].details; });
      Object.keys(doc.question_answers).forEach(k => { el('question-' + k).value = doc.question_answers[k]; });
      Object.keys(doc.acknowledgements).forEach(k => { el('ack-' + k).checked = doc.acknowledgements[k]; });
      el('reviewer').value = doc.reviewer_identity || '';
      el('decision').value = doc.decision; el('summary').value = doc.summary;
      el('human-attestation').checked = false;
      status('Loaded this exact package review. Original file preserved; any final re-export requires fresh personal attestation and records a new browser UTC time.');
    } catch (error) { status(error.message); }
  });
  status('All human decisions start pending / جميع القرارات البشرية معلقة.');
}());
