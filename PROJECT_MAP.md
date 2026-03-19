# Mapeamento do Projeto - SaaS Gestão de Estoque Inteligente

## Visão Geral
Sistema de Gestão de Estoque (WMS) evoluindo para um ERP SaaS focado em lucratividade e inteligência de dados. A arquitetura é dividida em um Frontend Mobile/Web feito em **Flutter**, um Backend em **Python (FastAPI)** com banco de dados **PostgreSQL** (usando **pgvector** para buscas semânticas), e um módulo de Inteligência Artificial rodando localmente via **Ollama** (modelos como Llama 3.2 1B) para geração de insights financeiros e logísticos. O sistema é Multi-Tenant, garantindo isolamento de dados por cliente.

---

## Arquitetura de Pastas

```text
C:\gestaoestoque\
├── app/                        # Backend (Python / FastAPI)
│   ├── api/                    # Controladores da API
│   │   ├── endpoints/          # (Legado - migrado para rotas)
│   │   └── routes/             # Rotas do FastAPI agrupadas por domínio
│   ├── core/                   # Configurações de segurança, banco e dependências
│   ├── models/                 # Modelos do SQLAlchemy (Mapeamento Objeto-Relacional)
│   ├── schemas/                # Schemas do Pydantic (Validação de dados entrada/saída)
│   ├── services/               # Regras de negócio complexas e integrações externas (ex: Ollama)
│   └── main.py                 # Ponto de entrada do servidor FastAPI
├── frontend/                   # Frontend (Flutter / Dart)
│   ├── lib/
│   │   ├── core/               # Constantes, temas e cliente HTTP base
│   │   ├── models/             # Classes de modelo de dados do Dart
│   │   ├── providers/          # Gerenciamento de estado global (Provider)
│   │   ├── screens/            # Telas da interface de usuário
│   │   │   └── widgets/        # Componentes visuais reutilizáveis
│   │   ├── services/           # Comunicação com a API (HTTP)
│   │   └── main.dart           # Ponto de entrada e configuração de rotas/estado do app
│   └── pubspec.yaml            # Gerenciamento de dependências do Flutter
├── alembic/                    # Arquivos de migração do banco de dados (Backend)
├── venv/                       # Ambiente virtual Python
└── alembic.ini                 # Configuração do Alembic
```

---

## Dicionário de Módulos

| Módulo | Descrição | Arquivos Backend (.py) | Arquivos Frontend (.dart) | Dependências Principais |
| :--- | :--- | :--- | :--- | :--- |
| **Auth & Multi-Tenant** | Gerencia autenticação JWT e isolamento de dados por locatário (Tenant). | `routes/auth.py`, `routes/tenants.py`, `models/tenant.py`, `models/user.py`, `core/security.py` | `services/auth_service.dart`, `providers/auth_provider.dart`, `screens/login_screen.dart` | Backend: Passlib, JWT, Bcrypt. Frontend: SharedPreferences. Todos os módulos dependem do Auth. |
| **Catálogo de Produtos** | CRUD de produtos, controle de estoque inicial, regras de logística (Estoque Mínimo, Dimensões, Código de Barras), precificação e busca vetorial inteligente. | `routes/products.py`, `models/product.py`, `schemas/product.py` | `services/product_service.dart`, `models/product.dart`, `screens/products_screen.dart`, `widgets/product_form_modal.dart` | Backend: pgvector (Busca Semântica). Frontend: csv, pdf, printing, share_plus (Exportação). |
| **Transações de Estoque** | Registro imutável de entradas (IN) e saídas (OUT), gravando custo e preço no momento do fato. | `routes/transactions.py`, `models/transaction.py`, `schemas/transaction.py` | `services/transaction_service.dart`, `models/transaction.dart` (implícito no Dashboard/Product) | Backend: Modifica `product.current_stock`. |
| **Fornecedores (Compras)** | Cadastro e gestão de Fornecedores, base para o futuro módulo de Ordens de Compra. | `routes/suppliers.py`, `models/supplier.py`, `schemas/supplier.py` | `services/supplier_service.dart`, `models/supplier.dart`, `screens/suppliers_screen.dart`, `widgets/supplier_form_modal.dart` | Depende diretamente de Auth para isolamento de Tenant. |
| **Módulo Fiscal** | Configuração de dados fiscais da empresa (CNPJ, Razão Social, Regime) e do Produto (NCM, CFOP, CEST, Origem). | `routes/tenants.py`, `models/tenant.py`, `models/product.py` | `screens/tenant_settings_screen.dart`, `widgets/product_form_modal.dart` | Prepara o sistema para futura emissão de NFe. |
| **Compras (Ordens)** | Criação e gestão de Ordens de Compra (Cabeçalho e Itens), vinculando Fornecedores a Produtos. | `routes/purchase_orders.py`, `models/purchase_order.py`, `models/purchase_order_item.py` | `services/purchase_order_service.dart`, `models/purchase_order.dart`, `screens/purchase_orders_screen.dart` | Relacionamento 1:N com Itens, N:1 com Fornecedores. |
| **Dashboards Analíticos** | Agregação de dados para KPIs de visão geral (Total de itens, alertas de ruptura, histórico recente). | `routes/dashboard.py`, `schemas/dashboard.py` | `screens/dashboard_screen.dart`, `models/dashboard_summary.dart` | Backend: Agrega dados de Produtos e Transações. Frontend: fl_chart. |
| **Financeiro** | Análise de lucratividade baseada em transações (Receita, Custo, Margem) e gráficos de série temporal. | `routes/finance.py`, `schemas/finance.py` | `services/finance_service.dart`, `models/finance_summary.dart`, `screens/finance_screen.dart` | Depende diretamente de Transações (OUT) e Produtos (Custo/Preço). |
| **Oráculo de IA (LLM)** | IA Local atuando como CFO (Insights Financeiros em Markdown) e CSO (Plano de Reposição de Estoque em JSON). | `routes/dashboard.py`, `routes/oracle.py`, `services/llm_service.py` | `screens/ai_consultant_screen.dart`, `screens/oracle_restock_screen.dart` | Backend: httpx, Ollama (Llama 3.2 1B). Frontend: flutter_markdown. |
| **Auditoria e Logs** | A "Caixa Preta". Rastreia alterações críticas (INSERT, UPDATE, DELETE) capturando o JSON de "Antes e Depois" com base no Tenant. | `routes/audit_logs.py`, `services/audit_service.py`, `models/audit_log.py` | `services/audit_service.dart`, `models/audit_log.dart`, `screens/audit_logs_screen.dart` | Backend: JSONB (PostgreSQL). Frontend: Modal com JsonEncoder (Pretty Print). |
| **TMS (Gestão de Frota e Logística)** | Cadastro de veículos com capacidades dimensionais e de peso. Motor de Bin Packing 3D para calcular cubagem de carga. | `routes/vehicles.py`, `routes/fleet.py`, `models/vehicle.py`, `services/logistics_service.py` | `services/vehicle_service.dart`, `models/vehicle.dart`, `screens/vehicles_screen.dart`, `screens/vehicle_form_screen.dart`, `screens/cargo_simulator_screen.dart`, `widgets/truck_bed_visualizer.dart` | Backend: `py3dbp` (Bin Packing 3D). Frontend: `CustomPainter` (Planta Baixa 2D). |
| **Vendas e Clientes** | Cadastro de Clientes e Pedidos de Venda. Gatilho automático logístico de dedução de estoque (OUT) ao marcar pedido como 'SHIPPED'. | `routes/customers.py`, `routes/sales_orders.py`, `models/customer.py`, `models/sales_order.py` | `services/customer_service.dart`, `services/sales_order_service.dart`, `screens/customers_screen.dart`, `screens/sales_orders_screen.dart` | Uso de `with_for_update` para locks de concorrência transacional no estoque. |
| **RBAC e Equipe** | Controle de Acesso Baseado em Perfis (ADMIN, MANAGER, OPERATOR). Restringe rotas e botões da UI. | `routes/users.py`, `models/user.py`, `schemas/user.py` | `services/user_service.dart`, `providers/auth_provider.dart`, `screens/users_screen.dart` | Decode de JWT em Base64 nativo no Frontend. Proteção de rotas sensíveis no Backend. |
| **Feedback e Sugestões** | Caixa de sugestões para os usuários do Tenant enviarem feedbacks de uso para os administradores. | `routes/suggestions.py`, `models/suggestion.py` | `services/suggestion_service.dart`, `screens/suggestions_screen.dart` |  |
| **Testes Automatizados** | Suite de testes para garantir a estabilidade do motor de Vendas, Compras, Produtos, Frota e Motor Logístico. | `tests/conftest.py`, `tests/api/test_*.py` | - | Backend: `pytest`, `httpx`. Uso de transações de DB isoladas (Rollback) por teste. |

---

## Estado Atual

*   **Infraestrutura Core:** Servidor FastAPI configurado, banco PostgreSQL rodando com Alembic para migrações. App Flutter consumindo API com tratamento de erros.
*   **Segurança:** Multi-tenancy implementado via UUID. Autenticação JWT funcional (Login e persistência de sessão).
*   **Gestão de Produtos (Logística Avançada):** CRUD completo com Importação em Lote via CSV (Dry-Run e Inserção otimizada). Campos logísticos (Código de Barras, Dimensões, Peso, Estoque Mínimo). Validação de integridade no banco (SKU/Barcode únicos por tenant). Paginação (Infinite Scroll) e Pull-to-Refresh funcionando. Exportação em PDF e CSV. Filtros rápidos (Estoque Crítico).
*   **Gestão de Fornecedores e Compras:** Módulo implementado com CRUD de fornecedores e estrutura completa de Ordens de Compra (Pedidos). Integração de status da Ordem com o gatilho de transação de Estoque. **Exportação Profissional em PDF** das Ordens de Compra.
*   **Gestão de Frota (TMS):** Módulo implementado. CRUD de veículos (Placa, Modelo, Tara, Capacidade Máxima de Peso e Volume, Dimensões do Baú). Interface de gerenciamento no Flutter com Pull-to-Refresh e menu de gaveta.
*   **Motor de Logística (Bin Packing) e Visualizador 2D:** Backend integrado à biblioteca `py3dbp`. Rota de simulação de carga (`/fleet/pack-order`) ativa. Frontend equipado com um **Simulador de Carga** que utiliza `CustomPainter` para desenhar a "Planta Baixa" (Blueprint) do caminhão e o encaixe visual e posicional das caixas dentro dele.
*   **Vendas e Clientes:** CRUD de Clientes. Master-Detail para Pedidos de Venda. Implementação crítica de controle de concorrência (`with_for_update()`) que realiza a dedução atômica e irreversível do estoque assim que um pedido é marcado como 'SHIPPED'.
*   **RBAC (Controle de Acesso Baseado em Perfis):** Modelo de Usuários adaptado com campos de `role` (ADMIN, MANAGER, OPERATOR). Frontend realiza o *decode* do JWT para ocultar rotas e botões sensíveis de usuários sem privilégio. Apenas Admins podem criar e excluir usuários.
*   **Feedback e Sugestões:** Canal de comunicação interno para envio de sugestões dos usuários.
*   **Módulo Fiscal (Fase 1):** Tela de configurações do Tenant (Razão Social, CNPJ, Regime) e campos fiscais brasileiros nos produtos (NCM, CFOP, CEST, Origem).
*   **Testes Automatizados (QA):** Suíte de testes `pytest` implementada no Backend, utilizando sessões de banco de dados transacionais com rollback automático. Cobertura atual: Multi-Tenant, Vendas (Validação de Estoque) e TMS (Algoritmo de Cubagem).
*   **Auditoria e Logs (Caixa Preta):** Implementação de log passivo no backend via gatilhos em rotas de Produtos, Fornecedores, Compras, Usuários e Tenant, salvando JSONB "Antes e Depois". Frontend com Painel do Inspetor e Modal de Diferenças.
*   **Inteligência Artificial (CFO e CSO):** Integração via Ollama consolidada. O LLM atua como CFO gerando análises formatadas em Markdown e como CSO sugerindo planos de reposição de estoque (JSON) que alimentam o carrinho de compras automaticamente (Human-in-the-Loop).
*   **Busca Avançada:** Busca vetorial (`pgvector`) funcional, com filtro de similaridade (`cosine_distance < 0.5`) para evitar falsos positivos.
*   **Módulo Financeiro:** Rotas de resumo financeiro ativas. Gráficos de barras de Entradas vs Saídas e Receita vs Custo implementados no frontend usando `fl_chart`. Registro de transações carimba valores históricos.

---

## Próximos Passos (Backlog Técnico)

1.  **Módulo Fiscal (Integração SEFAZ - Fase 2):**
    *   Preparar arquitetura para emissão de NFe baseada nas transações de `OUT` e dados fiscais do Tenant/Produto.
2.  **Expansão de Testes Automatizados:**
    *   Expandir Pytest para cobrir rotas de Produtos, Exportação de PDF e Usuários (RBAC).
    *   Implementar testes de Widget no Flutter para fluxos de checkout/saída.