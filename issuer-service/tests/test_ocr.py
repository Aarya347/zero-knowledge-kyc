import pytest

from synth import Identity, render_id_card
from app.ocr_dob import extract_dob, DobExtractionError


def test_roundtrip_iso_labels():
    """PROPERTY: DOB printed on a rendered card is extracted exactly."""
    cases = [((1990, 5, 14), 61), ((2001, 12, 31), 62), ((1975, 2, 3), 63)]
    for dob, seed in cases:
        img = render_id_card(Identity(seed), dob=dob)
        assert extract_dob(img) == dob, f"{dob} not recovered"


def test_no_date_fails():
    import numpy as np, cv2
    blank = np.full((400, 600, 3), 255, dtype=np.uint8)
    cv2.putText(blank, "HELLO WORLD", (40, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (0, 0, 0), 3)
    with pytest.raises(DobExtractionError):
        extract_dob(blank)


def test_roundtrip_numeric_dmy_labels():
    """PROPERTY: Non-ISO numeric DOB (DD-MM-YYYY) on labelled line is extracted."""
    from synth import draw_face
    from PIL import Image, ImageDraw, ImageFont
    import cv2
    import numpy as np

    cases = [
        ((1990, 5, 14), "14-05-1990", 61),
        ((2001, 12, 31), "31-12-2001", 62),
        ((1975, 2, 3), "03-02-1975", 63),
    ]
    for (expected_y, expected_m, expected_d), date_str, seed in cases:
        identity = Identity(seed)
        face = draw_face(identity, 0.0)
        card = Image.new("RGB", (640, 900), (235, 235, 240))
        d = ImageDraw.Draw(card)
        try:
            font = ImageFont.load_default(size=34)
            small = ImageFont.load_default(size=26)
        except TypeError:
            font = ImageFont.load_default()
            small = font
        d.rectangle([40, 40, 600, 860], fill=(255, 255, 255), outline=(60, 60, 60), width=3)
        d.text((70, 80), "REPUBLIC OF TESTLAND", fill=(20, 20, 20), font=font)
        d.text((70, 130), "NATIONAL IDENTITY CARD", fill=(60, 60, 60), font=small)
        pil_face = Image.fromarray(cv2.cvtColor(face, cv2.COLOR_BGR2RGB)).resize((260, 260))
        card.paste(pil_face, (340, 200))
        d.text((70, 220), f"NAME: {identity.name}", fill=(10, 10, 10), font=small)
        d.text((70, 280), f"DOB: {date_str}", fill=(10, 10, 10), font=font)
        d.text((70, 350), f"DOC NO: TL-{identity.seed:08d}", fill=(10, 10, 10), font=small)
        d.text((70, 800), "NOT A REAL DOCUMENT", fill=(120, 30, 30), font=small)
        img = cv2.cvtColor(np.array(card), cv2.COLOR_RGB2BGR)
        extracted = extract_dob(img)
        assert extracted == (expected_y, expected_m, expected_d), f"{date_str} extracted as {extracted}"


def test_implausible_date_fails():
    import numpy as np, cv2
    img = np.full((400, 600, 3), 255, dtype=np.uint8)
    cv2.putText(img, "DOB: 9999-99-99", (40, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 2)
    with pytest.raises(DobExtractionError):
        extract_dob(img)

