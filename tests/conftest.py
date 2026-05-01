import pytest
from app import create_app, db
from app.models.user import User


@pytest.fixture
def app():
    """Vytvoří instanci aplikace pro testy."""
    app = create_app()

    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
    })

    with app.app_context():
        db.create_all()

        yield app

        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Testovací klient pro simulaci prohlížeče (odesílání požadavků GET a POST)."""
    return app.test_client()


@pytest.fixture
def logged_in_client(client, app):
    """Testovací klient, který je již autorizován. Hodí se pro chráněné trasy."""
    with app.app_context():
        test_user = User(name="Test", email="test@example.com")
        test_user.set_password("12345")
        db.session.add(test_user)
        db.session.commit()

        client.post('/login', data={
            'email': 'test@example.com',
            'password': '12345'
        })

    return client