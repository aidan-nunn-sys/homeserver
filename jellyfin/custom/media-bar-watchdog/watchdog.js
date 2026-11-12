// Media Bar layout watchdog (JavaScript Injector, runs on every page).
// Media Bar 3.0.1 places the home rows below the banner with
//   margin-top: calc(var(--slideshow-content-top) - var(--slideshow-page-offset))
// Sometimes the rows end up over the banner. This checks the rows' position a few
// times after home is shown, logs what it saw to localStorage, and nudges Media Bar
// to re-measure. Read the log in the console: JSON.parse(localStorage.mbWatchdog)
(function () {
  "use strict";
  if (window.__mbWatchdog) {
    return;
  }
  window.__mbWatchdog = true;

  var LOG_KEY = "mbWatchdog";
  var TOLERANCE = 50; // px
  var timers = [];
  var selfResize = false;
  var scrolledAway = false;

  function isHome() {
    return /^#\/home(\.html)?(\?|$)/.test(location.hash) || location.hash === "" || location.hash === "#/";
  }

  function visibleRows() {
    var all = document.querySelectorAll(".homeSectionsContainer");
    for (var i = 0; i < all.length; i++) {
      if (all[i].offsetParent) {
        return all[i];
      }
    }
    return null;
  }

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  function expectedMargin() {
    var top = cssVar("--slideshow-content-top");
    var m = /^([\d.]+)vh$/.exec(top);
    if (!m) {
      return null;
    }
    return (parseFloat(m[1]) / 100) * window.innerHeight;
  }

  function snapshot(reason, rows) {
    var page = document.querySelector(".page");
    var pr = page ? page.getBoundingClientRect() : null;
    var sheetLoaded = false;
    for (var i = 0; i < document.styleSheets.length; i++) {
      var href = document.styleSheets[i].href || "";
      if (href.indexOf("slideshowpure.css") !== -1 && !document.styleSheets[i].disabled) {
        sheetLoaded = true;
      }
    }
    return {
      at: new Date().toISOString(),
      reason: reason,
      offset: cssVar("--slideshow-page-offset"),
      rowsTopVar: cssVar("--slideshow-rows-top"),
      contentTop: cssVar("--slideshow-content-top"),
      marginTop: rows ? getComputedStyle(rows).marginTop : null,
      expected: Math.round(expectedMargin() || -1),
      scrollTop: document.scrollingElement.scrollTop,
      firstPage: page ? page.className : null,
      firstPageTop: pr ? Math.round(pr.top) : null,
      pages: document.querySelectorAll(".page").length,
      stage: !!document.getElementById("slides-container"),
      sheetLoaded: sheetLoaded,
      viewport: window.innerWidth + "x" + window.innerHeight,
      visibility: document.visibilityState,
      ua: navigator.userAgent.slice(0, 80)
    };
  }

  function log(entry) {
    var list = [];
    try {
      list = JSON.parse(localStorage.getItem(LOG_KEY) || "[]");
    } catch (e) {
      list = [];
    }
    list.push(entry);
    while (list.length > 20) {
      list.shift();
    }
    localStorage.setItem(LOG_KEY, JSON.stringify(list));
    console.warn("[mbWatchdog]", entry);
  }

  function isBad(rows) {
    var want = expectedMargin();
    if (want === null) {
      return true; // variable missing: Media Bar CSS not applied
    }
    var have = parseFloat(getComputedStyle(rows).marginTop) || 0;
    return Math.abs(have - want) > TOLERANCE;
  }

  function check(label) {
    if (!isHome() || document.visibilityState !== "visible") {
      return;
    }
    if (!document.getElementById("slides-container")) {
      return; // Media Bar not on this view
    }
    var rows = visibleRows();
    if (!rows || !isBad(rows)) {
      return;
    }
    var entry = snapshot(label, rows);
    selfResize = true;
    window.dispatchEvent(new Event("resize"));
    selfResize = false;
    setTimeout(function () {
      if (!isBad(rows)) {
        entry.fixedBy = "resize";
        log(entry);
        return;
      }
      document.documentElement.style.removeProperty("--slideshow-page-offset");
      setTimeout(function () {
        if (isBad(rows)) {
          entry.fixedBy = "none";
          entry.marginAfter = getComputedStyle(rows).marginTop;
        } else {
          entry.fixedBy = "removeProperty";
        }
        log(entry);
      }, 100);
    }, 100);
  }

  function schedule(trigger) {
    while (timers.length) {
      clearTimeout(timers.pop());
    }
    [1000, 3000, 6000].forEach(function (ms) {
      timers.push(setTimeout(function () {
        check(trigger + "+" + ms);
      }, ms));
    });
  }

  window.addEventListener("hashchange", function () {
    if (isHome()) {
      schedule("hashchange");
    }
  });
  window.addEventListener("pageshow", function () {
    schedule("pageshow");
  });
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible") {
      schedule("visible");
    }
  });
  // Window moved or resized while booting (Hyprland tiling, phone rotation).
  window.addEventListener("resize", function () {
    if (!selfResize && isHome()) {
      schedule("resize");
    }
  }, { passive: true });
  // Scrolled back up to the banner after scrolling away.
  window.addEventListener("scroll", function () {
    var y = document.scrollingElement.scrollTop;
    if (y < 100 && scrolledAway && isHome()) {
      schedule("scrolltop");
    }
    scrolledAway = y >= 100;
  }, { passive: true });
  schedule("load");
})();
