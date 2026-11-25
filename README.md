# User segmentation bot

Classifies every user with four behavioural models and gives each one a recommended next action, plus a plain-language summary report. Standard-library Python, no installs.

| Model | Question it answers | Segments |
| --- | --- | --- |
| **RGS** (revenue generating service) | How recently did the user do a revenue-generating action? | Hot (1-3 days), Warm (4-7), At-risk (8-30), Churned (31-90), Lost (91-360, 360+), No revenue action |
| **DRIP** (activity frequency) | On how many of the last 30 days did they transact? | Daily (more than 15), Regular (6-15), Irregular (2-5), Poor (1), Dormant (0) |
| **Value extraction** | Is usage rising or falling? | Growth % = (this month - average of the previous two months) / that average x 100: Growing (>20%), Stable (0-20%), Declining (<0%) |
| **BOBR** (behaviour over behaviour range) | Who needs attention, nurturing or reactivation? | Non-user, New user, Stopper, Grower, Dropper, plus Steady for everyone else |

BOBR rules: never transacted and joined more than 30 days ago is a Non-user; joined in the last 30 days is a New user; transacted before but not in the last 30 days is a Stopper; value growth above 20% is a Grower; below 0% is a Dropper. "Steady" is an addition, so every user gets a label.

## Usage
```bash
python segmentation_bot.py users.sample.csv transactions.sample.csv --as-of 2026-11-30 --out segments.csv --md report.md
```

| File | Columns |
| --- | --- |
| users | `user_id`, `signup_date`; optional `channel`, `gender`, `age_group`, `device`, `location`, `occupation` |
| transactions | `user_id`, `date`, `amount` |

The report also shows the user distribution (gender, age group, device, location, occupation) when those columns exist, and a headline of how many users are Stoppers or Droppers versus Growers.

## Notes
- Segment boundaries follow the framework's tables; where they overlapped (30 days appears in two rows) the lower row wins.
- Transactions dated after `--as-of` are ignored.
- Feed the output into your email or CRM tools: one row per user with the segment and action.

## Credit
The RGS, DRIP, value extraction and BOBR models come from a growth-marketing framework document by Adeola Adesina. This repo is an implementation, not the framework itself.

## Tests
```bash
python -m unittest discover tests
```
