# Coleta os preços dos produtos de termos.txt e grava no banco (Supabase).
# Roda no seu PC, porque as lojas bloqueiam servidores na nuvem.
#
# Uso (PowerShell, nesta pasta):
#     .\coletar.ps1
#     .\coletar.ps1 -Lojas kabum
#     .\coletar.ps1 -Lojas amazon,kabum,pichau
#
# A string do banco fica no arquivo .env desta pasta, numa linha assim:
#     DATABASE_URL=postgresql://postgres.xxxx:SENHA@aws-1-us-east-2.pooler.supabase.com:5432/postgres
# (o .env não vai para o GitHub)

param(
    [string]$Lojas = "amazon,kabum"
)

$pasta = $PSScriptRoot
$env:PYTHONIOENCODING = "utf-8"

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

foreach ($termo in $termos) {
    python (Join-Path $pasta "comparador.py") $termo.Trim() --lojas $Lojas
    Start-Sleep -Seconds 5   # pausa entre buscas para não ser bloqueado
}
Write-Host "`nColeta concluida. Veja os precos no site." -ForegroundColor Green
