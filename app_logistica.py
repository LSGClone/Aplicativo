import streamlit as st
import pandas as pd
import json

# Configuração da página
st.set_page_config(
    page_title="Calculadora de Mobilização de Pranchas",
    page_icon="🚛",
    layout="wide"
)

st.title("🚛 Calculadora de Custos de Mobilização (Pranchas)")
st.caption("Sistema interno para estimativa de rotas, consumo de diesel, manutenção e custo operacional.")

# Sidebar - Parâmetros Padrão e Veículos
with st.sidebar:
    st.header("⚙️ Parâmetros Operacionais")
    
    st.subheader("1. Combustível")
    preco_diesel = st.number_input("Preço do Diesel (R$/Litro)", min_value=1.0, max_value=20.0, value=6.20, step=0.05, format="%.2f")
    
    st.subheader("2. Perfil da Prancha / Cavalo")
    consumo_carregado = st.number_input("Consumo Carregado (km/L)", min_value=0.5, max_value=10.0, value=1.8, step=0.1)
    consumo_vazio = st.number_input("Consumo Vazio / Retorno (km/L)", min_value=0.5, max_value=10.0, value=2.5, step=0.1)
    
    st.subheader("3. Manutenção e Desgaste")
    custo_manutencao_km = st.number_input("Custo de Manutenção / Pneus (R$/km)", min_value=0.0, max_value=10.0, value=1.40, step=0.05, format="%.2f",
                                         help="Inclui provisão para pneus, óleo, suspensão e revisões periódicas do conjunto.")
    
    st.subheader("4. Custos Fixos / Diária")
    custo_diaria_motorista = st.number_input("Diária Motorista/Operacional (R$/dia)", min_value=0.0, max_value=2000.0, value=250.0, step=10.0, format="%.2f")

# Aba Principal
tab1, tab2 = st.tabs(["📍 Nova Mobilização", "📊 Histórico / Simulações Rápidas"])

with tab1:
    col1, col2 = st.tabs(["Dados da Viagem", "Custos Extras & Carga"]) if False else st.columns(2)
    
    with col1:
        st.subheader("Informações da Rota")
        origem = st.text_input("Origem (Cidade / Obra)", value="Base Central")
        destino = st.text_input("Destino (Obra / Cliente / Região)", value="Obra Fazenda Nova")
        maquina = st.text_input("Equipamento / Máquina a transportar", value="Escavadeira Hidráulica 22t")
        
        col_dist1, col_dist2 = st.columns(2)
        with col_dist1:
            distancia_trecho = st.number_input("Distância Trecho (km)", min_value=1.0, max_value=5000.0, value=180.0, step=5.0)
        with col_dist2:
            tipo_viagem = st.selectbox("Tipo de Trajeto", ["Ida e Volta (Carregado + Vazio)", "Apenas Ida (Carregado)", "Ida e Volta Carregado"])
            
        dias_estimados = st.number_input("Duração estimada da mobilização (dias)", min_value=0.5, max_value=30.0, value=1.0, step=0.5)

    with col2:
        st.subheader("Custos Adicionais & Específicos")
        pedagio_total = st.number_input("Pedágios Estimados (R$)", min_value=0.0, max_value=5000.0, value=120.0, step=10.0, format="%.2f")
        requer_aet = st.checkbox("Requer AET (Autorização Especial de Trânsito)", value=False)
        custo_aet = 0.0
        if requer_aet:
            custo_aet = st.number_input("Taxa / Custo AET (R$)", min_value=0.0, max_value=3000.0, value=350.0, step=50.0)
            
        requer_escolta = st.checkbox("Requer Batedor / Escolta", value=False)
        custo_escolta = 0.0
        if requer_escolta:
            custo_escolta = st.number_input("Custo de Escolta Credenciada (R$)", min_value=0.0, max_value=10000.0, value=800.0, step=100.0)
            
        outros_custos = st.number_input("Outros Custos (Hospedagem, Alimentação extra, etc.) (R$)", min_value=0.0, max_value=5000.0, value=100.0, step=50.0)

    # Lógica de Cálculo
    if tipo_viagem == "Ida e Volta (Carregado + Vazio)":
        km_carregado = distancia_trecho
        km_vazio = distancia_trecho
        km_total = distancia_trecho * 2
    elif tipo_viagem == "Apenas Ida (Carregado)":
        km_carregado = distancia_trecho
        km_vazio = 0.0
        km_total = distancia_trecho
    else: # Ida e Volta Carregado
        km_carregado = distancia_trecho * 2
        km_vazio = 0.0
        km_total = distancia_trecho * 2

    # Consumo diesel
    litros_carregado = km_carregado / consumo_carregado if km_carregado > 0 else 0
    litros_vazio = km_vazio / consumo_vazio if km_vazio > 0 else 0
    total_litros = litros_carregado + litros_vazio
    custo_combustivel = total_litros * preco_diesel

    # Manutenção
    custo_manutencao = km_total * custo_manutencao_km

    # Diárias
    custo_diarias = dias_estimados * custo_diaria_motorista

    # Extras
    total_extras = pedagio_total + custo_aet + custo_escolta + outros_custos

    # Total Geral
    custo_total = custo_combustivel + custo_manutencao + custo_diarias + total_extras
    custo_por_km_medio = custo_total / km_total if km_total > 0 else 0

    st.markdown("---")
    st.header("📋 Resumo do Custo de Mobilização")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Custo Total Estimado", f"R$ {custo_total:,.2f}")
    m2.metric("Distância Total", f"{km_total:,.1f} km")
    m3.metric("Diesel Total", f"{total_litros:,.1f} L", f"R$ {custo_combustivel:,.2f}")
    m4.metric("Custo Médio / km", f"R$ {custo_por_km_medio:,.2f}")

    col_chart, col_det = st.columns([1, 1])

    with col_chart:
        df_custos = pd.DataFrame({
            "Componente": ["Diesel", "Manutenção/Pneus", "Diárias Operacionais", "Pedágios & Extras"],
            "Valor (R$)": [custo_combustivel, custo_manutencao, custo_diarias, total_extras]
        })
        st.bar_chart(df_custos.set_index("Componente"))

    with col_det:
        st.subheader("Detalhamento dos Gastos")
        st.write(f"- **Diesel (Carregado):** {litros_carregado:.1f} L (R$ {litros_carregado * preco_diesel:,.2f})")
        if km_vazio > 0:
            st.write(f"- **Diesel (Vazio):** {litros_vazio:.1f} L (R$ {litros_vazio * preco_diesel:,.2f})")
        st.write(f"- **Manutenção/Desgaste:** R$ {custo_manutencao:,.2f}")
        st.write(f"- **Diárias ({dias_estimados} dias):** R$ {custo_diarias:,.2f}")
        st.write(f"- **Pedágios:** R$ {pedagio_total:,.2f}")
        if requer_aet:
            st.write(f"- **AET:** R$ {custo_aet:,.2f}")
        if requer_escolta:
            st.write(f"- **Escolta:** R$ {custo_escolta:,.2f}")
        if outros_custos > 0:
            st.write(f"- **Outros:** R$ {outros_custos:,.2f}")

with tab2:
    st.subheader("Tabela de Apoio e Parâmetros Rápidos")
    st.markdown("""
    | Tipo de Carga / Máquina | Peso Médio | Requer AET? | Consumo Médio Esperado |
    | :--- | :--- | :--- | :--- |
    | **Retroescavadeira / Mini Carregadeira** | 7 - 9 ton | Geralmente Não | ~ 2.2 a 2.6 km/L |
    | **Escavadeira Hidráulica 20-24t** | 20 - 24 ton | Sim (Largura/Peso) | ~ 1.6 a 1.9 km/L |
    | **Trator de Esteira D6 / Motoniveladora** | 16 - 22 ton | Sim (Geralmente por largura de lâmina) | ~ 1.7 a 2.0 km/L |
    | **Escavadeira 30t+** | 30+ ton | Sim + Escolta dependendo da rota | ~ 1.3 a 1.6 km/L |
    """)
