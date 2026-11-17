"""
Acesso ao SQL Server (local ou Azure SQL).

O mesmo código funciona em dois modos:

1) NUVEM (Render + Azure SQL) - usa pymssql, que não precisa de driver ODBC.
   Defina as variáveis de ambiente:
       DB_SERVER    ex.: meuservidor.database.windows.net
       DB_NAME      ex.: Comparador
       DB_USER      usuário SQL criado no Azure
       DB_PASSWORD  senha desse usuário

2) LOCAL (seu PC, SQL Server Express com login do Windows) - usa pyodbc.
   Se DB_SERVER não estiver definida, conecta em localhost\\SQLEXPRESS.
   Requer: pip install pyodbc  (e o "ODBC Driver 17 for SQL Server")

As consultas usam %s como marcador de parâmetro; no modo pyodbc ele é
trocado automaticamente por ?.
"""

import os

CONEXAO_LOCAL = os.getenv(
    "COMPARADOR_DB",
    "DRIVER={ODBC Driver 17 for SQL Server};"
    r"SERVER=localhost\SQLEXPRESS;"
    "DATABASE=Comparador;"
    "Trusted_Connection=yes;",
)


def modo() -> str:
    return "nuvem" if os.getenv("DB_SERVER") else "local"


def configurado() -> bool:
    """True se há como conectar (variáveis da nuvem ou pyodbc instalado)."""
    if modo() == "nuvem":
        return True
    try:
        import pyodbc  # noqa: F401
        return True
    except ImportError:
        return False


class Banco:
    """Pequena camada para usar pymssql e pyodbc do mesmo jeito.

    Uso:
        with Banco() as b:
            b.executar("INSERT ...", valor)
            linhas = b.todas("SELECT ...")
    """

    def __enter__(self):
        if modo() == "nuvem":
            import pymssql
            self.con = pymssql.connect(
                server=os.environ["DB_SERVER"],
                user=os.environ["DB_USER"],
                password=os.environ["DB_PASSWORD"],
                database=os.getenv("DB_NAME", "Comparador"),
                port=int(os.getenv("DB_PORT", "1433")),
                login_timeout=30,  # o Azure grátis "dorme" e demora a acordar
                tds_version="7.4",
            )
            self.marcador = "%s"
        else:
            import pyodbc
            self.con = pyodbc.connect(CONEXAO_LOCAL)
            self.marcador = "?"
        self.cur = self.con.cursor()
        return self

    def __exit__(self, tipo_erro, *_):
        if tipo_erro is None:
            self.con.commit()
        else:
            self.con.rollback()
        self.con.close()

    def executar(self, sql: str, *params):
        if self.marcador == "%s":  # pymssql: parâmetros numa tupla
            self.cur.execute(sql, tuple(params) if params else None)
        else:                      # pyodbc: troca %s por ? e passa soltos
            self.cur.execute(sql.replace("%s", "?"), *params)

    def _como_dict(self, linha):
        nomes = [c[0] for c in self.cur.description]
        return dict(zip(nomes, linha))

    def uma(self, sql: str, *params) -> dict | None:
        self.executar(sql, *params)
        linha = self.cur.fetchone()
        return self._como_dict(linha) if linha else None

    def todas(self, sql: str, *params) -> list[dict]:
        self.executar(sql, *params)
        return [self._como_dict(l) for l in self.cur.fetchall()]


# ================================================================ operações
def _id_da_loja(b: Banco, nome: str) -> int:
    """Busca a loja pelo nome; se ainda não existir na tabela, cadastra."""
    linha = b.uma("SELECT Id FROM Loja WHERE Nome = %s", nome)
    if linha:
        return linha["Id"]
    return b.uma("INSERT INTO Loja (Nome) OUTPUT INSERTED.Id VALUES (%s)", nome)["Id"]


def salvar_grupo(ofertas) -> int:
    """Grava o mesmo produto encontrado em várias lojas e retorna o Id dele.

    Cada item de `ofertas` precisa ter: loja, nome, preco e url
    (é o objeto Produto do comparador.py).
    """
    with Banco() as b:
        # Se alguma das ofertas já existe, reaproveita o produto dela
        produto_id = None
        for o in ofertas:
            linha = b.uma("SELECT ProdutoId FROM Oferta WHERE Url = %s", o.url)
            if linha:
                produto_id = linha["ProdutoId"]
                break

        if produto_id is None:
            produto_id = b.uma(
                "INSERT INTO Produto (Nome) OUTPUT INSERTED.Id VALUES (%s)",
                ofertas[0].nome[:300],
            )["Id"]

        for o in ofertas:
            loja_id = _id_da_loja(b, o.loja)
            linha = b.uma("SELECT Id FROM Oferta WHERE Url = %s", o.url)
            if linha:
                oferta_id = linha["Id"]
            else:
                oferta_id = b.uma(
                    "INSERT INTO Oferta (ProdutoId, LojaId, NomeNaLoja, Url) "
                    "OUTPUT INSERTED.Id VALUES (%s, %s, %s, %s)",
                    produto_id, loja_id, o.nome[:300], o.url,
                )["Id"]
            b.executar("INSERT INTO Preco (OfertaId, Valor) VALUES (%s, %s)", oferta_id, o.preco)
        return produto_id


def listar_produtos(limite: int = 30) -> list[dict]:
    """Produtos acompanhados com o preço atual e o menor preço dos últimos 30 dias."""
    sql = """
        SELECT TOP (%s) p.Id, p.Nome, l.Nome AS Loja, o.NomeNaLoja, o.Url,
               pa.Valor, pa.ColetadoEm, m.Minimo
        FROM Produto p
        JOIN Oferta o         ON o.ProdutoId = p.Id
        JOIN Loja l           ON l.Id = o.LojaId
        JOIN vw_PrecoAtual pa ON pa.OfertaId = o.Id
        OUTER APPLY (
            SELECT MIN(Valor) AS Minimo FROM Preco
            WHERE OfertaId = o.Id AND ColetadoEm >= DATEADD(DAY, -30, SYSDATETIME())
        ) m
        ORDER BY pa.ColetadoEm DESC
    """
    with Banco() as b:
        linhas = b.todas(sql, limite * 6)  # até 6 lojas por produto

    produtos = {}
    for r in linhas:
        p = produtos.setdefault(r["Id"], {"id": r["Id"], "nome": r["Nome"], "ofertas": []})
        p["ofertas"].append({
            "loja": r["Loja"],
            "nome": r["NomeNaLoja"],
            "url": r["Url"],
            "preco": float(r["Valor"]),
            "minimo30d": float(r["Minimo"]) if r["Minimo"] is not None else None,
            "atualizadoEm": r["ColetadoEm"].isoformat(),
        })
    return list(produtos.values())[:limite]


def historico(produto_id: int) -> list[dict]:
    sql = """
        SELECT l.Nome AS Loja, pr.Valor, pr.ColetadoEm
        FROM Preco pr
        JOIN Oferta o ON o.Id = pr.OfertaId
        JOIN Loja l   ON l.Id = o.LojaId
        WHERE o.ProdutoId = %s
        ORDER BY pr.ColetadoEm
    """
    with Banco() as b:
        linhas = b.todas(sql, produto_id)
    return [
        {"loja": r["Loja"], "preco": float(r["Valor"]), "data": r["ColetadoEm"].isoformat()}
        for r in linhas
    ]
