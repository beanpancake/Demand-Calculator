from app import app


def test_index_get():
    client = app.test_client()
    resp = client.get('/')
    assert resp.status_code == 200


def test_api_calculate():
    client = app.test_client()
    resp = client.post(
        '/api/calculate',
        json={
            'voltage': '240',
            'area': '100',
            'range': '40',
            'heat': '0',
            'ac': '0',
            'evse': '0',
            'additional': [],
            'tankless': '',
            'sps': []
        }
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['result']['Final Calculated Load (W)'] == '24000'
