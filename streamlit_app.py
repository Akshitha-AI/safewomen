import json
import math
from pathlib import Path

import folium
import requests
import streamlit as st
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium


APP_USER_AGENT = "women-safe-route-hackathon/1.0"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DEFAULT_REGION = "Hyderabad, Telangana, India"
ROUTE_CORRIDOR_M = 300
MAX_FACILITY_MARKERS = 36
MAX_SUPPORT_MARKERS = 60
MAX_DIVERSE_ANCHORS = 6


@st.cache_resource
def http_session():
    session = requests.Session()
    session.headers.update({"User-Agent": APP_USER_AGENT})
    return session

ROUTE_STYLES = {
    "recommended": {"color": "#22c55e", "label": "Safest Route", "badge": "Safest"},
    "balanced": {"color": "#f97316", "label": "Balanced Route", "badge": "Balanced"},
    "fastest": {"color": "#ef4444", "label": "Fastest Route", "badge": "Fastest"},
}

FACILITY_LABELS = {
    "hospital": "Hospital",
    "police": "Police Station",
}

COMMERCIAL_KINDS = {
    "bank",
    "fuel",
    "hospital",
    "clinic",
    "pharmacy",
    "restaurant",
    "cafe",
    "fast_food",
    "marketplace",
    "cinema",
}


class RoutingError(Exception):
    pass


def haversine_m(a, b):
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    x = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371000 * 2 * math.atan2(math.sqrt(x), math.sqrt(1 - x))


def point_to_segment_distance_m(point, start, end):
    lat0 = math.radians(point[0])
    scale = 111320
    px, py = point[1] * math.cos(lat0) * scale, point[0] * scale
    sx, sy = start[1] * math.cos(lat0) * scale, start[0] * scale
    ex, ey = end[1] * math.cos(lat0) * scale, end[0] * scale
    dx, dy = ex - sx, ey - sy
    if dx == 0 and dy == 0:
        return math.hypot(px - sx, py - sy)
    t = max(0, min(1, ((px - sx) * dx + (py - sy) * dy) / (dx * dx + dy * dy)))
    nearest_x, nearest_y = sx + t * dx, sy + t * dy
    return math.hypot(px - nearest_x, py - nearest_y)


def distance_to_route_m(point, coords):
    if len(coords) < 2:
        return float("inf")
    return min(point_to_segment_distance_m(point, coords[i], coords[i + 1]) for i in range(len(coords) - 1))


def bearing_degrees(start, end):
    lat1, lat2 = math.radians(start[0]), math.radians(end[0])
    dlon = math.radians(end[1] - start[1])
    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def turn_angle_degrees(a, b, c):
    first = bearing_degrees(a, b)
    second = bearing_degrees(b, c)
    diff = abs(second - first)
    return min(diff, 360 - diff)


def route_quality_penalty(coords, route_distance_m):
    if len(coords) < 4:
        return 0

    sharp_turns = 0
    near_uturns = 0
    for idx in range(1, len(coords) - 1):
        if haversine_m(coords[idx - 1], coords[idx]) < 18 or haversine_m(coords[idx], coords[idx + 1]) < 18:
            continue
        angle = turn_angle_degrees(coords[idx - 1], coords[idx], coords[idx + 1])
        if angle > 145:
            near_uturns += 1
        elif angle > 105:
            sharp_turns += 1

    visited_cells = set()
    revisits = 0
    sampled = coords[:: max(1, len(coords) // 160)]
    for point in sampled:
        cell = (round(point[0], 3), round(point[1], 3))
        if cell in visited_cells:
            revisits += 1
        visited_cells.add(cell)

    self_revisits = 0
    for idx, point in enumerate(sampled):
        for previous in sampled[: max(0, idx - 10)]:
            if haversine_m(point, previous) < 35:
                self_revisits += 1
                break

    direct_m = haversine_m(coords[0], coords[-1])
    inefficient_ratio = route_distance_m / max(direct_m, 1)
    loop_penalty = max(0, inefficient_ratio - 1.42) * 42
    return round(near_uturns * 22 + sharp_turns * 5 + revisits * 9 + self_revisits * 12 + loop_penalty, 2)


def dedupe_points(points, precision=5):
    seen = set()
    unique = []
    for point in points:
        key = (round(point["lat"], precision), round(point["lon"], precision), point["kind"], point.get("name", ""))
        if key not in seen:
            unique.append(point)
            seen.add(key)
    return unique


@st.cache_data(ttl=60 * 60 * 24, show_spinner=False)
def geocode_location(query):
    query = query.strip()
    search = query if "," in query else f"{query}, {DEFAULT_REGION}"
    response = http_session().get(
        NOMINATIM_URL,
        params={"q": search, "format": "json", "limit": 1, "addressdetails": 0},
        timeout=20,
    )
    response.raise_for_status()
    results = response.json()
    if not results:
        raise RoutingError(f"Could not geocode '{query}'. Try a more specific place name.")
    item = results[0]
    return {
        "name": item.get("display_name", query),
        "lat": float(item["lat"]),
        "lon": float(item["lon"]),
    }


@st.cache_data(ttl=60 * 60 * 12, show_spinner=False)
def osrm_request_cached(coords, alternatives):
    response = http_session().get(
        f"{OSRM_URL}/{coords}",
        params={
            "overview": "full",
            "geometries": "geojson",
            "steps": "true",
            "alternatives": "true" if alternatives else "false",
        },
        timeout=35,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != "Ok" or not payload.get("routes"):
        raise RoutingError(payload.get("message", "OSRM could not generate a road route."))
    return payload["routes"]


def osrm_request(waypoints, alternatives=True):
    coords = ";".join(f"{point['lon']:.6f},{point['lat']:.6f}" for point in waypoints)
    return osrm_request_cached(coords, alternatives)


def flatten_osrm_route(route, route_id, source, destination):
    raw_coords = [(lat, lon) for lon, lat in route["geometry"]["coordinates"]]
    step = max(1, len(raw_coords) // 180)
    coords = raw_coords[::step]
    if raw_coords[-1] != coords[-1]:
        coords.append(raw_coords[-1])
    if len(coords) < 2:
        raise RoutingError("OSRM returned an invalid route geometry.")
    return {
        "id": route_id,
        "source": source,
        "destination": destination,
        "distance_m": float(route["distance"]),
        "duration_s": float(route["duration"]),
        "geometry": coords,
        "quality_penalty": route_quality_penalty(coords, float(route["distance"])),
    }


def route_bbox(routes, padding=0.018):
    points = [point for route in routes for point in route["geometry"]]
    south = min(point[0] for point in points) - padding
    north = max(point[0] for point in points) + padding
    west = min(point[1] for point in points) - padding
    east = max(point[1] for point in points) + padding
    return south, west, north, east


@st.cache_data(ttl=60 * 60 * 12, show_spinner=False)
def fetch_overpass_context(south, west, north, east):
    south, west, north, east = [round(value, 4) for value in (south, west, north, east)]
    bbox = f"{south},{west},{north},{east}"
    query = f"""
    [out:json][timeout:35];
    (
      node["amenity"="police"]({bbox});
      way["amenity"="police"]({bbox});
      relation["amenity"="police"]({bbox});
      node["amenity"~"hospital|clinic"]({bbox});
      way["amenity"~"hospital|clinic"]({bbox});
      relation["amenity"~"hospital|clinic"]({bbox});
      node["highway"="street_lamp"]({bbox});
      node["man_made"="surveillance"]({bbox});
      node["surveillance:type"="camera"]({bbox});

      node["amenity"~"bank|fuel|hospital|clinic|pharmacy|restaurant|cafe|fast_food|marketplace|cinema"]({bbox});
      way["amenity"~"bank|fuel|hospital|clinic|pharmacy|restaurant|cafe|fast_food|marketplace|cinema"]({bbox});
      node["shop"]({bbox});
      way["shop"]({bbox});
      node["railway"="station"]({bbox});
      way["railway"="station"]({bbox});
      node["station"~"subway|metro"]({bbox});
      way["station"~"subway|metro"]({bbox});
      way["landuse"="commercial"]({bbox});
      way["building"~"commercial|retail|mall"]({bbox});
    );
    out center tags;
    """
    response = http_session().post(
        OVERPASS_URL,
        data={"data": query},
        timeout=45,
    )
    response.raise_for_status()
    pois = []
    for element in response.json().get("elements", []):
        tags = element.get("tags", {})
        lat = element.get("lat") or element.get("center", {}).get("lat")
        lon = element.get("lon") or element.get("center", {}).get("lon")
        if lat is None or lon is None:
            continue

        amenity = tags.get("amenity")
        if amenity == "police":
            kind = "police"
        elif amenity in {"hospital", "clinic"}:
            kind = "hospital"
        elif tags.get("highway") == "street_lamp":
            kind = "streetlight"
        elif tags.get("man_made") == "surveillance" or tags.get("surveillance:type") == "camera":
            kind = "cctv"
        elif (
            amenity in COMMERCIAL_KINDS
            or tags.get("shop")
            or tags.get("railway") == "station"
            or tags.get("station") in {"subway", "metro"}
            or tags.get("landuse") == "commercial"
            or tags.get("building") in {"commercial", "retail", "mall"}
        ):
            kind = "commercial"
        else:
            continue

        pois.append(
            {
                "kind": kind,
                "lat": float(lat),
                "lon": float(lon),
                "name": tags.get("name") or FACILITY_LABELS.get(kind, kind.replace("_", " ").title()),
            }
        )
    return dedupe_points(pois)


def load_community_reports():
    path = Path("data/community_reports.json")
    if not path.exists():
        return []
    try:
        reports = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    clean = []
    for report in reports:
        if "lat" not in report or "lon" not in report:
            continue
        clean.append(
            {
                "kind": "community",
                "lat": float(report["lat"]),
                "lon": float(report["lon"]),
                "name": report.get("title", "Community report"),
                "sentiment": report.get("sentiment", "neutral"),
            }
        )
    return clean


def route_similarity(route_a, route_b):
    sample = route_a["geometry"][:: max(1, len(route_a["geometry"]) // 35)]
    if not sample:
        return 0
    close = sum(1 for point in sample if distance_to_route_m(point, route_b["geometry"]) < 35)
    return close / len(sample)


def unique_routes(candidates, threshold=0.92):
    unique = []
    for route in sorted(candidates, key=lambda item: item["duration_s"] + item.get("quality_penalty", 0) * 18):
        if all(route_similarity(route, existing) < threshold for existing in unique):
            unique.append(route)
    return unique


def route_is_clean(route, fastest_distance_m):
    if route.get("quality_penalty", 0) > 95:
        return False
    if route["distance_m"] > fastest_distance_m * 1.65:
        return False
    return True


def generate_diverse_candidates(source, destination, pois, reference_routes):
    direct_m = haversine_m((source["lat"], source["lon"]), (destination["lat"], destination["lon"]))
    anchors = []
    for poi in pois:
        if poi["kind"] not in {"police", "hospital", "commercial"}:
            continue
        point = (poi["lat"], poi["lon"])
        route_distance = min(distance_to_route_m(point, route["geometry"]) for route in reference_routes)
        source_to_anchor = haversine_m((source["lat"], source["lon"]), point)
        anchor_to_destination = haversine_m(point, (destination["lat"], destination["lon"]))
        trip_air_m = source_to_anchor + anchor_to_destination
        if trip_air_m > direct_m * 1.65:
            continue
        if not 250 <= route_distance <= 2600:
            continue
        kind_weight = {"police": 0, "hospital": 1, "commercial": 2}[poi["kind"]]
        ideal_offset = abs(route_distance - 950)
        anchors.append((kind_weight, ideal_offset, trip_air_m, poi))

    anchors.sort(key=lambda item: (item[0], item[1], item[2]))
    candidates = []
    for _, _, _, anchor in anchors[:MAX_DIVERSE_ANCHORS]:
        waypoint = {"lat": anchor["lat"], "lon": anchor["lon"]}
        try:
            route = osrm_request([source, waypoint, destination], alternatives=False)[0]
            shaped = flatten_osrm_route(route, 100 + len(candidates), source, destination)
            shaped["candidate_kind"] = f"via {anchor['kind']}: {anchor['name']}"
            candidates.append(shaped)
        except Exception:
            continue

    if len(candidates) < 4:
        mid_lat = (source["lat"] + destination["lat"]) / 2
        mid_lon = (source["lon"] + destination["lon"]) / 2
        offsets = [
            (0.012, 0),
            (-0.012, 0),
            (0, 0.014),
            (0, -0.014),
        ]
        for lat_offset, lon_offset in offsets:
            waypoint = {"lat": mid_lat + lat_offset, "lon": mid_lon + lon_offset}
            try:
                route = osrm_request([source, waypoint, destination], alternatives=False)[0]
                shaped = flatten_osrm_route(route, 200 + len(candidates), source, destination)
                shaped["candidate_kind"] = "via alternate corridor"
                if shaped["distance_m"] <= direct_m * 1.9:
                    candidates.append(shaped)
            except Exception:
                continue
    return candidates


def nearby_facilities(route, pois, source):
    facilities = []
    for poi in pois:
        if poi["kind"] not in {"hospital", "police"}:
            continue
        point = (poi["lat"], poi["lon"])
        route_distance = distance_to_route_m(point, route["geometry"])
        if route_distance <= ROUTE_CORRIDOR_M:
            facilities.append(
                {
                    **poi,
                    "route_distance_m": route_distance,
                    "source_distance_m": haversine_m((source["lat"], source["lon"]), point),
                }
            )
    facilities.sort(key=lambda item: item["route_distance_m"])
    return facilities


def nearby_layer_items(route, pois, kind, radius_m):
    items = []
    for poi in pois:
        if poi["kind"] != kind:
            continue
        route_distance = distance_to_route_m((poi["lat"], poi["lon"]), route["geometry"])
        if route_distance <= radius_m:
            items.append({**poi, "route_distance_m": route_distance})
    items.sort(key=lambda item: item["route_distance_m"])
    return items[:MAX_SUPPORT_MARKERS]


def estimate_cctv_coverage(route, commercial_pois):
    total_m = 0
    covered_m = 0
    sampled_segments = list(zip(route["geometry"], route["geometry"][1:]))
    step = max(1, len(sampled_segments) // 140)
    for start, end in sampled_segments[::step]:
        segment_m = haversine_m(start, end)
        if segment_m <= 0:
            continue
        midpoint = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
        total_m += segment_m
        if any(haversine_m(midpoint, (poi["lat"], poi["lon"])) <= 220 for poi in commercial_pois):
            covered_m += segment_m
    if total_m == 0:
        return 0
    return round(min(96, (covered_m / total_m) * 100))


def cctv_label(coverage):
    if coverage >= 70:
        return "High", "#16a34a", "🟢"
    if coverage >= 40:
        return "Moderate", "#f97316", "🟠"
    return "Low", "#dc2626", "🔴"


def commercial_activity_label(commercial_count, distance_km):
    density = commercial_count / max(distance_km, 0.1)
    if density >= 12:
        return "High"
    if density >= 5:
        return "Moderate"
    return "Low"


def confidence_level(hospitals, police, cctv_coverage, commercial_activity):
    confidence = 48
    confidence += min(16, len(hospitals) * 4)
    confidence += min(14, len(police) * 7)
    confidence += round(cctv_coverage * 0.18)
    confidence += {"High": 9, "Moderate": 5, "Low": 1}[commercial_activity]
    return min(95, confidence)


def enrich_route(route, pois, source, community_reports):
    facilities = nearby_facilities(route, pois, source)
    hospitals = [item for item in facilities if item["kind"] == "hospital"]
    police = [item for item in facilities if item["kind"] == "police"]
    streetlights = nearby_layer_items(route, pois, "streetlight", 100)
    cctv_points = nearby_layer_items(route, pois, "cctv", 160)
    community = [
        {**item, "route_distance_m": distance_to_route_m((item["lat"], item["lon"]), route["geometry"])}
        for item in community_reports
        if distance_to_route_m((item["lat"], item["lon"]), route["geometry"]) <= 140
    ]
    commercial = [
        poi
        for poi in pois
        if poi["kind"] == "commercial" and distance_to_route_m((poi["lat"], poi["lon"]), route["geometry"]) <= ROUTE_CORRIDOR_M
    ]
    distance_km = route["distance_m"] / 1000
    cctv_coverage = estimate_cctv_coverage(route, commercial)
    commercial_activity = commercial_activity_label(len(commercial), distance_km)
    confidence = confidence_level(hospitals, police, cctv_coverage, commercial_activity)
    route["context"] = {
        "facilities": facilities,
        "hospitals": hospitals,
        "police": police,
        "streetlights": streetlights,
        "cctv_points": cctv_points,
        "community": community,
        "commercial_count": len(commercial),
        "commercial_activity": commercial_activity,
        "cctv_coverage": cctv_coverage,
        "confidence": confidence,
    }
    return route


def rank_route(route):
    context = route["context"]
    access_score = min(28, len(context["hospitals"]) * 5) + min(24, len(context["police"]) * 8)
    cctv_score = context["cctv_coverage"] * 0.32
    activity_score = {"High": 16, "Moderate": 9, "Low": 2}[context["commercial_activity"]]
    time_penalty = route["duration_s"] / 120
    quality_penalty = route.get("quality_penalty", 0) * 1.4
    return access_score + cctv_score + activity_score - time_penalty - quality_penalty


def pick_different_route(pool, preferred, existing, similarity_limit=0.78):
    different = [route for route in pool if all(route_similarity(route, selected) < similarity_limit for selected in existing)]
    if different:
        return preferred(different)
    softer = [route for route in pool if all(route_similarity(route, selected) < 0.9 for selected in existing)]
    if softer:
        return preferred(softer)
    return preferred(pool)


def select_display_routes(routes):
    fastest_distance = min(route["distance_m"] for route in routes)
    clean_routes = [route for route in routes if route_is_clean(route, fastest_distance)] or routes

    fastest = min(clean_routes, key=lambda route: route["duration_s"] + route.get("quality_penalty", 0) * 10)
    safest = pick_different_route(clean_routes, lambda pool: max(pool, key=rank_route), [fastest], similarity_limit=0.74)

    def balanced_choice(pool):
        max_rank = max(rank_route(route) for route in clean_routes) or 1
        min_rank = min(rank_route(route) for route in clean_routes)
        slowest = max(route["duration_s"] for route in clean_routes) or 1
        return max(
            pool,
            key=lambda route: (
                0.45 * ((rank_route(route) - min_rank) / max(max_rank - min_rank, 1))
                + 0.35 * (1 - route["duration_s"] / slowest)
                + 0.20 * min(route_similarity(route, safest), route_similarity(route, fastest))
                - route.get("quality_penalty", 0) / 120
            ),
        )

    balanced = pick_different_route(clean_routes, balanced_choice, [safest, fastest], similarity_limit=0.72)
    ordered = [("recommended", safest), ("balanced", balanced), ("fastest", fastest)]
    selected = []
    used = set()
    for route_type, route in ordered:
        if id(route) in used:
            route = pick_different_route(clean_routes, lambda pool: max(pool, key=rank_route), selected, similarity_limit=0.68)
        shaped = dict(route)
        shaped["type"] = route_type
        shaped["name"] = ROUTE_STYLES[route_type]["label"]
        shaped["id"] = len(selected) + 1
        selected.append(shaped)
        used.add(id(route))
    return selected


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def build_routes(source_text, destination_text):
    source_text = source_text.strip()
    destination_text = destination_text.strip()
    source = geocode_location(source_text)
    destination = geocode_location(destination_text)
    base_routes = [
        flatten_osrm_route(route, idx + 1, source, destination)
        for idx, route in enumerate(osrm_request([source, destination], alternatives=True))
    ]
    bbox = route_bbox(base_routes, padding=0.035)
    pois = fetch_overpass_context(*bbox)
    diverse_candidates = generate_diverse_candidates(source, destination, pois, base_routes)
    routes = unique_routes(base_routes + diverse_candidates, threshold=0.86)
    community_reports = load_community_reports()
    routes = [enrich_route(route, pois, source, community_reports) for route in routes]
    return select_display_routes(routes), source, destination


@st.cache_data(ttl=60 * 60 * 6, show_spinner=False)
def build_facility_route(source_lat, source_lon, facility_lat, facility_lon):
    source = {"lat": source_lat, "lon": source_lon}
    facility = {"lat": facility_lat, "lon": facility_lon}
    route = osrm_request([source, facility], alternatives=False)[0]
    return {
        "distance_m": float(route["distance"]),
        "duration_s": float(route["duration"]),
        "geometry": [(lat, lon) for lon, lat in route["geometry"]["coordinates"]],
    }


def format_distance(meters):
    if meters >= 1000:
        return f"{meters / 1000:.1f} km"
    return f"{round(meters)} m"


def all_route_points(route, facility_route=None):
    points = list(route["geometry"])
    if facility_route:
        points += facility_route["geometry"]
    return points


def facility_popup_html(facility):
    if facility["kind"] == "hospital":
        distance_line = f"<div>Distance from current location: <b>{format_distance(facility['source_distance_m'])}</b></div>"
    else:
        distance_line = ""
    return f"""
    <div style="font-family:Arial,sans-serif;min-width:220px;">
      <div style="font-weight:700;font-size:14px;margin-bottom:6px;">{facility['name']}</div>
      <div>{FACILITY_LABELS[facility['kind']]}</div>
      <div>Distance from route: <b>{format_distance(facility['route_distance_m'])}</b></div>
      {distance_line}
      <div style="margin-top:8px;color:#2563eb;font-weight:700;">Select this marker, then use Show Route</div>
    </div>
    """


def marker_css():
    return """
    <style>
    .pulse-marker {
        position: relative;
        display: flex;
        align-items: center;
        gap: 6px;
        padding: 10px 14px;
        border-radius: 999px;
        color: #fff;
        font: 900 14px Arial, sans-serif;
        letter-spacing: .4px;
        box-shadow: 0 16px 34px rgba(15, 23, 42, .34), 0 0 0 4px rgba(255,255,255,.9);
        white-space: nowrap;
        transform: translate(-16px, -16px);
    }
    .pulse-marker::after {
        content: "";
        position: absolute;
        inset: -10px;
        border-radius: 999px;
        border: 4px solid currentColor;
        opacity: .45;
        animation: routePulse 1.45s ease-out infinite;
    }
    .source-marker { background: #15803d; color: #86efac; }
    .dest-marker { background: #b91c1c; color: #fecaca; }
    .source-marker span, .dest-marker span { color: #fff; }
    .tiny-map-icon {
        display: grid;
        place-items: center;
        border-radius: 999px;
        border: 1px solid rgba(255,255,255,.9);
        box-shadow: 0 4px 12px rgba(15, 23, 42, .26);
        font: 800 12px Arial, sans-serif;
    }
    .hospital-icon { width: 14px; height: 14px; background: #ef4444; color: #fff; }
    .police-icon { width: 16px; height: 16px; background: #2563eb; color: #fff; font-size: 11px; }
    .soft-layer-icon { width: 10px; height: 10px; background: #facc15; color: #713f12; font-size: 8px; opacity: .88; }
    .cctv-layer-icon { width: 10px; height: 10px; background: #7c3aed; color: #fff; font-size: 8px; opacity: .88; }
    .community-layer-icon { width: 10px; height: 10px; background: #f97316; color: #fff; font-size: 8px; opacity: .88; }
    @keyframes routePulse {
        0% { transform: scale(.72); opacity: .55; }
        100% { transform: scale(1.55); opacity: 0; }
    }
    </style>
    """


def div_icon(html, size=(120, 36), anchor=(20, 20)):
    return folium.DivIcon(html=html, icon_size=size, icon_anchor=anchor)


def small_facility_icon(kind):
    if kind == "hospital":
        return div_icon('<div class="tiny-map-icon hospital-icon">+</div>', size=(14, 14), anchor=(7, 7))
    return div_icon('<div class="tiny-map-icon police-icon">!</div>', size=(16, 16), anchor=(8, 8))


def small_layer_icon(kind):
    class_name = {
        "streetlight": "soft-layer-icon",
        "cctv": "cctv-layer-icon",
        "community": "community-layer-icon",
    }[kind]
    label = {"streetlight": "L", "cctv": "C", "community": "R"}[kind]
    return div_icon(f'<div class="tiny-map-icon {class_name}">{label}</div>', size=(10, 10), anchor=(5, 5))


def add_clustered_facilities(map_obj, route):
    hospitals = MarkerCluster(name="Hospitals", show=True, overlay=True, control=True).add_to(map_obj)
    police = MarkerCluster(name="Police Stations", show=True, overlay=True, control=True).add_to(map_obj)
    facilities = sorted(route["context"]["facilities"], key=lambda item: item["route_distance_m"])[:MAX_FACILITY_MARKERS]
    for facility in facilities:
        target = hospitals if facility["kind"] == "hospital" else police
        tooltip_label = facility["name"] if facility["kind"] == "hospital" else f"Police Station: {facility['name']}"
        folium.Marker(
            [facility["lat"], facility["lon"]],
            tooltip=f"{facility['kind']}::{facility['name']}::{tooltip_label}",
            popup=folium.Popup(facility_popup_html(facility), max_width=300),
            icon=small_facility_icon(facility["kind"]),
        ).add_to(target)


def add_support_layers(map_obj, route):
    layer_specs = [
        ("streetlights", "Street Lights", "streetlight", "Street light"),
        ("cctv_points", "CCTV Cameras", "cctv", "CCTV signal"),
        ("community", "Community Reports", "community", "Community report"),
    ]
    for context_key, layer_name, kind, fallback in layer_specs:
        cluster = MarkerCluster(name=layer_name, show=False, overlay=True, control=True).add_to(map_obj)
        for item in route["context"].get(context_key, [])[:MAX_SUPPORT_MARKERS]:
            folium.Marker(
                [item["lat"], item["lon"]],
                tooltip=item.get("name", fallback),
                popup=f"{item.get('name', fallback)}<br>Distance from route: {format_distance(item.get('route_distance_m', 0))}",
                icon=small_layer_icon(kind),
            ).add_to(cluster)


def add_route_legend(map_obj):
    legend_html = """
    <div style="position:fixed;bottom:24px;left:24px;z-index:9999;background:rgba(255,255,255,.88);
        backdrop-filter:blur(10px);border:1px solid rgba(148,163,184,.45);border-radius:8px;
        padding:10px 12px;font:12px Arial,sans-serif;color:#0f172a;box-shadow:0 12px 28px rgba(15,23,42,.16);">
      <div style="font-weight:800;margin-bottom:6px;">Map Legend</div>
      <div><span style="color:#22c55e;font-size:18px;">*</span> Safest route</div>
      <div><span style="color:#f97316;font-size:18px;">*</span> Balanced route</div>
      <div><span style="color:#ef4444;font-size:18px;">*</span> Fastest route</div>
      <div><span style="color:#ef4444;font-size:14px;">+</span> Hospital</div>
      <div><span style="color:#2563eb;font-size:14px;">!</span> Police station</div>
    </div>
    """
    map_obj.get_root().html.add_child(folium.Element(legend_html))


def make_route_map(routes, selected_route, source, destination, selected_facility=None, facility_route=None):
    points = [point for route in routes for point in route["geometry"]]
    if facility_route:
        points += facility_route["geometry"]
    center = [source["lat"], source["lon"]]
    if points:
        center = [sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)]
    map_obj = folium.Map(location=center, zoom_start=13, tiles="OpenStreetMap", control_scale=True)
    map_obj.get_root().html.add_child(folium.Element(marker_css()))

    for route in sorted(routes, key=lambda item: item["id"] == selected_route["id"]):
        style = ROUTE_STYLES[route["type"]]
        selected = route["id"] == selected_route["id"]
        if selected:
            folium.PolyLine(
                route["geometry"],
                color=style["color"],
                weight=18,
                opacity=0.22,
                line_cap="round",
                line_join="round",
            ).add_to(map_obj)
        folium.PolyLine(
            route["geometry"],
            color=style["color"],
            weight=12 if selected else 8,
            opacity=0.98 if selected else 0.58,
            tooltip=f"route::{route['type']}::{style['label']} | {route['distance_m'] / 1000:.1f} km | {round(route['duration_s'] / 60)} min",
            line_cap="round",
            line_join="round",
        ).add_to(map_obj)

    if facility_route:
        folium.PolyLine(
            facility_route["geometry"],
            color="#2563eb",
            weight=6,
            opacity=0.9,
            tooltip=f"Temporary facility route | {format_distance(facility_route['distance_m'])}",
            line_cap="round",
            line_join="round",
            dash_array="8,8",
        ).add_to(map_obj)

    add_clustered_facilities(map_obj, selected_route)
    add_support_layers(map_obj, selected_route)

    folium.Marker(
        [source["lat"], source["lon"]],
        tooltip=f"Source: {source['name']}",
        popup=f"📍 Source<br>{source['name']}",
        z_index_offset=1200,
        icon=div_icon('<div class="pulse-marker source-marker"><span>SOURCE START</span></div>', size=(142, 46), anchor=(22, 22)),
    ).add_to(map_obj)
    folium.Marker(
        [destination["lat"], destination["lon"]],
        tooltip=f"Destination: {destination['name']}",
        popup=f"🎯 Destination<br>{destination['name']}",
        z_index_offset=1200,
        icon=div_icon('<div class="pulse-marker dest-marker"><span>DESTINATION</span></div>', size=(148, 46), anchor=(22, 22)),
    ).add_to(map_obj)

    if points:
        map_obj.fit_bounds([[min(p[0] for p in points), min(p[1] for p in points)], [max(p[0] for p in points), max(p[1] for p in points)]])
    add_route_legend(map_obj)
    folium.LayerControl(collapsed=False).add_to(map_obj)
    return map_obj


def inject_css(dark_mode=False):
    app_bg = "#0f172a" if dark_mode else "#f8fafc"
    text = "#e5e7eb" if dark_mode else "#0f172a"
    muted = "#94a3b8" if dark_mode else "#64748b"
    card_bg = "rgba(15,23,42,.72)" if dark_mode else "rgba(255,255,255,.76)"
    card_border = "rgba(148,163,184,.24)" if dark_mode else "rgba(226,232,240,.88)"
    active_bg = "rgba(20,83,45,.42)" if dark_mode else "rgba(240,253,244,.86)"
    st.markdown(
        f"""
        <style>
        .stApp {{
            background: {app_bg};
            color: {text};
        }}
        .block-container {{
            padding-top: .9rem;
            padding-bottom: .8rem;
            max-width: 1560px;
        }}
        div[data-testid="stVerticalBlock"] {{ gap: .65rem; }}
        div[data-testid="stMetric"] {{
            background: {card_bg};
            border: 1px solid {card_border};
            border-radius: 8px;
            padding: 10px 12px;
            box-shadow: 0 14px 36px rgba(15,23,42,.12);
            backdrop-filter: blur(14px);
        }}
        .app-title {{ font-size: 28px; font-weight: 800; color: {text}; margin-bottom: 0; }}
        .app-subtitle {{ color: {muted}; margin-bottom: 10px; }}
        .panel {{
            background: {card_bg};
            border: 1px solid {card_border};
            border-radius: 8px;
            padding: 13px;
            box-shadow: 0 16px 40px rgba(15,23,42,.12);
            backdrop-filter: blur(14px);
            margin-bottom: 10px;
        }}
        .route-option {{
            background: {card_bg};
            border: 1px solid {card_border};
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 10px;
            transition: transform .16s ease, box-shadow .16s ease, border-color .16s ease;
        }}
        .route-option:hover {{ transform: translateY(-1px); box-shadow: 0 12px 28px rgba(15,23,42,.14); }}
        .route-option.active {{ border: 2px solid #22c55e; background: {active_bg}; }}
        .muted {{ color: {muted}; font-size: 13px; }}
        .checkline {{ margin: 7px 0; color: {text}; }}
        .status-pill {{
            display: inline-block;
            border-radius: 999px;
            padding: 4px 9px;
            font-weight: 700;
            font-size: 12px;
            background: #ecfeff;
            color: #155e75;
        }}
        .route-badge {{
            display: inline-flex;
            align-items: center;
            border-radius: 999px;
            padding: 3px 8px;
            font-size: 11px;
            font-weight: 800;
            color: white;
            margin-bottom: 7px;
        }}
        .stButton > button {{
            border-radius: 8px;
            transition: transform .16s ease, box-shadow .16s ease;
        }}
        .stButton > button:hover {{
            transform: translateY(-1px);
            box-shadow: 0 12px 26px rgba(15,23,42,.16);
        }}
        iframe {{ border-radius: 8px; box-shadow: 0 20px 48px rgba(15,23,42,.16); }}
        section.main > div {{ padding-bottom: 0; }}
        @media (max-width: 900px) {{
            .app-title {{ font-size: 24px; }}
            div[data-testid="column"] {{ width: 100% !important; flex: 1 1 100% !important; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_route_option(route, active):
    context = route["context"]
    active_class = " active" if active else ""
    style = ROUTE_STYLES[route["type"]]
    st.markdown(
        f"""
        <div class="route-option{active_class}">
            <div class="route-badge" style="background:{style['color']};">{style['badge']}</div>
            <div style="font-weight:800;color:{style['color']};">{route['name']}</div>
            <div class="muted">{route['distance_m'] / 1000:.1f} km | {round(route['duration_s'] / 60)} min</div>
            <div class="muted">{len(context['hospitals'])} hospitals | {len(context['police'])} police | {context['cctv_coverage']}% CCTV coverage</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_route_difference_panel(routes, selected_route):
    rows = []
    for route in routes:
        context = route["context"]
        rows.append(
            {
                "Route": ROUTE_STYLES[route["type"]]["badge"],
                "Distance": f"{route['distance_m'] / 1000:.1f} km",
                "ETA": f"{round(route['duration_s'] / 60)} min",
                "Hospitals": len(context["hospitals"]),
                "Police": len(context["police"]),
                "CCTV": f"{context['cctv_coverage']}%",
                "Quality": "Clean" if route.get("quality_penalty", 0) < 25 else "Moderate turns",
            }
        )
    st.markdown(
        """
        <div class="panel">
            <div style="font-weight:800;font-size:18px;margin-bottom:6px;">Route Differences</div>
            <div class="muted">Safest favors support access, Balanced keeps time and support close, Fastest prioritizes ETA while avoiding messy loops.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.dataframe(rows, hide_index=True, use_container_width=True, height=145)


def render_nearby_resources(route):
    facilities = route["context"]["facilities"][:8]
    if not facilities:
        return
    cards = []
    for facility in facilities:
        label = "Hospital" if facility["kind"] == "hospital" else "Police"
        cards.append(f"{label}: {facility['name']} ({format_distance(facility['route_distance_m'])})")
    st.markdown(
        f"""
        <div class="panel">
            <div style="font-weight:800;font-size:18px;margin-bottom:8px;">Closest Safety Resources</div>
            <div class="muted">{'<br>'.join(cards)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_summary(route):
    context = route["context"]
    coverage_label, color, icon = cctv_label(context["cctv_coverage"])
    st.subheader("Route Safety Summary")
    m1, m2 = st.columns(2)
    m1.metric("Route Distance", f"{route['distance_m'] / 1000:.1f} km")
    m2.metric("Estimated Time", f"{round(route['duration_s'] / 60)} min")
    m3, m4 = st.columns(2)
    m3.metric("Nearby Hospitals", f"{len(context['hospitals'])} Accessible")
    m4.metric("Nearby Police Stations", f"{len(context['police'])} Accessible")
    m5, m6 = st.columns(2)
    m5.metric("CCTV Coverage", f"{context['cctv_coverage']}%")
    m6.metric("Commercial Activity", context["commercial_activity"])
    st.metric("Confidence Level", f"{context['confidence']}%")

    st.markdown(
        f"""
        <div class="panel">
            <div style="font-weight:800;color:{color};">{coverage_label} CCTV Coverage</div>
            <div class="muted" style="margin-top:6px;">
                Approx. {context['cctv_coverage']}% of the route passes through commercial zones likely monitored by CCTV.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_explainability(route):
    context = route["context"]
    isolated_text = "No major isolated stretches detected" if context["commercial_activity"] != "Low" else "Some quieter stretches may need caution"
    st.subheader("Why is this route recommended?")
    st.markdown(
        f"""
        <div class="panel">
            <div class="checkline">✓ {len(context['hospitals'])} hospitals are accessible within {ROUTE_CORRIDOR_M}m</div>
            <div class="checkline">✓ {len(context['police'])} police stations are located close to the route</div>
            <div class="checkline">✓ Route passes through {context['commercial_activity'].lower()} commercial activity areas</div>
            <div class="checkline">✓ Approximately {context['cctv_coverage']}% CCTV coverage estimated</div>
            <div class="checkline">✓ {isolated_text}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def safety_score(route):
    context = route["context"]
    score = 5.8
    score += min(1.2, len(context["hospitals"]) * 0.25)
    score += min(1.1, len(context["police"]) * 0.45)
    score += context["cctv_coverage"] / 100 * 1.2
    score += {"High": 0.7, "Moderate": 0.35, "Low": 0.05}[context["commercial_activity"]]
    score -= min(0.7, route.get("quality_penalty", 0) / 120)
    return min(9.8, max(4.2, round(score, 1)))


def render_route_details(route):
    context = route["context"]
    positive = sum(1 for item in context.get("community", []) if item.get("sentiment") == "positive")
    negative = sum(1 for item in context.get("community", []) if item.get("sentiment") not in {"positive", "neutral"})
    lighting = "Excellent" if len(context.get("streetlights", [])) >= max(3, route["distance_m"] / 800) else "Limited public data"
    st.subheader(f"{ROUTE_STYLES[route['type']]['badge']} Route")
    st.markdown(
        f"""
        <div class="panel">
            <div class="route-badge" style="background:{ROUTE_STYLES[route['type']]['color']};">{ROUTE_STYLES[route['type']]['badge']}</div>
            <div style="font-size:26px;font-weight:800;">Safety Score: {safety_score(route)}</div>
            <div class="checkline"><b>Lighting:</b><br>{lighting}</div>
            <div class="checkline"><b>Police Coverage:</b><br>{len(context['police'])} stations within {ROUTE_CORRIDOR_M}m</div>
            <div class="checkline"><b>Hospital Access:</b><br>{len(context['hospitals'])} hospitals within {ROUTE_CORRIDOR_M}m</div>
            <div class="checkline"><b>Community Reports:</b><br>{positive} positive, {negative} negative near route</div>
            <div class="muted" style="margin-top:10px;">
                This route is recommended because it balances route clarity, nearby emergency support,
                commercial activity, and estimated monitored coverage better than the available alternatives.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def selected_facility_from_click(route, click_result):
    tooltip = click_result.get("last_object_clicked_tooltip") if click_result else None
    if not tooltip or "::" not in tooltip:
        return None
    parts = tooltip.split("::")
    if len(parts) < 2 or parts[0] not in {"hospital", "police"}:
        return None
    kind, name = parts[0], parts[1]
    for facility in route["context"]["facilities"]:
        if facility["kind"] == kind and facility["name"] == name:
            return facility
    return None


def route_choice_from_click(click_result):
    tooltip = click_result.get("last_object_clicked_tooltip") if click_result else None
    if not tooltip or not tooltip.startswith("route::"):
        return None
    route_type = tooltip.split("::", 2)[1]
    return {"recommended": "Safest", "balanced": "Balanced", "fastest": "Fastest"}.get(route_type)


def render_facility_panel(facility):
    label = FACILITY_LABELS[facility["kind"]]
    st.markdown(
        f"""
        <div class="panel">
            <div class="status-pill">{label}</div>
            <div style="font-weight:800;font-size:17px;margin-top:8px;">{facility['name']}</div>
            <div class="muted">Distance from route: {format_distance(facility['route_distance_m'])}</div>
            {f"<div class='muted'>Distance from current location: {format_distance(facility['source_distance_m'])}</div>" if facility['kind'] == 'hospital' else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )


def main():
    st.set_page_config(page_title="Women Safe Route", layout="wide", page_icon="📍")
    if "routes_payload" not in st.session_state:
        st.session_state.routes_payload = None
    if "selected_facility" not in st.session_state:
        st.session_state.selected_facility = None
    if "facility_route" not in st.session_state:
        st.session_state.facility_route = None
    if "active_route_choice" not in st.session_state:
        st.session_state.active_route_choice = None
    if "dark_mode" not in st.session_state:
        st.session_state.dark_mode = False
    if st.session_state.get("route_choice") not in {None, "Safest", "Balanced", "Fastest"}:
        st.session_state.route_choice = "Safest"

    inject_css(st.session_state.dark_mode)

    st.markdown('<div class="app-title">Women Safe Route</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="app-subtitle">A clean route view with nearby hospitals, police stations, commercial activity, and estimated CCTV coverage.</div>',
        unsafe_allow_html=True,
    )

    sidebar, map_col, insight_col = st.columns([1, 2, 1], gap="large")

    with sidebar:
        st.subheader("Route Planner")
        with st.form("route_search_form"):
            source_text = st.text_input("Source", value="Miyapur Hyderabad", placeholder="Enter starting point")
            destination_text = st.text_input("Destination", value="KPHB Hyderabad", placeholder="Enter destination")
            find_clicked = st.form_submit_button("Find Route", type="primary", use_container_width=True)
        route_pref = st.radio("Route", ["Safest", "Balanced", "Fastest"], horizontal=False, key="route_choice")
        st.toggle("Dark mode", key="dark_mode")

        st.divider()
        st.subheader("Emergency")
        st.button("SOS", type="primary", use_container_width=True)
        st.button("Call Emergency Contact", use_container_width=True)
        st.button("Share Live Route", use_container_width=True)
        st.info("CCTV coverage is estimated from nearby commercial and public activity signals. It is not a camera count.")

    if find_clicked:
        try:
            with st.spinner("Finding road route and nearby accessible facilities..."):
                st.session_state.routes_payload = build_routes(source_text, destination_text)
                st.session_state.selected_facility = None
                st.session_state.facility_route = None
        except Exception as exc:
            st.session_state.routes_payload = None
            st.error(f"Could not build route: {exc}")

    if not st.session_state.routes_payload:
        with map_col:
            st.info("Enter a source and destination, then choose Find Route.")
        with insight_col:
            st.info("The map will show only the source, destination, selected route, and nearby accessible facilities.")
        return

    routes, source, destination = st.session_state.routes_payload
    selected_route_id = {"Safest": 1, "Balanced": 2, "Fastest": 3}[route_pref]
    selected_route = next(route for route in routes if route["id"] == selected_route_id)
    if st.session_state.active_route_choice != route_pref:
        st.session_state.active_route_choice = route_pref
        st.session_state.selected_facility = None
        st.session_state.facility_route = None

    with map_col:
        st.caption(
            f"{source_text} → {destination_text} | actual road distance {selected_route['distance_m'] / 1000:.1f} km"
        )
        click_result = st_folium(
            make_route_map(
                routes,
                selected_route,
                source,
                destination,
                st.session_state.selected_facility,
                st.session_state.facility_route,
            ),
            width=None,
            height=780,
            returned_objects=["last_object_clicked_tooltip"],
        )
        clicked_route_choice = route_choice_from_click(click_result)
        if clicked_route_choice and clicked_route_choice != route_pref:
            st.session_state.route_choice = clicked_route_choice
            st.session_state.selected_facility = None
            st.session_state.facility_route = None
            st.rerun()
        clicked_facility = selected_facility_from_click(selected_route, click_result)
        if clicked_facility:
            st.session_state.selected_facility = clicked_facility

        route_cols = st.columns(3)
        for idx, route in enumerate(routes):
            with route_cols[idx]:
                render_route_option(route, route["id"] == selected_route_id)
        render_route_difference_panel(routes, selected_route)
        render_nearby_resources(selected_route)

    with insight_col:
        render_route_details(selected_route)
        render_summary(selected_route)
        render_explainability(selected_route)

        st.subheader("Selected Facility")
        if st.session_state.selected_facility:
            render_facility_panel(st.session_state.selected_facility)
            show_route = st.button("Show Route", type="primary", use_container_width=True)
            clear_route = st.button("Clear Facility Route", use_container_width=True)
            if show_route:
                facility = st.session_state.selected_facility
                with st.spinner("Drawing temporary route to selected facility..."):
                    st.session_state.facility_route = build_facility_route(
                        source["lat"],
                        source["lon"],
                        facility["lat"],
                        facility["lon"],
                    )
                st.rerun()
            if clear_route:
                st.session_state.facility_route = None
                st.rerun()
        else:
            st.info("Click a hospital or police marker on the map to view details and show a temporary route.")

        st.caption(
            f"Only hospitals and police stations within about {ROUTE_CORRIDOR_M}m of the selected route are shown."
        )


if __name__ == "__main__":
    main()
