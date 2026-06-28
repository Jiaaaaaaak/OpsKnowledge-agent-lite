from app.models.identity import AdminSession, Administrator


def test_administrator_and_session_contract():
    assert Administrator.__tablename__ == "administrators"
    assert Administrator.username.property.columns[0].unique is True
    assert AdminSession.__tablename__ == "admin_sessions"
    assert AdminSession.token_hash.property.columns[0].unique is True
    assert AdminSession.administrator.property.mapper.class_ is Administrator


def test_admin_session_lifecycle_contract():
    administrator_id = AdminSession.administrator_id.property.columns[0]
    foreign_key = next(iter(administrator_id.foreign_keys))

    assert administrator_id.nullable is False
    assert foreign_key.target_fullname == "administrators.id"
    assert foreign_key.ondelete == "CASCADE"
    assert Administrator.sessions.property.cascade.delete_orphan is True


def test_admin_session_timestamps_and_indexes_contract():
    assert AdminSession.expires_at.property.columns[0].type.timezone is True
    assert AdminSession.expires_at.property.columns[0].nullable is False
    assert AdminSession.revoked_at.property.columns[0].type.timezone is True
    assert AdminSession.revoked_at.property.columns[0].nullable is True

    indexes = {
        index.name: tuple(column.name for column in index.columns)
        for index in AdminSession.__table__.indexes
    }
    assert indexes["idx_admin_sessions_administrator_id"] == ("administrator_id",)
    assert indexes["idx_admin_sessions_expires_at"] == ("expires_at",)
