#!/usr/bin/env python3
"""
enrich_tickets.py
=================
Enrichissement complet du projet Jira pour tester le chatbot.

8 améliorations :
  1. Descriptions techniques réalistes (steps to reproduce, ADF, CAN frames, ECU codes)
  2. Sprints & fix versions (release milestones)
  3. Assignees multiples (3 personas : capgemini, harman, marelli)
  4. Dépendances complexes (chaînes 3-4 niveaux, cross-epic)
  5. Commentaires multi-tours (conversations dev ↔ QA ↔ tech lead)
  6. Nouveaux epics (Safety/AUTOSAR + Power Management)
  7. Time tracking & worklogs (estimates, time spent)
  8. Custom fields via labels enrichis (ECU_ID, CAN_Frame, SW_version, bench)

Usage :
    pip install requests python-dotenv
    python enrich_tickets.py
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

# Les 3 personas (même account_id = vous)
ACCOUNT_CAPGEMINI = os.getenv("JIRA_ACCOUNT_ID",   "712020:35298345-dfb1-4141-9ebe-3bbdc27697ab")
ACCOUNT_HARMAN    = os.getenv("HARMAN_ACCOUNT_ID",  "712020:35298345-dfb1-4141-9ebe-3bbdc27697ab")
ACCOUNT_MARELLI   = os.getenv("MARELLI_ACCOUNT_ID", "712020:35298345-dfb1-4141-9ebe-3bbdc27697ab")

PERSONAS = [ACCOUNT_CAPGEMINI, ACCOUNT_HARMAN, ACCOUNT_MARELLI]
PERSONA_NAMES = {
    ACCOUNT_CAPGEMINI: "jean.dupont (Capgemini)",
    ACCOUNT_HARMAN:    "ali.chen (Harman)",
    ACCOUNT_MARELLI:   "sofia.rossi (Marelli)",
}

REQUEST_TIMEOUT          = 30
SLEEP_BETWEEN_REQUESTS   = 0.15
RANDOM_SEED              = 99
random.seed(RANDOM_SEED)

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger("jira-enricher")


# ──────────────────────────────────────────────
#  Jira HTTP client
# ──────────────────────────────────────────────
class JiraError(RuntimeError):
    pass


class JiraClient:
    def __init__(self) -> None:
        if not all([JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN]):
            raise JiraError("Missing JIRA_BASE_URL / JIRA_EMAIL / JIRA_API_TOKEN in .env")
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
        self.session.headers.update({"Accept": "application/json", "Content-Type": "application/json"})
        self.issue_types: Dict[str, Any]  = {}
        self.link_types:  Dict[str, Any]  = {}
        self.story_points_field_id: Optional[str] = None
        self.epic_link_field_id:    Optional[str] = None
        self.epic_name_field_id:    Optional[str] = None
        self.time_tracking_enabled: bool = False

    def _url(self, path: str) -> str:
        return f"{JIRA_BASE_URL}{path}"

    def req(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        if DRY_RUN and method.upper() in {"POST", "PUT", "DELETE"}:
            logger.info("[DRY_RUN] %s %s", method, path)
            class _Fake:
                status_code = 200
                def json(self): return {"dry_run": True, "id": "FAKE", "key": f"{JIRA_PROJECT_KEY}-DRY"}
                def raise_for_status(self): pass
            time.sleep(SLEEP_BETWEEN_REQUESTS)
            return _Fake()  # type: ignore
        r = self.session.request(method, self._url(path), timeout=REQUEST_TIMEOUT, **kwargs)
        if r.status_code >= 400:
            try:   payload = r.json()
            except Exception: payload = r.text
            raise JiraError(f"{method} {path} [{r.status_code}]: {payload}")
        time.sleep(SLEEP_BETWEEN_REQUESTS)
        return r

    # ── Bootstrap ──────────────────────────────
    def bootstrap(self) -> None:
        me = self.req("GET", "/rest/api/3/myself").json()
        logger.info("Connected as %s", me.get("displayName"))

        types = self.req("GET", "/rest/api/3/issuetype").json()
        self.issue_types = {t["name"].lower(): t for t in types}

        fields = self.req("GET", "/rest/api/3/field").json()
        for f in fields:
            n = f["name"].lower()
            if "story point" in n:  self.story_points_field_id = f["id"]
            if n == "epic link":    self.epic_link_field_id    = f["id"]
            if n == "epic name":    self.epic_name_field_id    = f["id"]

        lt = self.req("GET", "/rest/api/2/issueLinkType").json()
        self.link_types = {l["name"].lower(): l for l in lt.get("issueLinkTypes", [])}
        logger.info("Link types: %s", list(self.link_types.keys()))

    # ── Issues ─────────────────────────────────
    def search(self, jql: str, max_results: int = 200, fields: Optional[List[str]] = None) -> List[Dict]:
        payload = {
            "jql": jql,
            "maxResults": max_results,
            "fields": fields or ["summary", "status", "issuetype", "labels", "assignee", "priority"],
        }
        return self.req("POST", "/rest/api/3/search/jql", json=payload).json().get("issues", [])

    def get_issue(self, key: str) -> Dict:
        return self.req("GET", f"/rest/api/3/issue/{key}").json()

    def update_issue(self, key: str, fields: Dict) -> None:
        self.req("PUT", f"/rest/api/3/issue/{key}", json={"fields": fields})
        logger.debug("Updated %s", key)

    def create_issue(self, fields: Dict) -> Dict:
        return self.req("POST", "/rest/api/3/issue", json={"fields": fields}).json()

    def add_comment(self, key: str, adf_body: Dict) -> None:
        self.req("POST", f"/rest/api/3/issue/{key}/comment", json={"body": adf_body})

    def add_worklog(self, key: str, time_spent: str, original_estimate: str) -> None:
        try:
            self.req("POST", f"/rest/api/3/issue/{key}/worklog",
                     json={"timeSpent": time_spent, "comment": adf_text("Engineering work logged.")})
        except JiraError as e:
            logger.warning("Worklog failed on %s: %s", key, e)

    def update_original_estimate(self, key: str, estimate: str) -> None:
        try:
            self.req("PUT", f"/rest/api/3/issue/{key}",
                     json={"fields": {"timetracking": {"originalEstimate": estimate}}})
        except JiraError as e:
            logger.warning("Time estimate failed on %s: %s", key, e)

    def link_issues(self, inward: str, outward: str, link_name: str) -> None:
        chosen = None
        for name, lt in self.link_types.items():
            if link_name.lower() in name:
                chosen = lt
                break
        if not chosen:
            chosen = list(self.link_types.values())[0] if self.link_types else None
        if not chosen:
            logger.warning("No link type found for '%s'", link_name)
            return
        try:
            self.req("POST", "/rest/api/3/issueLink", json={
                "type": {"name": chosen["name"]},
                "inwardIssue":  {"key": inward},
                "outwardIssue": {"key": outward},
            })
            logger.info("Linked %s -[%s]-> %s", inward, chosen["name"], outward)
        except JiraError as e:
            logger.warning("Link failed %s→%s: %s", inward, outward, e)

    def get_or_create_version(self, name: str, description: str, release_date: str) -> str:
        vers = self.req("GET", f"/rest/api/3/project/{JIRA_PROJECT_KEY}/versions").json()
        for v in vers:
            if v["name"] == name:
                return v["id"]
        v = self.req("POST", "/rest/api/3/version", json={
            "name": name,
            "description": description,
            "project": JIRA_PROJECT_KEY,
            "released": False,
            "releaseDate": release_date,
        }).json()
        logger.info("Created version %s", name)
        return v.get("id", "")


# ──────────────────────────────────────────────
#  ADF helpers
# ──────────────────────────────────────────────
def adf_text(text: str) -> Dict:
    return {"type": "doc", "version": 1, "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": text}]}
    ]}

def adf_doc(*paragraphs: str) -> Dict:
    content = []
    for p in paragraphs:
        content.append({"type": "paragraph", "content": [{"type": "text", "text": p}]})
    return {"type": "doc", "version": 1, "content": content}

def adf_rich(sections: List[Dict]) -> Dict:
    """
    sections: list of {"heading": str, "body": str}
    """
    content = []
    for s in sections:
        content.append({"type": "heading", "attrs": {"level": 3},
                        "content": [{"type": "text", "text": s["heading"]}]})
        content.append({"type": "paragraph",
                        "content": [{"type": "text", "text": s["body"]}]})
    return {"type": "doc", "version": 1, "content": content}


# ──────────────────────────────────────────────
#  1. Descriptions techniques réalistes
# ──────────────────────────────────────────────
BUG_DESCRIPTIONS: Dict[str, List[Dict]] = {
    "CAN bus communication lost intermittently": [
        {"heading": "Environment",
         "body": "Vehicle: Stellantis EMP2 platform | Bench: CAN-HIL-03 | SW: Marelli GW v2.4.1 | Harman HU v3.1.0"},
        {"heading": "Steps to reproduce",
         "body": (
             "1. Power on the vehicle bench (ignition ON).\n"
             "2. Start CAN logger (CANalyzer 17.0) on channels HS-CAN and MS-CAN.\n"
             "3. Trigger 3 consecutive ignition OFF/ON cycles within 30 seconds.\n"
             "4. Observe frames on ID 0x7DF (diagnostic request) and 0x7E8 (ECU response).\n"
             "5. After cycle 3, communication on HS-CAN drops for 4–8 seconds before recovering."
         )},
        {"heading": "Actual behavior",
         "body": "Frame loss observed: 0x7DF timeout after 150ms. Bus enters passive error state. "
                 "Error frames logged: 0x00FF (bus off counter = 3). CAN controller does not auto-reinitialize."},
        {"heading": "Expected behavior",
         "body": "Bus should recover within 50ms. CAN controller must reinitialize per ISO 11898-1 §6.3."},
        {"heading": "Acceptance criteria",
         "body": (
             "- AC1: No frame loss > 50ms after any ignition cycle.\n"
             "- AC2: Error counter resets within 2 bus-off events.\n"
             "- AC3: Regression test passes on CAN-HIL-03 and CAN-HIL-07."
         )},
        {"heading": "Attachments",
         "body": "CAN trace: can_log_20260410_HIL03.blf | Oscilloscope capture: scope_bus_off_20260410.png"},
    ],
    "ECU not responding after ignition": [
        {"heading": "Environment",
         "body": "ECU: Marelli BCM v1.9.3 | Bench: INT-BENCH-02 | Test tool: CANoe 16.0 | Battery: 12.4V"},
        {"heading": "Steps to reproduce",
         "body": (
             "1. Set bench to 12V nominal.\n"
             "2. Run ignition sequence: ACC → ON → START → ON.\n"
             "3. Send UDS diagnostic request 0x10 01 (Default Session) on CAN ID 0x7E0.\n"
             "4. Observe: ECU does not respond within 50ms."
         )},
        {"heading": "Actual behavior",
         "body": "ECU silent on 0x7E8. No NRC (Negative Response Code). Boot sequence log shows "
                 "WDT reset event at timestamp +320ms post-ignition. DTC P0601 stored."},
        {"heading": "Expected behavior",
         "body": "ECU must respond to UDS 0x10 01 within 50ms of bus active (per ISO 14229)."},
        {"heading": "Acceptance criteria",
         "body": (
             "- AC1: UDS response within 50ms on 10 consecutive cycles.\n"
             "- AC2: DTC P0601 cleared and does not reappear after fix.\n"
             "- AC3: WDT reset counter = 0 after 5 ignition cycles."
         )},
    ],
    "OTA package validation fails on signed bundle": [
        {"heading": "Environment",
         "body": "OTA Backend: Harman OTA Server v4.2 | Target: HU SW 3.0.1 | Bundle: v3.1.0-rc2.zip | "
                 "Signing tool: OpenSSL 3.0 / RSA-2048"},
        {"heading": "Steps to reproduce",
         "body": (
             "1. Generate update bundle v3.1.0-rc2.zip with signing tool.\n"
             "2. Upload to OTA staging server.\n"
             "3. Trigger OTA campaign for device group BENCH-GROUP-A.\n"
             "4. Device downloads bundle (SHA256 verified OK).\n"
             "5. Validation step fails with error: SIGNATURE_MISMATCH (code 0xE4)."
         )},
        {"heading": "Actual behavior",
         "body": "Error 0xE4 SIGNATURE_MISMATCH returned by validation module. "
                 "Bundle rejected. Device rolls back to v3.0.1. "
                 "Root cause: signing cert chain includes intermediate CA not provisioned on device trust store."},
        {"heading": "Expected behavior",
         "body": "Signed bundle must pass validation. All CA certs in chain must be pre-provisioned per UNECE R156."},
        {"heading": "Acceptance criteria",
         "body": (
             "- AC1: Bundle v3.1.0-rc2 passes validation on 5 bench devices.\n"
             "- AC2: Trust store updated and validated by security team.\n"
             "- AC3: No SIGNATURE_MISMATCH on re-run of 20-device campaign."
         )},
    ],
    "Infotainment UI freeze on startup": [
        {"heading": "Environment",
         "body": "HU SW: Harman HU v3.0.1 | OS: Android Automotive 12 | CPU: Qualcomm SA8155P | RAM: 8GB"},
        {"heading": "Steps to reproduce",
         "body": (
             "1. Cold start vehicle bench (battery disconnected 10 min).\n"
             "2. Ignition ON.\n"
             "3. Observe HU boot sequence on touchscreen.\n"
             "4. At ~T+8s, UI freezes. Touch input non-responsive. Audio plays but UI is stuck on splash screen."
         )},
        {"heading": "Actual behavior",
         "body": "SystemUI process (PID 1842) stops responding at T+8s. "
                 "ANR (Application Not Responding) dialog not shown. "
                 "logcat shows: SurfaceFlinger timeout waiting for vsync, "
                 "GPU hang detected, recovery in 12s."},
        {"heading": "Expected behavior",
         "body": "Full UI interactive within 6s of ignition ON (per Stellantis HMI spec v2.1 §4.2)."},
        {"heading": "Acceptance criteria",
         "body": (
             "- AC1: UI interactive in < 6s on 20 consecutive cold starts.\n"
             "- AC2: No ANR in logcat during boot sequence.\n"
             "- AC3: GPU hang counter = 0 after fix."
         )},
    ],
    "GPS synchronization delay": [
        {"heading": "Environment",
         "body": "Positioning module: Marelli GPS v2.1 | Protocol: NMEA 0183 / UBX | Antenna: active, 28dB gain"},
        {"heading": "Steps to reproduce",
         "body": (
             "1. Cold start GPS module (power off > 1 hour).\n"
             "2. Position vehicle outdoors, clear sky view.\n"
             "3. Measure TTFF (Time To First Fix) with GPS analysis tool.\n"
             "4. Repeat 10 times. Average TTFF observed: 94 seconds."
         )},
        {"heading": "Actual behavior",
         "body": "TTFF = 94s average (max 147s). Almanac data not retained after power cycle. "
                 "GNSS chipset log: AssistNow data expired (age > 72h), full cold acquisition required."},
        {"heading": "Expected behavior",
         "body": "TTFF ≤ 30s cold start, ≤ 5s warm start (Stellantis GPS spec §3.1)."},
        {"heading": "Acceptance criteria",
         "body": (
             "- AC1: Cold TTFF ≤ 30s on 90% of measurements (10-sample test).\n"
             "- AC2: AssistNow data retained across power cycles (NVM storage).\n"
             "- AC3: Warm start TTFF ≤ 5s."
         )},
    ],
}

STORY_DESCRIPTIONS: Dict[str, List[Dict]] = {
    "Stabilize CAN bus communication layer": [
        {"heading": "User story",
         "body": "As a vehicle integration engineer, I want the CAN bus layer to be fully stable "
                 "across all ignition cycles so that diagnostic and infotainment features are not disrupted."},
        {"heading": "Background",
         "body": "The CAN communication layer (Marelli GW) handles HS-CAN and MS-CAN arbitration. "
                 "Intermittent bus-off events have been observed on CAN-HIL-03 during rapid ignition cycling."},
        {"heading": "Acceptance criteria",
         "body": (
             "- AC1: Bus recovers from bus-off within 50ms on HS-CAN and MS-CAN.\n"
             "- AC2: No frame loss > 10ms during 50 consecutive ignition cycles.\n"
             "- AC3: Error counter never exceeds threshold TH_ERR_PASSIVE (127) during normal operation.\n"
             "- AC4: Recovery logic validated on CAN-HIL-03, CAN-HIL-07, and CAN-HIL-11."
         )},
        {"heading": "Technical notes",
         "body": "Impacted ECUs: BCM, GW, TCU. CAN controller: NXP TJA1145. "
                 "ISO reference: ISO 11898-1 §6.3 (bus-off recovery). "
                 "Marelli ticket ref: MAR-CAN-2024-0089."},
    ],
    "Add OTA update feature": [
        {"heading": "User story",
         "body": "As a Stellantis OTA campaign manager, I want to push SW updates to vehicles "
                 "over-the-air so that field defects can be fixed without physical recall."},
        {"heading": "Background",
         "body": "OTA delivery uses Harman OTA Server v4.x. Target ECUs: HU, TCU, BCM. "
                 "Update packages are ZIP bundles signed with RSA-2048, validated against UNECE R156."},
        {"heading": "Acceptance criteria",
         "body": (
             "- AC1: Full update cycle (download → validate → install → reboot → verify) < 8 minutes.\n"
             "- AC2: Rollback triggered automatically on validation failure (error codes 0xE1–0xE9).\n"
             "- AC3: Campaign status updated in OTA portal within 60s of completion.\n"
             "- AC4: SW version bump confirmed via UDS 0x22 F189 post-update."
         )},
        {"heading": "Dependencies",
         "body": "Requires: Implement update package validation (SCRUM-linked). "
                 "Blocked by: Trust store provisioning (Security team)."},
    ],
    "Implement vehicle diagnostic system": [
        {"heading": "User story",
         "body": "As a bench test engineer, I want a unified diagnostic API so that I can query "
                 "ECU health, DTCs, and sensor states from a single endpoint."},
        {"heading": "Acceptance criteria",
         "body": (
             "- AC1: API returns ECU health status within 200ms of request.\n"
             "- AC2: All SAE J1979 Mode 03 DTCs retrievable via GET /diagnostics/dtc/{ecu_id}.\n"
             "- AC3: Sensor state polling interval configurable (100ms–5000ms).\n"
             "- AC4: API documented in OpenAPI 3.0 format."
         )},
        {"heading": "Technical notes",
         "body": "Protocol: UDS over DoIP (ISO 13400). ECU list: BCM (0x10), GW (0x20), HU (0x30), TCU (0x40). "
                 "Marelli diagnostic module version: DiagCore v3.2."},
    ],
}

def get_technical_description(summary: str, issue_type: str) -> Optional[Dict]:
    if issue_type == "Bug":
        for key, sections in BUG_DESCRIPTIONS.items():
            if key.lower() in summary.lower() or summary.lower() in key.lower():
                return adf_rich(sections)
    if issue_type == "Story":
        for key, sections in STORY_DESCRIPTIONS.items():
            if key.lower() in summary.lower() or summary.lower() in key.lower():
                return adf_rich(sections)
    return None

def generic_bug_description(summary: str, component: str) -> Dict:
    return adf_rich([
        {"heading": "Environment",
         "body": f"Component: {component} | Bench: INT-BENCH-{random.randint(1,5):02d} | "
                 f"SW version: v{random.randint(1,4)}.{random.randint(0,9)}.{random.randint(0,9)}"},
        {"heading": "Steps to reproduce",
         "body": f"1. Initialize {component} subsystem.\n"
                 f"2. Trigger nominal operation sequence.\n"
                 f"3. Observe: {summary.lower()} occurs after 2–3 cycles."},
        {"heading": "Actual behavior",
         "body": f"Observed issue: {summary}. "
                 f"Error code: 0x{random.randint(0xA0, 0xFF):02X}{random.randint(0, 0xFF):02X}. "
                 f"Logged in ECU fault memory."},
        {"heading": "Expected behavior",
         "body": f"The {component} subsystem must operate within specification on all test cycles."},
        {"heading": "Acceptance criteria",
         "body": f"- AC1: Issue does not reproduce on 20 consecutive cycles.\n"
                 f"- AC2: No related DTC stored after fix.\n"
                 f"- AC3: Regression test passes on 2 benches."},
    ])

def generic_story_description(summary: str, component: str) -> Dict:
    return adf_rich([
        {"heading": "User story",
         "body": f"As an integration engineer, I want to {summary.lower()} "
                 f"so that the {component} subsystem meets Stellantis quality gates."},
        {"heading": "Acceptance criteria",
         "body": f"- AC1: Feature validated on integration bench.\n"
                 f"- AC2: Unit tests coverage ≥ 80%.\n"
                 f"- AC3: Peer review approved by tech lead."},
        {"heading": "Technical notes",
         "body": f"Component: {component} | Supplier: {'Harman' if 'info' in component or 'ota' in component else 'Marelli'} | "
                 f"Estimate: {random.choice([3, 5, 8, 13])} SP"},
    ])


# ──────────────────────────────────────────────
#  2. Versions / releases
# ──────────────────────────────────────────────
VERSIONS = [
    {"name": "v1.0.0 - Initial Integration",  "description": "First integrated build for bench validation.", "releaseDate": "2026-04-30"},
    {"name": "v1.1.0 - CAN & Diagnostics Fix", "description": "CAN stability and diagnostics corrections.",   "releaseDate": "2026-05-31"},
    {"name": "v1.2.0 - OTA & Infotainment",    "description": "OTA delivery and infotainment improvements.",  "releaseDate": "2026-06-30"},
    {"name": "v2.0.0 - Safety & AUTOSAR",       "description": "Safety layer and AUTOSAR compliance release.", "releaseDate": "2026-09-30"},
]

def assign_version(issue_type: str, labels: List[str]) -> Optional[str]:
    if issue_type == "Bug":
        if any(l in labels for l in ["canbus", "diagnostics", "marelli"]):
            return "v1.1.0 - CAN & Diagnostics Fix"
        if any(l in labels for l in ["ota", "infotainment", "harman"]):
            return "v1.2.0 - OTA & Infotainment"
        return "v1.0.0 - Initial Integration"
    if issue_type in ("Story", "Task"):
        return random.choice(["v1.1.0 - CAN & Diagnostics Fix", "v1.2.0 - OTA & Infotainment"])
    return None


# ──────────────────────────────────────────────
#  3. Assignees
# ──────────────────────────────────────────────
def choose_assignee(labels: List[str], issue_type: str) -> str:
    if any(l in labels for l in ["harman", "infotainment", "ota"]):
        return ACCOUNT_HARMAN
    if any(l in labels for l in ["marelli", "canbus", "diagnostics", "ecu"]):
        return ACCOUNT_MARELLI
    return ACCOUNT_CAPGEMINI


# ──────────────────────────────────────────────
#  5. Commentaires multi-tours réalistes
# ──────────────────────────────────────────────
COMMENT_THREADS: Dict[str, List[str]] = {
    "bug": [
        (
            "jean.dupont (Capgemini) — Investigation started. "
            "Reproduced on INT-BENCH-03 after 3 ignition cycles. "
            "Capturing CAN traces now. Suspect Marelli GW watchdog timer misconfiguration."
        ),
        (
            "ali.chen (Harman) — Confirmed: HU side shows no frame reception error. "
            "Issue is upstream of HU CAN transceiver. "
            "Sharing CAN trace from HIL session: can_trace_20260411.blf. "
            "Marelli to check GW bus-off recovery logic."
        ),
        (
            "sofia.rossi (Marelli) — Root cause identified: GW firmware v2.4.1 has incorrect "
            "bus-off recovery timeout (configured: 1000ms, spec: 50ms). "
            "Fix committed in branch fix/GW-BUS-OFF-RECOVERY. "
            "ETA for patch: 2 days. Will notify once build is available for validation."
        ),
        (
            "jean.dupont (Capgemini) — Patch v2.4.2-rc1 received and deployed on INT-BENCH-03. "
            "Running 50-cycle regression test. Preliminary results: no frame loss observed. "
            "Full report by EOD tomorrow."
        ),
    ],
    "ota_bug": [
        (
            "ali.chen (Harman) — Bundle v3.1.0-rc2 fails validation with 0xE4 SIGNATURE_MISMATCH. "
            "Checked signing process — cert chain looks correct. "
            "Suspecting device trust store is missing intermediate CA. Investigating."
        ),
        (
            "jean.dupont (Capgemini) — Confirmed: device trust store provisioned with root CA only. "
            "Intermediate CA (Harman_OTA_IntCA_2026) not included. "
            "Need Harman to provide updated trust store package for all bench devices."
        ),
        (
            "ali.chen (Harman) — Updated trust store package attached: truststore_v2_bench_20260412.zip. "
            "Includes root CA + Harman_OTA_IntCA_2026. "
            "Please deploy on all BENCH-GROUP-A devices and re-run validation."
        ),
        (
            "jean.dupont (Capgemini) — Trust store deployed on 5/5 bench devices. "
            "Re-ran OTA campaign. Bundle v3.1.0-rc2 now PASSES validation on all devices. "
            "Closing issue pending PM confirmation."
        ),
    ],
    "infotainment_bug": [
        (
            "jean.dupont (Capgemini) — Reproduced UI freeze on cold start. "
            "logcat extracted: SurfaceFlinger timeout at T+8s, GPU hang. "
            "Sharing full log: logcat_cold_start_20260410.zip."
        ),
        (
            "ali.chen (Harman) — Analyzed logcat. GPU hang caused by resource contention "
            "between MediaService and NavigationApp during boot. "
            "Fix: delay MediaService init by 3s. Branch: fix/HU-BOOT-SEQUENCE. Build in 48h."
        ),
        (
            "jean.dupont (Capgemini) — Build 3.0.2-rc1 received. "
            "Testing on 5 cold starts. UI now interactive at T+4.8s average. "
            "Spec requirement: ≤ 6s. PASS. Running 20-cycle soak test to confirm."
        ),
    ],
    "story": [
        (
            "jean.dupont (Capgemini) — Story kickoff: technical review done. "
            "Splitting into 3 sub-tasks. Assigning CAN layer analysis to Marelli team."
        ),
        (
            "sofia.rossi (Marelli) — Sub-task 1 complete: CAN transceiver analysis done. "
            "Report shared in Confluence: CAN-ANALYSIS-2026-03. "
            "Proceeding to sub-task 2: recovery path validation."
        ),
        (
            "jean.dupont (Capgemini) — Code review passed. "
            "All 3 acceptance criteria met on INT-BENCH-03. "
            "Moving to In Review for PM sign-off."
        ),
    ],
    "task": [
        (
            "jean.dupont (Capgemini) — Analysis started. "
            "Reviewing logs and existing documentation from Marelli."
        ),
        (
            "sofia.rossi (Marelli) — Technical documentation provided: "
            "GW_Interface_Spec_v2.3.pdf shared on Confluence. "
            "Key points summarized in ticket description."
        ),
    ],
    "default": [
        (
            "jean.dupont (Capgemini) — Ticket reviewed. "
            "Initial investigation in progress. Will update by EOD."
        ),
        (
            "jean.dupont (Capgemini) — Update: analysis complete. "
            "Technical details added to description. Assigned to relevant team."
        ),
    ],
}

def choose_comment_thread(summary: str, issue_type: str, labels: List[str]) -> List[str]:
    s = summary.lower()
    if issue_type == "Bug":
        if "can" in s or "bus" in s or "ecu" in s:
            return COMMENT_THREADS["bug"]
        if "ota" in s or "update" in s or "validation" in s or "signature" in s:
            return COMMENT_THREADS["ota_bug"]
        if "infotainment" in s or "ui" in s or "freeze" in s or "startup" in s:
            return COMMENT_THREADS["infotainment_bug"]
        return COMMENT_THREADS["bug"]
    if issue_type == "Story":
        return COMMENT_THREADS["story"]
    if issue_type == "Task":
        return COMMENT_THREADS["task"]
    return COMMENT_THREADS["default"]


# ──────────────────────────────────────────────
#  7. Time tracking
# ──────────────────────────────────────────────
TIME_BY_TYPE = {
    "Epic":    ("2w", "1w"),
    "Story":   ("3d", "1d"),
    "Task":    ("1d", "4h"),
    "Bug":     ("2d", "6h"),
    "Sub-task":("4h", "2h"),
}

def get_time_estimate(issue_type: str) -> tuple[str, str]:
    return TIME_BY_TYPE.get(issue_type, ("1d", "4h"))


# ──────────────────────────────────────────────
#  8. Custom fields via labels enrichis
# ──────────────────────────────────────────────
ECU_IDS      = ["BCM_0x10", "GW_0x20", "HU_0x30", "TCU_0x40", "ADAS_0x50"]
CAN_FRAMES   = ["0x7DF", "0x7E0", "0x7E8", "0x18DB33F1", "0x18DA10F1"]
SW_VERSIONS  = ["SW_v1.0.1", "SW_v2.4.1", "SW_v3.0.1", "SW_v3.1.0-rc2"]
BENCH_IDS    = ["BENCH_HIL01", "BENCH_HIL03", "BENCH_HIL07", "BENCH_INT02", "BENCH_INT05"]
SEVERITY     = ["SEV1_critical", "SEV2_major", "SEV3_minor", "SEV4_cosmetic"]

def enrich_labels(existing: List[str], issue_type: str, summary: str) -> List[str]:
    labels = set(existing)
    labels.add(random.choice(ECU_IDS))
    if issue_type == "Bug":
        labels.add(random.choice(CAN_FRAMES))
        labels.add(random.choice(SW_VERSIONS))
        labels.add(random.choice(SEVERITY))
    labels.add(random.choice(BENCH_IDS))
    labels.add("chatbot-seed")
    # Normalize: Jira labels cannot have spaces
    return sorted(l.replace(" ", "_") for l in labels)


# ──────────────────────────────────────────────
#  6. Nouveaux epics + stories/bugs/tasks
# ──────────────────────────────────────────────
NEW_EPIC_SPECS = [
    {
        "summary": "Safety & Functional Safety (AUTOSAR)",
        "component": "safety",
        "supplier": "marelli",
        "domain": "safety",
        "stories": [
            "Implement AUTOSAR OS watchdog integration",
            "Add E2E protection for critical CAN signals",
            "Validate ISO 26262 ASIL-B requirements for BCM",
            "Implement diagnostic fault memory (AUTOSAR DEM)",
            "Add safety mode transition logic for powertrain",
            "Validate memory protection unit (MPU) configuration",
        ],
        "tasks": [
            "Review AUTOSAR BSW configuration for safety partitions",
            "Document ASIL decomposition for BCM module",
            "Analyze E2E library integration with Marelli GW",
            "Verify OS stack usage under safety load",
            "Audit DTC mapping against FMEA table",
        ],
        "bugs": [
            "Watchdog not triggered on task overrun in safety partition",
            "E2E CRC mismatch on signal PDU_Safety_01 under EMC load",
            "DEM fault confirmation delay exceeds ISO 26262 requirement",
            "MPU violation detected during BCM initialization",
            "Safety mode not entered after consecutive CRC errors",
            "AUTOSAR OS task deadline miss not logged in fault memory",
        ],
    },
    {
        "summary": "Power Management & Sleep Modes",
        "component": "power",
        "supplier": "marelli",
        "domain": "hardware",
        "stories": [
            "Implement coordinated sleep mode for all ECUs",
            "Add low-power CAN wake-up frame handling",
            "Validate quiescent current < 1mA in deep sleep",
            "Implement power state machine (PSM) for vehicle modes",
            "Add battery monitoring and undervoltage protection",
            "Validate wake-up latency from deep sleep",
        ],
        "tasks": [
            "Measure current consumption per ECU in sleep mode",
            "Document power state transitions for HIL bench",
            "Analyze wake-up frame latency on HS-CAN",
            "Review battery discharge curve under bench load",
            "Inspect PSM state machine for race conditions",
        ],
        "bugs": [
            "ECU fails to enter deep sleep after ignition OFF",
            "Quiescent current exceeds 5mA after 10 minutes",
            "Wake-up frame on MS-CAN not detected by GW",
            "Power state machine stuck in STANDBY after undervoltage",
            "Battery voltage reading offset by +200mV in cold conditions",
            "Sleep mode re-entry blocked by HU audio process not terminating",
        ],
    },
]

def build_new_epic(jira: JiraClient, spec: Dict, version_ids: Dict[str, str]) -> Dict:
    """Create one new epic with stories, tasks, bugs, subtasks."""
    # Detect issue type names
    epic_type  = next((v["name"] for v in jira.issue_types.values() if v["name"].lower() == "epic"),  "Story")
    story_type = next((v["name"] for v in jira.issue_types.values() if v["name"].lower() == "story"), "Story")
    task_type  = next((v["name"] for v in jira.issue_types.values() if v["name"].lower() == "task"),  "Task")
    bug_type   = next((v["name"] for v in jira.issue_types.values() if v["name"].lower() == "bug"),   "Bug")
    subtask_type = next((v["name"] for v in jira.issue_types.values() if v.get("subtask") is True), task_type)

    component  = spec["component"]
    supplier   = spec["supplier"]
    assignee   = ACCOUNT_MARELLI if supplier == "marelli" else ACCOUNT_HARMAN

    base_labels = ["stellantis", "capgemini", "automotive", supplier, component, "chatbot-seed"]

    # Create epic
    epic_fields: Dict[str, Any] = {
        "project":   {"key": JIRA_PROJECT_KEY},
        "summary":   spec["summary"],
        "issuetype": {"name": epic_type},
        "priority":  {"name": "High"},
        "assignee":  {"id": assignee},
        "labels":    base_labels + ["portfolio", "parent"],
        "description": adf_rich([
            {"heading": "Epic overview",
             "body": f"Domain: {spec['domain']} | Component: {spec['component']} | Supplier: {spec['supplier'].title()}"},
            {"heading": "Goal",
             "body": f"Deliver and validate all {spec['component']} features for Stellantis integration milestone."},
            {"heading": "Success criteria",
             "body": "All stories accepted. No open Severity-1 or Severity-2 bugs. Integration bench sign-off obtained."},
        ]),
    }
    if jira.epic_name_field_id:
        epic_fields[jira.epic_name_field_id] = spec["summary"][:255]

    epic = jira.create_issue(epic_fields)
    epic_key = epic.get("key", "")
    logger.info("Created Epic %s: %s", epic_key, spec["summary"])

    created_issues: Dict[str, List[str]] = {"stories": [], "tasks": [], "bugs": []}

    # Stories
    for title in spec["stories"]:
        lbls = enrich_labels(base_labels + ["story", "feature"], "Story", title)
        f: Dict[str, Any] = {
            "project":   {"key": JIRA_PROJECT_KEY},
            "summary":   title,
            "issuetype": {"name": story_type},
            "priority":  {"name": random.choice(["High", "Medium"])},
            "assignee":  {"id": assignee},
            "labels":    lbls,
            "description": generic_story_description(title, component),
        }
        if jira.epic_link_field_id:
            f[jira.epic_link_field_id] = epic_key
        else:
            f["parent"] = {"key": epic_key}
        vid = version_ids.get("v1.2.0 - OTA & Infotainment") or version_ids.get(list(version_ids.keys())[0] if version_ids else "")
        if vid:
            f["fixVersions"] = [{"id": vid}]
        if jira.story_points_field_id:
            f[jira.story_points_field_id] = random.choice([3, 5, 8])
        iss = jira.create_issue(f)
        iss_key = iss.get("key", "")
        created_issues["stories"].append(iss_key)
        # 2 comments per story
        for c in choose_comment_thread(title, "Story", lbls)[:2]:
            jira.add_comment(iss_key, adf_text(c))
        # 2 subtasks
        for i in range(2):
            st_title = f"{title} — subtask {i+1}"
            st_f: Dict[str, Any] = {
                "project":   {"key": JIRA_PROJECT_KEY},
                "summary":   st_title,
                "issuetype": {"name": subtask_type},
                "priority":  {"name": "Medium"},
                "assignee":  {"id": assignee},
                "labels":    enrich_labels(base_labels + ["sub-task"], "Sub-task", st_title),
                "parent":    {"key": iss_key},
                "description": adf_text(f"Sub-task for: {title}. Scope: analysis and implementation."),
            }
            jira.create_issue(st_f)

    # Tasks
    for title in spec["tasks"]:
        lbls = enrich_labels(base_labels + ["task", "technical"], "Task", title)
        f = {
            "project":   {"key": JIRA_PROJECT_KEY},
            "summary":   title,
            "issuetype": {"name": task_type},
            "priority":  {"name": random.choice(["High", "Medium", "Low"])},
            "assignee":  {"id": assignee},
            "labels":    lbls,
            "description": adf_rich([
                {"heading": "Objective", "body": f"Technical task: {title}"},
                {"heading": "Deliverable", "body": "Analysis report or configuration validated on bench."},
            ]),
        }
        if jira.epic_link_field_id:
            f[jira.epic_link_field_id] = epic_key
        else:
            f["parent"] = {"key": epic_key}
        iss = jira.create_issue(f)
        iss_key = iss.get("key", "")
        created_issues["tasks"].append(iss_key)
        for c in choose_comment_thread(title, "Task", lbls)[:2]:
            jira.add_comment(iss_key, adf_text(c))

    # Bugs
    for title in spec["bugs"]:
        lbls = enrich_labels(base_labels + ["bug", "defect"], "Bug", title)
        prio = random.choices(["Highest", "High", "Medium"], weights=[3, 5, 2])[0]
        vid = version_ids.get("v1.1.0 - CAN & Diagnostics Fix") or ""
        f = {
            "project":   {"key": JIRA_PROJECT_KEY},
            "summary":   title,
            "issuetype": {"name": bug_type},
            "priority":  {"name": prio},
            "assignee":  {"id": assignee},
            "labels":    lbls,
            "description": generic_bug_description(title, component),
        }
        if vid:
            f["fixVersions"] = [{"id": vid}]
        if jira.epic_link_field_id:
            f[jira.epic_link_field_id] = epic_key
        else:
            f["parent"] = {"key": epic_key}
        iss = jira.create_issue(f)
        iss_key = iss.get("key", "")
        created_issues["bugs"].append(iss_key)
        for c in choose_comment_thread(title, "Bug", lbls)[:3]:
            jira.add_comment(iss_key, adf_text(c))

    return {"epic_key": epic_key, **created_issues}


# ──────────────────────────────────────────────
#  4. Dépendances complexes cross-epic
# ──────────────────────────────────────────────
def create_complex_dependencies(jira: JiraClient, all_issues: List[Dict], new_epic_keys: List[Dict]) -> None:
    """
    Builds a realistic dependency network:
    - Safety bugs block CAN stories
    - Power bugs block OTA stories
    - Cross-epic: Safety epic stories relate to Diagnostics stories
    - Chain: Bug → blocks → Story → blocks → Epic milestone
    """
    bugs   = [i for i in all_issues if i["fields"]["issuetype"]["name"] == "Bug"]
    stories = [i for i in all_issues if i["fields"]["issuetype"]["name"] == "Story"]
    tasks  = [i for i in all_issues if i["fields"]["issuetype"]["name"] == "Task"]

    if len(bugs) < 4 or len(stories) < 4:
        logger.warning("Not enough issues for complex dependency network")
        return

    # Chain 1: Bug → blocks → Story → blocks → another Story (3-level chain)
    jira.link_issues(bugs[0]["key"], stories[0]["key"], "blocks")
    jira.link_issues(stories[0]["key"], stories[1]["key"], "blocks")
    logger.info("Chain 1: %s blocks %s blocks %s", bugs[0]["key"], stories[0]["key"], stories[1]["key"])

    # Chain 2: Bug → blocks → Task → relates → Story (cross-type chain)
    if len(tasks) >= 2:
        jira.link_issues(bugs[1]["key"], tasks[0]["key"], "blocks")
        jira.link_issues(tasks[0]["key"], stories[2]["key"], "relates")
        logger.info("Chain 2: %s blocks %s relates %s", bugs[1]["key"], tasks[0]["key"], stories[2]["key"])

    # Chain 3: 4-level deep (Bug → Task → Story → Story)
    if len(bugs) >= 4 and len(stories) >= 5:
        jira.link_issues(bugs[2]["key"], tasks[1]["key"] if len(tasks) > 1 else bugs[3]["key"], "blocks")
        jira.link_issues(tasks[1]["key"] if len(tasks) > 1 else bugs[3]["key"], stories[3]["key"], "blocks")
        jira.link_issues(stories[3]["key"], stories[4]["key"], "blocks")
        logger.info("Chain 3 (4-level deep) created")

    # Cross-epic links: new Safety epic bugs relate to existing CAN stories
    if new_epic_keys:
        for new_ep in new_epic_keys:
            new_bugs = new_ep.get("bugs", [])
            new_stories = new_ep.get("stories", [])
            if new_bugs and stories:
                jira.link_issues(new_bugs[0], stories[0]["key"], "relates")
            if new_stories and stories:
                jira.link_issues(new_stories[0], stories[1]["key"], "relates")

    # Some bugs relate to each other (duplicate-suspect pattern)
    jira.link_issues(bugs[0]["key"], bugs[1]["key"], "relates")
    if len(bugs) >= 5:
        jira.link_issues(bugs[3]["key"], bugs[4]["key"], "relates")


# ──────────────────────────────────────────────
#  Main enrichment loop
# ──────────────────────────────────────────────
def enrich_existing_issues(jira: JiraClient, version_ids: Dict[str, str]) -> None:
    """Apply improvements 1–3 + 5 + 7 + 8 to all existing issues."""
    jql = f"project = {JIRA_PROJECT_KEY} ORDER BY created ASC"
    issues = jira.search(jql, max_results=300,
                         fields=["summary", "issuetype", "labels", "description",
                                 "assignee", "priority", "status"])
    logger.info("Found %d existing issues to enrich", len(issues))

    for iss in issues:
        key        = iss["key"]
        f          = iss["fields"]
        summary    = f.get("summary", "")
        itype      = f.get("issuetype", {}).get("name", "Task")
        labels     = f.get("labels", [])
        current_desc = f.get("description")

        updates: Dict[str, Any] = {}

        # ── 1. Description technique ──────────
        if not current_desc or current_desc == {"type": "doc", "version": 1, "content": []}:
            rich_desc = get_technical_description(summary, itype)
            if rich_desc:
                updates["description"] = rich_desc
            elif itype == "Bug":
                comp = next((l for l in labels if l in ["canbus","infotainment","ota","diagnostics","safety","power"]), "vehicle")
                updates["description"] = generic_bug_description(summary, comp)
            elif itype == "Story":
                comp = next((l for l in labels if l in ["canbus","infotainment","ota","diagnostics","safety","power"]), "vehicle")
                updates["description"] = generic_story_description(summary, comp)

        # ── 2. Fix version ────────────────────
        version_name = assign_version(itype, labels)
        if version_name and version_name in version_ids:
            updates["fixVersions"] = [{"id": version_ids[version_name]}]

        # ── 3. Assignee ───────────────────────
        updates["assignee"] = {"id": choose_assignee(labels, itype)}

        # ── 8. Labels enrichis ────────────────
        new_labels = enrich_labels(labels, itype, summary)
        updates["labels"] = new_labels

        # ── Story points (if missing) ──────────
        if itype in ("Story", "Task") and jira.story_points_field_id:
            updates[jira.story_points_field_id] = random.choice([1, 2, 3, 5, 8])

        # Apply all field updates
        if updates:
            try:
                jira.update_issue(key, updates)
                logger.info("Enriched %s (%s): %s", key, itype, list(updates.keys()))
            except JiraError as e:
                logger.warning("Could not update %s: %s", key, e)

        # ── 5. Commentaires multi-tours ───────
        thread = choose_comment_thread(summary, itype, labels)
        n_comments = 4 if itype == "Bug" else 2
        for comment in thread[:n_comments]:
            try:
                jira.add_comment(key, adf_text(comment))
            except JiraError as e:
                logger.warning("Comment failed on %s: %s", key, e)

        # ── 7. Time tracking ──────────────────
        original, spent = get_time_estimate(itype)
        jira.update_original_estimate(key, original)
        if f.get("status", {}).get("name", "") in ("In Progress", "In Review", "Done", "Blocked"):
            jira.add_worklog(key, spent, original)


# ──────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────
def main() -> int:
    jira = JiraClient()
    jira.bootstrap()

    # ── Step A: Create fix versions ───────────
    logger.info("=== Step A: Creating fix versions ===")
    version_ids: Dict[str, str] = {}
    for v in VERSIONS:
        try:
            vid = jira.get_or_create_version(v["name"], v["description"], v["releaseDate"])
            version_ids[v["name"]] = vid
        except JiraError as e:
            logger.warning("Version creation failed for %s: %s", v["name"], e)

    # ── Step B: Enrich existing issues (1–3, 5, 7, 8) ──
    logger.info("=== Step B: Enriching existing issues ===")
    enrich_existing_issues(jira, version_ids)

    # ── Step C: Create new epics (6) ──────────
    logger.info("=== Step C: Creating new epics (Safety + Power) ===")
    new_epic_results = []
    for spec in NEW_EPIC_SPECS:
        try:
            result = build_new_epic(jira, spec, version_ids)
            new_epic_results.append(result)
            logger.info("New epic created: %s with %d stories, %d bugs",
                        result["epic_key"],
                        len(result.get("stories", [])),
                        len(result.get("bugs", [])))
        except JiraError as e:
            logger.error("Failed to create epic %s: %s", spec["summary"], e)

    # ── Step D: Complex dependencies (4) ──────
    logger.info("=== Step D: Creating complex dependency network ===")
    all_issues = jira.search(
        f"project = {JIRA_PROJECT_KEY} ORDER BY created ASC",
        max_results=300,
        fields=["summary", "issuetype", "labels"],
    )
    create_complex_dependencies(jira, all_issues, new_epic_results)

    # ── Summary ────────────────────────────────
    print("\n" + "="*55)
    print("  ENRICHMENT COMPLETE")
    print("="*55)
    print(f"  Fix versions created : {len(version_ids)}")
    print(f"  Existing issues enriched (1–3, 5, 7, 8)")
    print(f"  New epics created    : {len(new_epic_results)}")
    for r in new_epic_results:
        print(f"    - {r['epic_key']}: {len(r.get('stories',[]))} stories, "
              f"{len(r.get('tasks',[]))} tasks, {len(r.get('bugs',[]))} bugs")
    print(f"  Complex dep. network : created")
    print("="*55)
    print("\nSuggested JQL for chatbot testing:")
    tests = [
        f'project = {JIRA_PROJECT_KEY} AND issuetype = Bug AND priority = Highest',
        f'project = {JIRA_PROJECT_KEY} AND labels = SEV1_critical',
        f'project = {JIRA_PROJECT_KEY} AND labels = safety AND issuetype = Bug',
        f'project = {JIRA_PROJECT_KEY} AND fixVersion = "v1.1.0 - CAN & Diagnostics Fix"',
        f'project = {JIRA_PROJECT_KEY} AND labels = BENCH_HIL03',
        f'project = {JIRA_PROJECT_KEY} AND issuetype in (Bug, Story) AND status = Blocked',
        f'project = {JIRA_PROJECT_KEY} AND text ~ "acceptance criteria"',
        f'project = {JIRA_PROJECT_KEY} AND text ~ "AUTOSAR"',
        f'project = {JIRA_PROJECT_KEY} AND labels = power AND issuetype = Bug',
    ]
    for jql in tests:
        print(f"  {jql}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
        raise SystemExit(130)
    except Exception as exc:
        logger.exception("Fatal error: %s", exc)
        raise SystemExit(1)