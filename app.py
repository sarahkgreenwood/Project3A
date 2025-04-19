from flask import Flask, render_template, request, redirect, url_for, Blueprint, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objs as go
import plotly.offline as pyo

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.root_path, 'stocks.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
app.config['SECRET_KEY'] = 'your_secret_key'

stocks_bp = Blueprint('stocks', __name__)

# get stock names
df = pd.read_csv('stocks.csv')
symbols_list = df["Symbol"].tolist()

class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(200), nullable=False)
    time_series = db.Column(db.String(20), nullable=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    
    def __repr__(self):
        return f'<Stock {self.symbol}>'
    
#Create application views/routes
@stocks_bp.route('/', methods=['GET'])
def index():
    stocks = Stock.query.all()
    print(stocks)

    return render_template('index.html', stocks=stocks)

@stocks_bp.route('/create', methods=['GET'])
def create_stock_get():
    return render_template('create.html')

@stocks_bp.route('/create', methods=['POST'])
def create_stock_post():
    symbol = request.form['symbol']
    time_series = request.form['time_series']
    chart_type = request.form.get('chart_type')

    interval_map = {
        "Intraday": "60min",
        "Daily": "daily",
        "Weekly": "weekly",
        "Monthly": "monthly"
        
    }
    interval = interval_map.get(time_series, "daily")
    
    start_date_str = request.form['start_date']
    end_date_str = request.form['end_date']
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d') if start_date_str else None
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d') if end_date_str else None

    if not symbol:
        flash('Symbol is required.', 'error')
        return redirect(url_for('stocks.create_stock_get'))

    # Validate symbol against CSV list
    if symbol not in symbols_list:
        flash('Invalid stock symbol.', 'error')
        return redirect(url_for('stocks.create_stock_get'))

    # Build API URL
    api_key = "ZFKV84P0PVJWZKCU"

    if interval in ["1min", "5min", "15min", "30min", "60min"]:
        function = "TIME_SERIES_INTRADAY"
    else:
        function = f"TIME_SERIES_{interval.upper()}"

    interval_param = f"&interval={interval}" if function == "TIME_SERIES_INTRADAY" else ""

    
    url = (
        f"https://www.alphavantage.co/query?function={function}" +
        f"&symbol={symbol}{interval_param}&apikey={api_key}"
    )

    response = requests.get(url)
    if response.status_code != 200:
        flash('API request failed.', 'error')
        return redirect(url_for('stocks.create_stock_get'))

    data = response.json()
    


    time_series_key = next((key for key in data.keys() if "Time Series" in key), None)
    if not time_series_key:
        flash('API data format error or limit exceeded.', 'error')
        return redirect(url_for('stocks.create_stock_get'))
    else:
        print(time_series_key)

    try:
        records = data[time_series_key]
        df = pd.DataFrame.from_dict(records, orient='index')
        df.index = pd.to_datetime(df.index)
        df.sort_index(inplace=True)

        print("Raw DataFrame shape:", df.shape)
        print("Raw DataFrame head:\n", df.head())

        if start_date and end_date:
            df = df[(df.index >= start_date) & (df.index <= end_date)]

        chart_type = request.form.get('chart_type', 'Line')
        df['4. close'] = df['4. close'].astype(float)

        if chart_type == "Bar":
            fig = px.bar(df, x=df.index, y='4. close', title=f'{symbol} Stock Prices ({interval}) - Bar Chart')
        else:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df.index, y=df['4. close'], mode='lines', name='Close Price'))
            fig.update_layout(title=f'{symbol} Stock Prices ({interval}) - Line Chart',
                            xaxis_title='Date',
                            yaxis_title='Price (USD)',
                            template='plotly_white')

        graph_html = pyo.plot(fig, output_type='div')
        return render_template('chart.html', graph_html=graph_html)

    except Exception as e:
        print("Error processing stock data:", e)
        flash('Error processing stock data.', 'error')
        return redirect(url_for('stocks.create_stock_get'))

@stocks_bp.route('/update/<int:id>', methods=['GET'])
def update_stock_get(id):
    stock = Stock.query.get_or_404(id)
    return render_template('update.html', stock=stock)

@stocks_bp.route('/update/<int:id>', methods=['POST'])
def update_stock_post(id):
    stock = Stock.query.get_or_404(id)
    symbol = request.form['symbol']
    time_series = request.form['time_series']
    start_date_str = request.form['start_date']
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d') if start_date_str else None
    end_date_str = request.form['end_date']
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d') if end_date_str else None

    #if not symbol show error message
    if not symbol:
        flash('Symbol is required.', 'error')
        return redirect(url_for('stocks.update_stock_get', id=id))
    
    if symbol:
        if symbol not in symbols_list:
            flash('Incorrect symbol, try again.')
            return redirect(url_for('stocks.update_stock_get', id=id))

    stock.symbol = symbol
    stock.time_series = time_series
    stock.start_date = start_date
    stock.end_date = end_date
    db.session.commit()
    return redirect(url_for('stocks.index'))

@stocks_bp.route('/delete/<int:id>', methods=['POST'])
def delete_stock(id):
    stock = Stock.query.get_or_404(id)
    
    db.session.delete(stock)
    db.session.commit()
    return redirect(url_for('stocks.index'))


app.register_blueprint(stocks_bp)
with app.app_context():
    db.create_all()

def plot_stock_chart(time_series_data, chart_type="Line", symbol="N/A"):
    if not time_series_data:
        print("No data to plot.")
        return

    df = pd.DataFrame.from_dict(time_series_data, orient='index')
    df = df.sort_index()
    df["date"] = df.index
    df["close"] = df["4. close"].astype(float)

    fig = None
    if chart_type == "Bar":
        fig = px.bar(df, x="date", y="close", title=f"{symbol} - Last 20 Closing Prices")
    else:
        fig = px.line(df, x="date", y="close", title=f"{symbol} - Last 20 Closing Prices")

    fig.update_layout(xaxis_title="Date", yaxis_title="Closing Price", xaxis_tickangle=-45)
    fig.show()

def build_url(symbol, interval, start_date, end_date, api_key):
    base_url = "https://www.alphavantage.co/query"
    params = {
        "function": "ADVANCED_ANALYTICS",
        "symbol": symbol,
        "interval": "60min",
        "start_date": start_date,
        "end_date": end_date,
        "apikey": "ZFKV84P0PVJWZKCU"
    }

    query_string = "&".join(f"{key}={value}" for key, value in params.items())
    print(f"{base_url}?{query_string}")
    return f"{base_url}?{query_string}"

if __name__ == '__main__':
    app.run(debug=True, port=5019)