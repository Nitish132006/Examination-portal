from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime, date
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = "change-this-secret-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(app.instance_path, "emp.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
os.makedirs(app.instance_path, exist_ok=True)
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

def now():
    return datetime.now()

def parse_dt(value):
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except (ValueError, TypeError):
        return None

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    department = db.Column(db.String(100))
    approved = db.Column(db.Boolean, default=True)
    active = db.Column(db.Boolean, default=True)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True)

class Examination(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("course.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    exam_type = db.Column(db.String(40), nullable=False)
    duration = db.Column(db.Integer, default=30)
    max_marks = db.Column(db.Integer, default=100)
    slot_start = db.Column(db.DateTime, nullable=False)
    slot_end = db.Column(db.DateTime, nullable=False)
    booking_start = db.Column(db.DateTime, nullable=False)
    booking_end = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(30), default="Draft")
    course = db.relationship("Course", backref="examinations")

class Rubric(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("examination.id"), nullable=False)
    criterion = db.Column(db.String(150), nullable=False)
    max_marks = db.Column(db.Float, nullable=False)
    weightage = db.Column(db.Float, default=1)
    description = db.Column(db.Text)
    exam = db.relationship("Examination", backref="rubrics")

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("examination.id"), nullable=False)
    examiner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    examiner = db.relationship("User")

class Slot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("examination.id"), nullable=False)
    examiner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    exam_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.String(10), nullable=False)
    end_time = db.Column(db.String(10), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default="Available")
    exam = db.relationship("Examination")
    examiner = db.relationship("User")

    @property
    def booked_count(self):
        return Booking.query.filter_by(slot_id=self.id, status="Booked").count()

    @property
    def seats_left(self):
        return max(0, self.capacity - self.booked_count)

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey("slot.id"), nullable=False)
    booked_at = db.Column(db.DateTime, default=now)
    status = db.Column(db.String(20), default="Booked")
    student = db.relationship("User")
    slot = db.relationship("Slot")

class Evaluation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    booking_id = db.Column(db.Integer, db.ForeignKey("booking.id"), unique=True, nullable=False)
    marks = db.Column(db.Float, nullable=False)
    remarks = db.Column(db.Text)
    published = db.Column(db.Boolean, default=False)
    evaluated_at = db.Column(db.DateTime, default=now)
    booking = db.relationship("Booking", backref=db.backref("evaluation", uselist=False))

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def roles(*allowed):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if current_user.role not in allowed:
                abort(403)
            if current_user.role == "examiner" and (not current_user.approved or not current_user.active):
                flash("Your examiner account is awaiting approval or is inactive.", "warning")
                return redirect(url_for("login"))
            if current_user.role == "student" and not current_user.active:
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

def exam_window_open(exam, kind):
    start = exam.slot_start if kind == "slot" else exam.booking_start
    end = exam.slot_end if kind == "slot" else exam.booking_end
    return start <= now() <= end

@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        role = request.form.get("role")
        name, email, password = request.form.get("name","").strip(), request.form.get("email","").strip().lower(), request.form.get("password","")
        if role not in ("student", "examiner") or not name or not email or len(password) < 6:
            flash("Enter valid details. Password must contain at least 6 characters.", "danger")
        elif User.query.filter_by(email=email).first():
            flash("Email already registered.", "danger")
        else:
            user = User(name=name, email=email, password=generate_password_hash(password),
                        role=role, department=request.form.get("department",""),
                        approved=(role == "student"))
            db.session.add(user); db.session.commit()
            flash("Registration successful. Examiner accounts require Admin approval." if role == "examiner" else "Registration successful. Please log in.", "success")
            return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(email=request.form.get("email","").strip().lower()).first()
        if user and check_password_hash(user.password, request.form.get("password","")) and user.active:
            if user.role == "examiner" and not user.approved:
                flash("Your account is waiting for Admin approval.", "warning")
            else:
                login_user(user)
                return redirect(url_for("dashboard"))
        else:
            flash("Invalid email/password or inactive account.", "danger")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    if current_user.role == "admin":
        stats = {
            "courses": Course.query.count(), "exams": Examination.query.count(),
            "examiners": User.query.filter_by(role="examiner").count(),
            "students": User.query.filter_by(role="student").count(),
            "slots": Slot.query.count(), "bookings": Booking.query.count()
        }
        return render_template("admin_dashboard.html", stats=stats,
            pending=User.query.filter_by(role="examiner", approved=False).all())
    if current_user.role == "examiner":
        assignments = Assignment.query.filter_by(examiner_id=current_user.id).all()
        exam_ids = [a.exam_id for a in assignments]
        slots = Slot.query.filter_by(examiner_id=current_user.id).all()
        pending = Booking.query.join(Slot).filter(Slot.examiner_id==current_user.id, Booking.status=="Booked",
                    ~Booking.id.in_(db.session.query(Evaluation.booking_id))).count()
        return render_template("examiner_dashboard.html", assignments=assignments, slots=slots, pending=pending)
    bookings = Booking.query.filter_by(student_id=current_user.id).order_by(Booking.booked_at.desc()).all()
    exams = Examination.query.filter(Examination.status != "Draft").all()
    return render_template("student_dashboard.html", bookings=bookings, exams=exams)

# Admin: courses
@app.route("/admin/courses", methods=["GET","POST"])
@roles("admin")
def courses():
    if request.method == "POST":
        code=request.form.get("code","").strip().upper()
        if not code or not request.form.get("name","").strip():
            flash("Course code and name are required.", "danger")
        elif Course.query.filter_by(code=code).first():
            flash("Course code already exists.", "danger")
        else:
            db.session.add(Course(code=code, name=request.form["name"], description=request.form.get("description",""))); db.session.commit()
            flash("Course created.", "success")
        return redirect(url_for("courses"))
    return render_template("courses.html", courses=Course.query.order_by(Course.code).all())

@app.route("/admin/course/<int:course_id>/delete", methods=["POST"])
@roles("admin")
def delete_course(course_id):
    course=db.get_or_404(Course, course_id)
    if course.examinations:
        flash("Cannot delete a course that has examinations. Deactivate it instead.", "warning")
    else:
        db.session.delete(course); db.session.commit(); flash("Course deleted.", "success")
    return redirect(url_for("courses"))

@app.route("/admin/course/<int:course_id>/toggle", methods=["POST"])
@roles("admin")
def toggle_course(course_id):
    c=db.get_or_404(Course, course_id); c.active=not c.active; db.session.commit()
    return redirect(url_for("courses"))

@app.route("/admin/exams", methods=["GET","POST"])
@roles("admin")
def exams():
    if request.method=="POST":
        values=[parse_dt(request.form.get(k)) for k in ("slot_start","slot_end","booking_start","booking_end")]
        if not all(values) or values[0]>=values[1] or values[2]>=values[3]:
            flash("Enter valid timeline dates; each start must be before its end.", "danger")
        else:
            exam=Examination(course_id=int(request.form["course_id"]), name=request.form["name"],
                exam_type=request.form["exam_type"], duration=int(request.form["duration"]),
                max_marks=int(request.form["max_marks"]), slot_start=values[0], slot_end=values[1],
                booking_start=values[2], booking_end=values[3], status="Draft")
            db.session.add(exam); db.session.commit(); flash("Examination created.", "success")
        return redirect(url_for("exams"))
    return render_template("exams.html", exams=Examination.query.order_by(Examination.id.desc()).all(),
                           courses=Course.query.filter_by(active=True).all(), examiners=User.query.filter_by(role="examiner",approved=True,active=True).all())

@app.route("/admin/exam/<int:exam_id>/assign", methods=["POST"])
@roles("admin")
def assign_exam(exam_id):
    examiner_id=int(request.form["examiner_id"])
    if not Assignment.query.filter_by(exam_id=exam_id, examiner_id=examiner_id).first():
        db.session.add(Assignment(exam_id=exam_id, examiner_id=examiner_id)); db.session.commit()
    flash("Examiner assigned.", "success"); return redirect(url_for("exams"))

@app.route("/admin/exam/<int:exam_id>/status", methods=["POST"])
@roles("admin")
def exam_status(exam_id):
    exam=db.get_or_404(Examination,exam_id)
    status=request.form.get("status")
    if status in ("Draft","Slot Creation","Booking Open","Closed","Completed"):
        exam.status=status; db.session.commit()
    return redirect(url_for("exams"))

@app.route("/admin/exam/<int:exam_id>/delete", methods=["POST"])
@roles("admin")
def delete_exam(exam_id):
    exam=db.get_or_404(Examination,exam_id)
    if Slot.query.filter_by(exam_id=exam_id).first():
        flash("Cannot delete an examination with slots/bookings. Set its status to Closed instead.", "warning")
    else:
        Rubric.query.filter_by(exam_id=exam_id).delete()
        Assignment.query.filter_by(exam_id=exam_id).delete()
        db.session.delete(exam); db.session.commit()
    return redirect(url_for("exams"))

@app.route("/admin/exam/<int:exam_id>/rubrics", methods=["GET","POST"])
@roles("admin")
def rubrics(exam_id):
    exam=db.get_or_404(Examination,exam_id)
    if request.method=="POST":
        criterion=request.form.get("criterion","").strip()
        marks=float(request.form.get("max_marks",0))
        if not criterion or marks<=0:
            flash("Enter a criterion and positive maximum marks.", "danger")
        else:
            db.session.add(Rubric(exam_id=exam_id,criterion=criterion,max_marks=marks,
                weightage=float(request.form.get("weightage",1)),description=request.form.get("description","")))
            db.session.commit(); flash("Rubric criterion added.", "success")
        return redirect(url_for("rubrics",exam_id=exam_id))
    return render_template("rubrics.html",exam=exam)

@app.route("/admin/rubric/<int:rubric_id>/delete",methods=["POST"])
@roles("admin")
def delete_rubric(rubric_id):
    r=db.get_or_404(Rubric,rubric_id); exam_id=r.exam_id; db.session.delete(r); db.session.commit()
    return redirect(url_for("rubrics",exam_id=exam_id))

@app.route("/admin/examiners")
@roles("admin")
def examiners():
    return render_template("examiners.html", examiners=User.query.filter_by(role="examiner").all())

@app.route("/admin/examiner/<int:user_id>/<action>",methods=["POST"])
@roles("admin")
def examiner_action(user_id,action):
    u=db.get_or_404(User,user_id)
    if u.role!="examiner": abort(404)
    if action=="approve": u.approved=True; u.active=True
    elif action=="deactivate": u.active=False
    elif action=="activate": u.active=True
    db.session.commit(); flash("Examiner account updated.", "success")
    return redirect(url_for("examiners"))

@app.route("/admin/slots")
@roles("admin")
def admin_slots():
    return render_template("admin_slots.html",slots=Slot.query.order_by(Slot.exam_date,Slot.start_time).all(), examiners=User.query.filter_by(role="examiner",approved=True,active=True).all())

@app.route("/admin/slot/<int:slot_id>/examiner",methods=["POST"])
@roles("admin")
def change_slot_examiner(slot_id):
    slot=db.get_or_404(Slot,slot_id); slot.examiner_id=int(request.form["examiner_id"]); db.session.commit()
    flash("Examiner assignment changed.", "success"); return redirect(url_for("admin_slots"))

@app.route("/admin/bookings")
@roles("admin")
def admin_bookings():
    q=request.args.get("q","").strip()
    query=Booking.query.join(User,Booking.student_id==User.id).join(Slot)
    if q:
        query=query.filter(db.or_(User.name.ilike(f"%{q}%"),User.email.ilike(f"%{q}%"),db.cast(Booking.id,db.String)==q))
    return render_template("bookings.html",bookings=query.order_by(Booking.booked_at.desc()).all(),admin=True,all_slots=Slot.query.all())

@app.route("/admin/booking/<int:booking_id>/reschedule",methods=["POST"])
@roles("admin")
def reschedule(booking_id):
    booking=db.get_or_404(Booking,booking_id); new_slot=db.get_or_404(Slot,int(request.form["slot_id"]))
    duplicate=Booking.query.join(Slot).filter(Booking.student_id==booking.student_id,Booking.status=="Booked",
        Slot.exam_id==new_slot.exam_id,Booking.id!=booking.id).first()
    if new_slot.exam_id!=booking.slot.exam_id or new_slot.seats_left<1 or duplicate:
        flash("Invalid destination slot: check examination, capacity and duplicate booking.", "danger")
    else:
        booking.slot_id=new_slot.id; booking.status="Booked"; db.session.commit(); flash("Booking rescheduled.", "success")
    return redirect(url_for("admin_bookings"))

@app.route("/admin/users")
@roles("admin")
def admin_users():
    q=request.args.get("q","").strip()
    query=User.query.filter(User.role!="admin")
    if q: query=query.filter(db.or_(User.name.ilike(f"%{q}%"),User.email.ilike(f"%{q}%"),db.cast(User.id,db.String)==q))
    return render_template("users.html",users=query.order_by(User.role,User.name).all())

# Examiner slot management and evaluation
@app.route("/examiner/slots",methods=["GET","POST"])
@roles("examiner")
def examiner_slots():
    if request.method=="POST":
        exam=db.get_or_404(Examination,int(request.form["exam_id"]))
        assigned=Assignment.query.filter_by(exam_id=exam.id,examiner_id=current_user.id).first()
        d=datetime.strptime(request.form["exam_date"],"%Y-%m-%d").date()
        cap=int(request.form["capacity"])
        if not assigned or exam.status!="Slot Creation" or not exam_window_open(exam,"slot"):
            flash("You are not assigned, or the slot creation period is closed.", "danger")
        elif cap<1 or request.form["start_time"]>=request.form["end_time"]:
            flash("Enter a valid time range and positive capacity.", "danger")
        else:
            db.session.add(Slot(exam_id=exam.id,examiner_id=current_user.id,exam_date=d,
                start_time=request.form["start_time"],end_time=request.form["end_time"],capacity=cap))
            db.session.commit(); flash("Slot created.", "success")
        return redirect(url_for("examiner_slots"))
    assignments=Assignment.query.filter_by(examiner_id=current_user.id).all()
    ids=[a.exam_id for a in assignments]
    return render_template("examiner_slots.html",slots=Slot.query.filter_by(examiner_id=current_user.id).all(),
        exams=Examination.query.filter(Examination.id.in_(ids),Examination.status=="Slot Creation").all())

@app.route("/examiner/slot/<int:slot_id>/delete",methods=["POST"])
@roles("examiner")
def delete_slot(slot_id):
    slot=db.get_or_404(Slot,slot_id)
    if slot.examiner_id!=current_user.id: abort(403)
    if slot.booked_count or slot.exam.status=="Booking Open":
        flash("A booked slot or a slot during booking cannot be deleted.", "warning")
    else:
        db.session.delete(slot); db.session.commit(); flash("Slot deleted.", "success")
    return redirect(url_for("examiner_slots"))

@app.route("/examiner/roster")
@roles("examiner")
def roster():
    slots=Slot.query.filter_by(examiner_id=current_user.id).all()
    return render_template("roster.html",slots=slots,s_booking=Booking.query.filter(Booking.slot_id.in_([x.id for x in slots])).all() if slots else [])

@app.route("/examiner/evaluate/<int:booking_id>",methods=["GET","POST"])
@roles("examiner")
def evaluate(booking_id):
    booking=db.get_or_404(Booking,booking_id)
    if booking.slot.examiner_id!=current_user.id or booking.status!="Booked": abort(403)
    if request.method=="POST":
        marks=float(request.form.get("marks",0))
        if marks<0 or marks>booking.slot.exam.max_marks:
            flash(f"Marks must be between 0 and {booking.slot.exam.max_marks}.", "danger")
        else:
            ev=Evaluation.query.filter_by(booking_id=booking.id).first()
            if not ev: ev=Evaluation(booking_id=booking.id); db.session.add(ev)
            ev.marks=marks; ev.remarks=request.form.get("remarks",""); ev.published=("publish" in request.form)
            booking.status="Completed"; db.session.commit(); flash("Evaluation saved.", "success")
            return redirect(url_for("roster"))
    return render_template("evaluate.html",booking=booking)

# Student
@app.route("/student/exams")
@roles("student")
def student_exams():
    q=request.args.get("q","").strip()
    query=Examination.query.filter(Examination.status.in_(["Slot Creation","Booking Open","Closed","Completed"]))
    if q: query=query.filter(Examination.name.ilike(f"%{q}%"))
    return render_template("student_exams.html",exams=query.all(),slots=Slot.query.all(),e_slots=[])

@app.route("/student/book/<int:slot_id>",methods=["POST"])
@roles("student")
def book_slot(slot_id):
    slot=db.get_or_404(Slot,slot_id); exam=slot.exam
    duplicate=Booking.query.join(Slot).filter(Booking.student_id==current_user.id,Booking.status=="Booked",Slot.exam_id==exam.id).first()
    if exam.status!="Booking Open" or not exam_window_open(exam,"booking"):
        flash("Booking is not currently open.", "danger")
    elif slot.status=="Cancelled" or slot.seats_left<1:
        flash("This slot is full or unavailable.", "danger")
    elif duplicate:
        flash("You already have a booking for this examination.", "warning")
    else:
        db.session.add(Booking(student_id=current_user.id,slot_id=slot.id)); db.session.commit()
        flash("Slot booked successfully.", "success")
    return redirect(url_for("student_exams"))

@app.route("/student/cancel/<int:booking_id>",methods=["POST"])
@roles("student")
def cancel_booking(booking_id):
    b=db.get_or_404(Booking,booking_id)
    if b.student_id!=current_user.id: abort(403)
    if b.status!="Booked" or now()>b.slot.exam.booking_end:
        flash("This booking can no longer be cancelled.", "warning")
    else:
        b.status="Cancelled"; db.session.commit(); flash("Booking cancelled.", "success")
    return redirect(url_for("dashboard"))

@app.route("/student/results")
@roles("student")
def results():
    bookings=Booking.query.filter_by(student_id=current_user.id).all()
    return render_template("results.html",bookings=bookings)

@app.route("/profile",methods=["GET","POST"])
@login_required
def profile():
    if request.method=="POST":
        current_user.name=request.form.get("name","").strip()
        current_user.department=request.form.get("department","")
        db.session.commit(); flash("Profile updated.", "success")
    return render_template("profile.html")

@app.errorhandler(403)
def forbidden(e):
    return render_template("message.html",title="Access denied",message="You do not have permission to access this page."),403

@app.errorhandler(404)
def not_found(e):
    return render_template("message.html",title="Not found",message="The requested record does not exist."),404

with app.app_context():
    db.create_all()
    if not User.query.filter_by(role="admin").first():
        db.session.add(User(name="Administrator",email="admin@emp.local",
            password=generate_password_hash("Admin@123"),role="admin",approved=True))
        db.session.commit()

if __name__ == "__main__":
    app.run(debug=True)
