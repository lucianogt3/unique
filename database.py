import sqlite3
import os
from datetime import datetime

DATABASE_PATH = 'data/auditoria.db'

def get_db_connection():
    """Cria uma conexão com o banco de dados"""
    os.makedirs('data', exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_database():
    """Inicializa o banco de dados com as tabelas necessárias"""
    conn = get_db_connection()
    
    # Tabela de convênios
    conn.execute('''
        CREATE TABLE IF NOT EXISTS convenios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            status TEXT DEFAULT 'ativo',
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela de setores
    conn.execute('''
        CREATE TABLE IF NOT EXISTS setores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            descricao TEXT,
            status TEXT DEFAULT 'ativo',
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela de responsáveis
    conn.execute('''
        CREATE TABLE IF NOT EXISTS responsaveis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE,
            funcao TEXT NOT NULL,
            setor TEXT,
            status TEXT DEFAULT 'ativo',
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela de tipos de erro - VERSÃO CORRIGIDA
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tipos_erro (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo TEXT NOT NULL UNIQUE,
            nome TEXT NOT NULL,
            descricao TEXT,
            cor TEXT DEFAULT '#dc3545',
            status TEXT DEFAULT 'ativo',
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela de causas
    conn.execute('''
        CREATE TABLE IF NOT EXISTS causas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT NOT NULL,
            tipo_erro_id INTEGER NOT NULL,
            status TEXT DEFAULT 'ativo',
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (tipo_erro_id) REFERENCES tipos_erro (id)
        )
    ''')
    
    # Tabela de prontuários
    conn.execute('''
        CREATE TABLE IF NOT EXISTS prontuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            beneficiario TEXT NOT NULL,
            convenio TEXT NOT NULL,
            setor TEXT NOT NULL,
            atendimento TEXT NOT NULL,
            admissao TEXT,
            alta TEXT,
            status TEXT DEFAULT 'Aguardando Auditoria',
            responsavel TEXT,
            data_erro TEXT,
            recebimento_prontuario TEXT,
            inicio_auditoria TEXT,
            enviado_faturamento TEXT,
            prazo TEXT,
            diarias INTEGER DEFAULT 0,
            fim_auditoria TEXT,
            observacao TEXT,
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Tabela de erros dos prontuários
    conn.execute('''
        CREATE TABLE IF NOT EXISTS prontuarios_erros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prontuario_id INTEGER NOT NULL,
            tipo_erro TEXT NOT NULL,
            causa TEXT NOT NULL,
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (prontuario_id) REFERENCES prontuarios (id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()

def atualizar_estrutura_tabelas():
    """Atualiza a estrutura das tabelas se necessário"""
    conn = get_db_connection()
    
    try:
        # Verificar se a coluna 'codigo' existe na tabela tipos_erro
        conn.execute("SELECT codigo FROM tipos_erro LIMIT 1")
    except sqlite3.OperationalError:
        # A coluna não existe, precisamos recriar a tabela
        print("Atualizando estrutura da tabela tipos_erro...")
        
        # Fazer backup dos dados existentes
        tipos_existentes = conn.execute("SELECT * FROM tipos_erro").fetchall()
        
        # Recriar a tabela com a nova estrutura
        conn.execute("DROP TABLE IF EXISTS tipos_erro_backup")
        conn.execute("ALTER TABLE tipos_erro RENAME TO tipos_erro_backup")
        
        # Criar nova tabela
        conn.execute('''
            CREATE TABLE tipos_erro (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT NOT NULL UNIQUE,
                nome TEXT NOT NULL,
                descricao TEXT,
                cor TEXT DEFAULT '#dc3545',
                status TEXT DEFAULT 'ativo',
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                data_atualizacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Restaurar dados se existirem
        if tipos_existentes:
            for tipo in tipos_existentes:
                tipo_dict = dict(tipo)
                codigo = tipo_dict['nome'].lower().replace(' ', '_').replace('ã', 'a').replace('ç', 'c')
                conn.execute('''
                    INSERT INTO tipos_erro (id, codigo, nome, descricao, cor, status, data_criacao, data_atualizacao)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    tipo_dict['id'], codigo, tipo_dict['nome'], 
                    tipo_dict.get('descricao', ''), tipo_dict.get('cor', '#dc3545'),
                    tipo_dict.get('status', 'ativo'), tipo_dict.get('data_criacao'), 
                    tipo_dict.get('data_atualizacao')
                ))
        
        conn.execute("DROP TABLE IF EXISTS tipos_erro_backup")
    
    conn.commit()
    conn.close()

def popular_dados_iniciais():
    """Popula o banco com dados iniciais"""
    conn = get_db_connection()
    
    # Primeiro, garantir que a estrutura está atualizada
    atualizar_estrutura_tabelas()
    
    # Tipos de erro padrão
    tipos_erro = [
        ('documentacao', 'Documentação', 'Erros relacionados a documentação', '#dc3545'),
        ('registro', 'Registro', 'Erros relacionados a registros', '#fd7e14'),
        ('procedimento', 'Procedimento', 'Erros relacionados a procedimentos', '#ffc107'),
        ('codificacao', 'Codificação', 'Erros relacionados a codificação', '#20c997'),
        ('faturamento', 'Faturamento', 'Erros relacionados a faturamento', '#0dcaf0'),
        ('prazo', 'Prazo', 'Erros relacionados a prazos', '#6f42c1')
    ]
    
    for codigo, nome, descricao, cor in tipos_erro:
        conn.execute('''
            INSERT OR IGNORE INTO tipos_erro (codigo, nome, descricao, cor) 
            VALUES (?, ?, ?, ?)
        ''', (codigo, nome, descricao, cor))
    
    # Obter IDs dos tipos de erro inseridos
    tipos_erro_ids = {}
    for codigo, nome, _, _ in tipos_erro:
        result = conn.execute('SELECT id FROM tipos_erro WHERE codigo = ?', (codigo,)).fetchone()
        if result:
            tipos_erro_ids[codigo] = result['id']
    
    # Convênios padrão
    convenios = [
        "Unimed", "SulAmérica", "Bradesco Saúde", "Amil", "NotreDame Intermédica",
        "Prevent Senior", "São Cristóvão", "Santa Casa", "Outros"
    ]
    
    for convenio in convenios:
        conn.execute('INSERT OR IGNORE INTO convenios (nome) VALUES (?)', (convenio,))
    
    # Setores padrão
    setores = [
        ("UTI", "Unidade de Terapia Intensiva"),
        ("Internação", "Setor de Internação"),
        ("Pronto Socorro", "Pronto Socorro"),
        ("Centro Cirúrgico", "Centro Cirúrgico"),
        ("Ambulatório", "Ambulatório"),
        ("Emergência", "Emergência"),
        ("Hospital Dia", "Hospital Dia")
    ]
    
    for nome, descricao in setores:
        conn.execute('INSERT OR IGNORE INTO setores (nome, descricao) VALUES (?, ?)', 
                    (nome, descricao))
    
    # Responsáveis padrão
    responsaveis = [
        ("Auditor 1", "Auditor", "Auditoria"),
        ("Auditor 2", "Auditor", "Auditoria"),
        ("Auditor 3", "Auditor", "Auditoria"),
        ("Enfermeiro A", "Enfermeiro", "Enfermagem"),
        ("Enfermeiro B", "Enfermeiro", "Enfermagem"),
        ("Médico A", "Médico", "Médico"),
        ("Médico B", "Médico", "Médico"),
        ("Coordenador", "Coordenador", "Coordenação")
    ]
    
    for nome, funcao, setor in responsaveis:
        conn.execute('INSERT OR IGNORE INTO responsaveis (nome, funcao, setor) VALUES (?, ?, ?)', 
                    (nome, funcao, setor))
    
    # Causas padrão
    causas = [
        ("Falta carimbo e assinatura em evolução", "documentacao"),
        ("Falta evolução diária impressa", "documentacao"),
        ("Carimbo em evolução incorreto", "documentacao"),
        ("Data/horário incorreto na evolução", "registro"),
        ("Data de admissão incorreta", "registro"),
        ("Horário de alta incorreto", "registro"),
        ("Falta evolução de curativo", "procedimento"),
        ("Cirurgia cadastrada incorretamente", "procedimento"),
        ("CID incorreto", "codificacao"),
        ("TUSS inadequado", "codificacao"),
        ("Cobrança indevida de procedimento", "faturamento"),
        ("Valor incorreto na guia", "faturamento"),
        ("Atraso no envio para faturamento", "prazo"),
        ("Prazo de entrega", "prazo")
    ]
    
    for descricao, tipo_codigo in causas:
        tipo_id = tipos_erro_ids.get(tipo_codigo)
        if tipo_id:
            conn.execute('INSERT OR IGNORE INTO causas (descricao, tipo_erro_id) VALUES (?, ?)', 
                        (descricao, tipo_id))
    
    conn.commit()
    conn.close()
    print("✅ Banco de dados inicializado com sucesso!")

# Inicializar banco ao importar
init_database()
popular_dados_iniciais()