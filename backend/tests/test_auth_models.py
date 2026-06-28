from app.models.identity import AdminSession, Administrator


def test_administrator_and_session_contract():
    assert Administrator.__tablename__ == "administrators"
    assert Administrator.username.property.columns[0].unique is True
    assert AdminSession.__tablename__ == "admin_sessions"
    assert AdminSession.token_hash.property.columns[0].unique is True
    assert AdminSession.administrator.property.mapper.class_ is Administrator
