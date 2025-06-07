import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from dotenv import load_dotenv

# --- Importações para E-mail ---

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import (
    MIMEMultipart,
)  # Para e-mails mais complexos (HTML, anexos)

import os
from datetime import datetime

load_dotenv()


# --- Função para Enviar E-mail ---
def send_email_alert(recipient_email, subject, body_content):
    # Use as informações da sua conta de e-mail para configurar o remetente
    # ATENÇÃO: NUNCA coloque suas senhas diretamente no código!
    # Usaremos st.secrets para segurança (explicado abaixo)

    sender_email = os.getenv("sender_email")

    sender_password = os.getenv("sender_password")

    # Configurações do servidor SMTP (para Gmail)
    smtp_server = "smtp.gmail.com"
    smtp_port = 587  # Porta padrão para TLS (criptografia)

    # Cria o objeto da mensagem
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg["Subject"] = subject

    # Anexa o corpo da mensagem (pode ser texto simples ou HTML)
    msg.attach(
        MIMEText(body_content, "html")
    )  # 'plain' para texto simples; 'html' para HTML

    try:
        # Inicia a conexão com o servidor SMTP
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Habilita a criptografia TLS

        # Faz login na conta do remetente
        server.login(sender_email, sender_password)

        # Envia o e-mail
        text = msg.as_string()
        server.sendmail(sender_email, recipient_email, text)

        server.quit()  # Encerra a conexão
        return True  # Indica sucesso
    except Exception as e:
        print(f"Erro ao enviar e-mail: {e}")
        return False


# Título da aplicação
st.title("InvestBot 📈")

# Mensagem de boas-vindas
st.write(
    "Olá! Use esta ferramenta para visualizar dados históricos de ações e obter insights de compra."
)

# Campo de entrada para o ticker da ação
ticker_input = st.text_input(
    "Digite o ticker da ação (ex: PETR4, ITUB4, VALE3):", "PETR4"
).upper()

# Adicionar o sufixo '.SA' para ações brasileiras, se o usuário não o fizer
if not ticker_input.endswith(".SA"):
    ticker_input += ".SA"

st.write(f"Você digitou: {ticker_input}")

# Botão para carregar os dados
if st.button("Buscar Dados"):
    st.write(f"Buscando dados para {ticker_input}...")

    try:
        # Baixa os dados históricos
        # period='60d' busca os últimos 60 dias (para ter dados suficientes para SMA de 20 dias)
        # interval='1d' define que queremos dados diários
        dados_acao = yf.Ticker(ticker_input).history(period="60d", interval="1d")

        # Verifica se há dados
        if dados_acao.empty:
            st.warning(
                f"Não foi possível encontrar dados para a ação {ticker_input}. Verifique o ticker e tente novamente."
            )
        else:
            st.success(f"Dados de {ticker_input} carregados com sucesso!")
            # Armazenar os dados na sessão do Streamlit para poder usá-los depois
            st.session_state["dados_acao"] = dados_acao
            st.session_state["ticker"] = ticker_input

    except Exception as e:
        st.error(
            f"Ocorreu um erro ao buscar os dados: {e}. Verifique sua conexão com a internet ou o ticker."
        )

# Isso garante que só processamos e exibimos se os dados estiverem disponíveis
if "dados_acao" in st.session_state and not st.session_state["dados_acao"].empty:
    dados_acao = st.session_state["dados_acao"]
    ticker_atual = st.session_state["ticker"]

    st.subheader(f"Cotação dos Últimos 30 Dias para {ticker_atual}")
    # Selecionar apenas os últimos 30 dias de dados para exibição

    # A API já retornou 60d, vamos pegar os 30 mais recentes
    dados_30_dias = dados_acao.tail(
        30
    ).copy()  # .copy() para evitar SettingWithCopyWarning

    # Calcula a Média Móvel Simples (SMA) de 20 dias
    # Usamos o DataFrame completo 'dados_acao' para ter 20 pontos de dados válidos
    dados_acao["SMA_20"] = dados_acao["Close"].rolling(window=20).mean()

    # Exibir o DataFrame (opcional, útil para depuração)
    # st.write(dados_30_dias[['Close', 'Volume']]) # Pode exibir aqui para ver os dados brutos

    # Pegar o último preço de fechamento e a última SMA calculada
    ultimo_preco = dados_acao["Close"].iloc[-1]
    ultima_sma_20 = dados_acao["SMA_20"].iloc[-1]

    st.write(f"Último Preço de Fechamento: R$ {ultimo_preco:.2f}")
    st.write(f"Última SMA 20 dias: R$ {ultima_sma_20:.2f}")

    # Criar o gráfico interativo com Plotly
    fig = go.Figure()

    # Adicionar o preço de fechamento
    fig.add_trace(
        go.Scatter(
            x=dados_30_dias.index,  # A data é o índice do DataFrame
            y=dados_30_dias["Close"],
            mode="lines",
            name="Preço de Fechamento",
            line=dict(color="blue"),
        )
    )

    # Adicionar a Média Móvel Simples (SMA_20)
    # Atenção: a SMA só terá valores válidos após os primeiros 20 dias.
    # Precisamos garantir que estamos plotando a SMA para o período visível de 30 dias.
    fig.add_trace(
        go.Scatter(
            x=dados_acao.tail(
                30
            ).index,  # Pegar o índice dos últimos 30 dias para a SMA
            y=dados_acao["SMA_20"].tail(30),  # Pegar a SMA dos últimos 30 dias
            mode="lines",
            name="SMA 20 Dias",
            line=dict(color="orange", dash="dash"),
        )
    )

    # Configurações do layout do gráfico
    fig.update_layout(
        title=f"Histórico de Preços e SMA para {ticker_atual} (Últimos 30 Dias)",
        xaxis_title="Data",
        yaxis_title="Preço (R$)",
        hovermode="x unified",  # Melhora a interação ao passar o mouse
        height=500,  # Altura do gráfico
    )

    # Exibir o gráfico no Streamlit
    st.plotly_chart(
        fig, use_container_width=True
    )  # use_container_width ajusta à largura da coluna

    # Lógica para o aviso de compra
    st.subheader("Análise de Valor:")
    if not pd.isna(
        ultima_sma_20
    ):  # Verifica se a SMA foi calculada (há dados suficientes)
        if ultimo_preco < ultima_sma_20:

            st.success(
                f"✅ **Alerta de Compra:** O preço atual (R\$ {ultimo_preco:.2f}) está abaixo da média Móvel de 20 dias (R\$ {ultima_sma_20:.2f}). Isso pode indicar uma oportunidade de compra, dependendo da sua estratégia!"
            )
        elif ultimo_preco > ultima_sma_20:
            st.info(
                f"💡 **Preço Acima da Média:** O preço atual (R\$    {ultimo_preco:.2f}) está ACIMA da Média Móvel de 20 dias (R\$  {ultima_sma_20:.2f}). Monitore ou considere outras análises."
            )
        else:
            st.warning(
                "Preço atual muito próximo da Média Móvel de 20 dias. Sem indicação clara."
            )
    else:

        st.warning(
            "Dados insuficientes para calcular a Média Móvel de 20 dias. São necessários pelo menos 20 dias de dados."
        )

    st.subheader("🔔 Receber Alerta por E-mail")
    recipient_email = st.text_input(
        "Seu e-mail para receber o alerta:", "email@email.com"
    )

    if st.button("Enviar Alerta por E-mail"):
        if not recipient_email or "@" not in recipient_email:
            st.error(
                "Por favor, insira um endereço de e-mail válido para o destinatário."
            )
        else:
            subject = f"Alerta de Ação: {ticker_atual} - Indicação de Compra!"
            if ultimo_preco < ultima_sma_20:
                msg = "✅ Preço baixo da média dos últimos 20 dias"
            elif ultimo_preco > ultima_sma_20:
                msg = "❌ Preço acima da média dos últimos 20 dias"
            else:
                msg = "⚠️ Preço estável nos últimos 20 dias"
            html_body = f"""

<p>Olá!</p>
<p>Aqui está um resumo rápido sobre a  {ticker_atual}</p>
<p>R$ {ultimo_preco:.2f}<br>
Média Móvel (20 dias): {ultima_sma_20:.2f}
</p>
<p>{msg} </p>
</html>
            """
            with st.spinner(
                "Enviando e-mail..."
            ):  # Exibe um spinner enquanto o e-mail é enviado
                if send_email_alert(recipient_email, subject, html_body):
                    st.success(
                        f"E-mail de alerta enviado com sucesso para {recipient_email}!"
                    )
                else:
                    st.error(
                        f"Falha ao enviar o e-mail de alerta para {recipient_email}. Verifique as configurações de e-mail e a senha de aplicativo."
                    )
