"""
Reads Active@ KillDisk XML erase reports and turns each one into a drive record
for the EndByte certificate scripts. Used by make_single_cert.py and make_batch_cert.py.

Nothing is invented: every field comes from the report. If the report says the
erase was not verified, the drive is marked "not verified" and the certificate
wording changes to match.
"""
import glob, os, re, sys
import xml.etree.ElementTree as ET
from datetime import datetime

# KillDisk writes dates in the bench PC's locale. Yours are day-first (20/12/2023).
# If a bench is set to US format (12/20/2023), change this to "%m/%d/%Y %H:%M:%S".
DATE_FORMAT = "%d/%m/%Y %H:%M:%S"


def _text(root, path, default=""):
    el = root.find(path)
    return (el.text or "").strip() if el is not None and el.text else default


def _date(s):
    s = (s or "").strip()
    for fmt in (DATE_FORMAT, "%d/%m/%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def _capacity(root):
    """Marketed (decimal) capacity from the byte count, e.g. 400,088,457,216 -> '400 GB'."""
    for p in root.iter("param"):
        if p.get("title") == "Capacity" and p.text:
            m = re.search(r"\(([\d,]+) bytes\)", p.text)
            if m:
                b = int(m.group(1).replace(",", ""))
                if b >= 1e12:
                    tb = b / 1e12
                    return ("%g TB" % round(tb, 1)) if tb < 10 else ("%d TB" % round(tb))
                return "%d GB" % round(b / 1e9)
    return _text(root, "device/size", "—")


def _method_label(raw, passes):
    """'NIST 800-88 (One Pass Random)' -> 'NIST 800-88 · 1-pass random'."""
    if not raw:
        return "—"
    m = re.match(r"\s*(.*?)\s*\((.*)\)\s*$", raw)
    if m:
        std, detail = m.group(1), m.group(2)
        detail = re.sub(r"\bOne Pass\b", "1-pass", detail, flags=re.I)
        detail = re.sub(r"\bThree Pass\b", "3-pass", detail, flags=re.I)
        return "%s · %s" % (std, detail.lower())
    if passes and passes != "1":
        return "%s · %s-pass" % (raw, passes)
    return raw


def parse_report(path):
    root = ET.parse(path).getroot()
    if root.tag != "report":
        raise ValueError("not a KillDisk report")
    erase = root.find("erase")
    method_raw = erase.get("method", "") if erase is not None else ""
    passes = erase.get("passes", "") if erase is not None else ""
    verified = (erase is not None and erase.get("verification", "no").strip().lower() in ("yes", "true", "1"))

    dtype = _text(root, "device/type")
    media = "SSD" if re.search(r"\b(SSD|NVMe|Solid)\b", dtype, re.I) else "HDD"
    result = _text(root, "results/result")
    errors = _text(root, "results/errors")
    conclusion = _text(root, "conclusion")
    erased = result.lower() == "erased" and (not errors or errors.lower() == "no errors")

    if not erased:
        status = "FAIL"
    elif verified:
        status = "PASS"
    else:
        status = "ERASED"          # erased, but the report does not include a verification pass

    started = _date(_text(root, "results/started"))
    finished = _date(root.get("created", ""))
    return {
        "file": os.path.basename(path),
        "model": _text(root, "device/product") or _text(root, "device/smart-parameters/param", "—"),
        "serial": _text(root, "device/serial-number", "—"),
        "firmware": _text(root, "device/revision"),
        "capacity": _capacity(root),
        "type": media,
        "method": _method_label(method_raw, passes),
        "method_raw": method_raw,
        "passes": passes,
        "verified": verified,
        "status": status,
        "result_raw": result or "—",
        "errors": errors or "—",
        "conclusion": conclusion,
        "started": started,
        "finished": finished,
        "duration": _text(root, "results/elapsed"),
        "software": "%s %s" % (root.get("provider", "KillDisk"), root.get("version", "")),
    }


def collect(paths):
    """Accepts report files and/or folders. Returns drive records, oldest first.
    If the same serial appears more than once, the most recent report wins."""
    files = []
    for p in paths:
        if os.path.isdir(p):
            files += sorted(glob.glob(os.path.join(p, "**", "*.xml"), recursive=True))
        else:
            files.append(p)
    by_serial, skipped = {}, []
    for f in files:
        try:
            d = parse_report(f)
        except Exception as e:
            skipped.append("%s (%s)" % (os.path.basename(f), e))
            continue
        prev = by_serial.get(d["serial"])
        if prev:
            newer = (d["finished"] or datetime.min) >= (prev["finished"] or datetime.min)
            print("note: %s appears in more than one report — using %s" %
                  (d["serial"], (d if newer else prev)["file"]), file=sys.stderr)
            if not newer:
                continue
        by_serial[d["serial"]] = d
    for s in skipped:
        print("skipped: " + s, file=sys.stderr)
    return sorted(by_serial.values(), key=lambda d: d["finished"] or datetime.min)
