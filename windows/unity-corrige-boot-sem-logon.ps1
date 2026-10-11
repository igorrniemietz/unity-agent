# Unity - fecha o ultimo buraco: boot do Windows SEM logon interativo.
#
# PRECISA DE ELEVACAO (Executar como administrador). Rode UMA vez.
#
# O problema: a tarefa UnityAncoraVigia roda com LogonType=InteractiveToken,
# ou seja, SO existe enquanto o dono esta logado. Num boot desacompanhado
# (queda de energia, reinicio do Windows Update de madrugada) o PC fica ligado
# na tela de bloqueio e NADA levanta a distro - a Unity fica fora do ar pelo
# tempo todo que o PC passar ali. Medido: 15 min em 07/10 e 19 min em 30/09.
#
# A correcao tem duas metades:
#   1. LogonType=S4U  -> a tarefa passa a rodar logado ou nao, sem guardar senha.
#   2. Gatilho ONSTART -> ela dispara no boot da maquina, nao so no logon.
#
# Continua rodando como Reaper (NAO como SYSTEM): a VM do WSL2 e por usuario
# do Windows, e uma tarefa como SYSTEM subiria uma distro SEPARADA, com dois
# daemons brigando pelo mesmo lock.

$ErrorActionPreference = 'Stop'
$nome = 'UnityAncoraVigia'

$p = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
  Write-Host "ERRO: rode este script numa janela ELEVADA (Executar como administrador)." -ForegroundColor Red
  exit 1
}

$antes = Join-Path $env:USERPROFILE ("unity-ancora-vigia.backup-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + ".xml")
Export-ScheduledTask -TaskName $nome | Set-Content -Path $antes -Encoding Unicode
Write-Host "backup da tarefa atual: $antes"

$tempo = New-ScheduledTaskTrigger -Once -At '2026-08-29T22:46:00' -RepetitionInterval (New-TimeSpan -Minutes 2)
$logon = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$boot  = New-ScheduledTaskTrigger -AtStartup

$cls = Get-CimClass -ClassName MSFT_TaskEventTrigger -Namespace Root/Microsoft/Windows/TaskScheduler
$evt = New-CimInstance -CimClass $cls -ClientOnly
$evt.Enabled = $true
$evt.Subscription = '<QueryList><Query Id="0" Path="System"><Select Path="System">*[System[Provider[@Name=''Microsoft-Windows-Kernel-Power''] and EventID=107]]</Select></Query></QueryList>'

$princ = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType S4U -RunLevel Limited
$cfg   = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
            -MultipleInstances IgnoreNew -StartWhenAvailable `
            -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries

Set-ScheduledTask -TaskName $nome -Principal $princ -Trigger @($tempo,$logon,$boot,$evt) -Settings $cfg | Out-Null

$x = [xml](Export-ScheduledTask -TaskName $nome)
Write-Host ""
Write-Host "LogonType agora : $($x.Task.Principals.Principal.LogonType)   (esperado: S4U)"
Write-Host "gatilhos        : $(($x.Task.Triggers.ChildNodes | ForEach-Object { $_.Name }) -join ', ')"
$i = Get-ScheduledTaskInfo -TaskName $nome
Write-Host "proxima execucao: $($i.NextRunTime)"
Write-Host ""
Write-Host "Para reverter:  Register-ScheduledTask -Xml (Get-Content '$antes' -Raw) -TaskName '$nome' -Force"
