# Prompt — Função da página /afiliados

> Prompt curto descrevendo a função da página unificada do vizin.Os.

**Função:** A página `/afiliados` é o hub único do programa de parceiros do vizin.Os ("O Uber da vizinhança").

**Para quem é:** Criadores de conteúdo e afiliados (hunters) parceiros do projeto.

**O que a página faz:**

A página pública é **enxuta** — o básico do básico, sem detalhar o sistema e as
regras de cada papel. Todo o conteúdo detalhado aparece **no painel**, em um bloco
completo acima do rodapé.

**Na página pública:**

1. **Hero** — o vizin.Os ("Uber da vizinhança"), app 100% brasileiro, independente
   e sem investidores, distribuído por criadores e afiliados. Traz os dois papéis
   (criador e afiliado) e os botões de criação de conta.
2. **O movimento (`#movimento`)** — o que é o projeto em um parágrafo, os três
   pilares (100% brasileiro, independente, anti-vigilância) e os links para o app,
   o documento técnico e o manual de moderação.
3. **A divisão (`#divisao`)** — a barra e os quatro percentuais (20% usuário,
   40% criador, 20% afiliado, 20% desenvolvimento) em uma linha de texto.
4. **Participar (`#participar`)** — CTA final curto com os dois botões.

**No painel do afiliado (fluxo em 4 grupos numerados):**

O painel é um fluxo, não uma pilha de cards soltos. Os grupos são numerados e
dão a ordem das ações:

1. **Seu link e seus números** — perfil, link de afiliado em destaque e os
   indicadores separados em **Atividade** (contatos, criadores recrutados,
   indicações) e **Dinheiro** (comissão total, disponível, em processamento, já
   sacado).
2. **Envie o convite por e-mail** — formulário com os dados do criador (como é
   conhecido, e-mail, onde encontrou e o `@`, obrigatório) e o botão “Verificar
   e enviar e-mail”, ao lado do card “Como funciona o envio”. A verificação da
   base é obrigatória e acontece no mesmo clique do envio. A VPS monta e dispara
   o e-mail: o texto do convite não aparece no painel.
3. **Acompanhe o resultado** — “Contatos recentes” e “Criadores recrutados” lado a
   lado. O contato é registrado sozinho quando o e-mail sai.
4. **Saque seu saldo** — pedido de saque e histórico de saques no mesmo card, em
   duas colunas; o histórico tem uma linha vertical à esquerda.

Hierarquia de títulos do painel: `H1` (painel) → `H2` (grupo) → `H3` (card) → `H4`
(subseção).

**No painel (bloco "Guia completo do programa", acima do rodapé):**

5. **Explica o projeto por dentro** — a história completa, os pilares e os links.
6. **Explica os dois programas** — passo a passo de 5 etapas para criador e afiliado.
7. **Explica a divisão** — a barra e os quatro itens e o fine-print do desconto.
8. **Guia completo de cada papel** — regras, templates, base de contatos, liberdade
   criativa e as regras do jogo.
9. **Transparência** — sem letras miútas, contato do time e o aviso de independência.

O bloco do papel atual (criador ou afiliado) fica destacado com o selo **"Seu
papel"**, e no fim aparece um convite para o outro papel (quem é afiliado vê o CTA
de virar criador, e vice-versa). O menu do topo acompanha: na página pública ele
aponta para `#movimento`, `#divisao` e `#participar`; no painel, para `#guiaProjeto`,
`#guiaPrograma` e `#guiaDivisao`.

O guia abre com um **sumário numerado** de seis links (`.guia-sumario`) para os
seis blocos, e dentro de cada bloco `H3` é o título e `H4` são as subseções.

**Funções do painel (criador e afiliado):**

10. **Cria conta** — criador escolhe o código; afiliado recebe um código aleatório gerado automaticamente.
11. **Dashboard** — criador (código, indicações, saldo, saques) e afiliado (link de afiliado em destaque, contatos na base, criadores recrutados, indicações, saldo, saques).
12. **Envio do convite** — só por e-mail, disparado pela VPS, com o link de
   afiliado creditado e o texto montado no servidor (invisível para o
   afiliado). Limite de 3 e-mails por afiliado a cada 3 dias.
13. **Atribuição** — link do afiliado (?a=<código>) salva o responsável no navegador (janela de 180 dias).
14. **Base de contatos** — compartilhada entre afiliados; identifica o criador por como é popularmente conhecido (não por @), bloqueando o contato duplicado.

**Regra de ouro:** a criação de conta de afiliado não pede código — gera um código aleatório direto para o painel.

**Ritmo visual:** o intervalo entre as seções da página pública e entre os grupos
do painel é sempre de **56px** (`--space-8`). Dentro das seções, rótulo → título
fica em 24px e título → texto em 16px. O texto é curto e direto: parágrafos de
no máximo ~25 palavras, sem repetir a mesma ideia no hero e no corpo.

**O painel do afiliado é próprio:** não repete o sistema de código do painel do
criador. O afiliado trabalha com o **link de afiliado** (em destaque no topo do
painel), não com um código para compartilhar.

**A verificação de criador é obrigatória e acontece junto com o envio do e-mail:**
a identidade usada na base é "como o criador é conhecido" (o mesmo criador usa
usernames diferentes em cada rede). O `@` do criador é obrigatório no formulário,
fica salvo por 6 meses e aparece no painel de dados do site (`/painel`); a
plataforma é apenas o contexto de onde o contato aconteceu.

**Envio do contato (no ar):** o envio é **somente por e-mail**, disparado pela
VPS (SMTP do Gmail com senha de app ou API HTTPS). O afiliado preenche os dados
do criador e a VPS monta e envia o e-mail — o texto não fica visível nem é
editável pelo afiliado. Limite: **3 e-mails por afiliado a cada 3 dias**,
contado no servidor; envio que falha não gasta cota. Não há mais template
copiável de e-mail nem de DM no painel: o registro do contato na base
compartilhada acontece junto com o envio.

- O painel mostra a cota no indicador **"E-mails enviados"** (`0/3`) e uma frase
  com quantos e-mails ainda restam na janela (e quando a próxima cota abre).
- Quando a janela acaba, o aviso é o de cota (**HTTP 429**). Quando o criador já
  foi contatado por outro afiliado, o aviso é o de contato duplicado (**HTTP
  409**) e a cota **não** é gasta.
- O texto do e-mail é montado no servidor: nenhuma frase do modelo existe no
  HTML nem no JS servido ao navegador.

**Link do painel (na janela de confirmação):** o link que aparece depois de criar
a conta ("Painel: …") usa a **mesma decoração em gradiente** do
`<span class="gradient-text">`, com o **corpo menor** para caber no modal. É a
regra `.panel-link a` do `assets/styles.css` (`background-clip: text`, `color:
transparent`, `font-size: 0.86rem`).

**Já validado no navegador (contra o site publicado):** criação da conta pelo
botão, link do painel em gradiente, os 3 envios da janela, o bloqueio do 4º
(envio), o bloqueio de criador repetido por outro afiliado, a persistência do
estado ao recarregar e a ausência do texto do e-mail no navegador.

**Bloqueio por IP:** a criação de conta é protegida por IP, decidido no servidor.

- **Datacenter, VPN, proxy, Tor ou IP fora do Brasil:** a página **não carrega**
  e o visitante vai direto para a página de erro (`/404.html`, com **status
  HTTP 404 real**).
- **IP que já criou uma conta:** a página carrega normalmente, mas a criação é
  recusada e aparece um **aviso curto dentro da janela**, em uma linha: "Você já
  criou uma conta de afiliado." ou "Você já criou uma conta de criador."
- A regra vale **por papel**: um IP pode ter uma conta de afiliado e uma de
  criador. O aviso só aparece no papel que o endereço já ocupou.
- **Quem já tem painel não é bloqueado**: link com token abre normalmente, mesmo
  de VPN ou datacenter.
- A classificação usa a ipquery.io (com fallback ipwho.is) e fica em cache por
  24 horas. Se a consulta externa falhar, ninguém é bloqueado.
- O backend é a autoridade: `POST /creators` e `POST /hunters` recusam com
  `403` e o código `IP_DENIED` ou `IP_BLOCKED_DUPLICATE`.
- Runbook completo: [`app/docs/guarda-ip.md`](../app/docs/guarda-ip.md).
