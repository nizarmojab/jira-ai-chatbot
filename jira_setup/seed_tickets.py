#!/usr/bin/env python3
"""
seed_tickets.py
===============
Génération initiale des tickets Jira pour le projet chatbot.
Crée 200+ tickets réalistes dans un contexte automotive :
  - Client : Stellantis
  - Intégrateur : Capgemini Engineering
  - Fournisseur SW : Harman (infotainment, OTA)
  - Fournisseur HW : Marelli (diagnostics, CAN bus, ECU)

Usage :
    pip install requests python-dotenv
    python seed_tickets.py

    # Mode test sans écrire dans Jira :
    DRY_RUN=true python seed_tickets.py
"""
from __future__ import annotations

import os
import time
import random
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────
#  Config
# ──────────────────────────────────────────────
LOG_LEVEL         = os.getenv("LOG_LEVEL", "INFO").upper()
JIRA_BASE_URL     = os.getenv("JIRA_BASE_URL", "").rstrip("/")
JIRA_EMAIL        = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN    = os.getenv("JIRA_API_TOKEN", "")
JIRA_PROJECT_KEY  = os.getenv("JIRA_PROJECT_KEY", "SCRUM")
DRY_RUN           = os.getenv("DRY_RUN", "false").strip().lower() == "true"

REQUEST_TIMEOUT        = 30
SLEEP_BETWEEN_REQUESTS = 0.12
RANDOM_SEED            = 42
random.seed(RANDOM_SEED)

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s | %(levelname)-8s | %(message)s"
)
logger = logging.getLogger("jira-seeder")

# ── Suppliers ──────────────────────────────────
SUPPLIER_SW = "harman"
SUPPLIER_HW = "marelli"

# ── Volume ─────────────────────────────────────
NUM_EPICS         = 4
STORIES_PER_EPIC  = 8
TASKS_PER_EPIC    = 6
BUGS_PER_EPIC     = 6
SUBTASKS_PER_STORY = 3

# ── Features ───────────────────────────────────
COMMENTS_PER_ISSUE  = 1
ENABLE_LINKS        = True
ENABLE_DUE_DATES    = True
ENABLE_WATCHERS     = False
ENABLE_STORY_POINTS = True
STORY_POINT_VALUES  = [1, 2, 3, 5, 8]

COMMON_LABELS = [
    "stellantis", "capgemini", "automotive", "vehicle", "integration",
]

TARGET_STATUSES = ["To Do", "In Progress", "In Review", "Blocked", "Done"]


# ──────────────────────────────────────────────
#  Data classes
# ──────────────────────────────────────────────
@dataclass
class CreatedIssue:
    key: str
    issue_id: str
    summary: str
    issue_type: str
    parent_key: Optional[str] = None
    epic_key: Optional[str] = None
    desired_status: Optional[str] = None
    labels: List[str] = field(default_factory=list)


class JiraError(RuntimeError):
    pass


# ──────────────────────────────────────────────
#  Jira Client
# ──────────────────────────────────────────────
class JiraClient:
    def __init__(self, base_url: str, email: str, api_token: str,
                 project_key: str) -> None:
        if not all([base_url, email, api_token, project_key]):
            raise JiraError(
                "Missing config. Set JIRA_BASE_URL, JIRA_EMAIL, "
                "JIRA_API_TOKEN, JIRA_PROJECT_KEY."
            )
        self.base_url    = base_url
        self.project_key = project_key
        self.email       = email
        self.session     = requests.Session()
        self.session.auth = HTTPBasicAuth(email, api_token)
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        self.issue_types:           Dict[str, Dict[str, Any]] = {}
        self.fields_by_name:        Dict[str, str] = {}
        self.link_types:            Dict[str, Dict[str, str]] = {}
        self.account_id:            Optional[str] = None
        self.story_points_field_id: Optional[str] = None
        self.epic_name_field_id:    Optional[str] = None
        self.epic_link_field_id:    Optional[str] = None

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        if DRY_RUN and method.upper() in {"POST", "PUT", "DELETE"}:
            logger.info("[DRY_RUN] %s %s", method, path)
            class _Fake:
                status_code = 200
                def json(self): return {"dry_run": True}
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            return _Fake()  # type: ignore
        r = self.session.request(method, self._url(path),
                                 timeout=REQUEST_TIMEOUT, **kwargs)
        if r.status_code >= 400:
            try:   payload = r.json()
            except Exception: payload = r.text
            raise JiraError(f"{method} {path} [{r.status_code}]: {payload}")
        time.sleep(SLEEP_BETWEEN_REQUESTS)
        return r

    # ── Bootstrap ──────────────────────────────
    def verify_connection(self) -> None:
        resp = self.request("GET", "/rest/api/3/myself")
        me = resp.json()
        self.account_id = me.get("accountId")
        logger.info("Connected to Jira as %s", me.get("displayName", self.email))

    def load_issue_types(self) -> None:
        resp = self.request("GET", "/rest/api/3/issuetype")
        all_types = resp.json()
        self.issue_types = {t["name"].lower().strip(): t for t in all_types}
        logger.info("Issue types: %s",
                    ", ".join(sorted(t["name"] for t in all_types)))

    def load_fields(self) -> None:
        resp = self.request("GET", "/rest/api/3/field")
        fields = resp.json()
        self.fields_by_name = {f["name"].lower().strip(): f["id"] for f in fields}
        for f in fields:
            n = f["name"].lower().strip()
            if "story point" in n: self.story_points_field_id = f["id"]
            if n == "epic name":   self.epic_name_field_id    = f["id"]
            if n == "epic link":   self.epic_link_field_id    = f["id"]
        logger.info("Loaded %d fields", len(fields))

    def load_link_types(self) -> None:
        resp = self.request("GET", "/rest/api/2/issueLinkType")
        data = resp.json()
        self.link_types = {lt["name"].lower(): lt
                           for lt in data.get("issueLinkTypes", [])}
        logger.info("Link types: %s",
                    ", ".join(sorted(self.link_types.keys())))

    # ── Issue type helpers ─────────────────────
    def get_issue_type_name(self, preferred: str,
                            fallback: Optional[str] = None) -> str:
        pl = preferred.lower().strip()
        if pl in self.issue_types:
            return self.issue_types[pl]["name"]
        if pl in {"sub-task", "subtask", "sub task"}:
            for it in self.issue_types.values():
                if it.get("subtask") is True:
                    return it["name"]
        if fallback:
            fl = fallback.lower().strip()
            if fl in self.issue_types:
                logger.warning("Issue type '%s' not found, using '%s'",
                               preferred, fallback)
                return self.issue_types[fl]["name"]
        raise JiraError(
            f"Issue type '{preferred}' not found. "
            f"Available: {', '.join(sorted(self.issue_types.keys()))}"
        )

    def get_subtask_issue_type_name(self) -> str:
        for it in self.issue_types.values():
            if it.get("subtask") is True:
                return it["name"]
        raise JiraError("No subtask issue type found.")

    # ── CRUD ───────────────────────────────────
    def create_issue(
        self,
        issue_type: str,
        summary: str,
        description: str,
        priority: Optional[str] = None,
        labels: Optional[List[str]] = None,
        parent_key: Optional[str] = None,
        epic_key: Optional[str] = None,
        due_date: Optional[str] = None,
        story_points: Optional[int] = None,
    ) -> CreatedIssue:
        fields: Dict[str, Any] = {
            "project":   {"key": self.project_key},
            "summary":   summary,
            "issuetype": {"name": issue_type},
            "description": {
                "type": "doc", "version": 1,
                "content": [{"type": "paragraph",
                             "content": [{"type": "text", "text": description}]}]
            },
        }
        if priority:   fields["priority"] = {"name": priority}
        if labels:     fields["labels"]   = labels
        if ENABLE_DUE_DATES and due_date:
            fields["duedate"] = due_date

        # subtask check
        is_subtask = any(
            it["name"].lower().strip() == issue_type.lower().strip()
            and it.get("subtask") is True
            for it in self.issue_types.values()
        )
        if parent_key and not is_subtask:
            raise JiraError(
                f"Cannot set parent for non-subtask type '{issue_type}'."
            )
        if parent_key:
            fields["parent"] = {"key": parent_key}
        if issue_type.lower() == "epic" and self.epic_name_field_id:
            fields[self.epic_name_field_id] = summary[:255]
        if epic_key and not parent_key:
            if self.epic_link_field_id:
                fields[self.epic_link_field_id] = epic_key
            else:
                fields["parent"] = {"key": epic_key}
        if story_points and ENABLE_STORY_POINTS and self.story_points_field_id:
            fields[self.story_points_field_id] = story_points

        if DRY_RUN:
            fake_key = f"{self.project_key}-DRY-{random.randint(1000, 9999)}"
            logger.info("[DRY] %-10s %-18s %s", issue_type, fake_key, summary)
            return CreatedIssue(
                key=fake_key,
                issue_id=str(random.randint(100000, 999999)),
                summary=summary, issue_type=issue_type,
                parent_key=parent_key, epic_key=epic_key,
                labels=labels or [],
            )

        resp = self.request("POST", "/rest/api/3/issue",
                            json={"fields": fields})
        data = resp.json()
        logger.info("Created %-10s %-12s %s",
                    issue_type, data["key"], summary)
        return CreatedIssue(
            key=data["key"], issue_id=data["id"],
            summary=summary, issue_type=issue_type,
            parent_key=parent_key, epic_key=epic_key,
            labels=labels or [],
        )

    def add_comment(self, issue_key: str, text: str) -> None:
        body = {
            "type": "doc", "version": 1,
            "content": [{"type": "paragraph",
                         "content": [{"type": "text", "text": text}]}]
        }
        self.request("POST", f"/rest/api/3/issue/{issue_key}/comment",
                     json={"body": body})

    def get_issue(self, key: str) -> Dict[str, Any]:
        return self.request("GET", f"/rest/api/3/issue/{key}").json()

    def get_transitions(self, key: str) -> List[Dict[str, Any]]:
        return self.request("GET",
            f"/rest/api/3/issue/{key}/transitions").json().get("transitions", [])

    def move_towards_status(self, key: str, target: str,
                            max_steps: int = 6) -> bool:
        for _ in range(max_steps):
            issue   = self.get_issue(key)
            current = issue["fields"]["status"]["name"]
            if current.lower() == target.lower():
                return True
            transitions = self.get_transitions(key)
            if not transitions:
                return False
            direct = next(
                (t for t in transitions
                 if t.get("to", {}).get("name", "").lower() == target.lower()),
                None
            )
            if direct:
                self.request("POST",
                    f"/rest/api/3/issue/{key}/transitions",
                    json={"transition": {"id": direct["id"]}})
                continue
            order = {
                "to do":      ["In Progress", "In Review", "Done"],
                "in progress":["In Review", "Done"],
                "in review":  ["Done"],
                "blocked":    ["In Progress", "Done"],
            }
            candidates = order.get(current.lower(), [])
            chosen = None
            for c in candidates:
                chosen = next(
                    (t for t in transitions
                     if t.get("to", {}).get("name", "").lower() == c.lower()),
                    None
                )
                if chosen: break
            if not chosen:
                return False
            self.request("POST",
                f"/rest/api/3/issue/{key}/transitions",
                json={"transition": {"id": chosen["id"]}})
        return self.get_issue(key)["fields"]["status"]["name"].lower() \
               == target.lower()

    def create_issue_link(self, inward: str, outward: str,
                          preferences: List[str]) -> bool:
        chosen = None
        for pref in preferences:
            if pref.lower() in self.link_types:
                chosen = self.link_types[pref.lower()]
                break
        if not chosen:
            return False
        try:
            self.request("POST", "/rest/api/3/issueLink", json={
                "type":          {"name": chosen["name"]},
                "inwardIssue":   {"key": inward},
                "outwardIssue":  {"key": outward},
            })
            logger.info("Linked %s -[%s]-> %s", inward, chosen["name"], outward)
            return True
        except JiraError as e:
            logger.warning("Link failed %s→%s: %s", inward, outward, e)
            return False


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────
def due_date_for(offset: int) -> str:
    day   = 10 + offset
    month = 5 if day > 30 else 4
    if day > 30: day -= 30
    return f"2026-{month:02d}-{day:02d}"


def automotive_description(title: str, domain: str,
                           supplier: str, component: str) -> str:
    return (
        f"Client: Stellantis\n"
        f"Integrator: Capgemini Engineering\n"
        f"Supplier: {supplier.title()}\n"
        f"Domain: {domain}\n"
        f"Component: {component}\n"
        f"Environment: Vehicle test bench / integration lab\n\n"
        f"Context:\n{title}\n\n"
        f"Expected behavior:\n"
        f"The component should behave according to system requirements.\n\n"
        f"Actual behavior:\n"
        f"The observed behavior does not match the expected result.\n"
    )


def choose_priority(issue_type: str) -> str:
    t = issue_type.lower()
    if t == "bug":   return random.choices(["Highest","High","Medium"], [2,5,3])[0]
    if t == "epic":  return random.choices(["High","Medium"], [3,2])[0]
    return random.choices(["High","Medium","Low"], [2,5,2])[0]


def choose_status(issue_type: str) -> str:
    if issue_type.lower() == "epic":
        return random.choices(["To Do","In Progress"], [1,3])[0]
    return random.choices(TARGET_STATUSES, [35,25,20,10,10])[0]


def choose_sp(issue_type: str) -> Optional[int]:
    if issue_type.lower() in {"story","task"}:
        return random.choice(STORY_POINT_VALUES)
    return None


def labels_for(issue_type: str, supplier: str, component: str,
               extra: Optional[List[str]] = None) -> List[str]:
    lbs = set(COMMON_LABELS)
    lbs.add(supplier.lower())
    lbs.add(component.lower().replace(" ", "-"))
    lbs.add(issue_type.lower().replace(" ", "-"))
    if extra: lbs.update(x.lower() for x in extra)
    return sorted(lbs)


# ──────────────────────────────────────────────
#  Content
# ──────────────────────────────────────────────
def build_epic_specs() -> List[Dict[str, str]]:
    return [
        {"summary": "Vehicle Infotainment System",
         "supplier": SUPPLIER_SW, "component": "infotainment", "domain": "software"},
        {"summary": "Vehicle Diagnostics & Monitoring",
         "supplier": SUPPLIER_HW, "component": "diagnostics", "domain": "integration"},
        {"summary": "OTA Update System",
         "supplier": SUPPLIER_SW, "component": "ota", "domain": "software"},
        {"summary": "Connectivity & CAN Communication",
         "supplier": SUPPLIER_HW, "component": "canbus", "domain": "hardware"},
    ]


STORY_TITLES: Dict[str, List[str]] = {
    "Vehicle Infotainment System": [
        "Integrate Harman infotainment module",
        "Implement media source switching",
        "Improve infotainment startup sequence",
        "Add Bluetooth pairing workflow",
        "Validate touchscreen responsiveness",
        "Stabilize navigation rendering",
        "Improve startup performance metrics",
        "Support voice command initialization",
    ],
    "Vehicle Diagnostics & Monitoring": [
        "Implement vehicle diagnostic system",
        "Expose ECU health monitoring endpoint",
        "Add DTC retrieval workflow",
        "Aggregate bench test diagnostics",
        "Build diagnostics dashboard backend",
        "Improve vehicle health event model",
        "Track sensor state transitions",
        "Add diagnostics export endpoint",
    ],
    "OTA Update System": [
        "Add OTA update feature",
        "Implement update package validation",
        "Build OTA rollback capability",
        "Track update campaign progress",
        "Validate OTA signature verification",
        "Improve update scheduling logic",
        "Handle low-battery update conditions",
        "Build update audit reporting",
    ],
    "Connectivity & CAN Communication": [
        "Stabilize CAN bus communication layer",
        "Detect intermittent CAN failures",
        "Add bus recovery handling",
        "Monitor communication latency",
        "Improve gateway fault visibility",
        "Correlate CAN errors with ECU reset events",
        "Track wake-up frame reliability",
        "Improve CAN watchdog diagnostics",
    ],
}

TASK_TITLES: Dict[str, List[str]] = {
    "Vehicle Infotainment System": [
        "Debug Harman API communication",
        "Review infotainment authentication flow",
        "Analyze startup logs",
        "Validate HMI resource loading",
        "Measure UI freeze frequency",
        "Document media service dependencies",
    ],
    "Vehicle Diagnostics & Monitoring": [
        "Analyze CAN bus logs",
        "Verify ECU firmware version",
        "Build diagnostic API contract",
        "Test Marelli hardware integration",
        "Document fault code mapping",
        "Inspect bench data collection pipeline",
    ],
    "OTA Update System": [
        "Create OTA package manifest",
        "Verify rollback package behavior",
        "Test interrupted update recovery",
        "Document OTA backend endpoints",
        "Benchmark update time on bench",
        "Inspect update error telemetry",
    ],
    "Connectivity & CAN Communication": [
        "Capture CAN traces during ignition",
        "Compare bus state across test runs",
        "Reproduce intermittent communication loss",
        "Validate bus watchdog handling",
        "Inspect ECU boot handshake",
        "Document bus reset scenarios",
    ],
}

BUG_TITLES: Dict[str, List[str]] = {
    "Vehicle Infotainment System": [
        "Infotainment UI freeze on startup",
        "Audio source disappears after ignition cycle",
        "Bluetooth pairing screen becomes unresponsive",
        "Navigation map tiles fail to render",
        "Touch input lag exceeds threshold",
        "Voice command service not available after reboot",
    ],
    "Vehicle Diagnostics & Monitoring": [
        "GPS synchronization delay",
        "Diagnostic request times out intermittently",
        "ECU health status not refreshed",
        "Fault code list incomplete in dashboard",
        "Bench diagnostics service returns stale data",
        "Sensor anomaly status not propagated",
    ],
    "OTA Update System": [
        "OTA package validation fails on signed bundle",
        "Rollback not triggered after failed update",
        "Update progress stuck at 82 percent",
        "Campaign status not updated after reboot",
        "Device reports success despite incomplete update",
        "Post-update validation does not run",
    ],
    "Connectivity & CAN Communication": [
        "ECU not responding after ignition",
        "CAN bus communication lost intermittently",
        "Gateway frame loss observed under load",
        "Heartbeat message missing after wake-up",
        "CAN recovery logic does not reinitialize bus",
        "Diagnostic frames dropped during heavy traffic",
    ],
}

SUBTASK_TITLES: Dict[str, List[str]] = {
    "Integrate Harman infotainment module":
        ["Analyze Harman API endpoints", "Fix authentication issues",
         "Test infotainment integration"],
    "Implement vehicle diagnostic system":
        ["Collect vehicle diagnostic data", "Build diagnostic API",
         "Test ECU communication"],
    "Add OTA update feature":
        ["Define update package format", "Implement update trigger endpoint",
         "Validate post-update health checks"],
    "Stabilize CAN bus communication layer":
        ["Inspect CAN transceiver state", "Replay failing CAN traces",
         "Validate communication recovery path"],
}


def comment_text(issue_type: str, summary: str) -> str:
    return (
        f"Auto-generated test data for chatbot scenario.\n"
        f"Use case: query, summarize, update, assign, dependency analysis.\n"
        f"Issue type: {issue_type}\n"
        f"Summary: {summary}"
    )


# ──────────────────────────────────────────────
#  Seeding
# ──────────────────────────────────────────────
def seed_project(jira: JiraClient) -> Dict[str, List[CreatedIssue]]:
    created: Dict[str, List[CreatedIssue]] = {
        "epics": [], "stories": [], "tasks": [], "bugs": [], "subtasks": []
    }
    epic_specs = build_epic_specs()

    # ── Epics ──────────────────────────────────
    for idx, spec in enumerate(epic_specs, 1):
        etype = jira.get_issue_type_name("Epic", fallback="Story")
        issue = jira.create_issue(
            issue_type=etype,
            summary=spec["summary"],
            description=automotive_description(
                spec["summary"], spec["domain"],
                spec["supplier"], spec["component"]),
            priority=choose_priority("Epic"),
            labels=labels_for("epic", spec["supplier"],
                              spec["component"], ["portfolio","parent"]),
            due_date=due_date_for(idx),
        )
        issue.desired_status = choose_status("Epic")
        created["epics"].append(issue)
        if COMMENTS_PER_ISSUE > 0:
            jira.add_comment(issue.key, comment_text(etype, spec["summary"]))

    # ── Stories + Subtasks + Tasks + Bugs per epic ──
    for ei, epic_issue in enumerate(created["epics"]):
        spec     = epic_specs[ei]
        supplier = spec["supplier"]
        comp     = spec["component"]
        domain   = spec["domain"]
        esum     = spec["summary"]

        # Stories
        for i, title in enumerate(STORY_TITLES.get(esum, [])[:STORIES_PER_EPIC]):
            stype = jira.get_issue_type_name("Story", fallback="Task")
            issue = jira.create_issue(
                issue_type=stype, summary=title,
                description=automotive_description(title, domain, supplier, comp),
                priority=choose_priority("Story"),
                labels=labels_for("story", supplier, comp, ["feature"]),
                epic_key=epic_issue.key,
                due_date=due_date_for((ei*5+i) % 12 + 1),
                story_points=choose_sp("Story"),
            )
            issue.epic_key      = epic_issue.key
            issue.desired_status = choose_status("Story")
            created["stories"].append(issue)
            if COMMENTS_PER_ISSUE > 0:
                jira.add_comment(issue.key, comment_text(stype, title))

            # Subtasks
            st_type = jira.get_subtask_issue_type_name()
            for st_title in (SUBTASK_TITLES.get(title)
                             or [f"{title} - Subtask {k+1}"
                                 for k in range(SUBTASKS_PER_STORY)])[:SUBTASKS_PER_STORY]:
                st = jira.create_issue(
                    issue_type=st_type, summary=st_title,
                    description=automotive_description(
                        st_title, domain, supplier, comp),
                    priority=choose_priority("Task"),
                    labels=labels_for("sub-task", supplier, comp, ["child"]),
                    parent_key=issue.key,
                    due_date=due_date_for((ei*7+i) % 10 + 1),
                )
                st.parent_key    = issue.key
                st.epic_key      = epic_issue.key
                st.desired_status = choose_status("Task")
                created["subtasks"].append(st)
                if COMMENTS_PER_ISSUE > 0:
                    jira.add_comment(st.key, comment_text(st_type, st_title))

        # Tasks
        for i, title in enumerate(TASK_TITLES.get(esum, [])[:TASKS_PER_EPIC]):
            ttype = jira.get_issue_type_name("Task", fallback="Story")
            issue = jira.create_issue(
                issue_type=ttype, summary=title,
                description=automotive_description(title, domain, supplier, comp),
                priority=choose_priority("Task"),
                labels=labels_for("task", supplier, comp, ["technical"]),
                epic_key=epic_issue.key,
                due_date=due_date_for((ei*3+i) % 11 + 1),
                story_points=choose_sp("Task"),
            )
            issue.epic_key       = epic_issue.key
            issue.desired_status = choose_status("Task")
            created["tasks"].append(issue)
            if COMMENTS_PER_ISSUE > 0:
                jira.add_comment(issue.key, comment_text(ttype, title))

        # Bugs
        for i, title in enumerate(BUG_TITLES.get(esum, [])[:BUGS_PER_EPIC]):
            btype = jira.get_issue_type_name("Bug", fallback="Task")
            issue = jira.create_issue(
                issue_type=btype, summary=title,
                description=automotive_description(title, domain, supplier, comp),
                priority=choose_priority("Bug"),
                labels=labels_for("bug", supplier, comp, ["defect"]),
                epic_key=epic_issue.key,
                due_date=due_date_for((ei*4+i) % 9 + 1),
            )
            issue.epic_key       = epic_issue.key
            issue.desired_status = choose_status("Bug")
            created["bugs"].append(issue)
            if COMMENTS_PER_ISSUE > 0:
                jira.add_comment(issue.key, comment_text(btype, title))

    return created


def create_dependencies(jira: JiraClient,
                        created: Dict[str, List[CreatedIssue]]) -> None:
    if not ENABLE_LINKS:
        return
    bugs    = created["bugs"]
    tasks   = created["tasks"]
    stories = created["stories"]

    for i in range(min(len(bugs), len(tasks))):
        if i % 2 == 0:
            jira.create_issue_link(bugs[i].key, tasks[i].key,
                                   ["Blocks","Relates"])
    for i in range(0, len(stories)-1, 2):
        jira.create_issue_link(stories[i].key, stories[i+1].key,
                               ["Relates","Blocks"])

    by_sum = lambda lst: {x.summary: x.key for x in lst}
    b_map  = by_sum(bugs)
    t_map  = by_sum(tasks)
    s_map  = by_sum(stories)

    if ("GPS synchronization delay" in b_map
            and "Analyze CAN bus logs" in t_map):
        jira.create_issue_link(b_map["GPS synchronization delay"],
                               t_map["Analyze CAN bus logs"],
                               ["Blocks","Relates"])
    if ("CAN bus communication lost intermittently" in b_map
            and "Stabilize CAN bus communication layer" in s_map):
        jira.create_issue_link(
            b_map["CAN bus communication lost intermittently"],
            s_map["Stabilize CAN bus communication layer"],
            ["Relates","Blocks"])


def transition_issues(jira: JiraClient,
                      created: Dict[str, List[CreatedIssue]]) -> None:
    for group in ["stories","tasks","bugs","subtasks","epics"]:
        for issue in created[group]:
            if issue.desired_status and \
               issue.desired_status.lower() != "to do":
                try:
                    jira.move_towards_status(issue.key, issue.desired_status)
                except Exception as e:
                    logger.warning("Transition %s: %s", issue.key, e)


def print_summary(created: Dict[str, List[CreatedIssue]]) -> None:
    total = sum(len(v) for v in created.values())
    print("\n=== CREATION SUMMARY ===")
    for g in ["epics","stories","tasks","bugs","subtasks"]:
        print(f"{g.capitalize():10}: {len(created[g])}")
    print(f"{'Total':10}: {total}")
    print("\nSample issues:")
    for g in ["epics","stories","bugs"]:
        for iss in created[g][:2]:
            print(f"  {iss.key:<14} [{g[:-1]}] {iss.summary}")
    print("\nJQL checks:")
    pk = JIRA_PROJECT_KEY
    for jql in [
        f"project = {pk}",
        f'project = {pk} AND status = "Blocked"',
        f"project = {pk} AND issuetype = Bug",
        f"project = {pk} AND issuetype = Epic",
        f"project = {pk} AND labels = harman",
        f"project = {pk} AND labels = marelli",
    ]:
        print(f"  {jql}")


# ──────────────────────────────────────────────
#  Main
# ──────────────────────────────────────────────
def main() -> int:
    jira = JiraClient(
        base_url=JIRA_BASE_URL,
        email=JIRA_EMAIL,
        api_token=JIRA_API_TOKEN,
        project_key=JIRA_PROJECT_KEY,
    )
    jira.verify_connection()
    jira.load_issue_types()
    jira.load_fields()
    jira.load_link_types()

    created = seed_project(jira)
    create_dependencies(jira, created)
    transition_issues(jira, created)
    print_summary(created)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        raise SystemExit(130)
    except Exception as e:
        logger.exception("Fatal error: %s", e)
        raise SystemExit(1)