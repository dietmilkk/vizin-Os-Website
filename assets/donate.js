(function () {
  'use strict';

  var config = window.VIZINHANCA_CONFIG || {};
  var form = document.getElementById('donation-form');
  if (!form) return;

  var amountInput = document.getElementById('donation-amount');
  var currencyInput = document.getElementById('donation-currency');
  var submit = document.getElementById('donation-submit');
  var message = document.getElementById('donation-message');
  var result = document.getElementById('donation-result');
  var minorUnits = { brl: 2, usd: 2, eur: 2, gbp: 2, jpy: 0, cad: 2, aud: 2 };

  function setMessage(text, tone) {
    if (!message) return;
    message.textContent = text || '';
    message.className = 'donation-message' + (tone ? ' is-' + tone : '');
  }

  function newIdempotencyKey() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
      return window.crypto.randomUUID();
    }
    var bytes = new Uint8Array(16);
    if (window.crypto && typeof window.crypto.getRandomValues === 'function') {
      window.crypto.getRandomValues(bytes);
    } else {
      for (var i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256);
    }
    return Array.prototype.map
      .call(bytes, function (byte) {
        return byte.toString(16).padStart(2, '0');
      })
      .join('');
  }

  function pendingKey(currency, amountMinor) {
    var key = 'vizin.donation.idempotency';
    var fingerprint = currency + ':' + amountMinor;
    try {
      var stored = JSON.parse(window.sessionStorage.getItem(key) || 'null');
      if (stored && stored.fingerprint === fingerprint) return stored.value;
      var value = newIdempotencyKey();
      window.sessionStorage.setItem(key, JSON.stringify({ fingerprint: fingerprint, value: value }));
      return value;
    } catch (error) {
      return newIdempotencyKey();
    }
  }

  function clearPendingKey() {
    try {
      window.sessionStorage.removeItem('vizin.donation.idempotency');
    } catch (error) {
      // A repeated submission can still be protected by the disabled button.
    }
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    var currency = currencyInput.value.toLowerCase();
    var major = Number(amountInput.value);
    var exponent = minorUnits[currency];
    if (!Number.isFinite(major) || typeof exponent !== 'number') {
      setMessage('Digite um valor válido.', 'error');
      return;
    }
    var amountMinor = Math.round(major * Math.pow(10, exponent));
    if (amountMinor < 50) {
      setMessage('O valor mínimo é 0,50 na moeda escolhida.', 'error');
      return;
    }

    submit.disabled = true;
    submit.classList.add('is-loading');
    setMessage('Abrindo o checkout seguro…');

    fetch(config.apiUrl + '/stripe/checkout/donation', {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'application/json' },
      body: JSON.stringify({
        amount_minor: amountMinor,
        currency: currency,
        source: 'site',
        idempotency_key: pendingKey(currency, amountMinor),
      }),
    })
      .then(function (response) {
        return response.json().then(function (data) {
          if (!response.ok || !data.checkout_url) {
            throw new Error((data && data.error) || 'Não foi possível abrir o pagamento.');
          }
          return data;
        });
      })
      .then(function (data) {
        clearPendingKey();
        window.location.assign(data.checkout_url);
      })
      .catch(function (error) {
        submit.disabled = false;
        submit.classList.remove('is-loading');
        setMessage(error.message || 'Não foi possível abrir o pagamento. Tente novamente.', 'error');
      });
  });

  var params = new URLSearchParams(window.location.search);
  var status = params.get('status');
  var reference = params.get('reference');
  if (!result) return;

  if (status === 'cancelled') {
    result.hidden = false;
    result.innerHTML =
      '<strong>Pagamento cancelado.</strong><span>Nada foi cobrado. Você pode voltar quando quiser.</span>';
    return;
  }
  if (status !== 'success') return;

  result.hidden = false;
  result.innerHTML =
    '<strong>Recebemos seu retorno.</strong><span>Confirmando o pagamento com a Stripe…</span>';
  if (!reference) {
    result.innerHTML =
      '<strong>Pagamento em análise.</strong><span>Se a cobrança foi aprovada, você receberá o recibo por e-mail.</span>';
    return;
  }

  var attempts = 0;
  var poll = function () {
    fetch(config.apiUrl + '/stripe/checkouts/' + encodeURIComponent(reference), {
      headers: { accept: 'application/json' },
    })
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        if (data && data.status === 'approved') {
          result.innerHTML =
            '<strong>Doação confirmada.</strong><span>Obrigado por apoiar o vizin.Os!</span>';
          return;
        }
        if (data && (data.status === 'rejected' || data.status === 'cancelled')) {
          result.innerHTML =
            '<strong>Pagamento não concluído.</strong><span>Nada foi cobrado. Você pode tentar novamente.</span>';
          return;
        }
        attempts += 1;
        if (attempts < 20) window.setTimeout(poll, 1500);
        else
          result.innerHTML =
            '<strong>Pagamento em análise.</strong><span>Se a cobrança foi aprovada, você receberá o recibo por e-mail.</span>';
      })
      .catch(function () {
        attempts += 1;
        if (attempts < 20) window.setTimeout(poll, 2000);
      });
  };
  poll();
})();
