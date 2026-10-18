#!/usr/bin/env python3
"""Download and keep local copies of every source in the register.

    python3 tools/archive.py

For each record in data/records.json this script:

  1. downloads the official URL (checking robots.txt first),
  2. if that is an HTML page, also downloads up to N PDFs it links to on the
     same official site (usually the legal text itself),
  3. downloads the secondary URL as a backup,
  4. stores every file under archive/<ID>/<YYYY-MM-DD>/ with a SHA-256 hash,
     the UTC retrieval time, the final URL after redirects and the HTTP status,
  5. writes the result into the record's "local_copy" block and flags anything
     that did not work (HTTP errors, timeouts, robots.txt blocks, bot-check or
     JavaScript-only pages, pages that no longer mention the document),
  6. regenerates data/records.js, data/records.csv and data/register.sqlite,
  7. writes archive/needs-attention.txt, the list of records that still need a
     human decision. The archiver never contacts anyone; what to do about a
     flagged record is left to the person running it.

Re-running is safe. Unchanged files are not stored twice; a changed source is
saved as a new dated snapshot and the record is marked "changed". If a source
that was archived before now fails, the earlier copy is kept and the record is
flagged for review.

Other modes:
  --run RUN_ID      store the sources of a pipeline run (AGENTS.md section 5.3): every active
                    candidate's URL and every extra_urls entry its extraction or check asked for,
                    under archive/_runs/<RUN_ID>/<cand-id>/; refresh candidates are archived as
                    their records. The stored files are listed in runs/<RUN_ID>/sources.json.
  --verify          re-hash every local file and flag missing or modified ones
  --dry-run         list what would be fetched, download nothing
  --browser         retry failed or suspicious pages in headless Chromium
                    (needs: pip install playwright && playwright install chromium)

Standard library only (Python 3.8+), except the optional --browser mode.
"""
import argparse
import concurrent.futures
import copy
import datetime as dt
import gzip
import hashlib
import html
import ipaddress
import json
import re
import socket
import ssl
import sys
import textwrap
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import zlib
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402  (same folder)

TOOL_VERSION = "1.0"
AGENT_TOKEN = "AISafetyPolicyRegister-Archiver"
ROOT = build.ROOT
ARCHIVE = ROOT / "archive"
ATTENTION_FILE = ARCHIVE / "needs-attention.txt"

ROLE_LABELS = {
    "official": "Official source",
    "document": "Linked document (PDF)",
    "secondary": "Secondary source",
    "official-rendered": "Official source, rendered in a browser",
    "official-print": "Official source, printed to PDF by a browser",
    "provided": "Official source, a copy provided by a person because the site does not allow automated downloads",
}

BOT_PATTERNS = [
    (r"just a moment|checking your browser|cf-browser-verification|cf_chl_|attention required! \| cloudflare",
     "The site returned a bot-check page instead of the document"),
    (r"captcha|are you a robot|are you human|verify you are human|unusual traffic",
     "The site returned a CAPTCHA or bot-check page"),
    (r"access denied|request unsuccessful|incapsula incident|request rejected|forbidden",
     "The site returned an access-denied page"),
    (r"incident id:|before proceeding|additional security check|verifying you are human|ddos protection",
     "The site returned a bot-check page instead of the document"),
    (r"enable javascript|javascript is (?:required|disabled|not enabled)|requires javascript|turn on javascript",
     "The page says it needs JavaScript; the saved copy may be empty"),
]

# Markers of JavaScript bot-check pages served by web application firewalls. They carry almost no
# visible text, so they are checked against the raw HTML.
WAF_PATTERN = re.compile(r"awswaf|gokuprops|challenge-platform|cf-challenge|/cdn-cgi/challenge|_incapsula_resource|"
                         r"datadome|px-captcha|distil_r_captcha|bm-verify|queue-it\.net|hcaptcha\.com|recaptcha/api", re.I)

# Single-page-application shells: the HTML carries a mount point and the content arrives by script.
APP_SHELL_PATTERN = re.compile(r"<app-root|\bng-app\b|ng-version=|id=\"root\"|id=\"app\"|id=\"__next\"|data-reactroot|__NEXT_DATA__|id=\"__nuxt\"", re.I)

STOPWORDS = set("""
the and for with from that this into under over about their which other these those such shall upon
act law laws rules rule order measures measure provisions provision regulation regulations decree
national general article annex part code policy guidelines guideline framework strategy plan report
artificial intelligence system systems
""".split())

GENERIC_SLD = {"co", "com", "org", "net", "ac", "edu", "or", "ne"}


# ----------------------------------------------------------------------------- helpers

def utcnow():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def rfc9309_rules(lines, agent):
    """The (allow, pattern) rules of robots.txt that apply to agent, read as RFC 9309 says: a group is the
    user-agent lines and the rules after them up to the next user-agent line (blank lines do not end it); the
    groups that name the agent's product token apply, or else the groups for '*'."""
    groups, agents, rules, in_rules = [], [], [], False
    for raw in lines:
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, val = (x.strip() for x in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if in_rules:
                groups.append((agents, rules))
                agents, rules, in_rules = [], [], False
            agents.append(val.lower())
        elif key in ("allow", "disallow") and agents:
            in_rules = True
            rules.append((key == "allow", val))
    if agents:
        groups.append((agents, rules))
    token = agent.lower()
    mine = [r for a, r in groups if any(x != "*" and token.startswith(x) for x in a)]
    return [rule for r in (mine or [r for a, r in groups if "*" in a]) for rule in r]


def rfc9309_allow(lines, agent, url):
    """RFC 9309 matching: the longest matching rule wins, Allow wins a tie, '*' matches any characters and a
    final '$' anchors the end; the path is matched with its query."""
    u = urllib.parse.urlsplit(url)
    path = (u.path or "/") + ("?" + u.query if u.query else "")
    best = None
    for allow, pat in rfc9309_rules(lines, agent):
        if not pat:
            continue  # an empty Disallow allows everything
        rx = "".join(".*" if c == "*" else re.escape(c) for c in (pat[:-1] if pat.endswith("$") else pat))
        if re.match(rx + ("$" if pat.endswith("$") else ""), path):
            if best is None or len(pat) > best[0] or (len(pat) == best[0] and allow):
                best = (len(pat), allow)
    return best is None or best[1]


def robots_allow(rp, url):
    """robots.txt allows the URL, and allows it when rules and path are compared without letter case. Many servers
    ignore case, so a rule for /TLODOCS/ also means /tlodocs/; this never allows more than the plain check."""
    if not rp.can_fetch(AGENT_TOKEN, url):
        return False
    lines = getattr(rp, "lines", None)
    if lines is not None and not (rfc9309_allow(lines, AGENT_TOKEN, url) and
                                  rfc9309_allow([x.lower() for x in lines], AGENT_TOKEN, url.lower())):
        return False  # robotparser ends a group at a blank line and ignores '*' and '$'; RFC 9309 does neither
    folded = getattr(rp, "folded", None)
    u = urllib.parse.urlsplit(url)
    return folded is None or folded.can_fetch(AGENT_TOKEN.lower(), urllib.parse.urlunsplit(u._replace(path=u.path.lower())))


def audit_robots(root=ROOT, out=None):
    """Read-only: every stored file (records' local copies and runs' sources) whose URL its site's robots.txt
    disallows when read as RFC 9309 says. Files stored before the archiver read robots.txt that way can be among
    them. Nothing is changed or deleted: robots.txt decides what the archiver downloads, not what the register keeps."""
    import glob
    import concurrent.futures as cf
    items = []
    for r in json.loads((root / "data" / "records.json").read_text(encoding="utf-8"))["records"]:
        for f in (r.get("local_copy") or {}).get("files") or []:
            for path in (f.get("path"), f.get("previous_path")):  # the earlier snapshot is kept and may be quoted
                if f.get("url") and path and (root / path).is_file():
                    items.append(("record", r["id"], path, f["url"]))
    for sj in sorted(glob.glob(str(root / "runs" / "*" / "sources.json"))):
        src = json.loads(Path(sj).read_text(encoding="utf-8"))
        for cid, e in src.items():
            lcs = [(e or {}).get("main")] + list(((e or {}).get("extras") or {}).values())
            for lc in lcs:
                for f in (lc or {}).get("files") or []:
                    for path in (f.get("path"), f.get("previous_path")):
                        if f.get("url") and path and (root / path).is_file():
                            items.append(("run " + Path(sj).parent.name, cid, path, f["url"]))
    hosts = sorted({urllib.parse.urlsplit(u).netloc for _, _, _, u in items})
    ua = "%s/%s" % (AGENT_TOKEN, TOOL_VERSION)

    def fetch(h):
        try:
            req = urllib.request.Request("https://%s/robots.txt" % h, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=20) as resp:
                return h, resp.read().decode("utf-8", "replace").splitlines()
        except urllib.error.HTTPError as e:
            return h, [] if 400 <= e.code < 500 else None
        except Exception:
            return h, None
    with cf.ThreadPoolExecutor(8) as ex:
        robots = dict(ex.map(fetch, hosts))
    bad = [dict(zip(("where", "id", "path", "url"), it)) for it in items
           if robots.get(urllib.parse.urlsplit(it[3]).netloc) is not None
           and not (rfc9309_allow(robots[urllib.parse.urlsplit(it[3]).netloc], AGENT_TOKEN, it[3]) and
                    rfc9309_allow([x.lower() for x in robots[urllib.parse.urlsplit(it[3]).netloc]], AGENT_TOKEN, it[3].lower()))]
    unknown = sorted(h for h in hosts if robots.get(h) is None)
    for b in bad:
        print("%-28s %-10s %s" % (b["where"][:28], b["id"], b["url"]))
    print("%d stored file(s) checked on %d sites; %d entr%s disallowed by robots.txt (RFC 9309), %d distinct files; "
          "robots.txt not reachable now for %d site(s)." % (len(items), len(hosts), len(bad), "y" if len(bad) == 1 else "ies",
                                                            len({b["path"] for b in bad}), len(unknown)))
    if out:
        Path(out).write_text(json.dumps({"disallowed": bad, "robots_unreachable": unknown}, indent=1), encoding="utf-8")
    return 0


def iri_to_uri(url):
    """Percent-encode non-ASCII paths and IDNA-encode hosts so urllib accepts the URL."""
    p = urllib.parse.urlsplit(url.strip())
    host = p.hostname or ""
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        pass
    netloc = host + (":%d" % p.port if p.port else "")
    path = urllib.parse.quote(p.path or "/", safe="/%:@!$&'()*+,;=-._~")
    query = urllib.parse.quote(p.query, safe="=&%:@!$'()*+,;/?-._~")
    return urllib.parse.urlunsplit((p.scheme, netloc, path, query, ""))


def site_key(host):
    parts = (host or "").lower().split(".")
    if len(parts) >= 3 and parts[-2] in GENERIC_SLD:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def same_site(a, b):
    ka = site_key(urllib.parse.urlsplit(a).hostname or "")
    hb = (urllib.parse.urlsplit(b).hostname or "").lower()
    return hb == ka or hb.endswith("." + ka)


def ext_for(content_type, body, url):
    if body[:5] == b"%PDF-":
        return ".pdf"
    ct = (content_type or "").split(";")[0].strip().lower()
    table = {
        "text/html": ".html", "application/xhtml+xml": ".html", "application/pdf": ".pdf",
        "text/plain": ".txt", "application/xml": ".xml", "text/xml": ".xml", "application/json": ".json",
        "application/msword": ".doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    }
    if ct in table:
        return table[ct]
    suffix = Path(urllib.parse.urlsplit(url).path).suffix.lower()
    if suffix in {".html", ".htm", ".pdf", ".txt", ".xml", ".json", ".doc", ".docx"}:
        return ".html" if suffix == ".htm" else suffix
    if body.lstrip()[:15].lower().startswith((b"<!doctype html", b"<html")):
        return ".html"
    return ".bin"


def decode_html(body, content_type):
    m = re.search(r"charset=([\w\-]+)", content_type or "", re.I)
    enc = m.group(1) if m else None
    if not enc:
        m = re.search(rb"<meta[^>]+charset=[\"']?([\w\-]+)", body[:4096], re.I)
        enc = m.group(1).decode("ascii", "ignore") if m else "utf-8"
    try:
        return body.decode(enc, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


class _TextAndLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text, self.links, self.title = [], [], ""
        self._skip = 0
        self._in_title = False
        self._a = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "noscript", "template"):
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "a" and a.get("href"):
            self._a = [a["href"], []]
        elif tag in ("iframe", "embed") and a.get("src"):
            self.links.append((a["src"], ""))
        elif tag == "object" and a.get("data"):
            self.links.append((a["data"], ""))
        elif tag == "link" and "pdf" in (a.get("type") or "") and a.get("href"):
            self.links.append((a["href"], "pdf"))

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "template") and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False
        elif tag == "a" and self._a:
            self.links.append((self._a[0], " ".join(self._a[1]).strip()))
            self._a = None

    def handle_data(self, data):
        if self._skip:
            return
        if self._in_title:
            self.title += data
        self.text.append(data)
        if self._a is not None:
            self._a[1].append(data.strip())


def parse_html(text):
    p = _TextAndLinks()
    try:
        p.feed(text)
        p.close()
    except Exception:  # malformed markup: keep what was parsed
        pass
    visible = re.sub(r"\s+", " ", " ".join(p.text)).strip()
    return visible, p.links, re.sub(r"\s+", " ", p.title).strip()


def words(s):
    return [w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(w) >= 4 and w not in STOPWORDS]


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def text_digest(body, content_type):
    """SHA-256 of the visible text of an HTML page, so that pages whose markup or scripts change on
    every request (session tokens, ads, timestamps in comments) are not stored again and again."""
    text, _, _ = parse_html(decode_html(body, content_type))
    text = re.sub(r"\b[0-9a-f]{8}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{12}\b|\b[0-9a-f]{16,}\b", "", text, flags=re.I)
    return sha256(re.sub(r"\s+", " ", text).strip().encode("utf-8"))


def describe_network_error(exc):
    """Turn a urllib/socket exception into (message, code) that says what actually went wrong."""
    reason = getattr(exc, "reason", exc)
    s = str(reason)
    if isinstance(reason, socket.gaierror) or "nodename nor servname" in s or "Name or service not known" in s \
            or "getaddrinfo" in s or "Temporary failure in name resolution" in s:
        return "DNS lookup failed, so the site could not be reached from this machine (try another network, or save the document by hand)", "dns"
    if isinstance(reason, (socket.timeout, TimeoutError)) or "timed out" in s:
        return "The connection timed out; the site may block this network", "timeout"
    if isinstance(reason, ssl.SSLCertVerificationError) or "CERTIFICATE_VERIFY_FAILED" in s:
        return "The site's TLS certificate could not be verified", "tls"
    if "refused" in s.lower():
        return "The connection was refused by the server", "network"
    return "Connection failed: %s" % s, "network"


# In pipeline run mode the archiver downloads URLs that agents supplied. It then fetches only public sites,
# so a page that misleads an agent cannot make the archiver read this machine or the local network.
PUBLIC_ONLY = False


def is_public_url(url):
    """False when the URL's host resolves to a loopback, private, link-local or otherwise non-public address."""
    host = urllib.parse.urlsplit(url).hostname
    if not host:
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except (socket.gaierror, UnicodeError):
        return True  # cannot resolve: the download fails on its own and is reported as a DNS error
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0].split("%")[0])
        except ValueError:
            return False
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    return True


class _Redirects(urllib.request.HTTPRedirectHandler):
    """Follow HTTP 308 like 307. Python before 3.11 treats 308 as an error."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if PUBLIC_ONLY and not is_public_url(newurl):
            raise urllib.error.HTTPError(newurl, code, "redirect to a local or private address refused", headers, fp)
        return super().redirect_request(req, fp, 307 if code == 308 else code, msg, headers, newurl)

    def http_error_308(self, req, fp, code, msg, headers):
        return self.http_error_307(req, fp, code, msg, headers)


# ----------------------------------------------------------------------------- fetching

class Result:
    def __init__(self, url, ok, status=None, final_url=None, headers=None, body=b"", error=None, code=None,
                 method="http", robots=False):
        self.url, self.ok, self.status, self.final_url = url, ok, status, final_url
        self.headers = headers or {}
        self.body, self.error, self.code, self.method = body, error, code, method
        self.robots = robots  # not attempted because of robots.txt (it disallows the URL, or could not be read)

    @property
    def content_type(self):
        return self.headers.get("content-type", "")

    @property
    def is_html(self):
        return ext_for(self.content_type, self.body, self.final_url or self.url) == ".html"

    @property
    def is_pdf(self):
        return self.body[:5] == b"%PDF-"


class TooLarge(Exception):
    pass


class Fetcher:
    def __init__(self, user_agent, timeout, retries, delay, max_bytes, respect_robots):
        self.ua, self.timeout, self.retries, self.delay = user_agent, timeout, retries, delay
        self.max_bytes, self.respect_robots = max_bytes, respect_robots
        self.host_locks = defaultdict(threading.Lock)
        self.last_hit = {}
        self.robots = {}
        self.robots_lock = threading.Lock()
        self.opener = urllib.request.build_opener(
            _Redirects(),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
            urllib.request.HTTPCookieProcessor(),
        )

    def _raw(self, url):
        req = urllib.request.Request(url, headers={
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
            "Accept-Language": "en;q=1.0, *;q=0.5",
            "Accept-Encoding": "gzip, deflate",
        })
        with self.opener.open(req, timeout=self.timeout) as resp:
            chunks, size = [], 0
            while True:
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                size += len(chunk)
                if size > self.max_bytes:
                    raise TooLarge()
                chunks.append(chunk)
            body = b"".join(chunks)
            headers = {k.lower(): v for k, v in resp.headers.items()}
            enc = headers.get("content-encoding", "").lower()
            if enc == "gzip":
                body = gzip.decompress(body)
            elif enc == "deflate":
                try:
                    body = zlib.decompress(body)
                except zlib.error:
                    body = zlib.decompress(body, -zlib.MAX_WBITS)
            return resp.status, resp.geturl(), headers, body

    def _robots_for(self, url):
        p = urllib.parse.urlsplit(url)
        base = "%s://%s" % (p.scheme, p.netloc)
        with self.robots_lock:
            if base in self.robots:
                return self.robots[base]
        rp = urllib.robotparser.RobotFileParser()
        note, code = None, "robots"
        with self.host_locks[p.netloc]:
            self._pace(p.netloc)
            try:
                status, _, _, body = self._raw(base + "/robots.txt")
                lines = body.decode("utf-8", errors="replace").splitlines() if status == 200 else []
                rp.parse(lines)
                rp.lines = lines  # read again by rfc9309_allow, which follows the standard where robotparser does not
                rp.folded = urllib.robotparser.RobotFileParser()  # the same rules in lower case (robots_allow)
                rp.folded.parse([x.lower() for x in lines])
            except urllib.error.HTTPError as e:
                if 400 <= e.code < 500:
                    rp.parse([])  # RFC 9309: robots.txt unavailable (4xx) means no restrictions
                    rp.lines = []
                else:
                    rp.parse(["User-agent: *", "Disallow: /"])
                    rp.lines = ["User-agent: *", "Disallow: /"]
                    note = "robots.txt returned HTTP %d, which RFC 9309 treats as 'do not crawl'" % e.code
            except Exception as e:  # unreachable
                rp.parse(["User-agent: *", "Disallow: /"])
                rp.lines = ["User-agent: *", "Disallow: /"]
                msg, code = describe_network_error(e)
                note = "%s. robots.txt could not be checked, which RFC 9309 treats as 'do not crawl'" % msg
            finally:
                self.last_hit[p.netloc] = time.monotonic()
        with self.robots_lock:
            self.robots[base] = (rp, note, code)
        return rp, note, code

    def _pace(self, host):
        wait = self.delay - (time.monotonic() - self.last_hit.get(host, 0))
        if wait > 0:
            time.sleep(wait)

    def get(self, url):
        try:
            url = iri_to_uri(url)
        except Exception as e:
            return Result(url, False, error="The URL is malformed (%s)" % e, code="bad-url")
        if not url.lower().startswith(("http://", "https://")):
            return Result(url, False, error="Not an http(s) URL", code="bad-url")
        if PUBLIC_ONLY and not is_public_url(url):
            return Result(url, False, error="Refused: the address is local or private, and pipeline runs fetch only public sites",
                          code="private-host")
        if self.respect_robots:
            rp, note, rcode = self._robots_for(url)
            if not robots_allow(rp, url):
                return Result(url, False, error=note or "The site's robots.txt does not allow automated downloads of this page",
                              code=rcode, robots=True)
        host = urllib.parse.urlsplit(url).netloc
        last_err = None
        for attempt in range(self.retries + 1):
            with self.host_locks[host]:
                self._pace(host)
                try:
                    status, final, headers, body = self._raw(url)
                    return Result(url, True, status, final, headers, body)
                except urllib.error.HTTPError as e:
                    msg = "HTTP %d %s" % (e.code, e.reason or "")
                    if e.code in (301, 302, 303, 307, 308):
                        msg = "HTTP %d redirect without a usable Location header; the site probably needs JavaScript or cookies" % e.code
                    last_err = Result(url, False, status=e.code, error=msg, code="http")
                    retry = e.code in (408, 425, 429, 500, 502, 503, 504)
                except TooLarge:
                    return Result(url, False, error="File is larger than the %d MB limit" % (self.max_bytes >> 20),
                                  code="too-large")
                except (socket.timeout, TimeoutError):
                    last_err = Result(url, False, error="Timed out after %ds" % self.timeout, code="timeout")
                    retry = True
                except (urllib.error.URLError, ConnectionError, ssl.SSLError, OSError) as e:
                    msg, code = describe_network_error(e)
                    if code == "tls":
                        return Result(url, False, error=msg, code=code)
                    if code == "timeout":
                        msg = "Timed out after %ds; the site may block this network" % self.timeout
                    last_err = Result(url, False, error=msg, code=code)
                    retry = code != "dns"
                finally:
                    self.last_hit[host] = time.monotonic()
            if not retry or attempt == self.retries:
                break
            time.sleep(3 * (attempt + 1) ** 2)
        return last_err


# ----------------------------------------------------------------------------- per-record work

def inspect_html(res, rec):
    """Return a list of warnings about an HTML page that downloaded with HTTP 200."""
    warnings = []
    text, _, title = parse_html(decode_html(res.body, res.content_type))
    low_title, low_text = title.lower(), text.lower()
    for pat, msg in BOT_PATTERNS:
        if re.search(pat, low_title) or (len(text) < 3000 and re.search(pat, low_text)):
            warnings.append(msg)
            break
    raw_head = decode_html(res.body[:300000], res.content_type) if len(text) < 2500 else ""
    if len(text) < 2500 and not warnings and APP_SHELL_PATTERN.search(raw_head) and not WAF_PATTERN.search(raw_head):
        warnings.append("The page is a JavaScript application shell; the saved copy holds only the site's navigation, not the document")
    if len(text) < 600 and not warnings:
        if WAF_PATTERN.search(raw_head):
            warnings.append("The site returned a JavaScript bot-check page (web application firewall) instead of the document")
        else:
            warnings.append("The page has very little readable text (%d characters); it probably needs JavaScript" % len(text))
    if not warnings:
        hay = low_text[:400000]
        best, checked = 0.0, False
        for cand in (rec.get("title"), rec.get("short_title")):
            ws = set(words(cand))
            if len(ws) >= 3:
                checked = True
                best = max(best, sum(1 for w in ws if w in hay) / len(ws))
        orig = (rec.get("original_title") or "").strip()
        if orig and orig[:10].lower() in hay:
            best = 1.0
        ident = rec.get("official_identifier") or ""
        nums = [n for n in re.findall(r"\d[\d/.\-]{2,}\d", ident) if len(n) >= 4]
        if any(n.lower() in hay for n in nums):
            best = 1.0
        if checked and best < 0.25:
            warnings.append("The page barely mentions the document's title; check that the URL still points to this document")
    return warnings, text


def pdf_candidates(res, rec, limit):
    if limit <= 0:
        return []
    _, links, _ = parse_html(decode_html(res.body, res.content_type))
    base = res.final_url or res.url
    title_words = set(words(rec.get("title")) + words(rec.get("short_title")))
    ident_nums = [n for n in re.findall(r"\d{3,}", rec.get("official_identifier") or "")]
    seen, scored = set(), []
    for pos, (href, text) in enumerate(links):
        href = (href or "").strip()
        if not href or href.startswith(("javascript:", "mailto:", "#", "tel:")):
            continue
        url = urllib.parse.urljoin(base, href).split("#")[0]
        if url in seen or not url.lower().startswith(("http://", "https://")):
            continue
        lu, lt = urllib.parse.unquote(url).lower(), (text or "").lower()
        path = urllib.parse.urlsplit(lu).path
        is_pdf = path.endswith(".pdf") or "/pdf/" in lu or re.search(r"[?&](format|type|rendition)=pdf", lu) \
            or "pdf" in lt
        if not is_pdf or not same_site(base, url):
            continue
        seen.add(url)
        score = (4 if path.endswith(".pdf") else 0) + (2 if "pdf" in lt else 0)
        hay = lu + " " + lt
        score += min(6, sum(1 for w in title_words if w in hay))
        if any(n in hay for n in ident_nums):
            score += 3
        if re.search(r"(^|[/_\-=.])en([/_\-.&]|$)", lu) or "english" in lt:
            score += 2
        if re.search(r"factsheet|fact-sheet|infographic|summary|press|brochure|poster", hay):
            score -= 2
        if re.search(r"accessib|certificat|veto[- ]message|signing[- ]message|privacy[- ]policy|terms", hay):
            continue  # site boilerplate or another bill's message, never the instrument
        if score <= 0:
            continue  # a PDF whose link says nothing about this document is more likely noise than the text
        scored.append((-score, pos, url))
    scored.sort()
    return [u for _, _, u in scored[:limit]]


class RecordJob:
    """Collects everything one record's run produced; finalise() turns it into local_copy."""

    def __init__(self, rec, run_date, run_time):
        self.rec = rec
        self.run_date, self.run_time = run_date, run_time
        prev = rec.get("local_copy") or {}
        self.prev_files = {f.get("role_key"): f for f in prev.get("files") or [] if f.get("role_key")}
        self.prev_attempts = prev.get("attempts") or []
        # copies a person provided (archive.py --provide) are never fetched again, so every run carries them over
        self.provided = [f for f in prev.get("files") or [] if f.get("role") == "provided"]
        self.files, self.attempts, self.notes = [], [], []
        self.official_ok = False
        self.official_warnings = []
        self.official_error = None
        self.unusable = None  # set when this run's download was a bot-check/empty page and an earlier clean copy is kept
        self.need_browser = False

    # -- storage
    def store(self, role_key, role, res, warning=None):
        # a new download replaces the earlier copy that keep_previous kept as stale for the same role (for example
        # after a failed plain download, when the browser retry stores the page again)
        self.files = [f for f in self.files if not (f.get("role_key") == role_key and f.get("stale"))]
        body = res.body
        digest = sha256(body)
        prev = self.prev_files.get(role_key)
        now = iso(utcnow())
        if prev and prev.get("sha256") == digest and (ROOT / prev.get("path", "")).is_file():
            f = dict(prev)
            f.update({"last_checked": now, "changed": False, "stale": False, "warning": warning,
                      "http_status": res.status, "final_url": res.final_url or res.url, "integrity": "ok"})
            self.files.append(f)
            return f
        ext = ext_for(res.content_type, body, res.final_url or res.url)
        tdigest = text_digest(body, res.content_type) if ext == ".html" else None
        if prev and tdigest and (ROOT / prev.get("path", "")).is_file() and prev.get("path", "").endswith(".html"):
            prev_td = prev.get("text_sha256") or text_digest((ROOT / prev["path"]).read_bytes(),
                                                               prev.get("content_type") or "text/html")
            if prev_td == tdigest:
                # Only markup or scripts differ; the readable content is the same, so keep the earlier copy.
                f = dict(prev)
                f.update({"last_checked": now, "changed": False, "stale": False, "warning": warning,
                          "http_status": res.status, "final_url": res.final_url or res.url, "integrity": "ok",
                          "text_sha256": prev_td})
                self.files.append(f)
                return f
        folder = ARCHIVE / self.rec["id"] / self.run_date
        folder.mkdir(parents=True, exist_ok=True)
        name = role_key + ext
        n = 2
        while (folder / name).exists() and sha256((folder / name).read_bytes()) != digest:
            name = "%s-%d%s" % (role_key, n, ext)
            n += 1
        (folder / name).write_bytes(body)
        rel = (folder / name).relative_to(ROOT).as_posix()
        self._append_sums(folder, name, digest)
        f = {
            "role_key": role_key, "role": role, "label": ROLE_LABELS.get(role, role), "path": rel,
            "url": res.url, "final_url": res.final_url or res.url, "http_status": res.status,
            "content_type": (res.content_type or "").split(";")[0] or None, "bytes": len(body), "sha256": digest,
            "text_sha256": tdigest,
            "retrieved_at": now, "last_checked": now, "method": res.method,
            "last_modified": res.headers.get("last-modified"), "etag": res.headers.get("etag"),
            "changed": bool(prev), "previous_sha256": prev.get("sha256") if prev else None,
            "previous_path": prev.get("path") if prev else None, "stale": False, "warning": warning,
            "integrity": "ok",
        }
        self.files.append(f)
        return f

    @staticmethod
    def _append_sums(folder, name, digest):
        sums = folder / "SHA256SUMS"
        lines = sums.read_text(encoding="utf-8").splitlines() if sums.exists() else []
        lines = [l for l in lines if not l.endswith("  " + name)] + ["%s  %s" % (digest, name)]
        sums.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def keep_unchanged(self, role_key):
        """Keep an earlier copy as the current one, unflagged: used when robots.txt keeps the archiver from fetching it
        again (it disallows the URL, or could not be read). The document is not gone, the archiver only does not
        download it again. Returns the kept file, or None."""
        prev = self.prev_files.get(role_key)
        if prev and (ROOT / prev.get("path", "")).is_file():
            f = {k: v for k, v in prev.items() if k not in ("stale", "last_failed", "last_error")}
            self.files.append(f)
            return f
        return None

    def keep_previous(self, role_key, error):
        prev = self.prev_files.get(role_key)
        if prev and (ROOT / prev.get("path", "")).is_file():
            f = dict(prev)
            f.update({"stale": True, "last_failed": iso(self.run_time), "last_error": error})
            self.files.append(f)
            return True
        return False

    def attempt(self, role, res):
        self.attempts.append({
            "role": role, "url": res.url, "attempted_at": iso(utcnow()), "ok": bool(res.ok),
            "http_status": res.status, "error": res.error, "method": res.method,
        })

    # -- outcome
    def finalise(self):
        rec = self.rec
        have = {f.get("path") for f in self.files}
        self.files += [dict(f) for f in self.provided if f.get("path") not in have and (ROOT / f["path"]).is_file()]
        stale = [f for f in self.files if f.get("stale")]
        fresh = [f for f in self.files if not f.get("stale")]
        provided = [f for f in fresh if f.get("role") == "provided"]
        has_official = any(f["role_key"] in ("official", "official-rendered") for f in fresh) or bool(provided)
        has_any_official = any(f["role_key"].startswith("official") for f in self.files)
        has_secondary = any(f["role_key"] == "secondary" for f in self.files)
        flags = []
        if not rec.get("official_url"):
            if has_secondary:
                status = "partial"
                flags.append("No official URL is recorded; only the secondary source was saved.")
            else:
                status = "no-url" if not rec.get("secondary_url") else "failed"
                flags.append("No official URL is recorded, so nothing official could be archived."
                             if status == "no-url" else "No official URL, and the secondary source failed: %s"
                             % (self.official_error or "unknown error"))
        elif has_official and not self.official_warnings:
            status = "archived"
        elif has_official:
            status = "archived-review"
            flags.extend(self.official_warnings)
        elif has_any_official:  # only an earlier copy is left
            status = "archived-review"
            kept = ", ".join(sorted({f["retrieved_at"][:10] for f in stale if f["role_key"].startswith("official")}))
            if self.unusable:
                flags.append("This run's download of the official page was not usable (%s), so the clean copy from %s "
                             "is kept." % (self.unusable, kept))
            else:
                flags.append("The official source could not be downloaded this time (%s). The copy from %s is kept; "
                             "the source may have moved or been taken down." % (self.official_error, kept))
        elif has_secondary:
            status = "partial"
            flags.append("The official source could not be downloaded (%s); only the secondary source was saved."
                         % self.official_error)
        else:
            status = "failed"
            flags.append("The official source could not be downloaded: %s." % (self.official_error or "unknown error"))
        flags.extend(self.notes)
        if provided and not any(f["role_key"] in ("official", "official-rendered") for f in fresh):
            flags.append(provided_flag(provided[-1]))
        if status == "archived" and any(f["role_key"].startswith(("official", "document")) for f in stale):
            status = "archived-review"  # a stale secondary is noted in the flag but does not need a review
        if any(f.get("changed") for f in fresh):
            flags.append("A source changed since the previous snapshot; both versions are kept.")
        flags = [f.strip() for f in flags if f and f.strip()]
        flags = [f if f.endswith((".", "!", "?")) else f + "." for f in flags]
        history = (self.prev_attempts + self.attempts)[-30:]
        rec["local_copy"] = {
            "status": status,
            "flag": " ".join(flags) or None,
            "last_attempt": iso(self.run_time),
            "files": sorted(self.files, key=lambda f: ["official", "official-rendered", "official-print",
                                                        "provided", "document", "secondary"].index(f["role"])
                            if f["role"] in ROLE_LABELS else 9),
            "attempts": history,
        }
        return status


def run_http(job, fetcher, args):
    rec = job.rec
    job.run_time = utcnow()
    url = rec.get("official_url")
    if url:
        res = fetcher.get(url)
        job.attempt("official", res)
        if res.ok and res.status and res.status < 400 and res.body:
            warnings = []
            if res.is_html:
                warnings, _ = inspect_html(res, rec)
            prev = job.prev_files.get("official")
            if warnings and prev and not prev.get("warning") and (ROOT / prev.get("path", "")).is_file():
                # A bot-check or empty page must not replace a clean copy from an earlier run.
                job.unusable = "; ".join(warnings)
                job.official_error = job.unusable
                for key in [k for k in job.prev_files if k.startswith(("official", "document-"))]:
                    job.keep_previous(key, job.unusable)
                job.need_browser = True
                warnings = []
            else:
                job.store("official", "official", res, "; ".join(warnings) or None)
                job.official_ok = True
                job.official_warnings = warnings
                if warnings:
                    job.need_browser = True
            if res.is_html and args.pdfs > 0 and not warnings and not job.unusable:
                cands = pdf_candidates(res, rec, args.pdfs)
                for i, link in enumerate(cands, 1):
                    r2 = fetcher.get(link)
                    job.attempt("document", r2)
                    key = "document-%d" % i
                    if r2.ok and r2.is_pdf:
                        job.store(key, "document", r2)
                    elif r2.ok:
                        job.notes.append("A linked file (%s) was not a PDF and was skipped." % link)
                    elif r2.robots and job.keep_unchanged(key):
                        pass  # stored earlier; robots.txt keeps the archiver from trying it again, so the copy stays as it is
                    elif job.keep_previous(key, r2.error):
                        job.notes.append("A linked PDF saved earlier can no longer be downloaded (%s: %s); "
                                         "the earlier copy is kept." % (link, r2.error))
                    else:
                        job.notes.append("A linked PDF could not be downloaded (%s: %s)." % (link, r2.error))
        else:
            if res.ok and not res.body:
                res.error = "The server returned an empty response"
            job.official_error = res.error or ("HTTP %s" % res.status)
            keys = [k for k in job.prev_files if k.startswith(("official", "document-"))]
            if res.robots and any(job.prev_files[k].get("url") == res.url for k in keys if k.startswith("official")):
                # Stored earlier from this URL; robots.txt now keeps the archiver from trying it again, which says nothing
                # about the document. The copies, and the documents linked from the page, stay current as they were,
                # with the warning that decided their status.
                kept = {k: job.keep_unchanged(k) for k in keys}
                cur = kept.get("official-rendered") or kept.get("official")
                job.official_warnings = [cur["warning"]] if cur and cur.get("warning") else []
            else:
                for key in keys:
                    job.keep_previous(key, job.official_error)
            job.need_browser = not res.robots and res.code not in ("bad-url", "dns", "timeout", "private-host")
    sec = rec.get("secondary_url")
    if sec and not args.no_secondary:
        r3 = fetcher.get(sec)
        job.attempt("secondary", r3)
        sec_warnings = inspect_html(r3, rec)[0] if r3.ok and r3.body and r3.is_html else []
        sec_warnings = [w for w in sec_warnings if not w.startswith("The page barely mentions")]  # a secondary may be about the document
        prev_sec = job.prev_files.get("secondary")
        if r3.ok and r3.body and sec_warnings and prev_sec and not prev_sec.get("warning") \
                and (ROOT / prev_sec.get("path", "")).is_file():
            job.keep_previous("secondary", "; ".join(sec_warnings))
            job.notes.append("The secondary source returned a bot-check or empty page this time (%s); the earlier copy is kept."
                             % "; ".join(sec_warnings))
        elif r3.ok and r3.body:
            job.store("secondary", "secondary", r3, "; ".join(sec_warnings) or None)
            if sec_warnings:
                job.notes.append("The secondary source is a bot-check or empty page (%s)." % "; ".join(sec_warnings))
        elif r3.robots and prev_sec and prev_sec.get("url") == r3.url and job.keep_unchanged("secondary"):
            if prev_sec.get("warning"):  # stored earlier; robots.txt keeps the archiver from trying it again, so it stays as it is
                job.notes.append("The secondary source is a bot-check or empty page (%s)." % prev_sec["warning"])
        elif job.keep_previous("secondary", r3.error):
            job.notes.append("The secondary source can no longer be downloaded (%s); the earlier copy is kept."
                             % r3.error)
        else:
            job.notes.append("The secondary source could not be downloaded (%s)." % r3.error)
            if not url:
                job.official_error = r3.error
    return job


class BrowserFetcher:
    """Optional fallback: render a page in headless Chromium via Playwright (sequential)."""

    def __init__(self, timeout):
        from playwright.sync_api import sync_playwright  # noqa: import inside so the rest needs no deps
        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch()
        self.ctx = self.browser.new_context(accept_downloads=False)
        self.timeout = timeout * 1000

    def get(self, url):
        url = iri_to_uri(url)
        if PUBLIC_ONLY and not is_public_url(url):
            return Result(url, False, error="Refused: the address is local or private", code="private-host",
                          method="browser"), None
        page = self.ctx.new_page()
        try:
            try:
                resp = page.goto(url, wait_until="networkidle", timeout=self.timeout)
            except Exception as e:
                if "Download is starting" in str(e):
                    r = self.ctx.request.get(url, timeout=self.timeout)
                    return Result(url, r.ok, r.status, r.url, {k.lower(): v for k, v in r.headers.items()},
                                  r.body(), None if r.ok else "HTTP %d" % r.status, method="browser"), None
                return Result(url, False, error="Browser could not load the page: %s" % str(e).splitlines()[0],
                              code="browser", method="browser"), None
            status = resp.status if resp else None
            if status and status >= 400:
                return Result(url, False, status, page.url, error="HTTP %d (in browser)" % status, code="http",
                              method="browser"), None
            prev = -1  # single-page apps keep loading after "networkidle": wait until the visible text stops growing
            for _ in range(8):
                page.wait_for_timeout(1000)
                try:
                    n = len(page.inner_text("body") or "")
                except Exception:
                    break
                if n == prev:
                    break
                prev = n
            html_bytes = page.content().encode("utf-8")
            res = Result(url, True, status, page.url, {"content-type": "text/html; charset=utf-8"}, html_bytes,
                         method="browser")
            try:
                pdf = page.pdf(format="A4", print_background=True)
                pres = Result(url, True, status, page.url, {"content-type": "application/pdf"}, pdf,
                              method="browser")
            except Exception:
                pres = None
            return res, pres
        finally:
            page.close()

    def close(self):
        self.browser.close()
        self._pw.stop()


def run_browser(job, bf, fetcher, args):
    rec = job.rec
    url = rec.get("official_url")
    if args.respect_robots:
        rp, _, _ = fetcher._robots_for(iri_to_uri(url))
        if not robots_allow(rp, iri_to_uri(url)):
            return
    res, pres = bf.get(url)
    job.attempt("official-rendered", res)
    if not res.ok:
        job.notes.append("The browser retry also failed (%s)." % res.error)
        return
    if res.is_pdf:
        job.store("official", "official", res)
        job.official_warnings = []
        return
    warnings, _ = inspect_html(res, rec)
    job.store("official-rendered", "official-rendered", res, "; ".join(warnings) or None)
    if pres:
        job.store("official-print", "official-print", pres)
    # the plain copy kept as stale is replaced by the browser copy
    job.files = [f for f in job.files if not (f["role_key"] == "official" and f.get("stale"))]
    job.official_warnings = warnings
    if not warnings:
        job.notes.append("Saved with a headless browser because the plain download %s." % (
            "failed" if not job.official_ok else "looked incomplete"))


# ----------------------------------------------------------------------------- modes

def provided_flag(f):
    return ("The official site does not allow automated downloads; the stored copy was provided by %s and confirmed by %s%s."
            % (f.get("provided_by") or "a person", f.get("confirmed_by") or "a maintainer",
               (" (issue #%s)" % f["issue"]) if f.get("issue") else ""))


def _write_provided(folder, src, url, by, confirmed_by=None, issue=None, note=None, source_url=None, known=()):
    """Write a provided file into folder with its SHA-256 in SHA256SUMS; the file entry, or None when a file with the
    same hash is among known."""
    import mimetypes
    body = Path(src).read_bytes()
    if not body:
        raise SystemExit("%s is empty" % src)
    digest = sha256(body)
    if digest in set(known):
        return None  # already stored
    ctype = mimetypes.guess_type(str(src))[0] or "application/octet-stream"
    ext = Path(src).suffix.lower() or ext_for(ctype, body, url)
    folder.mkdir(parents=True, exist_ok=True)
    # a retry after an interrupted store reuses the copy already written to this folder instead of writing another
    sums = folder / "SHA256SUMS"
    listed = [l.split("  ", 1)[1] for l in (sums.read_text(encoding="utf-8").splitlines() if sums.exists() else [])
              if l.startswith(digest + "  ")]
    name = next((x for x in listed if x.startswith("provided") and (folder / x).is_file()
                 and sha256((folder / x).read_bytes()) == digest), None)
    if not name:
        name, n = "provided" + ext, 2
        while (folder / name).exists():
            name, n = "provided-%d%s" % (n, ext), n + 1
        (folder / name).write_bytes(body)
        RecordJob._append_sums(folder, name, digest)
    now = iso(utcnow())
    return {"role_key": "provided", "role": "provided", "label": ROLE_LABELS["provided"],
            "path": (folder / name).relative_to(ROOT).as_posix(), "url": url, "final_url": source_url or url,
            "http_status": None, "content_type": ctype, "bytes": len(body), "sha256": digest, "text_sha256": None,
            "retrieved_at": now, "last_checked": now, "method": "provided", "last_modified": None, "etag": None,
            "changed": False, "previous_sha256": None, "previous_path": None, "stale": False, "warning": None,
            "integrity": "ok", "provided_by": by, "confirmed_by": confirmed_by or by, "issue": issue, "note": note}


def store_provided_lead(lead_id, src, url, by, confirmed_by=None, issue=None, note=None, source_url=None, known=()):
    """Store a document a person downloaded by hand for an instrument that has no record yet. It is kept under
    archive/_provided/<lead ID>/ and travels with the lead: the run that follows the lead up gets it as a stored
    source of its candidate (attach_provided)."""
    return _write_provided(ARCHIVE / "_provided" / lead_id / iso(utcnow())[:10], src, url, by, confirmed_by, issue,
                           note, source_url, known)


def attach_provided(rd):
    """Give each candidate of a run that follows up a lead with a provided document that document as a stored source
    (role "provided"), next to whatever the archiver could fetch itself. Returns the candidates that got one."""
    leads = {l.get("id"): l for l in (read_json(ROOT / "pipeline" / "leads.json", {}) or {}).get("leads") or []
             if l.get("id") and l.get("provided")}
    if not leads:
        return []
    path = rd / "sources.json"
    sources = read_json(path, {}) or {}
    got = []
    for c in (read_json(rd / "candidates.json", {}) or {}).get("candidates") or []:
        lead = leads.get(c.get("lead"))
        if not lead or c.get("status", "active") != "active" or not c.get("cand_id"):
            continue
        f = dict(lead["provided"])
        if not (ROOT / f.get("path", "")).is_file():
            print("  %s: the provided file of lead %s is missing: %s" % (c["cand_id"], lead["id"], f.get("path")))
            continue
        entry = sources.setdefault(c["cand_id"], {"main": None, "extras": {}})
        lc = entry.get("main") or {"status": "failed", "files": []}
        if any(x.get("sha256") == f["sha256"] for x in lc.get("files") or []):
            continue
        lc.setdefault("files", []).append(f)
        fresh = any(x.get("role_key") in ("official", "official-rendered") and not x.get("stale") for x in lc["files"])
        lc.update(status="archived", flag=None if fresh else provided_flag(f))
        entry["main"] = lc
        got.append(c["cand_id"])
    if got:
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(sources, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        tmp.replace(path)
    return got


def store_provided(db, rid, src, url, by, confirmed_by=None, issue=None, note=None, source_url=None):
    """Store a document a person downloaded by hand (the site blocks automated downloads by robots.txt or refuses
    this network) as a copy of the record's official source, with who provided and who confirmed it."""
    rec = {r["id"]: r for r in db["records"]}.get(rid)
    if not rec:
        raise SystemExit("No record %s" % rid)
    lc = rec.get("local_copy") or {}
    files = [f for f in lc.get("files") or []]
    f = _write_provided(ARCHIVE / rid / iso(utcnow())[:10], src, url, by, confirmed_by, issue, note, source_url,
                        known=[x.get("sha256") for x in files])
    if not f:
        return None
    files.append(f)
    has_fresh_official = any(x.get("role_key") in ("official", "official-rendered") and not x.get("stale") for x in files)
    rec["local_copy"] = dict(lc, files=files, status="archived",
                             flag=None if has_fresh_official else provided_flag(f), last_attempt=f["retrieved_at"])
    return f


def verify(db):
    problems = 0
    for rec in db["records"]:
        lc = rec.get("local_copy") or {}
        bad = []
        for f in lc.get("files") or []:
            p = ROOT / f.get("path", "")
            if not p.is_file():
                f["integrity"] = "missing"
                bad.append("%s (missing)" % f["path"])
            elif sha256(p.read_bytes()) != f.get("sha256"):
                f["integrity"] = "modified"
                bad.append("%s (modified)" % f["path"])
            else:
                f["integrity"] = "ok"
        if bad:
            problems += len(bad)
            msg = "Integrity check %s: local file missing or changed since archiving: %s." % (
                iso(utcnow())[:10], ", ".join(bad))
            lc["integrity_flag"] = msg
            if lc.get("status") == "archived":
                lc["status"] = "archived-review"
            print("  %-10s %s" % (rec["id"], msg))
        elif lc.get("files"):
            lc["integrity_flag"] = None
    return problems


def select(db, args):
    recs = db["records"]
    if args.only:
        ids = {x.strip() for x in args.only.split(",") if x.strip()}
        recs = [r for r in recs if r["id"] in ids or r.get("slug") in ids]
    if args.status:
        st = {x.strip() for x in args.status.split(",") if x.strip()}
        recs = [r for r in recs if (r.get("local_copy") or {}).get("status", "not-attempted") in st]
    return recs


# ----------------------------------------------------------------------------- pipeline runs

def run_dir(run_id):
    d = ROOT / "runs" / run_id
    if not (d / "run.json").is_file():
        raise SystemExit("No pipeline run %r (runs/%s/run.json is missing)" % (run_id, run_id))
    return d


def read_json(path, default=None):
    if not path.is_file():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def extra_urls(rd, cid):
    """Further sources the extractor, the blind extractor or the checker asked for."""
    urls = []
    for sub in ("extractions", "extractions-blind", "checks"):
        doc = read_json(rd / sub / ("%s.json" % cid), {}) or {}
        for u in doc.get("extra_urls") or []:
            u = u.get("url") if isinstance(u, dict) else u
            if isinstance(u, str) and u.startswith(("http://", "https://")) and u not in urls:
                urls.append(u)
    return urls


def select_run(db, args):
    """Records and pseudo-records to archive for a run, and where each result belongs in sources.json."""
    rd = run_dir(args.run)
    cands = (read_json(rd / "candidates.json", {}) or {}).get("candidates") or []
    if not cands:
        raise SystemExit("runs/%s/candidates.json has no candidates; run tools/pipeline.py dedupe first" % args.run)
    sources = read_json(rd / "sources.json", {}) or {}
    by = {r["id"]: r for r in db["records"]}
    only = {x.strip() for x in (args.only or "").split(",") if x.strip()}
    recs, where = [], {}
    # A source this run has already stored is not fetched again (pages that change on every request would otherwise
    # get a new snapshot each pass, and the files an extractor quoted would drop out of the record); failed and
    # partial ones are retried. --refetch fetches everything again.
    stored = lambda lc: not getattr(args, "refetch", False) and (lc or {}).get("status") in ("archived", "archived-review")  # noqa: E731
    for c in cands:
        cid = c["cand_id"]
        if c.get("status", "active") != "active" or (only and cid not in only):
            continue
        prev = sources.get(cid) or {}
        title = c.get("title_as_found") or ""
        if c.get("record_id"):
            rec = by.get(c["record_id"])
            if not rec:
                print("  %s: record %s does not exist; skipped" % (cid, c["record_id"]))
                continue
            title = rec.get("title") or title
            if not stored(prev.get("main")):
                recs.append(rec)
                where[id(rec)] = (cid, "main", None)
        else:
            leads = [u for u in c.get("lead_urls") or [] if isinstance(u, str)]
            pseudo = {"id": "_runs/%s/%s" % (args.run, cid), "title": title, "short_title": title,
                      "original_title": c.get("original_title"), "official_identifier": c.get("official_identifier"),
                      "official_url": c.get("url"), "secondary_url": None if c.get("url") else (leads[:1] or [None])[0],
                      "local_copy": prev.get("main")}
            if not stored(prev.get("main")):
                recs.append(pseudo)
                where[id(pseudo)] = (cid, "main", None)
        for u in extra_urls(rd, cid):
            if stored((prev.get("extras") or {}).get(u)):
                continue
            key = hashlib.sha256(u.encode("utf-8")).hexdigest()[:10]
            pseudo = {"id": "_runs/%s/%s/extra-%s" % (args.run, cid, key), "title": title, "short_title": title,
                      "official_url": u, "secondary_url": None, "local_copy": (prev.get("extras") or {}).get(u)}
            recs.append(pseudo)
            where[id(pseudo)] = (cid, "extra", u)
    return rd, recs, where


def save_run_sources(rd, recs, where):
    path = rd / "sources.json"
    sources = read_json(path, {}) or {}
    for rec in recs:
        cid, kind, url = where[id(rec)]
        entry = sources.setdefault(cid, {"main": None, "extras": {}})
        lc = copy.deepcopy(rec.get("local_copy"))
        if kind == "main":
            entry["main"] = lc
            if not str(rec["id"]).startswith("_runs/"):
                entry["record_id"] = rec["id"]
        else:
            entry.setdefault("extras", {})[url] = lc
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(sources, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)
    return sources


def write_manifest(db, started, args, counts, ua):
    ARCHIVE.mkdir(exist_ok=True)
    manifest = {
        "generated_at": iso(utcnow()), "tool": "tools/archive.py", "tool_version": TOOL_VERSION,
        "user_agent": ua, "records": {r["id"]: r.get("local_copy") for r in db["records"]},
    }
    tmp = ARCHIVE / "manifest.json.tmp"
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ARCHIVE / "manifest.json")
    with open(ARCHIVE / "runs.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "started": iso(started), "finished": iso(utcnow()), "counts": counts,
            "options": vars(args),
        }, ensure_ascii=False) + "\n")


ATTENTION_GROUPS = [
    ("failed", "Nothing could be downloaded"),
    ("partial", "Only the secondary source was saved"),
    ("archived-review", "Saved, but the copy needs a human look"),
    ("no-url", "No URL to archive"),
    ("not-attempted", "Not attempted yet"),
    ("integrity", "A local file is missing or has changed since it was archived"),
]


def write_attention_log(db):
    """Rewrite archive/needs-attention.txt: every record that is not cleanly archived, with the reason.

    The file is for the person running the register. Nothing in it is sent anywhere, and the
    archiver takes no further action; saving a copy by hand, asking the site operator or leaving
    the record flagged is their decision.
    """
    ARCHIVE.mkdir(exist_ok=True)
    today = utcnow().strftime("%Y-%m-%d")
    groups = defaultdict(list)
    listed = set()
    for rec in db["records"]:
        lc = rec.get("local_copy") or {}
        status = lc.get("status") or "not-attempted"
        if status != "archived":
            groups[status].append(rec)
            listed.add(rec["id"])
        if lc.get("integrity_flag"):
            groups["integrity"].append(rec)
            listed.add(rec["id"])

    def wrap(label, text):
        return textwrap.wrap("%-14s%s" % (label, text or "-"), width=96, subsequent_indent=" " * 14,
                             break_long_words=False, break_on_hyphens=False) or ["%-14s-" % label]

    lines = [
        "Records that need a human decision - Every AI Policy Ever",
        "Written %s by tools/archive.py. Register: %d records, %d listed here." % (
            iso(utcnow()), len(db["records"]), len(listed)),
        "",
        "This file is rewritten after every archiver run and after --verify. Nothing in it is sent",
        "anywhere. For each record, decide yourself what to do:",
        "  - open the official URL in a normal browser, save the document into the folder named",
        "    below, add it to local_copy.files in data/records.json, then run tools/build.py and",
        "    tools/archive.py --verify;",
        "  - or ask the site operator for a copy;",
        "  - or leave the record flagged (the flag stays visible in the app and the data files).",
        "",
    ]
    for status, heading in ATTENTION_GROUPS:
        recs = groups.get(status) or []
        if not recs:
            continue
        lines += ["=" * 100, "%s (%s): %d" % (heading, status, len(recs)), "=" * 100, ""]
        for rec in recs:
            lc = rec.get("local_copy") or {}
            lines.append("%s  %s" % (rec["id"], rec.get("short_title") or rec.get("title") or ""))
            lines += ["    " + l for l in wrap("jurisdiction:", rec.get("jurisdiction"))]
            if rec.get("official_url"):
                lines.append("    %-14s%s" % ("official:", rec["official_url"]))
            if rec.get("secondary_url"):
                lines.append("    %-14s%s" % ("secondary:", rec["secondary_url"]))
            problem = lc.get("integrity_flag") if status == "integrity" else lc.get("flag")
            lines += ["    " + l for l in wrap("problem:", problem)]
            if lc.get("last_attempt"):
                lines.append("    %-14s%s" % ("last attempt:", lc["last_attempt"]))
            stored = [f["path"] for f in lc.get("files") or [] if f.get("path") and not f.get("stale")]
            if stored:
                lines += ["    " + l for l in wrap("stored:", ", ".join(stored))]
            if status == "no-url":
                lines.append("    %-14s%s" % ("to do:", "add an official_url to data/records.json, then re-run the archiver"))
            else:
                lines.append("    %-14s%s" % ("save by hand:", "archive/%s/%s/" % (rec["id"], today)))
            lines.append("")
    if not listed:
        lines.append("Every record is cleanly archived. Nothing to decide.")
    ATTENTION_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(listed)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Download local copies of the register's sources and flag failures.")
    ap.add_argument("--only", help="comma-separated record IDs or slugs, e.g. EU-01,US-07 (with --run: candidate IDs)")
    ap.add_argument("--run", help="store the sources of a pipeline run's candidates (runs/<RUN>/candidates.json)")
    ap.add_argument("--refetch", action="store_true",
                    help="with --run: fetch again the sources this run has already stored (default: only new and failed ones)")
    ap.add_argument("--allow-private-hosts", action="store_true",
                    help="with --run: also fetch local and private addresses (only for tests against a local test site)")
    ap.add_argument("--status", help="only records whose local status is one of these, e.g. failed,partial,not-attempted")
    ap.add_argument("--pdfs", type=int, default=2, help="max linked PDFs to save per official page (default 2, 0 = none)")
    ap.add_argument("--no-secondary", action="store_true", help="do not download secondary URLs")
    ap.add_argument("--browser", action="store_true", help="retry failed/suspicious pages in headless Chromium (Playwright)")
    ap.add_argument("--ignore-robots", dest="respect_robots", action="store_false",
                    help="do not check robots.txt (only if you have the right to fetch these pages)")
    ap.add_argument("--workers", type=int, default=4, help="parallel downloads across different sites (default 4)")
    ap.add_argument("--delay", type=float, default=2.0, help="seconds between requests to the same site (default 2)")
    ap.add_argument("--timeout", type=int, default=45, help="seconds per request (default 45)")
    ap.add_argument("--retries", type=int, default=2, help="retries for timeouts and 5xx/429 errors (default 2)")
    ap.add_argument("--max-mb", type=int, default=150, help="largest file to keep, in MB (default 150)")
    ap.add_argument("--dry-run", action="store_true", help="list what would be fetched and exit")
    ap.add_argument("--provide", metavar="FILE", help="store FILE, downloaded by a person, as a copy of a record's official "
                                                      "source (with --id, --url and --by)")
    ap.add_argument("--id", help="with --provide: the record ID")
    ap.add_argument("--url", help="with --provide: the official URL the document comes from")
    ap.add_argument("--by", help="with --provide: who downloaded or provided it")
    ap.add_argument("--confirmed-by", help="with --provide: the maintainer who checked it matches the official source "
                                           "(default: --by)")
    ap.add_argument("--issue", type=int, help="with --provide: the GitHub issue it was provided in")
    ap.add_argument("--note", help="with --provide: a short note, e.g. how it was obtained")
    ap.add_argument("--verify", action="store_true", help="re-hash local files, flag missing/modified ones, and exit")
    ap.add_argument("--audit-robots", metavar="OUT.json", nargs="?", const="",
                    help="list stored files whose URL robots.txt disallows (RFC 9309); read-only")
    args = ap.parse_args(argv)

    db = build.normalise(build.load())

    if args.provide:
        if not (args.id and args.url and args.by):
            raise SystemExit("--provide needs --id, --url and --by")
        f = store_provided(db, args.id, args.provide, args.url, args.by, args.confirmed_by, args.issue, args.note)
        if not f:
            print("%s already has this file (same SHA-256); nothing stored." % args.id)
            return 0
        build.save(db)
        write_attention_log(db)
        print("Stored %s for %s (SHA-256 %s), provided by %s, confirmed by %s." % (
            f["path"], args.id, f["sha256"], f["provided_by"], f["confirmed_by"]))
        print("Next: python3 tools/build.py; a refresh run of %s reads it as the official text." % args.id)
        return 0

    if args.audit_robots is not None:
        return audit_robots(ROOT, args.audit_robots or None)
    if args.verify:
        print("Verifying local files against their recorded SHA-256 hashes ...")
        n = verify(db)
        build.save(db)
        todo = write_attention_log(db)
        print("Integrity problems: %d" % n)
        print("Records that need a decision: %d, listed in %s" % (todo, ATTENTION_FILE.relative_to(ROOT)))
        return 1 if n else 0

    global PUBLIC_ONLY
    PUBLIC_ONLY = bool(args.run) and not args.allow_private_hosts
    rd, where = None, {}
    if args.run:
        rd, recs, where = select_run(db, args)
    else:
        recs = select(db, args)
    if args.dry_run:
        for r in recs:
            print("%-10s %-15s official=%s secondary=%s" % (
                r["id"], (r.get("local_copy") or {}).get("status", "not-attempted"), r.get("official_url"),
                r.get("secondary_url")))
        print("%d records selected." % len(recs))
        return 0

    ua = "%s/%s (research archive of public AI policy documents)" % (AGENT_TOKEN, TOOL_VERSION)
    fetcher = Fetcher(ua, args.timeout, args.retries, args.delay, args.max_mb << 20, args.respect_robots)
    started = utcnow()
    run_date = started.strftime("%Y-%m-%d")
    print("Archiving %d records into %s (%s workers, %.1fs per-site delay, robots.txt %s)" % (
        len(recs), ARCHIVE.relative_to(ROOT), args.workers, args.delay,
        "respected" if args.respect_robots else "IGNORED"))

    jobs, done = [], 0
    counts = defaultdict(int)
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            futs = {pool.submit(run_http, RecordJob(r, run_date, utcnow()), fetcher, args): r for r in recs}
            for fut in concurrent.futures.as_completed(futs):
                rec = futs[fut]
                done += 1
                try:
                    job = fut.result()
                except Exception as e:  # never lose the run because of one record
                    job = RecordJob(rec, run_date, utcnow())
                    job.official_error = "Archiver error: %s: %s" % (type(e).__name__, e)
                    job.keep_previous("official", job.official_error)
                jobs.append(job)
                status = job.finalise()
                counts[status] += 1
                sizes = sum(f.get("bytes") or 0 for f in job.files if not f.get("stale"))
                print("[%3d/%d] %-10s %-16s %7.1f KB  %s" % (
                    done, len(recs), rec["id"], status, sizes / 1024,
                    (rec["local_copy"].get("flag") or "")[:110]))
                if done % 10 == 0:
                    build.save(db)
    except KeyboardInterrupt:
        print("\nInterrupted; saving what has been archived so far.")

    if args.browser:
        retry = [j for j in jobs if j.need_browser and j.rec.get("official_url")]
        if retry:
            try:
                bf = BrowserFetcher(args.timeout)
            except Exception as e:
                print("Browser mode unavailable (%s). Install with: pip install playwright && playwright install chromium" % e)
                bf = None
            if bf:
                print("Retrying %d records in a headless browser ..." % len(retry))
                try:
                    for j in retry:
                        before = j.rec["local_copy"]["status"]
                        counts[before] -= 1
                        try:
                            run_browser(j, bf, fetcher, args)
                        except Exception as e:
                            j.notes.append("The browser retry failed (%s)." % e)
                        after = j.finalise()
                        counts[after] += 1
                        print("  %-10s %s -> %s" % (j.rec["id"], before, after))
                finally:
                    bf.close()

    build.save(db)
    if rd is not None:
        save_run_sources(rd, recs, where)
        for cid in attach_provided(rd):
            print("  %s: added the document provided for its lead" % cid)
        print("Stored sources listed in %s; next: python3 tools/pipeline.py textify --run %s"
              % ((rd / "sources.json").relative_to(ROOT), args.run))
    counts = {k: v for k, v in counts.items() if v}
    write_manifest(db, started, args, counts, ua)
    todo = write_attention_log(db)
    total = defaultdict(int)
    for r in db["records"]:
        total[r["local_copy"]["status"]] += 1
    print("\nThis run: " + ", ".join("%s %d" % (k, counts[k]) for k in build.LOCAL_STATUSES if k in counts))
    print("Whole register: " + ", ".join("%s %d" % (k, total[k]) for k in build.LOCAL_STATUSES if k in total))
    print("Flags are stored in data/records.json (local_copy.flag) and shown in the app.")
    print("Records that need a decision: %d, listed in %s. Nothing is sent anywhere; what to do is up to you."
          % (todo, ATTENTION_FILE.relative_to(ROOT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
