# v4.5 — isolated Windows CUDA preparation

22 November 2026. Preparation only; **installation pending separate approval**.
The v4.4 experiment NO-GO remains unchanged. Current milestone: resolve and
actually hash the complete binary wheel graph on Windows CPython 3.11.9 x64.
No complete lock is claimed until that job succeeds. No target runtime packages
are installed or imported by resolution; no model operation is performed.

The ten v4.3 runtime pins are retained. Two installation-tool pins are separately
specified: pip 25.3 and setuptools 80.9.0, both with published universal Python
wheels on official PyPI. These prevent an unrecorded ensurepip bootstrap version
from becoming the final environment. They are installation tooling, not recovered
historical dependencies. Resolver pip is the existing CI interpreter's pip and its
actual version is recorded. Binary artifacts come from official PyPI, except the
exact Torch cu126 wheel from the official PyTorch index. No extra-index mixing,
source builds, dependency-name substitutions, models or vendor forks are allowed.

The native resolver validates compatible wheel tags, Requires-Python and the full
marker/extra-aware Requires-Dist closure. Every artifact is downloaded and its
actual bytes are SHA256 checked against official resolution/index evidence. ZIP
payload sizes are measured; installed footprint is not yet measured. Static API
and CUDA DLL presence checks do not establish import or hardware compatibility.

The readiness/installer workflow is being prepared separately. Its default will
be a zero-download dry-run. No active installation approval, checkpoint selection,
model-fit authorization or experiment budget is created in this milestone.
