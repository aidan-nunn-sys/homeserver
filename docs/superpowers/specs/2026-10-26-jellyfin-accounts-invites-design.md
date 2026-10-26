# Jellyfin accounts: invite links, email confirmation, self-service resets

Date: 2026-10-26. Status: draft for review.
Background decision: homelab ADR-0013 (private repo). This repo is public, so
real values (domain, users, keys, SMTP login) appear here only as placeholders
such as `<DOMAIN>`; real values live in gitignored env files on the server.

## Why

The Jellyfin server is shared with about 15 family and friends, all people the
owner knows, plus one friend-of-a-friend with no phone number on file. Most
people watch on a **TV, mainly the Roku app** (native, not the web UI), then
phones, sometimes laptops. Support requests are almost always "how do I find
the server" and "how do I log in". Today the owner creates every account by
hand, and most usernames and passwords are the person's first name.

Success: the owner texts a link, and the person ends up watching on their TV
without calling the owner. Signup should be fast with no hiccups.

## Goals

1. **Invite links.** The owner creates a link and texts it. Each link works
   **once** and **expires after 7 days**.
2. **One short signup page, phone-first.** Fields: **username, email,
   password**. Password rules are shown live as the person types, so nobody
   submits and then hits an error.
3. **Email confirmation before the account works.** After submitting, the
   person gets a confirmation email from `noreply@<DOMAIN>`; the Jellyfin
   account is not usable until they tap the link. This proves the address is
   real so resets reach them.
4. **"You're in" page after confirming**, offering both TV paths:
   - **Quick Connect (main path):** the TV app shows a 6-digit code; the
     person enters it on their phone and the TV signs in with no typing of a
     password on a remote.
   - **Written fallback:** what to type on the TV, with the server address in
     large text.
5. **My Account page** where each person can add or change their email and
   change their password, and request a password reset by email if they
   forgot it.
6. **Password resets by email**, from `noreply@<DOMAIN>` via SMTP2GO, with
   SPF and DKIM set up so mail lands in the inbox, not spam.
7. **Brute-force protection:** a Cloudflare rate-limit rule on the Jellyfin
   sign-in endpoint and on the new signup/My Account pages, on top of
   Jellyfin's existing lockout (3 bad attempts; admin 5).
8. **Jellyseerr keeps working** with the same Jellyfin login; new people's
   email is copied into Jellyseerr for request notifications.
9. **Config captured in this repo** (sanitized) so the setup can be rebuilt,
   matching the existing `jellyfin/` snapshot approach.

## Non-goals

- Forced password change at next sign-in (rejected: a Jellyfin password change
  signs the person out of every other device, TVs included).
- Text-message (SMS) resets.
- Authentik / single sign-on; Wizarr.
- Migrating existing users in this build. Existing people get a heads-up text
  and use My Account to add their email; that rollout is a follow-up (below).
- Closing public access to Immich or Nextcloud (parked by the owner).

## Anti-goals (failure even if it "works")

- Anything in this build that signs an existing person out of their TV.
- A new public login that is not backed by Jellyfin accounts.
- Any secret, real domain, user name, email or IP committed to this public
  repo (the pre-commit `check_secrets` hook must pass).
- Confirmation or reset emails that land in spam or arrive minutes late.

## Decided

- **Tool: jfa-go** (`hrfee/jfa-go`): invites with expiry and use limits,
  optional email confirmation, password requirements, profiles, My Account
  page, link-based resets, Jellyseerr integration. Pin a release version; no
  auto-updates.
- **Reset method: jfa-go "My Account" reset** (wiki: Password Resets, method
  4). Needs: Password Resets on, "Use reset link instead of PIN" on, "Set
  password through link" on, User Page on, General → "Use Jellyfin for
  Authentication" on. jfa-go does not need Jellyfin's config directory for
  this method.
- **Email: SMTP2GO** account already created and activated. SMTP server
  `mail.smtp2go.com`, port 587 with STARTTLS (alternatives 2525/8025; SSL on
  465). An SMTP user exists; its username and password go only in the server's
  private env/config (`<SMTP_USER>`, `<SMTP_PASSWORD>`). The owner enters the
  password on the server themselves and will rotate it after setup (it was
  shared in chat).
- **Receiving mail for `<DOMAIN>`:** Cloudflare Email Routing is enabled
  (MX + SPF `include:_spf.mx.cloudflare.net`), forwarding `admin@<DOMAIN>` to
  the owner's inbox. Inbound delivery was not yet confirmed at time of writing.
- **Sender domain:** verify `<DOMAIN>` in SMTP2GO and add its DKIM and
  return-path CNAMEs in Cloudflare DNS. The existing SPF TXT record must be
  **merged** (one SPF record with both includes), never duplicated.
- **Invite profile:** new accounts copy a template user's settings (library
  access, home screen layout, permissions) and are hidden from the public
  login page (`IsHidden`), like all current users.
- **Public access:** jfa-go served at its own subdomain (e.g.
  `join.<DOMAIN>`) through the existing Cloudflare Tunnel → Nginx Proxy
  Manager path.

- **Accounts never expire.** Only the invite link expires (7 days); jfa-go's
  per-invite "user expiry" stays off.
- **jfa-go signs in to Jellyfin as a dedicated admin service account**
  (jfa-go uses an admin username/password, not an API key), not the owner's
  own admin account. Creating it signs no one out. *(Design author's call.)*
- **Template user:** a dedicated hidden template user with a long random
  password nobody knows holds the settings new accounts copy. It is not
  disabled, because profiles copy the account policy and new accounts would
  start disabled. *(Design author's call.)*
- **jfa-go's admin pages are not public.** Only the invite signup, My Account
  and reset pages are reachable from the internet; the admin UI (creating
  invites, managing users) is reached only from home or over Tailscale, never
  through Cloudflare (owner's decision 2026-10-26).

## Left to the builder (decide and note it in the plan)

- Where jfa-go runs (new small LXC on the Proxmox host vs. an existing Docker
  host). It only needs HTTP access to Jellyfin (and Jellyseerr) and a
  persistent data directory. Do not use the container that hosts the
  owner's portfolio site.
- Exact password rule (suggestion: minimum 10 characters, no composition
  rules).
- Subdomain name and exact Cloudflare rate-limit thresholds.
- Wording and layout of the "You're in" page, confirmation and reset emails
  (jfa-go supports Markdown messages). Keep them short and phone-friendly;
  the server address must be easy to read.
- How the person enters the Quick Connect code on their phone. Jellyfin's
  Quick Connect authorize screen requires being signed in on the phone
  (web UI: user settings → Quick Connect). Verify the shortest real path
  (e.g. a button from the "You're in" page to the Jellyfin web sign-in, then
  to the Quick Connect screen) and test it on an actual Roku.
- Whether the web login page's "Forgot password" should be pointed at the
  My Account reset page (possible via the JavaScript Injector plugin already
  installed). The Roku app can't be changed; the "You're in" page and emails
  should mention the My Account address.
- Username changes: jfa-go's My Account page does not appear to support
  them. Unless the builder finds otherwise, the owner renames on request
  (a rename does not sign anyone out). Say so on the My Account page.
- Backup of jfa-go's data directory, and how its config is captured
  sanitized in this repo (reuse `jellyfin/scripts/sanitize.py` and the
  `check_secrets` hook where practical).

## Verification (must pass before it's called done)

1. DNS: SPF single record with both includes; DKIM verified in SMTP2GO.
2. End-to-end with a test email the owner controls: create invite → open on a
   phone → sign up → confirmation email arrives within ~1 minute, in the inbox
   (not spam) → confirm → "You're in" page.
3. The new account signs in on a Roku via Quick Connect, and separately with
   the written fallback.
4. The invite link refuses a second use, and an expired link is refused.
5. My Account: add/change email works; a reset email arrives and the reset
   page sets a new password that works in Jellyfin and Jellyseerr.
6. No existing user's sessions were revoked during setup (compare active
   sessions/devices before and after).
7. Rate limits trigger on repeated failed sign-ins and do not affect a normal
   sign-in.
8. `check_secrets` passes on everything committed.

## Follow-up (separate, after this works)

- Existing people: heads-up text with the My Account link; they sign in with
  their current credentials and add their email. Password change optional,
  with a warning that it signs out their TV and how to sign back in with
  Quick Connect.
- Move usernames off plain first names (renames don't sign people out).
