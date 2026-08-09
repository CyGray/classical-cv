# Result Metadata

`RESULTS_MANIFEST.json` is the per-artifact inventory: source path, source
script, checksum, commit/time, status, and rerun flag. Regenerate it with:

`python scripts/reporting/generate_results_manifest.py`

Read `PROVENANCE_AUDIT.md` for status meanings, known invalid runs, stand-ins,
and manuscript/vector requirements. Do not cite an artifact until its manifest
record and status have been checked.
