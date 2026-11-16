/**
 * Configuração pública do site.
 * Nenhum segredo deve ser colocado aqui: tudo é servido ao navegador.
 *
 * Override por query (`?api=...`): aponta para outra instância da MESMA API
 * pública — usado pelos testes locais (Playwright) e para depuração. Nada de
 * segredo passa por aqui; o parâmetro é lido antes do congelamento do objeto.
 */
(function () {
  var api = 'https://api.188.166.156.109.sslip.io';
  try {
    var override = new URLSearchParams(window.location.search).get('api');
    if (override && /^https:\/\//.test(override)) api = override.replace(/\/+$/, '');
  } catch (err) {
    // Sem query disponível: fica a API de produção.
  }
  window.VIZINHANCA_CONFIG = Object.freeze({
    siteUrl: 'https://vizin-os.vercel.app',
    apiUrl: api,
    androidUrl: 'https://play.google.com/store/apps/details?id=dev.vizinhoos.app',
    iosUrl: '',
    contactEmail: 'vizin.oos@gmail.com',
  });
})();
