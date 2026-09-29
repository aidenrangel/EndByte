#!/usr/bin/env python3
"""
Manage jobs on the tracking page (endbyte.net/track.html).

  python3 _build/job.py new --drives 32            # creates a job and prints its code, e.g. EB-7K3Q-92XD
  python3 _build/job.py set EB-7K3Q-92XD wiping    # stages: received, wiping, verifying, ready
  python3 _build/job.py note EB-7K3Q-92XD "3 drives failed verification, shredding Friday"
  python3 _build/job.py list
  python3 _build/job.py remove EB-7K3Q-92XD

Give the customer the job code. Then upload jobs.json to GitHub whenever it changes.
The certificate app marks a job "ready" automatically when you make its certificate
(put the job code in the "Job reference" box and set the website folder).

jobs.json is public: only the code, dates, drive count, stage and your short note go in it.
Never put client names, addresses or serial numbers here.
"""
import argparse, datetime, json, os, secrets, sys

PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "jobs.json")
STAGES = ["received", "wiping", "verifying", "ready"]
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"   # no 0/O, 1/I/L — easy to read over the phone


def load():
    if os.path.exists(PATH):
        with open(PATH, encoding="utf-8") as f: d = json.load(f)
    else:
        d = {}
    d.setdefault("_note", "Public job tracker for endbyte.net/track.html. Never put client names or serial numbers here.")
    d.setdefault("jobs", {})
    return d


def save(d):
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2, ensure_ascii=False); f.write("\n")


def new_code(existing):
    while True:
        code = "EB-" + "".join(secrets.choice(ALPHABET) for _ in range(4)) + "-" + "".join(secrets.choice(ALPHABET) for _ in range(4))
        if code not in existing: return code


def main():
    ap = argparse.ArgumentParser(description="Manage the public job tracking page.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new"); n.add_argument("--drives", type=int, default=0); n.add_argument("--date", default="")
    n.add_argument("--stage", default="received", choices=STAGES)
    s = sub.add_parser("set"); s.add_argument("code"); s.add_argument("stage", choices=STAGES); s.add_argument("--date", default="")
    s.add_argument("--drives", type=int)
    t = sub.add_parser("note"); t.add_argument("code"); t.add_argument("text")
    sub.add_parser("list")
    r = sub.add_parser("remove"); r.add_argument("code")
    a = ap.parse_args()

    d = load(); jobs = d["jobs"]
    today = datetime.date.today().isoformat()
    if a.cmd == "new":
        code = new_code(jobs)
        date = a.date or today
        hist = {}
        for st in STAGES[:STAGES.index(a.stage) + 1]: hist[st] = date
        jobs[code] = {"stage": a.stage, "drives": a.drives, "history": hist, "updated": date, "note": "", "certificates": []}
        save(d); print(code); return
    if a.cmd == "list":
        for k, v in sorted(jobs.items(), key=lambda kv: kv[1].get("updated", ""), reverse=True):
            print("%-14s %-10s %4s drives  updated %s  %s" % (k, v["stage"], v.get("drives", ""), v.get("updated", ""), " ".join(v.get("certificates", []))))
        return
    code = a.code.strip().upper()
    if code not in jobs: sys.exit("no job " + code)
    if a.cmd == "remove":
        del jobs[code]; save(d); print("removed", code); return
    if a.cmd == "note":
        jobs[code]["note"] = a.text; jobs[code]["updated"] = today; save(d); print("note saved"); return
    if a.cmd == "set":
        j = jobs[code]; date = a.date or today
        for st in STAGES[:STAGES.index(a.stage) + 1]: j["history"].setdefault(st, date)
        for st in STAGES[STAGES.index(a.stage) + 1:]: j["history"].pop(st, None)
        j["stage"] = a.stage; j["updated"] = date
        if a.drives is not None: j["drives"] = a.drives
        save(d); print(code, "->", a.stage)


if __name__ == "__main__":
    main()
