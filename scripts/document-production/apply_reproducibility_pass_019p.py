"""Targeted reproducibility and defensibility pass on Sections 3.1-3.3 for 019p.

Baseline: docs/manuscript/versions/pairwise/018p_polish_run.docm
Output:   docs/manuscript/versions/pairwise/019p_lsface_reproducibility-pass.docm
          docs/manuscript/versions/pairwise/019p_lsface_reproducibility-pass.pdf
"""

import hashlib
import io
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(r"C:\Users\acer\Documents\USLS 4th Year\Computer Vision")
SRC_DOCM = PROJECT_ROOT / "docs" / "manuscript" / "versions" / "pairwise" / "018p_polish_run.docm"
DST_DOCM = PROJECT_ROOT / "docs" / "manuscript" / "versions" / "pairwise" / "019p_lsface_reproducibility-pass.docm"
DST_PDF = PROJECT_ROOT / "docs" / "manuscript" / "versions" / "pairwise" / "019p_lsface_reproducibility-pass.pdf"

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14_NS = "http://schemas.microsoft.com/office/word/2010/wordml"
M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"

NAMESPACES = {
    "w": W_NS,
    "w14": W14_NS,
    "m": M_NS,
}

for prefix, uri in NAMESPACES.items():
    ET.register_namespace(prefix, uri)


def make_table_caption(table_num: int, title: str) -> ET.Element:
    """Create a Springer LNCS tablecaption paragraph with SEQ field."""
    p = ET.Element(f"{{{W_NS}}}p")
    pPr = ET.SubElement(p, f"{{{W_NS}}}pPr")
    pStyle = ET.SubElement(pPr, f"{{{W_NS}}}pStyle")
    pStyle.set(f"{{{W_NS}}}val", "tablecaption")

    # Table
    r1 = ET.SubElement(p, f"{{{W_NS}}}r")
    rPr1 = ET.SubElement(r1, f"{{{W_NS}}}rPr")
    ET.SubElement(rPr1, f"{{{W_NS}}}b")
    t1 = ET.SubElement(r1, f"{{{W_NS}}}t")
    t1.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t1.text = "Table "

    # Field begin
    r_fld_begin = ET.SubElement(p, f"{{{W_NS}}}r")
    rPr_fb = ET.SubElement(r_fld_begin, f"{{{W_NS}}}rPr")
    ET.SubElement(rPr_fb, f"{{{W_NS}}}b")
    fld_char_b = ET.SubElement(r_fld_begin, f"{{{W_NS}}}fldChar")
    fld_char_b.set(f"{{{W_NS}}}fldCharType", "begin")

    # InstrText
    r_instr = ET.SubElement(p, f"{{{W_NS}}}r")
    rPr_in = ET.SubElement(r_instr, f"{{{W_NS}}}rPr")
    ET.SubElement(rPr_in, f"{{{W_NS}}}b")
    instr = ET.SubElement(r_instr, f"{{{W_NS}}}instrText")
    instr.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    instr.text = ' SEQ "Table" \\* MERGEFORMAT '

    # Field separate
    r_sep = ET.SubElement(p, f"{{{W_NS}}}r")
    rPr_sep = ET.SubElement(r_sep, f"{{{W_NS}}}rPr")
    ET.SubElement(rPr_sep, f"{{{W_NS}}}b")
    fld_char_s = ET.SubElement(r_sep, f"{{{W_NS}}}fldChar")
    fld_char_s.set(f"{{{W_NS}}}fldCharType", "separate")

    # Number text
    r_num = ET.SubElement(p, f"{{{W_NS}}}r")
    rPr_num = ET.SubElement(r_num, f"{{{W_NS}}}rPr")
    ET.SubElement(rPr_num, f"{{{W_NS}}}b")
    ET.SubElement(rPr_num, f"{{{W_NS}}}noProof")
    t_num = ET.SubElement(r_num, f"{{{W_NS}}}t")
    t_num.text = str(table_num)

    # Field end
    r_end = ET.SubElement(p, f"{{{W_NS}}}r")
    rPr_end = ET.SubElement(r_end, f"{{{W_NS}}}rPr")
    ET.SubElement(rPr_end, f"{{{W_NS}}}b")
    fld_char_e = ET.SubElement(r_end, f"{{{W_NS}}}fldChar")
    fld_char_e.set(f"{{{W_NS}}}fldCharType", "end")

    # Period
    r_dot = ET.SubElement(p, f"{{{W_NS}}}r")
    rPr_dot = ET.SubElement(r_dot, f"{{{W_NS}}}rPr")
    ET.SubElement(rPr_dot, f"{{{W_NS}}}b")
    t_dot = ET.SubElement(r_dot, f"{{{W_NS}}}t")
    t_dot.text = "."

    # Title
    r_title = ET.SubElement(p, f"{{{W_NS}}}r")
    t_title = ET.SubElement(r_title, f"{{{W_NS}}}t")
    t_title.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t_title.text = f" {title}"

    return p


def make_cell(text: str, width: int, is_header: bool = False, align: str = "left", top_border: str | None = None, bottom_border: str | None = None) -> ET.Element:
    """Create a table cell with 9pt font and LNCS border rules."""
    tc = ET.Element(f"{{{W_NS}}}tc")
    tcPr = ET.SubElement(tc, f"{{{W_NS}}}tcPr")
    tcW = ET.SubElement(tcPr, f"{{{W_NS}}}tcW")
    tcW.set(f"{{{W_NS}}}w", str(width))
    tcW.set(f"{{{W_NS}}}type", "dxa")

    if top_border or bottom_border:
        tcBorders = ET.SubElement(tcPr, f"{{{W_NS}}}tcBorders")
        if top_border == "thick":
            b = ET.SubElement(tcBorders, f"{{{W_NS}}}top")
            b.set(f"{{{W_NS}}}val", "single")
            b.set(f"{{{W_NS}}}sz", "12")
            b.set(f"{{{W_NS}}}space", "0")
            b.set(f"{{{W_NS}}}color", "auto")
        elif top_border == "thin":
            b = ET.SubElement(tcBorders, f"{{{W_NS}}}top")
            b.set(f"{{{W_NS}}}val", "single")
            b.set(f"{{{W_NS}}}sz", "6")
            b.set(f"{{{W_NS}}}space", "0")
            b.set(f"{{{W_NS}}}color", "auto")

        if bottom_border == "thick":
            b = ET.SubElement(tcBorders, f"{{{W_NS}}}bottom")
            b.set(f"{{{W_NS}}}val", "single")
            b.set(f"{{{W_NS}}}sz", "12")
            b.set(f"{{{W_NS}}}space", "0")
            b.set(f"{{{W_NS}}}color", "auto")
        elif bottom_border == "thin":
            b = ET.SubElement(tcBorders, f"{{{W_NS}}}bottom")
            b.set(f"{{{W_NS}}}val", "single")
            b.set(f"{{{W_NS}}}sz", "6")
            b.set(f"{{{W_NS}}}space", "0")
            b.set(f"{{{W_NS}}}color", "auto")

    vAlign = ET.SubElement(tcPr, f"{{{W_NS}}}vAlign")
    vAlign.set(f"{{{W_NS}}}val", "center")

    p = ET.SubElement(tc, f"{{{W_NS}}}p")
    pPr = ET.SubElement(p, f"{{{W_NS}}}pPr")
    spacing = ET.SubElement(pPr, f"{{{W_NS}}}spacing")
    spacing.set(f"{{{W_NS}}}line", "240")
    spacing.set(f"{{{W_NS}}}lineRule", "auto")
    ind = ET.SubElement(pPr, f"{{{W_NS}}}ind")
    ind.set(f"{{{W_NS}}}firstLine", "0")
    jc = ET.SubElement(pPr, f"{{{W_NS}}}jc")
    jc.set(f"{{{W_NS}}}val", align)

    rPr_p = ET.SubElement(pPr, f"{{{W_NS}}}rPr")
    if is_header:
        ET.SubElement(rPr_p, f"{{{W_NS}}}b")
    sz_p = ET.SubElement(rPr_p, f"{{{W_NS}}}sz")
    sz_p.set(f"{{{W_NS}}}val", "18")

    r = ET.SubElement(p, f"{{{W_NS}}}r")
    rPr = ET.SubElement(r, f"{{{W_NS}}}rPr")
    if is_header:
        ET.SubElement(rPr, f"{{{W_NS}}}b")
        ET.SubElement(rPr, f"{{{W_NS}}}bCs")
    sz = ET.SubElement(rPr, f"{{{W_NS}}}sz")
    sz.set(f"{{{W_NS}}}val", "18")
    t = ET.SubElement(r, f"{{{W_NS}}}t")
    t.text = text

    return tc


def create_quality_parameter_table() -> ET.Element:
    """Create Table 1: Deployed quality and margin parameters (LNCS 3-rule style)."""
    tbl = ET.Element(f"{{{W_NS}}}tbl")

    # Table properties
    tblPr = ET.SubElement(tbl, f"{{{W_NS}}}tblPr")
    tblW = ET.SubElement(tblPr, f"{{{W_NS}}}tblW")
    tblW.set(f"{{{W_NS}}}w", "6930")
    tblW.set(f"{{{W_NS}}}type", "dxa")

    tblBorders = ET.SubElement(tblPr, f"{{{W_NS}}}tblBorders")
    top_b = ET.SubElement(tblBorders, f"{{{W_NS}}}top")
    top_b.set(f"{{{W_NS}}}val", "single")
    top_b.set(f"{{{W_NS}}}sz", "12")
    top_b.set(f"{{{W_NS}}}space", "0")
    top_b.set(f"{{{W_NS}}}color", "auto")

    bottom_b = ET.SubElement(tblBorders, f"{{{W_NS}}}bottom")
    bottom_b.set(f"{{{W_NS}}}val", "single")
    bottom_b.set(f"{{{W_NS}}}sz", "12")
    bottom_b.set(f"{{{W_NS}}}space", "0")
    bottom_b.set(f"{{{W_NS}}}color", "auto")

    tblLayout = ET.SubElement(tblPr, f"{{{W_NS}}}tblLayout")
    tblLayout.set(f"{{{W_NS}}}type", "fixed")

    tblCellMar = ET.SubElement(tblPr, f"{{{W_NS}}}tblCellMar")
    left_m = ET.SubElement(tblCellMar, f"{{{W_NS}}}left")
    left_m.set(f"{{{W_NS}}}w", "70")
    left_m.set(f"{{{W_NS}}}type", "dxa")
    right_m = ET.SubElement(tblCellMar, f"{{{W_NS}}}right")
    right_m.set(f"{{{W_NS}}}w", "70")
    right_m.set(f"{{{W_NS}}}type", "dxa")

    tblLook = ET.SubElement(tblPr, f"{{{W_NS}}}tblLook")
    tblLook.set(f"{{{W_NS}}}val", "04A0")
    tblLook.set(f"{{{W_NS}}}firstRow", "1")
    tblLook.set(f"{{{W_NS}}}lastRow", "0")
    tblLook.set(f"{{{W_NS}}}firstColumn", "1")
    tblLook.set(f"{{{W_NS}}}lastColumn", "0")
    tblLook.set(f"{{{W_NS}}}noHBand", "0")
    tblLook.set(f"{{{W_NS}}}noVBand", "1")

    # Grid columns (1300 + 2250 + 2180 + 1200 = 6930)
    col_widths = [1300, 2250, 2180, 1200]
    tblGrid = ET.SubElement(tbl, f"{{{W_NS}}}tblGrid")
    for w in col_widths:
        gc = ET.SubElement(tblGrid, f"{{{W_NS}}}gridCol")
        gc.set(f"{{{W_NS}}}w", str(w))

    # Header Row
    headers = [
        "Signal",
        "Measurement / condition",
        "Selection rule",
        "Deployed value",
    ]
    aligns = ["left", "left", "left", "center"]

    tr_h = ET.SubElement(tbl, f"{{{W_NS}}}tr")
    trPr_h = ET.SubElement(tr_h, f"{{{W_NS}}}trPr")
    ET.SubElement(trPr_h, f"{{{W_NS}}}cantSplit")
    trH_h = ET.SubElement(trPr_h, f"{{{W_NS}}}trHeight")
    trH_h.set(f"{{{W_NS}}}val", "352")
    ET.SubElement(trPr_h, f"{{{W_NS}}}tblHeader")

    for h_text, w, al in zip(headers, col_widths, aligns):
        tr_h.append(make_cell(h_text, w, is_header=True, align=al, top_border="thick", bottom_border="thin"))

    # Data Rows
    rows_data = [
        ("Blur", "Variance of Laplacian below threshold", "5th percentile of clean values", "587.83"),
        ("Illumination", "Mean grayscale outside bounds", "2nd and 98th percentiles of clean values", "[52.88, 137.71]"),
        ("Noise", "Immerkaer noise estimate above threshold", "95th percentile of clean values", "8.206"),
        ("Pose", "Max eye-roll and nose-yaw proxies above threshold", "95th percentile of clean values", "63.74"),
        ("Face size", "Detected box side below minimum", "⌊0.9 × p₅⌋ of clean box sizes", "61 px"),
        ("Relative margin", "(d₂ − d₁) / d₁ < m_min", "Fixed engineering policy value", "m_min = 0.05"),
    ]

    for r_idx, r_data in enumerate(rows_data):
        tr = ET.SubElement(tbl, f"{{{W_NS}}}tr")
        trPr = ET.SubElement(tr, f"{{{W_NS}}}trPr")
        ET.SubElement(trPr, f"{{{W_NS}}}cantSplit")

        # For the first row below header, top border is thin
        top_b_style = "thin" if r_idx == 0 else None
        bottom_b_style = "thick" if r_idx == len(rows_data) - 1 else None

        for val, w, al in zip(r_data, col_widths, aligns):
            tr.append(make_cell(val, w, is_header=False, align=al, top_border=top_b_style, bottom_border=bottom_b_style))

    return tbl


def make_paragraph(text: str, pStyle_val: str | None = None, before_spacing: int | None = None, first_line_ind: int | None = None, bold_prefix: str | None = None, heading3_prefix: str | None = None) -> ET.Element:
    """Create a body text paragraph."""
    p = ET.Element(f"{{{W_NS}}}p")
    pPr = ET.SubElement(p, f"{{{W_NS}}}pPr")

    if pStyle_val:
        pStyle = ET.SubElement(pPr, f"{{{W_NS}}}pStyle")
        pStyle.set(f"{{{W_NS}}}val", pStyle_val)

    if before_spacing is not None:
        spacing = ET.SubElement(pPr, f"{{{W_NS}}}spacing")
        spacing.set(f"{{{W_NS}}}before", str(before_spacing))

    if first_line_ind is not None:
        ind = ET.SubElement(pPr, f"{{{W_NS}}}ind")
        ind.set(f"{{{W_NS}}}firstLine", str(first_line_ind))

    if heading3_prefix:
        r_h3 = ET.SubElement(p, f"{{{W_NS}}}r")
        rPr_h3 = ET.SubElement(r_h3, f"{{{W_NS}}}rPr")
        rStyle_h3 = ET.SubElement(rPr_h3, f"{{{W_NS}}}rStyle")
        rStyle_h3.set(f"{{{W_NS}}}val", "heading30")
        t_h3 = ET.SubElement(r_h3, f"{{{W_NS}}}t")
        t_h3.text = heading3_prefix

    if bold_prefix:
        r_b = ET.SubElement(p, f"{{{W_NS}}}r")
        rPr_b = ET.SubElement(r_b, f"{{{W_NS}}}rPr")
        ET.SubElement(rPr_b, f"{{{W_NS}}}b")
        t_b = ET.SubElement(r_b, f"{{{W_NS}}}t")
        t_b.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        t_b.text = bold_prefix

    r_main = ET.SubElement(p, f"{{{W_NS}}}r")
    t_main = ET.SubElement(r_main, f"{{{W_NS}}}t")
    t_main.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t_main.text = text

    return p


def update_document_xml(xml_bytes: bytes) -> bytes:
    root = ET.fromstring(xml_bytes)
    body = root.find("w:body", NAMESPACES)
    if body is None:
        raise ValueError("Could not find w:body in document XML")

    # Find key elements
    children = list(body)
    
    # 1. Locate Equation (1) at Body index ~33 and paragraph 34
    eq1_idx = None
    for idx, child in enumerate(children):
        if child.tag.endswith("p"):
            texts = [node.text for node in child.iter() if node.tag.endswith("}t") and node.text]
            full_txt = "".join(texts)
            if "(1)" in full_txt and ("d" in full_txt or "m" in full_txt):
                eq1_idx = idx
                break

    if eq1_idx is None:
        raise ValueError("Could not find Equation (1) in document body")

    print(f"Found Equation (1) at body index {eq1_idx}")

    # Build Table 1 and Caption
    t1_cap = make_table_caption(1, "Deployed quality-check and candidate-separation parameters for Stage 1 escalation.")
    t1_tbl = create_quality_parameter_table()

    # Build updated Paragraph for quality & margin provenance in Section 3.1
    p31_text = (
        "The quality thresholds in Table 1 were defined from the empirical distribution edges "
        "of 279 clean facial crops detected across the 28-identity training split of La Salle DB1, "
        "rather than optimized on the 41-transformation evaluation set or fitted to a measured "
        "LBPH-to-SFace performance crossover. The relative margin expresses the separation between "
        "the two highest-ranked candidates relative to the best-match distance; m_min = 0.05 was "
        "chosen as a fixed engineering policy value rather than statistically optimized. The quality "
        "condition is evaluated independently of the LBPH score, allowing quality-flagged inputs to "
        "be escalated even when the first-stage distance appears confident."
    )
    p31_elem = make_paragraph(p31_text, before_spacing=120)

    # Insert Table 1 caption, Table 1 tbl, and updated paragraph after eq1
    # Replace old paragraph 34 (which was eq1_idx + 1)
    body.remove(children[eq1_idx + 1])
    body.insert(eq1_idx + 1, p31_elem)
    body.insert(eq1_idx + 1, t1_tbl)
    body.insert(eq1_idx + 1, t1_cap)

    # Refresh children list
    children = list(body)

    # 2. Section 3.2: replace '41 image modifications' with '41 image transformations'
    for child in children:
        if child.tag.endswith("p"):
            for t in child.iter():
                if t.tag.endswith("}t") and t.text and "robustness under the 41 image modifications" in t.text:
                    t.text = t.text.replace("robustness under the 41 image modifications", "robustness under the 41 image transformations")
                    print("Updated Section 3.2 text: 41 image transformations")

    # 3. Section 3.3: Update Independence Testing and Threshold Freezing
    # Find LFW 1 paragraph and Threshold freezing paragraph in Section 3.3
    lfw1_idx = None
    tf_idx = None
    for idx, child in enumerate(children):
        if child.tag.endswith("p"):
            texts = [node.text for node in child.iter() if node.tag.endswith("}t") and node.text]
            full_txt = "".join(texts)
            if lfw1_idx is None and full_txt.startswith("LFW 1 is used for the primary low-FAR"):
                lfw1_idx = idx
            elif tf_idx is None and full_txt.startswith("Threshold freezing."):
                tf_idx = idx

    print(f"Found LFW 1 paragraph at {lfw1_idx}, Threshold freezing at {tf_idx}")

    # Build updated Paragraph for LFW 1 / SFace L2 / Cosine
    p_lfw1_text = (
        "LFW 1 is used for the primary low-FAR independence test because its 5,749 identities "
        "yield 16,522,626 unique cross-identity comparisons, enabling resolution on the order of "
        "10 ppm (rank 165 yields 9.986 ppm). At this rank-165 operating point, the empirical LBPH "
        "acceptance threshold is τ_accept = 67.0333, and the SFace L2 threshold is L_2 ≤ 1.0313. "
        "The cosine threshold of 0.363 was retained from the existing SFace decision policy rather "
        "than independently fitted at this operating point; because normalized embeddings satisfy "
        "L_2 = √(2 − 2 cos θ), L_2 ≤ 1.0313 already implies cos θ ≥ 0.4682, rendering the 0.363 cosine "
        "constraint non-binding at the deployed L2 boundary."
    )
    p_lfw1_elem = make_paragraph(p_lfw1_text, before_spacing=120)

    # Build new Paragraph for LBPH Reject Boundary
    p_reject_text = (
        "Unlike the acceptance threshold, the LBPH rejection boundary τ_reject = 140.13 was not "
        "derived from rank-based low-FAR impostor calibration. Instead, a trade-off sweep across candidate "
        "values from 70 to 170 was conducted using 70,560 genuine and 70,560 designated-impostor rows "
        "from the image-disjoint LFW verification run (where the designated-impostor count serves as a "
        "1:1 proxy rather than a 1:N FPIR measurement). Because genuine rejection and impostor escalation "
        "tracked without a separation-favorable knee on unconstrained LFW, 140.13 was selected as a "
        "deliberately permissive engineering boundary corresponding to the heavy-tier 99th percentile genuine "
        "LBPH distance, minimizing irreversible genuine rejections before SFace fallback."
    )
    p_reject_elem = make_paragraph(p_reject_text, before_spacing=120)

    # Build updated Paragraph for Threshold Freezing
    p_tf_text = (
        "The final cascade configuration—comprising the LFW-calibrated LBPH acceptance threshold, "
        "the permissive LBPH rejection boundary, the fixed relative-margin rule, the clean-distribution "
        "quality thresholds, and the deployed SFace acceptance policy—was frozen before conducting the "
        "held-out LSDB evaluations. The evaluation harness records the configuration SHA-256, and no "
        "parameters were retuned using the held-out evaluation outcomes. The final numerical operating "
        "points are summarized in Section 4.2."
    )
    p_tf_elem = make_paragraph(p_tf_text, heading3_prefix="Threshold freezing. ")

    # Replace LFW1 paragraph and Threshold Freezing paragraph
    # Insert reject boundary paragraph in between
    body.remove(children[tf_idx])
    body.remove(children[lfw1_idx])
    body.insert(lfw1_idx, p_tf_elem)
    body.insert(lfw1_idx, p_reject_elem)
    body.insert(lfw1_idx, p_lfw1_elem)

    # 4. Renumber all subsequent tables and update all in-text citations throughout body
    children = list(body)
    for child in children:
        if child.tag.endswith("p"):
            texts = [node.text for node in child.iter() if node.tag.endswith("}t") and node.text]
            full_txt = "".join(texts)

            # Check table captions
            pPr = child.find(f"{{{W_NS}}}pPr")
            is_caption = False
            if pPr is not None:
                pStyle = pPr.find(f"{{{W_NS}}}pStyle")
                if pStyle is not None and pStyle.attrib.get(f"{{{W_NS}}}val") == "tablecaption":
                    is_caption = True

            if is_caption:
                # Update table numbers in captions
                if "Experiments and their roles in the study." in full_txt:
                    for t in child.iter():
                        if t.tag.endswith("}t") and t.text == "1":
                            t.text = "2"
                elif "Classical candidate selection on LSDB." in full_txt:
                    for t in child.iter():
                        if t.tag.endswith("}t") and t.text == "2":
                            t.text = "3"
                elif "DL candidate selection on LSDB." in full_txt:
                    for t in child.iter():
                        if t.tag.endswith("}t") and t.text == "3":
                            t.text = "4"
                elif "Final frozen operating points." in full_txt:
                    for t in child.iter():
                        if t.tag.endswith("}t") and t.text == "4":
                            t.text = "5"
                elif "Controlled Self-Match Robustness Test on LFW" in full_txt:
                    for t in child.iter():
                        if t.tag.endswith("}t") and t.text == "5":
                            t.text = "6"
            else:
                # In-text prose updates
                if "The experimental program consists of four evidence legs summarized in Table 1." in full_txt:
                    for t in child.iter():
                        if t.tag.endswith("}t") and t.text and "Table 1" in t.text:
                            t.text = t.text.replace("Table 1", "Table 2")
                            print("Updated prose: Table 1 -> Table 2")

                if "The LFW DB1 independence test produced the frozen operating points summarized in Table 4." in full_txt:
                    # Update Section 4.2 prose with consistency patch
                    new_42_prose = (
                        "The LFW DB1 independence test produced the frozen operating points summarized in Table 5. "
                        "The LBPH acceptance boundary corresponded to rank 165 of 16,522,626 impostor comparisons, "
                        "yielding a realized FAR of 9.986 ppm. The SFace L2 threshold of 1.0313 was obtained from the "
                        "same rank-165 calibration point, while the cosine condition (cosine ≥ 0.363) is inherited from "
                        "the existing SFace decision policy and is non-binding at the deployed L2 boundary."
                    )
                    # Clear existing runs and put new text
                    for r in list(child.findall(f"{{{W_NS}}}r")):
                        child.remove(r)
                    r_new = ET.SubElement(child, f"{{{W_NS}}}r")
                    t_new = ET.SubElement(r_new, f"{{{W_NS}}}t")
                    t_new.text = new_42_prose
                    print("Updated Section 4.2 prose with consistency patch and Table 5 reference")

                if "Table 5 reports the controlled self-match robustness test" in full_txt:
                    for t in child.iter():
                        if t.tag.endswith("}t") and t.text and "Table 5" in t.text:
                            t.text = t.text.replace("Table 5", "Table 6")
                            print("Updated prose: Table 5 -> Table 6 in Sec 4.3")

                if "they are not results of the Table 4 operating points." in full_txt:
                    for t in child.iter():
                        if t.tag.endswith("}t") and t.text and "Table 4" in t.text:
                            t.text = t.text.replace("Table 4", "Table 5")
                            print("Updated prose note: Table 4 -> Table 5")

                if "remains specific to the recorded Table 5 configuration." in full_txt:
                    for t in child.iter():
                        if t.tag.endswith("}t") and t.text and "Table 5" in t.text:
                            t.text = t.text.replace("Table 5", "Table 6")
                            print("Updated Discussion: Table 5 -> Table 6")

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def build_updated_docm():
    print(f"Reading from {SRC_DOCM}...")
    with zipfile.ZipFile(SRC_DOCM, "r") as zin:
        doc_xml_bytes = zin.read("word/document.xml")
        vba_bytes = zin.read("word/vbaProject.bin")
        all_items = {item.filename: zin.read(item.filename) for item in zin.infolist()}

    print("Updating document XML...")
    new_doc_xml = update_document_xml(doc_xml_bytes)
    all_items["word/document.xml"] = new_doc_xml

    print(f"Writing to {DST_DOCM}...")
    with zipfile.ZipFile(DST_DOCM, "w", zipfile.ZIP_DEFLATED) as zout:
        for fname, content in all_items.items():
            zout.writestr(fname, content)

    # Verify VBA bit-for-bit identical
    with zipfile.ZipFile(DST_DOCM, "r") as zcheck:
        dst_vba = zcheck.read("word/vbaProject.bin")

    h_src = hashlib.sha256(vba_bytes).hexdigest()
    h_dst = hashlib.sha256(dst_vba).hexdigest()
    print(f"Baseline VBA SHA256: {h_src}")
    print(f"Output   VBA SHA256: {h_dst}")
    assert h_src == h_dst, "VBA hash mismatch!"
    print("VBA project bit-for-bit verified identical!")


if __name__ == "__main__":
    build_updated_docm()
