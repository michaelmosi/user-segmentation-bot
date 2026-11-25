"""Regenerates deterministic sample data with one planted user per segment, plus a filler crowd.

As-of date for the samples: 2026-11-30.
"""
import csv
import datetime
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
AS_OF = datetime.date(2026, 11, 30)
D = datetime.timedelta


def day(n):  # n days before AS_OF
    return (AS_OF - D(days=n)).isoformat()


users, txs = [], []


def add(uid, signup_days_ago, tx_days_ago_amounts, **attrs):
    users.append({"user_id": uid, "signup_date": day(signup_days_ago),
                  "channel": attrs.get("channel", "organic"), "gender": attrs.get("gender", "F"),
                  "age_group": attrs.get("age_group", "26-35"), "device": attrs.get("device", "Mobile app"),
                  "location": attrs.get("location", "Nairobi"), "occupation": attrs.get("occupation", "Employed")})
    for ago, amount in tx_days_ago_amounts:
        txs.append({"user_id": uid, "date": day(ago), "amount": amount})


# planted users (one per BOBR / RGS / DRIP case)
add("u_nonuser", 200, [])                                                       # Non-user
add("u_new", 10, [(5, 1000)])                                                   # New user
add("u_stopper", 300, [(60, 2000), (75, 2000), (100, 2000)])                    # Stopper, RGS churned
add("u_grower", 300, [(d, 500) for d in (5, 9, 14, 20, 26)] + [(40, 200), (70, 200)],
    channel="referral")                                                         # Grower, Regular/Irregular
add("u_dropper", 300, [(3, 100)] + [(d, 1500) for d in (35, 42, 65, 72)])       # Dropper
add("u_daily", 300, [(i, 300) for i in range(0, 20)] + [(40, 300), (70, 300)])  # Daily
add("u_lost", 800, [(500, 1000)])                                               # Lost (360+)
add("u_lost2", 800, [(200, 1000)])                                              # Lost (91-360)

# filler crowd
rng = random.Random(7)
for i in range(60):
    signup = rng.randint(40, 700)
    n = rng.choice([0, 0, 1, 2, 3, 4, 6, 9])
    t = [(rng.randint(0, 120), rng.choice([200, 500, 1000, 2500])) for _ in range(n)]
    add(f"u_{i:03d}", signup, t, channel=rng.choice(["organic", "referral", "instagram", "podcast"]),
        gender=rng.choice(["F", "M"]), age_group=rng.choice(["18-25", "26-35", "36-50", "50+"]),
        device=rng.choice(["Mobile app", "Web", "USSD"]), location=rng.choice(["Nairobi", "Mombasa", "Kisumu", "Nakuru"]),
        occupation=rng.choice(["Student", "Employed", "Self-employed", "SME"]))

with open(os.path.join(HERE, "users.sample.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(users[0]))
    w.writeheader(); w.writerows(users)
with open(os.path.join(HERE, "transactions.sample.csv"), "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["user_id", "date", "amount"])
    w.writeheader(); w.writerows(txs)
print(len(users), "users,", len(txs), "transactions")
