# Reusing Puzzle Parlor's license system for Color Cafe

Resolves `.scratch/color-cafe-spec/issues/06-license-reuse.md`. Researched 2026-10-19 against the
Puzzle Parlor source at `/home/user/puzzle-parlor` (commit `6770a2b` on `main`) and Cloudflare's
own documentation. Every claim below cites the file or doc it came from. Secrets are referred to by
variable name only.

## TL;DR

- The license system is 220 lines across five files and is already ~80% generic. The
  product-specific parts are: the `PP-` code prefix, the email/subject copy, the Pages project
  name and KV namespace id in `wrangler.toml`, the `PUZZLE_PRICE_CENTS` setting name, the
  support inbox, and a handful of `jig-*` localStorage keys plus copy in the client.
- **Design A (separate deployment, own KV)**: copy five files, change ~12 lines, create one KV
  namespace and one Pages project, add a second Square webhook subscription. Zero code change to
  Puzzle Parlor. Hidden trap: Square sends every payment on the account to every webhook
  subscription, so if both apps cost the same, each purchase mints a code in *both* apps unless
  the webhook also checks what was bought.
- **Design B (one shared service with a `product` field)**: ~40 changed lines inside
  Puzzle Parlor's `functions/`, Color Cafe's client calls Puzzle Parlor's API cross-origin
  (CORS is already `*`). One admin page, one webhook, one KV. The village pass becomes a data
  change (`products:['pp','cc']`), not an architecture change. Risk: every Color Cafe license
  change redeploys the code that Puzzle Parlor customers' codes depend on.
- **Recommendation: Design B**, done as a two-step refactor inside `puzzle-parlor` (first make
  the code product-aware with `pp` as the default, verify existing codes still work, *then* add
  `cc`). Reasoning in section 6.

---

## 1. What is product-specific vs generic in the current code

Files (line counts from `wc -l`):

| File | Lines | Role |
|---|---|---|
| `functions/_lib/license.js` | 62 | KV helpers, code format, mint/activate/deactivate, admin auth, Resend email |
| `functions/api/license/[action].js` | 42 | HTTP router: `status`, `activate`, `deactivate` (public); `mint`, `list`, `revoke`, `unrevoke`, `settings`, `testemail` (admin) |
| `functions/api/square/webhook.js` | 43 | Verifies Square HMAC, filters by price, mints + emails a code |
| `functions/api/contact.js` | 20 | Support form → Resend (imports `json`, `CORS`, `cfg` from license.js) |
| `public/admin.html` | 53 | Admin UI: settings, mint, list, revoke |
| `wrangler.toml` | 7 | Pages project name + KV binding |
| `.github/workflows/deploy.yml` | — | Copies 7 GitHub secrets to the Pages project, then `pages deploy` |
| `tools/tests/lic_test.mjs` | — | In-memory KV test of all of the above; **passes today** (`node tools/tests/lic_test.mjs` → `TAX TOLERANCE TESTS PASSED`) |

### Generic (would work for Color Cafe unchanged)

Source: `functions/_lib/license.js`

- `CORS` (`access-control-allow-origin: *`), `json()` helper (lines 2–3)
- `MAX_DEVICES=3` (line 4)
- `cfg(env,name)`: KV `cfg:<NAME>` with env var fallback (line 7)
- `ALPHABET` (no 0/O/1/I) and the 12-char random body of `makeCode()` (lines 8–11)
- `licKey`, `getLicense`, `putLicense` (lines 20–22)
- `mint()` with 5 retries for uniqueness; license record shape
  `{code,c,note,email,src,order,devices:[],max,revoked}` (lines 23–26)
- `activate()`/`deactivate()` device-slot logic and all error codes
  (`bad_code`, `bad_device`, `unknown`, `revoked`, `device_limit`) (lines 28–48)
- `adminOk()` constant-time compare against `env.LICENSE_ADMIN_KEY` (lines 49–53)
- The Resend POST itself in `sendCodeEmail()` (line 59)

Source: `functions/api/license/[action].js`: the whole router, admin gate, `settings`
read/write/masking, `mint` batch of up to 100, `list` (reads up to 300 of the first 1000
`lic:` keys), `revoke`/`unrevoke`. Nothing in this file names the product.

Source: `functions/api/square/webhook.js`: HMAC verification (lines 6–14), order/customer email
lookup (lines 16–24), `sqpay:<id>` dedupe with 90-day TTL (lines 34–35, 41).

Source: `public/index.html` client (lines 410–468): `deviceId()`, `licCall()`, `redeem()`,
`removeDevice()`, `recheckLicense()` (re-validates every 7 days; clears the local license only on
`unknown`/`revoked`/`device_limit`, line 467), `refreshLockConfig()` (locking is on only when the
server reports `locking:true`, i.e. `LICENSE_ADMIN_KEY` is set — `[action].js` line 7).

### Product-specific (must change or be parameterised)

| Where | What | Line |
|---|---|---|
| `license.js` | `PP-` prefix in `makeCode()` and `normCode()` (which also strips a leading `PP`) | 12, 16, 18 |
| `license.js` | `SETTING_NAMES` includes `PUZZLE_PRICE_CENTS` | 6 |
| `license.js` | KV binding name `env.PROGRESS` (hard-coded in every helper; also used by `contact.js`, `webhook.js`, `[action].js`) | 7, 21, 22 |
| `license.js` | Email body: "Thank you for buying Puzzle Parlor!", the how-to steps ("Tap Unlock at the top of the puzzle gallery"), subject `Your Puzzle Parlor unlock code`, default `APP_URL` `https://puzzle-parlor-app.pages.dev/` | 57–59 |
| `webhook.js` | Reads `PUZZLE_PRICE_CENTS` and accepts only payments within price..price×1.17 USD | 31–33 |
| `contact.js` | `SUPPORT_TO='puzzles@kandyphoenix.com'`, subject prefix `Puzzle Parlor help:` | 3, 17 |
| `admin.html` | `SETTINGS` label list (same names), page title/copy | 44 |
| `wrangler.toml` | `name = "puzzle-parlor-app"`, KV `id = "1d77e8f1b9c74f8f9ce22b5b279f697a"` | 1, 7 |
| `deploy.yml` | `--project-name=puzzle-parlor-app` (3 places), account id, secret list | — |
| `index.html` | localStorage keys `jig-lic`, `jig-dev`, `jig-lockcfg`; `WEB_SALES` host regex `/\.pages\.dev$\|kandyphoenix\.com$/`; `API_ROOT` fallback `https://puzzle-parlor-app.pages.dev/`; placeholder `PP-XXXX-XXXX-XXXX` (3 places); `FREE_PER_CAT=2` free-tier rule; all unlock-dialog copy | 300, 412–418, 429–432, 561, 296–305 |
| `buy.html` | `CHECKOUT_URL` (Square payment link), price copy, `?paid=1` banner, `PP-XXXX` placeholder | 359, 364, 350 |

### One structural fact that matters for both designs

The license data lives in the **same KV namespace as progress sync**, under key prefixes
(`license.js` line 1; `SELLING.md` "live in the PUZZLE_PROGRESS KV namespace under `lic:` keys").
Prefixes in use today, from grepping `functions/`: `lic:` (licenses), `cfg:` (admin settings),
`sqpay:` (webhook dedupe), `contact:` (rate limit), and `<synccode>:index` / `<synccode>:jig:…`
(progress, `functions/api/p/[code]/[key].js` line 1). Any shared-namespace design must keep its
new keys out of those prefixes.

### Purchase → code delivery today (for context)

`buy.html` line 359 hard-codes a Square payment link; the buttons go straight to Square. Square
posts `payment.created`/`payment.updated` to `/api/square/webhook`; the function checks the HMAC,
checks the amount against `PUZZLE_PRICE_CENTS`, mints a code with `src:'square'`, emails it via
Resend, and records `sqpay:<payment id>` so retries do not mint twice (`webhook.js` lines 25–42).
Square redirects the buyer back to `buy.html?paid=1`, which shows "your code is on its way"
(`buy.html` line 364). Manual sales go through `admin.html` → `mint` (`SELLING.md`, "Manual sales").

---

## 2. Two designs with concrete file changes

### Design A: separate deployment, own KV namespace, own product id

Color Cafe gets its own Pages project (`color-cafe-app`), its own KV namespace, and a copy of the
five files. Puzzle Parlor is untouched.

Cloudflare's docs confirm this is the ordinary setup: a KV binding is just `binding` (a name you
choose) + `id` (the namespace), configured per Pages project in `wrangler.toml` or the dashboard
(https://developers.cloudflare.com/pages/functions/wrangler-configuration/ "KV namespaces";
https://developers.cloudflare.com/kv/concepts/kv-namespaces/).

Changes (all in the Color Cafe repo):

1. **`wrangler.toml`** (new): `name = "color-cafe-app"`, `[[kv_namespaces]] binding = "KV"`
   (or keep `PROGRESS` to avoid touching the copied code), `id = "<new namespace id>"`.
   Create the namespace with `wrangler kv namespace create` or the dashboard.
2. **`functions/_lib/license.js`** (copy, then edit):
   - line 12, 16, 18: `PP` → `CC` (three places). Recommend hoisting to
     `const PREFIX='CC'` and using it in both functions.
   - line 6: `PUZZLE_PRICE_CENTS` → keep the same name (least change) or rename to
     `PRICE_CENTS`; whichever you pick must match `webhook.js` line 31, `admin.html` line 44,
     and `deploy.yml`.
   - lines 57–59: Color Cafe email copy, subject, default `APP_URL`.
   - If the binding is renamed from `PROGRESS`, replace `env.PROGRESS` in this file (3 places),
     `[action].js` (4 places), `webhook.js` (4 places), `contact.js` (2 places).
3. **`functions/api/license/[action].js`**: copy verbatim.
4. **`functions/api/square/webhook.js`**: copy; see the price-collision trap below.
5. **`functions/api/contact.js`**: copy; change `SUPPORT_TO` and the subject prefix (lines 3, 17).
6. **`public/admin.html`**: copy; change the title and `SETTINGS` labels (line 44).
7. **`.github/workflows/deploy.yml`**: copy; `puzzle-parlor-app` → `color-cafe-app` (3 places).
   Add the same 7 secrets to the Color Cafe GitHub repo. `RESEND_API_KEY`,
   `LICENSE_FROM_EMAIL`, `LICENSE_REPLY_TO` can be the same values; `LICENSE_ADMIN_KEY` should be
   a different value (so a leaked Color Cafe admin key cannot revoke Puzzle Parlor codes).
8. **Square**: a second webhook subscription pointing at
   `https://color-cafe-app.pages.dev/api/square/webhook` (per `SELLING.md` "Square setup"),
   and a second payment link for Color Cafe.
9. **Client** (`index.html`): rename `jig-lic`/`jig-dev`/`jig-lockcfg` to `cc-*`, update
   `WEB_SALES` regex if the host differs, `API_ROOT` fallback, placeholders and copy.
10. **`tools/tests/lic_test.mjs`**: copy, change the `PP-` regex assertions to `CC-`.

**The price-collision trap.** `webhook.js` is explicitly written on the assumption that the
webhook receives *every* payment on the Square account: line 3–4's comment says
`PUZZLE_PRICE_CENTS` exists "so SEO-client payments on the same Square account never mint
codes". With two Pages projects each subscribed to the same Square application, each payment
event reaches both webhooks. If Puzzle Parlor and Color Cafe have the same price, a $2.99 Puzzle
Parlor purchase passes Color Cafe's amount check too, and the buyer gets a Color Cafe code they
did not pay for (and vice versa). Fixes, cheapest first: (a) give the two products different
prices; (b) extend each copy of `webhook.js` to fetch the order (it already does so for the
email when `SQUARE_ACCESS_TOKEN` is set, lines 16–23) and match a line-item name per product;
(c) one webhook only, routing by product — which is Design B.
*I cannot confirm from Square's docs in this session that subscriptions are account-wide; the
evidence is the existing code comment and `SELLING.md`'s warning about Phoenix Method client
payments. Verify in the Square Developer Dashboard before launch.*

### Design B: one shared license service with a `product` field

The service stays in `puzzle-parlor/functions/` (it already owns the KV, secrets, webhook and
admin page). Color Cafe's client calls it cross-origin; `CORS` is already
`access-control-allow-origin: *` with `x-admin-key` allowed (`license.js` line 2), and
Puzzle Parlor's own Android build already calls the API cross-origin via `API_ROOT`
(`index.html` line 561), so nothing new is needed on that front.

Changes (all in the Puzzle Parlor repo unless noted):

1. **`license.js`**
   - Add a product table:
     ```js
     export const PRODUCTS={
       pp:{prefix:'PP',name:'Puzzle Parlor',price:'PUZZLE_PRICE_CENTS',appUrl:'APP_URL',unlockLabel:'Unlock all puzzles'},
       cc:{prefix:'CC',name:'Color Cafe',price:'COLOR_PRICE_CENTS',appUrl:'COLOR_APP_URL',unlockLabel:'Unlock every page'}
     };
     ```
   - `makeCode(product)`: use `PRODUCTS[product].prefix`.
   - `normCode(raw)`: accept any known prefix; return `{code, product}` (or keep returning the
     string and derive the product from the prefix with a second helper `productOf(code)`).
     Because the KV key is `lic:<code>` and the code carries the prefix, `PP-…` and `CC-…` can
     never collide.
   - `mint(env,{product='pp',…})`: store `product` on the record. **Treat a missing `product`
     on an existing record as `'pp'`** everywhere (`lic.product||'pp'`) so the records minted so
     far need no migration.
   - `activate(env,rawCode,device,name,product)`: after loading `lic`, add
     `if(!licCovers(lic,product)) return {status:403,body:{ok:false,error:'wrong_product',
     message:'This code is for Puzzle Parlor, not Color Cafe.'}}`. Define
     `licCovers=(lic,p)=>(lic.products||[lic.product||'pp']).includes(p)` — the `products`
     array is what the village pass will use (section 4).
   - `SETTING_NAMES`: add `COLOR_PRICE_CENTS`, `COLOR_APP_URL`.
   - `sendCodeEmail(env,{to,code,product})`: pick name, how-to steps, app URL and subject from
     `PRODUCTS[product]`.
2. **`[action].js`**
   - Read `body.product` (default `'pp'`) and pass it to `activate`, `mint`, `sendCodeEmail`.
     `deactivate` needs no product (removing a device from a code you hold is harmless).
   - `list`: accept an optional `product` filter; the admin table otherwise shows both.
   - `status`: unchanged (one `LICENSE_ADMIN_KEY` gates both products).
3. **`webhook.js`**: replace the single `PUZZLE_PRICE_CENTS` check with a loop over `PRODUCTS`
   matching `amt` to each product's price setting; mint with that product. If the two prices are
   equal, this cannot disambiguate — then match on the order's line-item name instead (the order
   is already fetched when `SQUARE_ACCESS_TOKEN` is set). Decide the prices in ticket 07 with this
   in mind: **different prices make the webhook trivially unambiguous.**
4. **`admin.html`**: a product `<select>` on the mint form; a product column in the table; the
   two new settings in `SETTINGS`.
5. **`deploy.yml`**: add `COLOR_PRICE_CENTS`, `COLOR_APP_URL` to the secret list (they can also
   be set from admin.html, since `cfg()` reads KV first).
6. **`tools/tests/lic_test.mjs`**: add cases: `CC-` mint, `CC` code refused on `pp`, `PP` code
   refused on `cc`, record without `product` activates on `pp`, webhook routes by price.
7. **Color Cafe client**: `API_ROOT='https://puzzles.kandyphoenix.com/'` (or the pages.dev
   host), and send `product:'cc'` in `activate`. Everything else in the client block is the same
   as Puzzle Parlor's minus the `jig-*` key names and copy.
   *Optional polish:* a 10-line `functions/api/license/[action].js` in the Color Cafe project
   that forwards the request to the Puzzle Parlor host, so the Color Cafe page talks to its own
   origin and the shared service can move later without touching the client.
8. **Square**: one webhook subscription (the existing one); a second payment link for Color Cafe.
9. **`wrangler.toml` / KV**: unchanged. Color Cafe's Pages project needs **no** KV binding for
   licensing (it still needs one if Color Cafe gets progress sync — separate question).

---

## 3. Risk to existing Puzzle Parlor customers and codes

### Design A

- **Code risk to Puzzle Parlor: none.** No Puzzle Parlor file changes; its KV and secrets are not
  touched.
- **Operational risk: the double-mint trap** above. If prices are equal and the webhooks are not
  made product-aware, every Puzzle Parlor sale also creates (and emails) a Color Cafe code. Not a
  lockout, but it hands out unpaid licenses and confuses buyers with two emails.
- **Drift risk:** two copies of 220 lines. A bug fix in one must be hand-ported to the other.
  Puzzle Parlor's license code has had 4 follow-up commits already (`git log` on the two files:
  `de71742`, `6da0fc4`, `1488fbe`, `a2bec12`, `54f3066`).

### Design B

- **Every deploy of `puzzle-parlor` now carries Color Cafe's license changes.** A regression in
  `normCode`/`activate` affects live Puzzle Parlor customers. The blast radius is bounded by the
  client's behaviour: `recheckLicense()` only runs once per 7 days per device and only clears the
  local license on `unknown`, `revoked` or `device_limit` (`index.html` line 467). A buggy deploy
  that returned `wrong_product` or a 500 would **not** lock anyone out; one that returned
  `unknown` for `PP-` codes would lock out the fraction of devices whose weekly recheck fired
  during the outage (they would need to re-enter their code afterwards — the code itself is intact
  in KV). Mitigation: the new `wrong_product` error must not be in the client's clear-list; keep
  `lic.product||'pp'` defaulting; extend `lic_test.mjs` before deploying; deploy the refactor with
  `cc` disabled first and confirm a real `PP-` code still activates.
- **Existing records need no migration**: `product` is absent on all of them and the default
  covers that. `list` already reads at most 300 records (`[action].js` line 33); a mixed list is
  fine at current volume but the admin filter is worth adding.
- **Shared `LICENSE_ADMIN_KEY`**: one key administers both products. Acceptable for a solo
  operator; it is already the case that one Pages project holds all secrets.
- **Availability coupling**: Color Cafe's unlock depends on the Puzzle Parlor host being up. Both
  are Cloudflare Pages in the same account, and the client treats network failure as "try again",
  not as a lockout (`redeem()` line 457; `recheckLicense()` catches and ignores errors).
- **No risk to progress sync**: `functions/api/p/…` is untouched in both designs.

---

## 4. How a future "village pass" fits

A village pass = one code that unlocks Puzzle Parlor and Color Cafe (and any later shop).

### Under Design A (separate namespaces)

The pass must exist as a record in *both* KV namespaces, because each app's `activate` reads only
its own binding. Two ways:

- **Dual-mint**: when a pass is sold, the webhook (whichever project receives it) writes the same
  code string to both namespaces. A Pages project can bind two KV namespaces (Cloudflare docs: the
  `kv_namespaces` array takes multiple entries,
  https://developers.cloudflare.com/workers/wrangler/configuration/ "KV namespaces"), so
  Puzzle Parlor would bind Color Cafe's namespace as a second binding and vice versa. Both copies
  of `normCode` must accept the pass prefix (e.g. `KV-`). Device counts are then tracked
  **separately per app** (3 devices in each), and a revoke must be done twice.
- **Cross-call**: one project mints locally and POSTs to the other's admin `mint` with
  `x-admin-key`. Same consequences, plus a secret shared across projects.

Either way the pass is bolted on and every later shop adds another binding or call.

### Under Design B (shared service)

The pass is a license record whose `products` array lists more than one product:
`{code:'KV-…', products:['pp','cc'], devices:[…], max:3, …}`. `licCovers()` from section 2
already handles it; `makeCode` gets a third prefix; the webhook maps the pass price to
`products:['pp','cc']`; admin gets a "Village pass" option. One record, one revoke, and one
device list shared across apps (or, if Kandy wants 3 devices *per app*, make `devices` a map keyed
by product — a 5-line change in `activate`). A later shop is one more entry in `PRODUCTS`.

The pricing/village-pass decision itself is ticket 07 (blocked by this one).

---

## 5. What stays identical in both designs

- The code alphabet, 12-char body, 5-retry uniqueness loop, `lic:` key scheme, record shape.
- 3-device limit, activate/deactivate semantics and error codes, 7-day client recheck.
- Admin auth model (`x-admin-key` vs `LICENSE_ADMIN_KEY`, constant-time compare).
- Settings-in-KV-with-env-fallback (`cfg()`), Resend delivery, Square HMAC check and `sqpay:`
  dedupe, "locking is off until `LICENSE_ADMIN_KEY` exists" safety (`SELLING.md`).
- The buy-page flow: Square payment link → webhook → emailed code → `?paid=1` banner.
- The client-side block (`deviceId`, `licCall`, `redeem`, `removeDevice`, `recheckLicense`,
  `refreshLockConfig`) apart from key names, copy and (in B) the `product` field + `API_ROOT`.

---

## 6. Recommendation

**Design B, staged.** Reasons, in order of weight:

1. The map already says Color Cafe follows Puzzle Parlor's model and sits "next door" in the
   village, and ticket 07 asks whether a village pass should exist. Design B makes the pass a
   data change; Design A makes it a cross-namespace bolt-on that grows with every shop.
2. Design A's cheapest path (copy five files) silently inherits the account-wide Square webhook
   and double-mints at equal prices. Fixing that properly means making the webhook product-aware,
   which is most of Design B's work anyway, done twice.
3. One admin page, one list of codes, one set of Resend/Square secrets, one test file. Kandy is
   "on a phone most of the time" (map notes); one admin surface matters.
4. The coupling risk is real but bounded (section 3) and is controlled by doing it in two steps:
   - **Step 1 (Puzzle Parlor PR, no Color Cafe yet):** introduce `PRODUCTS`, `product` on
     records with `'pp'` default, `licCovers`, product-aware `normCode`/`mint`/`activate`/
     `sendCodeEmail`/webhook; extend `lic_test.mjs`; deploy; activate a real `PP-` code on a
     device to confirm nothing changed for customers.
   - **Step 2 (when Color Cafe has a buy page):** add the `cc` entry, `COLOR_PRICE_CENTS`,
     `COLOR_APP_URL`, the admin select, the second Square payment link. Color Cafe's client
     points `API_ROOT` at the Puzzle Parlor host and sends `product:'cc'`.
5. Choose **different prices** for the two products in ticket 07 unless there is a strong reason
   not to; it makes the webhook routing unambiguous without a Square orders lookup.

If Kandy would rather keep the two apps fully independent (e.g. she expects to sell or sunset one
without the other), Design A is sound provided the prices differ or the webhook checks the
line-item name, and provided she accepts maintaining two copies.

Confidence: high on everything derived from the source files (all cited by line). Medium on the
Square account-wide-webhook behaviour (inferred from the existing code comment and `SELLING.md`,
not re-verified against Square's docs in this session). The Cloudflare binding facts come from the
docs pages linked above.
