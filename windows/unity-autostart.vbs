' Unity — arranque no logon do Windows.
'
' O systemd do WSL so existe enquanto a distro esta de pe, e o Windows nao
' sobe a distro sozinho: ele espera alguem abrir um terminal. Ate la o
' unity-daemon.service nao roda e a Unity nao atende o Telegram, mesmo com
' `loginctl enable-linger` e as units habilitadas.
'
' Subir a distro, porem, nao basta. O WSL derruba a distro inteira poucos
' segundos depois que o ultimo cliente wsl.exe se desliga — e `wsl.exe -- cmd`
' se desliga assim que o comando termina. Era o que vinha acontecendo: o
' logon subia o Ubuntu, o supervisor rodava, e ~20s depois o WSL matava tudo
' (boots de 20-25s no `journalctl --list-boots` em 23/08, 24/08 e 26/08).
' O linger nao protege disso: quem encerra e o WSL, nao o logind.
'
' Por isso o primeiro passo agora e ancorar a distro: um cliente wsl.exe que
' fica vivo ate o logoff, segurando a sessao aberta. So depois o supervisor
' e acordado, para nao esperar os 45s do OnBootSec.
'
' O flock impede ancoras empilhadas se este script rodar duas vezes: a
' segunda desiste na hora, porque a primeira ja esta segurando a distro.
'
' Reintenta o supervisor porque uma falha aqui deixa a Unity fora do ar ate o
' proximo logon — nao ha quem tente de novo. As janelas ficam escondidas (o 0
' do Run).

Const ESPERA_INICIAL = 20000   ' 20s ate a primeira tentativa
Const ESPERA_ANCORA  = 15000   ' 15s para a distro terminar de subir
Const ESPERA_ENTRE   = 20000   ' 20s entre reintentos
Const TENTATIVAS     = 5

Dim sh, cmdAncora, cmdStart, i, codigo
Set sh = CreateObject("WScript.Shell")

cmdAncora = "C:\Windows\System32\wsl.exe -d Ubuntu -- /bin/sh -c " & _
            """exec flock -n /tmp/unity-wsl-ancora.lock sleep infinity"""
cmdStart  = "C:\Windows\System32\wsl.exe -d Ubuntu -- " & _
            "/usr/bin/systemctl --user start unity-supervisor.service"

WScript.Sleep ESPERA_INICIAL

' False = nao espera terminar. Este processo e que segura a distro de pe.
sh.Run cmdAncora, 0, False

WScript.Sleep ESPERA_ANCORA

For i = 1 To TENTATIVAS
    ' True = espera terminar, para poder ler o codigo de saida
    codigo = sh.Run(cmdStart, 0, True)
    If codigo = 0 Then
        Exit For
    End If
    WScript.Sleep ESPERA_ENTRE
Next
