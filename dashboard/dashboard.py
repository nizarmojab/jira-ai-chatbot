#!/usr/bin/env python3
"""
dashboard.py
============
Dashboard web pour le projet Jira Automotive (Stellantis / Capgemini).
Lance un serveur Flask local qui interroge l'API Jira en temps réel.

Usage :
    pip install flask requests python-dotenv
    python dashboard.py
    → ouvrir http://localhost:5000
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any, Dict, List

import requests
from requests.auth import HTTPBasicAuth
from flask import Flask, jsonify, render_template_string, render_template, request
from dotenv import load_dotenv

load_dotenv()

# Import multi-agent system
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from src.orchestrator import Orchestrator
from src.agents.search_agent import SearchAgent
from src.agents.analyze_agent import AnalyzeAgent

JIRA_BASE_URL  = os.getenv("JIRA_BASE_URL", "").rstrip("/")
JIRA_EMAIL     = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
PROJECT_KEY    = os.getenv("JIRA_PROJECT_KEY", "SCRUM")

app = Flask(__name__)

# Initialize multi-agent system
orchestrator = Orchestrator()
search_agent = SearchAgent()
analyze_agent = AnalyzeAgent()


# ──────────────────────────────────────────────
#  Jira helper
# ──────────────────────────────────────────────
def jira_search(jql: str, fields: List[str], max_results: int = 500) -> List[Dict]:
    """Paginated search using nextPageToken (Jira Cloud 2025 API)."""
    all_issues: List[Dict] = []
    next_token = None
    page_size = 100

    while len(all_issues) < max_results:
        payload: Dict[str, Any] = {
            "jql": jql,
            "maxResults": min(page_size, max_results - len(all_issues)),
            "fields": fields,
        }
        if next_token:
            payload["nextPageToken"] = next_token

        r = requests.post(
            f"{JIRA_BASE_URL}/rest/api/3/search/jql",
            auth=HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        issues = data.get("issues", [])
        if not issues:
            break
        all_issues.extend(issues)
        next_token = data.get("nextPageToken")
        if not next_token:
            break

    return all_issues


def jira_get(path: str) -> Any:
    r = requests.get(
        f"{JIRA_BASE_URL}{path}",
        auth=HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN),
        headers={"Accept": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


# ──────────────────────────────────────────────
#  API endpoints
# ──────────────────────────────────────────────
@app.route("/api/stats")
def api_stats():
    base = f"project = {PROJECT_KEY}"
    all_issues = jira_search(base, ["issuetype", "status", "priority", "labels",
                                     "assignee", "components", "duedate", "fixVersions"],
                             max_results=500)

    # Counts by type
    type_counts: Dict[str, int] = {}
    status_counts: Dict[str, int] = {}
    priority_counts: Dict[str, int] = {}
    component_counts: Dict[str, int] = {}

    blocked = overdue = regression = tech_debt = critical = 0
    test_pass = test_fail = test_blocked_count = 0

    from datetime import date
    today = date.today().isoformat()

    for iss in all_issues:
        f = iss["fields"]
        itype    = f.get("issuetype", {}).get("name", "?")
        status   = f.get("status",    {}).get("name", "?")
        priority = f.get("priority",  {}).get("name", "?")
        labels   = f.get("labels", [])
        due      = f.get("duedate") or ""
        comps    = [c["name"] for c in f.get("components", [])]

        type_counts[itype]       = type_counts.get(itype, 0) + 1
        status_counts[status]    = status_counts.get(status, 0) + 1
        priority_counts[priority] = priority_counts.get(priority, 0) + 1
        for c in (comps if comps else ["Unassigned"]):
            component_counts[c] = component_counts.get(c, 0) + 1

        if "blocked"    in labels or status == "Blocked": blocked += 1
        if "regression" in labels:                        regression += 1
        if "tech-debt"  in labels:                        tech_debt += 1
        if priority == "Highest" and itype == "Bug":      critical += 1
        if due and due < today and status != "Done":      overdue += 1
        if "test-passed"  in labels: test_pass    += 1
        if "test-failed"  in labels: test_fail    += 1
        if "test-blocked" in labels: test_blocked_count += 1

    return jsonify({
        "total":           len(all_issues),
        "blocked":         blocked,
        "overdue":         overdue,
        "regression":      regression,
        "tech_debt":       tech_debt,
        "critical_bugs":   critical,
        "test_pass":       test_pass,
        "test_fail":       test_fail,
        "test_blocked":    test_blocked_count,
        "by_type":         type_counts,
        "by_status":       status_counts,
        "by_priority":     priority_counts,
        "by_component":    component_counts,
    })


@app.route("/api/critical")
def api_critical():
    issues = jira_search(
        f"project = {PROJECT_KEY} AND issuetype = Bug AND priority = Highest ORDER BY updated DESC",
        ["summary", "status", "priority", "labels", "components", "duedate"],
        max_results=15,
    )
    return jsonify([{
        "key":       i["key"],
        "summary":   i["fields"]["summary"],
        "status":    i["fields"]["status"]["name"],
        "labels":    i["fields"]["labels"][:3],
        "url":       f"{JIRA_BASE_URL}/browse/{i['key']}",
    } for i in issues])


@app.route("/api/blocked")
def api_blocked():
    issues = jira_search(
        f"project = {PROJECT_KEY} AND (labels = blocked OR status = Blocked) ORDER BY priority DESC",
        ["summary", "status", "issuetype", "priority", "labels"],
        max_results=15,
    )
    return jsonify([{
        "key":     i["key"],
        "summary": i["fields"]["summary"],
        "type":    i["fields"]["issuetype"]["name"],
        "status":  i["fields"]["status"]["name"],
        "url":     f"{JIRA_BASE_URL}/browse/{i['key']}",
    } for i in issues])


@app.route("/api/regression")
def api_regression():
    issues = jira_search(
        f"project = {PROJECT_KEY} AND labels = regression ORDER BY created DESC",
        ["summary", "status", "priority", "labels"],
        max_results=10,
    )
    return jsonify([{
        "key":     i["key"],
        "summary": i["fields"]["summary"],
        "status":  i["fields"]["status"]["name"],
        "url":     f"{JIRA_BASE_URL}/browse/{i['key']}",
    } for i in issues])


@app.route("/api/overdue")
def api_overdue():
    from datetime import date
    today = date.today().isoformat()
    issues = jira_search(
        f'project = {PROJECT_KEY} AND duedate < "{today}" AND status != Done ORDER BY duedate ASC',
        ["summary", "status", "issuetype", "priority", "duedate"],
        max_results=15,
    )
    return jsonify([{
        "key":     i["key"],
        "summary": i["fields"]["summary"],
        "type":    i["fields"]["issuetype"]["name"],
        "due":     i["fields"].get("duedate", ""),
        "status":  i["fields"]["status"]["name"],
        "url":     f"{JIRA_BASE_URL}/browse/{i['key']}",
    } for i in issues])


@app.route("/api/techdebt")
def api_techdebt():
    issues = jira_search(
        f"project = {PROJECT_KEY} AND labels = tech-debt ORDER BY priority DESC",
        ["summary", "status", "priority", "labels"],
        max_results=10,
    )
    return jsonify([{
        "key":     i["key"],
        "summary": i["fields"]["summary"],
        "status":  i["fields"]["status"]["name"],
        "url":     f"{JIRA_BASE_URL}/browse/{i['key']}",
    } for i in issues])


@app.route("/api/sprint")
def api_sprint():
    try:
        boards = jira_get(f"/rest/agile/1.0/board?projectKeyOrId={PROJECT_KEY}")
        board_id = boards["values"][0]["id"]
        sprints  = jira_get(f"/rest/agile/1.0/board/{board_id}/sprint?state=active,closed&maxResults=10")
        result = []
        for s in sprints.get("values", []):
            result.append({
                "id":    s["id"],
                "name":  s["name"],
                "state": s["state"],
                "goal":  s.get("goal", ""),
                "start": s.get("startDate", "")[:10] if s.get("startDate") else "",
                "end":   s.get("endDate",   "")[:10] if s.get("endDate")   else "",
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ──────────────────────────────────────────────
#  HTML Dashboard
# ──────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Chatbot Jira — Automotive Dashboard</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {
    --bg:        #0a0e1a;
    --bg2:       #111827;
    --bg3:       #1a2236;
    --border:    #1e2d45;
    --accent:    #3b82f6;
    --accent2:   #06b6d4;
    --green:     #10b981;
    --red:       #ef4444;
    --orange:    #f59e0b;
    --purple:    #8b5cf6;
    --text:      #e2e8f0;
    --muted:     #64748b;
    --mono:      'Space Mono', monospace;
    --sans:      'DM Sans', sans-serif;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: var(--sans); min-height: 100vh; }

  /* Header */
  header {
    padding: 1.5rem 2rem;
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center; justify-content: space-between;
    background: var(--bg2);
  }
  .logo { font-family: var(--mono); font-size: 13px; color: var(--accent2); letter-spacing: .08em; }
  .logo span { color: var(--muted); }
  h1 { font-size: 18px; font-weight: 600; letter-spacing: -.02em; }
  .live { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--muted); font-family: var(--mono); }
  .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--green); animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }

  /* Layout */
  main { padding: 1.5rem 2rem; max-width: 1600px; margin: 0 auto; }

  /* KPI row */
  .kpi-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 12px; margin-bottom: 1.5rem;
  }
  .kpi {
    background: var(--bg2); border: 1px solid var(--border);
    border-radius: 10px; padding: 1rem 1.2rem;
    transition: border-color .2s;
  }
  .kpi:hover { border-color: var(--accent); }
  .kpi-label { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; margin-bottom: 6px; font-family: var(--mono); }
  .kpi-value { font-size: 28px; font-weight: 600; font-family: var(--mono); line-height: 1; }
  .kpi-value.red    { color: var(--red); }
  .kpi-value.orange { color: var(--orange); }
  .kpi-value.green  { color: var(--green); }
  .kpi-value.blue   { color: var(--accent); }
  .kpi-value.purple { color: var(--purple); }
  .kpi-sub { font-size: 11px; color: var(--muted); margin-top: 4px; }

  /* Charts row */
  .charts-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 12px; margin-bottom: 1.5rem;
  }
  .card {
    background: var(--bg2); border: 1px solid var(--border);
    border-radius: 10px; padding: 1.2rem;
  }
  .card-title {
    font-size: 11px; text-transform: uppercase; letter-spacing: .1em;
    color: var(--muted); font-family: var(--mono); margin-bottom: 1rem;
    display: flex; align-items: center; gap: 8px;
  }
  .card-title::before {
    content: ''; width: 3px; height: 12px;
    background: var(--accent); border-radius: 2px; display: inline-block;
  }
  .chart-wrap { position: relative; height: 180px; }

  /* Tables row */
  .tables-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px; margin-bottom: 1.5rem;
  }
  .issue-list { list-style: none; }
  .issue-item {
    display: flex; align-items: flex-start; gap: 10px;
    padding: 8px 0; border-bottom: 1px solid var(--border);
    font-size: 13px;
  }
  .issue-item:last-child { border-bottom: none; }
  .issue-key {
    font-family: var(--mono); font-size: 11px; color: var(--accent2);
    white-space: nowrap; padding-top: 1px; min-width: 80px;
    text-decoration: none;
  }
  .issue-key:hover { color: var(--accent); }
  .issue-summary { color: var(--text); flex: 1; line-height: 1.4; }
  .badge {
    font-size: 10px; font-family: var(--mono); padding: 2px 7px;
    border-radius: 4px; white-space: nowrap; font-weight: 700;
  }
  .badge-blocked  { background: #7f1d1d; color: #fca5a5; }
  .badge-done     { background: #064e3b; color: #6ee7b7; }
  .badge-progress { background: #1e3a5f; color: #93c5fd; }
  .badge-review   { background: #4a1d96; color: #c4b5fd; }
  .badge-todo     { background: #1f2937; color: #9ca3af; }
  .badge-red      { background: #7f1d1d; color: #fca5a5; }

  /* Sprints */
  .sprint-list { list-style: none; }
  .sprint-item {
    padding: 10px 0; border-bottom: 1px solid var(--border);
    font-size: 13px;
  }
  .sprint-item:last-child { border-bottom: none; }
  .sprint-header { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
  .sprint-name { font-weight: 500; }
  .sprint-state { font-size: 10px; font-family: var(--mono); padding: 2px 7px; border-radius: 4px; font-weight: 700; }
  .state-active { background: #065f46; color: #6ee7b7; }
  .state-closed { background: #1f2937; color: #6b7280; }
  .sprint-goal  { font-size: 12px; color: var(--muted); line-height: 1.4; }
  .sprint-dates { font-size: 11px; font-family: var(--mono); color: var(--muted); margin-top: 2px; }

  /* Test results */
  .test-bar { display: flex; height: 8px; border-radius: 4px; overflow: hidden; margin: 12px 0 8px; gap: 2px; }
  .test-pass-bar    { background: var(--green); }
  .test-fail-bar    { background: var(--red); }
  .test-blocked-bar { background: var(--orange); }
  .test-legend { display: flex; gap: 16px; font-size: 12px; }
  .test-legend-item { display: flex; align-items: center; gap: 5px; color: var(--muted); }
  .test-dot { width: 8px; height: 8px; border-radius: 50%; }

  /* Loading */
  .loading { color: var(--muted); font-size: 13px; font-family: var(--mono); padding: 1rem 0; }

  /* Refresh btn */
  .refresh-btn {
    background: none; border: 1px solid var(--border); color: var(--muted);
    padding: 6px 12px; border-radius: 6px; font-size: 12px; cursor: pointer;
    font-family: var(--mono); transition: all .2s;
  }
  .refresh-btn:hover { border-color: var(--accent); color: var(--accent); }

  @media (max-width: 1100px) {
    .charts-grid { grid-template-columns: 1fr 1fr; }
  }
  @media (max-width: 700px) {
    .charts-grid, .tables-grid { grid-template-columns: 1fr; }
    .kpi-grid { grid-template-columns: repeat(3, 1fr); }
  }
</style>
</head>
<body>

<header>
  <div>
    <div class="logo">STELLANTIS / CAPGEMINI <span>— SCRUM</span></div>
    <h1>Automotive Integration Dashboard</h1>
  </div>
  <div style="display:flex;align-items:center;gap:16px;">
    <button class="refresh-btn" onclick="loadAll()">↻ Refresh</button>
    <div class="live"><div class="dot"></div> LIVE</div>
  </div>
</header>

<main>

  <!-- KPIs -->
  <div class="kpi-grid" id="kpi-grid">
    <div class="kpi"><div class="kpi-label">Total tickets</div><div class="kpi-value blue" id="kpi-total">—</div></div>
    <div class="kpi"><div class="kpi-label">Bugs critiques</div><div class="kpi-value red" id="kpi-critical">—</div></div>
    <div class="kpi"><div class="kpi-label">Bloqués</div><div class="kpi-value red" id="kpi-blocked">—</div></div>
    <div class="kpi"><div class="kpi-label">Overdue</div><div class="kpi-value orange" id="kpi-overdue">—</div></div>
    <div class="kpi"><div class="kpi-label">Régressions</div><div class="kpi-value orange" id="kpi-regression">—</div></div>
    <div class="kpi"><div class="kpi-label">Tech debt</div><div class="kpi-value purple" id="kpi-techdebt">—</div></div>
    <div class="kpi"><div class="kpi-label">Tests passés</div><div class="kpi-value green" id="kpi-testpass">—</div></div>
    <div class="kpi"><div class="kpi-label">Tests échoués</div><div class="kpi-value red" id="kpi-testfail">—</div></div>
  </div>

  <!-- Charts -->
  <div class="charts-grid">
    <div class="card">
      <div class="card-title">Répartition par statut</div>
      <div class="chart-wrap"><canvas id="chartStatus"></canvas></div>
    </div>
    <div class="card">
      <div class="card-title">Répartition par type</div>
      <div class="chart-wrap"><canvas id="chartType"></canvas></div>
    </div>
    <div class="card">
      <div class="card-title">Bugs par composant</div>
      <div class="chart-wrap"><canvas id="chartComponent"></canvas></div>
    </div>
  </div>

  <!-- Tables row 1 -->
  <div class="tables-grid">
    <div class="card">
      <div class="card-title">Bugs critiques (Highest)</div>
      <ul class="issue-list" id="list-critical"><li class="loading">Chargement…</li></ul>
    </div>
    <div class="card">
      <div class="card-title">Tickets bloqués</div>
      <ul class="issue-list" id="list-blocked"><li class="loading">Chargement…</li></ul>
    </div>
  </div>

  <!-- Tables row 2 -->
  <div class="tables-grid">
    <div class="card">
      <div class="card-title">Régressions détectées</div>
      <ul class="issue-list" id="list-regression"><li class="loading">Chargement…</li></ul>
    </div>
    <div class="card">
      <div class="card-title">Tickets en retard</div>
      <ul class="issue-list" id="list-overdue"><li class="loading">Chargement…</li></ul>
    </div>
  </div>

  <!-- Sprints + Test results -->
  <div class="tables-grid">
    <div class="card">
      <div class="card-title">Sprints</div>
      <ul class="sprint-list" id="list-sprints"><li class="loading">Chargement…</li></ul>
    </div>
    <div class="card">
      <div class="card-title">Résultats des tests</div>
      <div id="test-results"><div class="loading">Chargement…</div></div>
      <div style="margin-top:1.5rem;">
        <div class="card-title" style="margin-bottom:.8rem;">Tech debt backlog</div>
        <ul class="issue-list" id="list-techdebt"></ul>
      </div>
    </div>
  </div>

</main>

<script>
const COLORS = {
  status: {
    'To Do':       '#64748b',
    'In Progress': '#3b82f6',
    'In Review':   '#8b5cf6',
    'Blocked':     '#ef4444',
    'Done':        '#10b981',
  },
  type: {
    'Bug':      '#ef4444',
    'Story':    '#3b82f6',
    'Task':     '#06b6d4',
    'Epic':     '#8b5cf6',
    'Subtask':  '#64748b',
    'Sub-task': '#64748b',
  },
  components: ['#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6','#06b6d4'],
};

const statusBadge = s => {
  const map = {
    'Blocked':'badge-blocked','Done':'badge-done',
    'In Progress':'badge-progress','In Review':'badge-review','To Do':'badge-todo'
  };
  return `<span class="badge ${map[s]||'badge-todo'}">${s}</span>`;
};

let chartStatus, chartType, chartComponent;

function makeChart(id, type, labels, data, colors) {
  const ctx = document.getElementById(id).getContext('2d');
  return new Chart(ctx, {
    type,
    data: {
      labels,
      datasets: [{ data, backgroundColor: colors,
        borderColor: '#0a0e1a', borderWidth: 2,
        hoverOffset: 6 }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'right', labels: {
          color: '#94a3b8', font: { family: 'DM Sans', size: 11 },
          boxWidth: 10, padding: 8,
        }},
        tooltip: { callbacks: {
          label: ctx => ` ${ctx.label}: ${ctx.raw}`
        }}
      },
    }
  });
}

function makeBar(id, labels, data, colors) {
  const ctx = document.getElementById(id).getContext('2d');
  return new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{ data, backgroundColor: colors, borderRadius: 4, borderSkipped: false }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#64748b', font: { size: 10 } }, grid: { color: '#1e2d45' } },
        y: { ticks: { color: '#64748b', font: { size: 10 } }, grid: { color: '#1e2d45' } },
      }
    }
  });
}

async function loadStats() {
  const d = await fetch('/api/stats').then(r => r.json());

  document.getElementById('kpi-total').textContent     = d.total;
  document.getElementById('kpi-critical').textContent  = d.critical_bugs;
  document.getElementById('kpi-blocked').textContent   = d.blocked;
  document.getElementById('kpi-overdue').textContent   = d.overdue;
  document.getElementById('kpi-regression').textContent = d.regression;
  document.getElementById('kpi-techdebt').textContent  = d.tech_debt;
  document.getElementById('kpi-testpass').textContent  = d.test_pass;
  document.getElementById('kpi-testfail').textContent  = d.test_fail;

  // Chart Status
  const sLabels = Object.keys(d.by_status);
  const sData   = Object.values(d.by_status);
  const sColors = sLabels.map(l => COLORS.status[l] || '#64748b');
  if (chartStatus) chartStatus.destroy();
  chartStatus = makeChart('chartStatus', 'doughnut', sLabels, sData, sColors);

  // Chart Type
  const tLabels = Object.keys(d.by_type);
  const tData   = Object.values(d.by_type);
  const tColors = tLabels.map(l => COLORS.type[l] || '#64748b');
  if (chartType) chartType.destroy();
  chartType = makeChart('chartType', 'doughnut', tLabels, tData, tColors);

  // Chart Components (bar)
  const cLabels = Object.keys(d.by_component).slice(0, 6);
  const cData   = cLabels.map(k => d.by_component[k]);
  if (chartComponent) chartComponent.destroy();
  chartComponent = makeBar('chartComponent', cLabels, cData, COLORS.components);

  // Test results bar
  const total = d.test_pass + d.test_fail + d.test_blocked;
  if (total > 0) {
    const pPct = (d.test_pass    / total * 100).toFixed(0);
    const fPct = (d.test_fail    / total * 100).toFixed(0);
    const bPct = (d.test_blocked / total * 100).toFixed(0);
    document.getElementById('test-results').innerHTML = `
      <div style="display:flex;justify-content:space-between;font-size:12px;color:var(--muted);margin-bottom:4px;">
        <span>Résultats — ${total} tests</span>
        <span style="color:var(--green);font-family:var(--mono)">${pPct}% PASS</span>
      </div>
      <div class="test-bar">
        <div class="test-pass-bar"    style="width:${pPct}%"></div>
        <div class="test-fail-bar"    style="width:${fPct}%"></div>
        <div class="test-blocked-bar" style="width:${bPct}%"></div>
      </div>
      <div class="test-legend">
        <div class="test-legend-item"><div class="test-dot" style="background:var(--green)"></div>${d.test_pass} PASS</div>
        <div class="test-legend-item"><div class="test-dot" style="background:var(--red)"></div>${d.test_fail} FAIL</div>
        <div class="test-legend-item"><div class="test-dot" style="background:var(--orange)"></div>${d.test_blocked} BLOCKED</div>
      </div>`;
  }
}

function renderIssueList(id, items, extra) {
  const el = document.getElementById(id);
  if (!items.length) { el.innerHTML = '<li class="loading">Aucun ticket.</li>'; return; }
  el.innerHTML = items.map(i => `
    <li class="issue-item">
      <a class="issue-key" href="${i.url}" target="_blank">${i.key}</a>
      <span class="issue-summary">${i.summary}</span>
      ${extra ? extra(i) : statusBadge(i.status)}
    </li>`).join('');
}

async function loadLists() {
  const [critical, blocked, regression, overdue, techdebt] = await Promise.all([
    fetch('/api/critical').then(r => r.json()),
    fetch('/api/blocked').then(r => r.json()),
    fetch('/api/regression').then(r => r.json()),
    fetch('/api/overdue').then(r => r.json()),
    fetch('/api/techdebt').then(r => r.json()),
  ]);
  renderIssueList('list-critical',  critical);
  renderIssueList('list-blocked',   blocked);
  renderIssueList('list-regression',regression);
  renderIssueList('list-overdue',   overdue,
    i => `<span class="badge badge-red" style="font-size:10px;">${i.due}</span>`);
  renderIssueList('list-techdebt',  techdebt);
}

async function loadSprints() {
  const sprints = await fetch('/api/sprint').then(r => r.json());
  if (sprints.error) {
    document.getElementById('list-sprints').innerHTML =
      `<li class="loading">${sprints.error}</li>`; return;
  }
  document.getElementById('list-sprints').innerHTML = sprints.map(s => `
    <li class="sprint-item">
      <div class="sprint-header">
        <span class="sprint-name">${s.name}</span>
        <span class="sprint-state ${s.state === 'active' ? 'state-active' : 'state-closed'}">${s.state.toUpperCase()}</span>
      </div>
      ${s.goal ? `<div class="sprint-goal">${s.goal}</div>` : ''}
      <div class="sprint-dates">${s.start} → ${s.end}</div>
    </li>`).join('');
}

async function loadAll() {
  await Promise.all([loadStats(), loadLists(), loadSprints()]);
}

loadAll();
setInterval(loadAll, 5 * 60 * 1000); // refresh every 5 min
</script>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/chat")
def chat_interface():
    """Serve the chat interface."""
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def api_chat():
    """
    Process chat message through multi-agent system.

    Request JSON:
        {
            "message": "show me critical bugs"
        }

    Response JSON:
        {
            "success": true,
            "intent": "SEARCH",
            "agent": "SearchAgent",
            "message": "Found 5 tickets",
            "data": {...}
        }
    """
    try:
        # Get user message
        data = request.get_json()
        user_message = data.get("message", "").strip()

        if not user_message:
            return jsonify({
                "success": False,
                "error": "Message is required"
            }), 400

        # 1. Orchestrator detects intent and routes
        routing = orchestrator.process_message(user_message)
        intent = routing["intent"]
        agent_name = routing["agent"]
        context = routing["context"]

        # 2. Call appropriate agent
        result = None
        if agent_name == "SearchAgent":
            result = search_agent.process(user_message, context)
        elif agent_name == "AnalyzeAgent":
            result = analyze_agent.process(user_message, context)
        else:
            # For now, only SearchAgent and AnalyzeAgent are implemented
            result = {
                "success": False,
                "agent": agent_name,
                "message": f"Agent {agent_name} not yet implemented (coming in FEATURE 5-8)",
                "error": "Agent not implemented"
            }

        # 3. Add assistant response to orchestrator memory
        if result and result.get("success"):
            orchestrator.add_assistant_response(result["message"])

        # 4. Return response
        return jsonify({
            "success": result["success"],
            "intent": intent,
            "agent": agent_name,
            "message": result["message"],
            "data": result.get("data"),
            "error": result.get("error")
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == "__main__":
    print(f"\n{'='*50}")
    print("  Chatbot Jira — Automotive Dashboard")
    print(f"  Project : {PROJECT_KEY}")
    print(f"  Jira    : {JIRA_BASE_URL}")
    print(f"{'='*50}")
    print("  -> http://localhost:5000\n")
    app.run(debug=True, port=5000)