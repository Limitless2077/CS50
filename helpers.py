import os
import requests
import urllib.parse

from flask import redirect, render_template, request, session
from functools import wraps


def apology(message, code=400):
    """Render message as an apology to user with given HTTP status code."""
    def escape(s):
        """
        Escape special characters for display in apology template.
        """
        for old, new in [
            ("-", "--"), (" ", "-"), ("_", "__"), ("?", "~q"),
            ("%", "~p"), ("#", "~h"), ("/", "~s"), ("\"", "''")
        ]:
            s = s.replace(old, new)
        return s

    return render_template("apology.html", top=code, bottom=escape(message)), code


def login_required(f):
    """Decorator that redirects users to login page if not logged in."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def lookup(symbol):
    """Look up quote for symbol using Alpha Vantage."""
    # Hardcoded API key
    api_key = "TJ10JLDBL9DLDN1D"

    try:
        url = (
            f"https://www.alphavantage.co/query"
            f"?function=GLOBAL_QUOTE&symbol={urllib.parse.quote_plus(symbol)}&apikey={api_key}"
        )
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        quote = data.get("Global Quote")
        if not quote:
            return None

        return {
            "name": symbol.upper(),  # Alpha Vantage doesn't return company name
            "price": float(quote["05. price"]),
            "symbol": quote["01. symbol"]
        }
    except (requests.RequestException, KeyError, ValueError, TypeError):
        return None


def usd(value):
    """Format numeric value as USD currency."""
    try:
        return f"${value:,.2f}"
    except (TypeError, ValueError):
        return "$0.00"
