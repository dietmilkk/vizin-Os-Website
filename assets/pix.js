/**
 * Gerador de PIX Copia e Cola (BR Code / EMV).
 * Sem dependências e sem rede: o código é montado no próprio navegador.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.VizinhancaPix = factory();
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  function tlv(id, value) {
    var text = String(value);
    if (text.length > 99) throw new Error('Campo PIX muito longo: ' + id);
    return id + String(text.length).padStart(2, '0') + text;
  }

  function crc16(payload) {
    var crc = 0xffff;
    for (var i = 0; i < payload.length; i += 1) {
      crc ^= payload.charCodeAt(i) << 8;
      for (var bit = 0; bit < 8; bit += 1) {
        crc = crc & 0x8000 ? ((crc << 1) ^ 0x1021) & 0xffff : (crc << 1) & 0xffff;
      }
    }
    return crc.toString(16).toUpperCase().padStart(4, '0');
  }

  function clean(text, max) {
    return String(text || '')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^A-Za-z0-9 .-]/g, '')
      .replace(/\s+/g, ' ')
      .trim()
      .slice(0, max)
      .toUpperCase();
  }

  function normalizeAmount(amount) {
    var value = Number(amount);
    if (!Number.isFinite(value) || value <= 0) return null;
    return value.toFixed(2);
  }

  function buildPayload(options) {
    var opts = options || {};
    var key = String(opts.key || '').trim();
    if (!key) throw new Error('Chave PIX obrigatória.');

    var merchant = clean(opts.merchant || 'VIZINHANCA', 25) || 'VIZINHANCA';
    var city = clean(opts.city || 'SAO PAULO', 15) || 'SAO PAULO';
    var txid = String(opts.txid || '***')
      .replace(/[^A-Za-z0-9]/g, '')
      .slice(0, 25) || '***';
    var amount = normalizeAmount(opts.amount);

    var account = tlv('00', 'BR.GOV.BCB.PIX') + tlv('01', key);
    var payload =
      tlv('00', '01') +
      tlv('26', account) +
      tlv('52', '0000') +
      tlv('53', '986') +
      (amount ? tlv('54', amount) : '') +
      tlv('58', 'BR') +
      tlv('59', merchant) +
      tlv('60', city) +
      tlv('62', tlv('05', txid)) +
      '6304';

    return payload + crc16(payload);
  }

  return {
    buildPayload: buildPayload,
    crc16: crc16,
    tlv: tlv,
    normalizeAmount: normalizeAmount,
  };
});
