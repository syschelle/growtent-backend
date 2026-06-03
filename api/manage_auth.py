#!/usr/bin/env python3
"""Small operational helper for GrowTent/CanopyOps auth settings.

Admin passwords are stored as Argon2id hashes. Legacy password hashes are not written or migrated.

Run inside the API container, for example:
  docker compose exec api python manage_auth.py status
  docker compose exec api python manage_auth.py set-admin --username '<admin-user>' --prompt-password --disable-2fa

For safer shell history handling. If --username is omitted, the existing configured username is kept:
  printf '%s' '<new-admin-password>' | docker compose exec -T api python manage_auth.py set-admin --password-stdin --disable-2fa

To change the username and password together:
  printf '%s' '<new-admin-password>' | docker compose exec -T api python manage_auth.py set-admin --username '<new-admin-name>' --password-stdin --disable-2fa
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from getpass import getpass

from argon2 import PasswordHasher


DATABASE_URL = (os.getenv("DATABASE_URL") or "").strip()


PASSWORD_HASHER = PasswordHasher()


def _hash_password(value: str) -> str:
    return PASSWORD_HASHER.hash(value)


def _connect():
    if not DATABASE_URL:
        raise SystemExit("DATABASE_URL is required. Run inside a configured API container or export a deployment-specific DATABASE_URL.")
    lowered = DATABASE_URL.lower()
    if "postgresql://growtent:growtent@" in lowered or "replace_with" in lowered or "change-me" in lowered:
        raise SystemExit("Refusing to use placeholder or weak default database credentials. Replace DATABASE_URL first.")
    try:
        import psycopg2
    except ModuleNotFoundError as exc:
        raise SystemExit("psycopg2 is not installed. Run this inside the API container, e.g. docker compose exec api python manage_auth.py status") from exc
    return psycopg2.connect(DATABASE_URL)


def _ensure_auth_table(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS app_auth_config (
            id INTEGER PRIMARY KEY,
            enabled BOOLEAN NOT NULL DEFAULT FALSE,
            username TEXT,
            password_hash TEXT,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )
    cur.execute("ALTER TABLE app_auth_config ADD COLUMN IF NOT EXISTS twofa_enabled BOOLEAN NOT NULL DEFAULT FALSE;")
    cur.execute("ALTER TABLE app_auth_config ADD COLUMN IF NOT EXISTS totp_secret TEXT;")
    cur.execute("ALTER TABLE app_auth_config ADD COLUMN IF NOT EXISTS recovery_codes_json TEXT NOT NULL DEFAULT '[]';")
    cur.execute("ALTER TABLE app_auth_config ADD COLUMN IF NOT EXISTS guest_enabled BOOLEAN NOT NULL DEFAULT FALSE;")
    cur.execute("ALTER TABLE app_auth_config ADD COLUMN IF NOT EXISTS guest_username TEXT;")
    cur.execute("ALTER TABLE app_auth_config ADD COLUMN IF NOT EXISTS guest_password_hash TEXT;")
    cur.execute("ALTER TABLE app_auth_config ADD COLUMN IF NOT EXISTS guest_expires_at TIMESTAMPTZ;")
    cur.execute("ALTER TABLE app_auth_config ADD COLUMN IF NOT EXISTS pushover_device TEXT;")
    cur.execute("ALTER TABLE app_auth_config ADD COLUMN IF NOT EXISTS pushover_app_token TEXT;")
    cur.execute("ALTER TABLE app_auth_config ADD COLUMN IF NOT EXISTS pushover_user_key TEXT;")
    cur.execute("ALTER TABLE app_auth_config ADD COLUMN IF NOT EXISTS gromate_api_password TEXT;")
    cur.execute("ALTER TABLE app_auth_config ADD COLUMN IF NOT EXISTS history_api_enabled BOOLEAN NOT NULL DEFAULT TRUE;")
    cur.execute("INSERT INTO app_auth_config(id, enabled) VALUES (1, FALSE) ON CONFLICT (id) DO NOTHING;")


def _read_password(args: argparse.Namespace) -> str | None:
    sources = [
        bool(args.password),
        bool(args.password_env),
        bool(args.password_stdin),
        bool(args.prompt_password),
    ]
    if sum(1 for x in sources if x) > 1:
        raise SystemExit("Use only one password source: --password, --password-env, --password-stdin or --prompt-password")
    if args.password:
        return args.password
    if args.password_env:
        value = os.getenv(args.password_env)
        if value is None:
            raise SystemExit(f"Environment variable {args.password_env!r} is not set")
        return value
    if args.password_stdin:
        return sys.stdin.read().rstrip("\n")
    if args.prompt_password:
        first = getpass("New admin password: ")
        second = getpass("Repeat new admin password: ")
        if first != second:
            raise SystemExit("Password confirmation does not match")
        return first
    return None


def cmd_status(_args: argparse.Namespace) -> int:
    with _connect() as conn:
        with conn.cursor() as cur:
            _ensure_auth_table(cur)
            cur.execute(
                """
                SELECT enabled, username, password_hash IS NOT NULL AS has_password,
                       twofa_enabled, updated_at
                FROM app_auth_config
                WHERE id=1
                """
            )
            row = cur.fetchone()
    payload = {
        "enabled": bool(row[0]) if row else False,
        "username": row[1] if row else None,
        "has_password": bool(row[2]) if row else False,
        "twofa_enabled": bool(row[3]) if row else False,
        "updated_at": row[4].isoformat() if row and row[4] else None,
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def cmd_set_admin(args: argparse.Namespace) -> int:
    requested_username = args.username.strip() if isinstance(args.username, str) else None
    if args.username is not None and not requested_username:
        raise SystemExit("Username must not be empty")

    password = _read_password(args)
    password_hash = _hash_password(password) if password is not None else None

    if args.enable_auth and args.disable_auth:
        raise SystemExit("Use either --enable-auth or --disable-auth, not both")
    if args.enable_auth:
        enabled = True
    elif args.disable_auth:
        enabled = False
    else:
        enabled = True

    with _connect() as conn:
        with conn.cursor() as cur:
            _ensure_auth_table(cur)
            cur.execute("SELECT username, password_hash FROM app_auth_config WHERE id=1")
            row = cur.fetchone()
            current_username = (row[0] or "").strip() if row else ""
            current_hash = row[1] if row else None
            username = requested_username or current_username or "admin"
            new_hash = password_hash if password_hash is not None else current_hash
            if enabled and not username:
                raise SystemExit("Cannot enable auth without a username. Provide one with --username.")
            if enabled and not new_hash:
                raise SystemExit("Cannot enable auth without a password. Provide one with --password, --password-stdin, --password-env or --prompt-password.")

            cur.execute(
                """
                UPDATE app_auth_config
                SET enabled=%s,
                    username=%s,
                    password_hash=%s,
                    updated_at=NOW()
                WHERE id=1
                """,
                (enabled, username, new_hash),
            )
            if args.disable_2fa:
                cur.execute(
                    """
                    UPDATE app_auth_config
                    SET twofa_enabled=FALSE,
                        totp_secret=NULL,
                        recovery_codes_json='[]',
                        updated_at=NOW()
                    WHERE id=1
                    """
                )

    changed = "changed" if password_hash is not None else "kept"
    twofa = "disabled" if args.disable_2fa else "unchanged"
    print(f"Admin auth updated: enabled={enabled}, username={username!r}, password={changed}, 2FA={twofa}.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage GrowTent/CanopyOps admin authentication from inside Docker.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="Show current auth status without exposing password hashes.")
    p_status.set_defaults(func=cmd_status)

    p_admin = sub.add_parser("set-admin", help="Set or reset the admin user/password.")
    p_admin.add_argument("--username", help="Admin username to set. If omitted, the currently configured username is kept; if none exists, 'admin' is used.")
    p_admin.add_argument("--password", help="New admin password. Visible in shell history; prefer --password-stdin or --prompt-password.")
    p_admin.add_argument("--password-env", help="Read the new password from this environment variable name.")
    p_admin.add_argument("--password-stdin", action="store_true", help="Read the new password from standard input.")
    p_admin.add_argument("--prompt-password", action="store_true", help="Prompt interactively and require confirmation.")
    p_admin.add_argument("--enable-auth", action="store_true", help="Enable authentication. This is the default for set-admin.")
    p_admin.add_argument("--disable-auth", action="store_true", help="Disable global authentication while keeping configured admin credentials.")
    p_admin.add_argument("--disable-2fa", action="store_true", help="Disable 2FA and clear TOTP/recovery data.")
    p_admin.set_defaults(func=cmd_set_admin)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
