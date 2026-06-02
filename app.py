from flask import Flask, jsonify, render_template
import json

app = Flask(__name__)

def police_score_from_distance(m):
    if m <= 500:
        return 10.0
    if m <= 1000:
        return 8.0
    if m <= 2000:
        return 6.0
    if m <= 5000:
        return 4.0
    return 2.0

def hospital_score_from_distance(m):
    if m <= 1000:
        return 10.0
    if m <= 2000:
        return 8.0
    if m <= 5000:
        return 6.0
    return 3.0

def community_score(pos, neg):
    total = pos + neg
    if total == 0:
        return 5.0
    ratio = pos / total
    return ratio * 10.0

def compute_segment_score(seg):
    lighting = float(seg.get('lighting', 0.5))
    police_d = float(seg.get('police_distance_m', 5000))
    hospital_d = float(seg.get('hospital_distance_m', 5000))
    pos = int(seg.get('community_positive', 0))
    neg = int(seg.get('community_negative', 0))
    police = police_score_from_distance(police_d)
    hospital = hospital_score_from_distance(hospital_d)
    community = community_score(pos, neg)
    seg_score = 0.4 * (lighting * 10.0) + 0.3 * police + 0.2 * hospital + 0.1 * community
    return {
        'lighting_score': round(lighting * 10.0, 2),
        'police_score': round(police, 2),
        'hospital_score': round(hospital, 2),
        'community_score': round(community, 2),
        'segment_score': round(seg_score, 3)
    }

def compute_route_scores(route):
    segments = route['segments']
    total_len = sum(s.get('length_m', 1.0) for s in segments)
    if total_len == 0:
        total_len = len(segments)
    weighted_sum = 0.0
    per_segment = []
    well_lit_len = 0.0
    police_within_500 = 0
    hospital_within_1000 = 0
    total_pos_reports = 0
    total_neg_reports = 0
    risky_segments = []
    for i, s in enumerate(segments):
        meta = compute_segment_score(s)
        length = float(s.get('length_m', 1.0))
        weighted_sum += meta['segment_score'] * length
        per_segment.append({**s, **meta, 'id': i})
        if s.get('lighting', 0) >= 0.8:
            well_lit_len += length
        if s.get('police_distance_m', 99999) <= 500:
            police_within_500 += int(s.get('police_count', 0))
        if s.get('hospital_distance_m', 99999) <= 1000:
            hospital_within_1000 += int(s.get('hospital_count', 0))
        total_pos_reports += int(s.get('community_positive', 0))
        total_neg_reports += int(s.get('community_negative', 0))
        if meta['segment_score'] < 5.0:
            risky_segments.append({'id': i, 'score': meta['segment_score'], 'reason': 'Low composite score'})

    route_score = round((weighted_sum / total_len), 3)
    lighting_pct = round((well_lit_len / total_len) * 100.0, 1)
    insights = []
    insights.append(f"{lighting_pct}% of the route is well-lit")
    insights.append(f"{police_within_500} police stations within 500 meters")
    insights.append(f"{hospital_within_1000} hospitals within 1 kilometer")
    insights.append(f"{total_pos_reports} positive community safety reports")
    if risky_segments:
        insights.append(f"{len(risky_segments)} poorly scored segment(s) detected")

    # Factor breakdown (averaged across segments weighted by length)
    avg_lighting = sum((s.get('lighting', 0) * 10.0) * s.get('length_m', 1.0) for s in segments) / total_len
    avg_police = sum(compute_segment_score(s)['police_score'] * s.get('length_m', 1.0) for s in segments) / total_len
    avg_hospital = sum(compute_segment_score(s)['hospital_score'] * s.get('length_m', 1.0) for s in segments) / total_len
    avg_community = sum(compute_segment_score(s)['community_score'] * s.get('length_m', 1.0) for s in segments) / total_len

    breakdown = {
        'lighting': round(avg_lighting, 2),
        'police': round(avg_police, 2),
        'hospital': round(avg_hospital, 2),
        'community': round(avg_community, 2),
    }

    highest = max(breakdown.items(), key=lambda x: x[1])[0]
    lowest = min(breakdown.items(), key=lambda x: x[1])[0]

    report = {
        'route_score': route_score,
        'breakdown': breakdown,
        'final_score_display': round(route_score, 2),
        'insights': insights,
        'segments': per_segment,
        'lighting_coverage_pct': lighting_pct,
        'police_within_500': police_within_500,
        'hospital_within_1000': hospital_within_1000,
        'community_positive': total_pos_reports,
        'community_negative': total_neg_reports,
        'highest_factor': highest,
        'lowest_factor': lowest,
        'risky_segments': risky_segments,
    }
    return report

with open('data/sample_routes.json', 'r', encoding='utf-8') as f:
    SAMPLE = json.load(f)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/routes')
def routes_list():
    out = []
    for r in SAMPLE['routes']:
        # compute quick aggregate distance and est_time
        total_len = sum(s.get('length_m', 0) for s in r['segments'])
        est_time_min = round((total_len / 1000.0) / 4.5 * 60)  # assume 4.5 km/h walking
        report = compute_route_scores(r)
        out.append({
            'id': r['id'],
            'name': r['name'],
            'type': r.get('type', ''),
            'distance_m': total_len,
            'est_time_min': est_time_min,
            'safety_score': report['route_score']
        })
    return jsonify(out)

@app.route('/api/route/<int:route_id>')
def route_detail(route_id):
    r = next((x for x in SAMPLE['routes'] if x['id'] == route_id), None)
    if not r:
        return jsonify({'error': 'not found'}), 404
    report = compute_route_scores(r)
    return jsonify({'route': r, 'report': report})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
