import sys, io, fitz, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

doc = fitz.open(r'docs/manuscript/versions/020p_lsface_canonical-selfmatch-promoted.pdf')
print(f'Total pages in 020p PDF: {len(doc)}')

full_text = ''
for pno, page in enumerate(doc, 1):
    txt = page.get_text()
    full_text += f'\n--- Page {pno} ---\n' + txt

obsolete_terms = [
    '86.66', '98.22', '94.69', '46.39', '46.70', '76.85', '67.0084', '1.018',
    'Threshold-basis FAR', 'augmented versions', 'recorded Table 5 configuration',
    'not results of the Table 4 operating points', 'improved robustness through selective fallback'
]

print('=== AUDIT OF OBSOLETE STRINGS ===')
for term in obsolete_terms:
    matches = list(re.finditer(re.escape(term), full_text, re.IGNORECASE))
    print(f'Term "{term}": {len(matches)} occurrences')
    if matches:
        for m in matches:
            snippet = full_text[max(0, m.start()-40):min(len(full_text), m.end()+40)].replace('\n', ' ')
            print(f'   Snippet: ...{snippet}...')

print('\n=== TABLE CAPTIONS IN PDF ===')
for line in full_text.split('\n'):
    if re.match(r'^\s*Table \d+\.', line):
        print('  ', line.strip())

print('\n=== PROMOTED CANONICAL SELF-MATCH NUMBERS CHECK ===')
canonical_terms = ['77.02', '88.90', '88.91', '92.45', '235,709', '217,917', '15,083', '6.40%', 'Table 6']
for term in canonical_terms:
    matches = list(re.finditer(re.escape(term), full_text, re.IGNORECASE))
    print(f'Promoted Term "{term}": {len(matches)} occurrences')
