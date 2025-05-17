from gradescopeapi.classes.connection import GSConnection
from gradescopeapi.classes.extensions import get_extensions, update_student_extension
import os

# create connection and login
connection = GSConnection()

username = os.environ.get("GRADESCOPE_USER")
password = os.environ.get("GRADESCOPE_PASS")
connection.login(username, password)

"""
Fetching all courses for user
"""
courses = connection.account.get_courses()
for course_id, course in courses["instructor"].items():
    print(course_id, course)

chosen_course_id = 973437

for assignment in connection.account.get_assignments(chosen_course_id):
    print(assignment)

chosen_assignment = 5869634
target_assignments = [5869642]

extensions = get_extensions(
    connection.account.session, str(chosen_course_id), str(chosen_assignment)
)

for target_assignment in target_assignments:
    for user_id, extension in extensions.items():
        update_student_extension(
            connection.account.session,
            str(chosen_course_id),
            str(target_assignment),
            user_id,
            due_date=extension.due_date,
        )
