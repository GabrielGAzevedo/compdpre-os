-- =============================================================
-- Tabelas do Comparador de Preços (PostgreSQL / Supabase)
--
-- No Supabase: menu "SQL Editor" > "New query", cole este arquivo
-- inteiro e clique em "Run".
--
-- Pode rodar mais de uma vez: o que já existe é mantido.
-- =============================================================

CREATE TABLE IF NOT EXISTS loja (
    id   SERIAL PRIMARY KEY,
    nome VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS produto (
    id        SERIAL PRIMARY KEY,
    nome      VARCHAR(300) NOT NULL,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Como o produto aparece em cada loja (nome e link de lá)
CREATE TABLE IF NOT EXISTS oferta (
    id           SERIAL PRIMARY KEY,
    produto_id   INT NOT NULL REFERENCES produto(id),
    loja_id      INT NOT NULL REFERENCES loja(id),
    nome_na_loja VARCHAR(300) NOT NULL,
    url          VARCHAR(500) NOT NULL UNIQUE
);

-- Histórico: cada busca grava um novo preço
CREATE TABLE IF NOT EXISTS preco (
    id          BIGSERIAL PRIMARY KEY,
    oferta_id   INT NOT NULL REFERENCES oferta(id),
    valor       NUMERIC(10, 2) NOT NULL,
    coletado_em TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_preco_oferta_data ON preco (oferta_id, coletado_em DESC);

-- Último preço coletado de cada oferta
CREATE OR REPLACE VIEW vw_preco_atual WITH (security_invoker = true) AS
SELECT DISTINCT ON (oferta_id) oferta_id, valor, coletado_em
FROM preco
ORDER BY oferta_id, coletado_em DESC, id DESC;

-- O Supabase também expõe as tabelas numa API pública. Ligar o RLS sem
-- nenhuma regra bloqueia esse acesso; o site continua funcionando porque
-- conecta direto no banco como dono das tabelas.
ALTER TABLE loja    ENABLE ROW LEVEL SECURITY;
ALTER TABLE produto ENABLE ROW LEVEL SECURITY;
ALTER TABLE oferta  ENABLE ROW LEVEL SECURITY;
ALTER TABLE preco   ENABLE ROW LEVEL SECURITY;

INSERT INTO loja (nome)
VALUES ('Amazon'), ('Kabum'), ('Mercado Livre'), ('Pichau'), ('Terabyte'), ('Magalu')
ON CONFLICT (nome) DO NOTHING;
