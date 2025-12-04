// ============================================================
// CONFIGURAÇÕES DO SISTEMA - VERSÃO COMPLETA (CORRIGIDA)
// ============================================================

// Estado global
let motivoSelecionado = null;

// Função auxiliar para modais
function getModalInstance(id) {
    const el = document.getElementById(id);
    if (!el) {
        console.error('Modal não encontrado:', id);
        return null;
    }
    return bootstrap.Modal.getInstance(el) || new bootstrap.Modal(el);
}

// ============================================================
// CONVÊNIOS
// ============================================================

function abrirModalConvenio(id = null, nome = '', status = 'ativo') {
    const modal = getModalInstance('modalConvenio');
    if (!modal) return;
    
    document.getElementById('convenio_id').value = id || '';
    document.getElementById('convenio_nome').value = nome || '';
    document.getElementById('convenio_status').value = status || 'ativo';
    document.getElementById('modalConvenioTitle').textContent = id ? 'Editar Convênio' : 'Novo Convênio';
    
    modal.show();
}

function salvarConvenio() {
    const form = document.getElementById('formConvenio');
    const formData = new FormData(form);
    
    const payload = {
        id: formData.get('id') || null,
        nome: formData.get('nome'),
        status: formData.get('status') || 'ativo'
    };
    
    console.log('💾 Salvando convênio:', payload);
    
    fetch('/api/configuracoes/convenios', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
        if (data.sucesso) {
            getModalInstance('modalConvenio')?.hide();
            showNotification('Convênio salvo com sucesso!', 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            alert('Erro ao salvar convênio: ' + (data.erro || 'Erro desconhecido'));
        }
    })
    .catch(error => {
        console.error('Erro:', error);
        alert('Erro ao salvar convênio: ' + error.message);
    });
}

async function excluirConvenio(id) {
    if (!confirm('Tem certeza que deseja excluir este convênio?')) return;
    
    try {
        const response = await fetch(`/api/configuracoes/convenios/${id}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showNotification('Convênio excluído com sucesso!', 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            const errorData = await response.json().catch(() => ({}));
            alert('Erro ao excluir convênio: ' + (errorData.erro || response.statusText));
        }
    } catch (error) {
        console.error('Erro:', error);
        alert('Erro ao excluir convênio: ' + error.message);
    }
}

// ============================================================
// SETORES
// ============================================================

function abrirModalSetor(id = null, nome = '', descricao = '', status = 'ativo') {
    const modal = getModalInstance('modalSetor');
    if (!modal) return;
    
    document.getElementById('setor_id').value = id || '';
    document.getElementById('setor_nome').value = nome || '';
    document.getElementById('setor_descricao').value = descricao || '';
    document.getElementById('setor_status').value = status || 'ativo';
    document.getElementById('modalSetorTitle').textContent = id ? 'Editar Setor' : 'Novo Setor';
    
    modal.show();
}

function salvarSetor() {
    const form = document.getElementById('formSetor');
    const formData = new FormData(form);
    
    const payload = {
        id: formData.get('id') || null,
        nome: formData.get('nome'),
        descricao: formData.get('descricao') || '',
        status: formData.get('status') || 'ativo'
    };
    
    console.log('💾 Salvando setor:', payload);
    
    fetch('/api/configuracoes/setores', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
        if (data.sucesso) {
            getModalInstance('modalSetor')?.hide();
            showNotification('Setor salvo com sucesso!', 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            alert('Erro ao salvar setor: ' + (data.erro || 'Erro desconhecido'));
        }
    })
    .catch(error => {
        console.error('Erro:', error);
        alert('Erro ao salvar setor: ' + error.message);
    });
}

async function excluirSetor(id) {
    if (!confirm('Tem certeza que deseja excluir este setor?')) return;
    
    try {
        const response = await fetch(`/api/configuracoes/setores/${id}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showNotification('Setor excluído com sucesso!', 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            const errorData = await response.json().catch(() => ({}));
            alert('Erro ao excluir setor: ' + (errorData.erro || response.statusText));
        }
    } catch (error) {
        console.error('Erro:', error);
        alert('Erro ao excluir setor: ' + error.message);
    }
}

// ============================================================
// RESPONSÁVEIS
// ============================================================

function abrirModalResponsavel(id = null, nome = '', funcao = '', setor = '', status = 'ativo') {
    const modal = getModalInstance('modalResponsavel');
    if (!modal) return;
    
    document.getElementById('responsavel_id').value = id || '';
    document.getElementById('responsavel_nome').value = nome || '';
    document.getElementById('responsavel_funcao').value = funcao || '';
    document.getElementById('responsavel_setor').value = setor || '';
    document.getElementById('responsavel_status').value = status || 'ativo';
    document.getElementById('modalResponsavelTitle').textContent = id ? 'Editar Responsável' : 'Novo Responsável';
    
    modal.show();
}

function salvarResponsavel() {
    const form = document.getElementById('formResponsavel');
    const formData = new FormData(form);
    
    const payload = {
        id: formData.get('id') || null,
        nome: formData.get('nome'),
        funcao: formData.get('funcao') || '',
        setor: formData.get('setor') || '',
        status: formData.get('status') || 'ativo'
    };
    
    console.log('💾 Salvando responsável:', payload);
    
    fetch('/api/configuracoes/responsaveis', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
        if (data.sucesso) {
            getModalInstance('modalResponsavel')?.hide();
            showNotification('Responsável salvo com sucesso!', 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            alert('Erro ao salvar responsável: ' + (data.erro || 'Erro desconhecido'));
        }
    })
    .catch(error => {
        console.error('Erro:', error);
        alert('Erro ao salvar responsável: ' + error.message);
    });
}

async function excluirResponsavel(id) {
    if (!confirm('Tem certeza que deseja excluir este responsável?')) return;
    
    try {
        const response = await fetch(`/api/configuracoes/responsaveis/${id}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showNotification('Responsável excluído com sucesso!', 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            const errorData = await response.json().catch(() => ({}));
            alert('Erro ao excluir responsável: ' + (errorData.erro || response.statusText));
        }
    } catch (error) {
        console.error('Erro:', error);
        alert('Erro ao excluir responsável: ' + error.message);
    }
}

// ============================================================
// MOTIVOS (TIPOS DE ERRO)
// ============================================================

function abrirModalTipoErro(id = null, nome = '', cor = '#6c757d', status = 'ativo', descricao = '') {
    const modal = getModalInstance('modalTipoErro');
    if (!modal) return;
    
    document.getElementById('tipo_erro_id').value = id || '';
    document.getElementById('tipo_erro_nome').value = nome || '';
    document.getElementById('tipo_erro_descricao').value = descricao || '';
    document.getElementById('tipo_erro_cor').value = cor || '#6c757d';
    document.getElementById('tipo_erro_status').value = status || 'ativo';
    document.getElementById('modalTipoErroTitle').textContent = id ? 'Editar Motivo' : 'Novo Motivo';
    
    modal.show();
}

function salvarTipoErro() {
    const form = document.getElementById('formTipoErro');
    const formData = new FormData(form);
    
    const payload = {
        id: formData.get('id') || null,
        nome: formData.get('nome'),
        descricao: formData.get('descricao'),
        cor: formData.get('cor') || '#6c757d',
        status: formData.get('status') || 'ativo'
    };
    
    console.log('💾 Salvando tipo de erro:', payload);
    
    fetch('/api/configuracoes/tipos_erro', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
        if (data.sucesso) {
            getModalInstance('modalTipoErro')?.hide();
            showNotification('Motivo salvo com sucesso!', 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            alert('Erro ao salvar motivo: ' + (data.erro || 'Erro desconhecido'));
        }
    })
    .catch(error => {
        console.error('Erro:', error);
        alert('Erro ao salvar motivo: ' + error.message);
    });
}

async function excluirTipoErro(codigo) {
    if (!confirm('Tem certeza que deseja excluir este motivo?')) return;
    
    try {
        const info = window.tipos_erro_dict[codigo];
        if (!info || !info.id) {
            alert('Erro: Não foi possível encontrar o ID do motivo');
            return;
        }
        
        const response = await fetch(`/api/configuracoes/tipos_erro/${info.id}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showNotification('Motivo excluído com sucesso!', 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            const errorData = await response.json().catch(() => ({}));
            alert('Erro ao excluir motivo: ' + (errorData.erro || response.statusText));
        }
    } catch (error) {
        console.error('Erro:', error);
        alert('Erro ao excluir motivo: ' + error.message);
    }
}

// ============================================================
// CAUSAS DE ERRO
// ============================================================

function selecionarMotivo(codigo) {
    console.log('🔍 Selecionando motivo:', codigo);
    
    const info = window.tipos_erro_dict[codigo];
    if (!info) return;

    motivoSelecionado = { codigo: codigo, nome: info.nome, id: info.id };

    document.getElementById('motivoSelecionadoLabel').textContent = info.nome;
    document.getElementById('motivoSelecionadoLabel').className = "text-primary";
    document.getElementById('btnNovaCausa').disabled = false;
    document.getElementById('alertSelecioneMotivo').classList.add('d-none');
    document.getElementById('containerCausas').classList.remove('d-none');

    document.querySelectorAll('#tabelaMotivos tr').forEach(tr => tr.classList.remove('table-active'));
    const tr = document.querySelector(`#tabelaMotivos tr[data-codigo="${codigo}"]`);
    if (tr) tr.classList.add('table-active');

    carregarCausasDoMotivo(info.id);
}

function carregarCausasDoMotivo(tipoErroId) {
    console.log('📥 Carregando causas para tipo_erro_id:', tipoErroId);
    
    fetch('/api/configuracoes/causas')
        .then(response => response.json())
        .then(causas => {
            const tbody = document.getElementById('tabelaCausasMotivo');
            tbody.innerHTML = '';
            
            const causasFiltradas = causas.filter(causa => Number(causa.tipo_erro_id) === Number(tipoErroId));
            
            console.log('✅ Causas encontradas:', causasFiltradas);
            
            if (causasFiltradas.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" class="text-muted text-center">Nenhuma causa cadastrada para este motivo.</td></tr>';
                return;
            }
            
            causasFiltradas.forEach(causa => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${causa.id}</td>
                    <td>${causa.descricao}</td>
                    <td>
                        <span class="badge bg-${causa.status === 'ativo' ? 'success' : 'secondary'}">
                            ${causa.status}
                        </span>
                    </td>
                    <td class="text-end">
                        <button class="btn btn-sm btn-outline-primary"
                            onclick="abrirModalCausa(${causa.id}, '${causa.descricao.replace(/'/g, "&#39;")}', ${causa.tipo_erro_id}, '${causa.status}')">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger" onclick="excluirCausa(${causa.id})">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        })
        .catch(error => {
            console.error('❌ Erro ao carregar causas:', error);
            const tbody = document.getElementById('tabelaCausasMotivo');
            tbody.innerHTML = '<tr><td colspan="4" class="text-danger text-center">Erro ao carregar causas.</td></tr>';
        });
}

function abrirModalCausaComMotivo() {
    if (!motivoSelecionado) {
        alert('Selecione um motivo primeiro.');
        return;
    }
    
    const modal = getModalInstance('modalCausa');
    if (!modal) return;

    document.getElementById('modalCausaTitle').textContent = 'Nova Causa - ' + motivoSelecionado.nome;
    document.getElementById('causa_id').value = '';
    document.getElementById('causa_descricao').value = '';
    document.getElementById('causa_status').value = 'ativo';

    document.getElementById('campo_selecionar_motivo').classList.add('d-none');
    document.getElementById('info_motivo_pre_selecionado').classList.remove('d-none');
    document.getElementById('texto_motivo_pre_selecionado').textContent = motivoSelecionado.nome;
    document.getElementById('hidden_tipo_erro_id').value = motivoSelecionado.id;
    document.getElementById('causa_motivo_pre_selecionado').value = 'true';

    modal.show();
}

function abrirModalCausa(id = null, descricao = '', tipo_erro_id = null, status = 'ativo') {
    const modal = getModalInstance('modalCausa');
    if (!modal) return;

    document.getElementById('campo_selecionar_motivo').classList.remove('d-none');
    document.getElementById('info_motivo_pre_selecionado').classList.add('d-none');
    document.getElementById('causa_motivo_pre_selecionado').value = 'false';

    if (id) {
        document.getElementById('modalCausaTitle').textContent = 'Editar Causa';
        document.getElementById('causa_id').value = id;
        document.getElementById('causa_descricao').value = descricao || '';
        document.getElementById('causa_status').value = status || 'ativo';
        if (tipo_erro_id) {
            document.getElementById('causa_tipo_erro').value = tipo_erro_id;
        }
    } else {
        document.getElementById('modalCausaTitle').textContent = 'Nova Causa de Erro';
        document.getElementById('causa_id').value = '';
        document.getElementById('causa_descricao').value = '';
        document.getElementById('causa_status').value = 'ativo';
        document.getElementById('causa_tipo_erro').value = '';
    }

    modal.show();
}

function salvarCausa() {
    const form = document.getElementById('formCausa');
    const formData = new FormData(form);
    
    const isPreSelecionado = formData.get('motivo_pre_selecionado') === 'true';
    let tipoErroId = isPreSelecionado ? 
        formData.get('tipo_erro_id_hidden') : 
        formData.get('tipo_erro_id');

    if (!tipoErroId) {
        alert('Selecione um motivo para esta causa.');
        return;
    }

    const payload = {
        id: formData.get('id') || null,
        tipo_erro_id: Number(tipoErroId),
        descricao: formData.get('descricao'),
        status: formData.get('status') || 'ativo'
    };

    console.log('💾 Salvando causa:', payload);

    fetch('/api/configuracoes/causas', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
        if (data.sucesso) {
            getModalInstance('modalCausa')?.hide();
            showNotification('Causa salva com sucesso!', 'success');
            
            if (motivoSelecionado) {
                carregarCausasDoMotivo(motivoSelecionado.id);
            } else {
                setTimeout(() => location.reload(), 1000);
            }
        } else {
            alert('Erro ao salvar causa: ' + (data.erro || 'Erro desconhecido'));
        }
    })
    .catch(error => {
        console.error('Erro:', error);
        alert('Erro ao salvar causa: ' + error.message);
    });
}

async function excluirCausa(id) {
    if (!confirm('Tem certeza que deseja excluir esta causa?')) return;
    
    try {
        const response = await fetch(`/api/configuracoes/causas/${id}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showNotification('Causa excluída com sucesso!', 'success');
            
            if (motivoSelecionado) {
                carregarCausasDoMotivo(motivoSelecionado.id);
            } else {
                setTimeout(() => location.reload(), 1000);
            }
        } else {
            const errorData = await response.json().catch(() => ({}));
            alert('Erro ao excluir causa: ' + (errorData.erro || response.statusText));
        }
    } catch (error) {
        console.error('Erro:', error);
        alert('Erro ao excluir causa: ' + error.message);
    }
}

function ativarModoSelecaoMotivo() {
    document.getElementById('campo_selecionar_motivo').classList.remove('d-none');
    document.getElementById('info_motivo_pre_selecionado').classList.add('d-none');
    document.getElementById('causa_motivo_pre_selecionado').value = 'false';
    document.getElementById('hidden_tipo_erro_id').value = '';
}

// ============================================================
// FUNÇÕES AUXILIARES
// ============================================================

function popularCausas() {
    if (!confirm('Recarregar as causas padronizadas? Isso substituirá as causas existentes.')) return;
    
    fetch('/api/popular_causas', { method: 'POST' })
        .then(response => response.json())
        .then(data => {
            if (data.sucesso) {
                showNotification(data.mensagem || 'Causas recarregadas com sucesso!', 'success');
                setTimeout(() => location.reload(), 1500);
            } else {
                alert('Erro: ' + (data.erro || 'Falha ao popular causas'));
            }
        })
        .catch(error => {
            console.error('Erro:', error);
            alert('Erro ao popular causas: ' + error.message);
        });
}

// 🔥 FUNÇÕES DE NOTIFICAÇÃO MODERNA
function showNotification(message, type = 'success', duration = 5000) {
    // Remove notificações anteriores
    const existingNotifications = document.querySelectorAll('.modern-notification');
    existingNotifications.forEach(notification => notification.remove());

    // Cria a notificação
    const notification = document.createElement('div');
    notification.className = `modern-notification notification-${type}`;
    
    let icon = '';
    switch(type) {
        case 'success':
            icon = `
                <svg class="checkmark" viewBox="0 0 24 24">
                    <path d="M20 6L9 17l-5-5"/>
                </svg>
            `;
            break;
        case 'warning':
            icon = `<i class="fas fa-exclamation-triangle fa-beat" style="--fa-animation-duration: 2s;"></i>`;
            break;
        case 'danger':
            icon = `<i class="fas fa-times-circle fa-shake"></i>`;
            break;
        default:
            icon = `<i class="fas fa-info-circle fa-fade"></i>`;
    }

    notification.innerHTML = `
        <div class="p-4">
            <div class="d-flex align-items-center">
                <div class="flex-shrink-0 me-3" style="font-size: 1.5rem;">
                    ${icon}
                </div>
                <div class="flex-grow-1">
                    <h6 class="mb-1 fw-bold">${getNotificationTitle(type)}</h6>
                    <p class="mb-0 small">${message}</p>
                </div>
                <button type="button" class="btn-close btn-close-white flex-shrink-0" onclick="this.closest('.modern-notification').remove()"></button>
            </div>
            <div class="progress-bar mt-3 rounded" style="width: 100%;"></div>
        </div>
    `;

    document.body.appendChild(notification);

    // Remove automaticamente após o tempo
    if (duration > 0) {
        setTimeout(() => {
            if (notification.parentNode) {
                notification.style.opacity = '0';
                notification.style.transform = 'translateY(-20px)';
                setTimeout(() => notification.remove(), 300);
            }
        }, duration);
    }

    return notification;
}

function getNotificationTitle(type) {
    const titles = {
        'success': 'Sucesso!',
        'warning': 'Atenção!',
        'danger': 'Erro!',
        'info': 'Informação'
    };
    return titles[type] || 'Notificação';
}

// 🔥 FUNÇÃO DE LOADING MODERNO
function showLoading(message = 'Processando...') {
    const loading = document.createElement('div');
    loading.className = 'modern-notification notification-info';
    loading.innerHTML = `
        <div class="p-4">
            <div class="d-flex align-items-center">
                <div class="flex-shrink-0 me-3">
                    <div class="modern-spinner"></div>
                </div>
                <div class="flex-grow-1">
                    <h6 class="mb-1 fw-bold">Processando</h6>
                    <p class="mb-0 small">${message}</p>
                </div>
            </div>
            <div class="progress-bar mt-3 rounded" style="width: 100%;"></div>
        </div>
    `;

    document.body.appendChild(loading);
    return loading;
}

// 🔥 ATUALIZAR A SUBMISSÃO DO FORMULÁRIO
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    // Validação básica
    if (estado.responsaveisAdicionados.length === 0) {
        showNotification('Adicione pelo menos um responsável.', 'warning');
        return;
    }

    // Mostrar loading
    const loading = showLoading('Salvando prontuário...');
    btnSalvarProntuario.disabled = true;
    btnSalvarProntuario.classList.add('btn-loading');
    btnSalvarProntuario.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> Salvando...';

    // Prepara os dados
    const formData = new FormData(form);
    const dados = Object.fromEntries(formData.entries());
    
    dados.responsaveis = estado.responsaveisAdicionados;
    dados.erros = [];
    estado.errosPorResponsavel.forEach((erros, responsavel) => {
        erros.forEach(erro => {
            dados.erros.push({
                tipo: erro.tipo,
                causa: erro.causa,
                quantidade: erro.quantidade,
                responsavel: responsavel
            });
        });
    });

    console.log('📤 Dados enviando:', dados);

    try {
        const response = await fetch('{{ url_for("adicionar_prontuario") }}', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(dados)
        });

        const resultado = await response.json();
        console.log('📥 Resposta:', resultado);

        // Remove loading
        loading.remove();

        if (response.ok && resultado.sucesso) {
            // Sucesso com animação
            showNotification('Prontuário salvo com sucesso! Redirecionando...', 'success', 2000);
            
            // Animação de confete (opcional)
            showConfetti();
            
            // Limpa tudo após sucesso
            setTimeout(() => {
                form.reset();
                estado = {
                    responsaveisAdicionados: [],
                    responsavelAtual: null,
                    errosPorResponsavel: new Map()
                };
                listaResponsaveis.innerHTML = '';
                nenhumResponsavelMensagem.style.display = 'block';
                limparResponsavelAtual();
                
                // Redireciona
                window.location.href = '{{ url_for("prontuarios") }}';
            }, 2000);

        } else {
            throw new Error(resultado.erro || 'Erro desconhecido ao salvar');
        }
    } catch (error) {
        loading.remove();
        console.error('Erro ao salvar:', error);
        showNotification(error.message, 'danger');
    } finally {
        btnSalvarProntuario.disabled = false;
        btnSalvarProntuario.classList.remove('btn-loading');
        btnSalvarProntuario.innerHTML = '<i class="fas fa-save"></i> Salvar Prontuário';
    }
});

// 🔥 CONFETI ANIMADO (Bônus)
function showConfetti() {
    const confettiCount = 50;
    const colors = ['#10b981', '#3b82f6', '#8b5cf6', '#f59e0b', '#ef4444'];
    
    for (let i = 0; i < confettiCount; i++) {
        const confetti = document.createElement('div');
        confetti.className = 'confetti';
        confetti.style.cssText = `
            position: fixed;
            width: 8px;
            height: 8px;
            background: ${colors[Math.floor(Math.random() * colors.length)]};
            top: -10px;
            left: ${Math.random() * 100}vw;
            opacity: ${Math.random() + 0.5};
            border-radius: 2px;
            animation: confettiFall ${Math.random() * 3 + 2}s linear forwards;
            z-index: 9998;
        `;
        
        document.body.appendChild(confetti);
        
        // Remove após animação
        setTimeout(() => confetti.remove(), 5000);
    }
    
    // Adicionar estilo de animação para confetti
    if (!document.querySelector('#confetti-styles')) {
        const style = document.createElement('style');
        style.id = 'confetti-styles';
        style.textContent = `
            @keyframes confettiFall {
                0% {
                    transform: translateY(0) rotate(0deg);
                }
                100% {
                    transform: translateY(100vh) rotate(360deg);
                }
            }
        `;
        document.head.appendChild(style);
    }
}

// ============================================================
// INICIALIZAÇÃO E CORREÇÃO DO BOTÃO
// ============================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Configurações do sistema carregadas');
    
    // -----------------------------------------------------------------
    // CORREÇÃO IMPORTANTE: VINCULAR O BOTÃO À FUNÇÃO
    // Como o botão no HTML não tem o 'onclick', fazemos via JS aqui:
    // -----------------------------------------------------------------
    const btnSalvar = document.getElementById('btnSalvarCausa');
    if(btnSalvar) {
        console.log('✅ Botão btnSalvarCausa encontrado e evento vinculado.');
        btnSalvar.addEventListener('click', salvarCausa);
    } else {
        console.warn('⚠️ Botão btnSalvarCausa NÃO encontrado.');
    }
    // -----------------------------------------------------------------

    setTimeout(() => {
        carregarTodasCausas();
    }, 500);
});

function carregarTodasCausas() {
    motivoSelecionado = null;
    
    document.getElementById('motivoSelecionadoLabel').textContent = "Todas as Causas";
    document.getElementById('motivoSelecionadoLabel').className = "text-dark";
    document.getElementById('btnNovaCausa').disabled = false;
    
    document.getElementById('alertSelecioneMotivo').classList.add('d-none');
    document.getElementById('containerCausas').classList.remove('d-none');

    document.querySelectorAll('#tabelaMotivos tr').forEach(tr => tr.classList.remove('table-active'));

    carregarCausasNaTabela(null);
}

function carregarCausasNaTabela(filtroTipoErroId) {
    console.log('📥 Carregando causas...', filtroTipoErroId ? `Filtro: ${filtroTipoErroId}` : 'Sem filtro');
    
    fetch('/api/configuracoes/causas')
        .then(response => response.json())
        .then(causas => {
            const tbody = document.getElementById('tabelaCausasMotivo');
            tbody.innerHTML = '';
            
            let causasParaExibir = causas;

            if (filtroTipoErroId) {
                causasParaExibir = causas.filter(c => Number(c.tipo_erro_id) === Number(filtroTipoErroId));
            }
            
            if (causasParaExibir.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" class="text-muted text-center">Nenhuma causa encontrada.</td></tr>';
                return;
            }
            
            causasParaExibir.forEach(causa => {
                const motivoInfo = window.tipos_erro_lista.find(t => t.id == causa.tipo_erro_id);
                const badgeMotivo = motivoInfo 
                    ? `<span class="badge me-2" style="background-color: ${motivoInfo.cor || '#6c757d'}">${motivoInfo.nome}</span>` 
                    : '';

                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${causa.id}</td>
                    <td>
                        ${!filtroTipoErroId ? badgeMotivo : ''} 
                        ${causa.descricao}
                    </td>
                    <td>
                        <span class="badge bg-${causa.status === 'ativo' ? 'success' : 'secondary'}">
                            ${causa.status}
                        </span>
                    </td>
                    <td class="text-end">
                        <button class="btn btn-sm btn-outline-primary"
                            onclick="abrirModalCausa(${causa.id}, '${causa.descricao.replace(/'/g, "&#39;")}', ${causa.tipo_erro_id}, '${causa.status}')">
                            <i class="fas fa-edit"></i>
                        </button>
                        <button class="btn btn-sm btn-outline-danger" onclick="excluirCausa(${causa.id})">
                            <i class="fas fa-trash"></i>
                        </button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        })
        .catch(error => {
            console.error('❌ Erro:', error);
        });
}

// Exporta funções para o escopo global
window.abrirModalConvenio = abrirModalConvenio;
window.salvarConvenio = salvarConvenio;
window.excluirConvenio = excluirConvenio;

window.abrirModalSetor = abrirModalSetor;
window.salvarSetor = salvarSetor;
window.excluirSetor = excluirSetor;

window.abrirModalResponsavel = abrirModalResponsavel;
window.salvarResponsavel = salvarResponsavel;
window.excluirResponsavel = excluirResponsavel;

window.abrirModalTipoErro = abrirModalTipoErro;
window.salvarTipoErro = salvarTipoErro;
window.excluirTipoErro = excluirTipoErro;

window.selecionarMotivo = selecionarMotivo;
window.abrirModalCausaComMotivo = abrirModalCausaComMotivo;
window.abrirModalCausa = abrirModalCausa;
window.salvarCausa = salvarCausa;
window.excluirCausa = excluirCausa;
window.popularCausas = popularCausas;
window.ativarModoSelecaoMotivo = ativarModoSelecaoMotivo;