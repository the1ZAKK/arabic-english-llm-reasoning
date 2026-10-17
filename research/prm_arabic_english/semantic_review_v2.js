/* Offline reviewer UI. Pure decision builder is also exercised by Node in CI. */
"use strict";
const categories = ["correct_arabic_mathematical_translation", "minor_grammar_or_style",
  "incorrect_mathematical_terminology", "changed_mathematical_meaning_or_operation",
  "incomplete_or_unsupported_semantic_judgment"];
function buildDecisions(bundle, values, reviewer, attestation, now) {
  if (values.length !== bundle.audit.items.length) throw new Error("Review coverage mismatch");
  const decisions = bundle.audit.items.map((item, index) => {
    const value = values[index];
    if (!["pending", "approved", "rejected", "needs_correction"].includes(value.decision)) throw new Error("Unknown decision");
    const active = value.decision !== "pending";
    if (active && (item.recorded_arabic === null || !reviewer.trim() || attestation !== true)) {
      throw new Error("A real output, your actual identity and explicit human attestation are required");
    }
    if (active && (!categories.includes(value.category) || !["none", "low", "medium", "high"].includes(value.severity))) {
      throw new Error("Select a category and severity for every non-pending decision");
    }
    const correction = value.proposed_correction.trim() || null;
    if (value.decision === "approved" && correction !== null && correction !== item.recorded_arabic) {
      throw new Error("A different correction needs separate review; approval concerns the original candidate");
    }
    if (value.decision === "needs_correction" && !correction) throw new Error("Enter a separate proposed correction");
    if (active && (!now || !Number.isFinite(Date.parse(now)))) throw new Error("Actual current UTC timestamp required");
    return {job: item.job, item_sha256: item.item_sha256, decision: value.decision,
      reviewer: active ? reviewer.trim() : null, reviewed_at_utc: active ? now : null,
      human_attestation: active, category: active ? value.category : null, severity: active ? value.severity : null,
      justification: value.justification, proposed_correction: correction, review_seconds: null};
  });
  return {schema_version: 1, kind: "arabicprm_human_semantic_decisions_v2", audit_sha256: bundle.audit_sha256,
    plan_sha256: bundle.audit.plan_sha256, training_eligible: false, decisions};
}
if (typeof module !== "undefined") module.exports = {buildDecisions};
if (typeof document !== "undefined") {
  const bundle = JSON.parse(document.getElementById("audit-data").textContent);
  const controls = [];
  function text(parent, tag, value, direction) {
    const node = document.createElement(tag); node.textContent = value;
    if (direction) node.dir = direction;
    parent.appendChild(node); return node;
  }
  function select(parent, label, options) {
    const holder = text(parent, "label", label); const node = document.createElement("select");
    options.forEach(value => {const option = document.createElement("option"); option.value = value; option.textContent = value || "Choose…"; node.appendChild(option);});
    holder.appendChild(node); return node;
  }
  text(document.getElementById("evidence"), "code", JSON.stringify(bundle.audit.evidence));
  bundle.audit.items.forEach(item => {
    const article = document.createElement("article"); document.getElementById("items").appendChild(article);
    text(article, "h2", item.job);
    text(article, "p", "Target English / المقطع الإنجليزي"); text(article, "pre", item.context.target_english);
    text(article, "p", "Original model Arabic / النص العربي الأصلي");
    text(article, "pre", item.recorded_arabic === null ? "UNAVAILABLE / غير متاح" : item.recorded_arabic, "auto");
    text(article, "p", "Full source sentence"); text(article, "pre", item.context.current_field);
    const details = document.createElement("details"); article.appendChild(details);
    text(details, "summary", "Full problem and reasoning / المسألة والاستدلال كاملاً");
    text(details, "pre", item.context.problem);
    item.context.all_reasoning_steps.forEach((step, index) => text(details, "pre", String(index) + ": " + step));
    text(article, "p", "Provisional AI warnings / تنبيهات آلية أولية");
    text(article, "pre", JSON.stringify(item.analysis, null, 2));
    text(article, "code", JSON.stringify({source_record: item.context.source_record_sha256, source_field: item.context.source_field_sha256,
      source_slot: item.context.source_slot_sha256, output: item.output_sha256, context: item.context_sha256, item: item.item_sha256}));
    const decision = select(article, "Your human decision", ["pending", "approved", "rejected", "needs_correction"]);
    const category = select(article, "Your error category", ["", ...categories]);
    const severity = select(article, "Your severity", ["", "none", "low", "medium", "high"]);
    const correctionLabel = text(article, "label", "Your separate correction proposal (never replaces the original)");
    const correction = document.createElement("textarea"); correction.dir = "auto"; correctionLabel.appendChild(correction);
    const reasonLabel = text(article, "label", "Your justification / تعليل المراجع");
    const justification = document.createElement("textarea"); reasonLabel.appendChild(justification);
    controls.push({decision, category, severity, correction, justification});
  });
  document.getElementById("download").addEventListener("click", () => {
    try {
      const values = controls.map(c => ({decision: c.decision.value, category: c.category.value, severity: c.severity.value,
        proposed_correction: c.correction.value, justification: c.justification.value}));
      const result = buildDecisions(bundle, values, document.getElementById("reviewer").value,
        document.getElementById("attestation").checked, new Date().toISOString());
      const url = URL.createObjectURL(new Blob([JSON.stringify(result, null, 2) + "\n"], {type: "application/json"}));
      const anchor = document.createElement("a"); anchor.href = url;
      anchor.download = "human_decisions_" + bundle.audit_sha256.slice(0, 12) + "_" + Date.now() + ".json";
      anchor.click(); URL.revokeObjectURL(url);
      document.getElementById("status").textContent = "Saved a separate local decision file. Keep the original audit and outputs. This does not authorize training or inference.";
    } catch (error) {document.getElementById("status").textContent = error.message;}
  });
}
