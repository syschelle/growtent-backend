import ast
from pathlib import Path


def _load_function(name: str):
    source_path = Path(__file__).resolve().parents[1] / "api" / "app.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    function = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )
    module = ast.Module(body=[function], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {"bool": bool, "int": int}
    exec(compile(module, str(source_path), "exec"), namespace)
    return namespace[name]


_migrate_legacy_admin_if_needed = _load_function("_migrate_legacy_admin_if_needed")
_sync_legacy_admin_mirror = _load_function("_sync_legacy_admin_mirror")


class FakeCursor:
    def __init__(self, responses):
        self.responses = list(responses)
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self.responses.pop(0)


def test_legacy_admin_migration_preserves_existing_credentials_and_2fa():
    legacy = (
        "schellie",
        "$argon2id$v=19$m=65536,t=3,p=4$existing-hash",
        True,
        "JBSWY3DPEHPK3PXP",
        '[{"hash":"recovery-hash","used":false}]',
    )
    cur = FakeCursor([(0,), legacy])

    _migrate_legacy_admin_if_needed(cur)

    insert = next((entry for entry in cur.executed if "INSERT INTO app_admin_users" in entry[0]), None)
    assert insert is not None
    assert insert[1] == (
        legacy[0],
        legacy[1],
        True,
        legacy[3],
        legacy[4],
    )


def test_legacy_admin_migration_is_idempotent_when_admins_already_exist():
    cur = FakeCursor([(2,)])

    _migrate_legacy_admin_if_needed(cur)

    assert not any("INSERT INTO app_admin_users" in sql for sql, _ in cur.executed)
    assert len(cur.executed) == 1


def test_legacy_mirror_uses_oldest_active_admin_without_rehashing():
    primary = (
        "admin-one",
        "$argon2id$v=19$m=65536,t=3,p=4$primary-hash",
        True,
        "PRIMARYSECRET",
        '[{"hash":"recovery-primary","used":false}]',
    )
    cur = FakeCursor([primary])

    _sync_legacy_admin_mirror(cur, preferred_admin_id=999)

    update = next((entry for entry in cur.executed if "UPDATE app_auth_config" in entry[0]), None)
    assert update is not None
    assert update[1] == (primary[0], primary[1], True, primary[3], primary[4])
