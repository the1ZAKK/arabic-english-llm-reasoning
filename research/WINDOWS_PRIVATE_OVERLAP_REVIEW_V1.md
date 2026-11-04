# Private overlap worksheet after the clean-development check

The user reports the read-only comparison succeeded for `c909dfa` against `0a4ffd2`: 15 potential overlaps remain, with no new matches, checkout writes or inference authorization. No private worksheet was supplied or inspected here. That comparison leaves the original, backup and worksheet in place. The counts identify no specific change to recover. If a concrete local change later proves necessary, nominate it for separate human review with its purpose and evidence locally; do not automatically transfer it.

The user reports that the separate development checkout verified at `0a4ffd2db38d13914dbcd0a5aecee2572f507cd5`. Keep it separate from the original checkout and verified backup. The 15 possible overlaps came from the **earlier** comparison with `f72bffb`; neither a backup nor a successful clean checkout resolves them.

Download [private_overlap_review_v1.py](prm_arabic_english/private_overlap_review_v1.py) to Downloads. Use the **original sync-preflight** private `report.json` next to `backup_manifest.json` (under the timestamped `sync-preflight-v1` folder), not the clean-development share receipt. In PowerShell run this once, replacing the last quoted argument with the report's actual path:

```powershell
py -3.11 -I -S -B "$env:USERPROFILE\Downloads\private_overlap_review_v1.py" "C:\path\to\sync-preflight-v1\report.json"
```

The tool checks the receipt and its manifest hash and counts. It compares the reported path inventory against names from the exact two Git trees in the verified **development** checkout. It does not read worktree or backup snapshot file contents, run Git status, contact the network, write either checkout or backup, or apply a merge. Keep the output in its new folder under `%LOCALAPPDATA%\ArabicPRM\overlap-review-v1`. If it cannot verify the report binding or exact local development commit, stop and keep all evidence in place. A newer branch tip is not assumed to be installed on the laptop. If you later have a separately verified local development SHA, specify it with `--verified-commit <exact-sha>`.

Open `private-overlaps.json` locally. It preserves earlier-only overlaps and adds any current-only matches. Same normalized path and parent/child path matches are possible collisions; no collision or lack of collision decides content safety. For each row, inspect the private backup and current file only if needed, using a read-only viewer; record a separate private note: **preserve as local evidence**, **candidate for individually reviewed code transfer**, or **uncertain, keep in place**. Check staged vs unstaged status, case variants and directory matches. Protected research artifacts, checkpoints and ledgers, reviewer files, machine-specific settings, credentials and uncertain changes stay in place. Only deliberately selected code may be considered for a later reviewed transfer, after this procedure. Never use the worksheet to apply a batch copy, stash, pull or merge.

If reporting back, share only the newly generated `share-status.json`. It has counts and public SHAs, no paths or file contents. Keep the private worksheet, original reports and backup on the laptop.
