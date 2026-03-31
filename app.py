from flask import Flask, render_template, jsonify

from data import (
    get_dashboard_data, get_price_history, get_top10_analysis,
    refresh_dashboard, refresh_top10, refresh_cache,
)

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/stocks")
def api_stocks():
    data = get_dashboard_data()
    return jsonify(data)


@app.route("/api/stock/<symbol>")
def api_stock(symbol):
    history = get_price_history(symbol.upper())
    return jsonify(history)


@app.route("/analysis")
def analysis():
    return render_template("analysis.html")


@app.route("/api/top10")
def api_top10():
    data = get_top10_analysis()
    return jsonify(data)


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    refresh_cache()
    data = refresh_dashboard()
    return jsonify(data)


@app.route("/api/refresh-top10", methods=["POST"])
def api_refresh_top10():
    refresh_cache()
    data = refresh_top10()
    return jsonify(data)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
