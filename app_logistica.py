import streamlit as st
import pandas as pd
import math
import requests

st.set_page_config(
    page_title="Roteirizador de Mobilização de Pranchas",
    page_icon="🚛",
    layout="wide"
)

st.title("🚛 Roteirizador & Calculador de Frete/Mobilização")
st.caption("Cálculo automático de rotas, consumo por trecho (vazio vs. carregado), manutenção e custos operacionais.")

# 1. Carrega todas as cidades do Brasil via API oficial do IBGE (Instantâneo e sem bloqueios)
@st.cache_data(ttl=86400, show_spinner=False)
def carregar_cidades_brasil():
    try:
        url = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            dados = r.json()
            cidades = sorted([f"{m['nome']} - {m['microrregiao']['mesorregiao']['UF']['sigla']}" for m in dados])
            return cidades
    except Exception:
        pass
    # Fallback caso a API do IBGE oscile
    return sorted([
        "Barreiras - BA", "Luis Eduardo Magalhaes - BA", "Sao Desiderio - BA", 
        "Formosa do Rio Preto - BA", "Correntina - BA", "Riachao das Neves - BA",
        "Santa Maria da Vitoria - BA", "Posse - GO", "Brasilia - DF", "Goiania - GO"
    ])

# 2. Coordenadas aproximadas com fallback geodésico rodoviário (fator de correção de sinuosidade 1.28)
def calcular_distancia_rodoviaria_estimada(lat1, lon1, lat2, lon2):
    """Calcula a distância rodoviária com correção de sinuosidade viária real (fator 1.28)."""
    R = 6371.0 # Raio da Terra em km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    dist_linha_reta = R * c
    return dist_linha_reta * 1.28 # Converte para km rodoviário real

@st.cache_data(ttl=3600, show_spinner=False)
def buscar_dados_rota(cidade_origem, cidade_destino):
    """Busca a rota no serviço rodoviário com fallback automático."""
    cidade_ori_limpa = cidade_origem.split(" - ")[0]
    cidade_dest_limpa = cidade_destino.split(" - ")[0]
    
    # Tentativa via OSRM com coordenadas diretas via nominatim com header padrão
    try:
        url_geo = f"https://nominatim.openstreetmap.org/search?q={cidade_ori_limpa},Brasil&format=json&limit=1"
        r1 = requests.get(url_geo, headers={"User-Agent": "Mozilla/5.0"}, timeout=4).json()
        
        url_geo2 = f"https://nominatim.openstreetmap.org/search?q={cidade_dest_limpa},Brasil&format=json&limit=1"
        r2 = requests.get(url_geo2, headers={"User-Agent": "Mozilla/5.0"}, timeout=4).json()
        
        if r1 and r2:
            lat1, lon1 = float(r1[0]["lat"]), float(r1[0]["lon"])
            lat2, lon2 = float(r2[0]["lat"]), float(r2[0]["lon"])
            
            url_osrm = f"https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
            r_osrm = requests.get(url_osrm, timeout=5).json()
            if r_osrm.get("routes"):
                dist = r_osrm["routes"][0]["distance"] / 1000.0
                tempo = r_osrm["routes"][0]["duration"] / 3600.0
                return dist, tempo, lat1, lon1, lat2, lon2
    except Exception:
        pass
        
    # Coordenadas de referência para a região Oeste Baiano / Centro-Oeste
    coords_ref = {
        "Barreiras": (-12.1528, -44.9936),
        "Luis Eduardo Magalhaes": (-12.0969, -45.7958),
        "Sao Desiderio": (-12.3556, -44.9750),
        "Formosa do Rio Preto": (-11.0483, -45.1931),
        "Correntina": (-13.3433, -44.6367),
        "Riachao das Neves": (-11.7461, -44.9089),
        "Santa Maria da Vitoria": (-13.3947, -44.1953),
        "Brasilia": (-15.7975, -47.8919),
        "Goiania": (-16.6869, -49.2648)
    }
    
    c1 = coords_ref.get(cidade_ori_limpa, (-12.15, -45.00))
    c2 = coords_ref.get(cidade_dest_limpa, (-12.10, -45.80))
    dist = calcular_distancia_rodoviaria_estimada(c1[0], c1[1], c2[0], c2[1])
    tempo = dist / 60.0 # Média de 60 km/h para prancha pesada
    return max(15.0, dist), tempo, c1[0], c1[1], c2[0], c2[1]

# Carrega lista completa de municípios
lista_cidades = carregar_cidades_brasil()

# Sidebar de Custos
with st.sidebar:
    st.header("⚙️ Parâmetros Operacionais")
    preco_diesel = st.number_input("Preço Diesel (R$/L)", min_value=3.0, max_value=15.0, value=6.20, step=0.05, format="%.2f")
    consumo_vazio = st.number_input("Consumo VAZIO (km/L)", min_value=0.5, max_value=10.0, value=2.6, step=0.1)
    consumo_carregado = st.number_input("Consumo CARREGADO (km/L)", min_value=0.5, max_value=10.0, value=1.7, step=0.1)
    manutencao_km = st.number_input("Manutenção/Pneus (R$/km)", min_value=0.0, max_value=10.0, value=1.35, step=0.05, format="%.2f")
    diaria_motorista = st.number_input("Diária Motorista (R$/dia)", min_value=0.0, max_value=2000.0, value=280.0, step=10.0, format="%.2f")

# Interface de Seleção com Autocompletar
st.subheader("📍 Roteiro da Mobilização")

idx_barreiras = lista_cidades.index("Barreiras - BA") if "Barreiras - BA" in lista_cidades else 0
idx_formosa = lista_cidades.index("Formosa do Rio Preto - BA") if "Formosa do Rio Preto - BA" in lista_cidades else 0
idx_lem = lista_cidades.index("Luís Eduardo Magalhães - BA") if "Luís Eduardo Magalhães - BA" in lista_cidades else (lista_cidades.index("Luis Eduardo Magalhaes - BA") if "Luis Eduardo Magalhaes - BA" in lista_cidades else 0)

col1, col2, col3 = st.columns(3)
with col1:
    ponto_a = st.selectbox("1. Saída da Prancha (Base)", lista_cidades, index=idx_barreiras)
with col2:
    ponto_b = st.selectbox("2. Coleta da Máquina (Origem)", lista_cidades, index=idx_formosa)
with col3:
    ponto_c = st.selectbox("3. Desembarque da Máquina (Obra)", lista_cidades, index=idx_barreiras)

col_ret, col_maquina = st.columns(2)
with col_ret:
    retorno_tipo = st.selectbox("4. Destino Final da Prancha", ["Retornar à Base (Ponto 1)", "Permanecer na Obra", "Ir para outra Cidade"])
    if retorno_tipo == "Ir para outra Cidade":
        ponto_d = st.selectbox("Selecione o Destino Final", lista_cidades, index=idx_lem)
    elif retorno_tipo == "Retornar à Base (Ponto 1)":
        ponto_d = ponto_a
    else:
        ponto_d = ponto_c

with col_maquina:
    maquina_nome = st.text_input("Equipamento a Transportar", value="Escavadeira Hidráulica 22t")

col_extra1, col_extra2 = st.columns(2)
with col_extra1:
    pedagios = st.number_input("Pedágios Totais (R$)", min_value=0.0, max_value=10000.0, value=0.0, step=10.0)
with col_extra2:
    custos_extras = st.number_input("AET / Escolta / Hospedagem (R$)", min_value=0.0, max_value=20000.0, value=350.0, step=50.0)

if st.button("🚀 Calcular Rota Automática e Custos", type="primary", use_container_width=True):
    with st.spinner("Calculando rotas e distâncias rodoviárias..."):
        # Trecho 1: Base -> Coleta
        dist_1, tempo_1, lat1, lon1, lat2, lon2 = buscar_dados_rota(ponto_a, ponto_b)
        # Trecho 2: Coleta -> Desembarque
        dist_2, tempo_2, _, _, lat3, lon3 = buscar_dados_rota(ponto_b, ponto_c)
        # Trecho 3: Desembarque -> Destino Final
        if ponto_c == ponto_d:
            dist_3, tempo_3 = 0.0, 0.0
            lat4, lon4 = lat3, lon3
        else:
            dist_3, tempo_3, _, _, lat4, lon4 = buscar_dados_rota(ponto_c, ponto_d)

        # Distâncias Totais
        km_vazio = dist_1 + dist_3
        km_carregado = dist_2
        km_total = km_vazio + km_carregado
        tempo_total = tempo_1 + tempo_2 + tempo_3
        dias_est = max(1.0, round((tempo_total + 3.0) / 8.0, 1))

        # Cálculos de Consumo e Custos
        litros_vazio = km_vazio / consumo_vazio
        litros_carregado = km_carregado / consumo_carregado
        litros_total = litros_vazio + litros_carregado

        c_diesel = litros_total * preco_diesel
        c_manutencao = km_total * manutencao_km
        c_diarias = dias_est * diaria_motorista
        c_total = c_diesel + c_manutencao + c_diarias + pedagios + custos_extras
        c_km_medio = c_total / km_total if km_total > 0 else 0

        st.success("✅ Mobilização calculada com sucesso!")

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Custo Total", f"R$ {c_total:,.2f}")
        m2.metric("Distância Total", f"{km_total:,.1f} km")
        m3.metric("Tempo Estimado", f"{tempo_total:,.1f} h", f"~ {dias_est} dia(s)")
        m4.metric("Diesel Total", f"{litros_total:,.1f} L", f"R$ {c_diesel:,.2f}")
        m5.metric("Custo Médio / km", f"R$ {c_km_medio:,.2f}")

        st.markdown("---")
        st.subheader("📋 Segmentação dos Trechos")
        df_trechos = pd.DataFrame([
            {"Trecho": "1. Posicionamento (Vazio)", "Origem": ponto_a, "Destino": ponto_b, "Condição": "Vazio", "Distância (km)": round(dist_1, 1), "Diesel (L)": round(dist_1/consumo_vazio, 1), "Custo Diesel": f"R$ {(dist_1/consumo_vazio)*preco_diesel:,.2f}"},
            {"Trecho": f"2. Transporte: {maquina_nome}", "Origem": ponto_b, "Destino": ponto_c, "Condição": "CARREGADO", "Distância (km)": round(dist_2, 1), "Diesel (L)": round(dist_2/consumo_carregado, 1), "Custo Diesel": f"R$ {(dist_2/consumo_carregado)*preco_diesel:,.2f}"},
            {"Trecho": "3. Retorno / Reposicionamento", "Origem": ponto_c, "Destino": ponto_d, "Condição": "Vazio", "Distância (km)": round(dist_3, 1), "Diesel (L)": round(dist_3/consumo_vazio, 1), "Custo Diesel": f"R$ {(dist_3/consumo_vazio)*preco_diesel:,.2f}"}
        ])
        st.dataframe(df_trechos, use_container_width=True)

        col_map, col_chart = st.columns([1.2, 1])
        with col_map:
            st.subheader("🗺️ Pontos da Mobilização")
            df_mapa = pd.DataFrame({
                "lat": [lat1, lat2, lat3, lat4],
                "lon": [lon1, lon2, lon3, lon4]
            })
            st.map(df_mapa)

        with col_chart:
            st.subheader("📊 Divisão de Gastos")
            df_gastos = pd.DataFrame({
                "Categoria": ["Diesel", "Manutenção/Pneus", "Diárias Motorista", "Pedágios & Extras"],
                "Valor (R$)": [c_diesel, c_manutencao, c_diarias, (pedagios + custos_extras)]
            })
            st.bar_chart(df_gastos.set_index("Categoria"))
