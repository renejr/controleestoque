# 📦 Gestão de Estoque Inteligente (SaaS)

Bem-vindo ao **Gestão de Estoque Inteligente**, um sistema ERP/WMS moderno, construído com arquitetura Multi-Tenant e inteligência artificial integrada para análise de dados e lucratividade.

Este projeto é dividido em um poderoso **Backend em Python (FastAPI)** e um aplicativo **Frontend multiplataforma em Flutter**.

---

## 🚀 Principais Recursos

- 🔐 **Multi-Tenant (SaaS) e RBAC Avançado:** Isolamento total de dados entre diferentes empresas/clientes usando PostgreSQL e UUID. Controle de acesso rigoroso por 7 Perfis de Usuário (ADMIN, MANAGER, OPERATOR, SALES, FINANCIAL, DRIVER, AUDITOR), com visibilidade de UI e proteção de rotas API baseadas em funções.
- 📦 **Catálogo de Produtos:** Cadastro completo com regras logísticas (SKU, Código de Barras, Peso, Dimensões e Estoque Mínimo), classificação fiscal brasileira e motor de **Importação em Lote via CSV** com validação inteligente (Dry-Run).
- 💸 **Módulo Financeiro e Vendas:** Análise de Receita, Custo (CMV) e Lucro Líquido gerados automaticamente a partir das movimentações de estoque. Módulo de Pedidos de Venda com baixa atômica de estoque. Dashboard executivo na tela inicial com gráficos vetoriais diários (`fl_chart`).
- 🚚 **Gestão de Compras e Fornecedores:** Controle centralizado de parceiros, fluxo de Ordens de Compra com **gatilho automático de entrada em estoque** e geração de **Documentos PDF Profissionais**.
-  **Gestão de Frota e Logística (TMS):** Cadastro de veículos, **Centros de Distribuição (Ponto 0 dinâmico)**, motor de **Bin Packing 3D** (Cubagem) com **Simulador de Carga Visual em Flutter** (Planta Baixa 2D inteligente, legendas de agrupamento e indicadores de empilhamento). Exportação nativa de **Romaneios Táticos em PDF** (`reportlab`).
- 🔄 **Módulo de Coleta (Inbound/Logística Reversa):** Gestão completa do ciclo de coletas de mercadorias. Inclui formulário operacional para escalonamento (vinculando CDs de destino e Veículos), Roteirização em lote de OCs pendentes, visualização no mapa com pinos diferenciados (Galpão Azul para CD e Arquivo Verde para coletas), e um **Painel de Execução Mobile** para o motorista dar baixa na coleta em tempo real no campo (com suporte previsto para câmera e scanner).
- 🗺️ **Roteirização Otimizada Avançada:** Geocodificação automática de endereços de clientes e CDs utilizando `geopy` (Nominatim). Sequência ótima calculada com OR-Tools e rotas urbanas obtidas do **OSRM** com perfil terrestre (`/route/v1/driving/`) e geometria completa da via (`geometries=geojson&overview=full`). O Frontend renderiza a Polyline azul exatamente sobre as ruas (decodificação GeoJSON), diferencia pinos de **CD** (galpão azul) e **Entregas** (vermelho numerado) e exibe instruções em português em UI adaptativa: painel lateral no Desktop e BottomSheet no Mobile.
- 💬 **Chat Corporativo em Tempo Real:** Comunicação instantânea via WebSockets entre os membros da equipe de cada empresa, com notificações, isolamento estrito, proteção de Handshake segura contra falhas de JWT e mecanismo de *Heartbeat* (Ping/Pong) para manter conexões ativas e evitar desconexões silenciosas.
- 🏛️ **Configurações Fiscais e Integrações:** Gestão de Razão Social, CNPJ, Inscrição Estadual, Certificado Digital. Webhooks nativos para provisionamento de empresas via gateways de pagamento externos.
- 🕵️ **Caixa Preta (Auditoria):** Sistema de logs invisível que rastreia alterações críticas (INSERT, UPDATE, DELETE) em tempo real, permitindo aos administradores inspecionarem o "Antes e Depois" de cada registro através de um painel de visualização de JSON. Inclui rotas globais para Super Admins do sistema.
- 🤖 **IA Dupla e Chatbot de Suporte (RAG):** Oráculos alimentados por LLM local (Ollama / Llama 3.2). O CFO gera relatórios gerenciais (com tom de voz dinâmico parametrizável por empresa), o CSO monta o carrinho de compras automaticamente para reposição e **responde dúvidas interativas com contexto de estoque**, e o **Agente de Suporte** responde às dúvidas dos usuários em tempo real baseado no manual do sistema, reduzindo a carga do atendimento humano.
- 🧪 **Segurança e Estabilidade:** Suíte de Testes Automatizados com `pytest` e transações de banco de dados isoladas para garantir que o motor financeiro e logístico não quebrem em produção.
- 🎨 **Identidade Visual Dinâmica:** Configuração White-Label por locatário (Tenant). A logo e o nome da empresa são injetados automaticamente na interface e em todos os relatórios PDF gerados (Romaneios, Ordens de Compra).
- 🌐 **Suporte Offline-First (Multiplataforma):** Banco de dados local robusto integrado. Funciona no Android/iOS via `sqflite` nativo e possui suporte total na Web e no Desktop através de compilação FFI (WASM/Workers) e persistência via IndexedDB.

---

## 🛠️ Tecnologias Utilizadas

### Backend
- **Linguagem:** Python 3.12+
- **Framework:** FastAPI
- **ORM:** SQLAlchemy (Async)
- **Banco de Dados:** PostgreSQL (com extensão `pgvector`)
- **Migrações:** Alembic
- **Autenticação:** JWT (JSON Web Tokens) e Passlib (Bcrypt)
- **IA Local:** Ollama

### Frontend
- **Framework:** Flutter (Dart)
- **Gerenciamento de Estado:** Provider
- **Gráficos:** fl_chart
- **Relatórios:** Exportação para PDF e CSV nativa

---

## ⚙️ Como Rodar e Expor o Projeto Localmente

### 1. Pré-requisitos
- [Python 3.12+](https://www.python.org/downloads/)
- [Flutter SDK](https://docs.flutter.dev/get-started/install)
- [PostgreSQL](https://www.postgresql.org/) (com a extensão `pgvector` instalada)
- [Ollama](https://ollama.com/) (Para rodar o assistente de IA)

### 2. Configurando o Backend (FastAPI)

1. Abra um terminal na raiz do projeto e crie um ambiente virtual:
   ```bash
   python -m venv venv
   ```

2. Ative o ambiente virtual:
   - Windows: `.\venv\Scripts\activate`
   - Linux/Mac: `source venv/bin/activate`

3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure a URL do Banco de Dados no arquivo `app/core/config.py` ou via variável de ambiente `DATABASE_URL`. O banco deve ter a extensão `pgvector` habilitada:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

5. Rode as migrações para criar as tabelas no banco de dados:
   ```bash
   alembic upgrade head
   ```

6. Inicie o servidor:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   *A API estará disponível em `http://localhost:8000`. Acesse `http://localhost:8000/docs` para ver a documentação interativa do Swagger.*

### 3. Configurando a Inteligência Artificial (Ollama)
Para que a aba "Oráculo de IA" funcione, você precisa ter o Ollama rodando localmente.
1. Instale o Ollama no seu computador.
2. No terminal, baixe e rode o modelo especificado no projeto (ex: Llama 3.2 1B):
   ```bash
   ollama run llama3.2:1b
   ```
   *O backend está configurado para se comunicar com o Ollama na porta padrão `11434`.*

### 4. Configurando o Frontend (Flutter)

1. Abra um novo terminal e navegue até a pasta do frontend:
   ```bash
   cd frontend
   ```

2. Baixe os pacotes do Dart:
   ```bash
   flutter pub get
   ```

3. Verifique a URL da API. No arquivo `lib/core/constants.dart`, certifique-se de que `apiBaseUrl` aponta para o seu backend local (ex: `http://localhost:8000`) ou para a URL do seu túnel do Cloudflare.

4. Rode o aplicativo:
   ```bash
   flutter run -d web-server --web-port 5000
   ```

### 5. Expondo na Internet (Cloudflare Tunnels)
Para acessar o sistema pelo seu celular ou enviar um link para teste global sem abrir portas no roteador, utilize o Cloudflare. 
Consulte o guia completo no arquivo [MANUAL_EXPOSICAO_CLOUDFLARE.md](./MANUAL_EXPOSICAO_CLOUDFLARE.md).

---

## 🗺️ Mapa Arquitetural
Para entender a fundo a arquitetura do projeto, as dependências entre os módulos e os próximos passos do roadmap, consulte o arquivo [PROJECT_MAP.md](./PROJECT_MAP.md) localizado na raiz do repositório.

---

## 🛡️ Licença
Este projeto é de uso privado/proprietário.
