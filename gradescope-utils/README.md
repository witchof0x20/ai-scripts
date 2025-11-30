# gradescope-utils

Utilities for managing Gradescope assignments via the unofficial API.

## Overview

This script provides automation for Gradescope course management tasks, with a focus on copying assignment extensions between assignments.

## Features

- Authentication with Gradescope using environment variables
- List all courses for an instructor
- Retrieve assignments for a course
- Copy student extensions from one assignment to others

## Configuration

Set the following environment variables:

```bash
export GRADESCOPE_USER="your_email@example.com"
export GRADESCOPE_PASS="your_password"
```

## Usage

The main script demonstrates:
1. Logging into Gradescope
2. Fetching all instructor courses
3. Getting assignments for a specific course
4. Copying extensions from a source assignment to target assignments

Edit the script to set:
- `chosen_course_id` - Your course ID
- `chosen_assignment` - Source assignment ID (to copy extensions from)
- `target_assignments` - List of target assignment IDs

Then run:

```bash
python main.py
```

## Use Case

Useful when you need to apply the same deadline extensions across multiple related assignments (e.g., copying extensions from a quiz to related homework assignments).

## Dependencies

- `gradescopeapi` - Unofficial Gradescope API wrapper (included in `gradescope-api/` subdirectory)

## Warning

This uses an unofficial API and may break if Gradescope changes their internal API structure. Use at your own risk.
