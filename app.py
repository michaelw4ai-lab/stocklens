import secrets
from functools import wraps

from flask import Flask, render_template, jsonify, request, session, redirect, url_for

from auth import register, authenticate
from data import (
    get_dashboard_data, get_price_history, get_top10_analysis,
    refresh_dashboard, refresh_top10, refresh_cache,
)

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)


def login_required_api(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return jsonify({"error": "login_required"}), 401
        return f(*args, **kwargs)
    return decorated


@app.route("/")
def index():
    return render_template("index.html", user=session.get("user"))


@app.route("/analysis")
def analysis():
    return render_template("analysis.html", user=session.get("user"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if authenticate(username, password):
            session["user"] = username.strip().lower()
            next_url = request.args.get("next", "/")
            return redirect(next_url)
        return render_template("login.html", error="Invalid username or password.", username=username)
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register_page():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if password != confirm:
            return render_template("register.html", error="Passwords do not match.", username=username)
        ok, msg = register(username, password)
        if ok:
            session["user"] = username.strip().lower()
            return redirect("/")
        return render_template("register.html", error=msg, username=username)
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/")


@app.route("/api/stocks")
def api_stocks():
    data = get_dashboard_data()
    return jsonify(data)


@app.route("/api/stock/<symbol>")
def api_stock(symbol):
    history = get_price_history(symbol.upper())
    return jsonify(history)


@app.route("/api/top10")
def api_top10():
    data = get_top10_analysis()
    return jsonify(data)


@app.route("/api/refresh", methods=["POST"])
@login_required_api
def api_refresh():
    refresh_cache()
    data = refresh_dashboard()
    return jsonify(data)


@app.route("/api/refresh-top10", methods=["POST"])
@login_required_api
def api_refresh_top10():
    refresh_cache()
    data = refresh_top10()
    return jsonify(data)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
