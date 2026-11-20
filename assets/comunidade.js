/**
 * Comunidade — fórum público de ideias do vizin.Os.
 *
 * Contas leves (apelido + senha), propostas com votos (popularidade),
 * comentários e a aba "Já implementadas". Tudo lido da API pública
 * (window.VIZINHANCA_CONFIG.apiUrl) e renderizado via textContent —
 * nenhum conteúdo de usuário vira HTML.
 */
(function () {
  'use strict';

  var config = window.VIZINHANCA_CONFIG || {};
  var API = (config.apiUrl || 'https://api.188.166.156.109.sslip.io').replace(/\/+$/, '');
  var SESSION_KEY = 'vizin.os.comunidade.v1';
  var PAGE_SIZE = 25;

  var TAG_LABELS = {
    ideia: 'Ideias',
    melhoria: 'Melhorias',
    bug: 'Problemas (bugs)',
    outro: 'Outros',
  };

  var SORT_LABELS = { top: 'Mais populares', new: 'Mais recentes' };

  var ICONS = {
    up: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19V5"/><path d="m5 12 7-7 7 7"/></svg>',
    down: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v14"/><path d="m19 12-7 7-7-7"/></svg>',
    check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>',
  };

  var state = {
    tab: 'open',
    tag: '',
    sort: 'top',
    posts: [],
    total: 0,
    loading: false,
    online: true,
    session: null, // { token, username }
    counts: { open: 0, done: 0 },
  };

  var pendingAction = null; // ação esperando login (voto, publicar)
  var authMode = 'login';
  var openModals = [];
  var lastFocus = null;

  /* ------------------------------------------------------------- utils --- */

  function $(selector, scope) {
    return (scope || document).querySelector(selector);
  }

  function $$(selector, scope) {
    return Array.prototype.slice.call((scope || document).querySelectorAll(selector));
  }

  function el(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text != null) node.textContent = text;
    return node;
  }

  /** Selo "adm" da conta de administração, ao lado do apelido. */
  function seloAdm() {
    return el('span', 'comunidade-badge-adm', 'adm');
  }

  /** "por @apelido" + selo, quando for a administração. */
  function autorComSelo(username, admin, prefixo) {
    var caixa = el('span', 'comunidade-autor');
    if (prefixo) caixa.appendChild(el('span', null, prefixo));
    caixa.appendChild(el('span', 'comunidade-autor__nome', '@' + username));
    if (admin) caixa.appendChild(seloAdm());
    return caixa;
  }

  function relativeTime(ts) {
    var diff = Date.now() - Number(ts || 0);
    if (!(diff >= 0)) return '';
    var minutes = Math.floor(diff / 60000);
    if (minutes < 1) return 'agora mesmo';
    if (minutes < 60) return 'há ' + minutes + ' min';
    var hours = Math.floor(minutes / 60);
    if (hours < 24) return 'há ' + hours + ' h';
    var days = Math.floor(hours / 24);
    if (days === 1) return 'há 1 dia';
    if (days < 7) return 'há ' + days + ' dias';
    var date = new Date(Number(ts));
    var out = new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: 'short' }).format(date);
    if (date.getFullYear() !== new Date().getFullYear()) out += ' de ' + date.getFullYear();
    return out;
  }

  function excerpt(text, max) {
    var clean = String(text || '').replace(/\s+/g, ' ').trim();
    if (clean.length <= max) return clean;
    return clean.slice(0, max - 1).replace(/\s+\S*$/, '') + '…';
  }

  /* ---------------------------------------------------------------- api --- */

  function apiRequest(path, options) {
    options = options || {};
    var headers = { accept: 'application/json' };
    if (options.body) headers['content-type'] = 'application/json';
    if (state.session && options.auth !== false) {
      headers.authorization = 'Bearer ' + state.session.token;
    }
    return fetch(API + path, {
      method: options.method || 'GET',
      headers: headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
    }).then(function (response) {
      return response
        .json()
        .catch(function () {
          return {};
        })
        .then(function (data) {
          if (!response.ok) {
            var error = new Error((data && data.error) || 'algo deu errado; tente de novo');
            error.status = response.status;
            throw error;
          }
          return data;
        });
    });
  }

  /* ------------------------------------------------------------ sessão --- */

  function readStoredSession() {
    try {
      var raw = window.localStorage.getItem(SESSION_KEY);
      if (!raw) return null;
      var parsed = JSON.parse(raw);
      if (parsed && parsed.token && parsed.username) return parsed;
    } catch (error) {
      // localStorage indisponível: segue sem sessão.
    }
    return null;
  }

  function storeSession(session) {
    state.session = session;
    try {
      if (session) window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
      else window.localStorage.removeItem(SESSION_KEY);
    } catch (error) {
      // Sem storage: a sessão vive só nesta visita.
    }
    renderAuthState();
  }

  function restoreSession() {
    var stored = readStoredSession();
    if (!stored) return Promise.resolve(false);
    state.session = stored;
    renderAuthState();
    return apiRequest('/forum/session')
      .then(function (data) {
        storeSession({ token: stored.token, username: data.username || stored.username, admin: data.admin === true });
        return true;
      })
      .catch(function (error) {
        if (error.status === 401) storeSession(null);
        return false;
      });
  }

  function requireLogin(action) {
    pendingAction = action || null;
    openAuthModal();
  }

  function afterLogin() {
    // O painel da conta muda de cara quando ha sessao aberta: some o
    // formulario de entrada, o X e o alternador, e resta a pergunta de sair.
    renderAuthModal();
    // O detalhe pode ter sido aberto no modo "entre para comentar": com a
    // conta aberta, ele precisa virar formulário de comentário.
    if (!$('#comunidade-detail-modal').hidden) {
      var postId = $('#comunidade-detail-content').getAttribute('data-id');
      if (postId) {
        apiRequest('/forum/posts/' + encodeURIComponent(postId)).then(function (detail) {
          renderDetail(detail);
        });
      }
    }
    if (!pendingAction) return;
    var action = pendingAction;
    pendingAction = null;
    if (action.type === 'vote') vote(action.postId, action.value, action.contextEl);
    if (action.type === 'new-post') openNewModal();
  }

  /* -------------------------------------------------------------- modais --- */

  function openModal(modal, focusEl) {
    if (openModals.indexOf(modal) === -1) openModals.push(modal);
    lastFocus = document.activeElement;
    modal.hidden = false;
    document.body.style.overflow = 'hidden';
    var target = focusEl || $('input, textarea, select, button.modal-close', modal);
    if (target && target.focus) target.focus();
  }

  function closeModal(modal) {
    var index = openModals.indexOf(modal);
    if (index >= 0) openModals.splice(index, 1);
    modal.hidden = true;
    if (!openModals.length) document.body.style.overflow = '';
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  function closeTopModal() {
    if (openModals.length) closeModal(openModals[openModals.length - 1]);
  }

  function openAuthModal() {
    authMode = state.session ? 'logged' : authMode;
    renderAuthModal();
    openModal($('#comunidade-auth-modal'), state.session ? $('#comunidade-logout-btn') : $('#comunidade-auth-user'));
  }

  /* --------------------------------------------------- menu de ordenação --- */

  function setSortUI() {
    var label = $('#comunidade-sort-label');
    if (label) label.textContent = SORT_LABELS[state.sort] || state.sort;
    $$('.comunidade-menu-option').forEach(function (option) {
      option.setAttribute('aria-selected', option.getAttribute('data-sort') === state.sort ? 'true' : 'false');
    });
  }

  function closeSortMenu() {
    var menu = $('#comunidade-sort-menu');
    var list = $('#comunidade-sort-list');
    var button = $('#comunidade-sort-btn');
    if (!menu || !list || !button) return;
    menu.classList.remove('is-open');
    list.hidden = true;
    button.setAttribute('aria-expanded', 'false');
  }

  function toggleSortMenu(force) {
    var menu = $('#comunidade-sort-menu');
    var list = $('#comunidade-sort-list');
    var button = $('#comunidade-sort-btn');
    if (!menu || !list || !button) return;
    var open = typeof force === 'boolean' ? force : Boolean(list.hidden);
    menu.classList.toggle('is-open', open);
    list.hidden = !open;
    button.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) {
      var selected = $('.comunidade-menu-option[aria-selected="true"]', list) || $('.comunidade-menu-option', list);
      if (selected) selected.focus();
    }
  }

  /* ------------------------------------------------------ menu de tags --- */

  var TAG_LABELS_NOVO = {
    ideia: 'Ideias',
    melhoria: 'Melhorias',
    bug: 'Problemas (bugs)',
    outro: 'Outros',
  };

  function setNovaTagUI(tag) {
    var campo = $('#comunidade-new-tag');
    var rotulo = $('#comunidade-new-tag-label-value');
    if (campo) campo.value = tag;
    if (rotulo) rotulo.textContent = TAG_LABELS_NOVO[tag] || tag;
    $$('#comunidade-new-tag-list .comunidade-menu-option').forEach(function (option) {
      option.setAttribute('aria-selected', option.getAttribute('data-tag') === tag ? 'true' : 'false');
    });
  }

  function closeTagMenu() {
    var menu = $('#comunidade-new-tag-menu');
    var list = $('#comunidade-new-tag-list');
    var button = $('#comunidade-new-tag-btn');
    if (!menu || !list || !button) return;
    menu.classList.remove('is-open');
    list.hidden = true;
    button.setAttribute('aria-expanded', 'false');
  }

  function toggleTagMenu(force) {
    var menu = $('#comunidade-new-tag-menu');
    var list = $('#comunidade-new-tag-list');
    var button = $('#comunidade-new-tag-btn');
    if (!menu || !list || !button) return;
    var open = typeof force === 'boolean' ? force : Boolean(list.hidden);
    menu.classList.toggle('is-open', open);
    list.hidden = !open;
    button.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) {
      var selected = $('.comunidade-menu-option[aria-selected="true"]', list) || $('.comunidade-menu-option', list);
      if (selected) selected.focus();
    }
  }

  function openNewModal() {
    openModal($('#comunidade-new-modal'), $('#comunidade-new-title'));
  }

  function openDetailModal() {
    openModal($('#comunidade-detail-modal'), $('#comunidade-detail-content'));
  }

  /* -------------------------------------------------------------- render --- */

  function setBanner(message) {
    var banner = $('#comunidade-banner');
    if (!message) {
      banner.hidden = true;
      banner.textContent = '';
      return;
    }
    banner.hidden = false;
    banner.textContent = '';
    banner.appendChild(el('strong', null, message.title || ''));
    if (message.text) banner.appendChild(el('span', null, ' ' + message.text));
  }

  function setStatus(message) {
    var status = $('#comunidade-status');
    if (!message) {
      status.hidden = true;
      status.textContent = '';
      return;
    }
    status.hidden = false;
    status.textContent = message;
  }

  function updateTabCounts() {
    $$('.comunidade-tab').forEach(function (tab) {
      var key = tab.getAttribute('data-tab');
      var count = state.counts[key];
      var holder = $('.comunidade-tab-count', tab);
      if (!holder) {
        holder = el('span', 'comunidade-tab-count');
        tab.appendChild(holder);
      }
      holder.textContent = typeof count === 'number' && count > 0 ? ' (' + count + ')' : '';
    });
  }

  /** Chip discreto com a conta atual: só aparece com sessão aberta;
      clicar abre o modal da conta (onde fica o "Sair"). */
  function renderAuthState() {
    var account = $('#comunidade-account-btn');
    if (!account) return;
    if (state.session) {
      account.textContent = '';
      account.appendChild(el('span', null, '@' + state.session.username));
      if (state.session.admin) account.appendChild(seloAdm());
      account.hidden = false;
    } else {
      account.hidden = true;
      account.textContent = '';
    }
  }

  function renderAuthModal() {
    var form = $('#comunidade-auth-form');
    var logged = $('#comunidade-auth-logged');
    var title = $('#comunidade-auth-title');
    var submit = $('#comunidade-auth-submit');
    var pass = $('#comunidade-auth-pass');
    var fechar = $('#comunidade-auth-modal .modal-close');
    var alternar = $('.comunidade-auth-switch');
    var nota = $('#comunidade-auth-note');
    if (state.session) {
      // Conectado: o painel vira uma pergunta simples e o botão de sair.
      // Nem o X, nem a troca Entrar/Criar conta, nem a nota de segurança.
      // A classe "hidden" esconde de verdade (o atributo hidden nao vence o
      // display: grid do botão de fechar).
      title.textContent = 'Conta da Comunidade';
      form.hidden = true;
      logged.hidden = false;
      if (fechar) fechar.classList.add('hidden');
      if (alternar) alternar.classList.add('hidden');
      if (nota) nota.classList.add('hidden');
      $('#comunidade-auth-who').textContent = '@' + state.session.username;
      return;
    }
    title.textContent = authMode === 'login' ? 'Entre na Comunidade' : 'Criar conta na Comunidade';
    form.hidden = false;
    logged.hidden = true;
    if (fechar) fechar.classList.remove('hidden');
    if (alternar) alternar.classList.remove('hidden');
    if (nota) nota.classList.remove('hidden');
    submit.textContent = authMode === 'login' ? 'Entrar' : 'Criar conta';
    pass.setAttribute('autocomplete', authMode === 'login' ? 'current-password' : 'new-password');
    $$('.comunidade-auth-switch button').forEach(function (button) {
      button.classList.toggle('is-active', button.getAttribute('data-auth-mode') === authMode);
    });
  }

  function showFormError(id, message) {
    var error = $(id);
    if (!error) return;
    error.hidden = !message;
    error.textContent = message || '';
  }

  function setBusy(button, busy, busyLabel) {
    if (!button) return;
    if (busy) {
      button.dataset.label = button.textContent;
      button.disabled = true;
      if (busyLabel) button.textContent = busyLabel;
    } else {
      button.disabled = false;
      if (button.dataset.label) button.textContent = button.dataset.label;
    }
  }

  function voteBox(post, compact) {
    var box = el('div', 'comunidade-votes');
    if (compact) box.className = 'comunidade-detail-votes';

    var up = el('button', 'comunidade-vote-btn' + (post.my_vote === 1 ? ' is-up' : ''));
    up.type = 'button';
    up.setAttribute('data-vote', '1');
    up.setAttribute('aria-pressed', post.my_vote === 1 ? 'true' : 'false');
    up.setAttribute('aria-label', 'Votar a favor');
    up.innerHTML = ICONS.up;

    var down = el('button', 'comunidade-vote-btn' + (post.my_vote === -1 ? ' is-down' : ''));
    down.type = 'button';
    down.setAttribute('data-vote', '-1');
    down.setAttribute('aria-pressed', post.my_vote === -1 ? 'true' : 'false');
    down.setAttribute('aria-label', 'Votar contra');
    down.innerHTML = ICONS.down;

    var score = el('span', 'comunidade-score' + (post.score < 0 ? ' is-negative' : ''), String(post.score));
    if (compact) {
      score.classList.add('comunidade-detail-score');
      box.appendChild(up);
      box.appendChild(score);
      box.appendChild(down);
    } else {
      box.appendChild(up);
      box.appendChild(score);
      box.appendChild(down);
    }
    return box;
  }

  function postCard(post) {
    var card = el('article', 'comunidade-post');
    card.setAttribute('data-id', post.id);
    card.appendChild(voteBox(post, false));

    var body = el('div', 'comunidade-post-body');
    var top = el('div', 'comunidade-post-top');
    top.appendChild(el('span', 'comunidade-tag', TAG_LABELS[post.tag] || post.tag));
    if (post.status === 'done') {
      var badge = el('span', 'comunidade-badge-done');
      badge.innerHTML = ICONS.check + '<span>Implementada</span>';
      top.appendChild(badge);
    }
    if (post.mine) top.appendChild(el('span', 'comunidade-mine', 'sua proposta'));
    body.appendChild(top);

    var title = el('button', 'comunidade-post-title', post.title);
    title.type = 'button';
    title.setAttribute('data-open', post.id);
    body.appendChild(title);

    body.appendChild(el('p', 'comunidade-post-excerpt', excerpt(post.body, 180)));

    var meta = el('div', 'comunidade-post-meta');
    meta.appendChild(autorComSelo(post.username, post.admin, 'por '));
    meta.appendChild(el('span', 'comunidade-meta-sep', '·'));
    meta.appendChild(el('span', null, relativeTime(post.created_at)));
    meta.appendChild(el('span', 'comunidade-meta-sep', '·'));
    var comments = el('button', 'comunidade-meta-link');
    comments.type = 'button';
    comments.setAttribute('data-open', post.id);
    comments.textContent =
      post.comment_count === 1 ? '1 comentário' : post.comment_count + ' comentários';
    meta.appendChild(comments);
    body.appendChild(meta);

    card.appendChild(body);
    return card;
  }

  function renderSkeletons(count) {
    var list = $('#comunidade-list');
    list.textContent = '';
    for (var i = 0; i < (count || 4); i++) {
      var skeleton = el('div', 'comunidade-skeleton');
      skeleton.appendChild(el('div', 'sk sk-votes'));
      var lines = el('div', 'sk-lines');
      lines.appendChild(el('div', 'sk sk-line'));
      lines.appendChild(el('div', 'sk sk-line'));
      lines.appendChild(el('div', 'sk sk-line'));
      skeleton.appendChild(lines);
      list.appendChild(skeleton);
    }
  }

  function renderEmptyState() {
    var list = $('#comunidade-list');
    list.textContent = '';
    var empty = el('div', 'comunidade-empty');
    /* h2: este texto fica logo abaixo do h1 da pagina, entao nao pode
       pular um nivel na hierarquia de titulos. */
    var title = el('h2');
    var text = el('p');
    if (state.tab === 'done') {
      title.textContent = 'Nada implementado ainda';
      text.textContent = state.tag
        ? 'Nenhuma proposta com a tag "' + (TAG_LABELS[state.tag] || state.tag) + '" foi implementada até agora. Vote nas favoritas para guiar o que vem primeiro.'
        : 'As propostas mais votadas da Comunidade guiam o que é construído primeiro. Vote nas suas favoritas.';
    } else {
      title.textContent = 'A comunidade está construída, falta a primeira fala';
      text.textContent = state.tag
        ? 'Nenhuma proposta com a tag "' + (TAG_LABELS[state.tag] || state.tag) + '" por enquanto. Que tal escrever a primeira?'
        : 'Proponha uma ideia, sugira uma melhoria ou reporte um problema — é assim que o vizin.Os cresce junto com quem usa.';
    }
    empty.appendChild(title);
    empty.appendChild(text);
    if (state.tab === 'open' && !state.tag) {
      var action = el('button', 'btn btn-primary');
      action.type = 'button';
      action.textContent = 'Publicar a primeira proposta';
      action.addEventListener('click', function () {
        openNewOrLogin();
      });
      var wrap = el('div');
      wrap.style.marginTop = 'var(--space-5)';
      wrap.appendChild(action);
      empty.appendChild(wrap);
    }
    list.appendChild(empty);
  }

  function renderList() {
    var list = $('#comunidade-list');
    var more = $('#comunidade-more-btn');
    list.textContent = '';
    more.hidden = state.posts.length >= state.total;
    if (!state.posts.length) {
      renderEmptyState();
      return;
    }
    state.posts.forEach(function (post) {
      list.appendChild(postCard(post));
    });
  }

  /* ---------------------------------------------------------- carregamento --- */

  function loadStatus() {
    return apiRequest('/forum/status')
      .then(function (data) {
        state.online = true;
        state.counts = { open: data.open_count || 0, done: data.done_count || 0 };
        updateTabCounts();
        setStatus(
          (data.open_count || 0) + ' em discussão · ' + (data.done_count || 0) + ' implementada(s) — cada voto pesa na direção do app.',
        );
        setBanner(null);
      })
      .catch(function () {
        state.online = false;
        setBanner({
          title: 'A Comunidade está fora do ar neste momento.',
          text: 'A API do vizin.Os não respondeu. Tente de novo em alguns minutos — as propostas e votos continuam guardados.',
        });
      });
  }

  /* Cada pedido de lista carrega um número. A resposta só pinta a tela se
     ainda for a mais recente: clicar duas vezes rápido numa aba não deixa a
     lista antiga sobrescrever a nova. */
  var listRequest = 0;

  function loadPosts(append) {
    var offset = append ? state.posts.length : 0;
    if (!append) {
      // Com dados na tela, trocar de aba/filtro não deve piscar esqueletos.
      if (!state.posts.length) renderSkeletons(4);
      else renderList();
    }
    var query =
      '?status=' + state.tab + '&sort=' + state.sort + '&limit=' + PAGE_SIZE + '&offset=' + offset +
      (state.tag ? '&tag=' + encodeURIComponent(state.tag) : '');
    var requestId = ++listRequest;
    apiRequest('/forum/posts' + query)
      .then(function (data) {
        if (requestId !== listRequest) return;
        state.total = data.total || 0;
        state.posts = append ? state.posts.concat(data.posts || []) : data.posts || [];
        renderList();
      })
      .catch(function (error) {
        if (requestId !== listRequest) return;
        if (!append) {
          state.posts = [];
          state.total = 0;
          renderList();
        }
        setStatus('Não foi possível carregar as propostas: ' + error.message);
      });
  }

  function reload() {
    loadPosts(false);
  }

  /* ------------------------------------------------------------- votos --- */

  function applyVoteUpdate(contextEl, data) {
    var scope = contextEl ? contextEl.closest('.comunidade-post, #comunidade-detail-content') : null;
    if (!scope) return;
    var upButton = $('[data-vote="1"]', scope);
    var downButton = $('[data-vote="-1"]', scope);
    var score = $('.comunidade-score', scope);
    if (upButton) {
      upButton.classList.toggle('is-up', data.my_vote === 1);
      upButton.setAttribute('aria-pressed', data.my_vote === 1 ? 'true' : 'false');
    }
    if (downButton) {
      downButton.classList.toggle('is-down', data.my_vote === -1);
      downButton.setAttribute('aria-pressed', data.my_vote === -1 ? 'true' : 'false');
    }
    if (score) {
      score.textContent = String(data.score);
      score.classList.toggle('is-negative', data.score < 0);
    }
    // Atualiza também o cartão equivalente na lista (o detalhe e o cartão
    // mostram a mesma proposta).
    var postId = scope.getAttribute('data-id');
    if (postId) {
      $$('.comunidade-post[data-id="' + postId + '"]').forEach(function (card) {
        if (card === scope) return;
        applyVoteUpdate(card, data);
      });
    }
  }

  function vote(postId, value, contextEl) {
    if (!state.session) {
      requireLogin({
        type: 'vote',
        postId: postId,
        value: value,
        contextEl: contextEl,
      });
      return;
    }
    var buttons = contextEl
      ? $$('[data-vote]', contextEl.closest('.comunidade-post, #comunidade-detail-content') || contextEl)
      : [];
    buttons.forEach(function (button) {
      button.disabled = true;
    });
    apiRequest('/forum/posts/' + encodeURIComponent(postId) + '/vote', {
      method: 'POST',
      body: { value: value },
    })
      .then(function (data) {
        applyVoteUpdate(contextEl, data);
        var stored = null;
        state.posts.some(function (post) {
          if (post.id === postId) stored = post;
          return post.id === postId;
        });
        if (stored) {
          stored.my_vote = data.my_vote;
          stored.score = data.score;
          stored.up = data.up;
          stored.down = data.down;
        }
      })
      .catch(function (error) {
        if (error.status === 401) {
          storeSession(null);
          requireLogin({
            type: 'vote',
            postId: postId,
            value: value,
            contextEl: contextEl,
          });
        } else {
          setStatus('O voto não foi registrado: ' + error.message);
        }
      })
      .then(function () {
        buttons.forEach(function (button) {
          button.disabled = false;
        });
      });
  }

  /* ------------------------------------------------------------ detalhe --- */

  function renderComments(post, comments) {
    var wrap = el('div', 'comunidade-comments');
    wrap.appendChild(
      el('h3', null, comments.length === 1 ? '1 comentário' : comments.length + ' comentários'),
    );
    var list = el('div', 'comunidade-comment-list');
    if (!comments.length) {
      list.appendChild(
        el('p', 'comunidade-modal-sub', 'Nenhum comentário ainda. Diga o que pensa — crítica boa também é contribuição.'),
      );
    }
    comments.forEach(function (comment) {
      var item = el('div', 'comunidade-comment');
      var head = el('div', 'comunidade-comment-head');
      head.appendChild(el('span', 'comunidade-comment-author', '@' + comment.username));
      if (comment.admin) head.appendChild(seloAdm());
      head.appendChild(el('span', null, relativeTime(comment.created_at)));
      if (comment.mine) {
        var del = el('button', 'comunidade-comment-del');
        del.type = 'button';
        del.setAttribute('data-del-comment', comment.id);
        del.textContent = 'apagar';
        head.appendChild(del);
      }
      item.appendChild(head);
      item.appendChild(el('p', 'comunidade-comment-body', comment.body));
      list.appendChild(item);
    });
    wrap.appendChild(list);

    if (state.session) {
      var form = el('form', 'comunidade-comment-form');
      form.setAttribute('data-comment-form', post.id);
      var field = el('div', 'field');
      var label = el('label', null, 'Seu comentário');
      label.setAttribute('for', 'comunidade-comment-input');
      var textarea = el('textarea');
      textarea.id = 'comunidade-comment-input';
      textarea.name = 'body';
      textarea.maxLength = 1000;
      textarea.rows = 3;
      textarea.placeholder = 'Apoie, questione ou complete a ideia (2 a 1000 caracteres).';
      field.appendChild(label);
      field.appendChild(textarea);
      form.appendChild(field);
      var error = el('p', 'comunidade-form-error');
      error.hidden = true;
      error.setAttribute('data-comment-error', '');
      form.appendChild(error);
      var submit = el('button', 'btn btn-primary comunidade-submit');
      submit.type = 'submit';
      submit.textContent = 'Comentar';
      form.appendChild(submit);
      wrap.appendChild(form);
    } else {
      var cta = el('div', 'comunidade-login-cta');
      cta.appendChild(el('span', null, 'Entre com sua conta para comentar nesta proposta.'));
      var button = el('button', 'btn btn-secondary btn-sm');
      button.type = 'button';
      button.textContent = 'Entrar';
      button.addEventListener('click', function () {
        requireLogin(null);
      });
      cta.appendChild(button);
      wrap.appendChild(cta);
    }
    return wrap;
  }

  function renderDetail(data) {
    var post = data.post;
    var content = $('#comunidade-detail-content');
    content.setAttribute('data-id', post.id);
    content.textContent = '';

    var top = el('div', 'comunidade-post-top');
    top.style.marginTop = 'var(--space-4)';
    top.appendChild(el('span', 'comunidade-tag', TAG_LABELS[post.tag] || post.tag));
    if (post.status === 'done') {
      var badge = el('span', 'comunidade-badge-done');
      badge.innerHTML = ICONS.check + '<span>Implementada</span>';
      top.appendChild(badge);
    }
    if (post.mine) top.appendChild(el('span', 'comunidade-mine', 'sua proposta'));
    content.appendChild(top);

    var head = el('div', 'comunidade-detail-head');
    head.appendChild(el('h2', 'comunidade-detail-title', post.title));
    head.appendChild(voteBox(post, true));
    content.appendChild(head);

    var metaDetalhe = el('p', 'comunidade-post-meta');
    metaDetalhe.appendChild(autorComSelo(post.username, post.admin, 'por '));
    metaDetalhe.appendChild(el('span', 'comunidade-meta-sep', '·'));
    metaDetalhe.appendChild(el('span', null, relativeTime(post.created_at)));
    content.appendChild(metaDetalhe);

    if (post.status === 'done') {
      var note = el('p', 'comunidade-detail-note');
      note.textContent = 'Implementada' + (post.status_note ? ' — ' + post.status_note : '') + '.';
      content.appendChild(note);
    }

    content.appendChild(el('div', 'comunidade-detail-body', post.body));

    if (post.mine) {
      var del = el('button', 'comunidade-comment-del');
      del.type = 'button';
      del.setAttribute('data-del-post', post.id);
      del.style.marginTop = 'var(--space-3)';
      del.textContent = 'apagar minha proposta';
      content.appendChild(del);
    }

    content.appendChild(renderComments(post, data.comments || []));
  }

  function openPost(postId) {
    openDetailModal();
    var content = $('#comunidade-detail-content');
    content.textContent = '';
    content.appendChild(el('p', 'comunidade-modal-sub', 'Carregando proposta…'));
    apiRequest('/forum/posts/' + encodeURIComponent(postId))
      .then(function (data) {
        renderDetail(data);
      })
      .catch(function (error) {
        content.textContent = '';
        content.appendChild(el('p', 'comunidade-form-error', 'Não foi possível abrir a proposta: ' + error.message));
      });
  }

  /* ------------------------------------------------------- novas propostas --- */

  function openNewOrLogin() {
    if (!state.session) {
      requireLogin({ type: 'new-post' });
      return;
    }
    openNewModal();
  }

  function publishPost(form) {
    var submit = $('#comunidade-new-submit');
    var title = $('#comunidade-new-title').value.trim();
    var body = $('#comunidade-new-body').value.trim();
    var tag = $('#comunidade-new-tag').value;
    showFormError('#comunidade-new-error', '');
    if (title.length < 6) {
      showFormError('#comunidade-new-error', 'O título precisa ter pelo menos 6 caracteres.');
      return;
    }
    if (body.length < 10) {
      showFormError('#comunidade-new-error', 'A proposta precisa de pelo menos 10 caracteres.');
      return;
    }
    setBusy(submit, true, 'Publicando…');
    apiRequest('/forum/posts', { method: 'POST', body: { title: title, body: body, tag: tag } })
      .then(function () {
        closeTopModal();
        form.reset();
        state.tab = 'open';
        state.sort = 'new';
        syncTabs();
        setSortUI();
        setStatus('Proposta publicada! Ela já está na lista — agora é hora de os votos falarem.');
        loadStatus();
        reload();
      })
      .catch(function (error) {
        if (error.status === 401) {
          storeSession(null);
          closeTopModal();
          requireLogin({ type: 'new-post' });
        } else {
          showFormError('#comunidade-new-error', error.message);
        }
      })
      .then(function () {
        setBusy(submit, false);
      });
  }

  /* --------------------------------------------------------------- auth --- */

  function submitAuth(form) {
    var submit = $('#comunidade-auth-submit');
    var username = $('#comunidade-auth-user').value.trim();
    var password = $('#comunidade-auth-pass').value;
    showFormError('#comunidade-auth-error', '');
    if (!/^[a-zA-Z0-9_.-]{3,20}$/.test(username)) {
      showFormError('#comunidade-auth-error', 'Apelido inválido: 3 a 20 caracteres (letras, números, ponto, hífen ou _).');
      return;
    }
    if (password.length < 8) {
      showFormError('#comunidade-auth-error', 'A senha precisa ter pelo menos 8 caracteres.');
      return;
    }
    setBusy(submit, true, authMode === 'login' ? 'Entrando…' : 'Criando conta…');
    apiRequest('/forum/' + (authMode === 'login' ? 'login' : 'register'), {
      method: 'POST',
      auth: false,
      body: { username: username, password: password },
    })
      .then(function (data) {
        storeSession({ token: data.token, username: data.username, admin: data.admin === true });
        form.reset();
        closeTopModal();
        afterLogin();
        loadPosts(false);
      })
      .catch(function (error) {
        showFormError('#comunidade-auth-error', error.message);
      })
      .then(function () {
        setBusy(submit, false);
      });
  }

  function logout() {
    var button = $('#comunidade-logout-btn');
    setBusy(button, true, 'Saindo…');
    var request = state.session
      ? apiRequest('/forum/logout', { method: 'POST' }).catch(function () {})
      : Promise.resolve();
    request.then(function () {
      storeSession(null);
      authMode = 'login'; // quem saiu quer entrar de novo, não criar outra conta
      setBusy(button, false);
      // O painel volta a ser o de entrada: com o X, o alternador e a nota.
      renderAuthModal();
      closeTopModal();
      setStatus('Você saiu da Comunidade. Até a próxima!');
    });
  }

  /* ---------------------------------------------------------------- eventos --- */

  function syncTabs() {
    $$('.comunidade-tab').forEach(function (tab) {
      var active = tab.getAttribute('data-tab') === state.tab;
      tab.classList.toggle('is-active', active);
      tab.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    $$('.comunidade-tag-chip').forEach(function (chip) {
      chip.classList.toggle('is-active', (chip.getAttribute('data-tag') || '') === state.tag);
    });
  }

  function bind() {
    // abas
    $$('.comunidade-tab').forEach(function (tab) {
      tab.addEventListener('click', function () {
        state.tab = tab.getAttribute('data-tab');
        syncTabs();
        reload();
      });
    });

    // tags
    $$('.comunidade-tag-chip').forEach(function (chip) {
      chip.addEventListener('click', function () {
        state.tag = chip.getAttribute('data-tag') || '';
        syncTabs();
        reload();
      });
    });

    // ordenação: menu customizado
    $('#comunidade-sort-btn').addEventListener('click', function () {
      toggleSortMenu();
    });
    $$('.comunidade-menu-option').forEach(function (option) {
      option.addEventListener('click', function () {
        state.sort = option.getAttribute('data-sort');
        setSortUI();
        closeSortMenu();
        $('#comunidade-sort-btn').focus();
        reload();
      });
    });
    $('#comunidade-sort-list').addEventListener('keydown', function (event) {
      if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
      event.preventDefault();
      var options = $$('.comunidade-menu-option', $('#comunidade-sort-list'));
      var index = options.indexOf(document.activeElement);
      var next = event.key === 'ArrowDown' ? Math.min(index + 1, options.length - 1) : Math.max(index - 1, 0);
      if (options[next]) options[next].focus();
    });
    document.addEventListener('click', function (event) {
      var menu = $('#comunidade-sort-menu');
      if (menu && !menu.contains(event.target)) closeSortMenu();
      var menuTag = $('#comunidade-new-tag-menu');
      if (menuTag && !menuTag.contains(event.target)) closeTagMenu();
    });

    // tag da proposta: mesmo menu customizado do "Mais populares"
    $('#comunidade-new-tag-btn').addEventListener('click', function () {
      toggleTagMenu();
    });
    $$('#comunidade-new-tag-list .comunidade-menu-option').forEach(function (option) {
      option.addEventListener('click', function () {
        setNovaTagUI(option.getAttribute('data-tag'));
        closeTagMenu();
        $('#comunidade-new-tag-btn').focus();
      });
    });
    $('#comunidade-new-tag-list').addEventListener('keydown', function (event) {
      if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
      event.preventDefault();
      var options = $$('.comunidade-menu-option', $('#comunidade-new-tag-list'));
      var index = options.indexOf(document.activeElement);
      var next = event.key === 'ArrowDown' ? Math.min(index + 1, options.length -1) : Math.max(index - 1, 0);
      if (options[next]) options[next].focus();
    });

    // nova proposta
    $('#comunidade-new-btn').addEventListener('click', openNewOrLogin);

    // carregar mais
    $('#comunidade-more-btn').addEventListener('click', function () {
      loadPosts(true);
    });

    // conta: chip da sessão atual
    $('#comunidade-account-btn').addEventListener('click', openAuthModal);

    // senha: mostrar/ocultar
    $('#comunidade-pass-toggle').addEventListener('click', function () {
      var input = $('#comunidade-auth-pass');
      var button = $('#comunidade-pass-toggle');
      var show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      button.setAttribute('aria-pressed', show ? 'true' : 'false');
      button.setAttribute('aria-label', show ? 'Ocultar senha' : 'Mostrar senha');
    });

    // delegação na lista: voto e abrir proposta
    $('#comunidade-list').addEventListener('click', function (event) {
      var target = event.target;
      var voteButton = target.closest ? target.closest('[data-vote]') : null;
      if (voteButton) {
        var card = voteButton.closest('.comunidade-post');
        vote(card.getAttribute('data-id'), Number(voteButton.getAttribute('data-vote')), voteButton);
        return;
      }
      var openTrigger = target.closest ? target.closest('[data-open]') : null;
      if (openTrigger) openPost(openTrigger.getAttribute('data-open'));
    });

    // delegação no detalhe: voto, comentário, apagar
    $('#comunidade-detail-content').addEventListener('click', function (event) {
      var target = event.target;
      var voteButton = target.closest ? target.closest('[data-vote]') : null;
      if (voteButton) {
        var content = $('#comunidade-detail-content');
        vote(content.getAttribute('data-id'), Number(voteButton.getAttribute('data-vote')), voteButton);
        return;
      }
      var delComment = target.closest ? target.closest('[data-del-comment]') : null;
      if (delComment) {
        deleteComment(delComment.getAttribute('data-del-comment'));
        return;
      }
      var delPost = target.closest ? target.closest('[data-del-post]') : null;
      if (delPost) deletePost(delPost.getAttribute('data-del-post'));
    });

    $('#comunidade-detail-content').addEventListener('submit', function (event) {
      var form = event.target;
      if (!form.matches('[data-comment-form]')) return;
      event.preventDefault();
      submitComment(form, form.getAttribute('data-comment-form'));
    });

    // modal de conta
    $('#comunidade-auth-form').addEventListener('submit', function (event) {
      event.preventDefault();
      submitAuth(event.target);
    });
    $$('.comunidade-auth-switch button').forEach(function (button) {
      button.addEventListener('click', function () {
        authMode = button.getAttribute('data-auth-mode');
        showFormError('#comunidade-auth-error', '');
        renderAuthModal();
        $('#comunidade-auth-user').focus();
      });
    });
    $('#comunidade-logout-btn').addEventListener('click', logout);

    // nova proposta
    $('#comunidade-new-form').addEventListener('submit', function (event) {
      event.preventDefault();
      publishPost(event.target);
    });

    // fechar modais
    $$('[data-comunidade-close]').forEach(function (trigger) {
      trigger.addEventListener('click', function () {
        closeModal(trigger.closest('.modal'));
      });
    });
    document.addEventListener('keydown', function (event) {
      if (event.key !== 'Escape') return;
      var list = $('#comunidade-sort-list');
      if (list && !list.hidden) {
        closeSortMenu();
        $('#comunidade-sort-btn').focus();
        return;
      }
      closeTopModal();
    });
  }

  /* -------------------------------------------------- comentários (ações) --- */

  function submitComment(form, postId) {
    var textarea = $('textarea', form);
    var error = $('[data-comment-error]', form);
    var submit = $('button[type="submit"]', form);
    var text = textarea.value.trim();
    error.hidden = true;
    if (text.length < 2) {
      error.hidden = false;
      error.textContent = 'Escreva pelo menos 2 caracteres.';
      return;
    }
    setBusy(submit, true, 'Enviando…');
    apiRequest('/forum/posts/' + encodeURIComponent(postId) + '/comments', {
      method: 'POST',
      body: { body: text },
    })
      .then(function (data) {
        textarea.value = '';
        // Recarrega o detalhe: traz o comentário novo no lugar certo.
        return apiRequest('/forum/posts/' + encodeURIComponent(postId)).then(function (detail) {
          renderDetail(detail);
          var focus = $('.comunidade-comment-input, #comunidade-comment-input', $('#comunidade-detail-content'));
          if (focus) focus.focus();
        });
      })
      .catch(function (err) {
        error.hidden = false;
        error.textContent = err.message;
      })
      .then(function () {
        setBusy(submit, false);
      });
  }

  function deleteComment(commentId) {
    apiRequest('/forum/comments/' + encodeURIComponent(commentId), { method: 'DELETE' })
      .then(function () {
        var postId = $('#comunidade-detail-content').getAttribute('data-id');
        return apiRequest('/forum/posts/' + encodeURIComponent(postId)).then(function (detail) {
          renderDetail(detail);
        });
      })
      .catch(function (error) {
        setStatus('Não foi possível apagar o comentário: ' + error.message);
      });
  }

  function deletePost(postId) {
    apiRequest('/forum/posts/' + encodeURIComponent(postId), { method: 'DELETE' })
      .then(function () {
        closeTopModal();
        setStatus('Proposta apagada.');
        loadStatus();
        reload();
      })
      .catch(function (error) {
        setStatus('Não foi possível apagar a proposta: ' + error.message);
      });
  }

  /* ----------------------------------------------------------------- boot --- */

  function boot() {
    bind();
    renderAuthState();
    syncTabs();
    setSortUI();
    renderSkeletons(4);
    restoreSession();
    loadStatus();
    loadPosts(false);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
