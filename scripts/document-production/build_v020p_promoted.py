import sys, io, os, zipfile, re, shutil, subprocess
import xml.etree.ElementTree as ET
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

DOCM_PATH = r'docs/manuscript/versions/020p_lsface_canonical-selfmatch-promoted.docm'
PDF_PATH = r'docs/manuscript/versions/020p_lsface_canonical-selfmatch-promoted.pdf'
BASELINE_DOCM = r'docs/manuscript/versions/pairwise/019p_lsface_reproducibility-pass.docm'

W_NS = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
ET.register_namespace('w', W_NS)

def get_vba_hash(path):
    import hashlib
    with zipfile.ZipFile(path, 'r') as z:
        return hashlib.sha256(z.read('word/vbaProject.bin')).hexdigest()

baseline_vba_hash = get_vba_hash(BASELINE_DOCM)
print(f'Baseline VBA Hash: {baseline_vba_hash}')

# Read document.xml from current 020p
with zipfile.ZipFile(DOCM_PATH, 'r') as z:
    xml_data = z.read('word/document.xml')

root = ET.fromstring(xml_data)

def make_run(text, italic=False, bold=False, subscript=False, size=None):
    r = ET.Element(f'{{{W_NS}}}r')
    rPr = ET.Element(f'{{{W_NS}}}rPr')
    if italic:
        rPr.append(ET.Element(f'{{{W_NS}}}i'))
    if bold:
        rPr.append(ET.Element(f'{{{W_NS}}}b'))
    if subscript:
        va = ET.Element(f'{{{W_NS}}}vertAlign')
        va.set(f'{{{W_NS}}}val', 'subscript')
        rPr.append(va)
    if size:
        sz = ET.Element(f'{{{W_NS}}}sz')
        sz.set(f'{{{W_NS}}}val', str(size))
        rPr.append(sz)
    if len(rPr) > 0:
        r.append(rPr)
    t = ET.Element(f'{{{W_NS}}}t')
    if text.startswith(' ') or text.endswith(' '):
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
    t.text = text
    r.append(t)
    return r

def get_p_text(p):
    return ''.join([n.text for n in p.iter() if n.tag.endswith('}t') and n.text])

# 1. Section 3.1: Quality trigger text (replace low illumination)
for p in root.iter(f'{{{W_NS}}}p'):
    txt = get_p_text(p)
    if '(i) an image-quality flag is raised because of blur' in txt:
        print('Updating P030 quality triggers...')
        # Clear all runs and build clean text
        # (i) an image-quality flag is raised because of blur, illumination outside the calibrated range, sensor noise, off-pose presentation, or insufficient face size;
        for child in list(p):
            if child.tag.endswith('}r'):
                p.remove(child)
        p.append(make_run('(i) an image-quality flag is raised because of blur, illumination outside the calibrated range, sensor noise, off-pose presentation, or insufficient face size;'))

    elif 'The quality thresholds in Table 1 were defined' in txt:
        print('Formatting Section 3.1 prose m_min...')
        # Ensure m_min renders as m with sub min
        for child in list(p):
            if child.tag.endswith('}r'):
                p.remove(child)
        p.append(make_run('The quality thresholds in Table 1 were defined from the empirical distribution edges of 279 clean facial crops detected across a 280-image reference collection (10 clean frontal and pose images per identity across 28 identities, with one detector miss excluded), rather than optimized on the 41-transformation evaluation set or fitted to a measured LBPH-to-SFace performance crossover. The relative top-two margin expresses the separation between the two highest-ranked candidates relative to the best-match distance; '))
        p.append(make_run('m', italic=True))
        p.append(make_run('min', subscript=True))
        p.append(make_run(' = 0.05 was chosen as a fixed engineering policy value rather than statistically optimized. The quality condition is evaluated independently of the LBPH score, allowing quality-flagged inputs to be escalated even when the first-stage distance appears confident.'))

# 2. Table 1 math formatting
tables = list(root.iter(f'{{{W_NS}}}tbl'))
t1 = tables[0]

# Row 5 (Face size): selection rule -> ⌊0.9 × p₅⌋ of clean box sizes
# Row 6 (Relative top-two margin): (d₂ − d₁) / d₁ < m_min -> (d₂ − d₁) / d₁ < m_min with sub min
# Row 6 (Deployed value): m_min = 0.05 with sub min
for r_idx, tr in enumerate(t1.iter(f'{{{W_NS}}}tr')):
    tcs = list(tr.iter(f'{{{W_NS}}}tc'))
    if r_idx == 5: # Face size row
        # Col 2: Selection rule
        p = tcs[2].find(f'{{{W_NS}}}p')
        for child in list(p):
            if child.tag.endswith('}r'):
                p.remove(child)
        p.append(make_run('⌊0.9 × ', size=18))
        p.append(make_run('p', italic=True, size=18))
        p.append(make_run('5', subscript=True, size=18))
        p.append(make_run('⌋ of clean box sizes', size=18))

    elif r_idx == 6: # Margin row
        # Col 1: (d₂ − d₁) / d₁ < m_min
        p = tcs[1].find(f'{{{W_NS}}}p')
        for child in list(p):
            if child.tag.endswith('}r'):
                p.remove(child)
        p.append(make_run('(', size=18))
        p.append(make_run('d', italic=True, size=18))
        p.append(make_run('2', subscript=True, size=18))
        p.append(make_run(' − ', size=18))
        p.append(make_run('d', italic=True, size=18))
        p.append(make_run('1', subscript=True, size=18))
        p.append(make_run(') / ', size=18))
        p.append(make_run('d', italic=True, size=18))
        p.append(make_run('1', subscript=True, size=18))
        p.append(make_run(' < ', size=18))
        p.append(make_run('m', italic=True, size=18))
        p.append(make_run('min', subscript=True, size=18))

        # Col 3: m_min = 0.05
        p3 = tcs[3].find(f'{{{W_NS}}}p')
        for child in list(p3):
            if child.tag.endswith('}r'):
                p3.remove(child)
        p3.append(make_run('m', italic=True, size=18))
        p3.append(make_run('min', subscript=True, size=18))
        p3.append(make_run(' = 0.05', size=18))

# 3. Section 4.3: τ_reject math formatting and 4.3 awkward sentence cleanup
for p in root.iter(f'{{{W_NS}}}p'):
    txt = get_p_text(p)
    if 'Table 6 reports the controlled self-match' in txt:
        print('Updating Section 4.3 prose with clean sentence and τ_reject formatting...')
        for child in list(p):
            if child.tag.endswith('}r'):
                p.remove(child)
        p.append(make_run('Table 6 reports the controlled self-match robustness test under the same frozen operating configuration summarized in Table 5. One selected source image for each of 5,749 LFW identities was enrolled, and the clean and transformed test images were derived from that same source. The experiment therefore measures within-image transformation retention rather than image-disjoint identification, and no FAR is measured because no impostor comparisons are performed. Across the 235,709 modified conditions (41 transformations × 5,749 source images), LBPH, SFace, and the hybrid cascade achieved retention rates of 77.02%, 88.90%, and 88.91%, respectively. The cascade escalated 217,917 of the 235,709 modified conditions (92.45% pooled escalation), essentially matching SFace retention (88.91% versus 88.90%). Under the strict detector-failure policy, 15,083 modified conditions (6.40%) failed face detection—concentrated in 90°, 180°, and 270° rotations and horizontal flipping—and were retained as failures. No modified condition terminated through the LBPH hard-reject branch at '))
        p.append(make_run('τ', italic=True))
        p.append(make_run('reject', subscript=True))
        p.append(make_run(' = 140.13, consistent with the boundary\'s deliberately permissive role on this workload.'))

# 4. Section 4.4: terminology cleanup (source test images, 2,060 test conditions) & τ_accept formatting
for p in root.iter(f'{{{W_NS}}}p'):
    txt = get_p_text(p)
    if 'The evaluation follows the three-link argument described above' in txt:
        print('Updating Section 4.4 intro terminology...')
        for child in list(p):
            if child.tag.endswith('}r'):
                p.remove(child)
        p.append(make_run('The evaluation follows the three-link argument described above. It uses 56 image-disjoint held-out La Salle DB1 source test images, two for each of 28 enrolled identities, and 41 deterministic transformations per source, yielding 2,296 correlated test conditions. The LFW-derived thresholds and routing rule were frozen before scoring, and detector failures were handled strictly. Figures 4 and 5 summarize the two main complementarity findings: whether SFace can recover LBPH failures and whether the routing rule can distinguish cases that should be escalated.'))

    elif 'Second, LBPH distance and relative top-two margin provided strong discrimination' in txt:
        print('Updating Section 4.4 test conditions terminology...')
        for child in list(p):
            if child.tag.endswith('}r'):
                p.remove(child)
        p.append(make_run('Second, LBPH distance and relative top-two margin provided strong discrimination of LBPH Rank-1 errors. Of the 1,589 thresholded LBPH failures, 1,353 had the LBPH signals required for routing analysis; the remaining 236 conditions were excluded from signal-based routing metrics. Among the 2,060 test conditions with available routing signals, LBPH distance and negative relative top-two margin separated 444 threshold-free LBPH Rank-1 errors with AUCs of 0.95019 and 0.95319, respectively. As shown in Fig. 5, the deployed rule escalated all 1,353 thresholded LBPH failures, giving 100.0% failure-routing recall. However, it also escalated 289 of the 707 LBPH-correct cases (40.88%), while the remaining 418 cases (59.12%) were correctly retained at the LBPH stage. Thus, the rule captured all signal-available thresholded LBPH failures but also escalated 40.88% of LBPH-correct cases.'))

    elif 'A post-hoc accept-protection replay examined whether this redundant routing' in txt:
        print('Formatting Section 4.4 replay τ_accept...')
        for child in list(p):
            if child.tag.endswith('}r'):
                p.remove(child)
        p.append(make_run('A post-hoc accept-protection replay examined whether this redundant routing could be reduced. The replay preserved the deployed low-margin trigger and all conditions above '))
        p.append(make_run('τ', italic=True))
        p.append(make_run('accept', subscript=True))
        p.append(make_run(', while treating accept-side quality flags as telemetry rather than escalation triggers. Under this replay, unnecessary escalations among LBPH-correct cases fell from 289 to 7 of 707. Because the same transformed probes motivated and evaluated this candidate policy, however, the result is treated only as a descriptive ablation and not as independent validation of an improved routing rule.'))

# 5. Section 6.1 & 6.2 Conclusion updates
for p in root.iter(f'{{{W_NS}}}p'):
    txt = get_p_text(p)
    if 'LS-Face combines an LBPH first stage with SFace fallback and was evaluated through separate selection' in txt:
        print('Updating Conclusion 6.1 tone...')
        for child in list(p):
            if child.tag.endswith('}r'):
                p.remove(child)
        p.append(make_run('LS-Face combines an LBPH first stage with SFace fallback and was evaluated through separate selection, calibration, controlled-robustness, and held-out cascade experiments. The controlled self-match rerun showed that SFace showed higher retention than LBPH under the tested transformations, while the cascade essentially matched SFace retention with high escalation. The held-out La Salle DB1-DL41 experiment separately showed substantial SFace recovery of LBPH failures and useful first-stage risk signals.'))

    elif 'Under the held-out La Salle DB1-DL41 stress workload, however' in txt:
        print('Updating Conclusion 6.2 routing claim precision...')
        for child in list(p):
            if child.tag.endswith('}r'):
                p.remove(child)
        p.append(make_run('Under the held-out La Salle DB1-DL41 stress workload, however, the cascade did not outperform direct SFace in the recognition-performance/runtime trade-off. The study therefore supports SFace as an effective fallback and LBPH scores as informative routing signals, while defining a clear efficiency limit of the current architecture. Open-set identification and end-to-end target-device evaluation remain outside the present scope.'))

# Write modified XML back into DOCM
modified_xml = ET.tostring(root, encoding='utf-8', xml_declaration=True)

temp_docm = DOCM_PATH + '.temp'
with zipfile.ZipFile(DOCM_PATH, 'r') as zin:
    with zipfile.ZipFile(temp_docm, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename == 'word/document.xml':
                zout.writestr(item.filename, modified_xml)
            else:
                zout.writestr(item.filename, zin.read(item.filename))

shutil.move(temp_docm, DOCM_PATH)
print('Updated word/document.xml inside 020p DOCM.')

# Now export PDF via Word COM and verify VBA hash
ps_export_script = f'''
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
$docPath = "{os.path.abspath(DOCM_PATH)}"
$pdfOut = "{os.path.abspath(PDF_PATH)}"
$doc = $word.Documents.Open($docPath, $false, $false)
$doc.Fields.Update()
foreach ($story in $doc.StoryRanges) {{ $story.Fields.Update() }}
$doc.Repaginate()
$pageCount = [int]$doc.ComputeStatistics(2)
Write-Output ("Document page count: " + $pageCount)
$doc.Save()
$doc.ExportAsFixedFormat($pdfOut, 17)
$doc.Close(0)
$word.Quit()
[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($doc)
[void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($word)
'''

with open('scripts/document-production/export_pdf_020p.ps1', 'w', encoding='utf-8') as f:
    f.write(ps_export_script)

subprocess.run(['pwsh', '-ExecutionPolicy', 'Bypass', '-File', 'scripts/document-production/export_pdf_020p.ps1'], check=True)

# Restore VBA binary
with zipfile.ZipFile(BASELINE_DOCM, 'r') as z_base:
    vba_bytes = z_base.read('word/vbaProject.bin')

temp_docm_vba = DOCM_PATH + '.vba_restore'
with zipfile.ZipFile(DOCM_PATH, 'r') as zin:
    with zipfile.ZipFile(temp_docm_vba, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename == 'word/vbaProject.bin':
                zout.writestr(item.filename, vba_bytes)
            else:
                zout.writestr(item.filename, zin.read(item.filename))

shutil.move(temp_docm_vba, DOCM_PATH)

final_vba_hash = get_vba_hash(DOCM_PATH)
print(f'Final VBA Hash: {final_vba_hash}')
assert final_vba_hash == baseline_vba_hash, 'VBA Hash mismatch!'
print('SUCCESS: Built and exported 020p with perfect XML math formatting and bit-for-bit VBA integrity.')
