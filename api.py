"""
API + site do comparador.

Rodar no seu PC:
    pip install -r requirements.txt
    uvicorn api:app --reload

No Render o comando é:
    uvicorn api:app --host 0.0.0.0 --port $PORT
Depois abra http://localhost:8000

BUSCA_NAS_LOJAS=0 (usado no Render): a busca do site procura só nos produtos
já salvos no banco, porque as lojas bloqueiam servidores na nuvem. A coleta
nas lojas é feita pelo seu PC (coletar.ps1).
"""

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles

import comparador as cmp

import db

# Sem banco configurado o site funciona normalmente, só não guarda histórico
BANCO_ATIVO = db.configurado()
BUSCA_NAS_LOJAS = os.getenv("BUSCA_NAS_LOJAS", "1") != "0"

app = FastAPI(title="Comparador de Preços")


def montar_resultado(produto_id, nome, ofertas, similaridade=None):
    ofertas = sorted(ofertas, key=lambda o: o["preco"])
    return {
        "id": produto_id,
        "nome": nome,
        "similaridade": round(similaridade) if similaridade else None,
        "ofertas": ofertas,
        "melhorLoja": ofertas[0]["loja"],
        "economia": round(ofertas[-1]["preco"] - ofertas[0]["preco"], 2),
    }


@app.get("/api/lojas")
def lojas():
    return [{"id": chave, "nome": nome} for chave, (nome, _) in cmp.LOJAS.items()]


@app.get("/api/buscar")
def buscar(
    q: str = Query(..., min_length=2, max_length=100),
    lojas: str = Query("", description="ids separados por vírgula, ex.: amazon,kabum"),
):
    escolhidas = [l.strip() for l in lojas.split(",") if l.strip() in cmp.LOJAS]
    if lojas and len(escolhidas) < 2:
        raise HTTPException(400, "Escolha pelo menos duas lojas para comparar.")

    if not BUSCA_NAS_LOJAS:
        return buscar_no_historico(q, escolhidas)

    por_loja = cmp.buscar_em_lojas(q, escolhidas or None)
    resultados = []
    for produtos, nota in cmp.agrupar(por_loja):
        produto_id = None
        if BANCO_ATIVO:
            try:
                produto_id = db.salvar_grupo(produtos)
            except Exception as erro:  # banco fora do ar não derruba a busca
                print(f"[aviso] não salvou no banco: {erro}")
        ofertas = [{"loja": p.loja, "nome": p.nome, "preco": p.preco, "url": p.url} for p in produtos]
        resultados.append(montar_resultado(produto_id, produtos[0].nome, ofertas, nota))

    return {
        "termo": q,
        "origem": "lojas",
        "encontrados": {loja: len(lista) for loja, lista in por_loja.items()},
        "resultados": resultados,
    }


def buscar_no_historico(q: str, chaves: list[str]):
    """Procura o termo nos produtos já salvos no banco (sem acessar as lojas)."""
    if not BANCO_ATIVO:
        raise HTTPException(503, "Banco de dados não configurado")
    nomes = [cmp.LOJAS[c][0] for c in chaves] or None
    try:
        produtos = db.listar_produtos(limite=30, termo=q, lojas=nomes)
    except Exception as erro:
        print(f"[aviso] banco indisponível: {erro}")
        raise HTTPException(503, "Banco indisponível no momento. Tente de novo em instantes.")

    resultados, encontrados = [], {}
    for p in produtos:  # inclui produtos vistos numa loja só (histórico)
        for o in p["ofertas"]:
            encontrados[o["loja"]] = encontrados.get(o["loja"], 0) + 1
        resultados.append(montar_resultado(p["id"], p["nome"], p["ofertas"]))
    return {"termo": q, "origem": "historico", "encontrados": encontrados, "resultados": resultados}


@app.get("/api/produtos")
def produtos():
    if not BANCO_ATIVO:
        return []
    try:
        return [montar_resultado(p["id"], p["nome"], p["ofertas"]) for p in db.listar_produtos()]
    except Exception as erro:
        print(f"[aviso] banco indisponível: {erro}")
        return []


@app.get("/api/produtos/{produto_id}/historico")
def historico(produto_id: int):
    if not BANCO_ATIVO:
        raise HTTPException(503, "Banco de dados não configurado")
    try:
        return db.historico(produto_id)
    except Exception as erro:
        print(f"[aviso] banco indisponível: {erro}")
        raise HTTPException(503, "Banco indisponível no momento. Tente de novo em instantes.")


@app.get("/api/saude")
def saude():
    """Usado pelo Render para saber se o serviço está no ar."""
    return {
        "status": "ok",
        "banco": db.modo() if BANCO_ATIVO else "desativado",
        "busca": "lojas" if BUSCA_NAS_LOJAS else "historico",
    }


# O site (pasta /site) é servido na raiz. Fica por último para não
# "engolir" as rotas /api.
app.mount("/", StaticFiles(directory=Path(__file__).parent / "site", html=True), name="site")
