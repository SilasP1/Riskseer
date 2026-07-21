# Three-case demo dataset

This fixture is a compact demo dataset for Riskseer.

It contains three cases that show the main kinds of things Riskseer should
surface:

- `DEMO-A`: strong support
  - Ticket submitted before work
  - Ticket covers the work area and time
  - Complete response
  - Visible marks
  - Field report aligns with the work

- `DEMO-B`: weak / degraded support
  - Ticket exists and was submitted before work
  - Work trends toward or beyond the supported edge
  - No positive response record is attached for the active work
  - No marking record is attached for the active work
  - Field report says support is getting harder to trust

- `DEMO-C`: conflicted / stop-work support
  - Ticket exists, but HDD activity occurs outside the ticketed zone
  - Work is near a high-consequence mapped asset
  - No marking or positive-response support is attached for the active work area
  - Field report conflicts with the apparent authorization picture

Use it when you want one small demo batch that shows the range of what
Riskseer flags without relying on a larger staged evolution run.
