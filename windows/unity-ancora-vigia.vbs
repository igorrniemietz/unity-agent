' Unity - vigia da ancora do WSL. Roda de 2 em 2 minutos pelo Agendador de
' Tarefas do Windows, enquanto o dono estiver logado.
'
' Por que existe: TODA a Unity (daemon do Claude, units e timers do systemd)
' mora dentro da distro Ubuntu. O WSL derruba a distro poucos segundos depois
' que o ultimo cliente wsl.exe se desliga, e nada no Windows a levanta de
' volta. O unity-autostart.vbs cria uma ancora - um wsl.exe que fica vivo
' segurando a distro - mas ele so roda no LOGON. Entao qualquer coisa que mate
' a distro no meio da sessao (wsl --shutdown, um travamento, o proprio WSL
' recolhendo a VM) mata a ancora junto, e ninguem cria outra ate o proximo
' logon. Foi assim que a Unity ficou 9h10 fora do ar em 29/08 e outras 6h25 no
' mesmo dia, esta ultima depois de um wsl --shutdown para aplicar o .wslconfig.
'
' Nenhum vigia de DENTRO do WSL resolve isso: eles morrem junto com a distro.
' O vigia precisa ser do lado do Windows. Este e ele.
'
' Rodado por wscript.exe: nada de janela piscando de 2 em 2 minutos. O preco
' disso e que o wscript engole erro de sintaxe em silencio - para depurar,
' rode o mesmo arquivo com cscript.exe, que imprime a linha do erro.

Option Explicit

Const LOCK = "/tmp/unity-wsl-ancora.lock"
Const WSL  = "C:\Windows\System32\wsl.exe"
Const ARQLOG  = "/home/reaper/.local/share/unity-supervisor/ancora.log"

Dim sh, codigo
Set sh = CreateObject("WScript.Shell")

' flock -n sai 0 se CONSEGUIU pegar o lock (ou seja: ninguem estava ancorando)
' e 1 se alguem ja o segura. Este probe sobe a distro caso ela esteja caida -
' de proposito: e o mesmo passo que detecta o problema e que da a chance de
' consertar, na mesma passada.
codigo = sh.Run(WSL & " -d Ubuntu -- /bin/sh -c ""flock -n " & LOCK & " true""", 0, True)

' Qualquer coisa diferente de 0 (ancora viva, ou wsl.exe falhando) fica em paz:
' reancorar por cima nao ajuda, e falhar em laco so enche o log.
If codigo <> 0 Then WScript.Quit 0

' Ancora nova. O exec faz o sh virar o proprio flock, sem processo sobrando.
sh.Run WSL & " -d Ubuntu -- /bin/sh -c ""exec flock -n " & LOCK & " sleep infinity""", 0, False

' O systemd da distro leva alguns segundos para subir num boot frio; sem esta
' espera o systemctl --user abaixo pega o gerenciador ainda pela metade.
WScript.Sleep 10000

' Sem aspas internas de proposito: o parser de linha de comando do Windows fica
' entre o VBScript e o /bin/sh, e aspas escapadas aqui chegam mastigadas do
' outro lado. echo com palavras soltas resolve sem precisar de nenhuma.
sh.Run WSL & " -d Ubuntu -- /bin/sh -c ""date -Is >> " & ARQLOG & "; " & _
       "echo ancora recriada pelo vigia do Windows >> " & ARQLOG & "; " & _
       "/usr/bin/systemctl --user start unity-supervisor.service""", 0, True
