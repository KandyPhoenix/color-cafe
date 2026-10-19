# Research: reusing Puzzle Parlor's license system for a second app

Type: research
Status: open
Blocked by: 

## Question

Puzzle Parlor's license API lives in puzzle-parlor/functions/_lib/license.js and functions/api/license/[action].js (KV-backed codes, device limits, admin actions, email). What would it take to use the same system for Color Cafe: a separate KV namespace and product id, or one shared service with a product field? List the exact changes, what stays identical, and any risk to existing Puzzle Parlor customers. Also note how a future 'village pass' (one code unlocking both apps) would fit.
