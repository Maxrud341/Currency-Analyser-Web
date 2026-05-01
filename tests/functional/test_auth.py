from app.models.user import User
from app import db


def test_register_get(client):
    """Ověřuje, že se otevře registrační stránka (GET požadavek)"""
    response = client.get('/register')
    assert response.status_code == 200


def test_register_success(client, app):
    """Ověřuje úspěšnou registraci nového uživatele"""
    data = {
        "name": "Jan Novak",
        "email": "jan@example.com",
        "password": "secure123",
        "confirm_password": "secure123"
    }
    response = client.post('/register', data=data, follow_redirects=True)

    assert response.status_code == 200
    assert b"Registrace byla" in response.data

    with app.app_context():
        user = User.query.filter_by(email="jan@example.com").first()
        assert user is not None
        assert user.name == "Jan Novak"


def test_register_password_mismatch(client, app):
    """Ověřuje chybu při neshodě hesel"""
    data = {
        "name": "Petr",
        "email": "petr@example.com",
        "password": "123",
        "confirm_password": "321"
    }
    response = client.post('/register', data=data, follow_redirects=True)

    assert b"Hesla se neshoduj" in response.data

    with app.app_context():
        assert User.query.filter_by(email="petr@example.com").first() is None


def test_register_existing_user(client, app):
    """Ověřuje pokus o registraci s již obsazeným emailem"""
    with app.app_context():
        existing_user = User(name="Old User", email="exist@example.com")
        existing_user.set_password("123")
        db.session.add(existing_user)
        db.session.commit()

    data = {
        "name": "New User",
        "email": "exist@example.com",
        "password": "abc",
        "confirm_password": "abc"
    }
    response = client.post('/register', data=data, follow_redirects=True)

    assert b"ji\xc5\xbe existuje" in response.data


def test_login_get(client):
    """Ověřuje, že se otevře přihlašovací stránka"""
    response = client.get('/login')
    assert response.status_code == 200


def test_login_success(client, app):
    """Ověřuje úspěšné přihlášení do systému"""
    with app.app_context():
        user = User(name="Test", email="login@example.com")
        user.set_password("correct_password")
        db.session.add(user)
        db.session.commit()

    data = {
        "email": "login@example.com",
        "password": "correct_password"
    }
    response = client.post('/login', data=data, follow_redirects=False)

    assert response.status_code == 302
    assert response.location.endswith('/')


def test_login_invalid_password(client, app):
    """Ověřuje chybu při nesprávném hesle"""
    with app.app_context():
        user = User(name="Test", email="wrongpass@example.com")
        user.set_password("correct_password")
        db.session.add(user)
        db.session.commit()

    data = {
        "email": "wrongpass@example.com",
        "password": "WRONG_password"
    }
    response = client.post('/login', data=data, follow_redirects=True)

    assert b"Neplatn\xc3\xbd e-mail nebo heslo" in response.data


def test_already_logged_in_redirects(logged_in_client):
    """Ověřuje přesměrování přihlášeného uživatele z /login na hlavní stránku"""
    response = logged_in_client.get('/login', follow_redirects=False)
    assert response.status_code == 302
    assert response.location.endswith('/')


def test_logout(logged_in_client):
    """Ověřuje funkci odhlášení"""
    response = logged_in_client.get('/logout', follow_redirects=False)

    assert response.status_code == 302
    assert response.location.endswith('/')


def test_logout_unauthorized(client):
    """Ověřuje odmítnutí neautorizovaného uživatele bez relace (login_required)"""
    response = client.get('/logout', follow_redirects=False)
    assert response.status_code in [302, 401]


def test_switch_user(logged_in_client):
    """Ověřuje vyčištění relace a přesměrování na přihlášení"""
    response = logged_in_client.get('/switch-user', follow_redirects=False)
    assert response.status_code == 302
    assert '/login' in response.location