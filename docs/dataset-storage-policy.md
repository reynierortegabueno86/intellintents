# Dataset Storage Policy — IntellIntents

**Subject:** `GPTAdvisorProcessedConv` corpus (id 4) and all derived artifacts (run 4 classifications, exports, application database, LLM response cache).
**Effective date:** 2026-05-16
**Owner:** Project Lead (hgarcia@gptadvisor.com)
**Review cadence:** Quarterly, or on any change of custodian / device.

---

## 1. Custody principle

The corpus contains real client conversations of a Spanish investment firm. **It is treated as confidential at all times.** Distribution is restricted to a single local custody point: the project lead's workstation. There is no shared copy, no cloud sync, no remote backup, no third-party processor.

## 2. Authoritative locations (local only)

All paths below are relative to the project working directory `/Users/reynier/Work/PythonProjects/intellintents/` on the project lead's workstation. **No other copy exists or is authorised to exist.**

| Path | Approx. size | Content |
|---|---:|---|
| `GPTAdvisorProcessedConv.jsonl` | 317 MB | Raw conversations, turn-by-turn, unclassified |
| `full_classified_dataset.json` | 317 MB | Conversations + run 4 classifications |
| `full_classified_conversations.json` | 765 MB | Flat denormalised view (one row per turn) |
| `run_export.json` | 765 MB | Snapshot of experiment run 4 |
| `backend/intellintents.db` | 1.2 GB | SQLite — authoritative app DB (datasets, conversations, turns, classifications, runs) |
| `llm_cache.db` | 8.3 MB | OpenAI/Anthropic response cache — guarantees run 4 reproducibility |

Total custody footprint: **~3.4 GB**.

## 3. What this policy forbids

The following are explicitly **not authorised** for the dataset or any derivative:

- ❌ Commit/push to **any git remote** (GitHub, GitLab, Bitbucket, internal mirrors).
- ❌ Upload to **any object storage** (S3, GCS, Azure Blob, R2, MinIO, Wasabi).
- ❌ Publish to **dataset hubs** (Hugging Face, Kaggle, OpenML).
- ❌ Bake into **container images** (Docker, OCI) or **CI artifacts**.
- ❌ Share via **collaboration tools** (Slack, Teams, Drive, Dropbox, OneDrive, iCloud, Notion, email attachment).
- ❌ Copy to **removable media** (USB, external SSD) unless full-disk encrypted and explicitly tracked in §6.
- ❌ Process by **third-party APIs** beyond the LLM calls already cached in `llm_cache.db` (no new external calls that would re-transmit raw text).

## 4. Repository hygiene (enforced)

`.gitignore` excludes the corpus paths so that an accidental `git add -A` cannot stage them:

```
*.jsonl
full_classified_*.json
run_export.json
*.db
*.db-shm
*.db-wal
*.db-journal
recovery_report.txt
backend/recovery_report.txt
```

**Verification command** (must return empty other than the Python module `llm_cache.py`):

```bash
git ls-files | grep -E "jsonl|full_classified|run_export|intellintents\.db|llm_cache\.db"
```

If this command ever returns a `.db`, `.jsonl`, `.json` data path, or a Drive/iCloud-shadowed copy, treat it as an incident under §7.

## 5. Workstation hardening checklist (one-time)

To be confirmed by the custodian and re-checked on any device change:

- [ ] `Work/` directory is **not** included in iCloud Drive / Desktop & Documents sync (System Settings → Apple ID → iCloud → iCloud Drive → Options).
- [ ] Workstation has **FileVault** (or equivalent full-disk encryption) enabled.
- [ ] Time Machine / equivalent backup either excludes `Work/PythonProjects/intellintents/` or writes only to an **encrypted, locally-attached** disk that itself stays on premises.
- [ ] No Dropbox / Google Drive / OneDrive client is syncing the working directory.
- [ ] Screen lock under 5 minutes, strong password, no shared OS account.

## 6. Authorised copies register

A copy is **authorised** only when listed below, signed by the project lead, and time-bounded. Empty by default.

| Date | Destination (device + path) | Purpose | Retention until | Sign-off |
|---|---|---|---|---|
| — | — | — | — | — |

Any copy not in this table is unauthorised and must be deleted on discovery.

## 7. Incident handling

On any of the following — accidental commit, upload, share-link creation, sync to a cloud provider, lost device, or detection by tooling — the custodian must:

1. Within **1 hour**: revoke/delete the offending copy (force-push removal, revoke share link, wipe device, etc.).
2. Within **24 hours**: notify the firm's DPO and Compliance lead with a written record (what leaked, when, scope, mitigation).
3. Within **72 hours** (GDPR Art. 33): if a personal-data breach risk is assessed as non-negligible, the DPO files notification to AEPD.
4. Update §6 and add a remediation note to the project changelog.

## 8. Decommission / deletion procedure

When the project concludes or the custodian rotates:

1. Generate SHA-256 manifest of all paths in §2 → save to `docs/dataset-manifest-final.txt` (manifest only — no data).
2. Securely erase all paths in §2 using `rm -P` (macOS) or `shred -u` (Linux equivalent) on the local disk.
3. Re-run the verification command from §4 to confirm working tree is clean.
4. Sign off in the project closure record.

## 9. Reproducibility note

The corpus is not redistributed even in anonymised form. Anyone reproducing the analysis must do so on the custodian's workstation, or by being added as a new authorised custodian under §6 — which in turn triggers §5 hardening and §3 forbidden-actions briefing.
