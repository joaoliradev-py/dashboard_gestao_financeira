import os
from datetime import datetime
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

# Inicialização do App
app = dash.Dash(__name__, suppress_callback_exceptions=True)

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
        html.H2("Gestão", className="display-4", style={'color': COLORS['sidebar_text'], 'padding': '20px'}),
        html.Hr(style={'borderColor': '#34495e'}),
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
                html.Li(dcc.Link("Tabela de Gastos do Mês", href="/", style={'color': COLORS['sidebar_text'], 'textDecoration': 'none'})),
                html.Li(dcc.Link("Gráficos de Gastos Mensais", href="/graficos", style={'color': COLORS['sidebar_text'], 'textDecoration': 'none'})),
            ],
            style={'listStyleType': 'none', 'padding': '20px', 'lineHeight': '2'}
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

content = html.Div(id="page-content", style={"marginLeft": "270px", "padding": "20px", "backgroundColor": COLORS['bg'], "minHeight": "100vh"})

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
        return html.Div([
            html.H1('Itens Comprados', style={'color': COLORS['text']}),
            html.Div([
                # Simples representação de tabela baseada no DF formatado
                html.Table(
                    # Header
                    [html.Tr([html.Th(col, style={'padding': '10px', 'borderBottom': '3px solid #ddd', 'color': COLORS['sidebar']}) for col in df_tabela.columns])] +
                    # Body
                    [html.Tr([html.Td(df_tabela.iloc[i][col], style={'padding': '8px', 'borderBottom': '1px solid #f1f1f1'}) for col in df_tabela.columns]) for i in range(len(df_tabela))],
                    style={'width': '100%', 'textAlign': 'left', 'backgroundColor': COLORS['card'], 'padding': '15px', 'borderRadius': '10px', 'fontSize': '13px'}
                )
            ], style={'overflowX': 'auto', 'marginTop': '20px'}) if not df_tabela.empty else html.P("Nenhum dado encontrado.")
        ])
    elif pathname == "/graficos":
        hoje = datetime.now()
        mes_atual = hoje.month
        ano_atual = hoje.year
        titulo_dinamico = f"Gráficos de Gastos do mês de {MESES_BR[mes_atual]}"

        # Filtrar DF para o mês atual para a caixa de "Gasto no Mês"
        df_notas_mes_atual = pd.DataFrame()
        total_gasto = 0
        if not df_notas.empty:
            df_notas['date_obj'] = pd.to_datetime(df_notas['data_compra_grafico'])
            df_notas_mes_atual = df_notas[(df_notas['date_obj'].dt.month == mes_atual) & (df_notas['date_obj'].dt.year == ano_atual)]
            if "total" in df_notas_mes_atual.columns:
                total_gasto = df_notas_mes_atual["total"].sum()

        tabs_historico = []
        if not df_notas.empty:
            for i in range(3): # Historico do Mês atual e 2 passados
                m = mes_atual - i
                y = ano_atual
                if m <= 0:
                    m += 12
                    y -= 1
                
                df_mes = df_notas[(df_notas['date_obj'].dt.month == m) & (df_notas['date_obj'].dt.year == y)]
                nome_tab = MESES_BR[m]
                
                fig = px.line(
                    df_mes, x="data_compra_grafico", y="total", 
                    title=f"Evolução de Gastos - {nome_tab}", markers=True
                ) if not df_mes.empty else px.line(title=f"Você não teve gastos em {nome_tab}")
                
                fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(t=40, b=40, l=40, r=40))
                
                abas = dcc.Tab(label=f"{nome_tab} de {y}" if i > 0 else f"{nome_tab} (Atual)", children=[
                    html.Div(dcc.Graph(figure=fig), style={'padding': '20px', 'backgroundColor': '#ffffff', 'borderRadius': '0 0 10px 10px'})
                ])
                tabs_historico.append(abas)
        else:
             tabs_historico.append(dcc.Tab(label="Atual", children=[dcc.Graph(figure=px.line(title="Sem dados suficientes"))]))

        return html.Div([
            html.H1(titulo_dinamico, style={'color': COLORS['text']}),
            html.Div([
                html.Div([
                    html.H3("Gasto no Mês", style={'margin': 0, 'color': '#7f8c8d'}),
                    html.H2(f"R$ {total_gasto:.2f}", style={'margin': 0, 'color': '#e74c3c'})
                ], style={'backgroundColor': COLORS['card'], 'padding': '20px', 'borderRadius': '10px', 'width': '30%', 'display': 'inline-block', 'marginRight': '20px'}),
                html.Div([
                    html.H3("Dinheiro Restante", style={'margin': 0, 'color': '#7f8c8d'}),
                    html.H2(f"R$ {(salario - total_gasto):.2f}", style={'margin': 0, 'color': '#2ecc71'})
                ], style={'backgroundColor': COLORS['card'], 'padding': '20px', 'borderRadius': '10px', 'width': '30%', 'display': 'inline-block'}),
            ], style={'marginBottom': '30px'}),
            html.Div([
                dcc.Tabs(children=tabs_historico, colors={
                    "border": "#d2d7d3",
                    "primary": COLORS['primary'],
                    "background": "#f9f9f9"
                })
            ], style={'backgroundColor': 'transparent', 'borderRadius': '10px'})
        ])
    return html.Div([
        html.H1("404: Não Encontrado", className="text-danger"),
        html.Hr(),
        html.P(f"O pathname {pathname} não foi reconhecido...")
    ])

if __name__ == "__main__":
    app.run_server(debug=True, port=8050)
