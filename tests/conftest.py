import pytest
from app import create_app, db
from app.models.user import User


@pytest.fixture
def app():
    """Создает экземпляр приложения для тестов."""
    # Вызываем твою функцию инициализации
    app = create_app()

    # Переопределяем настройки для тестов
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",  # База в оперативной памяти
        "WTF_CSRF_ENABLED": False,  # Отключаем CSRF, чтобы не мучиться с токенами в POST-запросах
    })

    with app.app_context():
        # Создаем таблицы в тестовой БД
        db.create_all()

        yield app  # В этот момент запускаются сами тесты

        # Убираем за собой
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Тестовый клиент для имитации браузера (отправки GET и POST запросов)."""
    return app.test_client()


@pytest.fixture
def logged_in_client(client, app):
    """Тестовый клиент, который уже авторизован. Пригодится для закрытых маршрутов."""
    with app.app_context():
        # Создаем фейкового юзера
        test_user = User(name="Test", email="test@example.com")
        test_user.set_password("12345")
        db.session.add(test_user)
        db.session.commit()

        # Логиним его через твой маршрут /login
        client.post('/login', data={
            'email': 'test@example.com',
            'password': '12345'
        })

    return client