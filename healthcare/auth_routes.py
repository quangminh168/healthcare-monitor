import os
import secrets
from PIL import Image
from flask import Blueprint, render_template, url_for, flash, redirect, request, current_app
from healthcare import db, bcrypt, limiter
from healthcare.models import User
from healthcare.form import (
    RegistrationForm,
    LoginForm,
    UpdateAccountForm,
    RequestResetForm,
    ResetPasswordForm,
)
from healthcare.tasks import send_reset_email_task
from flask_login import login_user, logout_user, login_required, current_user
from itsdangerous import URLSafeTimedSerializer as Serializer

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"], endpoint="register")
@limiter.limit(lambda: current_app.config.get("RATELIMIT_REGISTER", "3/minute"))
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode("utf-8")
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash(f"Account created for {form.username.data}!", "success")
        return redirect(url_for("auth.login"))
    return render_template("register.html", title="Register", form=form)


@auth_bp.route("/login", methods=["GET", "POST"], endpoint="login")
@limiter.limit(lambda: current_app.config.get("RATELIMIT_LOGIN", "5/minute"))
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get("next")
            return redirect(next_page) if next_page else redirect(url_for("dashboard.home"))
        else:
            flash("Login unsuccessful. Please check email or password", "danger")
    return render_template("login.html", title="Login", form=form)


@auth_bp.route("/logout", endpoint="logout")
def logout():
    logout_user()
    return redirect(url_for("dashboard.home"))


def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(current_app.root_path, "static/profile_pics", picture_fn)
    output_size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)
    return picture_fn


@auth_bp.route("/account", methods=["GET", "POST"], endpoint="account")
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
        flash("Your account has been updated!", "success")
        return redirect(url_for("auth.account"))
    elif request.method == "GET":
        form.username.data = current_user.username
        form.email.data = current_user.email
    image_file = url_for("static", filename="profile_pics/" + current_user.image_file)
    return render_template("account.html", title="Account", image_file=image_file, form=form)


def get_serializer():
    return Serializer(current_app.config["SECRET_KEY"])


def send_reset_email(user):
    s = get_serializer()
    token = s.dumps({"user_id": user.id})
    send_reset_email_task.delay(user.id, token)


@auth_bp.route("/reset_password", methods=["GET", "POST"], endpoint="reset_request")
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))

    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        send_reset_email(user)
        flash("Hệ thống đã gửi email đặt lại mật khẩu. Vui lòng kiểm tra hộp thư.", "success")
        return redirect(url_for("auth.login"))

    return render_template("reset_request.html", title="Reset Password", form=form)


@auth_bp.route("/reset_password/<token>", methods=["GET", "POST"], endpoint="reset_token")
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.home"))

    s = get_serializer()

    try:
        data = s.loads(token, max_age=1800)
        user_id = data["user_id"]
    except Exception:
        flash("Token không hợp lệ hoặc đã hết hạn.", "warning")
        return redirect(url_for("auth.reset_request"))

    user = User.query.get(user_id)
    if user is None:
        flash("Không tìm thấy người dùng.", "warning")
        return redirect(url_for("auth.reset_request"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        hashed_pw = bcrypt.generate_password_hash(form.password.data).decode("utf-8")
        user.password = hashed_pw
        db.session.commit()
        flash("Mật khẩu đã được cập nhật! Hãy đăng nhập.", "success")
        return redirect(url_for("auth.login"))

    return render_template("reset_token.html", title="Reset Password", form=form)
