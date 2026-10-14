# Let the forum-triage skill read forums.mozfr.org

Goal: keep the `.htaccess` block against AI crawlers, while letting Pascal's own Claude Code runs of the Relman `forum-triage` skill read the forum.

Approach: requests carrying a **secret header** bypass the block. A custom User-Agent alone isn't enough, since anyone can send any User-Agent and `robots.txt` is public. The skill fetches with `curl` from the local machine, so it can send the header. Claude Code's WebFetch can't, because it goes through Anthropic's servers.

## 1. Generate the secret

```sh
openssl rand -hex 24
```

## 2. `.htaccess`: exempt the header from the AI block

Add a condition to the existing block so it doesn't fire when the header matches.

If the block uses mod_rewrite:

```apache
RewriteCond %{HTTP:X-Geckozone-Triage} !=CHANGE_ME_LONG_RANDOM_STRING
RewriteCond %{HTTP_USER_AGENT} (ClaudeBot|Claude-User|anthropic-ai|GPTBot|...) [NC]
RewriteRule ^ - [F]
```

If it uses `SetEnvIf` with `Require`:

```apache
<If "%{HTTP:X-Geckozone-Triage} != 'CHANGE_ME_LONG_RANDOM_STRING'">
    # existing SetEnvIfNoCase / Require not env=... lines
</If>
```

Add a condition rather than a separate "allow" rule with `[L]` placed in front of the block. In `.htaccess`, `[L]` would also skip phpBB's own rewrite rules further down.

Make sure the skill's User-Agent (`GeckozoneTriage/1.0 ...`) doesn't match the block's User-Agent pattern. It doesn't contain "Claude", for example.

## 3. `robots.txt`: add a group for the skill's User-Agent

The skill re-reads `robots.txt` on every run and only reads mozfr if it's allowed. Add:

```
User-agent: GeckozoneTriage
Allow: /
Disallow: /adm
Disallow: /search.php
Disallow: /memberlist.php
Disallow: /ucp.php
```

Leave the existing `Claude-User` / AI agents `Disallow: /` group in place. Naming the token publicly is harmless, because the secret header is what actually lets requests through.

## 4. Store the secret locally, never in the Relman repo

Either in the shell profile:

```sh
export MOZFR_TRIAGE_KEY=CHANGE_ME_LONG_RANDOM_STRING
```

or in `~/.claude/settings.json`:

```json
{ "env": { "MOZFR_TRIAGE_KEY": "CHANGE_ME_LONG_RANDOM_STRING" } }
```

## 5. Check it works

Run from your own machine. Both should return 200:

```sh
curl -s -o /dev/null -w '%{http_code}\n' \
  -A "GeckozoneTriage/1.0 (+pchevrel@mozilla.com)" \
  -H "X-Geckozone-Triage: $MOZFR_TRIAGE_KEY" \
  https://forums.mozfr.org/viewforum.php?f=5

curl -s -o /dev/null -w '%{http_code}\n' \
  -A "GeckozoneTriage/1.0 (+pchevrel@mozilla.com)" \
  -H "X-Geckozone-Triage: $MOZFR_TRIAGE_KEY" \
  https://forums.mozfr.org/app.php/feed/forum/5
```

Without the header, a request with a `Claude-User` User-Agent should still return 403.

## 6. Then ask Claude to update the skill

Ask Claude Code to update `~/repos/github/Relman/.claude/skills/forum-triage/SKILL.md` so that it:

- fetches mozfr only when `MOZFR_TRIAGE_KEY` is set, sending `User-Agent: GeckozoneTriage/1.0 (+pchevrel@mozilla.com)` and the `X-Geckozone-Triage` header
- otherwise falls back to pages saved in the browser (colleagues without the key keep this behaviour)
- keeps the 3-second minimum between requests and a cap of a few dozen requests per run
- reads the Firefox board (`viewforum.php?f=5`), the site-problems board (`f=15`), the sticky update topic (`viewtopic.php?t=143235`), the Atom feed `app.php/feed/forum/5`, and the problem topics inside the release window, using the `phpbb-*` parser kinds that already exist in `scripts/forum_parse.py`

Then test it with a single request before a full run.
