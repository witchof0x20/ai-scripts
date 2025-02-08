#!/usr/bin/env python3

import argparse
from bs4 import BeautifulSoup
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from parse import parse_whenisigood, Student, TimeSlot
from typing import Dict, List, Set, Tuple, Optional
import logging
import sys
from itertools import combinations


@dataclass
class UnavailableBlock:
    day: str
    start_hour: int
    end_hour: int
    staff_name: str  # 'all' for everyone


@dataclass
class StaffMember:
    name: str
    start_hour: int  # 24-hour format
    end_hour: int  # 24-hour format
    hours_needed: int
    unavailable_blocks: List[UnavailableBlock] = None

    def __post_init__(self):
        if self.unavailable_blocks is None:
            self.unavailable_blocks = []


class OfficeHoursScheduler:
    def __init__(self, whenisigood_file: str, staff_file: str):
        self.staff = self._load_staff(staff_file)
        self.slots = parse_whenisigood(whenisigood_file)
        self.total_students = self._get_total_students()
        self.used_slots = set()
        self.covered_students = set()  # Track covered students

    def _load_staff(self, staff_file: str) -> List[StaffMember]:
        """Load staff availability constraints and unavailable blocks."""
        staff_dict = {}
        unavailable_blocks = []
        parsing_unavailable = False

        with open(staff_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                if line == "[unavailable]":
                    parsing_unavailable = True
                    continue

                if parsing_unavailable:
                    # Parse unavailable blocks
                    parts = line.strip().split()
                    staff_name = parts[0]
                    start_hour = int(parts[1])
                    end_hour = int(parts[2])
                    day = parts[3]
                    block = UnavailableBlock(day, start_hour, end_hour, staff_name)
                    unavailable_blocks.append(block)
                else:
                    # Parse staff member basic info
                    name, start, end, hours = line.split()
                    staff_dict[name] = StaffMember(
                        name=name,
                        start_hour=int(start),
                        end_hour=int(end),
                        hours_needed=int(hours),
                    )

        # Assign unavailable blocks to staff members
        for block in unavailable_blocks:
            if block.staff_name == "all":
                # Apply to all staff members
                for staff in staff_dict.values():
                    staff.unavailable_blocks.append(block)
            elif block.staff_name in staff_dict:
                staff_dict[block.staff_name].unavailable_blocks.append(block)

        return list(staff_dict.values())

    def _is_valid_time(self, slot: TimeSlot) -> bool:
        """Check if a time slot is within valid business hours."""
        business_days = {"Mon", "Tue", "Wed", "Thu", "Fri"}
        return slot.day in business_days and 8 <= slot.hour < 21

    def _is_staff_available(self, slot: TimeSlot, staff_member: StaffMember) -> bool:
        """Check if a staff member is available for a given time slot."""
        # Check regular hours
        if slot.hour < staff_member.start_hour or slot.hour >= staff_member.end_hour:
            return False

        # Check unavailable blocks
        for block in staff_member.unavailable_blocks:
            if block.day == slot.day and block.start_hour <= slot.hour < block.end_hour:
                return False

        return True

    def _get_total_students(self) -> int:
        """Get total number of students from any time slot."""
        for slots in self.slots.values():
            if slots:
                return slots[0].total_students
        return 0

    def _get_coverage_score(self, slots: List[TimeSlot]) -> float:
        """Calculate how many new students would be covered by these slots."""
        if not slots:
            return 0

        # Get all students available in any of the slots
        new_students = set()
        for slot in slots:
            new_students.update(slot.available_students)

        # Only count students not already covered
        uncovered_students = new_students - self.covered_students
        return len(uncovered_students)

    def _get_slot_score(self, slot: TimeSlot, staff_member: StaffMember) -> float:
        """Calculate score for a time slot based on new student coverage."""
        if not self._is_valid_time(slot):
            return -1

        if not self._is_staff_available(slot, staff_member):
            return -1

        if slot in self.used_slots:
            return -1

        # Calculate how many new students would be covered
        new_coverage = len(slot.available_students - self.covered_students)
        return new_coverage

    def _find_contiguous_block(
        self, day: str, start_hour: int, staff_member: StaffMember, hours_needed: int
    ) -> List[TimeSlot]:
        """Find a contiguous block of time slots."""
        slots = []
        current_hour = start_hour

        while len(slots) < hours_needed and current_hour < min(
            staff_member.end_hour, 21
        ):
            day_slots = [s for s in self.slots[day] if s.hour == current_hour]
            if not day_slots:
                break

            slot = day_slots[0]
            if self._get_slot_score(slot, staff_member) < 0:
                break

            slots.append(slot)
            current_hour += 1

        return slots if len(slots) == hours_needed else []

    def _find_best_blocks(
        self, hours_needed: int, staff_member: StaffMember
    ) -> List[Tuple[str, int, int]]:
        """Find best contiguous blocks maximizing student coverage."""
        best_blocks = []
        business_days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
        remaining_hours = hours_needed

        # Track day usage globally
        day_usage = defaultdict(int)
        for slot in self.used_slots:
            day_usage[slot.day] += 1

        # Try to allocate blocks to unused days first
        for day in business_days:
            if remaining_hours <= 0:
                break

            if day in {block[0] for block in best_blocks}:
                continue

            if day_usage[day] <= min(day_usage.values()):
                best_score = -float("inf")
                best_block = None
                target_hours = min(remaining_hours, 3)

                for start_hour in range(
                    staff_member.start_hour,
                    min(staff_member.end_hour - target_hours + 1, 21),
                ):
                    slots = self._find_contiguous_block(
                        day, start_hour, staff_member, target_hours
                    )
                    if slots:
                        score = self._get_coverage_score(slots)
                        if score > best_score:
                            best_score = score
                            best_block = (
                                day,
                                start_hour,
                                start_hour + len(slots),
                                slots,
                            )

                if best_block:
                    day, start, end, slots = best_block
                    best_blocks.append((day, start, end))
                    self.used_slots.update(slots)
                    self._update_coverage(slots)
                    remaining_hours -= end - start
                    day_usage[day] += 1

        # Fill remaining hours
        while remaining_hours > 0:
            best_score = -float("inf")
            best_block = None

            for day in business_days:
                for start_hour in range(
                    staff_member.start_hour, min(staff_member.end_hour, 21)
                ):
                    slots = self._find_contiguous_block(
                        day, start_hour, staff_member, remaining_hours
                    )
                    if slots:
                        score = self._get_coverage_score(slots) - (day_usage[day] * 2)
                        if score > best_score:
                            best_score = score
                            best_block = (
                                day,
                                start_hour,
                                start_hour + len(slots),
                                slots,
                            )

            if best_block:
                day, start, end, slots = best_block
                if end - start > remaining_hours:
                    end = start + remaining_hours
                    slots = slots[:remaining_hours]
                best_blocks.append((day, start, end))
                self.used_slots.update(slots)
                self._update_coverage(slots)
                remaining_hours -= end - start
                day_usage[day] += 1
            else:
                logging.warning(
                    f"Could not fill all hours for {staff_member.name}. "
                    f"Remaining hours: {remaining_hours}"
                )
                break

        return best_blocks

    def _update_coverage(self, slots: List[TimeSlot]):
        """Update the set of covered students after selecting slots."""
        for slot in slots:
            self.covered_students.update(slot.available_students)

    def _aggregate_blocks(
        self, blocks: List[Tuple[str, int, int]]
    ) -> List[Tuple[str, int, int]]:
        """Combine adjacent time blocks on the same day."""
        if not blocks:
            return blocks

        day_order = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4}
        blocks.sort(key=lambda x: (day_order.get(x[0], 5), x[1]))

        aggregated = []
        current_block = list(blocks[0])

        for block in blocks[1:]:
            if block[0] == current_block[0] and block[1] == current_block[2]:
                current_block[2] = block[2]
            else:
                aggregated.append(tuple(current_block))
                current_block = list(block)

        aggregated.append(tuple(current_block))
        return aggregated

    def generate_schedule(
        self,
    ) -> Tuple[Dict[str, List[Tuple[str, time, time]]], Dict[str, float]]:
        """Generate schedule optimizing for maximum student coverage."""
        schedule = {}
        coverage_stats = {
            "total_students": self.total_students,
            "covered_students": 0,
            "coverage_percentage": 0,
        }

        staff_sorted = sorted(self.staff, key=lambda x: x.hours_needed, reverse=True)

        for staff_member in staff_sorted:
            blocks = self._find_best_blocks(staff_member.hours_needed, staff_member)
            if blocks:
                blocks = self._aggregate_blocks(blocks)
                schedule[staff_member.name] = [
                    (day, time(start, 0), time(end, 0)) for day, start, end in blocks
                ]
            else:
                logging.warning(
                    f"Could not find any valid blocks for {staff_member.name}"
                )

        # Calculate final coverage statistics
        coverage_stats["covered_students"] = len(self.covered_students)
        coverage_stats["coverage_percentage"] = (
            coverage_stats["covered_students"] / coverage_stats["total_students"] * 100
            if coverage_stats["total_students"] > 0
            else 0
        )

        return schedule, coverage_stats


def main():
    parser = argparse.ArgumentParser(
        description="Generate optimal office hours schedule"
    )
    parser.add_argument("whenisigood_file", help="WhenIsGood HTML file")
    parser.add_argument("staff_file", help="Staff availability file")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose output"
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=0.0,
        help="Minimum percentage of students that must be covered (0-100)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    try:
        scheduler = OfficeHoursScheduler(args.whenisigood_file, args.staff_file)
        schedule, coverage_stats = scheduler.generate_schedule()

        print("\nProposed Office Hours Schedule:")
        print("=" * 50)

        for name, blocks in schedule.items():
            total_hours = sum((end.hour - start.hour) for _, start, end in blocks)
            print(f"\n{name} ({total_hours} hours):")
            day_order = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4}
            blocks.sort(key=lambda x: (day_order.get(x[0], 7), x[1]))
            for day, start, end in blocks:
                print(
                    f"  {day}: {start.strftime('%I:%M %p')} - {end.strftime('%I:%M %p')}"
                )

        print("\nCoverage Statistics:")
        print(f"Total students: {coverage_stats['total_students']}")
        print(f"Students covered: {coverage_stats['covered_students']}")
        print(f"Coverage percentage: {coverage_stats['coverage_percentage']:.1f}%")

        if coverage_stats["coverage_percentage"] < args.min_coverage:
            print(
                f"\nWARNING: Coverage ({coverage_stats['coverage_percentage']:.1f}%) is below minimum required ({args.min_coverage}%)"
            )
            sys.exit(1)

    except Exception as e:
        logging.error(f"Error generating schedule: {e}")
        if args.verbose:
            logging.exception("Detailed error information:")
        sys.exit(1)


if __name__ == "__main__":
    main()
