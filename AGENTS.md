# Repository Agent Instructions

For recurring order updates and cleaning, follow `HERMES.md` and run `./scripts/hermes_update_data.sh`. Do not edit generated public data by hand.

The recommendation grain is one canonical independent meal, keyed by `dishId`. Repeated dates, branches, and explicitly reviewed aliases must share one ID. Never use fuzzy name similarity alone to merge dishes.

Private raw orders and audit output stay under `.private/` and must never be committed. Run the full update script before proposing or publishing generated-data changes.
