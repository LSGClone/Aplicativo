import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import requests

st.set_page_config(
    page_title="Roteirizador de Mobilização de Pranchas",
    page_icon="🚛",
    layout="wide"
)

st.title("🚛 Roteirizador & Calculador Automático de Mobilização")
st.caption("Cálculo automático de rotas ponto a ponto (OSRM Routing), consumo por trecho (vazio vs. carregado), manutenção e custos operacionais.")

# Funções de Geocodificação e Rotas Gratuitas (OSRM / Nominatim)
@st.cache_data(ttl=3600, show_spinner=False)
def geocode_address(address_text):
    """Busca coordenadas latitude/longitude a partir do nome da cidade ou endereço."""
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": address_text,
        "format": "json",
        "limit": 1,
        "countrycodes": "br"
    }
    headers = {"User-Agent": "LogisticaPranchasApp/2.0"}
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
    """Calcula a rota real rodoviária, distância em km e coordenadas do traçado."""
    url = f"https://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}?overview=full&geometries=geojson"
    try:
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get("routes"):
            route = data["routes"][0]
            dist_km = route["distance"] / 1000.0  # metros para km
            dur_horas = route["duration"] / 3600.0 # segundos para horas
            coords = [[lat, lon] for lon, lat in route["geometry"]["coordinates"]]
            return dist_km, dur_horas, coords
    except Exception:
        pass
    return None, None, []

# Painel Lateral de Parâmetros Operacionais
with st.sidebar:
    st.header("⚙️ Parâmetros de Custo")
    
    st.subheader("Combustível")
    preco_diesel = st.number_input("Preço Diesel (R$/L)", min_value=3.0, max_value=15.0, value=6.20, step=0.05, format="%.2f")
    
    st.subheader("Consumo do Cavalo/Prancha")
    consumo_vazio = st.number_input("Consumo VAZIO (km/L)", min_value=0.5, max_value=10.0, value=2.6, step=0.1)
    consumo_carregado = st.number_input("Consumo CARREGADO (km/L)", min_value=0.5, max_value=10.0, value=1.7, step=0.1)
    
    st.subheader("Manutenção & Desgaste")
    manutencao_km = st.number_input("Manutenção/Pneus (R$/km)", min_value=0.0, max_value=10.0, value=1.35, step=0.05, format="%.2f")
    
    st.subheader("Custos Fixos")
    diaria_motorista = st.number_input("Diária Motorista/Equipe (R$/dia)", min_value=0.0, max_value=2000.0, value=280.0, step=10.0, format="%.2f")

# Definição do Roteiro Encadeado
st.subheader("📍 Planejamento de Rota da Mobilização")

col_p1, col_p2, col_p3, col_p4 = st.columns(4)
with col_p1:
    ponto_a = st.text_input("1. Saída da Prancha (Base/Garagem)", value="Barreiras, BA")
with col_p2:
    ponto_b = st.text_input("2. Coleta da Máquina (Origem da Carga)", value="Luis Eduardo Magalhaes, BA")
with col_p3:
    ponto_c = st.text_input("3. Desembarque da Máquina (Destino da Carga)", value="Sao Desiderio, BA")
with col_p4:
    retorno_base = st.selectbox("4. Destino Final da Prancha", ["Retornar à Base (Ponto 1)", "Permanecer no Desembarque", "Outra Cidade"])
    ponto_d = ponto_a if retorno_base == "Retornar à Base (Ponto 1)" else (ponto_c if retorno_base == "Permanecer no Desembarque" else st.text_input("Endereço do Destino Final", value="Correntina, BA"))

col_extra1, col_extra2, col_extra3 = st.columns(3)
with col_extra1:
    maquina_desc = st.text_input("Equipamento a Transportar", value="Escavadeira Hidráulica 22 Toneladas")
with col_extra2:
    pedagios_estimados = st.number_input("Pedágios Totais Estimados (R$)", min_value=0.0, max_value=10000.0, value=0.0, step=10.0)
with col_extra3:
    custos_extras = st.number_input("Taxas AET / Escolta / Hospedagem (R$)", min_value=0.0, max_value=20000.0, value=350.0, step=50.0)

btn_calcular = st.button("🚀 Calcular Rota Automática e Custos", type="primary", use_container_width=True)

if btn_calcular:
    with st.spinner("Geocodificando pontos e calculando melhores trajetos rodoviários..."):
        # Geocodificação
        lat_a, lon_a, name_a = geocode_address(ponto_a)
        lat_b, lon_b, name_b = geocode_address(ponto_b)
        lat_c, lon_c, name_c = geocode_address(ponto_c)
        lat_d, lon_d, name_d = geocode_address(ponto_d)

        erro_local = None
        if not lat_a: erro_local = f"Não encontramos o local de saída: {ponto_a}"
        elif not lat_b: erro_local = f"Não encontramos o local de coleta: {ponto_b}"
        elif not lat_c: erro_local = f"Não encontramos o local de desembarque: {ponto_c}"
        elif not lat_d: erro_local = f"Não encontramos o destino final: {ponto_d}"

        if erro_local:
            st.error(f"❌ {erro_local}. Verifique a grafia ou inclua a cidade/estado.")
        else:
            # Trecho 1: Base -> Coleta (VAZIO)
            dist_1, tempo_1, poly_1 = get_osrm_route(lat_a, lon_a, lat_b, lon_b)
            # Trecho 2: Coleta -> Desembarque (CARREGADO)
            dist_2, tempo_2, poly_2 = get_osrm_route(lat_b, lon_b, lat_c, lon_c)
            # Trecho 3: Desembarque -> Destino Final (VAZIO)
            dist_3, tempo_3, poly_3 = (0.0, 0.0, []) if ponto_c == ponto_d else get_osrm_route(lat_c, lon_c, lat_d, lon_d)

            if dist_1 is None or dist_2 is None or (dist_3 is None and ponto_c != ponto_d):
                st.error("❌ Não foi possível traçar a rota rodoviária entre os pontos. Verifique a conexão com a rede viária.")
            else:
                dist_3 = dist_3 or 0.0
                tempo_3 = tempo_3 or 0.0
                
                # Cálculos de Distância e Tempo
                km_vazio = dist_1 + dist_3
                km_carregado = dist_2
                km_total = km_vazio + km_carregado
                horas_total = tempo_1 + tempo_2 + tempo_3
                
                # Estimativa de Dias Operacionais (considerando média de 8h/dia + tempos de carga/descarga e amarração de prancha)
                tempo_carga_descarga_horas = 3.0  # Tempo para encostar prancha, subir máquina, amarrar correntes e desembarcar
                dias_calculados = max(1.0, round((horas_total + tempo_carga_descarga_horas) / 8.0, 1))

                # Cálculos Financeiros
                litros_vazio = km_vazio / consumo_vazio if km_vazio > 0 else 0
                litros_carregado = km_carregado / consumo_carregado if km_carregado > 0 else 0
                litros_totais = litros_vazio + litros_carregado
                custo_diesel_total = litros_totais * preco_diesel

                custo_manutencao_total = km_total * manutencao_km
                custo_diarias_total = dias_calculados * diaria_motorista
                custo_geral = custo_diesel_total + custo_manutencao_total + custo_diarias_total + pedagios_estimados + custos_extras
                custo_km_medio = custo_geral / km_total if km_total > 0 else 0

                st.success("✅ Rota calculada com sucesso!")
                
                # Métricas Principais
                m1, m2, m3, m4, m5 = st.columns(5)
                m1.metric("Custo Total", f"R$ {custo_geral:,.2f}")
                m2.metric("Distância Total", f"{km_total:,.1f} km")
                m3.metric("Tempo Dirigindo", f"{horas_total:,.1f} h", f"~ {dias_calculados} dias de op.")
                m4.metric("Diesel Total", f"{litros_totais:,.1f} L", f"R$ {custo_diesel_total:,.2f}")
                m5.metric("Custo / km", f"R$ {custo_km_medio:,.2f}")

                # Tabela de Segmentos da Viagem
                st.markdown("---")
                st.subheader("📋 Detalhamento dos Trechos da Mobilização")
                
                df_trechos = pd.DataFrame([
                    {
                        "Trecho": "1. Posicionamento (Vazio)",
                        "Origem": ponto_a,
                        "Destino": ponto_b,
                        "Condição": "Vazio",
                        "Distância": f"{dist_1:,.1f} km",
                        "Consumo": f"{dist_1/consumo_vazio:,.1f} L",
                        "Custo Diesel": f"R$ {(dist_1/consumo_vazio)*preco_diesel:,.2f}",
                    },
                    {
                        "Trecho": f"2. Transporte: {maquina_desc}",
                        "Origem": ponto_b,
                        "Destino": ponto_c,
                        "Condição": "CARREGADO",
                        "Distância": f"{dist_2:,.1f} km",
                        "Consumo": f"{dist_2/consumo_carregado:,.1f} L",
                        "Custo Diesel": f"R$ {(dist_2/consumo_carregado)*preco_diesel:,.2f}",
                    },
                    {
                        "Trecho": "3. Retorno / Reposicionamento",
                        "Origem": ponto_c,
                        "Destino": ponto_d,
                        "Condição": "Vazio",
                        "Distância": f"{dist_3:,.1f} km",
                        "Consumo": f"{dist_3/consumo_vazio:,.1f} L",
                        "Custo Diesel": f"R$ {(dist_3/consumo_vazio)*preco_diesel:,.2f}",
                    }
                ])
                st.dataframe(df_trechos, use_container_width=True)

                # Mapa Interativo da Rota
                col_mapa, col_resumo = st.columns([1.6, 1])
                
                with col_mapa:
                    st.subheader("🗺️ Mapa da Rota Traçada")
                    mapa = folium.Map(location=[lat_b, lon_b], zoom_start=8)
                    
                    # Marcadores
                    folium.Marker([lat_a, lon_a], popup=f"Saída: {ponto_a}", tooltip="Saída Base", icon=folium.Icon(color="gray", icon="home")).add_to(mapa)
                    folium.Marker([lat_b, lon_b], popup=f"Coleta: {ponto_b}", tooltip=f"Coleta Máquina: {maquina_desc}", icon=folium.Icon(color="green", icon="arrow-up")).add_to(mapa)
                    folium.Marker([lat_c, lon_c], popup=f"Desembarque: {ponto_c}", tooltip="Desembarque Máquina", icon=folium.Icon(color="red", icon="arrow-down")).add_to(mapa)
                    if ponto_c != ponto_d:
                        folium.Marker([lat_d, lon_d], popup=f"Destino Final: {ponto_d}", tooltip="Destino Final", icon=folium.Icon(color="blue", icon="flag")).add_to(mapa)

                    # Polylines dos Trechos
                    if poly_1:
                        folium.PolyLine(poly_1, color="blue", weight=4, opacity=0.7, tooltip=f"Trecho 1 (Vazio): {dist_1:.1f} km").add_to(mapa)
                    if poly_2:
                        folium.PolyLine(poly_2, color="orange", weight=6, opacity=0.9, tooltip=f"Trecho 2 (CARREGADO): {dist_2:.1f} km").add_to(mapa)
                    if poly_3:
                        folium.PolyLine(poly_3, color="blue", weight=4, opacity=0.7, tooltip=f"Trecho 3 (Vazio): {dist_3:.1f} km").add_to(mapa)

                    st_folium(mapa, width=700, height=450)

                with col_resumo:
                    st.subheader("📊 Composição do Custo Total")
                    df_pizza = pd.DataFrame({
                        "Custo": ["Diesel", "Manutenção/Pneus", "Diárias Motorista", "Pedágios & Extras"],
                        "Valor": [custo_diesel_total, custo_manutencao_total, custo_diarias_total, (pedagios_estimados + custos_extras)]
                    })
                    st.bar_chart(df_pizza.set_index("Custo"))
