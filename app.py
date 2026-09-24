import os
import json
from flask import (
    Flask, render_template, request, jsonify, redirect, url_for,
    Response, g, has_request_context
)
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
from collections import Counter, defaultdict
import traceback
import csv
import io
import re
from sqlalchemy import extract, func, or_, text
from calendar import monthrange, month_name
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# --- 1. CONFIGURAÇÃO INICIAL E BANCO DE DADOS ---
app = Flask(__name__)

# --- CONFIGURAÇÃO DE SEGURANÇA ---
app.config['SECRET_KEY'] = 'coloque-uma-chave-secreta-bem-dificil-aqui'  # Necessário para sessões

# --- INICIALIZAÇÃO DO LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Nome da função da rota de login
login_manager.login_message = "Por favor, faça login para acessar esta página."
login_manager.login_message_category = "warning"

@app.context_processor
def inject_current_year():
    return {'current_year': datetime.now().year}

basedir = os.path.abspath(os.path.dirname(__file__))
data_dir = os.path.join(basedir, 'data')
os.makedirs(data_dir, exist_ok=True)
db_path = os.path.join(data_dir, 'auditoria.db')

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

STATUS_OPCOES = [
    "Aguardando Auditoria",
    "Em Auditoria", 
    "Aguardando Correção",
    "Aguardando Revisão",
    "Entregue ao Faturamento"
]

# --- 2. DEFINIÇÃO DOS MODELOS (TABELAS) ---

# Tabelas de associação PRIMEIRO
prontuario_responsavel_association = db.Table('prontuario_responsavel_association',
    db.Column('prontuario_id', db.Integer, db.ForeignKey('prontuario.id'), primary_key=True),
    db.Column('responsavel_id', db.Integer, db.ForeignKey('responsavel.id'), primary_key=True)
)

# Tabela de relacionamento entre responsáveis e categorias de erro
responsavel_categoria_association = db.Table('responsavel_categoria_association',
    db.Column('responsavel_id', db.Integer, db.ForeignKey('responsavel.id'), primary_key=True),
    db.Column('categoria_erro_id', db.Integer, db.ForeignKey('categoria_erro.id'), primary_key=True),
    db.Column('data_inicio', db.DateTime, default=datetime.now),
    db.Column('data_fim', db.DateTime, nullable=True)
)

# Modelos base PRIMEIRO

# --- MODELO DE USUÁRIO ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(150))
    email = db.Column(db.String(150), unique=True, nullable=True)
    role = db.Column(db.String(30), nullable=False, default='admin')
    active = db.Column(db.Boolean, nullable=False, default=True)
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    data_atualizacao = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    ultimo_login = db.Column(db.DateTime)
    ultimo_ip = db.Column(db.String(64))
    login_count = db.Column(db.Integer, nullable=False, default=0)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_active(self):
        return bool(self.active)

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def nome_exibicao(self):
        return self.full_name or self.username

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'full_name': self.full_name or '',
            'email': self.email or '',
            'role': self.role or 'auditor',
            'active': bool(self.active),
            'data_criacao': self.data_criacao.isoformat() if self.data_criacao else None,
            'data_atualizacao': self.data_atualizacao.isoformat() if self.data_atualizacao else None,
            'ultimo_login': self.ultimo_login.isoformat() if self.ultimo_login else None,
            'ultimo_ip': self.ultimo_ip or '',
            'login_count': int(self.login_count or 0),
        }

class AuditLog(db.Model):
    __tablename__ = 'audit_log'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True, index=True)
    username = db.Column(db.String(100), nullable=False, default='sistema')
    action = db.Column(db.String(80), nullable=False, index=True)
    entity = db.Column(db.String(100), nullable=False, default='sistema')
    entity_id = db.Column(db.String(80))
    details = db.Column(db.Text)
    method = db.Column(db.String(10))
    path = db.Column(db.String(300))
    ip_address = db.Column(db.String(64))
    user_agent = db.Column(db.String(300))
    status = db.Column(db.String(20), nullable=False, default='sucesso')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now, index=True)
    user = db.relationship('User', backref='audit_logs')

    def to_dict(self):
        return {'id': self.id, 'user_id': self.user_id, 'username': self.username,
                'action': self.action, 'entity': self.entity,
                'entity_id': self.entity_id or '', 'details': self.details or '',
                'method': self.method or '', 'path': self.path or '',
                'ip_address': self.ip_address or '', 'user_agent': self.user_agent or '',
                'status': self.status, 'created_at': self.created_at.isoformat()}

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None

def _client_ip():
    forwarded = request.headers.get('X-Forwarded-For', '')
    return forwarded.split(',')[0].strip() if forwarded else (request.remote_addr or '')

def _validar_senha(password):
    password = str(password or '')
    if len(password) < 8: return 'A senha deve ter pelo menos 8 caracteres.'
    if not re.search(r'[A-Z]', password): return 'A senha deve possuir pelo menos uma letra maiúscula.'
    if not re.search(r'[a-z]', password): return 'A senha deve possuir pelo menos uma letra minúscula.'
    if not re.search(r'\d', password): return 'A senha deve possuir pelo menos um número.'
    return None

def registrar_log(action, entity='sistema', entity_id=None, details=None,
                  status='sucesso', user=None, commit=True):
    try:
        if user is None and has_request_context() and current_user.is_authenticated:
            user = current_user
        if isinstance(details, (dict, list, tuple)):
            details = json.dumps(details, ensure_ascii=False, default=str)
        elif details is not None:
            details = str(details)
        registro = AuditLog(
            user_id=getattr(user, 'id', None),
            username=getattr(user, 'username', None) or (request.form.get('username') if has_request_context() else None) or 'sistema',
            action=str(action or 'AÇÃO')[:80], entity=str(entity or 'sistema')[:100],
            entity_id=str(entity_id)[:80] if entity_id not in (None, '') else None,
            details=(details or '')[:4000], method=request.method if has_request_context() else None,
            path=request.path if has_request_context() else None,
            ip_address=_client_ip() if has_request_context() else None,
            user_agent=request.headers.get('User-Agent', '')[:300] if has_request_context() else None,
            status=str(status or 'sucesso')[:20])
        db.session.add(registro)
        if commit: db.session.commit()
        if has_request_context(): g.audit_registered = True
        return registro
    except Exception:
        db.session.rollback(); app.logger.exception('Falha ao registrar log de auditoria'); return None

def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not getattr(current_user, 'is_admin', False):
            if request.path.startswith('/api/'):
                return jsonify({'sucesso': False, 'erro': 'Acesso restrito ao administrador.'}), 403
            return redirect(url_for('index'))
        return view(*args, **kwargs)
    return wrapped

_schema_ready = False

def _ensure_security_schema():
    global _schema_ready
    if _schema_ready: return
    db.create_all()
    inspector = db.inspect(db.engine)
    cols = {c['name'] for c in inspector.get_columns('user')}
    additions = {'full_name':'VARCHAR(150)','email':'VARCHAR(150)',
                 'role':"VARCHAR(30) DEFAULT 'admin'",'active':'BOOLEAN DEFAULT 1',
                 'data_criacao':'DATETIME','data_atualizacao':'DATETIME',
                 'ultimo_login':'DATETIME','ultimo_ip':'VARCHAR(64)',
                 'login_count':'INTEGER DEFAULT 0'}
    for name, sql_type in additions.items():
        if name not in cols:
            db.session.execute(text(f'ALTER TABLE "user" ADD COLUMN {name} {sql_type}'))
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    db.session.execute(text("UPDATE \"user\" SET role='admin' WHERE role IS NULL OR TRIM(role)=''"))
    db.session.execute(text('UPDATE "user" SET active=1 WHERE active IS NULL'))
    db.session.execute(text('UPDATE "user" SET login_count=0 WHERE login_count IS NULL'))
    db.session.execute(text('UPDATE "user" SET data_criacao=:now WHERE data_criacao IS NULL'), {'now': now})
    db.session.execute(text('UPDATE "user" SET data_atualizacao=:now WHERE data_atualizacao IS NULL'), {'now': now})
    db.session.commit()
    inspector = db.inspect(db.engine)

    tipo_columns = {
        column['name']
        for column in inspector.get_columns('tipo_erro')
    }
    if 'codigo' not in tipo_columns:
        db.session.execute(text(
            'ALTER TABLE tipo_erro '
            'ADD COLUMN codigo VARCHAR(20)'
        ))
        db.session.commit()

    causa_columns = {
        column['name']
        for column in inspector.get_columns('causa')
    }
    if 'codigo' not in causa_columns:
        db.session.execute(text(
            'ALTER TABLE causa '
            'ADD COLUMN codigo VARCHAR(40)'
        ))
        db.session.commit()

    # Remove índices antigos antes da correção dos códigos.
    db.session.execute(text(
        'DROP INDEX IF EXISTS ux_tipo_erro_codigo'
    ))
    db.session.execute(text(
        'DROP INDEX IF EXISTS ux_causa_codigo'
    ))
    db.session.commit()

    _migrar_codigos_motivos_e_causas()

    db.session.execute(text(
        'CREATE UNIQUE INDEX IF NOT EXISTS '
        'ux_tipo_erro_codigo ON tipo_erro (codigo)'
    ))
    db.session.execute(text(
        'CREATE UNIQUE INDEX IF NOT EXISTS '
        'ux_causa_codigo ON causa (codigo)'
    ))
    db.session.commit()
    _schema_ready = True

@app.before_request
def initialize_security_schema():
    try: _ensure_security_schema()
    except Exception:
        db.session.rollback(); app.logger.exception('Falha ao preparar usuários e logs')

@app.after_request
def audit_mutating_request(response):
    try:
        if (request.method in {'POST','PUT','PATCH','DELETE'} and
            request.endpoint not in {'login','logout','api_logs','exportar_logs_csv'} and
            not getattr(g, 'audit_registered', False) and current_user.is_authenticated):
            payload = request.get_json(silent=True)
            keys = payload.keys() if isinstance(payload, dict) else request.form.keys()
            fields = sorted(k for k in keys if k.lower() not in {'password','senha','password_hash'})
            registrar_log(f'{request.method} {request.endpoint or "rota"}',
                          entity=request.endpoint or 'rota',
                          details={'campos_enviados': fields, 'codigo_http': response.status_code},
                          status='sucesso' if response.status_code < 400 else 'erro')
    except Exception: app.logger.exception('Falha no log automático')
    return response




class Convenio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='ativo')
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    data_atualizacao = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'status': self.status,
            'data_criacao': self.data_criacao.isoformat(),
            'data_atualizacao': self.data_atualizacao.isoformat()
        }

class Setor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    descricao = db.Column(db.String(200))
    status = db.Column(db.String(20), nullable=False, default='ativo')
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    data_atualizacao = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'descricao': self.descricao,
            'status': self.status,
            'data_criacao': self.data_criacao.isoformat(),
            'data_atualizacao': self.data_atualizacao.isoformat()
        }

class TipoErro(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Código visual/administrativo. Não é usado para agrupar relatórios.
    codigo = db.Column(
        db.String(20), unique=True, nullable=True, index=True
    )

    # Chave histórica usada pelos lançamentos, relatórios e dashboard.
    nome = db.Column(db.String(50), unique=True, nullable=False)
    descricao = db.Column(db.String(200))
    cor = db.Column(db.String(20), default='#dc3545')
    status = db.Column(db.String(20), nullable=False, default='ativo')
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    data_atualizacao = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    causas = db.relationship('Causa', backref='tipo_erro', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'codigo': self.codigo or '',
            'nome': self.nome,
            'descricao': self.descricao,
            'cor': self.cor,
            'status': self.status,
            'data_criacao': self.data_criacao.isoformat(),
            'data_atualizacao': self.data_atualizacao.isoformat()
        }

class Causa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(
        db.String(40), unique=True, nullable=True, index=True
    )
    descricao = db.Column(db.String(300), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='ativo')
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    data_atualizacao = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    tipo_erro_id = db.Column(db.Integer, db.ForeignKey('tipo_erro.id'), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'codigo': self.codigo or '',
            'descricao': self.descricao,
            'tipo_erro_id': self.tipo_erro_id,
            'tipo_erro_codigo': self.tipo_erro.codigo or '',
            'tipo_erro_chave': self.tipo_erro.nome,
            'tipo_erro_nome': (
                self.tipo_erro.descricao or self.tipo_erro.nome
            ),
            'status': self.status,
            'data_criacao': self.data_criacao.isoformat(),
            'data_atualizacao': self.data_atualizacao.isoformat()
        }


def _normalizar_nome_tipo(descricao):
    """
    Cria a chave interna do motivo sem utilizar o código numérico.
    Essa chave é a que permanece gravada em Erro.tipo.
    """
    nome = re.sub(
        r'\s+',
        ' ',
        str(descricao or '').strip().upper()
    )
    return nome[:50] or 'TIPO DE ERRO'


def _nome_tipo_unico(descricao, ignorar_id=None):
    base = _normalizar_nome_tipo(descricao)
    candidato = base
    sequencia = 2

    while True:
        query = TipoErro.query.filter(
            func.upper(TipoErro.nome) == candidato.upper()
        )
        if ignorar_id:
            query = query.filter(TipoErro.id != int(ignorar_id))

        if not query.first():
            return candidato

        sufixo = f' {sequencia}'
        candidato = f'{base[:50 - len(sufixo)]}{sufixo}'
        sequencia += 1


def _proximo_codigo_tipo_erro():
    """Gera códigos sequenciais usando apenas TipoErro.codigo."""
    maior = 0

    for (codigo,) in db.session.query(TipoErro.codigo).all():
        match = re.fullmatch(
            r'(\d+)\.01',
            str(codigo or '').strip()
        )
        if match:
            maior = max(maior, int(match.group(1)))

    return f'{maior + 1:02d}.01'


def _proximo_codigo_causa(tipo_erro_id, ignorar_id=None):
    """Gera código da causa a partir de TipoErro.codigo."""
    tipo = db.session.get(TipoErro, int(tipo_erro_id))
    if not tipo:
        raise ValueError('Tipo de erro não encontrado.')
    if not tipo.codigo:
        raise ValueError('O motivo ainda não possui código automático.')

    prefixo = str(tipo.codigo).strip()
    maior = 0

    query = Causa.query.filter_by(tipo_erro_id=tipo.id)
    if ignorar_id:
        query = query.filter(Causa.id != int(ignorar_id))

    padrao = re.compile(
        rf'^{re.escape(prefixo)}\.(\d+)$'
    )

    for causa in query.all():
        match = padrao.fullmatch(
            str(causa.codigo or '').strip()
        )
        if match:
            maior = max(maior, int(match.group(1)))

    return f'{prefixo}.{maior + 1:03d}'


def _migrar_codigos_motivos_e_causas():
    """
    Separa definitivamente código e nome:
    - preserva nomes textuais antigos;
    - converte testes em que nome recebeu 01.01;
    - atualiza Erro.tipo para a nova chave textual;
    - numera todos os motivos por ordem de cadastro;
    - recria códigos das causas sem alterar suas descrições.
    """
    tipos = TipoErro.query.order_by(TipoErro.id).all()
    alterou = False

    # Primeiro corrige motivos criados no teste em que nome virou o código.
    for tipo in tipos:
        nome_atual = str(tipo.nome or '').strip()

        if re.fullmatch(r'\d+\.01', nome_atual):
            nome_antigo = nome_atual
            novo_nome = _nome_tipo_unico(
                tipo.descricao or f'TIPO DE ERRO {tipo.id}',
                ignorar_id=tipo.id
            )

            # Mantém históricos e novos lançamentos agrupados pela chave textual.
            Erro.query.filter(
                Erro.tipo == nome_antigo
            ).update(
                {'tipo': novo_nome},
                synchronize_session=False
            )

            tipo.nome = novo_nome
            alterou = True

    if alterou:
        db.session.commit()

    # Códigos são administrativos e podem ser recalculados sem afetar relatórios.
    for tipo in tipos:
        tipo.codigo = f'TMP-TIPO-{tipo.id}'
    db.session.commit()

    for indice, tipo in enumerate(tipos, start=1):
        tipo.codigo = f'{indice:02d}.01'
    db.session.commit()

    # Usa códigos temporários nas causas para evitar colisão no índice único.
    causas = Causa.query.order_by(
        Causa.tipo_erro_id,
        Causa.id
    ).all()

    for causa in causas:
        causa.codigo = f'TMP-CAUSA-{causa.id}'
    db.session.commit()

    causas_por_tipo = defaultdict(list)
    for causa in causas:
        causas_por_tipo[causa.tipo_erro_id].append(causa)

    for tipo in tipos:
        for indice, causa in enumerate(
            causas_por_tipo.get(tipo.id, []),
            start=1
        ):
            causa.codigo = f'{tipo.codigo}.{indice:03d}'

    db.session.commit()


# NOVO: CategoriaErro antes de Responsavel
class CategoriaErro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)  # ex: 'FAT001'
    nome = db.Column(db.String(100), nullable=False)  # ex: 'ERRO FATURAMENTO'
    descricao = db.Column(db.String(200))
    cor = db.Column(db.String(7), default='#3498db')
    status = db.Column(db.String(20), default='ativo')
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    data_atualizacao = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relacionamento com responsáveis
    responsaveis = db.relationship('Responsavel', 
                                 secondary=responsavel_categoria_association,
                                 back_populates='categorias_erro')
    
    def to_dict(self):
        return {
            'id': self.id,
            'codigo': self.codigo,
            'nome': self.nome,
            'descricao': self.descricao,
            'cor': self.cor,
            'status': self.status
        }

# Responsavel DEPOIS de CategoriaErro
class Responsavel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    funcao = db.Column(db.String(100))
    setor_resp = db.Column(db.String(100))
    status = db.Column(db.String(20), nullable=False, default='ativo')
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    data_atualizacao = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    prontuarios = db.relationship('Prontuario', secondary=prontuario_responsavel_association, back_populates='responsaveis')
    
    # NOVO: Relacionamento com categorias de erro
    categorias_erro = db.relationship('CategoriaErro', 
                                    secondary=responsavel_categoria_association,
                                    back_populates='responsaveis')

    def to_dict(self):
        return {
            'id': self.id,
            'nome': self.nome,
            'funcao': self.funcao,
            'setor': self.setor_resp,
            'status': self.status,
            'data_criacao': self.data_criacao.isoformat(),
            'data_atualizacao': self.data_atualizacao.isoformat(),
            'categorias_erro': [ce.to_dict() for ce in self.categorias_erro]
        }

class Prontuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    beneficiario = db.Column(db.String(200), nullable=False)
    convenio = db.Column(db.String(100), nullable=False)
    setor = db.Column(db.String(100), nullable=False)
    atendimento = db.Column(db.String(50), nullable=False, index=True)
    admissao = db.Column(db.DateTime)
    alta = db.Column(db.DateTime)
    status = db.Column(db.String(50), default='Aguardando Auditoria', index=True)
    data_erro = db.Column(db.DateTime)
    recebimento_prontuario = db.Column(db.DateTime)
    data_conta = db.Column(db.DateTime)
    enviado_faturamento = db.Column(db.DateTime)
    diarias = db.Column(db.Integer, default=0)
    fim_auditoria = db.Column(db.DateTime)
    observacao = db.Column(db.Text)
    data_criacao = db.Column(db.DateTime, default=datetime.now, index=True)
    data_atualizacao = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    erros = db.relationship('Erro', backref='prontuario', cascade='all, delete-orphan')
    responsaveis = db.relationship('Responsavel', secondary=prontuario_responsavel_association, back_populates='prontuarios')

# ÚNICA definição da classe Erro
class Erro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prontuario_id = db.Column(db.Integer, db.ForeignKey('prontuario.id'), nullable=False)
    tipo = db.Column(db.String(100), nullable=False)
    causa = db.Column(db.String(300), nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.now, index=True)
    
    # NOVOS CAMPOS: responsável específico e categoria
    responsavel_id = db.Column(db.Integer, db.ForeignKey('responsavel.id'), nullable=True)
    categoria_erro_id = db.Column(db.Integer, db.ForeignKey('categoria_erro.id'), nullable=True)
    
    # Relacionamentos
    responsavel = db.relationship('Responsavel', backref='erros_atribuidos')
    categoria_erro = db.relationship('CategoriaErro', backref='erros')

    def to_dict(self):
        return {
            'id': self.id,
            'prontuario_id': self.prontuario_id,
            'tipo': self.tipo,
            'causa': self.causa,
            'responsavel_id': self.responsavel_id,
            'responsavel_nome': self.responsavel.nome if self.responsavel else None,
            'categoria_erro_id': self.categoria_erro_id,
            'categoria_erro_nome': self.categoria_erro.nome if self.categoria_erro else None
        }

# --- 3. FUNÇÕES HELPER (DATAS E CONVERSORES) ---

def _parse_any_date(s):
    if not s:
        return None
    if isinstance(s, (datetime, date)):
        return datetime(s.year, s.month, s.day) if isinstance(s, date) else s
    s = str(s).strip()
    if s.lower() in {"none", "null", ""}:
        return None
    
    try:
        d, m, y = s.split('/')
        if len(d) == 2 and len(m) == 2 and len(y) == 4:
            return datetime(int(y), int(m), int(d))
    except:
        pass
    
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except Exception:
        pass
    
    for pat in [
        "%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z",
        "%d-%m-%Y", "%d-%m-%Y %H:%M"
    ]:
        try:
            return datetime.strptime(s, pat)
        except Exception:
            continue
    return None

def _to_br_date(value) -> str:
    dt = _parse_any_date(value)
    return dt.strftime("%d/%m/%Y") if dt else ""

def _to_iso_date(value) -> str:
    dt = _parse_any_date(value)
    return dt.strftime("%Y-%m-%d") if dt else ""

def get_tipos_erro_dict():
    try:
        tipos_erro_db = TipoErro.query.options(db.joinedload(TipoErro.causas)).all()
    except Exception as e:
        print(f"AVISO: Falha ao carregar Tipos de Erro: {e}")
        return {}
        
    tipos_erro_dict = {}
    for tipo in tipos_erro_db:
        chave = tipo.nome
        tipos_erro_dict[chave] = {
            'id': tipo.id,
            'codigo': tipo.codigo or '',
            'nome': tipo.descricao or tipo.nome,
            'chave': tipo.nome,
            'cor': tipo.cor,
            'status': tipo.status,
            'descricao': tipo.descricao,
            'causas': [c.to_dict() for c in tipo.causas if c.status == 'ativo']
        }
    return tipos_erro_dict

def _serializar_erros_agrupados(erros):
    """Agrupa registros físicos iguais sem exigir alteração imediata no banco.

    O banco atual representa a quantidade criando várias linhas. Para a tela,
    devolvemos uma única ocorrência com o campo quantidade somado, preservando
    o responsável específico de cada erro.
    """
    grupos = {}

    for erro in erros or []:
        chave = (
            erro.tipo,
            erro.causa,
            erro.responsavel_id,
            erro.categoria_erro_id,
        )

        if chave not in grupos:
            grupos[chave] = {
                'id': erro.id,
                'tipo': erro.tipo,
                'causa': erro.causa,
                'quantidade': 0,
                'responsavel_id': erro.responsavel_id,
                'responsavel_nome': (
                    erro.responsavel.nome if erro.responsavel else 'Não atribuído'
                ),
                'categoria_erro_id': erro.categoria_erro_id,
                'categoria_erro_nome': (
                    erro.categoria_erro.nome
                    if erro.categoria_erro
                    else 'Não categorizado'
                ),
                'data_criacao': _to_iso_date(erro.data_criacao),
            }

        grupos[chave]['quantidade'] += 1

    return sorted(
        grupos.values(),
        key=lambda item: (
            item['responsavel_nome'],
            item['tipo'],
            item['causa'],
        ),
    )


def prontuario_to_dict(p: Prontuario) -> dict:
    """Converte o prontuário mantendo cada erro ligado ao colaborador."""
    try:
        erros_list = _serializar_erros_agrupados(p.erros)

        return {
            'id': p.id,
            'beneficiario': p.beneficiario,
            'convenio': p.convenio,
            'setor': p.setor,
            'atendimento': p.atendimento,
            'admissao': _to_br_date(p.admissao),
            'alta': _to_br_date(p.alta),
            'status': p.status,
            'responsaveis': [r.nome for r in p.responsaveis],
            'data_erro': _to_br_date(p.data_erro),
            'recebimento_prontuario': _to_br_date(p.recebimento_prontuario),
            'data_conta': _to_br_date(p.data_conta),
            'enviado_faturamento': _to_br_date(p.enviado_faturamento),
            'diarias': p.diarias,
            'fim_auditoria': _to_br_date(p.fim_auditoria),
            'observacao': p.observacao,
            'data_criacao': _to_iso_date(p.data_criacao),
            'data_atualizacao': _to_iso_date(p.data_atualizacao),
            'erros': erros_list,
            'total_erros': sum(e['quantidade'] for e in erros_list),
            'tem_erros': bool(erros_list),
        }

    except Exception:
        app.logger.exception(
            'Falha ao converter prontuário id=%s',
            getattr(p, 'id', None),
        )
        return {
            'id': p.id,
            'beneficiario': p.beneficiario,
            'convenio': p.convenio,
            'setor': p.setor,
            'atendimento': p.atendimento,
            'status': p.status,
            'responsaveis': [],
            'erros': [],
            'total_erros': 0,
            'tem_erros': False,
        }
# --- NOVAS FUNÇÕES PARA O SISTEMA DE CATEGORIAS ---

def get_categorias_erro_dict():
    """Busca todas as categorias de erro"""
    try:
        categorias = CategoriaErro.query.filter_by(status='ativo').all()
        return {cat.codigo: cat.to_dict() for cat in categorias}
    except Exception as e:
        print(f"AVISO: Falha ao carregar Categorias de Erro: {e}")
        return {}

def get_categorias_por_responsavel(responsavel_id):
    """Busca categorias de erro permitidas para um responsável"""
    try:
        responsavel = Responsavel.query.get(responsavel_id)
        if responsavel:
            return [ce.to_dict() for ce in responsavel.categorias_erro if ce.status == 'ativo']
        return []
    except Exception as e:
        print(f"AVISO: Falha ao buscar categorias do responsável {responsavel_id}: {e}")
        return []

def get_responsaveis_por_categoria(categoria_codigo):
    """Busca responsáveis permitidos para uma categoria"""
    try:
        categoria = CategoriaErro.query.filter_by(codigo=categoria_codigo, status='ativo').first()
        if categoria:
            return [r.to_dict() for r in categoria.responsaveis if r.status == 'ativo']
        return []
    except Exception as e:
        print(f"AVISO: Falha ao buscar responsáveis da categoria {categoria_codigo}: {e}")
        return []

# --- 4. FUNÇÕES HELPER DASHBOARD ---
def _norm_status(p):
    status_raw = str(p.get('status', '')).strip().title().replace('Ao', 'ao')
    status_map = {
        'Aguardando Auditoria': 'aguardando_auditoria',
        'Em Auditoria': 'em_auditoria', 
        'Aguardando Correção': 'aguardando_correcao',
        'Aguardando Revisão': 'aguardando_revisao',
        'Entregue ao Faturamento': 'entregue_faturamento'
    }
    return status_map.get(status_raw, 'desconhecido')

def _norm_convenio(p):
    return str(p.get('convenio', 'Não Informado')).strip() or 'Não Informado'

def _norm_setor(p):
    return str(p.get('setor', 'Não Informado')).strip() or 'Não Informado'

def _tem_erro(p):
    erros = p.get("erros") or []
    return len(erros) > 0

def _pega_data_base(p):
    v = p.get("data_criacao")
    dt = _parse_any_date(v)
    if dt:
        return dt
    for key in ("recebimento_prontuario", "admissao"):
        v = (p.get(key) or "").strip()
        dt = _parse_any_date(v)
        if dt:
            return dt
    return None

def _dif_dias(a, b):
    if not a or not b:
        return 0
    return max((b - a).days, 0)

def _calc_tempos_medios(prontuarios):
    tot_aud, n = 0, 0
    for p in prontuarios:
        rec = _parse_any_date(p.get("recebimento_prontuario", ""))
        env = _parse_any_date(p.get("enviado_faturamento", ""))
        if rec and env:
            n += 1
            tot_aud += _dif_dias(rec, env)
    if n == 0:
        return {"aguardando": 0, "auditoria": 0, "correcao": 0, "total": 0}
    tempo_auditoria = round(tot_aud / n, 1)
    return {"aguardando": 0, "auditoria": tempo_auditoria, "correcao": 0, "total": tempo_auditoria}

def _calc_produtividade_diaria_mes(prontuarios_lista, ano, mes):
    num_dias = monthrange(ano, mes)[1]
    dias_do_mes = [date(ano, mes, dia) for dia in range(1, num_dias + 1)]
    mapa = {d: 0 for d in dias_do_mes}
    total_registrado = 0
    
    for p in prontuarios_lista:
        dt = _pega_data_base(p)
        if isinstance(dt, datetime):
            dt = dt.date()
        if dt and dt in mapa:
            mapa[dt] += 1
            total_registrado += 1
            
    labels = [d.strftime("%d/%m") for d in dias_do_mes]
    valores = [mapa[d] for d in dias_do_mes]
    return {"labels": labels, "valores": valores, "total_registrado": total_registrado}

def _calc_erros_timeline_mensal():
    labels = []
    valores = []
    hoje = datetime.now()
    
    for i in range(5, -1, -1):
        ano = hoje.year
        mes = hoje.month - i
        if mes <= 0:
            mes += 12
            ano -= 1
        
        nome_mes_pt = {
            1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr', 5: 'Mai', 6: 'Jun',
            7: 'Jul', 8: 'Ago', 9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
        }
        labels.append(f"{nome_mes_pt[mes]}/{ano % 100}")
        
        try:
            total_erros = db.session.query(func.count(Erro.id)).filter(
                extract('year', Erro.data_criacao) == ano,
                extract('month', Erro.data_criacao) == mes
            ).scalar()
            valores.append(total_erros or 0)
        except Exception as e:
            print(f"AVISO: Falha ao buscar timeline de erros: {e}")
            valores.append(0)
    return {"labels": labels, "valores": valores}

def _calc_taxa_erros_setor(prontuarios):
    """Calcula taxa APENAS para setores que tiveram prontuários COM ERROS"""
    prontuarios_com_erro = [p for p in prontuarios if _tem_erro(p)]
    total_com_erro = len(prontuarios_com_erro)
    
    if total_com_erro == 0:
        return []
    
    # Conta quantos prontuários com erro cada setor teve
    contagem_por_setor = Counter()
    
    for p in prontuarios_com_erro:
        setor = _norm_setor(p)
        contagem_por_setor[setor] += 1
    
    # Calcula a porcentagem em relação ao total de prontuários com erro
    resultado = []
    for setor, quantidade in contagem_por_setor.items():
        taxa = round(100 * quantidade / total_com_erro, 1)
        resultado.append({
            'nome': setor,
            'prontuarios_com_erro': quantidade,
            'taxa': taxa
        })
    
    return sorted(resultado, key=lambda x: x['taxa'], reverse=True)

def _calc_taxa_erros_convenio(prontuarios):
    """Calcula taxa APENAS para convênios que tiveram prontuários COM ERROS"""
    prontuarios_com_erro = [p for p in prontuarios if _tem_erro(p)]
    total_com_erro = len(prontuarios_com_erro)
    
    if total_com_erro == 0:
        return []
    
    # Conta quantos prontuários com erro cada convênio teve
    contagem_por_convenio = Counter()
    
    for p in prontuarios_com_erro:
        convenio = _norm_convenio(p)
        contagem_por_convenio[convenio] += 1
    
    # Calcula a porcentagem em relação ao total de prontuários com erro
    resultado = []
    for convenio, quantidade in contagem_por_convenio.items():
        taxa = round(100 * quantidade / total_com_erro, 1)
        resultado.append({
            'nome': convenio,
            'prontuarios_com_erro': quantidade,
            'taxa': taxa
        })
    
    return sorted(resultado, key=lambda x: x['taxa'], reverse=True)

def _calc_top_erros(prontuarios_lista):
    contagem_motivos = Counter()
    contagem_causas = Counter()
    
    for p in prontuarios_lista:
        if _tem_erro(p):
            motivos_neste_prontuario = set() 
            for erro in p.get("erros", []):
                motivo = erro.get('tipo', 'Desconhecido')
                causa = erro.get('causa', 'Desconhecida')
                motivos_neste_prontuario.add(motivo)
                contagem_causas[causa] += 1
            for m in motivos_neste_prontuario:
                contagem_motivos[m] += 1

    mapa_tipos_erro = get_tipos_erro_dict()
    top_motivos = []
    for codigo, contagem in contagem_motivos.most_common(5):
        info = mapa_tipos_erro.get(codigo)
        nome = info['nome'] if info else codigo
        top_motivos.append({"nome": nome, "contagem": contagem})
        
    top_causas = []
    for causa, contagem in contagem_causas.most_common(5):
        top_causas.append({"nome": causa, "contagem": contagem})

    return top_motivos, top_causas

def _calc_taxa_erros_responsavel(prontuarios):
    """Calcula taxa APENAS para responsáveis que tiveram prontuários COM ERROS"""
    prontuarios_com_erro = [p for p in prontuarios if _tem_erro(p)]
    total_com_erro = len(prontuarios_com_erro)
    
    if total_com_erro == 0:
        return []  # Nenhum prontuário com erro = lista vazia
    
    # Conta quantos prontuários com erro cada responsável teve
    contagem_por_responsavel = Counter()
    
    for p in prontuarios_com_erro:
        responsaveis = p.get('responsaveis', [])
        for responsavel in responsaveis:
            contagem_por_responsavel[responsavel] += 1
    
    # Calcula a porcentagem em relação ao total de prontuários com erro
    resultado = []
    for responsavel, quantidade in contagem_por_responsavel.items():
        taxa = round(100 * quantidade / total_com_erro, 1)
        resultado.append({
            'nome': responsavel,
            'prontuarios_com_erro': quantidade,
            'taxa': taxa,
            'participacao': f"{quantidade}/{total_com_erro}"
        })
    
    return sorted(resultado, key=lambda x: x['taxa'], reverse=True)

def gerar_texto_periodo(ano, mes, periodo, data_inicio, data_fim):
    meses_pt = {
        '01': 'Janeiro', '02': 'Fevereiro', '03': 'Março', '04': 'Abril',
        '05': 'Maio', '06': 'Junho', '07': 'Julho', '08': 'Agosto',
        '09': 'Setembro', '10': 'Outubro', '11': 'Novembro', '12': 'Dezembro'
    }

    if periodo:
        periodos = {
            'hoje': 'Hoje',
            'ontem': 'Ontem',
            'semana': 'Última semana',
            'mes': 'Este Mês',
            'trimestre': 'Este Trimestre',
            'ano': 'Este Ano'
        }
        return periodos.get(periodo, '')
    elif data_inicio and data_fim:
        return f'De {_to_br_date(data_inicio)} até {_to_br_date(data_fim)}'
    elif ano and mes:
        return f'{meses_pt.get(mes, "")} de {ano}'
    elif ano:
        return f'Ano de {ano}'
    elif mes:
        return f'Mês de {meses_pt.get(mes, "")}'
    return 'Todos os períodos'

def _calc_erros_por_motivo_detalhado(prontuarios):
    """Calcula estatísticas detalhadas de erros por motivo"""
    prontuarios_com_erro = [p for p in prontuarios if _tem_erro(p)]
    total_prontuarios_com_erro = len(prontuarios_com_erro)
    
    if total_prontuarios_com_erro == 0:
        return [], {
            'total_prontuarios_com_erro': 0,
            'total_erros_registrados': 0,
            'total_tipos_erro': 0,
            'media_erros_por_prontuario': 0
        }
    
    # Contagem de prontuários por tipo de erro
    prontuarios_por_tipo = Counter()
    # Contagem total de ocorrências por tipo
    ocorrencias_por_tipo = Counter()
    # Cores dos tipos de erro
    cores_por_tipo = {}
    
    tipos_erro_dict = get_tipos_erro_dict()
    
    for p in prontuarios_com_erro:
        tipos_neste_prontuario = set()
        for erro in p.get('erros', []):
            tipo_erro = erro.get('tipo')
            tipos_neste_prontuario.add(tipo_erro)
            ocorrencias_por_tipo[tipo_erro] += 1
            
            # Guarda a cor do tipo de erro
            if tipo_erro not in cores_por_tipo and tipo_erro in tipos_erro_dict:
                cores_por_tipo[tipo_erro] = tipos_erro_dict[tipo_erro].get('cor', '#6c757d')
        
        for tipo in tipos_neste_prontuario:
            prontuarios_por_tipo[tipo] += 1
    
    # Prepara os dados detalhados
    resultado = []
    for tipo_erro, qtd_prontuarios in prontuarios_por_tipo.most_common():
        info_tipo = tipos_erro_dict.get(tipo_erro, {})
        nome_exibicao = info_tipo.get('nome', tipo_erro)
        cor = info_tipo.get('cor', '#6c757d')
        
        taxa_prontuarios = round(100 * qtd_prontuarios / total_prontuarios_com_erro, 1)
        total_ocorrencias = ocorrencias_por_tipo.get(tipo_erro, 0)
        
        # Calcular a média aqui no backend
        media_por_prontuario = round(total_ocorrencias / qtd_prontuarios, 1) if qtd_prontuarios > 0 else 0.0
        
        resultado.append({
            'tipo': tipo_erro,
            'nome': nome_exibicao,
            'prontuarios_com_erro': qtd_prontuarios,
            'taxa_prontuarios': taxa_prontuarios,
            'total_ocorrencias': total_ocorrencias,
            'media_por_prontuario': media_por_prontuario,
            'cor': cor
        })
    
    # Estatísticas gerais
    total_erros_registrados = sum(ocorrencias_por_tipo.values())
    stats_gerais = {
        'total_prontuarios_com_erro': total_prontuarios_com_erro,
        'total_erros_registrados': total_erros_registrados,
        'total_tipos_erro': len(prontuarios_por_tipo),
        'media_erros_por_prontuario': round(total_erros_registrados / total_prontuarios_com_erro, 1) if total_prontuarios_com_erro > 0 else 0
    }
    
    return resultado, stats_gerais

def calcular_estatisticas_bd(prontuarios_obj):
    """Calcula estatísticas diretamente dos objetos do banco"""
    total_por_status = {status: 0 for status in STATUS_OPCOES}
    erros_por_tipo = Counter()
    convenios = Counter()
    setores = Counter()
    
    # 🔥 CORREÇÃO: Usar os objetos já carregados com erros
    for p in prontuarios_obj:
        if not p.status:
            continue
            
        status_normalizado = p.status.title().replace('Ao', 'ao')
        if status_normalizado in total_por_status:
            total_por_status[status_normalizado] += 1
            
        convenios[p.convenio] += 1
        setores[p.setor] += 1
        
        # 🔥 CORREÇÃO: Contar erros reais do objeto
        tipos_de_erro_neste_prontuario = set()
        for erro in p.erros:  # Agora os erros já estão carregados
            tipo_erro_nome = erro.tipo
            tipos_de_erro_neste_prontuario.add(tipo_erro_nome)
        
        for tipo_nome in tipos_de_erro_neste_prontuario:
            erros_por_tipo[tipo_nome] += 1
    
    stats = {
        'total_por_status': total_por_status,
        'erros_por_tipo': dict(erros_por_tipo),
        'convenios': dict(convenios),
        'setores': dict(setores),
        'total_prontuarios_com_erro': sum(1 for p in prontuarios_obj if p.erros)  # 🔥 Nova estatística
    }
    
    print(f"📊 ESTATÍSTICAS BD: {stats['total_prontuarios_com_erro']} prontuários com erro")
    return stats

# --- ROTAS DE LOGIN/LOGOUT/REGISTRO ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('index'))
    if request.method == 'POST':
        username = str(request.form.get('username') or '').strip()
        password = request.form.get('password') or ''
        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            registrar_log('LOGIN_FALHOU', 'autenticacao', details='Usuário ou senha incorretos.', status='erro', user=user)
            return render_template('login.html', error='Usuário ou senha incorretos.')
        if not user.active:
            registrar_log('LOGIN_BLOQUEADO', 'autenticacao', details='Conta inativa.', status='erro', user=user)
            return render_template('login.html', error='Esta conta está inativa. Procure o administrador.')
        user.ultimo_login=datetime.now(); user.ultimo_ip=_client_ip(); user.login_count=int(user.login_count or 0)+1
        db.session.commit(); login_user(user)
        registrar_log('LOGIN','autenticacao',details='Acesso realizado com sucesso.',user=user)
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout', methods=['GET','POST'])
@login_required
def logout():
    registrar_log('LOGOUT','autenticacao',details='Sessão encerrada pelo usuário.',user=current_user)
    logout_user(); return redirect(url_for('index'))

@app.route('/registrar_admin', methods=['GET','POST'])
def registrar_admin():
    total = User.query.count()
    if total > 0:
        if not current_user.is_authenticated: return redirect(url_for('login'))
        if not current_user.is_admin: return redirect(url_for('index'))
    if request.method == 'POST':
        username=str(request.form.get('username') or '').strip(); password=request.form.get('password') or ''
        if not username: return render_template('register.html', error='Informe o nome de usuário.')
        err=_validar_senha(password)
        if err: return render_template('register.html', error=err)
        if User.query.filter_by(username=username).first(): return render_template('register.html', error='Usuário já existe.')
        u=User(username=username,full_name=username,role='admin',active=True); u.set_password(password)
        db.session.add(u); db.session.commit()
        registrar_log('CRIAR_USUARIO','usuario',u.id,f'Administrador criado: {username}.',user=current_user if current_user.is_authenticated else u)
        return redirect(url_for('login'))
    return render_template('register.html')


@app.route('/debug/verificar_erros')
@login_required
def debug_verificar_erros():
    """Rota para verificar rapidamente se os erros estão sendo salvos e carregados"""
    try:
        # Buscar o último prontuário salvo
        ultimo_prontuario = Prontuario.query.options(
            db.joinedload(Prontuario.erros)
        ).order_by(Prontuario.id.desc()).first()
        
        if not ultimo_prontuario:
            return jsonify({'erro': 'Nenhum prontuário encontrado'})
        
        resultado = {
            'ultimo_prontuario': {
                'id': ultimo_prontuario.id,
                'beneficiario': ultimo_prontuario.beneficiario,
                'atendimento': ultimo_prontuario.atendimento,
                'total_erros': len(ultimo_prontuario.erros),
                'erros': []
            }
        }
        
        for erro in ultimo_prontuario.erros:
            resultado['ultimo_prontuario']['erros'].append({
                'tipo': erro.tipo,
                'causa': erro.causa,
                'responsavel_id': erro.responsavel_id
            })
        
        # Verificar total de erros no sistema
        total_erros_sistema = db.session.query(func.count(Erro.id)).scalar()
        resultado['total_erros_sistema'] = total_erros_sistema
        
        return jsonify(resultado)
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.template_filter('format_date')
def format_date(value):
    """Filtro para formatar datas no template"""
    if not value:
        return '-'
    
    if isinstance(value, str):
        # Tenta converter string para datetime
        try:
            # Tenta vários formatos comuns
            for fmt in ['%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S']:
                try:
                    dt = datetime.strptime(value, fmt)
                    return dt.strftime('%d/%m/%Y')
                except ValueError:
                    continue
            # Se não conseguir converter, retorna os primeiros 10 caracteres (YYYY-MM-DD)
            return value[:10]
        except:
            return value[:10]
    elif hasattr(value, 'strftime'):
        # Se já é um objeto datetime
        return value.strftime('%d/%m/%Y')
    else:
        return str(value)
# --- 5. ROTAS PRINCIPAIS ---

# --- 5. ROTAS PRINCIPAIS ---

@app.route('/')
def index():
    """Dashboard público, agregado e consistente com os filtros selecionados."""
    try:
        # --------------------------------------------------------------
        # 1. FILTROS
        # --------------------------------------------------------------
        base_data = request.args.get('base_data', 'lancamento').strip().lower()
        if base_data not in {'lancamento', 'admissao'}:
            base_data = 'lancamento'

        periodo_filter = request.args.get('periodo', '').strip().lower()
        data_inicio_filter = request.args.get('data_inicio', '').strip()
        data_fim_filter = request.args.get('data_fim', '').strip()
        status_filter = request.args.get('status', '').strip()
        convenio_filter = request.args.get('convenio', '').strip()
        setor_filter = request.args.get('setor', '').strip()
        responsavel_filter = request.args.get('responsavel_id', '').strip()
        tipo_filter = request.args.get('tipo_erro', '').strip()
        causa_filter = request.args.get('causa', '').strip()
        situacao_erro_filter = request.args.get('situacao_erro', '').strip()

        periodos_validos = {
            'todos', 'hoje', 'ontem', 'semana',
            'mes', 'mes_passado', 'ano'
        }

        # Datas específicas têm prioridade.
        if data_inicio_filter or data_fim_filter:
            periodo_filter = 'personalizado'
        elif periodo_filter not in periodos_validos:
            periodo_filter = 'mes'

        campo_data = (
            Prontuario.data_criacao
            if base_data == 'lancamento'
            else Prontuario.admissao
        )
        base_data_label = (
            'Data do lançamento'
            if base_data == 'lancamento'
            else 'Data da admissão'
        )

        agora = datetime.now()
        inicio_hoje = datetime(
            agora.year, agora.month, agora.day, 0, 0, 0
        )
        inicio = None
        fim_exclusivo = None

        if periodo_filter == 'personalizado':
            inicio_parse = _parse_any_date(data_inicio_filter)
            fim_parse = _parse_any_date(data_fim_filter)

            if inicio_parse:
                inicio = datetime(
                    inicio_parse.year, inicio_parse.month, inicio_parse.day
                )
            if fim_parse:
                fim_exclusivo = datetime(
                    fim_parse.year, fim_parse.month, fim_parse.day
                ) + timedelta(days=1)

            # Intervalo invertido vira um intervalo de um dia na data inicial.
            if inicio and fim_exclusivo and inicio >= fim_exclusivo:
                fim_exclusivo = inicio + timedelta(days=1)
                data_fim_filter = inicio.strftime('%Y-%m-%d')

        elif periodo_filter == 'hoje':
            inicio = inicio_hoje
            fim_exclusivo = inicio_hoje + timedelta(days=1)

        elif periodo_filter == 'ontem':
            fim_exclusivo = inicio_hoje
            inicio = fim_exclusivo - timedelta(days=1)

        elif periodo_filter == 'semana':
            inicio = inicio_hoje - timedelta(days=6)
            fim_exclusivo = inicio_hoje + timedelta(days=1)

        elif periodo_filter == 'mes':
            inicio = inicio_hoje.replace(day=1)
            if inicio.month == 12:
                fim_exclusivo = inicio.replace(
                    year=inicio.year + 1, month=1, day=1
                )
            else:
                fim_exclusivo = inicio.replace(
                    month=inicio.month + 1, day=1
                )

        elif periodo_filter == 'mes_passado':
            fim_exclusivo = inicio_hoje.replace(day=1)
            if fim_exclusivo.month == 1:
                inicio = fim_exclusivo.replace(
                    year=fim_exclusivo.year - 1, month=12, day=1
                )
            else:
                inicio = fim_exclusivo.replace(
                    month=fim_exclusivo.month - 1, day=1
                )

        elif periodo_filter == 'ano':
            inicio = inicio_hoje.replace(month=1, day=1)
            fim_exclusivo = inicio.replace(year=inicio.year + 1)

        # --------------------------------------------------------------
        # 2. CONSULTA PRINCIPAL
        # --------------------------------------------------------------
        query = Prontuario.query.options(
            db.joinedload(Prontuario.responsaveis),
            db.joinedload(Prontuario.erros).joinedload(Erro.responsavel),
            db.joinedload(Prontuario.erros).joinedload(Erro.categoria_erro),
        )

        # A competência por admissão não considera registros sem admissão.
        if base_data == 'admissao':
            query = query.filter(Prontuario.admissao.isnot(None))

        if inicio:
            query = query.filter(campo_data >= inicio)
        if fim_exclusivo:
            query = query.filter(campo_data < fim_exclusivo)
        if status_filter:
            query = query.filter(Prontuario.status == status_filter)
        if convenio_filter:
            query = query.filter(Prontuario.convenio == convenio_filter)
        if setor_filter:
            query = query.filter(Prontuario.setor == setor_filter)

        prontuarios_obj = query.order_by(
            campo_data.desc(), Prontuario.id.desc()
        ).all()

        # --------------------------------------------------------------
        # 3. FILTROS QUE ATUAM EM CADA ERRO
        # --------------------------------------------------------------
        responsavel_id_num = None
        if responsavel_filter:
            try:
                responsavel_id_num = int(responsavel_filter)
            except (TypeError, ValueError):
                responsavel_filter = ''

        possui_filtro_erro = any([
            responsavel_id_num,
            tipo_filter,
            causa_filter,
        ])

        prontuarios = []
        for prontuario_obj in prontuarios_obj:
            prontuario = prontuario_to_dict(prontuario_obj)
            erros = prontuario.get('erros') or []

            if possui_filtro_erro:
                erros_filtrados = []
                for erro in erros:
                    if (
                        responsavel_id_num
                        and erro.get('responsavel_id') != responsavel_id_num
                    ):
                        continue
                    if tipo_filter and erro.get('tipo') != tipo_filter:
                        continue
                    if causa_filter and erro.get('causa') != causa_filter:
                        continue
                    erros_filtrados.append(erro)

                if not erros_filtrados:
                    continue

                prontuario = dict(prontuario)
                prontuario['erros'] = erros_filtrados
                prontuario['total_erros'] = sum(
                    max(int(erro.get('quantidade') or 1), 1)
                    for erro in erros_filtrados
                )
                prontuario['tem_erros'] = True

            if situacao_erro_filter == 'com_erro' and not prontuario['tem_erros']:
                continue
            if situacao_erro_filter == 'sem_erro' and prontuario['tem_erros']:
                continue

            prontuarios.append(prontuario)

        # --------------------------------------------------------------
        # 4. ESTATÍSTICAS — UMA ÚNICA FONTE DE VERDADE
        # --------------------------------------------------------------
        total = len(prontuarios)
        prontuarios_com_erro = [
            p for p in prontuarios if p.get('tem_erros')
        ]
        total_com_erro = len(prontuarios_com_erro)
        total_sem_erro = total - total_com_erro
        taxa_erros = round(
            total_com_erro / total * 100, 1
        ) if total else 0.0

        status_counter = Counter(
            p.get('status') or 'Não informado'
            for p in prontuarios
        )

        total_ocorrencias = sum(
            int(p.get('total_erros') or 0)
            for p in prontuarios
        )
        total_diarias = sum(
            max(int(p.get('diarias') or 0), 0)
            for p in prontuarios
        )
        media_diarias = round(
            total_diarias / total, 1
        ) if total else 0.0
        media_ocorrencias = round(
            total_ocorrencias / total_com_erro, 1
        ) if total_com_erro else 0.0

        entregues = status_counter.get('Entregue ao Faturamento', 0)
        taxa_conclusao = round(
            entregues / total * 100, 1
        ) if total else 0.0

        tipo_ocorrencias = Counter()
        tipo_prontuarios = defaultdict(set)
        causa_ocorrencias = Counter()
        causa_prontuarios = defaultdict(set)
        responsavel_ocorrencias = Counter()
        responsavel_prontuarios = defaultdict(set)

        setores_dados = defaultdict(
            lambda: {'total': 0, 'com_erro': 0, 'ocorrencias': 0}
        )
        convenios_dados = defaultdict(
            lambda: {'total': 0, 'com_erro': 0, 'ocorrencias': 0}
        )

        for p in prontuarios:
            p_id = p.get('id')
            setor = _norm_setor(p)
            convenio = _norm_convenio(p)
            ocorrencias_p = int(p.get('total_erros') or 0)

            setores_dados[setor]['total'] += 1
            setores_dados[setor]['ocorrencias'] += ocorrencias_p
            convenios_dados[convenio]['total'] += 1
            convenios_dados[convenio]['ocorrencias'] += ocorrencias_p

            if p.get('tem_erros'):
                setores_dados[setor]['com_erro'] += 1
                convenios_dados[convenio]['com_erro'] += 1

            for erro in p.get('erros') or []:
                quantidade = max(int(erro.get('quantidade') or 1), 1)
                tipo = erro.get('tipo') or 'Não informado'
                causa = erro.get('causa') or 'Não informada'
                responsavel_nome = (
                    erro.get('responsavel_nome') or 'Não atribuído'
                )

                tipo_ocorrencias[tipo] += quantidade
                tipo_prontuarios[tipo].add(p_id)
                causa_ocorrencias[(tipo, causa)] += quantidade
                causa_prontuarios[(tipo, causa)].add(p_id)
                responsavel_ocorrencias[responsavel_nome] += quantidade
                responsavel_prontuarios[responsavel_nome].add(p_id)

        tipos_config = get_tipos_erro_dict()

        stats_tipos = []
        for tipo, ocorrencias in tipo_ocorrencias.most_common():
            info = tipos_config.get(tipo, {})
            stats_tipos.append({
                'tipo': tipo,
                'nome': info.get('nome') or tipo,
                'cor': info.get('cor') or '#6c757d',
                'prontuarios': len(tipo_prontuarios[tipo]),
                'ocorrencias': ocorrencias,
                'participacao': round(
                    ocorrencias / total_ocorrencias * 100, 1
                ) if total_ocorrencias else 0.0,
            })

        stats_causas = []
        for (tipo, causa), ocorrencias in causa_ocorrencias.most_common():
            stats_causas.append({
                'tipo': tipo,
                'causa': causa,
                'prontuarios': len(causa_prontuarios[(tipo, causa)]),
                'ocorrencias': ocorrencias,
                'participacao': round(
                    ocorrencias / total_ocorrencias * 100, 1
                ) if total_ocorrencias else 0.0,
            })

        stats_responsavel = []
        for nome, ocorrencias in responsavel_ocorrencias.most_common():
            stats_responsavel.append({
                'nome': nome,
                'prontuarios': len(responsavel_prontuarios[nome]),
                'ocorrencias': ocorrencias,
                'participacao': round(
                    ocorrencias / total_ocorrencias * 100, 1
                ) if total_ocorrencias else 0.0,
            })

        def montar_stats_grupo(dados):
            resultado = []
            for nome, valores in dados.items():
                total_grupo = valores['total']
                com_erro = valores['com_erro']
                resultado.append({
                    'nome': nome,
                    'total': total_grupo,
                    'com_erro': com_erro,
                    'sem_erro': total_grupo - com_erro,
                    'ocorrencias': valores['ocorrencias'],
                    'taxa': round(
                        com_erro / total_grupo * 100, 1
                    ) if total_grupo else 0.0,
                })
            return sorted(
                resultado,
                key=lambda item: (
                    item['taxa'],
                    item['ocorrencias'],
                    item['total'],
                ),
                reverse=True,
            )

        stats_setores = montar_stats_grupo(setores_dados)
        stats_convenios = montar_stats_grupo(convenios_dados)

        stats = {
            'total': total,
            'com_erro': total_com_erro,
            'sem_erro': total_sem_erro,
            'taxa_erros': taxa_erros,
            'total_ocorrencias': total_ocorrencias,
            'media_ocorrencias': media_ocorrencias,
            'tipos_diferentes': len(tipo_ocorrencias),
            'causas_diferentes': len(causa_ocorrencias),
            'total_diarias': total_diarias,
            'media_diarias': media_diarias,
            'entregues': entregues,
            'taxa_conclusao': taxa_conclusao,
            'aguardando_auditoria': status_counter.get(
                'Aguardando Auditoria', 0
            ),
            'em_auditoria': status_counter.get('Em Auditoria', 0),
            'aguardando_correcao': (
                status_counter.get('Aguardando Correção', 0)
                + status_counter.get('Aguardando Revisão', 0)
            ),
        }

        # --------------------------------------------------------------
        # 5. EVOLUÇÃO DO PERÍODO
        # --------------------------------------------------------------
        def data_referencia(prontuario):
            valor = (
                prontuario.get('data_criacao')
                if base_data == 'lancamento'
                else prontuario.get('admissao')
            )
            return _parse_any_date(valor)

        datas_validas = [
            data_referencia(p)
            for p in prontuarios
            if data_referencia(p)
        ]

        evolucao = {
            'labels': [],
            'prontuarios': [],
            'ocorrencias': [],
            'granularidade': '',
        }

        if datas_validas:
            inicio_grafico = inicio or min(datas_validas)
            fim_grafico = (
                fim_exclusivo
                or (max(datas_validas) + timedelta(days=1))
            )
            quantidade_dias = max(
                (fim_grafico.date() - inicio_grafico.date()).days, 1
            )

            if quantidade_dias <= 62:
                evolucao['granularidade'] = 'Dia'
                mapa = {}
                cursor = inicio_grafico.date()
                fim_data = fim_grafico.date()
                while cursor < fim_data:
                    chave = cursor.strftime('%Y-%m-%d')
                    mapa[chave] = {'prontuarios': 0, 'ocorrencias': 0}
                    cursor += timedelta(days=1)

                for p in prontuarios:
                    dt_ref = data_referencia(p)
                    if not dt_ref:
                        continue
                    chave = dt_ref.strftime('%Y-%m-%d')
                    if chave in mapa:
                        mapa[chave]['prontuarios'] += 1
                        mapa[chave]['ocorrencias'] += int(
                            p.get('total_erros') or 0
                        )

                evolucao['labels'] = [
                    datetime.strptime(chave, '%Y-%m-%d').strftime('%d/%m')
                    for chave in mapa
                ]
                evolucao['prontuarios'] = [
                    valor['prontuarios'] for valor in mapa.values()
                ]
                evolucao['ocorrencias'] = [
                    valor['ocorrencias'] for valor in mapa.values()
                ]

            elif quantidade_dias <= 730:
                evolucao['granularidade'] = 'Mês'
                mapa = {}
                cursor = datetime(
                    inicio_grafico.year, inicio_grafico.month, 1
                )
                limite = datetime(
                    fim_grafico.year, fim_grafico.month, 1
                )
                if limite < fim_grafico:
                    if limite.month == 12:
                        limite = limite.replace(
                            year=limite.year + 1, month=1
                        )
                    else:
                        limite = limite.replace(month=limite.month + 1)

                while cursor < limite:
                    chave = cursor.strftime('%Y-%m')
                    mapa[chave] = {'prontuarios': 0, 'ocorrencias': 0}
                    if cursor.month == 12:
                        cursor = cursor.replace(
                            year=cursor.year + 1, month=1
                        )
                    else:
                        cursor = cursor.replace(month=cursor.month + 1)

                for p in prontuarios:
                    dt_ref = data_referencia(p)
                    if not dt_ref:
                        continue
                    chave = dt_ref.strftime('%Y-%m')
                    if chave in mapa:
                        mapa[chave]['prontuarios'] += 1
                        mapa[chave]['ocorrencias'] += int(
                            p.get('total_erros') or 0
                        )

                nomes_meses = {
                    1: 'Jan', 2: 'Fev', 3: 'Mar', 4: 'Abr',
                    5: 'Mai', 6: 'Jun', 7: 'Jul', 8: 'Ago',
                    9: 'Set', 10: 'Out', 11: 'Nov', 12: 'Dez'
                }
                evolucao['labels'] = [
                    f'{nomes_meses[int(chave[5:7])]}/{chave[:4]}'
                    for chave in mapa
                ]
                evolucao['prontuarios'] = [
                    valor['prontuarios'] for valor in mapa.values()
                ]
                evolucao['ocorrencias'] = [
                    valor['ocorrencias'] for valor in mapa.values()
                ]

            else:
                evolucao['granularidade'] = 'Ano'
                anos = range(
                    inicio_grafico.year,
                    fim_grafico.year + 1
                )
                mapa = {
                    str(ano): {'prontuarios': 0, 'ocorrencias': 0}
                    for ano in anos
                }
                for p in prontuarios:
                    dt_ref = data_referencia(p)
                    if not dt_ref:
                        continue
                    chave = str(dt_ref.year)
                    if chave in mapa:
                        mapa[chave]['prontuarios'] += 1
                        mapa[chave]['ocorrencias'] += int(
                            p.get('total_erros') or 0
                        )
                evolucao['labels'] = list(mapa.keys())
                evolucao['prontuarios'] = [
                    valor['prontuarios'] for valor in mapa.values()
                ]
                evolucao['ocorrencias'] = [
                    valor['ocorrencias'] for valor in mapa.values()
                ]

        # --------------------------------------------------------------
        # 6. TEXTO DO PERÍODO E ANÁLISE
        # --------------------------------------------------------------
        nomes_periodos = {
            'todos': 'Todos os períodos',
            'hoje': 'Hoje',
            'ontem': 'Ontem',
            'semana': 'Últimos 7 dias',
            'mes': 'Este mês',
            'mes_passado': 'Mês passado',
            'ano': 'Este ano',
        }

        if periodo_filter == 'personalizado':
            if data_inicio_filter and data_fim_filter:
                if data_inicio_filter == data_fim_filter:
                    periodo_info = _to_br_date(data_inicio_filter)
                else:
                    periodo_info = (
                        f'{_to_br_date(data_inicio_filter)} até '
                        f'{_to_br_date(data_fim_filter)}'
                    )
            elif data_inicio_filter:
                periodo_info = (
                    f'A partir de {_to_br_date(data_inicio_filter)}'
                )
            else:
                periodo_info = (
                    f'Até {_to_br_date(data_fim_filter)}'
                )
        else:
            periodo_info = nomes_periodos.get(
                periodo_filter, 'Este mês'
            )

        filtros_ativos = [base_data_label, periodo_info]
        if status_filter:
            filtros_ativos.append(f'Status: {status_filter}')
        if convenio_filter:
            filtros_ativos.append(f'Convênio: {convenio_filter}')
        if setor_filter:
            filtros_ativos.append(f'Setor: {setor_filter}')
        if responsavel_id_num:
            responsavel_obj = Responsavel.query.get(responsavel_id_num)
            if responsavel_obj:
                filtros_ativos.append(
                    f'Colaborador: {responsavel_obj.nome}'
                )
        if tipo_filter:
            filtros_ativos.append(f'Tipo: {tipo_filter}')
        if causa_filter:
            filtros_ativos.append(f'Causa: {causa_filter}')
        if situacao_erro_filter == 'com_erro':
            filtros_ativos.append('Somente com erro')
        elif situacao_erro_filter == 'sem_erro':
            filtros_ativos.append('Somente sem erro')

        analise_partes = [
            f'No período {periodo_info.lower()}, foram analisados '
            f'{total} prontuários pela {base_data_label.lower()}.'
        ]
        if total:
            analise_partes.append(
                f'{total_com_erro} apresentaram erro '
                f'({taxa_erros:.1f}%), totalizando '
                f'{total_ocorrencias} ocorrências.'
            )
            if stats_tipos:
                analise_partes.append(
                    f'O tipo mais frequente foi '
                    f'“{stats_tipos[0]["nome"]}”, com '
                    f'{stats_tipos[0]["ocorrencias"]} ocorrências.'
                )
            if stats_causas:
                analise_partes.append(
                    f'A causa específica mais registrada foi '
                    f'“{stats_causas[0]["causa"]}”, com '
                    f'{stats_causas[0]["ocorrencias"]} ocorrências.'
                )
            if stats_setores:
                analise_partes.append(
                    f'O setor com maior taxa de prontuários com erro foi '
                    f'{stats_setores[0]["nome"]} '
                    f'({stats_setores[0]["taxa"]:.1f}%).'
                )
        else:
            analise_partes.append(
                'Não foram encontrados registros para os filtros selecionados.'
            )

        analise_dashboard = ' '.join(analise_partes)

        # --------------------------------------------------------------
        # 7. OPÇÕES DOS FILTROS
        # --------------------------------------------------------------
        convenios = [
            c.nome
            for c in Convenio.query.filter_by(status='ativo')
            .order_by(Convenio.nome).all()
        ]
        setores = [
            s.nome
            for s in Setor.query.filter_by(status='ativo')
            .order_by(Setor.nome).all()
        ]
        responsaveis = Responsavel.query.filter_by(
            status='ativo'
        ).order_by(Responsavel.nome).all()

        tipos_existentes = [
            linha[0]
            for linha in db.session.query(Erro.tipo)
            .filter(Erro.tipo.isnot(None))
            .distinct().order_by(Erro.tipo).all()
            if linha[0]
        ]
        causas_opcoes = [
            {'tipo': tipo, 'causa': causa}
            for tipo, causa in db.session.query(
                Erro.tipo, Erro.causa
            ).filter(
                Erro.tipo.isnot(None),
                Erro.causa.isnot(None)
            ).distinct().order_by(Erro.tipo, Erro.causa).all()
        ]

        filtros = {
            'base_data': base_data,
            'periodo': periodo_filter,
            'data_inicio': data_inicio_filter,
            'data_fim': data_fim_filter,
            'status': status_filter,
            'convenio': convenio_filter,
            'setor': setor_filter,
            'responsavel_id': responsavel_filter,
            'tipo_erro': tipo_filter,
            'causa': causa_filter,
            'situacao_erro': situacao_erro_filter,
        }

        grafico_status = {
            'labels': [
                'Aguardando Auditoria',
                'Em Auditoria',
                'Aguardando Correção/Revisão',
                'Entregue ao Faturamento',
            ],
            'values': [
                stats['aguardando_auditoria'],
                stats['em_auditoria'],
                stats['aguardando_correcao'],
                stats['entregues'],
            ],
        }

        relatorio_url = url_for(
            'relatorios',
            base_data=base_data,
            periodo=(
                ''
                if periodo_filter == 'personalizado'
                else periodo_filter
            ),
            data_inicio=data_inicio_filter,
            data_fim=data_fim_filter,
        )

        return render_template(
            'index.html',
            stats=stats,
            stats_tipos=stats_tipos,
            stats_causas=stats_causas,
            stats_responsavel=stats_responsavel,
            stats_setores=stats_setores,
            stats_convenios=stats_convenios,
            evolucao=evolucao,
            grafico_status=grafico_status,
            periodo_info=periodo_info,
            base_data_label=base_data_label,
            analise_dashboard=analise_dashboard,
            filtros_ativos=filtros_ativos,
            filtros=filtros,
            convenios=convenios,
            setores=setores,
            responsaveis=responsaveis,
            tipos_existentes=tipos_existentes,
            causas_opcoes=causas_opcoes,
            status_opcoes=STATUS_OPCOES,
            relatorio_url=relatorio_url,
        )

    except Exception:
        app.logger.exception('Falha ao montar o dashboard')
        return 'Erro ao carregar o dashboard.', 500

@app.route('/prontuarios')
@login_required
def prontuarios():
    status_filter = str(request.args.get('status') or '').strip()
    convenio_filter = str(request.args.get('convenio') or '').strip()
    setor_filter = str(request.args.get('setor') or '').strip()

    # Limites autorizados. "all" só carrega tudo quando escolhido.
    per_page_raw = str(
        request.args.get('per_page') or '10'
    ).strip().lower()

    if per_page_raw not in {'10', '50', '100', 'all'}:
        per_page_raw = '10'

    all_mode = per_page_raw == 'all'
    per_page = None if all_mode else int(per_page_raw)

    try:
        page = max(int(request.args.get('page', 1)), 1)
    except (TypeError, ValueError):
        page = 1

    # Primeiro filtra sem carregar os relacionamentos.
    base_query = Prontuario.query

    if status_filter:
        base_query = base_query.filter(
            Prontuario.status == status_filter
        )
    if convenio_filter:
        base_query = base_query.filter(
            Prontuario.convenio == convenio_filter
        )
    if setor_filter:
        base_query = base_query.filter(
            Prontuario.setor == setor_filter
        )

    total_items = base_query.count()

    # Depois carrega os relacionamentos somente da página selecionada.
    query = base_query.options(
        db.joinedload(Prontuario.responsaveis),
        db.joinedload(Prontuario.erros).joinedload(
            Erro.responsavel
        ),
        db.joinedload(Prontuario.erros).joinedload(
            Erro.categoria_erro
        ),
    ).order_by(
        Prontuario.data_criacao.desc(),
        Prontuario.id.desc(),
    )

    if all_mode:
        page = 1
        total_pages = 1
        prontuarios_obj = query.all()
        first_item = 1 if total_items else 0
        last_item = total_items
    else:
        total_pages = max(
            1,
            (total_items + per_page - 1) // per_page,
        )
        page = min(page, total_pages)
        offset = (page - 1) * per_page

        prontuarios_obj = query.offset(offset).limit(
            per_page
        ).all()

        first_item = offset + 1 if total_items else 0
        last_item = min(
            offset + len(prontuarios_obj),
            total_items,
        )

    prontuarios_filtrados = [
        prontuario_to_dict(prontuario)
        for prontuario in prontuarios_obj
    ]

    page_start = max(1, page - 2)
    page_end = min(total_pages, page + 2)
    page_numbers = list(range(page_start, page_end + 1))

    pagination = {
        'page': page,
        'per_page': per_page_raw,
        'all_mode': all_mode,
        'total': total_items,
        'total_pages': total_pages,
        'first_item': first_item,
        'last_item': last_item,
        'has_prev': not all_mode and page > 1,
        'has_next': not all_mode and page < total_pages,
        'prev_num': page - 1 if page > 1 else 1,
        'next_num': (
            page + 1
            if page < total_pages
            else total_pages
        ),
        'page_numbers': page_numbers,
    }

    convenios = [
        convenio.nome
        for convenio in Convenio.query.filter_by(
            status='ativo'
        ).order_by(Convenio.nome).all()
    ]
    setores = [
        setor.nome
        for setor in Setor.query.filter_by(
            status='ativo'
        ).order_by(Setor.nome).all()
    ]
    responsaveis = Responsavel.query.filter_by(
        status='ativo'
    ).order_by(Responsavel.nome).all()
    tipos_erro_dict = get_tipos_erro_dict()

    return render_template(
        'prontuarios.html',
        prontuarios=prontuarios_filtrados,
        status_opcoes=STATUS_OPCOES,
        convenios=convenios,
        setores=setores,
        responsaveis=responsaveis,
        tipos_erro=tipos_erro_dict,
        status_filter=status_filter,
        convenio_filter=convenio_filter,
        setor_filter=setor_filter,
        pagination=pagination,
    )

@app.route('/debug/prontuarios_com_erros')
@login_required
def debug_prontuarios_com_erros():
    """Rota para debug - verificar todos os prontuários e seus erros"""
    try:
        prontuarios = Prontuario.query.options(
            db.joinedload(Prontuario.erros)
        ).all()
        
        resultado = []
        for p in prontuarios:
            p_dict = {
                'id': p.id,
                'beneficiario': p.beneficiario,
                'atendimento': p.atendimento,
                'total_erros': len(p.erros),
                'erros': []
            }
            
            for erro in p.erros:
                p_dict['erros'].append({
                    'tipo': erro.tipo,
                    'causa': erro.causa,
                    'responsavel_id': erro.responsavel_id
                })
            
            resultado.append(p_dict)
        
        return jsonify({
            'total_prontuarios': len(prontuarios),
            'prontuarios_com_erros': sum(1 for p in resultado if p['total_erros'] > 0),
            'total_erros_sistema': sum(p['total_erros'] for p in resultado),
            'detalhes': resultado
        })
        
    except Exception as e:
        return jsonify({'erro': str(e)}), 500
    
@app.route('/prontuario/<int:prontuario_id>')
@login_required
def detalhes_prontuario(prontuario_id):
    """Página de detalhes de um prontuário específico"""
    try:
        # 🔥 CORREÇÃO CRÍTICA: Carregar TODOS os relacionamentos
        prontuario = Prontuario.query.options(
            db.joinedload(Prontuario.responsaveis),
            db.joinedload(Prontuario.erros).joinedload(Erro.responsavel),  # 🔥 Carregar responsável do erro
            db.joinedload(Prontuario.erros).joinedload(Erro.categoria_erro)  # 🔥 Carregar categoria do erro
        ).get(prontuario_id)
        
        if not prontuario:
            return "Prontuário não encontrado", 404
        
        # Converter para dicionário para o template
        prontuario_dict = prontuario_to_dict(prontuario)
        
        # Carregar dados adicionais para o template
        convenios = [c.nome for c in Convenio.query.filter_by(status='ativo').order_by(Convenio.nome).all()]
        setores = [s.nome for s in Setor.query.filter_by(status='ativo').order_by(Setor.nome).all()]
        responsaveis = Responsavel.query.filter_by(status='ativo').order_by(Responsavel.nome).all()
        tipos_erro_dict = get_tipos_erro_dict()
        
        return render_template('detalhes_prontuario.html',
                              prontuario=prontuario_dict,
                              status_opcoes=STATUS_OPCOES,
                              convenios=convenios,
                              setores=setores,
                              responsaveis=responsaveis,
                              tipos_erro=tipos_erro_dict)
                              
    except Exception as e:
        print(f"❌ Erro ao carregar detalhes do prontuário {prontuario_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        return "Erro ao carregar prontuário", 500
        
@app.route('/api/dashboard_data')
@login_required
def api_dashboard_data():
    prontuarios_obj = Prontuario.query.all()
    prontuarios_lista = [prontuario_to_dict(p) for p in prontuarios_obj]
    
    total = len(prontuarios_lista)

    c_status = Counter(_norm_status(p) for p in prontuarios_lista)
    aguardando  = c_status.get("aguardando_auditoria", 0)
    em_aud      = c_status.get("em_auditoria", 0)
    para_corr   = c_status.get("aguardando_correcao", 0)
    entregues   = c_status.get("entregue_faturamento", 0)

    com_erro = sum(1 for p in prontuarios_lista if _tem_erro(p))
    taxa_erros = round(100 * com_erro / total, 1) if total else 0.0

    META_TAXA_ERROS = 10.0

    hoje = datetime.now()
    produtividade = _calc_produtividade_diaria_mes(prontuarios_lista, hoje.year, hoje.month)
    tempos = _calc_tempos_medios(prontuarios_lista)
    erros_por_setor = _calc_taxa_erros_setor(prontuarios_lista)
    
    payload = {
        "stats": {
            "aguardando_auditoria": aguardando,
            "em_auditoria": em_aud,
            "aguardando_correcao": para_corr,
            "entregue": entregues,
            "taxa_erros": taxa_erros,
            "meta_taxa_erros": META_TAXA_ERROS,
            "total_registrados_mes": produtividade["total_registrado"],
            "tempo_medio_auditoria": tempos["auditoria"],
            "taxa_conclusao": round(100 * entregues / total, 1) if total else 0.0,
            "percentual_com_erros": taxa_erros,
        },
        "taxa_erros_setor": erros_por_setor,
        "produtividade_diaria_mes": produtividade,
        "tempos_medios": tempos,
    }
    return jsonify(payload)

@app.route('/relatorios')
@login_required
def relatorios():
    """Relatório gerencial com uma única fonte de verdade.

    A base pode ser a data em que o registro foi lançado no sistema
    (data_criacao) ou a data assistencial de admissão. O fim do intervalo é
    sempre exclusivo, portanto um filtro de 16/07 a 16/07 inclui todo o dia 16.
    """
    base_data = request.args.get('base_data', 'lancamento').strip().lower()
    if base_data not in {'lancamento', 'admissao'}:
        base_data = 'lancamento'

    ano_filter = request.args.get('ano', '').strip()
    mes_filter = request.args.get('mes', '').strip()
    periodo_filter = request.args.get('periodo', '').strip().lower()
    data_inicio_filter = request.args.get('data_inicio', '').strip()
    data_fim_filter = request.args.get('data_fim', '').strip()

    campo_data = (
        Prontuario.data_criacao
        if base_data == 'lancamento'
        else Prontuario.admissao
    )
    base_data_label = (
        'Data do lançamento'
        if base_data == 'lancamento'
        else 'Data da admissão'
    )

    hoje = datetime.now()
    inicio = None
    fim_exclusivo = None

    # Intervalo específico tem prioridade sobre os demais filtros.
    if data_inicio_filter or data_fim_filter:
        periodo_filter = ''
        ano_filter = ''
        mes_filter = ''

        inicio_parse = _parse_any_date(data_inicio_filter)
        fim_parse = _parse_any_date(data_fim_filter)

        if inicio_parse:
            inicio = datetime(
                inicio_parse.year,
                inicio_parse.month,
                inicio_parse.day,
                0,
                0,
                0
            )

        if fim_parse:
            fim_exclusivo = datetime(
                fim_parse.year,
                fim_parse.month,
                fim_parse.day,
                0,
                0,
                0
            ) + timedelta(days=1)

        if inicio and fim_exclusivo and inicio >= fim_exclusivo:
            # Mantém o mesmo dia como intervalo válido e corrige datas invertidas.
            fim_exclusivo = inicio + timedelta(days=1)
            data_fim_filter = inicio.strftime('%Y-%m-%d')

    elif periodo_filter:
        inicio_hoje = hoje.replace(hour=0, minute=0, second=0, microsecond=0)

        if periodo_filter == 'hoje':
            inicio = inicio_hoje
            fim_exclusivo = inicio_hoje + timedelta(days=1)
        elif periodo_filter == 'ontem':
            fim_exclusivo = inicio_hoje
            inicio = fim_exclusivo - timedelta(days=1)
        elif periodo_filter == 'semana':
            inicio = inicio_hoje - timedelta(days=6)
            fim_exclusivo = inicio_hoje + timedelta(days=1)
        elif periodo_filter == 'mes':
            inicio = inicio_hoje.replace(day=1)
            if inicio.month == 12:
                fim_exclusivo = inicio.replace(
                    year=inicio.year + 1, month=1, day=1
                )
            else:
                fim_exclusivo = inicio.replace(month=inicio.month + 1, day=1)
        elif periodo_filter == 'trimestre':
            mes_inicio = ((inicio_hoje.month - 1) // 3) * 3 + 1
            inicio = inicio_hoje.replace(month=mes_inicio, day=1)
            if mes_inicio == 10:
                fim_exclusivo = inicio.replace(
                    year=inicio.year + 1, month=1, day=1
                )
            else:
                fim_exclusivo = inicio.replace(month=mes_inicio + 3, day=1)
        elif periodo_filter == 'ano':
            inicio = inicio_hoje.replace(month=1, day=1)
            fim_exclusivo = inicio.replace(year=inicio.year + 1)
        else:
            periodo_filter = ''

    elif ano_filter or mes_filter:
        try:
            ano_num = int(ano_filter) if ano_filter else hoje.year
            mes_num = int(mes_filter) if mes_filter else None

            if mes_num:
                inicio = datetime(ano_num, mes_num, 1)
                if mes_num == 12:
                    fim_exclusivo = datetime(ano_num + 1, 1, 1)
                else:
                    fim_exclusivo = datetime(ano_num, mes_num + 1, 1)
            else:
                inicio = datetime(ano_num, 1, 1)
                fim_exclusivo = datetime(ano_num + 1, 1, 1)
        except (TypeError, ValueError):
            ano_filter = ''
            mes_filter = ''

    else:
        # Padrão: mês atual pela data de lançamento.
        periodo_filter = 'mes'
        inicio = hoje.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        if inicio.month == 12:
            fim_exclusivo = inicio.replace(
                year=inicio.year + 1, month=1, day=1
            )
        else:
            fim_exclusivo = inicio.replace(month=inicio.month + 1, day=1)

    query = Prontuario.query.options(
        db.joinedload(Prontuario.responsaveis),
        db.joinedload(Prontuario.erros).joinedload(Erro.responsavel),
        db.joinedload(Prontuario.erros).joinedload(Erro.categoria_erro),
    )

    if inicio:
        query = query.filter(campo_data >= inicio)
    if fim_exclusivo:
        query = query.filter(campo_data < fim_exclusivo)

    prontuarios_obj = query.order_by(campo_data.desc(), Prontuario.id.desc()).all()
    prontuarios = [prontuario_to_dict(p) for p in prontuarios_obj]

    total_prontuarios = len(prontuarios_obj)
    prontuarios_com_erro = sum(1 for p in prontuarios_obj if p.erros)
    prontuarios_sem_erro = total_prontuarios - prontuarios_com_erro
    total_ocorrencias = sum(len(p.erros) for p in prontuarios_obj)
    tipos_diferentes = len({
        (erro.tipo or 'Não informado').strip()
        for p in prontuarios_obj
        for erro in p.erros
    })
    taxa_prontuarios_com_erro = round(
        (prontuarios_com_erro / total_prontuarios * 100), 1
    ) if total_prontuarios else 0.0
    media_ocorrencias = round(
        total_ocorrencias / prontuarios_com_erro, 2
    ) if prontuarios_com_erro else 0.0

    total_diarias = sum(max(int(p.diarias or 0), 0) for p in prontuarios_obj)
    diarias_validas = [
        int(p.diarias)
        for p in prontuarios_obj
        if p.diarias is not None and int(p.diarias) > 0
    ]
    media_permanencia = round(
        sum(diarias_validas) / len(diarias_validas), 1
    ) if diarias_validas else 0.0

    status_counter = Counter(
        (p.status or 'Não informado').strip() for p in prontuarios_obj
    )
    erros_tipo_counter = Counter()
    causas_counter = Counter()
    causas_detalhes = defaultdict(lambda: {
        'prontuarios': set(),
        'responsaveis': set(),
        'ocorrencias': 0,
    })
    diarias_convenio_counter = Counter()

    setores = defaultdict(lambda: {
        'auditados': 0,
        'com_erro': 0,
        'ocorrencias': 0,
    })
    convenios = defaultdict(lambda: {
        'auditados': 0,
        'com_erro': 0,
        'ocorrencias': 0,
        'diarias': 0,
    })
    responsaveis = defaultdict(lambda: {
        'prontuarios': set(),
        'tipos': set(),
        'ocorrencias': 0,
    })

    for prontuario in prontuarios_obj:
        setor = (prontuario.setor or 'Não informado').strip()
        convenio = (prontuario.convenio or 'Não informado').strip()
        tem_erro = bool(prontuario.erros)
        ocorrencias_prontuario = len(prontuario.erros)
        diarias = max(int(prontuario.diarias or 0), 0)

        setores[setor]['auditados'] += 1
        setores[setor]['ocorrencias'] += ocorrencias_prontuario
        convenios[convenio]['auditados'] += 1
        convenios[convenio]['ocorrencias'] += ocorrencias_prontuario
        convenios[convenio]['diarias'] += diarias
        diarias_convenio_counter[convenio] += diarias

        if tem_erro:
            setores[setor]['com_erro'] += 1
            convenios[convenio]['com_erro'] += 1

        for erro in prontuario.erros:
            tipo = (erro.tipo or 'Não informado').strip()
            causa = (erro.causa or 'Não informada').strip()
            responsavel_nome = (
                erro.responsavel.nome.strip()
                if erro.responsavel and erro.responsavel.nome
                else 'Não atribuído'
            )

            erros_tipo_counter[tipo] += 1
            causas_counter[causa] += 1

            chave_causa = (tipo, causa)
            causas_detalhes[chave_causa]['prontuarios'].add(prontuario.id)
            causas_detalhes[chave_causa]['responsaveis'].add(responsavel_nome)
            causas_detalhes[chave_causa]['ocorrencias'] += 1

            responsaveis[responsavel_nome]['prontuarios'].add(prontuario.id)
            responsaveis[responsavel_nome]['tipos'].add(tipo)
            responsaveis[responsavel_nome]['ocorrencias'] += 1

    stats_setor = []
    for nome, valores in setores.items():
        auditados = valores['auditados']
        stats_setor.append({
            'nome': nome,
            'auditados': auditados,
            'com_erro': valores['com_erro'],
            'sem_erro': auditados - valores['com_erro'],
            'ocorrencias': valores['ocorrencias'],
            'taxa': round(
                valores['com_erro'] / auditados * 100, 1
            ) if auditados else 0.0,
        })
    stats_setor.sort(key=lambda item: (
        item['taxa'], item['ocorrencias'], item['auditados']
    ), reverse=True)

    stats_convenio = []
    for nome, valores in convenios.items():
        auditados = valores['auditados']
        stats_convenio.append({
            'nome': nome,
            'auditados': auditados,
            'com_erro': valores['com_erro'],
            'sem_erro': auditados - valores['com_erro'],
            'ocorrencias': valores['ocorrencias'],
            'diarias': valores['diarias'],
            'taxa': round(
                valores['com_erro'] / auditados * 100, 1
            ) if auditados else 0.0,
        })
    stats_convenio.sort(key=lambda item: (
        item['taxa'], item['ocorrencias'], item['auditados']
    ), reverse=True)

    stats_responsavel = []
    for nome, valores in responsaveis.items():
        ocorrencias = valores['ocorrencias']
        stats_responsavel.append({
            'nome': nome,
            'prontuarios': len(valores['prontuarios']),
            'tipos': len(valores['tipos']),
            'ocorrencias': ocorrencias,
            'participacao': round(
                ocorrencias / total_ocorrencias * 100, 1
            ) if total_ocorrencias else 0.0,
        })
    stats_responsavel.sort(key=lambda item: (
        item['ocorrencias'], item['prontuarios']
    ), reverse=True)

    stats_causa = []
    for (tipo, causa), valores in causas_detalhes.items():
        ocorrencias = valores['ocorrencias']
        stats_causa.append({
            'tipo': tipo,
            'causa': causa,
            'prontuarios': len(valores['prontuarios']),
            'colaboradores': len(valores['responsaveis']),
            'ocorrencias': ocorrencias,
            'participacao': round(
                ocorrencias / total_ocorrencias * 100, 1
            ) if total_ocorrencias else 0.0,
        })

    stats_causa.sort(
        key=lambda item: (
            item['ocorrencias'],
            item['prontuarios'],
            item['causa']
        ),
        reverse=True
    )

    # Indicadores de consistência do conjunto filtrado.
    atendimento_counter = Counter(
        str(p.atendimento).strip()
        for p in prontuarios_obj
        if p.atendimento and str(p.atendimento).strip()
    )
    atendimentos_duplicados = sum(
        quantidade - 1
        for quantidade in atendimento_counter.values()
        if quantidade > 1
    )
    qualidade_dados = {
        'sem_admissao': sum(1 for p in prontuarios_obj if not p.admissao),
        'alta_antes_admissao': sum(
            1 for p in prontuarios_obj
            if p.admissao and p.alta and p.alta < p.admissao
        ),
        'diarias_invalidas': sum(
            1 for p in prontuarios_obj if int(p.diarias or 0) <= 0
        ),
        'erros_sem_responsavel': sum(
            1 for p in prontuarios_obj
            for erro in p.erros
            if not erro.responsavel_id
        ),
        'atendimentos_duplicados': atendimentos_duplicados,
    }
    qualidade_dados['total_alertas'] = sum(qualidade_dados.values())

    entregues = status_counter.get('Entregue ao Faturamento', 0)
    taxa_conclusao = round(
        entregues / total_prontuarios * 100, 1
    ) if total_prontuarios else 0.0

    stats = {
        'total_prontuarios': total_prontuarios,
        'prontuarios_com_erro': prontuarios_com_erro,
        'prontuarios_sem_erro': prontuarios_sem_erro,
        'taxa_prontuarios_com_erro': taxa_prontuarios_com_erro,
        'total_ocorrencias': total_ocorrencias,
        'tipos_diferentes': tipos_diferentes,
        'causas_diferentes': len(stats_causa),
        'media_ocorrencias': media_ocorrencias,
        'total_diarias': total_diarias,
        'media_permanencia': media_permanencia,
        'taxa_conclusao': taxa_conclusao,
        'total_por_status': dict(status_counter),
    }

    top_tipo = erros_tipo_counter.most_common(1)
    top_causa = stats_causa[0] if stats_causa else None
    top_setor = stats_setor[0] if stats_setor else None
    top_responsavel = stats_responsavel[0] if stats_responsavel else None

    analise_partes = []
    if total_prontuarios == 0:
        analise_partes.append(
            'Não foram encontrados prontuários para o período e a base de data selecionados.'
        )
    else:
        analise_partes.append(
            f'Foram analisados {total_prontuarios} prontuários; '
            f'{prontuarios_com_erro} apresentaram pelo menos um erro '
            f'({taxa_prontuarios_com_erro:.1f}%).'
        )
        analise_partes.append(
            f'O período concentrou {total_ocorrencias} ocorrências, '
            f'distribuídas em {tipos_diferentes} tipos diferentes.'
        )
        if top_tipo:
            analise_partes.append(
                f'O tipo mais frequente foi “{top_tipo[0][0]}”, '
                f'com {top_tipo[0][1]} ocorrências.'
            )
        if top_causa:
            analise_partes.append(
                f'A causa específica mais registrada foi '
                f'“{top_causa["causa"]}”, vinculada ao tipo '
                f'“{top_causa["tipo"]}”, com '
                f'{top_causa["ocorrencias"]} ocorrências.'
            )
        if top_setor:
            analise_partes.append(
                f'O setor com maior taxa de prontuários com erro foi '
                f'{top_setor["nome"]} ({top_setor["taxa"]:.1f}%).'
            )
        if top_responsavel:
            analise_partes.append(
                f'O colaborador com mais ocorrências vinculadas foi '
                f'{top_responsavel["nome"]}, com '
                f'{top_responsavel["ocorrencias"]} ocorrências.'
            )
        if qualidade_dados['total_alertas']:
            analise_partes.append(
                f'Há {qualidade_dados["total_alertas"]} alertas de qualidade '
                f'de dados que devem ser revisados antes de decisões definitivas.'
            )

    analise_periodo = ' '.join(analise_partes)

    if inicio and fim_exclusivo:
        fim_inclusivo = fim_exclusivo - timedelta(days=1)
        if inicio.date() == fim_inclusivo.date():
            periodo_info = inicio.strftime('%d/%m/%Y')
        else:
            periodo_info = (
                f'{inicio.strftime("%d/%m/%Y")} a '
                f'{fim_inclusivo.strftime("%d/%m/%Y")}'
            )
    elif inicio:
        periodo_info = f'A partir de {inicio.strftime("%d/%m/%Y")}'
    elif fim_exclusivo:
        fim_inclusivo = fim_exclusivo - timedelta(days=1)
        periodo_info = f'Até {fim_inclusivo.strftime("%d/%m/%Y")}'
    else:
        periodo_info = 'Todos os registros'

    anos_query = (
        db.session.query(db.extract('year', campo_data))
        .filter(campo_data.isnot(None))
        .distinct()
        .order_by(db.extract('year', campo_data).desc())
    )
    anos_disponiveis = [
        int(item[0]) for item in anos_query.all() if item[0] is not None
    ]
    if not anos_disponiveis:
        anos_disponiveis = [hoje.year]

    meses_disponiveis = [
        ('01', 'Janeiro'), ('02', 'Fevereiro'), ('03', 'Março'),
        ('04', 'Abril'), ('05', 'Maio'), ('06', 'Junho'),
        ('07', 'Julho'), ('08', 'Agosto'), ('09', 'Setembro'),
        ('10', 'Outubro'), ('11', 'Novembro'), ('12', 'Dezembro'),
    ]

    chart_data = {
        'status': {
            'labels': list(status_counter.keys()),
            'values': list(status_counter.values()),
        },
        'erros_tipo': {
            'labels': [item[0] for item in erros_tipo_counter.most_common(10)],
            'values': [item[1] for item in erros_tipo_counter.most_common(10)],
        },
        'causas': {
            'labels': [
                f'{item["tipo"]} — {item["causa"]}'
                for item in stats_causa[:10]
            ],
            'values': [
                item['ocorrencias']
                for item in stats_causa[:10]
            ],
        },
        'setores': {
            'labels': [item['nome'] for item in stats_setor[:10]],
            'values': [item['taxa'] for item in stats_setor[:10]],
        },
        'diarias_convenio': {
            'labels': [item[0] for item in diarias_convenio_counter.most_common()],
            'values': [item[1] for item in diarias_convenio_counter.most_common()],
        },
        'responsaveis': {
            'labels': [item['nome'] for item in stats_responsavel[:10]],
            'values': [item['ocorrencias'] for item in stats_responsavel[:10]],
        },
    }

    app.logger.info(
        'Relatório gerado: base=%s período=%s total=%s com_erro=%s ocorrências=%s',
        base_data,
        periodo_info,
        total_prontuarios,
        prontuarios_com_erro,
        total_ocorrencias,
    )

    return render_template(
        'relatorios.html',
        prontuarios=prontuarios,
        stats=stats,
        stats_responsavel=stats_responsavel,
        stats_causa=stats_causa,
        stats_convenio=stats_convenio,
        stats_setor=stats_setor,
        qualidade_dados=qualidade_dados,
        chart_data=chart_data,
        analise_periodo=analise_periodo,
        anos_disponiveis=anos_disponiveis,
        meses_disponiveis=meses_disponiveis,
        periodo_info=periodo_info,
        base_data=base_data,
        base_data_label=base_data_label,
        ano_filter=ano_filter,
        mes_filter=mes_filter,
        periodo_filter=periodo_filter,
        data_inicio_filter=data_inicio_filter,
        data_fim_filter=data_fim_filter,
    )

# --- 6. APIs DE PRONTUÁRIOS ---
@app.route('/api/excluir_prontuario/<int:prontuario_id>', methods=['DELETE'])
@login_required
def api_excluir_prontuario(prontuario_id):
    try:
        prontuario = Prontuario.query.get(prontuario_id)
        if not prontuario:
            return jsonify({'sucesso': False, 'erro': 'Prontuário não encontrado'}), 404
        
        db.session.delete(prontuario)
        db.session.commit()
        
        print(f"✅ Prontuário {prontuario_id} excluído com sucesso!")
        return jsonify({'sucesso': True, 'mensagem': 'Prontuário excluído com sucesso'})
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Erro ao excluir prontuário {prontuario_id}:", str(e))
        return jsonify({'sucesso': False, 'erro': str(e)}), 500

@app.route('/api/atualizar_status/<int:prontuario_id>', methods=['POST'])
@login_required
def atualizar_status(prontuario_id):
    dados = request.get_json()
    novo_status = dados.get('status')
    
    if not novo_status or novo_status not in STATUS_OPCOES:
        return jsonify({'erro': 'Status inválido'}), 400
    
    prontuario = Prontuario.query.get(prontuario_id)
    if not prontuario:
        return jsonify({'erro': 'Prontuário não encontrado'}), 404
    
    try:
        prontuario.status = novo_status
        prontuario.data_atualizacao = datetime.now()
        db.session.commit()
        return jsonify({'sucesso': True, 'novo_status': novo_status})
    except Exception as e:
        db.session.rollback()
        return jsonify({'sucesso': False, 'erro': str(e)}), 500

@app.route('/api/adicionar_prontuario', methods=['POST'])
@login_required
def adicionar_prontuario():
    try:
        dados = request.get_json()
        
        print("=== 🚀 NOVO SISTEMA DE LANÇAMENTO ===")
        print(f"📥 Dados recebidos: {list(dados.keys())}")
        
        # 🔥 DEBUG DETALHADO DOS ERROS
        if 'erros' in dados:
            print(f"🔍 TIPO DE 'erros': {type(dados['erros'])}")
            print(f"🔍 CONTEÚDO DE 'erros': {dados['erros']}")
            
            if isinstance(dados['erros'], list):
                print(f"📝 LISTA COM {len(dados['erros'])} ERROS:")
                for i, erro in enumerate(dados['erros']):
                    print(f"  Erro {i}: {erro}")
        
        # 🔥 CORREÇÃO 1: Validação de campos obrigatórios
        campos_obrigatorios = ['beneficiario', 'convenio', 'setor', 'atendimento', 'admissao']
        for campo in campos_obrigatorios:
            if not dados.get(campo):
                return jsonify({'sucesso': False, 'erro': f'Campo {campo} é obrigatório'}), 400
        
        # 🔥 CORREÇÃO 2: Processamento de responsáveis
        responsaveis_ids = []
        if 'responsaveis' in dados:
            if isinstance(dados['responsaveis'], list):
                responsaveis_ids = [int(r) for r in dados['responsaveis'] if str(r).isdigit()]
            elif isinstance(dados['responsaveis'], str):
                responsaveis_ids = [int(dados['responsaveis'])]
        
        print(f"👥 RESPONSÁVEIS RECEBIDOS (IDs): {responsaveis_ids}")
        
        # 🔥 CORREÇÃO 3: Processamento de erros - ESTRUTURA CORRIGIDA
        erros_processados = []
        responsaveis_dos_erros = set()
        
        if 'erros' in dados and isinstance(dados['erros'], list):
            for erro in dados['erros']:
                if (isinstance(erro, dict) and 
                    erro.get('tipo') and 
                    erro.get('causa') and 
                    erro.get('responsavel_id')):
                    
                    # 🔥 CORREÇÃO: Garantir que os campos estão com nomes corretos
                    erro_processado = {
                        'tipo': erro['tipo'],
                        'causa': erro['causa'],
                        'quantidade': erro.get('quantidade', 1),
                        'responsavel_id': int(erro['responsavel_id'])  # Converter para int
                    }
                    
                    erros_processados.append(erro_processado)
                    responsaveis_dos_erros.add(int(erro['responsavel_id']))
        
        print(f"🔍 ERROS PROCESSADOS: {len(erros_processados)}")
        print(f"👥 RESPONSÁVEIS DOS ERROS: {responsaveis_dos_erros}")
        
        # 🔥 CORREÇÃO 4: Validação de responsáveis vs erros
        todos_responsaveis = set(responsaveis_ids) | responsaveis_dos_erros
        print(f"👥 TODOS RESPONSÁVEIS ENVOLVIDOS: {todos_responsaveis}")
        
        if len(erros_processados) > 0 and len(todos_responsaveis) == 0:
            return jsonify({
                'sucesso': False, 
                'erro': 'Cada erro deve estar vinculado a um responsável válido.'
            }), 400

        # 🔥 CORREÇÃO 5: Criação do prontuário
        novo_prontuario = Prontuario(
            beneficiario=dados['beneficiario'].strip(),
            convenio=dados['convenio'],
            setor=dados['setor'],
            atendimento=dados['atendimento'].strip(),
            status=dados.get('status', 'Aguardando Auditoria'),
            observacao=dados.get('observacao', ''),
            diarias=int(dados.get('diarias', 0)),
            
            # Processamento de datas
            admissao=_parse_any_date(dados['admissao']),
            alta=_parse_any_date(dados.get('alta')),
            recebimento_prontuario=_parse_any_date(dados.get('recebimento_prontuario')),
            data_conta=_parse_any_date(dados.get('data_conta')),
            enviado_faturamento=_parse_any_date(dados.get('enviado_faturamento')),
            fim_auditoria=_parse_any_date(dados.get('fim_auditoria')),
        )
        
        db.session.add(novo_prontuario)
        db.session.flush()  # Para obter o ID

        # 🔥 CORREÇÃO 6: Associar responsáveis ao prontuário
        responsaveis_encontrados = []
        if todos_responsaveis:
            responsaveis_encontrados = Responsavel.query.filter(
                Responsavel.id.in_(list(todos_responsaveis))
            ).all()
            
            if responsaveis_encontrados:
                novo_prontuario.responsaveis.extend(responsaveis_encontrados)
                print(f"✅ {len(responsaveis_encontrados)} responsável(eis) associado(s) ao prontuário")
            else:
                print("⚠️  Nenhum responsável encontrado com os IDs fornecidos")

        # 🔥 CORREÇÃO 7: Adição de erros com quantidade
        for erro_data in erros_processados:
            # Buscar categoria pelo tipo de erro
            categoria = CategoriaErro.query.filter_by(
                nome=erro_data['tipo'], 
                status='ativo'
            ).first()
            
            # Criar múltiplos registros baseado na quantidade
            quantidade = erro_data.get('quantidade', 1)
            for _ in range(quantidade):
                novo_erro = Erro(
                    prontuario_id=novo_prontuario.id,
                    tipo=erro_data['tipo'],
                    causa=erro_data['causa'],
                    responsavel_id=erro_data['responsavel_id'],
                    categoria_erro_id=categoria.id if categoria else None
                )
                db.session.add(novo_erro)
            
            print(f"✅ Adicionado {quantidade} erro(s) do tipo: {erro_data['tipo']}")
        
        db.session.commit()
        
        print(f"✅ PRONTUÁRIO SALVO NO BD! ID: {novo_prontuario.id}")
        print(f"📝 RESPONSÁVEIS ASSOCIADOS: {[r.nome for r in responsaveis_encontrados]}")
        print(f"📝 TOTAL DE ERROS ASSOCIADOS: {len(erros_processados)} registros")
        
        return jsonify({
            'sucesso': True, 
            'prontuario_id': novo_prontuario.id,
            'mensagem': f'Prontuário salvo com {len(responsaveis_encontrados)} responsável(eis) e {len(erros_processados)} tipo(s) de erro'
        })
        
    except Exception as e:
        db.session.rollback()
        print("❌ ERRO AO ADICIONAR PRONTUÁRIO NO BD:", str(e))
        import traceback
        traceback.print_exc()
        return jsonify({'sucesso': False, 'erro': str(e)}), 500


@app.route('/api/categorias_erro')
@login_required
def api_categorias_erro():
    """Retorna todas as categorias de erro"""
    try:
        categorias = CategoriaErro.query.filter_by(status='ativo').order_by(CategoriaErro.nome).all()
        return jsonify([cat.to_dict() for cat in categorias])
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/api/categorias_por_responsavel/<int:responsavel_id>')
@login_required
def api_categorias_por_responsavel(responsavel_id):
    """Retorna categorias permitidas para um responsável"""
    try:
        categorias = get_categorias_por_responsavel(responsavel_id)
        return jsonify(categorias)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/api/responsaveis_por_categoria/<string:categoria_codigo>')
@login_required
def api_responsaveis_por_categoria(categoria_codigo):
    """Retorna responsáveis permitidos para uma categoria"""
    try:
        responsaveis = get_responsaveis_por_categoria(categoria_codigo)
        return jsonify(responsaveis)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500

@app.route('/api/prontuario/<int:prontuario_id>/dados')
@login_required
def api_prontuario_dados(prontuario_id):
    try:
        prontuario = Prontuario.query.options(
            db.joinedload(Prontuario.responsaveis),
            db.joinedload(Prontuario.erros).joinedload(Erro.responsavel),
            db.joinedload(Prontuario.erros).joinedload(Erro.categoria_erro),
        ).get(prontuario_id)

        if not prontuario:
            return jsonify({'erro': 'Prontuário não encontrado'}), 404

        return jsonify({
            'id': prontuario.id,
            'erros': _serializar_erros_agrupados(prontuario.erros),
            'responsaveis': [
                {'id': r.id, 'nome': r.nome}
                for r in prontuario.responsaveis
            ],
        })
    except Exception:
        app.logger.exception(
            'Falha ao carregar erros do prontuário id=%s',
            prontuario_id,
        )
        return jsonify({
            'erros': [],
            'responsaveis': [],
            'erro': 'Não foi possível carregar os dados do prontuário.',
        }), 500


@app.route('/api/atualizar_erros_responsavel/<int:prontuario_id>', methods=['POST'])
@login_required
def api_atualizar_erros_responsavel(prontuario_id):
    try:
        prontuario = Prontuario.query.get(prontuario_id)
        if not prontuario:
            return jsonify({
                'sucesso': False,
                'erro': 'Prontuário não encontrado',
            }), 404

        dados = request.get_json(silent=True) or {}
        erros_recebidos = dados.get('erros')

        if not isinstance(erros_recebidos, list):
            return jsonify({
                'sucesso': False,
                'erro': 'A lista de erros é obrigatória.',
            }), 400

        erros_validos = []
        responsaveis_ids = set()

        for indice, erro_data in enumerate(erros_recebidos, start=1):
            tipo = str(erro_data.get('tipo') or '').strip()
            causa = str(erro_data.get('causa') or '').strip()

            try:
                responsavel_id = int(erro_data.get('responsavel_id'))
                quantidade = int(erro_data.get('quantidade', 1))
            except (TypeError, ValueError):
                return jsonify({
                    'sucesso': False,
                    'erro': f'Erro {indice}: responsável ou quantidade inválida.',
                }), 400

            if not tipo or not causa:
                return jsonify({
                    'sucesso': False,
                    'erro': f'Erro {indice}: tipo e causa são obrigatórios.',
                }), 400

            if quantidade < 1 or quantidade > 999:
                return jsonify({
                    'sucesso': False,
                    'erro': f'Erro {indice}: quantidade deve estar entre 1 e 999.',
                }), 400

            if not Responsavel.query.filter_by(
                id=responsavel_id,
                status='ativo',
            ).first():
                return jsonify({
                    'sucesso': False,
                    'erro': f'Erro {indice}: responsável não encontrado ou inativo.',
                }), 400

            erros_validos.append({
                'tipo': tipo,
                'causa': causa,
                'responsavel_id': responsavel_id,
                'quantidade': quantidade,
            })
            responsaveis_ids.add(responsavel_id)

        Erro.query.filter_by(prontuario_id=prontuario_id).delete(
            synchronize_session=False
        )

        for erro_data in erros_validos:
            categoria = CategoriaErro.query.filter(
                or_(
                    CategoriaErro.codigo == erro_data['tipo'],
                    CategoriaErro.nome == erro_data['tipo'],
                )
            ).first()

            for _ in range(erro_data['quantidade']):
                db.session.add(Erro(
                    prontuario_id=prontuario_id,
                    tipo=erro_data['tipo'],
                    causa=erro_data['causa'],
                    responsavel_id=erro_data['responsavel_id'],
                    categoria_erro_id=categoria.id if categoria else None,
                ))

        prontuario.responsaveis.clear()
        if responsaveis_ids:
            prontuario.responsaveis.extend(
                Responsavel.query.filter(
                    Responsavel.id.in_(responsaveis_ids)
                ).all()
            )

        prontuario.data_atualizacao = datetime.now()
        db.session.commit()

        return jsonify({
            'sucesso': True,
            'mensagem': 'Erros e responsáveis atualizados com sucesso.',
        })

    except Exception:
        db.session.rollback()
        app.logger.exception(
            'Falha ao atualizar erros do prontuário id=%s',
            prontuario_id,
        )
        return jsonify({
            'sucesso': False,
            'erro': 'Não foi possível salvar as alterações.',
        }), 500
@app.route("/test-db")
def test_db():
    try:
        result = db.session.execute("SELECT NOW();")
        return {"status": "OK", "result": str(list(result)[0])}
    except Exception as e:
        return {"status": "ERROR", "message": str(e)}, 500

@app.route('/api/adicionar_erro_unico/<int:prontuario_id>', methods=['POST'])
@login_required
def api_adicionar_erro_unico(prontuario_id):
    try:
        dados = request.get_json(silent=True) or {}
        tipo_erro = str(dados.get('tipo_erro') or '').strip()
        causa = str(dados.get('causa') or '').strip()

        try:
            responsavel_id = int(dados.get('responsavel_id'))
            quantidade = int(dados.get('quantidade', 1))
        except (TypeError, ValueError):
            return jsonify({
                'sucesso': False,
                'erro': 'Responsável e quantidade são obrigatórios.',
            }), 400

        if not tipo_erro or not causa:
            return jsonify({
                'sucesso': False,
                'erro': 'Tipo e causa são obrigatórios.',
            }), 400

        if quantidade < 1 or quantidade > 999:
            return jsonify({
                'sucesso': False,
                'erro': 'Quantidade deve estar entre 1 e 999.',
            }), 400

        prontuario = Prontuario.query.get(prontuario_id)
        if not prontuario:
            return jsonify({
                'sucesso': False,
                'erro': 'Prontuário não encontrado.',
            }), 404

        responsavel = Responsavel.query.filter_by(
            id=responsavel_id,
            status='ativo',
        ).first()
        if not responsavel:
            return jsonify({
                'sucesso': False,
                'erro': 'Responsável não encontrado ou inativo.',
            }), 400

        categoria = CategoriaErro.query.filter(
            or_(
                CategoriaErro.codigo == tipo_erro,
                CategoriaErro.nome == tipo_erro,
            )
        ).first()

        for _ in range(quantidade):
            db.session.add(Erro(
                prontuario_id=prontuario_id,
                tipo=tipo_erro,
                causa=causa,
                responsavel_id=responsavel_id,
                categoria_erro_id=categoria.id if categoria else None,
            ))

        if responsavel not in prontuario.responsaveis:
            prontuario.responsaveis.append(responsavel)

        prontuario.data_atualizacao = datetime.now()
        db.session.commit()

        return jsonify({
            'sucesso': True,
            'mensagem': 'Erro vinculado ao responsável com sucesso.',
        })

    except Exception:
        db.session.rollback()
        app.logger.exception(
            'Falha ao adicionar erro no prontuário id=%s',
            prontuario_id,
        )
        return jsonify({
            'sucesso': False,
            'erro': 'Não foi possível adicionar o erro.',
        }), 500


@app.route('/api/remover_erro_unico/<int:prontuario_id>', methods=['POST'])
@login_required
def api_remover_erro_unico(prontuario_id):
    try:
        dados = request.get_json(silent=True) or {}
        tipo_erro = str(dados.get('tipo_erro') or '').strip()
        causa = str(dados.get('causa') or '').strip()
        responsavel_id = dados.get('responsavel_id')

        prontuario = Prontuario.query.get(prontuario_id)
        if not prontuario:
            return jsonify({
                'sucesso': False,
                'erro': 'Prontuário não encontrado.',
            }), 404

        query = Erro.query.filter_by(
            prontuario_id=prontuario_id,
            tipo=tipo_erro,
            causa=causa,
        )

        if responsavel_id not in (None, ''):
            try:
                query = query.filter_by(responsavel_id=int(responsavel_id))
            except (TypeError, ValueError):
                return jsonify({
                    'sucesso': False,
                    'erro': 'Responsável inválido.',
                }), 400

        removidos = query.delete(synchronize_session=False)
        if not removidos:
            return jsonify({
                'sucesso': False,
                'erro': 'Erro não encontrado para remover.',
            }), 404

        db.session.flush()

        responsaveis_restantes = {
            responsavel_id
            for (responsavel_id,) in db.session.query(Erro.responsavel_id)
            .filter(
                Erro.prontuario_id == prontuario_id,
                Erro.responsavel_id.isnot(None),
            )
            .distinct()
            .all()
        }

        prontuario.responsaveis.clear()
        if responsaveis_restantes:
            prontuario.responsaveis.extend(
                Responsavel.query.filter(
                    Responsavel.id.in_(responsaveis_restantes)
                ).all()
            )

        prontuario.data_atualizacao = datetime.now()
        db.session.commit()

        return jsonify({
            'sucesso': True,
            'removidos': removidos,
        })

    except Exception:
        db.session.rollback()
        app.logger.exception(
            'Falha ao remover erro do prontuário id=%s',
            prontuario_id,
        )
        return jsonify({
            'sucesso': False,
            'erro': 'Não foi possível remover o erro.',
        }), 500
# --- 7. APIs DE CONFIGURAÇÕES ---
@app.route('/api/configuracoes/<string:tipo>', methods=['GET', 'POST'])
@admin_required
def api_configuracoes(tipo):
    model_map = {
        'convenios': Convenio,
        'setores': Setor,
        'responsaveis': Responsavel
    }
    if tipo not in model_map:
        return jsonify({'sucesso': False, 'erro': 'Tipo de configuração inválido'}), 404
    
    Model = model_map[tipo]

    if request.method == 'GET':
        items = Model.query.order_by(Model.nome).all()
        return jsonify([item.to_dict() for item in items])
    
    if request.method == 'POST':
        dados = request.get_json()
        if not dados.get('nome'):
            return jsonify({'sucesso': False, 'erro': 'Nome é obrigatório'}), 400
        
        try:
            if dados.get('id'):
                item = Model.query.get(dados['id'])
                if not item:
                    return jsonify({'sucesso': False, 'erro': 'Item não encontrado'}), 404
                item.nome = dados['nome']
                item.status = dados.get('status', 'ativo')
                if tipo == 'setores':
                    item.descricao = dados.get('descricao', '')
                if tipo == 'responsaveis':
                    item.funcao = dados.get('funcao', '')
                    item.setor_resp = dados.get('setor', '') 
            else:
                if tipo == 'convenios':
                    item = Convenio(nome=dados['nome'], status=dados.get('status', 'ativo'))
                elif tipo == 'setores':
                    item = Setor(nome=dados['nome'], status=dados.get('status', 'ativo'), descricao=dados.get('descricao', ''))
                elif tipo == 'responsaveis':
                    item = Responsavel(nome=dados['nome'], status=dados.get('status', 'ativo'), funcao=dados.get('funcao', ''), setor_resp=dados.get('setor', ''))
                db.session.add(item)
            
            db.session.commit()
            registrar_log('ATUALIZAR_CONFIGURACAO' if dados.get('id') else 'CRIAR_CONFIGURACAO', entity=tipo, entity_id=item.id, details={'nome': item.nome, 'status': item.status})
            return jsonify({'sucesso': True, 'item': item.to_dict()})
        except Exception as e:
            db.session.rollback()
            return jsonify({'sucesso': False, 'erro': str(e)}), 500

@app.route('/api/configuracoes/<string:tipo>/<int:item_id>', methods=['DELETE'])
@admin_required
def api_excluir_configuracao(tipo, item_id):
    model_map = {
        'convenios': Convenio,
        'setores': Setor,
        'responsaveis': Responsavel,
        'causas': Causa,
        'tipos_erro': TipoErro
    }
    if tipo not in model_map:
        return jsonify({'sucesso': False, 'erro': 'Tipo de configuração inválido'}), 404
    
    Model = model_map[tipo]

    try:
        item = Model.query.get(item_id)
        if not item:
            return jsonify({'sucesso': False, 'erro': 'Item não encontrado'}), 404
        
        item_nome=getattr(item,'nome',None) or getattr(item,'descricao',None) or str(item_id)
        db.session.delete(item);db.session.commit();registrar_log('EXCLUIR_CONFIGURACAO',entity=tipo,entity_id=item_id,details={'item':item_nome})
        return jsonify({'sucesso': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'sucesso': False, 'erro': str(e)}), 500

@app.route('/api/configuracoes/causas', methods=['GET', 'POST'])
@admin_required
def api_causas():
    if request.method == 'GET':
        items = Causa.query.join(TipoErro).order_by(
            TipoErro.nome,
            Causa.codigo,
            Causa.descricao
        ).all()
        return jsonify([item.to_dict() for item in items])

    dados = request.get_json(silent=True) or {}
    descricao = str(dados.get('descricao') or '').strip()
    tipo_erro_id = dados.get('tipo_erro_id')

    if not descricao or not tipo_erro_id:
        return jsonify({
            'sucesso': False,
            'erro': 'Descrição e tipo de erro são obrigatórios.'
        }), 400

    try:
        tipo_erro_id = int(tipo_erro_id)
        tipo_erro = db.session.get(TipoErro, tipo_erro_id)

        if not tipo_erro:
            return jsonify({
                'sucesso': False,
                'erro': 'Tipo de erro não encontrado.'
            }), 404

        if dados.get('id'):
            item = db.session.get(Causa, int(dados['id']))
            if not item:
                return jsonify({
                    'sucesso': False,
                    'erro': 'Causa não encontrada.'
                }), 404

            mudou_tipo = item.tipo_erro_id != tipo_erro_id
            item.descricao = descricao
            item.tipo_erro_id = tipo_erro_id
            item.status = dados.get('status', 'ativo')

            if mudou_tipo or not item.codigo:
                item.codigo = _proximo_codigo_causa(
                    tipo_erro_id,
                    ignorar_id=item.id
                )

            acao_log = 'ATUALIZAR_CAUSA'
        else:
            item = Causa(
                codigo=_proximo_codigo_causa(tipo_erro_id),
                descricao=descricao,
                tipo_erro_id=tipo_erro_id,
                status=dados.get('status', 'ativo')
            )
            db.session.add(item)
            acao_log = 'CRIAR_CAUSA'

        db.session.commit()

        registrar_log(
            acao_log,
            entity='causa',
            entity_id=item.id,
            details={
                'codigo': item.codigo,
                'descricao': item.descricao,
                'tipo_erro_codigo': tipo_erro.codigo,
                'tipo_erro': tipo_erro.nome,
                'status': item.status,
            },
        )

        return jsonify({
            'sucesso': True,
            'item': item.to_dict()
        })

    except Exception as exc:
        db.session.rollback()
        app.logger.exception('Falha ao salvar causa')
        return jsonify({
            'sucesso': False,
            'erro': 'Não foi possível salvar a causa.',
            'detalhe': str(exc),
        }), 500
@app.route('/api/configuracoes/tipos_erro', methods=['GET', 'POST'])
@admin_required
def api_tipos_erro():
    if request.method == 'GET':
        items = TipoErro.query.order_by(TipoErro.codigo).all()
        return jsonify([item.to_dict() for item in items])

    dados = request.get_json(silent=True) or {}
    descricao = str(dados.get('descricao') or '').strip()

    if not descricao:
        return jsonify({
            'sucesso': False,
            'erro': 'O nome do motivo é obrigatório.'
        }), 400

    try:
        if dados.get('id'):
            item = db.session.get(
                TipoErro,
                int(dados['id'])
            )
            if not item:
                return jsonify({
                    'sucesso': False,
                    'erro': 'Motivo não encontrado.'
                }), 404

            # Código e chave histórica permanecem imutáveis.
            item.descricao = descricao
            item.cor = dados.get('cor', '#dc3545')
            item.status = dados.get('status', 'ativo')
            acao_log = 'ATUALIZAR_TIPO_ERRO'
        else:
            item = TipoErro(
                codigo=_proximo_codigo_tipo_erro(),
                nome=_nome_tipo_unico(descricao),
                descricao=descricao,
                cor=dados.get('cor', '#dc3545'),
                status=dados.get('status', 'ativo')
            )
            db.session.add(item)
            acao_log = 'CRIAR_TIPO_ERRO'

        db.session.commit()

        registrar_log(
            acao_log,
            entity='tipo_erro',
            entity_id=item.id,
            details={
                'codigo': item.codigo,
                'chave_historica': item.nome,
                'descricao': item.descricao,
                'status': item.status,
            },
        )

        return jsonify({
            'sucesso': True,
            'item': item.to_dict()
        })

    except Exception as exc:
        db.session.rollback()
        app.logger.exception('Falha ao salvar motivo')
        return jsonify({
            'sucesso': False,
            'erro': 'Não foi possível salvar o motivo.',
            'detalhe': str(exc),
        }), 500
@app.route('/api/popular_causas', methods=['POST'])
@admin_required
def popular_causas_padrao():
    DADOS_PADRAO = [
        {
            'nome': 'FALTA DE ASSINATURA',
            'descricao': 'Falta de Assinatura',
            'cor': '#ffc107',
            'causas': [
                'Falta assinatura do médico',
                'Falta assinatura do paciente',
                'Falta assinatura da enfermagem',
            ],
        },
        {
            'nome': 'REGISTRO INCOMPLETO',
            'descricao': 'Registro Incompleto',
            'cor': '#fd7e14',
            'causas': [
                'Evolução de enfermagem incompleta',
                'Prescrição médica ilegível',
                'Ausência de data/hora',
            ],
        },
        {
            'nome': 'TAXAS E MATERIAIS',
            'descricao': 'Taxas e Materiais',
            'cor': '#dc3545',
            'causas': [
                'Cobrança indevida de material',
                'Falta checagem de material',
                'Divergência de taxa',
            ],
        },
    ]

    try:
        db.session.query(Causa).delete()
        db.session.query(TipoErro).delete()
        db.session.commit()

        for indice_tipo, info in enumerate(
            DADOS_PADRAO,
            start=1
        ):
            codigo_tipo = f'{indice_tipo:02d}.01'
            tipo_erro = TipoErro(
                codigo=codigo_tipo,
                nome=info['nome'],
                descricao=info['descricao'],
                cor=info['cor'],
                status='ativo',
            )
            db.session.add(tipo_erro)
            db.session.flush()

            for indice_causa, descricao in enumerate(
                info['causas'],
                start=1
            ):
                db.session.add(Causa(
                    codigo=(
                        f'{codigo_tipo}.'
                        f'{indice_causa:03d}'
                    ),
                    descricao=descricao,
                    status='ativo',
                    tipo_erro_id=tipo_erro.id,
                ))

        db.session.commit()
        registrar_log(
            'RECARREGAR_CAUSAS_PADRAO',
            entity='configuracao',
            details='Tipos e causas padrão recarregados.',
        )
        return jsonify({
            'sucesso': True,
            'mensagem': 'Dados padrão recarregados.'
        })
    except Exception as exc:
        db.session.rollback()
        app.logger.exception('Erro ao popular causas')
        return jsonify({
            'sucesso': False,
            'erro': str(exc)
        }), 500
@app.route('/api/usuarios', methods=['GET','POST'])
@admin_required
def api_usuarios():
    if request.method == 'GET':
        return jsonify([u.to_dict() for u in User.query.order_by(User.active.desc(),User.full_name,User.username).all()])
    d=request.get_json(silent=True) or {}; uid=d.get('id'); username=str(d.get('username') or '').strip(); full=str(d.get('full_name') or '').strip(); email=str(d.get('email') or '').strip().lower() or None; role=str(d.get('role') or 'auditor').lower(); active=bool(d.get('active',True)); password=d.get('password') or ''
    if not username: return jsonify({'sucesso':False,'erro':'O login do usuário é obrigatório.'}),400
    if role not in {'admin','auditor'}: return jsonify({'sucesso':False,'erro':'Perfil inválido.'}),400
    q=User.query.filter(User.username==username)
    if uid: q=q.filter(User.id!=int(uid))
    if q.first(): return jsonify({'sucesso':False,'erro':'Já existe um usuário com este login.'}),409
    if email:
        q=User.query.filter(User.email==email)
        if uid: q=q.filter(User.id!=int(uid))
        if q.first(): return jsonify({'sucesso':False,'erro':'Este e-mail já pertence a outro usuário.'}),409
    try:
        if uid:
            u=db.session.get(User,int(uid))
            if not u: return jsonify({'sucesso':False,'erro':'Usuário não encontrado.'}),404
            if u.id==current_user.id and not active: return jsonify({'sucesso':False,'erro':'Você não pode inativar a própria conta.'}),400
            if u.role=='admin' and role!='admin' and User.query.filter_by(role='admin',active=True).count()<=1: return jsonify({'sucesso':False,'erro':'O sistema deve manter ao menos um administrador ativo.'}),400
            u.username=username;u.full_name=full or username;u.email=email;u.role=role;u.active=active;u.data_atualizacao=datetime.now()
            if password:
                err=_validar_senha(password)
                if err: return jsonify({'sucesso':False,'erro':err}),400
                u.set_password(password)
            action='ATUALIZAR_USUARIO'
        else:
            err=_validar_senha(password)
            if err: return jsonify({'sucesso':False,'erro':err}),400
            u=User(username=username,full_name=full or username,email=email,role=role,active=active);u.set_password(password);db.session.add(u);action='CRIAR_USUARIO'
        db.session.commit(); registrar_log(action,'usuario',u.id,{'login':u.username,'nome':u.full_name,'perfil':u.role,'ativo':u.active})
        return jsonify({'sucesso':True,'usuario':u.to_dict()})
    except Exception as exc:
        db.session.rollback();app.logger.exception('Falha ao salvar usuário');return jsonify({'sucesso':False,'erro':'Não foi possível salvar o usuário.','detalhe':str(exc)}),500

@app.route('/api/usuarios/<int:usuario_id>/senha', methods=['POST'])
@admin_required
def api_resetar_senha(usuario_id):
    password=(request.get_json(silent=True) or {}).get('password') or '';err=_validar_senha(password)
    if err:return jsonify({'sucesso':False,'erro':err}),400
    u=db.session.get(User,usuario_id)
    if not u:return jsonify({'sucesso':False,'erro':'Usuário não encontrado.'}),404
    u.set_password(password);u.data_atualizacao=datetime.now();db.session.commit();registrar_log('REDEFINIR_SENHA','usuario',u.id,f'Senha redefinida para {u.username}.')
    return jsonify({'sucesso':True})

@app.route('/api/logs')
@admin_required
def api_logs():
    q=AuditLog.query; usuario=str(request.args.get('usuario') or '').strip();action=str(request.args.get('action') or '').strip();status=str(request.args.get('status') or '').strip();inicio=_parse_any_date(request.args.get('inicio'));fim=_parse_any_date(request.args.get('fim'))
    if usuario:q=q.filter(AuditLog.username.ilike(f'%{usuario}%'))
    if action:q=q.filter(AuditLog.action==action)
    if status:q=q.filter(AuditLog.status==status)
    if inicio:q=q.filter(AuditLog.created_at>=datetime(inicio.year,inicio.month,inicio.day))
    if fim:q=q.filter(AuditLog.created_at<datetime(fim.year,fim.month,fim.day)+timedelta(days=1))
    limit=min(max(int(request.args.get('limit',200) or 200),1),1000)
    return jsonify([x.to_dict() for x in q.order_by(AuditLog.created_at.desc()).limit(limit).all()])

@app.route('/configuracoes/logs.csv')
@admin_required
def exportar_logs_csv():
    rows=AuditLog.query.order_by(AuditLog.created_at.desc()).limit(5000).all();out=io.StringIO();w=csv.writer(out,delimiter=';');w.writerow(['Data/Hora','Usuário','Ação','Módulo','Identificador','Detalhes','Método','Rota','IP','Status'])
    for x in rows:w.writerow([x.created_at.strftime('%d/%m/%Y %H:%M:%S'),x.username,x.action,x.entity,x.entity_id or '',x.details or '',x.method or '',x.path or '',x.ip_address or '',x.status])
    return Response('\ufeff'+out.getvalue(),mimetype='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename=logs_auditoria.csv'})

@app.route('/configuracoes')
@admin_required
def configuracoes():
    convenios=[x.to_dict() for x in Convenio.query.order_by(Convenio.nome).all()];setores=[x.to_dict() for x in Setor.query.order_by(Setor.nome).all()];responsaveis=[x.to_dict() for x in Responsavel.query.order_by(Responsavel.nome).all()];tipos=[x.to_dict() for x in TipoErro.query.order_by(TipoErro.nome).all()];causas=[x.to_dict() for x in Causa.query.join(TipoErro).order_by(TipoErro.nome,Causa.descricao).all()];usuarios=[x.to_dict() for x in User.query.order_by(User.active.desc(),User.full_name,User.username).all()];logs=[x.to_dict() for x in AuditLog.query.order_by(AuditLog.created_at.desc()).limit(200).all()]
    stats={'usuarios_total':len(usuarios),'usuarios_ativos':sum(1 for x in usuarios if x['active']),'administradores':sum(1 for x in usuarios if x['role']=='admin' and x['active']),'logs_total':AuditLog.query.count(),'convenios_ativos':sum(1 for x in convenios if x['status']=='ativo'),'setores_ativos':sum(1 for x in setores if x['status']=='ativo'),'responsaveis_ativos':sum(1 for x in responsaveis if x['status']=='ativo')}
    actions=[x[0] for x in db.session.query(AuditLog.action).distinct().order_by(AuditLog.action).all() if x[0]]
    return render_template('configuracoes.html',convenios=convenios,setores=setores,responsaveis=responsaveis,tipos_erro_lista=tipos,tipos_erro=get_tipos_erro_dict(),causas=causas,usuarios=usuarios,logs=logs,config_stats=stats,log_actions=actions)



@app.route('/alimentacao')
@login_required
def alimentacao():
    try:
        print("🔍 Carregando dados para a página de alimentação...")
        
        # Carregar convenios
        convenios = [c.nome for c in Convenio.query.filter_by(status='ativo').order_by(Convenio.nome).all()]
        print(f"✅ Convenios carregados: {len(convenios)}")
        
        # Carregar setores
        setores = [s.nome for s in Setor.query.filter_by(status='ativo').order_by(Setor.nome).all()]
        print(f"✅ Setores carregados: {len(setores)}")
        
        # Carregar responsáveis como OBJETOS (id, nome)
        responsaveis_db = Responsavel.query.filter_by(status='ativo').order_by(Responsavel.nome).all()
        responsaveis = [{'id': r.id, 'nome': r.nome} for r in responsaveis_db]
        
        print(f"✅ Responsáveis carregados: {len(responsaveis)}")
        
        # Carregar tipos de erro
        tipos_erro_dict = get_tipos_erro_dict()
        print(f"✅ Tipos de erro carregados: {len(tipos_erro_dict)}")
        
        return render_template('alimentacao.html',
                                convenios=convenios,
                                setores=setores,
                                responsaveis=responsaveis,
                                tipos_erro=tipos_erro_dict,
                                status_opcoes=STATUS_OPCOES
                                )
                                
    except Exception as e:
        print(f"❌ ERRO na rota /alimentacao: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Fallback com dados básicos
        return render_template('alimentacao.html',
                                convenios=['Convênio A', 'Convênio B'],
                                setores=['Setor A', 'Setor B'],
                                responsaveis=[{'id': 1, 'nome': 'Responsável 1'}],
                                tipos_erro={},
                                status_opcoes=STATUS_OPCOES
                                )

# --- 8. INICIALIZAÇÃO DA APLICAÇÃO ---
if __name__ == '__main__':
    with app.app_context():
        print("Verificando e criando banco de dados se necessário...")
        try:
            db.create_all()
            print(f"Banco de dados está em: {db_path}")
            
            inspector = db.inspect(db.engine)
            tabelas = inspector.get_table_names()
            print(f"Tabelas encontradas: {tabelas}")
            if 'prontuario' not in tabelas:
                 print("ALERTA: Tabela 'prontuario' não foi criada. Verifique as permissões.")
                 
        except Exception as e:
            print(f"ERRO CRÍTICO AO INICIAR O BANCO DE DADOS: {e}")
            print("Verifique se o diretório 'data' tem permissão de escrita.")
    
    app.run(debug=True, host='0.0.0.0', port=5006)