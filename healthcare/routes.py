import os
import secrets
import random
import time

from datetime import timezone
from PIL import Image
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer as Serializer

from flask import (
    Blueprint, render_template, url_for, flash, redirect,
    request, jsonify, abort, current_app
)
from flask_login import (
    login_user, logout_user, login_required,
    current_user
)

from healthcare import db, bcrypt, mail
from healthcare.models import User, Post, HeartRateData
from healthcare.form import (
    RegistrationForm, LoginForm, PostForm,
    UpdateAccountForm, RequestResetForm, ResetPasswordForm
)

# === BLUEPRINT ===
main = Blueprint("main", __name__)




# -------------------------- ROUTES -------------------------- #

@main.route("/")
@login_required
def home():
    page = request.args.get('page', 1, type=int)
    sort = request.args.get("filter", "newest")

    query = Post.query.filter_by(user_id=current_user.id)

    if sort == "risk":
        query = query.order_by(Post.risk.desc())
    else:
        query = query.order_by(Post.date_posted.desc())

    posts = query.paginate(page=page, per_page=5)
    return render_template("home.html", title="Trang chủ", posts=posts, filter=sort)


@main.route("/about")
def about():
    return render_template("about.html", title="About")


@main.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_pw = bcrypt.generate_password_hash(form.password.data).decode("utf-8")
        user = User(username=form.username.data, email=form.email.data, password=hashed_pw)

        db.session.add(user)
        db.session.commit()

        flash("Tạo tài khoản thành công!", "success")
        return redirect(url_for("main.login"))

    return render_template("register.html", form=form)


@main.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    form = LoginForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get("next")
            return redirect(next_page) if next_page else redirect(url_for("main.home"))

        flash("Sai email hoặc mật khẩu!", "danger")

    return render_template("login.html", form=form)


@main.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("main.home"))


# =================== PROFILE PICTURE =================== #

def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + ext
    picture_path = os.path.join(current_app.root_path, "static/profile_pics", picture_fn)

    i = Image.open(form_picture)
    i.thumbnail((125, 125))
    i.save(picture_path)

    return picture_fn


@main.route("/account", methods=["GET", "POST"])
@login_required
def account():
    form = UpdateAccountForm()

    if form.validate_on_submit():
        if form.picture.data:
            picture_file = save_picture(form.picture.data)
            current_user.image_file = picture_file

        current_user.username = form.username.data
        current_user.email = form.email.data

        db.session.commit()
        flash("Cập nhật thành công!", "success")
        return redirect(url_for("main.account"))

    elif request.method == "GET":
        form.username.data = current_user.username
        form.email.data = current_user.email

    image_file = url_for("static", filename="profile_pics/" + current_user.image_file)

    return render_template("account.html", image_file=image_file, form=form)


# =================== POSTS =================== #

@main.route("/post/new", methods=["GET", "POST"])
@login_required
def new_post():
    form = PostForm()

    if form.validate_on_submit():
        post = Post(
            patient_name=form.patient_name.data,
            age=form.age.data,
            gender=form.gender.data,
            condition=form.condition.data,
            notes=form.notes.data,
            device_id=form.device_id.data,
            author=current_user
        )

        db.session.add(post)
        db.session.commit()

        # Fake dữ liệu IoT
        for _ in range(100):
            db.session.add(
                HeartRateData(
                    device_id=form.device_id.data,
                    heart_rate=random.randint(60, 100),
                    spo2=random.randint(93, 100)
                )
            )
        db.session.commit()

        # Tính risk
        post.risk = random.uniform(0, 1)

        db.session.commit()

        flash("Đã tạo hồ sơ bệnh nhân!", "success")
        return redirect(url_for("main.home"))

    return render_template("create_post.html", form=form, legend="Hồ sơ mới")


@main.route("/post/<int:post_id>")
@login_required
def post(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template("post.html", post=post)


@main.route("/post/<int:post_id>/update", methods=["GET", "POST"])
@login_required
def update_post(post_id):
    post = Post.query.get_or_404(post_id)

    if post.author != current_user:
        abort(403)

    form = PostForm()

    if form.validate_on_submit():
        post.patient_name = form.patient_name.data
        post.age = form.age.data
        post.gender = form.gender.data
        post.condition = form.condition.data
        post.notes = form.notes.data
        post.device_id = form.device_id.data
        db.session.commit()

        post.risk = random.uniform(0, 1)

        db.session.commit()

        flash("Đã cập nhật!", "success")
        return redirect(url_for("main.home"))

    elif request.method == "GET":
        form.patient_name.data = post.patient_name
        form.age.data = post.age
        form.gender.data = post.gender
        form.condition.data = post.condition
        form.notes.data = post.notes
        form.device_id.data = post.device_id

    return render_template("create_post.html", form=form, legend="Cập nhật hồ sơ")


@main.route("/post/<int:post_id>/delete", methods=["POST"])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)

    if post.author != current_user:
        abort(403)

    db.session.delete(post)
    db.session.commit()

    flash("Đã xoá!", "success")
    return redirect(url_for("main.home"))


# =================== HEARTBEAT API =================== #

@main.route("/heartbeat/latest/<string:device_id>")
def heartbeat_latest(device_id):
    last = HeartRateData.query.filter_by(device_id=device_id).order_by(HeartRateData.timestamp.desc()).first()

    if not last:
        return jsonify({"timestamp": None, "bpm": 0, "spo2": 0})

    ts = last.timestamp.astimezone(timezone.utc)
    return jsonify({
        "timestamp_iso": ts.isoformat(),
        "timestamp_ms": int(ts.timestamp() * 1000),
        "bpm": last.heart_rate,
        "spo2": last.spo2
    })


@main.route("/api/heartbeat", methods=["POST"])
def receive_heartbeat():
    try:
        data = request.get_json()

        if not data:
            return jsonify({"error": "invalid JSON"}), 400

        entry = HeartRateData(
            device_id=data.get("device_id"),
            heart_rate=data.get("heart_rate"),
            spo2=data.get("spo2")
        )

        db.session.add(entry)
        db.session.commit()

        # Giữ 100 bản ghi gần nhất
        total = HeartRateData.query.count()
        if total > 100:
            old = HeartRateData.query.order_by(HeartRateData.timestamp.asc()).limit(total - 100)
            for row in old:
                db.session.delete(row)
            db.session.commit()

        return jsonify({"message": "saved"}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =================== PASSWORD RESET =================== #

def get_serializer():
    return Serializer(current_app.config["SECRET_KEY"])


def send_reset_email(user):
    s = get_serializer()
    token = s.dumps({"user_id": user.id})

    msg = Message(
        "Reset Password",
        sender=current_app.config["MAIL_USERNAME"],
        recipients=[user.email]
    )

    msg.body = f"""
Reset mật khẩu:

{url_for('main.reset_token', token=token, _external=True)}

Nếu bạn không yêu cầu, hãy bỏ qua.
"""
    mail.send(msg)


@main.route("/reset_password", methods=["GET", "POST"])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    form = RequestResetForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        send_reset_email(user)
        flash("Đã gửi email reset!", "success")
        return redirect(url_for("main.login"))

    return render_template("reset_request.html", form=form)


@main.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    s = get_serializer()
    try:
        data = s.loads(token, max_age=1800)
        user = User.query.get(data["user_id"])

    except Exception:
        flash("Token lỗi hoặc hết hạn!", "warning")
        return redirect(url_for("main.reset_request"))

    form = ResetPasswordForm()

    if form.validate_on_submit():
        hashed = bcrypt.generate_password_hash(form.password.data).decode("utf-8")
        user.password = hashed
        db.session.commit()

        flash("Đã đổi mật khẩu!", "success")
        return redirect(url_for("main.login"))

    return render_template("reset_token.html", form=form)


# =================== AI FEATURE =================== #

def encode_gender(g):
    g = g.lower()
    return 1 if g in ["nam", "male", "m"] else 0


