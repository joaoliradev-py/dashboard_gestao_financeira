import os
from datetime import datetime, timedelta
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.express as px
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

MESES_BR = {
    1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril', 5: 'Maio', 6: 'Junho',
    7: 'Julho', 8: 'Agosto', 9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
}

RESET_DAY = 25

def get_cycle_start(date):
    """Retorna o início do ciclo financeiro para uma determinada data."""
    if date.day < RESET_DAY:
        m = date.month - 1
        y = date.year
        if m == 0:
            m = 12
            y -= 1
        return datetime(y, m, RESET_DAY)
    return datetime(date.year, date.month, RESET_DAY)

# Inicialização do App
app = dash.Dash(
    __name__, 
    suppress_callback_exceptions=True, 
    assets_folder='Assets',
    title="Tospi Gestão Financeira"
)
server = app.server # Expondo o servidor Flask para o Gunicorn

# Cores baseadas na identidade visual (Será ajustado melhor com a paleta mais tarde)
COLORS = {
    'bg': '#f4f4f9',
    'sidebar': '#1e903a',
    'sidebar_text': '#ecf0f1',
    'navbar': '#ffffff',
    'card': '#ffffff',
    'text': '#333333',
    'primary': '#1e903a'
}

# Supabase Cliente
url = os.environ.get("SUPABASE_URL", "")
key = os.environ.get("SUPABASE_KEY", "")
try:
    supabase: Client = create_client(url, key)
except:
    supabase = None
    print("Aviso: Supabase desabilitado no Dashboard.")

def fetch_data():
    if not supabase:
        # Mock Data para testes visuais
        df_n = pd.DataFrame({
            "data_compra": ["2026-04-01", "2026-04-02", "2026-04-03"],
            "total": [150.50, 45.00, 320.10]
        })
        df_t = pd.DataFrame({
            "Produto": ["Desinfetante Omo", "Coca-Cola 2L", "Picanha Fatiada"],
            "Qtd": [2, 1, 1],
            "Unitário (R$)": [15.50, 9.50, 65.00],
            "Data Compra": ["01/04/2026", "02/04/2026", "03/04/2026"]
        })
        return df_n, df_t
    try:
        # Puxa cabeçalhos
        res_notas = supabase.table("notas_fiscais").select("*").execute()
        df_notas = pd.DataFrame(res_notas.data) if res_notas.data else pd.DataFrame()
        
        # Puxa itens
        res_itens = supabase.table("itens_nota").select("*").execute()
        df_itens = pd.DataFrame(res_itens.data) if res_itens.data else pd.DataFrame()

        df_tabela = pd.DataFrame()
        
        if not df_notas.empty:
            df_notas = df_notas.rename(columns={"data_emissao": "data_compra", "valor_total_nota": "total"})
            if 'data_compra' in df_notas.columns:
                df_notas['data_compra_grafico'] = pd.to_datetime(df_notas['data_compra']).dt.strftime('%Y-%m-%d')
                df_notas['data_compra_br'] = pd.to_datetime(df_notas['data_compra']).dt.strftime('%d/%m/%Y')
                
            if not df_itens.empty:
                # Junta itens e notas para formar a visualização da tabela
                df_merged = pd.merge(df_itens, df_notas, left_on='nota_id', right_on='id', how='left')
                
                # Consertar falha de importação do OpenCV (1.0000 virava 10000 por remoção cega de pontos)
                df_merged['quantidade'] = df_merged['quantidade'].apply(lambda x: x / 10000 if x >= 1000 else x)
                # Garantir também a leitura do qtde para quem perdeu apenas 3 zeros (1.000 virou 1000)
                df_merged['quantidade'] = df_merged['quantidade'].apply(lambda x: x / 1000 if x >= 100 and x < 1000 else x)
                
                df_tabela['Produto'] = df_merged['nome_produto']
                df_tabela['Qtd'] = df_merged['quantidade']
                df_tabela['Unitário (R$)'] = round(df_merged['valor_total_item'] / df_merged['quantidade'].replace(0, 1), 2)
                df_tabela['Data Compra'] = df_merged['data_compra_br']
                
        return df_notas, df_tabela
    except Exception as e:
        print(f"Erro ao buscar notas: {e}")
        return pd.DataFrame(), pd.DataFrame()

# Layouts
sidebar = html.Div(
    [
        html.Div(
            html.Img(src='/assets/Topsi.png', className='float-animation', style={
                'width': '100px', 
                'height': '100px', 
                'borderRadius': '50%', 
                'border': '3px solid #ecf0f1',
                'objectFit': 'cover'
            }), 
            style={'textAlign': 'center', 'padding': '20px'}
        ),
        html.Div([
            html.Label("Sua Renda Mensal (R$):", style={'color': '#bdc3c7', 'fontSize': '14px', 'marginBottom': '5px', 'display': 'block'}),
            dcc.Input(
                id='input-salario',
                type='number',
                value=5000,
                step=100,
                style={'width': '85%', 'padding': '10px', 'borderRadius': '5px', 'border': 'none', 'marginBottom': '10px', 'backgroundColor': '#ecf0f1', 'color': '#2c3e50', 'fontWeight': 'bold'}
            )
        ], style={'padding': '0 20px', 'marginTop': '10px'}),
        html.Ul(
            [
                html.Li(dcc.Link("Tabela de Gastos do Mês", href="/", className='sidebar-link', style={'color': COLORS['sidebar_text'], 'textDecoration': 'none'})),
                html.Li(dcc.Link("Gráficos de Gastos Mensais", href="/graficos", className='sidebar-link', style={'color': COLORS['sidebar_text'], 'textDecoration': 'none'})),
            ],
            style={'listStyleType': 'none', 'padding': '20px'}
        )
    ],
    style={
        "position": "fixed",
        "top": 0,
        "left": 0,
        "bottom": 0,
        "width": "250px",
        "padding": "20px 0",
        "backgroundColor": COLORS['sidebar']
    },
)

def get_cycle_label(start_date):
    """Gera uma string amigável para o intervalo do ciclo."""
    m_end = start_date.month + 1
    y_end = start_date.year
    if m_end > 12:
        m_end = 1
        y_end += 1
    return f"25 de {MESES_BR[start_date.month]} até 24 de {MESES_BR[m_end]}"

content = dcc.Loading(
    id="loading-content",
    type="dot",
    children=html.Div(id="page-content", style={"marginLeft": "270px", "padding": "20px", "backgroundColor": COLORS['bg'], "minHeight": "100vh"}),
    color=COLORS['primary']
)

app.layout = html.Div(
    [dcc.Location(id="url"), sidebar, content],
    style={'fontFamily': '"Segoe UI", Roboto, "Helvetica Neue", sans-serif'}
)

# Callbacks de roteamento
@app.callback(Output("page-content", "children"), [Input("url", "pathname"), Input("input-salario", "value")])
def render_page_content(pathname, salario_input):
    salario = salario_input or 0
    df_notas, df_tabela = fetch_data()
    
    if pathname == "/":
        current_cycle_start = get_cycle_start(datetime.now())
        
        # Filtra a tabela para mostrar apenas itens do ciclo atual
        df_tabela_filtrada = pd.DataFrame()
        if not df_tabela.empty:
            df_tabela['date_obj'] = pd.to_datetime(df_tabela['Data Compra'], format='%d/%m/%Y')
            df_tabela_filtrada = df_tabela[df_tabela['date_obj'] >= current_cycle_start]
            df_tabela_filtrada = df_tabela_filtrada.drop(columns=['date_obj'])

        return html.Div([
            html.H1(f'Itens Comprados ({get_cycle_label(current_cycle_start)})', style={'color': COLORS['text'], 'fontSize': '24px'}),
            html.Div([
                # Simples representação de tabela baseada no DF formatado
                html.Table(
                    # Header
                    [html.Tr([html.Th(col, style={'padding': '10px', 'borderBottom': '3px solid #ddd', 'color': COLORS['sidebar']}) for col in df_tabela_filtrada.columns])] +
                    # Body
                    [html.Tr([html.Td(df_tabela_filtrada.iloc[i][col], style={'padding': '8px', 'borderBottom': '1px solid #f1f1f1'}) for col in df_tabela_filtrada.columns]) for i in range(len(df_tabela_filtrada))],
                    style={'width': '100%', 'textAlign': 'left', 'backgroundColor': COLORS['card'], 'padding': '15px', 'borderRadius': '10px', 'fontSize': '13px'}
                )
            ], style={'overflowX': 'auto', 'marginTop': '20px'}) if not df_tabela_filtrada.empty else html.P("Nenhum dado encontrado para o ciclo atual.")
        ], className='fade-in')
    elif pathname == "/graficos":
        hoje = datetime.now()
        current_cycle_start = get_cycle_start(hoje)
        titulo_dinamico = f"Resumo: {get_cycle_label(current_cycle_start)}"

        # Filtrar DF para o ciclo atual para a caixa de "Gasto no Mês"
        total_gasto = 0
        if not df_notas.empty:
            df_notas['date_obj'] = pd.to_datetime(df_notas['data_compra_grafico'])
            df_notas_ciclo_atual = df_notas[df_notas['date_obj'] >= current_cycle_start]
            if "total" in df_notas_ciclo_atual.columns:
                total_gasto = df_notas_ciclo_atual["total"].sum()

        tabs_historico = []
        if not df_notas.empty:
            ref_date = hoje
            next_cycle_start = None
            for i in range(3): # Historico do Mês atual e 2 passados
                cycle_start = get_cycle_start(ref_date)
                
                if i == 0:
                    # Ciclo atual (do dia 25 até hoje)
                    df_ciclo = df_notas[df_notas['date_obj'] >= cycle_start]
                    label = "Ciclo Atual"
                else:
                    # Ciclos anteriores (entre dois dias 25)
                    df_ciclo = df_notas[(df_notas['date_obj'] >= cycle_start) & (df_notas['date_obj'] < next_cycle_start)]
                    label = get_cycle_label(cycle_start)
                
                fig = px.line(
                    df_ciclo, x="data_compra_grafico", y="total", 
                    title=f"Evolução de Gastos - {label}", markers=True
                ) if not df_ciclo.empty else px.line(title=f"Sem gastos em: {label}")
                
                fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=40, b=40, l=40, r=40))
                
                abas = dcc.Tab(label=label, children=[
                    html.Div(dcc.Graph(figure=fig), style={'padding': '20px', 'backgroundColor': '#ffffff', 'borderRadius': '0 0 10px 10px'})
                ])
                tabs_historico.append(abas)
                
                # Prepara para o ciclo anterior
                next_cycle_start = cycle_start
                ref_date = cycle_start - timedelta(days=1)
        else:
             tabs_historico.append(dcc.Tab(label="Atual", children=[dcc.Graph(figure=px.line(title="Sem dados suficientes"))]))

        return html.Div([
            html.H1(titulo_dinamico, style={'color': COLORS['text']}),
            html.Div([
                html.Div([
                    html.H3("Gasto no Mês", style={'margin': 0, 'color': '#7f8c8d'}),
                    html.H2(f"R$ {total_gasto:.2f}", style={'margin': 0, 'color': '#e74c3c'})
                ], className='custom-card', style={'backgroundColor': COLORS['card'], 'padding': '20px', 'borderRadius': '10px', 'width': '30%', 'display': 'inline-block', 'marginRight': '20px'}),
                html.Div([
                    html.H3("Dinheiro Restante", style={'margin': 0, 'color': '#7f8c8d'}),
                    html.H2(f"R$ {(salario - total_gasto):.2f}", style={'margin': 0, 'color': '#2ecc71'})
                ], className='custom-card', style={'backgroundColor': COLORS['card'], 'padding': '20px', 'borderRadius': '10px', 'width': '30%', 'display': 'inline-block'}),
            ], style={'marginBottom': '30px'}),
            html.Div([
                dcc.Tabs(children=tabs_historico, colors={
                    "border": "#d2d7d3",
                    "primary": COLORS['primary'],
                    "background": "#f9f9f9"
                })
            ], style={'backgroundColor': 'transparent', 'borderRadius': '10px'})
        ], className='fade-in')
    return html.Div([
        html.H1("404: Não Encontrado", className="text-danger"),
        html.Hr(),
        html.P(f"O pathname {pathname} não foi reconhecido...")
    ])

if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
