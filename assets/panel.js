/**
 * Painel público (/painel): estatísticas agregadas do serviço organizadas em
 * blocos visuais — cartões de número, barras de proporção, anel, medidores e
 * sparkline de latência. Só números agregados: o painel nunca exibe dado
 * pessoal (só contagens, estados de serviço e o @ público de criadores já
 * contatados).
 *
 * Coleta:
 *   1. GET /stats/public, quando a API publica a rota — painel completo;
 *   2. senão, só as rotas públicas existentes (/health + /beacons) — o que a
 *      API não informa fica com "—". Nada é estimado ou inventado.
 */
(function () {
  "use strict";

  var REFRESH_MS = 60 * 1000;
  var TIMEOUT_MS = 10 * 1000;
  // Célula de consulta do registro público de beacons: serve só para ler a rota
  // pública `/beacons`, que devolve os beacons globais e os da própria célula.
  var GEOHASH_CELULA = "u4pry";
  // Histórico local da latência medida no navegador (só números de ms).
  var LAT_CHAVE = "vizinOs.painel.latencia.v1";
  var LAT_MAX = 24;

  var config = window.VIZINHANCA_CONFIG || {};
  var apiUrl = String(config.apiUrl || "").replace(/\/+$/, "");

  var statusEl = document.getElementById("painelStatus");
  var statusTextEl = document.getElementById("painelStatusTexto");
  var errorEl = document.getElementById("painelErro");
  var regionsEl = document.getElementById("painelRegioesLista");
  var contactsEl = document.getElementById("painelContatosLista");
  var loading = false;

  /* ------------------------------------------------------------------ */
  /* Formatação                                                          */
  /* ------------------------------------------------------------------ */

  function setText(id, value) {
    var el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function fmtInt(value) {
    return new Intl.NumberFormat("pt-BR").format(Number(value) || 0);
  }

  function fmtBytes(value) {
    var bytes = Number(value);
    if (!bytes || bytes <= 0) return "—";
    var mb = bytes / (1024 * 1024);
    if (mb >= 1024) return (mb / 1024).toFixed(2).replace(".", ",") + " GB";
    if (mb >= 1) return mb.toFixed(1).replace(".", ",") + " MB";
    return Math.max(1, Math.round(bytes / 1024)) + " kB";
  }

  function fmtMs(value) {
    return Math.round(Number(value) || 0) + " ms";
  }

  function fmtDuration(seconds) {
    var total = Math.max(0, Math.floor(Number(seconds) || 0));
    var days = Math.floor(total / 86400);
    var hours = Math.floor((total % 86400) / 3600);
    var minutes = Math.floor((total % 3600) / 60);
    if (days > 0) return days + " d " + hours + " h";
    if (hours > 0) return hours + " h " + minutes + " min";
    return minutes + " min";
  }

  function fmtDate(unixSeconds) {
    var ms = (Number(unixSeconds) || 0) * 1000;
    if (!ms) return "—";
    try {
      // Mes abreviado + horario: "9 de nov. de 2026, 14:32".
      return new Intl.DateTimeFormat("pt-BR", {
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }).format(new Date(ms));
    } catch (err) {
      return "—";
    }
  }

  function fmtAgo(unixSeconds) {
    var seconds = Math.max(0, Math.floor(Date.now() / 1000) - (Number(unixSeconds) || 0));
    if (seconds < 10) return "agora";
    if (seconds < 60) return "há " + seconds + " s";
    var minutes = Math.floor(seconds / 60);
    if (minutes < 60) return "há " + minutes + " min";
    var hours = Math.floor(minutes / 60);
    if (hours < 24) return "há " + hours + " h";
    return "há " + Math.floor(hours / 24) + " d";
  }

  function fmtPercent(value) {
    if (value === null || value === undefined) return "—";
    return String(value).replace(".", ",") + " %";
  }

  function agora() {
    return Math.floor(Date.now() / 1000);
  }

  /* ------------------------------------------------------------------ */
  /* Elementos visuais (barras, anel, sparkline)                         */
  /* ------------------------------------------------------------------ */

  /** Largura de uma barra em % — ignora silenciosamente se não houver style. */
  function setFill(id, percent) {
    var el = document.getElementById(id);
    if (!el || !el.style) return;
    var p = Math.max(0, Math.min(100, Number(percent) || 0));
    el.style.width = p.toFixed(2) + "%";
  }

  function lerLatencias() {
    try {
      var bruto = window.localStorage ? window.localStorage.getItem(LAT_CHAVE) : null;
      var lista = bruto ? JSON.parse(bruto) : [];
      if (!Array.isArray(lista)) return [];
      var limpa = [];
      for (var i = 0; i < lista.length; i += 1) {
        var n = Number(lista[i]);
        if (isFinite(n) && n >= 0) limpa.push(n);
      }
      return limpa.slice(-LAT_MAX);
    } catch (err) {
      return [];
    }
  }

  function registrarLatencia(ms) {
    var lista = lerLatencias();
    lista.push(Math.max(0, Math.round(Number(ms) || 0)));
    lista = lista.slice(-LAT_MAX);
    try {
      if (window.localStorage) window.localStorage.setItem(LAT_CHAVE, JSON.stringify(lista));
    } catch (err) {
      /* sem armazenamento disponível: segue só com a medição atual */
    }
    return lista;
  }

  /** Desenha a sparkline (SVG puro, 1 linha) com as últimas medições. */
  function desenharSparkline(lista) {
    var el = document.getElementById("painelLatenciaGrafo");
    if (!el) return;
    if (!lista || !lista.length) {
      el.innerHTML = "";
      return;
    }
    var W = 240;
    var H = 44;
    var P = 4;
    var max = Math.max.apply(null, lista);
    var min = Math.min.apply(null, lista);
    var span = Math.max(1, max - min);
    var pontos = [];
    for (var i = 0; i < lista.length; i += 1) {
      var x = lista.length === 1 ? W / 2 : P + (i * (W - 2 * P)) / (lista.length - 1);
      var y = H - P - ((lista[i] - min) / span) * (H - 2 * P);
      pontos.push(x.toFixed(1) + "," + y.toFixed(1));
    }
    var grafico;
    if (lista.length === 1) {
      // Primeira medição ainda não forma linha: mostra só o ponto.
      grafico =
        '<svg viewBox="0 0 ' + W + " " + H + '" preserveAspectRatio="none" focusable="false">' +
        '<circle cx="' + pontos[0].split(",")[0] + '" cy="' + pontos[0].split(",")[1] + '" r="2" ' +
        'fill="currentColor"/></svg>';
    } else {
      grafico =
        '<svg viewBox="0 0 ' + W + " " + H + '" preserveAspectRatio="none" focusable="false">' +
        '<polyline points="' + pontos.join(" ") + '" fill="none" stroke="currentColor" ' +
        'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
    }
    el.innerHTML = grafico;
  }

  /** Zera os visuais derivados (modo em que a API não publica /stats/public). */
  function limparVisuais() {
    var fills = [
      "painelBarra24",
      "painelBarra7",
      "painelBarra30",
      "painelHeapFill",
      "painelBarraCpu",
      "painelBarraUsernames",
      "painelBarraCofres",
      "painelIndicacoesBar",
      "painelSaquesPilhaCriadores",
      "painelSaquesPilhaAfiliados",
    ];
    for (var i = 0; i < fills.length; i += 1) setFill(fills[i], 0);
    setText("painelOnlineLegenda", "—");
    setText("painelHeapLegenda", "—");
    setText("painelIndicacoesLegenda", "—");
    setText("painelSaquesCriadores", "—");
    setText("painelSaquesAfiliados", "—");
  }

  /* ------------------------------------------------------------------ */
  /* Busca na API                                                        */
  /* ------------------------------------------------------------------ */

  /**
   * Busca uma rota da API e devolve o resultado sem jogar exceção:
   * { ok, status, data, latencyMs }.
   */
  function getJson(path) {
    var controller = typeof AbortController === "function" ? new AbortController() : null;
    var timeout = controller ? setTimeout(function () { controller.abort(); }, TIMEOUT_MS) : null;
    var inicio = Date.now();
    return fetch(apiUrl + path, {
      headers: { accept: "application/json" },
      signal: controller ? controller.signal : undefined,
    })
      .then(function (response) {
        return response.text().then(function (texto) {
          var data = null;
          try {
            data = texto ? JSON.parse(texto) : null;
          } catch (err) {
            data = null;
          }
          return {
            ok: response.ok,
            status: response.status,
            data: data,
            latencyMs: Date.now() - inicio,
          };
        });
      })
      .catch(function (error) {
        return {
          ok: false,
          status: 0,
          data: null,
          latencyMs: Date.now() - inicio,
          error: error,
        };
      })
      .then(function (resultado) {
        if (timeout) clearTimeout(timeout);
        return resultado;
      });
  }

  /* ------------------------------------------------------------------ */
  /* Etiquetas (regiões e criadores contatados)                          */
  /* ------------------------------------------------------------------ */

  function regionLabel(code) {
    return code === "*" ? "Global (todas as regiões)" : code;
  }

  function renderRegions(regions) {
    if (!regionsEl) return;
    regionsEl.innerHTML = "";
    var list = Array.isArray(regions) ? regions : [];
    if (!list.length) {
      var empty = document.createElement("span");
      empty.className = "panel-regiao panel-regiao--vazia";
      empty.textContent = "Nenhuma região configurada";
      regionsEl.appendChild(empty);
      return;
    }
    for (var i = 0; i < list.length; i += 1) {
      var chip = document.createElement("span");
      chip.className = "panel-regiao";
      chip.title = "Código geohash da região do beacon";
      chip.textContent = regionLabel(list[i]);
      regionsEl.appendChild(chip);
    }
  }

  function platformLabel(platform) {
    if (platform === "instagram") return "Instagram";
    if (platform === "tiktok") return "TikTok";
    if (platform === "youtube") return "YouTube";
    if (platform === "twitch") return "Twitch";
    if (platform === "x") return "X / Twitter";
    return "Contato";
  }

  function renderContacts(contacts) {
    if (!contactsEl) return;
    contactsEl.innerHTML = "";
    var list = Array.isArray(contacts) ? contacts : [];
    var rendered = 0;
    for (var i = 0; i < list.length; i += 1) {
      var contact = list[i] || {};
      var handle = String(contact.handle || "").trim();
      if (!handle) continue;
      var chip = document.createElement("span");
      chip.className = "panel-regiao";
      chip.title = platformLabel(contact.platform);
      var link = String(contact.contact_url || "").trim();
      if (link) chip.title += " · " + link;
      chip.textContent = handle;
      contactsEl.appendChild(chip);
      rendered += 1;
    }
    if (!rendered) {
      var none = document.createElement("span");
      none.className = "panel-regiao panel-regiao--vazia";
      none.textContent = "Nenhum criador contatado nos últimos 6 meses";
      contactsEl.appendChild(none);
    }
  }

  /* ------------------------------------------------------------------ */
  /* Modo completo: GET /stats/public                                    */
  /* ------------------------------------------------------------------ */

  function render(data) {
    var accounts = data.accounts || {};
    var server = data.server || {};
    var network = data.network || {};
    var partners = data.partners || {};
    var vaults = data.vaults || {};

    var total = Number(accounts.total) || 0;
    var online = Number(accounts.online_now);
    var a1h = Number(accounts.active_1h) || 0;
    var a24 = Number(accounts.active_24h) || 0;
    var a7 = Number(accounts.active_7d) || 0;
    var a30 = Number(accounts.active_30d) || 0;

    // Dispositivos online agora: contagem real da API.
    setText("painelOnline", isFinite(online) ? fmtInt(online) : "—");
    // A janela usada na contagem vem da propria API: o painel nunca promete
    // um prazo diferente do que o servidor realmente aplicou.
    var janela = Number(accounts.online_window_seconds);
    if (isFinite(janela) && janela > 0) {
      var minutos = janela >= 3600 ? Math.round(janela / 3600) + " h" : Math.round(janela / 60) + " min";
      setText("painelOnlineLegenda", "sinal de vida nos últimos " + minutos);
    }

    // Barras de janela: proporcionais à janela maior (30 dias).
    setText("painelAtivos1h", fmtInt(a1h));
    setText("painelAtivos24", fmtInt(a24));
    setText("painelAtivos7", fmtInt(a7));
    setText("painelAtivos30", fmtInt(a30));
    setFill("painelBarra1h", a30 > 0 ? (a1h / a30) * 100 : 0);
    setFill("painelBarra24", a30 > 0 ? (a24 / a30) * 100 : 0);
    setFill("painelBarra7", a30 > 0 ? (a7 / a30) * 100 : 0);
    setFill("painelBarra30", a30 > 0 ? 100 : 0);

    setText("painelRegioes", fmtInt(Array.isArray(network.regions) ? network.regions.length : 0));
    setText("painelBeacons", fmtInt(network.beacons));
    setText("painelUptime", fmtDuration(server.uptime_seconds));
    renderRegions(network.regions);

    // Memória: total (RSS) no cartão e fatia do heap dentro dele no medidor.
    var rss = Number(server.memory_rss_bytes) || 0;
    var heap = Number(server.memory_heap_used_bytes) || 0;
    setText("painelMemoria", fmtBytes(rss));
    if (rss > 0) {
      setFill("painelHeapFill", (heap / rss) * 100);
      setText("painelHeapLegenda", fmtBytes(heap) + " de heap em " + fmtBytes(rss));
    } else {
      setFill("painelHeapFill", 0);
      setText("painelHeapLegenda", "—");
    }

    var cpu = Number(server.cpu_percent);
    setText("painelCpu", fmtPercent(server.cpu_percent));
    setFill("painelBarraCpu", isFinite(cpu) ? Math.max(0, Math.min(100, cpu)) : 0);
    setText("painelBanco", fmtBytes(server.database_size_bytes));
    setText(
      "painelRuntime",
      server.runtime === "bun" && server.runtime_version ? "Bun " + server.runtime_version : "—",
    );
    setText("painelContas", fmtInt(total));
    setText(
      "painelContaRecente",
      accounts.newest_created_at ? fmtDate(accounts.newest_created_at) : "—",
    );

    setText("painelApagadas", fmtInt(accounts.deleted_total));
    setText("painelNovas24h", fmtInt(accounts.new_24h));
    setText("painelNovas7d", fmtInt(accounts.new_7d));

    var withUser = Number(accounts.with_username) || 0;
    var backups = Number(vaults.backups) || 0;
    setText("painelUsernames", fmtInt(withUser));
    setText("painelCofres", fmtInt(backups));
    setFill("painelBarraUsernames", total > 0 ? (withUser / total) * 100 : 0);
    setFill("painelBarraCofres", total > 0 ? (backups / total) * 100 : 0);
    setText(
      "painelUsernamesLegenda",
      total > 0
        ? Math.round((withUser / total) * 100) + "% de " + fmtInt(total) + " contas"
        : "—",
    );
    setText(
      "painelCofresLegenda",
      total > 0
        ? Math.round((backups / total) * 100) + "% de " + fmtInt(total) + " contas"
        : "—",
    );

    setText("painelCriadores", fmtInt(partners.creators));
    setText("painelAfiliados", fmtInt(partners.hunters));
    renderContacts(partners.recent_contacts);
    setText(
      "painelIndicacoes",
      fmtInt(partners.referrals_active) + " de " + fmtInt(partners.referrals_total),
    );

    var refT = Number(partners.referrals_total) || 0;
    var refA = Number(partners.referrals_active) || 0;
    setFill("painelIndicacoesBar", refT > 0 ? (refA / refT) * 100 : 0);
    setText("painelIndicacoesLegenda", refT > 0 ? Math.round((refA / refT) * 100) + "% ativas" : "—");

    setText("painelComissoes", fmtInt(partners.earnings));
    /* Total movimentado pelo programa: comissoes geradas + saques pagos. */
    setText(
      "painelProgramaTotal",
      fmtInt(
        (Number(partners.earnings) || 0) +
          (Number(partners.payouts_paid) || 0) +
          (Number(partners.payouts_hunter_paid) || 0),
      ),
    );
    var pagosC = Number(partners.payouts_paid) || 0;
    var pagosA = Number(partners.payouts_hunter_paid) || 0;
    setText("painelSaques", fmtInt(pagosC + pagosA));
    setText("painelSaquesCriadores", fmtInt(pagosC));
    setText("painelSaquesAfiliados", fmtInt(pagosA));
    var pagosTotal = pagosC + pagosA;
    setFill("painelSaquesPilhaCriadores", pagosTotal > 0 ? (pagosC / pagosTotal) * 100 : 0);
    setFill("painelSaquesPilhaAfiliados", pagosTotal > 0 ? (pagosA / pagosTotal) * 100 : 0);

    if (statusEl) statusEl.classList.remove("panel-status--erro");
    if (errorEl) errorEl.hidden = true;
    if (statusTextEl) {
      statusTextEl.textContent = "Atualizado " + fmtAgo(data.generated_at || agora());
    }
  }

  /* ------------------------------------------------------------------ */
  /* Modo público: só o que a API atual publica                          */
  /* ------------------------------------------------------------------ */

  function renderPublico(extras) {
    var beacons = extras && extras.beacons;
    var lista = beacons && beacons.ok && beacons.data && Array.isArray(beacons.data.beacons)
      ? beacons.data.beacons
      : [];
    var regioes = [];
    for (var i = 0; i < lista.length; i += 1) {
      var geohash = String((lista[i] || {}).geohash || "");
      if (geohash && regioes.indexOf(geohash) === -1) regioes.push(geohash);
    }
    regioes.sort();

    setText("painelBeacons", lista.length ? fmtInt(lista.length) : "—");
    setText(
      "painelRegioes",
      regioes.length === 1 && regioes[0] === "*"
        ? "Global"
        : regioes.length
          ? fmtInt(regioes.length)
          : "—",
    );
    renderRegions(regioes);
    limparVisuais();

    if (statusEl) statusEl.classList.remove("panel-status--erro");
    if (errorEl) errorEl.hidden = true;
    if (statusTextEl) {
      statusTextEl.textContent = "Atualizado agora";
    }
  }

  /* ------------------------------------------------------------------ */
  /* Erro e estado da coleta                                             */
  /* ------------------------------------------------------------------ */

  function showError(message) {
    if (statusEl) statusEl.classList.add("panel-status--erro");
    if (errorEl) {
      errorEl.textContent =
        message || "Não foi possível obter os dados do servidor agora. Tentamos de novo automaticamente.";
      errorEl.hidden = false;
    }
    if (statusTextEl) statusTextEl.textContent = "Sem dados no momento";
  }

  /** Traduz a falha da busca em uma mensagem que diz o que fazer. */
  function mensagemDeErro(stats, health) {
    var status = (stats && stats.status) || (health && health.status) || 0;
    if (status === 404) {
      return (
        "A API não respondeu como esperado (HTTP 404) e o painel não conseguiu " +
        "nenhum dado público agora. Tentamos de novo automaticamente."
      );
    }
    if (status) {
      return "A API respondeu com erro HTTP " + status + ". Tentamos de novo automaticamente.";
    }
    return "Não foi possível obter os dados do servidor agora. Tentamos de novo automaticamente.";
  }

  function coletar() {
    if (loading) return;
    if (!apiUrl) {
      showError("A URL da API não está configurada (assets/config.js).");
      return;
    }
    loading = true;

    Promise.all([getJson("/stats/public"), getJson("/health")])
      .then(function (respostas) {
        var stats = respostas[0];
        var health = respostas[1];

        // Latência medida neste navegador: serve nos dois modos de coleta.
        var medicao = null;
        if (stats.ok && stats.data) medicao = stats.latencyMs;
        else if (health.ok && health.data) medicao = health.latencyMs;
        if (medicao !== null && isFinite(medicao)) {
          setText("painelLatencia", fmtMs(medicao));
          desenharSparkline(registrarLatencia(medicao));
        }

        if (stats.ok && stats.data && stats.data.ok === true) {
          render(stats.data);
          return null;
        }

        if (health.ok && health.data && health.data.ok === true) {
          return getJson("/beacons?geohash=" + GEOHASH_CELULA).then(function (beacons) {
            renderPublico({ beacons: beacons });
          });
        }

        showError(mensagemDeErro(stats, health));
        return null;
      })
      .catch(function (error) {
        showError(mensagemDeErro(null, null));
      })
      .then(function () {
        loading = false;
      });
  }

  coletar();
  setInterval(coletar, REFRESH_MS);
})();
