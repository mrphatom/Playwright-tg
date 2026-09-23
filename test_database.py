from database import _translate_sql


def test_translate_sql_escapes_literal_percent_for_psycopg():
    translated = _translate_sql(
        "SELECT * FROM t WHERE note LIKE 'permission_loss:%' AND id = ?"
    )
    assert "permission_loss:%%" in translated
    assert translated.endswith("id = %s")


def test_translate_sql_preserves_postgres_placeholders_and_escaped_percent():
    translated = _translate_sql("SELECT setval(%s, 100, true), '100%%'")
    assert translated == "SELECT setval(%s, 100, true), '100%%'"


def test_translate_sql_escapes_sequence_default_pattern():
    translated = _translate_sql(
        "SELECT column_default FROM information_schema.columns "
        "WHERE column_default LIKE 'nextval(%%'"
    )
    assert "LIKE 'nextval(%%'" in translated
