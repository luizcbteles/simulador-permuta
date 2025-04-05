import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# ========= Função SAC com juros definido ==========
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

# ========= TIR manual segura ==========
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

# ========= Simulador ==========
def simular_investidor(valor_permuta, parcelas_terreno, juros_mensal, meses_total=120):
    entrada = [0] * meses_total
    parcelas = [0] * meses_total
    chaves = [0] * meses_total
    fluxo = [0] * meses_total

    curva_vendas = [0] * meses_total
    curva_vendas[0] = 0.5
    for i in range(1, 11):
        if i < meses_total:
            curva_vendas[i] = 0.05

    for mes in range(meses_total):
        venda_pct = curva_vendas[mes]
        venda_valor = valor_permuta * venda_pct

        if venda_valor > 0:
            entrada[mes] = venda_valor * 0.10
            sac = gerar_sac(venda_valor * 0.20, 48, juros_mensal)
            for i, val in enumerate(sac):
                if mes + i + 1 < meses_total:
                    parcelas[mes + i + 1] += val
            if 59 < meses_total:
                chaves[59] += venda_valor * 0.70

    # Investimento (parcelas pagas pelo investidor)
    fluxo_investidor = [0] * meses_total
    valor_parcela_terreno = valor_permuta / parcelas_terreno
    for i in range(parcelas_terreno):
        fluxo_investidor[i] = -valor_parcela_terreno

    for mes in range(meses_total):
        fluxo_investidor[mes] += entrada[mes] + parcelas[mes] + chaves[mes]

    df = pd.DataFrame({
        'Mês': list(range(1, meses_total + 1)),
        'Entrada 10%': entrada,
        'Parcelas 20% SAC': parcelas,
        'Chaves 70%': chaves,
        'Fluxo do Investidor': fluxo_investidor
    })

    tir = calcular_tir(fluxo_investidor)
    moic = sum(fluxo_investidor) / valor_permuta
    payback = next((i + 1 for i, v in enumerate(np.cumsum(fluxo_investidor)) if v >= 0), None)

    return df, tir, moic, payback

# ========= Streamlit App ==========
st.set_page_config(layout="centered")
st.title("🏦 Simulador de Investidor da Permuta (Terreno)")

with st.form("formulario"):
    valor_permuta = st.number_input("Valor do Terreno / Permuta (R$)", value=300000.0, step=10000.0)
    parcelas_terreno = st.number_input("Número de parcelas pagas pelo investidor", value=3, min_value=1)
    juros_mensal = st.number_input("Juros mensal sobre parcelas do recebível (%)", value=0.5) / 100
    simular = st.form_submit_button("Simular")

if simular:
    df, tir, moic, payback = simular_investidor(valor_permuta, int(parcelas_terreno), juros_mensal)

    st.subheader("📊 Fluxo de Caixa do Investidor")
    st.dataframe(df)

    col1, col2, col3 = st.columns(3)
    col1.metric("TIR", f"{tir:.2%}" if tir else "N/A")
    col2.metric("MoIC", f"{moic:.2f}x")
    col3.metric("Payback", f"{payback} meses" if payback else "N/A")

    st.caption("📌 A TIR considera o valor pago em parcelas pelo investidor e os recebíveis da permuta (10/20/70 com SAC corrigido pelos juros definidos).")

    st.subheader("📈 Gráfico Acumulado do Investidor")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['Mês'], y=np.cumsum(df['Fluxo do Investidor']),
                             mode='lines+markers', name='Acumulado', line=dict(color='blue')))
    st.plotly_chart(fig, use_container_width=True)

    st.download_button("📥 Baixar Excel", df.to_excel(index=False, engine='openpyxl'),
                       file_name="fluxo_investidor.xlsx")
