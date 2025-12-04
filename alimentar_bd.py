# alimentar_banco.py
import os
import pandas as pd
from datetime import datetime
from app import app, db
from app import Convenio, Setor, Responsavel, TipoErro, Causa, Prontuario, Erro

# --- DADOS DE CONFIGURAÇÃO (EMBUTIDOS) ---

CONVENIOS_PADRAO = [
    "Unimed", "SulAmérica", "Bradesco Saúde", "Amil", "NotreDame Intermédica",
    "Prevent Senior", "São Cristóvão", "Santa Casa", "Outros"
]
SETORES_PADRAO = [
    "UTI", "Internação", "Pronto Socorro", "Centro Cirúrgico",
    "Ambulatório", "Emergência", "Hospital Dia"
]
RESPONSAVEIS_PADRAO = [
    "Auditor 1", "Auditor 2", "Auditor 3", "Enfermeiro A", "Enfermeiro B",
    "Médico A", "Médico B", "Coordenador"
]

# Mapa completo de Tipos de Erro (11 tipos)
TIPOS_ERRO_PADRAO = {
    'documentacao': {'nome': 'Documentação', 'cor': '#0d6efd'},
    'registro': {'nome': 'Registro', 'cor': '#6610f2'},
    'procedimento': {'nome': 'Procedimento', 'cor': '#0dcaf0'},
    'codificacao': {'nome': 'Codificação', 'cor': '#6f42c1'},
    'faturamento': {'nome': 'Faturamento', 'cor': '#d63384'},
    'prazo': {'nome': 'Prazo', 'cor': '#dc3545'},
    'materiais': {'nome': 'Materiais', 'cor': '#198754'},
    'medicamentos': {'nome': 'Medicamentos', 'cor': '#20c997'},
    'taxas': {'nome': 'Taxas', 'cor': '#ffc107'},
    'diárias': {'nome': 'Diárias', 'cor': '#6c757d'},
    'visitas/interconsultas': {'nome': 'Visitas/Interconsultas', 'cor': '#fd7e14'}
}

# Mapa de Causas (138 + as do CSV)
CAUSAS_PADRONIZADAS = {
    'documentacao': [
        "Aguardando justificativa", "Carimbo e/ou assinatura em falta", "Carimbo em evolução incorreto",
        "Assinatura em falta", "Carimbo em falta", "Falta carimbo/assinatura em evolução",
        "Falta carimbo/assinatura em prescrição", "Falta carimbo/assinatura em evolução de curativo",
        "Falta carimbo/assinatura em procedimento", "Ausência de carimbo/assinatura", "Documentação não carimbada",
        "Evolução sem carimbo/assinatura", "Prescrição sem carimbo/assinatura", "Folha de emergência sem checagem",
        "Relatorio enf não impresso", "OXIGENIOTERAPIA SEM COBRAR", "FALTA AUTORIZAÇÃO DE DIARIAS"
    ],
    'registro': [
        "Data/horário incorreto na evolução", "Data de admissão incorreta", "Horário de alta incorreto",
        "Balanço hídrico incorreto", "Dados clínicos inconsistentes", "Informações divergentes no prontuário",
        "Registro de procedimento incorreto", "Medidas clínicas incorretas", "Oxigenoterapia registrada incorretamente",
        "Precaução registrada incorretamente", "Evolução com dados inconsistentes", "Horário de medicação incorreto",
        "Horário de procedimento incorreto", "Horário de transferência incorreto", "Proveniência do paciente incorreta",
        "Sequência cronológica incorreta", "Valores de glicemia incorretos", "Litragem de O2 incorreta",
        "Tamanho de curativo incorreto", "Material de punção não registrado", "Retirada de dispositivo não registrada",
        "Início/término de terapia não registrado", "Dados de ventilação incorretos", "Irrigação vesical incorreta",
        "Balanço de medicação incorreto", "Horário de plantão incorreto", "Transferência setorial incorreta",
        "Admissão UTI incorreta", "Procedimento CC incorreto", "Hemodiálise registrada incorretamente",
        "Evolução com rasura", "Dados de punção incorretos", "Horário extubação incorreto",
        "Retirada de dreno não registrada", "Nefrostomia não registrada", "Passagem de SNE incorreta",
        "Curativo registrado incorretamente", "Procedimento AVC não registrado", "Terapia intravenosa incorreta",
        "Sinais vitais incorretos", "Dieta registrada incorretamente", "Chegada no leito incorreta",
        "COBRANÇA INDEVIDA"
    ],
    'procedimento': [
        "Evolução em falta", "Evolução diária em falta", "Evolução de alta em falta", "Evolução de admissão em falta",
        "Evolução de curativo em falta", "Evolução de procedimento em falta", "Evolução de punção em falta",
        "Evolução médica em falta", "Evolução de enfermagem em falta", "Evolução não impressa",
        "Boletim de procedimento em falta", "Descritivo cirúrgico em falta", "Prescrição em falta",
        "Prescrição de curativo em falta", "Prescrição de material em falta", "Prescrição de medicação em falta",
        "Folha de gasto incompleta", "Material de centro cirúrgico em falta", "Equipamento não prescrito",
        "Balanço hídrico em falta", "Autorização em falta", "Relatório em falta", "Glicemia não registrada",
        "Medicação não registrada", "Procedimento não registrado", "Punção não registrada", "Curativo não registrado",
        "Dreno não registrado", "Sonda não registrada", "Oxigenoterapia não registrada",
        "Terapia intravenosa não registrada", "Ventilação não registrada", "Hemodiálise não registrada",
        "Transferência não registrada", "Plantão não registrado", "Material não informado",
        "Quantidade de material não informada", "Justificativa de procedimento em falta", "Justificativa de medicação em falta",
        "Checagem em falta", "Folha de irrigação em falta", "Folha de emergência em falta",
        "Relatório recuperação em falta", "Documentação OPME em falta", "Evolução lesão em falta",
        "Procedimento prostática em falta", "Fisioterapia não autorizada", "Terapia não registrada",
        "2 º PROCEDIMENTO", "COBRAR ANESTESISTA", "COBRAR AUXILIAR CC"
    ],
    'codificacao': [
        "Cadastro de cirurgia incompatível", "Cadastro de cirurgia incorreto", "Nome da cirurgia incorreto",
        "Registro de cirurgia incorreto", "Descritivo cirúrgico divergente", "Cirurgia registrada incorretamente",
        "Procedimento codificado incorretamente", "Ficha de gasto divergente"
    ],
    'faturamento': [
        "Guia não executada", "Serviços não faturados"
    ],
    'prazo': [
        "Ausência de documentação", "Ausência de evolução", "Ausência de prescrição", "Ausência de registro",
        "Ausência de checagem", "Ausência de justificativa", "Ausência de informação", "Documentação não impressa",
        "Registro em atraso", "Checagem pendente", "Justificativa pendente", "Informação pendente",
        "Preenchimento incompleto", "Documentação incompleta", "Registro incompleto", "Checagem incompleta",
        "Tempo de procedimento incorreto", "Horário inconsistentes", "Cronologia incorreta", "Prazo de registro vencido",
        "Documentação fora do prazo", "Checagem fora do prazo", "Justificativa fora do prazo", "Informação fora do prazo"
    ],
    'materiais': [
        "MATERIAL NÃO COBRADO", "MATERIAL NÃO AUTORIZADO", "MATERIAL SEM AUTORIZAÇÃO"
    ],
    'medicamentos': [
        "MEDICAÇÃO NÃO COBRADO", "MEDICAÇÃO NÃO COBRADA"
    ],
    'taxas': [
        "TX ALIMENTAÇÃO", "TX INTENCIFICADOR DE IMAGEM"
    ],
    'diárias': [
        "DIARIA NÃO COBRADA"
    ],
    'visitas/interconsultas': [
        "COBRAR VISITA INFECTO"
    ]
}

# Mapa para encontrar o 'tipo_nome' a partir da 'causa_descricao'
MAPA_CAUSA_PARA_TIPO_NOME = {}
for tipo_key, causas_lista in CAUSAS_PADRONIZADAS.items():
    nome_tipo = TIPOS_ERRO_PADRAO[tipo_key]['nome']
    for causa_desc in causas_lista:
        MAPA_CAUSA_PARA_TIPO_NOME[causa_desc.strip().lower()] = nome_tipo


def _parse_any_date_for_migration(s):
    if not s: return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        try:
            d, m, y = s.split('/')
            return datetime(int(y), int(m), int(d))
        except Exception:
            try:
                y, m, d = s.split('-')
                return datetime(int(y), int(m), int(d))
            except Exception:
                return None
def normalize_key(text):
    return str(text).strip().lower()

def main():
    with app.app_context():
        print("=== MIGRAÇÃO INICIADA ===")
        # 1. Apagar e recriar tabelas
        db.drop_all()
        db.create_all()
        print("✅ Banco criado")

        # 2. Migrar Configurações
        print("📋 Migrando configurações...")
        tipos_erro_map = {} # para consulta rápida
        
        # Migrar Tipos de Erro
        for tipo_key, tipo_info in TIPOS_ERRO_PADRAO.items():
            novo_tipo = TipoErro(
                nome=tipo_info['nome'], # Ex: "Documentação"
                descricao=f"Erros relacionados a {tipo_info['nome'].lower()}",
                cor=tipo_info.get('cor', '#dc3545'),
                status='ativo'
            )
            db.session.add(novo_tipo)
        db.session.commit()
        
        tipos_salvos = TipoErro.query.all()
        tipos_erro_map_lower = {t.nome.lower(): t.id for t in tipos_salvos} # ex: 'documentação' -> 1
        print(f"  -> {len(tipos_erro_map_lower)} Tipos de Erro migrados.")

        # Migrar Causas
        causas_count = 0
        for tipo_key, causas_lista in CAUSAS_PADRONIZADAS.items():
            tipo_nome = TIPOS_ERRO_PADRAO[tipo_key]['nome']
            tipo_id = tipos_erro_map_lower.get(tipo_nome.lower())
            
            if not tipo_id:
                print(f"  ERRO FATAL: Não foi possível encontrar o ID para o tipo '{tipo_nome}'")
                continue
                
            for causa_desc in causas_lista:
                nova_causa = Causa(
                    descricao=causa_desc,
                    status='ativo',
                    tipo_erro_id=tipo_id
                )
                db.session.add(nova_causa)
                causas_count += 1
        print(f"  -> {causas_count} Causas migradas.")

        # Migrar Convenios, Setores, Responsaveis
        for nome_conv in CONVENIOS_PADRAO:
            db.session.add(Convenio(nome=nome_conv))
        print(f"  -> {len(CONVENIOS_PADRAO)} Convênios migrados.")
        
        for nome_setor in SETORES_PADRAO:
            db.session.add(Setor(nome=nome_setor, descricao=f'Setor de {nome_setor}'))
        print(f"  -> {len(SETORES_PADRAO)} Setores migrados.")

        for nome_resp in RESPONSAVEIS_PADRAO:
            funcao = 'Auditor' if 'Auditor' in nome_resp else 'Enfermeiro' if 'Enfermeiro' in nome_resp else 'Médico' if 'Médico' in nome_resp else 'Coordenador'
            setor_resp = 'Auditoria' if 'Auditor' in nome_resp else 'Enfermagem' if 'Enfermeiro' in nome_resp else 'Médico' if 'Médico' in nome_resp else 'Coordenação'
            db.session.add(Responsavel(nome=nome_resp, funcao=funcao, setor_resp=setor_resp))
        print(f"  -> {len(RESPONSAVEIS_PADRAO)} Responsáveis migrados.")
        
        db.session.commit()
        print("✅ Configurações migradas!")

        # 3. Migrar Prontuários do CSV
        print("📁 Migrando prontuários do CSV...")
        csv_path = 'Auditoria unique - lu.xlsx - OUTUBRO 2025 HU.csv'
        try:
            df = pd.read_csv(csv_path)
            df = df.fillna('')
            grouped = df.groupby('Atendimento')
            total_prontuarios = len(grouped)
            print(f"📊 Encontrados {total_prontuarios} prontuários únicos no CSV.")
            
            count = 0
            for atendimento_id, erros_df in grouped:
                first_row = erros_df.iloc[0]
                
                novo_prontuario = Prontuario(
                    beneficiario=first_row['Beneficiario'],
                    convenio=first_row['Convênio'],
                    setor=first_row['Setor'],
                    atendimento=str(atendimento_id),
                    responsavel=first_row['Responsavel'],
                    status=first_row['STATUS'] or first_row['Status'] or 'Aguardando Auditoria',
                    observacao='',
                    
                    admissao=_parse_any_date_for_migration(first_row['Admissão']),
                    alta=_parse_any_date_for_migration(first_row['Alta']),
                    recebimento_prontuario=_parse_any_date_for_migration(first_row['Recebimento do Prontuário']),
                    inicio_auditoria=_parse_any_date_for_migration(first_row['Início da Auditoria']),
                    enviado_faturamento=_parse_any_date_for_migration(first_row['Envio para Correção']),
                )
                
                for erro_desc in erros_df['Causa']:
                    if not erro_desc:
                        continue
                    
                    erro_desc_limpa = str(erro_desc).strip()
                    chave_causa = normalize_key(erro_desc_limpa)
                    
                    # Encontra o Nome do Tipo (ex: "Materiais")
                    tipo_nome = MAPA_CAUSA_PARA_TIPO_NOME.get(chave_causa, 'Documentação')

                    novo_erro = Erro(
                        tipo=tipo_nome,
                        causa=erro_desc_limpa
                    )
                    novo_prontuario.erros.append(novo_erro)
                
                db.session.add(novo_prontuario)
                count += 1
                if count % 20 == 0:
                    print(f"  ⏳ Processando {count}/{total_prontuarios}...")

            db.session.commit()
            print(f"✅ Migração concluída! {count} prontuários processados.")
            
            total_no_bd = db.session.query(func.count(Prontuario.id)).scalar()
            print(f"📈 Prontuários no banco: {total_no_bd}")

        except FileNotFoundError:
            print(f"❌ ERRO FATAL: O arquivo CSV '{csv_path}' não foi encontrado.")
            print("Por favor, coloque o arquivo 'Auditoria unique - lu.xlsx - OUTUBRO 2025 HU.csv' na mesma pasta do script.")
        except Exception as e:
            db.session.rollback()
            print(f"❌ ERRO DURANTE A MIGRAÇÃO DOS PRONTUÁRIOS: {e}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    main()