# RIM demo dataset

This fixture exercises the Responsibility Integrity Model through the currently
loaded Riskseer inputs: events, tickets, and assets.

What it demonstrates:

- `RIM-E001/RIM-E002`: no plausible ticket near a mapped gas asset; locate support should be `MISSING`.
- `RIM-E010/RIM-E011`: aligned ticket and nearby asset, but no positive response or marking source is loaded; locate/marks should be `UNKNOWN`.
- `RIM-E020/RIM-E021`: active ticket exists but field activity is outside the ticket area.
- `RIM-E030/RIM-E031`: activity occurs after ticket window expiry with HDD equipment.
- `RIM-E040/RIM-E041`: multiple ticket candidates create scope ambiguity.
- `RIM-E050/RIM-E051`: ticket exists but no nearby mapped asset is attached.
- `RIM-E060/RIM-E061`: low-intensity locate/site-walk style activity with ticket and asset context.
- `RIM-E070/RIM-E071`: high-consequence HDD work near transmission gas with no loaded locate/mark confirmation.

Important limitation:

`main.py` does not currently load positive-response, marking, or field-report
CSV files. Absence of those source records should therefore render as
`UNKNOWN`, not `MISSING`, unless another backend observation proves absence.
