from app import app, db, Usuario
from werkzeug.security import generate_password_hash

print("--- Iniciando criação de usuário ---")

with app.app_context():
    # Verifica se o admin já existe para não dar erro
    usuario_existente = Usuario.query.filter_by(username='admin').first()
    
    if not usuario_existente:
        print("Criando usuário admin...")
        # Cria a senha criptografada
        senha_criptografada = generate_password_hash('admin123')
        
        # Cria o usuário
        admin = Usuario(username='admin', nome='Administrador', password_hash=senha_criptografada)
        
        db.session.add(admin)
        db.session.commit()
        print("✅ SUCESSO! Usuário criado.")
        print("Login: admin")
        print("Senha: admin123")
    else:
        print("⚠️ O usuário 'admin' JÁ EXISTE no banco de dados.")
        # Se quiser resetar a senha, descomente as linhas abaixo:
        # usuario_existente.password_hash = generate_password_hash('admin123')
        # db.session.commit()
        # print("Senha do admin resetada para 'admin123'.")

print("--- Fim ---")