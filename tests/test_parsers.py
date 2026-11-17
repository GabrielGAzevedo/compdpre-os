"""Testes dos leitores de página (parse_amazon, parse_kabum, parse_pichau).

Cada loja tem uma página de busca salva em tests/fixtures/. Se um teste daqui
falhar, foi o código do comparador que quebrou a leitura. Se os testes passam
mas a coleta volta 0 produtos, foi a loja que mudou a página (ou bloqueou):
rode `python tests/atualizar_fixtures.py` no PC para salvar páginas novas.

Rodar (nesta pasta):
    python -m unittest discover tests -v
"""

import unittest
from pathlib import Path
from unittest import mock

import comparador
from comparador import parse_amazon, parse_kabum, parse_pichau

FIXTURES = Path(__file__).parent / "fixtures"

# loja -> (função de leitura, nome da loja, início esperado das URLs, mínimo de produtos)
LOJAS = {
    "amazon": (parse_amazon, "Amazon", "https://www.amazon.com.br/", 3),
    "kabum": (parse_kabum, "Kabum", "https://www.kabum.com.br/produto/", 3),
    "pichau": (parse_pichau, "Pichau", "https://www.pichau.com.br/", 3),
}

PAGINA_BLOQUEADA = """<!doctype html><html><head><title>Just a moment...</title></head>
<body><div id="cf-chl-widget">Verificando se você é humano.</div>
<form action="/errors/validateCaptcha">captcha</form></body></html>"""


def ler_fixture(chave: str) -> str:
    return (FIXTURES / f"{chave}_busca.html").read_text(encoding="utf-8")


class TestLeituraDasLojas(unittest.TestCase):
    def test_cada_loja_devolve_produtos(self):
        for chave, (parse, nome, inicio_url, minimo) in LOJAS.items():
            with self.subTest(loja=chave):
                produtos = parse(ler_fixture(chave))
                self.assertGreaterEqual(
                    len(produtos), minimo,
                    f"{nome}: a página salva deveria render {minimo} ou mais produtos")
                for p in produtos:
                    self.assertEqual(p.loja, nome)
                    self.assertGreaterEqual(len(p.nome), 8, p)
                    self.assertGreater(p.preco, 0, p)
                    self.assertTrue(p.url.startswith(inicio_url), p.url)
                    self.assertNotIn("#", p.url)

    def test_respeita_limite_e_nao_repete(self):
        for chave, (parse, *_resto) in LOJAS.items():
            with self.subTest(loja=chave):
                produtos = parse(ler_fixture(chave))
                self.assertLessEqual(len(produtos), comparador.LIMITE_POR_LOJA)
                urls = [p.url for p in produtos]
                self.assertEqual(len(urls), len(set(urls)), "URL repetida")

    def test_pagina_de_bloqueio_devolve_lista_vazia(self):
        for chave, (parse, *_resto) in LOJAS.items():
            with self.subTest(loja=chave):
                self.assertEqual(parse(PAGINA_BLOQUEADA), [])


class TestDetalhesDaPaginaDeExemplo(unittest.TestCase):
    """Valores exatos das páginas de exemplo. Se você trocar as fixtures por
    páginas reais com atualizar_fixtures.py, estes testes são pulados."""

    def exemplo(self, chave: str) -> str:
        html = ler_fixture(chave)
        if "fixture de exemplo" not in html:
            self.skipTest(f"{chave}: fixture real, valores exatos não se aplicam")
        return html

    def test_amazon_ignora_card_sem_preco_e_limpa_url(self):
        produtos = parse_amazon(self.exemplo("amazon"))
        self.assertEqual(len(produtos), 3)  # o card patrocinado sem preço fica de fora
        self.assertEqual(produtos[0].preco, 379.90)
        self.assertEqual(produtos[2].preco, 1029.00)  # "R$ 1.029,00"
        self.assertNotIn("?", produtos[0].url)

    def test_kabum_usa_preco_com_desconto(self):
        produtos = parse_kabum(self.exemplo("kabum"))
        self.assertEqual(produtos[0].preco, 382.49)
        self.assertEqual(
            produtos[0].url,
            "https://www.kabum.com.br/produto/520389/"
            "ssd-kingston-nv2-1tb-m-2-2280-pcie-nvme-leitura-3500mb-s-snv2s-1000g")

    def test_pichau_usa_preco_a_vista(self):
        produtos = parse_pichau(self.exemplo("pichau"))
        self.assertEqual(produtos[0].preco, 369.99)


class TestBuscaSemRede(unittest.TestCase):
    """buscar_xxx com baixar_html simulado (não acessa a internet)."""

    def test_amazon_com_captcha_devolve_vazio(self):
        with mock.patch.object(comparador, "baixar_html", return_value=PAGINA_BLOQUEADA):
            self.assertEqual(comparador.buscar_amazon("ssd"), [])

    def test_loja_fora_do_ar_devolve_vazio(self):
        with mock.patch.object(comparador, "baixar_html", return_value=None):
            for chave in LOJAS:
                with self.subTest(loja=chave):
                    self.assertEqual(getattr(comparador, f"buscar_{chave}")("ssd"), [])

    def test_busca_le_a_pagina_baixada(self):
        for chave, (_parse, nome, *_resto) in LOJAS.items():
            with self.subTest(loja=chave), mock.patch.object(
                    comparador, "baixar_html", return_value=ler_fixture(chave)):
                produtos = getattr(comparador, f"buscar_{chave}")("ssd kingston 1tb")
                self.assertTrue(produtos)
                self.assertTrue(all(p.loja == nome for p in produtos))


if __name__ == "__main__":
    unittest.main()
