from app.models.user import User
from app import db


# --- ТЕСТЫ РЕГИСТРАЦИИ (/register) ---

def test_register_get(client):
    """Проверяем, что страница регистрации открывается (GET-запрос)"""
    response = client.get('/register')
    assert response.status_code == 200


def test_register_success(client, app):
    """Проверяем успешную регистрацию нового пользователя"""
    data = {
        "name": "Jan Novak",
        "email": "jan@example.com",
        "password": "secure123",
        "confirm_password": "secure123"
    }
    response = client.post('/register', data=data, follow_redirects=True)

    # Проверяем, что мы перешли на главную и увидели flash сообщение
    assert response.status_code == 200
    assert b"Registrace byla" in response.data

    # Проверяем, что пользователь реально появился в базе данных
    with app.app_context():
        user = User.query.filter_by(email="jan@example.com").first()
        assert user is not None
        assert user.name == "Jan Novak"


def test_register_password_mismatch(client, app):
    """Проверяем ошибку при несовпадении паролей"""
    data = {
        "name": "Petr",
        "email": "petr@example.com",
        "password": "123",
        "confirm_password": "321"  # Пароли разные
    }
    response = client.post('/register', data=data, follow_redirects=True)

    assert b"Hesla se neshoduj" in response.data  # Проверяем flash сообщение

    # В базе не должно быть этого пользователя
    with app.app_context():
        assert User.query.filter_by(email="petr@example.com").first() is None


def test_register_existing_user(client, app):
    """Проверяем попытку регистрации с уже занятым email"""
    # Сначала создаем пользователя напрямую
    with app.app_context():
        existing_user = User(name="Old User", email="exist@example.com")
        existing_user.set_password("123")
        db.session.add(existing_user)
        db.session.commit()

    # Пытаемся зарегистрировать такого же
    data = {
        "name": "New User",
        "email": "exist@example.com",
        "password": "abc",
        "confirm_password": "abc"
    }
    response = client.post('/register', data=data, follow_redirects=True)

    assert b"ji\xc5\xbe existuje" in response.data  # "již existuje" в байтах


# --- ТЕСТЫ АВТОРИЗАЦИИ (/login) ---

def test_login_get(client):
    """Проверяем, что страница логина открывается"""
    response = client.get('/login')
    assert response.status_code == 200


def test_login_success(client, app):
    """Проверяем успешный вход в систему"""
    # Создаем пользователя для теста
    with app.app_context():
        user = User(name="Test", email="login@example.com")
        user.set_password("correct_password")
        db.session.add(user)
        db.session.commit()

    data = {
        "email": "login@example.com",
        "password": "correct_password"
    }
    # follow_redirects=False позволяет проверить статус 302 (перенаправление)
    response = client.post('/login', data=data, follow_redirects=False)

    # После успешного логина должен быть редирект на главную (index)
    assert response.status_code == 302
    assert response.location.endswith('/')  # Куда редиректит url_for("main.index")


def test_login_invalid_password(client, app):
    """Проверяем ошибку при неверном пароле"""
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

    assert b"Neplatn\xc3\xbd e-mail nebo heslo" in response.data  # "Neplatný e-mail nebo heslo"


def test_already_logged_in_redirects(logged_in_client):
    """Если авторизованный пользователь заходит на /login, его должно кинуть на главную"""
    response = logged_in_client.get('/login', follow_redirects=False)
    assert response.status_code == 302
    assert response.location.endswith('/')


# --- ТЕСТЫ ВЫХОДА (/logout) ---

def test_logout(logged_in_client):
    """Проверяем функцию выхода"""
    # logged_in_client уже авторизован благодаря фикстуре в conftest.py
    response = logged_in_client.get('/logout', follow_redirects=False)

    assert response.status_code == 302
    assert response.location.endswith('/')


def test_logout_unauthorized(client):
    """Неавторизованного пользователя без сессии должно откинуть (login_required)"""
    response = client.get('/logout', follow_redirects=False)
    # login_required обычно кидает 302 на страницу логина или 401 Unauthorized
    assert response.status_code in [302, 401]


# --- ТЕСТЫ СМЕНЫ ПОЛЬЗОВАТЕЛЯ (/switch-user) ---

def test_switch_user(logged_in_client):
    """Проверяем очистку сессии и редирект на логин"""
    response = logged_in_client.get('/switch-user', follow_redirects=False)
    assert response.status_code == 302
    assert '/login' in response.location