import os
import datetime
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from dotenv import load_dotenv

from helpers import apology, login_required, lookup, usd

# Load API key from .env file
load_dotenv()

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded and register custom filter
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Ensure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user_id = session["user_id"]
    rows = db.execute(
        "SELECT symbol, SUM(shares) AS shares"
        " FROM transactions"
        " WHERE user_id = ?"
        " GROUP BY symbol"
        " HAVING shares > 0", user_id
    )

    portfolio = []
    total_value = 0
    for row in rows:
        symbol = row["symbol"]
        shares = row["shares"]
        quote = lookup(symbol)
        if not quote:
            return apology(f"Could not retrieve quote for {symbol}")
        price = quote["price"]
        value = shares * price
        total_value += value
        portfolio.append({
            "symbol": symbol,
            "name": quote["name"],
            "shares": shares,
            "price": price,
            "value": value
        })

    cash_row = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]
    cash = cash_row["cash"]
    total_value += cash

    return render_template("index.html", portfolio=portfolio, cash=cash, total=total_value)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    if request.method == "GET":
        return render_template("buy.html")

    symbol = request.form.get("symbol")
    if not symbol:
        return apology("must provide symbol", 400)

    share_str = request.form.get("shares")
    if not share_str or not share_str.isdigit():
        return apology("shares must be a positive integer", 400)
    shares = int(share_str)
    if shares <= 0:
        return apology("shares must be positive", 400)

    stock = lookup(symbol.upper())
    if not stock:
        return apology("invalid symbol", 400)

    user_id = session["user_id"]
    cash_row = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]
    cash = cash_row["cash"]
    cost = shares * stock["price"]
    if cash < cost:
        return apology("not enough cash", 400)

    db.execute("UPDATE users SET cash = ? WHERE id = ?", cash - cost, user_id)
    timestamp = datetime.datetime.now()
    db.execute(
        "INSERT INTO transactions (user_id, symbol, shares, price, date)"
        " VALUES (?, ?, ?, ?, ?)",
        user_id, stock["symbol"], shares, stock["price"], timestamp
    )

    flash(f"Bought {shares} shares of {stock['symbol']}")
    return redirect("/")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    user_id = session["user_id"]

    if request.method == "GET":
        rows = db.execute(
            "SELECT symbol FROM transactions"
            " WHERE user_id = ?"
            " GROUP BY symbol"
            " HAVING SUM(shares) > 0", user_id
        )
        symbols = [row["symbol"] for row in rows]
        return render_template("sell.html", symbols=symbols)

    symbol = request.form.get("symbol")
    if not symbol:
        return apology("must provide symbol", 400)

    share_str = request.form.get("shares")
    if not share_str or not share_str.isdigit():
        return apology("shares must be a positive integer", 400)
    shares = int(share_str)
    if shares <= 0:
        return apology("shares must be positive", 400)

    owned = db.execute(
        "SELECT SUM(shares) AS shares FROM transactions"
        " WHERE user_id = ? AND symbol = ?", user_id, symbol
    )[0]["shares"]
    if shares > owned:
        return apology("not enough shares", 400)

    stock = lookup(symbol)
    if not stock:
        return apology("invalid symbol", 400)
    revenue = shares * stock["price"]

    cash_row = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]
    db.execute("UPDATE users SET cash = ? WHERE id = ?", cash_row["cash"] + revenue, user_id)
    timestamp = datetime.datetime.now()
    db.execute(
        "INSERT INTO transactions (user_id, symbol, shares, price, date)"
        " VALUES (?, ?, ?, ?, ?)",
        user_id, symbol, -shares, stock["price"], timestamp
    )

    flash(f"Sold {shares} shares of {symbol}")
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    if request.method == "GET":
        return render_template("quote.html")

    symbol = request.form.get("symbol")
    if not symbol:
        return apology("must provide symbol", 400)

    stock = lookup(symbol.upper())
    if not stock:
        return apology("invalid symbol", 400)

    return render_template("quoted.html", name=stock["name"], price=stock["price"], symbol=stock["symbol"])


@app.route("/history")
@login_required
def history():
    user_id = session["user_id"]
    rows = db.execute(
        "SELECT symbol, shares, price, date"
        " FROM transactions"
        " WHERE user_id = ?"
        " ORDER BY date DESC", user_id
    )
    return render_template("history.html", transactions=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    session.clear()

    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if not username or not password:
            return apology("must provide username and password", 403)
        rows = db.execute("SELECT * FROM users WHERE username = ?", [username])
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], password):
            return apology("invalid username and/or password", 403)
        session["user_id"] = rows[0]["id"]
        return redirect("/")
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    username = request.form.get("username")
    password = request.form.get("password")
    confirmation = request.form.get("confirmation")

    if not username or not password or not confirmation:
        return apology("must fill all fields", 400)
    if password != confirmation:
        return apology("passwords do not match", 400)

    hashpw = generate_password_hash(password)

    try:
        db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hashpw)
    except Exception:
        return apology("username already exists", 400)

    user = db.execute("SELECT id FROM users WHERE username = ?", username)
    session["user_id"] = user[0]["id"]

    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)
