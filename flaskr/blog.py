from flask import Blueprint
from flask import flash
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for
from werkzeug.exceptions import abort

from .auth import login_required
from .db import get_db

bp = Blueprint("blog", __name__)


@bp.route("/")
def index():
    """Show all the posts, most recent first."""
    db = get_db()
    posts = db.execute(
        "SELECT p.id, title, body, created, author_id, username"
        " FROM post p JOIN user u ON p.author_id = u.id"
        " ORDER BY created DESC"
    ).fetchall()
    return render_template("blog/index.html", posts=posts)


def get_post(id, check_author=True):
    """Get a post and its author by id.

    Checks that the id exists and optionally that the current user is
    the author.

    :param id: id of post to get
    :param check_author: require the current user to be the author
    :return: the post with author information
    :raise 404: if a post with the given id doesn't exist
    :raise 403: if the current user isn't the author
    """
    post = (
        get_db()
        .execute(
            "SELECT p.id, title, body, created, author_id, username"
            " FROM post p JOIN user u ON p.author_id = u.id"
            " WHERE p.id = ?",
            (id,),
        )
        .fetchone()
    )

    if post is None:
        abort(404, f"Post id {id} doesn't exist.")

    if check_author and post["author_id"] != g.user["id"]:
        abort(403)

    return post


def _validate_post(title):
    """Return an error message if the submitted post is invalid.

    Every blog post form shares these rules, so new validation belongs
    here instead of being copied into each route.

    :param title: the submitted post title
    :return: an error message, or ``None`` when the post is valid
    """
    if not title:
        return "Title is required."

    return None


def _handle_post_form(save):
    """Run the form flow shared by creating and updating a post.

    Reads the submitted fields, validates them, and persists the post
    through ``save`` when it is valid.

    :param save: callable taking ``(title, body)`` that writes the post
    :return: a redirect response after a successful save, or ``None``
        when the caller should render the form (a GET request, or a
        validation error that has already been flashed)
    """
    if request.method != "POST":
        return None

    title = request.form["title"]
    body = request.form["body"]
    error = _validate_post(title)

    if error is not None:
        flash(error)
        return None

    save(title, body)
    return redirect(url_for("blog.index"))


@bp.route("/create", methods=("GET", "POST"))
@login_required
def create():
    """Create a new post for the current user."""

    def save(title, body):
        db = get_db()
        db.execute(
            "INSERT INTO post (title, body, author_id) VALUES (?, ?, ?)",
            (title, body, g.user["id"]),
        )
        db.commit()

    response = _handle_post_form(save)
    if response is not None:
        return response

    return render_template("blog/create.html")


@bp.route("/<int:id>/update", methods=("GET", "POST"))
@login_required
def update(id):
    """Update a post if the current user is the author."""
    post = get_post(id)

    def save(title, body):
        db = get_db()
        db.execute(
            "UPDATE post SET title = ?, body = ? WHERE id = ?", (title, body, id)
        )
        db.commit()

    response = _handle_post_form(save)
    if response is not None:
        return response

    return render_template("blog/update.html", post=post)


@bp.route("/<int:id>/delete", methods=("POST",))
@login_required
def delete(id):
    """Delete a post.

    Ensures that the post exists and that the logged in user is the
    author of the post.
    """
    get_post(id)
    db = get_db()
    db.execute("DELETE FROM post WHERE id = ?", (id,))
    db.commit()
    return redirect(url_for("blog.index"))
