import pandas as pd
import sqlite3
from datetime import datetime
import os

# ==============================================================================
# CONFIGURAÇÕES DE CAMINHOS (Ajuste se necessário)
# ==============================================================================
ARQUIVO_EXCEL = r"C:\Users\LUCIANO\Desktop\Auditoria unique jeiza.xlsx"
CAMINHO_BD = r"C:\Users\LUCIANO\Desktop\auditoria_hospitalar\data\auditoria.db"
NOME_PLANILHA = 'OUTUBRO 2025 HU'

def corrigir_estrutura_banco(conn):
    """
    Verifica e corrige a estrutura do banco de dados automaticamente
    antes de tentar inserir dados.
    """
    cursor = conn.cursor()
    print("🔧 Verificando estrutura do banco de dados...")

    # 1. Criar tabela categoria_erro se não existir
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS categoria_erro (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        codigo VARCHAR(20) UNIQUE NOT NULL,
        nome VARCHAR(100) NOT NULL,
        descricao VARCHAR(200),
        cor VARCHAR(7),
        status VARCHAR(20) DEFAULT 'ativo',
        data_criacao DATETIME,
        data_atualizacao DATETIME
    )
    ''')

    # 2. Criar tabela de associação se não existir
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS responsavel_categoria_association (
        responsavel_id INTEGER NOT NULL,
        categoria_erro_id INTEGER NOT NULL,
        data_inicio DATETIME,
        data_fim DATETIME,
        PRIMARY KEY (responsavel_id, categoria_erro_id),
        FOREIGN KEY(responsavel_id) REFERENCES responsavel (id),
        FOREIGN KEY(categoria_erro_id) REFERENCES categoria_erro (id)
    )
    ''')

    # 3. Verificar e Adicionar colunas na tabela ERRO
    cursor.execute("PRAGMA table_info(erro)")
    colunas_existentes = [col[1] for col in cursor.fetchall()]

    if 'responsavel_id' not in colunas_existentes:
        print("⚠️ Coluna 'responsavel_id' faltando. Adicionando...")
        try:
            cursor.execute("ALTER TABLE erro ADD COLUMN responsavel_id INTEGER REFERENCES responsavel(id)")
            print("✅ Coluna 'responsavel_id' adicionada.")
        except Exception as e:
            print(f"❌ Erro ao adicionar responsavel_id: {e}")

    if 'categoria_erro_id' not in colunas_existentes:
        print("⚠️ Coluna 'categoria_erro_id' faltando. Adicionando...")
        try:
            cursor.execute("ALTER TABLE erro ADD COLUMN categoria_erro_id INTEGER REFERENCES categoria_erro(id)")
            print("✅ Coluna 'categoria_erro_id' adicionada.")
        except Exception as e:
            print(f"❌ Erro ao adicionar categoria_erro_id: {e}")

    conn.commit()
    print("🏁 Estrutura do banco verificada e pronta!")

def popular_dados_excel_no_bd_estruturado():
    """
    Popula os dados do Excel com a estrutura correta
    """
    
    # 1. Ler o arquivo Excel
    if not os.path.exists(ARQUIVO_EXCEL):
        print(f"❌ Arquivo Excel não encontrado: {ARQUIVO_EXCEL}")
        return

    try:
        print(f"📂 Lendo arquivo Excel: {ARQUIVO_EXCEL}...")
        df = pd.read_excel(ARQUIVO_EXCEL, sheet_name=NOME_PLANILHA)
        print(f"✅ Excel lido com sucesso. {len(df)} registros encontrados.")
    except Exception as e:
        print(f"❌ Erro ao ler arquivo Excel: {e}")
        return
    
    # 2. Conectar ao banco de dados
    try:
        conn = sqlite3.connect(CAMINHO_BD)
        cursor = conn.cursor()
        print("✅ Conexão com BD estabelecida.")
        
        # 🔥 CHAMA A CORREÇÃO DE ESTRUTURA AQUI
        corrigir_estrutura_banco(conn)
        
    except Exception as e:
        print(f"❌ Erro ao conectar com BD: {e}")
        return
    
    # Mapeamentos (Mantidos do seu código original)
    mapeamento_causas_tipos = {
        'COBRANÇA INDEVIDA': 'ERRO FATURAMENTO',
        'DIARIA NÃO COBRADA': 'ERRO FATURAMENTO',
        'DIARIA SEM AUTORIZAÇÃO': 'ERRO FATURAMENTO',
        'EXAME NÃO COBRADO / NÃO AUTORIZADO': 'ERRO FATURAMENTO',
        'FALTA COBRAR ANESTESIA': 'ERRO FATURAMENTO',
        'FALTA COBRAR ANESTESISTA': 'ERRO FATURAMENTO',
        'FALTA COBRAR AUXILIAR CC': 'ERRO FATURAMENTO',
        'FALTA COBRAR OXIGENIO': 'ERRO FATURAMENTO',
        'OXIGENIOTERAPIA SEM COBRAR': 'ERRO FATURAMENTO',
        'FALTA COBRAR PRESCRIÇÃO / BOLETIM CIRURGICO': 'ERRO FATURAMENTO',
        'FALTA COBRAR PROCEDIMENTO': 'ERRO FATURAMENTO',
        'FALTA COBRAR VISITA INFECTO': 'ERRO FATURAMENTO',
        'COBRAR VISITA INFECTO': 'ERRO FATURAMENTO',
        'FALTA COBRAR VISITA MÉDICA': 'ERRO FATURAMENTO',
        'MATERIAL NÃO AUTORIZADO': 'ERRO FATURAMENTO',
        'MATERIAL SEM AUTORIZAÇÃO': 'ERRO FATURAMENTO',
        'MATERIAL NÃO COBRADO': 'ERRO FATURAMENTO',
        'MEDICAÇÃO NÃO COBRADA': 'ERRO FATURAMENTO',
        'NÃO COBRADO FISIOTERAPIA': 'ERRO FATURAMENTO',
        'NÃO COBRADO HONORÁRIOS DE 1º AUXILIAR CC': 'ERRO FATURAMENTO',
        'NÃO COBRADO TX ALIMENTAÇÃO': 'ERRO FATURAMENTO',
        'TX ALIMENTAÇÃO': 'ERRO FATURAMENTO',
        'NÃO COBRADO TX APARELHO ENDOSCOPIA RESP': 'ERRO FATURAMENTO',
        'NÃO COBRADO TX APARELHO UROLOGIA': 'ERRO FATURAMENTO',
        'NÃO COBRADO TX AUDITORIA INTRA': 'ERRO FATURAMENTO',
        'NÃO COBRADO TX INTENCIFICADOR DE IMAGEM': 'ERRO FATURAMENTO',
        'TX INTENCIFICADOR DE IMAGEM': 'ERRO FATURAMENTO',
        'NÃO COBRADO TX LASER': 'ERRO FATURAMENTO',
        'PROCEDIMENTO SEM COBRAR': 'ERRO FATURAMENTO',
        'REIMPRESSÃO DO ESPELHO': 'ERRO FATURAMENTO',
        'FALTA IMPRESSÃO RELATORIO DE ENFERMAGEM': 'ERRO ENFERMAGEM',
        'FALTA RELATORIOS DE ENFERMAGEM': 'ERRO ENFERMAGEM',
        'FALTA JUSTIFICATIVA EQUIPO BIC': 'ERRO ENFERMAGEM',
        'SEM RELATAR AVP E EQUIPO BIC': 'ERRO ENFERMAGEM',
        'FALTA PRESCRIÇÃO DE CURATIVO': 'ERRO ENFERMAGEM',
        'FALTA RELATORIO DE CURATIVO': 'ERRO ENFERMAGEM',
        'FALTA RELATORIO DE ENFERMAGEM': 'ERRO ENFERMAGEM',
        'FALTA RELATORIO DE AVP': 'ERRO ENFERMAGEM',
        'FALTA IMPRESSÃO EVOLUÇÃO MEDICA': 'ERRO MÉDICO',
        'FALTA EVOLUÇÃO ANESTESISTA': 'ERRO MÉDICO',
        'ALTA DADA ERRADA': 'ERRO MÉDICO',
        'DIARIAS NÃO AUTORIZADAS': 'ERRO RECEPÇÃO',
        'FALTA AUTORIZAÇÃO DE DIARIAS': 'ERRO RECEPÇÃO',
        'EXAME NÃO AUTORIZADO': 'ERRO RECEPÇÃO',
        'EXAME RADIOSCOPIA SEM AUTORIZAÇÃO': 'ERRO RECEPÇÃO',
        'FALTA AUTORIZAÇÃO DE EXAME': 'ERRO RECEPÇÃO',
        'GUIA SEM ASSINATURA': 'ERRO RECEPÇÃO',
        'FALTA AUTORIZAÇÃO MATERIAL': 'ERRO RECEPÇÃO',
        'SEM AUTORIZAÇÃO DE ATB NA CONTA': 'ERRO RECEPÇÃO',
        'FALTA CARIMBO FISIOTERAPIA': 'ERRO ENFERMAGEM'
    }
    
    mapeamento_responsaveis_categorias = {
        'Bruno Tavares': 'ERRO FATURAMENTO',
        'KATIA ALVES': 'ERRO FATURAMENTO',
        'Sabryna Gabriella': 'ERRO ENFERMAGEM',
        'Dr Ledismar': 'ERRO MÉDICO',
        'DR LEONARDO FERREIRA': 'ERRO MÉDICO',
        'DR JUNICHIRO': 'ERRO MÉDICO',
        'DR ANDRE PASSAGLIA': 'ERRO MÉDICO',
        'Warley': 'ERRO RECEPÇÃO',
        'DHIOGO / BEATRIZ C': 'ERRO ENFERMAGEM'
    }
    
    # Inicializar contadores e auxiliares
    prontuarios_inseridos = 0
    erros_inseridos = 0
    atendimentos_processados = set()
    data_atual = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Garantir Tipos de Erro
    tipos_erro_necessarios = ['ERRO FATURAMENTO', 'ERRO ENFERMAGEM', 'ERRO MÉDICO', 'ERRO RECEPÇÃO']
    for tipo_erro in tipos_erro_necessarios:
        cursor.execute('INSERT OR IGNORE INTO tipo_erro (nome, descricao, status, data_criacao, data_atualizacao) VALUES (?, ?, ?, ?, ?)', 
                       (tipo_erro, tipo_erro.replace("ERRO ", ""), 'ativo', data_atual, data_atual))

    print("🔄 Iniciando processamento das linhas...")

    # Loop principal
    for index, row in df.iterrows():
        try:
            # Dados do Prontuário
            beneficiario = str(row['Beneficiario']).strip()
            convenio_nome = str(row['Convênio']).strip()
            setor_nome = str(row['Setor']).strip()
            atendimento = str(row['Atendimento']).strip()
            observacoes = str(row.get('Observações', ''))
            
            # Ignora linhas inválidas
            if atendimento in atendimentos_processados or atendimento.lower() == 'nan':
                continue
                
            atendimentos_processados.add(atendimento)
            
            # Função auxiliar de data
            def parse_date(val):
                if pd.isna(val) or val == '' or str(val).lower() == 'nat':
                    return data_atual.split()[0] # Retorna string YYYY-MM-DD
                try:
                    return pd.to_datetime(val).strftime('%Y-%m-%d')
                except:
                    return data_atual.split()[0]

            admissao = parse_date(row['Admissão'])
            alta = parse_date(row['Alta'])
            recebimento = parse_date(row['Recebimento do Prontuário'])
            envio = parse_date(row['Envio para Correção'])
            
            # Cálculo de Diárias
            diarias = 1
            try:
                d1 = datetime.strptime(admissao, '%Y-%m-%d')
                d2 = datetime.strptime(alta, '%Y-%m-%d')
                diarias = max(1, (d2 - d1).days)
            except:
                pass

            # Inserir Prontuário
            cursor.execute('''
                INSERT OR IGNORE INTO prontuario 
                (beneficiario, convenio, setor, atendimento, admissao, alta, 
                 recebimento_prontuario, data_conta, enviado_faturamento, diarias, 
                 fim_auditoria, observacao, status, data_criacao, data_atualizacao)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (beneficiario, convenio_nome, setor_nome, atendimento, admissao, alta,
                  recebimento, admissao, envio, diarias,
                  envio, observacoes, 'Entregue ao Faturamento', data_atual, data_atual))
            
            if cursor.rowcount > 0:
                prontuarios_inseridos += 1

            # Pegar ID do Prontuário (Existente ou Novo)
            cursor.execute('SELECT id FROM prontuario WHERE atendimento = ?', (atendimento,))
            prontuario_id = cursor.fetchone()[0]
            
            # Processar Erros deste atendimento
            erros_do_atendimento = df[df['Atendimento'] == row['Atendimento']]
            
            for _, erro_row in erros_do_atendimento.iterrows():
                causa_desc = str(erro_row['Causa']).strip()
                responsavel_nome = str(erro_row['Responsavel']).strip()
                
                if causa_desc.lower() == 'nan': continue

                # Determinar Tipo Macro
                tipo_erro_nome = mapeamento_causas_tipos.get(causa_desc, 'ERRO FATURAMENTO')
                
                # Pegar ID do Tipo
                cursor.execute('SELECT id FROM tipo_erro WHERE nome = ?', (tipo_erro_nome,))
                tipo_res = cursor.fetchone()
                tipo_erro_id = tipo_res[0] if tipo_res else 1 # Fallback
                
                # Gerenciar Responsável
                cursor.execute('SELECT id FROM responsavel WHERE nome = ?', (responsavel_nome,))
                resp_res = cursor.fetchone()
                
                if resp_res:
                    responsavel_id = resp_res[0]
                else:
                    cat_resp = mapeamento_responsaveis_categorias.get(responsavel_nome, 'ERRO FATURAMENTO')
                    cursor.execute('''
                        INSERT INTO responsavel (nome, funcao, status, data_criacao, data_atualizacao)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (responsavel_nome, cat_resp, 'ativo', data_atual, data_atual))
                    responsavel_id = cursor.lastrowid
                
                # Vincular Responsável ao Prontuário
                cursor.execute('''
                    INSERT OR IGNORE INTO prontuario_responsavel_association (prontuario_id, responsavel_id)
                    VALUES (?, ?)
                ''', (prontuario_id, responsavel_id))
                
                # Inserir o Erro (Agora com as colunas garantidas)
                cursor.execute('''
                    INSERT INTO erro 
                    (prontuario_id, responsavel_id, tipo, causa, data_criacao, categoria_erro_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (prontuario_id, responsavel_id, tipo_erro_nome, causa_desc, data_atual, tipo_erro_id))
                
                erros_inseridos += 1

            if prontuarios_inseridos % 50 == 0:
                print(f"⏳ Processados: {prontuarios_inseridos} prontuários...")
                conn.commit()

        except Exception as e:
            print(f"⚠️ Erro na linha {index}: {e}")
            continue

    conn.commit()
    conn.close()
    
    print("\n" + "="*40)
    print("📊 RELATÓRIO FINAL")
    print("="*40)
    print(f"✅ Prontuários Processados: {prontuarios_inseridos}")
    print(f"✅ Erros Inseridos: {erros_inseridos}")
    print("="*40)

if __name__ == "__main__":
    print("🚀 Iniciando migração completa e segura...")
    popular_dados_excel_no_bd_estruturado()
    input("\nPressione Enter para sair...")