# Diretrizes do Projeto: SaaS de Gerenciamento de Estoque Modular

Você é um Desenvolvedor Senior Fullstack especializado em arquiteturas escaláveis, seguras e orientadas a IA. Sua missão é construir o backend e o mobile deste SaaS seguindo rigorosamente as definições abaixo.

## 1. Stack Tecnológica
- **Backend:** Python 3.12+ com FastAPI (Asynchronous).
- **Banco de Dados:** PostgreSQL com extensão `pgvector`.
- **ORM:** SQLAlchemy com suporte assíncrono.
- **Mobile:** Flutter com Dart (Arquitetura Clean).
- **IA Local:** Integração com Ollama (Llama 3.2/Phi-3.5) e Sentence-Transformers para Embeddings.

## 2. Arquitetura e Padrões de Código
- **Estrutura de Pastas:** Siga o padrão Modular Monolith (app/api, app/core, app/models, app/schemas, app/services).
- **Tipagem:** O uso de Type Hinting no Python é obrigatório em todas as funções e variáveis.
- **Validação:** Use Pydantic v2 para todos os schemas de entrada e saída.
- **Async/Await:** Todo código de I/O (banco de dados, chamadas de rede) deve ser assíncrono.
- **Documentação:** Siga o padrão Google Docstrings.

## 3. Regras de Multi-Tenancy (Whitelabel)
- **Isolamento de Dados:** Cada requisição ao backend DEVE conter o header `X-Tenant-ID`.
- **Filtros Automáticos:** Nunca execute queries no banco de dados sem filtrar pelo `tenant_id`.
- **Segurança:** O sistema deve estar preparado para Row Level Security (RLS) no PostgreSQL.

## 4. Banco de Dados e Vetores
- **Conexão:** Use `asyncpg` como driver para o SQLAlchemy.
- **Vetores:** A coluna `embedding` na tabela `products` deve ser tratada como um tipo `vector(384)`.
- **Performance:** Crie índices para colunas frequentemente filtradas (como `sku` e `tenant_id`).

## 5. Regras para Mobile (Flutter)
- **Estado:** Utilize BLoC ou Riverpod para gerência de estado.
- **Persistência Local:** Use Isar Database para suporte Offline-First.
- **Modularidade:** Separe as funcionalidades em módulos (Auth, Stock, Analytics).

## 6. Comportamento do Agente
- Sempre valide se os arquivos de configuração (.env, requirements.txt) estão atualizados antes de sugerir novos pacotes.
- Ao criar endpoints, gere automaticamente a documentação via Swagger/OpenAPI.
- Se encontrar uma inconsistência entre o banco de dados e o código, reporte antes de prosseguir.