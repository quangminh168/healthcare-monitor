import os
import secrets
from datetime import timedelta, timezone

from PIL import Image
from flask import render_template, url_for, flash, redirect, request, jsonify, abort
from healthcare.form import (
    RegistrationForm,
    LoginForm,
    PostForm,
    UpdateAccountForm,
    RequestResetForm,
    ResetPasswordForm
)

from healthcare import app, db, bcrypt
from healthcare.models import User, Post, HeartRateData
from flask_login import login_user, logout_user, login_required, current_user
import time, random
from itsdangerous import URLSafeTimedSerializer as Serializer
from flask_mail import Message
from healthcare import mail
from flask import current_app
import joblib
import numpy as np

model = joblib.load("patient_model.pkl")



@app.route("/")
@login_required
def home():
    page = request.args.get('page', 1, type=int)
    sort = request.args.get("filter", "newest")

    query = Post.query.filter_by(user_id=current_user.id)

    # Sắp xếp
    if sort == "risk":
        query = query.order_by(Post.risk.desc())
    else:
        query = query.order_by(Post.date_posted.desc())

    posts = query.paginate(page=page, per_page=5)
    return render_template("home.html", title="Trang chủ", posts=posts, filter=sort)



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

@app.route("/post/new", methods=["GET", "POST"])
@login_required
def new_post():
    form = PostForm()
    if form.validate_on_submit():
        # 1) Tạo Post bình thường
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

        # 2) Tạo 100 nhịp tim ngẫu nhiên mô phỏng dữ liệu IoT
        bpm_data = [random.randint(60, 100) for _ in range(100)]
        spo2_data = [random.randint(93, 100) for _ in range(100)]
        for i in range(100):
            hr = HeartRateData(
                device_id=form.device_id.data,
                heart_rate=bpm_data[i],
                spo2=spo2_data[i]
            )
            db.session.add(hr)
        db.session.commit()  # commit xong trước khi tính features

        # 3) Tính feature và dự đoán risk
        X = calculate_features(post.id)
        print("DEBUG X:", X)
        predicted_risk = model.predict_proba(X)[0][1]
        print("DEBUG predicted_risk:", predicted_risk)
        post.risk = float(predicted_risk)  # lưu chính xác
        db.session.commit()

        flash(f"Hồ sơ bệnh nhân đã được lưu! Nguy cơ bệnh: {post.risk*100:.2f}%", "success")
        return redirect(url_for("home"))

    return render_template(
        "create_post.html",
        title="Hồ sơ bệnh nhân mới",
        form=form,
        legend="Thêm hồ sơ bệnh nhân"
    )



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
        X = calculate_features(post.id)
        post.risk = round(model.predict_proba(X)[0][1], 2)
        db.session.commit()

        flash(f"Thông tin bệnh nhân đã được cập nhật! Nguy cơ bệnh: {post.risk * 100:.2f}%", "success")
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
        print(" Nhận từ ESP:", data)

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


def get_serializer():
    return Serializer(current_app.config['SECRET_KEY'])

def send_reset_email(user):
    s = get_serializer()
    token = s.dumps({'user_id': user.id})

    msg = Message("Reset Your Password",
                  sender=current_app.config['MAIL_USERNAME'],
                  recipients=[user.email])

    msg.body = f'''Để đặt lại mật khẩu, click vào link sau:
{url_for('reset_token', token=token, _external=True)}

Nếu bạn không yêu cầu, hãy bỏ qua email này.
'''
    mail.send(msg)
@app.route("/reset_password", methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    form = RequestResetForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        # user chắc chắn tồn tại vì validator đã check
        send_reset_email(user)
        flash("Hệ thống đã gửi email đặt lại mật khẩu. Vui lòng kiểm tra hộp thư.", "success")
        return redirect(url_for('login'))

    return render_template('reset_request.html', title='Reset Password', form=form)



@app.route("/reset_password/<token>", methods=['GET','POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    s = get_serializer()

    try:
        data = s.loads(token, max_age=1800)      # 30 phút
        user_id = data['user_id']
    except:
        flash("Token không hợp lệ hoặc đã hết hạn.", "warning")
        return redirect(url_for('reset_request'))

    user = User.query.get(user_id)
    if user is None:
        flash("Không tìm thấy người dùng.", "warning")
        return redirect(url_for('reset_request'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        hashed_pw = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user.password = hashed_pw
        db.session.commit()
        flash("Mật khẩu đã được cập nhật! Hãy đăng nhập.", "success")
        return redirect(url_for('login'))

    return render_template('reset_token.html', title='Reset Password', form=form)


@app.route("/heartbeat/all/<string:device_id>")
def heartbeat_all(device_id):
    data_rows = HeartRateData.query.filter_by(device_id=device_id).order_by(HeartRateData.timestamp.asc()).all()
    result = []
    for row in data_rows:
        ts = row.timestamp.astimezone(timezone.utc)
        result.append({
            "timestamp_ms": int(ts.timestamp()*1000),
            "bpm": row.heart_rate,
            "spo2": row.spo2
        })
    return jsonify(result)


def encode_gender(gender):
    g = gender.lower()
    if g in ["nam", "male", "m"]:
        return 1
    return 0



def calculate_features(post_id):
    post = Post.query.get(post_id)
    hr_data = HeartRateData.query.filter_by(device_id=post.device_id).all()

    if not hr_data:
        avg_bpm = 0
        avg_spo2 = 0
    else:
        avg_bpm = sum([d.heart_rate for d in hr_data]) / len(hr_data)
        avg_spo2 = sum([d.spo2 for d in hr_data]) / len(hr_data)

    X = np.array([[post.age, encode_gender(post.gender), avg_bpm, avg_spo2]])
    return X
