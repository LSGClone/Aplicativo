import streamlit as st
import pandas as pd
import requests

st.set_page_config(
    page_title="Roteirizador de Mobilização de Pranchas",
    page_icon="🚛",
    layout="wide"
)

st.title("🚛 Roteirizador & Calculador Automático de Mobilização")
st.caption("Cálculo automático de rotas, consumo por trecho (vazio vs. carregado), manutenção e custos operacionais.")

# Funções de Geocodificação e Rotas (OpenStreetMap / OSRM)
@st.cache_data(ttl=3600, show_spinner=False)
def geocode_address(address_text):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": address_text,
        "format": "json",
        "limit": 1,
        "countrycodes": "br"
    }
    headers = {"User-Agent": "LogisticaApp/1.0"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=10)
        data = r.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"]), data[0]["display_name"]
    except Exception:
        pass
    return None, None, None

@st.cache_data(ttl=3600, show_spinner=False)
def get_osrm_route(lat1, lon1, lat2, lon2):
    url = f"https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get("routes"):
            route = data["routes"][0]
            dist_km = route["distance"] / 1000.0
            dur_horas = route["duration"] / 3600.0
            coords = route["geometry"]["coordinates"]
            return dist_km, dur_horas, coords
    except Exception:
        pass
    return None, None, []

# Sidebar de Custos
with st.sidebar:
    st.header("⚙️ Parâmetros Operacionais")
    preco_diesel = st.number_input("Preço Diesel (R$/L)", min_value=3.0, max_value=15.0, value=6.20, step=0.05, format="%.2f")
    consumo_vazio = st.number_input("Consumo VAZIO (km/L)", min_value=0.5, max_value=10.0, value=2.6, step=0.1)
    consumo_carregado = st.number_input("Consumo CARREGADO (km/L)", min_value=0.5, max_value=10.0, value=1.7, step=0.1)
    manutencao_km = st.number_input("Manutenção/Pneus (R$/km)", min_value=0.0, max_value=10.0, value=1.35, step=0.05, format="%.2f")
    diaria_motorista = st.number_input("Diária Motorista (R$/dia)", min_value=0.0, max_value=2000.0, value=280.0, step=10.0, format="%.2f")

# Interface de Entrada
st.subheader("📍 Planejamento de Rota da Mobilização")

col_p1, col_p2, col_p3, col_p4 = st.columns(4)
with col_p1:
    ponto_a = st.text_input("1. Saída da Prancha (Base)", value="Barreiras, BA")
with col_p2:
    ponto_b = st.text_input("2. Coleta da Máquina", value="Luis Eduardo Magalhaes, BA")
with col_p3:
    ponto_c = st.text_input("3. Desembarque da Máquina", value="Sao Desiderio, BA")
with col_p4:
    retorno_base = st.selectbox("4. Destino Final", ["Retornar à Base (Ponto 1)", "Permanecer no Desembarque", "Outra Cidade"])
    ponto_d = ponto_a if retorno_base == "Retornar à Base (Ponto 1)" else (ponto_c if retorno_base == "Permanecer no Desembarque" else st.text_input("Endereço Destino", value="Correntina, BA"))

col_extra1, col_extra2, col_extra3 = st.columns(3)
with col_extra1:
    maquina_desc = st.text_input("Equipamento a Transportar", value="Escavadeira Hidráulica 22t")
with col_extra2:
    pedagios = st.number_input("Pedágios Estimados (R$)", min_value=0.0, max_value=10000.0, value=0.0, step=10.0)
with col_extra3:
    custos_extras = st.number_input("AET / Escolta / Outros (R$)", min_value=0.0, max_value=20000.0, value=350.0, step=50.0)

if st.button("🚀 Calcular Rota Automática e Custos", type="primary", use_container_width=True):
    with st.spinner("Calculando distâncias rodoviárias e rotas..."):
        lat_a, lon_a, _ = geocode_address(ponto_a)
        lat_b, lon_b, _ = geocode_address(ponto_b)
        lat_c, lon_c, _ = geocode_address(ponto_c)
        lat_d, lon_d, _ = geocode_address(ponto_d)

        if not all([lat_a, lat_b, lat_c, lat_d]):
            st.error("❌ Um ou mais endereços não foram localizados. Verifique se incluiu a cidade/estado.")
        else:
            dist_1, tempo_1, coords_1 = get_osrm_route(lat_a, lon_a, lat_b, lon_b)
            dist_2, tempo_2, coords_2 = get_osrm_route(lat_b, lon_b, lat_c, lon_c)
            dist_3, tempo_3, coords_3 = (0.0, 0.0, []) if ponto_c == ponto_d else get_osrm_route(lat_c, lon_c, lat_d, lon_d)

            dist_3 = dist_3 or 0.0
            tempo_3 = tempo_3 or 0.0
            
            km_vazio = dist_1 + dist_3
            km_carregado = dist_2
            km_total = km_vazio + km_carregado
            horas_total = (tempo_1 or 0) + (tempo_2 or 0) + tempo_3
            dias_estimados = max(1.0, round((horas_total + 3.0) / 8.0, 1))

            litros_vazio = km_vazio / consumo_vazio
            litros_carregado = km_carregado / consumo_carregado
            litros_totais = litros_vazio + litros_carregado
            custo_diesel = litros_totais * preco_diesel
            custo_manutencao = km_total * manutencao_km
            custo_diarias = dias_estimados * diaria_motorista
            custo_total = custo_diesel + custo_manutencao + custo_diarias + pedagios + custos_extras
            custo_km_medio = custo_total / km_total if km_total > 0 else 0

            st.success("✅ Rota calculada com sucesso!")
            
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Custo Total", f"R$ {custo_total:,.2f}")
            m2.metric("Distância Total", f"{km_total:,.1f} km")
            m3.metric("Tempo Dirigindo", f"{horas_total:,.1f} h", f"~ {dias_estimados} dias")
            m4.metric("Diesel Total", f"{litros_totais:,.1f} L", f"R$ {custo_diesel:,.2f}")
            m5.metric("Custo / km", f"R$ {custo_km_medio:,.2f}")

            st.markdown("---")
            st.subheader("📋 Segmentação dos Trechos")
            df_trechos = pd.DataFrame([
                {"Trecho": "1. Posicionamento (Vazio)", "De": ponto_a, "Para": ponto_b, "Distância (km)": round(dist_1, 1), "Diesel (L)": round(dist_1/consumo_vazio, 1), "Custo Diesel": f"R$ {(dist_1/consumo_vazio)*preco_diesel:,.2f}"},
                {"Trecho": f"2. Transporte: {maquina_desc}", "De": ponto_b, "Para": ponto_c, "Distância (km)": round(dist_2, 1), "Diesel (L)": round(dist_2/consumo_carregado, 1), "Custo Diesel": f"R$ {(dist_2/consumo_carregado)*preco_diesel:,.2f}"},
                {"Trecho": "3. Retorno / Final (Vazio)", "De": ponto_c, "Para": ponto_d, "Distância (km)": round(dist_3, 1), "Diesel (L)": round(dist_3/consumo_vazio, 1), "Custo Diesel": f"R$ {(dist_3/consumo_vazio)*preco_diesel:,.2f}"}
            ])
            st.dataframe(df_trechos, use_container_width=True)

            col_map, col_chart = st.columns([1.2, 1])
            with col_map:
                st.subheader("🗺️ Pontos de Parada no Mapa")
                df_mapa = pd.DataFrame({
                    "lat": [lat_a, lat_b, lat_c, lat_d],
                    "lon": [lon_a, lon_b, lon_c, lon_d]
                })
                st.map(df_mapa)

            with col_chart:
                st.subheader("📊 Divisão de Gastos")
                df_gastos = pd.DataFrame({
                    "Categoria": ["Diesel", "Manutenção/Pneus", "Diárias Motorista", "Pedágios & Extras"],
                    "Valor (R$)": [custo_diesel, custo_manutencao, custo_diarias, (pedagios + custos_extras)]
                })
                st.bar_chart(df_gastos.set_index("Categoria"))
