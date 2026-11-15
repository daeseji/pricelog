/* 싸다구 '제휴 링크 끄기'
 * 켜 두면 이 브라우저에서는 '쿠팡에서 보기'가 쿠팡 파트너스 링크 대신 일반 쿠팡 상품 주소로 열려요.
 * 주소 뒤에 ?noaff=1 을 붙여 한 번 열어도 켜지고, ?noaff=0 으로 끌 수 있어요.
 * 설정은 이 브라우저(localStorage)에만 저장돼요.
 */
(function () {
  var KEY = 'sadagu:noaff';
  function get() {
    try { return localStorage.getItem(KEY) === '1'; } catch (e) { return false; }
  }
  function set(on) {
    try { if (on) localStorage.setItem(KEY, '1'); else localStorage.removeItem(KEY); } catch (e) {}
  }
  try {
    var q = new URLSearchParams(location.search).get('noaff');
    if (q === '1') set(true);
    else if (q === '0') set(false);
  } catch (e) {}
  window.SDG_NOAFF = get;

  function sync() {
    var on = get();
    document.querySelectorAll('input[data-noaff]').forEach(function (box) { box.checked = on; });
    document.querySelectorAll('[data-noaff-state]').forEach(function (el) {
      el.textContent = on ? '지금 이 브라우저에서는 일반 쿠팡 주소로 열려요.' : '지금은 쿠팡 파트너스 링크로 열려요.';
    });
  }
  document.addEventListener('change', function (e) {
    var box = e.target.closest && e.target.closest('input[data-noaff]');
    if (!box) return;
    set(box.checked);
    sync();
    document.dispatchEvent(new CustomEvent('sdg:noaff'));
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', sync);
  else sync();
})();
