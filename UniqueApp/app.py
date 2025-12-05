import os
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
from collections import Counter, defaultdict
import traceback
from sqlalchemy import extract, func
from calendar import monthrange
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import joinedload # Importação explícita

# --- 1. CONFIGURAÇÃO INICIAL E BANCO DE DADOS ---
app = Flask(__name__)

# --- CONFIGURAÇÃO DE SEGURANÇA ---
app.config['SECRET_KEY'] = 'coloque-uma-chave-secreta-bem-dificil-aqui' # Necessário para sessões

# --- INICIALIZAÇÃO DO LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' # Nome da função da rota de login
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

# Tabelas de associação
prontuario_responsavel_association = db.Table('prontuario_responsavel_association',
    db.Column('prontuario_id', db.Integer, db.ForeignKey('prontuario.id'), primary_key=True),
    db.Column('responsavel_id', db.Integer, db.ForeignKey('responsavel.id'), primary_key=True)
)

responsavel_categoria_association = db.Table('responsavel_categoria_association',
    db.Column('responsavel_id', db.Integer, db.ForeignKey('responsavel.id'), primary_key=True),
    db.Column('categoria_erro_id', db.Integer, db.ForeignKey('categoria_erro.id'), primary_key=True),
    db.Column('data_inicio', db.DateTime, default=datetime.now),
    db.Column('data_fim', db.DateTime, nullable=True)
)

# Modelos base

# --- MODELO DE USUÁRIO ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

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
            'nome': self.nome,
            'descricao': self.descricao,
            'cor': self.cor,
            'status': self.status,
            'data_criacao': self.data_criacao.isoformat(),
            'data_atualizacao': self.data_atualizacao.isoformat()
        }

class Causa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(300), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='ativo')
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    data_atualizacao = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    tipo_erro_id = db.Column(db.Integer, db.ForeignKey('tipo_erro.id'), nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'descricao': self.descricao,
            'tipo_erro_id': self.tipo_erro_id,
            'tipo_erro_nome': self.tipo_erro.nome,
            'status': self.status,
            'data_criacao': self.data_criacao.isoformat(),
            'data_atualizacao': self.data_atualizacao.isoformat()
        }

class CategoriaErro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.String(200))
    cor = db.Column(db.String(7), default='#3498db')
    status = db.Column(db.String(20), default='ativo')
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    data_atualizacao = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
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

class Responsavel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    funcao = db.Column(db.String(100))
    setor_resp = db.Column(db.String(100))
    status = db.Column(db.String(20), nullable=False, default='ativo')
    data_criacao = db.Column(db.DateTime, default=datetime.now)
    data_atualizacao = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    prontuarios = db.relationship('Prontuario', secondary=prontuario_responsavel_association, back_populates='responsaveis')
    
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

class Erro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    prontuario_id = db.Column(db.Integer, db.ForeignKey('prontuario.id'), nullable=False)
    tipo = db.Column(db.String(100), nullable=False) # TipoErro.nome
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
    
    # Tentativa 1: Formato DD/MM/YYYY
    try:
        # Verifica se tem / e se as partes tem o tamanho esperado
        parts = s.split('/')
        if len(parts) == 3 and len(parts[0]) <= 2 and len(parts[1]) == 2 and len(parts[2]) == 4:
             d, m, y = map(int, parts)
             return datetime(y, m, d)
    except:
        pass
    
    # Tratamento de ISO/Zulu Time
    if 'T' in s or s.endswith("Z"):
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            # Tenta parsear com offset de fuso horário
            return datetime.fromisoformat(s)
        except ValueError:
             # Se falhar, tenta sem o fuso horário (removendo o offset/Z)
             s = s.split('+')[0]
             s = s.replace('Z', '')
             try:
                 # Tenta formato ISO sem timezone
                 return datetime.fromisoformat(s)
             except ValueError:
                 pass

    # Tentativa 3: Formatos comuns sem separador
    for pat in [
        "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", 
        "%d-%m-%Y", "%d/%m/%Y", "%d/%m/%Y %H:%M:%S"
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
    # Retorna apenas a data YYYY-MM-DD
    return dt.strftime("%Y-%m-%d") if dt else ""

def get_tipos_erro_dict():
    try:
        # Usa joinedload para carregar as causas de uma vez
        tipos_erro_db = TipoErro.query.options(joinedload(TipoErro.causas)).all()
    except Exception as e:
        print(f"AVISO: Falha ao carregar Tipos de Erro: {e}")
        return {}
        
    tipos_erro_dict = {}
    for tipo in tipos_erro_db:
        chave = tipo.nome # Usa o nome/código como chave, ex: '01.01'
        tipos_erro_dict[chave] = {
            'id': tipo.id,
            'nome': tipo.descricao, # Nome amigável
            'cor': tipo.cor,
            'status': tipo.status,
            'descricao': tipo.descricao,
            'causas': [c.to_dict() for c in tipo.causas if c.status == 'ativo']
        }
    return tipos_erro_dict

def prontuario_to_dict(p: Prontuario) -> dict:
    """Converte um prontuário para dicionário, incluindo todos os erros - VERSÃO CORRIGIDA E OTIMIZADA"""
    try:
        # print(f"🔍 DEBUG prontuario_to_dict - ID: {p.id}")
        
        # Carregar responsáveis
        responsaveis_nomes = [r.nome for r in p.responsaveis]
        # print(f"    👥 Responsáveis: {responsaveis_nomes}")

        # Processar Erros - assume que foram carregados via joinedload na query principal
        erros_list = []
        if p.erros:
            for erro in p.erros:
                erro_dict = {
                    'id': erro.id,
                    'tipo': erro.tipo,
                    'causa': erro.causa,
                    'quantidade': 1, # Mantém 1 se o erro é um registro por ocorrência
                    'responsavel_id': erro.responsavel_id,
                    'responsavel_nome': erro.responsavel.nome if erro.responsavel else 'Não atribuído',
                    'categoria_erro_id': erro.categoria_erro_id,
                    'categoria_erro_nome': erro.categoria_erro.nome if erro.categoria_erro else 'Não categorizado',
                    'data_criacao': _to_iso_date(erro.data_criacao)
                }
                erros_list.append(erro_dict)
                # print(f"    📝 Erro: {erro.tipo} - {erro.causa} (Resp: {erro_dict['responsavel_nome']})")
        # else:
            # print("    ⚠️  NENHUM ERRO CARREGADO para este prontuário")

        return {
            'id': p.id,
            'beneficiario': p.beneficiario,
            'convenio': p.convenio,
            'setor': p.setor,
            'atendimento': p.atendimento,
            'admissao': _to_br_date(p.admissao),
            'alta': _to_br_date(p.alta),
            'status': p.status,
            'responsaveis': responsaveis_nomes,
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
            'total_erros': len(erros_list),
            'tem_erros': len(erros_list) > 0
        }
        
    except Exception as e:
        print(f"❌ ERRO em prontuario_to_dict para prontuario {p.id}: {str(e)}")
        import traceback
        traceback.print_exc()
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
            'tem_erros': False
        }

# --- NOVAS FUNÇÕES PARA O SISTEMA DE CATEGORIAS ---

def get_categorias_erro_dict():
    """Busca todas as categorias de erro"""
    try:
        categorias = CategoriaErro.query.filter_by(status='ativo').all()
        # Retorna um dicionário mapeado pelo CODIGO para fácil acesso
        return {cat.codigo: cat.to_dict() for cat in categorias}
    except Exception as e:
        print(f"AVISO: Falha ao carregar Categorias de Erro: {e}")
        return {}

def get_categorias_por_responsavel(responsavel_id):
    """Busca categorias de erro permitidas para um responsável"""
    try:
        # Usa joinedload para evitar N+1
        responsavel = Responsavel.query.options(joinedload(Responsavel.categorias_erro)).get(responsavel_id)
        if responsavel:
            return [ce.to_dict() for ce in responsavel.categorias_erro if ce.status == 'ativo']
        return []
    except Exception as e:
        print(f"AVISO: Falha ao buscar categorias do responsável {responsavel_id}: {e}")
        return []

def get_responsaveis_por_categoria(categoria_codigo):
    """Busca responsáveis permitidos para uma categoria"""
    try:
        # Usa joinedload para evitar N+1
        categoria = CategoriaErro.query.options(joinedload(CategoriaErro.responsaveis)).filter_by(codigo=categoria_codigo, status='ativo').first()
        if categoria:
            return [r.to_dict() for r in categoria.responsaveis if r.status == 'ativo']
        return []
    except Exception as e:
        print(f"AVISO: Falha ao buscar responsáveis da categoria {categoria_codigo}: {e}")
        return []

# --- 4. FUNÇÕES HELPER DASHBOARD ---
# (Manutenção das funções auxiliares de dashboard - sem grandes alterações de lógica, apenas ajuste fino)

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
        # Converte para datetime para manter a consistência com os outros objetos
        if isinstance(dt, date) and not isinstance(dt, datetime):
            return datetime(dt.year, dt.month, dt.day)
        return dt
    return None

def _dif_dias(a, b):
    # Certifica que a e b são objetos datetime para subtração
    a_dt = _parse_any_date(a)
    b_dt = _parse_any_date(b)
    
    if not a_dt or not b_dt:
        return 0
    return max((b_dt - a_dt).days, 0)

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
    
    # Busca dos últimos 6 meses (incluindo o atual)
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
            # Busca a contagem de erros no banco de dados para o mês/ano
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
    
    contagem_por_setor = Counter(_norm_setor(p) for p in prontuarios_com_erro)
    
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
    
    contagem_por_convenio = Counter(_norm_convenio(p) for p in prontuarios_com_erro)
    
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
        # Usa o nome amigável (descricao) se disponível
        info = mapa_tipos_erro.get(codigo)
        nome = info['descricao'] if info else codigo
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
        return [] 
    
    contagem_por_responsavel = Counter()
    
    for p in prontuarios_com_erro:
        responsaveis = p.get('responsaveis', [])
        for responsavel in responsaveis:
            contagem_por_responsavel[responsavel] += 1 # Conta prontuário por responsável

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
            'ano': 'Este Ano',
            'todos': 'Todos os períodos'
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
    """Calcula estatísticas detalhadas de erros por motivo (TipoErro)"""
    prontuarios_com_erro = [p for p in prontuarios if _tem_erro(p)]
    total_prontuarios_com_erro = len(prontuarios_com_erro)
    
    if total_prontuarios_com_erro == 0:
        return [], {
            'total_prontuarios_com_erro': 0,
            'total_erros_registrados': 0,
            'total_tipos_erro': 0,
            'media_erros_por_prontuario': 0.0
        }
    
    prontuarios_por_tipo = Counter()
    ocorrencias_por_tipo = Counter()
    
    tipos_erro_dict = get_tipos_erro_dict()
    
    total_erros_registrados = 0
    
    for p in prontuarios_com_erro:
        tipos_neste_prontuario = set()
        for erro in p.get('erros', []):
            tipo_erro = erro.get('tipo')
            if tipo_erro:
                tipos_neste_prontuario.add(tipo_erro)
                ocorrencias_por_tipo[tipo_erro] += 1
                total_erros_registrados += 1
        
        for tipo in tipos_neste_prontuario:
            prontuarios_por_tipo[tipo] += 1
    
    # Prepara os dados detalhados
    resultado = []
    for tipo_erro, qtd_prontuarios in prontuarios_por_tipo.most_common():
        info_tipo = tipos_erro_dict.get(tipo_erro, {})
        nome_exibicao = info_tipo.get('descricao', tipo_erro) # Usa a descrição como nome amigável
        cor = info_tipo.get('cor', '#6c757d')
        
        taxa_prontuarios = round(100 * qtd_prontuarios / total_prontuarios_com_erro, 1)
        total_ocorrencias = ocorrencias_por_tipo.get(tipo_erro, 0)
        
        media_por_prontuario = round(total_ocorrencias / qtd_prontuarios, 1) if qtd_prontuarios > 0 else 0.0
        
        resultado.append({
            'tipo': tipo_erro, # Código/Nome interno
            'nome': nome_exibicao, # Descrição amigável
            'prontuarios_com_erro': qtd_prontuarios,
            'taxa_prontuarios': taxa_prontuarios,
            'total_ocorrencias': total_ocorrencias,
            'media_por_prontuario': media_por_prontuario,
            'cor': cor
        })
    
    # Estatísticas gerais
    stats_gerais = {
        'total_prontuarios_com_erro': total_prontuarios_com_erro,
        'total_erros_registrados': total_erros_registrados,
        'total_tipos_erro': len(prontuarios_por_tipo),
        'media_erros_por_prontuario': round(total_erros_registrados / total_prontuarios_com_erro, 1) if total_prontuarios_com_erro > 0 else 0.0
    }
    
    return resultado, stats_gerais

def calcular_estatisticas_bd(prontuarios_obj):
    """Calcula estatísticas diretamente dos objetos do banco (para relatórios)"""
    total_por_status = {status: 0 for status in STATUS_OPCOES}
    erros_por_tipo = Counter()
    convenios = Counter()
    setores = Counter()
    
    for p in prontuarios_obj:
        if not p.status:
            continue
            
        status_normalizado = p.status.title().replace('Ao', 'ao')
        if status_normalizado in total_por_status:
            total_por_status[status_normalizado] += 1
            
        convenios[p.convenio] += 1
        setores[p.setor] += 1
        
        tipos_de_erro_neste_prontuario = set()
        for erro in p.erros:
            tipo_erro_nome = erro.tipo
            tipos_de_erro_neste_prontuario.add(tipo_erro_nome)
        
        for tipo_nome in tipos_de_erro_neste_prontuario:
            erros_por_tipo[tipo_nome] += 1 # Contagem de prontuários por tipo
    
    stats = {
        'total_por_status': total_por_status,
        'erros_por_tipo': dict(erros_por_tipo),
        'convenios': dict(convenios),
        'setores': dict(setores),
        'total_prontuarios_com_erro': sum(1 for p in prontuarios_obj if p.erros) 
    }
    
    # print(f"📊 ESTATÍSTICAS BD: {stats['total_prontuarios_com_erro']} prontuários com erro")
    return stats

# --- ROTAS DE LOGIN/LOGOUT/REGISTRO ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        # Verifica se usuário existe e a senha bate
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        
        return render_template('login.html', error="Usuário ou senha incorretos")

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/registrar_admin', methods=['GET', 'POST'])
def registrar_admin():
    # Rota para criar o primeiro usuário administrador
    if User.query.first():
        return "Usuário administrador já existe. Acesso restrito.", 403
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            return "Usuário já existe!"
            
        novo_usuario = User(username=username)
        novo_usuario.set_password(password)
        db.session.add(novo_usuario)
        db.session.commit()
        
        return redirect(url_for('login'))
        
    return render_template('register.html')


@app.route('/debug/verificar_erros')
@login_required
def debug_verificar_erros():
    """Rota para verificar rapidamente se os erros estão sendo salvos e carregados"""
    try:
        # Buscar o último prontuário salvo
        ultimo_prontuario = Prontuario.query.options(
            joinedload(Prontuario.erros)
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
    dt = _parse_any_date(value)
    return dt.strftime('%d/%m/%Y') if dt else '-'

# --- 5. ROTAS PRINCIPAIS ---

@app.route('/')
@login_required # Adicionado login_required
def index():
    try:
        print("🚀 INICIANDO DASHBOARD COMPLETO...")
        
        # Parâmetros de filtro
        ano_filter = request.args.get('ano', '')
        mes_filter = request.args.get('mes', '')
        periodo_filter = request.args.get('periodo', 'mes') # Padrão: Este Mês
        data_inicio_filter = request.args.get('data_inicio', '')
        data_fim_filter = request.args.get('data_fim', '')
        
        print(f"📋 FILTROS: periodo={periodo_filter}, ano={ano_filter}, mes={mes_filter}")

        # Query com todos os relacionamentos
        # Usamos joinedload para carregar tudo de uma vez
        query = Prontuario.query.options(
            joinedload(Prontuario.responsaveis),
            joinedload(Prontuario.erros).joinedload(Erro.responsavel),
            joinedload(Prontuario.erros).joinedload(Erro.categoria_erro)
        )

        # Lógica de Filtragem (Centralizada no helper de relatórios para DRY)
        def _aplicar_filtros_data(q, ano, mes, periodo, data_inicio, data_fim):
            hoje = datetime.now()
            
            # Filtro por período predefinido (se data_inicio/fim não for informado)
            if not data_inicio and not data_fim:
                start_date = None
                end_date = None
                if periodo == 'hoje':
                    start_date = hoje.replace(hour=0, minute=0, second=0, microsecond=0)
                elif periodo == 'semana':
                    start_date = hoje - timedelta(days=7)
                elif periodo == 'mes':
                    start_date = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                elif periodo == 'trimestre':
                    trimestre_atual = (hoje.month - 1) // 3 + 1
                    mes_inicio_trimestre = (trimestre_atual - 1) * 3 + 1
                    start_date = hoje.replace(month=mes_inicio_trimestre, day=1, hour=0, minute=0, second=0, microsecond=0)
                elif periodo == 'ano':
                    start_date = hoje.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                # 'todos' não aplica start_date
                
                if start_date:
                    q = q.filter(Prontuario.data_criacao >= start_date)

            # Filtro por data inicial e final (sobrescreve o filtro por período)
            if data_inicio:
                data_ini = _parse_any_date(data_inicio)
                if data_ini:
                    q = q.filter(Prontuario.data_criacao >= data_ini)
            if data_fim:
                data_fim_dt = _parse_any_date(data_fim)
                if data_fim_dt:
                    data_fim_dt = data_fim_dt.replace(hour=23, minute=59, second=59)
                    q = q.filter(Prontuario.data_criacao <= data_fim_dt)
            
            # Filtro por ano/mês (sobrescreve/complementa)
            if ano:
                q = q.filter(db.extract('year', Prontuario.data_criacao) == int(ano))
            if mes:
                q = q.filter(db.extract('month', Prontuario.data_criacao) == int(mes))

            return q

        query_filtrada = _aplicar_filtros_data(query, ano_filter, mes_filter, periodo_filter, data_inicio_filter, data_fim_filter)

        # Ordenar e executar
        prontuarios_obj = query_filtrada.order_by(Prontuario.data_criacao.desc()).all()
        prontuarios_lista = [prontuario_to_dict(p) for p in prontuarios_obj]
        
        print(f"📊 DADOS CARREGADOS: {len(prontuarios_lista)} prontuários")

        total = len(prontuarios_lista)
        
        if total == 0:
            print("⚠️  Nenhum dado encontrado")
            # Dados de fallback
            stats = {
                "aguardando_auditoria": 0, "em_auditoria": 0, "aguardando_correcao": 0,
                "entregue": 0, "taxa_erros": 0.0, "meta_taxa_erros": 10.0,
                "total_registrados_mes": 0, "tempo_medio_auditoria": 0.0,
                "taxa_conclusao": 0.0, "percentual_com_erros": 0.0,
                "media_erros_por_prontuario": 0.0,
                "total_prontuarios_com_erro": 0,
                "total_erros_registrados": 0,
                "total_tipos_erro": 0
            }
            
            stats_responsavel = []
            stats_convenio = []
            stats_top_motivos = []
            stats_top_causas = []
            stats_top_setores = []
            stats_motivos_detalhados = []
            stats_gerais_erros = {
                'total_prontuarios_com_erro': 0,
                'total_erros_registrados': 0,  
                'total_tipos_erro': 0,
                'media_erros_por_prontuario': 0.0
            }
            produtividade_mes = {"labels": [], "valores": [], "total_registrado": 0}
            stats_erros_mensais = {"labels": [], "valores": []}
            
        else:
            # 1. Calcular estatísticas de erros
            stats_motivos_detalhados, stats_gerais_erros = _calc_erros_por_motivo_detalhado(prontuarios_lista)
            
            # 2. Contar status
            status_count = Counter(p.get('status') for p in prontuarios_lista if p.get('status'))
            
            # 3. Calcular métricas principais
            com_erro = stats_gerais_erros.get('total_prontuarios_com_erro', 0)
            taxa_erros = round(100 * com_erro / total, 1) if total else 0.0

            # 4. Calcular outras estatísticas para gráficos
            stats_top_setores = _calc_taxa_erros_setor(prontuarios_lista)
            stats_top_motivos, stats_top_causas = _calc_top_erros(prontuarios_lista)
            stats_responsavel = _calc_taxa_erros_responsavel(prontuarios_lista)
            stats_convenio = _calc_taxa_erros_convenio(prontuarios_lista)
            
            # O cálculo de produtividade e timeline mensal usa o mês/ano atual ou filtros, dependendo de como a função helper está implementada
            hoje = datetime.now()
            produtividade_mes = _calc_produtividade_diaria_mes(prontuarios_lista, hoje.year, hoje.month)
            stats_erros_mensais = _calc_erros_timeline_mensal()
            
            # 5. Agrupar estatísticas
            stats = {
                "aguardando_auditoria": status_count['Aguardando Auditoria'] if 'Aguardando Auditoria' in status_count else 0,
                "em_auditoria": status_count['Em Auditoria'] if 'Em Auditoria' in status_count else 0,
                "aguardando_correcao": (status_count['Aguardando Correção'] if 'Aguardando Correção' in status_count else 0) + \
                                       (status_count['Aguardando Revisão'] if 'Aguardando Revisão' in status_count else 0),
                "entregue": status_count['Entregue ao Faturamento'] if 'Entregue ao Faturamento' in status_count else 0,
                "taxa_erros": taxa_erros,
                "meta_taxa_erros": 10.0,
                "total_registrados_mes": total,
                "tempo_medio_auditoria": 0.0, # Implementação mais complexa, por enquanto 0
                "taxa_conclusao": round(100 * (status_count['Entregue ao Faturamento'] if 'Entregue ao Faturamento' in status_count else 0) / total, 1) if total else 0.0,
                "percentual_com_erros": taxa_erros,
                # DADOS SINCRONIZADOS DE stats_gerais_erros
                "media_erros_por_prontuario": stats_gerais_erros.get('media_erros_por_prontuario', 0.0),
                "total_prontuarios_com_erro": stats_gerais_erros.get('total_prontuarios_com_erro', 0),
                "total_erros_registrados": stats_gerais_erros.get('total_erros_registrados', 0),
                "total_tipos_erro": stats_gerais_erros.get('total_tipos_erro', 0)
            }

            # print(f"📈 ESTATÍSTICAS: Total={total}, Com erro={com_erro}, Taxa={taxa_erros}%")

        # Carregar dados de configuração
        try:
            convenios_lista = [c.nome for c in Convenio.query.filter_by(status='ativo').order_by(Convenio.nome).all()]
            setores_lista = [s.nome for s in Setor.query.filter_by(status='ativo').order_by(Setor.nome).all()]
            responsaveis_lista = [r.nome for r in Responsavel.query.filter_by(status='ativo').order_by(Responsavel.nome).all()]
            tipos_erro_dict = get_tipos_erro_dict()
            categorias_erro_lista = [ce.to_dict() for ce in CategoriaErro.query.filter_by(status='ativo').order_by(CategoriaErro.nome).all()]
            
            # Anos disponíveis para filtro
            anos_query = db.session.query(db.extract('year', Prontuario.data_criacao)).distinct().order_by(db.extract('year', Prontuario.data_criacao).desc()).all()
            anos_disponiveis = [int(ano[0]) for ano in anos_query if ano[0] is not None]
            
        except Exception as e:
            print(f"⚠️  Erro em configurações: {e}")
            convenios_lista, setores_lista, responsaveis_lista = [], [], []
            tipos_erro_dict = {}
            categorias_erro_lista = []
            anos_disponiveis = []

        periodo_info = gerar_texto_periodo(ano_filter, mes_filter, periodo_filter, data_inicio_filter, data_fim_filter)
        
        # print(f"✅ RENDERIZANDO TEMPLATE com {total} prontuários e {len(stats_motivos_detalhados)} tipos de erro")

        return render_template('index.html', 
            periodo_info=periodo_info,
            stats=stats,
            stats_responsavel=stats_responsavel,
            stats_convenio=stats_convenio,
            stats_top_motivos=stats_top_motivos,
            stats_top_causas=stats_top_causas,
            stats_top_setores=stats_top_setores,
            stats_motivos_detalhados=stats_motivos_detalhados,
            stats_gerais_erros=stats_gerais_erros,
            dados_grafico_produtividade=produtividade_mes,
            dados_erros_mensais=stats_erros_mensais,
            convenios=convenios_lista,
            setores=setores_lista,
            responsaveis=responsaveis_lista,
            tipos_erro=tipos_erro_dict,
            categorias_erro=categorias_erro_lista,
            dados_raw=prontuarios_lista,
            anos_disponiveis=anos_disponiveis,
            ano_filter=ano_filter,
            mes_filter=mes_filter,
            periodo_filter=periodo_filter,
            data_inicio_filter=data_inicio_filter,
            data_fim_filter=data_fim_filter
        )

    except Exception as e:
        print(f"❌ ERRO CRÍTICO na rota /: {e}")
        import traceback
        traceback.print_exc()
        return f"Erro no servidor: {str(e)}", 500
        
@app.route('/prontuarios')
@login_required
def prontuarios():
    status_filter = request.args.get('status', '')
    convenio_filter = request.args.get('convenio', '')
    setor_filter = request.args.get('setor', '')
    
    # Query com joinedload para carregar todos os relacionamentos
    query = Prontuario.query.options(
        joinedload(Prontuario.responsaveis),
        joinedload(Prontuario.erros).joinedload(Erro.responsavel),
        joinedload(Prontuario.erros).joinedload(Erro.categoria_erro)
    )
    
    if status_filter:
        query = query.filter(Prontuario.status == status_filter)
    if convenio_filter:
        query = query.filter(Prontuario.convenio == convenio_filter)
    if setor_filter:
        query = query.filter(Prontuario.setor == setor_filter)
    
    prontuarios_obj = query.order_by(Prontuario.data_criacao.desc()).all()
    prontuarios_filtrados = [prontuario_to_dict(p) for p in prontuarios_obj]
    
    # Debug removido para otimizar, mas mantido para referência
    # total_erros = sum(len(p['erros']) for p in prontuarios_filtrados)
    # prontuarios_com_erro = sum(1 for p in prontuarios_filtrados if p['tem_erros'])
    
    convenios = [c.nome for c in Convenio.query.filter_by(status='ativo').order_by(Convenio.nome).all()]
    setores = [s.nome for s in Setor.query.filter_by(status='ativo').order_by(Setor.nome).all()]
    responsaveis = [r.nome for r in Responsavel.query.filter_by(status='ativo').order_by(Responsavel.nome).all()]
    tipos_erro_dict = get_tipos_erro_dict()
    
    return render_template('prontuarios.html',
                           prontuarios=prontuarios_filtrados,
                           status_opcoes=STATUS_OPCOES,
                           convenios=convenios,
                           setores=setores,
                           responsaveis=responsaveis,
                           tipos_erro=tipos_erro_dict,
                           status_filter=status_filter,
                           convenio_filter=convenio_filter,
                           setor_filter=setor_filter)

@app.route('/debug/prontuarios_com_erros')
@login_required
def debug_prontuarios_com_erros():
    """Rota para debug - verificar todos os prontuários e seus erros"""
    try:
        # Usamos joinedload para garantir que os erros estão carregados
        prontuarios = Prontuario.query.options(
            joinedload(Prontuario.erros)
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
        # Query com joinedload para carregar todos os relacionamentos
        prontuario = Prontuario.query.options(
            joinedload(Prontuario.responsaveis),
            joinedload(Prontuario.erros).joinedload(Erro.responsavel),
            joinedload(Prontuario.erros).joinedload(Erro.categoria_erro)
        ).get(prontuario_id)
        
        if not prontuario:
            return "Prontuário não encontrado", 404
        
        # Converter para dicionário para o template
        prontuario_dict = prontuario_to_dict(prontuario)
        
        # Carregar dados adicionais para o template
        convenios = [c.nome for c in Convenio.query.filter_by(status='ativo').order_by(Convenio.nome).all()]
        setores = [s.nome for s in Setor.query.filter_by(status='ativo').order_by(Setor.nome).all()]
        responsaveis = [r.nome for r in Responsavel.query.filter_by(status='ativo').order_by(Responsavel.nome).all()]
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
    # Esta rota pode ser simplificada removendo a lógica de filtro e delegando ao /
    # Mantenho a estrutura original, mas sem a lógica de filtro de período
    
    prontuarios_obj = Prontuario.query.options(
        joinedload(Prontuario.erros)
    ).all()
    prontuarios_lista = [prontuario_to_dict(p) for p in prontuarios_obj]
    
    total = len(prontuarios_lista)

    c_status = Counter(_norm_status(p) for p in prontuarios_lista)
    aguardando  = c_status.get("aguardando_auditoria", 0)
    em_aud      = c_status.get("em_auditoria", 0)
    para_corr   = c_status.get("aguardando_correcao", 0) + c_status.get("aguardando_revisao", 0)
    entregues   = c_status.get("entregue_faturamento", 0)

    com_erro = sum(1 for p in prontuarios_lista if _tem_erro(p))
    taxa_erros = round(100 * com_erro / total, 1) if total else 0.0

    META_TAXA_ERROS = 10.0

    hoje = datetime.now()
    produtividade = _calc_produtividade_diaria_mes(prontuarios_lista, hoje.year, hoje.month)
    tempos = _calc_tempos_medios(prontuarios_lista)
    erros_por_setor = _calc_taxa_erros_setor(prontuarios_lista)
    
    stats_gerais_erros = _calc_erros_por_motivo_detalhado(prontuarios_lista)[1]

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
            "media_erros_por_prontuario": stats_gerais_erros.get('media_erros_por_prontuario', 0.0),
            "total_prontuarios_com_erro": stats_gerais_erros.get('total_prontuarios_com_erro', 0),
            "total_erros_registrados": stats_gerais_erros.get('total_erros_registrados', 0),
            "total_tipos_erro": stats_gerais_erros.get('total_tipos_erro', 0)
        },
        "taxa_erros_setor": erros_por_setor,
        "produtividade_diaria_mes": produtividade,
        "tempos_medios": tempos,
    }
    return jsonify(payload)

@app.route('/relatorios')
@login_required
def relatorios():
    ano_filter = request.args.get('ano', '')
    mes_filter = request.args.get('mes', '')
    periodo_filter = request.args.get('periodo', '')
    data_inicio_filter = request.args.get('data_inicio', '')
    data_fim_filter = request.args.get('data_fim', '')
    
    # Query com joinedload para carregar todos os relacionamentos
    query = Prontuario.query.options(
        joinedload(Prontuario.responsaveis),
        joinedload(Prontuario.erros).joinedload(Erro.responsavel),
        joinedload(Prontuario.erros).joinedload(Erro.categoria_erro)
    ).order_by(Prontuario.data_criacao.desc())
    
    def _aplicar_filtros_data(q, ano, mes, periodo, data_inicio, data_fim):
        # ... [Implementação da função de filtro de data, idêntica à da rota index] ...
        hoje = datetime.now()
        
        # Define o período padrão se nenhum filtro for fornecido
        if not any([ano, mes, periodo, data_inicio, data_fim]):
            periodo = 'mes' # Default para 'Este Mês'
        
        # Filtro por período predefinido (se data_inicio/fim não for informado)
        if periodo:
            start_date = None
            end_date = None
            if periodo == 'hoje':
                start_date = hoje.replace(hour=0, minute=0, second=0, microsecond=0)
            elif periodo == 'ontem':
                start_date = (hoje - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = hoje.replace(hour=0, minute=0, second=0, microsecond=0)
            elif periodo == 'semana':
                start_date = (hoje - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
            elif periodo == 'mes':
                start_date = hoje.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            elif periodo == 'trimestre':
                trimestre_atual = (hoje.month - 1) // 3 + 1
                mes_inicio_trimestre = (trimestre_atual - 1) * 3 + 1
                start_date = hoje.replace(month=mes_inicio_trimestre, day=1, hour=0, minute=0, second=0, microsecond=0)
            elif periodo == 'ano':
                start_date = hoje.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            
            if start_date and end_date:
                q = q.filter(Prontuario.data_criacao >= start_date, Prontuario.data_criacao < end_date)
            elif start_date:
                q = q.filter(Prontuario.data_criacao >= start_date)

        # Filtro por data inicial e final
        if data_inicio:
            data_ini = _parse_any_date(data_inicio)
            if data_ini:
                q = q.filter(Prontuario.data_criacao >= data_ini)
        if data_fim:
            data_fim_dt = _parse_any_date(data_fim)
            if data_fim_dt:
                data_fim_dt = data_fim_dt.replace(hour=23, minute=59, second=59)
                q = q.filter(Prontuario.data_criacao <= data_fim_dt)
        
        # Filtro por ano/mês
        if ano:
            q = q.filter(db.extract('year', Prontuario.data_criacao) == int(ano))
        if mes:
            q = q.filter(db.extract('month', Prontuario.data_criacao) == int(mes))
            
        return q
    # ...
    query_filtrada = _aplicar_filtros_data(query, ano_filter, mes_filter, periodo_filter, data_inicio_filter, data_fim_filter)
    
    prontuarios_filtrados_obj = query_filtrada.all()
    prontuarios_filtrados = [prontuario_to_dict(p) for p in prontuarios_filtrados_obj]
    
    # print(f"📊 RELATÓRIO - Prontuários: {len(prontuarios_filtrados)}, Erros: {total_erros_relatorio}")
    
    anos_query = db.session.query(db.extract('year', Prontuario.data_criacao)).distinct().order_by(db.extract('year', Prontuario.data_criacao).desc()).limit(5)
    anos_disponiveis = [int(ano[0]) for ano in anos_query.all() if ano[0] is not None]
    
    meses_disponiveis = [
        ('01', 'Janeiro'), ('02', 'Fevereiro'), ('03', 'Março'), ('04', 'Abril'),
        ('05', 'Maio'), ('06', 'Junho'), ('07', 'Julho'), ('08', 'Agosto'),
        ('09', 'Setembro'), ('10', 'Outubro'), ('11', 'Novembro'), ('12', 'Dezembro')
    ]
        
    periodo_info = gerar_texto_periodo(
        ano_filter, 
        mes_filter, 
        periodo_filter,
        data_inicio_filter, 
        data_fim_filter
    )
    
    # Calculando estatísticas a partir dos objetos carregados
    stats = calcular_estatisticas_bd(prontuarios_filtrados_obj)
    stats_taxa_erro_responsavel = _calc_taxa_erros_responsavel(prontuarios_filtrados)
    stats_taxa_erro_convenio = _calc_taxa_erros_convenio(prontuarios_filtrados)
    
    tipos_erro_dict = get_tipos_erro_dict()
    
    return render_template('relatorios.html',
                           prontuarios=prontuarios_filtrados,
                           stats=stats,
                           tipos_erro=tipos_erro_dict,
                           anos_disponiveis=anos_disponiveis,
                           meses_disponiveis=meses_disponiveis,
                           periodo_info=periodo_info,
                           ano_filter=ano_filter,
                           mes_filter=mes_filter,
                           periodo_filter=periodo_filter,
                           data_inicio_filter=data_inicio_filter,
                           data_fim_filter=data_fim_filter,
                           stats_responsavel=stats_taxa_erro_responsavel,
                           stats_convenio=stats_taxa_erro_convenio)
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
        # Atualizar a data de envio ao faturamento se o status for final
        if novo_status == "Entregue ao Faturamento" and not prontuario.enviado_faturamento:
             prontuario.enviado_faturamento = datetime.now()
        
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
        
        # print("=== 🚀 NOVO SISTEMA DE LANÇAMENTO ===")
        # print(f"📥 Dados recebidos: {list(dados.keys())}")
        
        # 1. Validação de campos obrigatórios
        campos_obrigatorios = ['beneficiario', 'convenio', 'setor', 'atendimento', 'admissao']
        for campo in campos_obrigatorios:
            if not dados.get(campo):
                return jsonify({'sucesso': False, 'erro': f'Campo {campo} é obrigatório'}), 400
        
        # 2. Processamento de responsáveis e erros
        erros_processados = []
        responsaveis_dos_erros = set()
        
        if 'erros' in dados and isinstance(dados['erros'], list):
            for erro in dados['erros']:
                # Validação básica de erro
                if (isinstance(erro, dict) and 
                    erro.get('tipo') and 
                    erro.get('causa') and 
                    erro.get('responsavel_id')):
                    
                    erro_processado = {
                        'tipo': erro['tipo'], # Ex: '01.01' (Nome/Código do TipoErro)
                        'causa': erro['causa'],
                        'quantidade': int(erro.get('quantidade', 1)),
                        'responsavel_id': int(erro['responsavel_id'])
                    }
                    
                    erros_processados.append(erro_processado)
                    responsaveis_dos_erros.add(int(erro['responsavel_id']))

        # Responsáveis gerais (do formulário) + responsáveis dos erros
        responsaveis_ids_form = []
        if 'responsaveis' in dados:
            if isinstance(dados['responsaveis'], list):
                responsaveis_ids_form = [int(r) for r in dados['responsaveis'] if str(r).isdigit()]
            elif isinstance(dados['responsaveis'], str) and dados['responsaveis'].isdigit():
                responsaveis_ids_form = [int(dados['responsaveis'])]
                
        todos_responsaveis = set(responsaveis_ids_form) | responsaveis_dos_erros
        
        # print(f"👥 TODOS RESPONSÁVEIS ENVOLVIDOS: {todos_responsaveis}")
        
        # 3. Criação do prontuário
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
        db.session.flush() # Para obter o ID

        # 4. Associar responsáveis ao prontuário
        responsaveis_encontrados = []
        if todos_responsaveis:
            responsaveis_encontrados = Responsavel.query.filter(
                Responsavel.id.in_(list(todos_responsaveis))
            ).all()
            
            if responsaveis_encontrados:
                novo_prontuario.responsaveis.extend(responsaveis_encontrados)
                # print(f"✅ {len(responsaveis_encontrados)} responsável(eis) associado(s) ao prontuário")

        # 5. Adição de erros
        for erro_data in erros_processados:
            # Buscar CategoriaErro pelo nome (Tipo)
            categoria_erro = CategoriaErro.query.filter_by(
                nome=erro_data['tipo'], # Se 'tipo' vier com o nome da CategoriaErro
                status='ativo'
            ).first()

            # Se não encontrar pela CategoriaErro, tenta TipoErro
            tipo_erro_obj = TipoErro.query.filter_by(
                nome=erro_data['tipo'], # Assumindo que o campo 'tipo' no payload é o código/nome do TipoErro
                status='ativo'
            ).first()
            
            # Se categoria não encontrada, tenta encontrar pelo TipoErro e define um padrão
            if not categoria_erro and tipo_erro_obj:
                # Se for um TipoErro mas não uma CategoriaErro, não atribui categoria
                pass

            # O campo 'tipo' no modelo Erro é a string do nome/código
            tipo_para_erro_campo = tipo_erro_obj.nome if tipo_erro_obj else erro_data['tipo'] 

            # Criar múltiplos registros baseado na quantidade
            quantidade = erro_data.get('quantidade', 1)
            for _ in range(quantidade):
                novo_erro = Erro(
                    prontuario_id=novo_prontuario.id,
                    tipo=tipo_para_erro_campo, # Ex: '01.01'
                    causa=erro_data['causa'],
                    responsavel_id=erro_data['responsavel_id'],
                    categoria_erro_id=categoria_erro.id if categoria_erro else None # Atribui o ID da Categoria
                )
                db.session.add(novo_erro)
            
            # print(f"✅ Adicionado {quantidade} erro(s) do tipo: {erro_data['tipo']}")
        
        db.session.commit()
        
        # print(f"✅ PRONTUÁRIO SALVO NO BD! ID: {novo_prontuario.id}")
        
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

# Funções auxiliares de data já estão no escopo global e corrigidas

# --- NOVAS ROTAS PARA O SISTEMA DE CATEGORIAS ---
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
        # Usamos joinedload para buscar erros com responsáveis e categorias
        prontuario = Prontuario.query.options(
            joinedload(Prontuario.responsaveis),
            joinedload(Prontuario.erros).joinedload(Erro.responsavel),
            joinedload(Prontuario.erros).joinedload(Erro.categoria_erro)
        ).get(prontuario_id)
        
        if not prontuario:
            return jsonify({'erro': 'Prontuário não encontrado'}), 404
        
        # Retorna o dicionário completo do prontuário
        return jsonify(prontuario_to_dict(prontuario))
        
    except Exception as e:
        print(f"❌ Erro em api_prontuario_dados: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'erros': [], 'responsaveis': [], 'erro': str(e)}), 500

@app.route('/api/atualizar_erros_responsavel/<int:prontuario_id>', methods=['POST'])
@login_required
def api_atualizar_erros_responsavel(prontuario_id):
    try:
        prontuario = Prontuario.query.get(prontuario_id)
        if not prontuario:
            return jsonify({'sucesso': False, 'erro': 'Prontuário não encontrado'}), 404

        dados = request.get_json()
        
        # 1. Atualizar Responsáveis (Geral)
        if 'responsaveis' in dados:
            nomes_responsaveis = dados.get('responsaveis', [])
            if not isinstance(nomes_responsaveis, list):
                nomes_responsaveis = [nomes_responsaveis]
            
            prontuario.responsaveis.clear() # Limpa associações antigas
            if nomes_responsaveis:
                responsaveis_encontrados = Responsavel.query.filter(Responsavel.nome.in_(nomes_responsaveis)).all()
                prontuario.responsaveis.extend(responsaveis_encontrados)
        
        # 2. Atualizar Erros (Substituição Completa)
        if 'erros' in dados:
            Erro.query.filter_by(prontuario_id=prontuario_id).delete() # Remove todos os erros existentes
            
            for erro_data in dados['erros']:
                if erro_data.get('tipo') and erro_data.get('causa'):
                    # Tenta encontrar a CategoriaErro e o Responsável pelo ID
                    responsavel_id = erro_data.get('responsavel_id')
                    categoria_id = erro_data.get('categoria_erro_id')

                    # Criar múltiplos registros (se quantidade for 1 ou mais)
                    quantidade = int(erro_data.get('quantidade', 1))
                    for _ in range(quantidade):
                        novo_erro = Erro(
                            prontuario_id=prontuario_id,
                            tipo=erro_data['tipo'],
                            causa=erro_data['causa'],
                            responsavel_id=responsavel_id,
                            categoria_erro_id=categoria_id
                        )
                        db.session.add(novo_erro)
        
        prontuario.data_atualizacao = datetime.now()
        db.session.commit()
        
        return jsonify({'sucesso': True})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'sucesso': False, 'erro': str(e)}), 500

@app.route('/api/adicionar_erro_unico/<int:prontuario_id>', methods=['POST'])
@login_required
def api_adicionar_erro_unico(prontuario_id):
    try:
        dados = request.get_json()
        tipo_erro = dados.get('tipo_erro')
        causa = dados.get('causa')
        responsavel_id = dados.get('responsavel_id') # Adicionado
        categoria_id = dados.get('categoria_erro_id') # Adicionado
        
        if not tipo_erro or not causa:
            return jsonify({'sucesso': False, 'erro': 'Tipo e causa são obrigatórios'}), 400
        
        prontuario = Prontuario.query.get(prontuario_id)
        if not prontuario:
            return jsonify({'sucesso': False, 'erro': 'Prontuário não encontrado'}), 404
        
        novo_erro = Erro(
            prontuario_id=prontuario_id,
            tipo=tipo_erro,
            causa=causa,
            responsavel_id=responsavel_id,
            categoria_erro_id=categoria_id
        )
        db.session.add(novo_erro)
        
        prontuario.data_atualizacao = datetime.now()
        db.session.commit()
        
        return jsonify({'sucesso': True, 'erro_id': novo_erro.id})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'sucesso': False, 'erro': str(e)}), 500

@app.route('/api/remover_erro_unico/<int:erro_id>', methods=['DELETE']) # Rota ajustada para usar ID do Erro
@login_required
def api_remover_erro_unico(erro_id):
    try:
        erro = Erro.query.get(erro_id)
        
        if not erro:
            return jsonify({'sucesso': False, 'erro': 'Erro não encontrado para remover'}), 404
            
        prontuario_id = erro.prontuario_id
        prontuario = Prontuario.query.get(prontuario_id)
        
        db.session.delete(erro)
        
        if prontuario:
            prontuario.data_atualizacao = datetime.now()
            
        db.session.commit()
        
        return jsonify({'sucesso': True})
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'sucesso': False, 'erro': str(e)}), 500

# --- 7. APIs DE CONFIGURAÇÕES ---
# Mantidas as APIs de configurações (convenios, setores, responsaveis, causas, tipos_erro)

@app.route('/api/configuracoes/<string:tipo>', methods=['GET', 'POST'])
@login_required
def api_configuracoes(tipo):
    model_map = {
        'convenios': Convenio,
        'setores': Setor,
        'responsaveis': Responsavel,
        'categorias_erro': CategoriaErro
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
                if tipo == 'categorias_erro':
                    item.codigo = dados.get('codigo', item.codigo)
                    item.descricao = dados.get('descricao', '')
                    item.cor = dados.get('cor', '#3498db')
                    
            else:
                if tipo == 'convenios':
                    item = Convenio(nome=dados['nome'], status=dados.get('status', 'ativo'))
                elif tipo == 'setores':
                    item = Setor(nome=dados['nome'], status=dados.get('status', 'ativo'), descricao=dados.get('descricao', ''))
                elif tipo == 'responsaveis':
                    item = Responsavel(nome=dados['nome'], status=dados.get('status', 'ativo'), funcao=dados.get('funcao', ''), setor_resp=dados.get('setor', ''))
                elif tipo == 'categorias_erro':
                    if not dados.get('codigo'):
                        return jsonify({'sucesso': False, 'erro': 'Código é obrigatório para Categoria de Erro'}), 400
                    item = CategoriaErro(
                        nome=dados['nome'], 
                        codigo=dados['codigo'], 
                        descricao=dados.get('descricao', ''), 
                        cor=dados.get('cor', '#3498db'),
                        status=dados.get('status', 'ativo')
                    )
                db.session.add(item)
            
            db.session.commit()
            return jsonify({'sucesso': True, 'item': item.to_dict()})
        except Exception as e:
            db.session.rollback()
            return jsonify({'sucesso': False, 'erro': str(e)}), 500

@app.route('/api/configuracoes/<string:tipo>/<int:item_id>', methods=['DELETE'])
@login_required
def api_excluir_configuracao(tipo, item_id):
    model_map = {
        'convenios': Convenio,
        'setores': Setor,
        'responsaveis': Responsavel,
        'causas': Causa,
        'tipos_erro': TipoErro,
        'categorias_erro': CategoriaErro
    }
    if tipo not in model_map:
        return jsonify({'sucesso': False, 'erro': 'Tipo de configuração inválido'}), 404
    
    Model = model_map[tipo]

    try:
        item = Model.query.get(item_id)
        if not item:
            return jsonify({'sucesso': False, 'erro': 'Item não encontrado'}), 404
        
        # Lógica especial para Responsável/CategoriaErro (tabelas de associação)
        if tipo == 'responsaveis':
            # Remove associações antes de deletar o responsável
            item.categorias_erro.clear()
            item.prontuarios.clear()
        
        db.session.delete(item)
        db.session.commit()
        return jsonify({'sucesso': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'sucesso': False, 'erro': str(e)}), 500

@app.route('/api/configuracoes/causas', methods=['GET', 'POST'])
@login_required
def api_causas():
    if request.method == 'GET':
        items = Causa.query.join(TipoErro).order_by(TipoErro.nome, Causa.descricao).all()
        return jsonify([item.to_dict() for item in items])
    
    if request.method == 'POST':
        dados = request.get_json()
        if not dados.get('descricao') or not dados.get('tipo_erro_id'):
            return jsonify({'sucesso': False, 'erro': 'Descrição e ID do Tipo de Erro são obrigatórios'}), 400
        
        try:
            if dados.get('id'):
                item = Causa.query.get(dados['id'])
                if not item:
                    return jsonify({'sucesso': False, 'erro': 'Causa não encontrada'}), 404
                item.descricao = dados['descricao']
                item.tipo_erro_id = dados['tipo_erro_id']
                item.status = dados.get('status', 'ativo')
            else:
                item = Causa(
                    descricao=dados['descricao'],
                    tipo_erro_id=dados['tipo_erro_id'],
                    status=dados.get('status', 'ativo')
                )
                db.session.add(item)
            
            db.session.commit()
            return jsonify({'sucesso': True, 'item': item.to_dict()})
        except Exception as e:
            db.session.rollback()
            return jsonify({'sucesso': False, 'erro': str(e)}), 500

@app.route('/api/configuracoes/tipos_erro', methods=['GET', 'POST'])
@login_required
def api_tipos_erro():
    if request.method == 'GET':
        items = TipoErro.query.order_by(TipoErro.nome).all()
        return jsonify([item.to_dict() for item in items])
    
    if request.method == 'POST':
        dados = request.get_json()
        # 'nome' do TipoErro é o código (ex: '01.01'), 'descricao' é o nome amigável
        if not dados.get('nome') or not dados.get('descricao'):
            return jsonify({'sucesso': False, 'erro': 'Código e Nome (Descrição) são obrigatórios'}), 400
        
        try:
            if dados.get('id'):
                item = TipoErro.query.get(dados['id'])
                if not item:
                    return jsonify({'sucesso': False, 'erro': 'Item não encontrado'}), 404
                item.nome = dados['nome']
                item.descricao = dados.get('descricao', '')
                item.cor = dados.get('cor', '#dc3545')
                item.status = dados.get('status', 'ativo')
            else:
                existente = TipoErro.query.filter_by(nome=dados['nome']).first()
                if existente:
                    return jsonify({'sucesso': False, 'erro': 'Já existe um motivo com este código.'}), 409
                    
                item = TipoErro(
                    nome=dados['nome'],
                    descricao=dados.get('descricao', ''),
                    cor=dados.get('cor', '#dc3545'),
                    status=dados.get('status', 'ativo')
                )
                db.session.add(item)
            
            db.session.commit()
            return jsonify({'sucesso': True, 'item': item.to_dict()})
        except Exception as e:
            db.session.rollback()
            return jsonify({'sucesso': False, 'erro': str(e)}), 500


# Rota de população de causas padrão REMOVIDA, conforme solicitado: @app.route('/api/popular_causas', methods=['POST'])

@app.route('/configuracoes')
@login_required
def configuracoes():
    # Usando .all() dentro do list comprehension para execução imediata da query
    convenios = [c.to_dict() for c in Convenio.query.order_by(Convenio.nome).all()]
    setores = [s.to_dict() for s in Setor.query.order_by(Setor.nome).all()]
    
    # Carregar responsáveis com as categorias associadas
    responsaveis_obj = Responsavel.query.options(joinedload(Responsavel.categorias_erro)).order_by(Responsavel.nome).all()
    responsaveis = [r.to_dict() for r in responsaveis_obj]
    
    tipos_erro_lista = [t.to_dict() for t in TipoErro.query.order_by(TipoErro.nome).all()]
    tipos_erro_dict = get_tipos_erro_dict() 
    
    categorias_erro_lista = [c.to_dict() for c in CategoriaErro.query.order_by(CategoriaErro.nome).all()]
    
    # Carregar causas com o TipoErro associado
    causas_obj = Causa.query.options(joinedload(Causa.tipo_erro)).order_by(Causa.descricao).all()
    causas_lista = [c.to_dict() for c in causas_obj]

    return render_template(
        'configuracoes.html',
        convenios=convenios,
        setores=setores,
        responsaveis=responsaveis,
        tipos_erro_lista=tipos_erro_lista,
        tipos_erro=tipos_erro_dict,
        causas=causas_lista,
        categorias_erro_lista=categorias_erro_lista
    )


@app.route('/alimentacao')
@login_required
def alimentacao():
    try:
        # print("🔍 Carregando dados para a página de alimentação...")
        
        # Carregar listas de opções ativas
        convenios = [c.nome for c in Convenio.query.filter_by(status='ativo').order_by(Convenio.nome).all()]
        setores = [s.nome for s in Setor.query.filter_by(status='ativo').order_by(Setor.nome).all()]
        responsaveis_db = Responsavel.query.filter_by(status='ativo').order_by(Responsavel.nome).all()
        responsaveis = [{'id': r.id, 'nome': r.nome} for r in responsaveis_db]
        
        # Carregar dicionário de tipos de erro (com causas aninhadas)
        tipos_erro_dict = get_tipos_erro_dict()
        
        # Carregar lista de categorias de erro (para associação nos erros)
        categorias_erro = [ce.to_dict() for ce in CategoriaErro.query.filter_by(status='ativo').order_by(CategoriaErro.nome).all()]
        
        # print(f"✅ Dados carregados. Convenios: {len(convenios)}, Responsáveis: {len(responsaveis)}, Tipos Erro: {len(tipos_erro_dict)}")
        
        return render_template('alimentacao.html',
                                 convenios=convenios,
                                 setores=setores,
                                 responsaveis=responsaveis,
                                 tipos_erro=tipos_erro_dict,
                                 categorias_erro=categorias_erro, # Passando categorias também
                                 status_opcoes=STATUS_OPCOES
                                 )
                                 
    except Exception as e:
        print(f"❌ ERRO na rota /alimentacao: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Fallback com dados básicos em caso de erro no banco
        return render_template('alimentacao.html',
                                 convenios=['Erro no BD'],
                                 setores=['Erro no BD'],
                                 responsaveis=[{'id': 1, 'nome': 'Erro no BD'}],
                                 tipos_erro={},
                                 categorias_erro=[],
                                 status_opcoes=STATUS_OPCOES
                                 )

# --- 8. INICIALIZAÇÃO DA APLICAÇÃO ---
if __name__ == '__main__':
    with app.app_context():
        print("Verificando e criando banco de dados se necessário...")
        try:
            # Garante que as tabelas existem. Não popula nem apaga dados existentes.
            db.create_all() 
            print(f"Banco de dados está em: {db_path}")
            
            inspector = db.inspect(db.engine)
            tabelas = inspector.get_table_names()
            print(f"Tabelas encontradas: {tabelas}")
            
            # Verificação básica de usuário admin - Rota /registrar_admin ainda está disponível se não houver usuários
            if not User.query.first():
                 print("⚠️ ALERTA: NENHUM USUÁRIO ENCONTRADO. Acesse /registrar_admin para criar o primeiro usuário.")
                
        except Exception as e:
            print(f"ERRO CRÍTICO AO INICIAR O BANCO DE DADOS: {e}")
            print("Verifique se o diretório 'data' tem permissão de escrita.")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
