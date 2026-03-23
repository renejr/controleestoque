import httpx
import json
from app.core.config import settings

async def generate_inventory_insights(dashboard_data: dict) -> str:
    """
    Usa um LLM local (via Ollama) para gerar insights de negócios baseados nos dados do dashboard.
    """
    
    # Extrair e formatar dados para evitar alucinação do modelo
    metrics = {
        "Total de Produtos": dashboard_data.get('total_products', 0),
        "Valor Total em Estoque (R$)": f"{dashboard_data.get('total_inventory_value', 0):.2f}",
        "Custo Total do Estoque (R$)": f"{dashboard_data.get('total_inventory_cost', 0):.2f}",
        "Lucro Potencial (R$)": f"{dashboard_data.get('potential_profit', 0):.2f}"
    }
    
    low_stock = dashboard_data.get('low_stock_alerts', [])
    # Formata a lista de produtos de forma descritiva
    products_text = ""
    if low_stock:
        for p in low_stock:
            # Assumindo que low_stock_alerts pode não ter todos os campos de preço no schema atual,
            # mas o prompt pede análise. Se o schema DashboardSummary->LowStockAlert tiver apenas (id, name, sku, current_stock),
            # o modelo vai analisar apenas o risco de ruptura. Se tiver preço, melhor.
            # Baseado no código anterior, LowStockAlert tem: id, name, sku, current_stock.
            # O usuário mencionou no exemplo "Preço R$ 7200", mas o endpoint dashboard atual envia LowStockAlert.
            # Vamos formatar com o que temos para evitar alucinação de preços inexistentes.
            products_text += f"- {p.get('name')} (SKU: {p.get('sku')}): Estoque atual {p.get('current_stock')} unidades.\n"
    else:
        products_text = "Nenhum produto com estoque baixo no momento."

    recent_tx = dashboard_data.get('recent_transactions', [])
    tx_text = ""
    if recent_tx:
        for tx in recent_tx:
             tx_text += f"- {tx.get('type')} de {tx.get('quantity')} itens em {tx.get('date')}\n"
    
    
    prompt = f"""
    Você é um Diretor Financeiro (CFO) e Especialista em Supply Chain. 
    Sua missão é analisar os dados abaixo e fornecer um relatório técnico em Markdown.
    
    --- METRICAS GERAIS DA EMPRESA ---
    {json.dumps(metrics, indent=2, ensure_ascii=False)}
    
    --- ALERTA DE ESTOQUE BAIXO (PRODUTOS INDIVIDUAIS) ---
    {products_text}
    
    --- ULTIMAS MOVIMENTACOES ---
    {tx_text}
    
    INSTRUCOES RIGIDAS:
    1. Não confunda o 'Valor Total em Estoque' da empresa com o preço de um único produto.
    2. Analise a saúde financeira baseada no Lucro Potencial vs Custo.
    3. Identifique riscos de ruptura (estoque baixo) e sugira reposição se houver saídas recentes.
    4. Seja direto, crítico e use tópicos.
    
    IMPORTANTE: Responda EXCLUSIVAMENTE em Português do Brasil.
    """

    try:
        print(f"--- [LLM Service] Iniciando requisição para o Ollama (Modelo: llama3.2:1b) ---")
        
        # Timeout definido para 180 segundos conforme solicitado
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_URL}/api/generate",
                json={
                    "model": "llama3.2:1b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "num_predict": 400,
                        "temperature": 0.1,
                        "repeat_penalty": 1.2
                    }
                }
            )
            print(f"--- [LLM Service] Resposta recebida. Status: {response.status_code} ---")
            
            response.raise_for_status()
            result = response.json()
            insight = result.get("response", "").strip()
            
            if not insight:
                print("--- [LLM Service] Erro: IA retornou uma resposta vazia ---")
                return "A IA está temporariamente indisponível (retornou resposta vazia). Tente novamente em instantes."
                
            return insight
            
    except httpx.ConnectError:
        print("--- [LLM Service] Erro: Ollama não encontrado ---")
        return "IA indisponível no momento (Ollama não encontrado), mas seu estoque está seguro e operante."
    except httpx.ReadTimeout:
        print("--- [LLM Service] Erro: Timeout (180s) excedido ---")
        return "O servidor de IA está sobrecarregado, tente novamente"
    except httpx.HTTPStatusError as e:
        print(f"--- [LLM Service] Erro HTTP: {e.response.status_code} ---")
        return f"Erro na API da IA: Status {e.response.status_code} - {e.response.text}"
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Erro inesperado ao consultar o oráculo de estoque: {type(e).__name__} - {str(e)}"

async def get_embedding(text: str) -> list[float]:
    """
    Gera um vetor de embedding para um texto usando o modelo nomic-embed-text do Ollama.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_URL}/api/embeddings",
                json={
                    "model": "nomic-embed-text",
                    "prompt": text
                }
            )
            response.raise_for_status()
            result = response.json()
            return result.get("embedding", [])
    except Exception as e:
        print(f"--- [LLM Service] Erro ao gerar embedding: {str(e)} ---")
        return []

async def generate_support_answer(question: str, context_text: str) -> str:
    """
    Usa um LLM local (via Ollama) para atuar como um agente de suporte,
    respondendo à dúvida do usuário com base no manual fornecido (context_text).
    """
    
    prompt = f"""
    Você é o Agente de Suporte Especialista do nosso ERP SaaS de Gestão de Estoque.
    Seja extremamente útil e amigável.
    
    Abaixo está a BASE DE CONHECIMENTO do sistema, contendo o manual e os tutoriais passo a passo.
    Você DEVE usar essa base para responder a pergunta do usuário.
    
    --- BASE DE CONHECIMENTO (MANUAL DO SISTEMA) ---
    {context_text}
    
    --- PERGUNTA DO USUÁRIO ---
    {question}
    
    INSTRUÇÕES RÍGIDAS:
    1. Responda à pergunta do usuário baseando-se no texto acima.
    2. Se a informação não constar no texto, diga educadamente que não sabe e peça para contatar o suporte humano.
    3. Formate a sua resposta usando Markdown (listas, negritos, etc.) para ficar fácil de ler no chat.
    4. Responda sempre em Português do Brasil.
    """

    try:
        print(f"--- [LLM Service] Iniciando requisição de Suporte para o Ollama ---")
        
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_URL}/api/generate",
                json={
                    "model": "llama3.2:1b",
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1, # Temperatura baixa para garantir fidelidade ao manual
                        "num_predict": 500,
                    }
                }
            )
            
            response.raise_for_status()
            result = response.json()
            answer = result.get("response", "").strip()
            
            if not answer:
                return "Desculpe, meu cérebro processou a informação mas não conseguiu formular a resposta. Tente novamente."
                
            return answer
            
    except httpx.ConnectError:
        return "Desculpe, nosso servidor de IA de Suporte está offline no momento."
    except httpx.ReadTimeout:
        return "Desculpe, a busca no manual demorou muito. Tente reformular a pergunta."
    except Exception as e:
        return "Ocorreu um erro interno ao contatar o suporte automatizado."

async def generate_restock_advice(critical_products: list) -> dict:
    """
    Pede ao Ollama para gerar um plano de reposição estruturado em JSON
    baseado nos produtos com estoque crítico.
    """
    
    if not critical_products:
        return {"advice": "Nenhum produto em estado crítico.", "suggested_purchases": []}

    context_text = ""
    for p in critical_products:
        supplier_info = f"Fornecedor: {p['supplier_name']} ({p['supplier_id']})" if p['supplier_id'] else "Sem Fornecedor"
        context_text += (
            f"- Produto: {p['name']} (ID: {p['id']}) | "
            f"Estoque Atual: {p['current_stock']} | Mínimo Exigido: {p['min_stock']} | "
            f"Custo Unitário: R$ {p['cost_price']:.2f} | {supplier_info}\n"
        )

    system_prompt = """
    Você é um Diretor de Suprimentos (CSO) de um ERP. 
    Analise a lista de produtos com estoque crítico abaixo.
    
    INSTRUÇÕES RÍGIDAS:
    1. Calcule a 'suggested_quantity' para que o novo estoque fique pelo menos 20% acima do mínimo exigido. (Ex: se mínimo é 10 e atual é 2, sugiro comprar 10 para ficar com 12).
    2. Devolva a resposta EXATAMENTE no formato JSON abaixo. NÃO inclua nenhum texto adicional, saudações ou formatação markdown (sem ```json).
    
    FORMATO ESPERADO:
    {
      "advice": "Mensagem curta em português do Brasil explicando a decisão.",
      "suggested_purchases": [
        {
          "product_id": "uuid-do-produto",
          "supplier_id": "uuid-do-fornecedor-se-houver-senao-null",
          "suggested_quantity": numero_inteiro
        }
      ]
    }
    """

    prompt = f"{system_prompt}\n\n--- PRODUTOS CRÍTICOS ---\n{context_text}"

    try:
        print(f"--- [LLM Oracle] Iniciando requisição para o Ollama (JSON Mode) ---")
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_URL}/api/generate",
                json={
                    "model": "llama3.2:1b",
                    "prompt": prompt,
                    "stream": False,
                    "format": "json", # Força o Ollama a cuspir JSON
                    "options": {
                        "temperature": 0.0, # Zero alucinação
                        "top_p": 0.1
                    }
                }
            )
            
            response.raise_for_status()
            result = response.json()
            raw_json_str = result.get("response", "{}").strip()
            
            # Tenta parsear o JSON retornado pela IA
            try:
                advice_data = json.loads(raw_json_str)
                return advice_data
            except json.JSONDecodeError:
                print("--- [LLM Oracle] Erro: Ollama não retornou um JSON válido ---")
                print(f"Raw: {raw_json_str}")
                return {
                    "advice": "O modelo de IA falhou em estruturar os dados. Tente novamente.",
                    "suggested_purchases": []
                }
                
    except httpx.ConnectError:
        raise Exception("Serviço de IA (Ollama) está offline ou inacessível.")
    except httpx.ReadTimeout:
        raise Exception("O servidor de IA demorou muito para responder (Timeout).")
    except Exception as e:
        raise Exception(f"Erro na geração de reposição: {str(e)}")
