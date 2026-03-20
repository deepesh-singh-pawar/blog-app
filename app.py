import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, request, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user,
    logout_user, login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

# ── App setup ────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///blog.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to continue."

# ── Models ────────────────────────────────────────────────────────────────────
post_tags = db.Table(
    "post_tags",
    db.Column("post_id", db.Integer, db.ForeignKey("post.id")),
    db.Column("tag_id",  db.Integer, db.ForeignKey("tag.id")),
)


class User(UserMixin, db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80),  unique=True, nullable=False)
    email         = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    posts         = db.relationship("Post",    back_populates="author", cascade="all, delete")
    comments      = db.relationship("Comment", back_populates="author", cascade="all, delete")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"


class Post(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title        = db.Column(db.String(200), nullable=False)
    slug         = db.Column(db.String(200), unique=True, nullable=False)
    content      = db.Column(db.Text, nullable=False)
    status       = db.Column(db.String(20), default="draft")   # draft | published
    published_at = db.Column(db.DateTime)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    author       = db.relationship("User",    back_populates="posts")
    comments     = db.relationship("Comment", back_populates="post", cascade="all, delete")
    tags         = db.relationship("Tag",     secondary=post_tags, back_populates="posts")

    def __repr__(self):
        return f"<Post {self.title}>"


class Comment(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    post_id    = db.Column(db.Integer, db.ForeignKey("post.id"), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    body       = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    post       = db.relationship("Post", back_populates="comments")
    author     = db.relationship("User", back_populates="comments")

    def __repr__(self):
        return f"<Comment by {self.author.username}>"


class Tag(db.Model):
    id    = db.Column(db.Integer, primary_key=True)
    name  = db.Column(db.String(50), unique=True, nullable=False)
    slug  = db.Column(db.String(50), unique=True, nullable=False)
    posts = db.relationship("Post", secondary=post_tags, back_populates="tags")

    def __repr__(self):
        return f"<Tag {self.name}>"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ── Helper ────────────────────────────────────────────────────────────────────
def make_slug(title):
    import re
    slug = title.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    slug = re.sub(r"^-+|-+$", "", slug)
    # ensure uniqueness
    base, n = slug, 1
    while Post.query.filter_by(slug=slug).first():
        slug = f"{base}-{n}"
        n += 1
    return slug


# ── Routes: Auth ──────────────────────────────────────────────────────────────
@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form["username"].strip()
        email    = request.form["email"].strip().lower()
        password = request.form["password"]

        if User.query.filter_by(username=username).first():
            flash("Username already taken.", "error")
        elif User.query.filter_by(email=email).first():
            flash("Email already registered.", "error")
        elif len(password) < 6:
            flash("Password must be at least 6 characters.", "error")
        else:
            user = User(username=username, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("Account created! Please log in.", "success")
            return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    if request.method == "POST":
        email    = request.form["email"].strip().lower()
        password = request.form["password"]
        user     = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            next_page = request.args.get("next")
            return redirect(next_page or url_for("index"))
        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


# ── Routes: Posts ─────────────────────────────────────────────────────────────
@app.route("/")
def index():
    page  = request.args.get("page", 1, type=int)
    posts = (
        Post.query
        .filter_by(status="published")
        .order_by(Post.published_at.desc())
        .paginate(page=page, per_page=5, error_out=False)
    )
    return render_template("index.html", posts=posts)


@app.route("/post/<slug>")
def post_detail(slug):
    # This is the ONE database call per request the user asked about
    post = Post.query.filter_by(slug=slug, status="published").first_or_404()
    return render_template("post_detail.html", post=post)


@app.route("/post/new", methods=["GET", "POST"])
@login_required
def post_create():
    if request.method == "POST":
        title   = request.form["title"].strip()
        content = request.form["content"].strip()
        status  = request.form.get("status", "draft")

        if not title or not content:
            flash("Title and content are required.", "error")
        else:
            post = Post(
                title=title,
                slug=make_slug(title),
                content=content,
                status=status,
                user_id=current_user.id,
                published_at=datetime.utcnow() if status == "published" else None,
            )
            db.session.add(post)
            db.session.commit()
            flash("Post created!", "success")
            return redirect(url_for("post_detail", slug=post.slug))

    return render_template("post_form.html", post=None)


@app.route("/post/<int:post_id>/edit", methods=["GET", "POST"])
@login_required
def post_edit(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id:
        abort(403)

    if request.method == "POST":
        post.title   = request.form["title"].strip()
        post.content = request.form["content"].strip()
        old_status   = post.status
        post.status  = request.form.get("status", "draft")
        if post.status == "published" and old_status != "published":
            post.published_at = datetime.utcnow()
        db.session.commit()
        flash("Post updated!", "success")
        return redirect(url_for("post_detail", slug=post.slug))

    return render_template("post_form.html", post=post)


@app.route("/post/<int:post_id>/delete", methods=["POST"])
@login_required
def post_delete(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash("Post deleted.", "success")
    return redirect(url_for("index"))


# ── Routes: Comments ──────────────────────────────────────────────────────────
@app.route("/post/<int:post_id>/comment", methods=["POST"])
@login_required
def comment_add(post_id):
    post = Post.query.get_or_404(post_id)
    body = request.form["body"].strip()
    if not body:
        flash("Comment cannot be empty.", "error")
    else:
        comment = Comment(post_id=post.id, user_id=current_user.id, body=body)
        db.session.add(comment)
        db.session.commit()
        flash("Comment added!", "success")
    return redirect(url_for("post_detail", slug=post.slug))


@app.route("/comment/<int:comment_id>/delete", methods=["POST"])
@login_required
def comment_delete(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.user_id != current_user.id:
        abort(403)
    slug = comment.post.slug
    db.session.delete(comment)
    db.session.commit()
    flash("Comment deleted.", "success")
    return redirect(url_for("post_detail", slug=slug))


# ── Routes: Tags ──────────────────────────────────────────────────────────────
@app.route("/tag/<slug>")
def tag_posts(slug):
    tag   = Tag.query.filter_by(slug=slug).first_or_404()
    posts = [p for p in tag.posts if p.status == "published"]
    return render_template("tag_posts.html", tag=tag, posts=posts)


# ── Health check ──────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    return {"status": "ok", "db": "sqlite"}


# ── DB init + seed data ───────────────────────────────────────────────────────
def seed():
    """Create demo user and two posts on first run."""
    if User.query.count():
        return
    demo = User(username="demo", email="demo@example.com")
    demo.set_password("password123")
    db.session.add(demo)
    db.session.flush()

    tag_py  = Tag(name="Python", slug="python")
    tag_web = Tag(name="Web",    slug="web")
    db.session.add_all([tag_py, tag_web])

    p1 = Post(
        title="Welcome to the Blog",
        slug="welcome-to-the-blog",
        content=(
            "This is a fully working Flask blog application with a SQLite database.\n\n"
            "Features:\n"
            "- Register and log in\n"
            "- Create, edit, and delete posts\n"
            "- Comment on posts\n"
            "- Tag support\n"
            "- Pagination on the homepage\n\n"
            "Use the demo account (demo@example.com / password123) to explore."
        ),
        status="published",
        user_id=demo.id,
        published_at=datetime.utcnow(),
        tags=[tag_py, tag_web],
    )
    p2 = Post(
        title="Getting Started with Python",
        slug="getting-started-with-python",
        content=(
            "Python is a great first programming language.\n\n"
            "Install Python from python.org, open a terminal, and type:\n\n"
            "    print('Hello, world!')\n\n"
            "That is all you need to get started!"
        ),
        status="published",
        user_id=demo.id,
        published_at=datetime.utcnow(),
        tags=[tag_py],
    )
    db.session.add_all([p1, p2])
    db.session.commit()
    print("✅ Seed data created — log in with demo@example.com / password123")


with app.app_context():
    db.create_all()
    seed()


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=5000)
