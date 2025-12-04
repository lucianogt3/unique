# corrigir_json_final.py
import json
import re

def corrigir_problema_especifico():
    print("Corrigindo problema específico...")
    
    with open('data/prontuarios.json', 'r', encoding='utf-8') as f:
        linhas = f.readlines()
    
    # Corrigir o problema na linha 3406-3407
    if len(linhas) > 3406:
        # Linha 3406: "  }" deve virar "  },"
        if linhas[3406].strip() == '}':
            linhas[3406] = '  },\n'
            print("✅ Vírgula adicionada na linha 3407")
        
        # Também verificar se há outros problemas similares
        for i in range(len(linhas) - 1):
            if linhas[i].strip() == '}' and linhas[i + 1].strip() == '[':
                linhas[i] = linhas[i].rstrip() + ',\n'
                print(f"✅ Vírgula adicionada na linha {i + 1}")
    
    # Salvar arquivo corrigido
    with open('data/prontuarios_corrigido.json', 'w', encoding='utf-8') as f:
        f.writelines(linhas)
    
    # Validar
    try:
        with open('data/prontuarios_corrigido.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"✅ JSON corrigido com sucesso! Total de registros: {len(data)}")
        return True
    except json.JSONDecodeError as e:
        print(f"❌ Ainda há erro: {e}")
        print("Tentando estratégia alternativa...")
        return corrigir_com_estrategia_alternativa()

def corrigir_com_estrategia_alternativa():
    """Estratégia mais agressiva para corrigir o JSON"""
    print("Aplicando correção alternativa...")
    
    with open('data/prontuarios.json', 'r', encoding='utf-8') as f:
        conteudo = f.read()
    
    # Estratégia: encontrar todos os padrões problemáticos
    # 1. } seguido de [ (sem vírgula)
    padrao1 = r'\}\s*\[\s*\{'
    substituicao1 = '}, [{'
    conteudo = re.sub(padrao1, substituicao1, conteudo)
    
    # 2. } seguido de { (sem vírgula)  
    padrao2 = r'\}\s*\{'
    substituicao2 = '}, {'
    conteudo = re.sub(padrao2, substituicao2, conteudo)
    
    # 3. ] seguido de [ (sem vírgula)
    padrao3 = r'\]\s*\[\s*'
    substituicao3 = '], ['
    conteudo = re.sub(padrao3, substituicao3, conteudo)
    
    # Salvar
    with open('data/prontuarios_corrigido2.json', 'w', encoding='utf-8') as f:
        f.write(conteudo)
    
    # Validar
    try:
        with open('data/prontuarios_corrigido2.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"✅ JSON corrigido com sucesso! Total de registros: {len(data)}")
        return True
    except json.JSONDecodeError as e:
        print(f"❌ Erro persistente: {e}")
        return False

def criar_json_valido_manual():
    """Cria um JSON válido manualmente a partir dos objetos"""
    print("Criando JSON válido manualmente...")
    
    with open('data/prontuarios.json', 'r', encoding='utf-8') as f:
        conteudo = f.read()
    
    # Extrair todos os objetos entre { }
    objetos = []
    inicio = 0
    nivel = 0
    dentro_objeto = False
    
    for i, char in enumerate(conteudo):
        if char == '{':
            nivel += 1
            if nivel == 1:
                inicio = i
                dentro_objeto = True
        elif char == '}':
            nivel -= 1
            if nivel == 0 and dentro_objeto:
                fim = i + 1
                obj_str = conteudo[inicio:fim].strip()
                try:
                    obj = json.loads(obj_str)
                    objetos.append(obj)
                except json.JSONDecodeError:
                    # Tenta limpar o objeto
                    obj_str_limpo = obj_str
                    if obj_str_limpo.endswith(','):
                        obj_str_limpo = obj_str_limpo[:-1]
                    try:
                        obj = json.loads(obj_str_limpo)
                        objetos.append(obj)
                    except:
                        print(f"⚠️  Ignorando objeto inválido")
                dentro_objeto = False
    
    # Criar novo JSON válido
    novo_json = json.dumps(objetos, indent=2, ensure_ascii=False)
    
    with open('data/prontuarios_manual.json', 'w', encoding='utf-8') as f:
        f.write(novo_json)
    
    print(f"✅ JSON manual criado com {len(objetos)} objetos")
    return True

if __name__ == '__main__':
    print("=== CORREÇÃO DE JSON ===")
    
    # Tentativa 1: Correção específica
    if not corrigir_problema_especifico():
        # Tentativa 2: Estratégia alternativa
        if not corrigir_com_estrategia_alternativa():
            # Tentativa 3: Reconstrução manual
            criar_json_valido_manual()
    
    print("✅ Processo de correção concluído!")