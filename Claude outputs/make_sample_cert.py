#!/usr/bin/env python3
"""
EndByte sample certificate generator.

Edit the CERT block below, then run:
    pip install reportlab      (once)
    python3 make_sample_cert.py

Writes endbyte-sample-certificate.pdf next to this script.
"""
import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

# ===================== EDIT THESE =====================
CERT = {
    "number":      "CD-2611",
    "device":      "Seagate Exos 7E8  ·  8 TB Enterprise HDD",
    "serial":      "ZA1C8TK9",
    "media":       "HDD (SATA)",
    "method":      "NIST 800-88 Clear  ·  Overwrite + full verify",
    "verification":"PASS  ·  100% of sectors read zero",
    "disposition": "Sanitized  ·  retained for asset recovery",
    "operator":    "ENDBYTE-BENCH-01",
    "date":        "2026-06-14",
    "location":    "Santa Clara, California",
}
SAMPLE = True   # False removes the "SAMPLE" markings
STATEMENT = ("This certifies that the media identified above was "
             "sanitized or destroyed in accordance with NIST "
             "Special Publication 800-88 guidelines, and that the "
             "result was verified by full-surface read-back.")
FOOTER_LEFT  = "EndByte Data Destruction  ·  Santa Clara, CA"
FOOTER_RIGHT = "info@endbyte.net  ·  +1 (408) 420-6991"
VERIFY_URL   = "endbyte.net/verify.html?id="
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "endbyte-sample-certificate.pdf")
# ======================================================

BG, PANEL, LINE, LINE2 = HexColor("#0E1116"), HexColor("#151A21"), HexColor("#262D38"), HexColor("#313A48")
TEXT, DIM, FAINT = HexColor("#E8ECF2"), HexColor("#8B95A5"), HexColor("#5A6373")
AMBER, GREEN = HexColor("#FFB020"), HexColor("#2FD672")
SANS, SANS_B, MONO = "Helvetica", "Helvetica-Bold", "Courier"

def wrap(c, text, font, size, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if c.stringWidth(t, font, size) <= width: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

def build():
    W, H = letter
    c = canvas.Canvas(OUTPUT, pagesize=letter)
    c.setTitle("EndByte — %sCertificate of Destruction" % ("Sample " if SAMPLE else ""))
    c.setAuthor("EndByte Data Destruction")

    # page + frame
    c.setFillColor(BG); c.rect(0, 0, W, H, fill=1, stroke=0)
    M = 36
    c.setStrokeColor(LINE2); c.setLineWidth(1); c.rect(M, M, W - 2*M, H - 2*M, fill=0, stroke=1)
    L, R = M + 32, W - M - 32

    # logo
    top = H - M - 50
    c.setStrokeColor(AMBER); c.setLineWidth(1.6); c.rect(L, top - 8, 22, 22, fill=0, stroke=1)
    c.setFillColor(AMBER); c.rect(L + 7, top - 1, 8, 8, fill=1, stroke=0)
    c.setFont(SANS_B, 17); c.setFillColor(TEXT); c.drawString(L + 32, top - 1, "END")
    c.setFillColor(AMBER); c.drawString(L + 32 + c.stringWidth("END", SANS_B, 17), top - 1, "BYTE")
    c.setFont(MONO, 6.5); c.setFillColor(FAINT); c.drawRightString(R, top + 8, "DOCUMENT TYPE")
    c.setFont(MONO, 7.5); c.setFillColor(DIM); c.drawRightString(R, top - 3, "CERTIFICATE OF DESTRUCTION")
    c.setStrokeColor(LINE2); c.line(L, top - 32, R, top - 32)

    # title
    y = top - 72
    c.setFont(SANS_B, 25); c.setFillColor(TEXT); c.drawString(L, y, "Certificate of Destruction")
    sub = ("SAMPLE  ·  " if SAMPLE else "") + "NIST 800-88 COMPLIANT  ·  No. " + CERT["number"]
    c.setFont(MONO, 7.5); c.setFillColor(AMBER); c.drawString(L, y - 20, sub)

    # details table
    rows = [("CERTIFICATE NO.", CERT["number"], TEXT), ("DEVICE", CERT["device"], TEXT),
            ("SERIAL NUMBER", CERT["serial"], TEXT), ("MEDIA TYPE", CERT["media"], TEXT),
            ("METHOD", CERT["method"], TEXT), ("VERIFICATION", CERT["verification"], GREEN),
            ("DISPOSITION", CERT["disposition"], TEXT), ("OPERATOR", CERT["operator"], TEXT),
            ("DATE PROCESSED", CERT["date"], TEXT), ("PROCESSED AT", CERT["location"], TEXT)]
    rh = 20.5
    ty = y - 44
    th = rh * len(rows) + 10
    c.setFillColor(PANEL); c.setStrokeColor(LINE2)
    c.rect(L - 10, ty - th, (R - L) + 20, th, fill=1, stroke=1)
    ry = ty - 4
    for i, (k, v, col) in enumerate(rows):
        base = ry - rh + 7
        c.setFont(MONO, 6.8); c.setFillColor(FAINT); c.drawString(L, base, k)
        c.setFont(MONO, 8.2); c.setFillColor(col); c.drawRightString(R, base, v)
        if i < len(rows) - 1:
            c.setStrokeColor(LINE); c.line(L, ry - rh, R, ry - rh)
        ry -= rh

    # statement
    sy = ty - th - 28
    c.setFont(SANS, 8.8); c.setFillColor(DIM)
    for line in wrap(c, STATEMENT, SANS, 8.8, 250):
        c.drawString(L, sy, line); sy -= 13.5
    c.setFont(MONO, 6.8); c.setFillColor(FAINT)
    c.drawString(L, sy - 8, "Verify online: " + VERIFY_URL + CERT["number"])

    # stamp
    c.saveState()
    cx, cy = R - 62, ty - th - 42
    c.translate(cx, cy); c.rotate(-7)
    c.setStrokeColor(GREEN); c.setLineWidth(1.8); c.rect(-62, -24, 124, 48, fill=0, stroke=1)
    c.setFillColor(GREEN); c.setFont("Times-BoldItalic", 12); c.drawCentredString(0, 3, "VERIFIED")
    c.setFont(MONO, 5.5); c.drawCentredString(0, -12, "ENDBYTE  ·  " + CERT["date"][:4])
    c.restoreState()

    # footer
    fy = M + 40
    c.setStrokeColor(LINE2); c.line(L, fy + 12, R, fy + 12)
    c.setFont(MONO, 6.8); c.setFillColor(FAINT)
    c.drawString(L, fy, FOOTER_LEFT); c.drawRightString(R, fy, FOOTER_RIGHT)
    if SAMPLE:
        c.setFont(MONO, 6)
        c.drawCentredString(W / 2, fy - 16, "SAMPLE DOCUMENT — illustrative format only. Actual certificates reflect the specific media processed.")

    c.showPage(); c.save()
    print("wrote", OUTPUT)

if __name__ == "__main__":
    build()
