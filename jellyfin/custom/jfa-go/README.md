# jfa-go (invites and accounts)

[jfa-go](https://github.com/hrfee/jfa-go) handles everything a viewer does
without the owner's help:

| Flow | What the viewer sees |
|---|---|
| **Invite** | Email with a one-use link (expires after 7 days). They pick a username, email and password. |
| **Confirm** | The account is only created after they click the link in the confirmation email. |
| **Welcome** | Email with TV sign-in steps (server address, Quick Connect, their username). |
| **My Account** | `https://<JOIN_HOST>/my/account`: change email or password, request a reset. |
| **Forgot password** | Jellyfin's login button goes to My Account; the reset link arrives by email. |

The admin UI and API are **never public**: reach them over LAN or Tailscale
(`ssh -L 8056:<JFA_LAN>:8056 <proxmox host>`, then `http://localhost:8056`).

## Pieces

| File | Where it goes |
|---|---|
| `config.example.ini` | `/etc/jfa-go/config.ini` (owner `jfa-go`, mode 600), placeholders filled from `.env` / the password manager |
| `jfa-go.service` | `/etc/systemd/system/` in the jfa-go LXC |
| `messages/*.md` | Admin → Settings → Messages, the matching message's custom content (see below) |
| `npm-advanced.conf` | NPM → proxy host `<JOIN_HOST>` → Advanced |
| `forgot-password.js` | Jellyfin → JavaScript Injector, one script, "Requires authentication" off |

Placeholders: `<JOIN_HOST>` public jfa-go host, `<JELLYFIN_PUBLIC_URL>` public
Jellyfin URL, `<JFA_LAN>` jfa-go LXC address, `<OWNER_NAME>` the name viewers
know the owner by. `{username}`-style fields are jfa-go's own and stay as is.

| Message file | jfa-go message |
|---|---|
| `invite.md` | Invite email |
| `email-confirmation.md` | Email confirmation |
| `welcome.md` | Welcome email |
| `password-reset.md` | Password reset |
| `user-page.md` | User page (My Account) |
| `post-signup.md` | Post-signup card (only shown when email confirmation is off) |

## Rebuild

1. LXC: Debian 12, unprivileged, 1 core, 512 MB RAM, 4 GB disk, static
   `<JFA_LAN>`, `onboot=1`, hostname `jfa-go`.
2. Install the `jfa-go_*_amd64.deb` matching the `0.6.0` release and
   `apt-mark hold jfa-go`. Create a `jfa-go` system user, `/etc/jfa-go` and
   `/var/lib/jfa-go` (both owned by it), install `jfa-go.service`, enable it.
3. In Jellyfin, create the `jfa-go` admin user (hidden from login screen) and
   a normal template user `new-user-template` with all libraries, no admin or
   management rights, and the home screen layout new users should get.
4. Copy `config.example.ini` to `/etc/jfa-go/config.ini`, fill in the
   placeholders, start the service. In the admin UI create the `default`
   profile from `new-user-template` (with home screen) and paste in the messages.
5. NPM: proxy host `<JOIN_HOST>` → `http://<JFA_LAN>:8056`, Block Common
   Exploits on, SSL the same as the Jellyfin host, Advanced = `npm-advanced.conf`.
   The allowlist only passes the signup, My Account and reset paths; everything
   else (admin UI, API) is 404.
6. Cloudflare tunnel: public hostname `<JOIN_HOST>` → NPM, same as Jellyfin.
7. Cloudflare rate limit (free plan allows one rule, 10 s period/block):
   5 requests per 10 s per IP, block, on

   ```
   (http.host eq "<JELLYFIN_HOST>" and http.request.uri.path in {"/Users/AuthenticateByName" "/users/authenticatebyname" "/Users/authenticatebyname"})
   or (http.host eq "<JOIN_HOST>" and (http.request.uri.path in {"/user/invite" "/reset" "/my/token/login" "/my/password"}
       or starts_with(http.request.uri.path, "/my/password/reset/")))
   ```

8. Email: SMTP2GO with a verified sender domain (SPF, DKIM and DMARC records
   in Cloudflare DNS), open/click tracking **off** on the SMTP user (tracked
   links look like phishing and land in spam).
9. Load `forgot-password.js` in JavaScript Injector.
10. Test: send an invite to yourself, sign up, confirm, sign in, reset the
    password, and check an expired invite is refused.

## Sending invites

Admin UI → Invites: 1 use, 7 days, profile `default`, send to the person's
email. jfa-go has no saved defaults for these, so set them each time (the form
starts at 30 minutes).

## Gotchas

- **Admins can't reset through jfa-go.** Reset clears the password before
  setting the new one and Jellyfin 10.11 refuses an empty admin password
  (500). Admins change their password in Jellyfin itself.
- **Changing a password signs out every device**, TVs included. The messages
  point viewers to Quick Connect to sign the TV back in.
- **Reset links die on restart**: jfa-go keeps reset PINs in memory.
- **The admin UI signs you out on reload or restart** when opened through the
  tunnel: its refresh cookie is scoped to `<JOIN_HOST>`. Sign in again.
- **With email confirmation on, the post-signup card is skipped**; the signup
  page only shows `success_message` (in `[ui]`), so the TV steps live there and
  in the welcome email.
- **Submit buttons sometimes need a second click** (signup and reset forms).
  Check the jfa-go log before clicking again.
- **SMTP2GO can hold mail at "Processed" for 5-10 minutes** while the sending
  domain is new; it is delivered afterwards.
