-- =============================================================
-- Tabelas do Comparador de Preços
-- Funciona no SQL Server local e no Azure SQL Database.
--
-- LOCAL (SSMS): crie o banco antes e selecione-o:
--     CREATE DATABASE Comparador;
--     GO
--     USE Comparador;
--
-- AZURE: o banco é criado pelo portal. Abra o "Editor de consultas"
-- do banco (ou conecte pelo SSMS) e rode só este script.
--
-- Pode rodar mais de uma vez: o que já existe é mantido.
-- =============================================================

IF OBJECT_ID('Loja') IS NULL
CREATE TABLE Loja (
    Id   INT IDENTITY PRIMARY KEY,
    Nome NVARCHAR(50) NOT NULL UNIQUE
);

IF OBJECT_ID('Produto') IS NULL
CREATE TABLE Produto (
    Id       INT IDENTITY PRIMARY KEY,
    Nome     NVARCHAR(300) NOT NULL,
    CriadoEm DATETIME2 NOT NULL DEFAULT SYSDATETIME()
);

-- Como o produto aparece em cada loja (nome e link de lá)
IF OBJECT_ID('Oferta') IS NULL
CREATE TABLE Oferta (
    Id         INT IDENTITY PRIMARY KEY,
    ProdutoId  INT NOT NULL REFERENCES Produto(Id),
    LojaId     INT NOT NULL REFERENCES Loja(Id),
    NomeNaLoja NVARCHAR(300) NOT NULL,
    Url        NVARCHAR(500) NOT NULL UNIQUE
);

-- Histórico: cada busca grava um novo preço
IF OBJECT_ID('Preco') IS NULL
BEGIN
    CREATE TABLE Preco (
        Id         BIGINT IDENTITY PRIMARY KEY,
        OfertaId   INT NOT NULL REFERENCES Oferta(Id),
        Valor      DECIMAL(10, 2) NOT NULL,
        ColetadoEm DATETIME2 NOT NULL DEFAULT SYSDATETIME()
    );
    CREATE INDEX IX_Preco_Oferta_Data ON Preco (OfertaId, ColetadoEm DESC);
END
GO

-- Último preço coletado de cada oferta
CREATE OR ALTER VIEW vw_PrecoAtual AS
SELECT OfertaId, Valor, ColetadoEm
FROM (
    SELECT OfertaId, Valor, ColetadoEm,
           ROW_NUMBER() OVER (PARTITION BY OfertaId
                              ORDER BY ColetadoEm DESC, Id DESC) AS Ordem
    FROM Preco
) x
WHERE Ordem = 1;
GO

INSERT INTO Loja (Nome)
SELECT Nome FROM (VALUES ('Amazon'), ('Kabum'), ('Mercado Livre'),
                         ('Pichau'), ('Terabyte'), ('Magalu')) AS v(Nome)
WHERE Nome NOT IN (SELECT Nome FROM Loja);
GO
