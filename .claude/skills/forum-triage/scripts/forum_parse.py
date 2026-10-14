#!/usr/bin/env python3
"""Parse saved pages from non-English Mozilla community forums into JSON lines.

Usage: forum_parse.py <kind> FILE...

Kinds:
  smf-board    Mozilla Italia board page (index.php?board=N.0): one line per topic
  smf-topic    Mozilla Italia topic page (index.php?topic=N.0): one line per post
  wbb-feed     camp-firefox thread-list RSS feed: one line per thread
  wbb-board    camp-firefox board page (forum/forum/N-slug/): one line per thread
  wbb-thread   camp-firefox thread page (forum/thema/N-slug/): one line per post
  phpbb-feed   mozfr Atom feed saved by the user: one line per post
  phpbb-forum  mozfr forum page (viewforum.php?f=N) saved by the user: one line per topic
  phpbb-topic  mozfr topic page (viewtopic.php?t=N) saved by the user: one line per post

Every line is a JSON object. Dates are ISO 8601 in UTC.
"""

import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
PARIS = ZoneInfo("Europe/Paris")
IT_MONTHS = {
    m: i + 1
    for i, m in enumerate(
        "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split()
    )
}
FR_MONTHS = {
    m: i + 1
    for i, m in enumerate(
        "janv. févr. mars avr. mai juin juil. août sept. oct. nov. déc.".split()
    )
}
VOID = {"br", "img", "hr", "input", "meta", "link", "source", "wbr", "area", "col"}
BLOCK = {"br", "p", "div", "li", "blockquote", "tr", "h1", "h2", "h3", "h4", "h5", "pre"}


def utc(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clean_url(url):
    url = html.unescape(url)
    url = re.sub(r"(PHPSESSID|sid)=[0-9a-z]+(&|;)?", "", url)
    return url.replace("?&", "?").rstrip("?&")


def strip_tags(s):
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"[ \t\xa0]+", " ", html.unescape(s)).strip()


class Blocks(HTMLParser):
    """Collect text of every element whose start tag matches `match`, nested ones included."""

    def __init__(self, match):
        super().__init__(convert_charrefs=True)
        self.match = match
        self.stack = []
        self.found = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in VOID:
            if tag == "br":
                for f in self.stack:
                    f["text"].append("\n")
            return
        for f in self.stack:
            f["depth"] += 1
            if tag == "blockquote":
                f["text"].append("\n[quote] ")
            elif tag in BLOCK:
                f["text"].append("\n")
        if self.match(tag, a):
            self.stack.append({"attrs": a, "depth": 1, "text": []})

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        for f in list(self.stack):
            f["depth"] -= 1
            if tag == "blockquote":
                f["text"].append(" [/quote]\n")
            if f["depth"] == 0:
                self.stack.remove(f)
                self.found.append((f["attrs"], norm("".join(f["text"]))))

    def handle_data(self, data):
        for f in self.stack:
            f["text"].append(data)


def norm(t):
    t = re.sub(r"[ \t\xa0]+", " ", t)
    return re.sub(r"\n\s*\n+", "\n", t).strip()


def blocks(text, match):
    p = Blocks(match)
    p.feed(text)
    return p.found


def it_date(s, now=None):
    s = strip_tags(s).lower()
    now = now or datetime.now(ROME)
    m = re.search(r"(oggi|ieri)\D*(\d{1,2}):(\d{2})(?::(\d{2}))?", s)
    if m:
        d = now.date() - timedelta(days=1 if m.group(1) == "ieri" else 0)
        dt = datetime(d.year, d.month, d.day, int(m.group(2)), int(m.group(3)), int(m.group(4) or 0), tzinfo=ROME)
        return utc(dt)
    m = re.search(r"(\d{1,2}) (\w+) (\d{4}),? (\d{1,2}):(\d{2})(?::(\d{2}))?", s)
    if m and m.group(2) in IT_MONTHS:
        dt = datetime(int(m.group(3)), IT_MONTHS[m.group(2)], int(m.group(1)), int(m.group(4)), int(m.group(5)), int(m.group(6) or 0), tzinfo=ROME)
        return utc(dt)
    return None


def fr_date(s):
    s = strip_tags(s).lower()
    m = re.search(r"(\d{1,2}) (\S+) (\d{4}),? (\d{1,2}):(\d{2})", s)
    if m and m.group(2) in FR_MONTHS:
        dt = datetime(int(m.group(3)), FR_MONTHS[m.group(2)], int(m.group(1)), int(m.group(4)), int(m.group(5)), tzinfo=PARIS)
        return utc(dt)
    return None


def iso(s):
    return utc(datetime.fromisoformat(s)) if s else None


def read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def smf_board(text):
    base = "https://forum.mozillaitalia.org/index.php"
    for row in re.findall(r"<tr>(.*?)</tr>", text, re.S):
        m = re.search(r'<span id="msg_\d+"><a href="[^"]*topic=(\d+)\.0">(.*?)</a>', row, re.S)
        if not m:
            continue
        author = re.search(r"Aperto da (?:<a[^>]*>)?([^<]+)", row)
        replies = re.search(r"(\d+) Rispost", row)
        last = re.search(r'class="lastpost[^"]*">(.*?)</td>', row, re.S)
        yield {
            "topic": m.group(1),
            "url": f"{base}?topic={m.group(1)}.0",
            "title": strip_tags(m.group(2)),
            "author": author.group(1).strip() if author else None,
            "replies": int(replies.group(1)) if replies else None,
            "last_post": it_date(last.group(1)) if last else None,
            "sticky": "stickybg" in row,
        }


def smf_topic(text):
    base = "https://forum.mozillaitalia.org/index.php"
    topic = re.search(r"topic=(\d+)\.", text)
    bodies = {a["id"][4:]: t for a, t in blocks(text, lambda tag, a: tag == "div" and a.get("class") == "inner" and a.get("id", "").startswith("msg_"))}
    for chunk in re.split(r'<a id="msg(?=\d+"></a>)', text)[1:]:
        mid = chunk.split('"', 1)[0]
        author = re.search(r'<h4>.*?<a [^>]*>([^<]+)</a>', chunk, re.S) or re.search(r"<h4>\s*([^<]+?)\s*</h4>", chunk, re.S)
        date = re.search(r'<div class="smalltext">&#171; <strong>[^<]*</strong>(.*?)&#187;', chunk, re.S)
        subject = re.search(r'<h5 id="subject_\d+">(.*?)</h5>', chunk, re.S)
        yield {
            "post": mid,
            "url": f"{base}?topic={topic.group(1) if topic else ''}.msg{mid}#msg{mid}",
            "author": author.group(1).strip() if author else None,
            "date": it_date(date.group(1)) if date else None,
            "subject": strip_tags(subject.group(1)) if subject else None,
            "body": bodies.get(mid, ""),
        }


def wbb_feed(text):
    for item in ET.fromstring(text).iter("item"):
        link = item.findtext("link")
        yield {
            "thread": re.search(r"/thema/(\d+)-", link).group(1),
            "url": link,
            "title": item.findtext("title"),
            "author": item.findtext("{http://purl.org/dc/elements/1.1/}creator"),
            "replies": int(item.findtext("{http://purl.org/rss/1.0/modules/slash/}comments") or 0),
            "last_post": utc(parsedate_to_datetime(item.findtext("pubDate"))),
        }


def wbb_board(text):
    for row in re.split(r'<ol\s+id="thread(?=\d+")', text)[1:]:
        tid = row.split('"', 1)[0]
        title = re.search(r'class="messageGroupLink wbbTopicLink"[^>]*>(.*?)</a>', row, re.S)
        url = re.search(r'href="(https://www\.camp-firefox\.de/forum/thema/\d+-[^"/]+/)"', row)
        author = re.search(r'class="messageGroupAuthorMobile">([^<]+)', row)
        created = re.search(r'class="messageGroupTime"><woltlab-core-date-time date="([^"]+)"', row)
        last = re.search(r'class="messageGroupLastPostTimeMobile"><woltlab-core-date-time date="([^"]+)"', row)
        replies = re.search(r"<dt>Antworten</dt>\s*<dd>([\d.]+)</dd>", row)
        yield {
            "thread": tid,
            "url": url.group(1) if url else None,
            "title": strip_tags(title.group(1)) if title else None,
            "author": author.group(1).strip() if author else None,
            "created": iso(created.group(1)) if created else None,
            "last_post": iso(last.group(1)) if last else None,
            "replies": int(replies.group(1).replace(".", "")) if replies else None,
            "sticky": 'data-is-sticky="1"' in row or "wbbThreadAnnouncement" in row,
            "done": "Erledigt" in row and "Unerledigt" not in row,
        }


def wbb_thread(text):
    canon = re.search(r'<link rel="canonical" href="([^"?]+)', text)
    texts = {}
    for chunk in re.split(r'<article class="wbbPost(?=[^>]*data-post-id)', text)[1:]:
        pid = re.search(r'data-post-id="(\d+)"', chunk).group(1)
        date = re.search(r'itemprop="datePublished" content="([^"]+)"', chunk)
        author = re.search(r'<span itemprop="name">(.*?)</span>\s*</a>', chunk, re.S)
        body = blocks(chunk, lambda tag, a: a.get("itemprop") == "text")
        texts[pid] = {
            "post": pid,
            "url": f"{canon.group(1) if canon else ''}?postID={pid}#post{pid}",
            "author": strip_tags(author.group(1)) if author else None,
            "date": iso(date.group(1)) if date else None,
            "body": body[0][1] if body else "",
        }
    yield from texts.values()


def phpbb_feed(text):
    ns = {"a": "http://www.w3.org/2005/Atom"}
    for e in ET.fromstring(text).findall("a:entry", ns):
        link = e.find("a:link", ns).get("href")
        post = re.search(r"p=(\d+)", link)
        yield {
            "post": post.group(1) if post else None,
            "url": clean_url(link),
            "title": e.findtext("a:title", namespaces=ns),
            "author": e.findtext("a:author/a:name", namespaces=ns),
            "date": iso(e.findtext("a:updated", namespaces=ns)),
            "body": re.split(r"Statistiques\s?:", strip_tags(e.findtext("a:content", default="", namespaces=ns)))[0].strip(),
        }


def phpbb_forum(text):
    base = "https://forums.mozfr.org/viewtopic.php"
    for row in re.split(r'<li class="row', text)[1:]:
        m = re.search(r'viewtopic\.php\?t=(\d+)[^"]*" class="topictitle">(.*?)</a>', row, re.S)
        if not m:
            continue
        author = re.search(r'class="username(?:-coloured)?"[^>]*>([^<]+)</a>', row)
        replies = re.search(r'class="posts">\s*(\d+)', row)
        last = re.search(r'class="lastpost">(.*?)</dd>', row, re.S)
        last_iso = re.search(r'datetime="([^"]+)"', last.group(1)) if last else None
        yield {
            "topic": m.group(1),
            "url": f"{base}?t={m.group(1)}",
            "title": strip_tags(m.group(2)),
            "author": author.group(1).strip() if author else None,
            "replies": int(replies.group(1)) if replies else None,
            "last_post": iso(last_iso.group(1)) if last_iso else (fr_date(last.group(1)) if last else None),
            "sticky": "sticky" in row.split('"', 1)[0] or "announce" in row.split('"', 1)[0],
        }


def phpbb_topic(text):
    base = "https://forums.mozfr.org/viewtopic.php"
    bodies = {a["id"][8:]: t for a, t in blocks(text, lambda tag, a: tag == "div" and a.get("class") == "content" and a.get("id", "").startswith("post_content"))}
    if not bodies:
        bodies = {}
        for chunk in re.split(r'<div id="p(?=\d+")', text)[1:]:
            pid = chunk.split('"', 1)[0]
            b = blocks(chunk, lambda tag, a: tag == "div" and a.get("class") == "content")
            bodies[pid] = b[0][1] if b else ""
    for chunk in re.split(r'<div id="p(?=\d+")', text)[1:]:
        pid = chunk.split('"', 1)[0]
        author = re.search(r'class="username(?:-coloured)?"[^>]*>([^<]+)</a>', chunk)
        date = re.search(r'<time datetime="([^"]+)"', chunk)
        subject = re.search(r"<h3[^>]*>\s*<a [^>]*>(.*?)</a>", chunk, re.S)
        yield {
            "post": pid,
            "url": f"{base}?p={pid}#p{pid}",
            "author": author.group(1).strip() if author else None,
            "date": iso(date.group(1)) if date else None,
            "subject": strip_tags(subject.group(1)) if subject else None,
            "body": bodies.get(pid, ""),
        }


KINDS = {
    "smf-board": smf_board,
    "smf-topic": smf_topic,
    "wbb-feed": wbb_feed,
    "wbb-board": wbb_board,
    "wbb-thread": wbb_thread,
    "phpbb-feed": phpbb_feed,
    "phpbb-forum": phpbb_forum,
    "phpbb-topic": phpbb_topic,
}


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in KINDS:
        sys.exit(__doc__)
    for path in sys.argv[2:]:
        for rec in KINDS[sys.argv[1]](read(path)):
            rec["file"] = path
            print(json.dumps(rec, ensure_ascii=False))


if __name__ == "__main__":
    main()
