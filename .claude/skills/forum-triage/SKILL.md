---
name: forum-triage
description: Post-release triage of non-English Firefox community forums (camp-firefox.de in German, forum.mozillaitalia.org in Italian, forums.mozfr.org in French). Finds each forum's release announcement thread and recent support topics, reads the posts in the original language, extracts user-reported problems with the new version, de-dupes and groups them across forums, links each to a matching Bugzilla bug, and buckets them (Act now / Worth a look / New, no ticket / Not actionable) with English summaries. Supports re-runs that report only what is new since the last pull. Use when the user asks things like "what are the French/German/Italian forums saying about the release", "check camp-firefox", "forum triage", "non-English forum digest", "any new ones on the forums?", or wants the reddit-triage analysis for local-language communities.
---

# Forum Triage (non-English communities)

The sibling `reddit-triage` skill covers r/firefox. This skill does the same job for local-language Firefox support forums, which reach users who never post on Reddit and often report locale-specific problems: translations, regional sites and banks, dictionaries, and keyboard layouts. Turn what they report about the new release into a short triage list in English. Every item carries a **forum permalink**, a **one-line quote in the original language with an English translation**, and, where one exists, a **matching bug**.

**Scope: read and report only.** Never post, reply, register, log in or send private messages on a forum, and never modify Bugzilla. When an action is warranted (ask a reporter for details, file a bug, request an uplift), list it under Next steps for the user. If a reply on the forum is useful, draft it in the forum's language for the user to post.

Read `../reddit-triage/SKILL.md` before running. This skill reuses its **Inputs**, **Extracting and grouping reports**, **Matching to Bugzilla** and **Re-runs** sections as written, and only spells out what differs.

## Sources

| Forum | Language | Software | Automated access |
|---|---|---|---|
| camp-firefox.de | German | WoltLab Burning Board | Allowed (`robots.txt`: `Allow: /`) |
| forum.mozillaitalia.org | Italian | Simple Machines Forum 2 | Allowed except URLs containing `action=` or `;`, so **no RSS feeds**. Use board and topic pages. Crawl-delay 0.5s |
| forums.mozfr.org (Geckozone) | French | phpBB 3 | **Disallowed for `Claude-User`** and other AI agents (whole site). Do not fetch it; see "mozfr" below |

These policies were checked on 2026-10-14. **At the start of every run, fetch each site's `/robots.txt` and re-check it.** If a site now disallows `Claude-User` or `*` for the paths below, skip that site and say so. If mozfr now allows `Claude-User`, fetch it like the others, using the URLs below.

All three forums also host Thunderbird, SeaMonkey and localization boards. Skip those.

### Fetching

- Fetch sequentially, one request every 3 seconds or more, with a browser-like User-Agent. These are small volunteer-run servers, so keep each run to a few dozen requests per site. Never send cookies, and never log in.
- SMF adds `PHPSESSID=...` to every link when no cookie is sent. Strip it before fetching or citing a URL. `scripts/forum_parse.py` already does this in its output.
- Save downloads in a fresh `mktemp -d`, never in this repo or the Gecko checkout. Run the parser from the skill directory with `python3 -I`, passing file paths as arguments.
  ```sh
  UA="Mozilla/5.0 (X11; Linux x86_64; rv:140.0) Gecko/20100101 Firefox/140.0"
  fetch(){ code=$(curl -sL -A "$UA" -o "$2" -w '%{http_code}' "$1"); echo "$code $(wc -c <"$2") $1"; sleep 3; }
  ```
  Run fetch loops with `run_in_background` (foreground `sleep` is blocked) and wait for the completion notification.
- Parse with `scripts/forum_parse.py <kind> FILE...`. It prints one JSON object per topic or post, with UTC dates, a clean permalink, the author and the body text; quoted text is wrapped in `[quote] ... [/quote]`. Run it with no arguments to list the kinds. Don't build a classifier. Read the text yourself.

### camp-firefox.de (German)

- **Recent activity, all boards:** `https://www.camp-firefox.de/forum/thread-list-rss-feed/` (kind `wbb-feed`). It lists the 20 most recently active threads, which covers about 2–3 days. It ignores board filters.
- **Board listings**, sorted by last post (kind `wbb-board`). Use `.../forum/forum/<id>/`; it redirects to the slug URL. Add `?pageNo=2` to go further back.
  - 15 Firefox allgemein (main support board)
  - 8 Probleme auf Websites (site breakage)
  - 16 Individuelle Anpassungen (userChrome.css and scripts, the r/FirefoxCSS equivalent)
  - 4 Erweiterungen & Themes
  - 7 Vorab-Versionen (Beta and Nightly)
  - 21 Firefox für Smartphones und Tablets
  - 2 Nachrichten (news)
- **Release thread:** the forum admin (Sören Hentzschel, who also runs soeren-hentzschel.at) posts **"Mozilla veröffentlicht Firefox NNN ..."** in board 2. Release comments go there; there are separate posts for Android, iOS and dot releases.
- **Thread pages** (kind `wbb-thread`): `.../forum/thema/<id>-<slug>/`, 20 posts per page, `?pageNo=N`. Post permalinks look like `...?postID=<id>#post<id>`.
- Solved threads are marked "Erledigt". The listing parser exposes this as `done`.

### forum.mozillaitalia.org (Italian)

- **Board listings**, sorted by last post (kind `smf-board`): `https://forum.mozillaitalia.org/index.php?board=<id>.0`. There are 25 topics per page; use `board=<id>.25` and so on to go further back. Skip rows where `sticky` is true unless their `last_post` is in the window.
  - 2 Firefox (main support board)
  - 16 Siti non funzionanti (site breakage)
  - 29 Versioni di sviluppo Firefox
  - 36 Firefox per Android e iOS
  - 12 Componenti aggiuntivi
- **Topic pages** (kind `smf-topic`): `index.php?topic=<id>.0`, 15 posts per page, then `topic=<id>.15`, `topic=<id>.30` and so on. A listing row's `replies` tells you how many pages there are. Post permalinks look like `index.php?topic=<id>.msg<msg>#msg<msg>`; cite them, but don't fetch them (`.msg` is disallowed).
- **No release thread.** The Annunci board stopped announcing releases in 2013, so rely on the support boards. Users usually put the version in the title ("firefox157 ...", "dopo l'aggiornamento a 157").
- Dates on the page are Europe/Rome local time ("Oggi"/"Ieri" for recent posts). The parser converts them to UTC.
- Solved topics get "[Risolto]" in the title.

### mozfr (forums.mozfr.org, French)

Its `robots.txt` disallows `Claude-User`, `ClaudeBot`, `anthropic-ai` and many other AI agents from the whole site. **Do not fetch any mozfr URL**, including feeds and `robots.txt` mirrors, and do not get around the block with a different User-Agent. Instead, offer the user two options:

1. **The user saves the pages in their browser** (File > Save Page As, "Web Page, HTML only") into a directory and gives you the path. Parse the files with the `phpbb-*` kinds. Pages worth saving:
   - `https://forums.mozfr.org/viewforum.php?f=5` (Firefox board; topics sorted by last post) and `f=15` (Rapporter un site posant problème)
   - the sticky release topic **"[Info] Arrivée d'une nouvelle mise à jour pour Firefox"** (`viewtopic.php?t=143235`), last page; `&start=N` pages back in steps of the per-page post count shown on the page
   - each topic in the window that looks like a problem report
   - `https://forums.mozfr.org/app.php/feed/forum/5` (Atom, last 10 posts; kind `phpbb-feed`)
2. **The user asks the Geckozone admins** to allow `Claude-User` for read-only triage, and runs mozfr once the `robots.txt` change is live.

If neither happens, report on the other forums and list mozfr as not read.

## What to collect

For each forum, within the window:
1. **The release thread(s)**, all posts (camp-firefox board 2; the mozfr sticky topic if the user provided it).
2. **Listings of every board above**, until `last_post` is older than the window start. Then **every topic in the window that looks like a problem report**, all pages. Skip pure how-to questions, add-on recommendations and off-topic threads unless the replies show a regression.
3. Mozilla staff and long-time volunteers often answer on these forums. On camp-firefox, Sören Hentzschel and the moderators sometimes link the matching bug themselves, so check replies for `bugzilla.mozilla.org` links and `bug NNNNNN` before searching.

## Reading non-English reports

- **Read the original text.** Don't machine-translate first and judge the translation; idioms and technical shorthand ("ça rame", "hängt sich auf", "si pianta") change the severity you'd infer.
- Give each report a short English summary of the symptom, plus the most telling sentence quoted in the original language with an English translation.
- UI strings in reports are **localized**. Map them back to the English UI and the code feature before searching Bugzilla, e.g. "Chronik" = History, "Lesezeichen-Symbolleiste" = Bookmarks Toolbar, "Barra degli indirizzi" = Address bar, "Onglets" = Tabs, "Fehlerbehebungsmodus" / "Modalità risoluzione problemi" / "mode de dépannage" = Troubleshoot Mode. If a localized string itself looks wrong or truncated, that's a possible l10n bug for the locale's team (product `Mozilla Localizations`, component for the locale), not a Firefox regression.
- Check for **locale-specific causes**, which these forums surface and Reddit rarely does:
  - regional sites, banks and government portals (ELSTER, SPID/CIE, impots.gouv, FranceConnect, Ameli)
  - security suites common in the region (G DATA, Avira, ESET, Kaspersky)
  - dictionaries, hyphenation and translation (Firefox Translations) for that language
  - date/number formatting
  - keyboard layouts (AZERTY, QWERTZ, dead keys)
  - region-specific search engines and default settings
- Count distinct users **across forums**. A German and an Italian user reporting the same symptom are two users, and a symptom showing up in several languages is a trend signal.

## Matching to Bugzilla

Follow **Matching to Bugzilla** in `../reddit-triage/SKILL.md`: known `NNN` regressions first, then keyword searches per group, the version-timing guardrail, and the per-bug status line. In addition:
- Search with **English** keywords. Also search the reporter's distinctive original-language terms and the domain names of affected sites, because forum users sometimes file bugs in their own language.
- For a locale-only symptom, also look in `Mozilla Localizations :: <locale>` and in `Firefox :: Translations`.
- If a forum reply links a bug, verify that it matches before using it.

## Output format

Same buckets and formatting as **Output format** in `../reddit-triage/SKILL.md`, with these differences:
- Open with one line: pull time (UTC), time since release, the window, and per forum what was read, e.g. "camp-firefox: release thread (10 posts) + 14 topics from 5 boards; Mozilla Italia: 9 topics from 3 boards; mozfr: not read (robots.txt)".
- Tag every report with its forum: `[DE]`, `[IT]`, `[FR]`. Give each report its English summary, the original-language quote and translation, and its permalink.
- Add **Locale-specific** as its own section, between "New, no ticket" and "Not actionable", when there are reports that only affect one language or region (l10n string errors, regional sites, dictionaries). Name the component where each should go.
- In **Trending**, show which forums each topic appears in. If the user has also run `reddit-triage` in this conversation, say which groups are also on Reddit and which only show up in non-English forums.

## Re-runs

Follow **Re-runs** in `../reddit-triage/SKILL.md`. For forums, re-fetch the camp-firefox RSS feed and the first page of each board listing, diff topics by `last_post` against the previous pull, and re-fetch only the topics with new posts (the last page or two). Keep the seen post IDs per forum. These forums are much quieter than Reddit: a day after release, a single new report can be meaningful. A typical release produces a handful of relevant topics per forum, not dozens.

## Caveats to state when they apply

- A forum or board couldn't be fetched, or was skipped because of its `robots.txt` (name it).
- mozfr content came from pages the user saved, so it is limited to what they saved and when.
- Translations of quotes are yours. Note when a phrase is ambiguous.
- The `moz` MCP wasn't available, so REST was used for bug detail.
- A bug match is a best guess, not confirmed.
