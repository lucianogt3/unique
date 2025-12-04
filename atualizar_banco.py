from app import app, db
# O Flask é inteligente: o create_all só cria o que está faltando.
# Ele vai ignorar as tabelas que já existem e criar apenas a tabela de usuário.

print("Iniciando atualização do banco de dados...")

with app.app_context():
    db.create_all()
    print("Sucesso! As tabelas novas foram criadas.")
    print("Seus dados antigos continuam lá.")