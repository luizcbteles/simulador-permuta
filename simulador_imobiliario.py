import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# ========= Função para calcular parcelas SAC ==========
def gerar_sac(valor_total, meses, taxa_mensal):
    saldo_devedor = valor_total
    amortizacao = valor_total / meses
    parcelas = []
    for _ in range(meses):
        juros = saldo_devedor * taxa_mensal
        parcela = amortizacao + juros
        parcelas.append(parcela)
        saldo_devedor -= amortizacao
    return parcelas

# ========= Função para calcular TIR (substituindo np.irr) ==========
def calcular_tir(fluxos, chute_inicial=0.1, max_iter=100, tol=1e-6):
    taxa = chute_inicial
    for _ in range(max_iter):
        f = sum([fluxos[i] / (1 + taxa) ** i for i in range(len(fluxos))])
        df = sum([-i * fluxos[i] / (1 + taxa) ** (i + 1) for i in range(len(fluxos))])
        if abs(df) < 1e-10:
            break
        nova_taxa = taxa - f / df
        if abs(nova_taxa - taxa) < tol:
            return nova_taxa
        taxa = nova_taxa
    return None

# ========= Função principal ==========
def simular_projeto(nome, VGV, valor_permuta, custo_obra, custo_terreno,
                    mes_inicio_vendas, mes_inicio_obra, parcelas_terreno,
                    correcao_CUB_ano, meses_total=120):

    correcao_CUB_mensal = (1 + correcao_CUB_ano) ** (1 / 12) - 1
    VGV_equity = valor_permuta
    obra_mensal_base = custo_obra / 60

    # Curva de vendas 50% no mês inicial, 5% por mês após
    vendas_percentuais = [0] * meses_total
    vendas_percentuais[mes_inicio_vendas - 1] = 0.5
    for i in range(mes_inicio_vendas, min(mes_inicio_vendas + 10, meses_total)):
        vendas_percentuais[i] = 0.05

    entrada_equity = [0] * meses_total
    parcelas_equity = [0] * meses_total
    chaves_equity = [0] * meses_total
    obra = [0] * meses_total
    custos_comerciais = [0] * meses_total
    investimento = [0] * meses_total
    fluxo_liquido = [0] * meses_total
    fluxo_investidor = [0] * meses_total

    cub_fator = 1

    for mes in range(meses_total):
        # Vendas
        venda_pct = vendas_percentuais[mes]
        venda_valor = VGV_equity * venda_pct

        if venda_valor > 0:
            entrada_equity[mes] = venda_valor * 0.10
            custos_comerciais[mes] = venda_valor * 0.09

            sac = gerar_sac(venda_valor * 0.20, 48, correcao_CUB_mensal)
            for i, val in enumerate(sac):
                if mes + i + 1 < meses_total:
                    parcelas_equity[mes + i + 1] += val

            if 59 < meses_total:
                chaves_equity[59] += venda_valor * 0.70

        # Obra corrigida
        if mes >= mes_inicio_obra - 1 and mes < mes_inicio_obra - 1 + 60:
            cub_fator *= 1 + correcao_CUB_mensal
            obra[mes] = obra_mensal_base * cub_fator

        # Investimentos do projeto
        if mes == 0:
            investimento[mes] += custo_terreno
        if obra[mes] > 0:
            investimento[mes] += obra[mes]

        # Receita total e fluxo do projeto
        receita = entrada_equity[mes] + parcelas_equity[mes] + chaves_equity[mes]
        saidas = obra[mes] + custos_comerciais[mes] + (custo_terreno if mes == 0 else 0)
        fluxo_liquido[mes] = receita - saidas

    # Parcelas do terreno para o investidor
    parcela_terreno = custo_terreno / parcelas_terreno
    for i in range(parcelas_terreno):
        fluxo_investidor[i] = -parcela_terreno

    for mes in range(meses_total):
        fluxo_investidor[mes] += entrada_equity[mes] + parcelas_equity[mes] + chaves_equity[mes]

    # DataFrame final
    df = pd.DataFrame({
        'Mês': list(range(1, meses_total + 1)),
        'Entrada 10%': entrada_equity,
        'Parcelas 20% SAC': parcelas_equity,
        'Chaves 70%': chaves_equity,
        'Receita Total': [entrada_equity[i] + parcelas_equity[i] + chaves_equity[i] for i in range(meses_total)],
        'Obra': obra,
        'Custos Comerciais': custos_comerciais,
        'Investimento': investimento,
        'Fluxo Líquido Projeto': fluxo_liquido,
        'Fluxo Investidor Terreno': fluxo_investidor
    })

    # Indicadores
    tir_projeto = calcular_tir(fluxo_liquido)
    moic_projeto = sum(fluxo_liquido) / (custo_obra + custo_terreno)
    payback_projeto = next((i+1 for i, v in enumerate(np.cumsum(fluxo_liquido)) if v >= 0), None)

    tir_investidor = calcular_tir(fluxo_investidor)
    moic_investidor = sum(fluxo_investidor) / custo_terreno
    payback_investidor = next((i+1 for i, v in enumerate(np.cumsum(fluxo_investidor)) if v >= 0), None)

    return df, tir_projeto, moic_projeto, payback_projeto, tir_investidor, moic_investidor, payback_investidor

# ========== Interface Streamlit ==========
st.set_page_config(layout="wide")
st.title("🏗️ Simulador de Fluxo de Caixa - Permuta com Investidor do Terreno")

with st.form("inputs"):
    col1, col2 = st.columns(2)

    with col1:
        nome = st.text_input("Nome do Projeto", "Duna III")
        VGV = st.number_input("VGV Total", value=1000000)
        valor_permuta = st.number_input("Valor da Permuta (Equity do Investidor)", value=200000)
        custo_obra = st.number_input("Custo da Obra", value=500000)

    with col2:
        custo_terreno = st.number_input("Custo do Terreno", value=300000)
        parcelas_terreno = st.number_input("Parcelas do Investidor para pagar o Terreno", value=3)
        mes_inicio_vendas = st.number_input("Mês de Início das Vendas", value=1)
        mes_inicio_obra = st.number_input("Mês de Início da Obra", value=1)
        correcao_CUB = st.number_input("Correção Anual do CUB (%)", value=5.0) / 100

    submitted = st.form_submit_button("Simular")

if submitted:
    df, tir_proj, moic_proj, pb_proj, tir_inv, moic_inv, pb_inv = simular_projeto(
        nome, VGV, valor_permuta, custo_obra, custo_terreno,
        mes_inicio_vendas, mes_inicio_obra, int(parcelas_terreno), correcao_CUB
    )

    st.subheader("📊 Fluxo de Caixa - Projeto")
    st.dataframe(df)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("TIR do Projeto", f"{tir_proj:.2%}")
        st.metric("MoIC do Projeto", f"{moic_proj:.2f}x")
        st.metric("Payback do Projeto", f"{pb_proj} meses")
    with col2:
        st.metric("TIR do Investidor", f"{tir_inv:.2%}")
        st.metric("MoIC do Investidor", f"{moic_inv:.2f}x")
        st.metric("Payback do Investidor", f"{pb_inv} meses")

    st.subheader("📈 Gráfico: Fluxo Acumulado")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['Mês'], y=np.cumsum(df['Fluxo Líquido Projeto']),
                             name='Projeto', line=dict(color='green')))
    fig.add_trace(go.Scatter(x=df['Mês'], y=np.cumsum(df['Fluxo Investidor Terreno']),
                             name='Investidor Terreno', line=dict(color='blue')))
    st.plotly_chart(fig, use_container_width=True)

    st.download_button("📥 Baixar Excel", df.to_excel(index=False, engine='openpyxl'),
                       file_name="fluxo_caixa_simulador.xlsx")
