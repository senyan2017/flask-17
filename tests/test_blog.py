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


def test_delete(client, auth, app):
    auth.login()
    response = client.post("/1/delete")
    assert response.headers["Location"] == "/"

    with app.app_context():
        db = get_db()
        post = db.execute("SELECT * FROM post WHERE id = 1").fetchone()
        assert post is None


def _add_post(app, title, body, author_id, created):
    """Insert an extra post so filtering has something to work with."""
    with app.app_context():
        db = get_db()
        db.execute(
            "INSERT INTO post (title, body, author_id, created)"
            " VALUES (?, ?, ?, ?)",
            (title, body, author_id, created),
        )
        db.commit()


def test_index_filter_by_keyword(client, auth, app):
    auth.login()
    _add_post(app, "python tips", "all about snakes", 1, "2018-02-01 00:00:00")

    # keyword found in the title
    response = client.get("/?q=python")
    assert b"python tips" in response.data
    assert b"test title" not in response.data

    # keyword found in the body
    response = client.get("/?q=snakes")
    assert b"python tips" in response.data
    assert b"test title" not in response.data

    # no keyword shows every post
    response = client.get("/")
    assert b"python tips" in response.data
    assert b"test title" in response.data


def test_index_filter_by_author(client, auth, app):
    auth.login()
    _add_post(app, "other post", "written by other", 2, "2018-03-01 00:00:00")

    # only the "test" author's posts
    response = client.get("/?author=test")
    assert b"test title" in response.data
    assert b"other post" not in response.data

    # only the "other" author's posts
    response = client.get("/?author=other")
    assert b"other post" in response.data
    assert b"test title" not in response.data


def test_index_filter_no_results(client, auth):
    auth.login()
    response = client.get("/?q=zzzznomatch")
    assert b"No posts match your filter." in response.data
    assert b"test title" not in response.data
