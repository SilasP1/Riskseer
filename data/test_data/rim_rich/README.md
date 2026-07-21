# Rich RIM staged demo data

This fixture gives Riskseer fuller case stories instead of two-row toy cases.
Each stage has three operational cases with about ten field events each plus
ticket, asset, field-report, marking/locate, and positive-response context.

Core modeling rule:

- Tickets are submitted before work starts.
- Riskseer should still verify whether the ticket covers the work time and work
  zone when the field activity actually happens.

Stages:

- `stage_01_baseline`: baseline support picture.
  - `RICH-A`: strong support. Ticket covers time/place, response complete,
    marks visible, field report aligns.
  - `RICH-B`: weak support. Ticket exists and was submitted before work, but
    work trends toward the edge of the ticketed area with partial marks and
    incomplete positive response.
  - `RICH-C`: conflicted/degraded support. Ticket exists, but the active HDD
    work is outside the ticketed zone near a high-consequence asset.
- `stage_02_evolution`: follow-up batch for temporal evolution.
  - `RICH-A`: trends safer with refreshed marks and lower intensity work.
  - `RICH-B`: becomes riskier as activity moves outside the ticketed zone and
    response/marking support remains incomplete.
  - `RICH-C`: becomes more urgent as HDD activity continues after the ticket
    window near transmission gas context.

To run the temporal demo manually, copy a stage's CSVs into `data/`, run
`python main.py`, then copy the next stage and run `python main.py` again.
The active `data/*.csv` files are archived and cleared after each run by the
normal pipeline.
