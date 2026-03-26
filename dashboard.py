import dash
from dash import dcc, html
import pandas as pd
import requests
import plotly.express as px

app = dash.Dash(__name__)
server = app.server # Render צריך את המשתנה הזה כדי להריץ את השרת

def fetch_data():
    url = "https://michaelketash.pythonanywhere.com/api/expenses"
    try:
        r = requests.get(url)
        return pd.DataFrame(r.json())
    except:
        return pd.DataFrame(columns=['merchant', 'amount', 'category', 'date'])

app.layout = html.Div([
    html.H1("Michael & Partner Finance Dashboard"),
    dcc.Graph(id='main-pie-chart'),
    dcc.Interval(id='interval-component', interval=60*1000, n_intervals=0)
])

@app.callback(dash.Output('main-pie-chart', 'figure'), [dash.Input('interval-component', 'n_intervals')])
def update_graph(n):
    df = fetch_data()
    if df.empty:
        return {}
    fig = px.pie(df, values='amount', names='category', title="הוצאות לפי קטגוריה")
    return fig

if __name__ == '__main__':
    app.run_server(debug=True)