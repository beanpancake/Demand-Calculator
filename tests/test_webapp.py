from app import app


def test_index_get():
    client = app.test_client()
    resp = client.get('/')
    assert resp.status_code == 200


def test_index_post():
    client = app.test_client()
    resp = client.post('/', data={
        'voltage': '240',
        'area': '100',
        'range': '40',
        'heat': '0',
        'ac': '0',
        'evse': '0',
        'additional': '',
        'tankless': '',
        'sps': ''
    })
    assert resp.status_code == 200
    assert b'Result' in resp.data
