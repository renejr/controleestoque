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
| **TMS (Gestão de Frota e Logística)** | Cadastro de veículos com capacidades dimensionais e de peso. Motor de Bin Packing 3D para calcular cubagem de carga. | `routes/vehicles.py`, `routes/fleet.py`, `models/vehicle.py`, `services/logistics_service.py` | `services/vehicle_service.dart`, `models/vehicle.dart`, `screens/vehicles_screen.dart`, `screens/vehicle_form_screen.dart` | Backend: `py3dbp` (Bin Packing 3D). |

---

## Estado Atual

*   **Infraestrutura Core:** Servidor FastAPI configurado, banco PostgreSQL rodando com Alembic para migrações. App Flutter consumindo API com tratamento de erros.
*   **Segurança:** Multi-tenancy implementado via UUID. Autenticação JWT funcional (Login e persistência de sessão).
*   **Gestão de Produtos (Logística Avançada):** CRUD completo com Importação em Lote via CSV (Dry-Run e Inserção otimizada). Campos logísticos (Código de Barras, Dimensões, Peso, Estoque Mínimo). Validação de integridade no banco (SKU/Barcode únicos por tenant). Paginação (Infinite Scroll) e Pull-to-Refresh funcionando. Exportação em PDF e CSV. Filtros rápidos (Estoque Crítico).
*   **Gestão de Fornecedores e Compras:** Módulo implementado com CRUD de fornecedores e estrutura completa de Ordens de Compra (Pedidos). Integração de status da Ordem com o gatilho de transação de Estoque. **Exportação Profissional em PDF** das Ordens de Compra.
*   **Gestão de Frota (TMS):** Módulo implementado. CRUD de veículos (Placa, Modelo, Tara, Capacidade Máxima de Peso e Volume, Dimensões do Baú). Interface de gerenciamento no Flutter com Pull-to-Refresh e menu de gaveta.
*   **Motor de Logística (Bin Packing):** Backend integrado à biblioteca `py3dbp`. Rota de simulação de carga (`/fleet/pack-order`) ativa, capaz de calcular quais caixas cabem no caminhão, gerar as coordenadas 3D (x, y, z) de empacotamento e calcular o percentual de ocupação de peso e volume.
*   **Módulo Fiscal (Fase 1):** Tela de configurações do Tenant (Razão Social, CNPJ, Regime) e campos fiscais brasileiros nos produtos (NCM, CFOP, CEST, Origem).
*   **Auditoria e Logs (Caixa Preta):** Implementação de log passivo no backend via gatilhos em rotas de Produtos, Fornecedores, Compras e Tenant, salvando JSONB "Antes e Depois". Frontend com Painel do Inspetor e Modal de Diferenças.
*   **Inteligência Artificial (CFO e CSO):** Integração via Ollama consolidada. O LLM atua como CFO gerando análises formatadas em Markdown e como CSO sugerindo planos de reposição de estoque (JSON) que alimentam o carrinho de compras automaticamente (Human-in-the-Loop).
*   **Busca Avançada:** Busca vetorial (`pgvector`) funcional, com filtro de similaridade (`cosine_distance < 0.5`) para evitar falsos positivos.
*   **Módulo Financeiro:** Rotas de resumo financeiro ativas. Gráficos de barras de Entradas vs Saídas e Receita vs Custo implementados no frontend usando `fl_chart`. Registro de transações carimba valores históricos.

---

## Próximos Passos (Backlog Técnico)

1.  **Integração Visual do Bin Packing:**
    *   Criar tela no Flutter para disparar a simulação de carga (`/fleet/pack-order`) a partir de uma Ordem de Compra ou Venda.
    *   (Opcional) Renderizar as caixas em 3D usando as coordenadas do relatório.
2.  **Módulo Fiscal (Integração SEFAZ - Fase 2):**
    *   Preparar arquitetura para emissão de NFe baseada nas transações de `OUT` e dados fiscais do Tenant/Produto.
3.  **Testes Automatizados:**
    *   Expandir Pytest para cobrir o motor de logística e geração de PDF.
    *   Implementar testes de Widget no Flutter para fluxos de checkout/saída.