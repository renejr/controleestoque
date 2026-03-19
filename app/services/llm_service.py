import httpx
import json

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
                "http://localhost:11434/api/generate",
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
