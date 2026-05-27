import random
from flask import Blueprint, render_template, url_for, flash, redirect, request, abort
from healthcare import db
from healthcare.models import Post, HeartRateData
from healthcare.form import PostForm
from healthcare.ml_service import predict_risk
from flask_login import login_required, current_user

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/", endpoint="home")
@login_required
def home():
    page = request.args.get("page", 1, type=int)
    sort = request.args.get("filter", "newest")

    query = Post.query.filter_by(user_id=current_user.id)

    if sort == "risk":
        query = query.order_by(Post.risk.desc())
    else:
        query = query.order_by(Post.date_posted.desc())

    posts = query.paginate(page=page, per_page=5)
    return render_template("home.html", title="Trang chủ", posts=posts, filter=sort)


@dashboard_bp.route("/about", endpoint="about")
def about():
    return render_template("about.html", title="About")


@dashboard_bp.route("/post/new", methods=["GET", "POST"], endpoint="new_post")
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
            author=current_user,
        )
        db.session.add(post)
        db.session.commit()
        if post.device_id != "esp8266-01":
            bpm_data = [random.randint(60, 100) for _ in range(100)]
            spo2_data = [random.randint(93, 100) for _ in range(100)]
            for i in range(100):
                hr = HeartRateData(
                    device_id=form.device_id.data,
                    heart_rate=bpm_data[i],
                    spo2=spo2_data[i],
                )
                db.session.add(hr)
            db.session.commit()

        post.risk = predict_risk(post.id)
        db.session.commit()

        flash(f"Hồ sơ bệnh nhân đã được lưu! Nguy cơ bệnh: {post.risk*100:.2f}%", "success")
        return redirect(url_for("dashboard.home"))

    return render_template(
        "create_post.html",
        title="Hồ sơ bệnh nhân mới",
        form=form,
        legend="Thêm hồ sơ bệnh nhân",
    )


@dashboard_bp.route("/post/<int:post_id>", endpoint="post")
@login_required
def post(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template("post.html", title=post.patient_name, post=post)


@dashboard_bp.route("/post/<int:post_id>/update", methods=["GET", "POST"], endpoint="update_post")
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
        post.risk = predict_risk(post.id)
        db.session.commit()

        flash(f"Thông tin bệnh nhân đã được cập nhật! Nguy cơ bệnh: {post.risk * 100:.2f}%", "success")
        return redirect(url_for("dashboard.home"))
    elif request.method == "GET":
        form.patient_name.data = post.patient_name
        form.age.data = post.age
        form.gender.data = post.gender
        form.condition.data = post.condition
        form.notes.data = post.notes
        form.device_id.data = post.device_id

    return render_template("create_post.html", title="Cập nhật hồ sơ", form=form, legend="Cập nhật hồ sơ")


@dashboard_bp.route("/post/<int:post_id>/delete", methods=["POST"], endpoint="delete_post")
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash("Your post has been deleted!", "success")
    return redirect(url_for("dashboard.home"))
