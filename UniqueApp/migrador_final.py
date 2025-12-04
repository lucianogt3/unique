import os
import sqlite3
from app import app, db

def migrate_database():
    """Migra o banco de dados para a nova estrutura"""
    print("🚀 INICIANDO MIGRAÇÃO DO BANCO DE DADOS...")
    
    with app.app_context():
        try:
            # Conectar diretamente ao SQLite
            db_path = os.path.join(os.path.dirname(__file__), 'data', 'auditoria.db')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 1. Verificar se as colunas já existem
            cursor.execute("PRAGMA table_info(erro)")
            columns = [col[1] for col in cursor.fetchall()]
            
            # 2. Adicionar colunas se não existirem
            if 'responsavel_id' not in columns:
                print("📝 Adicionando coluna responsavel_id...")
                cursor.execute("ALTER TABLE erro ADD COLUMN responsavel_id INTEGER")
            
            if 'categoria_erro_id' not in columns:
                print("📝 Adicionando coluna categoria_erro_id...")
                cursor.execute("ALTER TABLE erro ADD COLUMN categoria_erro_id INTEGER")
            
            # 3. Verificar se a tabela categoria_erro existe
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='categoria_erro'")
            if not cursor.fetchone():
                print("📝 Criando tabela categoria_erro...")
                cursor.execute("""
                    CREATE TABLE categoria_erro (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        codigo VARCHAR(20) UNIQUE NOT NULL,
                        nome VARCHAR(100) NOT NULL,
                        descricao TEXT,
                        cor VARCHAR(7) DEFAULT '#3498db',
                        status VARCHAR(20) DEFAULT 'ativo',
                        data_criacao DATETIME DEFAULT CURRENT_TIMESTAMP,
                        data_atualizacao DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            
            # 4. Verificar se a tabela de relacionamento existe
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='responsavel_categoria_association'")
            if not cursor.fetchone():
                print("📝 Criando tabela responsavel_categoria_association...")
                cursor.execute("""
                    CREATE TABLE responsavel_categoria_association (
                        responsavel_id INTEGER NOT NULL,
                        categoria_erro_id INTEGER NOT NULL,
                        data_inicio DATETIME DEFAULT CURRENT_TIMESTAMP,
                        data_fim DATETIME NULL,
                        PRIMARY KEY (responsavel_id, categoria_erro_id),
                        FOREIGN KEY (responsavel_id) REFERENCES responsavel(id),
                        FOREIGN KEY (categoria_erro_id) REFERENCES categoria_erro(id)
                    )
                """)
            
            # 5. Popular categorias padrão
            cursor.execute("SELECT COUNT(*) FROM categoria_erro")
            if cursor.fetchone()[0] == 0:
                print("📝 Populando categorias padrão...")
                categorias = [
                    ('FAT001', 'ERRO FATURAMENTO', 'Erros relacionados ao faturamento de contas', '#e74c3c'),
                    ('ENF001', 'ERRO ENFERMAGEM', 'Erros relacionados à enfermagem', '#3498db'),
                    ('MED001', 'ERRO MÉDICO', 'Erros relacionados à parte médica', '#2ecc71'),
                    ('REC001', 'ERRO RECEPÇÃO', 'Erros relacionados à recepção', '#f39c12'),
                    ('FIS001', 'ERRO FISIOTERAPIA', 'Erros relacionados à fisioterapia', '#9b59b6')
                ]
                
                for codigo, nome, descricao, cor in categorias:
                    cursor.execute(
                        "INSERT INTO categoria_erro (codigo, nome, descricao, cor) VALUES (?, ?, ?, ?)",
                        (codigo, nome, descricao, cor)
                    )
            
            # 6. Criar relacionamentos padrão
            print("📝 Criando relacionamentos padrão...")
            
            # Buscar IDs dos responsáveis
            cursor.execute("SELECT id, nome FROM responsavel")
            responsaveis = {nome: id for id, nome in cursor.fetchall()}
            
            # Buscar IDs das categorias
            cursor.execute("SELECT id, codigo FROM categoria_erro")
            categorias = {codigo: id for id, codigo in cursor.fetchall()}
            
            # Relacionamentos
            relacionamentos = [
                ('BRUNO TAVARES', 'FAT001'),
                ('KATIA ALVES', 'FAT001'),
                ('SABRYNA GABRIELLA', 'ENF001'),
                ('LEDISMAR', 'MED001'),
                ('ANDRE PASSAGLIA', 'MED001'),
                ('WARLEY', 'REC001'),
                ('DHIOGO BENTO / BEATRIZ C', 'FIS001')
            ]
            
            for resp_nome, cat_codigo in relacionamentos:
                if resp_nome in responsaveis and cat_codigo in categorias:
                    cursor.execute(
                        "INSERT OR IGNORE INTO responsavel_categoria_association (responsavel_id, categoria_erro_id) VALUES (?, ?)",
                        (responsaveis[resp_nome], categorias[cat_codigo])
                    )
            
            conn.commit()
            print("✅ MIGRAÇÃO CONCLUÍDA COM SUCESSO!")
            
        except Exception as e:
            print(f"❌ ERRO NA MIGRAÇÃO: {e}")
            conn.rollback()
        finally:
            conn.close()

if __name__ == '__main__':
    migrate_database()