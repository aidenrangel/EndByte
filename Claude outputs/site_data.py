"""
Reads and writes the two public data files in your website folder:
  jobs.json          -> the Track a Job page (endbyte.net/track.html)
  certificates.json  -> the Verify a Certificate page (endbyte.net/verify.html)

Used by the EndByte app (make_certs_app.py). Only non-sensitive fields go in these
files — never client names, addresses or serial numbers.
"""
import datetime, json, os, secrets

STAGES = ["received", "wiping", "verifying", "ready"]
STAGE_LABELS = {"received": "Received", "wiping": "Wiping", "verifying": "Verifying", "ready": "Certificate ready"}
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # no 0/O or 1/I/L, easy to read over the phone
TRACK_URL = "https://www.endbyte.net/track.html?job="


def today():
    return datetime.date.today().isoformat()


def _load(path, key, note):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    data.setdefault("_note", note)
    data.setdefault(key, {})
    return data


def _save(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False); f.write("\n")
    os.replace(tmp, path)


# ------------------------------------------------------------------ jobs
class Jobs:
    NOTE = "Public job tracker for endbyte.net/track.html. Never put client names or serial numbers here."

    def __init__(self, site):
        self.path = os.path.join(site, "jobs.json")

    def all(self):
        return _load(self.path, "jobs", self.NOTE)["jobs"]

    def new(self, drives=0):
        d = _load(self.path, "jobs", self.NOTE)
        while True:
            code = "EB-%s-%s" % ("".join(secrets.choice(_ALPHABET) for _ in range(4)),
                                 "".join(secrets.choice(_ALPHABET) for _ in range(4)))
            if code not in d["jobs"]:
                break
        d["jobs"][code] = {"stage": "received", "drives": int(drives or 0), "history": {"received": today()},
                           "updated": today(), "note": "", "certificates": []}
        _save(self.path, d)
        return code

    def set_stage(self, code, stage):
        d = _load(self.path, "jobs", self.NOTE)
        j = d["jobs"][code]
        i = STAGES.index(stage)
        for st in STAGES[:i + 1]:
            j["history"].setdefault(st, today())
        for st in STAGES[i + 1:]:
            j["history"].pop(st, None)
        j["stage"] = stage; j["updated"] = today()
        _save(self.path, d)

    def update(self, code, drives=None, note=None):
        d = _load(self.path, "jobs", self.NOTE)
        j = d["jobs"][code]
        if drives is not None: j["drives"] = int(drives or 0)
        if note is not None: j["note"] = note.strip()
        j["updated"] = today()
        _save(self.path, d)

    def remove(self, code):
        d = _load(self.path, "jobs", self.NOTE)
        d["jobs"].pop(code, None)
        _save(self.path, d)


# ------------------------------------------------------------------ verify list
class Certificates:
    NOTE = "Public certificate registry for endbyte.net/verify.html. Never put client names or full serial numbers here."

    def __init__(self, site):
        self.path = os.path.join(site, "certificates.json")

    def all(self):
        return _load(self.path, "certificates", self.NOTE)["certificates"]

    def put(self, number, issued, method, drives, result):
        d = _load(self.path, "certificates", self.NOTE)
        d["certificates"][number.strip().upper()] = {"issued": issued, "method": method,
                                                     "drives": int(drives or 0), "result": result}
        _save(self.path, d)

    def remove(self, number):
        d = _load(self.path, "certificates", self.NOTE)
        d["certificates"].pop(number, None)
        _save(self.path, d)
