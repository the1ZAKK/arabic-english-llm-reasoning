"""Immutable local bilingual review artifacts. No model, approval or export runner."""
import argparse
import base64
from datetime import datetime
import hashlib
from html import escape
import json
from pathlib import Path
import tempfile

import recover_v2 as baseline
import resume_v2_local as legacy
from source_preserving_translation import validate_slot

STATES = ("pending", "approved", "rejected", "needs_correction")
JS = Path(__file__).with_suffix(".js")


def pending(audit):
    return {"schema_version": 1, "kind": "arabicprm_human_semantic_decisions_v2",
        "audit_sha256": baseline.digest(audit), "plan_sha256": audit["plan_sha256"],
        "training_eligible": False, "decisions": [{"job": item["job"], "item_sha256": item["item_sha256"],
            "decision": "pending", "reviewer": None, "reviewed_at_utc": None, "human_attestation": False,
            "category": None, "severity": None, "justification": "", "proposed_correction": None,
            "review_seconds": None} for item in audit["items"]]}


def validate_decisions(audit, document):
    """Validate recorded human provenance; cannot authenticate a person's identity."""
    for item in audit["items"]:
        context, output = item["context"], item["recorded_arabic"]
        if (item["item_sha256"] != baseline.digest({k: v for k, v in item.items() if k != "item_sha256"}) or
                item["context_sha256"] != baseline.digest(context) or
                item["output_sha256"] != (legacy.sha(output.encode("utf-8")) if output is not None else None) or
                context["source_field_sha256"] != legacy.sha(context["current_field"].encode("utf-8")) or
                context["source_slot_sha256"] != legacy.sha(context["target_english"].encode("utf-8"))):
            raise ValueError("Original audit item/source/output integrity mismatch")
    if (document.get("schema_version") != 1 or document.get("kind") != "arabicprm_human_semantic_decisions_v2" or
            document.get("audit_sha256") != baseline.digest(audit) or document.get("plan_sha256") != audit["plan_sha256"] or
            document.get("training_eligible") is not False):
        raise ValueError("Human decision audit/plan binding mismatch")
    decisions = document.get("decisions")
    if not isinstance(decisions, list) or [d.get("job") for d in decisions] != [i["job"] for i in audit["items"]]:
        raise ValueError("Human decision coverage/order mismatch")
    from semantic_recovery_v2 import CATEGORIES
    for item, decision in zip(audit["items"], decisions):
        if set(decision) != set(pending(audit)["decisions"][0]) or decision["item_sha256"] != item["item_sha256"]:
            raise ValueError("Human decision item hash/schema mismatch")
        state, correction = decision["decision"], decision["proposed_correction"]
        if state not in STATES:
            raise ValueError("Unknown human decision state")
        if not isinstance(decision["justification"], str):
            raise ValueError("Reviewer justification must be text")
        seconds = decision["review_seconds"]
        if seconds is not None and (type(seconds) not in (int, float) or not 0 <= seconds <= 86400):
            raise ValueError("Invalid optional measured review duration")
        if correction is not None:
            validate_slot(item["context"]["target_english"], correction)
        if state == "pending":
            if (decision["reviewer"] is not None or decision["reviewed_at_utc"] is not None or
                    decision["human_attestation"] is not False or decision["category"] is not None or decision["severity"] is not None):
                raise ValueError("Pending decisions cannot claim completed human review")
            continue
        if item["recorded_arabic"] is None:
            raise ValueError("Cannot review an unavailable model output")
        if (not isinstance(decision["reviewer"], str) or not decision["reviewer"].strip() or
                decision["human_attestation"] is not True):
            raise ValueError("Actual human reviewer and explicit attestation are required")
        try:
            stamp = datetime.fromisoformat(decision["reviewed_at_utc"].replace("Z", "+00:00"))
            if stamp.utcoffset() is None or stamp.utcoffset().total_seconds() != 0:
                raise ValueError("Expected UTC")
        except (ValueError, TypeError, AttributeError):
            raise ValueError("Actual UTC human-review timestamp required") from None
        if decision["category"] not in CATEGORIES or decision["severity"] not in ("none", "low", "medium", "high"):
            raise ValueError("A human category and severity are required")
        if state == "approved" and correction not in (None, item["recorded_arabic"]):
            raise ValueError("Approval concerns the original output; a different correction needs separate review")
        if state == "needs_correction" and not correction:
            raise ValueError("Needs-correction decision requires a separately recorded proposal")
    return document


def immutable_directory(target, files):
    """Atomic create-or-verify, including safe restart after a failed build."""
    target = baseline.safe_path(target)
    if target.exists():
        actual = {}
        for path in target.rglob("*"):
            baseline.safe_path(path)
            if path.is_file():
                actual[path.relative_to(target).as_posix()] = path.read_bytes()
        if actual != files:
            raise ValueError("Existing immutable review changed; preserved without overwrite")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="semantic-review-", dir=target.parent) as temporary:
        build = Path(temporary) / "review"
        build.mkdir()
        for name, raw in files.items():
            with (build / name).open("xb") as stream:
                stream.write(raw)
        build.rename(target)


def qc_markdown(audit):
    text = ["# Provisional AI bilingual semantic review — human QC pending", "",
        "These deterministic lexical warnings are not semantic approval. Missing outputs cannot be audited. "
        "Original Arabic is retained verbatim; proposals never replace it. Full source reasoning may itself contain errors.", "",
        "Audit SHA256: `" + baseline.digest(audit) + "`", "",
        "Evidence: " + escape(json.dumps(audit["evidence"], ensure_ascii=False, sort_keys=True)), ""]
    for item in audit["items"]:
        context, analysis = item["context"], item["analysis"]
        text.extend(["## " + item["job"], "", "Original English target: " + escape(context["target_english"]), "",
            "Recorded Arabic / النص المسجل: " + escape(item["recorded_arabic"] if item["recorded_arabic"] is not None else "UNAVAILABLE / غير متاح"), "",
            "AI proposed correction / اقتراح آلي: " + escape(analysis["suggested_correction"] or "None; bilingual reviewer must decide / لا يوجد اقتراح"), "",
            "Category: `" + analysis["provisional_category"] + "`. Semantic acceptance: not established. Human decision: pending.", "",
            "Source sentence: " + escape(context["current_field"]), "", "Problem: " + escape(context["problem"]), ""])
        for index, step in enumerate(context["all_reasoning_steps"]):
            text.extend([f"Step {index}: " + escape(step), ""])
        text.extend(["Risk flags and severity: " + escape(json.dumps(analysis["flags"], ensure_ascii=False)), "",
            "Separate source-reasoning cautions: " + escape(json.dumps(analysis["source_reasoning_warnings"], ensure_ascii=False)), "",
            "Explanation: " + analysis["explanation"], "",
            "Source record: `" + context["source_record_sha256"] + "`; field: `" + context["source_field_sha256"] +
            "`; slot: `" + context["source_slot_sha256"] + "`; output: `" + str(item["output_sha256"]) +
            "`; context: `" + item["context_sha256"] + "`; review item: `" + item["item_sha256"] + "`.", ""])
    return "\n".join(text).encode("utf-8")


def review_html(audit):
    script = JS.read_text(encoding="utf-8")
    if "</script" in script.lower():
        raise ValueError("Unsafe inline review code")
    script_hash = base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode("ascii")
    data = json.dumps({"audit": audit, "audit_sha256": baseline.digest(audit)}, ensure_ascii=False, sort_keys=True)
    for a, b in (("&", "\\u0026"), ("<", "\\u003c"), (">", "\\u003e"), ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        data = data.replace(a, b)
    return ("<!doctype html><html lang='en'><meta charset='utf-8'>"
        "<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; connect-src 'none'; "
        "img-src 'none'; style-src 'unsafe-inline'; script-src 'sha256-" + script_hash + "'; base-uri 'none'; form-action 'none'\">"
        "<title>ArabicPRM bilingual review — pending</title><style>"
        "body{font:17px system-ui;margin:2rem auto;max-width:1150px;padding:0 1rem;color:#162735;background:#fafcfe}"
        "article{background:white;border:1px solid #b5c9d2;padding:1rem;margin:1.5rem 0;border-radius:8px}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;line-height:1.6}"
        "label{display:block;margin:.8rem 0}select,input,textarea,button{font:inherit;padding:.5rem;max-width:95%}"
        "textarea{display:block;width:95%}code{overflow-wrap:anywhere}strong{color:#9b3500}</style>"
        "<h1>Bilingual mathematical review / مراجعة رياضية ثنائية اللغة</h1>"
        "<p><strong>Provisional AI risk review. All human states start pending. No model requests or training export.</strong></p>"
        "<p>Approve means approve the original candidate. Record a different correction as needs correction; it needs later independent review. "
        "Source errors must be flagged separately without repairing the English. Downloaded decisions are local records, not authenticated identities or training eligibility.</p>"
        "<p id='evidence'></p><label>Your actual reviewer identity <input id='reviewer' autocomplete='off'></label>"
        "<label><input id='attestation' type='checkbox'> I personally compared the source, context and original Arabic for every non-pending decision below.</label>"
        "<div id='items'></div><button id='download' type='button'>Save my human decisions JSON</button>"
        "<p id='status' role='status'></p><p>No automatic persistence. Save before closing. Reopening starts pending and cannot overwrite an earlier decision file.</p>"
        "<script id='audit-data' type='application/json'>" + data + "</script><script>" + script + "</script></html>").encode("utf-8")


def write_review(target, audit, proposal):
    files = {"semantic_audit.json": legacy.encoded(audit), "experiment_proposal_NOT_APPROVED.json": legacy.encoded(proposal),
        "human_decisions_PENDING.json": legacy.encoded(pending(audit)), "human_review.html": review_html(audit),
        "provisional_bilingual_QC.md": qc_markdown(audit)}
    manifest = {"schema_version": 1, "audit_sha256": baseline.digest(audit),
                "files_sha256": {name: legacy.sha(raw) for name, raw in files.items()},
                "generation_requests_authorized": 0, "training_eligible": False}
    files["review_manifest.json"] = legacy.encoded(manifest)
    immutable_directory(target, files)


def import_decisions(audit_path, decisions_path):
    audit_path = baseline.safe_path(audit_path)
    manifest = legacy.parse(baseline.safe_path(audit_path.parent / "review_manifest.json").read_bytes())
    if audit_path.name != "semantic_audit.json":
        raise ValueError("Expected immutable semantic_audit.json")
    for name, expected in manifest["files_sha256"].items():
        path = baseline.safe_path(audit_path.parent / name)
        if path.parent != audit_path.parent or legacy.sha(path.read_bytes()) != expected:
            raise ValueError("Immutable review manifest/file mismatch")
    audit = legacy.parse(audit_path.read_bytes())
    if manifest["audit_sha256"] != baseline.digest(audit):
        raise ValueError("Review manifest audit identity mismatch")
    document = legacy.parse(baseline.safe_path(decisions_path).read_bytes())
    validate_decisions(audit, document)
    target = baseline.safe_path(audit_path.parent.parent / "human_reviews" / baseline.digest(audit) / baseline.digest(document))
    immutable_directory(target, {"human_decisions.json": legacy.encoded(document)})
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--human-decisions", required=True, type=Path)
    args = parser.parse_args()
    print("Recorded separately; no training eligibility or inference: " + str(import_decisions(args.audit, args.human_decisions)))


if __name__ == "__main__":
    main()
