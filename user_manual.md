# User Manual

## Introduction

Women Safe Route helps users choose safer travel routes in Hyderabad by showing multiple paths ranked by safety rather than just distance.

## Getting Started

1. Run the application locally: `python app.py` and open `http://localhost:5000` in your browser.
2. Allow the app to access your location if prompted, or enter start and end points manually.

## Searching for Safe Routes

- Enter your starting point and destination.
- Tap **Find Safe Routes**.
- The app displays up to three route options: Safest, Balanced, and Shortest.

Each route shows:

- Safety Score (0–10)
- Distance
- Estimated duration
- Nearby police stations and hospitals
- Lit road percentage

## Choosing a Route

- Review the safety score and nearby features.
- Select a preferred route by tapping the route on the map or choosing it from the list.

## During Travel

- Monitor live GPS position on the map.
- Tap the red SOS button to send your current location to emergency contacts.

## After Travel

- Submit a community safety report (1–10) for the route you took — this improves future scores.

## Safety Tips

- Prefer routes with better lighting and nearby police/hospitals even if slightly longer.
- Share trip details with a trusted contact when travelling alone.

## Troubleshooting

- Map not loading: refresh the page and check internet connection.
- GPS unavailable: enter start/end points manually.
- Route search fails: check backend is running (`python app.py`) and the server logs for errors.

This manual is a concise reference. Expand with screenshots and step-by-step UI guides as the app UI matures.
