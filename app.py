from flask import Flask, request, jsonify, render_template, make_response
import os
import secrets
import psycopg2
from datetime import datetime
import re

app = Flask(__name__)
TABLE_NAME = "wiki_pages_f7095a"

def get_db():
    return psycopg2.connect(os.environ["DATABASE_URL"])

def ensure_table_exists():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id SERIAL PRIMARY KEY,
            token TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(token, title)
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

@app.route("/")
def index():
    ensure_table_exists()
    token = request.args.get("token") or request.cookies.get("token")
    if not token:
        token = secrets.token_urlsafe(16)
    resp = make_response(render_template("index.html", token=token))
    resp.set_cookie("token", token)
    return resp

@app.route("/api/page_list")
def page_list():
    ensure_table_exists()
    token = request.args.get("token")
    query = request.args.get("query", "").lower()
    conn = get_db()
    cur = conn.cursor()
    if query:
        cur.execute(f"""
            SELECT title, content FROM {TABLE_NAME}
            WHERE token = %s AND (LOWER(title) LIKE %s OR LOWER(content) LIKE %s)
            ORDER BY updated_at DESC
        """, (token, f"%{query}%", f"%{query}%"))
    else:
        cur.execute(f"""
            SELECT title, content FROM {TABLE_NAME}
            WHERE token = %s
            ORDER BY updated_at DESC
        """, (token,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([{"title": row[0], "content": row[1]} for row in rows])

@app.route("/api/related_pages")
def related_pages():
    ensure_table_exists()
    token = request.args.get("token")
    title = request.args.get("title")
    conn = get_db()
    cur = conn.cursor()

    # 現在開いているページの本文中の[キーワード]を抽出
    cur.execute(f"SELECT content FROM {TABLE_NAME} WHERE token = %s AND title = %s", (token, title))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return jsonify([])

    content = row[0]
    keywords = re.findall(r'\[([^\]]+)\]', content)
    if not keywords:
        cur.close()
        conn.close()
        return jsonify([])

    # キーワードを含むページを検索（現在のページを除外）
    keyword_conditions = " OR ".join([f"content LIKE '%%[{kw}]%%'" for kw in keywords])
    cur.execute(f"""
        SELECT title, content FROM {TABLE_NAME}
        WHERE token = %s AND title != %s AND ({keyword_conditions})
        ORDER BY updated_at DESC
    """, (token, title))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([{"title": row[0], "content": row[1]} for row in rows])

@app.route("/api/save", methods=["POST"])
def save():
    ensure_table_exists()
    data = request.json
    token = data["token"]
    title = data["title"]
    content = data["content"]
    conn = get_db()
    cur = conn.cursor()
    cur.execute(f"""
        INSERT INTO {TABLE_NAME} (token, title, content, updated_at)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (token, title)
        DO UPDATE SET content = EXCLUDED.content, updated_at = EXCLUDED.updated_at
    """, (token, title, content, datetime.now()))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"status": "success"})
