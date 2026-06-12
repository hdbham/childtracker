# CFC Memo Structure & Bulk Update Guide

> **Read this before running any bulk memo script.**

---

## Memo Format

Every memo has two sections separated by `---`:

```
[SCHEDULE BLOCK]

---

[DAY-SPECIFIC CONTENT]
```

- **Schedule block** — the daily schedule table + reminders. Changes per day-of-week type.
- **Day-specific content** — activities, riddles, parent reminders, etc. Unique to each date.

When running bulk updates, **always split on `---` and only replace the section you intend to change.** Never overwrite the full memo string.

---

## Schedule Templates by Day Type

| Day | Type | Schedule Template |
|-----|------|-------------------|
| Monday | Onsite | Regular onsite schedule |
| Tuesday | Movie Day (Offsite) | Regular schedule + movie block 12:00–2:30 |
| Wednesday | Field Trip (Offsite) | Leave 9:30 AM, return ~2:30 PM |
| Thursday | Onsite | Regular onsite schedule |
| **Friday** | **Swim Day (Offsite)** | **Swim schedule — see below** |

### Friday Swim Day Schedule (DO NOT REPLACE WITH REGULAR ONSITE)

```
7:30–8:00 AM   | Attendance / Sign-In / Quiet Activity
8:00–8:15 AM   | Clean Up Tables / Wash Hands
8:15–8:45 AM   | Breakfast
8:45–9:00 AM   | Transition — Clean, bathroom, gather items for outside
9:00–9:15 AM   | GET WATERS & SUNSCREEN — Physical Activity
9:15–9:45 AM   | Opening Ceremony
9:45–10:45 AM  | Centers / Activity Block
10:45–11:00 AM | Get Ready for Swimming — change into swimsuit
11:00–11:45 AM | Lunch — early lunch on-site before pool
11:45 AM–12:15 PM | Load Bus & Drive to Pool
12:15–2:00 PM  | Swim — sunscreen, review rules, swim tests as needed
2:00–2:15 PM   | Safety whistle at 2:00 — count all kids, load bus & drive back
2:15–2:30 PM   | Change to Dry Clothes — back at site
2:30–2:45 PM   | Transition — Clean, bathroom, wash hands
2:45–3:05 PM   | Snack
3:05–3:15 PM   | Transition — Clean, bathroom, gather items for outside
3:15–3:45 PM   | Centers / Activity Block
3:45–4:15 PM   | Closing Ceremony — All camp together
4:15–4:45 PM   | Camp Games
4:45–6:00 PM   | Structured Free Play / Sign-Out
```

**Key Friday notes:**
- Lunch is early (11:00 AM) — before the pool, not at normal time
- Kids change back into dry clothes **at site** after returning on the bus (2:15 PM), NOT at the pool
- 1–2 staff bring life jackets, wristbands, water, backpack, sunscreen on bus

---

## Bulk Update Rules

### Safe to bulk update across ALL days:
- Reminders section (the bullet points after the schedule table)
- Parent Reminder section (below `---`)

### Only update by day-of-week:
- Schedule table — use `datetime.weekday()` to filter:
  - `weekday() == 4` → Friday → use Swim Day schedule
  - `weekday() in [0, 3]` → Mon/Thu → use regular onsite schedule
  - `weekday() == 1` → Tuesday → Movie Day schedule
  - `weekday() == 2` → Wednesday → Field Trip schedule

### Never bulk replace the full memo string:
Always preserve day-specific content below `---`.

---

## Backup

Before any bulk update, run a backup:

```bash
python3.11 /tmp/backup_memos.py
# Saves to Desktop: cfc_memos_backup_YYYY-MM-DD_HHMM.json
```

A backup from 2026-06-12 is saved on the Desktop (`cfc_memos_backup_2026-06-12_0718.json`).

---

## Firebase Path

- **All CFC memos:** `cfc/memos` in `group-manager-a55a2-default-rtdb`
- Each record: `{ staff, date, memo }`
- 488 total memos (6 staff × ~11 weeks × 5 days + some extras)
