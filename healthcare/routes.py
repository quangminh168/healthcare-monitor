import os
import secrets
from datetime import timedelta, timezone

from PIL import Image
from flask import render_template, url_for, flash, redirect, request, jsonify, abort
from healthcare.form import RegistrationForm, LoginForm, PostForm,UpdateAccountForm
from healthcare import app, db, bcrypt
from healthcare.models import User, Post, HeartRateData
from flask_login import login_user, logout_user, login_required, current_user
import time, random



@app.route("/")
@login_required
def home():
    posts = Post.query.filter_by(user_id=current_user.id).order_by(Post.date_posted.desc()).all()
    return render_template("home.html", title="Trang chủ", posts=posts)

@app.route("/about")
def about():
    return render_template("about.html", title="About")

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash(f"Account created for {form.username.data}!", "success")
        return redirect(url_for("login"))
    return render_template('register.html', title='Register', form=form)

@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for("home"))
        else:
            flash("Login unsuccessful. Please check email or password", "danger")
    return render_template('login.html', title='Login', form=form)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("home"))

def save_picture(form_picture):
    random_hex = secrets.token_hex(8)
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_fn = random_hex + f_ext
    picture_path = os.path.join(app.root_path, 'static/profile_pics', picture_fn)
    output_size = (125, 125)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)
    return picture_fn


@app.route("/account",methods=["GET","POST"])
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
        return redirect(url_for("account"))
    elif request.method == "GET":
        form.username.data = current_user.username
        form.email.data = current_user.email
    image_file = url_for('static', filename='profile_pics/' + current_user.image_file   )
    return render_template("account.html", title="Account", image_file=image_file,form=form)

@app.route("/post/new",methods=["GET","POST"])
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
        flash("Hồ sơ bệnh nhân đã được lưu!", "success")
        return redirect(url_for("home"))
    return render_template("create_post.html", title="Hồ sơ bệnh nhân mới", form=form, legend="Thêm hồ sơ bệnh nhân")

@app.route("/post/<int:post_id>",methods=["GET","POST"])
@login_required
def post(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template("post.html", title=post.patient_name, post=post)


@app.route("/post/<int:post_id>/update", methods=["GET", "POST"])
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
        post.device_id = form.device_id.data  # ✅ thêm dòng này
        db.session.commit()
        flash("Thông tin bệnh nhân đã được cập nhật!", "success")
        return redirect(url_for("home"))

    elif request.method == "GET":
        form.patient_name.data = post.patient_name
        form.age.data = post.age
        form.gender.data = post.gender
        form.condition.data = post.condition
        form.notes.data = post.notes
        form.device_id.data = post.device_id

    return render_template("create_post.html", title="Cập nhật hồ sơ", form=form, legend="Cập nhật hồ sơ")


@app.route("/post/<int:post_id>/delete",methods=["POST"])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash("Your post has been deleted!", "success")
    return redirect(url_for("home"))

@app.route("/heartbeat/latest/<string:device_id>")
def heartbeat_latest(device_id):
    last_data = HeartRateData.query.filter_by(device_id=device_id).order_by(HeartRateData.timestamp.desc()).first()
    print(f" Gửi dữ liệu đến web từ {device_id}")
    if last_data:
        ts = last_data.timestamp.astimezone(timezone.utc)
        return jsonify({
            "timestamp_iso": ts.isoformat(),  # e.g. "2025-10-18T15:03:20.123456+00:00"
            "timestamp_ms": int(ts.timestamp() * 1000),  # epoch in milliseconds
            "bpm": last_data.heart_rate,
            "spo2": last_data.spo2
        })
    else:
        return jsonify({"timestamp_iso": None, "timestamp_ms": 0, "bpm": 0, "spo2": 0})

@app.route("/api/heartbeat", methods=["POST"])
def receive_heartbeat():
    try:
        data = request.get_json()
        print("📡 Nhận từ ESP:", data)

        if not data or "device_id" not in data or "heart_rate" not in data or "spo2" not in data:
            print(" Thiếu dữ liệu hoặc sai định dạng:", data)
            return jsonify({"error": "Invalid data"}), 400

        new_data = HeartRateData(
            device_id=data.get("device_id", "unknown"),
            heart_rate=data.get("heart_rate", 0),
            spo2=data.get("spo2", 0)
        )
        db.session.add(new_data)
        db.session.commit()

        # Xóa dữ liệu cũ, chỉ giữ 100 bản ghi gần nhất
        total = HeartRateData.query.count()
        if total > 100:
            old = HeartRateData.query.order_by(HeartRateData.timestamp.asc()).limit(total - 100)
            for row in old:
                db.session.delete(row)
            db.session.commit()

        return jsonify({"message": "Data saved"}), 201

    except Exception as e:
        print(" Lỗi khi lưu dữ liệu:", e)
        return jsonify({"error": str(e)}), 500


