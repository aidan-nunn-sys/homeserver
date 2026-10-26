# Jellyfin Accounts and Invite Links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Family and friends join Jellyfin from a texted invite link, confirm their email, sign their TV in with Quick Connect, and reset forgotten passwords by email, without the owner's help.

**Architecture:** jfa-go 0.6.0 runs as a systemd service in a new small LXC on the Proxmox host. Only its signup, My Account and reset pages are published (Cloudflare Tunnel → Nginx Proxy Manager with a path allowlist); its admin UI stays LAN/Tailscale-only. Mail goes out through SMTP2GO from `noreply@<DOMAIN>`. Sanitized config and message templates live in `jellyfin/custom/jfa-go/`.

**Tech Stack:** jfa-go 0.6.0 (.deb), Debian 12 LXC (Proxmox `pct`), Nginx Proxy Manager, Cloudflare Tunnel / DNS / rate limiting, SMTP2GO, Python 3 stdlib for the export script (same style as `jellyfin/scripts/`).

**Spec:** `docs/superpowers/specs/2026-10-26-jellyfin-accounts-invites-design.md`

## Global Constraints

- This repo is public. Real domain, LAN IPs, user names, emails, keys and the SMTP login never appear in committed files; use the placeholders below. `python3 jellyfin/scripts/check_secrets.py` must pass on every commit (hook: `core.hooksPath jellyfin/scripts/hooks`).
- Placeholders: `<DOMAIN>`, `<JOIN_HOST>` (= `join.<DOMAIN>`), `<JFA_CTID>`, `<JFA_LAN>`, `<JELLYFIN_LAN>` (Jellyfin `http://host:8096`), `<NPM_LAN>`, `<JELLYSEERR_LAN>` (`http://host:5055`), `<SMTP_USER>`, `<SMTP_PASSWORD>`. Real values: homelab repo `services/jfa-go.md` (private) and server-local files only.
- Invite links: **1 use, expire after 7 days**. Accounts created from them **never expire** (user expiry off).
- Signup fields: username, email, password. Email confirmation required before the account works. Password rule: minimum 10 characters, no composition rules, shown live.
- Reset method: jfa-go "My Account" reset (Password Resets on, "Use reset link instead of PIN" on, "Set password through link" on, User Page on, General → "Use Jellyfin for Authentication" on).
- SMTP: `mail.smtp2go.com`, port 587, STARTTLS. From `noreply@<DOMAIN>`. The owner types `<SMTP_PASSWORD>` in themselves; the agent never sees or echoes it.
- jfa-go admin UI is never reachable through Cloudflare. Anything not on the public allowlist returns 404 on `<JOIN_HOST>`.
- No step may change an existing user's password or revoke their sessions. New Jellyfin users are hidden from the login page (`IsHidden`).
- Pin jfa-go 0.6.0; no auto-update.
- Server-changing steps (DNS, Cloudflare, NPM, new CT, Jellyfin users) need the owner's OK before running; ask once per task with the exact change listed.
- Commits: one line, no AI attribution trailers.

## Review Focus

1. **Typo'd email at signup.** If the person mistypes their email, the confirmation never arrives. Expected: the owner can see the pending signup and the invite is not burned (or the owner can issue a new one in under a minute). Task 9 step 3 tests which jfa-go does and the README documents the recovery.
2. **Rate-limit testing must not lock out real people.** Jellyfin locks an account after 3 bad attempts. Expected: tests use a username that does not exist. Task 7 step 4.
3. **Confirmation link opened on another device** (sign up on phone, tap link on laptop). Expected: it still confirms. Task 9 step 2.
4. **Forgot password with an email or username not on file.** Expected: a generic "if this account exists, we sent a link" response, no hint whether the account exists. Task 9 step 5.
5. **Existing TV sessions survive setup.** Expected: the device/session baseline from Task 1 matches afterward for every existing user. Task 9 step 7.

---

### Task 1: Baseline and inbound mail check

**Files:** none committed (baseline is server-local).

- [ ] **Step 1: Save a device baseline.** Using `jellyfin/scripts/api.py` `Client`, `GET Devices` and write `{UserId: sorted device Ids}` to `/tmp/jfa-baseline-devices.json` on this machine. Print only the count per user, not names.
- [ ] **Step 2: Confirm inbound mail works.** The owner sends a message from a non-forwarding address to `admin@<DOMAIN>`. Check Cloudflare Email Routing → Activity log shows it "Delivered" and it is in the owner's inbox. If not delivered, stop and debug before Task 2 (SMTP2GO sender verification mails go to this address).

### Task 2: Sender domain (SPF, DKIM, return path)

**Files:** none.

- [ ] **Step 1:** Owner (or agent in the owner's browser, with OK) adds `<DOMAIN>` as a Verified Sender Domain in SMTP2GO, keeping its default tracking/return-path subdomains. Record the CNAMEs it lists.
- [ ] **Step 2:** In Cloudflare DNS add those CNAMEs **DNS only (grey cloud)**. Edit the existing apex SPF TXT to exactly one record containing both `include:_spf.mx.cloudflare.net` and `include:spf.smtp2go.com`, ending `~all`.
- [ ] **Step 3: Verify.** DoH queries (`cloudflare-dns.com/dns-query`) return each CNAME, and exactly one TXT at the apex starting `v=spf1`. SMTP2GO shows the domain Verified.
- [ ] **Step 4:** Add `_dmarc.<DOMAIN>` TXT `v=DMARC1; p=none; rua=mailto:admin@<DOMAIN>` if none exists (helps Gmail placement). Verify with DoH.

### Task 3: Jellyfin service account and template user

**Files:** none committed.

- [ ] **Step 1:** Create Jellyfin user `jfa-go` (administrator, hidden, remote access off is fine since jfa-go connects over LAN) with a 32-byte random password generated on the server and written only to the jfa-go config in Task 5. Creating users revokes nothing.
- [ ] **Step 2:** Create user `new-user-template`: not admin, hidden, random unknown password, library access and playback permissions copied from a typical existing non-admin user's `Policy` (owner confirms which user), not disabled.
- [ ] **Step 3: Verify.** `GET Users` shows both as `IsHidden: true`; template `IsAdministrator: false`, `IsDisabled: false`. Device baseline unchanged.

### Task 4: jfa-go container

**Files:** none committed (Task 8 captures config).

- [ ] **Step 1:** `pct create <JFA_CTID>` from `debian-12-standard_12.12-1_amd64`: unprivileged, 1 core, 512 MB RAM, 4 GB on `local-lvm`, static `<JFA_LAN>/24` on `vmbr0`, gateway as other CTs, `onboot=1`, hostname `jfa-go`.
- [ ] **Step 2:** Install `jfa-go_amd64_v0.6.0.deb` from the GitHub release (verify the release checksum if published). Run as a dedicated `jfa-go` system user with config `/etc/jfa-go/config.ini` and data `/var/lib/jfa-go`, port 8056, via a systemd unit `jfa-go.service` (`Restart=on-failure`). Hold the package (`apt-mark hold jfa-go`).
- [ ] **Step 3: Verify.** `systemctl is-active jfa-go` → `active`; from the Proxmox host `curl -s -o /dev/null -w '%{http_code}' http://<JFA_LAN>:8056/` → `200`. `pct snapshot <JFA_CTID> pre-setup` succeeds (this CT has no GPU or bind mounts).

### Task 5: jfa-go setup

**Files:** none committed.

- [ ] **Step 1:** Run the setup wizard from the LAN/Tailscale browser. Jellyfin `<JELLYFIN_LAN>`, user `jfa-go` + its password. Email: SMTP `mail.smtp2go.com:587` STARTTLS, user `<SMTP_USER>`; **the owner types `<SMTP_PASSWORD>`**. From `noreply@<DOMAIN>`, sender name = the server's display name.
- [ ] **Step 2:** Settings: External URL `https://<JOIN_HOST>`; "Use Jellyfin for Authentication" on; admin URL path changed from the default to a non-obvious path (record it in homelab only); Password Resets with the three link options on; User Page on; Email confirmation on; password min length 10, other rules off; Jellyseerr integration on with `<JELLYSEERR_LAN>` and a Jellyseerr API key; Ombi, Discord, Telegram, Matrix, CAPTCHA off; invite defaults 1 use / 7 days / user expiry off.
- [ ] **Step 3:** Profile `default` from `new-user-template` (policy, display preferences/home layout), set as default.
- [ ] **Step 4: Verify.** Send jfa-go's test email to the owner; it arrives in the inbox (not spam) within 1 minute, and Gmail "Show original" shows SPF, DKIM and DMARC `PASS` for `<DOMAIN>`.

### Task 6: Messages and the "You're in" page

**Files:**
- Create: `jellyfin/custom/jfa-go/messages/post-signup.md`, `email-confirmation.md`, `password-reset.md`, `user-page.md`

- [ ] **Step 1: Verify the Quick Connect path.** On Jellyfin web 10.11 signed in as a test user, find the shortest route to the "authorize Quick Connect code" screen (user menu → Quick Connect; check whether `#/quickconnect` deep-links). Record the exact URL/steps.
- [ ] **Step 2: Write `post-signup.md`.** Short, phone-first. Order: "You're in"; **On your TV** (Quick Connect: open Jellyfin app → enter server `<JELLYFIN_PUBLIC_URL>` in large text → choose Quick Connect → on this phone tap the button to sign in to Jellyfin and enter the 6-digit code); **Or type it in** (server, username, password); **Forgot your password later?** link to `https://<JOIN_HOST>/my/account`. Use jfa-go template variables where available; `<JELLYFIN_PUBLIC_URL>` is filled in when pasted.
- [ ] **Step 3:** Write the confirmation, reset and user-page texts: one sentence plus the button. `user-page.md` says changing the password signs out TVs (how to sign back in with Quick Connect), and that username changes go through the owner.
- [ ] **Step 4:** Paste them into jfa-go (Settings → Messages/Customization) with real values, preview each.
- [ ] **Step 5: Forgot password on the web login.** Add a JavaScript Injector script (stored as `jellyfin/custom/jfa-go/forgot-password.js`, `<JOIN_HOST>` placeholder) that makes the login page's "Forgot Password" button open `https://<JOIN_HOST>/my/account` instead of Jellyfin's PIN flow. Verify in a private browser window on the web login page. (Roku can't be changed; the messages cover it.)
- [ ] **Step 6: Commit** `jellyfin/custom/jfa-go/messages/` and `forgot-password.js` (placeholders only).

### Task 7: Publish the public pages only, plus rate limits

**Files:**
- Create: `jellyfin/custom/jfa-go/npm-advanced.conf` (placeholders)

- [ ] **Step 1: Discover the public paths.** On the LAN, open an invite page, sign up, confirm, open My Account, request a reset, with devtools recording. List every path prefix requested (pages, static assets, translations, API calls). Expected shape: `/invite/`, `/my/`, `/reset`, static asset and language prefixes, and the user-facing API calls.
- [ ] **Step 2:** Write `npm-advanced.conf`: `location` blocks that proxy only those prefixes to `<JFA_LAN>:8056` with the headers from the jfa-go reverse-proxy docs (`Host`, `X-Real-IP`, `X-Forwarded-For`, `X-Forwarded-Proto`, `X-Forwarded-Host`, `proxy_buffering off`), and `location / { return 404; }`.
- [ ] **Step 3:** NPM proxy host `<JOIN_HOST>` with that advanced config and block-exploits on. Cloudflare Tunnel public hostname `<JOIN_HOST>` → NPM, same as the Jellyfin hostname. Cloudflare: respect strong ETags for `<JOIN_HOST>` (jfa-go docs).
- [ ] **Step 4: Rate limit.** One Cloudflare rate-limiting rule (fit the plan's limits): POST to `jellyfin.<DOMAIN>` path `/Users/AuthenticateByName` or POST to `<JOIN_HOST>`, per IP, block when over the threshold (start: 10 requests / 1 minute). Test with a **nonexistent username** only: 15 quick failed sign-ins get blocked; one normal sign-in afterward from another network works.
- [ ] **Step 5: Verify from outside the LAN.** `https://<JOIN_HOST>/invite/<test-code>` → 200; `/my/account` → 200; `/` → 404; the admin path → 404; `GET /users`, `/invites`, `/config` → 404.
- [ ] **Step 6: Commit** `npm-advanced.conf`.

### Task 8: Capture config in the repo

**Files:**
- Create: `jellyfin/scripts/export_jfa.py`, `jellyfin/tests/test_export_jfa.py`, `jellyfin/custom/jfa-go/config.example.ini`, `jellyfin/custom/jfa-go/README.md`
- Modify: `jellyfin/README.md` (Custom additions list)

**Interfaces:**
- Consumes: `sanitize.Sanitizer` (existing; `sanitize(obj, context)` returns the sanitized object and records new placeholders in `.new`).
- Produces: `export_ini(text: str, sanitizer: Sanitizer) -> str`.

- [ ] **Step 1: Write failing tests** in `test_export_jfa.py`:
  - `test_secret_keys_become_placeholders`: `[email]\npassword = x` and `[jellyfin]\npassword = y` → values `<JFA_EMAIL_PASSWORD>` and `<JFA_JELLYFIN_PASSWORD>`.
  - `test_urls_and_ips_sanitized`: a server URL built at runtime from `'.'.join(['192','168','0','9'])` becomes a `<HOST_N>` placeholder.
  - `test_non_secret_values_kept`: `[password_validation]\nlength = 10` stays `10`.
  - `test_section_order_preserved`.
- [ ] **Step 2:** Run `python3 -m unittest discover -s jellyfin/tests -t jellyfin/tests`; expect the 4 new tests to fail (module missing).
- [ ] **Step 3: Implement `export_ini(text, sanitizer) -> str`** in `export_jfa.py`: parse with `configparser` (interpolation off, case preserved), replace values of keys named `password`, `api_key`, `token`, `secret` with `<JFA_<SECTION>_<KEY>>`, pass the rest through `sanitizer.sanitize`, write back in order. CLI: `export_jfa.py <config.ini> > jellyfin/custom/jfa-go/config.example.ini`, saving new placeholders to the env file like `export.py`.
- [ ] **Step 4:** Run tests; expect all pass.
- [ ] **Step 5:** Copy `/etc/jfa-go/config.ini` from the CT to `/tmp`, run the export, delete the `/tmp` copy. `check_secrets.py --all` passes (apart from the known `curator.py` path).
- [ ] **Step 6: README** for `jellyfin/custom/jfa-go/`: what it is, rebuild steps (Tasks 2–7 condensed), backup (`vzdump <JFA_CTID>` or tar `/etc/jfa-go` + `/var/lib/jfa-go`), how to make an invite, typo'd-email recovery (from Task 9), and that the admin UI is LAN/Tailscale only. Add a bullet to `jellyfin/README.md` Custom additions.
- [ ] **Step 7: Commit.**

### Task 9: End-to-end check (with the owner)

**Files:** none.

- [ ] **Step 1:** Create an invite; open it on a phone off Wi-Fi; sign up with a test username and an email the owner controls. Confirmation email arrives within ~1 minute, in the inbox.
- [ ] **Step 2:** Tap the confirmation link on a **different device** than signup; the account activates; the "You're in" page shows. Reusing the invite link is refused.
- [ ] **Step 3:** New invite: sign up with a deliberately wrong email. Record whether the invite is used up and how the owner recovers (cancel pending signup / new invite). Put the answer in the jfa-go README.
- [ ] **Step 4:** On a Roku: add the server, sign in via Quick Connect from the phone. Sign out, sign in again with the typed fallback.
- [ ] **Step 5:** My Account: change email; request reset by username and by email; reset link sets a new password that works in Jellyfin and Jellyseerr. Request a reset for an unknown username/email: response is generic.
- [ ] **Step 6:** Expired invite (create one with a short expiry for the test) is refused.
- [ ] **Step 7:** Compare `GET Devices` with `/tmp/jfa-baseline-devices.json`: no existing user lost a device. Delete the test accounts (jfa-go and Jellyseerr).

### Task 10: Record it

**Files (homelab repo, private):** `services/jfa-go.md` (create from template, real IPs/CTID/admin path), `decisions/0013-...md` (status → accepted, link the spec), `CHANGELOG.md`, `BACKLOG.md` (remove accounts item; add the existing-user rollout and username moves as next), `services/jellyfin.md` (Users and access section).

- [ ] **Step 1:** Write the docs, commit and push homelab.
- [ ] **Step 2:** Owner rotates the SMTP2GO user's password (shared in chat) and updates it in jfa-go Settings; send a test email again.
