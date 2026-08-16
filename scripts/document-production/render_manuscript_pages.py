import fitz
from pathlib import Path

pdf_path = Path('docs/manuscript/versions/021_lsface_major.pdf')
out_dir = Path(r'C:\Users\acer\.gemini\antigravity-cli\brain\f461de9b-792a-4ad4-be27-0bcd66122ec7')
out_dir.mkdir(parents=True, exist_ok=True)

doc = fitz.open(pdf_path)
print(f'Rendering {len(doc)} pages from {pdf_path}...')

for pno, page in enumerate(doc, 1):
    pix = page.get_pixmap(dpi=150)
    img_name = f'page_{pno:02d}.png'
    img_path = out_dir / img_name
    pix.save(img_path)
    print(f'Saved Page {pno:02d} -> {img_path.name}')
