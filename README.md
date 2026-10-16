# 🗳️ Secure AI Facial e-Voting Platform

An end-to-end, multi-tenant digital election and facial recognition voting platform built with **Python, Flask, SQLAlchemy, SQLite, face-api.js, OpenCV, Bootstrap 5 (Glassmorphism), and Chart.js**.

---

## 🌟 Key Features

### 1. 💼 Election Conductor & Subscription System
- **Conduct an Election**: Create new elections on-demand with live duration and cost estimation (₹499/hr).
- **3-Step Setup Wizard (`/setup/<election_id>`)**:
  - **Step 1 — Candidate Roster**: Add and manage candidates/positions with live dynamic rosters.
  - **Step 2 — Biometric Voter Registration**: Capture face photos via webcam and generate 128-dimensional facial descriptors with duplicate face detection (tolerance = 0.5).
  - **Step 3 — Launch & Share**: Publish elections and generate shareable voting links (`/vote/<election_id>`) with one-click clipboard copying.

### 2. 👤 AI-Powered Facial Voter Authentication
- **Zero-Credential Login**: Voters scan their face via webcam for instant facial authentication using client-side `face-api.js` and server verification.
- **Election-Scoped Security**: Face matching is strictly scoped to the registered voter roster of the specific active election.
- **Strict Eligibility Enforcement**: Enforces age restrictions ($\ge 18$) and prevents duplicate voting.

### 3. 🗳️ Election-Scoped Ballot & Receipt
- **Dynamic Ballot (`/vote`)**: Displays candidate lists and party logos filtered specifically for the active election.
- **Atomic Vote Recording**: Single-transaction database commits with audit timestamps and optional Google Sheets cloud sync.
- **Encrypted Digital Receipt (`/confirmation`)**: Generates a verified vote confirmation showing voter name, election title, and timestamp.

### 4. 📊 Comprehensive Admin & Analytics Dashboard
- **All Elections Overview (`/admin/results`)**: Track all conducted elections, active/inactive statuses, registered voter counts, and total votes cast.
- **Live Visual Results (`/admin/results/<election_id>`)**: Real-time Chart.js bar charts with automatic 5-second polling and candidate vote share breakdowns.

---

## 🛠️ Technology Stack

- **Backend**: Python 3.8+, Flask, Flask-SQLAlchemy, SQLite
- **Computer Vision & Biometrics**: `face-api.js` (client-side neural nets), OpenCV (`opencv-python`), NumPy
- **Frontend & Styling**: Jinja2 Templates, HTML5 Canvas/WebRTC, Vanilla CSS (Dark-Theme Glassmorphism), Bootstrap 5, Bootstrap Icons
- **Data Visualization**: Chart.js

---

## 🚀 Getting Started

### 1. Clone & Install Dependencies
```bash
pip install Flask Flask-SQLAlchemy requests opencv-python numpy
```

### 2. Initialize and Seed the Database
Seed sample elections (College Student Election 2026 & Department Head Vote) along with candidate rosters and pending voters:
```bash
python seed.py
```

### 3. Start the Application
```bash
python app.py
```
The server will start on `http://127.0.0.1:5001`.

---

## 📍 Quick Navigation & URLs

| Portal / Feature | URL | Description |
| :--- | :--- | :--- |
| **Home Portal** | `http://127.0.0.1:5001/` | Facial voter login & Conduct an Election subscription |
| **Election 1 Setup** | `http://127.0.0.1:5001/setup/1` | Conductor setup wizard for Election #1 |
| **Election 1 Voting** | `http://127.0.0.1:5001/vote/1` | Shareable voter authentication landing for Election #1 |
| **Election 1 Live Results** | `http://127.0.0.1:5001/admin/results/1` | Real-time vote tally chart for Election #1 |
| **Admin Overview** | `http://127.0.0.1:5001/admin/results` | View and monitor all elections |
| **Admin Login** | `http://127.0.0.1:5001/admin` | Admin Portal Login (PIN: `12345`) |

---

## 🔒 Security & Privacy Architecture

- **Biometric Encodings**: Facial landmarks are converted into mathematical embeddings (128-d float vectors) without persisting raw sensitive credentials.
- **Session Scoping**: Active elections isolate voting sessions and candidate selections to prevent cross-election interference.
- **One-Vote Constraint**: Database-level boolean flags ensure each registered voter can only submit a ballot once per election.
