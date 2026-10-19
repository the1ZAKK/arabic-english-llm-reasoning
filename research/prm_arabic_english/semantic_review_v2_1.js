/* Local-only review and resume. No model/network client; no invented human QC. */
"use strict";
const categories = ["correct_arabic_mathematical_translation", "minor_grammar_or_style",
  "incorrect_mathematical_terminology", "changed_mathematical_meaning_or_operation",
  "incomplete_or_unsupported_semantic_judgment"];
const kind = "arabicprm_human_semantic_decisions_v2_1";
const fields = ["decision", "category", "severity", "justification", "proposed_correction"];
function normalizedValue(value) {
  return {decision: value.decision, category: value.decision === "pending" ? null : value.category,
    severity: value.decision === "pending" ? null : value.severity,
    justification: value.justification, proposed_correction: (value.proposed_correction || "").trim() || null};
}
function validateImported(bundle, doc) {
  const keys = ["schema_version", "kind", "audit_sha256", "plan_sha256", "training_eligible", "resumed_file_sha256", "decisions"];
  if (Object.keys(doc).sort().join() !== keys.sort().join() || doc.schema_version !== 1 || doc.kind !== kind ||
      doc.audit_sha256 !== bundle.audit_sha256 || doc.plan_sha256 !== bundle.audit.plan_sha256 ||
      doc.training_eligible !== false || !Array.isArray(doc.decisions) || doc.decisions.length !== bundle.audit.items.length ||
      (doc.resumed_file_sha256 !== null && !/^[0-9a-f]{64}$/.test(doc.resumed_file_sha256))) throw new Error("Saved file audit/plan/schema mismatch");
  doc.decisions.forEach((d, i) => {
    const item = bundle.audit.items[i];
    const expected = ["job", "item_sha256", "decision", "reviewer", "reviewed_at_utc", "human_attestation",
      "category", "severity", "justification", "proposed_correction", "review_seconds"];
    if (Object.keys(d).sort().join() !== expected.sort().join() || d.job !== item.job || d.item_sha256 !== item.item_sha256 ||
        typeof d.justification !== "string" || !["pending", "approved", "rejected", "needs_correction"].includes(d.decision) ||
        (d.proposed_correction !== null && typeof d.proposed_correction !== "string") ||
        (d.review_seconds !== null && (typeof d.review_seconds !== "number" || !Number.isFinite(d.review_seconds) || d.review_seconds < 0 || d.review_seconds > 86400))) throw new Error("Saved decision item/schema mismatch");
    if (d.decision === "pending") {
      if (d.reviewer !== null || d.reviewed_at_utc !== null || d.human_attestation !== false || d.category !== null || d.severity !== null) throw new Error("Pending cannot claim human QC");
    } else if (item.recorded_arabic === null || typeof d.reviewer !== "string" || !d.reviewer.trim() || d.human_attestation !== true ||
        typeof d.reviewed_at_utc !== "string" || !/(?:Z|\+00:00)$/.test(d.reviewed_at_utc) || !Number.isFinite(Date.parse(d.reviewed_at_utc)) ||
        !categories.includes(d.category) || !["none", "low", "medium", "high"].includes(d.severity)) throw new Error("Saved human provenance missing or invalid");
    if (d.decision === "approved" && d.proposed_correction !== null && d.proposed_correction !== item.recorded_arabic) throw new Error("Original approval cannot approve a different correction");
    if (d.decision === "needs_correction" && !d.proposed_correction) throw new Error("Missing correction proposal");
  });
  return doc;
}
function buildDecisions(bundle, values, reviewer, attestation, now, resumed = null, resumedHash = null) {
  if (values.length !== bundle.audit.items.length) throw new Error("Review coverage mismatch");
  if (resumed) validateImported(bundle, resumed);
  if ((resumed !== null) !== (resumedHash !== null) || (resumedHash !== null && !/^[0-9a-f]{64}$/.test(resumedHash))) throw new Error("Resume file identity missing");
  const decisions = bundle.audit.items.map((item, i) => {
    const value = normalizedValue(values[i]);
    const prior = resumed && resumed.decisions[i];
    if (prior && fields.every(k => value[k] === normalizedValue(prior)[k])) return {...prior};
    const active = value.decision !== "pending";
    if (active && (item.recorded_arabic === null || typeof reviewer !== "string" || !reviewer.trim() || attestation !== true)) throw new Error("Actual reviewer and explicit attestation required for changed decisions");
    if (active && (typeof now !== "string" || !now.endsWith("Z") || !Number.isFinite(Date.parse(now)))) throw new Error("Actual current UTC timestamp required");
    return {job: item.job, item_sha256: item.item_sha256, ...value,
      reviewer: active ? reviewer.trim() : null, reviewed_at_utc: active ? now : null,
      human_attestation: active, review_seconds: null};
  });
  return validateImported(bundle, {schema_version: 1, kind, audit_sha256: bundle.audit_sha256,
    plan_sha256: bundle.audit.plan_sha256, training_eligible: false, resumed_file_sha256: resumedHash, decisions});
}
function progress(values) {
  return {total: values.length, pending: values.filter(v => v.decision === "pending").length,
    decided: values.filter(v => v.decision !== "pending").length};
}
if (typeof module !== "undefined") module.exports = {buildDecisions, validateImported, progress};
if (typeof document !== "undefined") {
  const bundle = JSON.parse(document.getElementById("audit-data").textContent);
  const controls = []; let resumed = null, resumedHash = null;
  function text(parent, tag, value, direction) {
    const n = document.createElement(tag); n.textContent = value; if (direction) n.dir = direction; parent.appendChild(n); return n;
  }
  function select(parent, label, options) {
    const holder = text(parent, "label", label), n = document.createElement("select");
    options.forEach(v => {const o = document.createElement("option"); o.value = v; o.textContent = v || "Choose…"; n.appendChild(o);}); holder.appendChild(n); return n;
  }
  function values() {return controls.map(c => ({decision: c.decision.value, category: c.category.value,
    severity: c.severity.value, proposed_correction: c.correction.value, justification: c.justification.value}));}
  function update() {
    const p = progress(values()); document.getElementById("progress").textContent = `${p.decided}/${p.total} decided; ${p.pending} pending. `;
    const filter = document.getElementById("filter").value;
    controls.forEach((c, i) => {c.article.hidden = (filter === "pending" && c.decision.value !== "pending") ||
      (filter === "decided" && c.decision.value === "pending") || (filter === "risk" && !bundle.audit.items[i].analysis.flags.length);});
  }
  text(document.getElementById("evidence"), "p", "Generation: msa-single-fragment-v1. This is a new offline v2.1 review, not new generated output. Audit: " + bundle.audit_sha256);
  bundle.audit.items.forEach(item => {
    const a = document.createElement("article"); document.getElementById("items").appendChild(a); text(a, "h2", item.job);
    text(a, "p", "English target"); text(a, "pre", item.context.target_english);
    text(a, "p", "Original recorded Arabic / النص العربي المسجل"); text(a, "pre", item.recorded_arabic, "auto");
    text(a, "p", "Full source sentence"); text(a, "pre", item.context.current_field);
    const context = document.createElement("details"); a.appendChild(context); text(context, "summary", "Full problem and reasoning");
    text(context, "pre", item.context.problem); item.context.all_reasoning_steps.forEach((step, i) => text(context, "pre", `${i}: ${step}`));
    const source = document.createElement("details"); source.className = "source"; a.appendChild(source);
    text(source, "summary", "Separate English source/label audit — native rating: " + String(item.context.source_step_rating));
    text(source, "p", "Source ratings may be intentional negative examples or contain annotation concerns. Do not silently change them.");
    item.analysis.source_reasoning_warnings.forEach(n => text(source, "p", n.code + ": " + n.note));
    const ai = document.createElement("details"); a.appendChild(ai); text(ai, "summary", "Provisional AI review and suggestions — not human QC");
    text(ai, "p", item.provisional_case_review.note);
    item.analysis.flags.forEach(f => text(ai, "p", f.severity + " — " + f.code + ": " + f.explanation));
    if (!item.analysis.flags.length) text(ai, "p", "No heuristic flags does not establish semantic correctness.");
    text(ai, "pre", "Separate AI suggestion: " + (item.provisional_case_review.suggested_correction || "None; reviewer must decide"), "auto");
    const decision = select(a, "Your human decision", ["pending", "approved", "rejected", "needs_correction"]);
    const category = select(a, "Your category", ["", ...categories]); const severity = select(a, "Your severity", ["", "none", "low", "medium", "high"]);
    const correction = text(text(a, "label", "Your separate correction proposal"), "textarea", "", "auto");
    const justification = text(text(a, "label", "Your justification (record source concerns separately)"), "textarea", "");
    const hashes = document.createElement("details"); a.appendChild(hashes); text(hashes, "summary", "Provenance hashes");
    text(hashes, "code", JSON.stringify({parent_item: item.parent_item_sha256, item: item.item_sha256, context: item.context_sha256, output: item.output_sha256}));
    const control = {article: a, decision, category, severity, correction, justification}; controls.push(control);
    for (const node of [decision, category, severity, correction, justification]) node.addEventListener("input", update);
  });
  document.getElementById("filter").addEventListener("change", update); update();
  document.getElementById("load").addEventListener("change", async event => {
    try {
      const file = event.target.files[0]; if (!file) return;
      if (file.size > 2 * 1024 * 1024) throw new Error("Decision file too large");
      const raw = await file.arrayBuffer(); const candidate = validateImported(bundle, JSON.parse(new TextDecoder("utf-8", {fatal: true}).decode(raw)));
      const digest = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", raw)), b => b.toString(16).padStart(2, "0")).join("");
      controls.forEach((c, i) => {const d = candidate.decisions[i]; c.decision.value = d.decision; c.category.value = d.category || "";
        c.severity.value = d.severity || ""; c.correction.value = d.proposed_correction || ""; c.justification.value = d.justification;});
      resumed = candidate; resumedHash = digest; document.getElementById("attestation").checked = false; update();
      document.getElementById("status").textContent = "Loaded validated audit-bound decisions. Existing identities/timestamps preserved; changed decisions need fresh attestation. File SHA256: " + digest;
    } catch (e) {document.getElementById("status").textContent = e.message;}
  });
  document.getElementById("download").addEventListener("click", () => {
    try {
      const result = buildDecisions(bundle, values(), document.getElementById("reviewer").value,
        document.getElementById("attestation").checked, new Date().toISOString(), resumed, resumedHash);
      const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2) + "\n"], {type: "application/json"}));
      const a = document.createElement("a"); a.href = url; a.download = "human_decisions_v2_1_" + bundle.audit_sha256.slice(0, 12) + "_" + Date.now() + ".json";
      a.click(); URL.revokeObjectURL(url); document.getElementById("status").textContent = "Saved a separate decision file. Preserve previous files. Python validation is still required; no inference or training authorized.";
    } catch (e) {document.getElementById("status").textContent = e.message;}
  });
}
