"""
Acesso ao PostgreSQL (Supabase).

Defina a variável de ambiente DATABASE_URL com a string de conexão do Supabase
(botão "Connect" > "Session pooler"), por exemplo:

    postgresql://postgres.abcdefgh:SENHA@aws-0-sa-east-1.pooler.supabase.com:5432/postgres

Sem DATABASE_URL o site funciona normalmente, só não guarda histórico.
"""

import os

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()


def modo() -> str:
    return "nuvem" if DATABASE_URL else "desativado"


def configurado() -> bool:
    return bool(DATABASE_URL)


def _conectar():
    import psycopg
    from psycopg.rows import dict_row

    extras = {}
    local = any(h in DATABASE_URL for h in ("localhost", "127.0.0.1"))
    if "sslmode=" not in DATABASE_URL and not local:
        extras["sslmode"] = "require"  # o Supabase exige SSL

    return psycopg.connect(
        DATABASE_URL,
        row_factory=dict_row,
        connect_timeout=15,
        # o pooler do Supabase não guarda "prepared statements" entre conexões
        prepare_threshold=None,
        **extras,
    )


class Banco:
    """Uso:
        with Banco() as b:
            b.executar("INSERT ...", valor)
            linhas = b.todas("SELECT ...")
    """

    def __enter__(self):
        self.con = _conectar()
        self.cur = self.con.cursor()
        return self

    def __exit__(self, tipo_erro, *_):
        if tipo_erro is None:
            self.con.commit()
        else:
            self.con.rollback()
        self.con.close()

    def executar(self, sql: str, *params):
        self.cur.execute(sql, params or None)

    def uma(self, sql: str, *params) -> dict | None:
        self.executar(sql, *params)
        return self.cur.fetchone()

    def todas(self, sql: str, *params) -> list[dict]:
        self.executar(sql, *params)
        return self.cur.fetchall()


# ================================================================ operações
def _id_da_loja(b: Banco, nome: str) -> int:
    """Busca a loja pelo nome; se ainda não existir na tabela, cadastra."""
    linha = b.uma("SELECT id FROM loja WHERE nome = %s", nome)
    if linha:
        return linha["id"]
    return b.uma("INSERT INTO loja (nome) VALUES (%s) RETURNING id", nome)["id"]


def salvar_grupo(ofertas) -> int:
    """Grava o mesmo produto encontrado em várias lojas e retorna o id dele.

    Cada item de `ofertas` precisa ter: loja, nome, preco e url
    (é o objeto Produto do comparador.py).
    """
    with Banco() as b:
        # Se alguma das ofertas já existe, reaproveita o produto dela
        produto_id = None
        for o in ofertas:
            linha = b.uma("SELECT produto_id FROM oferta WHERE url = %s", o.url)
            if linha:
                produto_id = linha["produto_id"]
                break

        if produto_id is None:
            produto_id = b.uma(
                "INSERT INTO produto (nome) VALUES (%s) RETURNING id",
                ofertas[0].nome[:300],
            )["id"]

        for o in ofertas:
            loja_id = _id_da_loja(b, o.loja)
            linha = b.uma("SELECT id FROM oferta WHERE url = %s", o.url)
            if linha:
                oferta_id = linha["id"]
            else:
                oferta_id = b.uma(
                    "INSERT INTO oferta (produto_id, loja_id, nome_na_loja, url) "
                    "VALUES (%s, %s, %s, %s) RETURNING id",
                    produto_id, loja_id, o.nome[:300], o.url[:500],
                )["id"]
            b.executar("INSERT INTO preco (oferta_id, valor) VALUES (%s, %s)", oferta_id, o.preco)
        return produto_id


def listar_produtos(limite: int = 30) -> list[dict]:
    """Produtos acompanhados com o preço atual e o menor preço dos últimos 30 dias."""
    sql = """
        SELECT p.id, p.nome, l.nome AS loja, o.nome_na_loja, o.url,
               pa.valor, pa.coletado_em, m.minimo
        FROM produto p
        JOIN oferta o           ON o.produto_id = p.id
        JOIN loja l             ON l.id = o.loja_id
        JOIN vw_preco_atual pa  ON pa.oferta_id = o.id
        LEFT JOIN LATERAL (
            SELECT MIN(valor) AS minimo FROM preco
            WHERE oferta_id = o.id AND coletado_em >= now() - interval '30 days'
        ) m ON true
        ORDER BY pa.coletado_em DESC
        LIMIT %s
    """
    with Banco() as b:
        linhas = b.todas(sql, limite * 6)  # até 6 lojas por produto

    produtos = {}
    for r in linhas:
        p = produtos.setdefault(r["id"], {"id": r["id"], "nome": r["nome"], "ofertas": []})
        p["ofertas"].append({
            "loja": r["loja"],
            "nome": r["nome_na_loja"],
            "url": r["url"],
            "preco": float(r["valor"]),
            "minimo30d": float(r["minimo"]) if r["minimo"] is not None else None,
            "atualizadoEm": r["coletado_em"].isoformat(),
        })
    return list(produtos.values())[:limite]


def historico(produto_id: int) -> list[dict]:
    sql = """
        SELECT l.nome AS loja, pr.valor, pr.coletado_em
        FROM preco pr
        JOIN oferta o ON o.id = pr.oferta_id
        JOIN loja l   ON l.id = o.loja_id
        WHERE o.produto_id = %s
        ORDER BY pr.coletado_em
    """
    with Banco() as b:
        linhas = b.todas(sql, produto_id)
    return [
        {"loja": r["loja"], "preco": float(r["valor"]), "data": r["coletado_em"].isoformat()}
        for r in linhas
    ]
