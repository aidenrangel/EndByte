#!/usr/bin/env python3
"""
EndByte single-drive certificates, made straight from KillDisk XML reports.

    pip install reportlab                      (once)
    python3 make_single_cert.py Report-XXXX.xml --number CD-2743
    python3 make_single_cert.py reports_folder/ --number CD-2743 --client "Acme Corp"

One PDF per drive. With several reports, numbers count up from --number
(CD-2743, CD-2744, ...). PDFs go into ./certificates/ unless you pass --out.

Everything on the certificate comes from the report. If the report says the
erase wasn't verified, the certificate says so too — see the note in README.
"""
import argparse, os, re, sys
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
import killdisk_reports
import cert_extras

# ===================== DEFAULTS (override on the command line) =====================
DEFAULTS = {
    "operator":    "ENDBYTE-BENCH-01",
    "location":    "Santa Clara, California",
    "disposition": "Sanitized · retained for asset recovery",
    "disposition_failed": "Physically destroyed (shredded)",
}
FOOTER_LEFT  = "EndByte Data Destruction  ·  Santa Clara, CA"
FOOTER_RIGHT = "info@endbyte.net  ·  +1 (408) 420-6991"
VERIFY_URL   = "endbyte.net/verify.html?id="
# ====================================================================================

BG, PANEL, LINE, LINE2 = HexColor("#0E1116"), HexColor("#151A21"), HexColor("#262D38"), HexColor("#313A48")
TEXT, DIM, FAINT = HexColor("#E8ECF2"), HexColor("#8B95A5"), HexColor("#5A6373")
AMBER, GREEN, RED = HexColor("#FFB020"), HexColor("#2FD672"), HexColor("#E0736F")
SANS, SANS_B, MONO = "Helvetica", "Helvetica-Bold", "Courier"


def wrap(c, text, font, size, width):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if c.stringWidth(t, font, size) <= width: cur = t
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines


def fit(c, text, font, size, width):
    if c.stringWidth(text, font, size) <= width: return text
    while text and c.stringWidth(text + "…", font, size) > width: text = text[:-1]
    return text + "…"


def statement_for(d):
    if d["status"] == "PASS":
        return ("This certifies that the media identified above was sanitized in accordance "
                "with NIST Special Publication 800-88 guidelines, and that the result was "
                "verified by read-back.")
    if d["status"] == "ERASED":
        return ("This certifies that the media identified above was erased using the method "
                "recorded above, which completed without errors as reported by the erasure "
                "software.")
    return ("The erasure recorded above did not complete successfully. This device did not "
            "receive a sanitization certificate; its final disposition is recorded above.")


def draw(path, d, number, opts):
    W, H = letter
    c = canvas.Canvas(path, pagesize=letter)
    c.setTitle("EndByte — Certificate of Destruction %s" % number)
    c.setAuthor("EndByte Data Destruction")
    sample = opts.sample

    c.setFillColor(BG); c.rect(0, 0, W, H, fill=1, stroke=0)
    M = 36
    c.setStrokeColor(LINE2); c.setLineWidth(1); c.rect(M, M, W - 2*M, H - 2*M, fill=0, stroke=1)
    L, R = M + 32, W - M - 32

    top = H - M - 50
    c.setStrokeColor(AMBER); c.setLineWidth(1.6); c.rect(L, top - 8, 22, 22, fill=0, stroke=1)
    c.setFillColor(AMBER); c.rect(L + 7, top - 1, 8, 8, fill=1, stroke=0)
    c.setFont(SANS_B, 17); c.setFillColor(TEXT); c.drawString(L + 32, top - 1, "END")
    c.setFillColor(AMBER); c.drawString(L + 32 + c.stringWidth("END", SANS_B, 17), top - 1, "BYTE")
    c.setFont(MONO, 6.5); c.setFillColor(FAINT); c.drawRightString(R, top + 8, "DOCUMENT TYPE")
    c.setFont(MONO, 7.5); c.setFillColor(DIM); c.drawRightString(R, top - 3, "CERTIFICATE OF DESTRUCTION")
    c.setStrokeColor(LINE2); c.line(L, top - 32, R, top - 32)

    y = top - 72
    c.setFont(SANS_B, 25); c.setFillColor(TEXT); c.drawString(L, y, "Certificate of Destruction")
    sub = ("SAMPLE  ·  " if sample else "") + "NIST 800-88  ·  No. " + number
    c.setFont(MONO, 7.5); c.setFillColor(AMBER); c.drawString(L, y - 20, sub)

    fmt = lambda dt: dt.strftime("%Y-%m-%d %H:%M") if dt else "—"
    if d["status"] == "PASS":
        ver, vcol = "Verified · read-back passed", GREEN
    elif d["status"] == "ERASED":
        ver, vcol = "Not performed (per erase report)", AMBER
    else:
        ver, vcol = "—", FAINT
    if d["status"] != "FAIL":
        res = "Erased · %s" % d["errors"].lower()
    else:
        detail = d["errors"] if d["errors"].lower() not in ("no errors", "—") else d["result_raw"]
        res = "FAILED · %s" % detail.lower()
    rescol = GREEN if d["status"] != "FAIL" else RED
    disp = opts.disposition if d["status"] != "FAIL" else opts.disposition_failed

    rows = [("CERTIFICATE NO.", number, TEXT)]
    if opts.client:
        rows.append(("PREPARED FOR", opts.client, TEXT))
    if getattr(opts, "job", ""):
        rows.append(("JOB REFERENCE", opts.job, TEXT))
    rows += [
        ("DEVICE", d["model"], TEXT),
        ("SERIAL NUMBER", d["serial"], TEXT),
        ("MEDIA TYPE", "%s  ·  %s" % (d["type"], d["capacity"]), TEXT),
        ("FIRMWARE", d["firmware"] or "—", TEXT),
        ("METHOD", d["method"], TEXT),
        ("RESULT", res, rescol),
        ("VERIFICATION", ver, vcol),
        ("ERASE STARTED", fmt(d["started"]), TEXT),
        ("ERASE COMPLETED", "%s  ·  %s" % (fmt(d["finished"]), d["duration"] or "—"), TEXT),
        ("DISPOSITION", disp, TEXT if d["status"] != "FAIL" else RED),
        ("OPERATOR", opts.operator, TEXT),
        ("SOFTWARE", d["software"].strip(), TEXT),
        ("PROCESSED AT", opts.location, TEXT),
    ]
    rh = 19
    ty = y - 44
    th = rh * len(rows) + 10
    c.setFillColor(PANEL); c.setStrokeColor(LINE2)
    c.rect(L - 10, ty - th, (R - L) + 20, th, fill=1, stroke=1)
    ry = ty - 4
    for i, (k, v, col) in enumerate(rows):
        base = ry - rh + 6.5
        c.setFont(MONO, 6.8); c.setFillColor(FAINT); c.drawString(L, base, k)
        c.setFont(MONO, 8.2); c.setFillColor(col); c.drawRightString(R, base, fit(c, v, MONO, 8.2, R - L - 110))
        if i < len(rows) - 1:
            c.setStrokeColor(LINE); c.line(L, ry - rh, R, ry - rh)
        ry -= rh

    sy = ty - th - 28
    c.setFont(SANS, 8.8); c.setFillColor(DIM)
    for line in wrap(c, statement_for(d), SANS, 8.8, 280):
        c.drawString(L, sy, line); sy -= 13.5
    c.setFont(MONO, 6.8); c.setFillColor(FAINT)
    c.drawString(L, sy - 6, "Source report: " + fit(c, d["file"], MONO, 6.8, 300))
    cert_extras.draw_qr(c, L, sy - 88, number)

    label, scol = {"PASS": ("VERIFIED", GREEN), "ERASED": ("ERASED", GREEN), "FAIL": ("FAILED", RED)}[d["status"]]
    c.saveState()
    c.translate(R - 62, ty - th - 44); c.rotate(-7)
    c.setStrokeColor(scol); c.setLineWidth(1.8); c.rect(-62, -24, 124, 48, fill=0, stroke=1)
    c.setFillColor(scol); c.setFont("Times-BoldItalic", 12); c.drawCentredString(0, 3, label)
    c.setFont(MONO, 5.5)
    c.drawCentredString(0, -12, "ENDBYTE  ·  " + (d["finished"].strftime("%Y") if d["finished"] else ""))
    c.restoreState()

    fy = M + 40
    c.setStrokeColor(LINE2); c.line(L, fy + 12, R, fy + 12)
    c.setFont(MONO, 6.8); c.setFillColor(FAINT)
    c.drawString(L, fy, FOOTER_LEFT); c.drawRightString(R, fy, FOOTER_RIGHT)
    if sample:
        c.setFont(MONO, 6)
        c.drawCentredString(W / 2, fy - 16, "SAMPLE DOCUMENT — illustrative format only. Actual certificates reflect the specific media processed.")
    c.showPage(); c.save()


def publish(site, d, number, opts):
    """Add this certificate to the website's verify list (and the job's track page, if given)."""
    d = dict(d, _disposition=opts.disposition_failed if d["status"] == "FAIL" else opts.disposition)
    issued = (d["finished"] or d["started"]).strftime("%Y-%m-%d") if (d["finished"] or d["started"]) else ""
    cert_extras.register(os.path.join(site, "certificates.json"), number, issued,
                         d["method"], 1, cert_extras.single_result(d))
    if getattr(opts, "job", ""):
        cert_extras.mark_job_ready(os.path.join(site, "jobs.json"), opts.job, number)


def next_number(n, i):
    m = re.match(r"^(.*?)(\d+)$", n)
    if not m: return n if i == 0 else "%s-%d" % (n, i + 1)
    return "%s%0*d" % (m.group(1), len(m.group(2)), int(m.group(2)) + i)


def main():
    ap = argparse.ArgumentParser(description="Make one EndByte certificate per KillDisk report.")
    ap.add_argument("reports", nargs="+", help="KillDisk .xml report files and/or folders")
    ap.add_argument("--number", required=True, help="certificate number for the first drive, e.g. CD-2743")
    ap.add_argument("--client", default="", help="customer name to print on the certificate")
    ap.add_argument("--operator", default=DEFAULTS["operator"])
    ap.add_argument("--location", default=DEFAULTS["location"])
    ap.add_argument("--disposition", default=DEFAULTS["disposition"], help="what happened to drives that erased OK")
    ap.add_argument("--disposition-failed", default=DEFAULTS["disposition_failed"], help="what happened to drives that failed")
    ap.add_argument("--out", default="certificates", help="output folder (default: ./certificates)")
    ap.add_argument("--job", default="", help="job code from the track page, e.g. EB-7K3Q-92XD")
    ap.add_argument("--site", default="", help="your website folder (EndByte-main): adds each certificate to the "
                                               "verify page and marks the job ready on the track page")
    ap.add_argument("--sample", action="store_true", help="add SAMPLE markings")
    opts = ap.parse_args()

    drives = killdisk_reports.collect(opts.reports)
    if not drives:
        sys.exit("No readable KillDisk reports found.")
    os.makedirs(opts.out, exist_ok=True)
    for i, d in enumerate(drives):
        number = next_number(opts.number, i)
        path = os.path.join(opts.out, "%s_%s.pdf" % (number, re.sub(r"[^A-Za-z0-9_-]", "", d["serial"])))
        draw(path, d, number, opts)
        print("%-10s %-22s %-7s -> %s" % (number, d["serial"], d["status"], path))
        if opts.site and not opts.sample:
            publish(opts.site, d, number, opts)
    unverified = sum(1 for d in drives if d["status"] == "ERASED")
    if unverified:
        print("\nheads up: %d report(s) show verification='no' — those certificates say "
              "'Verification: not performed'." % unverified)
    if opts.site and not opts.sample:
        print("\nAdded to %s — upload certificates.json%s to GitHub to publish."
              % (os.path.join(opts.site, "certificates.json"), " and jobs.json" if opts.job else ""))


if __name__ == "__main__":
    main()
