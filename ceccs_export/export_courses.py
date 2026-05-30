"""
Export all UofT courses from the TTB API into a CSV file.

Each row is one course offering (e.g. MAT135H1F), with:
  - Course code, title, full description
  - Faculty, department, credit weight
  - Breadth/distribution requirements, prerequisites, exclusions
  - Total enrollment, capacity, waitlist across all lecture sections
  - Instructor names
  - Delivery mode (in-person, online, hybrid, etc.)

Usage:
    python export_courses.py                         # auto-detects current session
    python export_courses.py --session 20265         # specific session
    python export_courses.py --all-divisions         # include ARTSC, APSC, UTSC, UTM, etc.
    python export_courses.py --session 20265 --all-divisions
"""

import argparse
import csv
import os
import re
import time
from datetime import date

import requests

TTB_API = "https://api.easi.utoronto.ca/ttb/getPageableCourses"
PAGE_SIZE = 20  # TTB API enforces a maximum of 20 per page

ALL_DIVISIONS = ["APSC", "ARCLA", "ARTSC", "ERIN", "MUSIC", "SCAR", "FPEH"]

COLUMNS = [
    "full_code",
    "course_code",
    "section_code",
    "title",
    "description",
    "level",
    "faculty_code",
    "faculty_name",
    "department_code",
    "department_name",
    "credit_weight",
    "breadth_requirements",
    "distribution_requirements",
    "prerequisites",
    "exclusions",
    "total_enrollment",
    "total_capacity",
    "total_waitlist",
    "instructors",
    "delivery_mode",
    "campus",
    "session",
]


def get_current_sessions() -> tuple[list[str], str]:
    """Return (sessions_list, session_folder_name) based on today's date.
    Mirrors the logic in main_weak.py from the data-for-enrol scraper.
    """
    dt = date.today()
    year = dt.year

    if date(year, 2, 17) <= dt <= date(year, 8, 20):
        ses = f"{year}5"
        return [ses, f"{ses}F", f"{ses}S"], ses

    if dt >= date(year, 6, 12):
        next_year = year + 1
        ses = f"{year}9"
        return [ses, f"{year}9F", f"{next_year}1", f"{ses}-{next_year}1"], ses

    last_year = year - 1
    ses = f"{last_year}9"
    return [ses, f"{ses}F", f"{year}1", f"{ses}-{year}1"], ses


def fetch_all_courses(sessions: list[str], divisions: list[str]) -> list[dict]:
    """Paginate through the TTB API and return every course offering."""
    payload = {
        "courseCodeAndTitleProps": {
            "courseCode": "",
            "courseTitle": "",
            "courseSectionCode": "",
            "searchCourseDescription": False,
        },
        "departmentProps": [],
        "campuses": [],
        "sessions": sessions,
        "requirementProps": [],
        "instructor": "",
        "courseLevels": [],
        "deliveryModes": [],
        "dayPreferences": [],
        "timePreferences": [],
        "divisions": divisions,
        "creditWeights": [],
        "page": 1,
        "pageSize": PAGE_SIZE,
        "direction": "asc",
    }

    all_courses: list[dict] = []
    page = 1

    while True:
        payload["page"] = page
        print(f"  Page {page} ...", end=" ", flush=True)

        resp = requests.post(TTB_API, json=payload, headers={"Accept": "application/json"}, timeout=30)
        resp.raise_for_status()

        data = resp.json()
        if data.get("payload") is None:
            print("no results.")
            break

        pageable = data["payload"]["pageableCourse"]
        courses = pageable.get("courses") or []
        total = pageable.get("total", 0)

        all_courses.extend(courses)
        print(f"{len(all_courses)}/{total}")

        if len(all_courses) >= total or not courses:
            break

        page += 1
        time.sleep(0.15)

    return all_courses


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"<[^>]+>", "", text).strip()


def extract_row(course: dict) -> dict:
    cm = course.get("cmCourseInfo") or {}
    faculty = course.get("faculty") or {}
    department = course.get("department") or {}
    sections = course.get("sections") or []

    lec_sections = [s for s in sections if s.get("teachMethod") == "LEC"]
    if not lec_sections:
        lec_sections = sections

    total_enrollment = sum(int(s.get("currentEnrolment") or 0) for s in lec_sections)
    total_capacity = sum(int(s.get("maxEnrolment") or 0) for s in lec_sections)
    total_waitlist = sum(int(s.get("currentWaitlist") or 0) for s in lec_sections)

    seen: set[str] = set()
    instructors: list[str] = []
    for s in lec_sections:
        for ins in s.get("instructors") or []:
            name = f"{(ins.get('firstName') or '').strip()} {(ins.get('lastName') or '').strip()}".strip()
            if name and name not in seen:
                seen.add(name)
                instructors.append(name)

    delivery = ""
    if lec_sections:
        modes = lec_sections[0].get("deliveryModes") or []
        if modes:
            delivery = modes[0].get("mode", "")

    session_tag = (course.get("sessions") or [""])[0]

    return {
        "full_code": (course.get("code", "") + course.get("sectionCode", "")),
        "course_code": course.get("code", ""),
        "section_code": course.get("sectionCode", ""),
        "title": course.get("name", ""),
        "description": cm.get("description", ""),
        "level": cm.get("levelOfInstruction", ""),
        "faculty_code": faculty.get("code", ""),
        "faculty_name": faculty.get("name", ""),
        "department_code": department.get("code", ""),
        "department_name": department.get("name", ""),
        "credit_weight": course.get("maxCredit", ""),
        "breadth_requirements": "; ".join(cm.get("breadthRequirements") or []),
        "distribution_requirements": "; ".join(cm.get("distributionRequirements") or []),
        "prerequisites": strip_html(cm.get("prerequisitesText")),
        "exclusions": strip_html(cm.get("exclusionsText")),
        "total_enrollment": total_enrollment,
        "total_capacity": total_capacity,
        "total_waitlist": total_waitlist,
        "instructors": "; ".join(instructors),
        "delivery_mode": delivery,
        "campus": course.get("campus", ""),
        "session": session_tag,
    }


def export_csv(rows: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} rows → {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export UofT TTB courses to CSV")
    parser.add_argument("--session", help="Session code, e.g. 20265. Auto-detected if omitted.")
    parser.add_argument(
        "--divisions",
        nargs="+",
        default=["ARTSC"],
        help="Divisions to query. Default: ARTSC only.",
    )
    parser.add_argument(
        "--all-divisions",
        action="store_true",
        help="Query all divisions: ARTSC, APSC, ARCLA, SCAR, ERIN, MUSIC, FPEH",
    )
    args = parser.parse_args()

    if args.session:
        session_name = args.session
        if session_name.endswith("5"):
            sessions = [session_name, f"{session_name}F", f"{session_name}S"]
        else:
            sessions = [session_name]
    else:
        sessions, session_name = get_current_sessions()

    divisions = ALL_DIVISIONS if args.all_divisions else args.divisions

    print(f"Session : {session_name}  →  querying as {sessions}")
    print(f"Divisions: {', '.join(divisions)}")
    print("Fetching from TTB API...")

    raw = fetch_all_courses(sessions, divisions)

    print(f"\nProcessing {len(raw)} course offerings...")
    rows = [extract_row(c) for c in raw]

    out_dir = os.path.join(os.path.dirname(__file__), "output")
    div_tag = "all" if args.all_divisions else "_".join(divisions)
    out_path = os.path.join(out_dir, f"courses_{session_name}_{div_tag}.csv")
    export_csv(rows, out_path)


if __name__ == "__main__":
    main()
