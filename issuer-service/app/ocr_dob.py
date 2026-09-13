"""Extract a date of birth from an ID-card image with Tesseract.

Strategy: OCR with word boxes; locate an explicit DOB/BIRTH/BORN label; prefer
numeric dates on the label's own line; otherwise fall back to unambiguous ISO
dates anywhere. Ambiguous numeric dates require ID_DATE_FORMAT config and are
rejected outright if conflicting candidates exist. Never guesses.
"""
import os
import re
from collections import defaultdict

import cv2
import numpy as np
import pytesseract

from . import config

LABEL_RE = re.compile(r"\b(DOB|B\.O\.B|BIRTHDATE|BIRTH|BORN)\b", re.I)
ISO_RE = re.compile(r"\b(\d{4})[-./](\d{1,2})[-./](\d{1,2})\b")
NUM_RE = re.compile(r"\b(\d{1,2})[-./](\d{1,2})[-./](\d{4})\b")


class DobExtractionError(Exception):
    pass


def _lines_from_tsv(data):
    lines = defaultdict(list)
    n = len(data["text"])
    for i in range(n):
        txt = (data["text"][i] or "").strip()
        if not txt or int(data["conf"][i]) < 0:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines[key].append(txt)
    return [(" ".join(ws), ws) for _, ws in sorted(lines.items())]


def _validate(y, m, d):
    if not (1900 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31):
        raise DobExtractionError(f"implausible date {y}-{m}-{d}")


def extract_dob(image_bgr) -> tuple[int, int, int]:
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    gray = cv2.fastNlMeansDenoising(gray, h=7)
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    data = pytesseract.image_to_data(bw, config="--psm 6", output_type=pytesseract.Output.DICT)
    lines = _lines_from_tsv(data)

    label_line_idx = None
    for i, (line, _) in enumerate(lines):
        if LABEL_RE.search(line):
            label_line_idx = i
            break

    iso_hits, num_hits = [], []
    for i, (line, _) in enumerate(lines):
        for mm in ISO_RE.finditer(line):
            iso_hits.append((i, int(mm.group(1)), int(mm.group(2)), int(mm.group(3))))
        for mm in NUM_RE.finditer(line):
            num_hits.append((i, mm.group(1), mm.group(2), mm.group(3)))

    # Prefer ISO on the labelled line, then any ISO, then labelled numeric, then any numeric.
    if label_line_idx is not None:
        for li, y, m, d in iso_hits:
            if li == label_line_idx:
                _validate(y, m, d); return (y, m, d)
    if len(iso_hits) == 1:
        li, y, m, d = iso_hits[0]
        _validate(y, m, d); return (y, m, d)
    if label_line_idx is not None and num_hits:
        same_line = [h for h in num_hits if h[0] == label_line_idx]
        if len(same_line) == 1:
            a, b, ytxt = same_line[0][1], same_line[0][2], same_line[0][3]
            y, first, second = int(ytxt), int(a), int(b)
            fmt = config.ID_DATE_FORMAT.lower()
            if fmt == "dmy":
                m, d = second, first
            elif fmt == "mdy":
                m, d = first, second
            else:
                raise DobExtractionError("ambiguous numeric date and ID_DATE_FORMAT=ymd")
            _validate(y, m, d); return (y, m, d)
    if len(num_hits) == 1:
        a, b, ytxt = num_hits[0][1], num_hits[0][2], num_hits[0][3]
        y, first, second = int(ytxt), int(a), int(b)
        fmt = config.ID_DATE_FORMAT.lower()
        if fmt == "dmy":
            m, d = second, first
        elif fmt == "mdy":
            m, d = first, second
        else:
            raise DobExtractionError("ambiguous numeric date and ID_DATE_FORMAT=ymd")
        _validate(y, m, d); return (y, m, d)

    raise DobExtractionError("no confident date-of-birth found")
