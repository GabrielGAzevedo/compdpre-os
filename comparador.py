"""
Comparador de preços - várias lojas
-----------------------------------
Lojas: Amazon, Kabum, Mercado Livre, Pichau, Terabyte e Magalu.

Uso no terminal:
    python comparador.py "ssd kingston 1tb"
    python comparador.py "ssd kingston 1tb" --lojas amazon,kabum,pichau

Dependências:
    pip install requests beautifulsoup4 rapidfuzz

Observações:
- A maioria das lojas não tem API pública aberta, então o script lê as
  páginas de busca (scraping). Os sites mudam o HTML com frequência e podem
  bloquear muitas requisições seguidas: use com moderação (projeto de estudo).
- Mercado Livre: se você criar um app em developers.mercadolivre.com.br e
  definir a variável de ambiente ML_ACCESS_TOKEN, o script usa a API oficial.
  Sem o token, ele lê a página de busca.
- Servidores na nuvem (Render etc.) costumam ser bloqueados pelas lojas.
  Definindo SCRAPER_API_KEY (scraperapi.com), as páginas passam pelo ScraperAPI.
- Para adicionar uma loja nova: escreva uma função buscar_xxx(termo) que
  devolve uma lista de Produto e registre-a no dicionário LOJAS (no fim).
"""

import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from urllib.parse import quote, quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

try:
    from rapidfuzz import fuzz

    def _texto_parecido(a: str, b: str) -> float:
        return fuzz.token_set_ratio(a, b)
except ImportError:  # alternativa sem dependência extra
    from difflib import SequenceMatcher

    def _texto_parecido(a: str, b: str) -> float:
        return SequenceMatcher(None, a, b).ratio() * 100


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}
LIMITE_POR_LOJA = 10


@dataclass
class Produto:
    loja: str
    nome: str
    preco: float
    url: str


# ================================================================ utilidades
def texto_para_preco(texto) -> float | None:
    """Converte 'R$ 1.299,90' -> 1299.90 (aceita também números)."""
    if texto is None or isinstance(texto, bool):
        return None
    if isinstance(texto, (int, float)):
        return float(texto) if texto > 0 else None
    limpo = re.sub(r"[^\d,\.]", "", str(texto))
    if not limpo:
        return None
    if "," in limpo:  # formato brasileiro: 1.299,90
        limpo = limpo.replace(".", "").replace(",", ".")
    elif limpo.count(".") > 1:  # 1.299.000
        limpo = limpo.replace(".", "")
    try:
        valor = float(limpo)
        return valor if valor > 0 else None
    except ValueError:
        return None


def baixar_html(url: str) -> str | None:
    """Baixa a página. Se SCRAPER_API_KEY estiver definida, passa pelo ScraperAPI,
    que acessa a loja por IPs residenciais (as lojas bloqueiam servidores na nuvem)."""
    chave = os.getenv("SCRAPER_API_KEY", "").strip()
    try:
        if chave:
            resp = requests.get(
                "https://api.scraperapi.com/",
                params={"api_key": chave, "url": url, "country_code": "br"},
                timeout=70,  # o ScraperAPI pode levar até 60 s tentando
            )
        else:
            resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            origem = "ScraperAPI" if chave else "loja"
            print(f"  [aviso] {url} respondeu {resp.status_code} ({origem})")
            return None
        return resp.text
    except requests.RequestException as erro:
        print(f"  [erro] falha ao acessar {url}: {erro}")
        return None


# ----------------------------------------------- leitura genérica de JSON
# Muitas lojas (Kabum, Pichau, Magalu...) são feitas em Next.js e colocam os
# produtos num JSON dentro da página. Em vez de depender do HTML, que muda
# muito, procuramos nesse JSON objetos com "cara de produto".
CHAVES_NOME = ("name", "title")
CHAVES_PRECO = ("priceWithDiscount", "bestPrice", "avista", "final_price",
                "salePrice", "price", "value", "amount")
CHAVES_URL = ("url", "link", "permalink", "path", "url_key", "urlKey", "slug")


def _achar_preco(obj, profundidade=0):
    if profundidade > 3:
        return None
    if isinstance(obj, dict):
        for chave in CHAVES_PRECO:
            if chave in obj:
                valor = obj[chave]
                if isinstance(valor, (dict, list)):
                    valor = _achar_preco(valor, profundidade + 1)
                else:
                    valor = texto_para_preco(valor)
                if valor:
                    return valor
        for chave in ("offers", "prices", "pichau_prices", "price_range"):
            if chave in obj:
                valor = _achar_preco(obj[chave], profundidade + 1)
                if valor:
                    return valor
    elif isinstance(obj, list) and obj:
        return _achar_preco(obj[0], profundidade + 1)
    return None


def _parece_produto(obj: dict, base_url: str) -> Produto | None:
    nome = next((obj[c] for c in CHAVES_NOME if isinstance(obj.get(c), str)), None)
    if not nome or len(nome) < 8:
        return None
    url = next((obj[c] for c in CHAVES_URL if isinstance(obj.get(c), str) and obj[c]), None)
    preco = _achar_preco(obj)
    if not (url and preco):
        return None
    return Produto("", nome.strip(), preco, urljoin(base_url + "/", url))


def produtos_do_json(dados, base_url: str, achados=None) -> list[Produto]:
    achados = [] if achados is None else achados
    if isinstance(dados, dict):
        produto = _parece_produto(dados, base_url)
        if produto:
            achados.append(produto)
            return achados  # não desce dentro de um produto já achado
        for valor in dados.values():
            produtos_do_json(valor, base_url, achados)
    elif isinstance(dados, list):
        for item in dados:
            produtos_do_json(item, base_url, achados)
    elif isinstance(dados, str) and dados[:1] in "{[" and len(dados) > 50:
        try:  # algumas lojas guardam JSON dentro de string
            produtos_do_json(json.loads(dados), base_url, achados)
        except json.JSONDecodeError:
            pass
    return achados


def produtos_embutidos(soup: BeautifulSoup, base_url: str) -> list[Produto]:
    """Lê __NEXT_DATA__ e JSON-LD (schema.org) da página."""
    blocos = soup.select('script#__NEXT_DATA__, script[type="application/ld+json"]')
    achados = []
    for bloco in blocos:
        try:
            produtos_do_json(json.loads(bloco.string or ""), base_url, achados)
        except json.JSONDecodeError:
            continue
    return achados


def finalizar(produtos: list[Produto], loja: str) -> list[Produto]:
    """Define a loja, remove repetidos e limita a quantidade."""
    vistos, saida = set(), []
    for p in produtos:
        if p.url in vistos:
            continue
        vistos.add(p.url)
        p.loja = loja
        p.url = p.url.split("#")[0]
        saida.append(p)
        if len(saida) >= LIMITE_POR_LOJA:
            break
    return saida


def produtos_por_seletor(soup, base_url, card, nome, preco, link=None) -> list[Produto]:
    """Plano B: lê os cards do HTML com seletores CSS."""
    produtos = []
    for c in soup.select(card):
        n = c.select_one(nome)
        p = c.select_one(preco)
        a = c.select_one(link) if link else (c if c.name == "a" else c.select_one("a[href]"))
        if not (n and p and a and a.get("href")):
            continue
        valor = texto_para_preco(p.get_text(" ", strip=True))
        if valor:
            titulo = n.get("title") or n.get_text(" ", strip=True)
            produtos.append(Produto("", titulo, valor, urljoin(base_url, a["href"])))
    return produtos


# ==================================================================== Amazon
def parse_amazon(html: str) -> list[Produto]:
    soup = BeautifulSoup(html, "html.parser")
    produtos = []
    for card in soup.select('div[data-component-type="s-search-result"]'):
        titulo = card.select_one("h2 span") or card.select_one("h2")
        preco = card.select_one("span.a-price span.a-offscreen")
        link = card.select_one("a.a-link-normal[href*='/dp/']") or card.select_one("h2 a")
        if not (titulo and preco and link):
            continue  # anúncio sem preço, indisponível etc.
        valor = texto_para_preco(preco.get_text())
        if valor:
            url = urljoin("https://www.amazon.com.br", link["href"].split("?")[0])
            produtos.append(Produto("", titulo.get_text(strip=True), valor, url))
    return finalizar(produtos, "Amazon")


def buscar_amazon(termo: str) -> list[Produto]:
    html = baixar_html(f"https://www.amazon.com.br/s?k={quote_plus(termo)}")
    if html and "captcha" in html.lower() and "s-search-result" not in html:
        print("  [aviso] Amazon pediu captcha (bloqueio anti-bot). Tente mais tarde.")
        return []
    return parse_amazon(html) if html else []


# ===================================================================== Kabum
def parse_kabum(html: str) -> list[Produto]:
    base = "https://www.kabum.com.br"
    soup = BeautifulSoup(html, "html.parser")

    # A Kabum guarda os produtos num JSON com "code" e "friendlyName"
    produtos = []
    script = soup.find("script", id="__NEXT_DATA__")
    if script and script.string:
        def varrer(obj):
            if isinstance(obj, dict):
                if "name" in obj and "code" in obj and ("priceWithDiscount" in obj or "price" in obj):
                    valor = texto_para_preco(obj.get("priceWithDiscount") or obj.get("price"))
                    if valor:
                        url = f"{base}/produto/{obj['code']}/{obj.get('friendlyName', '')}".rstrip("/")
                        produtos.append(Produto("", obj["name"], valor, url))
                    return
                for v in obj.values():
                    varrer(v)
            elif isinstance(obj, list):
                for v in obj:
                    varrer(v)
            elif isinstance(obj, str) and obj[:1] == "{":
                try:
                    varrer(json.loads(obj))
                except json.JSONDecodeError:
                    pass
        varrer(json.loads(script.string))

    if not produtos:
        produtos = produtos_por_seletor(
            soup, base, "a[href*='/produto/']",
            "span[class*='nameCard'], h3, h2", "span[class*='priceCard']")
    return finalizar(produtos, "Kabum")


def buscar_kabum(termo: str) -> list[Produto]:
    html = baixar_html(f"https://www.kabum.com.br/busca/{quote(termo.replace(' ', '-'))}")
    return parse_kabum(html) if html else []


# ============================================================= Mercado Livre
def buscar_mercadolivre(termo: str) -> list[Produto]:
    token = os.getenv("ML_ACCESS_TOKEN")
    if token:  # API oficial
        try:
            resp = requests.get(
                "https://api.mercadolibre.com/sites/MLB/search",
                params={"q": termo, "limit": LIMITE_POR_LOJA},
                headers={"Authorization": f"Bearer {token}"}, timeout=15)
            if resp.ok:
                return finalizar([
                    Produto("", i["title"], float(i["price"]), i["permalink"])
                    for i in resp.json().get("results", []) if i.get("price")
                ], "Mercado Livre")
            print(f"  [aviso] API do Mercado Livre respondeu {resp.status_code}; lendo a página")
        except requests.RequestException as erro:
            print(f"  [erro] API do Mercado Livre: {erro}")

    html = baixar_html(f"https://lista.mercadolivre.com.br/{quote(termo.replace(' ', '-'))}")
    return parse_mercadolivre(html) if html else []


def parse_mercadolivre(html: str) -> list[Produto]:
    soup = BeautifulSoup(html, "html.parser")
    produtos = []
    for card in soup.select("li.ui-search-layout__item, div.poly-card"):
        link = card.select_one("a.poly-component__title, h2 a, a.ui-search-link")
        titulo = card.select_one("a.poly-component__title, h2, h3")
        # preço atual (ignora o preço antigo riscado)
        atual = (card.select_one(".poly-price__current .andes-money-amount")
                 or card.select_one(".andes-money-amount:not(.andes-money-amount--previous)"))
        if not (link and titulo and atual):
            continue
        inteiro = atual.select_one(".andes-money-amount__fraction")
        centavos = atual.select_one(".andes-money-amount__cents")
        if not inteiro:
            continue
        valor = texto_para_preco(f"{inteiro.get_text()},{centavos.get_text() if centavos else '00'}")
        if valor:
            url = link["href"].split("#")[0]
            produtos.append(Produto("", titulo.get_text(" ", strip=True), valor, url))
    return finalizar(produtos, "Mercado Livre")


# ==================================================================== Pichau
def parse_pichau(html: str) -> list[Produto]:
    base = "https://www.pichau.com.br"
    soup = BeautifulSoup(html, "html.parser")
    produtos = produtos_embutidos(soup, base)
    if not produtos:
        produtos = produtos_por_seletor(
            soup, base, "a[data-cy='list-product'], a[href][class*='product']",
            "h2, [class*='name']", "[class*='price_vista'], [class*='Price'], [class*='price']")
    return finalizar(produtos, "Pichau")


def buscar_pichau(termo: str) -> list[Produto]:
    html = baixar_html(f"https://www.pichau.com.br/search?q={quote_plus(termo)}")
    return parse_pichau(html) if html else []


# ================================================================== Terabyte
def parse_terabyte(html: str) -> list[Produto]:
    base = "https://www.terabyteshop.com.br"
    soup = BeautifulSoup(html, "html.parser")
    produtos = produtos_por_seletor(
        soup, base, "div.product-item, div.pbox",
        "a.product-item__name, a.prod-name, h2",
        ".product-item__new-price span, .prod-new-price span, .product-item__new-price",
        "a.product-item__name, a.prod-name, a[href*='/produto/']")
    if not produtos:
        produtos = produtos_embutidos(soup, base)
    return finalizar(produtos, "Terabyte")


def buscar_terabyte(termo: str) -> list[Produto]:
    html = baixar_html(f"https://www.terabyteshop.com.br/busca?str={quote_plus(termo)}")
    if html and "cf-chl" in html:
        print("  [aviso] Terabyte bloqueou a requisição (proteção anti-bot).")
        return []
    return parse_terabyte(html) if html else []


# ===================================================================== Magalu
def parse_magalu(html: str) -> list[Produto]:
    base = "https://www.magazineluiza.com.br"
    soup = BeautifulSoup(html, "html.parser")
    produtos = produtos_embutidos(soup, base)
    if not produtos:
        produtos = produtos_por_seletor(
            soup, base, "a[data-testid='product-card-container']",
            "[data-testid='product-title'], h2", "[data-testid='price-value']")
    return finalizar(produtos, "Magalu")


def buscar_magalu(termo: str) -> list[Produto]:
    html = baixar_html(f"https://www.magazineluiza.com.br/busca/{quote(termo)}/")
    return parse_magalu(html) if html else []


# ============================================================ registro de lojas
# chave (usada na API/site) -> (nome exibido, função de busca)
LOJAS = {
    "amazon": ("Amazon", buscar_amazon),
    "kabum": ("Kabum", buscar_kabum),
    "mercadolivre": ("Mercado Livre", buscar_mercadolivre),
    "pichau": ("Pichau", buscar_pichau),
    "terabyte": ("Terabyte", buscar_terabyte),
    "magalu": ("Magalu", buscar_magalu),
}


def buscar_em_lojas(termo: str, chaves: list[str] | None = None) -> dict[str, list[Produto]]:
    """Busca em paralelo nas lojas escolhidas. Retorna {nome da loja: produtos}."""
    chaves = [c for c in (chaves or LOJAS) if c in LOJAS]

    def tarefa(chave):
        nome, funcao = LOJAS[chave]
        try:
            return nome, funcao(termo)
        except Exception as erro:  # uma loja com problema não derruba as outras
            print(f"  [erro] {nome}: {erro}")
            return nome, []

    with ThreadPoolExecutor(max_workers=len(chaves) or 1) as pool:
        return dict(pool.map(tarefa, chaves))


# =============================================================== comparação
UNIDADES = r"(tb|gb|mb|hz|w|mah|mm|dpi|pol|polegadas|\")"


def _especificacoes(nome: str) -> dict[str, set]:
    """'SSD 1TB 3500MB/s' -> {'tb': {'1'}, 'mb': {'3500'}}"""
    specs = {}
    for numero, unidade in re.findall(r"(\d+(?:[.,]\d+)?)\s?" + UNIDADES, nome.lower()):
        unidade = "pol" if unidade in ('"', "polegadas") else unidade
        specs.setdefault(unidade, set()).add(numero.replace(",", "."))
    return specs


def similaridade(a: str, b: str) -> float:
    """Nota de 0 a 100. Zera se as especificações forem diferentes
    (ex.: SSD 1TB x SSD 2TB têm nomes quase iguais, mas não são o mesmo produto)."""
    ea, eb = _especificacoes(a), _especificacoes(b)
    for unidade in ea.keys() & eb.keys():
        if not ea[unidade] & eb[unidade]:
            return 0.0
    return _texto_parecido(a.lower(), b.lower())


def agrupar(por_loja: dict[str, list[Produto]], minimo: float = 70):
    """Junta o mesmo produto de lojas diferentes.

    Retorna uma lista de (lista de Produto, nota mínima de similaridade),
    só com grupos presentes em pelo menos 2 lojas.
    """
    grupos = []  # cada item: [produtos, nota]
    for produtos in por_loja.values():
        usados = set()
        for grupo in grupos:
            referencia = grupo[0][0]
            melhor, nota = None, 0.0
            for i, p in enumerate(produtos):
                if i in usados:
                    continue
                n = similaridade(referencia.nome, p.nome)
                if n > nota:
                    melhor, nota = i, n
            if melhor is not None and nota >= minimo:
                grupo[0].append(produtos[melhor])
                grupo[1] = min(grupo[1], nota)
                usados.add(melhor)
        for i, p in enumerate(produtos):
            if i not in usados:
                grupos.append([[p], 100.0])

    resultado = [(sorted(g, key=lambda p: p.preco), nota) for g, nota in grupos if len(g) >= 2]
    resultado.sort(key=lambda r: r[0][-1].preco - r[0][0].preco, reverse=True)
    return resultado


# ==================================================================== terminal
def moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main():
    args = sys.argv[1:]
    chaves = None
    if "--lojas" in args:
        i = args.index("--lojas")
        chaves = args[i + 1].split(",") if i + 1 < len(args) else None
        args = args[:i] + args[i + 2:]
    termo = " ".join(args) or input("O que deseja buscar? ")

    print(f"\nBuscando '{termo}'...\n")
    por_loja = buscar_em_lojas(termo, chaves)
    for loja, produtos in por_loja.items():
        print(f"  {loja:<14} {len(produtos)} produtos")

    grupos = agrupar(por_loja)
    if not grupos:
        print("\nNenhum produto equivalente encontrado em duas lojas ou mais.")
        return

    print("\n" + "=" * 72)
    for produtos, nota in grupos:
        barato, caro = produtos[0], produtos[-1]
        print(f"Produto: {barato.nome[:66]}")
        for p in produtos:
            marca = "  <- menor preço" if p is barato else ""
            print(f"  {p.loja:<14}{moeda(p.preco):>14}  {p.url[:60]}{marca}")
        print(f"  >> Economia de {moeda(caro.preco - barato.preco)}  [similaridade {nota:.0f}%]")
        print("-" * 72)

    try:  # salva o histórico no banco, se DATABASE_URL estiver definida
        import db
        if not db.configurado():
            return
        for produtos, _ in grupos:
            db.salvar_grupo(produtos)
        print(f"\n{len(grupos)} produto(s) salvos no banco.")
    except Exception as erro:
        print(f"\n[aviso] não foi possível salvar no banco: {erro}")


if __name__ == "__main__":
    main()
