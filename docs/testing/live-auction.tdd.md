# Live auction TDD evidence

## Source and user journeys

The journeys were derived from the approved conversation plan; no separate plan file was supplied.

- As an admin, I can start an auction with a fixed bid increment and a selected or random first nominator without changing individual team budgets.
- As the current nominator, I can place an unsold footballer on the virtual auction spot.
- As a snapshotted participant, I can enter a bid at or above the visible minimum for the team assigned to my browser.
- As an admin, I can award or cancel a lot and rotate or skip the nominator without corrupting budgets or purchases.

## RED and GREEN evidence

| Task | Test target | RED evidence | GREEN evidence |
|---|---|---|---|
| Auction domain transitions | `tests/auction_logic.test.js` | `node --test tests/auction_logic.test.js` failed with `Cannot find module '../auction_logic'` before production logic existed; later regression tests covered leave handling, resuming, and Firebase-omitted null bid fields. | 23 domain tests pass after `auction_logic.js`, its authorization guards, active leave/resume handling, and Firebase round-trip normalization were implemented. |
| Build and UI integration | `tests/auction_build_integration.test.js` | Three assertions failed because the panel, controls, build placeholder, and inlined logic did not yet exist. | All fourteen integration checks pass after rebuilding `transferbrett.html`. |
| Nominator skip | `tests/auction_logic.test.js` | The new test failed with `TypeError: skipNominator is not a function`. | The same test passes after the transition was added. |

## Guarantees

| # | What is guaranteed | Test type | Result |
|---|---|---|---|
| 1 | Every registered browser with a valid team is snapshotted without changing individual budgets or balances. | Unit + Integration | PASS |
| 2 | Existing purchases and team balances remain unchanged when a session starts. | Unit | PASS |
| 3 | Only the current person may nominate an unsold player. | Unit | PASS |
| 4 | Bids require at least the visible minimum, matching team ownership, a current snapshot, tenths precision, and sufficient budget. | Unit | PASS |
| 5 | Stale simultaneous bids cannot overwrite the newer accepted bid. | Unit | PASS |
| 6 | Awarding creates exactly one purchase/history entry, debits exactly once, and rotates the nominator. | Unit | PASS |
| 7 | Canceling preserves balances; skipping rotates only when no lot is active. | Unit | PASS |
| 8 | The standalone build contains the auction controls and inlined reusable domain logic without unresolved placeholders. | Integration | PASS |
| 9 | The local page loads without browser console errors and the auction panel fits a 375 px viewport without document overflow. | Browser smoke | PASS |
| 10 | Admin-only transitions reject a browser whose token differs from the current admin token. | Unit | PASS |
| 11 | Connectivity is read from Firebase and both ordinary state writes and new-board creation use transactions. | Integration | PASS |
| 12 | The admin can assign a team to every present browser before the auction starts. | Integration | PASS |
| 13 | Browser caches are isolated by game code, so a new game starts from the embedded base state. | Integration | PASS |
| 14 | A browser can leave explicitly; nomination/admin succession remains valid and existing bids are retained. | Unit + Integration | PASS |
| 15 | Every player row shows an auction button that is enabled only for the current nominator and an available player. | Integration | PASS |
| 16 | The auction panel is placed directly above the player table and below the team overview. | Integration | PASS |
| 17 | Admin takeover stays available during an auction and is written through a Firebase transaction. | Integration | PASS |
| 18 | Player search, filters, legend, and bulk controls are located immediately above the player table. | Integration | PASS |
| 19 | A fresh Firebase lot whose null bid fields were omitted starts at the player's market value without a stale-bid error. | Unit | PASS |
| 20 | A finished auction can resume with the same participants, current nominator, budgets, and purchases. | Unit + Integration | PASS |

## Commands and coverage

- Build: bundled Python `build_transferbrett.py` — PASS.
- Tests: bundled Node `--test --experimental-test-coverage tests/auction_logic.test.js tests/auction_build_integration.test.js` — 37/37 PASS at the recorded full-suite checkpoint.
- Domain coverage at that checkpoint: 98.31% lines, 84.30% branches, 96.97% functions.
- Syntax: bundled Node `--check auction_logic.js` — PASS.

## Known gaps

- Production Firebase was not mutated during browser QA. Multi-client concurrency is covered at the pure transaction-transition boundary; a disposable Firebase staging project is still the safest place for a destructive end-to-end race test.
- No committed visual baseline existed, so pixel-level visual regression is INCONCLUSIVE. Responsive overflow and console errors were checked directly.
- Roles remain client-side in the existing application architecture. Firebase Authentication and restrictive database rules are required for hostile-user authorization, outside this feature's approved scope.
