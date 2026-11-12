(function () {
  'use strict';

  var config = window.VIZINHANCA_CONFIG || {};
  var API = (config.apiUrl || 'https://api.188.166.156.109.sslip.io').replace(/\/+$/, '');
  var params = new URLSearchParams(window.location.search);
  var AFILIADO_KEY = 'vizin.os.afiliado.v1';
  var AFILIADO_KEY_LEGACY = 'vizin-os.afiliado.v1';
  var AFILIADO_WINDOW_MS = 180 * 24 * 60 * 60 * 1000;
  var CODE_RE = /^[A-Z0-9_-]{3,32}$/;
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  document.documentElement.classList.add('js');

  var creatorToken = params.get('token') || '';
  var afiliadoToken = params.get('afiliado_token') || '';
  if (!afiliadoToken && params.get('tipo') === 'afiliado') {
    afiliadoToken = params.get('token') || '';
  }
  /* Link curto do painel: ?p=<token>. O prefixo do token indica o papel
     (C = criador, A = afiliado), entao um unico parametro abre o painel certo.
     Tokens antigos (?token= / ?afiliado_token=) continuam funcionando. */
  var panelToken = params.get('p') || '';
  if (panelToken) {
    if (panelToken.charAt(0) === 'A') {
      afiliadoToken = panelToken;
    } else if (panelToken.charAt(0) === 'C') {
      creatorToken = panelToken;
    }
    /* Sem prefixo (token de uma VPS antiga): o papel e descoberto na API. */
  }
  if (afiliadoToken) creatorToken = '';

  var currentMode = 'creator';
  var currentCode = '';
  /* Resultado da verificacao de IP (datacenter/VPN/duplicidade/fora do pais).
     `taken` diz, por papel, se este endereco ja criou conta: quem tem
     conta de afiliado ainda pode criar a de criador, e vice-versa. */
  var signupGuard = {
    allowed: true,
    blocked: false,
    reason: '',
    taken: { creator: false, hunter: false },
  };
  var guardSettled = false;
  var afiliadoCode = '';
  var afiliadoHandle = '';
  // Nome do titular da chave Pix de cada papel. Vem da conta (cadastro) e nao
  // de um campo no formulario: quem pede o saque e a propria pessoa da conta.
  var pixNomeTitular = { creator: '', afiliado: '' };
  // O @ da conta aberta agora. Quem ja tem uma conta usa o mesmo @ ao criar
  // a outra: a pessoa continua sendo a mesma, com os dois papeis.
  var handleAtual = '';
  var afiliadoLink = '';
  var afiliadoAttributionName = '';
  var attributionCode = '';
  var storedAttribution = readAttribution();

  function $(id) {
    return document.getElementById(id);
  }

  function show(id) {
    var el = $(id);
    if (el) el.classList.remove('hidden');
  }

  function hide(id) {
    var el = $(id);
    if (el) el.classList.add('hidden');
  }

  /* ------------------------------------------------- guia completo (rodapé)

     O mesmo guia aparece na página pública e no painel. Na página pública ele
     abre na primeira aba ("O projeto"); no painel ele assume o bloco do papel
     de quem está logado, com o convite para o outro papel. */

  var GUIDE_NAV = [
    ['O projeto', 'guiaProjeto'],
    ['Como funciona', 'guiaPrograma'],
    ['Divisão', 'guiaDivisao'],
  ];

  var PUBLIC_NAV = [
    ['A divisão', 'divisao'],
    ['Participar', 'participar'],
    ['O guia', 'guiaCompleto'],
  ];

  function setNavLinks(links) {
    var nav = document.querySelector('.partners-nav');
    if (!nav) return;
    var anchors = nav.querySelectorAll('a');
    links.forEach(function (item, index) {
      var anchor = anchors[index];
      if (!anchor) return;
      anchor.textContent = item[0];
      anchor.setAttribute('href', '#' + item[1]);
    });
  }

  /* O guia completo funciona como um acordeao: cada botao de "Neste guia"
     abre um unico bloco de conteudo. O bloco do papel atual ja nasce aberto. */
  function openGuideBlock(id) {
    var guide = $('guiaCompleto');
    if (!guide || !id) return;
    var buttons = guide.querySelectorAll('[data-guide-target]');
    Array.prototype.forEach.call(buttons, function (button) {
      var active = button.getAttribute('data-guide-target') === id;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-expanded', active ? 'true' : 'false');
    });
    var blocks = guide.querySelectorAll('.guia-bloco');
    Array.prototype.forEach.call(blocks, function (block) {
      var active = block.id === id;
      block.hidden = !active;
      block.classList.toggle('is-open', active);
      block.classList.add('is-visible');
    });
  }

  function showGuide(role) {
    var guide = $('guiaCompleto');
    if (!guide) return;
    guide.classList.remove('hidden');
    setNavLinks(GUIDE_NAV);

    var target = role === 'afiliado' ? 'guiaAfiliado' : 'guiaCriador';
    var blocks = guide.querySelectorAll('.guia-bloco');
    Array.prototype.forEach.call(blocks, function (block) {
      block.classList.toggle('is-current', block.id === target);
    });
    openGuideBlock(target);

    var cross = guide.querySelectorAll('[data-guide-cta]');
    Array.prototype.forEach.call(cross, function (item) {
      var visible = item.getAttribute('data-guide-cta') === role;
      item.classList.toggle('hidden', !visible);
    });
  }

  function setupGuideAccordion() {
    var guide = $('guiaCompleto');
    if (!guide) return;
    var buttons = guide.querySelectorAll('[data-guide-target]');
    Array.prototype.forEach.call(buttons, function (button) {
      button.addEventListener('click', function () {
        openGuideBlock(button.getAttribute('data-guide-target'));
      });
    });
    var first = buttons.length ? buttons[0].getAttribute('data-guide-target') : '';
    if (first) openGuideBlock(first);
  }

  /* A página pública mantém o guia visível: ele só volta ao estado inicial
     (primeira aba aberta, sem convite de papel) e aponta o menu para a
     página pública. */
  function resetGuide() {
    setNavLinks(PUBLIC_NAV);
    var guide = $('guiaCompleto');
    if (!guide) return;
    var cross = guide.querySelectorAll('[data-guide-cta]');
    Array.prototype.forEach.call(cross, function (item) {
      item.classList.add('hidden');
    });
    var blocks = guide.querySelectorAll('.guia-bloco');
    Array.prototype.forEach.call(blocks, function (block) {
      block.classList.remove('is-current');
    });
    openGuideBlock('guiaProjeto');
  }

  function brl(cents) {
    return (Number(cents || 0) / 100).toLocaleString('pt-BR', {
      style: 'currency',
      currency: 'BRL',
    });
  }

  function formatDate(seconds) {
    if (!seconds) return '—';
    return new Date(Number(seconds) * 1000).toLocaleDateString('pt-BR');
  }

  function formatDateTime(seconds) {
    if (!seconds) return '—';
    return new Date(Number(seconds) * 1000).toLocaleString('pt-BR');
  }

  function platformLabel(value) {
    var labels = {
      instagram: 'Instagram',
      tiktok: 'TikTok',
      youtube: 'YouTube',
      twitch: 'Twitch',
      x: 'X / Twitter',
      outro: 'Outro lugar',
    };
    return labels[value] || 'Outro lugar';
  }

  /* Identidade de um criador na base compartilhada de contatos.

     A mesma pessoa pode ter @ diferentes em cada rede, entao a base nao usa
     o @ como identidade: usa "como o criador e conhecido". O texto digitado
     vira um identificador estavel (slug), de modo que "Ana Souza",
     "ana souza" e "ANA-SOUZA" apontam para o mesmo registro. */
  function creatorSlug(value) {
    return String(value || '')
      .trim()
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 60);
  }

  function creatorDisplayName(value) {
    return String(value || '').trim().replace(/\s+/g, ' ');
  }

  function api(path, options) {
    return fetch(API + path, {
      headers: { 'content-type': 'application/json', accept: 'application/json' },
      ...(options || {}),
    }).then(function (response) {
      return response.json().catch(function () { return {}; }).then(function (data) {
        if (!response.ok) {
          var error = new Error(data.error || 'http_' + response.status);
          error.status = response.status;
          error.data = data;
          throw error;
        }
        return data;
      });
    });
  }

  function withLoading(button, task) {
    if (!button) return task();
    button.classList.add('is-loading');
    button.setAttribute('aria-busy', 'true');
    // O botao fica realmente desabilitado durante a operacao: so o
    // `pointer-events: none` do CSS nao impede o clique, e um clique no
    // meio do envio seria engolido em silencio (o afiliado acharia que
    // mandou o e-mail e nao mandou).
    var estavaDesabilitado = button.disabled;
    button.disabled = true;
    return task().finally(function () {
      button.classList.remove('is-loading');
      button.removeAttribute('aria-busy');
      button.disabled = estavaDesabilitado;
    });
  }

  function copy(text, button) {
    function done() {
      if (!button) return;
      var original = button.textContent;
      button.textContent = 'Copiado!';
      window.setTimeout(function () {
        button.textContent = original;
      }, 1600);
    }
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(done).catch(function () {});
      return;
    }
    var area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    try {
      document.execCommand('copy');
      done();
    } catch (error) {
      // Clipboard unavailable.
    }
    document.body.removeChild(area);
  }

  function row(left, right, badge) {
    var div = document.createElement('div');
    div.className = 'list-row';
    var l = document.createElement('span');
    l.textContent = left;
    var r = document.createElement('span');
    r.textContent = right;
    if (badge) {
      r.className = 'badge';
      r.textContent = badge;
    }
    div.appendChild(l);
    div.appendChild(r);
    return div;
  }

  /* Situacao de um saque: a API devolve o estado cru (requested, processing,
     paid...). Aqui ele vira um rotulo em portugues com a cor do estado. */
  var WITHDRAW_STATUS = {
    requested: { label: 'Solicitado', cls: 'requested' },
    processing: { label: 'Processando', cls: 'processing' },
    paid: { label: 'Pago', cls: 'paid' },
    failed: { label: 'Falhou', cls: 'failed' },
    rejected: { label: 'Recusado', cls: 'failed' },
  };

  function withdrawStatus(status) {
    return WITHDRAW_STATUS[status] || { label: status || '—', cls: 'requested' };
  }

  /* Linha do historico de saques: valor, data e selo de situacao. */
  function withdrawalRow(w) {
    var div = document.createElement('div');
    div.className = 'withdraw-row';

    var amount = document.createElement('span');
    amount.className = 'withdraw-row__amount';
    amount.textContent = brl(w.amount_cents);

    var date = document.createElement('span');
    date.className = 'withdraw-row__date';
    date.textContent = formatDate(w.created_at);

    var status = document.createElement('span');
    status.className = 'withdraw-row__status';
    var info = withdrawStatus(w.status);
    var tag = document.createElement('span');
    tag.className = 'withdraw-status withdraw-status--' + info.cls;
    tag.textContent = info.label;
    status.appendChild(tag);

    div.appendChild(amount);
    div.appendChild(date);
    div.appendChild(status);
    return div;
  }

  function renderList(container, items, emptyText, formatter) {
    if (!container) return;
    container.textContent = '';
    if (!items || items.length === 0) {
      var p = document.createElement('p');
      p.className = 'muted';
      p.textContent = emptyText;
      container.appendChild(p);
      return;
    }
    items.forEach(function (item) {
      container.appendChild(formatter(item));
    });
  }

  /* Linha de contato do afiliado: nome popular, onde foi encontrado,
     data do contato e selo de status. */
  function contactRow(prospect) {
    var div = document.createElement('div');
    div.className = 'list-row contact-row';

    var main = document.createElement('div');
    main.className = 'contact-row__main';
    var name = document.createElement('span');
    name.className = 'contact-row__name';
    name.textContent = prospect.name || prospect.handle;
    var meta = document.createElement('span');
    meta.className = 'contact-row__meta';
    var handle = prospect.contact_url || (prospect.handle ? '@' + prospect.handle : '');
    var bits = [];
    if (handle) bits.push(handle);
    bits.push(platformLabel(prospect.platform));
    meta.textContent = bits.join(' · ');
    main.appendChild(name);
    main.appendChild(meta);

    var side = document.createElement('div');
    side.className = 'contact-row__side';
    var when = document.createElement('span');
    when.className = 'contact-row__date';
    when.textContent = formatDate(prospect.contacted_at);
    var badge = document.createElement('span');
    badge.className = 'badge';
    badge.textContent = 'contatado';
    side.appendChild(when);
    side.appendChild(badge);

    div.appendChild(main);
    div.appendChild(side);
    return div;
  }

  /* -------------------------------------------------------- attribution */

  function readAttribution() {
    try {
      var raw = window.localStorage.getItem(AFILIADO_KEY);
      if (!raw) {
        // Chave antiga: migra a atribuicao existente para a chave atual.
        raw = window.localStorage.getItem(AFILIADO_KEY_LEGACY);
        if (raw) {
          window.localStorage.setItem(AFILIADO_KEY, raw);
          window.localStorage.removeItem(AFILIADO_KEY_LEGACY);
        }
      }
      if (!raw) return null;
      var data = JSON.parse(raw);
      var code = String(data.code || '').toUpperCase();
      var at = Number(data.at || 0);
      if (!CODE_RE.test(code)) return null;
      if (!at || Date.now() - at > AFILIADO_WINDOW_MS) {
        window.localStorage.removeItem(AFILIADO_KEY);
        window.localStorage.removeItem(AFILIADO_KEY_LEGACY);
        return null;
      }
      return { code: code, at: at };
    } catch (error) {
      return null;
    }
  }

  function rememberAttribution(code) {
    var normalized = String(code || '').trim().toUpperCase();
    if (!CODE_RE.test(normalized)) return null;
    var existing = readAttribution();
    // First touch wins: a creator already linked to a afiliado cannot be
    // claimed by a second link in the same browser.
    if (existing && existing.code !== normalized) return existing;
    if (existing && existing.code === normalized) return existing;
    var data = { code: normalized, at: Date.now() };
    try {
      window.localStorage.setItem(AFILIADO_KEY, JSON.stringify(data));
    } catch (error) {
      // Storage may be blocked; keep the value for this page load.
    }
    return data;
  }

  function readAfiliadoFromUrl() {
    var value =
      params.get('a') ||
      params.get('afiliado') ||
      params.get('afiliado_code') ||
      params.get('ref') ||
      '';
    value = value.trim().toUpperCase();
    return CODE_RE.test(value) ? value : '';
  }

  var urlAfiliado = readAfiliadoFromUrl();
  if (urlAfiliado) {
    storedAttribution = rememberAttribution(urlAfiliado) || storedAttribution;
  }
  attributionCode = storedAttribution ? storedAttribution.code : '';

  function attributionMessage() {
    if (!attributionCode) return '';
    var who = afiliadoAttributionName
      ? 'o afiliado ' + afiliadoAttributionName
      : 'um afiliado parceiro';
    return (
      'Você chegou por indicação de ' + who + ' (código ' + attributionCode + '). ' +
      'Se você criar seu código neste navegador, ele receberá os créditos da parceria.'
    );
  }

  function updateAttributionUI() {
    if (!attributionCode) return;
    var banner = $('afiliadoBanner');
    if (banner && !creatorToken && !afiliadoToken) {
      banner.textContent = attributionMessage();
      banner.classList.remove('hidden');
    }
    if (currentMode === 'creator') {
      var box = $('afiliadoAttribution');
      if (box) {
        box.textContent = attributionMessage();
        box.classList.remove('hidden');
      }
    }
  }

  function loadAttributionName() {
    if (!attributionCode) return;
    api('/hunters/public?code=' + encodeURIComponent(attributionCode))
      .then(function (data) {
        // A API responde "hunter"; o nome antigo era "afiliado".
        var entity = data && (data.hunter || data.afiliado);
        if (entity) {
          afiliadoAttributionName = '@' + entity.handle;
          updateAttributionUI();
        }
      })
      .catch(function () {
        // The code may be old or the API may be offline; the raw code still works.
      });
  }

  /* ------------------------------------------------------ guarda de IP

     Antes de mostrar a pagina, consultamos a API sobre o IP do visitante.
     - datacenter, VPN, proxy, Tor ou fora do Brasil: a pagina nao carrega
       e o visitante vai para a pagina de erro 404;
     - IP que ja criou conta: a pagina abre normalmente e o aviso aparece
       na hora de tentar criar a conta. */

  var NOT_FOUND_URL = '/404.html';

  function releaseGuard() {
    guardSettled = true;
    document.documentElement.classList.remove('is-guarding');
  }

  function goToNotFound() {
    guardSettled = true;
    window.location.replace(NOT_FOUND_URL);
  }

  function runSignupGuard() {
    // Quem ja tem painel nao passa pelo bloqueio: pode acessar de qualquer rede.
    if (creatorToken || afiliadoToken) {
      releaseGuard();
      return;
    }
    var done = false;
    var fallback = window.setTimeout(function () {
      // A API demorou: liberamos a pagina para nao travar o acesso.
      if (done) return;
      done = true;
      releaseGuard();
    }, 5000);
    fetch(API + '/signup-guard', {
      headers: { accept: 'application/json' },
    })
      .then(function (response) {
        return response.json().catch(function () { return {}; });
      })
      .then(function (data) {
        if (done) return;
        done = true;
        window.clearTimeout(fallback);
        signupGuard = {
          allowed: data.allowed !== false,
          blocked: data.blocked === true,
          reason: data.reason || '',
          taken: normalizeTaken(data),
        };
        if (signupGuard.blocked) {
          goToNotFound();
          return;
        }
        releaseGuard();
      })
      .catch(function () {
        if (done) return;
        done = true;
        window.clearTimeout(fallback);
        // Falha de rede nao bloqueia o visitante.
        releaseGuard();
      });
  }

  /* ------------------------------------------------- aviso dentro da janela

     O aviso de IP duplicado aparece dentro do modal de criacao, no lugar do
     erro generico. E um bloco pequeno, discreto, com o aviso do usuario.

     A regra e por papel: um mesmo IP pode ter uma conta de criador e uma de
     afiliado. O aviso so aparece no papel que este endereco ja ocupou. */

  /* Normaliza o mapa de papeis ja usados por este endereco. Uma resposta
     sem `taken` (API anterior) vale como aviso geral para os dois papeis. */
  function normalizeTaken(data) {
    var source = data && data.taken;
    if (source && typeof source === 'object') {
      var one = function (key) {
        var info = source[key] || {};
        return info.taken === true;
      };
      return { creator: one('creator'), hunter: one('hunter') };
    }
    var duplicate = Boolean(data && data.reason === 'IP_BLOCKED_DUPLICATE');
    return { creator: duplicate, hunter: duplicate };
  }

  function takenFor(role) {
    var taken = signupGuard.taken || {};
    return role === 'afiliado' ? taken.hunter === true : taken.creator === true;
  }

  /* O aviso e curto e direto: o bloco ja avisa que e um aviso, e o papel
     basta para a pessoa entender o que ja aconteceu. */
  function avisoDeDuplicidade(isAfiliado) {
    // A guarda é por papel: quem ja tem uma conta ainda pode criar a outra.
    return isAfiliado
      ? 'Você já criou uma conta de afiliado neste endereço. A conta de criador ainda está disponível.'
      : 'Você já criou uma conta de criador neste endereço. A conta de afiliado ainda está disponível.';
  }

  function clearGuardWarning() {
    var box = $('createWarning');
    if (!box) return;
    box.textContent = '';
    box.classList.add('hidden');
  }

  function showGuardWarning(message) {
    var box = $('createWarning');
    if (!box) return;
    box.textContent = message;
    box.classList.remove('hidden');
  }

  /* ------------------------------------------------------------- modal */

  var modal = $('createModal');

  function openModal(mode) {
    currentMode = mode === 'afiliado' ? 'afiliado' : 'creator';
    var isAfiliado = currentMode === 'afiliado';
    $('createTitle').textContent = 'Criar conta';
    $('createIntro').textContent = isAfiliado ? 'Geramos seu código.' : 'Defina seu código.';
    $('createButton').textContent = 'Criar';
    $('codeStatus').textContent = '';
    $('codeStatus').className = 'code-status';
    $('createError').textContent = '';
    clearGuardWarning();
    // O aviso so aparece no papel que este endereco ja ocupou: quem ja tem
    // conta de afiliado ainda pode criar a de criador.
    if (takenFor(isAfiliado ? 'afiliado' : 'creator')) {
      showGuardWarning(avisoDeDuplicidade(isAfiliado));
    }
    var codeInput = $('code');
    if (codeInput) {
      if (isAfiliado) codeInput.classList.add('hidden');
      else codeInput.classList.remove('hidden');
    }
    $('code').value = '';
    hide('createdView');
    show('createView');
    if (isAfiliado) hide('afiliadoAttribution');
    else updateAttributionUI();
    if (!modal) return;
    modal.hidden = false;
    document.body.style.overflow = 'hidden';
    var input = $('code');
    if (input) window.setTimeout(function () { input.focus(); }, 60);
  }

  function closeModal() {
    if (!modal) return;
    modal.hidden = true;
    document.body.style.overflow = '';
  }

  function deriveHandle(code, forceSuffix) {
    var base = code.toLowerCase().replace(/[^a-z0-9_]/g, '');
    if (base.length < 3) base = 'parceiro_' + base;
    base = base.slice(0, 20);
    if (!forceSuffix) return base;
    // Collisions can happen when two codes only differ by punctuation
    // (ANA-10 and ANA10 both become "ana10"). Retry with a random suffix.
    return (base.slice(0, 14) + '_' + Math.random().toString(36).slice(2, 8)).slice(0, 20);
  }

  function generateAffiliateCode() {
    // O afiliado não escolhe o código: ele é gerado aqui no navegador (6
    // caracteres) e a VPS apenas valida se está livre antes de gravar a conta.
    var chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    var out = '';
    for (var i = 0; i < 6; i++) {
      out += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return out;
  }

  function showCreated(data, isAfiliado) {
    var entity = isAfiliado ? (data.afiliado || data.hunter) : data.creator;
    currentCode = entity.code;
    handleAtual = entity.handle;
    if (isAfiliado) {
      afiliadoCode = entity.code;
      afiliadoHandle = entity.handle;
      afiliadoToken = data.token;
      creatorToken = '';
    } else {
      creatorToken = data.token;
      afiliadoToken = '';
    }
    var dashboardPath = '/afiliados?p=' + encodeURIComponent(data.token);
    var link = window.location.origin + dashboardPath;
    $('dashboardLink').href = link;
    $('dashboardLink').textContent = link;
    $('createdTitle').textContent = 'Pronto 🎉';
    $('createdIntro').textContent = 'Guarde o link, ele é a sua senha.';
    hide('createView');
    show('createdView');
    window.history.replaceState(null, '', dashboardPath);
  }

  function createAccount(code, isAfiliado, handle, allowRetry) {
    var body = { handle: handle, code: code };
    if (!isAfiliado && attributionCode) body.afiliado_code = attributionCode;
    return api(isAfiliado ? '/hunters' : '/creators', {
      method: 'POST',
      body: JSON.stringify(body),
    })
      .then(function (data) {
        showCreated(data, isAfiliado);
      })
      .catch(function (error) {
        var message = String(error.message || error);
        if (allowRetry && error.status === 409 && /handle/i.test(message)) {
          return createAccount(code, isAfiliado, deriveHandle(code, true), false);
        }
        throw error;
      });
  }

  $('createForm').addEventListener('submit', function (event) {
    event.preventDefault();
    $('createError').textContent = '';
    $('codeStatus').textContent = '';
    clearGuardWarning();
    var codeInput = $('code');
    var code = codeInput && !codeInput.classList.contains('hidden')
      ? String(codeInput.value || '').trim().toUpperCase()
      : '';
    var isAfiliado = currentMode === 'afiliado';
    // Affiliates never pick a code: one is generated randomly for them.
    if (isAfiliado) {
      code = generateAffiliateCode();
      if (codeInput) codeInput.value = code;
    }
    if (!CODE_RE.test(code)) {
      $('createError').textContent = 'Use de 3 a 32 letras, números, _ ou -.';
      return;
    }

    withLoading($('createButton'), function () {
      // Quem ja tem conta usa o mesmo @ na segunda conta; quem esta criando
      // a primeira recebe um @ derivado do codigo escolhido.
      var handle = handleAtual || deriveHandle(code);
      return createAccount(code, isAfiliado, handle, true).catch(function (error) {
        var code409 = error.status === 409;
        var data = error.data || {};
        // Bloqueio por IP: datacenter, VPN, proxy, Tor ou fora do Brasil.
        if (data.code === 'IP_DENIED') {
          goToNotFound();
          return null;
        }
        // Ja existe uma conta deste papel criada com este endereco de IP.
        if (data.code === 'IP_BLOCKED_DUPLICATE') {
          signupGuard = {
            allowed: false,
            blocked: false,
            reason: 'IP_BLOCKED_DUPLICATE',
            taken: signupGuard.taken,
          };
          signupGuard.taken[isAfiliado ? 'hunter' : 'creator'] = true;
          showGuardWarning(avisoDeDuplicidade(isAfiliado));
          return null;
        }
        if (isAfiliado && code409) {
          var retryCode = generateAffiliateCode();
          if (codeInput) codeInput.value = retryCode;
          return createAccount(retryCode, isAfiliado, deriveHandle(retryCode), true).catch(function (retryError) {
            var retryData = retryError.data || {};
            if (retryData.code === 'IP_BLOCKED_DUPLICATE') {
              signupGuard = {
                allowed: false,
                blocked: false,
                reason: 'IP_BLOCKED_DUPLICATE',
                taken: signupGuard.taken,
              };
              signupGuard.taken[isAfiliado ? 'hunter' : 'creator'] = true;
              showGuardWarning(avisoDeDuplicidade(isAfiliado));
              return null;
            }
            if (retryData.code === 'IP_DENIED') {
              goToNotFound();
              return null;
            }
            $('createError').textContent = String(retryError.message || retryError);
            return null;
          });
        }
        $('createError').textContent = String(error.message || error);
        return null;
      });
    });
  });

  $('openDashboard').addEventListener('click', loadDashboard);

  /* -------------------------------------------------------- dashboards */

  function loadDashboard() {
    if (afiliadoToken) return loadAfiliadoDashboard();
    if (creatorToken) return loadCreatorDashboard();
    if (panelToken) return resolvePanelRole();
    show('createView');
    return Promise.resolve();
  }

  /* Token de link curto sem prefixo de papel (gerado por uma VPS antiga):
     tenta o painel do criador e, se o token nao for de criador, o do afiliado. */
  function resolvePanelRole() {
    return api('/creators/me?token=' + encodeURIComponent(panelToken))
      .then(function (data) {
        creatorToken = panelToken;
        return loadCreatorDashboard(data);
      })
      .catch(function (error) {
        if (error.status !== 401 && error.status !== 403) throw error;
        afiliadoToken = panelToken;
        return loadAfiliadoDashboard();
      });
  }

  function loadCreatorDashboard(preloaded) {
    closeModal();
    hide('partnerMarketing');
    hide('afiliadoDashboardView');
    show('dashboardView');
    hide('createView');
    hide('createdView');
    showGuide('creator');
    var request = preloaded
      ? Promise.resolve(preloaded)
      : api('/creators/me?token=' + encodeURIComponent(creatorToken));
    return request
      .then(function (data) {
        var c = data.creator;
        currentCode = c.code;
        handleAtual = c.handle;
        $('creatorName').textContent = c.name;
        $('creatorHandle').textContent = '@' + c.handle;
        $('creatorCode').textContent = c.code;
        $('creatorError').textContent = '';
        $('statReferrals').textContent = data.referrals;
        $('statCommission').textContent = brl(data.commission_cents);
        $('statAvailable').textContent = brl(data.available_cents);
        $('withdrawAvailable').textContent = brl(data.available_cents);
        $('statPending').textContent = brl(data.pending_cents);
        $('statWithdrawn').textContent = brl(data.withdrawn_cents);
        if ($('withdrawPixCpf') && !$('withdrawPixCpf').value) {
          $('withdrawPixCpf').value = c.pix_cpf_cnpj || '';
        }
        pixNomeTitular.creator = c.pix_name || c.name || '';
        if (data.afiliado) {
          $('creatorAfiliadoNote').textContent =
            'Você foi convidado pelo afiliado @' + data.afiliado.handle + '.';
          show('creatorAfiliadoNote');
        } else {
          hide('creatorAfiliadoNote');
        }

        renderList($('referralList'), data.recent_referrals, 'Nenhuma indicação ainda.', function (r) {
          return row(r.pubkey, formatDate(r.created_at), r.status);
        });
        renderList($('withdrawalList'), data.withdrawals, 'Nenhum saque solicitado.', withdrawalRow);
      })
      .catch(function (error) {
        $('creatorName').textContent = 'Link inválido';
        $('creatorHandle').textContent = 'Confira o link do painel ou gere um novo código.';
        $('creatorCode').textContent = '—';
        $('creatorError').textContent = String(error.message || error);
      });
  }

  function buildAfiliadoLink() {
    if (!afiliadoCode) return '';
    return window.location.origin + '/afiliados?a=' + encodeURIComponent(afiliadoCode);
  }

  /* Cota de e-mail: 3 envios a cada 3 dias, contada no servidor.
     O painel mostra o contador no proprio indicador ("1/3") e a regra fica no
     texto do cartao; a mensagem dinamica entra como title + aria-label, para
     nao inventar um paragrafo a parte que o painel do criador nao tem. */
  function renderEmailQuota(quota) {
    var stat = $('afiliadoStatEmails');
    if (!stat) return;
    var card = $('afiliadoStatEmailsCard');
    var limit = Number((quota && quota.limit) || 3);
    var used = Number((quota && quota.used) || 0);
    var remaining = Number((quota && quota.remaining) || 0);
    stat.textContent = used + '/' + limit;
    var mensagem;
    if (remaining > 0) {
      mensagem =
        'Você pode enviar mais ' +
        remaining +
        (remaining === 1 ? ' e-mail' : ' e-mails') +
        ' nesta janela de 3 dias.';
    } else {
      mensagem =
        'Você usou os ' +
        limit +
        ' e-mails da janela. O próximo envio libera em ' +
        (quota && quota.next_at ? formatDateTime(quota.next_at) : '3 dias') +
        '.';
    }
    if (card) {
      card.setAttribute('title', mensagem);
      card.setAttribute('aria-label', 'E-mails enviados: ' + used + ' de ' + limit + '. ' + mensagem);
    }
  }

  function loadAfiliadoDashboard(preloaded) {
    closeModal();
    hide('partnerMarketing');
    hide('dashboardView');
    show('afiliadoDashboardView');
    hide('createView');
    hide('createdView');
    showGuide('afiliado');
    var view = $('afiliadoDashboardView');
    if (view) view.classList.add('is-loaded');
    var request = preloaded
      ? Promise.resolve(preloaded)
      : api('/hunters/me?token=' + encodeURIComponent(afiliadoToken));
    return request
      .then(function (data) {
        var h = data.afiliado || data.hunter;
        if (!h) throw new Error('resposta invalida da API');
        afiliadoCode = h.code;
        afiliadoHandle = h.handle;
        handleAtual = h.handle;
        currentCode = h.code;
        afiliadoLink = buildAfiliadoLink();
        $('afiliadoName').textContent = h.name;
        $('afiliadoHandle').textContent = '@' + h.handle;
        $('afiliadoError').textContent = '';
        $('afiliadoStatOutreach').textContent = data.outreach_count;
        $('afiliadoStatCreators').textContent = data.recruited_creators;
        $('afiliadoStatReferrals').textContent = data.referrals;
        $('afiliadoStatCommission').textContent = brl(data.commission_cents);
        $('afiliadoStatAvailable').textContent = brl(data.available_cents);
        $('afiliadoWithdrawAvailable').textContent = brl(data.available_cents);
        $('afiliadoStatPending').textContent = brl(data.pending_cents);
        $('afiliadoStatWithdrawn').textContent = brl(data.withdrawn_cents);
        if ($('afiliadoWithdrawPixCpf') && !$('afiliadoWithdrawPixCpf').value) {
          $('afiliadoWithdrawPixCpf').value = h.pix_cpf_cnpj || '';
        }
        pixNomeTitular.afiliado = h.pix_name || h.name || '';
        var linkInput = $('afiliadoLink');
        if (linkInput && !linkInput.value) linkInput.value = afiliadoLink;
        renderEmailQuota(data.email_quota);

        renderList($('outreachList'), data.recent_outreach, 'Nenhum contato registrado ainda.', contactRow);
        renderList($('recruitedList'), data.recent_creators, 'Nenhum criador recrutado ainda.', function (c) {
          return row(
            '@' + c.handle + ' · ' + c.code,
            c.referrals + ' indicação(ões) · ' + brl(c.commission_cents),
            'ativo',
          );
        });
        renderList($('afiliadoWithdrawalList'), data.withdrawals, 'Nenhum saque solicitado.', withdrawalRow);
      })
      .catch(function (error) {
        $('afiliadoName').textContent = 'Link inválido';
        $('afiliadoHandle').textContent = 'Confira o link do painel ou gere um novo código.';
        $('afiliadoError').textContent = String(error.message || error);
      });
  }

  /* ---------------------------------------------------------- withdrawals */

  function requestWithdrawal(kind) {
    var isAfiliado = kind === 'afiliado';
    var pix = $(isAfiliado ? 'afiliadoWithdrawPix' : 'withdrawPix').value.trim();
    /* O nome do titular vem da conta que esta logada (cadastro da VPS), nao de
       um campo no formulario: quem saca e a propria pessoa do cadastro. */
    var pixName = (pixNomeTitular[isAfiliado ? 'afiliado' : 'creator'] || '').trim();
    var pixCpf = $(isAfiliado ? 'afiliadoWithdrawPixCpf' : 'withdrawPixCpf').value.trim();
    var email = $(isAfiliado ? 'afiliadoWithdrawEmail' : 'withdrawEmail').value.trim();
    var errorEl = $(isAfiliado ? 'afiliadoWithdrawError' : 'withdrawError');
    var button = $(isAfiliado ? 'afiliadoWithdrawButton' : 'withdrawButton');
    var documentDigits = pixCpf.replace(/\D/g, '');
    errorEl.textContent = '';
    if (pix.length < 3) {
      errorEl.textContent = 'Informe a chave Pix para receber.';
      return;
    }
    if (pixName.length < 2) {
      errorEl.textContent =
        'Não achamos o nome do titular da chave na sua conta. Atualize seus dados antes de sacar.';
      return;
    }
    if (documentDigits.length !== 11 && documentDigits.length !== 14) {
      errorEl.textContent = 'Informe o CPF ou CNPJ do titular (somente números).';
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      errorEl.textContent = 'Informe um e-mail válido para o comprovante.';
      return;
    }
    withLoading(button, function () {
      return api(isAfiliado ? '/hunters/withdraw' : '/creators/withdraw', {
        method: 'POST',
        body: JSON.stringify({
          token: isAfiliado ? afiliadoToken : creatorToken,
          pix_key: pix,
          pix_name: pixName,
          pix_cpf_cnpj: documentDigits,
          payer_email: email,
        }),
      })
        .then(function () {
          return isAfiliado ? loadAfiliadoDashboard() : loadCreatorDashboard();
        })
        .catch(function (error) {
          errorEl.textContent = String(error.message || error);
        });
    });
  }

  $('withdrawButton').addEventListener('click', function () {
    requestWithdrawal('creator');
  });

  $('afiliadoWithdrawButton').addEventListener('click', function () {
    requestWithdrawal('afiliado');
  });

  /* ------------------------------------------------------- afiliado tools */

  /* O convite vai direto para o e-mail do criador: sem etapa de verificacao.
     O proprio servidor continua impedindo contato repetido e abuso de cota. */

  /* Limpa os campos do convite que continuam com o valor que foi enviado.
     O que o afiliado escreveu depois do clique (o proximo criador) e
     preservado: o envio pode levar alguns segundos e apagar o formulario
     inteiro perderia o trabalho dele. */
  function limpaCamposDoEnvio(campos) {
    if (!campos) return;
    if ($('outreachName').value === campos.nome) $('outreachName').value = '';
    if ($('outreachEmail').value === campos.email) $('outreachEmail').value = '';
    if ($('outreachContact').value === campos.contato) $('outreachContact').value = '';
    if ($('outreachPlatform').value === campos.plataforma) {
      $('outreachPlatform').selectedIndex = 0;
    }
  }

  $('outreachForm').addEventListener('submit', function (event) {
    event.preventDefault();
    $('outreachStatus').textContent = '';
    $('outreachStatus').className = 'code-status';
    $('outreachError').textContent = '';
    var name = creatorDisplayName($('outreachName').value);
    var email = ($('outreachEmail').value || '').trim();
    var contact = ($('outreachContact').value || '').trim();
    // Os valores como estavam no momento do clique: o e-mail pode levar
    // alguns segundos para sair (o servidor entrega por um provedor externo)
    // e o afiliado pode ja ter comecado a escrever o proximo criador nesse
    // intervalo. Guardamos a foto dos campos para nao limpar o que ele
    // escreveu depois do envio.
    var camposNoEnvio = {
      nome: $('outreachName').value,
      email: $('outreachEmail').value,
      plataforma: $('outreachPlatform').value,
      contato: $('outreachContact').value,
    };
    // O texto do e-mail vive no servidor: o afiliado so manda os dados do
    // criador. O modelo e montado pela VPS.
    var payload = {
      token: afiliadoToken,
      name: name,
      email: email,
      platform: $('outreachPlatform').value,
      contact_url: contact,
    };
    if (name.length < 2) {
      $('outreachError').textContent = 'Informe como o criador é conhecido.';
      return;
    }
    if (!/^@[a-zA-Z0-9._-]{2,60}$/.test(contact)) {
      $('outreachError').textContent = 'Informe o @ do criador, começando com @.';
      return;
    }
    if (!email) {
      $('outreachError').textContent = 'Informe o e-mail do criador.';
      return;
    }
    withLoading($('outreachButton'), function () {
      $('outreachStatus').textContent = 'Enviando o convite…';
      $('outreachStatus').setAttribute('data-estado', 'enviando');
      return api('/hunters/outreach/email', {
        method: 'POST',
        body: JSON.stringify(payload),
      })
        .then(function (data) {
          $('outreachStatus').className = 'code-status is-ok';
          $('outreachStatus').setAttribute('data-estado', 'enviado');
          $('outreachStatus').textContent = data.queued
            ? 'Convite na fila para ' +
              (data.recipient || email) +
              '. Ele sai assim que o computador que envia os e-mails estiver online.'
            : 'E-mail enviado para ' +
              (data.recipient || email) +
              '. O contato foi registrado na base.';
          limpaCamposDoEnvio(camposNoEnvio);
          return loadAfiliadoDashboard();
        })
        .catch(function (error) {
          $('outreachStatus').textContent = '';
          $('outreachStatus').setAttribute('data-estado', 'erro');
          var data = error.data || {};
          if (data.quota) renderEmailQuota(data.quota);
          if (error.status === 429) {
            $('outreachError').textContent =
              'Você já usou os 3 e-mails desta janela' +
              (data.quota && data.quota.next_at
                ? '. O próximo envio libera em ' + formatDateTime(data.quota.next_at) + '.'
                : '.');
            return;
          }
          if (error.status === 409) {
            var prospect = data.prospect || {};
            var date = prospect.contacted_at ? formatDate(prospect.contacted_at) : '';
            var known = prospect.name || prospect.handle || '';
            $('outreachError').textContent =
              (known ? known + ' já foi' : 'Este criador já foi') +
              ' contatado' +
              (date ? ' em ' + date : '') +
              '. Não entre em contato novamente.';
            return;
          }
          $('outreachError').textContent = String(error.message || error);
        });
    });
  });

  /* ----------------------------------------------------------- listeners */

  Array.prototype.forEach.call(document.querySelectorAll('[data-open-create]'), function (button) {
    button.addEventListener('click', function () {
      openModal(button.getAttribute('data-open-create'));
    });
  });

  Array.prototype.forEach.call(document.querySelectorAll('[data-close]'), function (el) {
    el.addEventListener('click', closeModal);
  });

  /* Navegação por âncoras: quando o guia é exibido dinamicamente, o scroll
     nativo do navegador nem sempre acompanha, então cuidamos aqui. */
  var partnersNav = document.querySelector('.partners-nav');
  if (partnersNav) {
    partnersNav.addEventListener('click', function (event) {
      var anchor = event.target.closest ? event.target.closest('a[href^="#"]') : null;
      if (!anchor) return;
      var target = document.getElementById(anchor.getAttribute('href').slice(1));
      if (!target) return;
      event.preventDefault();
      var top = target.getBoundingClientRect().top + window.pageYOffset - 88;
      window.scrollTo({ top: top, behavior: reduceMotion ? 'auto' : 'smooth' });
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, '', anchor.getAttribute('href'));
      }
    });
  }

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') closeModal();
  });

  $('copyDashboardCode').addEventListener('click', function () {
    copy(currentCode, $('copyDashboardCode'));
  });
  /* O painel do link do afiliado pode ser removido do HTML sem quebrar o
     restante do script: so registramos o botao quando ele existe. */
  var copyAfiliadoLink = $('copyAfiliadoLink');
  if (copyAfiliadoLink) {
    copyAfiliadoLink.addEventListener('click', function () {
      copy(afiliadoLink || buildAfiliadoLink(), copyAfiliadoLink);
    });
  }

  /* feedback de clique nos botões: pop elástico (ver .btn.is-pressed no CSS) */
  if (!reduceMotion) {
    document.addEventListener('click', function (event) {
      var button = event.target && event.target.closest ? event.target.closest('.btn') : null;
      if (!button || button.disabled || button.classList.contains('is-loading')) return;
      button.classList.remove('is-pressed');
      void button.offsetWidth; /* reinicia a animação em cliques rápidos */
      button.classList.add('is-pressed');
    });
    document.addEventListener('animationend', function (event) {
      var target = event.target;
      if (target && target.classList && target.classList.contains('is-pressed')) {
        target.classList.remove('is-pressed');
      }
    });
  }

  var year = $('year');
  if (year) year.textContent = String(new Date().getFullYear());

  /* Progressive rendering: sections marked with data-reveal fade in only
     when they enter the viewport. Falls back to immediate visibility when
     reduced motion is set or IntersectionObserver is unavailable. */
  function setupReveal() {
    var items = Array.prototype.slice.call(document.querySelectorAll('[data-reveal]'));
    if (reduceMotion || !('IntersectionObserver' in window)) {
      items.forEach(function (item) {
        item.classList.add('is-visible');
      });
      return;
    }
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.08, rootMargin: '0px 0px -32px 0px' },
    );
    items.forEach(function (item) {
      observer.observe(item);
    });
  }

  function setupPage() {
    setupReveal();
    setupGuideAccordion();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupPage);
  } else {
    setupPage();
  }

  runSignupGuard();

  if (afiliadoToken) {
    loadAfiliadoDashboard();
  } else if (creatorToken) {
    loadCreatorDashboard();
  } else if (panelToken) {
    resolvePanelRole();
  } else {
    resetGuide();
    loadAttributionName();
    updateAttributionUI();
  }
})();
