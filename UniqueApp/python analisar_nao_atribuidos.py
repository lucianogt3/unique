from collections import Counter

# ANALISE DO LOG COMPLETO
log_content = """
[SEU LOG COMPLETO AQUI]
"""

def analisar_nao_atribuidos_rapido(log_text):
    print("ANALISE RAPIDA - NAO ATRIBUIDOS")
    print("=" * 50)
    
    # Encontra todos os casos de "Nao atribuido"
    import re
    nao_atribuidos = re.findall(r'Responsável ID: None, Nome: Não atribuído', log_text)
    total_nao_atribuidos = len(nao_atribuidos)
    
    print(f"TOTAL DE NAO ATRIBUIDOS: {total_nao_atribuidos}")
    print(f"PRONTUARIOS ANALISADOS: 167")
    
    # Encontra prontuarios especificos com nao atribuidos
    prontuarios_com_nao_atribuidos = []
    padrao_prontuario = re.compile(r'DEBUG prontuario_to_dict - ID: (\d+).*?Total de erros: (\d+).*?Responsável ID: None, Nome: Não atribuído', re.DOTALL)
    
    for match in padrao_prontuario.findall(log_text):
        prontuarios_com_nao_atribuidos.append(int(match[0]))
    
    print(f"PRONTUARIOS COM NAO ATRIBUIDOS: {len(prontuarios_com_nao_atribuidos)}")
    print(f"PRONTUARIOS AFETADOS: {sorted(prontuarios_com_nao_atribuidos)[:20]}...")
    
    # Distribuicao por faixa de IDs
    print(f"\nDISTRIBUICAO POR FAIXA DE PRONTUARIOS:")
    faixas = {
        "1-50": 0,
        "51-100": 0, 
        "101-167": 0
    }
    
    for pront_id in prontuarios_com_nao_atribuidos:
        if pront_id <= 50:
            faixas["1-50"] += 1
        elif pront_id <= 100:
            faixas["51-100"] += 1
        else:
            faixas["101-167"] += 1
    
    for faixa, quantidade in faixas.items():
        print(f"  {faixa}: {quantidade} prontuarios")

# Executar analise
analisar_nao_atribuidos_rapido(log_content)