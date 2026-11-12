/**
 * Limpeza dos dados de teste na VPS.
 *
 * Apaga as contas de partners criadas pelos testes (criador, afiliado),
 * as referencias, os contatos registrados e os saques de teste. Como cada
 * conta de parceiro libera um endereco de IP (tabelas `signup_ips` e
 * `signup_ip_kinds`), as linhas desses mesmos registros tambem saem — senao o
 * IP ficaria bloqueado para sempre mesmo depois da conta apagada.
 *
 * Nunca toca em `accounts`, `vaults` nem `kv`.
 *
 * Uso na VPS:
 *   sudo -u vizin bun run tools/limpar-teste-vps.ts            # mostra o que faria
 *   sudo -u vizin bun run tools/limpar-teste-vps.ts --aplicar  # aplica
 *
 *   sudo -u vizin bun run tools/limpar-teste-vps.ts --ip 45.4.58.93 --aplicar
 *
 * A opcao `--ip` apaga tambem as contas criadas a partir de um endereco de
 * rede. Ela existe porque os codigos das contas sao aleatorios (a plataforma
 * os gera no navegador), entao o prefixo de teste nem sempre identifica quem
 * o teste criou — o IP sim, ja que a guarda permite uma conta por papel e
 * endereco.
 */

import { Database } from 'bun:sqlite';

const DB_PATH = process.env.DB_PATH ?? '/var/lib/vizin-api/vizin.sqlite';
const aplicar = process.argv.includes('--aplicar');

// --ip <endereco>: apaga as contas registradas a partir deste IP.
const argIp = process.argv.indexOf('--ip');
const ipTeste = argIp >= 0 ? String(process.argv[argIp + 1] ?? '').trim() : '';

// Contas de teste: nome/handle/codigo com o prefixo usado pelos testes do site.
// USR/USRREAL vem de tests/test-usuario-real.py (handle carimbado no navegador).
const PADRAO_TESTE = /^(TEST|TST|AU|TP|TL|TG|TK|TB|TC|TF|FH|FC|SH|GP|MZ|MW|OV|USR|USRREAL)/i;

const db = new Database(DB_PATH);
db.exec('PRAGMA foreign_keys = OFF;');

function idsTeste(tabela: string, colunas: string[]): string[] {
  const linhas = db
    .query(`SELECT id, ${colunas.join(', ')} FROM ${tabela}`)
    .all() as Record<string, string>[];
  const ids = new Set<string>();
  for (const linha of linhas) {
    const combina = colunas.some(
      (coluna) => typeof linha[coluna] === 'string' && PADRAO_TESTE.test(linha[coluna]),
    );
    if (combina) ids.add(linha.id);
  }
  return [...ids];
}

/** Contas de parceiro registradas a partir de um endereco de rede. */
function idsPorIp(tabela: string, ip: string): string[] {
  if (!ip) return [];
  const linhas = db
    .query(`SELECT entity_id AS id FROM signup_ip_kinds WHERE ip = ?`)
    .all(ip) as { id: string | null }[];
  const ids = new Set<string>();
  for (const linha of linhas) {
    if (!linha.id) continue;
    const existe = db
      .query(`SELECT id FROM ${tabela} WHERE id = ?`)
      .get(linha.id) as { id: string } | null;
    if (existe) ids.add(existe.id);
  }
  return [...ids];
}

const hunters = [
  ...new Set([...idsTeste('hunters', ['name', 'handle', 'code']), ...idsPorIp('hunters', ipTeste)]),
];
const creators = [
  ...new Set([...idsTeste('creators', ['name', 'handle', 'code']), ...idsPorIp('creators', ipTeste)]),
];

if (ipTeste) {
  console.log(`Filtro por IP: ${ipTeste}`);
}

const remover = (sql: string, params: unknown[]): number => {
  const antes = db.query(sql.replace('DELETE', 'SELECT COUNT(*) AS n')).get(...params) as
    | { n: number }
    | null;
  const total = antes ? Number(antes.n) || 0 : 0;
  if (aplicar && total > 0) db.query(sql).run(...params);
  return total;
};

const plano: { tabela: string; total: number }[] = [];

plano.push({
  tabela: 'hunter_withdrawal_audit',
  total: remover(
    `DELETE FROM hunter_withdrawal_audit WHERE withdrawal_id IN (SELECT id FROM hunter_withdrawals WHERE hunter_id IN (${hunters.map(() => '?').join(',') || "''"}))`,
    hunters,
  ),
});
plano.push({
  tabela: 'hunter_withdrawals',
  total: remover(
    `DELETE FROM hunter_withdrawals WHERE hunter_id IN (${hunters.map(() => '?').join(',') || "''"})`,
    hunters,
  ),
});
plano.push({
  tabela: 'hunter_emails',
  total: remover(
    `DELETE FROM hunter_emails WHERE hunter_id IN (${hunters.map(() => '?').join(',') || "''"})`,
    hunters,
  ),
});
plano.push({
  tabela: 'outreach_creators',
  total: remover(
    `DELETE FROM outreach_creators WHERE hunter_id IN (${hunters.map(() => '?').join(',') || "''"})`,
    hunters,
  ),
});
plano.push({
  tabela: 'referral_earnings',
  total: remover(
    `DELETE FROM referral_earnings WHERE creator_id IN (${creators.map(() => '?').join(',') || "''"}) OR hunter_id IN (${hunters.map(() => '?').join(',') || "''"})`,
    [...creators, ...hunters],
  ),
});
plano.push({
  tabela: 'withdrawal_audit',
  total: remover(
    `DELETE FROM withdrawal_audit WHERE withdrawal_id IN (SELECT id FROM withdrawals WHERE creator_id IN (${creators.map(() => '?').join(',') || "''"}))`,
    creators,
  ),
});
plano.push({
  tabela: 'withdrawals',
  total: remover(
    `DELETE FROM withdrawals WHERE creator_id IN (${creators.map(() => '?').join(',') || "''"})`,
    creators,
  ),
});
plano.push({
  tabela: 'referrals',
  total: remover(
    `DELETE FROM referrals WHERE creator_id IN (${creators.map(() => '?').join(',') || "''"})`,
    creators,
  ),
});
// O IP e liberado junto com a conta: o bloqueio de IP duplicado vale para a
// conta que existe, nao para o endereco de rede para sempre. As duas
// tabelas precisam sair — a guarda consulta `signup_ip_kinds`, que guarda o
// papel (criador ou afiliado) ocupado por cada endereco.
plano.push({
  tabela: 'signup_ips',
  total: remover(
    `DELETE FROM signup_ips WHERE entity_id IN (${[...hunters, ...creators].map(() => '?').join(',') || "''"})`,
    [...hunters, ...creators],
  ),
});
plano.push({
  tabela: 'signup_ip_kinds',
  total: remover(
    `DELETE FROM signup_ip_kinds WHERE entity_id IN (${[...hunters, ...creators].map(() => '?').join(',') || "''"})`,
    [...hunters, ...creators],
  ),
});
plano.push({
  tabela: 'hunters',
  total: remover(`DELETE FROM hunters WHERE id IN (${hunters.map(() => '?').join(',') || "''"})`, hunters),
});
plano.push({
  tabela: 'creators',
  total: remover(
    `DELETE FROM creators WHERE id IN (${creators.map(() => '?').join(',') || "''"})`,
    creators,
  ),
});
// Registros de IP sem conta correspondente (a conta ja tinha sido apagada em
// uma execucao anterior, mas o registro ficou). Sem esta limpeza o endereco
// continua bloqueado para aquele papel, mesmo sem existir conta nenhuma.
plano.push({
  tabela: 'signup_ips orfas',
  total: remover(
    `DELETE FROM signup_ips WHERE entity_id IS NULL OR (kind = 'hunter' AND entity_id NOT IN (SELECT id FROM hunters)) OR (kind = 'creator' AND entity_id NOT IN (SELECT id FROM creators))`,
    [],
  ),
});
plano.push({
  tabela: 'signup_ip_kinds orfas',
  total: remover(
    `DELETE FROM signup_ip_kinds WHERE entity_id IS NULL OR (kind = 'hunter' AND entity_id NOT IN (SELECT id FROM hunters)) OR (kind = 'creator' AND entity_id NOT IN (SELECT id FROM creators))`,
    [],
  ),
});

for (const item of plano) {
  console.log(`${item.tabela}: ${item.total}`);
}

console.log(aplicar ? 'Limpeza aplicada.' : 'Simulacao. Use --aplicar para realmente apagar.');

// Situacao final das tabelas do programa de parceiros.
const CONTAGEM = [
  'creators',
  'hunters',
  'signup_ips',
  'signup_ip_kinds',
  'referrals',
  'outreach_creators',
  'hunter_emails',
  'hunter_withdrawals',
  'withdrawals',
  'referral_earnings',
];
const resumo = CONTAGEM.map((tabela) => {
  const linha = db.query(`SELECT COUNT(*) AS n FROM ${tabela}`).get() as { n: number };
  return `${tabela}=${Number(linha.n) || 0}`;
});
console.log('Estado final: ' + resumo.join(' '));
