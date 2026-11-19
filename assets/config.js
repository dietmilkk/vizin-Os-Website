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
    if (override) {
      // Produção (https) é sempre aceita. HTTP só vale para loopback, que é
      // onde os testes locais rodam a API — nenhum segredo passa por aqui.
      var local = /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?(\/|$)/i.test(override);
      if (/^https:\/\//i.test(override) || local) api = override.replace(/\/+$/, '');
    }
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
