/* 싸다구로 보내기 (북마크 버튼)
   쿠팡 '다시 구매' 화면(www.coupang.com/np/fbi)에 이미 떠 있는 상품 카드만 읽어서 (상품 번호, 옵션, 이름, 가격, 구매 횟수, 썸네일 주소)
   이 브라우저 안에서 싸다구 '내 상품' 탭으로 바로 넘겨요.
   쿠팡 서버에 따로 요청하지 않고, 로그인 정보나 주문·배송·결제 정보는 읽지 않아요.
   싸다구 서버로도 보내지 않아요 (탭끼리 postMessage로만 주고받아요).
   scripts/build_site.py가 이 파일을 한 줄로 줄여 '내 상품' 화면의 북마크 버튼에 넣어요.
   주석은 블록 주석만 쓰고, 문장마다 세미콜론을 붙여 주세요 (한 줄로 합쳐지기 때문이에요). */
(function () {
  var S = 'https://sadagu.pages.dev';
  if (!/(^|\.)coupang\.com$/.test(location.hostname) || location.pathname.indexOf('/np/fbi') !== 0) {
    if (confirm('쿠팡 다시 구매 화면에서 눌러 주세요.\n지금 그 화면을 열까요?')) location.href = 'https://www.coupang.com/np/fbi';
    return;
  }
  var out = [], seen = {}, total = 0;
  var cards = document.querySelectorAll('.fbi-goods-card');
  for (var i = 0; i < cards.length; i++) {
    var c = cards[i], ks = Object.keys(c), k = null;
    for (var j = 0; j < ks.length; j++) {
      if (ks[j].indexOf('__reactFiber') === 0) { k = ks[j]; break; }
    }
    var f = k ? c[k] : null;
    for (var n = 0; n < 8 && f; n++, f = f.return) {
      var p = f.memoizedProps, d = p && p.data;
      if (d && d.id && d.title) {
        if (p.totalCount) total = p.totalCount;
        var key = d.id + '-' + (d.vendorItemId || '');
        if (!seen[key]) {
          seen[key] = 1;
          out.push([String(d.id), String(d.itemId || ''), String(d.vendorItemId || ''), String(d.title).slice(0, 100), parseInt(String(d.salesPrice || '').replace(/[^0-9]/g, ''), 10) || 0, d.purchaseCount | 0, (d.soldOut || d.temporaryOos) ? 1 : 0, String(d.thumbnailSquare || '')]);
        }
        break;
      }
    }
  }
  if (!out.length) {
    alert('상품을 읽지 못했어요.\n다시 구매 목록이 화면에 보이는지 확인해 주세요.\n그래도 안 되면 싸다구 내 상품 화면에서 북마크 버튼을 새로 받아 주세요.');
    return;
  }
  if (total > out.length && !confirm('다시 구매 ' + total + '개 중 ' + out.length + '개가 화면에 불러와져 있어요.\n\n나머지도 담으려면 [취소]를 누르고, 목록을 끝까지 내린 뒤 다시 눌러 주세요.\n지금 ' + out.length + '개만 보낼까요?')) return;
  /* 새 탭이 다 열릴 때까지 0.3초마다 건네고, 싸다구 탭이 받았다고 답하면 멈춰요.
     받는 주소를 싸다구로 정해 두어서 다른 사이트는 이 목록을 받을 수 없어요. */
  var w = window.open(S + '/mine/?from=coupang', '_blank');
  if (!w) {
    alert('새 탭이 막혔어요. 이 사이트의 팝업을 허용한 뒤 다시 눌러 주세요.');
    return;
  }
  var msg = { type: 'sadagu-import', v: 1, total: total, items: out };
  var done = false, tries = 0, timer = 0;
  var stop = function () {
    done = true;
    clearInterval(timer);
    removeEventListener('message', on);
  };
  var on = function (e) {
    if (e.origin === S && e.data && e.data.type === 'sadagu-got') stop();
  };
  addEventListener('message', on);
  timer = setInterval(function () {
    if (done || ++tries > 80 || w.closed) return stop();
    try { w.postMessage(msg, S); } catch (err) { }
  }, 300);
})();
