from app.security import AuthError, create_session_jwt, validate_origin, verify_session_jwt


def test_validate_origin_accepts_exact_match():
    assert validate_origin('http://localhost:3000', ['http://localhost:3000']) == 'http://localhost:3000'


def test_validate_origin_rejects_unknown_origin():
    try:
        validate_origin('http://evil.example', ['http://localhost:3000'])
        assert False, 'Expected AuthError'
    except AuthError:
        assert True


def test_jwt_round_trip():
    token = create_session_jwt(session_id='session-1', site_id='demo-site', origin='http://localhost:3000', ttl_seconds=120)
    payload = verify_session_jwt(token)
    assert payload['sub'] == 'session-1'
    assert payload['site_id'] == 'demo-site'
