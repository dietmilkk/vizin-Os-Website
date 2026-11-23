/**
 * Divisão de receita do Plus — fonte única dos percentuais da página /membros.
 *
 * Toda porcentagem exibida na página (planilha, cartões de mérito, diagrama e
 * simulação) sai deste objeto. Para mudar a divisão, altere apenas `shares`:
 * a soma é validada em 100% e o restante da página se atualiza sozinho.
 *
 * A base das comissões é o preço de referência (preço de lista) da compra.
 * O desconto do usuário sai dessa base e as comissões são normalizadas sobre
 * o valor efetivamente pago, como o backend também faz.
 */
(function () {
  'use strict';

  var REVENUE_SPLIT = Object.freeze({
    shares: Object.freeze({
      creator: 50,
      user: 25,
      affiliate: 10,
      mod: 5,
      development: 10,
    }),
    simulation: Object.freeze({
      mods: 1,
      affiliatesPerMod: 10,
      creatorsPerAffiliate: 5,
      referencePerCreator: 100,
    }),
  });

  var shares = REVENUE_SPLIT.shares;
  var simulation = REVENUE_SPLIT.simulation;

  var total = Object.keys(shares).reduce(function (sum, key) {
    return sum + shares[key];
  }, 0);

  if (total !== 100) {
    throw new Error('A divisão de receita precisa somar 100% (atual: ' + total + '%).');
  }

  var affiliates = simulation.mods * simulation.affiliatesPerMod;
  var creators = affiliates * simulation.creatorsPerAffiliate;
  var networkReferenceBase = creators * simulation.referencePerCreator;
  var paidSharePercent = 100 - shares.user;
  var paidPerCreator = simulation.referencePerCreator * (1 - shares.user / 100);
  var userDiscountPerCreator = simulation.referencePerCreator * (shares.user / 100);
  var networkPaidTotal = creators * paidPerCreator;
  var modRevenue = (networkReferenceBase * shares.mod) / 100;
  var creatorRevenue = (simulation.referencePerCreator * shares.creator) / 100;
  var affiliateRevenuePerCreator = simulation.referencePerCreator * (shares.affiliate / 100);
  var modRevenuePerCreator = simulation.referencePerCreator * (shares.mod / 100);
  var developmentRevenuePerCreator =
    simulation.referencePerCreator * (shares.development / 100);
  var creatorNetworkRevenue = creators * creatorRevenue;

  function formatBRL(value) {
    return new Intl.NumberFormat('pt-BR', {
      style: 'currency',
      currency: 'BRL',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  }

  var simulated = Object.freeze({
    mods: simulation.mods,
    affiliates: affiliates,
    creatorsPerAffiliate: simulation.creatorsPerAffiliate,
    creators: creators,
    referencePerCreator: formatBRL(simulation.referencePerCreator),
    paidPerCreator: formatBRL(paidPerCreator),
    userDiscountPerCreator: formatBRL(userDiscountPerCreator),
    networkReferenceTotal: formatBRL(networkReferenceBase),
    networkPaidTotal: formatBRL(networkPaidTotal),
    modRevenue: formatBRL(modRevenue),
    creatorRevenue: formatBRL(creatorRevenue),
    affiliateRevenuePerCreator: formatBRL(affiliateRevenuePerCreator),
    modRevenuePerCreator: formatBRL(modRevenuePerCreator),
    developmentRevenuePerCreator: formatBRL(developmentRevenuePerCreator),
    creatorNetworkRevenue: formatBRL(creatorNetworkRevenue),
    modPaidRatio: shares.mod + '/' + paidSharePercent,
  });

  window.VIZIN_REVENUE_SPLIT = Object.freeze({
    shares: shares,
    total: total,
    simulation: simulation,
  });

  function percent(key) {
    return shares[key] + '%';
  }

  function render() {
    document.querySelectorAll('[data-revenue-share]').forEach(function (el) {
      var key = el.getAttribute('data-revenue-share');
      if (Object.prototype.hasOwnProperty.call(shares, key)) {
        el.textContent = percent(key);
      }
    });

    document.querySelectorAll('[data-revenue-total]').forEach(function (el) {
      el.textContent = total + '%';
    });

    document.querySelectorAll('[data-revenue-sim]').forEach(function (el) {
      var key = el.getAttribute('data-revenue-sim');
      if (Object.prototype.hasOwnProperty.call(simulated, key)) {
        el.textContent = String(simulated[key]);
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', render);
  } else {
    render();
  }
})();
