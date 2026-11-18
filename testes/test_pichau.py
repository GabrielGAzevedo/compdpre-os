"""Testes offline do leitor da Pichau (não acessam a internet).

Rodar na pasta do projeto:
    python -m unittest discover testes
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import comparador  # noqa: E402

PRODUTOS = [
    {"id": 1, "sku": "SSD-KC3000-1TB", "name": "SSD Kingston KC3000, 1TB, M.2 NVMe",
     "url_key": "ssd-kingston-kc3000-1tb-m-2-nvme", "stock_status": "IN_STOCK",
     "image": {"url": "https://media.pichau.com.br/x.jpg"},
     "pichau_prices": {"avista": 499.99, "avista_discount": 15, "avista_method": "PIX",
                       "base_price": 699.99, "final_price": 588.22,
                       "max_installments": 12, "min_installment_price": 49.02}},
    {"id": 2, "sku": "SSD-NV3-1TB", "name": "SSD Kingston NV3, 1TB, M.2 2280",
     "url_key": "ssd-kingston-nv3-1tb", "stock_status": "IN_STOCK",
     "pichau_prices": {"avista": None, "final_price": "389,90"}},
    {"id": 3, "sku": "SSD-ESGOTADO", "name": "SSD Kingston A400, 960GB, SATA",
     "url_key": "ssd-kingston-a400-960gb", "stock_status": "OUT_OF_STOCK",
     "pichau_prices": {"avista": 299.99, "final_price": 352.93}},
]


def pagina_flight(produtos) -> str:
    """Imita a página do Next.js app router: JSON escapado em __next_f.push,
    quebrado em vários pedaços (como no site real)."""
    linha = '7:["$","$L8",null,{"data":{"products":{"items":%s}}}]\n' % json.dumps(produtos)
    meio = len(linha) // 2
    blocos = "".join(
        "<script>self.__next_f.push([1,%s])</script>" % json.dumps(parte)
        for parte in (linha[:meio], linha[meio:]))
    return ("<!DOCTYPE html><html><head><title>Busca | Pichau</title></head><body>"
            '<script>(self.__next_f=self.__next_f||[]).push([0])</script>'
            + blocos + "</body></html>")


class TestPichau(unittest.TestCase):
    def test_flight_app_router(self):
        produtos = comparador.parse_pichau(pagina_flight(PRODUTOS))
        self.assertEqual([p.nome for p in produtos],
                         ["SSD Kingston KC3000, 1TB, M.2 NVMe", "SSD Kingston NV3, 1TB, M.2 2280"])
        kc, nv = produtos
        self.assertEqual(kc.preco, 499.99)  # usa o preço no PIX
        self.assertEqual(kc.url, "https://www.pichau.com.br/ssd-kingston-kc3000-1tb-m-2-nvme")
        self.assertEqual(kc.loja, "Pichau")
        self.assertEqual(nv.preco, 389.90)  # sem PIX, usa o preço no cartão

    def test_next_data_antigo(self):
        dados = {"props": {"pageProps": {"apolloState": {"products": PRODUTOS}}}}
        html = ('<html><body><script id="__NEXT_DATA__" type="application/json">%s'
                "</script></body></html>" % json.dumps(dados))
        self.assertEqual(len(comparador.parse_pichau(html)), 2)

    def test_desafio_cloudflare(self):
        html = ("<html><head><title>Just a moment...</title></head><body>"
                "<script>window._cf_chl_opt={}</script></body></html>")
        self.assertTrue(comparador.parece_bloqueio(html))
        self.assertFalse(comparador.parece_bloqueio(pagina_flight(PRODUTOS)))
        self.assertEqual(comparador.parse_pichau(html), [])

    def test_resposta_da_api(self):
        itens = json.loads(json.dumps(PRODUTOS))
        produtos = comparador.finalizar(
            [p for p in map(comparador._pichau_produto, itens) if p], "Pichau")
        self.assertEqual(len(produtos), 2)


if __name__ == "__main__":
    unittest.main()
