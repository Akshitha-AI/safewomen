 Agents Guide

> This file is a temporary placeholder. We can update it later based on project-specific agent workflows.

## Project Agents Overview

This project may use the following agent roles:

- **Routing Agent** — evaluates route safety, calculates safety scores, and selects candidate routes.
- **Data Agent** — ingests OpenStreetMap data, computes proximity to police stations and hospitals, and prepares map layers.
- **UI Agent** — builds the frontend map experience, route comparison UI, and SOS interaction.
- **Support Agent** — handles documentation, user guides, API design, and community reporting flows.

## Suggested Agent Responsibilities

### Routing Agent

- Score road segments using lighting, police proximity, hospital proximity, and community ratings
- Apply modified Dijkstra algorithm for safety-aware routing
- Return route summaries with distance, duration, and safety details

### Data Agent

- Load Hyderabad road network from OSMnx
- Query police stations and hospitals from OpenStreetMap
- Keep cached data updated and support offline use

### UI Agent

- Display interactive map with route overlays
- Show route safety details and comparison cards
- Provide SOS button and live location feedback

### Support Agent

- Maintain documentation files like README, contribution guide, and user manual
- Define API endpoints and request/response formats
- Coordinate future roadmap and feature planning

## Notes

This file is a temporary starting point. The agent definitions can be refined once the project code and workflow are ready.











# Contribution Guide

> This file is a temporary placeholder. We can update it later with exact contribution workflows after the project is built.

## How to Contribute

Thank you for helping improve Women Safe Route! Contributions are welcome from developers, designers, testers, and anyone interested in making the app safer and more useful.

### Ways to Contribute

- Fix bugs or improve routing logic
- Add new safety data sources or improve score calculations
- Improve frontend UI and mobile usability
- Add tests for backend APIs and data processing
- Help document setup, usage, and developer notes
- Translate UI strings and documentation

### Contribution Workflow

1. Fork the repository
2. Create a new branch with a clear name
   - `feature/safe-route-ui`
   - `fix/sos-button`
   - `docs/update-readme`
3. Make your changes
4. Run existing tests (if any)
5. Submit a pull request with a clear summary

### Coding Standards

- Keep code clean and readable
- Use descriptive variable and function names
- Add comments for non-obvious behavior
- Follow existing Python and HTML/CSS style patterns

### Reporting Issues

If you find a bug or want to propose a feature, please open an issue describing:

- What happened
- Where it happened
- How to reproduce it
- Why it matters for safety or usability

### Notes

This file is temporary and can be expanded with:

- exact branch naming rules
- commit message conventions
- testing requirements
- review checklist
- contribution agreement details







# 🛡️ Women Safe Route

> **Helping women choose the safest route — not just the shortest one.**

A smart navigation system built for Hyderabad that recommends safer travel routes by considering streetlight availability, nearby police stations, hospitals, and real community safety reports. Users can compare multiple routes with safety scores and choose what suits them best.

---

## 📌 Table of Contents

- [Problem Statement](#-problem-statement)
- [Our Solution](#-our-solution)
- [Key Features](#-key-features)
- [How the Safety Score Works](#-how-the-safety-score-works)
- [Data Sources](#-data-sources)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Installation & Setup](#-installation--setup)
- [How to Run](#-how-to-run)
- [How to Use the App](#-how-to-use-the-app)
- [API Endpoints](#-api-endpoints)
- [Screenshots](#-screenshots)
- [Future Roadmap](#-future-roadmap)
- [Team](#-team)

---

## 🚨 Problem Statement

Women traveling alone — especially at night — face serious safety risks due to:

- Poorly lit roads and isolated areas
- Lack of nearby police stations or hospitals
- No awareness of which routes are safer
- Existing apps (Google Maps, etc.) only optimize for **speed**, not **safety**

There is no navigation tool today that puts **women's safety** at the center of route planning.

---

## 💡 Our Solution

**Women Safe Route** calculates a **Safety Score (0–10)** for every road segment in Hyderabad using real open data, then shows the user **multiple route options** ranked by safety — so she can make her own informed choice.

Instead of one route, she sees:

| Route | Safety Score | Distance | What's along it |
|-------|-------------|----------|-----------------|
| Route A — Safest | 8.7 / 10 | 3.2 km | Lit roads, 2 police stations, 1 hospital |
| Route B — Balanced | 6.2 / 10 | 2.6 km | Partial lighting, 1 police station |
| Route C — Shortest | 4.1 / 10 | 2.1 km | No lighting, no police nearby |

She chooses. The app informs, not decides.

---

## ✨ Key Features

- 🗺️ **Multi-route display** — shows 3 routes with individual safety scores
- 🔢 **Safety Score Engine** — scores every road segment using 4 real data factors
- 🚨 **SOS Emergency Button** — one tap sends your live GPS location to saved contacts via SMS/WhatsApp
- 🏥 **Hospitals on map** — shows both government and private hospitals along each route
- 👮 **Police stations on map** — highlights all police stations within range
- 💡 **Lit road indicator** — shows which roads are well-lit vs dark
- 📝 **Community Reports** — users rate route safety after every trip, making the system smarter over time
- 📍 **Live GPS tracking** — tracks the user's position throughout the journey

---

## 🧮 How the Safety Score Works

Every road segment gets a score from **0 (very unsafe) to 10 (very safe)** using this formula:

```
Safety Score = (Lighting × 0.30) + (Police Proximity × 0.30) + (Hospital Proximity × 0.20) + (Community Rating × 0.20)
```

### Factor Breakdown

| Factor | Weight | How it's measured |
|--------|--------|-------------------|
| 🔦 Road lighting | 30% | OSM `lit=yes/no` tag on the road itself |
| 👮 Police station nearby | 30% | Nearest police station within 500m |
| 🏥 Hospital nearby | 20% | Nearest hospital (govt or private) within 1km |
| 👥 Community reports | 20% | Average safety rating submitted by app users |

### Routing Logic

We use a **modified Dijkstra's algorithm** where the route cost is:

```
Route Cost = Distance + (1 - Safety Score) × Penalty Factor
```

This means a slightly longer road that is very safe will always be preferred over a shorter road that is dark and isolated.

---

## 📊 Data Sources

All data used in this project is **real and freely available** — nothing is made up.

| Data | Source | How we get it |
|------|--------|---------------|
| All roads in Hyderabad | OpenStreetMap | `osmnx` Python library |
| Lit / unlit road status | OpenStreetMap (`lit=` tag) | `osmnx` Python library |
| Police station locations | OpenStreetMap | `osmnx` features query |
| Hospital locations (govt + private) | OpenStreetMap | `osmnx` features query |
| Community safety ratings | App users | Submitted through in-app form |

> **Note:** OpenStreetMap is a free, open-source, community-maintained map — like Wikipedia for geographic data. It already has every road, police station, and hospital in Hyderabad with GPS coordinates.

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+, Flask |
| Routing & Maps | OSMnx, NetworkX |
| Data Processing | Pandas, GeoPandas |
| Frontend Map | Folium (Leaflet.js) |
| Database | SQLite (community reports) |
| SOS Alerts | Twilio API (SMS) |
| Frontend UI | HTML, CSS, Bootstrap 5 |

---

## 📁 Project Structure

```
women-safe-route/
│
├── app.py                  # Flask app — main server & API routes (older demo)
├── streamlit_app.py        # Streamlit demo UI (recommended)
├── safety_engine.py        # Safety score calculation logic
├── routing.py              # Modified Dijkstra routing algorithm
├── data_loader.py          # Fetches OSM data (roads, police, hospitals)
├── sos.py                  # SOS alert via Twilio SMS
│
├── data/
│   └── community_reports.db    # SQLite DB for user-submitted ratings
│
├── templates/
│   ├── index.html          # Main map page
│   ├── result.html         # Route comparison page
│   └── report.html         # Community safety report form
│
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── map.js
│
├── requirements.txt
├── .env.example            # Template for environment variables
└── README.md
```

---

## ⚙️ Installation & Setup

### Prerequisites

- Python 3.10 or above
- pip
- Git
- A Twilio account (free trial works) for SOS SMS feature

### Step 1 — Clone the repository

```bash
git clone https://github.com/yourusername/women-safe-route.git
cd women-safe-route
```

### Step 2 — Create a virtual environment

```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On Mac/Linux
source venv/bin/activate
```

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Set up environment variables

Copy the example env file and fill in your credentials:

```bash
cp .env.example .env
```

Open `.env` and add:

```env
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=your_twilio_phone_number
EMERGENCY_CONTACT_1=+91XXXXXXXXXX
EMERGENCY_CONTACT_2=+91XXXXXXXXXX
```

### Step 5 — Download Hyderabad map data

This fetches all roads, police stations, and hospitals from OpenStreetMap. Run once — it caches locally:

```bash
python data_loader.py
```

> This may take 2–3 minutes the first time as it downloads the full Hyderabad road network.

---

## ▶️ How to Run

Run the Streamlit demo (recommended):

```powershell
python -m pip install -r requirements.txt
streamlit run streamlit_app.py
```

Open the URL shown by Streamlit (usually http://localhost:8501).

Alternatively run the Flask demo:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Open http://localhost:5000

---

## 📱 How to Use the App

1. **Open the app** at `localhost:5000`
2. **Enter your starting point** (or allow GPS to auto-detect)
3. **Enter your destination**
4. Click **"Find Safe Routes"**
5. The app shows **3 routes on the map** — each with its safety score, distance, and what's nearby (police stations, hospitals, lit roads)
6. **Choose your preferred route** — tap it on the map or select from the list
7. During your journey, tap the **red SOS button** at any time to send your live location to your emergency contacts
8. After you arrive, **rate your route's safety** (1–10) to help other women

---

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Home page with map |
| `POST` | `/routes` | Get safe routes between two points |
| `GET` | `/score?lat=&lng=` | Get safety score for a specific location |
| `POST` | `/report` | Submit a community safety report |
| `POST` | `/sos` | Trigger SOS alert to emergency contacts |
| `GET` | `/hospitals` | Get all hospitals near a location |
| `GET` | `/police` | Get all police stations near a location |

### Example — Get Routes

**Request:**
```json
POST /routes
{
  "start": [17.4156, 78.4347],
  "end": [17.4400, 78.3489]
}
```

**Response:**
```json
{
  "routes": [
    {
      "id": "A",
      "label": "Safest",
      "safety_score": 8.7,
      "distance_km": 3.2,
      "duration_min": 9,
      "lit_percentage": 85,
      "police_stations_nearby": 2,
      "hospitals_nearby": 1,
      "coordinates": [[17.415, 78.434], "..."]
    },
    {
      "id": "B",
      "label": "Balanced",
      "safety_score": 6.2,
      "distance_km": 2.6,
      "duration_min": 7,
      "lit_percentage": 55,
      "police_stations_nearby": 1,
      "hospitals_nearby": 1,
      "coordinates": ["..."]
    },
    {
      "id": "C",
      "label": "Shortest",
      "safety_score": 4.1,
      "distance_km": 2.1,
      "duration_min": 6,
      "lit_percentage": 20,
      "police_stations_nearby": 0,
      "hospitals_nearby": 0,
      "coordinates": ["..."]
    }
  ]
}
```

---

## 🖼️ Screenshots

> *(Add screenshots of your app here after building)*

```
screenshots/
├── home_screen.png
├── route_comparison.png
├── map_with_scores.png
└── sos_button.png
```

---

## 🚀 Future Roadmap

| Feature | Description |
|---------|-------------|
| 🔴 Live crime data | Integrate Telangana Police crime report API when available |
| 💡 GHMC streetlight API | Replace OSM lit tags with real-time GHMC CCMS streetlight status |
| 📸 CCTV coverage layer | Show roads covered by TSPOLICE surveillance cameras |
| 🤖 ML safety prediction | Train a model on historical community reports to predict unsafe times/areas |
| 🚌 Safe bus stop routing | Integrate TSRTC bus stop data for safer public transport routes |
| 📴 Offline mode | Cache map data for use without internet |
| 🌙 Time-aware scoring | Safety scores that change based on time of day (night vs day) |

---

## 👥 Team

| Name | Role |
|------|------|
| *(Your Name)* | Full Stack Developer |
| *(Team Member 2)* | Backend & Routing Logic |
| *(Team Member 3)* | UI/UX & Frontend |

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgements

- [OpenStreetMap](https://www.openstreetmap.org/) — for free, open geographic data
- [OSMnx](https://github.com/gboeing/osmnx) — for making OSM data easy to work with in Python
- [Twilio](https://www.twilio.com/) — for SMS alert infrastructure
- [Folium](https://python-visualization.github.io/folium/) — for interactive map rendering

---

<div align="center">
  <strong>Built with ❤️ for women's safety in Hyderabad</strong><br/>
  <em>"Don't just find the fastest route. Find the safest one."</em>
</div>







# User Manual

> This file is a temporary placeholder. We can update it later with the final app flow and UI details.

## Introduction

Women Safe Route helps users choose safer travel routes in Hyderabad by showing multiple paths ranked by safety rather than just distance.

## Getting Started

1. Open the app in your browser at `http://localhost:5000`
2. Allow the app to access your location if prompted
3. Enter your starting point and destination
4. Tap **"Find Safe Routes"**

## Reading the Route Options

The app displays up to three route options:

- **Safest Route** — highest safety score
- **Balanced Route** — good mix of safety and distance
- **Shortest Route** — usually the fastest, but may be less safe

Each option includes:

- Safety Score
- Distance
- Estimated duration
- Nearby police stations and hospitals
- Lit road percentage

## Choosing a Route

- Review the safety score and nearby safety features
- Select the route that feels best for your trip
- Follow the route on the map

## During Travel

- Monitor your live GPS position
- Use the **SOS button** if you feel unsafe
- The SOS feature sends your current location to saved emergency contacts

## After Travel

- Submit a **community safety report** to rate the route
- Your feedback helps improve the score for future users

## Safety Tips

- Choose the safest available route, even if it is slightly longer
- Prefer routes with better lighting and nearby police/hospitals
- Share your trip details with a trusted contact when traveling alone

## Troubleshooting

- If the map does not load, refresh the page
- If route search fails, check your internet connection
- If GPS location is unavailable, enter start and end points manually

## What’s Next

This manual will be expanded later with screenshots, exact UI controls, and any mobile-specific guidance.

## Demo Prototype

A small, self-contained demo was added to demonstrate the explainable scoring system (server + frontend).

Run the demo locally:

```powershell
python -m pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000/ to view an interactive map showing three sample routes, per-segment coloring, and a detailed explainable safety report for each route.

Files to inspect:

- [app.py](app.py) — demo Flask server and the scoring engine
- [data/sample_routes.json](data/sample_routes.json) — sample routes and segment metadata
- [templates/index.html](templates/index.html) — frontend using Leaflet to visualise routes and explanations


