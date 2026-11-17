# Coleta os preços dos produtos de termos.txt e grava no banco (Supabase).
# Roda no seu PC, porque as lojas bloqueiam servidores na nuvem.
#
# Uso (PowerShell, nesta pasta):
#     .\coletar.ps1
#     .\coletar.ps1 -Lojas kabum
#     .\coletar.ps1 -Lojas amazon,kabum,pichau
#     .\coletar.ps1 -AvisarApos 5
#
# Se uma loja devolver 0 produtos em -AvisarApos termos seguidos (padrão: 3),
# aparece um AVISO em amarelo: a loja provavelmente bloqueou o acesso ou mudou
# a página. No fim, um resumo mostra quantos termos vieram vazios em cada loja.
#
# A string do banco fica no arquivo .env desta pasta, numa linha assim:
#     DATABASE_URL=postgresql://postgres.xxxx:SENHA@aws-1-us-east-2.pooler.supabase.com:5432/postgres
# (o .env não vai para o GitHub)

param(
    [string]$Lojas = "amazon,kabum",
    [int]$AvisarApos = 3
)

$pasta = $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"                      # mostra cada linha na hora
[Console]::OutputEncoding = [Text.Encoding]::UTF8  # acentos certos ao ler a saída do Python

# Lê o .env
$arquivoEnv = Join-Path $pasta ".env"
if (Test-Path $arquivoEnv) {
    foreach ($linha in Get-Content $arquivoEnv -Encoding utf8) {
        if ($linha -match '^\s*([A-Z_]+)\s*=\s*(.+?)\s*$') {
            Set-Item -Path "env:$($Matches[1])" -Value $Matches[2]
        }
    }
}
if (-not $env:DATABASE_URL) {
    Write-Host "Crie o arquivo .env com a linha DATABASE_URL=... (veja o topo deste script)." -ForegroundColor Red
    exit 1
}

$termos = Get-Content (Join-Path $pasta "termos.txt") -Encoding utf8 |
    Where-Object { $_.Trim() -and -not $_.Trim().StartsWith("#") }

# Por loja: termos seguidos sem produto, total de termos vazios e termos com produto
$seguidos = @{}
$vazios = @{}
$comProduto = @{}

foreach ($termo in $termos) {
    python (Join-Path $pasta "comparador.py") $termo.Trim() --lojas $Lojas | ForEach-Object {
        Write-Host $_
        # o comparador imprime uma linha por loja, por exemplo "  Amazon         7 produtos"
        if ($_ -match '^\s{2}(\S.*?)\s+(\d+) produtos\s*$') {
            $loja = $Matches[1]
            $qtd = [int]$Matches[2]
            if ($qtd -eq 0) {
                $seguidos[$loja] = 1 + [int]$seguidos[$loja]
                $vazios[$loja] = 1 + [int]$vazios[$loja]
                if ($seguidos[$loja] -eq $AvisarApos) {
                    Write-Host ""
                    Write-Host "  AVISO: $loja voltou 0 produtos em $AvisarApos termos seguidos." -ForegroundColor Yellow
                    Write-Host "  Ela provavelmente bloqueou o acesso (captcha, 403, 503) ou mudou a pagina." -ForegroundColor Yellow
                    Write-Host "  Veja os [aviso] acima. Para diagnosticar: python tests\atualizar_fixtures.py" -ForegroundColor Yellow
                    Write-Host ""
                }
            } else {
                if ([int]$seguidos[$loja] -ge $AvisarApos) {
                    Write-Host "  $loja voltou a responder ($qtd produtos)." -ForegroundColor Green
                }
                $seguidos[$loja] = 0
                $comProduto[$loja] = 1 + [int]$comProduto[$loja]
            }
        }
    }
    Start-Sleep -Seconds 5   # pausa entre buscas para não ser bloqueado
}

# Resumo por loja
Write-Host "`nResumo da coleta ($($termos.Count) termos):"
$problema = $false
foreach ($loja in (@($vazios.Keys) + @($comProduto.Keys) | Sort-Object -Unique)) {
    $v = [int]$vazios[$loja]
    $ok = [int]$comProduto[$loja]
    $linha = "  {0,-14} {1} com produtos, {2} vazios" -f $loja, $ok, $v
    if ($ok -eq 0) {
        Write-Host "$linha  <- NENHUM produto na coleta toda" -ForegroundColor Red
        $problema = $true
    } elseif ([int]$seguidos[$loja] -ge $AvisarApos) {
        Write-Host "$linha  <- terminou com $($seguidos[$loja]) vazios seguidos" -ForegroundColor Yellow
        $problema = $true
    } else {
        Write-Host $linha
    }
}
if ($problema) {
    Write-Host "`nColeta concluida, mas alguma loja parou de responder (veja acima)." -ForegroundColor Yellow
} else {
    Write-Host "`nColeta concluida. Veja os precos no site." -ForegroundColor Green
}
