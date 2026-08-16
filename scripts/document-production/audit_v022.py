"""Audit script for v022 scope-contracted manuscript PDF.
Verifies page count, forbidden legacy tokens, and key statistics.
Renders pages as PNGs for visual inspection.
"""

from pathlib import Path
import fitz  # PyMuPDF

def audit_pdf(pdf_path: str):
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    print(f"============================================================")
    print(f" AUDIT FOR: {pdf_path}")
    print(f" Total Pages: {total_pages}")
    print(f"============================================================")

    full_text = ""
    for idx, page in enumerate(doc):
        text = page.get_text()
        full_text += f"\n--- Page {idx+1} ---\n" + text

    # Obsolete / Banned strings
    banned_tokens = [
        "235,709",
        "5,749",
        "77.02%",
        "15,083",
        "67.0333",
        "16,522,626",
        "baseline sequential",
        "architecture only",
        "descriptor only",
        "ablation",
        "77.53",
        "38.99",
        "43.75%",
        "retuning",
        "28 identities",
        "56-probe",
        "energy efficiency",
        "throughput"
    ]

    print("\n--- BANNED / OBSOLETE STRINGS CHECK ---")
    found_banned = False
    for token in banned_tokens:
        count = full_text.lower().count(token.lower())
        if count > 0:
            print(f"[FAIL] Found '{token}': {count} occurrences")
            found_banned = True
        else:
            print(f"[OK]   '{token}': 0 occurrences")

    if not found_banned:
        print("-> ALL BANNED STRINGS CLEAN! 0 OBSOLETE TOKENS FOUND.")

    # Target key phrases
    target_tokens = [
        "Quality-First",
        "Selective Computation",
        "7.015 ms",
        "8.300 ms",
        "15.48%",
        "1,804",
        "88.36%",
        "1,594 / 1,804",
        "117,834",
        "89.55%",
        "96.54%",
        "81.19%",
        "2,874",
        "2,875",
        "36 KiB",
        "52.3724",
        "140.13",
        "1.0313",
        "1,156",
        "0.26%",
        "96.35%",
        "18.06%",
        "50.50%"
    ]

    print("\n--- TARGET PHRASES AUDIT ---")
    for token in target_tokens:
        count = full_text.count(token)
        print(f"[{'OK' if count > 0 else 'MISSING'}] '{token}': {count} occurrences")

    # Render pages as PNGs
    render_dir = Path("docs/manuscript/versions/_page_renders_022")
    render_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n--- RENDERING {total_pages} PAGES TO {render_dir} ---")
    for idx, page in enumerate(doc):
        pix = page.get_pixmap(dpi=150)
        out_png = render_dir / f"page_{idx+1:02d}.png"
        pix.save(str(out_png))
        print(f"Saved {out_png}")

if __name__ == "__main__":
    audit_pdf("docs/manuscript/versions/022_lsface_scope-contracted.pdf")
