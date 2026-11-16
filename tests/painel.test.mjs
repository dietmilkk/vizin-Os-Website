/**
 * Teste do painel público (/painel) rodando o assets/panel.js de verdade.
 *
 * Sobe a VPS (Bun) em uma porta livre, popula o banco com um cenário
 * realista e executa o JavaScript real da página contra um DOM mínimo.
 * Confere que todos os números aparecem na tela, no formato pt-BR, batendo
 * com o que a API devolveu — e que a página se recupera quando a API falha.
 *
 * Uso:
 *   node --test tests/painel.test.mjs
 *
 * Requer `bun` no PATH ou `npx --yes bun` disponível.
 */

import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import { spawn, spawnSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import http from 'node:http';
import net from 'node:net';
import vm from 'node:vm';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = join(HERE, '..');
const APP_DIR = process.env.VIZIN_APP_DIR || join(ROOT, '..', 'app');
const VPS_ENTRY = join(APP_DIR, 'vps', 'src', 'index.ts');
const PANEL_HTML = join(ROOT, 'painel', 'index.html');
const PANEL_JS = join(ROOT, 'assets', 'panel.js');

const DAY = 86_400;
const SEED_LIB = join(HERE, 'lib');

/**
 * Números esperados do cenário de teste, lidos do próprio seed (fonte única
 * da verdade): se o cenário mudar, o teste acompanha sem ajuste manual.
 */
function seedExpectations() {
  const script = [
    'import json, sys',
    `sys.path.insert(0, ${JSON.stringify(SEED_LIB)})`,
    'import seed_stats',
    'print(json.dumps({',
    '  "total": seed_stats.CONTAS_TOTAL,',
    '  "online_now": seed_stats.CONTAS_ONLINE,',
    '  "active_1h": seed_stats.CONTAS_ATIVAS_1H,',
    '  "active_24h": seed_stats.accounts_ativas(86400),',
    '  "active_7d": seed_stats.accounts_ativas(7 * 86400),',
    '  "active_30d": seed_stats.accounts_ativas(30 * 86400),',
    '  "new_24h": seed_stats.CONTAS_NOVAS_24H,',
    '  "new_7d": seed_stats.CONTAS_NOVAS_7D,',
    '}))',
  ].join('\n');
  const result = spawnSync('python3', ['-c', script], { encoding: 'utf8' });
  if (result.status !== 0) {
    throw new Error(`Falha ao ler o seed de teste: ${result.stderr || result.stdout}`);
  }
  return JSON.parse(result.stdout);
}
const BEACONS = JSON.stringify([
  {
    id: 'vps-br',
    url: 'https://beacon.br.example.com',
    pubkey: '0'.repeat(64),
    geohash: 'g8u4y',
  },
  {
    id: 'vps-global',
    url: 'https://beacon.global.example.com',
    pubkey: '0'.repeat(64),
    geohash: '*',
  },
]);

/* ------------------------------------------------------------------ */
/* Infraestrutura: subir a API real                                   */
/* ------------------------------------------------------------------ */

function bunCommand() {
  const direct = spawnSync('sh', ['-lc', 'command -v bun'], { encoding: 'utf8' });
  if (direct.status === 0 && direct.stdout.trim()) return [direct.stdout.trim()];
  return ['npx', '--yes', 'bun'];
}

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
  });
}

async function waitForHealth(port, child, timeoutMs = 120_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) {
      throw new Error(`A VPS encerrou antes de ficar pronta (código ${child.exitCode}).`);
    }
    try {
      const response = await fetch(`http://127.0.0.1:${port}/health`);
      if (response.ok) return;
    } catch {
      /* ainda subindo */
    }
    await new Promise((resolve) => setTimeout(resolve, 400));
  }
  throw new Error(`A VPS não respondeu /health em ${timeoutMs / 1000}s.`);
}

let api = null;
let dataDir = null;
let server = null;
let esperado = null;

before(async () => {
  const { existsSync } = await import('node:fs');
  if (!existsSync(VPS_ENTRY)) {
    throw new Error(`Não encontrei a entrada da VPS em ${VPS_ENTRY} (use VIZIN_APP_DIR).`);
  }

  dataDir = mkdtempSync(join(tmpdir(), 'vizin-painel-'));
  const port = await freePort();

  const [bun, ...bunArgs] = bunCommand();
  server = spawn(bun, bunArgs.concat(['run', VPS_ENTRY]), {
    cwd: join(APP_DIR, 'vps'),
    env: {
      ...process.env,
      PORT: String(port),
      DATA_DIR: dataDir,
      BEACONS_JSON: BEACONS,
      ACCOUNT_INACTIVE_SECONDS: String(365 * DAY),
      ACCOUNT_DELETE_SECONDS: String(365 * DAY),
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  server.stdout.on('data', () => {});
  server.stderr.on('data', () => {});

  await waitForHealth(port, server);

  const seed = spawnSync(
    'python3',
    [join(HERE, 'lib', 'seed_stats.py'), join(dataDir, 'vizin.sqlite')],
    { encoding: 'utf8' },
  );
  if (seed.status !== 0) {
    throw new Error(`Falha ao popular o banco de teste: ${seed.stderr || seed.stdout}`);
  }

  const response = await fetch(`http://127.0.0.1:${port}/stats/public`);
  api = { url: `http://127.0.0.1:${port}`, data: await response.json() };
  esperado = seedExpectations();
});

after(() => {
  if (server) {
    server.kill('SIGTERM');
  }
  if (dataDir) {
    rmSync(dataDir, { recursive: true, force: true });
  }
});

/* ------------------------------------------------------------------ */
/* DOM mínimo para rodar o panel.js                                   */
/* ------------------------------------------------------------------ */

class FakeClassList {
  constructor() {
    this.items = new Set();
  }
  add(name) {
    this.items.add(name);
  }
  remove(name) {
    this.items.delete(name);
  }
  contains(name) {
    return this.items.has(name);
  }
}

class FakeElement {
  constructor(tag = 'div') {
    this.tagName = tag.toUpperCase();
    this.textContent = '';
    this.title = '';
    this.hidden = false;
    this.disabled = false;
    this.className = '';
    this.classList = new FakeClassList();
    this.childNodes = [];
    this.attributes = {};
    this.listeners = {};
  }
  get innerHTML() {
    return this._innerHTML ?? '';
  }
  set innerHTML(value) {
    this._innerHTML = String(value);
    if (value === '') this.childNodes = [];
  }
  appendChild(child) {
    this.childNodes.push(child);
    return child;
  }
  addEventListener(type, handler) {
    (this.listeners[type] ||= []).push(handler);
  }
  click() {
    for (const handler of this.listeners.click ?? []) handler();
  }
}

function buildDom(ids) {
  const elements = new Map();
  for (const id of ids) elements.set(id, new FakeElement());
  const requested = [];

  const document = {
    getElementById(id) {
      requested.push(id);
      if (!elements.has(id)) elements.set(id, new FakeElement());
      return elements.get(id);
    },
    createElement(tag) {
      return new FakeElement(tag);
    },
  };

  return { document, elements, requested };
}

function htmlIds() {
  const html = readFileSync(PANEL_HTML, 'utf8');
  return [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
}

/**
 * Executa o panel.js real contra um DOM mínimo e devolve os elementos.
 * `apiUrl` aponta para a API; o script é avaliado no contexto global.
 */
async function runPanel(apiUrl) {
  const ids = htmlIds();
  const { document, elements, requested } = buildDom(ids);

  const previous = {
    window: globalThis.window,
    document: globalThis.document,
    setInterval: globalThis.setInterval,
  };
  const nativeSetInterval = globalThis.setInterval;

  globalThis.window = { VIZINHANCA_CONFIG: { apiUrl } };
  globalThis.document = document;

  const timers = [];
  globalThis.setInterval = (fn, delay) => {
    timers.push({ fn, delay });
    const handle = nativeSetInterval(() => {}, 2 ** 31 - 1);
    handle.unref?.();
    return handle;
  };

  try {
    const source = readFileSync(PANEL_JS, 'utf8');
    vm.runInThisContext(source, { filename: PANEL_JS });

    // Espera a primeira busca terminar.
    const deadline = Date.now() + 20_000;
    while (Date.now() < deadline) {
      const status = elements.get('painelStatusTexto');
      if (status && /Atualizado|Sem dados/.test(status.textContent)) break;
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    return { elements, requested, timers };
  } finally {
    globalThis.window = previous.window;
    globalThis.document = previous.document;
    globalThis.setInterval = previous.setInterval;
  }
}

const fmtInt = (value) => new Intl.NumberFormat('pt-BR').format(Number(value) || 0);

/* ------------------------------------------------------------------ */
/* API de produção sem /stats/public (modo público do painel)          */
/* ------------------------------------------------------------------ */

/**
 * Reproduz o que a VPS em produção responde hoje: a rota /stats/public ainda
 * não existe, mas as rotas públicas /health, /beacons, /account/policy e
 * /signup-guard respondem normalmente.
 */
function startStubApi() {
  const server = http.createServer((request, response) => {
    const url = new URL(request.url, 'http://127.0.0.1');
    const send = (status, body) => {
      response.writeHead(status, { 'content-type': 'application/json' });
      response.end(JSON.stringify(body));
    };
    if (url.pathname === '/stats/public') {
      send(404, { ok: false, error: 'rota não encontrada' });
      return;
    }
    if (url.pathname === '/health') {
      send(200, {
        ok: true,
        service: 'vizin-vps',
        version: '1',
        registry: true,
        accounts: true,
        payments: true,
        referrals: true,
        hunters: true,
        vault: true,
        mail: { transport: 'api', configured: false },
      });
      return;
    }
    if (url.pathname === '/beacons') {
      send(200, {
        beacons: [
          {
            id: 'vps1',
            url: 'https://beacon.188.166.156.109.sslip.io',
            pubkey: '0'.repeat(64),
            geohash: '*',
          },
        ],
      });
      return;
    }
    if (url.pathname === '/account/policy') {
      send(200, {
        ok: true,
        inactive_after_seconds: 604800,
        delete_after_seconds: 2592000,
        recoverable: true,
      });
      return;
    }
    if (url.pathname === '/signup-guard') {
      send(200, { ok: true, allowed: true, blocked: false, reason: null, message: '' });
      return;
    }
    send(404, { ok: false, error: 'rota não encontrada' });
  });
  return new Promise((resolve) => {
    server.listen(0, '127.0.0.1', () => {
      resolve({ server, url: `http://127.0.0.1:${server.address().port}` });
    });
  });
}

/* ------------------------------------------------------------------ */
/* Testes                                                              */
/* ------------------------------------------------------------------ */

test('a API de teste responde com o cenário completo', () => {
  assert.ok(api, 'a API não foi iniciada');
  assert.equal(api.data.ok, true);
  assert.equal(api.data.accounts.total, esperado.total);
  assert.equal(api.data.accounts.online_now, esperado.online_now);
  assert.equal(api.data.accounts.active_1h, esperado.active_1h);
  assert.equal(api.data.accounts.active_24h, esperado.active_24h);
  assert.equal(api.data.accounts.active_7d, esperado.active_7d);
  assert.equal(api.data.accounts.active_30d, esperado.active_30d);
  assert.equal(api.data.accounts.new_24h, esperado.new_24h);
  assert.equal(api.data.accounts.new_7d, esperado.new_7d);
  assert.ok(api.data.accounts.newest_created_at > 0, 'a conta mais recente precisa de data');
  assert.ok(api.data.server.service_started_at > 0, 'o inicio do servico precisa de data');
  assert.ok(
    api.data.server.uptime_seconds > api.data.server.process_uptime_seconds,
    'o uptime do servico tem de ser maior que o do processo',
  );
  assert.equal(api.data.accounts.with_username, 1);
  assert.equal(api.data.accounts.deleted_total, 1);
  assert.equal(api.data.network.beacons, 2);
  assert.deepEqual(api.data.network.regions, ['*', 'g8u4y']);
  assert.equal(api.data.partners.creators, 2);
  assert.equal(api.data.partners.hunters, 1);
  assert.equal(api.data.partners.creators_contacted, 3);
  assert.equal(api.data.partners.referrals_total, 2);
  assert.equal(api.data.partners.referrals_active, 1);
  assert.equal(api.data.partners.earnings, 1);
  assert.equal(api.data.vaults.backups, 2);
});

test('todo id lido pelo panel.js existe na página /painel', () => {
  const ids = new Set(htmlIds());
  const source = readFileSync(PANEL_JS, 'utf8');
  const used = new Set([
    ...[...source.matchAll(/getElementById\("([^"]+)"\)/g)].map((m) => m[1]),
    ...[...source.matchAll(/setText\(\s*"([^"]+)"/g)].map((m) => m[1]),
  ]);
  assert.ok(used.size > 10, 'o panel.js deveria ler vários ids');
  for (const id of used) {
    assert.ok(ids.has(id), `o id "${id}" usado pelo panel.js não existe em painel/index.html`);
  }
});

test('o painel preenche todos os números com o que a API devolveu', async () => {
  const { elements } = await runPanel(api.url);
  const stats = api.data;

  const expected = {
    painelOnline: fmtInt(stats.accounts.online_now),
    painelAtivos1h: fmtInt(stats.accounts.active_1h),
    painelAtivos24: fmtInt(stats.accounts.active_24h),
    painelAtivos7: fmtInt(stats.accounts.active_7d),
    painelAtivos30: fmtInt(stats.accounts.active_30d),
    painelRegioes: fmtInt(stats.network.regions.length),
    painelBeacons: fmtInt(stats.network.beacons),
    painelContas: fmtInt(stats.accounts.total),
    painelNovas24h: fmtInt(stats.accounts.new_24h),
    painelNovas7d: fmtInt(stats.accounts.new_7d),
    painelUsernames: fmtInt(stats.accounts.with_username),
    painelApagadas: fmtInt(stats.accounts.deleted_total),
    painelCofres: fmtInt(stats.vaults.backups),
    painelCriadores: fmtInt(stats.partners.creators),
    painelAfiliados: fmtInt(stats.partners.hunters),
    painelProgramaTotal: fmtInt(
      stats.partners.earnings + stats.partners.payouts_paid + stats.partners.payouts_hunter_paid,
    ),
    painelIndicacoes: `${fmtInt(stats.partners.referrals_active)} de ${fmtInt(stats.partners.referrals_total)}`,
    painelComissoes: fmtInt(stats.partners.earnings),
    painelSaques: fmtInt(stats.partners.payouts_paid + stats.partners.payouts_hunter_paid),
    painelRuntime: `Bun ${stats.server.runtime_version}`,
  };

  for (const [id, value] of Object.entries(expected)) {
    const element = elements.get(id);
    assert.ok(element, `faltou o elemento #${id}`);
    assert.equal(element.textContent, value, `#${id} deveria mostrar "${value}"`);
  }
});

test('nenhum campo fica com o placeholder "—" depois da carga', async () => {
  const { elements } = await runPanel(api.url);
  const ids = [
    'painelOnline',
    'painelAtivos1h',
    'painelAtivos24',
    'painelAtivos7',
    'painelAtivos30',
    'painelRegioes',
    'painelBeacons',
    'painelUptime',
    'painelMemoria',
    'painelCpu',
    'painelBanco',
    'painelRuntime',
    'painelContas',
    'painelContaRecente',
    'painelOnlineLegenda',
    'painelNovas24h',
    'painelNovas7d',
    'painelUsernames',
    'painelUsernamesLegenda',
    'painelApagadas',
    'painelCofres',
    'painelCofresLegenda',

    'painelCriadores',
    'painelAfiliados',
    'painelProgramaTotal',
    'painelIndicacoes',
    'painelComissoes',
    'painelSaques',
  ];
  for (const id of ids) {
    const text = elements.get(id)?.textContent ?? '';
    assert.notEqual(text.trim(), '—', `#${id} ficou sem valor`);
    assert.ok(text.trim().length > 0, `#${id} ficou vazio`);
  }
});

test('a página mostra o estado de atualização e nenhum erro', async () => {
  const { elements } = await runPanel(api.url);
  const status = elements.get('painelStatusTexto');
  assert.match(status.textContent, /^Atualizado/, 'a barra de status deveria anunciar a atualização');
  assert.doesNotMatch(
    status.textContent,
    /atualiza sozinho a cada minuto/,
    'a barra de status deveria ser curta',
  );
  assert.equal(elements.get('painelErro').hidden, true, 'o aviso de erro deveria ficar escondido');
  assert.equal(elements.get('painelStatus').classList.contains('panel-status--erro'), false);
});

test('a página é minimalista: sem selo de modo, sem etiquetas e sem aviso', () => {
  const ids = new Set(htmlIds());
  for (const id of ['painelModo', 'painelResumo', 'painelAviso']) {
    assert.equal(ids.has(id), false, `o painel não deveria mostrar "${id}"`);
  }
  const html = readFileSync(PANEL_HTML, 'utf8');
  assert.doesNotMatch(html, /nunca mostra/, 'o painel não deveria explicar o que não mostra');
});

test('as regiões e os criadores contatados viram etiquetas', async () => {
  const { elements } = await runPanel(api.url);

  const regioes = elements.get('painelRegioesLista').childNodes.map((node) => node.textContent);
  assert.equal(regioes.length, api.data.network.regions.length);
  assert.ok(regioes.includes('Global (todas as regiões)'), 'a região global deveria aparecer');
  assert.ok(regioes.includes('g8u4y'), 'a região do beacon deveria aparecer');

  const contatos = elements.get('painelContatosLista').childNodes.map((node) => node.textContent);
  assert.equal(contatos.length, api.data.partners.recent_contacts.length);
  for (const contact of api.data.partners.recent_contacts) {
    assert.ok(contatos.includes(contact.handle), `o @ ${contact.handle} deveria aparecer`);
  }
  assert.ok(
    contatos.every((text) => text.startsWith('@')),
    'as etiquetas de contato devem mostrar o @, não a URL',
  );
});

test('o painel nao tem botao manual: atualiza sozinho a cada minuto', async () => {
  const html = readFileSync(PANEL_HTML, 'utf8');
  assert.doesNotMatch(html, /id="painelAtualizar"/, 'o painel nao deveria ter botao de atualizar');

  const { timers } = await runPanel(api.url);
  const timer = timers.find((item) => item.delay === 60_000);
  assert.ok(timer, 'o painel.js deveria agendar a atualizacao automatica');
  assert.equal(typeof timer.fn, 'function', 'o agendamento deveria chamar a coleta');
});

test('a página se recupera e avisa quando a API está fora do ar', async () => {
  const { elements } = await runPanel('http://127.0.0.1:1');
  assert.equal(elements.get('painelErro').hidden, false, 'deveria mostrar o aviso de erro');
  assert.match(elements.get('painelErro').textContent, /Não foi possível obter os dados/i);
  assert.equal(elements.get('painelStatusTexto').textContent, 'Sem dados no momento');
  assert.equal(elements.get('painelStatus').classList.contains('panel-status--erro'), true);
});

/* ------------------------------------------------------------------ */
/* Modo público: quando a API ainda não tem /stats/public              */
/* ------------------------------------------------------------------ */

test('sem /stats/public o painel mostra os dados públicos que existem', async () => {
  const stub = await startStubApi();
  try {
    const { elements } = await runPanel(stub.url);

    assert.equal(elements.get('painelErro').hidden, true, 'não deveria mostrar erro');
    assert.match(
      elements.get('painelStatusTexto').textContent,
      /^Atualizado/,
      'a barra de status deveria anunciar a atualização',
    );
    assert.equal(elements.get('painelStatusTexto').textContent, 'Atualizado agora');

    assert.equal(elements.get('painelBeacons').textContent, '1', 'deveria contar o beacon público');
    assert.equal(elements.get('painelRegioes').textContent, 'Global');
    assert.notEqual(elements.get('painelLatencia').textContent.trim(), '—');

    const regioes = elements.get('painelRegioesLista').childNodes.map((node) => node.textContent);
    assert.deepEqual(regioes, ['Global (todas as regiões)']);
  } finally {
    stub.server.close();
  }
});

test('no modo público os campos que a API não informa ficam vazios, não inventados', async () => {
  const stub = await startStubApi();
  try {
    const { elements } = await runPanel(stub.url);
    for (const id of [
      'painelOnline',
      'painelAtivos1h',
      'painelAtivos24',
      'painelAtivos7',
      'painelAtivos30',
      'painelUptime',
      'painelMemoria',
      'painelCpu',
      'painelBanco',
      'painelContas',
      'painelContaRecente',
      'painelNovas24h',
      'painelNovas7d',
      'painelUsernames',
      'painelApagadas',
      'painelCofres',
      'painelCriadores',
      'painelAfiliados',
      'painelProgramaTotal',
      'painelIndicacoes',
      'painelComissoes',
      'painelSaques',
    ]) {
      const text = (elements.get(id)?.textContent ?? '').trim();
      // No DOM de teste o texto inicial do HTML não existe; no navegador, o
      // campo já vem com "—". Nos dois casos não pode haver número inventado.
      assert.ok(
        text === '' || text === '—',
        `#${id} não deveria inventar valor no modo público (veio '${text}')`,
      );
    }
  } finally {
    stub.server.close();
  }
});

test('quando a API inteira está fora do ar, o painel avisa e não inventa número', async () => {
  const stub = await startStubApi();
  const url = stub.url;
  await new Promise((resolve) => stub.server.close(resolve));
  const { elements } = await runPanel(url);
  assert.equal(elements.get('painelErro').hidden, false, 'deveria mostrar o aviso de erro');
  assert.match(elements.get('painelErro').textContent, /Não foi possível obter os dados/i);
  assert.equal(elements.get('painelStatusTexto').textContent, 'Sem dados no momento');
});
