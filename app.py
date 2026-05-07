import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timedelta, timezone
from http import cookies
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None

try:
    import jwt
    from jwt import PyJWKClient
except ImportError:
    jwt = None
    PyJWKClient = None

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "feature_priority.db"
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
SESSION_COOKIE = "feature_priority_session"
OIDC_STATE_COOKIE = "feature_priority_oidc_state"
SESSION_TTL_DAYS = 14
HOST = os.environ.get("APP_HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT") or os.environ.get("APP_PORT", "8000"))
SECRET_PATH = BASE_DIR / ".app_secret"
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "").lower() in {"1", "true", "yes"}
MICROSOFT_CLIENT_ID = os.environ.get("MICROSOFT_CLIENT_ID", "").strip()
MICROSOFT_CLIENT_SECRET = os.environ.get("MICROSOFT_CLIENT_SECRET", "").strip()
MICROSOFT_TENANT_ID = os.environ.get("MICROSOFT_TENANT_ID", "organizations").strip()
MICROSOFT_AUTHORITY = os.environ.get(
    "MICROSOFT_AUTHORITY", "https://login.microsoftonline.com"
).rstrip("/")
MICROSOFT_REDIRECT_URI = os.environ.get("MICROSOFT_REDIRECT_URI", "").strip()
MICROSOFT_ALLOWED_DOMAINS = {
    domain.strip().lower()
    for domain in os.environ.get("MICROSOFT_ALLOWED_DOMAINS", "").split(",")
    if domain.strip()
}
MICROSOFT_AUTO_PROVISION = os.environ.get("MICROSOFT_AUTO_PROVISION", "true").lower() in {
    "1",
    "true",
    "yes",
}
MICROSOFT_DEFAULT_ROLE = os.environ.get("MICROSOFT_DEFAULT_ROLE", "viewer").strip().lower()
MICROSOFT_OIDC_SCOPE = "openid profile email"

SQLITE_FEATURE_SCHEMA = """
CREATE TABLE IF NOT EXISTS features (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    problem_statement TEXT NOT NULL,
    request_source TEXT NOT NULL,
    product_area TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Idea',
    team_owner TEXT,
    submitted_by TEXT,
    urgency_reason TEXT,
    notes TEXT,
    dependencies TEXT,
    tagged_user_ids TEXT NOT NULL DEFAULT '[]',
    quick_win INTEGER NOT NULL DEFAULT 0,
    customer_impact INTEGER NOT NULL,
    strategic_fit INTEGER NOT NULL,
    urgency INTEGER NOT NULL,
    confidence INTEGER NOT NULL,
    effort INTEGER NOT NULL,
    dependency_risk INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

POSTGRES_FEATURE_SCHEMA = """
CREATE TABLE IF NOT EXISTS features (
    id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    title TEXT NOT NULL,
    problem_statement TEXT NOT NULL,
    request_source TEXT NOT NULL,
    product_area TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Idea',
    team_owner TEXT,
    submitted_by TEXT,
    urgency_reason TEXT,
    notes TEXT,
    dependencies TEXT,
    tagged_user_ids TEXT NOT NULL DEFAULT '[]',
    quick_win BOOLEAN NOT NULL DEFAULT FALSE,
    customer_impact INTEGER NOT NULL,
    strategic_fit INTEGER NOT NULL,
    urgency INTEGER NOT NULL,
    confidence INTEGER NOT NULL,
    effort INTEGER NOT NULL,
    dependency_risk INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

SQLITE_USER_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

POSTGRES_USER_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

SQLITE_SESSION_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""

POSTGRES_SESSION_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    user_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
"""

SEED_FEATURES = [
    {
        "title": "Update user page and user data",
        "problem_statement": "Customer settings are missing and support workarounds are costly.",
        "request_source": "Customer request",
        "product_area": "User accounts",
        "status": "Idea",
        "team_owner": "Product",
        "submitted_by": "Arsaman",
        "urgency_reason": "Support workarounds consume time each week.",
        "notes": "",
        "dependencies": "User settings refactor",
        "tagged_user_ids": [],
        "quick_win": 0,
        "customer_impact": 4,
        "strategic_fit": 3,
        "urgency": 4,
        "confidence": 4,
        "effort": 2,
        "dependency_risk": 1,
    },
    {
        "title": "Result anonymity issue",
        "problem_statement": "Anonymity rules are insufficient in some scenarios.",
        "request_source": "Internal request",
        "product_area": "Survey results",
        "status": "Triage",
        "team_owner": "Engineering",
        "submitted_by": "Support",
        "urgency_reason": "This can create trust issues with customers.",
        "notes": "Needs validation with compliance.",
        "dependencies": "Rules engine review",
        "tagged_user_ids": [],
        "quick_win": 0,
        "customer_impact": 5,
        "strategic_fit": 4,
        "urgency": 5,
        "confidence": 4,
        "effort": 3,
        "dependency_risk": 2,
    },
]

ALLOWED_ROLES = {"admin", "editor", "viewer"}
ROLE_EDITORS = {"admin", "editor"}
MICROSOFT_METADATA = None
MICROSOFT_JWKS_CLIENT = None


def utc_now():
    return datetime.now(timezone.utc)


def iso_now():
    return utc_now().isoformat()


def get_secret_key():
    secret = os.environ.get("APP_SECRET")
    if secret:
        return secret

    if SECRET_PATH.exists():
        return SECRET_PATH.read_text().strip()

    generated = secrets.token_hex(32)
    SECRET_PATH.write_text(generated)
    return generated


APP_SECRET = get_secret_key()


def microsoft_enabled():
    return bool(MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET)


def score_feature(feature):
    return (
        feature["customer_impact"] * 3
        + feature["strategic_fit"] * 2
        + feature["urgency"] * 2
        + feature["confidence"]
        - feature["effort"] * 2
        - feature["dependency_risk"]
        + (2 if feature["quick_win"] else 0)
    )


def parse_request_sources(value):
    if not value:
        return []

    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except json.JSONDecodeError:
        pass

    return [str(value).strip()]


def serialize_request_sources(sources):
    cleaned = [str(item).strip() for item in sources if str(item).strip()]
    return json.dumps(cleaned)


def parse_tagged_user_ids(value):
    if not value:
        return []

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    tagged_ids = []
    for item in parsed:
        try:
            tagged_ids.append(int(item))
        except (TypeError, ValueError):
            continue
    return tagged_ids


def serialize_tagged_user_ids(tagged_user_ids):
    cleaned = []
    seen = set()
    for item in tagged_user_ids:
        try:
            normalized = int(item)
        except (TypeError, ValueError):
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return json.dumps(cleaned)


def db_bool(value):
    if is_postgres():
        return bool(value)
    return 1 if value else 0


def encode_state_payload(payload):
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return urlsafe_b64encode(raw).decode("utf-8")


def decode_state_payload(value):
    padding = "=" * (-len(value) % 4)
    raw = urlsafe_b64decode((value + padding).encode("utf-8"))
    return json.loads(raw.decode("utf-8"))


def http_json(url, method="GET", data=None, headers=None):
    body = None
    request_headers = headers.copy() if headers else {}
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = Request(url, data=body, headers=request_headers, method=method)
    with urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def http_form(url, data):
    encoded = urlencode(data).encode("utf-8")
    request = Request(
        url,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def get_microsoft_metadata():
    global MICROSOFT_METADATA, MICROSOFT_JWKS_CLIENT
    if MICROSOFT_METADATA is None:
        metadata_url = (
            f"{MICROSOFT_AUTHORITY}/{MICROSOFT_TENANT_ID}/v2.0/.well-known/openid-configuration"
        )
        MICROSOFT_METADATA = http_json(metadata_url)
        if PyJWKClient is None:
            raise RuntimeError("PyJWT is required for Microsoft SSO.")
        MICROSOFT_JWKS_CLIENT = PyJWKClient(MICROSOFT_METADATA["jwks_uri"])
    return MICROSOFT_METADATA


def validate_microsoft_token(id_token, expected_nonce):
    metadata = get_microsoft_metadata()
    signing_key = MICROSOFT_JWKS_CLIENT.get_signing_key_from_jwt(id_token)
    payload = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256"],
        audience=MICROSOFT_CLIENT_ID,
        issuer=metadata["issuer"],
        options={"require": ["exp", "iat", "iss", "aud", "nonce"]},
    )

    if payload.get("nonce") != expected_nonce:
        raise ValueError("Invalid Microsoft sign-in nonce.")
    return payload


def get_email_from_claims(claims):
    for key in ["preferred_username", "email", "upn"]:
        value = str(claims.get(key, "")).strip().lower()
        if value and "@" in value:
            return value
    return ""


def domain_allowed(email):
    if not MICROSOFT_ALLOWED_DOMAINS:
        return True
    domain = email.split("@", 1)[-1].lower()
    return domain in MICROSOFT_ALLOWED_DOMAINS


def score_order_sql():
    if is_postgres():
        quick_win_term = "CASE WHEN quick_win THEN 2 ELSE 0 END"
    else:
        quick_win_term = "CASE quick_win WHEN 1 THEN 2 ELSE 0 END"

    return f"""
        ((customer_impact * 3) + (strategic_fit * 2) + (urgency * 2) + confidence
        - (effort * 2) - dependency_risk + ({quick_win_term}))
    """


def get_connection():
    if DATABASE_URL:
        if psycopg is None:
            raise RuntimeError("psycopg is required when DATABASE_URL is set.")
        return psycopg.connect(DATABASE_URL, row_factory=dict_row)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def is_postgres():
    return bool(DATABASE_URL)


def adapt_query(query):
    if not is_postgres():
        return query

    parts = query.split("?")
    if len(parts) == 1:
        return query
    return "%s".join(parts)


def fetchone(conn, query, params=()):
    row = conn.execute(adapt_query(query), params).fetchone()
    if row is None:
        return None
    return dict(row) if not isinstance(row, dict) else row


def fetchall(conn, query, params=()):
    rows = conn.execute(adapt_query(query), params).fetchall()
    return [dict(row) if not isinstance(row, dict) else row for row in rows]


def execute(conn, query, params=()):
    return conn.execute(adapt_query(query), params)


def hash_password(password, salt=None):
    chosen_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        chosen_salt.encode("utf-8"),
        100_000,
    ).hex()
    return chosen_salt, digest


def verify_password(password, salt, password_hash):
    _, digest = hash_password(password, salt)
    return hmac.compare_digest(digest, password_hash)


def hash_token(token):
    return hashlib.sha256(f"{token}:{APP_SECRET}".encode("utf-8")).hexdigest()


def seed_features_if_needed(conn):
    count = fetchone(conn, "SELECT COUNT(*) AS count FROM features")["count"]
    if count:
        return

    created_at = iso_now()
    for feature in SEED_FEATURES:
        execute(
            conn,
            """
            INSERT INTO features (
                title, problem_statement, request_source, product_area, status, team_owner,
                submitted_by, urgency_reason, notes, dependencies, tagged_user_ids, quick_win,
                customer_impact, strategic_fit, urgency, confidence, effort, dependency_risk,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                feature["title"],
                feature["problem_statement"],
                feature["request_source"],
                feature["product_area"],
                feature["status"],
                feature["team_owner"],
                feature["submitted_by"],
                feature["urgency_reason"],
                feature["notes"],
                feature["dependencies"],
                serialize_tagged_user_ids(feature.get("tagged_user_ids", [])),
                db_bool(feature["quick_win"]),
                feature["customer_impact"],
                feature["strategic_fit"],
                feature["urgency"],
                feature["confidence"],
                feature["effort"],
                feature["dependency_risk"],
                created_at,
                created_at,
            ),
        )


def seed_initial_admin(conn):
    count = fetchone(conn, "SELECT COUNT(*) AS count FROM users")["count"]
    if count:
        return None

    name = os.environ.get("APP_ADMIN_NAME", "Admin User")
    email = os.environ.get("APP_ADMIN_EMAIL", "admin@example.com").strip().lower()
    password = os.environ.get("APP_ADMIN_PASSWORD") or secrets.token_urlsafe(12)
    salt, password_hash = hash_password(password)
    created_at = iso_now()

    execute(
        conn,
        """
        INSERT INTO users (name, email, role, password_hash, password_salt, created_at)
        VALUES (?, ?, 'admin', ?, ?, ?)
        """,
        (name, email, password_hash, salt, created_at),
    )

    generated = "APP_ADMIN_PASSWORD" not in os.environ
    return {"email": email, "password": password, "generated": generated}


def init_db():
    with get_connection() as conn:
        execute(conn, SQLITE_FEATURE_SCHEMA if not is_postgres() else POSTGRES_FEATURE_SCHEMA)
        execute(conn, SQLITE_USER_SCHEMA if not is_postgres() else POSTGRES_USER_SCHEMA)
        execute(conn, SQLITE_SESSION_SCHEMA if not is_postgres() else POSTGRES_SESSION_SCHEMA)
        ensure_feature_columns(conn)
        seed_features_if_needed(conn)
        return seed_initial_admin(conn)


def ensure_feature_columns(conn):
    if is_postgres():
        column = fetchone(
            conn,
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'features' AND column_name = 'tagged_user_ids'
            """,
        )
        if not column:
            execute(
                conn,
                "ALTER TABLE features ADD COLUMN tagged_user_ids TEXT NOT NULL DEFAULT '[]'",
            )
        return

    columns = fetchall(conn, "PRAGMA table_info(features)")
    if not any(column["name"] == "tagged_user_ids" for column in columns):
        execute(
            conn,
            "ALTER TABLE features ADD COLUMN tagged_user_ids TEXT NOT NULL DEFAULT '[]'",
        )


def normalize_feature(row, user_lookup=None):
    feature = dict(row)
    feature["quick_win"] = bool(feature["quick_win"])
    feature["request_sources"] = parse_request_sources(feature["request_source"])
    feature["tagged_user_ids"] = parse_tagged_user_ids(feature.get("tagged_user_ids"))
    feature["tagged_users"] = []
    if user_lookup:
        feature["tagged_users"] = [
            user_lookup[user_id]
            for user_id in feature["tagged_user_ids"]
            if user_id in user_lookup
        ]
    feature["priority_score"] = score_feature(feature)
    return feature


def normalize_user(row):
    user = dict(row)
    user.pop("password_hash", None)
    user.pop("password_salt", None)
    return user


def list_features():
    user_lookup = list_user_lookup()
    with get_connection() as conn:
        rows = fetchall(
            conn,
            """
            SELECT *
            FROM features
            ORDER BY
              """
            + score_order_sql()
            + """
              DESC,
              updated_at DESC
            """
        )
    return [normalize_feature(row, user_lookup) for row in rows]


def get_feature(feature_id):
    user_lookup = list_user_lookup()
    with get_connection() as conn:
        row = fetchone(conn, "SELECT * FROM features WHERE id = ?", (feature_id,))
    return normalize_feature(row, user_lookup) if row else None


def list_users():
    with get_connection() as conn:
        rows = fetchall(
            conn,
            "SELECT id, name, email, role, created_at FROM users ORDER BY created_at ASC"
        )
    return rows


def list_user_lookup():
    return {user["id"]: user for user in list_users()}


def list_mentionable_users():
    with get_connection() as conn:
        rows = fetchall(
            conn,
            "SELECT id, name, email, role FROM users ORDER BY name COLLATE NOCASE ASC"
            if not is_postgres()
            else "SELECT id, name, email, role FROM users ORDER BY LOWER(name) ASC",
        )
    return rows


def get_user_by_email(email):
    with get_connection() as conn:
        row = fetchone(conn, "SELECT * FROM users WHERE email = ?", (email.lower(),))
    return row


def get_user_by_id(user_id):
    with get_connection() as conn:
        row = fetchone(
            conn,
            "SELECT id, name, email, role, created_at FROM users WHERE id = ?",
            (user_id,),
        )
    return row


def get_or_create_sso_user(email, name):
    existing = get_user_by_email(email)
    if existing:
        return normalize_user(existing)

    if not MICROSOFT_AUTO_PROVISION:
        raise ValueError("This Microsoft account is not provisioned for access.")

    if MICROSOFT_DEFAULT_ROLE not in ALLOWED_ROLES:
        raise ValueError("MICROSOFT_DEFAULT_ROLE must be admin, editor, or viewer.")

    random_password = secrets.token_urlsafe(24)
    created = create_user(
        {
            "name": name or email.split("@", 1)[0],
            "email": email,
            "role": MICROSOFT_DEFAULT_ROLE,
            "password": random_password,
        }
    )
    return created


def validate_feature_payload(payload):
    required_text = [
        "title",
        "problem_statement",
        "product_area",
        "status",
    ]
    cleaned = {}

    for field in required_text:
        value = str(payload.get(field, "")).strip()
        if not value:
            raise ValueError(f"{field.replace('_', ' ').title()} is required.")
        cleaned[field] = value

    request_sources = payload.get("request_sources")
    if request_sources is None:
        request_sources = [payload.get("request_source", "")]
    if not isinstance(request_sources, list):
        raise ValueError("Request sources must be a list.")

    normalized_sources = [str(item).strip() for item in request_sources if str(item).strip()]
    if not normalized_sources:
        raise ValueError("At least one source is required.")

    cleaned["request_source"] = serialize_request_sources(normalized_sources)
    cleaned["request_sources"] = normalized_sources

    for field in ["team_owner", "submitted_by", "urgency_reason", "notes", "dependencies"]:
        cleaned[field] = str(payload.get(field, "")).strip()

    tagged_user_ids = payload.get("tagged_user_ids", [])
    if tagged_user_ids is None:
        tagged_user_ids = []
    if not isinstance(tagged_user_ids, list):
        raise ValueError("Tagged users must be a list.")

    mentionable_users = list_user_lookup()
    normalized_tagged_ids = []
    for item in tagged_user_ids:
        try:
            user_id = int(item)
        except (TypeError, ValueError):
            raise ValueError("Tagged users must contain valid user ids.")
        if user_id not in mentionable_users:
            raise ValueError("One or more tagged users could not be found.")
        normalized_tagged_ids.append(user_id)

    cleaned["tagged_user_ids"] = normalized_tagged_ids
    cleaned["tagged_user_ids_serialized"] = serialize_tagged_user_ids(normalized_tagged_ids)

    for field in [
        "customer_impact",
        "strategic_fit",
        "urgency",
        "confidence",
        "effort",
        "dependency_risk",
    ]:
        value = int(payload.get(field, 0))
        if value < 1 or value > 5:
            raise ValueError(f"{field.replace('_', ' ').title()} must be between 1 and 5.")
        cleaned[field] = value

    cleaned["quick_win"] = db_bool(payload.get("quick_win"))
    return cleaned


def validate_user_payload(payload):
    name = str(payload.get("name", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    role = str(payload.get("role", "")).strip().lower()
    password = str(payload.get("password", ""))

    if not name:
        raise ValueError("Name is required.")
    if not email or "@" not in email:
        raise ValueError("A valid email is required.")
    if role not in ALLOWED_ROLES:
        raise ValueError("Role must be admin, editor, or viewer.")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")

    return {"name": name, "email": email, "role": role, "password": password}


def create_feature(payload):
    cleaned = validate_feature_payload(payload)
    now = iso_now()
    with get_connection() as conn:
        created = fetchone(
            conn,
            """
            INSERT INTO features (
                title, problem_statement, request_source, product_area, status, team_owner,
                submitted_by, urgency_reason, notes, dependencies, tagged_user_ids, quick_win,
                customer_impact, strategic_fit, urgency, confidence, effort, dependency_risk,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                cleaned["title"],
                cleaned["problem_statement"],
                cleaned["request_source"],
                cleaned["product_area"],
                cleaned["status"],
                cleaned["team_owner"],
                cleaned["submitted_by"],
                cleaned["urgency_reason"],
                cleaned["notes"],
                cleaned["dependencies"],
                cleaned["tagged_user_ids_serialized"],
                cleaned["quick_win"],
                cleaned["customer_impact"],
                cleaned["strategic_fit"],
                cleaned["urgency"],
                cleaned["confidence"],
                cleaned["effort"],
                cleaned["dependency_risk"],
                now,
                now,
            ),
        )
        feature_id = created["id"]
    return get_feature(feature_id)


def update_feature(feature_id, payload):
    cleaned = validate_feature_payload(payload)
    now = iso_now()
    with get_connection() as conn:
        updated = execute(
            conn,
            """
            UPDATE features
            SET
                title = ?, problem_statement = ?, request_source = ?, product_area = ?, status = ?,
                team_owner = ?, submitted_by = ?, urgency_reason = ?, notes = ?, dependencies = ?,
                tagged_user_ids = ?, quick_win = ?, customer_impact = ?, strategic_fit = ?,
                urgency = ?, confidence = ?, effort = ?, dependency_risk = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                cleaned["title"],
                cleaned["problem_statement"],
                cleaned["request_source"],
                cleaned["product_area"],
                cleaned["status"],
                cleaned["team_owner"],
                cleaned["submitted_by"],
                cleaned["urgency_reason"],
                cleaned["notes"],
                cleaned["dependencies"],
                cleaned["tagged_user_ids_serialized"],
                cleaned["quick_win"],
                cleaned["customer_impact"],
                cleaned["strategic_fit"],
                cleaned["urgency"],
                cleaned["confidence"],
                cleaned["effort"],
                cleaned["dependency_risk"],
                now,
                feature_id,
            ),
        )
        if updated.rowcount == 0:
            return None
    return get_feature(feature_id)


def delete_feature(feature_id):
    with get_connection() as conn:
        cursor = execute(conn, "DELETE FROM features WHERE id = ?", (feature_id,))
    return cursor.rowcount > 0


def create_user(payload):
    cleaned = validate_user_payload(payload)
    if get_user_by_email(cleaned["email"]):
        raise ValueError("A user with that email already exists.")

    salt, password_hash = hash_password(cleaned["password"])
    created_at = iso_now()

    with get_connection() as conn:
        created = fetchone(
            conn,
            """
            INSERT INTO users (name, email, role, password_hash, password_salt, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            (
                cleaned["name"],
                cleaned["email"],
                cleaned["role"],
                password_hash,
                salt,
                created_at,
            ),
        )
        user_id = created["id"]
    return get_user_by_id(user_id)


def delete_user(user_id):
    with get_connection() as conn:
        execute(conn, "DELETE FROM sessions WHERE user_id = ?", (user_id,))
        cursor = execute(conn, "DELETE FROM users WHERE id = ?", (user_id,))
    return cursor.rowcount > 0


def create_session(user_id):
    token = secrets.token_urlsafe(32)
    token_hash = hash_token(token)
    created_at = iso_now()
    expires_at = (utc_now() + timedelta(days=SESSION_TTL_DAYS)).isoformat()

    with get_connection() as conn:
        execute(
            conn,
            """
            INSERT INTO sessions (user_id, token_hash, expires_at, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, token_hash, expires_at, created_at),
        )
    return token


def delete_session(token):
    with get_connection() as conn:
        execute(conn, "DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))


def get_current_user_from_token(token):
    if not token:
        return None

    with get_connection() as conn:
        row = fetchone(
            conn,
            """
            SELECT users.id, users.name, users.email, users.role, users.created_at, sessions.expires_at
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token_hash = ?
            """,
            (hash_token(token),),
        )

    if not row:
        return None

    if datetime.fromisoformat(row["expires_at"]) <= utc_now():
        delete_session(token)
        return None

    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "role": row["role"],
        "created_at": row["created_at"],
    }


class FeaturePriorityHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def send_json(self, payload, status=200, headers=None):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if headers:
            if isinstance(headers, dict):
                headers = list(headers.items())
            for key, value in headers:
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def clear_session_cookie(self):
        jar = cookies.SimpleCookie()
        jar[SESSION_COOKIE] = ""
        jar[SESSION_COOKIE]["path"] = "/"
        jar[SESSION_COOKIE]["max-age"] = 0
        return jar.output(header="").strip()

    def clear_oidc_state_cookie(self):
        jar = cookies.SimpleCookie()
        jar[OIDC_STATE_COOKIE] = ""
        jar[OIDC_STATE_COOKIE]["path"] = "/"
        jar[OIDC_STATE_COOKIE]["max-age"] = 0
        return jar.output(header="").strip()

    def set_session_cookie(self, token):
        jar = cookies.SimpleCookie()
        jar[SESSION_COOKIE] = token
        jar[SESSION_COOKIE]["path"] = "/"
        jar[SESSION_COOKIE]["httponly"] = True
        jar[SESSION_COOKIE]["samesite"] = "Lax"
        jar[SESSION_COOKIE]["max-age"] = SESSION_TTL_DAYS * 24 * 60 * 60
        if COOKIE_SECURE or self.headers.get("X-Forwarded-Proto", "").lower() == "https":
            jar[SESSION_COOKIE]["secure"] = True
        return jar.output(header="").strip()

    def set_oidc_state_cookie(self, payload):
        jar = cookies.SimpleCookie()
        jar[OIDC_STATE_COOKIE] = encode_state_payload(payload)
        jar[OIDC_STATE_COOKIE]["path"] = "/"
        jar[OIDC_STATE_COOKIE]["httponly"] = True
        jar[OIDC_STATE_COOKIE]["samesite"] = "Lax"
        jar[OIDC_STATE_COOKIE]["max-age"] = 15 * 60
        if COOKIE_SECURE or self.headers.get("X-Forwarded-Proto", "").lower() == "https":
            jar[OIDC_STATE_COOKIE]["secure"] = True
        return jar.output(header="").strip()

    def parse_body(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON body.")

    def read_session_token(self):
        header = self.headers.get("Cookie")
        if not header:
            return None
        jar = cookies.SimpleCookie()
        jar.load(header)
        morsel = jar.get(SESSION_COOKIE)
        return morsel.value if morsel else None

    def current_user(self):
        return get_current_user_from_token(self.read_session_token())

    def get_request_origin(self):
        proto = self.headers.get("X-Forwarded-Proto", "http")
        host = self.headers.get("X-Forwarded-Host") or self.headers.get("Host", "")
        return f"{proto}://{host}"

    def get_microsoft_redirect_uri(self):
        if MICROSOFT_REDIRECT_URI:
            return MICROSOFT_REDIRECT_URI
        return f"{self.get_request_origin()}/api/auth/callback/microsoft"

    def read_oidc_state_cookie(self):
        header = self.headers.get("Cookie")
        if not header:
            return None
        jar = cookies.SimpleCookie()
        jar.load(header)
        morsel = jar.get(OIDC_STATE_COOKIE)
        if not morsel:
            return None
        try:
            return decode_state_payload(morsel.value)
        except Exception:
            return None

    def redirect(self, location, headers=None):
        self.send_response(302)
        self.send_header("Location", location)
        if headers:
            if isinstance(headers, dict):
                headers = list(headers.items())
            for key, value in headers:
                self.send_header(key, value)
        self.end_headers()

    def require_auth(self):
        user = self.current_user()
        if not user:
            self.send_json({"error": "Authentication required."}, 401)
            return None
        return user

    def require_role(self, allowed_roles):
        user = self.require_auth()
        if not user:
            return None
        if user["role"] not in allowed_roles:
            self.send_json({"error": "You do not have permission for this action."}, 403)
            return None
        return user

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)

        if parsed.path == "/api/auth/config":
            self.send_json({"microsoftEnabled": microsoft_enabled()})
            return

        if parsed.path == "/api/auth/microsoft/start":
            if not microsoft_enabled():
                self.send_json({"error": "Microsoft SSO is not configured."}, 400)
                return

            callback_url = query.get("callbackURL", ["/"])[0]
            state = secrets.token_urlsafe(24)
            nonce = secrets.token_urlsafe(24)
            payload = {"state": state, "nonce": nonce, "callbackURL": callback_url}
            metadata = get_microsoft_metadata()
            authorize_url = metadata["authorization_endpoint"] + "?" + urlencode(
                {
                    "client_id": MICROSOFT_CLIENT_ID,
                    "response_type": "code",
                    "redirect_uri": self.get_microsoft_redirect_uri(),
                    "response_mode": "query",
                    "scope": MICROSOFT_OIDC_SCOPE,
                    "state": state,
                    "nonce": nonce,
                    "prompt": "select_account",
                }
            )
            self.redirect(authorize_url, headers={"Set-Cookie": self.set_oidc_state_cookie(payload)})
            return

        if parsed.path == "/api/auth/callback/microsoft":
            if not microsoft_enabled():
                self.redirect("/")
                return

            cookie_state = self.read_oidc_state_cookie()
            state = query.get("state", [""])[0]
            code = query.get("code", [""])[0]
            error = query.get("error", [""])[0]
            callback_url = "/"

            if cookie_state:
                callback_url = cookie_state.get("callbackURL") or "/"

            clear_cookie = self.clear_oidc_state_cookie()

            if error:
                self.redirect(f"/?authError={error}", headers={"Set-Cookie": clear_cookie})
                return

            if not cookie_state or cookie_state.get("state") != state or not code:
                self.redirect("/?authError=invalid_state", headers={"Set-Cookie": clear_cookie})
                return

            metadata = get_microsoft_metadata()
            token_response = http_form(
                metadata["token_endpoint"],
                {
                    "client_id": MICROSOFT_CLIENT_ID,
                    "client_secret": MICROSOFT_CLIENT_SECRET,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.get_microsoft_redirect_uri(),
                    "scope": MICROSOFT_OIDC_SCOPE,
                },
            )
            claims = validate_microsoft_token(token_response["id_token"], cookie_state["nonce"])
            email = get_email_from_claims(claims)
            if not email:
                self.redirect("/?authError=no_email", headers={"Set-Cookie": clear_cookie})
                return

            if not domain_allowed(email):
                self.redirect("/?authError=domain_not_allowed", headers={"Set-Cookie": clear_cookie})
                return

            try:
                user = get_or_create_sso_user(email, claims.get("name", ""))
            except ValueError:
                self.redirect("/?authError=not_provisioned", headers={"Set-Cookie": clear_cookie})
                return

            token = create_session(user["id"])
            self.redirect(
                callback_url,
                headers=[
                    ("Set-Cookie", self.clear_oidc_state_cookie()),
                    ("Set-Cookie", self.set_session_cookie(token)),
                ],
            )
            return

        if parsed.path == "/api/me":
            user = self.require_auth()
            if user:
                self.send_json(user)
            return

        if parsed.path == "/api/features":
            if not self.require_auth():
                return
            self.send_json(list_features())
            return

        if parsed.path == "/api/mentionable-users":
            if not self.require_auth():
                return
            self.send_json(list_mentionable_users())
            return

        if parsed.path == "/api/users":
            if not self.require_role({"admin"}):
                return
            self.send_json(list_users())
            return

        if parsed.path.startswith("/api/features/"):
            if not self.require_auth():
                return
            feature_id = parsed.path.rsplit("/", 1)[-1]
            if not feature_id.isdigit():
                self.send_json({"error": "Invalid feature id."}, 400)
                return
            feature = get_feature(int(feature_id))
            if not feature:
                self.send_json({"error": "Feature not found."}, 404)
                return
            self.send_json(feature)
            return

        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/login":
            try:
                payload = self.parse_body()
                email = str(payload.get("email", "")).strip().lower()
                password = str(payload.get("password", ""))
                user = get_user_by_email(email)
                if not user or not verify_password(password, user["password_salt"], user["password_hash"]):
                    self.send_json({"error": "Invalid email or password."}, 401)
                    return

                token = create_session(user["id"])
                response_user = normalize_user(user)
                self.send_json(
                    response_user,
                    200,
                    headers={"Set-Cookie": self.set_session_cookie(token)},
                )
            except ValueError as error:
                self.send_json({"error": str(error)}, 400)
            return

        if parsed.path == "/api/logout":
            token = self.read_session_token()
            if token:
                delete_session(token)
            self.send_json({"ok": True}, headers={"Set-Cookie": self.clear_session_cookie()})
            return

        if parsed.path == "/api/features":
            if not self.require_role(ROLE_EDITORS):
                return
            try:
                feature = create_feature(self.parse_body())
                self.send_json(feature, 201)
            except ValueError as error:
                self.send_json({"error": str(error)}, 400)
            return

        if parsed.path == "/api/users":
            if not self.require_role({"admin"}):
                return
            try:
                user = create_user(self.parse_body())
                self.send_json(user, 201)
            except ValueError as error:
                self.send_json({"error": str(error)}, 400)
            return

        self.send_json({"error": "Not found."}, 404)

    def do_PUT(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/features/"):
            self.send_json({"error": "Not found."}, 404)
            return

        if not self.require_role(ROLE_EDITORS):
            return

        feature_id = parsed.path.rsplit("/", 1)[-1]
        if not feature_id.isdigit():
            self.send_json({"error": "Invalid feature id."}, 400)
            return

        try:
            feature = update_feature(int(feature_id), self.parse_body())
            if not feature:
                self.send_json({"error": "Feature not found."}, 404)
                return
            self.send_json(feature)
        except ValueError as error:
            self.send_json({"error": str(error)}, 400)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/users/"):
            current_user = self.require_role({"admin"})
            if not current_user:
                return

            user_id = parsed.path.rsplit("/", 1)[-1]
            if not user_id.isdigit():
                self.send_json({"error": "Invalid user id."}, 400)
                return

            if int(user_id) == current_user["id"]:
                self.send_json({"error": "You cannot delete your own account."}, 400)
                return

            deleted = delete_user(int(user_id))
            if not deleted:
                self.send_json({"error": "User not found."}, 404)
                return
            self.send_json({"ok": True})
            return

        if not parsed.path.startswith("/api/features/"):
            self.send_json({"error": "Not found."}, 404)
            return

        if not self.require_role(ROLE_EDITORS):
            return

        feature_id = parsed.path.rsplit("/", 1)[-1]
        if not feature_id.isdigit():
            self.send_json({"error": "Invalid feature id."}, 400)
            return

        deleted = delete_feature(int(feature_id))
        if not deleted:
            self.send_json({"error": "Feature not found."}, 404)
            return
        self.send_json({"ok": True})


def run():
    admin_info = init_db()
    if admin_info:
        print("Bootstrap admin account created.")
        print(f"Email: {admin_info['email']}")
        if admin_info["generated"]:
            print(f"Temporary password: {admin_info['password']}")
            print("Set APP_ADMIN_PASSWORD before first run if you want to control this value.")
        else:
            print("Password loaded from APP_ADMIN_PASSWORD.")

    server = ThreadingHTTPServer((HOST, PORT), FeaturePriorityHandler)
    print(f"Feature Priority Framework running on http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    run()
