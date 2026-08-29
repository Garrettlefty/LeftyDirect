# LeftyDirect

An affiliate marketplace that lists **only** left-handed golf clubs. Visitors
click through to a retailer, buy there, and LeftyDirect earns a commission —
LeftyDirect never holds inventory or handles money.

This repo contains a working site plus the automation pipeline that's meant
to feed it. Read this file before you deploy anything — it's honest about
what's ready to go and what still needs a few things only you can do
(signing up for affiliate programs, adding API keys).

## What's in here

```
index.html                          the storefront (open it directly to preview)
products.json                       the current product feed (starts with 14 demo items)
scripts/fetch_products.py           pulls listings from affiliate APIs, rebuilds products.json
requirements.txt                    Python deps for the script above
.github/workflows/update-products.yml   runs the script daily and commits changes
```

## What's real right now vs. what you still need to connect

**Real and working today:**
- The site itself — responsive, filterable by category, searchable, sorts
  by price/newest, reads from `products.json`.
- An affiliate disclosure in the footer and "how it works" section (FTC
  requires this on any site earning from affiliate links).
- `rel="sponsored nofollow noopener"` on every outbound product link, which
  is the attribute Google and most affiliate networks expect on paid links.
- The automation script's *structure*, filtering logic (it only ever keeps
  items with a confirmed left-hand indicator), de-duplication, and output
  format.
- The GitHub Actions workflow that runs the script on a schedule and
  commits the result.

**Needs you, because these require accounts and approvals no one can do on
your behalf:**
- Signing up for the Amazon Associates Program and/or eBay Partner Network
  (and any golf-specific retailer programs — see below).
- Getting API credentials from each program once approved.
- Verifying the exact API request shape against that program's current
  docs — I wrote the eBay/Amazon functions in `fetch_products.py` from
  general knowledge of how those APIs work, not a live test call, and
  affiliate APIs change their fields and auth flows over time.

Until you do that, the site runs on the 14 sample products in
`products.json` so you have something real to look at and share.

## 1. Preview it locally

```bash
cd leftydirect
python3 -m http.server 8000
```

Then open `http://localhost:8000`. (Opening `index.html` by double-clicking
it usually also works, but some browsers block the `fetch('products.json')`
call under the `file://` protocol — the local server avoids that.)

## 2. Deploy it (free, no server to manage)

Either works well for a static site like this:

- **GitHub Pages** — push this repo to GitHub, then in *Settings → Pages*
  set the source to the `main` branch, root folder. Your site will be at
  `https://yourusername.github.io/leftydirect`.
- **Netlify** — drag the `leftydirect` folder into Netlify's dashboard, or
  connect the GitHub repo for automatic redeploys on every push.

Either way, once `products.json` changes and gets pushed, your host
redeploys automatically — that's the "auto-update" loop closed.

## 3. Connect affiliate programs

Sign up directly (I can't create these accounts for you):

- **Amazon Associates** — associates.amazon.com. Approval also requires a
  few qualifying sales within your first 180 days, so don't wait to submit.
- **eBay Partner Network** — partnernetwork.ebay.com.
- **Golf-specific retailers** (Golf Galaxy / Dick's, PGA Tour Superstore,
  Worldwide Golf Shops, Rock Bottom Golf, 2nd Swing Golf, etc.) — most run
  their programs through an affiliate *network* rather than their own
  portal: check **Impact**, **Rakuten Advertising**, **CJ Affiliate**,
  **ShareASale**, and **AWIN** for each retailer's program. These are
  often a better fit than Amazon/eBay since they're golf-only inventory,
  usually with a higher left-handed selection.

Once approved, each program gives you API credentials (or, for network
programs, a product feed file — usually CSV or XML). Add the credentials
as **GitHub repo secrets** (*Settings → Secrets and variables → Actions*):

```
EBAY_OAUTH_TOKEN
EBAY_CAMPAIGN_ID
AMAZON_ACCESS_KEY
AMAZON_SECRET_KEY
AMAZON_PARTNER_TAG
```

## 4. Turn on the automation

The workflow in `.github/workflows/update-products.yml` is already set to
run daily. Once your secrets are in place:

1. Push this repo to GitHub.
2. Go to the **Actions** tab and confirm the "Update LeftyDirect catalog"
   workflow is enabled.
3. Optionally trigger it once manually (*Run workflow* button) to confirm
   it pulls real data.

From here, it runs itself: daily pull → filter for confirmed left-handed
items → rebuild `products.json` → commit if anything changed → host
redeploys. No one has to touch it for the catalog to stay current.

## 5. Add more sources over time

`fetch_products.py` has a placeholder function
(`fetch_network_feed_placeholder`) and comments showing where to plug in
each new network's feed once you're approved. The pattern is always the
same: pull raw listings → confirm left-hand dexterity → normalize into the
shared schema → let `normalize()` and the de-duplication step handle the
rest.

## 6. Compliance notes (not legal advice)

- Every affiliate program has its own linking and disclosure rules —
  Amazon in particular is strict about price/availability caching and
  exact disclosure wording. Read each program's operating agreement
  before going live.
- The disclosure text baked into `index.html` covers the general FTC
  requirement, but you're responsible for keeping it accurate as you add
  or drop programs.
- If you want a dedicated privacy policy page (most ad/affiliate networks
  require one), that's a straightforward addition — just ask.

## Customizing

- **Branding / colors** — CSS variables are all at the top of `index.html`
  inside `:root`.
- **Categories** — edit `CATEGORY_LABEL` and `ICONS` in the `<script>` at
  the bottom of `index.html`, and `CATEGORY_KEYWORDS` in
  `fetch_products.py`, together.
- **Manually adding a product** — you can hand-edit `products.json` any
  time; the automated run will simply overwrite it on its next schedule.

## Roadmap ideas (not built yet)

- Click tracking / basic analytics on which clubs get clicked most.
- Price-drop or back-in-stock alerts.
- A "notify me" email capture for out-of-stock left-handed items (a real
  gap in this market).

Happy to build any of these next — just ask.
