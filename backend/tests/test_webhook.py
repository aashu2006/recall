from tests.conftest import TEST_VERIFY_TOKEN


def test_verify_accepts_correct_token(client):
    r = client.get(
        "/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": TEST_VERIFY_TOKEN, "hub.challenge": "12345"},
    )
    assert r.status_code == 200
    assert r.text == "12345"


def test_verify_rejects_wrong_token(client):
    r = client.get(
        "/webhook",
        params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "12345"},
    )
    assert r.status_code == 403
