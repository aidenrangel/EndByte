#!/usr/bin/env python3
"""
Add a certificate to the public registry used by endbyte.net/verify.html.

  python3 _build/add_cert.py CD-2612 --drives 48 --method "NIST 800-88 Clear"
  python3 _build/add_cert.py CD-2613 --drives 3 --method "Physical destruction (shred)" --date 2026-09-30
  python3 _build/add_cert.py --list
  python3 _build/add_cert.py --remove CD-2612

Only non-sensitive fields are published: number, date, method, drive count, result.
Never add client names or full serial numbers — the registry is a public file.
Then commit and push certificates.json with the rest of the site.
"""
import argparse, datetime, json, os, re, sys

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "certificates.json")

def load():
    with open(PATH, encoding="utf-8") as f: return json.load(f)

def save(d):
    with open(PATH, "w", encoding="utf-8") as f: json.dump(d, f, indent=2); f.write("\n")

ap = argparse.ArgumentParser(description="Manage the public certificate registry.")
ap.add_argument("id", nargs="?", help="certificate number, e.g. CD-2612")
ap.add_argument("--drives", type=int, default=1)
ap.add_argument("--method", default="NIST 800-88 Clear")
ap.add_argument("--result", default="PASS · 100% sectors verified")
ap.add_argument("--date", default=datetime.date.today().isoformat(), help="YYYY-MM-DD (default: today)")
ap.add_argument("--list", action="store_true")
ap.add_argument("--remove", metavar="ID")
a = ap.parse_args()

d = load(); certs = d.setdefault("certificates", {})
if a.list:
    for k, v in sorted(certs.items()): print(k, v)
    sys.exit()
if a.remove:
    print("removed" if certs.pop(a.remove.upper(), None) else "not found", a.remove.upper()); save(d); sys.exit()
if not a.id: ap.error("certificate number required")
cid = a.id.strip().upper()
if not re.fullmatch(r"[A-Z]{2,4}-\d{3,8}", cid): ap.error("expected a number like CD-2612")
datetime.date.fromisoformat(a.date)
if cid in certs: print("updating existing", cid)
certs[cid] = {"issued": a.date, "method": a.method, "drives": a.drives, "result": a.result}
save(d)
print("saved", cid, certs[cid])
