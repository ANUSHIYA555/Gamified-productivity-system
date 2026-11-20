# FocusQuest: Gamified Productivity System
> **Plan • Focus • Level Up**

A production-grade, gamified productivity web application built to the exact specifications of the ISO/IEC/IEEE 29148 SRS document and the neon-purple gamified dashboard UI design.

---

## 🌟 Key Features & SRS Traceability

### 1. Dashboard & Visual System (1:1 UI Match)
* **Gamified Dark Theme**: Deep royal navy / cosmic purple aesthetic (`#0c0a1a`, `#191439`, `#7c3aed`) with luminous gradients, glowing status indicators, and rounded cards.
* **Top Header**: Live search input, notification badge ("1"), user avatar with online status, dynamic greeting ("Good Evening, Anushiya! ✨"), and Level 12 Golden Star widget (`720 / 1000 XP` progress bar).
* **Mascot (Focus Coach)**: Cute purple gamer kitty with headset and laptop delivering supportive feedback ("You're doing amazing! 💜").
* **Today's Progress**: Circular 75% SVG donut chart, 6/8 tasks indicator, 2h 15m focus time, and +50 XP counter.
* **Streak Card**: 7-Day streak counter with luminous fire graphic, motivation text, and weekly streak freeze status (FR-4.5, FR-4.9).
* **My Tasks**: Checkable tasks with priority badges (`High` - reddish pink, `Medium` - amber, `Low` - emerald) with live XP bonuses on completion (FR-4.2).
* **Weekly Overview**: 7-day column chart with glowing bars for Mon–Sun (FR-6.2).
* **Featured Achievements**: 3 featured badges matching the UI screenshot:
  * 🌟 **Task Master** (Complete 50 tasks)
  * 👑 **Focus Champ** (Focus for 10 hrs)
  * 📅 **On Track** (Maintain 7-day streak)
* **Next Reward Card**: 3D Gift Box illustration with progress toward 80% weekly productivity to unlock premium theme rewards.

---

### 2. Functional Capabilities

| ID | Requirement | Implementation |
|---|---|---|
| **FR-1.1 - FR-1.4** | Authentication & Roles | Registration, password hashing, session login/logout, profile customization, Google OAuth demo sign-in, and 3 distinct roles: **Learner**, **Task Assigner**, and **Administrator**. |
| **FR-2.1 - FR-2.7** | Task Management | CRUD operations, priorities, due dates, overdue sorting & highlighting, subtask checklists, and AI-powered task breakdowns. |
| **FR-3.1 - FR-3.9** | Focus Timer | Pomodoro cycles (25m Focus, 5m Short Break, 15m Long Break), start/pause/resume/abandon controls, server-timestamp drift-free countdown (NFR-3), session outcome logging, Web Audio crystal harmonic chimes, and browser notifications. |
| **FR-3.9** | Distraction Tracking | Page Visibility API detects tab switching during active sessions and increments the distraction count. |
| **FR-4.1 - FR-4.9** | Gamification Engine | 1 XP per focus minute; task completion bonuses (+10 Low, +20 Medium, +30 High); Level formula: Level $n \to n+1$ requires $100 \times n$ XP; 1 streak freeze per week; server-validated immutable XP ledger. |
| **FR-5.1 - FR-5.10** | Gemini Focus Coach | System prompt adhering to Section 4.3; task and timer context injection; <60 word concise responses during active focus; JSON structured breakdown; rate-limiting (30 msgs/hr); intelligent offline fallback when API key is not configured. |
| **FR-6.1 - FR-6.4** | Analytics & Export | 7-day and 30-day analytics charts, session history log, and CSV session export. |

---

## 🚀 Quick Start

### Prerequisites
- Python 3.10+ (Python 3.14 compatible)
- Django & Django REST Framework (pre-installed)

### Running the Application
Run the start batch file or execute manage.py:
```powershell
python manage.py runserver 127.0.0.1:8000
```
Open your browser and navigate to:
```
http://127.0.0.1:8000
```

---

## 🧪 Automated Testing
Run the comprehensive unit test suite covering gamification formulas, streak logic, badge unlocking, and Gemini coach rules:
```powershell
python manage.py test
```
Or execute the automated endpoint verification script:
```powershell
python verify_endpoints.py
```
