"""Run the explicitly selected offline, standard-library research checks."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "research" / "prm_arabic_english"))
MODULES = (
    "test_prm800k_ingest",
    "test_translation_batch",
    "test_materialize_translation",
    "test_materialize_authorized_normalizations",
    "test_reviewed_export",
    "test_source_quarantine",
    "test_prm800k_production_sample",
    "test_select_production_translation_set",
    "test_resume_v2_local",
    "test_source_preserving_translation",
    "test_unattended_v2",
    "test_triage_exhausted_v2",
    "test_prepare_v2_recovery",
    "test_recover_v2",
    "test_recovery_runtime",
    "test_pilot_preparation_v1",
    "test_pilot_execution_v1",
    "test_project_evidence_v2",
    "test_semantic_recovery_v2",
    "test_semantic_runtime_v2",
    "test_research_contracts_v2",
)

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromNames(MODULES)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)

