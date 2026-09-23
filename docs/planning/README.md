# Planning

Working plan for Tier 1 V1, October to mid-December 2026.

| File | What it is |
|---|---|
| `tier1v1-gantt-and-audit.xlsx` | The main plan. Seven sheets — see below. |
| `tier1v1-calendar-combined.ics` | Both people's schedule in one calendar, shared events listed once. Import into its own new calendar. |
| `tier1v1-calendar-you.ics` | Lead's schedule only. |
| `tier1v1-calendar-teammate.ics` | Teammate's schedule only. |

## Sheets in the workbook

| Sheet | Purpose |
|---|---|
| Gantt (October) | 56 task rows for Oct 1–30, coloured by stream. Shows who leads and what role the teammate plays. |
| Roadmap (Oct-Dec) | Weekly view of 22 items through Dec 18. |
| Daily plan (Oct 1-30) | Per-day work blocks and learning, with a "done when" test for each. |
| Data audit | Scorecard deciding the crop. Scores each public dataset on size, real-field conditions, licence and independence, then recommends tea or coffee. |
| Teammate ramp | Daily learning with links and a "you can prove it by" test. |
| Prerequisites | 28 things needed before or during the work, with owner and due date. |
| Reminders | Standalone reminders, mirrored as alarms in the calendar files. |

## How this maps to GitHub issues

Each task block in the Daily plan is a GitHub issue. Issues carry the detail: why the task matters, the steps, the checklist to satisfy before closing, and learning resources.

The workbook stays the calendar-shaped view — what happens when, and who is doing it. The issues are the working record.

## Gates

| Gate | Date | Test |
|---|---|---|
| Gate 0 | Oct 2 | Linux route decided: does Gazebo with a camera reach about 10 FPS? |
| Gate 1 | Oct 16 | Crop chosen, baseline model trained, robot drives in Gazebo, slope analysis done |
| Gate 2 | Oct 30 | Cross-dataset gap number, robot navigating terrain worlds, design constraints, chassis concept, cost model |
| Gate 3 | Dec 18 | Tier 1 V1 package complete |

Pass marks for Gates 1 and 2 are set at the Oct 8 supervisor check-in.

## Editing

The workbook's blue cells are inputs; everything else is formulas. Close the file in Excel before it is regenerated, or Excel leaves a `~$` lock file behind (git ignores those).
