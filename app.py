import streamlit as st
import pandas as pd
import plotly.express as px
import psycopg
import requests

# -----------------------------------------------------------------------------
# Configuração e Conexão
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Dashboard de Vacinação", layout="wide")

# Uso do st.secrets para segurança no deploy público, com fallback para testes locais
NAME_DB = st.secrets.get("NAME_DB", "notebook-db")
LINK = st.secrets.get("LINK", "db-project-vaccine-brazil.postgres.database.azure.com")
USER = st.secrets.get("USER", "admin_db")
PASSWORD = st.secrets.get("PASSWORD", "-LVSHj3X6\"[L%B{f[r8(")
DB_CONN = f"host='{LINK}' dbname='{NAME_DB}' user='{USER}' password='{PASSWORD}'"

@st.cache_data(ttl=3600)
def fetch_data(query: str, params: tuple = None) -> pd.DataFrame:
    """Executa uma query SQL e retorna um DataFrame do pandas."""
    with psycopg.connect(DB_CONN) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            columns = [desc[0] for desc in cur.description]
            data = cur.fetchall()
            return pd.DataFrame(data, columns=columns)

@st.cache_data
def load_geojson() -> dict:
    """Busca o GeoJSON dos estados do Brasil para o mapa coroplético."""
    url = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson"
    return requests.get(url).json()

# -----------------------------------------------------------------------------
# Controles da Barra Lateral (Sidebar)
# -----------------------------------------------------------------------------
st.sidebar.title("Controles do Dashboard")

# 0. Seleção do Tamanho da Amostra
opcao_amostra = st.sidebar.radio(
    "0. Selecione a Amostra de Dados:",
    ["1% (Padrão)", "10%"]
)

# Definir qual tabela será usada em todas as queries com base na seleção
tabela_amostra = "mv_dim_aplicacao_1" if opcao_amostra == "1% (Padrão)" else "mv_dim_aplicacao_10"

st.sidebar.markdown("---")

state_query = "SELECT DISTINCT sg_uf_paciente FROM dim_paciente WHERE sg_uf_paciente IS NOT NULL ORDER BY sg_uf_paciente;"
states_df = fetch_data(state_query)
states_list = states_df["sg_uf_paciente"].tolist()

estado_demo_selecionado = st.sidebar.selectbox("1. Filtrar Demografia por Estado:", ["Todos"] + states_list)
estado_origem_selecionado = st.sidebar.selectbox("2. Estado de Origem do Turismo de Vacina:", states_list, index=states_list.index("MG") if "MG" in states_list else 0)
faixa_etaria_selecionada = st.sidebar.selectbox("3. Principais Vacinas por Faixa Etária:", ["0-17", "18-59", "60+"])

# -----------------------------------------------------------------------------
# Corpo Principal da Aplicação
# -----------------------------------------------------------------------------
st.title("Programa Nacional de Imunizações (PNI) - Janeiro de 2026")
st.markdown("---")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Distribuição Demográfica")

    if estado_demo_selecionado == "Todos":
        demo_query = f"""
            SELECT
                p.tp_sexo_paciente,
                CASE
                    WHEN p.nu_idade_paciente BETWEEN 0 AND 9 THEN '0-9'
                    WHEN p.nu_idade_paciente BETWEEN 10 AND 19 THEN '10-19'
                    WHEN p.nu_idade_paciente BETWEEN 20 AND 29 THEN '20-29'
                    WHEN p.nu_idade_paciente BETWEEN 30 AND 39 THEN '30-39'
                    WHEN p.nu_idade_paciente BETWEEN 40 AND 49 THEN '40-49'
                    WHEN p.nu_idade_paciente BETWEEN 50 AND 59 THEN '50-59'
                    ELSE '60+'
                END AS faixa_etaria,
                COUNT(a.co_documento) AS total_doses
            FROM {tabela_amostra} a
            JOIN public.dim_paciente p ON a.co_paciente = p.co_paciente
            GROUP BY 1, 2
            ORDER BY faixa_etaria;
        """
        df_demo = fetch_data(demo_query)
    else:
        demo_query = f"""
            SELECT
                p.tp_sexo_paciente,
                CASE
                    WHEN p.nu_idade_paciente BETWEEN 0 AND 9 THEN '0-9'
                    WHEN p.nu_idade_paciente BETWEEN 10 AND 19 THEN '10-19'
                    WHEN p.nu_idade_paciente BETWEEN 20 AND 29 THEN '20-29'
                    WHEN p.nu_idade_paciente BETWEEN 30 AND 39 THEN '30-39'
                    WHEN p.nu_idade_paciente BETWEEN 40 AND 49 THEN '40-49'
                    WHEN p.nu_idade_paciente BETWEEN 50 AND 59 THEN '50-59'
                    ELSE '60+'
                END AS faixa_etaria,
                COUNT(a.co_documento) AS total_doses
            FROM {tabela_amostra} a
            JOIN public.dim_paciente p ON a.co_paciente = p.co_paciente
            WHERE p.sg_uf_paciente = %s
            GROUP BY 1, 2
            ORDER BY faixa_etaria;
        """
        df_demo = fetch_data(demo_query, (estado_demo_selecionado,))

    fig_demo = px.bar(df_demo, x="total_doses", y="faixa_etaria", color="tp_sexo_paciente",
                      barmode="group", orientation='h',
                      labels={"total_doses": "Total de Doses", "faixa_etaria": "Faixa Etária", "tp_sexo_paciente": "Sexo"})
    st.plotly_chart(fig_demo, use_container_width=True)

with col2:
    st.subheader(f"Turismo de Vacina a partir de {estado_origem_selecionado}")

    tourism_query = f"""
        SELECT
            e.sg_uf_estabelecimento AS estado_destino,
            COUNT(a.co_documento) AS total_doses
        FROM {tabela_amostra} a
        JOIN public.dim_paciente p ON a.co_paciente = p.co_paciente
        JOIN public.dim_estabelecimento e ON a.co_cnes_estabelecimento = e.co_cnes_estabelecimento
        WHERE p.sg_uf_paciente = %s AND p.sg_uf_paciente <> e.sg_uf_estabelecimento
        GROUP BY e.sg_uf_estabelecimento
        ORDER BY total_doses DESC
        LIMIT 10;
    """
    df_tourism = fetch_data(tourism_query, (estado_origem_selecionado,))

    fig_tourism = px.bar(df_tourism, x="estado_destino", y="total_doses",
                         labels={"estado_destino": "Estado de Destino", "total_doses": "Doses Administradas"})
    st.plotly_chart(fig_tourism, use_container_width=True)

st.markdown("---")

col3, col4 = st.columns(2)

with col3:
    st.subheader(f"Principais Vacinas para a Faixa Etária: {faixa_etaria_selecionada}")

    # Traduzir a string demográfica para condição SQL
    if faixa_etaria_selecionada == "0-17":
        condicao_idade = "p.nu_idade_paciente < 18"
    elif faixa_etaria_selecionada == "18-59":
        condicao_idade = "p.nu_idade_paciente BETWEEN 18 AND 59"
    else:
        condicao_idade = "p.nu_idade_paciente >= 60"

    vaccine_query = f"""
        SELECT
            v.ds_vacina,
            COUNT(a.co_documento) AS total_doses
        FROM {tabela_amostra} a
        JOIN public.dim_paciente p ON a.co_paciente = p.co_paciente
        JOIN public.dim_vacina v ON a.co_vacina = v.co_vacina
        WHERE {condicao_idade}
        GROUP BY 1
        ORDER BY total_doses DESC
        LIMIT 5;
    """
    df_vaccines = fetch_data(vaccine_query)

    fig_vaccines = px.pie(df_vaccines, names="ds_vacina", values="total_doses", hole=0.4)
    fig_vaccines.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig_vaccines, use_container_width=True)

with col4:
    st.subheader("Evolução Temporal")

    # Elemento Interativo 4: Limites de datas
    min_date_query = f"SELECT MIN(dt_vacina), MAX(dt_vacina) FROM {tabela_amostra} WHERE dt_vacina >= '2025-01-01';"
    dates = fetch_data(min_date_query)
    start_dt, end_dt = dates.iloc[0, 0], dates.iloc[0, 1]

    if start_dt and end_dt:
        datas_selecionadas = st.slider("4. Filtrar Intervalo de Datas", min_value=start_dt, max_value=end_dt, value=(start_dt, end_dt))

        temporal_query = f"""
            SELECT
                DATE_TRUNC('day', a.dt_vacina) AS data_vacinacao,
                COUNT(a.co_documento) AS total_doses
            FROM {tabela_amostra} a
            WHERE a.dt_vacina BETWEEN %s AND %s
            GROUP BY data_vacinacao
            ORDER BY data_vacinacao;
        """
        df_temporal = fetch_data(temporal_query, (datas_selecionadas[0], datas_selecionadas[1]))

        fig_temporal = px.line(df_temporal, x="data_vacinacao", y="total_doses",
                               labels={"data_vacinacao": "Data", "total_doses": "Doses Administradas"})
        st.plotly_chart(fig_temporal, use_container_width=True)

st.markdown("---")

st.subheader("Distribuição Geoespacial (Integração Censo 2022)")
metrica_mapa = st.radio("5. Selecionar Métrica do Mapa:", ["População Geral", "População Indígena"], horizontal=True)

geojson = load_geojson()

if metrica_mapa == "População Geral":
    map_query = f"""
        WITH pessoas_vacinadas_uf AS (
            SELECT
                e.sg_uf_estabelecimento AS uf,
                COUNT(DISTINCT a.co_paciente) AS total_pessoas_vacinadas
            FROM {tabela_amostra} a
            JOIN public.dim_estabelecimento e ON a.co_cnes_estabelecimento = e.co_cnes_estabelecimento
            GROUP BY e.sg_uf_estabelecimento
        ),
        populacao_uf AS (
            SELECT sigla_uf, SUM(populacao) AS populacao_total
            FROM public.ibge_censo_2022_municipio
            GROUP BY sigla_uf
        )
        SELECT
            v.uf,
            v.total_pessoas_vacinadas,
            p.populacao_total,
            ROUND(100.0 * v.total_pessoas_vacinadas / p.populacao_total, 2) AS percentual_vacinados
        FROM pessoas_vacinadas_uf v
        JOIN populacao_uf p ON v.uf = p.sigla_uf;
    """
else:
    map_query = f"""
        WITH pessoas_indigenas_vacinadas_uf AS (
            SELECT
                e.sg_uf_estabelecimento AS uf,
                COUNT(DISTINCT a.co_paciente) AS total_pessoas_vacinadas
            FROM {tabela_amostra} a
            JOIN public.dim_paciente pac ON a.co_paciente = pac.co_paciente
            JOIN public.dim_estabelecimento e ON a.co_cnes_estabelecimento = e.co_cnes_estabelecimento
            WHERE pac.no_raca_cor_paciente = 'INDIGENA'
            GROUP BY e.sg_uf_estabelecimento
        ),
        populacao_uf AS (
            SELECT sigla_uf, SUM(populacao_indigena) AS populacao_total
            FROM public.ibge_censo_2022_municipio
            GROUP BY sigla_uf
        )
        SELECT
            v.uf,
            v.total_pessoas_vacinadas,
            p.populacao_total,
            ROUND(100.0 * v.total_pessoas_vacinadas / NULLIF(p.populacao_total, 0), 2) AS percentual_vacinados
        FROM pessoas_indigenas_vacinadas_uf v
        JOIN populacao_uf p ON v.uf = p.sigla_uf;
    """

df_map = fetch_data(map_query)

fig_map = px.choropleth(
    data_frame=df_map,
    geojson=geojson,
    locations='uf',
    featureidkey='properties.sigla',
    color='percentual_vacinados',
    color_continuous_scale="Viridis",
    hover_name='uf',
    hover_data={'total_pessoas_vacinadas': True, 'populacao_total': True, 'percentual_vacinados': ':.2f', 'uf': False},
    labels={'percentual_vacinados': '% Vacinados'}
)
fig_map.update_geos(fitbounds="locations", visible=False)
fig_map.update_layout(margin={"r":0, "t":0, "l":0, "b":0})

st.plotly_chart(fig_map, use_container_width=True)