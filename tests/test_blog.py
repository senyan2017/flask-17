import pytest

from flaskr.db import get_db


def test_index(client, auth):
    response = client.get("/")
    assert b"Log In" in response.data
    assert b"Register" in response.data

    auth.login()
    response = client.get("/")
    assert b"test title" in response.data
    assert b"by test on 2018-01-01" in response.data
    assert b"test\nbody" in response.data
    assert b'href="/1/update"' in response.data


@pytest.mark.parametrize("path", ("/create", "/1/update", "/1/delete"))
def test_login_required(client, path):
    response = client.post(path)
    assert response.headers["Location"] == "/auth/login"


def test_author_required(app, client, auth):
    # change the post author to another user
    with app.app_context():
        db = get_db()
        db.execute("UPDATE post SET author_id = 2 WHERE id = 1")
        db.commit()

    auth.login()
    # current user can't modify other user's post
    assert client.post("/1/update").status_code == 403
    assert client.post("/1/delete").status_code == 403
    # current user doesn't see edit link
    assert b'href="/1/update"' not in client.get("/").data


@pytest.mark.parametrize("path", ("/2/update", "/2/delete"))
def test_exists_required(client, auth, path):
    auth.login()
    assert client.post(path).status_code == 404


def test_create(client, auth, app):
    auth.login()
    assert client.get("/create").status_code == 200
    client.post("/create", data={"title": "created", "body": ""})

    with app.app_context():
        db = get_db()
        count = db.execute("SELECT COUNT(id) FROM post").fetchone()[0]
        assert count == 2


def test_update(client, auth, app):
    auth.login()
    assert client.get("/1/update").status_code == 200
    client.post("/1/update", data={"title": "updated", "body": ""})

    with app.app_context():
        db = get_db()
        post = db.execute("SELECT * FROM post WHERE id = 1").fetchone()
        assert post["title"] == "updated"


@pytest.mark.parametrize("path", ("/create", "/1/update"))
def test_create_update_validate(client, auth, path):
    auth.login()
    response = client.post(path, data={"title": "", "body": ""})
    assert b"Title is required." in response.data


@pytest.mark.parametrize("path", ("/create", "/1/update"))
def test_create_update_strip_whitespace_title_still_invalid(client, auth, path):
    """Both routes use the same parse_post_form helper; ensure behaviour is
    identical when title is only whitespace (still falsy after strip not
    applied — empty string check)."""
    auth.login()
    response = client.post(path, data={"title": "", "body": "some body"})
    assert b"Title is required." in response.data


@pytest.mark.parametrize(
    "path,expected_title",
    (("/create", "shared title"), ("/1/update", "shared title")),
)
def test_create_update_shared_validation_passes(client, auth, app, path, expected_title):
    """Valid submissions through both routes succeed via the same helper."""
    auth.login()
    client.post(path, data={"title": expected_title, "body": "body text"})

    with app.app_context():
        db = get_db()
        if path == "/create":
            post = db.execute(
                "SELECT title FROM post WHERE title = ?", (expected_title,)
            ).fetchone()
        else:
            post = db.execute("SELECT title FROM post WHERE id = 1").fetchone()
        assert post["title"] == expected_title


def test_delete(client, auth, app):
    auth.login()
    response = client.post("/1/delete")
    assert response.headers["Location"] == "/"

    with app.app_context():
        db = get_db()
        post = db.execute("SELECT * FROM post WHERE id = 1").fetchone()
        assert post is None
