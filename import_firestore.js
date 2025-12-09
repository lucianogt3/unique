const admin = require('firebase-admin');
const fs = require('fs');

// 1. Caminhos dos arquivos
const serviceAccountPath = './firebase-service-account.json';
const dataExportPath = './data_export_firestore.json';

// Substituído pelo novo ID do projeto: unique-73ac7
const firebaseProjectId = 'unique-73ac7'; 

// 2. Inicialização do Firebase Admin SDK
// IMPORTANTE: O arquivo de chave de serviço precisa estar na raiz
const serviceAccount = require(serviceAccountPath);

admin.initializeApp({
  credential: admin.credential.cert(serviceAccount),
  databaseURL: `https://${firebaseProjectId}.firebaseio.com`
});

const db = admin.firestore();

// Função auxiliar para converter strings vazias em null
function cleanData(data) {
    if (typeof data === 'object' && data !== null) {
        for (const key in data) {
            if (data.hasOwnProperty(key)) {
                if (data[key] === '' || data[key] === 'null' || data[key] === '-') {
                    data[key] = null;
                } else if (typeof data[key] === 'object' || Array.isArray(data[key])) {
                    data[key] = cleanData(data[key]); // Recursão para objetos aninhados e arrays
                }
            }
        }
    }
    return data;
}

// 3. Função principal de importação
async function importData() {
    try {
        console.log(`\nIniciando importação de dados para o projeto: ${firebaseProjectId}`);
        
        // Carrega o JSON
        const dataJson = JSON.parse(fs.readFileSync(dataExportPath, 'utf8'));
        
        // Define a ordem de importação (mestres primeiro)
        const collectionsToImport = [
            'convenios', 'setores', 'tipos_erro', 'categorias_erro', 'responsaveis', 'prontuarios'
        ];

        for (const collectionName of collectionsToImport) {
            const dataArray = dataJson[collectionName];
            if (!dataArray || dataArray.length === 0) {
                console.log(`\nColeção '${collectionName}' vazia ou não encontrada. Pulando.`);
                continue;
            }
            
            console.log(`\nImportando ${dataArray.length} documentos para a coleção '${collectionName}'...`);
            
            let batch = db.batch();
            let count = 0;
            
            for (const item of dataArray) {
                const docId = String(item.id);
                const cleanItem = cleanData({ ...item }); // Copia e limpa
                
                // Remove o ID do objeto antes de salvar (Firestore usa o ID do documento)
                delete cleanItem.id;
                
                // Limpeza especial para prontuários
                if (collectionName === 'prontuarios') {
                    // Remove arrays de relacionamento complexos que devem ser subcoleções no futuro,
                    // mas por agora, os erros são salvos como objetos aninhados se houver.
                    delete cleanItem.responsaveis; 
                    
                    // Salvando erros como subcoleção de forma simplificada
                    const errosParaSubcolecao = cleanItem.erros || [];
                    delete cleanItem.erros;
                    
                    // Salva o documento principal do prontuário
                    const docRef = db.collection(collectionName).doc(docId);
                    batch.set(docRef, cleanItem);

                    // Adiciona erros como subcoleção (Substitua se precisar de uma lógica mais complexa)
                    if (errosParaSubcolecao.length > 0) {
                         for (let i = 0; i < errosParaSubcolecao.length; i++) {
                             const erro = errosParaSubcolecao[i];
                             const erroId = erro.id ? String(erro.id) : String(i + 1);
                             delete erro.id; // Remove o ID do erro
                             delete erro.prontuario_id; // Remove FK redundante na subcoleção

                             const erroRef = docRef.collection('erros').doc(erroId);
                             batch.set(erroRef, cleanData(erro));

                             count++;
                             if (count % 400 === 0) { // Limite do Batch: 500 operações
                                 await batch.commit();
                                 batch = db.batch();
                                 console.log(`  -> Batch de 400 operações concluído para ${collectionName}...`);
                             }
                         }
                    }

                } else {
                    // Salva as coleções mestre (Convênios, Setores, etc.)
                    const docRef = db.collection(collectionName).doc(docId);
                    batch.set(docRef, cleanItem);

                    count++;
                }

                if (count % 400 === 0) { // Finaliza o batch para as coleções mestre
                    await batch.commit();
                    batch = db.batch();
                    console.log(`  -> Batch de 400 operações concluído para ${collectionName}...`);
                }
            }
            
            // Finaliza o último batch
            await batch.commit();
            console.log(`✅ Coleção '${collectionName}' importada com sucesso. Total de operações: ${count}.`);
        }

        console.log("\nProcesso de importação finalizado! Sucesso na migração de dados.");

    } catch (error) {
        console.error("❌ ERRO FATAL NA IMPORTAÇÃO:", error);
        if (error.code) {
             console.error("Código do Erro:", error.code);
        }
        process.exit(1);
    }
}

importData();