import os
import secrets
from functools import wraps

from authlib.integrations.flask_client import OAuth
from flask import Flask, render_template, jsonify, request, session, redirect, url_for

from data import (
    get_dashboard_data, get_price_history, get_top10_analysis,
    refresh_dashboard, refresh_top10, refresh_cache,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

# Google OAuth setup
oauth = OAuth(app)
oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


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


@app.route("/login")
def login():
    next_url = request.args.get("next", "/")
    session["login_next"] = next_url
    redirect_uri = url_for("auth_callback", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@app.route("/auth/callback")
def auth_callback():
    token = oauth.google.authorize_access_token()
    userinfo = token.get("userinfo")
    if userinfo:
        session["user"] = userinfo.get("email", userinfo.get("name", "User"))
        session["user_name"] = userinfo.get("name", "")
        session["user_picture"] = userinfo.get("picture", "")
    next_url = session.pop("login_next", "/")
    return redirect(next_url)


@app.route("/logout")
def logout():
    session.clear()
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
