# TCL Home AC para Noctalia

Controle seu ar-condicionado TCL Home pela central de ações ou barra do Noctalia,
sem Alexa e sem precisar instalar Home Assistant.

**Depende da internet e da nuvem TCL/AWS. Não é controle local pela rede.**
A API é não oficial e pode mudar. Testado no **TAC-12CHTG2-INV**, com Noctalia
5.3.0 no CachyOS/Hyprland. Outros modelos e regiões não são garantidos.
Esta versão exige exatamente um ar-condicionado na conta.

## Instalação

Requer Python 3.11+, venv/pip, Git e Noctalia com API de plugins 24 ou superior.
No Arch/CachyOS: `sudo pacman -S --needed python git`.

Revise o código antes de executar:

```sh
git clone https://github.com/ggmorais/noctalia-tcl-control.git
sh noctalia-tcl-control/tcl-control/setup.sh
noctalia msg plugins source add tcl-home git https://github.com/ggmorais/noctalia-tcl-control.git
noctalia msg plugins enable ggmorais/tcl-control
```

O instalador cria um ambiente Python isolado e solicita o login do TCL Home,
com senha oculta. Não modifica o Python do sistema nem o estado do ar.
Use preferencialmente uma conta separada e compartilhe somente o ar desejado.

Em **Configurações → Central de ações**, adicione o atalho **TCL Home AC**.
Há no máximo seis atalhos visíveis: substitua outro se necessário.
Também há um widget opcional para a barra.

Para abrir diretamente:

```sh
noctalia msg panel-open ggmorais/tcl-control:controls
```

Você terá liga/desliga, temperatura (16–30 °C), modos, ventilação e visor.
Comandos só são enviados quando você usa os controles. O painel mostra o estado
reportado separadamente de comandos aguardando confirmação do aparelho.

Os botões **+ e −** mostram a temperatura escolhida imediatamente e enviam um único
comando **800 ms após o último clique**. Você pode continuar ajustando durante um
envio: somente o último valor escolhido será enviado em seguida, sem solicitações
concorrentes. Ao fechar o painel, o ajuste restante é enviado sem esperar o prazo
(ou após o envio em andamento terminar). Desativar/recarregar o plugin cancela
rascunhos ainda não enviados; erros não causam repetição automática dos comandos.

## Credenciais e segurança

- Credenciais em `~/.config/tcl-control/credentials.env` (ou `$XDG_CONFIG_HOME`),
  fora do repositório, com permissão `600`.
- **A senha fica em texto simples**: permissão de arquivo não é criptografia.
- Tokens de autenticação ficam somente na memória do processo.
- Ambiente Python em `~/.local/share/tcl-control/venv` (ou `$XDG_DATA_HOME`).
- Nenhuma senha, QR de compartilhamento ou token deve ir para commits/issues.
- O QR de compartilhamento não substitui o login de uma conta TCL Home.

Para atualizar dependências, execute novamente `setup.sh`; credenciais existentes
não são sobrescritas. Atualize o plugin pelo gerenciador do Noctalia.

Para desativar:

```sh
noctalia msg plugins disable ggmorais/tcl-control
```

Depois remova o atalho/widget nas configurações. Credenciais e ambiente Python
são mantidos para você decidir se deseja apagá-los.

O repositório tem catálogo próprio; **ainda não está no catálogo comunitário**.
Consulte o [README completo](README.md), a [política de segurança](SECURITY.md)
e os [créditos da integração de referência](NOTICE).
