import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# ========= SAC com juros ==========
def gerar_sac(valor_total, meses, taxa_mensal):
    saldo = valor_total
    amortizacao = valor_total / meses
    parcelas = []
    for _ in range(meses):
        juros = saldo * taxa_mensal
        parcela = amortizacao + juros
        parcelas.append(parcela)
        saldo -= amortizacao
    return parcelas

# ========= TIR com proteção ==========
def calcular_tir(fluxos, chute=0.1, max_iter=100, tol=1e-6):
    taxa = chute
    for _ in range(max_iter):
        try:
            f = sum([fluxos[i] / (1 + taxa) ** i for i in range(len(fluxos))])
            df = sum([-i * fluxos[i] / (1 + taxa) ** (i + 1) for i in range(len(fluxos))])
            if abs(df) < 1e-10 or np.isnan(f) or np.isinf(f): break
            nova_taxa = taxa - f / df
            if abs(nova_taxa - taxa) < tol: return nova_taxa
            if nova_taxa > 10 or nova_taxa < -0.99: return None
            taxa = nova_taxa
        except OverflowError:
            return None
    return None

# ========= Simulador principal ==========
def simular_investidor(
    valor_pago_terreno,
    valor_recebido_permuta,
    parcelas_terreno,
    juros_mensal,
    inicio_vendas,
    curva,
    inicio_obra,
    duracao_obra,
    meses_total=120
):
    entrada = [0] * meses_total
    parcelas = [0] * meses_total
    chaves = [0] * meses_total
    fluxo = [0] * meses_total

    # === curva de vendas ===
    if curva == "Normal":
        pct_inicio = 0.35
        pct_mes = 0.06
    elif curva == "Otimista":
        pct_inicio = 0.50
        pct_mes = 0.10
    else:  # Pessimista
        pct_inicio = 0.20
        pct_mes = 0.05

    vendas_percentuais = [0] * meses_total
    if inicio_vendas - 1 < meses_total:
        vendas_percentuais[inicio_vendas - 1] = pct_inicio
        acumulado = pct_inicio
        for i in range(inicio_vendas, meses_total):
            if acumulado >= 1: break
            vendas_percentuais[i] = min(pct_mes, 1 - acumulado)
            acumulado += vendas_percentuais[i]

    # === mês das chaves ===
    mes_chaves = inicio_obra + duracao_obra - 1

    for mes in range(meses_total):
        pct = vendas_percentuais[mes]
        venda_valor = valor_recebido_permuta * pct
        if venda_valor > 0:
            entrada[mes] = venda_valor * 0.10

            sac_meses = max(mes_chaves - mes, 1)
            sac = gerar_sac(venda_valor * 0.20, sac_meses, juros_mensal)
            for i, val in enumerate(sac):
                if mes + i + 1 < meses_total:
                    parcelas[mes + i + 1] += val

            if mes_chaves - 1 < meses_total:
                chaves[mes_chaves - 1] += venda_valor * 0.70

    # === fluxo do investidor ===
    fluxo_investidor = [0] * meses_total
    parcela_terreno = valor_pago_terreno / parcelas_terreno
    for i in range(parcelas_terreno):
        fluxo_investidor[i] = -parcela_terreno

    for mes in range(meses_total):
        fluxo_investidor[mes] += entrada[mes] + parcelas[mes] + chaves[mes]

    df = pd.DataFrame({
        'Mês': list(range(1, meses_total + 1)),
        'Entrada (10%)': entrada,
        'Parcelas SAC (20%)': parcelas,
        'Chaves (70%)': chaves,
        'Fluxo do Investidor': fluxo_investidor
    })

    tir = calcular_tir(fluxo_investidor)
    moic = sum(fluxo_investidor) / valor_pago_terreno
    payback = next((i + 1 for i, v in enumerate(np.cumsum(fluxo_investidor)) if v >= 0), None)

    return df, tir, moic, payback, mes_chaves

# ========= Streamlit App ==========
st.set_page_config(layout="wide")
st.title("🏗️ Simulador do Investidor da Permuta Física (Terreno)")

with st.form("formulario"):
    col1, col2 = st.columns(2)

    with col1:
        valor_pago_terreno = st.number_input("Valor pago pelo terreno (R$)", value=300000.0, step=10000.0)
        parcelas_terreno = st.number_input("Parcelas do pagamento", value=3, min_value=1)
        valor_recebido_permuta = st.number_input("Valor recebido na permuta (R$)", value=300000.0, step=10000.0)

    with col2:
        juros_mensal = st.number_input("Juros mensal sobre SAC (%)", value=0.5) / 100
        inicio_vendas = st.number_input("Mês de início das vendas", value=1, min_value=1)
        curva = st.selectbox("Velocidade de vendas", ["Normal", "Otimista", "Pessimista"])
        inicio_obra = st.number_input("Mês de início da obra", value=1, min_value=1)
        duracao_obra = st.number_input("Duração da obra (meses)", value=36, min_value=1)

    simular = st.form_submit_button("Simular")

if simular:
    df, tir, moic, payback, mes_chaves = simular_investidor(
        valor_pago_terreno,
        valor_recebido_permuta,
        int(parcelas_terreno),
        juros_mensal,
        int(inicio_vendas),
        curva,
        int(inicio_obra),
        int(duracao_obra)
    )

    st.success(f"🏁 Entrega das chaves prevista para o mês {mes_chaves}")

    st.subheader("📊 Fluxo de Caixa do Investidor")
    st.dataframe(df)

    col1, col2, col3 = st.columns(3)
    col1.metric("TIR", f"{tir:.2%}" if tir else "N/A")
    col2.metric("MoIC", f"{moic:.2f}x")
    col3.metric("Payback", f"{payback} meses" if payback else "N/A")

    st.caption("📌 A TIR considera o valor pago pelo terreno (parcelado) e os recebíveis 10/20/70 da permuta física recebida.")

    st.subheader("📈 Gráfico Acumulado")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['Mês'], y=np.cumsum(df['Fluxo do Investidor']),
                             mode='lines+markers', name='Acumulado', line=dict(color='blue')))
    st.plotly_chart(fig, use_container_width=True)

    st.download_button("📥 Baixar Excel", df.to_excel(index=False, engine='openpyxl'),
                       file_name="fluxo_investidor.xlsx")

    # ===== Gráfico Didático =====
    st.subheader("📊 Gráfico Didático: Entradas x Saídas x Acumulado")
    fluxo = df['Fluxo do Investidor']
    entrada_total = df['Entrada (10%)'] + df['Parcelas SAC (20%)'] + df['Chaves (70%)']
    saida_total = [abs(val) if val < 0 else 0 for val in fluxo]
    entrada_total = [val if val > 0 else 0 for val in fluxo]
    acumulado = np.cumsum(fluxo)

    fig_final = go.Figure()
    fig_final.add_trace(go.Bar(x=df['Mês'], y=saida_total, name='Investimento (Saída)', marker_color='crimson'))
    fig_final.add_trace(go.Bar(x=df['Mês'], y=entrada_total, name='Recebíveis (Entrada)', marker_color='seagreen'))
    fig_final.add_trace(go.Scatter(x=df['Mês'], y=acumulado,
                                   name='Fluxo Acumulado',
                                   mode='lines+markers',
                                   line=dict(color='royalblue', width=3)))

    fig_final.update_layout(
        barmode='relative',
        xaxis_title='Mês',
        yaxis_title='R$',
        legend_title='Fluxos',
        title='📉 Visão Completa do Fluxo de Caixa do Investidor',
        height=600,
        template='plotly_white'
    )
    st.plotly_chart(fig_final, use_container_width=True)
