#!/usr/bin/env python3
"""
EndByte Certificates — a small window for making certificates from KillDisk reports.

    python3 make_certs_app.py        (or double-click "EndByte Certificates.command" on a Mac)

Pick the folder of XML reports, choose batch or single, fill in the number and
client, click Make Certificates. The PDFs are saved into the folder you picked
(or wherever you choose), and the folder opens when it's done.

Needs killdisk_reports.py, make_single_cert.py and make_batch_cert.py in the same folder.
"""
import json, os, re, subprocess, sys, threading, traceback
from argparse import Namespace
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import killdisk_reports
import make_single_cert
import make_batch_cert

SETTINGS = os.path.join(HERE, "cert_app_settings.json")


# ------------------------------------------------------------------ settings
def load_settings():
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(s):
    try:
        with open(SETTINGS, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2)
    except Exception:
        pass


def bump(number, by):
    """CD-2800 + 1 -> CD-2801 (keeps any leading zeros)."""
    m = re.match(r"^(.*?)(\d+)$", number or "")
    if not m:
        return number
    return "%s%0*d" % (m.group(1), len(m.group(2)), int(m.group(2)) + by)


# ------------------------------------------------------------------ the actual work
def run_job(p):
    """p: dict of the form values. Returns (message, output_folder)."""
    drives = killdisk_reports.collect([p["folder"]])
    if not drives:
        raise ValueError("No KillDisk XML reports were found in that folder.")
    out = p["out"] or p["folder"]
    os.makedirs(out, exist_ok=True)

    if p["mode"] == "batch":
        opts = Namespace(number=p["number"], client=p["client"], job=p["job"], received="", completed="",
                         custody=make_batch_cert.DEFAULTS["custody"], operator=p["operator"],
                         location=make_batch_cert.DEFAULTS["location"], disposition=p["disposition"],
                         disposition_failed=p["disposition_failed"], sample=False,
                         output=os.path.join(out, "%s_batch.pdf" % p["number"]))
        rows, info = make_batch_cert.from_reports([p["folder"]], opts)
        make_batch_cert.build(rows, info, opts)
        if p["site"]:
            make_batch_cert.publish(p["site"], rows, info, opts)
        made, used = [opts.output], 1
    else:
        opts = Namespace(client=p["client"], job=p["job"], operator=p["operator"],
                         location=make_single_cert.DEFAULTS["location"], disposition=p["disposition"],
                         disposition_failed=p["disposition_failed"], sample=False)
        made = []
        for i, d in enumerate(drives):
            number = make_single_cert.next_number(p["number"], i)
            path = os.path.join(out, "%s_%s.pdf" % (number, re.sub(r"[^A-Za-z0-9_-]", "", d["serial"])))
            make_single_cert.draw(path, d, number, opts)
            if p["site"]:
                make_single_cert.publish(p["site"], d, number, opts)
            made.append(path)
        used = len(drives)

    v = sum(1 for d in drives if d["status"] == "PASS")
    e = sum(1 for d in drives if d["status"] == "ERASED")
    f = sum(1 for d in drives if d["status"] == "FAIL")
    msg = "Made %d PDF%s for %d drive%s  (%d verified, %d erased/not verified, %d failed)." % (
        len(made), "" if len(made) == 1 else "s", len(drives), "" if len(drives) == 1 else "s", v, e, f)
    if e:
        msg += "\n\nNote: %d report%s had verification turned off, so %s" % (
            e, "" if e == 1 else "s",
            "those drives are marked ERASED (not verified) on the certificate." if p["mode"] == "batch"
            else "those certificates say \"Verification: not performed.\"")
    if p["site"]:
        msg += ("\n\nAdded to your verify page%s. Upload certificates.json%s from your website folder "
                "to GitHub to make %s live.") % (
            " and marked job %s ready" % p["job"] if p["job"] else "",
            " and jobs.json" if p["job"] else "", "them" if len(made) > 1 else "it")
    return msg, out, used


def open_folder(path):
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
        elif os.name == "nt":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


# ------------------------------------------------------------------ window
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("EndByte Certificates")
        self.resizable(False, False)
        s = load_settings()
        self.v = {
            "folder": tk.StringVar(),
            "out": tk.StringVar(),
            "site": tk.StringVar(value=s.get("site", "")),
            "mode": tk.StringVar(value=s.get("mode", "batch")),
            "number": tk.StringVar(value=s.get("next_number", "CD-2800")),
            "client": tk.StringVar(),
            "job": tk.StringVar(),
            "operator": tk.StringVar(value=s.get("operator", make_batch_cert.DEFAULTS["operator"])),
            "disposition": tk.StringVar(value=s.get("disposition", make_batch_cert.DEFAULTS["disposition"])),
            "disposition_failed": tk.StringVar(value=s.get("disposition_failed", make_batch_cert.DEFAULTS["disposition_failed"])),
        }
        self.last_dir = s.get("last_dir", os.path.expanduser("~"))
        self.build()
        self.v["mode"].trace_add("write", lambda *_: self.sync_mode())
        self.sync_mode()

    def build(self):
        pad = {"padx": 14, "pady": 5}
        f = ttk.Frame(self, padding=(10, 12))
        f.grid(sticky="nsew")
        f.columnconfigure(1, weight=1)
        r = 0

        ttk.Label(f, text="Reports folder").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(f, textvariable=self.v["folder"], width=46).grid(row=r, column=1, sticky="ew", pady=5)
        ttk.Button(f, text="Choose…", command=self.pick_folder).grid(row=r, column=2, padx=(6, 14))
        r += 1
        self.found = ttk.Label(f, text="Pick the folder with this job's KillDisk XML reports.", foreground="#666")
        self.found.grid(row=r, column=1, columnspan=2, sticky="w", padx=0, pady=(0, 8))
        r += 1

        ttk.Label(f, text="Certificate type").grid(row=r, column=0, sticky="w", **pad)
        m = ttk.Frame(f); m.grid(row=r, column=1, columnspan=2, sticky="w")
        ttk.Radiobutton(m, text="Batch — one PDF for the whole job", value="batch", variable=self.v["mode"]).pack(anchor="w")
        ttk.Radiobutton(m, text="Single — one PDF per drive", value="single", variable=self.v["mode"]).pack(anchor="w")
        r += 1

        self.number_label = ttk.Label(f, text="Certificate number")
        self.number_label.grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(f, textvariable=self.v["number"], width=18).grid(row=r, column=1, sticky="w", pady=5)
        r += 1
        ttk.Label(f, text="Client").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(f, textvariable=self.v["client"], width=46).grid(row=r, column=1, columnspan=2, sticky="ew", padx=(0, 14), pady=5)
        r += 1
        self.job_label = ttk.Label(f, text="Job reference")
        self.job_label.grid(row=r, column=0, sticky="w", **pad)
        self.job_entry = ttk.Entry(f, textvariable=self.v["job"], width=24)
        self.job_entry.grid(row=r, column=1, sticky="w", pady=5)
        r += 1

        ttk.Separator(f).grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
        r += 1
        ttk.Label(f, text="Erased drives went to").grid(row=r, column=0, sticky="w", **pad)
        ttk.Combobox(f, textvariable=self.v["disposition"], width=34,
                     values=["Retained · resale", "Returned to client", "Recycled", "Shredded"]).grid(row=r, column=1, sticky="w", pady=5)
        r += 1
        ttk.Label(f, text="Failed drives went to").grid(row=r, column=0, sticky="w", **pad)
        ttk.Combobox(f, textvariable=self.v["disposition_failed"], width=34,
                     values=["Shredded", "Physically destroyed (shredded)", "Returned to client", "Pending destruction"]).grid(row=r, column=1, sticky="w", pady=5)
        r += 1
        ttk.Label(f, text="Operator").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(f, textvariable=self.v["operator"], width=24).grid(row=r, column=1, sticky="w", pady=5)
        r += 1
        ttk.Label(f, text="Save PDFs to").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(f, textvariable=self.v["out"], width=46).grid(row=r, column=1, sticky="ew", pady=5)
        ttk.Button(f, text="Choose…", command=self.pick_out).grid(row=r, column=2, padx=(6, 14))
        r += 1
        ttk.Label(f, text="Leave blank to save into the reports folder.", foreground="#666").grid(row=r, column=1, columnspan=2, sticky="w")
        r += 1
        ttk.Label(f, text="Website folder").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(f, textvariable=self.v["site"], width=46).grid(row=r, column=1, sticky="ew", pady=5)
        ttk.Button(f, text="Choose…", command=self.pick_site).grid(row=r, column=2, padx=(6, 14))
        r += 1
        ttk.Label(f, text="Your EndByte-main folder. New certificates are added to the verify page and the job's\n"
                          "tracking status is set to \"Certificate ready.\" Leave blank to skip.",
                  foreground="#666", justify="left").grid(row=r, column=1, columnspan=2, sticky="w")
        r += 1

        self.go = ttk.Button(f, text="Make Certificates", command=self.make)
        self.go.grid(row=r, column=0, columnspan=3, pady=(16, 4))
        r += 1
        self.status = ttk.Label(f, text="", foreground="#666", wraplength=460, justify="left")
        self.status.grid(row=r, column=0, columnspan=3, sticky="w", padx=14, pady=(4, 6))

    def sync_mode(self):
        batch = self.v["mode"].get() == "batch"
        self.number_label.config(text="Certificate number" if batch else "First certificate number")
        pass

    def pick_folder(self):
        d = filedialog.askdirectory(title="Choose the folder with the KillDisk reports", initialdir=self.last_dir)
        if not d:
            return
        self.v["folder"].set(d)
        self.last_dir = os.path.dirname(d)
        try:
            drives = killdisk_reports.collect([d])
        except Exception as e:
            drives = []
        if not drives:
            self.found.config(text="No KillDisk XML reports found in that folder.", foreground="#b33")
            return
        v = sum(1 for x in drives if x["status"] == "PASS")
        e = sum(1 for x in drives if x["status"] == "ERASED")
        fl = sum(1 for x in drives if x["status"] == "FAIL")
        self.found.config(text="Found %d drive%s:  %d verified · %d erased, not verified · %d failed" %
                          (len(drives), "" if len(drives) == 1 else "s", v, e, fl), foreground="#2a7")

    def pick_site(self):
        d = filedialog.askdirectory(title="Choose your website folder (EndByte-main)", initialdir=self.v["site"].get() or self.last_dir)
        if not d:
            return
        if not os.path.exists(os.path.join(d, "verify.html")):
            messagebox.showwarning("EndByte Certificates", "That doesn't look like the website folder — it should contain verify.html.")
            return
        self.v["site"].set(d)

    def pick_out(self):
        d = filedialog.askdirectory(title="Where should the PDFs go?", initialdir=self.v["folder"].get() or self.last_dir)
        if d:
            self.v["out"].set(d)

    def make(self):
        p = {k: var.get().strip() for k, var in self.v.items()}
        if not p["folder"] or not os.path.isdir(p["folder"]):
            messagebox.showwarning("EndByte Certificates", "Choose the folder with the KillDisk reports first.")
            return
        if not re.match(r"^[A-Za-z]{1,6}-?\d+$", p["number"]):
            messagebox.showwarning("EndByte Certificates", "Enter a certificate number like CD-2800.")
            return
        self.go.config(state="disabled")
        self.status.config(text="Working…", foreground="#666")

        def work():
            try:
                msg, out, used = run_job(p)
                self.after(0, lambda: self.done(msg, out, used, p))
            except Exception as e:
                err = str(e) or traceback.format_exc(limit=1)
                self.after(0, lambda: self.failed(err))
        threading.Thread(target=work, daemon=True).start()

    def done(self, msg, out, used, p):
        self.go.config(state="normal")
        nxt = bump(p["number"], used)
        self.v["number"].set(nxt)
        save_settings({"next_number": nxt, "mode": p["mode"], "operator": p["operator"],
                       "disposition": p["disposition"], "disposition_failed": p["disposition_failed"],
                       "last_dir": self.last_dir, "site": p["site"]})
        self.status.config(text=msg + "\n\nNext certificate number: " + nxt, foreground="#2a7")
        open_folder(out)

    def failed(self, err):
        self.go.config(state="normal")
        self.status.config(text="Something went wrong: " + err, foreground="#b33")


if __name__ == "__main__":
    App().mainloop()
