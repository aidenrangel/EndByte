"""
Shared helpers for the EndByte certificate tools:
  - draw_qr(): puts a scannable "verify this certificate" QR code on a PDF page
  - register(): adds a certificate to the website's certificates.json (the verify page's list)
  - mark_job_ready(): moves a job on the website's jobs.json (the track page) to "Certificate ready"

Only non-sensitive fields ever go into the website files: certificate number, date,
method, drive count and result. Never client names or serial numbers.
"""
import datetime, json, os, re
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF
from reportlab.lib.colors import HexColor, white

SITE = "https://www.endbyte.net"


def verify_url(number):
    return "%s/verify.html?id=%s" % (SITE, number)


def draw_qr(c, x, y, number, size=62, label_color=HexColor("#8B95A5"), faint=HexColor("#5A6373")):
    """Draws a white-backed QR code with its bottom-left corner at (x, y), plus a caption to its right."""
    pad = 5
    c.setFillColor(white)
    c.roundRect(x, y, size, size, 3, fill=1, stroke=0)
    w = qr.QrCodeWidget(verify_url(number), barLevel="M")
    b = w.getBounds()
    bw, bh = b[2] - b[0], b[3] - b[1]
    inner = size - 2 * pad
    d = Drawing(inner, inner, transform=[inner / bw, 0, 0, inner / bh, 0, 0])
    d.add(w)
    renderPDF.draw(d, c, x + pad, y + pad)
    tx = x + size + 12
    c.setFont("Helvetica-Bold", 8.5); c.setFillColor(label_color)
    c.drawString(tx, y + size - 14, "Scan to verify this certificate")
    c.setFont("Courier", 6.8); c.setFillColor(faint)
    c.drawString(tx, y + size - 27, "endbyte.net/verify.html?id=" + number)
    c.drawString(tx, y + size - 38, "Or enter No. %s at endbyte.net/verify.html" % number)


# ------------------------------------------------------------------ website files
def _load(path, key):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    data.setdefault(key, {})
    return data


def _save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False); f.write("\n")
    os.replace(tmp, path)


def register(registry_path, number, issued, method, drives, result):
    """Add or update one certificate on the verify page's list."""
    data = _load(registry_path, "certificates")
    data.setdefault("_note", "Public certificate registry for endbyte.net/verify.html. "
                             "Never put client names or full serial numbers here.")
    existed = number in data["certificates"]
    data["certificates"][number] = {"issued": issued, "method": method, "drives": drives, "result": result}
    _save(registry_path, data)
    return "updated" if existed else "added"


def mark_job_ready(jobs_path, job, number, when=None):
    """If `job` is on the track page, move it to 'Certificate ready' and link the certificate."""
    if not job or not os.path.exists(jobs_path):
        return False
    data = _load(jobs_path, "jobs")
    key = job.strip().upper()
    if key not in data["jobs"]:
        return False
    j = data["jobs"][key]
    today = when or datetime.date.today().isoformat()
    hist = j.setdefault("history", {})
    for stage in ("received", "wiping", "verifying"):
        hist.setdefault(stage, today)
    hist["ready"] = today
    j["stage"] = "ready"
    certs = j.setdefault("certificates", [])
    if number not in certs:
        certs.append(number)
    j["updated"] = today
    _save(jobs_path, data)
    return True


# ------------------------------------------------------------------ summaries for the registry
def single_result(d):
    if d["status"] == "PASS":
        return "PASS · erased and verified"
    if d["status"] == "ERASED":
        return "Erased · no errors · not verified"
    return "Erase failed · " + ("physically destroyed" if re.search(r"shred|destroy", d.get("_disposition", ""), re.I)
                                else "see certificate")


def batch_result(verified, erased_only, failed):
    parts = []
    if verified: parts.append("%d erased + verified" % verified)
    if erased_only: parts.append("%d erased, not verified" % erased_only)
    if failed: parts.append("%d failed" % failed)
    return " · ".join(parts) or "—"
