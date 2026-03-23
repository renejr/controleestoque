# 🌐 Manual de Exposição do App na Internet (via Cloudflare Tunnels)

Este manual descreve o passo a passo para expor o seu SaaS de Gestão de Estoque (rodando localmente na sua máquina) para a internet. Isso é extremamente útil para:
- Testar o aplicativo no seu celular (4G/5G).
- Enviar o link para um cliente ou investidor testar de qualquer lugar do mundo.
- Contornar problemas de rede (CGNAT, portas bloqueadas no roteador).

Utilizaremos o **Cloudflare Tunnels** (antigo Argo Tunnel), que cria uma conexão segura (HTTPS automático) do seu computador até a rede global da Cloudflare de forma 100% gratuita.

---

## 🛠️ Pré-requisitos

1. **Ter o projeto rodando localmente** (Banco de dados PostgreSQL, IA Ollama, etc).
2. **Ter o aplicativo `cloudflared` instalado no seu computador.**
   - *Se não tiver, baixe e instale a partir do site oficial da Cloudflare: [Cloudflare Tunnel Downloads](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)*

---

## 🚀 Passo a Passo

Para que tudo funcione, precisaremos de **2 túneis separados**: um para o Backend (FastAPI) e outro para o Frontend (Flutter).

### Passo 1: Iniciar e Expor o Backend (FastAPI)

O Frontend (no celular) precisa conseguir se comunicar com a API e o banco de dados.

1. Abra um terminal na raiz do projeto (`c:\gestaoestoque`).
2. Inicie o backend na porta padrão `8000`:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
3. Abra um **segundo terminal** e inicie o túnel do Cloudflare apontando para a porta 8000:
   ```bash
   cloudflared tunnel --url http://localhost:8000
   ```
4. O Cloudflare vai gerar vários logs. Procure por uma linha semelhante a esta:
   ```text
   +--------------------------------------------------------------------------------------------+
   |  Your quick Tunnel has been created! Visit it at (it may take some time to be reachable):  |
   |  https://nome-aleatorio-aqui.trycloudflare.com                                             |
   +--------------------------------------------------------------------------------------------+
   ```
5. **Copie essa URL (ex: `https://discs-residence...trycloudflare.com`)**. Ela é a sua API pública.
   > **⚠️ Importante:** Não feche esse terminal, senão o túnel cai!

---

### Passo 2: Configurar o Frontend para usar a Nova API Pública

Agora que o backend está na internet, precisamos dizer ao Flutter para parar de procurar o servidor no `localhost` e usar a nova URL do Cloudflare.

1. Abra o arquivo de configuração do Flutter no seu editor de código:
   `c:\gestaoestoque\frontend\lib\core\constants.dart`
2. Substitua o valor da constante `apiBaseUrl` pela URL que você copiou no Passo 1.
3. Substitua o valor da constante `wsBaseUrl` pela mesma URL, mas troque o prefixo `https://` por `wss://` (necessário para o Chat Corporativo funcionar com segurança).

O arquivo deve ficar parecido com isto:
```dart
class AppConstants {
  // URL pública do backend via Cloudflare Tunnel
  static const String apiBaseUrl = 'https://nome-aleatorio-aqui.trycloudflare.com'; 
  
  // Como o Cloudflare Tunnel provê HTTPS, usamos wss:// para WebSockets seguros
  static const String wsBaseUrl = 'wss://nome-aleatorio-aqui.trycloudflare.com'; 
}
```
4. Salve o arquivo.

---

### Passo 3: Iniciar e Expor o Frontend (Flutter Web)

Agora vamos rodar o Flutter em formato de site (Web Server) e expô-lo para a internet.

1. Abra um **terceiro terminal** e navegue até a pasta do frontend:
   ```bash
   cd frontend
   ```
2. Rode o Flutter travando ele na porta `5000`:
   ```bash
   flutter run -d web-server --web-port 5000
   ```
   *(Aguarde até ele dizer que está pronto e rodando em `localhost:5000`)*
3. Abra um **quarto (e último) terminal** e crie o túnel para o Flutter:
   ```bash
   cloudflared tunnel --url http://localhost:5000
   ```
4. O Cloudflare vai gerar uma **segunda URL pública** (diferente da primeira).
   Exemplo: `https://fell-semester-participation...trycloudflare.com`

---

## 📱 Passo 4: O Teste Final (Acessando do Celular)

1. Pegue o seu smartphone (se quiser, desligue o Wi-Fi para usar o 4G e provar que está na internet real).
2. Abra o navegador (Chrome/Safari) e digite a **URL gerada no Passo 3** (a URL do Frontend).
3. O aplicativo irá carregar a tela de login.
4. Ao fazer o login, o app no celular se comunicará com a URL do Backend (Passo 1), autenticará no seu banco de dados local e retornará o acesso.
5. O Chat e as conexões de IA (CFO) também funcionarão normalmente!

---

## 🚨 Dicas Importantes e Resolução de Problemas

- **Erro `502 Bad Gateway`:** Significa que o Cloudflare está no ar, mas o seu servidor local (FastAPI ou Flutter) caiu ou não está rodando na porta que você informou no comando do túnel. Verifique os terminais locais.
- **As URLs do `.trycloudflare.com` são efêmeras:** Elas mudam toda vez que você fecha e abre o comando `cloudflared tunnel`. Se você for testar no dia seguinte, terá que repetir o processo, pegar a nova URL do backend, colocar no `constants.dart` e gerar a nova URL do frontend.
- **A IA (Ollama) precisa ser exposta?** **Não!** O Ollama (porta 11434) deve continuar fechado no seu computador. O Backend (FastAPI) já acessa ele internamente via `localhost`. O usuário de fora nunca fala diretamente com a IA, ele fala com o FastAPI, que repassa a pergunta para a IA local.