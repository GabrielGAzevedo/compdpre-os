# Preço Certo GGA: comparador de preços

Compara o mesmo produto em Amazon, Kabum e Pichau (Mercado Livre, Terabyte e Magalu estão
no código, mas desativados no dicionário `LOJAS` do `comparador.py`).
No site você marca quais lojas quer comparar (mínimo 2) e vê o histórico de preços.

```
comparador/
├── api.py           # API FastAPI + serve o site
├── comparador.py    # busca nas lojas e compara (também roda no terminal)
├── db.py            # histórico no PostgreSQL (Supabase)
├── banco.sql        # cria as tabelas
├── render.yaml      # configuração para publicar no Render
├── coletar.ps1      # coleta os preços de termos.txt pelo seu PC
├── termos.txt       # produtos acompanhados (um por linha)
├── requirements.txt
└── site/            # index.html, style.css, app.js
```

---

## 1. Rodar no seu PC (Windows)

1. Instale as dependências (Python 3.10+):
   ```
   pip install -r requirements.txt
   ```
2. (Opcional) Para guardar o histórico, use o mesmo banco do Supabase (passo 2 abaixo).
   No PowerShell, antes de subir o servidor:
   ```
   $env:DATABASE_URL = "postgresql://postgres.xxxx:SENHA@aws-0-sa-east-1.pooler.supabase.com:5432/postgres"
   ```
3. Suba o servidor:
   ```
   uvicorn api:app --reload
   ```
4. Abra **http://localhost:8000**

Sem `DATABASE_URL` o site funciona normalmente, só a parte de histórico fica vazia.

Testes do leitor da Pichau (não acessam a internet): `python -m unittest discover testes`

No terminal também funciona:
```
python comparador.py "ssd 1tb"
python comparador.py "ssd 1tb" --lojas amazon,kabum,pichau
```

---

## 2. Publicar de graça (GitHub + Supabase + Render)

### Passo 1: subir o código para o GitHub
1. Crie um repositório em https://github.com/new (pode ser público).
2. Na pasta do projeto:
   ```
   git init
   git add .
   git commit -m "Comparador de preços"
   git branch -M main
   git remote add origin https://github.com/SEU-USUARIO/precocerto.git
   git push -u origin main
   ```

### Passo 2: criar o banco grátis no Supabase
1. Crie a conta em https://supabase.com (entre com o GitHub, não pede cartão).
2. **New project**:
   - **Name:** `precocerto`
   - **Database Password:** clique em *Generate a password* e **guarde a senha**.
     Se escolher uma senha sua, use só letras e números (símbolos como `@`, `#`, `/`
     quebram a string de conexão).
   - **Region:** South America (São Paulo).
3. Quando o projeto terminar de criar, vá em **SQL Editor** > **New query**, cole todo o
   `banco.sql` e clique em **Run**.
4. Clique em **Connect** (no topo) e copie a string do **Session pooler**. Ela tem este formato:
   ```
   postgresql://postgres.xxxx:[YOUR-PASSWORD]@aws-0-sa-east-1.pooler.supabase.com:5432/postgres
   ```
   Troque `[YOUR-PASSWORD]` pela senha (sem os colchetes).
   ⚠️ Use a do **Session pooler**, não a "Direct connection": a direta só funciona com IPv6,
   e o Render grátis não tem IPv6.

### Passo 3: publicar no Render
1. Crie a conta em https://render.com (entre com o GitHub, não pede cartão).
2. **New** > **Blueprint** > escolha o repositório. O Render lê o `render.yaml`.
3. Preencha as variáveis:
   - `DATABASE_URL`: a string do Supabase do passo anterior (já com a senha)
   - `ML_ACCESS_TOKEN`: opcional, pode deixar vazio
4. Clique em **Apply**. Em alguns minutos o site fica no ar em
   `https://precocerto.onrender.com` (ou nome parecido).
5. Teste `https://SEU-SITE.onrender.com/api/saude`: deve mostrar `"banco": "nuvem"`.

A cada `git push` no GitHub, o Render publica a nova versão sozinho.

### Passo 4: coletar os preços pelo seu PC
As lojas bloqueiam servidores na nuvem, então no Render (`BUSCA_NAS_LOJAS=0`) a busca do
site procura só nos produtos **já salvos no banco**. Quem vai às lojas é o seu PC:

1. Crie um arquivo `.env` nesta pasta com uma linha (a string do Supabase, com a senha):
   ```
   DATABASE_URL=postgresql://postgres.xxxx:SENHA@aws-1-us-east-2.pooler.supabase.com:5432/postgres
   ```
   O `.env` está no `.gitignore`: não vai para o GitHub.
2. Coloque os produtos que quer acompanhar no `termos.txt` (um por linha).
3. Rode no PowerShell, nesta pasta:
   ```
   powershell -ExecutionPolicy Bypass -File .\coletar.ps1
   ```
   Por padrão busca na Amazon, na Kabum e na Pichau.
   Para escolher: `... -File .\coletar.ps1 -Lojas kabum` ou `-Lojas amazon,kabum`.

Cada vez que rodar, um novo preço entra no histórico. Para coletar todo dia sozinho, crie
uma tarefa no **Agendador de Tarefas** do Windows que execute o comando acima.

### O que esperar do plano grátis
- **O site "dorme"** depois de 15 minutos sem visitas. A primeira visita depois disso
  demora de 30 a 60 segundos para abrir.
- **O Supabase pausa o projeto** depois de 7 dias sem nenhum uso do banco. Se acontecer,
  entre no painel do Supabase e clique em **Restore project**. Enquanto o site for usado
  (cada busca grava no banco), ele não pausa.
- **As lojas bloqueiam servidores na nuvem** (erro 403 nos logs do Render), e o plano
  grátis do ScraperAPI também não passou pela proteção delas. Por isso a coleta roda no
  seu PC (passo 4). As páginas são baixadas com `curl_cffi` imitando o Chrome, o que
  passa pela proteção Cloudflare da Pichau. Terabyte, Magalu e Mercado Livre ainda
  costumam bloquear.
- Sem banco configurado o site continua funcionando: só a parte de histórico fica vazia.

---

## Variáveis de ambiente

| Variável | Para quê |
|----------|----------|
| `DATABASE_URL` | conexão com o PostgreSQL (string do Supabase, Session pooler) |
| `BUSCA_NAS_LOJAS` | `0` faz a busca do site procurar só no histórico do banco (usado no Render) |
| `SCRAPER_API_KEY` | chave do scraperapi.com; as buscas passam por ele (necessário no Render, onde as lojas bloqueiam o acesso) |
| `ML_ACCESS_TOKEN` | usa a API oficial do Mercado Livre (crie um app em developers.mercadolivre.com.br) |

## Rotas da API

| Rota | O que faz |
|------|-----------|
| `GET /api/lojas` | lojas disponíveis |
| `GET /api/buscar?q=termo&lojas=amazon,kabum` | busca nas lojas escolhidas, compara e salva no banco |
| `GET /api/produtos` | produtos já salvos, com o preço mais recente |
| `GET /api/produtos/{id}/historico` | todos os preços coletados do produto |
| `GET /api/saude` | verifica se o serviço está no ar |

## Adicionar outra loja
Escreva uma função `buscar_xxx(termo)` em `comparador.py` que devolve uma lista de `Produto`
e registre no dicionário `LOJAS`. Para ter cor própria no site, adicione `--xxx` e
`.loja--xxx, .opcao-loja--xxx` no `style.css`.
