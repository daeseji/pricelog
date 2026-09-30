/* 싸다구 가격 알림 — 페이지와 서비스 워커(sw.js)가 함께 쓰는 판단 로직
 *
 * 알림 규칙 (상품 이름마다 하나)
 *   { on: true,
 *     target: { on, v },   // v원 이하가 되면
 *     avg:    { on, v },   // 평균가보다 v% 이상 싸지면 (기록 3번 이상)
 *     low:    { on, v } }  // 최근 v일 중 가장 싸지면 (v = 0 이면 전체 기록)
 */
(function (root) {
  const won = n => Math.round(n).toLocaleString('ko-KR') + '원';
  const LOW_LABEL = { 0: '전체 기록', 7: '최근 7일', 14: '최근 2주', 30: '최근 30일', 90: '최근 3개월' };

  function toTime(s) {
    const [d, t = '00:00'] = String(s).split(' ');
    const [y, m, dd] = d.split('-').map(Number);
    const [h, mi] = t.split(':').map(Number);
    return Date.UTC(y, m - 1, dd, h || 0, mi || 0);
  }

  // history의 마지막 기록이 각 조건을 만족하는지 봐요
  function hits(history, rule) {
    const out = [];
    if (!rule || !rule.on || !history || !history.length) return out;
    const prices = history.map(h => Number(h.price));
    const n = prices.length, curr = prices[n - 1];

    if (rule.target && rule.target.on && rule.target.v > 0 && curr <= rule.target.v) {
      out.push({ type: 'target', text: `목표 ${won(rule.target.v)} 이하가 됐어요` });
    }
    if (rule.avg && rule.avg.on && rule.avg.v > 0 && n >= 3) {
      const avg = prices.reduce((s, x) => s + x, 0) / n;
      const off = (avg - curr) / avg;
      if (off * 100 >= rule.avg.v) out.push({ type: 'avg', text: `평균가(${won(avg)})보다 ${Math.round(off * 100)}% 싸요` });
    }
    if (rule.low && rule.low.on) {
      const days = Number(rule.low.v) || 0;
      const from = days ? toTime(history[n - 1].date) - days * 86400000 : -Infinity;
      const others = history.slice(0, -1).filter(h => toTime(h.date) >= from).map(h => Number(h.price));
      if (others.length && curr <= Math.min(...others) && curr < Math.max(...others)) {
        out.push({ type: 'low', text: `${LOW_LABEL[days] || `최근 ${days}일`} 중 가장 싼 가격이에요` });
      }
    }
    return out;
  }

  // 새로 알릴 것만 골라요: 조건에 막 들어왔거나, 지난 알림보다 더 싸졌을 때
  function fresh(history, rule, sent) {
    const now = hits(history, rule);
    if (!now.length) return [];
    const last = history[history.length - 1];
    const before = new Set(hits(history.slice(0, -1), rule).map(h => h.type));
    return now.filter(h => {
      const prev = sent[h.type];
      if (prev && prev.date === last.date) return false;
      if (!prev || !before.has(h.type)) return true;
      return Number(last.price) < prev.price;
    });
  }

  // 알림을 보낸 뒤 기록해 둬요
  function mark(sent, list, last) {
    for (const h of list) sent[h.type] = { date: last.date, price: Number(last.price) };
    return sent;
  }

  function hasActive(rule) {
    return !!(rule && rule.on && ((rule.target && rule.target.on && rule.target.v > 0) || (rule.avg && rule.avg.on && rule.avg.v > 0) || (rule.low && rule.low.on)));
  }

  root.SDGAlerts = { hits, fresh, mark, hasActive, won, LOW_LABEL };
})(typeof self !== 'undefined' ? self : this);
