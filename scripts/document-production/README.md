# Document production scripts

This folder holds reusable automation for manuscript production. Keep final
papers, templates, author-reference images, and claim-evidence documents in
`docs/`; do not place generators or scratch outputs there.

## LS-Face Springer build

Run the macro-preserving LS-Face build from the workspace root:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\document-production\build-springer-paper.ps1
```

The script copies `docs/splnproc2510.docm`, migrates the LS-Face content from
`classical-cv/docs/PAPER.md`, keeps Abstract and Introduction reserved for
Doc Oh, and writes `docs/lsface_hybrid_independence_testing.docm`. It disables
macro execution during automation and verifies that the original VBA project
is retained exactly.
