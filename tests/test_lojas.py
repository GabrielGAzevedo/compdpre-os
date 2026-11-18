"""Testes da escolha de lojas (--lojas / -Lojas). Rodam sem internet:
    python -m unittest discover tests
"""
import io
import os
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comparador as cmp  # noqa: E402


def lojas_falsas():
    """Troca as funções de busca por versões que não acessam a internet."""
    def vazia(termo):
        return []

    def com_produto(termo):
        return [cmp.Produto("Kabum", "SSD Kingston NV3 1TB", 399.9, "https://x/1")]

    def quebrada(termo):
        raise RuntimeError("bloqueado")

    return {
        "amazon": ("Amazon", vazia),
        "kabum": ("Kabum", com_produto),
        "pichau": ("Pichau", quebrada),
    }


class TestLerLojas(unittest.TestCase):
    def test_separadores_e_maiusculas(self):
        for texto in ("amazon,kabum", "Amazon, Kabum", "amazon kabum", "AMAZON;kabum", " amazon,,kabum "):
            self.assertEqual(cmp.ler_lojas(texto), (["amazon", "kabum"], []), texto)

    def test_lista(self):
        self.assertEqual(cmp.ler_lojas(["amazon", "kabum"]), (["amazon", "kabum"], []))

    def test_desconhecida(self):
        self.assertEqual(cmp.ler_lojas("amazom,kabum"), (["kabum"], ["amazom"]))

    def test_padrao_todas(self):
        self.assertEqual(cmp.ler_lojas(None), (list(cmp.LOJAS), []))


class TestBuscarEmLojas(unittest.TestCase):
    def test_lista_toda_loja_pedida_mesmo_vazia_ou_com_erro(self):
        with mock.patch.object(cmp, "LOJAS", lojas_falsas()), redirect_stdout(io.StringIO()):
            r = cmp.buscar_em_lojas("ssd", ["amazon", "kabum", "pichau"])
        self.assertEqual(list(r), ["Amazon", "Kabum", "Pichau"])
        self.assertEqual(len(r["Amazon"]), 0)
        self.assertEqual(len(r["Kabum"]), 1)
        self.assertEqual(len(r["Pichau"]), 0)


class TestMain(unittest.TestCase):
    def rodar(self, *args):
        saida = io.StringIO()
        with mock.patch.object(cmp, "LOJAS", lojas_falsas()), \
                mock.patch.object(sys, "argv", ["comparador.py", *args]), \
                mock.patch.dict(os.environ, {"DATABASE_URL": ""}), \
                redirect_stdout(saida):
            try:
                cmp.main()
                codigo = 0
            except SystemExit as e:
                codigo = e.code
        return codigo, saida.getvalue()

    def test_powershell_junta_com_espaco(self):
        # .\coletar.ps1 -Lojas amazon,kabum chega ao Python como "amazon kabum"
        codigo, saida = self.rodar("ssd", "--lojas", "amazon kabum")
        self.assertEqual(codigo, 0)
        self.assertIn("em Amazon, Kabum", saida)
        self.assertRegex(saida, r"(?m)^  Amazon\s+0 produtos$")
        self.assertRegex(saida, r"(?m)^  Kabum\s+1 produtos$")

    def test_loja_desconhecida_e_erro(self):
        codigo, saida = self.rodar("ssd", "--lojas", "amazom,kabum")
        self.assertEqual(codigo, 2)
        self.assertIn("amazom", saida)
        self.assertNotIn("produtos", saida)


if __name__ == "__main__":
    unittest.main()
