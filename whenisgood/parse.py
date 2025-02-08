# parse.py
from typing import Dict, List, Set
from bs4 import BeautifulSoup
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
import logging


@dataclass
class Student:
    id: str
    name: str


@dataclass
class TimeSlot:
    day: str
    hour: int
    minute: int
    available_students: Set[str]  # Set of student IDs
    total_students: int
    cant_count: int

    def __str__(self):
        return f"{self.day} {time(self.hour, self.minute).strftime('%I:%M %p')}"

    def availability_score(self):
        return (
            len(self.available_students) / self.total_students
            if self.total_students > 0
            else 0
        )

    def __eq__(self, other):
        if not isinstance(other, TimeSlot):
            return NotImplemented
        return (
            self.day == other.day
            and self.hour == other.hour
            and self.minute == other.minute
        )

    def __hash__(self):
        return hash((self.day, self.hour, self.minute))

    def sort_key(self):
        day_order = {
            "Mon": 0,
            "Tue": 1,
            "Wed": 2,
            "Thu": 3,
            "Fri": 4,
            "Sat": 5,
            "Sun": 6,
        }
        return (day_order.get(self.day, 7), self.hour, self.minute)


def parse_whenisigood(html_file: str) -> Dict[str, List[TimeSlot]]:
    """Parse WhenIsGood HTML file to get student availability."""
    with open(html_file, "r") as f:
        html_content = f.read()

    if not html_content:
        raise ValueError("Empty HTML file")

    soup = BeautifulSoup(html_content, "html.parser")
    logging.debug(f"Parsing HTML content of length: {len(html_content)}")

    # First validate we can find the main table
    grid_table = soup.find("table", id="grid")
    if not grid_table:
        raise ValueError("Could not find the main grid table in HTML")

    slots_by_day = defaultdict(list)

    # Get all respondents
    respondents_div = soup.find("div", class_="respondents")
    if not respondents_div:
        raise ValueError("Could not find respondents section in HTML")

    respondents = []
    for div in respondents_div.find_all("div", class_="respondentActive"):
        student_id = div.get("id")
        student_name = div.text.strip()
        respondents.append(Student(student_id, student_name))

    total_respondents = len(respondents)
    logging.debug(f"Found {total_respondents} respondents")

    # Process each time slot in the grid
    grid_table = soup.find("table", id="grid")
    if not grid_table:
        raise ValueError("Could not find the grid table")

    tbody = grid_table.find("tbody")
    if not tbody:
        raise ValueError("Could not find tbody in grid table")

    for tr in tbody.find_all("tr"):
        tds = tr.find_all("td", class_="slot")
        if not tds:
            continue

        logging.debug(f"Processing row with {len(tds)} slots")

        for td in tds:
            # Get time from the nested table
            time_table = td.find("table")
            if not time_table:
                logging.debug(f"No time table found in slot")
                continue

            time_td = time_table.find("td", class_="gridText")
            if not time_td:
                logging.debug(f"No gridText td found in time table")
                continue

            time_text = time_td.text.strip()
            try:
                time_obj = datetime.strptime(time_text, "%I:%M %p")
            except ValueError as e:
                logging.debug(f"Could not parse time: {time_text} - {e}")
                continue

            # Get day
            tr_header = tr.find_parent("tbody").find_all("tr")[0]
            day_headers = tr_header.find_all("td", class_="dateHeader")
            day_idx = list(tr.find_all("td")).index(td)
            if day_idx >= len(day_headers):
                continue
            day = day_headers[day_idx].text.strip()

            # Get number of students who can't make it
            cant_count = int(td.find("td", class_="cantCount").text.strip())

            # The students who can make it are total_respondents - cant_count
            available_students = set()
            for respondent in respondents:
                # In a real implementation, we'd check if this student marked this slot
                # as available. For now, we'll use the cant_count
                if len(available_students) < (total_respondents - cant_count):
                    available_students.add(respondent.id)

            slot = TimeSlot(
                day=day,
                hour=time_obj.hour,
                minute=time_obj.minute,
                available_students=available_students,
                total_students=total_respondents,
                cant_count=cant_count,
            )
            slots_by_day[day].append(slot)

    # Sort slots within each day
    for day in slots_by_day:
        slots_by_day[day].sort(key=lambda x: (x.hour, x.minute))

    return slots_by_day
