# PreçoCerto: comparador de preços

Compara o mesmo produto em Amazon, Kabum, Mercado Livre, Pichau, Terabyte e Magalu.
No site você marca quais lojas quer comparar (mínimo 2) e vê o histórico de preços.

```
comparador/
├── api.py           # API FastAPI + serve o site
├── comparador.py    # busca nas lojas e compara (também roda no terminal)
├── db.py            # histórico no SQL Server (local ou Azure)
├── banco.sql        # cria as tabelas
├── render.yaml      # configuração para publicar no Render
├── requirements.txt
└── site/            # index.html, style.css, app.js
```

---

## 1. Rodar no seu PC (Windows)

1. No SSMS: `CREATE DATABASE Comparador;`, selecione o banco e rode o `banco.sql`.
2. Instale as dependências (Python 3.10+):
   ```
   pip install -r requirements.txt
   pip install pyodbc
   ```
3. Suba o servidor:
   ```
   uvicorn api:app --reload
   ```
4. Abra **http://localhost:8000**

Sem variáveis de ambiente, o `db.py` conecta no `localhost\SQLEXPRESS` com login do Windows
(precisa do "ODBC Driver 17 for SQL Server").

No terminal também funciona:
```
python comparador.py "ssd 1tb"
python comparador.py "ssd 1tb" --lojas amazon,kabum,pichau
```

---

## 2. Publicar de graça (GitHub + Azure SQL + Render)

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

### Passo 2: criar o banco grátis no Azure
1. Crie a conta em https://azure.microsoft.com/free (pede cartão para verificação, mas a
   oferta grátis do banco não cobra).
2. No portal, procure **SQL databases** > **Create**.
3. No topo da página aparece o banner **"Want to try Azure SQL Database for free?" > Apply offer**. Clique nele.
4. Preencha:
   - **Database name:** `Comparador`
   - **Server:** *Create new* > escolha um nome (vira `nome.database.windows.net`),
     região (ex.: Brazil South) e **autenticação SQL** com usuário e senha forte. Anote os dois.
   - Em **Free offer behavior**, deixe *Auto-pause the database until next month*
     (assim nunca cobra; se acabar a cota do mês, o banco pausa até o mês seguinte).
5. Na aba **Networking**: *Public endpoint* e marque
   **"Allow Azure services and resources to access this server"**.
6. Crie. Quando terminar, abra o banco > **Query editor**, entre com o usuário e senha
   e rode o conteúdo do `banco.sql`.
7. Liberar o Render no firewall: o Render grátis não tem IP fixo. Em **Server > Networking >
   Firewall rules**, adicione uma regra de `0.0.0.0` a `255.255.255.255`.
   ⚠️ Isso deixa o servidor acessível de qualquer IP: a proteção passa a ser só a senha,
   então use uma senha longa e não use esse banco para dados sensíveis.

### Passo 3: publicar no Render
1. Crie a conta em https://render.com (entre com o GitHub, não pede cartão).
2. **New** > **Blueprint** > escolha o repositório. O Render lê o `render.yaml`.
3. Preencha as variáveis:
   - `DB_SERVER`: `nome.database.windows.net`
   - `DB_NAME`: `Comparador`
   - `DB_USER` e `DB_PASSWORD`: o usuário e senha do Azure
   - `ML_ACCESS_TOKEN`: opcional, pode deixar vazio
4. Clique em **Apply**. Em alguns minutos o site fica no ar em
   `https://precocerto.onrender.com` (ou nome parecido).
5. Teste `https://SEU-SITE.onrender.com/api/saude`: deve mostrar `"banco": "nuvem"`.

A cada `git push` no GitHub, o Render publica a nova versão sozinho.

### O que esperar do plano grátis
- **O site "dorme"** depois de 15 minutos sem visitas. A primeira visita depois disso
  demora de 30 a 60 segundos para abrir.
- **O banco também pausa** depois de um tempo parado; a primeira consulta pode demorar
  alguns segundos (o código já espera até 30 s).
- **Algumas lojas bloqueiam servidores na nuvem**: Amazon e Terabyte costumam bloquear
  acessos vindos de datacenter. No site publicado, é normal essas lojas voltarem com 0
  produtos mesmo funcionando no seu PC.
- Sem banco configurado o site continua funcionando: só a parte de histórico fica vazia.

---

## Variáveis de ambiente

| Variável | Para quê |
|----------|----------|
| `DB_SERVER`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | conexão com o Azure SQL (modo nuvem) |
| `COMPARADOR_DB` | string de conexão ODBC personalizada (modo local) |
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
