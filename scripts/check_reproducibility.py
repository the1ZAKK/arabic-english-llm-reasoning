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
)

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromNames(MODULES)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)

