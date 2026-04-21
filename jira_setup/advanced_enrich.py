#!/usr/bin/env python3
"""
advanced_enrich.py
==================
Améliorations avancées du projet Jira — toutes les 8 cartes en un seul script.

  A. Sprints réalistes        (3 terminés + 1 actif, vélocité, goals)
  B. Workflow transitions     (cycles réalistes, reopen, rejected, résolutions)
  C. Blocage en cascade       (chemin critique, root cause commenté)
  D. Roadmap & dates          (start/due cohérentes, overdue intentionnels)
  E. Composants & releases    (5 composants, affected versions, leads)
  F. Régression & retest      (bugs rouverts, tickets régression liés)
  G. Test scenarios           (tasks PASS/FAIL/BLOCKED liées aux stories)
  H. Tech debt & improvements (20 tickets backlog, refactor, performance)

Usage :
    pip install requests python-dotenv
    python advanced_enrich.py
"""
from __future__ import annotations

import os
import time
import random
import logging
from typing import Any, Dict, List, Optional, Tuple

import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────
#  Config
# ──────────────────────────────────────────────
LOG_LEVEL        = os.getenv("LOG_LEVEL", "INFO").upper()
JIRA_BASE_URL    = os.getenv("JIRA_BASE_URL", "").rstrip("/")
JIRA_EMAIL       = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN   = os.getenv("JIRA_API_TOKEN", "")
PROJECT_KEY      = os.getenv("JIRA_PROJECT_KEY", "SCRUM")
DRY_RUN          = os.getenv("DRY_RUN", "false").strip().lower() == "true"

ACCOUNT_ID       = os.getenv("JIRA_ACCOUNT_ID",   "712020:35298345-dfb1-4141-9ebe-3bbdc27697ab")
ACCOUNT_HARMAN   = os.getenv("HARMAN_ACCOUNT_ID",  "712020:35298345-dfb1-4141-9ebe-3bbdc27697ab")
ACCOUNT_MARELLI  = os.getenv("MARELLI_ACCOUNT_ID", "712020:35298345-dfb1-4141-9ebe-3bbdc27697ab")

SLEEP            = 0.15
RANDOM_SEED      = 77
random.seed(RANDOM_SEED)

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s | %(levelname)-8s | %(message)s")
log = logging.getLogger("advanced-enrich")


# ──────────────────────────────────────────────
#  HTTP Client
# ──────────────────────────────────────────────
class JiraError(RuntimeError):
    pass


class Jira:
    def __init__(self) -> None:
        if not all([JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN]):
            raise JiraError("Missing credentials in .env")
        self.s = requests.Session()
        self.s.auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
        self.s.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
        self.issue_types: Dict[str, Any] = {}
        self.link_types:  Dict[str, Any] = {}
        self.transitions_cache: Dict[str, List[Dict]] = {}
        self.story_points_field: Optional[str] = None
        self.epic_link_field:    Optional[str] = None
        self.epic_name_field:    Optional[str] = None
        self.board_id:           Optional[int] = None

    def url(self, path: str) -> str:
        return f"{JIRA_BASE_URL}{path}"

    def req(self, method: str, path: str, **kw: Any) -> requests.Response:
        if DRY_RUN and method.upper() in {"POST", "PUT", "DELETE"}:
            log.info("[DRY] %s %s", method, path)
            class _F:
                status_code = 200
                def json(self): return {"id": "FAKE", "key": f"{PROJECT_KEY}-DRY", "dry": True}
                def raise_for_status(self): pass
            time.sleep(SLEEP)
            return _F()  # type: ignore
        r = self.s.request(method, self.url(path), timeout=30, **kw)
        if r.status_code >= 400:
            try:   body = r.json()
            except Exception: body = r.text
            raise JiraError(f"{method} {path} [{r.status_code}]: {body}")
        time.sleep(SLEEP)
        return r

    # ── Bootstrap ──────────────────────────────
    def bootstrap(self) -> None:
        me = self.req("GET", "/rest/api/3/myself").json()
        log.info("Connected as %s", me.get("displayName"))

        types = self.req("GET", "/rest/api/3/issuetype").json()
        self.issue_types = {t["name"].lower(): t for t in types}

        fields = self.req("GET", "/rest/api/3/field").json()
        for f in fields:
            n = f["name"].lower()
            if "story point" in n: self.story_points_field = f["id"]
            if n == "epic link":   self.epic_link_field    = f["id"]
            if n == "epic name":   self.epic_name_field    = f["id"]

        lt = self.req("GET", "/rest/api/2/issueLinkType").json()
        self.link_types = {l["name"].lower(): l for l in lt.get("issueLinkTypes", [])}

        # Find board id (for sprint assignment)
        try:
            boards = self.req("GET", f"/rest/agile/1.0/board?projectKeyOrId={PROJECT_KEY}").json()
            vals = boards.get("values", [])
            if vals:
                self.board_id = vals[0]["id"]
                log.info("Board ID: %s", self.board_id)
        except Exception as e:
            log.warning("Could not get board: %s", e)

    # ── Search ─────────────────────────────────
    def search(self, jql: str, max_results: int = 300,
               fields: Optional[List[str]] = None) -> List[Dict]:
        payload = {
            "jql": jql,
            "maxResults": max_results,
            "fields": fields or ["summary", "status", "issuetype", "labels",
                                  "assignee", "priority", "fixVersions",
                                  "duedate", "created", "updated"],
        }
        return self.req("POST", "/rest/api/3/search/jql", json=payload).json().get("issues", [])

    # ── Issue CRUD ─────────────────────────────
    def get(self, key: str) -> Dict:
        return self.req("GET", f"/rest/api/3/issue/{key}").json()

    def create(self, fields: Dict) -> Dict:
        r = self.req("POST", "/rest/api/3/issue", json={"fields": fields}).json()
        log.info("Created %s: %s", r.get("key", "?"), fields.get("summary", "")[:60])
        return r

    def update(self, key: str, fields: Dict) -> None:
        self.req("PUT", f"/rest/api/3/issue/{key}", json={"fields": fields})

    def comment(self, key: str, text: str) -> None:
        body = {"type": "doc", "version": 1, "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": text}]}
        ]}
        self.req("POST", f"/rest/api/3/issue/{key}/comment", json={"body": body})

    def link(self, inward: str, outward: str, link_name: str) -> None:
        chosen = None
        for name, lt in self.link_types.items():
            if link_name.lower() in name:
                chosen = lt; break
        if not chosen and self.link_types:
            chosen = list(self.link_types.values())[0]
        if not chosen:
            log.warning("No link type for '%s'", link_name); return
        try:
            self.req("POST", "/rest/api/3/issueLink", json={
                "type": {"name": chosen["name"]},
                "inwardIssue":  {"key": inward},
                "outwardIssue": {"key": outward},
            })
            log.info("  Link %s -[%s]-> %s", inward, chosen["name"], outward)
        except JiraError as e:
            log.warning("  Link failed %s→%s: %s", inward, outward, e)

    # ── Transitions ────────────────────────────
    def get_transitions(self, key: str) -> List[Dict]:
        if key in self.transitions_cache:
            return self.transitions_cache[key]
        t = self.req("GET", f"/rest/api/3/issue/{key}/transitions").json().get("transitions", [])
        self.transitions_cache[key] = t
        return t

    def transition_to(self, key: str, target: str) -> bool:
        """Move issue toward target status using available transitions."""
        for _ in range(6):
            issue = self.get(key)
            current = issue["fields"]["status"]["name"].lower()
            if current == target.lower():
                return True
            transitions = self.req("GET", f"/rest/api/3/issue/{key}/transitions").json().get("transitions", [])
            direct = next((t for t in transitions
                           if t["to"]["name"].lower() == target.lower()), None)
            if direct:
                self.req("POST", f"/rest/api/3/issue/{key}/transitions",
                         json={"transition": {"id": direct["id"]}})
                continue
            # Step toward target
            order = ["in progress", "in review", "done"]
            step = next((t for s in order for t in transitions
                         if t["to"]["name"].lower() == s), None)
            if step:
                self.req("POST", f"/rest/api/3/issue/{key}/transitions",
                         json={"transition": {"id": step["id"]}})
            else:
                break
        return False

    # ── Sprint helpers ─────────────────────────
    def get_sprints(self) -> List[Dict]:
        if not self.board_id:
            return []
        try:
            r = self.req("GET", f"/rest/agile/1.0/board/{self.board_id}/sprint?maxResults=50").json()
            return r.get("values", [])
        except Exception as e:
            log.warning("get_sprints: %s", e); return []

    def create_sprint(self, name: str, goal: str,
                      start: str, end: str) -> Optional[int]:
        if not self.board_id:
            return None
        try:
            r = self.req("POST", "/rest/agile/1.0/sprint", json={
                "name": name,
                "goal": goal,
                "originBoardId": self.board_id,
                "startDate": f"{start}T09:00:00.000Z",
                "endDate":   f"{end}T18:00:00.000Z",
            }).json()
            sid = r.get("id")
            log.info("Created sprint %s (id=%s)", name, sid)
            return sid
        except JiraError as e:
            log.warning("create_sprint failed: %s", e); return None

    def start_sprint(self, sprint_id: int, start: str, end: str) -> None:
        try:
            self.req("POST", f"/rest/agile/1.0/sprint/{sprint_id}", json={
                "state": "active",
                "startDate": f"{start}T09:00:00.000Z",
                "endDate":   f"{end}T18:00:00.000Z",
            })
        except JiraError as e:
            log.warning("start_sprint %s: %s", sprint_id, e)

    def close_sprint(self, sprint_id: int) -> None:
        try:
            self.req("POST", f"/rest/agile/1.0/sprint/{sprint_id}",
                     json={"state": "closed"})
        except JiraError as e:
            log.warning("close_sprint %s: %s", sprint_id, e)

    def add_to_sprint(self, sprint_id: int, issue_keys: List[str]) -> None:
        if not issue_keys: return
        try:
            self.req("POST", f"/rest/agile/1.0/sprint/{sprint_id}/issue",
                     json={"issues": issue_keys})
            log.info("  Added %d issues to sprint %s", len(issue_keys), sprint_id)
        except JiraError as e:
            log.warning("  add_to_sprint %s: %s", sprint_id, e)

    # ── Versions ───────────────────────────────
    def get_or_create_version(self, name: str, description: str,
                               release_date: str) -> Optional[str]:
        vers = self.req("GET", f"/rest/api/3/project/{PROJECT_KEY}/versions").json()
        for v in vers:
            if v["name"] == name:
                return v["id"]
        try:
            v = self.req("POST", "/rest/api/3/version", json={
                "name": name, "description": description,
                "project": PROJECT_KEY, "released": False,
                "releaseDate": release_date,
            }).json()
            log.info("Created version %s", name)
            return v.get("id")
        except JiraError as e:
            log.warning("Version creation failed %s: %s", name, e); return None

    # ── Components ─────────────────────────────
    def get_or_create_component(self, name: str, description: str,
                                 lead_id: str) -> Optional[str]:
        try:
            comps = self.req("GET", f"/rest/api/3/project/{PROJECT_KEY}/components").json()
            for c in comps:
                if c["name"] == name:
                    return c["id"]
            c = self.req("POST", "/rest/api/3/component", json={
                "name": name,
                "description": description,
                "project": PROJECT_KEY,
                "leadAccountId": lead_id,
            }).json()
            log.info("Created component %s", name)
            return c.get("id")
        except JiraError as e:
            log.warning("Component %s: %s", name, e); return None

    def worklog(self, key: str, time_spent: str) -> None:
        try:
            self.req("POST", f"/rest/api/3/issue/{key}/worklog",
                     json={"timeSpent": time_spent})
        except JiraError as e:
            log.warning("worklog %s: %s", key, e)


# ──────────────────────────────────────────────
#  ADF helpers
# ──────────────────────────────────────────────
def adf(text: str) -> Dict:
    return {"type": "doc", "version": 1, "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": text}]}
    ]}

def adf_sections(sections: List[Tuple[str, str]]) -> Dict:
    content = []
    for heading, body in sections:
        content.append({"type": "heading", "attrs": {"level": 3},
                        "content": [{"type": "text", "text": heading}]})
        content.append({"type": "paragraph",
                        "content": [{"type": "text", "text": body}]})
    return {"type": "doc", "version": 1, "content": content}


# ──────────────────────────────────────────────
#  A. SPRINTS RÉALISTES
# ──────────────────────────────────────────────
SPRINT_DEFS = [
    {
        "name": "Sprint 1 - CAN Foundation",
        "goal": "Stabilize CAN bus communication and establish diagnostic baseline on INT-BENCH.",
        "start": "2026-02-02", "end": "2026-02-13", "state": "closed",
        "velocity": 34,
    },
    {
        "name": "Sprint 2 - OTA & Infotainment",
        "goal": "Deliver OTA package validation and fix infotainment startup sequence.",
        "start": "2026-02-16", "end": "2026-02-27", "state": "closed",
        "velocity": 41,
    },
    {
        "name": "Sprint 3 - Safety & Power",
        "goal": "Implement AUTOSAR watchdog integration and coordinated ECU sleep mode.",
        "start": "2026-03-02", "end": "2026-03-13", "state": "closed",
        "velocity": 38,
    },
    {
        "name": "Sprint 4 - Release Prep v1.1",
        "goal": "Fix all Severity-1 bugs. Prepare v1.1.0 release for Stellantis sign-off.",
        "start": "2026-03-16", "end": "2026-03-27", "state": "active",
        "velocity": None,
    },
]

def step_A_sprints(jira: Jira, issues: List[Dict]) -> Dict[str, int]:
    """Create 3 closed + 1 active sprint and distribute issues."""
    log.info("=== Step A: Sprints réalistes ===")

    existing = jira.get_sprints()
    existing_names = {s["name"] for s in existing}

    stories  = [i for i in issues if i["fields"]["issuetype"]["name"] == "Story"]
    tasks    = [i for i in issues if i["fields"]["issuetype"]["name"] == "Task"]
    bugs     = [i for i in issues if i["fields"]["issuetype"]["name"] == "Bug"]
    epics    = [i for i in issues if i["fields"]["issuetype"]["name"] == "Epic"]

    sprint_ids: Dict[str, int] = {}
    buckets = [
        stories[:8]  + tasks[:4]  + bugs[:6],   # Sprint 1
        stories[8:16] + tasks[4:8] + bugs[6:12], # Sprint 2
        stories[16:22] + tasks[8:12] + bugs[12:16], # Sprint 3
        stories[22:28] + tasks[12:16] + bugs[16:20], # Sprint 4 (active)
    ]

    for idx, sdef in enumerate(SPRINT_DEFS):
        sid = None
        if sdef["name"] in existing_names:
            sid = next((s["id"] for s in existing if s["name"] == sdef["name"]), None)
            log.info("Sprint already exists: %s", sdef["name"])
        else:
            sid = jira.create_sprint(sdef["name"], sdef["goal"],
                                     sdef["start"], sdef["end"])

        if sid is None:
            continue

        sprint_ids[sdef["name"]] = sid

        # Assign issues to sprint
        bucket_keys = [i["key"] for i in buckets[idx]]
        if bucket_keys:
            jira.add_to_sprint(sid, bucket_keys)

        # Set story points and due dates
        for iss in buckets[idx]:
            key   = iss["key"]
            itype = iss["fields"]["issuetype"]["name"]
            upd: Dict[str, Any] = {}
            if itype in ("Story", "Task") and jira.story_points_field:
                upd[jira.story_points_field] = random.choice([2, 3, 5, 8])
            if sdef["end"]:
                upd["duedate"] = sdef["end"]
            if upd:
                try: jira.update(key, upd)
                except JiraError as e: log.warning("SP/due %s: %s", key, e)

        # Close completed sprints
        if sdef["state"] == "closed":
            # Transition most issues to Done
            for iss in buckets[idx][:-2]:  # leave last 2 "not done" for realism
                try: jira.transition_to(iss["key"], "Done")
                except Exception: pass
            jira.close_sprint(sid)
            log.info("Closed sprint: %s (velocity ~%s SP)", sdef["name"], sdef["velocity"])
        elif sdef["state"] == "active":
            jira.start_sprint(sid, sdef["start"], sdef["end"])
            # Mix of statuses for active sprint
            for iss in buckets[idx][:3]:
                try: jira.transition_to(iss["key"], "In Progress")
                except Exception: pass
            for iss in buckets[idx][3:5]:
                try: jira.transition_to(iss["key"], "In Review")
                except Exception: pass

    log.info("Step A complete: %d sprints configured", len(sprint_ids))
    return sprint_ids


# ──────────────────────────────────────────────
#  B. WORKFLOW TRANSITIONS RÉALISTES
# ──────────────────────────────────────────────
RESOLUTION_COMMENTS = {
    "Fixed": (
        "jean.dupont (Capgemini) — Fix validated on INT-BENCH-03. "
        "20-cycle regression test passed. Closing as Fixed. "
        "Build available in v1.1.0-rc3."
    ),
    "Won't Fix": (
        "jean.dupont (Capgemini) — After triaging with Stellantis PM, this issue "
        "is out of scope for the current integration milestone. "
        "Closing as Won't Fix. Will be re-evaluated for v2.0."
    ),
    "Duplicate": (
        "jean.dupont (Capgemini) — This issue is a duplicate of an existing ticket. "
        "Root cause identical. Closing as Duplicate. "
        "Please follow the parent ticket for fix progress."
    ),
    "Cannot Reproduce": (
        "sofia.rossi (Marelli) — Unable to reproduce on INT-BENCH-03 and INT-BENCH-07 "
        "after 15 attempts. Bench configuration verified. "
        "Closing as Cannot Reproduce — please reopen with additional trace data if observed again."
    ),
}

REOPEN_COMMENT = (
    "jean.dupont (Capgemini) — Regression detected in build v1.1.0-rc2. "
    "Issue reappears on INT-BENCH-07 after cold start sequence. "
    "Reopening for root cause analysis. Assigning back to Marelli team."
)

BLOCKED_REASON_COMMENTS = [
    ("sofia.rossi (Marelli) — Blocked: waiting for updated CAN transceiver firmware from NXP. "
     "ETA: 3 business days. Cannot proceed with integration tests until firmware v3.2.1 is available."),
    ("ali.chen (Harman) — Blocked: OTA signing certificate expired. "
     "Security team provisioning new cert. ETA: 48h. "
     "All OTA-related stories blocked until cert is renewed."),
    ("jean.dupont (Capgemini) — Blocked: test bench INT-BENCH-03 unavailable due to hardware fault. "
     "Maintenance team notified. ETA: 2 days. Stories requiring this bench are on hold."),
    ("sofia.rossi (Marelli) — Blocked: dependency on SCRUM-5 not yet resolved. "
     "Bus-off recovery fix must be validated before this story can proceed."),
]

def step_B_transitions(jira: Jira, issues: List[Dict]) -> None:
    """Apply realistic workflow transitions, resolutions, reopen cycles."""
    log.info("=== Step B: Workflow transitions réalistes ===")

    bugs    = [i for i in issues if i["fields"]["issuetype"]["name"] == "Bug"]
    stories = [i for i in issues if i["fields"]["issuetype"]["name"] == "Story"]

    if not bugs or not stories:
        log.warning("Not enough bugs/stories for transitions")
        return

    # ── Bugs with resolution ──────────────────
    resolutions = list(RESOLUTION_COMMENTS.items())
    for i, bug in enumerate(bugs[:len(resolutions)]):
        key = bug["key"]
        resolution, comment = resolutions[i]
        try:
            jira.transition_to(key, "Done")
            jira.comment(key, comment)
            jira.update(key, {"labels": bug["fields"].get("labels", []) + [f"resolution-{resolution.lower().replace(' ', '-')}"]})
            log.info("  Bug %s → Done [%s]", key, resolution)
        except Exception as e:
            log.warning("  transition B bug %s: %s", key, e)

    # ── Bugs with reopen cycle (regression) ──
    for bug in bugs[4:7]:
        key = bug["key"]
        try:
            jira.transition_to(key, "Done")
            jira.comment(key, RESOLUTION_COMMENTS["Fixed"])
            jira.transition_to(key, "In Progress")  # reopen
            jira.comment(key, REOPEN_COMMENT)
            jira.update(key, {"labels": bug["fields"].get("labels", []) + ["reopened", "regression-risk"]})
            log.info("  Bug %s → Done → Reopened (regression cycle)", key)
        except Exception as e:
            log.warning("  reopen cycle %s: %s", key, e)

    # ── Stories: rejected in review ──────────
    for story in stories[2:4]:
        key = story["key"]
        try:
            jira.transition_to(key, "In Review")
            jira.comment(key,
                "jean.dupont (Capgemini) — Review rejected: acceptance criteria AC3 not met. "
                "Test bench results incomplete. Returning to In Progress for rework. "
                "Rework estimate: +1 day.")
            jira.transition_to(key, "In Progress")
            jira.update(key, {"labels": story["fields"].get("labels", []) + ["review-rejected", "rework"]})
            log.info("  Story %s → In Review → Rejected → In Progress", key)
        except Exception as e:
            log.warning("  story review cycle %s: %s", key, e)

    # ── Stories: blocked with documented reason ──
    for i, story in enumerate(stories[5:9]):
        key = story["key"]
        comment = BLOCKED_REASON_COMMENTS[i % len(BLOCKED_REASON_COMMENTS)]
        try:
            jira.transition_to(key, "Blocked")
            jira.comment(key, comment)
            jira.update(key, {"labels": story["fields"].get("labels", []) + ["blocked", "waiting-dependency"]})
            log.info("  Story %s → Blocked (documented reason)", key)
        except Exception as e:
            log.warning("  blocked story %s: %s", key, e)

    log.info("Step B complete")


# ──────────────────────────────────────────────
#  C. BLOCAGE EN CASCADE
# ──────────────────────────────────────────────
CASCADE_COMMENT_ROOT = (
    "jean.dupont (Capgemini) — ROOT CAUSE ANALYSIS:\n"
    "This is the root cause ticket blocking the entire CAN integration path.\n"
    "Impact: 3 stories blocked, 1 epic milestone delayed by ~1 sprint.\n"
    "Critical path: {root} → blocks → {s1} → blocks → {s2} → blocks → {s3}.\n"
    "Priority: HIGHEST. All other work in CAN epic is on hold until this is resolved."
)

CASCADE_COMMENT_BLOCKED = (
    "jean.dupont (Capgemini) — BLOCKED by {blocker}.\n"
    "This story cannot proceed until the root cause bug is fixed.\n"
    "Impact on milestone: v1.1.0 release at risk.\n"
    "Please see {blocker} for root cause analysis and fix ETA."
)

def step_C_cascade(jira: Jira, issues: List[Dict]) -> None:
    """Build a realistic blocking cascade with root cause analysis."""
    log.info("=== Step C: Blocage en cascade ===")

    bugs    = [i for i in issues if i["fields"]["issuetype"]["name"] == "Bug"]
    stories = [i for i in issues if i["fields"]["issuetype"]["name"] == "Story"]
    epics   = [i for i in issues if i["fields"]["issuetype"]["name"] == "Epic"]

    if len(bugs) < 2 or len(stories) < 6:
        log.warning("Not enough issues for cascade"); return

    root_bug = bugs[0]["key"]
    s1 = stories[0]["key"]
    s2 = stories[1]["key"]
    s3 = stories[2]["key"]
    s4 = stories[3]["key"]
    s5 = stories[4]["key"]

    # Root cause bug blocks 3 stories (level 1)
    jira.link(root_bug, s1, "blocks")
    jira.link(root_bug, s2, "blocks")
    jira.link(root_bug, s3, "blocks")

    # Cascading: blocked stories block more stories (level 2)
    jira.link(s1, s4, "blocks")
    jira.link(s2, s5, "blocks")

    # If there's a second serious bug, cross-epic cascade
    if len(bugs) >= 3 and len(stories) >= 8:
        jira.link(bugs[1]["key"], stories[5]["key"], "blocks")
        jira.link(stories[5]["key"], stories[6]["key"], "blocks")
        jira.link(stories[6]["key"], stories[7]["key"], "blocks")
        log.info("  Cross-epic 3-level cascade: %s→%s→%s→%s",
                 bugs[1]["key"], stories[5]["key"], stories[6]["key"], stories[7]["key"])

    # Root cause analysis comment
    jira.comment(root_bug, CASCADE_COMMENT_ROOT.format(
        root=root_bug, s1=s1, s2=s2, s3=s3))

    # Blocked reason on each blocked story
    for blocked_key in [s1, s2, s3, s4, s5]:
        jira.comment(blocked_key,
            CASCADE_COMMENT_BLOCKED.format(blocker=root_bug))
        try:
            jira.transition_to(blocked_key, "Blocked")
        except Exception: pass

    # Mark root bug as highest priority
    try:
        jira.update(root_bug, {"priority": {"name": "Highest"},
                               "labels": bugs[0]["fields"].get("labels", []) + ["critical-path", "cascade-root"]})
    except Exception: pass

    log.info("Step C complete: cascade from %s blocking %d stories", root_bug, 5)


# ──────────────────────────────────────────────
#  D. ROADMAP & DATES
# ──────────────────────────────────────────────
ROADMAP_MILESTONES = {
    "v1.0.0 - Initial Integration":      {"epics": 0,    "stories_range": (0, 8),   "overdue": False},
    "v1.1.0 - CAN & Diagnostics Fix":    {"epics": 1,    "stories_range": (8, 18),  "overdue": True},
    "v1.2.0 - OTA & Infotainment":       {"epics": 2,    "stories_range": (18, 28), "overdue": False},
    "v2.0.0 - Safety & AUTOSAR":         {"epics": 3,    "stories_range": (28, 36), "overdue": False},
}

DATE_MAP = {
    "v1.0.0 - Initial Integration":   {"start": "2026-02-01", "due": "2026-02-28", "overdue": False, "overdue_due": "2026-02-15"},
    "v1.1.0 - CAN & Diagnostics Fix": {"start": "2026-03-01", "due": "2026-03-31", "overdue": True,  "overdue_due": "2026-03-10"},
    "v1.2.0 - OTA & Infotainment":    {"start": "2026-04-01", "due": "2026-04-30", "overdue": True,  "overdue_due": "2026-03-25"},
    "v2.0.0 - Safety & AUTOSAR":      {"start": "2026-06-01", "due": "2026-09-30", "overdue": False, "overdue_due": "2026-05-01"},
}

def step_D_roadmap(jira: Jira, issues: List[Dict], version_ids: Dict[str, str]) -> None:
    """Assign start dates, due dates, and create intentional overdue tickets."""
    log.info("=== Step D: Roadmap & dates ===")

    stories = [i for i in issues if i["fields"]["issuetype"]["name"] == "Story"]
    bugs    = [i for i in issues if i["fields"]["issuetype"]["name"] == "Bug"]
    epics   = [i for i in issues if i["fields"]["issuetype"]["name"] == "Epic"]

    # Assign dates per version
    for vname, conf in DATE_MAP.items():
        vid = version_ids.get(vname)
        m = ROADMAP_MILESTONES.get(vname, {})
        start_idx, end_idx = m.get("stories_range", (0, 5))
        bucket = stories[start_idx:end_idx]

        for i, story in enumerate(bucket):
            key  = story["key"]
            # Some stories are intentionally overdue (past due date)
            is_overdue = conf["overdue"] and i < 3
            due = conf["overdue_due"] if is_overdue else conf["due"]
            upd: Dict[str, Any] = {"duedate": due}
            if vid:
                upd["fixVersions"] = [{"id": vid}]
            try:
                jira.update(key, upd)
                if is_overdue:
                    jira.comment(key,
                        f"jean.dupont (Capgemini) — WARNING: This ticket is OVERDUE (due: {due}). "
                        f"Blocked by integration dependency. PM notified. "
                        f"Impact on {vname} release milestone.")
                    jira.update(key, {"labels": story["fields"].get("labels", []) + ["overdue", "milestone-risk"]})
            except Exception as e:
                log.warning("  roadmap date %s: %s", key, e)

    # Epic-level dates
    for i, epic in enumerate(epics[:4]):
        versions = list(DATE_MAP.values())
        d = versions[i % len(versions)]
        try:
            jira.update(epic["key"], {"duedate": d["due"]})
        except Exception: pass

    # Intentional overdue bugs (past due)
    for bug in bugs[:5]:
        try:
            jira.update(bug["key"], {"duedate": "2026-03-01"})  # clearly past
        except Exception: pass

    log.info("Step D complete: roadmap dates assigned")


# ──────────────────────────────────────────────
#  E. COMPOSANTS & RELEASES
# ──────────────────────────────────────────────
COMPONENTS_DEF = [
    {"name": "CAN Communication",    "desc": "HS-CAN and MS-CAN bus layer. Marelli GW firmware.", "lead": ACCOUNT_MARELLI},
    {"name": "OTA Update System",    "desc": "Over-the-air update delivery. Harman OTA server.",  "lead": ACCOUNT_HARMAN},
    {"name": "HMI & Infotainment",   "desc": "Harman HU touchscreen, audio, navigation.",         "lead": ACCOUNT_HARMAN},
    {"name": "Diagnostics & ECU",    "desc": "UDS diagnostics, DTC management, ECU health.",      "lead": ACCOUNT_MARELLI},
    {"name": "Safety & Power",       "desc": "AUTOSAR safety, watchdog, sleep modes.",             "lead": ACCOUNT_MARELLI},
]

COMPONENT_LABEL_MAP = {
    "CAN Communication":  ["canbus", "can", "gateway"],
    "OTA Update System":  ["ota", "update", "firmware"],
    "HMI & Infotainment": ["infotainment", "hmi", "audio", "navigation", "bluetooth"],
    "Diagnostics & ECU":  ["diagnostics", "ecu", "dtc", "uds"],
    "Safety & Power":     ["safety", "power", "autosar", "watchdog"],
}

def step_E_components(jira: Jira, issues: List[Dict]) -> Dict[str, str]:
    """Create project components and assign issues to them."""
    log.info("=== Step E: Composants & releases ===")

    comp_ids: Dict[str, str] = {}
    for c in COMPONENTS_DEF:
        cid = jira.get_or_create_component(c["name"], c["desc"], c["lead"])
        if cid:
            comp_ids[c["name"]] = cid

    # Assign components to issues based on labels
    for iss in issues:
        labels = iss["fields"].get("labels", [])
        assigned_comp = None
        for comp_name, comp_labels in COMPONENT_LABEL_MAP.items():
            if any(l in labels for l in comp_labels):
                assigned_comp = comp_name
                break
        if assigned_comp and assigned_comp in comp_ids:
            try:
                jira.update(iss["key"], {"components": [{"id": comp_ids[assigned_comp]}]})
            except Exception as e:
                log.warning("  component assign %s: %s", iss["key"], e)

    log.info("Step E complete: %d components created", len(comp_ids))
    return comp_ids


# ──────────────────────────────────────────────
#  F. RÉGRESSION & RETEST
# ──────────────────────────────────────────────
REGRESSION_BUGS = [
    {
        "summary": "[REGRESSION] CAN bus communication lost — reappears in v1.1.0-rc2",
        "parent_summary": "CAN bus communication lost intermittently",
        "description": (
            "REGRESSION detected in build v1.1.0-rc2 on INT-BENCH-07.\n\n"
            "Original fix (v1.1.0-rc1) appeared to resolve the issue during Sprint 2 validation.\n"
            "However, the bug reappears under specific conditions:\n"
            "  1. Cold start after battery disconnect > 2 hours\n"
            "  2. Ambient temperature < 10°C\n"
            "  3. Rapid ignition cycling (3 cycles in < 30s)\n\n"
            "Root cause suspected: temperature-dependent timing regression in GW watchdog.\n"
            "Assigned to Marelli for urgent investigation.\n\n"
            "Linked to original: see parent ticket."
        ),
        "labels": ["regression", "retest-required", "canbus", "marelli", "SEV1_critical"],
        "priority": "Highest",
    },
    {
        "summary": "[REGRESSION] OTA validation fails after trust store update",
        "parent_summary": "OTA package validation fails on signed bundle",
        "description": (
            "REGRESSION detected after trust store deployment.\n\n"
            "Trust store v2 was deployed to resolve SCRUM-linked ticket.\n"
            "New issue: OTA validation now fails with error 0xE5 CERT_CHAIN_INCOMPLETE "
            "on devices with factory trust store (not updated).\n\n"
            "Affected: 12% of bench devices still running factory trust store.\n"
            "Workaround: manual trust store update per device.\n\n"
            "Root cause: trust store update script did not cover all device groups."
        ),
        "labels": ["regression", "retest-required", "ota", "harman", "SEV2_major"],
        "priority": "High",
    },
    {
        "summary": "[REGRESSION] ECU diagnostics timeout — reappears after GW firmware update",
        "parent_summary": "ECU not responding after ignition",
        "description": (
            "REGRESSION in GW firmware v2.4.2.\n\n"
            "UDS diagnostic timeout (0x78 requestCorrectlyReceivedResponsePending) "
            "now occurs on ECU 0x20 (GW) after the firmware update intended to fix bus-off recovery.\n\n"
            "Impact: diagnostic tools (CANoe, INCA) cannot access GW for configuration.\n"
            "Bench test campaign blocked on INT-BENCH-05.\n\n"
            "Marelli to provide hotfix build v2.4.3 within 24h."
        ),
        "labels": ["regression", "retest-required", "diagnostics", "marelli", "SEV2_major"],
        "priority": "High",
    },
]

def step_F_regression(jira: Jira, issues: List[Dict]) -> List[str]:
    """Create regression tickets linked to original bugs."""
    log.info("=== Step F: Régression & retest ===")

    bug_type  = next((v["name"] for v in jira.issue_types.values()
                      if v["name"].lower() == "bug"), "Bug")
    bugs_by_summary = {i["fields"]["summary"]: i["key"] for i in issues
                       if i["fields"]["issuetype"]["name"] == "Bug"}

    created_keys = []
    for reg in REGRESSION_BUGS:
        f: Dict[str, Any] = {
            "project":     {"key": PROJECT_KEY},
            "summary":     reg["summary"],
            "issuetype":   {"name": bug_type},
            "priority":    {"name": reg["priority"]},
            "assignee":    {"id": ACCOUNT_MARELLI},
            "labels":      reg["labels"],
            "description": adf(reg["description"]),
        }
        r = jira.create(f)
        key = r.get("key", "")
        if not key: continue
        created_keys.append(key)

        # Link to original bug
        parent_key = bugs_by_summary.get(reg["parent_summary"])
        if parent_key:
            jira.link(key, parent_key, "relates")
            jira.comment(key,
                f"jean.dupont (Capgemini) — This is a REGRESSION of {parent_key}. "
                f"Original fix was validated in Sprint 2 but broke in the subsequent build. "
                f"See {parent_key} for original root cause analysis.")
            jira.comment(parent_key,
                f"jean.dupont (Capgemini) — REGRESSION detected: see {key}. "
                f"Fix is not stable across all bench configurations. Escalating to Marelli.")

        # Add retest comment
        jira.comment(key,
            "ali.chen (Harman) / sofia.rossi (Marelli) — Retest plan:\n"
            "1. Apply hotfix build on INT-BENCH-03, 05, and 07.\n"
            "2. Run 20-cycle regression test per bench.\n"
            "3. Validate under cold temperature conditions (< 10°C if applicable).\n"
            "4. Update test results in this ticket within 48h.")

        try: jira.transition_to(key, "In Progress")
        except Exception: pass

    log.info("Step F complete: %d regression tickets created", len(created_keys))
    return created_keys


# ──────────────────────────────────────────────
#  G. TEST SCENARIOS
# ──────────────────────────────────────────────
TEST_SCENARIOS = [
    # (story_keyword, test_title, result, bench, notes)
    ("Stabilize CAN bus",         "TC-CAN-001: Bus recovery after bus-off",         "PASS",    "BENCH_HIL03",
     "20 cycles executed. No frame loss > 50ms. Pass criteria met."),
    ("Stabilize CAN bus",         "TC-CAN-002: Bus recovery under EMC load",         "FAIL",    "BENCH_HIL07",
     "Frame loss detected at 87ms under 50V/m EMC field. Exceeds 50ms spec. Bug raised."),
    ("Stabilize CAN bus",         "TC-CAN-003: Wake-up frame latency",               "PASS",    "BENCH_HIL03",
     "Average wake-up latency: 12ms. Spec: < 20ms. Pass."),
    ("Add OTA update",            "TC-OTA-001: Full update cycle end-to-end",        "PASS",    "BENCH_INT02",
     "Update cycle 6m32s. Spec: < 8min. Rollback tested: triggers correctly on 0xE1."),
    ("Add OTA update",            "TC-OTA-002: Interrupted update recovery",         "BLOCKED", "BENCH_INT05",
     "Test blocked: bench INT-BENCH-05 unavailable (hardware fault). ETA: 2 days."),
    ("Implement vehicle diag",    "TC-DIAG-001: UDS session establishment",          "PASS",    "BENCH_HIL03",
     "Default session (0x10 01) response in 23ms. Spec: < 50ms. Pass on 10 ECUs."),
    ("Implement vehicle diag",    "TC-DIAG-002: DTC retrieval — all ECUs",           "FAIL",    "BENCH_HIL07",
     "GW ECU (0x20) returns NRC 0x22 (conditionsNotCorrect). DTC list incomplete. Bug raised."),
    ("Infotainment startup",      "TC-HMI-001: Cold start UI interactive time",      "PASS",    "BENCH_INT02",
     "UI interactive at T+4.8s average (20 cold starts). Spec: < 6s. Pass."),
    ("Infotainment startup",      "TC-HMI-002: Rapid ignition cycle stability",      "FAIL",    "BENCH_INT02",
     "UI freeze detected on cycle 7/10 under rapid ignition (< 5s between cycles). Bug raised."),
    ("ECU sleep mode",            "TC-PWR-001: Deep sleep current consumption",      "PASS",    "BENCH_HIL03",
     "Quiescent current: 0.82mA. Spec: < 1mA. Pass."),
    ("AUTOSAR watchdog",          "TC-SAFE-001: Watchdog trigger on task overrun",   "FAIL",    "BENCH_HIL07",
     "WDT not triggered when safety partition task overruns by 15ms. Spec: trigger at 10ms. Bug raised."),
    ("OTA rollback",              "TC-OTA-003: Rollback on signature mismatch",      "PASS",    "BENCH_INT02",
     "Rollback triggered correctly on 0xE4 error. Device returns to previous SW version. Pass."),
]

def step_G_test_scenarios(jira: Jira, issues: List[Dict]) -> None:
    """Create test scenario tasks linked to their stories."""
    log.info("=== Step G: Test scenarios ===")

    task_type = next((v["name"] for v in jira.issue_types.values()
                      if v["name"].lower() == "task"), "Task")
    stories_by_summary = {i["fields"]["summary"].lower(): i
                          for i in issues if i["fields"]["issuetype"]["name"] == "Story"}

    result_labels = {"PASS": "test-passed", "FAIL": "test-failed", "BLOCKED": "test-blocked"}
    result_priority = {"PASS": "Medium", "FAIL": "High", "BLOCKED": "High"}

    for tc in TEST_SCENARIOS:
        story_kw, title, result, bench, notes = tc

        # Find matching story
        parent_story = None
        for summary, story in stories_by_summary.items():
            if story_kw.lower() in summary:
                parent_story = story; break

        labels = ["test-case", "validation", "bench-test",
                  result_labels.get(result, "test-case"),
                  bench.lower(), "chatbot-seed"]

        f: Dict[str, Any] = {
            "project":     {"key": PROJECT_KEY},
            "summary":     title,
            "issuetype":   {"name": task_type},
            "priority":    {"name": result_priority.get(result, "Medium")},
            "assignee":    {"id": ACCOUNT_CAPGEMINI},
            "labels":      labels,
            "description": adf_sections([
                ("Test objective",     f"Validate: {title}"),
                ("Bench",             bench),
                ("Result",            result),
                ("Test notes",        notes),
                ("Acceptance criteria", "Per Stellantis integration validation plan v2.1."),
            ]),
        }

        # Link to parent story via epic link or parent
        if parent_story:
            epic_key = parent_story["fields"].get("parent", {}).get("key")
            if jira.epic_link_field and epic_key:
                f[jira.epic_link_field] = epic_key

        r = jira.create(f)
        key = r.get("key", "")
        if not key: continue

        # Link to parent story
        if parent_story:
            jira.link(key, parent_story["key"], "relates")

        # Transition based on result
        if result == "PASS":
            try: jira.transition_to(key, "Done")
            except Exception: pass
        elif result == "FAIL":
            try: jira.transition_to(key, "In Progress")
            except Exception: pass
            jira.comment(key,
                f"jean.dupont (Capgemini) — TEST FAILED: {notes}\n"
                f"Bug raised and linked to this test case. "
                f"Re-test required after fix is deployed on {bench}.")
        elif result == "BLOCKED":
            try: jira.transition_to(key, "Blocked")
            except Exception: pass
            jira.comment(key,
                f"jean.dupont (Capgemini) — TEST BLOCKED: {notes}\n"
                f"Will reschedule once {bench} is available.")

    log.info("Step G complete: %d test scenarios created", len(TEST_SCENARIOS))


# ──────────────────────────────────────────────
#  H. TECH DEBT & IMPROVEMENTS
# ──────────────────────────────────────────────
TECH_DEBT_ITEMS = [
    # (summary, labels, story_points, description_highlight)
    ("[Tech Debt] Refactor CAN error handler — remove hardcoded retry counts",
     ["tech-debt", "refactor", "canbus", "marelli"], 8,
     "Hardcoded retry count (3) in CAN error handler. Should be configurable via AUTOSAR parameter."),
    ("[Tech Debt] Replace polling-based ECU status check with interrupt-driven model",
     ["tech-debt", "performance", "ecu", "marelli"], 13,
     "Current ECU health check polls every 100ms. Wastes CPU cycles. "
     "Should use CAN status frame interrupt (0x7E8 NMPDU)."),
    ("[Tech Debt] Centralize OTA error code mapping — currently duplicated in 3 modules",
     ["tech-debt", "refactor", "ota", "harman"], 5,
     "Error codes 0xE1–0xE9 are mapped in OTAValidator.cpp, OTAManager.cpp, and CampaignService.java. "
     "Should be extracted to shared constant file."),
    ("[Tech Debt] Remove deprecated Jira /rest/api/2/ calls in diagnostic backend",
     ["tech-debt", "refactor", "diagnostics"], 3,
     "Diagnostic service still uses deprecated v2 API endpoints. Migrate to v3."),
    ("[Tech Debt] Increase unit test coverage for GW firmware — currently 42%",
     ["tech-debt", "testing", "canbus", "marelli"], 13,
     "GW firmware module coverage: 42%. Target: 80%. "
     "Missing: error path coverage, bus-off recovery, watchdog trigger scenarios."),
    ("[Tech Debt] Migrate infotainment build system from Make to CMake",
     ["tech-debt", "build-system", "infotainment", "harman"], 8,
     "Legacy Makefile-based build. Migration to CMake needed for AUTOSAR BSW integration."),
    ("[Tech Debt] Remove debug logs from production HU build — causing boot delay",
     ["tech-debt", "performance", "infotainment", "harman"], 3,
     "Debug log statements in MediaService.cpp causing +800ms boot delay in production build. "
     "Should be guarded by compile-time flag."),
    ("[Tech Debt] Standardize CAN frame ID naming convention across all ECU specs",
     ["tech-debt", "documentation", "canbus"], 5,
     "Frame IDs use different naming in GW spec (hex) vs BCM spec (decimal) vs TCU spec (symbolic). "
     "Causes confusion during integration. Align on hex + symbolic name."),
    ("[Tech Debt] Replace manual test bench setup scripts with Ansible playbooks",
     ["tech-debt", "automation", "infrastructure"], 8,
     "Bench setup currently requires 45-minute manual configuration. "
     "Ansible automation target: < 5 minutes."),
    ("[Tech Debt] Add timeout handling to all UDS diagnostic requests",
     ["tech-debt", "reliability", "diagnostics", "marelli"], 5,
     "3 UDS request functions have no timeout. If ECU is unresponsive, "
     "diagnostic tool hangs indefinitely. Add 50ms timeout per ISO 14229."),
]

IMPROVEMENT_ITEMS = [
    ("[Improvement] Add CAN bus health dashboard — real-time frame loss visualization",
     ["improvement", "monitoring", "canbus"], 8,
     "Real-time dashboard showing frame loss rate, error counters, and bus state per ECU. "
     "Target: Grafana integration with CAN logger data feed."),
    ("[Improvement] Implement OTA campaign dry-run mode for pre-deployment validation",
     ["improvement", "ota", "harman"], 5,
     "Dry-run mode: validates package, checks device eligibility, simulates rollout "
     "without actually flashing. Reduces risk of failed mass campaigns."),
    ("[Improvement] Add automated regression test suite for CAN bus recovery",
     ["improvement", "automation", "testing", "canbus"], 13,
     "Automated 50-cycle regression test triggered on every GW firmware build. "
     "Jenkins CI integration. Result posted to Jira automatically."),
    ("[Improvement] Implement smart sprint planning assistant — velocity-based story allocation",
     ["improvement", "process", "automation"], 3,
     "Tool to suggest story allocation for upcoming sprint based on team velocity history "
     "and story point estimates. Reduces sprint planning meeting from 2h to 30min."),
    ("[Improvement] Add ECU firmware version tracking to diagnostic dashboard",
     ["improvement", "diagnostics", "monitoring"], 5,
     "Dashboard showing current firmware version per ECU across all test benches. "
     "Alert when bench ECU version differs from reference."),
    ("[Improvement] Implement OTA campaign progress webhook — real-time Slack notifications",
     ["improvement", "ota", "integration", "harman"], 3,
     "Webhook notifies Slack channel on campaign start, 50% completion, success, and failure. "
     "Reduces manual monitoring during long OTA campaigns."),
    ("[Improvement] Add AUTOSAR memory usage profiling to safety partition",
     ["improvement", "safety", "performance", "autosar"], 8,
     "Profile stack and heap usage per AUTOSAR OS task. "
     "Alert if usage exceeds 80% of allocated memory. Prevents stack overflow in production."),
    ("[Improvement] Create unified integration test report — all benches, all components",
     ["improvement", "reporting", "testing"], 5,
     "Consolidated HTML report aggregating test results from all 5 benches. "
     "Auto-generated daily. Distributed to Stellantis PM and Capgemini leads."),
    ("[Improvement] Add dark mode to Harman HU — per Stellantis UX spec v3.0",
     ["improvement", "hmi", "infotainment", "harman"], 13,
     "Stellantis UX spec v3.0 §7.2 requires dark mode for all HU displays. "
     "Auto-switch based on ambient light sensor. Manual toggle in settings."),
    ("[Improvement] Implement power consumption telemetry — per-ECU real-time monitoring",
     ["improvement", "power", "monitoring", "marelli"], 8,
     "Real-time power consumption per ECU streamed to monitoring dashboard. "
     "Alert on anomalies > 20% above baseline. Supports quiescent current analysis."),
]

def step_H_tech_debt(jira: Jira) -> None:
    """Create tech debt and improvement backlog tickets."""
    log.info("=== Step H: Tech debt & improvements ===")

    task_type = next((v["name"] for v in jira.issue_types.values()
                      if v["name"].lower() == "task"), "Task")
    story_type = next((v["name"] for v in jira.issue_types.values()
                       if v["name"].lower() == "story"), "Story")

    for summary, labels, sp, detail in TECH_DEBT_ITEMS:
        f: Dict[str, Any] = {
            "project":   {"key": PROJECT_KEY},
            "summary":   summary,
            "issuetype": {"name": task_type},
            "priority":  {"name": random.choice(["Medium", "Low"])},
            "assignee":  {"id": ACCOUNT_CAPGEMINI},
            "labels":    labels + ["backlog", "chatbot-seed"],
            "description": adf_sections([
                ("Tech debt description", detail),
                ("Impact", "Developer productivity / system reliability / maintenance cost."),
                ("Proposed solution", "Refactor during next available sprint. Estimate: "
                                      f"{sp} story points."),
                ("Acceptance criteria",
                 "- Code reviewed and merged.\n"
                 "- Unit tests updated.\n"
                 "- No regression in integration tests."),
            ]),
        }
        if jira.story_points_field:
            f[jira.story_points_field] = sp
        jira.create(f)

    for summary, labels, sp, detail in IMPROVEMENT_ITEMS:
        f = {
            "project":   {"key": PROJECT_KEY},
            "summary":   summary,
            "issuetype": {"name": story_type},
            "priority":  {"name": random.choice(["Medium", "High"])},
            "assignee":  {"id": ACCOUNT_CAPGEMINI},
            "labels":    labels + ["improvement", "backlog", "chatbot-seed"],
            "description": adf_sections([
                ("Improvement description", detail),
                ("Business value", "Improves team velocity / product quality / Stellantis satisfaction."),
                ("Acceptance criteria",
                 f"- Feature delivered and demo-ed to PM.\n"
                 f"- Validated on at least 2 benches.\n"
                 f"- Documentation updated."),
            ]),
        }
        if jira.story_points_field:
            f[jira.story_points_field] = sp
        jira.create(f)

    log.info("Step H complete: %d tech debt + %d improvements created",
             len(TECH_DEBT_ITEMS), len(IMPROVEMENT_ITEMS))


# ──────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────
def main() -> int:
    jira = Jira()
    jira.bootstrap()

    # Load all existing issues
    log.info("Loading existing issues...")
    all_issues = jira.search(
        f"project = {PROJECT_KEY} ORDER BY created ASC",
        max_results=300,
        fields=["summary", "status", "issuetype", "labels",
                "assignee", "priority", "fixVersions", "duedate", "parent"],
    )
    log.info("Loaded %d issues", len(all_issues))

    # Load existing versions
    vers = jira.req("GET", f"/rest/api/3/project/{PROJECT_KEY}/versions").json()
    version_ids = {v["name"]: v["id"] for v in vers}
    log.info("Versions available: %s", list(version_ids.keys()))

    # ── Run all steps ──────────────────────────
    sprint_ids = step_A_sprints(jira, all_issues)
    step_B_transitions(jira, all_issues)
    step_C_cascade(jira, all_issues)
    step_D_roadmap(jira, all_issues, version_ids)
    comp_ids = step_E_components(jira, all_issues)
    regression_keys = step_F_regression(jira, all_issues)
    step_G_test_scenarios(jira, all_issues)
    step_H_tech_debt(jira)

    # ── Final summary ──────────────────────────
    print("\n" + "=" * 60)
    print("  ADVANCED ENRICHMENT COMPLETE")
    print("=" * 60)
    print(f"  A. Sprints créés/configurés : {len(sprint_ids)}")
    print(f"     (3 closed + 1 active avec vélocité et goals)")
    print(f"  B. Workflow transitions      : done")
    print(f"     (reopen cycles, review rejected, blocked documenté)")
    print(f"  C. Blocage en cascade        : done")
    print(f"     (chemin critique root cause analysé)")
    print(f"  D. Roadmap & dates           : done")
    print(f"     (overdue tickets, milestones Q2/Q3 2026)")
    print(f"  E. Composants créés          : {len(comp_ids)}")
    print(f"     ({', '.join(comp_ids.keys())})")
    print(f"  F. Régression tickets        : {len(regression_keys)}")
    print(f"     ({', '.join(regression_keys)})")
    print(f"  G. Test scenarios            : {len(TEST_SCENARIOS)}")
    print(f"     (PASS / FAIL / BLOCKED liés aux stories)")
    print(f"  H. Tech debt + improvements  : {len(TECH_DEBT_ITEMS) + len(IMPROVEMENT_ITEMS)}")
    print(f"     ({len(TECH_DEBT_ITEMS)} tech debt + {len(IMPROVEMENT_ITEMS)} improvements)")
    print("=" * 60)

    print("\nJQL de test pour le chatbot :")
    jql_tests = [
        f'project = {PROJECT_KEY} AND labels = critical-path',
        f'project = {PROJECT_KEY} AND labels = overdue',
        f'project = {PROJECT_KEY} AND labels = regression',
        f'project = {PROJECT_KEY} AND labels = test-failed',
        f'project = {PROJECT_KEY} AND labels = tech-debt ORDER BY story_points DESC',
        f'project = {PROJECT_KEY} AND labels = blocked AND issuetype = Story',
        f'project = {PROJECT_KEY} AND labels = review-rejected',
        f'project = {PROJECT_KEY} AND component = "CAN Communication" AND issuetype = Bug',
        f'project = {PROJECT_KEY} AND fixVersion = "v1.1.0 - CAN & Diagnostics Fix" AND status != Done',
        f'project = {PROJECT_KEY} AND labels = retest-required',
        f'project = {PROJECT_KEY} AND text ~ "root cause"',
        f'project = {PROJECT_KEY} AND labels = improvement AND labels = backlog',
        f'project = {PROJECT_KEY} AND duedate < "2026-04-01" AND status != Done',
    ]
    for jql in jql_tests:
        print(f"  {jql}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        raise SystemExit(130)
    except Exception as exc:
        log.exception("Fatal error: %s", exc)
        raise SystemExit(1)