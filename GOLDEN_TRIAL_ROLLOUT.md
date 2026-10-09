# Golden Early Access — implementation checklist (NOT LIVE)

Goal: 10 manually invited beta testers, each with 7 days from first activation. Existing lifetime codes and activation must remain unchanged.

## Safe rollout
1. Inspect the current Supabase SQL definitions for `activate_planora_gold`, license tables, and RLS. Export a backup first.
2. Add a separate trial entitlement table or an additive license type. Never modify existing lifetime records or reinterpret them as trials.
3. Create exactly 10 unique trial codes server-side. Store only hashed codes where practical; avoid committing secrets to GitHub.
4. The activation RPC must return a verified entitlement type and expiration timestamp. Enforce expiration on the server, not just in localStorage. Preserve existing lifetime device limits and behavior.
5. After expiration, allow backup/export and license upgrade without deleting locally stored collection data. Verify lifetime upgrade uses the existing activation path.
6. Only after server testing, add the CH-logo trial UI (no diamond icon), remaining-time indicator, and upgrade screen to the public app.
7. Test lifetime old code, new trial code, expiry, device changes, offline behavior, and trial-to-lifetime upgrade.

## Status
Planning only. No trial codes created, no database migration executed, and no live activation behavior changed.

## Needed before implementation
SQL schema or Supabase SQL editor definitions for the existing license tables and `activate_planora_gold` function. Never share the Supabase service-role key or user passwords.
