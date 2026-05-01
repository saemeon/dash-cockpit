# Demo Cockpit

A complete working example of dash-cockpit aggregating cards from two
sibling team packages.

## Structure

```
demo_cockpit/
├── app.py                    # cockpit wiring (run this)
├── team_finance/             # team package #1
│   ├── __init__.py           # exports get_cards()
│   └── cards/
│       ├── revenue_trend.py
│       └── cash_position.py
└── team_ops/                 # team package #2
    ├── __init__.py           # exports get_cards()
    └── cards/
        ├── headcount.py
        ├── ticket_volume.py
        └── broken_card.py    # intentionally raises — shows error isolation
```

## Run

```bash
cd examples/demo_cockpit
python app.py
```

Then open http://localhost:8051

## Pages

- **Finance Overview** — TeamPage with 2 finance cards in a 2-column grid
- **Operations** — TeamPage with 3 ops cards (one is broken; renders an error
  card while the others continue working)
- **Executive Mix** — UserPage demonstrating an explicit row-layout mixing
  cards from both teams

## What this demonstrates

1. **Cards as atomic units** — each card is a standalone Python module
2. **Team package contract** — each team exposes a single `get_cards()` function
3. **Failure isolation** — `broken_card` raises an exception but the cockpit
   keeps rendering everything else
4. **Mixed page types** — both team-defined (curated) and user-defined
   (explicit grid) pages
5. **Single Dash runtime** — one app, sidebar nav, all cards loaded at startup
