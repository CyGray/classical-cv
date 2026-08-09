# Hardware enrollment

Use one folder per person. Capture at least three varied, well-lit, single-face photos per person.

```text
captures/
  Alice Cruz/
    001.jpg
    002.jpg
    003.jpg
  Ben Reyes/
    001.jpg
    002.jpg
    003.jpg
```

Run from `classical-cv/`:

```powershell
python scripts/pipeline/enroll_hardware_identities.py --input-dir captures
```

It writes one safe central source database, `models/hardware/enrollment.npz`, plus a dated deploy bundle under `models/hardware/releases/`. Every accepted photo creates both an LBPH tile and SFace embedding in the same record. The script rebuilds both output models from that same record set, so identity and sample parity cannot drift.

Add samples or people: place only new photos in `captures/<identity>/`, then run same command. Exact duplicate files are skipped. Replace a person's old photos deliberately:

```powershell
python scripts/pipeline/enroll_hardware_identities.py --input-dir captures --replace-identity "Alice Cruz"
```

By default, every photo must contain exactly one YuNet-detected face. One bad or multi-face photo aborts before database changes; use `--skip-invalid` only when you deliberately want to omit bad photos. Use `--allow-fallback` only for known pre-cropped face tiles. Use `--assume-cropped` for a dataset where every image already is one face tile.

Never combine files across release folders. Deploy together:

- LBPH: `lbph.yml` + `labels.json`
- SFace: `sface_gallery.npy`

If release creation is interrupted after database update, rebuild without re-reading photos:

```powershell
python scripts/pipeline/enroll_hardware_identities.py --rebuild-only
```
