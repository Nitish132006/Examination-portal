# Examination Management Portal (EMP)

A simple Flask + Jinja2 + Bootstrap + SQLite project for Admin, Examiner and Student roles.

## 1. Requirements
- Python 3.10 or newer
- Internet connection for Bootstrap CDN (or download Bootstrap locally)
- No separately created database is required.

## 2. Run on Windows
Open Command Prompt in this project folder:

```bash
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open: http://127.0.0.1:5000

On first run, Flask creates `instance/emp.db` and all tables automatically.

## 3. Default Admin Login
- Email: `admin@emp.local`
- Password: `Admin@123`

Change this password and SECRET_KEY before any real deployment. This is a local academic demo.

## 4. Suggested demo workflow
1. Login as Admin.
2. Create a Course.
3. Create an Examination and set slot-creation and booking dates around the current date/time.
4. Register an Examiner in another browser/incognito session.
5. As Admin, approve the Examiner and assign them to the Examination.
6. Login as Examiner; create one or more slots during the configured slot-creation period.
7. As Admin, change the examination status to `Booking Open` when the booking timeline is active.
8. Register/login as Student and book a slot.
9. Login as Examiner, open Student Roster and evaluate a booked student.
10. Tick Publish result; login as Student and view Results.
11. Admin can inspect bookings, search users and reschedule a booking.

## 5. Important timeline rules
- Examiner slot creation is allowed only when the examination status is `Slot Creation` AND current server time is between slot creation start/end.
- Student booking is allowed only when status is `Booking Open` AND current server time is between booking start/end.
- Cancellation is allowed only until the booking end date/time.
- Capacity and duplicate booking are checked on the server.
- Admin status changes are explicit so you can demonstrate opening/closing periods.

## 6. Database tables
- `user`: admin, examiner and student accounts
- `course`: courses
- `examination`: course examination and timelines
- `rubric`: examination marking criteria
- `assignment`: examiner-to-examination mapping
- `slot`: examiner-created examination slots
- `booking`: student slot bookings and booking history
- `evaluation`: marks, remarks and publication status

## 7. Notes / limitations for the academic version
- This is a compact educational implementation intended for local demonstration.
- Rubrics are displayed to examiners as evaluation guidance; marks are entered as a total score. If your evaluator expects marks per individual rubric criterion, extend Evaluation with a child table such as `evaluation_item`.
- Rescheduling moves a booking to another slot of the same examination and checks capacity.
- The interface uses Bootstrap and normal HTML form submissions. JavaScript is not used for core application logic.
- Before production use, add CSRF protection, stronger secret management, password reset, audit logs and database migrations.
- The database is created programmatically using SQLAlchemy `db.create_all()`; do not create it manually.