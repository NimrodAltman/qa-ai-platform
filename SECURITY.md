# Security

This is a local, single-process tool built as a portfolio project — not a
hosted multi-tenant product. This document says what was reviewed, what was
found and fixed, and what's left on purpose, so the trade-offs are explicit
rather than silent.

## What was reviewed

A manual review covering: session/auth handling, role enforcement on every
API route, SQL usage, file upload and path handling, the LLM-call surface
(prompt construction, no shell/eval/pickle anywhere in the codebase), the
frontend's handling of server-returned data, HTTP response headers, and
third-party dependency versions. Secret handling was checked separately:
`.env` and the local run database were confirmed never committed, in the
full git history, not just the current tree.

## Fixed

- **Session-signing secret.** The cookie-signing key had a hardcoded
  fallback value, present in this public repo, usable to forge a valid
  login session for any user without a password. Fixed: with no
  `SESSION_SECRET` set, a random key is generated per process instead.
  Trade-off: sessions no longer survive a server restart unless
  `SESSION_SECRET` is set explicitly.
- **Seeded admin credential.** The first run created an `admin` account
  with a fixed, published password. Fixed: the password is now generated
  randomly and printed once to the console on first startup.
- **Output path handling.** A task/tag value supplied by the caller was
  used directly in the path of the file written to disk, without
  restricting its characters. Fixed: it's now reduced to a safe character
  set before being used in a path.
- **Unescaped data in the UI.** Several screens built HTML by concatenating
  server-returned values (tags, filenames, feedback comments, usernames)
  directly into the page, without escaping. Since an admin's view includes
  data submitted by other users, this was more than self-inflicted damage.
  Fixed: all such values now go through an escaping helper before being
  inserted into the page. Also added response headers (Content-Security-
  Policy, X-Frame-Options, X-Content-Type-Options, Referrer-Policy) as a
  second layer; CSP still permits inline scripts/styles because the UI uses
  inline event handlers, so it does not block an injected `<script>` tag on
  its own — the escaping fix is what actually closes that gap.
- **Leftover temp files.** Every uploaded specification was written to a
  temp file that was never deleted. Fixed: it's removed after each request,
  whether generation succeeds or fails.

Each fix has an automated test that fails against the prior code and passes
against the fix.

## Known limitations (left as-is, deliberately)

This is a tool for local or small-trusted-group use, not a public service,
so the following were judged not worth the added complexity right now:

- **No login rate limiting.** Repeated login attempts aren't throttled or
  locked out. Acceptable for a tool not meant to be internet-facing with
  untrusted traffic; would need addressing before that changes.
- **No upload size limits.** A very large file or image could use a lot of
  memory or disk, or run up Claude API usage, before any per-request cap
  kicks in.
- **Exception text returned to the client.** A failed generation returns
  the raw Python exception message, which can include internal paths.
  Useful for local debugging; would want a generic message in anything
  public-facing.
- **Session cookie lifetime.** Cookies are `HttpOnly` and `SameSite=Lax`,
  but a copied cookie stays valid for its ~2-week lifetime; there's no
  server-side session store to revoke it early, and "log out" only clears
  the browser's copy.
- **Password policy.** No minimum length or complexity is enforced on
  user-chosen passwords.

None of these affect data outside the operator's own machine/database under
normal use; they matter only if the instance is exposed to untrusted users
or the network, which isn't the deployment this project is built for today.
