#!/usr/bin/env python3
"""
EndByte site builder.

Run from anywhere:   python3 _build/build.py

What it does (in place, safe to run repeatedly):
  1. Injects the shared header (status bar + nav) and footer from _build/partials/
     into every page, between the <!-- @header --> / <!-- @end header --> and
     <!-- @footer --> / <!-- @end footer --> markers. Edit the partials, not the pages.
     {{R}} in a partial becomes the page's path back to the site root
     ("" for root pages, "../" for services/ and areas/, "/" for 404.html).
  2. Cache-busts styles.css and main.js (?v=<content hash>) on every page.
  3. Regenerates the FAQPage structured data on index.html from the FAQ section.
  4. Regenerates sitemap.xml from the pages on disk.

Certificates for verify.html: python3 _build/add_cert.py --help

The _build/ folder is ignored by GitHub Pages (folders starting with "_" aren't published).
"""
import hashlib, html, json, os, re, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://www.endbyte.net"
PARTIALS = os.path.join(ROOT, "_build", "partials")
NO_SITEMAP = {"404.html", "services/onsite-destruction.html"}  # pages kept out of sitemap.xml

def read(p):
    with open(p, encoding="utf-8") as f: return f.read()

def write(p, s):
    with open(p, "w", encoding="utf-8") as f: f.write(s)

def pages():
    out = []
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if not d.startswith((".", "_"))]
        for fn in files:
            if fn.endswith(".html"):
                out.append(os.path.relpath(os.path.join(dirpath, fn), ROOT).replace(os.sep, "/"))
    return sorted(out)

def prefix(rel):
    if rel == "404.html": return "/"
    return "../" * rel.count("/")

def short_hash(name):
    return hashlib.sha1(open(os.path.join(ROOT, name), "rb").read()).hexdigest()[:8]

def inject(src, name, body):
    pat = re.compile(r"<!-- @%s -->.*?<!-- @end %s -->" % (name, name), re.S)
    if not pat.search(src):
        raise SystemExit("missing <!-- @%s --> markers" % name)
    return pat.sub(lambda m: "<!-- @%s -->\n%s<!-- @end %s -->" % (name, body, name), src)

def strip_tags(s):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s))).strip()

def faq_schema(src):
    qs = re.findall(r'<button class="faq-q"[^>]*>(.*?)<span class="faq-pm">.*?<div class="faq-a">(.*?)</div>\s*</div>', src, re.S)
    data = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": strip_tags(q),
         "acceptedAnswer": {"@type": "Answer", "text": strip_tags(a)}} for q, a in qs]}
    block = '<script type="application/ld+json" id="faq-schema">\n%s\n</script>' % json.dumps(data, indent=2, ensure_ascii=False)
    pat = re.compile(r'<script type="application/ld\+json" id="faq-schema">.*?</script>', re.S)
    return (pat.sub(lambda m: block, src) if pat.search(src) else src.replace("</head>", block + "\n</head>", 1)), len(qs)

def sitemap(all_pages):
    def prio(p):
        if p == "index.html": return "1.0"
        if p.startswith("services/"): return "0.8"
        if p.startswith("industries/") or p == "trust.html": return "0.8"
        if p.startswith(("areas/", "guides/")) or p == "estimate.html": return "0.7"
        if p == "privacy.html": return "0.3"
        return "0.6"
    rows = []
    for p in all_pages:
        if p in NO_SITEMAP: continue
        loc = SITE + "/" + ("" if p == "index.html" else p)
        mod = datetime.date.fromtimestamp(os.path.getmtime(os.path.join(ROOT, p))).isoformat()
        rows.append("  <url>\n    <loc>%s</loc>\n    <lastmod>%s</lastmod>\n    <priority>%s</priority>\n  </url>" % (loc, mod, prio(p)))
    write(os.path.join(ROOT, "sitemap.xml"),
          '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s\n</urlset>\n' % "\n".join(rows))
    return len(rows)

def main():
    header = read(os.path.join(PARTIALS, "header.html"))
    footer = read(os.path.join(PARTIALS, "footer.html"))
    css_v, js_v = short_hash("styles.css"), short_hash("main.js")
    all_pages = pages()
    for rel in all_pages:
        path = os.path.join(ROOT, rel)
        src = orig = read(path)
        R = prefix(rel)
        src = inject(src, "header", header.replace("{{R}}", R))
        src = inject(src, "footer", footer.replace("{{R}}", R))
        src = re.sub(r'styles\.css(\?v=[\w-]*)?"', 'styles.css?v=%s"' % css_v, src)
        src = re.sub(r'main\.js(\?v=[\w-]*)?"', 'main.js?v=%s"' % js_v, src)
        if rel == "index.html":
            src, n = faq_schema(src)
            print("  FAQ schema: %d questions" % n)
        if src != orig:
            write(path, src)
            print("  updated", rel)
    print("  sitemap: %d urls" % sitemap(all_pages))
    print("done — %d pages" % len(all_pages))

if __name__ == "__main__":
    main()
