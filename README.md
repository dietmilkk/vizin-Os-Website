# vizin.Os — site de apresentação

Site estático, minimalista e responsivo para apresentar o app **vizin.Os**.
Sem build, sem framework e sem dependências de runtime.

**No ar:** <https://vizin-os.page.gd> · **API:** `https://api.188.166.156.109.sslip.io`
· **cópia de trabalho na VPS:** `https://site.188.166.156.109.sslip.io`

> `vizin-os.page.gd` é um subdomínio gratuito do page.gd (hospedagem
> InfinityFree). O DNS dele não aponta para a VPS — a publicação no domínio
> oficial é feita por FTP ou por pacote `.zip` (ver [Deploy](#deploy)).

## Páginas

| Arquivo | Público | Função |
| --- | --- | --- |
| `index.html` | Sim | Landing page em texto contínuo: a ilusão da conexão, o problema dos apps, o vizin.Os, privacidade e convite |
| `documento/index.html` | Sim | Explicação detalhada em `/documento` para imprensa e mídia de tecnologia: identidade local, regiões por bairro (raio máximo de 5 km), criptografia, transporte entre pares e moderação — sem detalhes internos |
| `afiliados/index.html` | **Não listado** | Hub único do programa de parceiros em `/afiliados`: apresentação, guia completo, criação de conta, painel do criador e painel do afiliado |
| `moderacao/index.html` | Sim | Manual público em `/moderacao` sobre como a moderação funciona: denúncias, votação, banimentos, reputação e convivência |
| `painel/index.html` | Sim | Painel público em `/painel`: estatísticas agregadas do serviço (dispositivos ativos, regiões, consumo do servidor, parceiros), sem nenhum dado pessoal |
| `404.html` | — | Página de erro |

A página `/afiliados` **não aparece no menu, no sitemap ou no rodapé**. Ela é
enviada apenas nos convites de criadores e afiliados, e usa
`noindex, nofollow, noarchive` no `<meta name="robots">`. O `robots.txt`
também bloqueia `/afiliados` e `/criadores`.

O antigo `/criadores` virou **apelido**: responde `301` para `/afiliados/`,
que é a URL canônica — o mesmo vale nos três lugares onde o site roda
(Caddy na VPS, `.htaccess` no InfinityFree e `_redirects` no Cloudflare Pages).
A pasta `criadores/` no repositório está vazia de propósito — o HTML vive em
`afiliados/index.html`.

### O que as páginas públicas dizem sobre o app

As páginas públicas descrevem o app do jeito que ele funciona hoje:

- **Regiões (`/documento`)**: cada região é um conjunto de **bairros** (municípios do
  IBGE) montado no próprio aparelho. O nome da região é a **lista de todos os bairros**
  que ela contém, separados por vírgula; cada bairro pertence a **exatamente uma**
  região (nenhum bairro se repete) e o **raio máximo é de 5 km**. A localização é
  estritamente por bairro: o ponto do aparelho vira o município mais próximo, e é ele
  que define a região.
- **Moderação (`/moderacao`)**: manual público enxuto, com denúncias, votação,
  banimentos, reputação e score de convivência. É o resumo do que o app faz, não um
  regulamento completo.
- **Social (em breve)**: a aba “Social” do app é só um **aviso**. O feed cronológico,
  sem algoritmo, ainda não existe — e nenhuma página do site promete a feature como
  disponível.

## Prévia local

```bash
cd site
python3 tools/servidor-local.py
```

Abra `http://localhost:8099`.

O `python3 -m http.server` não serve: ele é single-threaded e trava quando o
navegador mantém a conexão aberta, o que derruba a suíte de Playwright.
`tools/servidor-local.py` usa `ThreadingHTTPServer` (uma thread por conexão).
Para servir outra pasta/porta: `python3 tools/servidor-local.py <raiz> <porta>`.

## Estrutura

```
index.html                  Página principal
documento/index.html            Página para imprensa/mídia em /documento
afiliados/index.html        Hub do programa de parceiros em /afiliados
moderacao/index.html        Manual público de moderação em /moderacao
painel/index.html           Painel público de estatísticas em /painel
404.html                    Página de erro
assets/styles.css           Design system papel quente + rosa, claro/escuro e responsivo
assets/app.js               Menu mobile, reveal e link de download
assets/creators.js          Programa de parceiros: cadastro, painéis, atribuição, envio de e-mail e contatos
assets/config.js            URL da API, link do APK e contato
assets/pix.js               Gerador de BR Code (Pix) usado nos saques
assets/panel.js             Painel público: busca /stats/public e atualiza a cada 60 s
assets/galeria/             Imagens da galeria de etapas
assets/favicon.png          Favicon
assets/icon-192.png         Ícone PWA
assets/icon-512.png         Ícone PWA
assets/apple-touch-icon.png
site.webmanifest            Manifest PWA
_headers                    Cabeçalhos de segurança e noindex dos criadores
_redirects                  Redireciona /afiliados e /criadores (Cloudflare Pages)
.htaccess                   Equivalente do _redirects para hospedagem compartilhada
                            (InfinityFree): página 404 própria, sem listagem de
                            pastas e bloqueio de arquivos internos
robots.txt                  Indexação (bloqueia /afiliados e /criadores)
sitemap.xml                 Sitemap (sem /afiliados)
prompt-afiliados.md         Prompt de função e regras da página /afiliados
tests/pix.test.js           Testes do gerador PIX
tests/painel.test.mjs       Teste do painel público: roda o panel.js real contra a API real
tests/test-stats-publico.py Teste fim a fim do GET /stats/public (contrato + privacidade)
tests/test-painel-publico.py Teste do /painel no Chromium (navegador de verdade)
tests/test-layout-painel.py Auditoria de layout do /painel (desktop, tablet e celular)
tests/capturar-painel.py    Capturas de tela do /painel (desktop e celular)
tests/lib/seed_stats.py     Cenário de dados compartilhado pelos testes do painel
tests/test-painel-afiliado.py  Teste end-to-end do painel de afiliado (Playwright)
tests/test-layout-afiliado.py  Teste de layout e responsividade do painel
tests/test-guard-ip.py      Teste do bloqueio por IP no navegador (API simulada)
tests/test-usuario-real.py  Jornada completa de uso contra a produção
tests/test-guia-acordeao.py Teste do guia em acordeão (um bloco por vez) e do rodapé minimalista
tests/test-breadcrumb.py   Teste do breadcrumb onde ele existe (desktop e celular)
tests/conferir-oficial.py  Confere o conteúdo publicado no domínio oficial (como visitante)
tests/auditoria-mobile.py   Auditoria de layout no celular em todas as páginas do site
tests/medir-header.py       Confere que o header tem a mesma largura em todas as páginas
tests/alinhamento-paginas.py Confere que o conteúdo de cada página alinha com o header
tests/passeio-final.py    Passeio final pelo site publicado (desktop e celular), com caça a erros de JS
tools/servidor-local.py   Servidor local com threads (o http.server padrão trava com keep-alive)
tools/prints-header.py      Prints do topo das páginas (conference visual do header)
tools/check-site.py         Validação estática
tools/check-links.py        Rastreia o site como um usuário (Chromium) e checa todo link interno
tools/conferir-dominio.py   Confere o site no ar como uma pessoa: páginas, canonical, painel e vazamentos
tools/comparar-site-publicado.py  Confere se o publicado é idêntico ao repositório
tools/comparar-painel-publicado.py  Confere os blocos do painel publicado
tools/auditar-painel-visual.py  Auditoria visual (geometria) do painel
tools/checar-painel-publicado.py  Checagem rápida do painel publicado
tools/diff-publicado.py     Diferença entre o publicado e o repositório
tools/ver-painel-publico.py  Mostra os números do painel publicado (como um visitante)
tools/provar-online-ao-vivo.py  Prova que "dispositivos online agora" responde ao uso real do app
tools/deploy-infinityfree.py  Espelho do site público no InfinityFree (FTP) + conferência no ar
tools/deploy-infinityfree.sh  Atalho para o deploy-infinityfree.py
tools/recuperar-ftp-infinityfree.py  Lê as credenciais de FTP no painel do InfinityFree
tools/pacote-infinityfree.sh Gera o .zip para subir pelo File Manager
tools/prever-painel.sh      Prévia local do /painel com uma API de verdade (sem deploy)
tools/deploy-vps.sh         Publica API e site na VPS, com backup do banco e verificação
tools/limpar-teste.sh       Limpa os dados de teste na VPS (libera o IP; aceita --ip)
tools/limpar-teste-vps.ts   Script de limpeza executado na VPS (aceita --ip)
tools/testar-envio-real.sh  Ciclo completo do teste de e-mail (SMTP de captura na VPS)
tools/gateway-email-local.py Gateway de e-mail no PC (fala o formato do Resend e entrega via Gmail)
tools/rodar-gateway-email.sh Sobe o gateway no PC, abre o túnel SSH e aponta a VPS para ele
tools/apontar-gateway-local.py Aponta a API da VPS para o gateway do PC (token pelo stdin)
tools/ativar-gmail-smtp.py  Liga o transporte SMTP do Gmail na VPS (senha de app pelo stdin)
tools/restaurar-mail-api.py  Volta ao transporte HTTPS (api) na VPS
tools/make-images.py        Geração dos ícones
tools/simplify-site.py      Simplificação do HTML servido
tools/montar-publicacao-vercel.py  Monta a pasta de publicação da Vercel (site publicado + snippet do Analytics)
tools/commitar-publicacao-vercel.py  Cria o commit de publicação sem tocar no working tree
tools/check-analytics-vercel.py  Confere no navegador que o script do Analytics carrega em todas as páginas
tools/checar-segredos.py   Varre o que seria versionado em busca de segredo vazado (sai com 1 se achar)
tools/hooks/pre-commit     Hook do Git: bloqueia o commit se houver segredo no que entraria
tools/systemd/vizin-gateway-email.service  Unidade que sobe o gateway de e-mail no boot do PC
```

## Configuração

Edite `assets/config.js`:

```js
window.VIZINHANCA_CONFIG = Object.freeze({
  siteUrl: 'https://vizin-os.page.gd',
  apiUrl: 'https://api.188.166.156.109.sslip.io',
  androidUrl: 'https://play.google.com/store/apps/details?id=dev.vizinhoos.app',  // link da Play Store
  iosUrl: '',
  contactEmail: 'vizin.oos@gmail.com',
});
```

- **`androidUrl`**: o botão “Quero testar no Android” aponta para a Google Play
  Store.
- **`apiUrl`**: usado pela página de criadores/afiliados para gerar códigos,
  consultar comissões, gerenciar contatos e solicitar saques.
- **`contactEmail`**: contato exibido no rodapé e nas páginas públicas.

## Página de criadores e afiliados

A página `/afiliados` apresenta o projeto e os dois programas no mesmo lugar:

- **Criador**: escolhe um código (3–32 letras, números, `_` ou `-`), compartilha
  com a audiência e recebe **40%** de cada pagamento confirmado por 1 ano.
- **Afiliado**: encontra criadores de conteúdo, apresenta o projeto, registra o
  contato na base compartilhada e recebe **20%** dos pagamentos gerados pelos
  criadores que recrutou.
- **Usuário indicado**: ganha **15 dias com todos os recursos Plus desbloqueados**,
  sem pagar nada, e ainda **20% de desconto** no Plus por 1 ano.
- **Desenvolvimento**: os **20%** restantes pagam os servidores, a estrutura e o
  criador do app. Manter o espaço vivo é o que faz as pessoas aparecerem.

Outros pontos:

- A **janela flutuante de criação** é curta e direta: título ("Criar conta"),
  uma linha de texto ("Defina seu código." / "Geramos seu código.") e o botão
  ("Criar"). Nada mais. O `h2` do modal tem fonte própria
  (`.modal-card h2`, ~1,2–1,35rem) porque o `h2` global do site é grande demais
  para uma janela pequena. Na confirmação, o texto é "Pronto 🎉" + "Guarde o
  link: é a sua senha." + o link + "Abrir painel".
- O cadastro de criador e de afiliado usa o mesmo fluxo: código, painel e link
  secreto de acesso (o link é a senha). O afiliado **não escolhe código**: o
  **navegador** gera um código aleatório de 6 caracteres
  (`generateAffiliateCode()`, em `assets/creators.js`) e a VPS apenas valida se
  ele está livre antes de gravar a conta.
- **Quem já tem uma conta pode ter a outra.** O painel de cada papel traz o
  botão para criar o papel complementary ("Criar conta de afiliado" no painel
  do criador, "Criar conta de criador" no do afiliado). A segunda conta nasce
  com o **mesmo `@`** da primeira (`handleAtual` em `assets/creators.js`): a
  pessoa continua sendo a mesma, com os dois papéis. Na VPS as contas de
  criador e de afiliado ficam em tabelas diferentes (`creators` e `hunters`),
  cada uma com `handle` único — por isso o mesmo `@` pode existir nas duas.
  O bloqueio por IP é **por papel**: quem já tem uma conta recebe o aviso "a
  conta de afiliado ainda está disponível" (e vice-versa) em vez de um erro
  seco.
- O **link do painel** é curto e minimalista: `https://vizin-os.page.gd/afiliados?p=CXXXXXXXXXXXXXXX`
  (criador) ou `?p=AXXXXXXXXXXXXXXX` (afiliado). São 16 caracteres — um prefixo
  de papel (`C`/`A`) mais 15 caracteres base32 — e ele **é a senha de acesso**.
  Os links antigos (`?token=` e `?afiliado_token=`) continuam funcionando.
- O afiliado tem um link no formato
  `https://vizin-os.page.gd/afiliados?a=SEUCODIGO`. O código fica salvo no
  navegador por 180 dias (primeira visita) e é enviado como `hunter_code` quando
  o criador cria a conta.
- **O vínculo afiliado → criador é real e fica registrado.** Quando o criador
  cria a conta pelo link do afiliado, a VPS grava o `hunter_id` na linha do
  criador (`creators.hunter_id`). No painel do afiliado isso aparece como
  **“criadores recrutados”** (`recruited_creators`), com a lista do `@`, do
  código e da comissão de cada um. É esse vínculo que dá ao afiliado os **20%**
  sobre os pagamentos dos criadores que ele trouxe. Verificado em produção:
  criar o afiliado, criar o criador com `hunter_code` do afiliado e ler
  `GET /hunters/me` — o `recruited_creators` sobe para 1 e o criador aparece
  em `recent_creators`.
- O painel do afiliado é próprio e **organizado em 4 grupos numerados**, que dão a
  ordem das ações: (1) seu link e seus números, (2) envie o convite por e-mail,
  (3) acompanhe o resultado, (4) saque seu saldo. Ele mostra o
  **link de afiliado** em destaque (sem sistema de código, que é exclusivo do painel
  do criador), contatos registrados, criadores recrutados, indicações, comissão,
  saldo disponível, valores em processamento, já sacados e histórico.
  - **A aparência é quase uma cópia do painel do criador**: os dois painéis
    compartilham o mesmo desenho de cartão (título grande no topo, texto de apoio
    cinza, indicadores em grade, caixa tracejada do link/código à direita). O que
    muda é só o conteúdo: o afiliado tem 4 grupos numerados e o criador tem 3
    cartões soltos.
  - Hierarquia de títulos: `H1` (painel) → `H2` (grupo) → `H3` (card) → `H4`
    (subseção). Os números dos grupos ficam em `aria-hidden` porque o texto do
    título já dá o contexto.
  - Os números são uma grade só de indicadores, como no painel do criador:
    contatos registrados, criadores recrutados, indicações geradas, e-mails
    enviados, comissão total, disponível, em processamento e já sacado.
  - A **cota de e-mail** mora no próprio indicador "E-mails enviados": o
    contador (`1/3`) e a mensagem da janela no `title`/`aria-label` do cartão.
    Não há parágrafo separado para a regra — o texto fixo ("3 e-mails a cada
    3 dias") está na lista "Como funciona o envio".
  - O formulário de envio ocupa a largura inteira do cartão e a explicação
    ("Como funciona o envio") fica **abaixo** dele, separada por uma regra —
    não são lado a lado. "Contatos recentes" e "Criadores recrutados" (grupo 3)
    e "Pedir saque"/"Histórico de saques" (grupo 4) são os blocos que dividem a
    linha em duas colunas. O envio é direto: o botão é "Enviar e-mail", sem
    etapa de verificação no formulário (a base continua recusando contato
    duplicado no servidor).
- **O bloco de saque é o mesmo nos dois painéis** (`.withdraw-panel` em
  `/assets/styles.css`): o formulário à esquerda, o histórico à direita, com
  uma linha vertical separando as colunas. Ele existe no painel do afiliado
  (grupo 4, “Saque seu saldo”) e no do criador (card “Sacar saldo”), onde
  substituiu os dois cards separados que havia antes (“Sacar saldo” e
  “Saques”).
  - Acima dos campos há uma faixa com o **saldo disponível** para saque: é o
    número que a pessoa precisa ver antes de preencher o formulário.
  - Cada linha do histórico traz o **valor**, a **data** e um **selo de
    situação** com a cor do estado (`pago`, `processando`, `solicitado`,
    `falhou`). O rótulo vem em português; a API devolve o estado cru.
  - No telefone as duas colunas caem uma abaixo da outra e a linha vertical
    vira uma linha horizontal no topo.
- A página pública de `/afiliados` mostra o essencial e entrega o resto no
  **guia completo**: hero (com o texto que explica o programa), `#divisao` (a
  barra e os quatro percentuais) e `#participar` (CTA final com os dois botões).
  A seção curta que resumia o funcionamento (`#porDentro`) foi **substituída**
  pelo bloco `#guiaCompleto`, que é o mesmo que o painel usa.
- **Ritmo vertical único**: o intervalo entre as seções públicas
  (hero → `#divisao` → `#participar` → `#guiaCompleto`) e entre os grupos do
  painel é sempre de **56px** (`--space-8`). Dentro das seções, rótulo → título
  fica em 24px e título → texto em 16px.
- Todo o conteúdo detalhado fica em um bloco **"Guia completo do programa"**
  (`#guiaCompleto`), que fica **na página pública** e **no painel** (na página
  pública, acima do rodapé; no painel, no lugar do papel de quem está logado).
  Ele reúne o projeto por dentro, o passo a passo dos dois programas, a
  divisão completa, o guia de cada papel e a transparência.
- O guia abre com um **sumário** (`.guia-sumario`) de seis botões numerados para
  os seis blocos. Os botões funcionam como **acordeão**: cada clique expande o
  bloco escolhido e recolhe o anterior, de modo que só um bloco fica aberto por
  vez (o primeiro já vem aberto). A lógica está em `setupGuideAccordion()` e
  `openGuideBlock()`, em `assets/creators.js`.
- Dentro do guia, `H3` é o título do bloco e `H4` são as subseções — antes as
  subseções usavam `H3` e quebravam a hierarquia.
- No painel, o bloco do papel atual (`#guiaAfiliado` ou `#guiaCriador`) recebe o
  selo **"Seu papel"** e um convite cruzado para o outro papel. O menu do topo
  troca as âncoras: na página pública aponta para `#divisao`, `#participar` e
  `#guiaCompleto`; no painel, para `#guiaProjeto`, `#guiaPrograma` e
  `#guiaDivisao`.
  - Esse menu **aparece no desktop** (a partir de 721px): era o único jeito de
    chegar no guia, que fica bem abaixo da dobra. Antes ele era escondido por
    uma regra no CSS (`.creators-page .desktop-nav { display: none }`) que
    existia quando a página pública era curta — o `creators.js` já reescrevia
    os links, mas ninguém os via. No telefone (até 720px) a barra do
    `.desktop-nav` continua escondida, como nas outras páginas.
- **No celular o hero decorado some**: `.creators-hero` é `display: none` até
  720px (e em telefone deitado) e no lugar dele entra `.creators-hero-mobile`,
  com o mesmo título e o mesmo texto em versão curta. A seção mobile **não**
  usa `aria-hidden`, senão o leitor de tela não leria o texto que está
  justamente visível no telefone.
- A base de contatos é compartilhada entre afiliados e identifica o criador por
  **como ele é popularmente conhecido**, e não por `@`: o mesmo criador usa
  usernames diferentes em cada rede. O nome digitado é normalizado para um
  identificador estável (`Ana Souza`, `ana souza` e `ANA-SOUZA` viram o mesmo
  registro), o que bloqueia o contato duplicado sem depender de plataforma.
  O `@` do criador é **obrigatório**: ele fica salvo por 6 meses e aparece no
  painel público de dados do site (`/painel`). A plataforma é apenas o contexto
  de onde o contato aconteceu.
- **O contato é só por e-mail, enviado pela VPS.** O afiliado preenche alguns
  dados do criador (como ele é conhecido, e-mail, onde encontrou e o `@`,
  obrigatório) e a VPS monta o convite com o modelo do programa e o link de
  afiliado creditado. O texto do e-mail **não** fica visível nem editável no
  painel — o navegador só manda os dados. O envio é **direto**: não existe
  etapa de verificação no formulário, o botão é só "Enviar e-mail". A proteção
  contra contato duplicado e contra abuso continua no servidor (a base
  rejeita quem já foi contatado). O limite é de **3 e-mails por
  afiliado a cada 3 dias**, contado no servidor; envio que falha não gasta
  cota. Os templates copiáveis de e-mail e DM saíram do painel.
- Os saques de criadores e afiliados exigem chave Pix, **nome e CPF/CNPJ do
  titular da chave** (exigidos pela Efí) e e-mail para o comprovante. O valor é
  sempre o saldo disponível calculado pelo servidor; o cliente não envia valor
  e não existe saque mínimo.
  - O **nome do titular não é campo do formulário**: sai da conta logada
    (`pix_name` do cadastro, com o nome da conta como reserva) e vai no
    corpo do pedido de saque. Quem pede o saque é a própria pessoa da conta,
    então o dado já está no servidor — pedir de novo só dava chance de errar.
    O CPF/CNPJ continua editável, porque pode ser o documento de um
    representante e não o do titular da conta.
- A VPS debita o saldo, envia o Pix pela API da **Efí (Gerencianet)** e mantém o
  saque em `processing` até a liquidação. Um job consulta a Efí a cada 30s;
  quando o Pix é liquidado, o saque vira `paid` e o comprovante é enviado. Se a
  transferência falhar, for devolvida ou recusada, o valor volta ao saldo.
  - **Pendência de credencial:** o `/health` da API mostra
    `payouts: {provider: "efi", configured: false}` — falta o
    `EFI_CLIENT_ID`/`EFI_CLIENT_SECRET` e o certificado `.pfx` da Efí em
    `/etc/vizin/api.env`. Sem isso o valor fica **reservado em `processing`**
    (o saldo já sai da conta), mas o Pix não é enviado. O runbook completo
    está em [`app/docs/deploy-vps.md`](../app/docs/deploy-vps.md).
- Endpoints usados: `POST /creators`, `GET /creators/me`,
  `POST /creators/withdraw`, `POST /hunters`, `GET /hunters/me`,
  `POST /hunters/withdraw`, `GET /hunters/public`,
  `GET /hunters/outreach`, `POST /hunters/outreach/email` (envio do e-mail do
  convite) e `GET /signup-guard` (verificação de IP antes de carregar a página).
  `GET /hunters/outreach/check` continua existindo na API, mas **o site não
  o usa**: o envio é direto e é o próprio `POST /hunters/outreach/email` que
  recusa (409) o contato duplicado.

### Bloqueio por IP (cadastro de parceiros)

O cadastro de criador e de afiliado é protegido por IP, decidido **no servidor**:

- **Datacenter, VPN, proxy ou Tor**: a página **não carrega** e o visitante vai
  direto para a página de erro (`/404.html`, que responde **status HTTP 404
  real** — o Caddy usa `handle_errors` para servir o arquivo com 404). O
  conteúdo nunca chega a aparecer.
- **IP fora do Brasil**: segue a mesma regra de bloqueio e vai para o 404.
- **IP que já criou uma conta**: a página carrega normalmente, mas a criação de
  conta é recusada e aparece um **aviso curto dentro da janela de criação**,
  em uma linha: *"Você já criou uma conta de afiliado."* ou *"Você já criou uma
  conta de criador."* O texto vem do site, pelo papel que já foi usado.
- A regra vale **por papel**: um IP pode ter uma conta de afiliado e uma de
  criador. Quem já criou a de afiliado ainda pode criar a de criador (e vice-
  versa); o aviso só aparece no papel que o endereço já ocupou.
- **Quem já tem painel não é bloqueado**: um link com `?p=` (link curto atual),
  `?afiliado_token=` ou `?token=` abre o painel normalmente, mesmo de VPN ou
  datacenter. O bloqueio vale para a criação de contas.

Como funciona:

- A API extrai o IP real (`CF-Connecting-IP` → `X-Real-IP` → último item do
  `X-Forwarded-For` → IP do socket). O Caddy, que fica na frente, já anexa o IP
  do cliente no `X-Forwarded-For`.
- A classificação usa a **ipquery.io** (camada gratuita, HTTPS) com fallback
  para a **ipwho.is**: ela informa `is_datacenter`, `is_vpn`, `is_proxy`,
  `is_tor` e o país. O resultado fica em cache no KV por **24 horas**.
- Se a consulta externa falhar, **ninguém é bloqueado** (a página abre e o
  cadastro é aceito). A indisponibilidade do serviço externo não derruba o
  programa.
- O IP usado na criação fica gravado na tabela `signup_ips` da VPS.
- No navegador, `assets/creators.js` chama `GET /signup-guard` antes de
  mostrar a página. Um script no `<head>` esconde o conteúdo enquanto a
  verificação não termina, com um fallback de 6 segundos para a página nunca
  ficar em branco se a API estiver fora do ar.
- O backend é a autoridade: `POST /creators` e `POST /hunters` respondem `403`
  com `code: IP_DENIED` ou `code: IP_BLOCKED_DUPLICATE` se alguém contornar
  o navegador.
- Runbook completo no projeto principal:
  [`app/docs/guarda-ip.md`](../app/docs/guarda-ip.md).

### Envio de e-mail pelo afiliado (no ar)

O fluxo de contato do afiliado é **só por e-mail**, com o envio feito pela VPS
(SMTP do Gmail com senha de app ou API HTTPS). O afiliado preenche os dados do
criador e a VPS monta e dispara o e-mail — o texto enviado **não fica visível
nem é editável pelo afiliado**.

Regras:

- **3 e-mails por afiliado a cada 3 dias**, contados no servidor (rolante).
  Envio que falha não gasta cota.
- Um e-mail por criador: o registro entra na base compartilhada e bloqueia o
  contato duplicado, como hoje. A base tem uma regra de identidade só — o nome
  popular normalizado.
- O modelo de e-mail é montado no servidor com o link de afiliado já embutido;
  o afiliado só personaliza os dados do criador.

Estado e pendências (detalhes e diagnóstico de rede em
[`app/docs/email-afiliados.md`](../app/docs/email-afiliados.md)):

- O fluxo completo já foi **testado de ponta a ponta num navegador real**
  contra o site publicado: os 3 envios da janela, o `429` no 4º, o `409` de
  criador repetido (por outro afiliado, sem gastar cota) e a prova de que o
  texto do e-mail não existe no DOM nem no JS servido.
- A VPS atual **não consegue sair por SMTP**: as portas 465 e 587 dão timeout
  em todos os provedores testados (Gmail, Outlook, AWS SES, Brevo, Resend).
  O bloqueio é da rede do datacenter, não do `ufw` — abrir as regras de saída
  não resolveu. O transporte ativo é, portanto, o **HTTPS** (`MAIL_TRANSPORT=api`),
  que funciona na porta 443.
- Falta a **chave do provedor** (`MAIL_API_KEY` em `/etc/vizin/mail.env`) para
  o envio real sair. O SMTP do Gmail fica pronto para ser ligado trocando
  `MAIL_TRANSPORT=smtp` e a senha de app, assim que a rede liberar as portas.
  **Como ativar:** com a chave do Resend em mãos, basta escrever
  `MAIL_API_KEY=re_...` em `/etc/vizin/mail.env` (permissão `600`), reiniciar
  a API (`systemctl restart vizin-api`) e conferir
  `curl -s https://api.188.166.156.109.sslip.io/health` — o bloco `mail`
  precisa mostrar `"configured": true`. Sem isso, a API responde
  “provedor de e-mail não configurado no servidor” e nenhum e-mail sai.
  O caminho completo (formulário → API → e-mail montado na VPS) já está
  verificado: `tools/testar-envio-real.sh` sobe um servidor SMTP de captura na
  VPS, aponta a API para ele e mostra as mensagens recebidas.
- **SMTP do Gmail:** `tools/ativar-gmail-smtp.py` liga o transporte
  (`MAIL_TRANSPORT=smtp`, `smtp.gmail.com:465`) com a senha de app, que entra
  pelo **stdin** — a senha nunca passa por argv de processo nem pelo
  repositório. Conferido na VPS em 11/11/2026: a senha fica aplicada e o
  `/health` mostra `"transport": "smtp", "configured": true`, **mas a saída
  SMTP continua bloqueada** (465/587/25 com timeout, handshake de verdade
  com o Gmail dá timeout): nenhum e-mail sai enquanto a rede do datacenter não
  liberar. Para desfazer, `tools/restaurar-mail-api.py` volta ao HTTPS (api).
  Atenção: `tools/testar-envio-real.sh` termina restaurando `api` — rodar o
  ciclo de captura desfaz esta configuração.

#### O gateway de e-mail no PC (o caminho que funciona hoje)

A VPS não sai por SMTP, mas sai por HTTPS na 443. E o transporte `api` da
API é exatamente um `POST` no formato do Resend. A solução é fazer o **PC
falar com o Gmail** e a VPS falar com o PC:

```
VPS (MAIL_TRANSPORT=api)  ──POST /emails──▶  gateway no PC  ──SMTP 465──▶  Gmail
   127.0.0.1:8789            (túnel SSH reverso)   127.0.0.1:8789
```

O túnel é um `ssh -R` aberto pelo próprio script: nada é exposto na
internet, o gateway escuta só em `127.0.0.1` e o túnel também. **Não é
preciso mudar a API, nem fazer deploy, nem criar fila** — a VPS continua
falando o mesmo protocolo de sempre.

Para usar (no PC do dono, com a internet da VPS):

```sh
tools/rodar-gateway-email.sh
```

O script:

1. lê (ou cria na primeira vez) `site/.deploy-gmail.env` — arquivo `600`,
   **ignorado pelo git**, com `GMAIL_USER`, `GMAIL_PASS` e `GATEWAY_TOKEN`.
   Na primeira execução ele pergunta a conta e a senha de app (a senha
   aparece mascarada e vai para o arquivo, nunca para o git);
2. sobe `tools/gateway-email-local.py` em `127.0.0.1:8789` (log em
   `/tmp/vizin-gateway.log`);
3. aponta a VPS para ele (`tools/apontar-gateway-local.py` grava
   `MAIL_TRANSPORT=api`, `MAIL_API_URL=http://127.0.0.1:8789/emails` e
   `MAIL_API_KEY=<token>` em `/etc/vizin/mail.env`, permissão `600`) e
   reinicia a `vizin-api`;
4. segura o túnel em primeiro plano. **Enquanto o comando estiver rodando, a
   VPS envia e-mail pelo PC.** Ao sair (Ctrl+C), o gateway fecha.

O token entra pelo **stdin** (nunca por argv, que fica visível em `ps`) e o
gateway só aceita pedido com o `Bearer` correto.

Enquanto o PC estiver desligado (ou o túnel cair), a VPS não consegue
entregar: a API devolve erro de conexão, **a cota não é consumida** e o
afiliado pode tentar de novo. É o mesmo comportamento de "envio que falha
não gasta cota".

Para desfazer o apontamento e voltar ao provedor HTTPS de verdade
(Resend/Brevo), na VPS: `python3 tools/restaurar-mail-api.py` e
`systemctl restart vizin-api`.

> Atenção: `tools/testar-envio-real.sh` termina restaurando `MAIL_TRANSPORT=api`
> com a URL do Resend — rodar o ciclo de captura **desfaz** o apontamento para
> o gateway e é preciso rodar `tools/rodar-gateway-email.sh` de novo.

**Conferido em 12/11/2026:** com o gateway no ar, os 3 e-mails da janela
saíram de verdade (chegando na caixa `vizin.oos@gmail.com`), o `429` do 4º
envio e o `409` de criador repetido funcionaram, e o texto do e-mail continua
inexistente no DOM e no JS servido. O `tests/test-envio-email-real.py` roda
esse caminho inteiro contra o site publicado (46/46 verificações).

Com o envio real (alguns segundos por e-mail, porque o Gmail entrega em
~3 s), o formulário do afiliado não pode perder o que o afiliado já
escreveu: `assets/creators.js` limpa **só** os campos que continuam com o
valor que foi enviado, e o botão fica **desabilitado** durante o envio (um
clique no meio do envio seria engolido em silêncio).

#### Ligar o gateway sozinho, a cada boot do PC

O `tools/rodar-gateway-email.sh` também roda **sozinho quando o PC liga**, sem
ninguém precisar logar e abrir terminal. A unidade do systemd que faz isso é
versionada em `tools/systemd/vizin-gateway-email.service` e precisa ser
instalada **uma vez** na máquina:

```sh
mkdir -p ~/.config/systemd/user
cp tools/systemd/vizin-gateway-email.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now vizin-gateway-email.service
loginctl enable-linger user     # sobe no boot mesmo sem ninguem logar
```

O que a unidade garante:

- **1 minuto de atraso** no começo (`Environment=ATRASO_INICIAL=60`), para não
  competir com o boot do sistema e com a rede ainda subindo;
- **consumo mínimo**: `Nice=10`, `CPUQuota=25%`, `CPUWeight=10`,
  `MemoryMax=512M` — o gateway ocioso usa ~16 MB de RAM;
- **trava anti-duplicata** por `flock` (o script nunca abre dois gateways nem
  dois túneis);
- **sobrevive a queda**: `Restart=on-failure` com `RestartSec=60` e o próprio
  script tenta reabrir o túnel SSH por ~5 min se a VPS ainda não responder;
- **log com teto de 1 MB** (`/tmp/vizin-gateway.log`), para o `/tmp` não encher.

Para ver o que está acontecendo:

```sh
systemctl --user status vizin-gateway-email.service
journalctl --user -u vizin-gateway-email.service -n 40
```

Para desligar o autostart: `systemctl --user disable --now vizin-gateway-email.service`.

> O `ExecStart` da unidade aponta para o caminho absoluto deste repositório
> (`/home/user/Downloads/site/tools/rodar-gateway-email.sh`). Se o repositório
> for movido, ajuste o `ExecStart` antes de religar a unidade.

### Decoração do link do painel

O link que aparece no modal de confirmação usa o **mesmo
gradiente** do `<span class="gradient-text">`, com o **corpo menor** para caber
no modal. A regra está em `assets/styles.css`:

```css
.panel-link a {
  background: linear-gradient(90deg, var(--primary), var(--accent));
  background-size: 200% auto;
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
  font-family: var(--font-gradient);
  font-size: 0.86rem;   /* menor que o texto ao redor */
  font-weight: 700;
}
```

Verificado no navegador: `background-clip: text`, `color: transparent` e
`font-size: 13.77px` (o parágrafo ao redor fica maior).

## Navegação entre páginas

Todas as páginas se conectam de forma consistente:

- **Breadcrumb** ("Início / …") no topo de cada página interna;
- **Menu desktop** inclui o link "Painel" além das seções da home;
- **Menu mobile** traz um grupo "Saiba mais" com as demais páginas;
- **Rodapé "Continue explorando"** (`.footer-explore` + `.explore-grid`) em todas
  as páginas, com um cartão por página — o cartão da página atual leva
  `aria-current="page"`;
- A **404** também lista as páginas principais.
- **Breadcrumb onde ajuda a orientar**: a página de afiliados (`/afiliados`) e a
  404 abrem com um `nav.breadcrumb` que mostra o caminho como um diretório de
  arquivos simplificado ("Início / página atual"), com separador e
  `aria-current="page"`. A regra vive no `styles.css` global. No `/afiliados`,
  o hero do desktop e o hero do celular têm cada um a sua cópia — o do desktop
  fica dentro do cartão decorado e o do celular aparece junto do texto, porque
  o hero decorado some no telefone. Nas demais páginas a navegação do próprio
  cabeçalho já resolve o caminho, e o breadcrumb foi retirado para não repetir
  a informação.
- Os componentes (`.explore-*`, `.breadcrumb`, `.mobile-nav-group`) vivem no
  `styles.css` global.

## Painel público (/painel)

A página `/painel` exibe estatísticas agregadas do serviço, buscadas de
`GET /stats/public` na API (implementado em `app/vps/src/stats.ts` +
`Store.publicStats()`), com atualização automática a cada 60 segundos:

- **Atividade**: **dispositivos online agora** (sinal de vida nos últimos
  10 min) e contas ativas em janelas de 1 h, 24 h, 7 e 30 dias;
- **Cobertura**: quantidade de beacons e regiões distintas (código geohash dos
  beacons, que já são públicos via `/beacons`);
- **Servidor**: tempo no ar do serviço, data em que o serviço começou, memória
  (RSS + fatia do heap), CPU, tamanho do banco, versão do runtime e latência
  medida no próprio navegador;
- **Comunidade**: total de contas, usernames reservados, contas apagadas
  (tombstones), backups de cofre, contas criadas nas últimas 24 h e 7 dias e as
  datas da primeira e da mais recente conta;
- **Parceiros**: contagens de criadores, afiliados, contatos, indicações,
  comissões e saques pagos, e as etiquetas dos criadores já contatados.

### De onde vem cada número (100% real)

| Número | Origem | Observação |
| --- | --- | --- |
| Dispositivos online agora | `accounts.online_now` | contas com heartbeat nos últimos `online_window_seconds` (10 min = 2× o intervalo de 5 min do app) |
| Janela usada | `accounts.online_window_seconds` | a API publica a janela que ela aplicou; o painel nunca promete outro prazo |
| Ativos 1 h / 24 h / 7 d / 30 d | `accounts.active_*` | contagem por `last_seen` |
| Servidor no ar há | `server.uptime_seconds` | **do serviço**, não do processo: o instante de início fica no banco (`meta:server_started_at`) e sobrevive a restart e deploy |
| Serviço no ar desde | `server.service_started_at` | data real do início do serviço |
| CPU | `server.cpu_percent` | diferença entre duas leituras de `process.cpuUsage()`: uso da janela recente, não média desde o boot |
| Contas, novas 24 h / 7 d | `accounts.total`, `new_24h`, `new_7d` | contagens diretas do banco |
| Primeira / mais recente conta | `accounts.oldest_created_at`, `newest_created_at` | datas reais de criação |
| Proporções | contagens sobre `accounts.total` | a legenda mostra o denominador real ("7 de 10 contas") |

O número de dispositivos online **sobe e desce com o uso real do app**: o app
manda heartbeat assinado a cada 5 min enquanto está aberto, a API grava
`last_seen` e o contador público conta essa conta na janela de 10 min. Quando
ninguém está com o app aberto, o número é **0** — não é um número inventado.

### Como os números aparecem

A página é uma **grade bento**: blocos com o mesmo arcabouço (borda, raio,
fundo) e conteúdos diferentes, para não ser uma parede de cartões iguais.
Em 6 colunas no desktop, 2 no tablet e 1 no celular:

| Bloco | Visual | Dado |
| --- | --- | --- |
| Dispositivos online agora | número em destaque + ponto pulsando | `online_now` (com a janela em `online_window_seconds`) |
| Ativos por período | 4 barras finas (1 h, 24 h, 7 dias, 30 dias) | `active_1h`, `active_24h`, `active_7d`, `active_30d` |
| Ativos em 7 dias | anel SVG | `active_7d` sobre `accounts.total` |
| Regiões / Beacons | número | `network.regions`, `network.beacons` |
| Servidor no ar há / Serviço no ar desde | número / data | `uptime_seconds`, `service_started_at` |
| Memória em uso | número + medidor | `memory_rss_bytes` e a fatia do `memory_heap_used_bytes` |
| Latência da API | número + sparkline | tempo de resposta medido no navegador a cada atualização |
| CPU / Banco / Runtime | número (+ medidor na CPU) | `cpu_percent`, `database_size_bytes`, `runtime` |
| Contas / Conta mais recente / Primeira conta / Apagadas | número / data | `total`, `newest_created_at`, `oldest_created_at`, `deleted_total` |
| Novas contas em 24 h / 7 dias | número | `new_24h`, `new_7d` |
| Usernames / Backups de cofre | número + medidor | `with_username` e `vaults.backups` sobre o total de contas |
| Criadores / Afiliados / Contatados / Indicações / Comissões / Saques | número | `partners.*` |
| Saques por tipo | barra empilhada | `payouts_paid` vs `payouts_hunter_paid` |
| Indicações ativas | medidor | `referrals_active` sobre `referrals_total` |

Os gráficos são SVG/CSS puros (nenhuma biblioteca), o texto é curto e o
histórico de latência fica só no `localStorage` do visitante.

O endpoint só devolve **números agregados** — nunca chaves, usernames, IPs,
localização de pessoas, conteúdo ou valores individuais. Aqui, "região" tem um
significado próprio: é a **região do beacon/servidor** (o código geohash dele),
não a região do app. No app, a localização de cada pessoa é o seu **bairro**
(município) e ela cai numa região que se nomeia pela lista de bairros — mas nada
disso é exposto aqui.

A única informação não numérica é o **@ (e o link público) do criador já
contatado** — que é público por natureza e some sozinho após 6 meses.

O contrato completo, as garantias de privacidade e o runbook de publicação
estão em [`app/docs/painel-publico.md`](../app/docs/painel-publico.md).

### Dois modos de coleta

A página é minimalista de propósito: rótulo, número e o visual do bloco —
sem legendas, sem etiquetas de resumo e sem texto sobre o que o painel não
mostra. Os dois modos diferem apenas nos números que aparecem:

| Modo | Quando | O que aparece |
| --- | --- | --- |
| **dados completos** | a VPS já responde `GET /stats/public` | tudo que está listado acima |
| **dados públicos** | a VPS ainda não tem a rota | beacons, regiões e latência medida no navegador |

No modo público a página só usa rotas que **já são públicas** na API
(`/health` e `/beacons`) e **nunca estima**: campo que a API não informa fica
com "—", e os medidores zeram.

O modo público continua funcionando quando a API inteira está fora do ar —
nesse caso, aparece o aviso de erro ("Não foi possível obter os dados do
servidor agora. Tentamos de novo automaticamente.") e nenhum número é
inventado.

## Analytics de visitação (site)

O `/painel` mede o **app** (contas, beacons, servidor). Para medir o **site**
— visitantes e page views das páginas públicas — o `<head>` das 7 páginas
(`index`, `documento`, `afiliados`, `moderacao`, `manifesto`, `painel`, `404`)
leva o snippet do Vercel Web Analytics:

```html
<script>
  window.va = window.va || function () { (window.vaq = window.vaq || []).push(arguments) };
</script>
<script defer src="/_vercel/insights/script.js"></script>
```

### Onde o site é servido

O script vive na rota `/_vercel/insights/script.js`, que **só existe quando o
site é servido pela Vercel**. Nos outros lugares (VPS, InfinityFree) o script
não é encontrado e **nenhum dado é coletado** (a página continua funcionando
normalmente — o `<script defer>` apenas falha em silêncio).

**Hoje o site está na Vercel em `https://vizin-os.vercel.app`, e o Web Analytics
já está ligado** — a rota `/_vercel/insights/script.js` responde 200 e o
`/_vercel/insights/view` aceita eventos.

A publicação é automática: o projeto da Vercel está conectado ao repositório
`dietmilkk/vizin-Os-Website`, então **cada push na `main` vira um deploy**. O
site é 100% estático — não há build, npm ou framework.

Para publicar o conteúdo que está no ar (a cópia da VPS) na Vercel:

```bash
# 1) monta a pasta: site publicado + snippet do Analytics + .vercelignore
python3 tools/montar-publicacao-vercel.py /caminho/site-publicado /tmp/deploy-vercel

# 2) cria o commit sem tocar no working tree (usa um índice temporário do Git)
python3 tools/commitar-publicacao-vercel.py /tmp/deploy-vercel "site: publica na Vercel"

# 3) envia para a main — a Vercel publica sozinha
git push origin <commit>:main
```

Confira depois do deploy:

```bash
python3 tools/check-analytics-vercel.py https://vizin-os.vercel.app
```

Ele abre um navegador de verdade e confirma que o script do Analytics é
requisitado em todas as páginas. (O script ignora navegadores automatizados,
então o evento do teste não entra na contagem — o que importa é o script
carregar e a rota responder.)

Se o Analytics não registrar nada: no painel da Vercel, projeto → **Analytics**
deve estar **Enable**; e vale checar bloqueador de conteúdo (adblock) na sua
máquina.

### Se o site continuar no InfinityFree

Se mudar de hospedagem não estiver nos planos, o Vercel Analytics não
serve: a alternativa é um contador que funciona em qualquer hospedagem, com
uma única linha de `<script>` no mesmo lugar — **Cloudflare Web Analytics**
(só com a conta Cloudflare), **GoatCounter** (código aberto) ou **Plausible**.
Nesse caso, troque o snippet das 7 páginas pelo do provedor escolhido.

> O snapshot publicado em `dist/` (`.zip` do InfinityFree) continua levando o
> snippet: lá ele não faz nada, e na Vercel passa a coletar sozinho.

## Segurança do repositório (segredos fora do Git)

Duas camadas independentes, porque o `.gitignore` sozinho não basta:

**1. `.gitignore` — nada de credencial entra no repositório**

O `.gitignore` bloqueia, entre outras coisas:

- qualquer arquivo de ambiente (`*.env`, `*.env.*`), com exceção só do
  `.env.example` (que existe para ser versionado);
- chaves e certificados (`*.pem`, `*.key`, `*.p12`, `*.pfx`, `*.jks`, `*.asc`,
  `*.gpg`, `*.ppk`, `*.kdbx`, `*.crt`, `*.cer`, `*.der`, `*.p7b`);
- chaves SSH (`id_ed25519*`, `id_rsa*`, `*.identity`) — a pública `.pub`
  continua versionada;
- credenciais de serviço (`credentials*.json`, `*credencial*.json`,
  `service-account*.json`, `*.tfvars`, `*.tfstate`, `config.tfstate*`);
- sessões e cookies de navegador (`storage_state*.json`, `cookies*.json`,
  `auth.json`, `*.har`);
- arquivos locais de deploy (`.deploy-*`, `deploy/*secret*`) e o estado do
  gateway (`*.lock`, `*.pid`, `vizin-gateway-email.*`).

**2. `tools/checar-segredos.py` — pegou o que o `.gitignore` não pega**

O `.gitignore` impede que o arquivo entre; ele **não** impede que a senha seja
colada *dentro* de um arquivo normal (um `.js`, um `.py`, um `.html`). Esse
script varre o que seria versionado e procura:

| Padrão | Exemplo |
| --- | --- |
| chave privada PEM | `-----BEGIN RSA PRIVATE KEY-----` |
| senha de app do Gmail | `abce efgh ijkl mnop` |
| token do GitHub | `ghp_…`, `gho_…` |
| token do Slack | `xoxb-…` |
| chave da AWS | `AKIA…` |
| chave da OpenAI | `sk-…` |
| token da Vercel | `aaa.bbb.ccc` (JWT) |
| senha/token literal | `GMAIL_PASS="…"`, `GMAIL_PASS=…` |
| `Authorization` fixo | `Authorization: Bearer …` |

Ele sabe distinguir segredo de placeholder: `example`, `xxx`, `seu_token`,
`changeme`, `${VAR}`, e-mails, IPs, URLs, caminhos e chamadas de função são
ignorados — e a regra genérica não se aplica em `tests/`, onde os tokens são
de mentira por definição.

```bash
python3 tools/checar-segredos.py             # tudo que é versionado
python3 tools/checar-segredos.py --staged    # só o que entraria no commit
python3 tools/checar-segredos.py --arquivo X # um arquivo específico
```

Sai com código **1** quando acha algo (e 0 quando está limpo).

**3. O hook que bloqueia o commit**

`tools/hooks/pre-commit` roda o scanner no modo `--staged` antes de cada
commit e **impede o commit** se algo for encontrado. Para ativar nesta
máquina:

```sh
git config core.hooksPath tools/hooks
```

O hook está versionado, então o resto do time só precisa desse comando (ou
clonar o repositório já com `core.hooksPath` configurado).

> O hook é uma rede de segurança, não um cofre: ele **bloqueia** o commit, mas
> não apaga um segredo que já tenha sido commitado antes. Se isso acontecer, a
> correção é **girar (rotacionar) o segredo** — apagar do histórico não
> desfaz a exposição.

> ⚠️ A senha de app do Gmail já passou em texto plano no chat desta conversa.
> Trate-a como exposta e **gere outra** na conta Google antes de usar em
> produção (Configurações da conta Google → Segurança → Verificação em duas
> etapas → Senhas de app).

## Testes

```bash
python3 tools/check-site.py
node --test tests/pix.test.js
```

### Painel público: API e página, de verdade

Os dois testes abaixo sobem a **VPS real** (Bun) em uma porta livre, com um
banco SQLite temporário e um cenário de dados determinístico
(`tests/lib/seed_stats.py`). Nada toca a produção.

```bash
# contrato do endpoint + checagem ativa de privacidade
python3 tests/test-stats-publico.py

# roda o assets/panel.js de verdade contra a API de verdade
node --test tests/painel.test.mjs
```

O `test-stats-publico.py` popula o banco com segredos marcados (pubkey,
username, chave PIX, e-mail, IP e conteúdo de cofre) e garante que **nenhum**
deles aparece na resposta — a privacidade é testada, não só documentada.

O `painel.test.mjs` executa o JavaScript real da página contra um DOM mínimo e
confere que cada número exibido bate com o JSON da API, que nenhuma etiqueta
fica com o placeholder "—", que **não existe botão manual** (a página se
atualiza sozinha), que a página **avisa e se recupera quando a API está fora do
ar** e que a atualização automática de 60 s está agendada.

Além disso, ele simula a API de produção **sem** a rota `/stats/public` e
confere o modo público: os beacons públicos são contados, o status passa a
"Atualizado agora" e **nenhum campo do servidor é inventado**.

### Todos os links, como um usuário

O `check-links.py` começa em `/`, segue todos os links e recursos internos e
**abre cada um no Chromium** — o navegador é usado de verdade porque a
hospedagem pública coloca uma verificação de JavaScript antes de mostrar a
página (um `curl` puro veria só a tela de verificação). Os redirecionamentos
são conferidos **no servidor**, não simulados no script, e páginas que não
existem têm de mostrar a página de erro:

```bash
python3 tools/check-links.py https://vizin-os.page.gd
```

Ele só verifica o que é servido por nós: URLs externas (Play Store, Instagram)
ficam de fora.

### Links do painel público

O `test-links-painel.py` abre o `/painel` no Chromium e confere **todos os
links clicáveis** da página (beacons, regiões, contatos, saques, etc.) contra
a API real. Ele valida que cada `href` responde 200/301/302 e que nenhum
link interno quebra:

```bash
python3 tests/test-links-painel.py
```

### No navegador de verdade

Dois testes abrem o Chromium e conferem o que uma pessoa vê — inclusive em
tela de celular:

```bash
python3 -m http.server 8099 &          # sobe o site
python3 tests/test-painel-publico.py http://127.0.0.1:8099   # o que aparece na tela
python3 tests/test-layout-painel.py   http://127.0.0.1:8099   # mede o layout
```

O `test-painel-publico.py` confere cada número visível, as etiquetas de região
e de criador contatado, a barra de estado, os links do painel e a
ausência de rolagem horizontal no celular. O `test-layout-painel.py` mede a
geometria: cartões do mesmo tamanho dentro de cada linha, colunas
consistentes, tipografia com hierarquia clara, foco visível no teclado e
nada invadindo a tela em 1280, 820 e 390 px.

Para olhar com os próprios olhos:

```bash
python3 tests/capturar-painel.py http://127.0.0.1:8099 /tmp/painel
```

### Celular em todas as páginas

A auditoria mobile abre **todas** as páginas do site em 390 px e 320 px e mede
o que atrapalha no telefone: rolagem horizontal, elemento fora da tela, texto
pequeno demais para ler e área tocável apertada.

```bash
python3 -m http.server 8099 &                 # sobe o site
python3 tests/auditoria-mobile.py http://127.0.0.1:8099
```

Link de dentro do texto não conta como área tocável apertada: ele vive na
linha do parágrafo e não pode virar bloco sem quebrar o texto. Os demais
elementos (botões, campos, links soltos) precisam de pelo menos 32 px de
altura.

**No telefone nada de conteúdo some.** A regra "ar leve" (≤ 760 px) corta
apenas o texto de apoio — dicas, legendas de card, rótulos descritivos — e
nunca esconde bloco de conteúdo, botão ou link. A página de afiliados
continua mostrando a divisão da receita, o "como funciona por dentro" e o
bloco de participação (com os botões) nos 390 px e 320 px. O que muda no
telefone é o *hero*: o cartão decorado some e fica só o texto
(`.creators-hero-mobile`), sem perder o breadcrumb.

### Guia em acordeão e rodapé minimalista

```bash
python3 tests/test-guia-acordeao.py http://127.0.0.1:8099
```

Confere que o guia "Como funciona por dentro" abre **um bloco por vez** (cada
botão expande o seu e recolhe o anterior, com apenas um marcado como
aberto), que o primeiro bloco já vem aberto, que os blocos do rodapé "Continue
explorando" mostram **ícone e título lado a lado** e que a página não gera
erro de JavaScript.

### Breadcrumb onde existe

```bash
python3 tests/test-breadcrumb.py http://127.0.0.1:8099
```

Abre as seis páginas do site e confere que, onde há breadcrumb, ele é único,
começa em "Início", termina na página atual, tem separador e
`aria-current="page"`, e que o link do início aponta para a raiz. Também
confirma que ele continua visível **no celular**. Páginas sem breadcrumb
(`/`, `/painel`, `/documento`, `/moderacao`) passam sem aviso: o caminho já
está no cabeçalho.

### Header com a mesma largura em todas as páginas

```bash
python3 tests/medir-header.py http://127.0.0.1:8099
python3 tests/alinhamento-paginas.py http://127.0.0.1:8099
```

O site inteiro usa **uma grade só**: `--max: 1120px`. O header e o rodapé
declaram esse valor na própria regra (`.site-header` e `.site-footer`), então
nenhuma página consegue esticá-los por acidente — foi o que fazia o
`/documento` abrir com o header largo demais antes.

O `medir-header.py` mede a largura real do container do header nas seis
páginas, no desktop e no celular, e exige que sejam iguais. O
`alinhamento-paginas.py` confere a outra ponta: o conteúdo de cada página
precisa alinhar com as margens do header. Bloco centralizado e mais estreito
que a grade (o hero da home, por exemplo) é aceito — é simetria editorial, não
quebra de alinhamento.

### O que está publicado no domínio oficial

```bash
python3 tests/conferir-oficial.py https://vizin-os.page.gd
```

Confere, no domínio que as pessoas visitam, o texto do hero, a divisão da
receita, os textos da janela de criação, o acordeão do guia, a linha vertical
do histórico de saques e a ausência de "Observações" e de `eyebrow`.

### Contra a API que está no ar

O `test-painel-producao.py` é o teste "como um usuário usaria": ele sobe o
site, abre `/painel` no Chromium e deixa a página falar com a **API pública de
verdade**. Ele confere que há números na tela (CPU, memória e contas), que a
barra de status é curta, que não há erro de console e que o celular não
rola de lado:

```bash
python3 tests/test-painel-producao.py
python3 tests/test-painel-producao.py https://vizin-os.page.gd
```

### O publicado bate com o repositorio?

Duas ferramentas comparam o que está no ar com o que está no repositorio — o
caminho mais curto para descobrir que um deploy ficou para trás:

```bash
# todas as paginas e assets, linha a linha, contra o arquivo local
python3 tools/comparar-site-publicado.py https://vizin-os.page.gd

# so o painel: confere se todos os blocos e ids do HTML local estao no ar
python3 tools/comparar-painel-publicado.py https://vizin-os.page.gd
```

A leitura é feita **dentro do Chromium**, com os cookies da verificação de
JavaScript do page.gd, e a comparação ignora apenas espaços a direita e quebras
de linha no fim do arquivo. Serve para as duas cópias do site:

```bash
python3 tools/comparar-site-publicado.py https://vizin-os.page.gd
python3 tools/comparar-site-publicado.py https://site.188.166.156.109.sslip.io
```

### Medir o painel sem depender de olho

`tools/auditar-painel-visual.py` imprime a geometria de cada bloco (posição e
tamanho), o preenchimento das barras, o arco do anel e a sparkline, em desktop e
celular — e salva as capturas em PNG. `tools/checar-painel-publicado.py` confere
os detalhes do painel já publicado (cores, alturas, etiquetas e links internos):

```bash
python3 tools/auditar-painel-visual.py https://vizin-os.page.gd /tmp/auditoria
python3 tools/checar-painel-publicado.py https://vizin-os.page.gd
```

### Prévia local do painel (sem deploy)

O `tools/prever-painel.sh` sobe uma **API local de verdade** (com o banco de
teste populado) e serve uma **cópia** do site em `/tmp`, com o `config.js`
apontado para ela. O repositório não é alterado:

```bash
tools/prever-painel.sh
# abra http://127.0.0.1:8099/painel
```

Os testes do painel de afiliado rodam contra a API real e criam um afiliado de
teste descartável. Requer o servidor local e o Playwright:

```bash
cd site && python3 -m http.server 8099
python3 tests/test-painel-afiliado.py
python3 tests/test-layout-afiliado.py
python3 tests/test-guard-ip.py
```

O `test-guard-ip.py` confere o bloqueio por IP no navegador: IP de
datacenter/VPN/fora do Brasil vai para o 404, IP duplicado mostra o aviso na
janela de criação, painel com token nunca é bloqueado e API fora do ar não
trava a página. Ele simula a resposta da API, então não depende do IP real da
máquina.

### Jornada real, contra a produção

O `test-usuario-real.py` percorre o caminho inteiro **como um visitante**,
num navegador limpo (sem cache nem cookies): abre a página pública, abre a
janela de criação, **clica no botão** para criar a conta, confere a
confirmação, entra no painel pelo “Abrir painel”, confere o link de
afiliado, recarrega a página pelo link do painel, tenta criar uma segunda
conta (que deve ser recusada com o aviso pequeno na janela) e por fim simula
um IP de datacenter para conferir o 404 com **status 404 real**.

```bash
python3 tests/test-usuario-real.py
```

> **Depois deste teste, limpe os dados.** A conta criada registra o IP da
> máquina em `signup_ips`, e sem a limpeza a próxima execução é recusada pelo
> próprio bloqueio de IP duplicado:
>
> ```bash
> tools/limpar-teste.sh --ip 45.4.58.93 --aplicar
> ```
>
> O `tools/limpar-teste.sh` apaga as contas de teste (criador e afiliado),
> referências, contatos, saques e as linhas de `signup_ips` e
> `signup_ip_kinds` dessas contas — liberando o IP. **Nunca** toca em
> `accounts`, `vaults` nem `kv`. Sem `--aplicar` ele só simula e imprime o
> que seria apagado.
>
> O `--ip` é o caminho mais seguro: os códigos das contas são **aleatórios**
> (a plataforma os gera no navegador), então o prefixo de teste nem sempre
> identifica a conta que o teste criou — mas o endereço de rede sim, já que a
> guarda permite uma conta por papel e IP. Sem `--ip`, a limpeza usa só o
> prefixo (`TEST`, `TST`, `AU`, `USRREAL`…). Ajuste a conexão com
> `SSH_CONFIG` (padrão `/tmp/opencode/ssh_config`) e `HOST` (padrão
> `vizin-vps`); sem o `ssh_config`, o script usa a chave do app em
> `app/.local/vps/id_ed25519`.

No backend, os testes da guarda de IP rodam com `bun`:

```bash
cd app/vps && bun test tests/ip-guard.test.ts
```

### Envio de e-mail de verdade (contra a produção)

O `test-envio-email-real.py` é o teste que responde "**está funcionando de
verdade?**": ele abre o **site publicado** num navegador, entra no painel do
afiliado pelo link, preenche o formulário de contato e clica em **Enviar
e-mail** — o e-mail é montado e despachado pela VPS em produção.

O texto do e-mail é montado no servidor, então o teste também confirma que
**nenhuma frase do modelo** aparece no HTML nem no `assets/creators.js`
servido, e que os campos de template (`emailTemplate`, `dmTemplate`,
`copyEmailTemplate`, `copyDmTemplate`) não existem.

```bash
python3 tests/test-envio-email-real.py
```

O ciclo completo (limpar → subir o servidor SMTP de captura → apontar a API
para ele → rodar o teste → mostrar as mensagens → restaurar o transporte de
produção) roda com **um comando**:

```bash
SSH_CONFIG=/tmp/opencode/ssh_config HOST=vizin-vps tools/testar-envio-real.sh
```

> O script **sobe e derruba** o servidor SMTP de captura e **restaura** o
> `MAIL_TRANSPORT=api` no final. Se for interrompido no meio, a API fica
> apontada para o servidor local — sem efeito colateral, ele só escuta em
> `127.0.0.1`. Para desfazer na mão:
> `python3 tools/restaurar-mail-api.py` na VPS + `systemctl restart vizin-api`.

O que ele cobre:

| Passo | Resultado esperado |
| --- | --- |
| Abre o painel pelo link real | os dados do afiliado vêm da API |
| Envia 3 e-mails | sucesso na tela, contador `1/3` → `3/3`, contato em "Contatos recentes" |
| 4º envio | barrado com o aviso de cota (`429`) |
| Outro afiliado, mesmo criador | aviso de "já foi contatado" (`409`), **sem** gastar cota |
| Inspeção do DOM e do JS | o modelo do e-mail **não** chega ao navegador |
| Recarrega a página | a cota e o contato continuam lá |

> O e-mail em si é entregue pelo transporte de produção. Duas opções:
>
> - **Gateway no PC (entrega real):** com `tools/rodar-gateway-email.sh` rodando
>   no PC, a API aponta para o gateway local e os e-mails **saem de verdade**
>   pelo Gmail. Foi assim que o teste passou com 46/46 verificações em
>   12/11/2026.
> - **Servidor SMTP de captura (sem internet):** durante o ciclo de
>   `tools/testar-envio-real.sh`, a API aponta para um **servidor SMTP local na
>   própria VPS** (`app/vps/tools/smtp-sink.ts`), que fala o mesmo protocolo do
>   Gmail (`STARTTLS` + `AUTH PLAIN` depois do handshake) e grava a mensagem
>   recebida em disco. O procedimento completo está em
>   [`app/docs/email-afiliados.md`](../app/docs/email-afiliados.md#62-teste-real-de-ponta-a-ponta-navegador--vps--smtp).

### Jornada do cadastro e do link do painel

O `test-jornada-afiliado.py` percorre a jornada do visitante contra o site
publicado: página pública → "Quero ser afiliado" → cria a conta (o código é
gerado no navegador) → confere o **link do painel no modal** (inclusive a
decoração em gradiente com o corpo menor) → "Abrir painel" → confere o
link de afiliado no painel.

```bash
python3 tests/test-jornada-afiliado.py
```

> A conta criada por esse teste registra o IP da máquina em `signup_ips`. Ele
> é removido no final (a conta libera o IP), mas se a execução for
> interrompida, use o `tools/limpar-teste.sh --aplicar` descrito acima.

## Deploy

O site é 100% estático e hoje está publicado em **https://vizin-os.page.gd**.

Esse endereço é um subdomínio gratuito do **page.gd**, que é a hospedagem
**InfinityFree** (o domínio `page.gd` é servido por eles). Ou seja: o domínio
oficial do site fica dentro da conta InfinityFree e **não** aponta para um IP
externo — não é possível apontá-lo para a VPS. A VPS (188.166.156.109) continua
sendo a **cópia de trabalho**, a casa da **API** e a referência de deploy.

Onde cada coisa vive:

| Onde | Endereço | Para quê |
| --- | --- | --- |
| Site oficial | `https://vizin-os.page.gd` | páginas públicas (InfinityFree) |
| Cópia de trabalho | `https://site.188.166.156.109.sslip.io` | mesma cópia na VPS, para conferir e diagnosticar |
| API | `https://api.188.166.156.109.sslip.io` | API do serviço (painel, health, beacons) |

> O `page.gd` pede uma verificação de JavaScript antes de mostrar a página.
> Isso é normal para quem abre o site no navegador; ferramentas de linha de
> comando (`curl`) veem apenas a tela de verificação. Por isso os testes de
> produção usam Chromium de verdade (`tools/conferir-dominio.py`).

### Publicar no domínio oficial (InfinityFree)

Dois caminhos, ambos a partir de `site/`:

**1. FTP (automático)** — precisa das credenciais da conta InfinityFree:

```bash
# credenciais ficam em site/.deploy-infinityfree.env (está no .gitignore)
cat > .deploy-infinityfree.env <<'EOF'
INFINITYFREE_FTP_HOST=ftpupload.net
INFINITYFREE_FTP_USER=SEU_USUARIO
INFINITYFREE_FTP_PASS=SUA_SENHA
INFINITYFREE_FTP_DIR=vizin-os.page.gd/htdocs
EOF

tools/deploy-infinityfree.sh --dry-run   # mostra o que seria enviado
tools/deploy-infinityfree.sh             # publica e confere
```

O `tools/deploy-infinityfree.py` (o `.sh` é um atalho para ele) faz um
**espelho**: sobe os 28 arquivos públicos (páginas, `assets/`, `robots.txt`,
`sitemap.xml`, `.htaccess`) e **apaga do servidor** tudo que não faz parte do
site — `README.md`, `prompt-afiliados.md`, `tools/`, `tests/`, `tmp-vps/`,
`deploy/`, `dist/` e qualquer sobra de publicações antigas. No fim ele chama o
`conferir-dominio.py` e só termina com sucesso se o site estiver no ar, sem
vazamento e com o painel pulling números da API.

> A pasta remota é `vizin-os.page.gd/htdocs`. A pasta `htdocs` na raiz da conta
> é **outro site** (`vizin.page.gd`) e não é tocada por este deploy.

**2. Painel do InfinityFree (manual)** — para quem prefere o navegador:

```bash
tools/pacote-infinityfree.sh   # gera dist/vizin-os-page-gd.zip
```

Depois, em <https://client.infinityfree.com>: **File Manager →
`vizin-os.page.gd` → `htdocs` → Upload →** envie o `.zip` e extraia. **Apague**
da pasta `htdocs` o que não deve ficar no ar: `README.md`, `prompt-afiliados.md`
e as pastas `tools/`, `tests/` e `tmp-vps/` (se existirem de publicações
antigas).

### Recuperar a senha do FTP (quando ela mudar)

O painel do InfinityFree mostra a senha de FTP em **FTP Details**
(`dash.infinityfree.com/accounts/<conta>/ftp-details`). O
`tools/recuperar-ftp-infinityfree.py` entra no painel reaproveitando a sessão
do Google que já está no navegador do dono da conta e grava as credenciais em
`site/.deploy-infinityfree.env` (permissão `600`, fora do git):

```bash
python3 tools/recuperar-ftp-infinityfree.py
```

Ele só funciona se o Firefox (ou o navegador indicado em `--perfil`) já estiver
logado na conta do InfinityFree. Nenhuma senha é impressa no terminal.

### Publicar na cópia de trabalho (VPS)

O deploy para a VPS é feito por `rsync` para `/var/www/vizinhanca.app/`,
servido pelo Caddy. O nome da pasta é histórico (`vizinhanca.app` era um
domínio que nunca existiu); **só a URL pública mudou** — a pasta continua
assim para não quebrar o caminho já configurado.

O `tools/deploy-vps.sh` faz a publicação inteira (API + site) em um passo, com
backup do banco antes de qualquer mudança e verificação no final:

```bash
tools/deploy-vps.sh               # acha a chave sozinha
tools/deploy-vps.sh --so-backend   # só a API
tools/deploy-vps.sh --so-site      # só o site
SSH_KEY=/caminho/da/chave tools/deploy-vps.sh   # chave em outro lugar
```

> **A chave SSH é obrigatória.** O deploy usa `rsync` + `ssh`; a VPS não tem
> credencial de `git pull`. O script procura a chave em
> `app/.local/vps/id_ed25519` (fora do versionamento), em
> `/tmp/opencode/id_deploy_new` e em `~/.ssh/id_ed25519` — ou use `SSH_KEY=`.

O script também apaga da pasta pública o que não deve estar no ar
(`README.md`, `prompt-afiliados.md`, `tools/`, `tests/`, `dist/`) e o Caddy
responde **404** para esses caminhos, mesmo que alguém peça por eles.

### Publicar nos dois destinos de uma vez (o jeito usado na prática)

O site oficial (InfinityFree) e a cópia na VPS recebem **o mesmo conteúdo**.
Depois de mexer em qualquer página ou em `assets/`, publique nos dois, sempre a
partir de `site/`:

```bash
bash tools/deploy-vps.sh --so-site      # copia de trabalho (VPS) — só o site
python3 tools/deploy-infinityfree.py    # domínio oficial (InfinityFree)
```

- `tools/deploy-vps.sh --so-site` publica **só o site** na VPS (a API não é
  tocada). Sem `--so-site`, ele publica API + site e faz backup do banco.
- `python3 tools/deploy-infinityfree.py` é o mesmo script do
  `tools/deploy-infinityfree.sh` (o `.sh` é só um atalho) e já termina
  conferindo o site no ar.

Depois de publicar, confira como um visitante:

```bash
python3 tools/conferir-dominio.py                                   # domínio oficial
python3 tools/conferir-dominio.py https://site.188.166.156.109.sslip.io   # cópia na VPS
python3 tools/ver-painel-publico.py https://vizin-os.page.gd        # números do painel
```

> **Atenção:** o `page.gd` pede verificação de JavaScript, então `curl` não
> serve para conferir o domínio oficial — use os scripts acima, que abrem um
> Chromium de verdade.

### Publicar na Vercel (o destino que conta visitação)

O projeto na Vercel está ligado ao repositório `dietmilkk/vizin-Os-Website`:
**cada push na `main` publica o site** em `https://vizin-os.vercel.app`. O
site é estático, então não há build — o que está na `main` é o que vai ao ar.

O `.vercelignore` do repositório mantém `tools/`, `tests/`, `README.md` e
arquivos de configuração fora do ar (a Vercel serve a pasta do repositório
inteira, então sem isso esses caminhos responderiam 200).

Fluxo que preserva o conteúdo já publicado e adiciona o snippet do Analytics
**sem tocar no working tree** (importante quando há trabalho em andamento):

```bash
python3 tools/montar-publicacao-vercel.py /caminho/site-publicado /tmp/deploy-vercel
python3 tools/commitar-publicacao-vercel.py /tmp/deploy-vercel "site: publica na Vercel"
git push origin <commit>:main
```

Depois do push, confira:

```bash
python3 tools/check-analytics-vercel.py https://vizin-os.vercel.app
```

> O `page.gd` (InfinityFree) hoje **aceita TLS mas não responde ao HTTP** — o
> domínio oficial está travado na hospedagem. A Vercel responde normalmente e é
> lá que o Analytics coleta.

### Conferir o site como um usuário

```bash
python3 tools/conferir-dominio.py                                   # domínio oficial
python3 tools/conferir-dominio.py https://site.188.166.156.109.sslip.io   # cópia na VPS
```

Abre as cinco páginas no Chromium e confere:

- cada página abre com 200, tem título e **não deixa erro de JavaScript**;
- o `canonical` aponta para o domínio certo — e as páginas `noindex` (como
  `/afiliados`) se declaram assim, sem canonical conflitante;
- o painel público sai do carregamento e **mostra números da API**;
- todo link interno responde;
- os apelidos antigos (`/criadores` → `/afiliados/`) ainda levam ao lugar certo;
- `robots.txt` e `sitemap.xml` falam do domínio certo;
- **nenhum arquivo interno está exposto** (`README.md`, `prompt-afiliados.md`,
  `tools/`, `tests/`, `deploy/`, `dist/`, `.git/`, `.env`, `.htaccess`).

São 48 verificações no domínio oficial e no mirror da VPS.

O `tools/check-links.py` faz o outro lado do mesmo teste: rastreia o site
inteiro como um visitante (abrindo cada link no Chromium), confere que as
páginas inexistentes mostram a página de erro e que todo recurso interno
(carregado em páginas) responde.

### Publicar pelo GitHub Actions (sem o computador local)

O repositório tem o workflow `.github/workflows/deploy-site.yml`: ele publica
o site na VPS direto do GitHub, com a chave do host fixada em
`deploy/known_hosts`. Para usar, crie **uma vez** o segredo `VPS_SSH_KEY`
(Settings → Secrets and variables → Actions → New repository secret) com a
chave privada da VPS e rode o workflow pela aba **Actions**.

O mesmo existe para a API, no repositório `vizin-Os`
(`.github/workflows/deploy-vps.yml`). Detalhes em
[`app/docs/painel-publico.md`](../app/docs/painel-publico.md#publicar).

> **Ordem de publicação:** o site pode ir no ar antes da VPS. A página `/painel`
> continua funcionando no **modo público** (status da API, latência, versão,
> módulos, política de conta e registro de beacons) enquanto a rota
> `/stats/public` não existir, avisando na tela que o detalhamento completo
> ainda não foi publicado. Para o painel mostrar CPU, memória, contas e
> parceiros, **a VPS precisa ser redeployada** — ver
> [`app/docs/painel-publico.md`](../app/docs/painel-publico.md#publicar).

## Acessibilidade e desempenho

- Navegação por teclado, `skip-link`, foco visível e `aria-*`.
- `prefers-reduced-motion` desliga animações.
- Sem bibliotecas de terceiros no runtime.
- Sem rastreadores e sem cookies.
- Layout mobile-first, com bastante espaçamento e tipografia legível.
