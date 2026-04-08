import os
from datetime import datetime
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

# Carrega variáveis de ambiente
load_dotenv()

# Configurações iniciais
MESES_BR = {
    1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho',
    7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
}

COLORS = {
    'bg': '#f4f4f9',
    'sidebar': '#1e903a',
    'sidebar_text': '#ecf0f1',
    'navbar': '#ffffff',
    'card': '#ffffff',
    'text': '#333333',
    'primary': '#1e903a'
}

# --- INICIALIZAÇÃO DO APP (IMPORTANTE PARA O RENDER) ---
app = dash.Dash(__name__, suppress_callback_exceptions=True)
server = app.server  # O Gunicorn vai procurar esta variável!
# -------------------------------------------------------

# Conexão Supabase
url = os.environ.get("SUPABASE_URL", "")
key = os.environ.get("SUPABASE_KEY", "")
try:
    supabase: Client = create_client(url, key)
except:
    supabase = None
    print("Aviso: Supabase desabilitado no Dashboard.")

def fetch_data():
    if not supabase:
        df_n = pd.DataFrame({"data_compra": ["2026-04-01"], "total": [150.50]})
        df_t = pd.DataFrame({"Produto": ["Teste"], "Qtd": [1], "Unitário (R$)": [10.0], "Data Compra": ["01/04/2026"]})
        return df_n, df_t
    
    try:
        res_notas = supabase.table("notas_fiscais").select("*").execute()
        df_notas = pd.DataFrame(res_notas.data) if res_notas.data else pd.DataFrame()
        
        res_itens = supabase.table("itens_nota").select("*").execute()
        df_itens = pd.DataFrame(res_itens.data) if res_itens.data else pd.DataFrame()

        df_tabela = pd.DataFrame()
        
        if not df_notas.empty:
            df_notas = df_notas.rename(columns={"data_emissao": "data_compra", "valor_total_nota": "total"})
            df_notas['data_compra_grafico'] = pd.to_datetime(df_notas['data_compra']).dt.strftime('%Y-%m-%d')
            df_notas['data_compra_br'] = pd.to_datetime(df_notas['data_compra']).dt.strftime('%d/%m/%Y')
                
            if not df_itens.empty:
                df_merged = pd.merge(df_itens, df_notas, left_on='nota_id', right_on='id', how='left')
                df_merged['quantidade'] = df_merged['quantidade'].apply(lambda x: x / 1000 if x >= 100 else x)
                
                df_tabela = pd.DataFrame({
                    'Produto': df_merged['nome_produto'],
                    'Qtd': df_merged['quantidade'],
                    'Unitário (R$)': (df_merged['valor_total_item'] / df_merged['quantidade'].replace(0, 1)).round(2),
                    'Data Compra': df_merged['data_compra_br']
                })
        return df_notas, df_tabela
    except Exception as e:
        print(f"Erro: {e}")
        return pd.DataFrame(), pd.DataFrame()

# Componentes de Layout
sidebar = html.Div([
    html.H2("Gestão", style={'color': COLORS['sidebar_text'], 'padding': '20px'}),
    html.Hr(style={'borderColor': '#34495e'}),
    html.Div([
        html.Label("Renda Mensal (R$):", style={'color': '#bdc3c7', 'fontSize': '14px'}),
        dcc.Input(id='input-salario', type='number', value=5000, style={'width': '90%', 'padding': '8px'})
    ], style={'padding': '20px'}),
    html.Ul([
        html.Li(dcc.Link("Tabela de Gastos", href="/", style={'color': COLORS['sidebar_text'], 'textDecoration': 'none'})),
        html.Li(dcc.Link("Gráficos", href="/graficos", style={'color': COLORS['sidebar_text'], 'textDecoration': 'none'})),
    ], style={'listStyleType': 'none', 'padding': '20px'})
], style={"position": "fixed", "top": 0, "left": 0, "bottom": 0, "width": "250px", "backgroundColor": COLORS['sidebar']})

content = html.Div(id="page-content", style={"marginLeft": "270px", "padding": "20px"})

app.layout = html.Div([dcc.Location(id="url"), sidebar, content])

@app.callback(Output("page-content", "children"), [Input("url", "pathname"), Input("input-salario", "value")])
def render_page_content(pathname, salario_input):
    df_notas, df_tabela = fetch_data()
    
    if pathname == "/":
        return html.Div([
            html.H1('Itens Comprados'),
            html.Table(
                [html.Tr([html.Th(col) for col in df_tabela.columns])] +
                [html.Tr([html.Td(df_tabela.iloc[i][col]) for col in df_tabela.columns]) for i in range(len(df_tabela))],
                style={'width': '100%', 'backgroundColor': 'white'}
            ) if not df_tabela.empty else html.P("Sem dados.")
        ])
    
    elif pathname == "/graficos":
        if df_notas.empty: return html.P("Sem dados para gráficos.")
        df_notas['date_obj'] = pd.to_datetime(df_notas['data_compra_grafico'])
        fig = px.line(df_notas, x="data_compra_grafico", y="total", title="Evolução de Gastos", markers=True)
        return html.Div([html.H1("Análise de Gastos"), dcc.Graph(figure=fig)])

if __name__ == "__main__":
    app.run_server(debug=True)
