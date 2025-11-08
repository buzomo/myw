from flask import Flask, request, jsonify
import os
import secrets
import psycopg2
from datetime import datetime
import re

app = Flask(__name__)
TABLE_NAME = "wiki_pages_f7095a"

def get_db():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    return conn

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

@app.route("/page_list")
def page_list():
    ensure_table_exists()
    token = request.args.get("token")
    query = request.args.get("query", "")
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
    pages = [{"title": row[0], "content": row[1]} for row in rows]
    return jsonify(pages)

@app.route("/related_pages")
def related_pages():
    ensure_table_exists()
    token = request.args.get("token")
    title = request.args.get("title")
    conn = get_db()
    cur = conn.cursor()
    # キーワードリンクから関連ページを検索
    cur.execute(f"""
        SELECT title, content FROM {TABLE_NAME}
        WHERE token = %s AND content LIKE %s AND title != %s
        ORDER BY updated_at DESC
    """, (token, "%[[]%]", title))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    pages = [{"title": row[0], "content": row[1]} for row in rows]
    return jsonify(pages)

@app.route("/save", methods=["POST"])
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

if __name__ == "__main__":
    app.run()
