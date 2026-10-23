# OrionTV cloud maintenance

## Scope

This repository packages an OrionTV backend: LunaTV on Cloud Run, Upstash Redis,
public live/VOD source examples, and a monthly/expiry billing guard.
Projector desktop, wallpapers, firmware adapters and APKs are outside this repo.

## Entry points and stack

- Start with `README.md`, then `docs/deployment.md` and `docs/cost-guard.md`.
- `cloud/`: Python 3.10+ standard library and Google Cloud CLI.
- `cloud/cost-guard/workflow.yaml.template`: Google Workflows source.
- `vendor/LunaTV/`: pinned Next.js/TypeScript source; container built with Cloud Build.
- `.local/`: ignored deployment parameters and receipts; never commit it.

## Verification

- Source/title regression: `node --experimental-strip-types --test vendor/LunaTV/tests/*.test.mjs` (Node 24) and `python3 -B cloud/test_add_sources.py`; these run offline.
- `python3 -B cloud/cost-guard/check.py` checks source and live metadata.
- `python3 -B cloud/cost-guard/test_guard.py` runs 18 cloud dry-run cases.
- Both need existing private configuration and authenticated Google Cloud CLI.
- The boundary fixtures target the shipped deadline; update them when extending it.
- Documentation-only changes need link/consistency checks, not a redeploy.

## Invariants

- Add sources to an existing service with `configure_service.py --add-sources <json>`; the default import replaces configuration. Preserve source permissions and private state.
- Retain ignored deployment/rollback receipts during cleanup; physical playback of newly added sources remains separate from API verification.
- Videos stay client-direct; preserve DISABLE_VIDEO_PROXY and DISABLE_BACKGROUND_JOBS.
- `/api/live/playlist` serves playlist text only and stays gated by LIVE_PLAYLIST_TOKEN. App code must not log its URL; Cloud Run request logs still record the query string, as documented.
- USD 5 is a protection threshold, not a strict final-bill ceiling.
- Monthly recovery must preserve user-initiated pauses and stop at expiry.
- Billing unlink must remain project-scoped and gated by both real time and IAM.
- Never test expiry by actually unlinking billing before its authorized deadline.
- Do not print/export credentials, cookies, private subscriptions or service-account keys. The one exception is `configure_service.py --live-url`, which prints the TV playlist URL only when explicitly run.
- Keep actual project/account/device identifiers and local paths out of public commits.
- Preserve the CC BY-NC-SA license of LunaTV; root MIT does not override it.

## Current verification boundary

See `docs/verification.md`: the original deployment and physical playback were
verified; fresh-account bootstrap and real future billing unlink are not fully tested.
Keep these distinctions when reporting changes. Routine closeout does not authorize
stopping the service, changing its IAM or deleting the original private evidence.
