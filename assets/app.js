(function () {
  'use strict';

  var config = window.VIZINHANCA_CONFIG || {};
  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var $ = function (selector, scope) {
    return (scope || document).querySelector(selector);
  };
  var $$ = function (selector, scope) {
    return Array.prototype.slice.call((scope || document).querySelectorAll(selector));
  };

  /* menu mobile */
  var menuToggle = $('#menu-toggle');
  var mobileNav = $('#mobile-nav');

  function closeMenu() {
    if (!mobileNav || !menuToggle) return;
    mobileNav.hidden = true;
    menuToggle.setAttribute('aria-expanded', 'false');
  }

  if (menuToggle && mobileNav) {
    menuToggle.addEventListener('click', function () {
      var open = mobileNav.hidden;
      mobileNav.hidden = !open;
      menuToggle.setAttribute('aria-expanded', String(open));
    });
    $$('a', mobileNav).forEach(function (link) {
      link.addEventListener('click', closeMenu);
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') closeMenu();
    });
  }

  /* cabeçalho: progresso de leitura e seção ativa */
  var header = $('.site-header');
  var navLinks = $$('.desktop-nav a[href^="#"]');
  var navTargets = navLinks
    .map(function (link) {
      var id = link.getAttribute('href');
      var target = id && id.length > 1 ? $(id) : null;
      return target ? { link: link, target: target } : null;
    })
    .filter(Boolean);
  var ticking = false;

  function onScroll() {
    var y = window.scrollY;
    var doc = document.documentElement;

    if (header) {
      header.classList.toggle('is-scrolled', y > 12);

      /* Barra de progresso de leitura. */
      var max = Math.max(0, doc.scrollHeight - window.innerHeight);
      header.style.setProperty('--scroll-progress', String(max > 0 ? Math.min(1, y / max) : 0));
    }

    if (navTargets.length) {
      var offset = (header ? header.offsetHeight : 0) + 28;
      var current = null;
      navTargets.forEach(function (item) {
        if (item.target.getBoundingClientRect().top - offset <= 0) current = item;
      });
      navLinks.forEach(function (link) {
        var active = current ? link === current.link : false;
        link.classList.toggle('is-active', active);
        if (active) link.setAttribute('aria-current', 'location');
        else link.removeAttribute('aria-current');
      });
    }

    ticking = false;
  }

  window.addEventListener(
    'scroll',
    function () {
      if (!ticking) {
        ticking = true;
        window.requestAnimationFrame(onScroll);
      }
    },
    { passive: true },
  );
  onScroll();

  /* entrada suave */
  var revealItems = $$('.reveal');
  if (reduceMotion || !('IntersectionObserver' in window)) {
    revealItems.forEach(function (item) {
      item.classList.add('is-visible');
    });
  } else {
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' },
    );

    /* Blocos `no-fade` (como o ensaio da home) não somem nem deslizam, mas
       precisam de `is-visible` para ativar os enfeites do texto. Usam um
       observador mais sensível porque são muito altos. */
    var staticObserver = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-visible');
            staticObserver.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.02 },
    );

    revealItems.forEach(function (item) {
      if (item.classList.contains('no-fade')) staticObserver.observe(item);
      else observer.observe(item);
    });
  }

  /* marca: sorteia uma das versões da wordmark a cada carregamento.
     As artes são brancas com transparência e entram como máscara, então
     herdam a cor do texto (e o hover da marca) em qualquer tema. */
  var wordmarks = [
    { src: '/assets/brand/wordmark-1.png', ratio: 298 / 66 },
    { src: '/assets/brand/wordmark-2.png', ratio: 294 / 71 },
    { src: '/assets/brand/wordmark-3.png', ratio: 188 / 63 },
    { src: '/assets/brand/wordmark-4.png', ratio: 301 / 61 },
    { src: '/assets/brand/wordmark-5.png', ratio: 390 / 75 },
    { src: '/assets/brand/wordmark-6.png', ratio: 353 / 57 },
  ];
  var wordmarkTargets = $$('[data-brand-wordmark]');
  if (wordmarkTargets.length) {
    var lastWordmark = -1;
    try {
      lastWordmark = parseInt(window.sessionStorage.getItem('vizin-wordmark'), 10);
    } catch (error) {
      lastWordmark = -1;
    }

    var wordmarkIndex = Math.floor(Math.random() * wordmarks.length);
    if (!isNaN(lastWordmark) && wordmarkIndex === lastWordmark) {
      wordmarkIndex = (wordmarkIndex + 1) % wordmarks.length;
    }

    try {
      window.sessionStorage.setItem('vizin-wordmark', String(wordmarkIndex));
    } catch (error) {
      /* sessionStorage indisponível: segue com o sorteio simples. */
    }

    var wordmark = wordmarks[wordmarkIndex];
    wordmarkTargets.forEach(function (target) {
      target.style.setProperty('--wordmark-ratio', String(wordmark.ratio));
      target.style.webkitMaskImage = 'url("' + wordmark.src + '")';
      target.style.maskImage = 'url("' + wordmark.src + '")';
      target.classList.add('is-ready');
    });
  }

  /* link de download */
  var download = $('#android-download');
  if (download) {
    if (config.androidUrl) {
      download.href = config.androidUrl;
      download.removeAttribute('target');
    } else if (config.contactEmail) {
      download.href =
        'mailto:' +
        config.contactEmail +
        '?subject=' +
        encodeURIComponent('Quero testar o vizin.Os');
    }
  }

  /* ano do rodapé */
  var year = $('#year');
  if (year) year.textContent = String(new Date().getFullYear());

  /* feedback de clique nos botões: pop elástico (ver .btn.is-pressed no CSS) */
  if (!reduceMotion) {
    document.addEventListener('click', function (event) {
      var button = event.target && event.target.closest ? event.target.closest('.btn') : null;
      if (!button || button.disabled || button.classList.contains('is-loading')) return;
      button.classList.remove('is-pressed');
      void button.offsetWidth; /* reinicia a animação em cliques rápidos */
      button.classList.add('is-pressed');
    });
    document.addEventListener('animationend', function (event) {
      var target = event.target;
      if (target && target.classList && target.classList.contains('is-pressed')) {
        target.classList.remove('is-pressed');
      }
    });
  }

  /* aviso de primeira visita */
  var firstVisitModal = $('#firstVisitModal');
  if (firstVisitModal) {
    var firstVisitSeen = false;
    try {
      firstVisitSeen =
        window.localStorage.getItem('vizin.os.first-visit') === '1' ||
        window.localStorage.getItem('vizin-os-first-visit') === '1';
    } catch (error) {
      firstVisitSeen = false;
    }
    if (!firstVisitSeen) {
      firstVisitModal.hidden = false;
      document.body.style.overflow = 'hidden';
    }
    var closeFirstVisit = function () {
      firstVisitModal.hidden = true;
      document.body.style.overflow = '';
      try {
        window.localStorage.setItem('vizin.os.first-visit', '1');
        window.localStorage.removeItem('vizin-os-first-visit');
      } catch (error) {
        // ignore
      }
    };
    $$('[data-first-visit-close]', firstVisitModal).forEach(function (el) {
      el.addEventListener('click', closeFirstVisit);
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && !firstVisitModal.hidden) closeFirstVisit();
    });
  }

  /* Galeria de etapas: abas numeradas, teclado e avanço guiado pelo scroll. */
  var stepTabs = $$('.step-tab');
  var stepPanels = $$('.step-panel');
  var stepStage = $('.step-gallery-stage');
  var stepGallery = $('.step-gallery');
  var stepPanelsWrap = $('.step-gallery-panels');
  if (stepTabs.length && stepPanels.length) {
    var currentStep = 0;
    var stepScrollEnabled = false;
    var stepTicking = false;
    var stepStickyTop = 0;

    /* Todas as etapas ficam empilhadas; a visibilidade é controlada por classe. */
    stepPanels.forEach(function (panel) {
      var active = panel.classList.contains('is-active');
      panel.hidden = false;
      if (active) panel.removeAttribute('aria-hidden');
      else panel.setAttribute('aria-hidden', 'true');
      panel.tabIndex = active ? 0 : -1;
    });
    if (stepPanelsWrap) stepPanelsWrap.classList.add('is-ready');

    var applyStep = function (index, focusTab) {
      if (focusTab) stepTabs[index].focus({ preventScroll: true });
      if (index === currentStep) return;
      currentStep = index;
      stepTabs.forEach(function (tab, i) {
        var active = i === index;
        tab.classList.toggle('is-active', active);
        tab.classList.toggle('is-seen', i < index);
        tab.setAttribute('aria-selected', String(active));
        tab.tabIndex = active ? 0 : -1;
      });
      stepPanels.forEach(function (panel, i) {
        var active = i === index;
        panel.classList.toggle('is-active', active);
        if (active) panel.removeAttribute('aria-hidden');
        else panel.setAttribute('aria-hidden', 'true');
        panel.tabIndex = active ? 0 : -1;
      });
    };

    var canDriveByScroll = function () {
      /* Mobile (largura <= 720px): a galeria vira uma pilha de blocos simples,
         sem sticky/crossfade/rolagem guiada. */
      return !reduceMotion && window.innerWidth > 720 && window.innerHeight >= 720;
    };

    /* No mobile só o painel fica preso; o título e as abas rolam normalmente. */
    var isMobileLayout = function () {
      return window.innerWidth <= 720;
    };

    /* Cada etapa ocupa uma "tela" de rolagem: a galeria fica presa e o scroll
       avança (ou retrocede) um nível por vez. */
    var getStepHeight = function () {
      return Math.max(240, Math.round(window.innerHeight * 0.72));
    };

    var getScrollDistance = function () {
      return getStepHeight() * stepTabs.length;
    };

    var getPinnedElement = function () {
      return isMobileLayout() && stepPanelsWrap ? stepPanelsWrap : stepGallery;
    };

    /* Deslocamento do bloco preso dentro da galeria (título + abas no mobile). */
    var getStageOffset = function () {
      if (isMobileLayout() && stepPanelsWrap && stepGallery) {
        return Math.max(0, stepPanelsWrap.offsetTop - stepGallery.offsetTop);
      }
      return 0;
    };

    /* Progresso medido direto pela posição do palco: não depende do sticky. */
    var getStageProgress = function () {
      var distance = getScrollDistance();
      if (!distance) return 0;
      var rect = stepStage.getBoundingClientRect();
      var scrolled = -rect.top + stepStickyTop - getStageOffset();
      return Math.max(0, Math.min(1, scrolled / distance));
    };

    var updateStepFromScroll = function () {
      if (!stepScrollEnabled) return;
      var progress = getStageProgress();
      var index = Math.min(stepTabs.length - 1, Math.floor(progress * stepTabs.length));
      applyStep(index, false);
    };

    var resizeStepStage = function () {
      if (!stepStage || !stepGallery) return;
      stepScrollEnabled = canDriveByScroll();
      stepStage.classList.toggle('is-scroll-driven', stepScrollEnabled);
      if (!stepScrollEnabled) {
        stepStage.style.height = '';
        stepGallery.style.height = '';
        stepStage.style.removeProperty('--step-sticky-top');
        stepStage.style.removeProperty('--step-pin-gap');
        syncHeaderVisibility();
        return;
      }
      /* Sem o header, o bloco preso usa o espaço liberado com um respiro
         pequeno no topo. */
      var pinGap = 16;
      stepStickyTop = pinGap;
      stepStage.style.setProperty('--step-pin-gap', pinGap + 'px');
      stepStage.style.setProperty('--step-sticky-top', stepStickyTop + 'px');
      var pinned = getPinnedElement();
      var stickyHeight = pinned.offsetHeight;
      if (pinned !== stepGallery) {
        stickyHeight += Math.max(0, pinned.offsetTop - stepGallery.offsetTop);
      }
      var stageHeight = getScrollDistance() + stickyHeight;
      stepStage.style.height = stageHeight + 'px';
      stepGallery.style.height = pinned !== stepGallery ? stageHeight + 'px' : '';
      updateStepFromScroll();
      syncHeaderVisibility();
    };

    var jumpToY = function (top) {
      /* O CSS usa scroll-behavior: smooth na página; forçamos o salto
         instantâneo nas trocas por teclado. */
      var root = document.documentElement;
      var previous = root.style.scrollBehavior;
      root.style.scrollBehavior = 'auto';
      window.scrollTo(0, top);
      root.style.scrollBehavior = previous;
    };

    var scrollToStep = function (index, smooth) {
      if (!stepScrollEnabled) {
        applyStep(index, false);
        return false;
      }
      var distance = getScrollDistance();
      if (!distance) {
        applyStep(index, false);
        return false;
      }
      var stageTop = window.scrollY + stepStage.getBoundingClientRect().top;
      var target = Math.max(
        0,
        Math.round(stageTop - stepStickyTop + getStageOffset() + ((index + 0.5) / stepTabs.length) * distance),
      );
      var maxScroll = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
      target = Math.min(target, maxScroll);
      if (smooth && !reduceMotion) window.scrollTo({ top: target, behavior: 'smooth' });
      else jumpToY(target);
      return true;
    };

    /* Roda do mouse, setas e PageUp/PageDown trocam de nível sem depender do
       scroll nativo, que fica travado enquanto a galeria está presa. */
    var isStagePinned = function () {
      if (!stepScrollEnabled) return false;
      var rect = getPinnedElement().getBoundingClientRect();
      var stageBottom = stepStage.getBoundingClientRect().top + stepStage.offsetHeight;
      return rect.top <= stepStickyTop + 1 && stageBottom > stepStickyTop + window.innerHeight * 0.5;
    };

    /* O header só some enquanto o bloco está de fato preso na tela. */
    var siteHeader = $('.site-header');
    var pinnedState = false;
    var syncHeaderVisibility = function () {
      if (!siteHeader) return;
      var pinned = isStagePinned();
      if (pinned === pinnedState) return;
      pinnedState = pinned;
      siteHeader.classList.toggle('is-hidden', pinned);
      stepStage.classList.toggle('is-pinned', pinned);
    };

    /* Troca de nível: aplica a etapa e move o scroll para o centro dela. */
    var stepBy = function (delta) {
      var next = Math.max(0, Math.min(stepTabs.length - 1, currentStep + delta));
      if (next === currentStep) return false;
      applyStep(next, false);
      scrollToStep(next, true);
      return true;
    };

    /* Ao entrar na área presa, o nível 1 é ativado automaticamente. */
    var enterStage = function () {
      if (currentStep !== 0) applyStep(0, false);
    };

    var wheelLocked = false;
    var wheelUnlockTimer = 0;

    window.addEventListener(
      'wheel',
      function (event) {
        if (!isStagePinned() || event.ctrlKey) return;
        var delta = event.deltaY;
        if (Math.abs(delta) < 4) return;
        var atLast = currentStep === stepTabs.length - 1;
        var atFirst = currentStep === 0;
        /* No último nível (descendo) ou no primeiro (subindo) o scroll é liberado. */
        if ((delta > 0 && atLast) || (delta < 0 && atFirst)) return;
        event.preventDefault();
        /* Um gesto = um nível: ignora a inércia do trackpad até o scroll parar. */
        if (wheelLocked) return;
        wheelLocked = true;
        window.clearTimeout(wheelUnlockTimer);
        wheelUnlockTimer = window.setTimeout(function () {
          wheelLocked = false;
        }, 420);
        stepBy(delta > 0 ? 1 : -1);
      },
      { passive: false },
    );

    document.addEventListener('keydown', function (event) {
      if (!isStagePinned()) return;
      var target = event.target;
      if (target && /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)) return;
      var delta = 0;
      if (event.key === 'ArrowDown' || event.key === 'PageDown') delta = 1;
      else if (event.key === 'ArrowUp' || event.key === 'PageUp') delta = -1;
      if (!delta) return;
      var atLast = currentStep === stepTabs.length - 1;
      var atFirst = currentStep === 0;
      if ((delta > 0 && atLast) || (delta < 0 && atFirst)) return;
      event.preventDefault();
      stepBy(delta);
    });

    stepTabs.forEach(function (tab, index) {
      tab.addEventListener('click', function () {
        applyStep(index, false);
        scrollToStep(index, false);
      });
      tab.addEventListener('keydown', function (event) {
        var next = null;
        if (event.key === 'ArrowRight') next = (index + 1) % stepTabs.length;
        else if (event.key === 'ArrowLeft') next = (index - 1 + stepTabs.length) % stepTabs.length;
        else if (event.key === 'Home') next = 0;
        else if (event.key === 'End') next = stepTabs.length - 1;
        if (next !== null) {
          event.preventDefault();
          applyStep(next, true);
          scrollToStep(next, false);
        }
      });
    });

    window.addEventListener(
      'scroll',
      function () {
        if (!stepScrollEnabled || stepTicking) return;
        stepTicking = true;
        window.requestAnimationFrame(function () {
          stepTicking = false;
          var wasPinned = pinnedState;
          syncHeaderVisibility();
          /* Acabou de entrar na área presa: começa no nível 1. */
          if (!wasPinned && pinnedState) enterStage();
          else updateStepFromScroll();
        });
      },
      { passive: true },
    );

    window.addEventListener('resize', resizeStepStage);
    window.addEventListener('load', resizeStepStage);
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(resizeStepStage);
    }
    if ('ResizeObserver' in window && stepGallery) {
      new ResizeObserver(function () {
        if (stepScrollEnabled) resizeStepStage();
      }).observe(stepGallery);
    }

    var motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
    var onMotionChange = function (event) {
      reduceMotion = event.matches;
      resizeStepStage();
      syncHeaderVisibility();
    };
    if (motionQuery.addEventListener) motionQuery.addEventListener('change', onMotionChange);
    else if (motionQuery.addListener) motionQuery.addListener(onMotionChange);

    resizeStepStage();
    syncHeaderVisibility();
  }

  /* Sublinhado animado que desce linha por linha. */
  function animateUnderlineLayer(layer) {
    var segments = Array.prototype.slice.call(layer.querySelectorAll('.underline-segment'));
    if (!segments.length) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      segments.forEach(function (segment) { segment.style.transform = 'scaleX(1)'; });
      return;
    }
    var index = 0;
    function step() {
      if (index >= segments.length) {
        window.setTimeout(function () {
          segments.forEach(function (segment) { segment.style.transform = 'scaleX(0)'; });
          index = 0;
          window.setTimeout(step, 700);
        }, 1800);
        return;
      }
      segments[index].style.transform = 'scaleX(1)';
      index += 1;
      window.setTimeout(step, 380);
    }
    step();
  }

  function drawAnimatedUnderlines() {
    $$('.underline-animated').forEach(function (el) {
      var parent = el.parentElement;
      if (!parent) return;
      var existing = parent.querySelector('.underline-layer');
      if (existing) existing.remove();
      parent.style.position = 'relative';
      var range = document.createRange();
      range.selectNodeContents(el);
      var rects = Array.prototype.slice.call(range.getClientRects());
      if (!rects.length) return;
      var base = parent.getBoundingClientRect();
      var layer = document.createElement('span');
      layer.className = 'underline-layer';
      layer.setAttribute('aria-hidden', 'true');
      rects.forEach(function (rect) {
        var segment = document.createElement('span');
        segment.className = 'underline-segment';
        segment.style.left = rect.left - base.left + 'px';
        segment.style.top = rect.bottom - base.top - 2 + 'px';
        segment.style.width = rect.width + 'px';
        layer.appendChild(segment);
      });
      parent.appendChild(layer);
      animateUnderlineLayer(layer);
    });
  }

  drawAnimatedUnderlines();
  window.addEventListener('resize', drawAnimatedUnderlines);
})();
