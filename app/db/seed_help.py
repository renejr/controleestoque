import asyncio
import sys
import os

# Adiciona o diretório raiz do projeto ao PYTHONPATH para permitir imports absolutos
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.core.database import SessionLocal
from app.models.help import HelpArticle

ARTICLES = [
    {
        "title": "Gestão de Estoque e Pedidos de Venda",
        "category": "ESTOQUE",
        "content": (
            "No nosso ERP SaaS, a gestão de estoque foi projetada para garantir a máxima integridade e evitar vendas sem fundo. "
            "Quando um Pedido de Venda (Sales Order) é criado no sistema, os itens são inicialmente apenas reservados logicamente. "
            "A dedução física (baixa) no inventário de um produto SÓ OCORRE no momento exato em que o status do Pedido de Venda "
            "é alterado para 'SHIPPED' (Enviado). Neste momento, o sistema utiliza um controle de concorrência rigoroso "
            "para garantir que a quantidade não fique negativa. Se você cancelar um pedido antes do envio, o estoque não sofre nenhuma dedução."
        )
    },
    {
        "title": "Como funciona o Simulador de Carga 3D (Bin Packing)?",
        "category": "LOGÍSTICA",
        "content": (
            "O Módulo de Gestão de Frota (TMS) possui um poderoso Simulador de Carga 3D integrado. "
            "Este motor matemático utiliza as dimensões (altura, largura, profundidade) e o peso de cada produto de uma ordem de venda "
            "e tenta encaixá-los de forma otimizada dentro do baú do veículo selecionado (Bin Packing). "
            "O sistema calcula o percentual de ocupação tanto de volume quanto de peso. "
            "Se a capacidade máxima do caminhão for atingida (por espaço físico ou limite da balança), "
            "os itens que não couberem serão explicitamente listados na seção 'Itens Excedentes' (Unfitted Items) do relatório gerado."
        )
    },
    {
        "title": "Análise de Lucratividade pelo Oráculo CFO",
        "category": "FINANCEIRO",
        "content": (
            "O nosso Módulo Financeiro é automatizado e dispensa lançamentos manuais complexos. "
            "O coração deste módulo é o Oráculo CFO (IA), que cruza todas as transações de entrada (IN) com as de saída (OUT). "
            "Ao registrar o custo de aquisição na entrada e o preço de venda na saída, o sistema calcula o Lucro Líquido e a "
            "Margem de Contribuição em tempo real. O assistente de IA pode gerar relatórios textuais formatados explicando "
            "quais produtos estão trazendo maior rentabilidade e sugerindo melhorias no fluxo de caixa baseadas no giro de estoque."
        )
    },
    {
        "title": "Privacidade e Uso do Chat Corporativo",
        "category": "COMUNICAÇÃO",
        "content": (
            "O Chat Corporativo é a ferramenta oficial de comunicação instantânea do sistema. "
            "Ele opera em tempo real utilizando tecnologia de WebSockets. Para garantir a segurança industrial e a Lei Geral de Proteção de Dados (LGPD), "
            "o chat é estritamente isolado por empresa (Tenant). Um usuário só pode visualizar e conversar com outros funcionários "
            "que estejam cadastrados sob o mesmo CNPJ/Empresa. O histórico das conversas é salvo no banco de dados e pode ser consultado a qualquer momento."
        )
    },
    {
        "title": "Como cadastrar um Produto e Regras Logísticas",
        "category": "PRODUTOS",
        "content": (
            "Para cadastrar um produto, acesse a aba 'Produtos' no menu inferior e clique no botão '+'. "
            "Você precisará informar dados básicos como Nome, SKU, Preço de Custo e Preço de Venda. "
            "É obrigatório preencher os campos logísticos: Largura, Altura, Profundidade (em cm) e Peso (em kg). "
            "Essas dimensões são cruciais porque alimentam o nosso Simulador de Carga 3D (Bin Packing) "
            "na hora de roteirizar a frota. Se você deixar as dimensões zeradas, o sistema não conseguirá calcular "
            "o espaço que a caixa ocupa no caminhão."
        )
    }
]

async def seed_help_manual():
    print("Iniciando o processo de inserção do Manual do Sistema (Base de Conhecimento)...")
    
    async with SessionLocal() as db:
        try:
            for item in ARTICLES:
                article = HelpArticle(
                    title=item["title"],
                    category=item["category"],
                    content=item["content"]
                )
                db.add(article)
            
            await db.commit()
            print("Manual do SaaS inserido com sucesso!")
            
        except Exception as e:
            await db.rollback()
            print(f"Erro ao inserir o manual: {e}")

if __name__ == "__main__":
    # Roda a função assíncrona
    asyncio.run(seed_help_manual())
