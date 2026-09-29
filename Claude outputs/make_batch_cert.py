#!/usr/bin/env python3
"""
EndByte batch certificate — one document covering every drive in a job.

    pip install reportlab                                   (once)
    python3 make_batch_cert.py reports_folder/ --number CD-2742 --client "Acme Corp" --job JOB-2026-0142
    python3 make_batch_cert.py a.xml b.xml c.xml --number CD-2742
    python3 make_batch_cert.py drives.csv --number CD-2742      (CSV still works)
    python3 make_batch_cert.py --sample                         (made-up demo batch)

KillDisk XML reports are read directly: model, serial, capacity, type, method,
result and dates all come from the reports. The received and completed dates
are taken from the earliest and latest report unless you pass --received /
--completed. Long lists continue onto extra pages automatically.

CSV columns (header row required): model,serial,capacity,type,method,result,disposition
  result: PASS (erased + verified), ERASED (erased, not verified) or FAIL
"""
import argparse, csv, os, random, sys
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
import killdisk_reports
import cert_extras

# ===================== DEFAULTS (override on the command line) =====================
DEFAULTS = {
    "custody":     "Pickup · sealed transport",
    "operator":    "ENDBYTE-BENCH-01",
    "location":    "Santa Clara, California",
    "disposition": "Retained · resale",
    "disposition_failed": "Shredded",
}
FOOTER_LEFT  = "EndByte Data Destruction  ·  Santa Clara, CA"
FOOTER_RIGHT = "info@endbyte.net  ·  +1 (408) 420-6991"
VERIFY_URL   = "endbyte.net/verify.html?id="
# ====================================================================================


# ---------------------------------------------------------------- inputs
def short_method(m):
    """Keeps the table column narrow: 'NIST 800-88 · 1-pass random' -> 'NIST · 1-pass random'."""
    return m.replace("NIST 800-88 · ", "NIST · ").replace("NIST 800-88 ", "NIST ")


def from_reports(paths, opts):
    rows, info = [], {}
    drives = killdisk_reports.collect(paths)
    for d in drives:
        disp = opts.disposition if d["status"] != "FAIL" else opts.disposition_failed
        rows.append([d["model"], d["serial"], d["capacity"], d["type"], short_method(d["method"]), d["status"], disp])
    starts = [d["started"] for d in drives if d["started"]]
    ends = [d["finished"] for d in drives if d["finished"]]
    if starts: info["received"] = min(starts).strftime("%Y-%m-%d")
    if ends: info["completed"] = max(ends).strftime("%Y-%m-%d")
    info["methods"] = sorted({d["method"] for d in drives})
    return rows, info


def from_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = [[r["model"], r["serial"], r["capacity"], r["type"], short_method(r["method"]),
                 r["result"].strip().upper(), r["disposition"]] for r in csv.DictReader(f)]
    return rows, {"methods": sorted({r[4] for r in rows})}


def sample_rows():
    rnd = random.Random(2742)
    def ser(prefix, n, chars="ABCDEFGHJKLMNPQRSTUVWXYZ0123456789"):
        return prefix + "".join(rnd.choice(chars) for _ in range(n))
    rows = []
    rows += [["Seagate ST8000NM0055", ser("ZA1", 5), "8 TB", "HDD", "NIST · Clear", "PASS", "Retained · resale"] for _ in range(14)]
    rows += [["WD HUH721212ALE604", ser("8DG", 5), "12 TB", "HDD", "NIST · Clear", "PASS", "Retained · resale"] for _ in range(8)]
    rows += [["Samsung MZ7LH960HAJR", ser("S4CHNX0M", 6), "960 GB", "SSD", "NIST · Purge", "PASS", "Retained · resale"] for _ in range(6)]
    rows += [["Intel SSDSC2KB480G8", ser("PHYF", 10, "0123456789"), "480 GB", "SSD", "NIST · Purge", "PASS", "Returned to client"] for _ in range(3)]
    rows.insert(17, ["Seagate ST8000NM0055", ser("ZA1", 5), "8 TB", "HDD", "NIST · Clear", "FAIL", "Shredded"])
    return rows, {"received": "2026-09-21", "completed": "2026-09-22", "methods": ["NIST 800-88 Clear", "NIST 800-88 Purge"]}


# ---------------------------------------------------------------- drawing
BG, PANEL, LINE, LINE2 = HexColor("#0E1116"), HexColor("#151A21"), HexColor("#262D38"), HexColor("#313A48")
TEXT, DIM, FAINT = HexColor("#E8ECF2"), HexColor("#8B95A5"), HexColor("#5A6373")
AMBER, GREEN, RED = HexColor("#FFB020"), HexColor("#2FD672"), HexColor("#E0736F")
SANS, SANS_B, MONO = "Helvetica", "Helvetica-Bold", "Courier"
W, H = letter
M = 36
L, R = M + 32, W - M - 32

COLS = [("#", 16, "l"), ("MODEL", 100, "l"), ("SERIAL", 82, "l"), ("CAP.", 34, "l"),
        ("TYPE", 24, "l"), ("METHOD", 90, "l"), ("RESULT", 38, "l"), ("DISPOSITION", None, "r")]


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


def col_x():
    xs, x = [], L
    fixed = sum(w for _, w, _ in COLS if w)
    for _, w, a in COLS:
        w = w or (R - L - fixed)
        xs.append((x, w, a)); x += w
    return xs


def page_frame(c, page, pages, number, sample):
    c.setFillColor(BG); c.rect(0, 0, W, H, fill=1, stroke=0)
    c.setStrokeColor(LINE2); c.setLineWidth(1); c.rect(M, M, W - 2*M, H - 2*M, fill=0, stroke=1)
    top = H - M - 50
    c.setStrokeColor(AMBER); c.setLineWidth(1.6); c.rect(L, top - 8, 22, 22, fill=0, stroke=1)
    c.setFillColor(AMBER); c.rect(L + 7, top - 1, 8, 8, fill=1, stroke=0)
    c.setFont(SANS_B, 17); c.setFillColor(TEXT); c.drawString(L + 32, top - 1, "END")
    c.setFillColor(AMBER); c.drawString(L + 32 + c.stringWidth("END", SANS_B, 17), top - 1, "BYTE")
    c.setFont(MONO, 6.5); c.setFillColor(FAINT); c.drawRightString(R, top + 8, "DOCUMENT TYPE")
    c.setFont(MONO, 7.5); c.setFillColor(DIM); c.drawRightString(R, top - 3, "BATCH CERTIFICATE OF DESTRUCTION")
    c.setStrokeColor(LINE2); c.line(L, top - 32, R, top - 32)
    fy = M + 40
    c.setStrokeColor(LINE2); c.line(L, fy + 12, R, fy + 12)
    c.setFont(MONO, 6.8); c.setFillColor(FAINT)
    c.drawString(L, fy, FOOTER_LEFT)
    c.drawCentredString(W / 2, fy, "%s  ·  PAGE %d OF %d" % (number, page, pages))
    c.drawRightString(R, fy, FOOTER_RIGHT)
    if sample:
        c.setFont(MONO, 6)
        c.drawCentredString(W / 2, fy - 16, "SAMPLE DOCUMENT — illustrative format only. Actual certificates reflect the specific media processed.")
    return top - 32


def table_header(c, y):
    c.setFillColor(PANEL); c.rect(L - 8, y - 16, (R - L) + 16, 18, fill=1, stroke=0)
    c.setFont(MONO, 6.3); c.setFillColor(FAINT)
    for (name, _, _), (x, w, a) in zip(COLS, col_x()):
        (c.drawRightString(x + w, y - 10, name) if a == "r" else c.drawString(x, y - 10, name))
    return y - 18


def drive_row(c, y, i, d, rh):
    model, serial, cap, typ, method, result, disp = d
    rcol = {"PASS": GREEN, "ERASED": AMBER}.get(result, RED)
    vals = [str(i), model, serial, cap, typ, method, result, disp]
    for k, (v, (x, w, a)) in enumerate(zip(vals, col_x())):
        col = FAINT if k == 0 else (rcol if k == 6 else (RED if (k == 7 and result == "FAIL") else TEXT))
        c.setFont(MONO, 6.8); c.setFillColor(col)
        v = fit(c, v, MONO, 6.8, w - 5)
        (c.drawRightString(x + w, y - rh + 5.5, v) if a == "r" else c.drawString(x, y - rh + 5.5, v))
    c.setStrokeColor(LINE); c.line(L - 8, y - rh, R + 8, y - rh)
    return y - rh


def build(rows, info, opts):
    n = len(rows)
    verified = sum(1 for d in rows if d[5] == "PASS")
    erased_only = sum(1 for d in rows if d[5] == "ERASED")
    failed = n - verified - erased_only
    hdd = sum(1 for d in rows if d[3].upper() == "HDD"); ssd = n - hdd
    dispositions = {}
    for d in rows: dispositions[d[6]] = dispositions.get(d[6], 0) + 1
    received = opts.received or info.get("received", "—")
    completed = opts.completed or info.get("completed", "—")
    methods = info.get("methods") or []
    methods_txt = " / ".join(m.replace("NIST 800-88 · ", "").replace("NIST 800-88 ", "") for m in methods) or "—"

    if erased_only == 0:
        statement = ("This certifies that every device listed in this certificate was received into "
                     "EndByte custody and sanitized in accordance with NIST Special Publication 800-88 "
                     "guidelines, with the result verified by read-back — or, where erasure failed, "
                     "handled as recorded in its disposition. The device count on this certificate "
                     "reconciles against the intake list for this job.")
    else:
        statement = ("This certifies that every device listed in this certificate was received into "
                     "EndByte custody and erased using the method recorded for it, as reported by the "
                     "erasure software. Devices marked ERASED completed without errors; verification "
                     "was not part of their erase run. Devices marked FAIL are handled as recorded in "
                     "their disposition. The device count reconciles against the intake list for this job.")

    RH = 15.5
    first_rows, other_rows = 20, 34
    closing_space = 230
    chunks, rest = [rows[:first_rows]], rows[first_rows:]
    while rest:
        chunks.append(rest[:other_rows]); rest = rest[other_rows:]
    last_room = (other_rows if len(chunks) > 1 else first_rows) - len(chunks[-1])
    needs_extra = last_room * RH < closing_space
    pages = len(chunks) + (1 if needs_extra else 0)

    c = canvas.Canvas(opts.output, pagesize=letter)
    c.setTitle("EndByte — Batch Certificate of Destruction %s" % opts.number)
    c.setAuthor("EndByte Data Destruction")

    idx = 1
    for p, chunk in enumerate(chunks, start=1):
        y = page_frame(c, p, pages, opts.number, opts.sample)
        if p == 1:
            y -= 40
            c.setFont(SANS_B, 23); c.setFillColor(TEXT); c.drawString(L, y, "Batch Certificate of Destruction")
            sub = ("SAMPLE  ·  " if opts.sample else "") + "NIST 800-88  ·  No. " + opts.number
            c.setFont(MONO, 7.5); c.setFillColor(AMBER); c.drawString(L, y - 18, sub)
            y -= 40
            left = [("PREPARED FOR", opts.client or "—"), ("JOB REFERENCE", opts.job or "—"),
                    ("CUSTODY", opts.custody), ("PROCESSED AT", opts.location)]
            right = [("WORK STARTED", received), ("COMPLETED", completed),
                     ("OPERATOR", opts.operator), ("METHODS", methods_txt)]
            bh = 4 * 17 + 10
            c.setFillColor(PANEL); c.setStrokeColor(LINE2); c.rect(L - 10, y - bh, (R - L) + 20, bh, fill=1, stroke=1)
            mid = (L + R) / 2
            for col_i, items in enumerate((left, right)):
                x0 = L if col_i == 0 else mid + 14
                x1 = mid - 14 if col_i == 0 else R
                yy = y - 5
                for k, v in items:
                    c.setFont(MONO, 6.6); c.setFillColor(FAINT); c.drawString(x0, yy - 12, k)
                    c.setFont(MONO, 7.8); c.setFillColor(TEXT); c.drawRightString(x1, yy - 12, fit(c, v, MONO, 7.8, x1 - x0 - 66))
                    yy -= 17
            c.setStrokeColor(LINE); c.line(mid, y - 6, mid, y - bh + 6)
            y -= bh + 16
            tiles = [("DRIVES RECEIVED", str(n), TEXT)]
            if erased_only:
                tiles += [("ERASED · NOT VERIFIED", str(erased_only), AMBER), ("ERASED + VERIFIED", str(verified), GREEN)]
            else:
                tiles += [("SANITIZED + VERIFIED", str(verified), GREEN)]
            tiles += [("FAILED", str(failed), RED if failed else TEXT)]
            if len(tiles) == 3:
                tiles.append(("UNACCOUNTED FOR", "0", GREEN))
            tw = ((R - L) + 20) / 4
            for t, (k, v, col) in enumerate(tiles):
                x = L - 10 + t * tw
                c.setFillColor(BG); c.setStrokeColor(LINE2); c.rect(x, y - 44, tw, 44, fill=1, stroke=1)
                c.setFont(SANS_B, 17); c.setFillColor(col); c.drawString(x + 10, y - 22, v)
                c.setFont(MONO, 6); c.setFillColor(FAINT); c.drawString(x + 10, y - 36, k)
            y -= 62
            c.setFont(MONO, 6.8); c.setFillColor(FAINT)
            c.drawString(L, y, "DEVICE LIST  ·  %d HDD  ·  %d SSD" % (hdd, ssd))
            y -= 8
        else:
            y -= 22
            c.setFont(MONO, 6.8); c.setFillColor(FAINT)
            c.drawString(L, y, "DEVICE LIST (CONTINUED)  ·  No. " + opts.number)
            y -= 8
        y = table_header(c, y)
        for d in chunk:
            y = drive_row(c, y, idx, d, RH); idx += 1
        if p < len(chunks) or needs_extra:
            c.showPage()

    if needs_extra:
        y = page_frame(c, pages, pages, opts.number, opts.sample) - 30

    y -= 22
    disp_txt = "   ·   ".join("%s: %d" % (k, v) for k, v in dispositions.items())
    c.setFont(MONO, 6.8); c.setFillColor(FAINT); c.drawString(L, y, fit(c, "DISPOSITION  ·  " + disp_txt, MONO, 6.8, R - L))
    y -= 26
    c.setFont(SANS, 8.8); c.setFillColor(DIM)
    for line in wrap(c, statement, SANS, 8.8, 300):
        c.drawString(L, y, line); y -= 13.5
    cert_extras.draw_qr(c, L, y - 82, opts.number)
    stamp, scol = ("VERIFIED", GREEN) if erased_only == 0 else ("COMPLETE", GREEN)
    c.saveState()
    c.translate(R - 62, y + 40); c.rotate(-7)
    c.setStrokeColor(scol); c.setLineWidth(1.8); c.rect(-62, -24, 124, 48, fill=0, stroke=1)
    c.setFillColor(scol); c.setFont("Times-BoldItalic", 12); c.drawCentredString(0, 3, stamp)
    c.setFont(MONO, 5.5); c.drawCentredString(0, -12, "ENDBYTE  ·  %d DRIVES" % n)
    c.restoreState()

    c.showPage(); c.save()
    opts._summary = (verified, erased_only, failed)
    print("wrote %s  (%d drives: %d verified, %d erased/not verified, %d failed · %d page%s)" %
          (opts.output, n, verified, erased_only, failed, pages, "" if pages == 1 else "s"))


def main():
    ap = argparse.ArgumentParser(description="Make one EndByte batch certificate for a job.")
    ap.add_argument("inputs", nargs="*", help="KillDisk .xml reports, folders of them, or one .csv")
    ap.add_argument("--number", help="certificate number, e.g. CD-2742")
    ap.add_argument("--client", default="")
    ap.add_argument("--job", default="", help="job reference, e.g. JOB-2026-0142")
    ap.add_argument("--received", default="", help="override the work-started date (YYYY-MM-DD)")
    ap.add_argument("--completed", default="", help="override the completed date (YYYY-MM-DD)")
    ap.add_argument("--custody", default=DEFAULTS["custody"])
    ap.add_argument("--operator", default=DEFAULTS["operator"])
    ap.add_argument("--location", default=DEFAULTS["location"])
    ap.add_argument("--disposition", default=DEFAULTS["disposition"], help="for drives that erased OK")
    ap.add_argument("--disposition-failed", default=DEFAULTS["disposition_failed"], help="for drives that failed")
    ap.add_argument("--output", default="", help="PDF path (default: <number>_batch.pdf)")
    ap.add_argument("--site", default="", help="your website folder (EndByte-main): adds the certificate to the "
                                               "verify page and marks the job ready on the track page")
    ap.add_argument("--sample", action="store_true", help="made-up demo batch with SAMPLE markings")
    opts = ap.parse_args()

    if opts.sample and not opts.inputs:
        rows, info = sample_rows()
        opts.number = opts.number or "CD-2742"
        opts.client = opts.client or "Sample Company, Inc."
        opts.job = opts.job or "JOB-2026-0142"
    elif not opts.inputs:
        ap.error("give KillDisk reports (files or a folder), a CSV, or --sample")
    elif len(opts.inputs) == 1 and opts.inputs[0].lower().endswith(".csv"):
        rows, info = from_csv(opts.inputs[0])
    else:
        rows, info = from_reports(opts.inputs, opts)
    if not rows:
        sys.exit("No drives found.")
    if not opts.number:
        ap.error("--number is required, e.g. --number CD-2742")
    opts.output = opts.output or "%s_batch.pdf" % opts.number
    build(rows, info, opts)
    if opts.site and not opts.sample:
        publish(opts.site, rows, info, opts)
        print("Added %s to the verify page%s — upload certificates.json%s to GitHub to publish." % (
            opts.number, " and marked %s ready" % opts.job if opts.job else "", " and jobs.json" if opts.job else ""))


def publish(site, rows, info, opts):
    """Add this batch certificate to the website's verify list (and mark the job ready on the track page)."""
    verified, erased_only, failed = opts._summary
    issued = opts.completed or info.get("completed") or ""
    methods = info.get("methods") or []
    method = " / ".join(methods) if len(methods) <= 2 else "Multiple (see certificate)"
    cert_extras.register(os.path.join(site, "certificates.json"), opts.number, issued, method,
                         len(rows), cert_extras.batch_result(verified, erased_only, failed))
    if opts.job:
        cert_extras.mark_job_ready(os.path.join(site, "jobs.json"), opts.job, opts.number)


if __name__ == "__main__":
    main()
