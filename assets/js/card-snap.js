// Phone-only "one product per screen" snapping for the product grid.
// CSS scroll-snap on the page root is unreliable in iOS Safari, so after the
// user's scroll (incl. momentum) settles we glide the nearest card to the
// centre of the screen. A deliberate swipe moves at least one card onward.
(function () {
  var mq = window.matchMedia('(max-width: 620px)');
  var SETTLE_MS = 120;   // quiet time that counts as "scroll finished"
  var SWIPE_PX = 50;     // a swipe longer than this always advances a card
  var timer = null, touching = false, auto = false, autoTimer = null;
  var startY = 0, startIdx = -1;

  function cards() { return Array.prototype.slice.call(document.querySelectorAll('.grid .card')); }

  function vh() { return window.visualViewport ? window.visualViewport.height : window.innerHeight; }

  function targetTop(card) {
    var r = card.getBoundingClientRect();
    return window.scrollY + r.top - (vh() - r.height) / 2;
  }

  // Index of the card whose centre is closest to the viewport centre, or -1
  // when the grid is not what the user is looking at.
  function nearest(list) {
    var mid = vh() / 2, best = -1, bestD = Infinity;
    for (var i = 0; i < list.length; i++) {
      var r = list[i].getBoundingClientRect();
      var d = Math.abs(r.top + r.height / 2 - mid);
      if (d < bestD) { bestD = d; best = i; }
    }
    if (best < 0) return -1;
    var h = list[best].getBoundingClientRect().height;
    return bestD <= h * 0.75 ? best : -1;
  }

  function glide(top) {
    auto = true;
    clearTimeout(autoTimer);
    window.scrollTo({ top: Math.max(0, Math.round(top)), behavior: 'smooth' });
    autoTimer = setTimeout(function () { auto = false; }, 700);
  }

  function settle() {
    if (!mq.matches || touching || auto) return;
    var list = cards();
    var i = nearest(list);
    if (i < 0) { startIdx = -1; startY = window.scrollY; return; }
    var moved = window.scrollY - startY;
    // A short flick that did not reach the next card still moves one card on.
    if (startIdx >= 0 && i === startIdx && Math.abs(moved) > SWIPE_PX) {
      var next = startIdx + (moved > 0 ? 1 : -1);
      if (next >= 0 && next < list.length) i = next;
      else return; // let people scroll past the first/last card freely
    }
    var top = targetTop(list[i]);
    if (Math.abs(top - window.scrollY) > 3) glide(top);
    startY = top; startIdx = i;
  }

  function markStart() {
    startY = window.scrollY;
    startIdx = nearest(cards());
  }

  window.addEventListener('touchstart', function () {
    touching = true; auto = false; clearTimeout(timer); markStart();
  }, { passive: true });
  window.addEventListener('touchend', function () {
    touching = false; clearTimeout(timer); timer = setTimeout(settle, SETTLE_MS);
  }, { passive: true });
  window.addEventListener('touchcancel', function () { touching = false; }, { passive: true });
  window.addEventListener('scroll', function () {
    if (auto) return;
    if (!touching && startIdx < 0 && timer === null) markStart();
    clearTimeout(timer);
    timer = setTimeout(function () { timer = null; settle(); }, SETTLE_MS);
  }, { passive: true });
})();
