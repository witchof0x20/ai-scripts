# whenisgood

Optimize office hours scheduling based on student availability and instructor constraints.

## Overview

This script solves the office hours scheduling problem by analyzing student availability data and instructor constraints to create an optimal schedule that maximizes student coverage while respecting working hours, unavailable times, and guaranteed office hours blocks.

## Features

- Processes student availability from WhenIsGood-style JSON data
- Supports instructor-specific constraints (working hours, unavailable times)
- Handles guaranteed (fixed) office hours blocks
- Optimizes for maximum student coverage
- Respects maximum block length constraints
- Validates schedules against all constraints
- Provides detailed utilization statistics

## Input Files

### respondents.json

Student availability data with timestamps:

```json
{
  "student1": {
    "myCanDos": [1234567890000, 1234571490000, ...]
  },
  "student2": {
    "myCanDos": [...]
  }
}
```

### instructors.toml

Instructor constraints and preferences:

```toml
[instructors.instructor1]
start = 9          # Earliest working hour
end = 17           # Latest working hour (exclusive)
max_hours = 4      # Total office hours per week
max_length = 2     # Max consecutive hours per day

[[instructors.instructor1.guaranteed]]
day = "Monday"
start = 14
end = 15

[unavailable]
all = [
  { day = "Friday", start = 12, end = 17 }
]
instructor2 = [
  { day = "Wednesday", start = 10, end = 12 }
]
```

## Usage

```bash
./solve_office_hours.py
```

The script expects `respondents.json` and `instructors.toml` in the current directory.

## Features Explained

### Guaranteed Hours
Fixed office hours blocks that must be scheduled (e.g., regular weekly meetings). These are scheduled first before optimization.

### Unavailable Times
Time blocks when instructors cannot hold office hours. Can be specified globally or per-instructor.

### Optimization Algorithm
1. Schedules all guaranteed hours first
2. Processes instructors in order (seniority-based)
3. For each instructor, finds continuous blocks that maximize student coverage
4. Respects maximum block length per day
5. Avoids scheduling conflicts

### Validation
The script validates:
- No overlapping office hours
- Total hours match requirements
- Block lengths respect maximums
- All times fall within working hours
- No scheduling during unavailable times

## Output

The script displays:
- Total student coverage (count and percentage)
- Per-instructor schedules with:
  - Day and time blocks
  - Average utilization per block
  - Total hours scheduled

## Dependencies

- Python 3.11+ (requires `tomllib`)

## Algorithm Details

The optimizer prioritizes:
1. Guaranteed office hours (fixed scheduling)
2. Senior instructors (scheduled first)
3. High student availability times
4. Continuous time blocks
5. Even distribution across the week
