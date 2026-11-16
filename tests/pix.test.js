'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const pix = require('../assets/pix.js');

test('CRC-16/CCITT-FALSE tem o valor de verificação conhecido', () => {
  assert.equal(pix.crc16('123456789'), '29B1');
});

test('gera um payload PIX com valor e campos obrigatórios', () => {
  const payload = pix.buildPayload({
    key: 'vizin-os@proton.me',
    merchant: 'VIZINHANCA',
    city: 'SAO PAULO',
    amount: 10,
    txid: 'VIZINHANCA',
  });

  assert.match(payload, /^000201/);
  assert.match(payload, /5303986/);
  assert.match(payload, /540510\.00/);
  assert.match(payload, /5802BR/);
  assert.match(payload, /5910VIZINHANCA/);
  assert.match(payload, /6009SAO PAULO/);
  assert.match(payload, /6304[0-9A-F]{4}$/);
  assert.equal(payload.slice(-4), pix.crc16(payload.slice(0, -4)));
});

test('omite o campo de valor quando não há valor definido', () => {
  const payload = pix.buildPayload({
    key: 'vizin-os@proton.me',
    merchant: 'VIZINHANCA',
    city: 'SAO PAULO',
  });
  assert.doesNotMatch(payload, /5405/);
  assert.equal(payload.slice(-4), pix.crc16(payload.slice(0, -4)));
});

test('normaliza valores e rejeita valores inválidos', () => {
  assert.equal(pix.normalizeAmount('12,5'), null);
  assert.equal(pix.normalizeAmount(12.5), '12.50');
  assert.equal(pix.normalizeAmount(0), null);
  assert.equal(pix.normalizeAmount(-3), null);
});

test('remove acentos e caracteres inválidos do nome do recebedor', () => {
  const payload = pix.buildPayload({
    key: 'vizin-os@proton.me',
    merchant: 'Vizinhança & Cia.',
    city: 'São Paulo',
    amount: 25,
  });
  assert.match(payload, /5915VIZINHANCA CIA\./);
  assert.match(payload, /6009SAO PAULO/);
});
