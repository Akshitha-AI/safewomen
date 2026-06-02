# Agents Guide

This file is a temporary starting point describing suggested agent roles and responsibilities for the Women Safe Route project. It can be refined once the project codebase and workflows are in place.

## Project Agents Overview

The project may use the following agent roles:

- **Routing Agent** — evaluates route safety, calculates safety scores, and selects candidate routes.
- **Data Agent** — ingests OpenStreetMap data, computes proximity to police stations and hospitals, and prepares map layers.
- **UI Agent** — builds the frontend map experience, route comparison UI, and SOS interaction.
- **Support Agent** — handles documentation, user guides, API design, and community reporting flows.

## Suggested Agent Responsibilities

### Routing Agent

- Score road segments using lighting, police proximity, hospital proximity, and community ratings.
- Apply a modified Dijkstra algorithm for safety-aware routing.
- Return route summaries with distance, duration, and safety details.

### Data Agent

- Load Hyderabad road network using OSMnx and preprocess into a routable graph.
- Query police stations and hospitals from OpenStreetMap and cache results.
- Provide utilities to refresh cached data and export map layers used by the UI.

### UI Agent

- Display an interactive map with route overlays and comparison cards.
- Show route safety details and supporting layers (police, hospitals, lit roads).
- Implement SOS UI, live location updates, and route rating forms.

### Support Agent

- Maintain documentation: README, contribution guide, user manual, API docs.
- Define API endpoints and request/response formats for routing and reporting.
- Coordinate roadmap, tests, and community reporting workflows.

## Notes

This file is intended as a temporary starting point. Agent definitions and responsibilities should be refined as the code and team structure evolve.
