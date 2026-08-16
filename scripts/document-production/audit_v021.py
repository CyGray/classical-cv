import sys, io, fitz, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

pdf_path = r'docs/manuscript/versions/021_lsface_major.pdf'
doc = fitz.open(pdf_path)
print(f'Total pages in 021_major PDF: {len(doc)}')

full_text = ''
for pno, page in enumerate(doc, 1):
    txt = page.get_text()
    full_text += f'\n--- Page {pno} ---\n' + txt

print('\n=== KEY VERIFIED PROMOTED PHRASES ===')
terms = [
    'Selective Computation', '7.015 ms', '8.300 ms', '15.48%', '1,804', '88.36%',
    '1,594 / 1,804', '[-1.482, -1.088]', '117,834', '89.55%', '96.54%', '81.19%',
    '2,874', '2,875', '43.75%', '36 KiB', '64 KiB', 'r=3, n=8, 6x6'
]
for t in terms:
    matches = list(re.finditer(re.escape(t), full_text))
    print(f'Term "{t}": {len(matches)} occurrences')

print('\n=== AUDIT OF OBSOLETE/SUPERSEDED STRINGS ===')
obsolete = [
    '86.66', '98.22', '94.69', '46.39', '46.70', '76.85', '67.0084', '1.018',
    'p < 10', '235,709', '5,749', 'improved robustness through selective fallback'
]
for o in obsolete:
    matches = list(re.finditer(re.escape(o), full_text))
    print(f'Obsolete "{o}": {len(matches)} occurrences')
    if matches:
        for m in matches:
            snippet = full_text[max(0, m.start()-40):min(len(full_text), m.end()+40)].replace('\n', ' ')
            print(f'   Snippet: ...{snippet}...')

print('\n=== TABLE CAPTIONS FOUND IN PDF ===')
for line in full_text.split('\n'):
    if re.match(r'^\s*Table \d+\.', line):
        print('  ', line.strip())
