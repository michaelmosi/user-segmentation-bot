#!/usr/bin/env python3
"""User segmentation bot (standard library only).

Classifies every user with four behavioural models from a growth-marketing framework and
turns them into a recommended next action per user plus a plain-language summary:

  RGS   Revenue Generating Service: how recently did the user last do a revenue-generating action?
  DRIP  Activity frequency: how many days in the last 30 did they transact?
  VALUE Value extraction: this month's usage against the average of the previous two months.
  BOBR  Behaviour over behaviour range: non-user, new user, stopper, grower, dropper (or steady).

    python segmentation_bot.py users.sample.csv transactions.sample.csv --as-of 2026-11-30 --out segments.csv --md report.md

Inputs
  users.csv         user_id, signup_date  (optional: channel, gender, age_group, device, location, occupation)
  transactions.csv  user_id, date, amount (a revenue-generating action: an investment, a top-up, a purchase)
"""
import argparse
import csv
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

ACTIONS = {
    "RGS": {
        "Hot (1-3 days)": "Upsell or incentivise.",
        "Warm (4-7 days)": "Remind or nudge to return.",
        "At-risk (8-30 days)": "Deploy a reactivation campaign.",
        "Churned (31-90 days)": "Use a win-back offer.",
        "Lost (91-360 days)": "Reacquire with a special incentive.",
        "Lost (360+ days)": "Reacquire with a special incentive.",
        "No revenue action": "Educate and onboard.",
    },
    "DRIP": {
        "Daily": "Reward with loyalty or exclusive offers.",
        "Regular": "Send habit-building nudges.",
        "Irregular": "Educate and re-engage.",
        "Poor": "Reactivate with high-touch campaigns.",
        "Dormant (no activity in 30 days)": "Retarget or label as a churn risk.",
    },
    "BOBR": {
        "Non-user": "Educate and onboard.",
        "New user": "Ensure a strong first experience.",
        "Stopper": "Trigger a reactivation sequence.",
        "Grower": "Encourage referrals or upsells.",
        "Dropper": "Send 'we miss you' nudges or loyalty rewards.",
        "Steady": "Keep the habit going; no intervention needed.",
    },
}


def parse_date(value):
    return datetime.strptime(str(value).strip()[:10], "%Y-%m-%d").date()


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return [{k.strip().lower(): (v or "").strip() for k, v in r.items() if k} for r in csv.DictReader(fh)]


def month_start(d, back=0):
    y, m = d.year, d.month - back
    while m <= 0:
        y, m = y - 1, m + 12
    return date(y, m, 1)


# ------------------------------------------------------------------ models
def rgs_segment(days_since_last):
    """days_since_last is None when the user has never transacted."""
    if days_since_last is None:
        return "No revenue action"
    if days_since_last <= 3:
        return "Hot (1-3 days)"
    if days_since_last <= 7:
        return "Warm (4-7 days)"
    if days_since_last <= 30:
        return "At-risk (8-30 days)"
    if days_since_last <= 90:
        return "Churned (31-90 days)"
    if days_since_last <= 360:
        return "Lost (91-360 days)"
    return "Lost (360+ days)"


def drip_segment(active_days_30):
    if active_days_30 > 15:
        return "Daily"
    if active_days_30 >= 6:
        return "Regular"
    if active_days_30 >= 2:
        return "Irregular"
    if active_days_30 == 1:
        return "Poor"
    return "Dormant (no activity in 30 days)"


def value_growth(current, previous_two):
    """Value Growth % = (current month usage - average of last 2 months) / average of last 2 months x 100.
    Returns None when there is no baseline to compare against."""
    baseline = sum(previous_two) / len(previous_two)
    if baseline == 0:
        return None
    return (current - baseline) / baseline * 100


def value_class(growth, current, baseline_total):
    if growth is None:
        return "New value (no baseline)" if current > 0 else "No usage"
    if growth > 20:
        return "Growing (>20%)"
    if growth >= 0:
        return "Stable (0-20%)"
    return "Declining (<0%)"


def bobr_segment(has_ever_transacted, signup, as_of, active_days_30, growth):
    recently_joined = signup is not None and (as_of - signup).days <= 30
    if not has_ever_transacted:
        return "New user" if recently_joined else "Non-user"
    if recently_joined:
        return "New user"
    if active_days_30 == 0:
        return "Stopper"
    if growth is not None and growth > 20:
        return "Grower"
    if growth is not None and growth < 0:
        return "Dropper"
    return "Steady"


# ------------------------------------------------------------------ pipeline
def segment_users(users, transactions, as_of):
    by_user = defaultdict(list)
    for t in transactions:
        d = parse_date(t["date"])
        if d <= as_of:
            by_user[t["user_id"]].append((d, float(t.get("amount") or 0)))
    cur_m, m1, m2 = month_start(as_of), month_start(as_of, 1), month_start(as_of, 2)
    results = []
    for u in users:
        txs = by_user.get(u["user_id"], [])
        last = max((d for d, _ in txs), default=None)
        days_since = (as_of - last).days if last else None
        active_days = len({d for d, _ in txs if 0 <= (as_of - d).days < 30})

        def usage(month):
            return sum(a for d, a in txs if month_start(d) == month)

        current, p1, p2 = usage(cur_m), usage(m1), usage(m2)
        growth = value_growth(current, [p1, p2])
        signup = parse_date(u["signup_date"]) if u.get("signup_date") else None
        rgs = rgs_segment(days_since)
        drip = drip_segment(active_days)
        bobr = bobr_segment(bool(txs), signup, as_of, active_days, growth)
        results.append({
            "user_id": u["user_id"], "channel": u.get("channel", ""),
            "days_since_last_action": "" if days_since is None else days_since,
            "rgs": rgs, "active_days_30": active_days, "drip": drip,
            "usage_this_month": round(current, 2), "usage_prev_2m_avg": round((p1 + p2) / 2, 2),
            "value_growth_pct": "" if growth is None else round(growth, 1),
            "value_class": value_class(growth, current, p1 + p2), "bobr": bobr,
            "recommended_action": ACTIONS["BOBR"][bobr] + " (RGS: " + ACTIONS["RGS"][rgs] + ")",
        })
    return results


def distribution(users, field):
    counts = Counter((u.get(field) or "Unknown") for u in users)
    total = sum(counts.values())
    return [(k, v, v / total) for k, v in counts.most_common()]


def build_report(users, results, as_of):
    total = len(results)
    lines = [f"# User segmentation report", f"As of {as_of}. {total:,} users.", ""]
    for key, label, order in (("rgs", "RGS: recency of revenue action", list(ACTIONS["RGS"])),
                              ("drip", "DRIP: activity frequency (last 30 days)", list(ACTIONS["DRIP"])),
                              ("bobr", "BOBR: behaviour over behaviour range", list(ACTIONS["BOBR"]))):
        counts = Counter(r[key] for r in results)
        lines += [f"## {label}", "", "| Segment | Users | Share | Action |", "| --- | --- | --- | --- |"]
        table = ACTIONS["RGS"] if key == "rgs" else ACTIONS[key.upper()]
        for seg in order:
            if counts.get(seg):
                lines.append(f"| {seg} | {counts[seg]:,} | {counts[seg] / total * 100:.1f}% | {table[seg]} |")
        lines.append("")
    counts = Counter(r["value_class"] for r in results)
    lines += ["## Value extraction (this month vs average of the previous two months)", "",
              "| Class | Users | Share |", "| --- | --- | --- |"]
    for k, v in counts.most_common():
        lines.append(f"| {k} | {v:,} | {v / total * 100:.1f}% |")
    lines.append("")
    for field, title in (("gender", "Gender"), ("age_group", "Age group"), ("device", "Device or channel"),
                         ("location", "Location"), ("occupation", "Occupation")):
        if any(u.get(field) for u in users):
            lines += [f"## User distribution: {title}", "", "| Group | Users | Share |", "| --- | --- | --- |"]
            lines += [f"| {k} | {v:,} | {s * 100:.1f}% |" for k, v, s in distribution(users, field)]
            lines.append("")
    at_risk = sum(1 for r in results if r["bobr"] in ("Stopper", "Dropper"))
    lines += ["## Headline", "", f"- {at_risk:,} users ({at_risk / total * 100:.1f}%) are Stoppers or Droppers and need a retention action first."]
    growers = sum(1 for r in results if r["bobr"] == "Grower")
    lines += [f"- {growers:,} users ({growers / total * 100:.1f}%) are Growers: the best group for referral and upsell asks."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="RGS, DRIP, value extraction and BOBR user segmentation.")
    ap.add_argument("users"); ap.add_argument("transactions")
    ap.add_argument("--as-of", help="YYYY-MM-DD, defaults to today")
    ap.add_argument("--out", default="segments.csv"); ap.add_argument("--md")
    args = ap.parse_args(argv)
    as_of = parse_date(args.as_of) if args.as_of else date.today()
    users, txs = read_csv(args.users), read_csv(args.transactions)
    results = segment_users(users, txs, as_of)
    with open(args.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(results[0]))
        w.writeheader()
        w.writerows(results)
    print(f"wrote {len(results)} users to {args.out}")
    if args.md:
        open(args.md, "w", encoding="utf-8").write(build_report(users, results, as_of))
        print("wrote", args.md)
    return results


if __name__ == "__main__":
    main()
