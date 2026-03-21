import asyncio
import sys
import os

# Adiciona o diretório raiz do projeto ao PYTHONPATH para permitir imports absolutos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.core.database import SessionLocal
from app.models.help import HelpArticle
from sqlalchemy import delete
from app.services.llm_service import get_embedding

# Uma base de conhecimento massiva cobrindo todos os módulos do ERP
ARTICLES = [
    {
        "title": "Como cadastrar um Produto",
        "category": "PRODUTOS",
        "content": (
            "Para cadastrar um produto, siga estes passos:\n\n"
            "1. Acesse a aba 'Produtos' no menu de navegação inferior.\n"
            "2. Clique no botão de '+' flutuante no canto inferior direito.\n"
            "3. Preencha as Informações Básicas (Nome, SKU, Preço de Custo e Preço de Venda).\n"
            "4. É obrigatório preencher os campos logísticos: Largura, Altura, Profundidade (em cm) e Peso (em kg). "
            "Essas dimensões alimentam o Simulador de Carga 3D. Sem elas, o produto não poderá ser roteirizado na frota.\n"
            "5. Clique em 'Salvar'."
        )
    },
    {
        "title": "Importação de Produtos em Lote (CSV)",
        "category": "PRODUTOS",
        "content": (
            "Para cadastrar muitos produtos de uma vez:\n\n"
            "1. Na aba 'Produtos', clique no ícone de Upload (Nuvem com seta para cima) no topo da tela.\n"
            "2. Baixe o 'Template de Importação (CSV)' clicando no botão correspondente.\n"
            "3. Preencha o arquivo no Excel ou Google Sheets mantendo o cabeçalho original. Não deixe SKU vazio.\n"
            "4. Salve como .csv e faça o upload na mesma tela.\n"
            "5. O sistema fará um Dry-Run (teste) e informará se há erros. Se tudo estiver correto, confirme a importação."
        )
    },
    {
        "title": "Gestão de Estoque e Baixa Automática",
        "category": "VENDAS",
        "content": (
            "A baixa do estoque ocorre de forma totalmente automatizada no sistema.\n"
            "Quando você cria um Pedido de Venda (Sales Order), os itens são apenas reservados logicamente. "
            "A dedução real e física do estoque SÓ OCORRE quando você altera o status do Pedido de Venda para 'SHIPPED' (Enviado). "
            "Neste momento, a baixa é irreversível. Cancelar pedidos em status 'PROCESSING' não afeta o estoque físico."
        )
    },
    {
        "title": "Como cadastrar um Veículo na Frota",
        "category": "LOGÍSTICA",
        "content": (
            "Para cadastrar um novo veículo (caminhão ou van) na sua frota:\n\n"
            "1. Acesse o menu lateral (Gaveta) clicando no ícone de três linhas no canto superior esquerdo.\n"
            "2. Clique em 'Gestão de Frota (TMS)'.\n"
            "3. Clique no botão de '+' flutuante no canto inferior direito.\n"
            "4. Preencha os dados básicos: Placa, Modelo e Tara (Peso do veículo vazio).\n"
            "5. Preencha as Capacidades Máximas de carga: Peso (em kg) e Volume (em m³).\n"
            "6. É fundamental preencher as dimensões internas do baú: Largura, Altura e Profundidade (em cm). "
            "Essas medidas são obrigatórias para que o Simulador de Carga 3D saiba exatamente onde as caixas podem ser empilhadas.\n"
            "7. Clique em 'Salvar'."
        )
    },
    {
        "title": "Como simular uma Carga no Caminhão (Bin Packing 3D)",
        "category": "LOGÍSTICA",
        "content": (
            "Para saber se uma venda cabe no caminhão:\n\n"
            "1. Acesse o menu lateral (Gaveta) na aba 'Início' ou 'Produtos' e clique em 'Gestão de Frota (TMS)'.\n"
            "2. Cadastre seu veículo informando a capacidade máxima em KG e Volume, além das dimensões do baú.\n"
            "3. Vá até a aba do 'Simulador de Carga (TMS)'.\n"
            "4. Selecione o veículo desejado e os pedidos de venda que deseja carregar.\n"
            "5. O sistema fará o cálculo matemático em 3D, desenhando a planta baixa de como as caixas devem ser empilhadas.\n"
            "6. Itens que excederem o peso ou o espaço do baú aparecerão na aba 'Itens Excedentes'."
        )
    },
    {
        "title": "Como gerar uma Rota Otimizada para o Motorista",
        "category": "LOGÍSTICA",
        "content": (
            "Após simular a carga no caminhão, você pode gerar a melhor rota de entrega:\n\n"
            "1. Na tela do Simulador de Carga, após confirmar que os itens cabem, clique no ícone de Mapa no topo da tela.\n"
            "2. O sistema acionará o motor OSRM + OR-Tools para calcular o trajeto mais rápido pelas ruas.\n"
            "3. Você verá um mapa mostrando a ordem exata de entrega (1, 2, 3...).\n"
            "4. O motorista pode clicar no ícone do carro ao lado do cliente para abrir a rota diretamente no Waze ou Google Maps do celular dele."
        )
    },
    {
        "title": "Como o Oráculo CFO calcula o Lucro",
        "category": "FINANCEIRO",
        "content": (
            "O Módulo Financeiro dispensa lançamentos contábeis manuais.\n"
            "Toda vez que você dá entrada em um produto (Compra), o custo é registrado. "
            "Toda vez que o status de uma Venda muda para 'SHIPPED', a receita é registrada.\n"
            "O Oráculo CFO (Nossa Inteligência Artificial) cruza esses dados em tempo real e calcula seu Lucro Líquido. "
            "Para ver o relatório, acesse a aba 'CFO (IA)' e peça uma análise do mês."
        )
    },
    {
        "title": "Como o Assistente CSO ajuda nas Compras",
        "category": "COMPRAS",
        "content": (
            "A aba 'CSO (IA)' atua como seu Diretor de Suprimentos.\n"
            "Ele analisa constantemente os produtos que atingiram o 'Estoque Mínimo' cadastrado. "
            "Com um clique, a IA gera um plano de reposição recomendando exatamente quanto comprar de cada fornecedor "
            "para que o estoque fique 20% acima do limite de segurança. Você pode aprovar o plano para que as Ordens de Compra sejam geradas automaticamente."
        )
    },
    {
        "title": "Chat Corporativo e Privacidade",
        "category": "COMUNICAÇÃO",
        "content": (
            "O sistema possui um chat interno para comunicação entre os funcionários.\n"
            "Por questões de LGPD e segurança empresarial (Multi-Tenant), o chat é estritamente isolado por empresa. "
            "Um funcionário só consegue ver e conversar com colegas cadastrados sob o mesmo CNPJ. "
            "A comunicação ocorre em tempo real, sem necessidade de atualizar a página."
        )
    },
    {
        "title": "Auditoria (Caixa Preta) e Segurança",
        "category": "SEGURANÇA",
        "content": (
            "Qualquer alteração crítica no sistema (como mudar o preço de um produto, excluir um fornecedor ou aprovar uma venda) "
            "é registrada invisivelmente pela Caixa Preta do sistema.\n"
            "Apenas usuários com perfil 'ADMIN' podem acessar o log de auditoria para visualizar exatamente qual usuário fez a alteração, "
            "o horário exato e comparar o dado 'Antes e Depois' (JSON)."
        )
    },
    {
        "title": "Perfis de Acesso (RBAC)",
        "category": "SEGURANÇA",
        "content": (
            "O sistema opera com três perfis de acesso:\n"
            "- ADMIN: Acesso total. Pode ver faturamento, auditar ações e excluir registros críticos.\n"
            "- MANAGER: Acesso a relatórios e movimentações, mas não pode excluir histórico financeiro.\n"
            "- OPERATOR: Acesso restrito apenas à operação de estoque (separação e expedição), sem visualizar painéis financeiros."
        )
    }
]

async def seed_help_manual_full():
    print("🧹 Limpando a base de conhecimento antiga...")
    
    async with SessionLocal() as db:
        try:
            # Apaga tudo para evitar duplicatas ou informações obsoletas
            await db.execute(delete(HelpArticle))
            
            print("🚀 Injetando a nova Base de Conhecimento Suprema e gerando Embeddings (isso pode demorar alguns segundos)...")
            for item in ARTICLES:
                # Gera o vetor matemático do texto para o RAG Vetorial
                text_to_embed = f"TÍTULO: {item['title']}\nCONTEÚDO: {item['content']}"
                embedding_vector = await get_embedding(text_to_embed)
                
                article = HelpArticle(
                    title=item["title"],
                    category=item["category"],
                    content=item["content"],
                    embedding=embedding_vector if embedding_vector else None
                )
                db.add(article)
            
            await db.commit()
            print("✅ Manual do SaaS reconstruído com sucesso! O LLM agora sabe tudo sobre o sistema.")
            
        except Exception as e:
            await db.rollback()
            print(f"❌ Erro ao reconstruir o manual: {e}")

if __name__ == "__main__":
    asyncio.run(seed_help_manual_full())