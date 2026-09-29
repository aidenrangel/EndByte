#!/usr/bin/env python3
"""
EndByte Desk — certificates, job tracking and the verify list in one window.

    python3 make_certs_app.py        (or double-click "EndByte Certificates.command" on a Mac)

Tabs:
  Make certificates  pick a folder of KillDisk reports -> batch or single PDFs with QR codes
  Jobs               create job codes for customers and move them through
                     Received -> Wiping -> Verifying -> Certificate ready
  Verify list        see / add / remove certificates customers can look up online

Everything that touches the website edits two files in your website folder:
jobs.json and certificates.json. The bar at the top tells you when they've changed
and need uploading to GitHub.

Needs killdisk_reports.py, make_single_cert.py, make_batch_cert.py, cert_extras.py and
site_data.py in the same folder.
"""
import json, os, re, subprocess, sys, threading, traceback, webbrowser
from argparse import Namespace
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import killdisk_reports
import make_single_cert
import make_batch_cert
import site_data
from site_data import STAGES, STAGE_LABELS

SETTINGS = os.path.join(HERE, "cert_app_settings.json")
GREEN, RED, GREY, AMBER = "#1f9d55", "#b33", "#666", "#b7791f"


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


def open_path(path):
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", path])
        elif os.name == "nt":
            os.startfile(path)
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


# ------------------------------------------------------------------ certificate work (unchanged logic)
def run_job(p):
    """p: dict of the form values. Returns (message, output_folder, numbers_used)."""
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
        msg += "\nNote: %d report%s had verification turned off, so %s" % (
            e, "" if e == 1 else "s",
            "those drives are marked ERASED (not verified) on the certificate." if p["mode"] == "batch"
            else "those certificates say \"Verification: not performed.\"")
    if p["site"]:
        msg += "\nAdded to the verify list%s." % (" and marked job %s ready" % p["job"] if p["job"] else "")
    return msg, out, used


# ------------------------------------------------------------------ window
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("EndByte Desk")
        self.minsize(860, 640)
        self.s = load_settings()
        self.site = tk.StringVar(value=self.s.get("site", ""))
        self.pending = set(self.s.get("pending_upload", []))
        self.last_dir = self.s.get("last_dir", os.path.expanduser("~"))

        style = ttk.Style(self)
        style.configure("Big.TLabel", font=("Menlo", 20, "bold"))
        style.configure("Head.TLabel", font=("Helvetica", 13, "bold"))

        self.build_topbar()
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.tab_certs = ttk.Frame(nb, padding=10)
        self.tab_jobs = ttk.Frame(nb, padding=10)
        self.tab_verify = ttk.Frame(nb, padding=10)
        nb.add(self.tab_certs, text="  Make certificates  ")
        nb.add(self.tab_jobs, text="  Jobs  ")
        nb.add(self.tab_verify, text="  Verify list  ")
        self.nb = nb
        self.build_certs()
        self.build_jobs()
        self.build_verify()
        self.refresh_all()

    # ============================================================ top bar
    def build_topbar(self):
        bar = ttk.Frame(self, padding=(12, 10, 12, 6))
        bar.pack(fill="x")
        self.bar = bar
        ttk.Label(bar, text="Website folder:").pack(side="left")
        self.site_lbl = ttk.Label(bar, text="", foreground=GREY)
        self.site_lbl.pack(side="left", padx=(6, 8))
        ttk.Button(bar, text="Choose…", command=self.pick_site).pack(side="left")

        self.upbar = tk.Frame(self, bg="#fff4d6", highlightthickness=1, highlightbackground="#e8c46a")
        self.up_lbl = tk.Label(self.upbar, text="", bg="#fff4d6", fg="#5a4200", anchor="w", justify="left")
        self.up_lbl.pack(side="left", padx=10, pady=6, fill="x", expand=True)
        ttk.Button(self.upbar, text="I've uploaded them", command=self.clear_pending).pack(side="right", padx=(4, 10), pady=4)
        ttk.Button(self.upbar, text="Open website folder", command=lambda: self.site.get() and open_path(self.site.get())).pack(side="right", pady=4)

    def pick_site(self):
        d = filedialog.askdirectory(title="Choose your website folder (EndByte-main)", initialdir=self.site.get() or self.last_dir)
        if not d:
            return
        if not os.path.exists(os.path.join(d, "verify.html")):
            messagebox.showwarning("EndByte Desk", "That doesn't look like the website folder — it should contain verify.html and track.html.")
            return
        self.site.set(d)
        self.save()
        self.refresh_all()

    def mark_pending(self, *files):
        self.pending.update(files)
        self.save()
        self.refresh_topbar()

    def clear_pending(self):
        self.pending.clear()
        self.save()
        self.refresh_topbar()

    def refresh_topbar(self):
        site = self.site.get()
        self.site_lbl.config(text=site or "not set — choose your EndByte-main folder so jobs and the verify list work",
                             foreground=GREY if site else RED)
        if self.pending:
            files = ", ".join(sorted(self.pending))
            self.up_lbl.config(text="Changed: %s  —  upload %s to GitHub so customers see the update."
                                    % (files, "these" if len(self.pending) > 1 else "it"))
            self.upbar.pack(fill="x", padx=10, pady=(0, 8), after=self.bar)
        else:
            self.upbar.pack_forget()

    def save(self):
        self.s.update({"site": self.site.get(), "pending_upload": sorted(self.pending), "last_dir": self.last_dir})
        save_settings(self.s)

    def need_site(self):
        if not self.site.get() or not os.path.isdir(self.site.get()):
            messagebox.showwarning("EndByte Desk", "Choose your website folder (EndByte-main) at the top first.")
            return False
        return True

    def refresh_all(self):
        self.refresh_topbar()
        self.refresh_jobs()
        self.refresh_verify()

    # ============================================================ tab 1: certificates
    def build_certs(self):
        f = self.tab_certs
        f.columnconfigure(1, weight=1)
        self.cv = {
            "folder": tk.StringVar(), "out": tk.StringVar(),
            "mode": tk.StringVar(value=self.s.get("mode", "batch")),
            "number": tk.StringVar(value=self.s.get("next_number", "CD-2800")),
            "client": tk.StringVar(), "job": tk.StringVar(),
            "operator": tk.StringVar(value=self.s.get("operator", make_batch_cert.DEFAULTS["operator"])),
            "disposition": tk.StringVar(value=self.s.get("disposition", make_batch_cert.DEFAULTS["disposition"])),
            "disposition_failed": tk.StringVar(value=self.s.get("disposition_failed", make_batch_cert.DEFAULTS["disposition_failed"])),
            "publish": tk.BooleanVar(value=self.s.get("publish", True)),
        }
        pad = {"padx": (4, 12), "pady": 5}
        r = 0
        ttk.Label(f, text="Reports folder").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(f, textvariable=self.cv["folder"]).grid(row=r, column=1, sticky="ew", pady=5)
        ttk.Button(f, text="Choose…", command=self.pick_reports).grid(row=r, column=2, padx=(6, 0))
        r += 1
        self.found = ttk.Label(f, text="Pick the folder with this job's KillDisk XML reports.", foreground=GREY)
        self.found.grid(row=r, column=1, columnspan=2, sticky="w", pady=(0, 6))
        r += 1
        ttk.Label(f, text="Certificate type").grid(row=r, column=0, sticky="nw", **pad)
        m = ttk.Frame(f); m.grid(row=r, column=1, columnspan=2, sticky="w")
        ttk.Radiobutton(m, text="Batch — one PDF for the whole job", value="batch", variable=self.cv["mode"]).pack(anchor="w")
        ttk.Radiobutton(m, text="Single — one PDF per drive", value="single", variable=self.cv["mode"]).pack(anchor="w")
        r += 1
        self.number_lbl = ttk.Label(f, text="Certificate number")
        self.number_lbl.grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(f, textvariable=self.cv["number"], width=16).grid(row=r, column=1, sticky="w", pady=5)
        self.cv["mode"].trace_add("write", lambda *_: self.number_lbl.config(
            text="Certificate number" if self.cv["mode"].get() == "batch" else "First certificate number"))
        r += 1
        ttk.Label(f, text="Client").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(f, textvariable=self.cv["client"]).grid(row=r, column=1, columnspan=2, sticky="ew", pady=5)
        r += 1
        ttk.Label(f, text="Job code").grid(row=r, column=0, sticky="w", **pad)
        jr = ttk.Frame(f); jr.grid(row=r, column=1, columnspan=2, sticky="w")
        self.job_combo = ttk.Combobox(jr, textvariable=self.cv["job"], width=18)
        self.job_combo.pack(side="left")
        ttk.Label(jr, text="  optional — pick the job and it's marked \"Certificate ready\" automatically",
                  foreground=GREY).pack(side="left")
        r += 1
        ttk.Separator(f).grid(row=r, column=0, columnspan=3, sticky="ew", pady=10)
        r += 1
        ttk.Label(f, text="Erased drives went to").grid(row=r, column=0, sticky="w", **pad)
        ttk.Combobox(f, textvariable=self.cv["disposition"], width=32,
                     values=["Retained · resale", "Returned to client", "Recycled", "Shredded"]).grid(row=r, column=1, sticky="w", pady=5)
        r += 1
        ttk.Label(f, text="Failed drives went to").grid(row=r, column=0, sticky="w", **pad)
        ttk.Combobox(f, textvariable=self.cv["disposition_failed"], width=32,
                     values=["Shredded", "Physically destroyed (shredded)", "Returned to client", "Pending destruction"]).grid(row=r, column=1, sticky="w", pady=5)
        r += 1
        ttk.Label(f, text="Operator").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(f, textvariable=self.cv["operator"], width=22).grid(row=r, column=1, sticky="w", pady=5)
        r += 1
        ttk.Label(f, text="Save PDFs to").grid(row=r, column=0, sticky="w", **pad)
        ttk.Entry(f, textvariable=self.cv["out"]).grid(row=r, column=1, sticky="ew", pady=5)
        ttk.Button(f, text="Choose…", command=self.pick_out).grid(row=r, column=2, padx=(6, 0))
        r += 1
        ttk.Label(f, text="Leave blank to save into the reports folder.", foreground=GREY).grid(row=r, column=1, sticky="w")
        r += 1
        ttk.Checkbutton(f, text="Add to the website's verify list (needs the website folder at the top)",
                        variable=self.cv["publish"]).grid(row=r, column=1, columnspan=2, sticky="w", pady=(10, 0))
        r += 1
        self.go = ttk.Button(f, text="Make Certificates", command=self.make)
        self.go.grid(row=r, column=0, columnspan=3, pady=(14, 4))
        r += 1
        self.cstatus = ttk.Label(f, text="", foreground=GREY, wraplength=760, justify="left")
        self.cstatus.grid(row=r, column=0, columnspan=3, sticky="w", pady=(4, 0))

    def pick_reports(self):
        d = filedialog.askdirectory(title="Choose the folder with the KillDisk reports", initialdir=self.last_dir)
        if not d:
            return
        self.cv["folder"].set(d)
        self.last_dir = os.path.dirname(d); self.save()
        try:
            drives = killdisk_reports.collect([d])
        except Exception:
            drives = []
        if not drives:
            self.found.config(text="No KillDisk XML reports found in that folder.", foreground=RED)
            return
        v = sum(1 for x in drives if x["status"] == "PASS")
        e = sum(1 for x in drives if x["status"] == "ERASED")
        fl = sum(1 for x in drives if x["status"] == "FAIL")
        self.found.config(text="Found %d drive%s:  %d verified · %d erased, not verified · %d failed" %
                          (len(drives), "" if len(drives) == 1 else "s", v, e, fl), foreground=GREEN)

    def pick_out(self):
        d = filedialog.askdirectory(title="Where should the PDFs go?", initialdir=self.cv["folder"].get() or self.last_dir)
        if d:
            self.cv["out"].set(d)

    def make(self):
        p = {k: v.get() for k, v in self.cv.items()}
        p = {k: (v.strip() if isinstance(v, str) else v) for k, v in p.items()}
        p["job"] = p["job"].split()[0].upper() if p["job"] else ""
        if not p["folder"] or not os.path.isdir(p["folder"]):
            messagebox.showwarning("EndByte Desk", "Choose the folder with the KillDisk reports first.")
            return
        if not re.match(r"^[A-Za-z]{1,6}-?\d+$", p["number"]):
            messagebox.showwarning("EndByte Desk", "Enter a certificate number like CD-2800.")
            return
        p["site"] = self.site.get() if (p["publish"] and self.site.get()) else ""
        if p["publish"] and not p["site"]:
            if not messagebox.askyesno("EndByte Desk", "The website folder isn't set, so these certificates won't be "
                                       "added to the verify list. Make them anyway?"):
                return
        if p["job"] and p["site"] and p["job"] not in site_data.Jobs(p["site"]).all():
            if not messagebox.askyesno("EndByte Desk", "Job %s isn't in your job list, so no tracking page will be "
                                       "updated. Continue?" % p["job"]):
                return
        self.go.config(state="disabled")
        self.cstatus.config(text="Working…", foreground=GREY)

        def work():
            try:
                res = run_job(p)
                self.after(0, lambda: self.made(p, *res))
            except Exception as e:
                err = str(e) or traceback.format_exc(limit=1)
                self.after(0, lambda: self.make_failed(err))
        threading.Thread(target=work, daemon=True).start()

    def made(self, p, msg, out, used):
        self.go.config(state="normal")
        nxt = bump(p["number"], used)
        self.cv["number"].set(nxt)
        self.s.update({"next_number": nxt, "mode": p["mode"], "operator": p["operator"],
                       "disposition": p["disposition"], "disposition_failed": p["disposition_failed"],
                       "publish": p["publish"]})
        if p["site"]:
            self.mark_pending("certificates.json", *(["jobs.json"] if p["job"] else []))
        else:
            self.save()
        self.refresh_jobs(); self.refresh_verify()
        self.cstatus.config(text=msg + "\nNext certificate number: " + nxt, foreground=GREEN)
        open_path(out)

    def make_failed(self, err):
        self.go.config(state="normal")
        self.cstatus.config(text="Something went wrong: " + err, foreground=RED)

    # ============================================================ tab 2: jobs
    def build_jobs(self):
        f = self.tab_jobs
        f.columnconfigure(0, weight=3); f.columnconfigure(1, weight=2); f.rowconfigure(1, weight=1)

        top = ttk.Frame(f); top.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Label(top, text="New job:").pack(side="left")
        ttk.Label(top, text="drives").pack(side="left", padx=(10, 4))
        self.new_drives = tk.StringVar()
        ttk.Entry(top, textvariable=self.new_drives, width=6).pack(side="left")
        ttk.Button(top, text="Create job code", command=self.create_job).pack(side="left", padx=8)
        ttk.Label(top, text="Give the code to the customer at pickup or drop-off.", foreground=GREY).pack(side="left", padx=6)

        cols = ("code", "stage", "drives", "updated", "cert")
        tv = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse", height=14)
        for c, t, w in (("code", "Job code", 130), ("stage", "Stage", 130), ("drives", "Drives", 60),
                        ("updated", "Updated", 95), ("cert", "Certificate", 110)):
            tv.heading(c, text=t); tv.column(c, width=w, anchor="w")
        tv.grid(row=1, column=0, sticky="nsew")
        tv.bind("<<TreeviewSelect>>", lambda e: self.show_job())
        self.jobs_tv = tv

        d = ttk.Frame(f, padding=(16, 0, 0, 0)); d.grid(row=1, column=1, sticky="nsew")
        d.columnconfigure(0, weight=1)
        self.jd_code = ttk.Label(d, text="Select a job", style="Big.TLabel")
        self.jd_code.grid(row=0, column=0, sticky="w")
        cb = ttk.Frame(d); cb.grid(row=1, column=0, sticky="w", pady=(4, 10))
        ttk.Button(cb, text="Copy code", command=lambda: self.copy(self.cur_job())).pack(side="left")
        ttk.Button(cb, text="Copy tracking link", command=lambda: self.cur_job() and self.copy(site_data.TRACK_URL + self.cur_job())).pack(side="left", padx=6)
        ttk.Button(cb, text="Open", command=lambda: self.cur_job() and webbrowser.open(site_data.TRACK_URL + self.cur_job())).pack(side="left")

        ttk.Label(d, text="Stage", style="Head.TLabel").grid(row=2, column=0, sticky="w")
        self.jd_stage = tk.StringVar()
        sf = ttk.Frame(d); sf.grid(row=3, column=0, sticky="w", pady=(2, 10))
        for st in STAGES:
            ttk.Radiobutton(sf, text=STAGE_LABELS[st], value=st, variable=self.jd_stage,
                            command=self.set_stage).pack(anchor="w")
        self.jd_hist = ttk.Label(d, text="", foreground=GREY, justify="left")
        self.jd_hist.grid(row=4, column=0, sticky="w", pady=(0, 10))

        dr = ttk.Frame(d); dr.grid(row=5, column=0, sticky="w")
        ttk.Label(dr, text="Drives").pack(side="left")
        self.jd_drives = tk.StringVar()
        ttk.Entry(dr, textvariable=self.jd_drives, width=6).pack(side="left", padx=6)

        ttk.Label(d, text="Note the customer will see (optional)", style="Head.TLabel").grid(row=6, column=0, sticky="w", pady=(12, 2))
        self.jd_note = tk.Text(d, height=4, width=34, wrap="word", font=("Helvetica", 12))
        self.jd_note.grid(row=7, column=0, sticky="ew")
        ttk.Label(d, text="Public — no names or serial numbers.", foreground=GREY).grid(row=8, column=0, sticky="w")
        bb = ttk.Frame(d); bb.grid(row=9, column=0, sticky="w", pady=(8, 0))
        ttk.Button(bb, text="Save drives & note", command=self.save_job_details).pack(side="left")
        ttk.Button(bb, text="Remove job", command=self.remove_job).pack(side="left", padx=8)
        self.jd_certs = ttk.Label(d, text="", foreground=GREEN)
        self.jd_certs.grid(row=10, column=0, sticky="w", pady=(10, 0))
        self.jobs_status = ttk.Label(f, text="", foreground=GREY)
        self.jobs_status.grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def jobs(self):
        return site_data.Jobs(self.site.get()) if self.site.get() else None

    def cur_job(self):
        sel = self.jobs_tv.selection()
        return sel[0] if sel else ""

    def refresh_jobs(self, keep=None):
        tv = self.jobs_tv
        keep = keep or self.cur_job()
        tv.delete(*tv.get_children())
        J = self.jobs()
        data = J.all() if J else {}
        order = sorted(data.items(), key=lambda kv: (kv[1].get("stage") == "ready", kv[1].get("updated", "")), reverse=False)
        order = sorted(order, key=lambda kv: kv[1].get("updated", ""), reverse=True)
        order = sorted(order, key=lambda kv: kv[1].get("stage") == "ready")
        for code, j in order:
            tv.insert("", "end", iid=code, values=(code + ("  (demo)" if j.get("demo") else ""),
                                                   STAGE_LABELS.get(j.get("stage"), j.get("stage")),
                                                   j.get("drives") or "", j.get("updated", ""),
                                                   ", ".join(j.get("certificates", []))))
        open_codes = ["%s  (%s drives)" % (c, j.get("drives") or "?") for c, j in order if j.get("stage") != "ready"]
        self.job_combo.config(values=[""] + open_codes)
        if keep and keep in data:
            tv.selection_set(keep); tv.see(keep)
            self.show_job()
        else:
            self.show_job()
        n_open = sum(1 for _, j in order if j.get("stage") != "ready")
        self.jobs_status.config(text=("%d job%s · %d in progress" % (len(order), "" if len(order) == 1 else "s", n_open))
                                if J else "Choose your website folder at the top to see jobs.")

    def show_job(self):
        code = self.cur_job()
        J = self.jobs()
        j = J.all().get(code) if (J and code) else None
        if not j:
            self.jd_code.config(text="Select a job"); self.jd_stage.set(""); self.jd_hist.config(text="")
            self.jd_drives.set(""); self.jd_note.delete("1.0", "end"); self.jd_certs.config(text="")
            return
        self.jd_code.config(text=code)
        self.jd_stage.set(j.get("stage", "received"))
        h = j.get("history", {})
        self.jd_hist.config(text="\n".join("%-18s %s" % (STAGE_LABELS[s] + ":", h[s]) for s in STAGES if s in h))
        self.jd_drives.set(str(j.get("drives") or ""))
        self.jd_note.delete("1.0", "end"); self.jd_note.insert("1.0", j.get("note", ""))
        certs = j.get("certificates", [])
        self.jd_certs.config(text=("Certificate: " + ", ".join(certs)) if certs else "")

    def create_job(self):
        if not self.need_site():
            return
        drives = self.new_drives.get().strip()
        if drives and not drives.isdigit():
            messagebox.showwarning("EndByte Desk", "Drives should be a number (or leave it blank).")
            return
        code = self.jobs().new(int(drives or 0))
        self.new_drives.set("")
        self.mark_pending("jobs.json")
        self.refresh_jobs(keep=code)
        self.copy(code)
        messagebox.showinfo("EndByte Desk", "New job created:\n\n%s\n\nIt's copied to your clipboard. Give this code to the "
                                            "customer — they can track it at endbyte.net/track.html once you upload jobs.json." % code)

    def set_stage(self):
        code = self.cur_job()
        if not code or not self.need_site():
            return
        self.jobs().set_stage(code, self.jd_stage.get())
        self.mark_pending("jobs.json")
        self.refresh_jobs(keep=code)

    def save_job_details(self):
        code = self.cur_job()
        if not code or not self.need_site():
            return
        drives = self.jd_drives.get().strip()
        if drives and not drives.isdigit():
            messagebox.showwarning("EndByte Desk", "Drives should be a number.")
            return
        self.jobs().update(code, drives=int(drives or 0), note=self.jd_note.get("1.0", "end"))
        self.mark_pending("jobs.json")
        self.refresh_jobs(keep=code)
        self.jobs_status.config(text="Saved %s." % code)

    def remove_job(self):
        code = self.cur_job()
        if not code or not self.need_site():
            return
        if messagebox.askyesno("EndByte Desk", "Remove job %s from the tracking page?" % code):
            self.jobs().remove(code)
            self.mark_pending("jobs.json")
            self.refresh_jobs()

    def copy(self, text):
        if not text:
            return
        self.clipboard_clear(); self.clipboard_append(text)
        self.jobs_status.config(text="Copied: " + text)

    # ============================================================ tab 3: verify list
    def build_verify(self):
        f = self.tab_verify
        f.columnconfigure(0, weight=1); f.rowconfigure(1, weight=1)
        ttk.Label(f, text="Certificates customers can look up at endbyte.net/verify.html. New ones are added "
                          "automatically when you make certificates.", foreground=GREY).grid(row=0, column=0, sticky="w", pady=(0, 8))
        cols = ("num", "issued", "method", "drives", "result")
        tv = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse", height=16)
        for c, t, w in (("num", "Number", 100), ("issued", "Issued", 95), ("method", "Method", 220),
                        ("drives", "Drives", 60), ("result", "Result", 260)):
            tv.heading(c, text=t); tv.column(c, width=w, anchor="w")
        tv.grid(row=1, column=0, sticky="nsew")
        self.ver_tv = tv
        b = ttk.Frame(f); b.grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Button(b, text="Add an older certificate…", command=self.add_cert).pack(side="left")
        ttk.Button(b, text="Open on website", command=self.open_cert).pack(side="left", padx=8)
        ttk.Button(b, text="Remove", command=self.remove_cert).pack(side="left")
        self.ver_status = ttk.Label(f, text="", foreground=GREY)
        self.ver_status.grid(row=3, column=0, sticky="w", pady=(6, 0))

    def refresh_verify(self):
        tv = self.ver_tv
        tv.delete(*tv.get_children())
        if not self.site.get():
            self.ver_status.config(text="Choose your website folder at the top to see the verify list.")
            return
        data = site_data.Certificates(self.site.get()).all()
        for num, c in sorted(data.items(), key=lambda kv: kv[1].get("issued", ""), reverse=True):
            tv.insert("", "end", iid=num, values=(num + ("  (sample)" if c.get("sample") else ""), c.get("issued", ""),
                                                  c.get("method", ""), c.get("drives", ""), c.get("result", "")))
        self.ver_status.config(text="%d certificate%s on the verify list." % (len(data), "" if len(data) == 1 else "s"))

    def add_cert(self):
        if not self.need_site():
            return
        dlg = CertDialog(self)
        self.wait_window(dlg)
        if dlg.result:
            site_data.Certificates(self.site.get()).put(*dlg.result)
            self.mark_pending("certificates.json")
            self.refresh_verify()

    def open_cert(self):
        sel = self.ver_tv.selection()
        if sel:
            webbrowser.open("https://www.endbyte.net/verify.html?id=" + sel[0])

    def remove_cert(self):
        sel = self.ver_tv.selection()
        if not sel or not self.need_site():
            return
        if messagebox.askyesno("EndByte Desk", "Remove %s from the verify list? Anyone checking it will get \"no match\"." % sel[0]):
            site_data.Certificates(self.site.get()).remove(sel[0])
            self.mark_pending("certificates.json")
            self.refresh_verify()


class CertDialog(tk.Toplevel):
    """Small form for adding a certificate that was made before the app existed."""
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Add a certificate to the verify list")
        self.resizable(False, False)
        self.result = None
        self.vars = {k: tk.StringVar() for k in ("number", "issued", "method", "drives", "result")}
        self.vars["issued"].set(site_data.today())
        self.vars["method"].set("NIST 800-88 Clear")
        self.vars["drives"].set("1")
        self.vars["result"].set("PASS · erased and verified")
        f = ttk.Frame(self, padding=14); f.pack()
        rows = [("Certificate number", "number", 16), ("Issued (YYYY-MM-DD)", "issued", 14), ("Method", "method", 32),
                ("Drives", "drives", 6), ("Result", "result", 32)]
        for i, (lbl, k, w) in enumerate(rows):
            ttk.Label(f, text=lbl).grid(row=i, column=0, sticky="w", padx=(0, 10), pady=4)
            ttk.Entry(f, textvariable=self.vars[k], width=w).grid(row=i, column=1, sticky="w", pady=4)
        ttk.Label(f, text="Public — don't include client names or serial numbers.", foreground=GREY).grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))
        b = ttk.Frame(f); b.grid(row=6, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(b, text="Cancel", command=self.destroy).pack(side="left", padx=4)
        ttk.Button(b, text="Add", command=self.ok).pack(side="left", padx=4)
        self.transient(parent); self.grab_set()

    def ok(self):
        v = {k: x.get().strip() for k, x in self.vars.items()}
        if not re.match(r"^[A-Za-z]{2,4}-\d{3,8}$", v["number"]):
            messagebox.showwarning("EndByte Desk", "Use a number like CD-2743.", parent=self); return
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v["issued"]):
            messagebox.showwarning("EndByte Desk", "Use a date like 2026-09-29.", parent=self); return
        if not v["drives"].isdigit():
            messagebox.showwarning("EndByte Desk", "Drives should be a number.", parent=self); return
        self.result = (v["number"], v["issued"], v["method"], int(v["drives"]), v["result"])
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
