from flask import Flask, render_template, request, jsonify, make_response, send_file
import os
import re
import secrets
import psycopg2
from datetime import datetime
import io

app = Flask(__name__)
app.secret_key = os.urandom(24)

# テーブル名（ランダムな6桁の16進数）
TABLE_NAME = "wiki_pages_f7095a"


def get_db():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    return conn


def ensure_table_exists():
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id SERIAL PRIMARY KEY,
            token TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(token, title)
        )
    """
    )
    conn.commit()
    cur.close()
    conn.close()


@app.route("/")
def index():
    ensure_table_exists()  # テーブルの存在を確認・作成
    token = request.args.get("token") or request.cookies.get("token")
    if not token:
        token = secrets.token_urlsafe(16)

    resp = make_response(render_template("index.html", token=token))
    resp.set_cookie("token", token)
    return resp


@app.route("/save", methods=["POST"])
def save():
    ensure_table_exists()  # テーブルの存在を確認・作成
    data = request.json
    token = data["token"]
    title = data["title"]
    content = data["content"]

    if not content.strip():
        return jsonify({"status": "error", "message": "Content is empty"}), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        f"""
        INSERT INTO {TABLE_NAME} (token, title, content, updated_at)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (token, title)
        DO UPDATE SET content = EXCLUDED.content, updated_at = EXCLUDED.updated_at
    """,
        (token, title, content, datetime.now()),
    )
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"status": "success"})


@app.route("/search_keywords", methods=["GET"])
def search_keywords():
    ensure_table_exists()  # テーブルの存在を確認・作成
    keyword = request.args.get("keyword")
    token = request.args.get("token")

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        f"""
        SELECT title FROM {TABLE_NAME}
        WHERE content LIKE %s AND token = %s
    """,
        (f"%[{keyword}]%", token),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([row[0] for row in rows])

@app.route("/load", methods=["GET"])
def load():
    ensure_table_exists()
    token = request.args.get("token")
    title = request.args.get("title")

    conn = get_db()
    cur = conn.cursor()
    cur.execute(f"SELECT content FROM {TABLE_NAME} WHERE token = %s AND title = %s", (token, title))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row:
        return jsonify({"status": "success", "content": row[0]})
    else:
        return jsonify({"status": "error", "message": "Not found"}), 404


@app.route("/archive", methods=["GET"])
def archive():
    ensure_table_exists()  # テーブルの存在を確認・作成
    token = request.args.get("token")
    conn = get_db()
    cur = conn.cursor()
    cur.execute(f"SELECT title, content FROM {TABLE_NAME} WHERE token = %s", (token,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    output = io.StringIO()
    for row in rows:
        output.write(f"# {row[0]}\n{row[1]}\n\n")
    output.seek(0)

    return send_file(
        io.BytesIO(output.read().encode("utf-8")),
        mimetype="text/plain",
        as_attachment=True,
        download_name="wiki_archive.txt",
    )


@app.route("/get_titles", methods=["GET"])
def get_titles():
    ensure_table_exists()
    token = request.args.get("token")

    conn = get_db()
    cur = conn.cursor()
    cur.execute(f"SELECT title FROM {TABLE_NAME} WHERE token = %s ORDER BY updated_at DESC", (token,))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    titles = [row[0] for row in rows]
    return jsonify(titles)

@app.route("/load_last", methods=["GET"])
def load_last():
    ensure_table_exists()
    token = request.args.get("token")

    conn = get_db()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT title, content
        FROM {TABLE_NAME}
        WHERE token = %s
        ORDER BY updated_at DESC
        LIMIT 1
    """, (token,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row:
        return jsonify({"status": "success", "title": row[0], "content": row[1]})
    else:
        return jsonify({"status": "error", "message": "Not found"}), 404


# if __name__ == "__main__": はVercelでは使用しない
