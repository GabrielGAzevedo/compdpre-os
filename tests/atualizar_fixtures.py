"""Salva páginas de busca reais da Amazon, KaBuM! e Pichau em tests/fixtures/.

Rode no seu PC (as lojas bloqueiam servidores na nuvem), nesta pasta:
    python tests/atualizar_fixtures.py
    python tests/atualizar_fixtures.py "ssd kingston 1tb" --lojas amazon,kabum

Só grava a página se a loja respondeu e o leitor achou produtos nela, para
não trocar uma fixture boa por uma página de bloqueio. Depois rode os testes:
    python -m unittest discover tests -v
"""

import sys
from pathlib import Path
from urllib.parse import quote, quote_plus

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import comparador  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"

URLS = {
    "amazon": lambda t: f"https://www.amazon.com.br/s?k={quote_plus(t)}",
    "kabum": lambda t: f"https://www.kabum.com.br/busca/{quote(t.replace(' ', '-'))}",
    "pichau": lambda t: f"https://www.pichau.com.br/search?q={quote_plus(t)}",
}


def main():
    args = sys.argv[1:]
    lojas = list(URLS)
    if "--lojas" in args:
        i = args.index("--lojas")
        lojas = [c for c in args[i + 1].split(",") if c in URLS]
        args = args[:i] + args[i + 2:]
    termo = " ".join(args) or "ssd kingston 1tb"

    for chave in lojas:
        print(f"{chave}: baixando...")
        html = comparador.baixar_html(URLS[chave](termo))
        if not html:
            print(f"  {chave}: sem resposta, fixture mantida")
            continue
        produtos = getattr(comparador, f"parse_{chave}")(html)
        if not produtos:
            print(f"  {chave}: a página veio, mas o leitor achou 0 produtos "
                  f"(bloqueio ou layout novo); fixture mantida")
            continue
        (FIXTURES / f"{chave}_busca.html").write_text(html, encoding="utf-8")
        print(f"  {chave}: {len(produtos)} produtos, fixture salva")


if __name__ == "__main__":
    main()
