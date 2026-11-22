/**
 * Divisão de receita do Plus — fonte única dos percentuais da página /membros.
 *
 * Toda porcentagem exibida na página (planilha, cards de mérito, diagrama e
 * simulação) sai deste objeto. Para mudar a divisão, altere apenas `shares`:
 * a soma é validada em 100% e o restante da página se atualiza sozinho.
 */
(function () {
  "use strict";

  var shares = Object.freeze({
    creator: 50,
    user: 25,
    affiliate: 10,
    mod: 5,
    development: 10,
  });

  var simulation = Object.freeze({
    mods: 1,
    affiliatesPerMod: 10,
    creatorsPerAffiliate: 5,
  });

  var total = Object.keys(shares).reduce(function (sum, key) {
    return sum + shares[key];
  }, 0);

  if (total !== 100) {
    throw new Error(
      "A divisão de receita precisa somar 100% (atual: " + total + "%)."
    );
  }

  window.VIZIN_REVENUE_SPLIT = Object.freeze({
    shares: shares,
    total: total,
    simulation: simulation,
  });

  function percent(key) {
    return shares[key] + "%";
  }

  function render() {
    document.querySelectorAll("[data-revenue-share]").forEach(function (el) {
      var key = el.getAttribute("data-revenue-share");
      if (Object.prototype.hasOwnProperty.call(shares, key)) {
        el.textContent = percent(key);
      }
    });

    document.querySelectorAll("[data-revenue-total]").forEach(function (el) {
      el.textContent = total + "%";
    });

    var simulated = {
      mods: simulation.mods,
      affiliates: simulation.mods * simulation.affiliatesPerMod,
      creatorsPerAffiliate: simulation.creatorsPerAffiliate,
      creators:
        simulation.mods *
        simulation.affiliatesPerMod *
        simulation.creatorsPerAffiliate,
    };

    document.querySelectorAll("[data-revenue-sim]").forEach(function (el) {
      var key = el.getAttribute("data-revenue-sim");
      if (Object.prototype.hasOwnProperty.call(simulated, key)) {
        el.textContent = String(simulated[key]);
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", render);
  } else {
    render();
  }
})();
