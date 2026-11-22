"""Encryption of database credentials and portable configuration backups.

The Fernet key lives only in GT_DATA_ENCRYPTION_KEY (outside PostgreSQL and
backups).  Legacy plaintext rows are sealed transactionally during startup.
A missing/wrong key never makes ciphertext silently look like plaintext.
"""
from __future__ import annotations

import json
import os
from cryptography.fernet import Fernet, InvalidToken

PREFIX = 'gtenc:v1:'
BACKUP_KIND = 'canopyops-encrypted-config-backup'


def _cipher() -> Fernet | None:
    key = (os.getenv('GT_DATA_ENCRYPTION_KEY') or '').strip()
    if not key:
        return None
    try:
        return Fernet(key.encode('ascii'))
    except (ValueError, TypeError, UnicodeError) as exc:
        raise RuntimeError('Invalid GT_DATA_ENCRYPTION_KEY: expected a Fernet key') from exc


def has_key() -> bool:
    return _cipher() is not None


def require_key() -> Fernet:
    cipher = _cipher()
    if cipher is None:
        raise RuntimeError('GT_DATA_ENCRYPTION_KEY is required for encrypted backups')
    return cipher


def open_secret(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    if not text.startswith(PREFIX):
        return text
    try:
        return require_key().decrypt(text[len(PREFIX):].encode('ascii')).decode('utf-8')
    except (InvalidToken, UnicodeError, ValueError) as exc:
        raise RuntimeError('Cannot decrypt stored secret: wrong or missing encryption key') from exc


def seal_secret(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    if not text or text.startswith(PREFIX):
        # Verify existing ciphertext before accepting it as already sealed.
        if text.startswith(PREFIX):
            open_secret(text)
        return text
    cipher = _cipher()
    if cipher is None:
        # Test runs and opt-in transitional deployments without a key retain
        # their existing behavior. Production Compose REQUIRES the key.
        return text
    return PREFIX + cipher.encrypt(text.encode('utf-8')).decode('ascii')


def encrypt_backup(document: dict) -> dict:
    """No plaintext export fallback; encrypted backups require configured key."""
    raw = json.dumps(document, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return {
        'kind': BACKUP_KIND,
        'schema_version': 1,
        'encryption': 'fernet-v1',
        'ciphertext': require_key().encrypt(raw).decode('ascii'),
    }


def decrypt_backup(envelope: dict) -> dict:
    if (envelope.get('kind') != BACKUP_KIND or envelope.get('schema_version') != 1
            or envelope.get('encryption') != 'fernet-v1'
            or not isinstance(envelope.get('ciphertext'), str)):
        raise ValueError('Invalid encrypted backup envelope')
    try:
        raw = require_key().decrypt(envelope['ciphertext'].encode('ascii'))
        document = json.loads(raw)
    except (InvalidToken, UnicodeError, ValueError, TypeError) as exc:
        raise ValueError('Backup decryption failed: wrong key or corrupt backup') from exc
    if not isinstance(document, dict) or document.get('kind') != 'canopyops-config-backup':
        raise ValueError('Decrypted backup contains an invalid document')
    return document


# Whitelist of real columns; never interpolate untrusted identifiers into SQL.
_MIGRATION_TABLES = (
    ('app_auth_config', ('totp_secret', 'pushover_app_token', 'pushover_user_key', 'gromate_api_password')),
    ('app_admin_users', ('totp_secret',)),
    ('tents', ('rtsp_url', 'shelly_main_password', 'backend_hmac_secret')),
)


def migrate_legacy_secrets(cur) -> int:
    """Idempotent in-place migration inside caller's PostgreSQL transaction.

    A wrong key raises before commit, so PostgreSQL rolls back the transaction;
    already encrypted fields are independently authenticated each startup.
    """
    if not has_key():
        return 0
    changed = 0
    for table, columns in _MIGRATION_TABLES:
        cur.execute(f"SELECT id, {', '.join(columns)} FROM {table} ORDER BY id FOR UPDATE")
        for record in cur.fetchall():
            row_id, *values = record
            new_values = [seal_secret(value) for value in values]
            changed_columns = [(column, new) for column, old, new in zip(columns, values, new_values) if new != old]
            if not changed_columns:
                continue
            setter = ', '.join(f'{column}=%s' for column, _ in changed_columns)
            cur.execute(f'UPDATE {table} SET {setter} WHERE id=%s',
                        tuple(value for _, value in changed_columns) + (row_id,))
            changed += len(changed_columns)
    return changed
