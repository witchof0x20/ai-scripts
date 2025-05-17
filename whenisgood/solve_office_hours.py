#!/usr/bin/env python3
"""
Office hours scheduler that optimizes coverage of student availability while respecting instructor constraints.
Supports guaranteed (fixed) office hours blocks and unavailable time blocks.
"""

import json
import tomllib
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Set, Tuple, DefaultDict

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


def load_data(respondents_file: str, instructors_file: str) -> Tuple[Dict, Dict]:
    """
    Load student availability data from JSON and instructor constraints from TOML.

    Args:
        respondents_file: Path to JSON file with student availability data
        instructors_file: Path to TOML file with instructor constraints

    Returns:
        Tuple of (respondents data dict, instructors data dict)
    """
    with open(respondents_file, "r") as f:
        respondents = json.load(f)
    with open(instructors_file, "rb") as f:
        instructors = tomllib.load(f)
    return respondents, instructors


def process_availabilities(
    respondents: Dict,
) -> Tuple[Dict[Tuple[str, int], List[str]], Dict[Tuple[str, int], int], int]:
    """
    Process raw respondent data into availability mappings.

    Args:
        respondents: Dict of student availability data

    Returns:
        Tuple of (
            availability by time slot mapping,
            student count by time slot mapping,
            total number of students
        )
    """
    availability_by_time: Dict[Tuple[str, int], List[str]] = {}
    student_counts: DefaultDict[Tuple[str, int], int] = defaultdict(int)
    time_students: DefaultDict[Tuple[str, int], Set[str]] = defaultdict(set)
    total_students = len(respondents)

    for student_id, student_data in respondents.items():
        for timestamp in student_data["myCanDos"]:
            dt = datetime.fromtimestamp(int(timestamp) / 1000)
            weekday = dt.strftime("%A")

            if weekday not in WEEKDAYS:
                continue

            hour = dt.hour
            time_key = (weekday, hour)
            time_students[time_key].add(student_id)
            student_counts[time_key] += 1

    for time_key, students in time_students.items():
        availability_by_time[time_key] = sorted(students)

    return availability_by_time, dict(student_counts), total_students


def get_instructor_constraints(instructors_data: Dict) -> Dict:
    """
    Process instructor constraints from TOML data.

    Args:
        instructors_data: Dict of instructor constraints from TOML

    Returns:
        Dict containing processed constraints including hours, unavailable times,
        and guaranteed slots
    """
    constraints = {
        "hours": {},
        "unavailable": defaultdict(set),
        "guaranteed": defaultdict(list),
    }

    # Process instructor hours and guaranteed times
    for instructor_key, instructor_data in instructors_data["instructors"].items():
        # Handle both flat and nested table formats
        if isinstance(instructor_data, dict):
            base_data = instructor_data
        else:
            base_data = instructors_data["instructors"][instructor_key]

        constraints["hours"][instructor_key] = {
            "start": base_data["start"],
            "end": base_data["end"],
            "max_hours": base_data["max_hours"],
            "max_length": base_data["max_length"],
        }

        # Process guaranteed hours if present
        if "guaranteed" in base_data:
            for slot in base_data["guaranteed"]:
                block = (slot["day"], slot["start"], slot["end"])
                constraints["guaranteed"][instructor_key].append(block)

    # Process unavailable times
    all_unavailable = instructors_data["unavailable"].get("all", [])
    for instructor in constraints["hours"]:
        instructor_unavailable = instructors_data["unavailable"].get(instructor, [])
        for time in all_unavailable + instructor_unavailable:
            for hour in range(time["start"], time["end"]):
                constraints["unavailable"][instructor].add((time["day"], hour))

    return constraints


def is_time_valid(weekday: str, hour: int, instructor: str, constraints: Dict) -> bool:
    """
    Check if a time slot is valid for an instructor given their constraints.

    Args:
        weekday: Day of the week
        hour: Hour of the day (0-23)
        instructor: Instructor name
        constraints: Dict of instructor constraints

    Returns:
        Boolean indicating if the time slot is valid
    """
    hours = constraints["hours"][instructor]
    if hour < hours["start"] or hour >= hours["end"]:
        return False
    return (weekday, hour) not in constraints["unavailable"][instructor]


def find_continuous_blocks(
    times_list: List[Tuple[str, int]]
) -> List[Tuple[str, int, int]]:
    """
    Convert a list of time slots into continuous blocks.

    Args:
        times_list: List of (weekday, hour) tuples

    Returns:
        List of (weekday, start_hour, end_hour) block tuples
    """
    if not times_list:
        return []

    times_list.sort()
    blocks = []
    current_weekday = times_list[0][0]
    current_start = times_list[0][1]
    current_end = current_start

    for weekday, hour in times_list[1:]:
        if weekday == current_weekday and hour == current_end + 1:
            current_end = hour
        else:
            blocks.append((current_weekday, current_start, current_end + 1))
            current_weekday = weekday
            current_start = hour
            current_end = hour

    blocks.append((current_weekday, current_start, current_end + 1))
    return blocks


def find_continuous_block(
    valid_times: List[Tuple[str, int]],
    block_size: int,
    student_counts: Dict[Tuple[str, int], int],
    scheduled_times: Set[Tuple[str, int]],
) -> List[Tuple[str, int]]:
    """
    Find the best continuous block of specified size from available times.

    Args:
        valid_times: List of valid (weekday, hour) tuples
        block_size: Desired size of the continuous block
        student_counts: Dict mapping time slots to number of available students
        scheduled_times: Set of already scheduled time slots

    Returns:
        List of (weekday, hour) tuples forming the best block, or None if no valid block found
    """
    best_block = None
    max_value = -1

    times_by_day = defaultdict(list)
    for weekday, hour in valid_times:
        times_by_day[weekday].append(hour)

    for weekday, hours in times_by_day.items():
        hours.sort()

        for i in range(len(hours)):
            if i + block_size <= len(hours):
                block_hours = hours[i : i + block_size]
                block_length = block_hours[-1] - block_hours[0] + 1
                if block_length == block_size:
                    block_slots = [(weekday, hour) for hour in block_hours]
                    if any(slot in scheduled_times for slot in block_slots):
                        continue
                    block_value = sum(
                        student_counts[(weekday, hour)] for hour in block_hours
                    )
                    if block_value > max_value:
                        max_value = block_value
                        best_block = block_slots

    return best_block


def find_best_blocks(
    valid_times: List[Tuple[str, int]],
    hours_needed: int,
    max_length: int,
    student_counts: Dict[Tuple[str, int], int],
    scheduled_times: Set[Tuple[str, int]],
) -> List[Tuple[str, int]]:
    """
    Find the best combination of blocks given constraints.

    Args:
        valid_times: List of valid (weekday, hour) tuples
        hours_needed: Total hours needed to schedule
        max_length: Maximum block length allowed
        student_counts: Dict mapping time slots to number of available students
        scheduled_times: Set of already scheduled time slots

    Returns:
        List of (weekday, hour) tuples forming the best blocks
    """
    blocks = []
    remaining_hours = hours_needed

    # Group times by day
    times_by_day = defaultdict(list)
    for time in valid_times:
        times_by_day[time[0]].append(time)

    # Track hours used per day
    hours_per_day = defaultdict(int)

    while remaining_hours > 0:
        best_block = None
        best_value = -1

        for day, times in times_by_day.items():
            # Skip if we've hit daily limit
            if hours_per_day[day] >= max_length:
                continue

            available_hours = max_length - hours_per_day[day]
            block_size = min(remaining_hours, available_hours)

            if block_size <= 0:
                continue

            block = find_continuous_block(
                times, block_size, student_counts, scheduled_times.union(set(blocks))
            )

            if block:
                block_value = sum(student_counts[time] for time in block)
                if block_value > best_value:
                    best_value = block_value
                    best_block = block

        if not best_block:
            return []

        blocks.extend(best_block)
        remaining_hours -= len(best_block)
        hours_per_day[best_block[0][0]] += len(best_block)

        # Remove used times
        times_by_day[best_block[0][0]] = [
            t for t in times_by_day[best_block[0][0]] if t not in best_block
        ]

    return blocks


def optimize_office_hours(
    availability_by_time: Dict[Tuple[str, int], List[str]],
    student_counts: Dict[Tuple[str, int], int],
    constraints: Dict,
) -> Tuple[Dict[str, List[Tuple[str, int, int]]], int]:
    """
    Optimize office hours schedule considering all constraints.

    Args:
        availability_by_time: Dict mapping time slots to available students
        student_counts: Dict mapping time slots to number of available students
        constraints: Dict of instructor constraints

    Returns:
        Tuple of (schedule dict mapping instructors to their blocks, number of students covered)
    """
    schedule = {}
    all_covered_students = set()
    scheduled_times = set()

    # First, schedule all guaranteed hours
    remaining_instructors = set(constraints["hours"].keys())

    for instructor, guaranteed_blocks in constraints["guaranteed"].items():
        if instructor not in remaining_instructors:
            print(
                f"Warning: Found guaranteed blocks for unknown instructor {instructor}"
            )
            continue

        schedule[instructor] = []
        total_max_hours = constraints["hours"][instructor]["max_hours"]
        guaranteed_hours = 0

        # Schedule all guaranteed blocks first
        for weekday, start, end in guaranteed_blocks:
            # Validate guaranteed block
            block_length = end - start
            if not all(
                is_time_valid(weekday, hour, instructor, constraints)
                for hour in range(start, end)
            ):
                print(
                    f"Warning: Guaranteed block for {instructor} conflicts with constraints"
                )
                continue

            schedule[instructor].append((weekday, start, end))
            guaranteed_hours += block_length

            # Add times to scheduled set
            for hour in range(start, end):
                time_slot = (weekday, hour)
                scheduled_times.add(time_slot)
                if time_slot in availability_by_time:
                    all_covered_students.update(availability_by_time[time_slot])

        # Update remaining hours
        remaining_hours = total_max_hours - guaranteed_hours
        if remaining_hours == 0:
            # Remove instructor from further scheduling if all hours are guaranteed
            remaining_instructors.remove(instructor)
        elif remaining_hours < 0:
            print(
                f"Warning: {instructor} has more guaranteed hours ({guaranteed_hours}) than max_hours ({total_max_hours})"
            )
            remaining_instructors.remove(instructor)
        else:
            constraints["hours"][instructor]["max_hours"] = remaining_hours

    # Calculate average usage per time slot for remaining scheduling
    time_values = {
        time: student_counts[time] / len(availability_by_time[time])
        for time in availability_by_time
    }

    # Sort instructors by order in TOML (seniority)
    instructors = [(name, constraints["hours"][name]) for name in remaining_instructors]

    # Schedule remaining flexible hours
    for instructor, hours_data in instructors:
        if instructor not in schedule:
            schedule[instructor] = []

        valid_times = [
            (weekday, hour)
            for weekday in WEEKDAYS
            for hour in range(hours_data["start"], hours_data["end"])
            if (weekday, hour) in availability_by_time
            and is_time_valid(weekday, hour, instructor, constraints)
            and (weekday, hour) not in scheduled_times
        ]

        # Sort valid_times by usage for senior instructors
        valid_times.sort(key=lambda x: time_values[x], reverse=True)

        selected_blocks = find_best_blocks(
            valid_times,
            hours_data["max_hours"],
            hours_data["max_length"],
            student_counts,
            scheduled_times,
        )

        if selected_blocks:
            schedule[instructor].extend(find_continuous_blocks(selected_blocks))
            for time in selected_blocks:
                all_covered_students.update(availability_by_time[time])
                scheduled_times.add(time)
        else:
            print(f"Error: Could not schedule all hours for {instructor}")

    return schedule, len(all_covered_students)


def validate_schedule(
    schedule: Dict[str, List[Tuple[str, int, int]]], constraints: Dict
) -> None:
    """
    Validate the generated schedule against all constraints.

    Args:
        schedule: Dict mapping instructors to their scheduled blocks
        constraints: Dict of instructor constraints
    """
    all_times = set()
    for instructor, blocks in schedule.items():
        # Check overlaps
        for weekday, start, end in blocks:
            for hour in range(start, end):
                time_slot = (weekday, hour)
                if time_slot in all_times:
                    print(f"Error: Overlapping office hours at {weekday} {hour}:00")
                all_times.add(time_slot)

        # Skip further validation for instructors with only guaranteed hours
        if instructor not in constraints["hours"]:
            continue

        # Check total hours and block lengths
        total_hours = sum(end - start for _, start, end in blocks)
        required_hours = constraints["hours"][instructor]["max_hours"]
        if total_hours != required_hours:
            print(
                f"Error: {instructor} has {total_hours} hours scheduled but requires {required_hours}"
            )

        # Check max block length
        max_length = constraints["hours"][instructor]["max_length"]
        for _, start, end in blocks:
            block_length = end - start
            if block_length > max_length:
                print(
                    f"Error: {instructor} has block of length {block_length} but maximum is {max_length}"
                )

        # Check working hours and unavailable times
        for weekday, start, end in blocks:
            if weekday not in WEEKDAYS:
                print(f"Error: {instructor} scheduled on weekend ({weekday})")
            for hour in range(start, end):
                if not is_time_valid(weekday, hour, instructor, constraints):
                    print(
                        f"Error: Invalid time slot for {instructor}: {weekday} {hour}:00"
                    )


def main() -> None:
    """
    Main function: Load data, optimize schedule, and display results.
    """
    respondents, instructors = load_data("respondents.json", "instructors.toml")
    availability_by_time, student_counts, total_students = process_availabilities(
        respondents
    )
    constraints = get_instructor_constraints(instructors)

    schedule, coverage = optimize_office_hours(
        availability_by_time, student_counts, constraints
    )

    validate_schedule(schedule, constraints)

    print(
        f"\nOptimal Schedule (covers {coverage} students, {coverage/total_students:.1%} of total):"
    )

    for instructor, blocks in schedule.items():
        print(f"\n{instructor.capitalize()}:")
        total_hours = sum(end - start for _, start, end in blocks)
        print(f"Total hours: {total_hours}")

        # Sort blocks by day using WEEKDAYS order
        day_order = {day: i for i, day in enumerate(WEEKDAYS)}
        sorted_blocks = sorted(blocks, key=lambda x: day_order[x[0]])

        for weekday, start, end in sorted_blocks:
            block_slots = sum(
                student_counts.get((weekday, hour), 0) for hour in range(start, end)
            )
            avg_utilization = block_slots / ((end - start) * total_students)
            print(
                f"  {weekday}: {start:02d}:00-{end:02d}:00 (avg usage: {avg_utilization:.1%})"
            )


if __name__ == "__main__":
    main()
