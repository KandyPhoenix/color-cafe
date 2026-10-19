# Research: reusing Puzzle Parlor's license system for a second app

Type: research
Status: resolved
Blocked by: 

## Question

Puzzle Parlor's license API lives in puzzle-parlor/functions/_lib/license.js and functions/api/license/[action].js (KV-backed codes, device limits, admin actions, email). What would it take to use the same system for Color Cafe: a separate KV namespace and product id, or one shared service with a product field? List the exact changes, what stays identical, and any risk to existing Puzzle Parlor customers. Also note how a future 'village pass' (one code unlocking both apps) would fit.

## Answer

Findings: branch `research/license-reuse`, file `research/license-reuse/findings.md`.

- About 80% of Puzzle Parlor's license code is generic. Product-specific: the `PP-` code prefix, email copy/subject, price constant name, support inbox, Pages project + KV id in wrangler.toml, and the client's `jig-*` localStorage keys.
- Design A (separate deployment + own KV): ~12 line edits, no Puzzle Parlor changes, but Square sends every payment to every webhook, so equal prices would mint codes in both apps.
- Design B (one shared service with a `product` field): ~40 changed lines, Color Cafe calls it cross-origin with `product:'cc'`, no migration of existing codes; a village pass becomes a record with `products:['pp','cc']`.
- Recommendation: Design B, done in two steps (make Puzzle Parlor product-aware and verify a real code first, then add `cc`), and give the two products different prices so webhook routing is unambiguous.
- Caveat: the Square account-wide-webhook behaviour is inferred from the repo's comments, not re-verified against Square docs.
