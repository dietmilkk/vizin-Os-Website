(function () {
  'use strict';

  var config = window.VIZINHANCA_CONFIG || {};
  var API = (config.apiUrl || 'https://api.188.166.156.109.sslip.io').replace(/\/+$/, '');
  var SESSION_KEY = 'vizin.os.painel.token.v1';
  var params = new URLSearchParams(window.location.search);
  var numericCode = extractNumericCode(window.location.pathname);
  var modToken = '';
  var connectStatus = 'not_started';
  var profileComplete = false;
  var toastTimer = null;

  function $(id) {
    return document.getElementById(id);
  }

  function extractNumericCode(pathname) {
    var match = String(pathname || '').match(/(?:^|\/)1\d{10}\/?$/);
    return match ? match[0].replace(/^\//, '').replace(/\/$/, '') : '';
  }

  function readSession() {
    try {
      var raw = window.sessionStorage.getItem(SESSION_KEY);
      if (!raw) return {};
      var parsed = JSON.parse(raw);
      return parsed && typeof parsed === 'object' ? parsed : {};
    } catch (error) {
      return {};
    }
  }

  function saveModToken(token) {
    var session = readSession();
    session.c = session.c || '';
    session.a = session.a || '';
    session.m = String(token || '').trim();
    try {
      window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
    } catch (error) {
      /* Se o navegador bloquear storage, o token continua só em memória. */
    }
  }

  function removeModToken() {
    var session = readSession();
    delete session.m;
    try {
      window.sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
    } catch (error) {
      /* Sem storage não há sessão antiga para limpar. */
    }
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

  function newIdempotencyKey(prefix) {
    var random = '';
    try {
      var values = new Uint32Array(6);
      window.crypto.getRandomValues(values);
      values.forEach(function (value) {
        random += value.toString(16);
      });
    } catch (error) {
      random = Math.random().toString(36).slice(2) + Date.now().toString(36);
    }
    return (prefix + random).replace(/[^A-Za-z0-9_-]/g, '').slice(0, 64);
  }

  // Intenção de saque guardada enquanto a pessoa configura a conta na Stripe:
  // ao voltar, o saque continua sozinho (sem precisar clicar de novo).
  var PENDING_KEY = 'vizin.os.mod.payout.v1';

  function rememberPendingWithdrawal() {
    try {
      window.sessionStorage.setItem(PENDING_KEY, newIdempotencyKey('modsaq'));
    } catch (error) {
      /* Sem storage: o saque continua manual após o onboarding. */
    }
  }

  function pendingWithdrawalKey() {
    try {
      var saved = window.sessionStorage.getItem(PENDING_KEY);
      if (saved) return saved;
    } catch (error) {
      /* Sem storage: gera uma chave nova. */
    }
    return newIdempotencyKey('modsaq');
  }

  function clearPendingWithdrawal() {
    try {
      window.sessionStorage.removeItem(PENDING_KEY);
    } catch (error) {
      /* Nada a fazer. */
    }
  }

  function api(path, options) {
    var opts = options || {};
    var headers = { Accept: 'application/json' };
    if (opts.body) headers['Content-Type'] = 'application/json';
    if (modToken) headers.Authorization = 'Bearer ' + modToken;

    return fetch(API + path, {
      method: opts.method || 'GET',
      headers: headers,
      body: opts.body || undefined,
      cache: 'no-store',
    }).then(function (response) {
      return response.json().catch(function () {
        return {};
      }).then(function (data) {
        if (!response.ok) {
          var error = new Error(data.error || 'Não foi possível concluir a operação.');
          error.status = response.status;
          error.data = data;
          throw error;
        }
        return data;
      });
    });
  }

  function setFeedback(element, message, isError) {
    if (!element) return;
    element.textContent = message || '';
    element.classList.toggle('is-error', Boolean(isError));
    element.classList.toggle('is-success', Boolean(message) && !isError);
  }

  function showToast(message) {
    var toast = $('mod-toast');
    if (!toast) return;
    window.clearTimeout(toastTimer);
    toast.textContent = message;
    toast.hidden = false;
    toast.classList.add('is-visible');
    toastTimer = window.setTimeout(function () {
      toast.classList.remove('is-visible');
      toast.hidden = true;
    }, 2600);
  }

  function withLoading(button, task) {
    if (!button) return task();
    var wasDisabled = button.disabled;
    button.disabled = true;
    button.setAttribute('aria-busy', 'true');
    button.classList.add('is-loading');
    return task().finally(function () {
      button.disabled = wasDisabled;
      button.removeAttribute('aria-busy');
      button.classList.remove('is-loading');
    });
  }

  function copyText(text) {
    if (!text) return;
    function done() {
      showToast('Copiado!');
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
      showToast('Não foi possível copiar.');
    }
    document.body.removeChild(area);
  }

  function statusLabel(status) {
    var labels = {
      requested: 'Solicitado',
      processing: 'Processando',
      paid: 'Pago',
      failed: 'Falhou',
      rejected: 'Recusado',
    };
    return labels[status] || status || '—';
  }

  function statusClass(status) {
    if (status === 'paid') return 'withdraw-status--paid';
    if (status === 'processing') return 'withdraw-status--processing';
    if (status === 'failed' || status === 'rejected') return 'withdraw-status--failed';
    return 'withdraw-status--requested';
  }

  function renderWithdrawals(items) {
    var container = $('mod-withdrawals');
    if (!container) return;
    container.textContent = '';
    if (!items || items.length === 0) {
      var empty = document.createElement('p');
      empty.className = 'muted';
      empty.textContent = 'Nenhum saque solicitado.';
      container.appendChild(empty);
      return;
    }

    items.forEach(function (item) {
      var row = document.createElement('div');
      row.className = 'withdraw-row';

      var amount = document.createElement('span');
      amount.className = 'withdraw-row__amount';
      amount.textContent = brl(item.amount_cents);

      var date = document.createElement('span');
      date.className = 'withdraw-row__date';
      date.textContent = formatDate(item.created_at);

      var status = document.createElement('span');
      status.className = 'withdraw-row__status';
      var badge = document.createElement('span');
      badge.className = 'withdraw-status ' + statusClass(item.status);
      badge.textContent = statusLabel(item.status);
      status.appendChild(badge);

      row.appendChild(amount);
      row.appendChild(date);
      row.appendChild(status);

      if (item.failure_reason) {
        var reason = document.createElement('span');
        reason.className = 'withdraw-row__reason';
        reason.textContent = item.failure_reason;
        row.appendChild(reason);
      }
      container.appendChild(row);
    });
  }

  function updateConnectStatus(status) {
    connectStatus = status || 'not_started';
    var label = $('mod-connect-status');
    if (!label) return;
    var texts = {
      not_started: 'Configure sua conta Stripe ao solicitar o primeiro saque.',
      pending: 'Onboarding Stripe em andamento. Clique em “Sacar” para continuar.',
      complete: 'Conta Stripe configurada. Os saques vão direto para ela.',
      restricted: 'A Stripe pediu dados adicionais. Clique em “Sacar” para revisar.',
    };
    label.textContent = texts[connectStatus] || texts.pending;
  }

  function currentPanelLink(mod) {
    var code = numericCode;
    if (!code && mod && mod.link_id) code = '1' + mod.link_id;
    if (!code) return '';
    var base = String(config.siteUrl || window.location.origin).replace(/\/+$/, '');
    return base + '/' + code;
  }

  function showDashboard(data) {
    var mod = data.mod || {};
    var expectedLinkId = numericCode ? numericCode.slice(1) : '';
    if (expectedLinkId && mod.link_id && mod.link_id !== expectedLinkId) {
      throw new Error('Este token não corresponde ao link do Mod aberto.');
    }

    $('mod-access').hidden = true;
    $('mod-dashboard').hidden = false;
    $('mod-identity').textContent = mod.name
      ? mod.name + (mod.handle ? ' · @' + mod.handle : '')
      : 'Sua conta de Mod Parceiro';
    $('mod-affiliates').textContent = Number(data.recruited_hunters || 0).toLocaleString('pt-BR');
    $('mod-volume').textContent = brl(data.network_volume_cents);
    $('mod-earnings').textContent = brl(data.earnings_cents);
    $('mod-available').textContent = brl(data.available_cents);
    updateConnectStatus(
      mod.stripe_onboarding_status || (mod.stripe_account_id ? 'pending' : 'not_started'),
    );
    renderProfile(mod, data.profile_complete);
    renderWithdrawals(data.withdrawals);
  }

  function renderProfile(mod, complete) {
    profileComplete = Boolean(complete);
    var status = $('mod-profile-status');
    if (status) {
      status.textContent = profileComplete
        ? 'Nome cadastrado. Agora é só configurar a Stripe e clicar em Sacar.'
        : 'Informe seu nome completo para receber seus repasses. Dá para deixar para depois.';
    }
    var nameInput = $('mod-profile-name');
    var emailInput = $('mod-profile-email');
    if (nameInput && !nameInput.value) nameInput.value = mod.name || '';
    if (emailInput && !emailInput.value) emailInput.value = mod.email || '';
  }

  function saveProfile(event) {
    event.preventDefault();
    var feedback = $('mod-profile-feedback');
    var button = $('mod-profile-save');
    setFeedback(feedback, '', false);
    var payload = {
      name: String($('mod-profile-name').value || '').trim(),
      email: String($('mod-profile-email').value || '').trim(),
    };
    withLoading(button, function () {
      return api('/mods/profile', {
        method: 'POST',
        body: JSON.stringify(payload),
      }).then(function (data) {
        profileComplete = Boolean(data.profile_complete);
        if (data.name_already_used) {
          setFeedback(
            feedback,
            'Cadastro salvo. Já existe outro Mod com esse nome — tudo bem, o que vale é o nome que você informar na Stripe.',
            false,
          );
        } else {
          setFeedback(feedback, 'Cadastro salvo.', false);
        }
        showToast('Cadastro salvo');
        return loadDashboard();
      }).catch(function (error) {
        setFeedback(feedback, String(error.message || error), true);
      });
    });
  }

  function loadDashboard() {
    return api('/mods/me').then(function (data) {
      if (!data || !data.ok) throw new Error('Resposta inválida da API.');
      showDashboard(data);
      return data;
    });
  }

  function showAccess(message, isError) {
    $('mod-dashboard').hidden = true;
    $('mod-access').hidden = false;
    setFeedback($('mod-token-feedback'), message, isError);
  }

  function handleTokenSubmit(event) {
    event.preventDefault();
    var input = $('mod-token');
    var token = String(input.value || '').trim();
    if (!token) {
      setFeedback($('mod-token-feedback'), 'Cole o token do Mod para continuar.', true);
      return;
    }

    modToken = token;
    setFeedback($('mod-token-feedback'), 'Validando token…', false);
    withLoading($('mod-token-submit'), function () {
      return loadDashboard()
        .then(function () {
          saveModToken(token);
          input.value = '';
          setFeedback($('mod-token-feedback'), '', false);
        })
        .catch(function (error) {
          modToken = '';
          removeModToken();
          setFeedback($('mod-token-feedback'), String(error.message || error), true);
        });
    });
  }

  function startOnboarding(button) {
    setFeedback($('mod-withdraw-feedback'), '', false);
    return withLoading(button, function () {
      return api('/mods/stripe/onboarding', {
        method: 'POST',
        body: JSON.stringify({ idempotency_key: newIdempotencyKey('modonb') }),
      }).then(function (data) {
        if (!data || !data.account_link || !data.account_link.url) {
          throw new Error('A Stripe não retornou o link de configuração.');
        }
        updateConnectStatus(data.onboarding_status);
        window.location.assign(data.account_link.url);
      });
    });
  }

  /**
   * Um clique faz o saque: se a conta Stripe ainda não está configurada, abrimos
   * o onboarding hospedado e, ao voltar, o saque é concluído automaticamente.
   */
  function requestWithdrawal(options) {
    var opts = options || {};
    var button = $('mod-withdraw-button');
    setFeedback($('mod-withdraw-feedback'), '', false);

    if (!profileComplete) {
      setFeedback(
        $('mod-withdraw-feedback'),
        'Informe seu nome completo antes de sacar.',
        true,
      );
      var campo = $('mod-profile-name');
      if (campo && campo.focus) campo.focus();
      return;
    }

    if (connectStatus !== 'complete') {
      // Guarda a intenção: ao voltar da Stripe o saque segue sozinho.
      rememberPendingWithdrawal();
      startOnboarding(button).catch(function (error) {
        var status = error.status === 503
          ? 'O serviço de saques Stripe ainda não está disponível.'
          : 'Não foi possível abrir a configuração da Stripe: ' + String(error.message || error);
        setFeedback($('mod-withdraw-feedback'), status, true);
      });
      return;
    }

    withLoading(button, function () {
      return api('/mods/withdraw', {
        method: 'POST',
        body: JSON.stringify({ idempotency_key: pendingWithdrawalKey() }),
      }).then(function () {
        clearPendingWithdrawal();
        return loadDashboard();
      }).then(function () {
        setFeedback(
          $('mod-withdraw-feedback'),
          'Saque enviado para sua conta Stripe. O repasse segue o cronograma da Stripe.',
          false,
        );
        showToast('Saque enviado para sua conta Stripe');
      }).catch(function (error) {
        if (error.status === 409) {
          var codigo = error.data && error.data.code;
          if (codigo === 'name_mismatch') {
            clearPendingWithdrawal();
            setFeedback(
              $('mod-withdraw-feedback'),
              String(error.message || error),
              true,
            );
            return;
          }
          setFeedback(
            $('mod-withdraw-feedback'),
            'Sua configuração da Stripe ainda está incompleta. Abrindo a configuração novamente…',
            true,
          );
          rememberPendingWithdrawal();
          startOnboarding(button).catch(function (onboardingError) {
            setFeedback(
              $('mod-withdraw-feedback'),
              String(onboardingError.message || onboardingError),
              true,
            );
          });
          return;
        }
        if (error.status === 503) {
          setFeedback(
            $('mod-withdraw-feedback'),
            'O serviço de saques Stripe ainda não está disponível.',
            true,
          );
          return;
        }
        if (error.status === 401) {
          removeModToken();
          modToken = '';
          showAccess('Token inválido ou expirado. Cole o token atual para continuar.', true);
          return;
        }
        setFeedback($('mod-withdraw-feedback'), String(error.message || error), true);
      });
    });
  }

  function completeStripeOnboarding() {
    if (!modToken) return;
    api('/mods/stripe/onboarding/complete', {
      method: 'POST',
      body: JSON.stringify({}),
    }).then(function (data) {
      updateConnectStatus(data.onboarding_status);
      var completo = data.onboarding_status === 'complete';
      setFeedback(
        $('mod-withdraw-feedback'),
        completo
          ? 'Configuração da Stripe atualizada.'
          : 'A configuração da Stripe ainda precisa de dados adicionais.',
        !completo,
      );
      return loadDashboard().then(function () {
        // Retomada automática: se a pessoa clicou em Sacar antes de ir para a
        // Stripe, o saque segue agora, sem outro clique.
        if (completo && temPedidoPendente()) {
          requestWithdrawal({ resuming: true });
        }
      });
    }).catch(function (error) {
      setFeedback(
        $('mod-withdraw-feedback'),
        'Não foi possível atualizar a configuração da Stripe: ' + String(error.message || error),
        true,
      );
    });
  }

  function temPedidoPendente() {
    try {
      return Boolean(window.sessionStorage.getItem(PENDING_KEY));
    } catch (error) {
      return false;
    }
  }

  function init() {
    if (numericCode) {
      $('mod-code-box').hidden = false;
      $('mod-code-value').textContent = numericCode;
    }

    $('mod-token-form').addEventListener('submit', handleTokenSubmit);
    $('mod-profile-form').addEventListener('submit', saveProfile);
    $('mod-withdraw-button').addEventListener('click', requestWithdrawal);
    $('mod-copy-link').addEventListener('click', function () {
      var link = currentPanelLink();
      if (!link) {
        showToast('O link do painel ainda não está disponível.');
        return;
      }
      copyText(link);
    });

    var savedToken = readSession().m;
    if (savedToken) {
      modToken = String(savedToken).trim();
      loadDashboard().catch(function (error) {
        modToken = '';
        removeModToken();
        showAccess(String(error.message || error), true);
      });
    } else {
      showAccess('Cole o token do Mod para abrir este painel.', false);
    }

    if (params.get('stripe_connect_return') || params.get('stripe_connect_refresh')) {
      if (savedToken) completeStripeOnboarding();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
