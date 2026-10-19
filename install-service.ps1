<#
.SYNOPSIS
Instala o Dashboard Parque Suspenso como serviço Windows usando NSSM ou o utilitário nativo `sc`.

.DESCRIPTION
Este script tenta instalar o dashboard como serviço Windows.
- Se NSSM (Non-Sucking Service Manager) estiver disponível, usa-o.
- Se não, tenta usar o utilitário nativo do Windows `sc create`.
- Caso contrário, fornece instruções manuais.

Pré-requisitos:
- O dashboard já deve estar funcional em localhost:8503.
- O Python e o Streamlit devem estar configurados.
- Para `sc` nativo: o caminho do lote deve ser absoluto.

EXEMPLO DE USO:
    PowerShell > .\install-service.ps1
    PowerShell > .\install-service.ps1 -UseSc  # forçar uso do sc nativo
#>

param(
    [switch]$UseSc,
    [string]$ServiceName = "ParqueSuspenso-Dashboard",
    [string]$DisplayName = "Parque Suspenso - Dashboard Executivo",
    [string]$Description = "Monitoramento, priorização e recuperação de linhas corporativas suspensas (B2B).",
    [string]$PythonPath = (python -c "import sys; sys.path.insert(0, '.'); print(sys.executable)"),
    [string]$ScriptAbsolute = (Resolve-Path "$PSScriptRoot\..\app.py").Path,
    [string]$Port = "8503"
)

Write-Host "=== Instalador de Serviço Windows - Dashboard Parque Suspenso ===" -ForegroundColor Cyan

# Detecta o Python executable
if (-not $PythonPath -or $PythonPath -eq "") {
    Write-Error "Não foi possível detectar o executável do Python."
    return 1
}

# Constrói o comando de início
$startCmd = "& '\"$PythonPath\"' -m streamlit run \"$ScriptAbsolute\" --server.port $Port --server.headless true"

if ($UseSc -or (-not (Get-Command nssm.exe -ErrorAction SilentlyContinue))) {
    Write-Host "Usando utilitário nativo `sc`..." -ForegroundColor Yellow

    # Para serviço já existir
    try { sc stop $ServiceName 2>$null; sc delete $ServiceName 2>$null } catch {}

    # Cria o serviço usando o Python executável para rodar o streamlit
    $binaryPath = "\"$PythonPath\" -m streamlit run \"$ScriptAbsolute\" --server.port $Port --server.headless true"

    try {
        $result = sc create $ServiceName binPath= $binaryPath start= auto displayname= "$DisplayName" depend= "" 2>&1
        Write-Host "Resultado do `sc create`: $result" -ForegroundColor Green

        if ($result -match "OK") {
            sc start $ServiceName
            Write-Host "Serviço `$ServiceName` criado e iniciado com sucesso!" -ForegroundColor Green
            Write-Host "Acesse o dashboard em: http://localhost:$Port" -ForegroundColor Cyan
        } else {
            Write-Warning "O `sc create` não retornou OK. Verifique a saída acima."
            Write-Host "Para instalação manual com NSSM:" -ForegroundColor Yellow
            Write-Host "  1. Baixe o NSSM em https://nssm.io/"
            Write-Host "  2. Execute: nssm install $ServiceName"
            Write-Host "  3. Em 'Path': $startCmd"
            Write-Host "  4. Em 'Startup': Auto"
            Write-Host "  5. Execute: nssm start $ServiceName"
        }
    } catch {
        Write-Error "Erro ao criar serviço com `sc`: $_"
        Write-Host "Alternativa: instalar NSSM manualmente." -ForegroundColor Red
    }
}
else {
    Write-Host "Usando NSSM detectado..." -ForegroundColor Cyan

    try {
        # Tenta localizar nssm
        $nssmPath = "nssm.exe"
        if (-not (Test-Path $nssmPath)) {
            Write-Warning "nssm.exe não encontrado no PATH. Baixe em https://nssm.io/"
            return 1
        }

        # Remove serviço antigo se existir
        try { & $nssmPath remove $ServiceName confirm 2>$null } catch {}

        # Configura o serviço
        $env:NSSMPATH = & $nssmPath install $ServiceName $startCmd 2>&1
        Write-Host "NSSM instalado. Para iniciar:" -ForegroundColor Green
        & $nssmPath start $ServiceName
        Write-Host "Dashboard disponível em: http://localhost:$Port" -ForegroundColor Cyan
    }
    catch {
        Write-Error "Erro ao usar NSSM: $_"
        # Fallback para instruções manuais
        Write-Host "=== INSTALAÇÃO MANUAL NECESÁRIA ===" -ForegroundColor Red
        Write-Host "1. Baixe o NSSM em https://nssm.io/ e coloque em C:\\Windows\\System32\\"
        Write-Host "2. Execute em PowerShell como ADMINISTRADOR:" -ForegroundColor Cyan
        Write-Host "   nssm install $ServiceName" -ForegroundColor Green
        Write-Host "   Caminho: $startCmd" -ForegroundColor Green
        Write-Host "   Inicialização: Auto" -ForegroundColor Green
        Write-Host "   nssm start $ServiceName" -ForegroundColor Green
        Write-Host "3. Acesse em: http://localhost:$Port" -ForegroundColor Cyan
    }
}

Write-Host "=== Fim do instalador ===" -ForegroundColor Cyan