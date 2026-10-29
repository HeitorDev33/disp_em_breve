import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
import json

# Define as permissões do Google (o scope)
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

# Lê a chave diretamente do cofre invisível do Streamlit
credenciais_dict = json.loads(st.secrets["google_credentials"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(credenciais_dict, scope)

st.set_page_config(page_title="Disponível Em Breve", page_icon="🏡", layout="wide")

# --- 1. SISTEMA DE LOGIN (PROTEÇÃO DA REDE INTERNA) ---
SENHA_EMPRESA = "159753" # Mude aqui a senha da sua empresa

if "logado" not in st.session_state:
    st.session_state.logado = False

if not st.session_state.logado:
    st.title("🔒 Acesso Restrito")
    senha_digitada = st.text_input("Digite a senha", type="password")
    if st.button("Entrar"):
        if senha_digitada == SENHA_EMPRESA:
            st.session_state.logado = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
else:
    # --- 2. CONEXÃO COM GOOGLE SHEETS ---
    @st.cache_resource
    def conectar_planilha():
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("disponivel-em-breve-e6b0fdf0f9b7.json", scope)
        client = gspread.authorize(creds)
        sheet = client.open("disponivel_em_breve").worksheet("disponivel_em_breve")
        return sheet

    planilha = conectar_planilha()

    # --- 3. INTERFACE DO SISTEMA ---
    st.title("🏡 Imóveis: Disponível Em Breve")

    aba_cadastro, aba_busca, aba_gerenciar = st.tabs(["➕ Cadastro Imóvel", "🔍 Buscar e Filtrar", "⚙️ Excluir Imóvel"])

    # ABA CADASTRO
    with aba_cadastro:
        st.subheader("Adicionar novo imóvel")
        with st.form("form_imovel", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                corretor = st.text_input("Nome do Corretor")
                codigo = st.text_input("Código do Imóvel")
            with col2:
                status = st.selectbox("Status", ["Em anúncio", "Pausado"])
                data_disp = st.date_input("Data de Disponibilidade", format="DD/MM/YYYY")
            
            submit = st.form_submit_button("Salvar Imóvel")
            
            if submit:
                if corretor and codigo:
                    data_str = data_disp.strftime("%d/%m/%Y")
                    # Envia para a planilha com "NAO" por padrão (o site recalcula depois)
                    nova_linha = [corretor, codigo, status, data_str, "NAO"]
                    planilha.append_row(nova_linha)
                    
                    mensagem = st.success(f"✅ Imóvel {codigo} incluído com sucesso!")
                    time.sleep(2)
                    mensagem.empty()
                    st.rerun()
                else:
                    st.error("Preencha o nome do corretor e o código do imóvel.")

    # ABA BUSCA (COM CÁLCULO DE VENCIMENTO AUTOMÁTICO)
    with aba_busca:
        st.subheader("Filtro de Imóveis")
        
        dados = planilha.get_all_records()
        df = pd.DataFrame(dados)
        
        if not df.empty and "Corretor" in df.columns:
            # MAGIA DA DATA: Recalcula o status "Vencido" ao vivo todos os dias
            hoje = datetime.now().date()
            def checar_vencimento(data_str):
                try:
                    data_obj = datetime.strptime(str(data_str), "%d/%m/%Y").date()
                    return "SIM" if data_obj < hoje else "NAO"
                except:
                    return "ERRO"
            
            if "Data de Disponibilidade" in df.columns:
                df["Vencido"] = df["Data de Disponibilidade"].apply(checar_vencimento)

            lista_corretores = df["Corretor"].dropna().unique().tolist()
            col_filtro, col_botao, _ = st.columns([2, 1, 3])
            
            with col_filtro:
                corretor_selecionado = st.selectbox("Filtrar por Corretor:", ["Todos"] + lista_corretores)
            with col_botao:
                st.write("")
                st.write("")
                botao_filtrar = st.button("Aplicar Filtro")
            
            if botao_filtrar or corretor_selecionado == "Todos":
                df_filtrado = df if corretor_selecionado == "Todos" else df[df["Corretor"] == corretor_selecionado]
                
                def colorir_vencidos(val):
                    cor = 'red' if str(val).upper() == 'SIM' else 'green'
                    return f'color: {cor}; font-weight: bold'
                
                if 'Vencido' in df_filtrado.columns:
                    st.dataframe(df_filtrado.style.map(colorir_vencidos, subset=['Vencido']), use_container_width=True, hide_index=True)
                    imoveis_vencidos = df_filtrado[df_filtrado["Vencido"] == "SIM"]
                    if not imoveis_vencidos.empty:
                        qtd = len(imoveis_vencidos)
                        texto_imovel = "imóvel" if qtd == 1 else "imóveis"
                        st.warning(f"⚠️ Atenção: {qtd} {texto_imovel} com a data vencida!")
                else:
                    st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum imóvel cadastrado ainda ou colunas incorretas.")

    # ABA EXCLUIR
    with aba_gerenciar:
        st.subheader("Excluir Imóvel do Sistema")
        codigo_excluir = st.text_input("Digite o Código do Imóvel para excluir (ex: AP3773)")
        
        if st.button("Excluir Definitivamente", type="primary"):
            if codigo_excluir:
                try:
                    celula = planilha.find(codigo_excluir)
                    if celula:
                        planilha.delete_rows(celula.row)
                        msg_sucesso = st.success(f"🗑️ O imóvel {codigo_excluir} foi removido com sucesso!")
                        time.sleep(2)
                        msg_sucesso.empty()
                        st.rerun()
                    else:
                        st.error(f"❌ O código {codigo_excluir} não foi encontrado.")
                except Exception:
                    st.error(f"❌ O código {codigo_excluir} não foi encontrado na folha de cálculo.")
            else:
                st.warning("Por favor, digite um código antes de clicar no botão.")
