/**
 * Teste ao vivo do caminho de produção do e-mail, sem gastar cota de afiliado.
 *
 * Usa o mailer real da API (o mesmo que o painel de afiliado usa), com o
 * mesmo /etc/vizin/mail.env do serviço, e envia uma mensagem para o próprio
 * endereço de contato. Assim percorre: VPS -> MAIL_API_URL -> gateway no PC
 * (túnel SSH) -> SMTP do Gmail.
 */
import { readFileSync } from 'node:fs';
import { mailerConfigFromEnv, sendMail } from '/opt/vizin-api/src/mailer.ts';

function carregarEnv(caminho: string): Record<string, string | undefined> {
  const env: Record<string, string | undefined> = {};
  for (const linha of readFileSync(caminho, 'utf8').split('\n')) {
    const texto = linha.trim();
    if (!texto || texto.startsWith('#')) continue;
    const separador = texto.indexOf('=');
    if (separador < 0) continue;
    env[texto.slice(0, separador).trim()] = texto.slice(separador + 1).trim();
  }
  return env;
}

const env = carregarEnv('/etc/vizin/mail.env');
const config = mailerConfigFromEnv(env);
const destino = process.argv[2] ?? 'vizin.oos@gmail.com';

console.log(
  `transporte=${config.transport} url=${config.apiUrl} de=${config.from} para=${destino}`,
);

const resultado = await sendMail(config, {
  to: destino,
  subject: 'vizin.Os — teste do caminho de e-mail',
  text: [
    'Teste automático do caminho de e-mail:',
    'VPS -> gateway no PC -> Gmail.',
    'Se você leu isto, a entrega está funcionando.',
  ].join('\n'),
  replyTo: config.replyTo,
});

console.log(`enviado: ${JSON.stringify(resultado)}`);
