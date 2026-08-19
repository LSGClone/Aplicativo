import streamlit as st
import pandas as pd
import requests
import urllib.parse
import unicodedata

st.set_page_config(
    page_title="Roteirizador de Mobilização de Pranchas",
    page_icon="🚛",
    layout="wide"
)

st.title("🚛 Roteirizador & Calculador de Frete/Mobilização")
st.caption("Roteirização automática para pranchas e maquinários pesados.")

def normalizar_texto(texto):
    if not texto: return ""
    texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('ASCII')
    substituicoes = {
        "LEM": "Luis Eduardo Magalhaes, BA",
        "SAO DESIDERIO": "Sao Desiderio, BA",
        "BARREIRAS": "Barreiras, BA",
        "CORRENTINA": "Correntina, BA",
        "FORMOSA": "Formosa do Rio Preto, BA",
        "RIACHAO": "Riachao das Neves, BA",
        "RODA VELHA": "Roda Velha, Sao Desiderio, BA"
    }
    texto_upper = texto.upper().strip()
    for k, v in substituicoes.items():
        if texto_upper == k:
            return v
    return texto.strip()

@st.cache_data(ttl=3600, show_spinner=False)
def geocode_cidade(cidade_str):
    """Busca robusta com múltiplos fallbacks para cidades e regiões do Brasil."""
    if not cidade_str or len(cidade_str.strip()) < 2:
        return None, None, None
        
    query_limpa = normalizar_texto(cidade_str)
    headers = {"User-Agent": f"LogisticaAppPranchas_LSG_{urllib.parse.quote(query_limpa)}@internal.app"}
    
    tentativas = [
        f"{query_limpa}, Brasil",
        query_limpa,
        f"{query_limpa.split(',')[0]}, Brasil" if ',' in query_limpa else f"{query_limpa}, Bahia, Brasil"
    ]
    
    for q in tentativas:
        try:
            url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(q)}&format=json&limit=1&countrycodes=br"
            r = requests.get(url, headers=headers, timeout=6)
            data = r.json()
            if data and len(data) > 0:
                return float(data[0]["lat"]), float(data[0]["lon"]), data[0]["display_name"]
        except Exception:
            continue
            
    return None, None, None

@st.cache_data(ttl=3600, show_spinner=False)
def get_osrm_route(lat1, lon1, lat2, lon2):
    """Calcula trajeto rodoviário real via OSRM."""
    try:
        url = f"https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=false"
        r = requests.get(url, timeout=8)
        data = r.json()
        if data.get("routes") and len(data["routes"]) > 0:
            route = data["routes"][0]
            dist_km = route["distance"] / 1000.0
            dur_horas = route["duration"] / 3600.0
            return dist_km, dur_horas
    except Exception:
        pass
    return None, None

# Sidebar de Custos
with st.sidebar:
    st.header("⚙️ Parâmetros Operacionais")
    preco_diesel = st.number_input("Preço Diesel (R$/L)", min_value=3.0, max_value=15.0, value=6.20, step=0.05, format="%.2f")
    consumo_vazio = st.number_input("Consumo VAZIO (km/L)", min_value=0.5, max_value=10.0, value=2.6, step=0.1)
    consumo_carregado = st.number_input("Consumo CARREGADO (km/L)", min_value=0.5, max_value=10.0, value=1.7, step=0.1)
    manutencao_km = st.number_input("Manutenção/Pneus (R$/km)", min_value=0.0, max_value=10.0, value=1.35, step=0.05, format="%.2f")
    diaria_motorista = st.number_input("Diária Motorista (R$/dia)", min_value=0.0, max_value=2000.0, value=280.0, step=10.0, format="%.2f")

# Planejamento dos Trechos
st.subheader("📍 Roteiro da Mobilização")
col1, col2, col3 = st.columns(3)
with col1:
    ponto_a = st.text_input("1. Saída da Prancha (Base / Garagem)", value="Barreiras - BA")
with col2:
    ponto_b = st.text_input("2. Coleta da Máquina (Origem)", value="Luis Eduardo Magalhaes - BA")
with col3:
    ponto_c = st.text_input("3. Desembarque da Máquina (Obra)", value="Sao Desiderio - BA")

col_final, col_extra_opt = st.columns([2, 1])
with col_final:
    retorno_tipo = st.selectbox("4. Destino Final da Prancha após Desembarque", 
                                ["Retornar à Base (Ponto 1)", "Permanecer na Obra", "Ir para outra Cidade"])
    if retorno_tipo == "Ir para outra Cidade":
        ponto_d = st.text_input("Cidade de Destino Final", value="Correntina - BA")
    elif retorno_tipo == "Retornar à Base (Ponto 1)":
        ponto_d = ponto_a
    else:
        ponto_d = ponto_c

with col_extra_opt:
    ajuste_manual = st.checkbox("Habilitar ajuste manual de KM (se for fazenda/zona rural)", value=False)

col_carga1, col_carga2, col_carga3 = st.columns(3)
with col_carga1:
    maquina_nome = st.text_input("Equipamento a Transportar", value="Escavadeira Hidráulica 22t")
with col_carga2:
    pedagios = st.number_input("Pedágios Totais (R$)", min_value=0.0, max_value=10000.0, value=0.0, step=10.0)
with col_carga3:
    custos_extras = st.number_input("AET / Escolta / Outros (R$)", min_value=0.0, max_value=20000.0, value=350.0, step=50.0)

if st.button("🚀 Calcular Rota Automática e Custos", type="primary", use_container_width=True):
    with st.spinner("Localizando cidades e calculando distâncias rodoviárias..."):
        lat_a, lon_a, nome_a = geocode_cidade(ponto_a)
        lat_b, lon_b, nome_b = geocode_cidade(ponto_b)
        lat_c, lon_c, nome_c = geocode_cidade(ponto_c)
        lat_d, lon_d, nome_d = (lat_c, lon_c, nome_c) if ponto_c == ponto_d else geocode_cidade(ponto_d)

        # Validação detalhada ponto a ponto
        erros = []
        if not lat_a: erros.append(f"Saída: '{ponto_a}'")
        if not lat_b: erros.append(f"Coleta: '{ponto_b}'")
        if not lat_c: erros.append(f"Desembarque: '{ponto_c}'")
        if not lat_d: erros.append(f"Destino Final: '{ponto_d}'")

        if erros:
            st.error(f"❌ Não foi possível encontrar as seguintes localidades no mapa: {', '.join(erros)}.")
            st.info("💡 **Dica:** Digite no formato: **Nome da Cidade - UF** (ex: *Luis Eduardo Magalhaes - BA*, *Barreiras - BA*).")
        else:
            # Trechos
            dist_1, tempo_1 = get_osrm_route(lat_a, lon_a, lat_b, lon_b)
            dist_2, tempo_2 = get_osrm_route(lat_b, lon_b, lat_c, lon_c)
            dist_3, tempo_3 = (0.0, 0.0) if ponto_c == ponto_d else get_osrm_route(lat_c, lon_c, lat_d, lon_d)

            # Fallback de rota se a malha viária falhar
            dist_1 = dist_1 or 50.0
            dist_2 = dist_2 or 50.0
            dist_3 = dist_3 or 0.0
            tempo_total = (tempo_1 or 1.0) + (tempo_2 or 1.0) + (tempo_3 or 0.0)

            km_vazio = dist_1 + dist_3
            km_carregado = dist_2
            km_total = km_vazio + km_carregado

            dias_est = max(1.0, round((tempo_total + 3.0) / 8.0, 1))

            # Custos
            l_vazio = km_vazio / consumo_vazio
            l_carregado = km_carregado / consumo_carregado
            l_total = l_vazio + l_carregado
            c_diesel = l_total * preco_diesel
            c_manutencao = km_total * manutencao_km
            c_diarias = dias_est * diaria_motorista
            c_total = c_diesel + c_manutencao + c_diarias + pedagios + custos_extras
            c_km_medio = c_total / km_total if km_total > 0 else 0

            st.success("✅ Rota calculada com sucesso!")

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Custo Total", f"R$ {c_total:,.2f}")
            m2.metric("Distância Total", f"{km_total:,.1f} km")
            m3.metric("Tempo Dirigindo", f"{tempo_total:,.1f} h", f"~ {dias_est} dia(s)")
            m4.metric("Diesel Total", f"{l_total:,.1f} L", f"R$ {c_diesel:,.2f}")
            m5.metric("Custo Médio / km", f"R$ {c_km_medio:,.2f}")

            st.markdown("---")
            st.subheader("📋 Segmentação dos Trechos da Mobilização")
            df_trechos = pd.DataFrame([
                {"Trecho": "1. Posicionamento (Vazio)", "Origem": ponto_a, "Destino": ponto_b, "Condição": "Vazio", "Distância (km)": round(dist_1, 1), "Diesel (L)": round(dist_1/consumo_vazio, 1), "Custo Diesel": f"R$ {(dist_1/consumo_vazio)*preco_diesel:,.2f}"},
                {"Trecho": f"2. Transporte: {maquina_nome}", "Origem": ponto_b, "Destino": ponto_c, "Condição": "CARREGADO", "Distância (km)": round(dist_2, 1), "Diesel (L)": round(dist_2/consumo_carregado, 1), "Custo Diesel": f"R$ {(dist_2/consumo_carregado)*preco_diesel:,.2f}"},
                {"Trecho": "3. Retorno / Reposicionamento", "Origem": ponto_c, "Destino": ponto_d, "Condição": "Vazio", "Distância (km)": round(dist_3, 1), "Diesel (L)": round(dist_3/consumo_vazio, 1), "Custo Diesel": f"R$ {(dist_3/consumo_vazio)*preco_diesel:,.2f}"}
            ])
            st.dataframe(df_trechos, use_container_width=True)

            col_map, col_chart = st.columns([1.2, 1])
            with col_map:
                st.subheader("🗺️ Pontos Localizados no Mapa")
                df_mapa = pd.DataFrame({
                    "lat": [lat_a, lat_b, lat_c, lat_d],
                    "lon": [lon_a, lon_b, lon_c, lon_d]
                })
                st.map(df_mapa)

            with col_chart:
                st.subheader("📊 Divisão de Gastos")
                df_gastos = pd.DataFrame({
                    "Categoria": ["Diesel", "Manutenção/Pneus", "Diárias Motorista", "Pedágios & Extras"],
                    "Valor (R$)": [c_diesel, c_manutencao, c_diarias, (pedagios + custos_extras)]
                })
                st.bar_chart(df_gastos.set_index("Categoria"))
