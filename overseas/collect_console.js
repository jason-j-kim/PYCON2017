// OPSI 케이스 수집 — 콘솔에 붙여넣고 Enter.
// 원리: 직접 fetch()를 만들지 않는다(그러면 Cloudflare가 403으로 막는다).
//   대신 페이지의 "Load more" 버튼을 자동으로 끝까지 눌러(=FacetWP 자신의 JS가
//   요청하므로 Cloudflare를 통과) 580건을 모두 화면(DOM)에 올린 뒤, DOM만 긁는다.
// 결과: 클립보드에 JSON 배열이 복사됨 →  python overseas/import_cases.py --watch-clip 창이 자동 임포트.
(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  const findMore = () =>
    [...document.querySelectorAll(
      '.facetwp-load-more, a.facetwp-load-more, button, a'
    )].find(
      (b) => /load more|더\s*보기|더보기|show more/i.test(b.textContent || '') &&
             b.offsetParent !== null
    );

  // 1) "Load more"를 다 눌러 모든 케이스를 DOM에 올린다.
  let guard = 0, lastCount = -1, stall = 0;
  console.log('▶ Load more 자동 클릭 시작…');
  while (guard++ < 200) {
    const btn = findMore();
    if (!btn) { console.log('· Load more 버튼 사라짐(끝).'); break; }
    btn.click();
    await sleep(1600);
    // 로딩 스피너가 있으면 사라질 때까지 대기
    let w = 0;
    while (document.querySelector('.facetwp-loading, .facetwp-load-more.loading') && w++ < 25)
      await sleep(300);
    const n = document.querySelectorAll('a[href*="/innovations/"]').length;
    if (n === lastCount) { if (++stall >= 3) { console.log('· 더 안 늘어남(끝).'); break; } }
    else { stall = 0; lastCount = n; console.log('  …현재', n, '개 링크'); }
  }

  // 2) DOM에서 케이스 카드 수집 (fetch 없음 → Cloudflare 없음).
  const byUrl = new Map();
  document.querySelectorAll('a[href*="/innovations/"]').forEach((a) => {
    const url = a.href.split('#')[0].split('?')[0].replace(/\/$/, '');
    let title = (a.textContent || '').replace(/\s+/g, ' ').trim();
    if (!url) return;
    // 같은 카드에 이미지 링크(제목 없음)+제목 링크가 둘 다 있음 → 더 긴 제목을 채택
    const card = a.closest('article, li, .fwpl-result, [class*="result"], .card') || a.parentElement;
    let country = '';
    if (card) {
      const c = card.querySelector('[class*="country"], [class*="Country"]');
      if (c) country = (c.textContent || '').replace(/\s+/g, ' ').trim();
      if (!country) {
        const img = card.querySelector('img[alt]');
        if (img && /^[A-Z]/.test(img.alt) && img.alt.length < 40) country = img.alt.trim();
      }
    }
    const prev = byUrl.get(url);
    if (!prev) byUrl.set(url, { source_url: url, title, country, level_of_government: 'central' });
    else {
      if (title.length > (prev.title || '').length) prev.title = title;
      if (!prev.country && country) prev.country = country;
    }
  });

  const cases = [...byUrl.values()].filter((c) => (c.title || '').length >= 6);
  console.log('✅ 수집:', cases.length, '건');
  try { copy(JSON.stringify(cases, null, 2)); console.log('📋 클립보드에 복사됨 → --watch-clip 창이 자동 임포트합니다.'); }
  catch (e) { window.__opsi = cases; console.log('copy() 실패. window.__opsi 에 저장됨. 콘솔에서: copy(JSON.stringify(window.__opsi))'); }
  return cases.length;
})();
