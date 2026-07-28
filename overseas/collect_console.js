// OPSI 케이스 수집 (개선판) — 콘솔에 붙여넣고 Enter.
// 변경점: (1) Load more 클릭을 천천히(3.5s) → Cloudflare 403 회피
//         (2) 끝나면 clipboard 복사 + JSON 파일 자동 다운로드(포커스 문제 대비)
//         (3) 중간에 FacetWP가 403으로 깨져도 그때까지 모은 건 저장
// 결과 파일:  Downloads\opsi_cases_NNN.json
//   →  python overseas\import_cases.py %USERPROFILE%\Downloads\opsi_cases_60.json
(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

  const collect = () => {
    const byUrl = new Map();
    document.querySelectorAll('a[href*="/innovations/"]').forEach((a) => {
      const url = a.href.split('#')[0].split('?')[0].replace(/\/$/, '');
      let title = (a.textContent || '').replace(/\s+/g, ' ').trim();
      if (!url) return;
      const card = a.closest('article, li, .fwpl-result, [class*="result"], .card') || a.parentElement;
      let country = '';
      if (card) {
        const c = card.querySelector('[class*="country"], [class*="Country"]');
        if (c) country = (c.textContent || '').replace(/\s+/g, ' ').trim();
        if (!country) { const img = card.querySelector('img[alt]'); if (img && /^[A-Z]/.test(img.alt) && img.alt.length < 40) country = img.alt.trim(); }
      }
      const prev = byUrl.get(url);
      if (!prev) byUrl.set(url, { source_url: url, title, country, level_of_government: 'central' });
      else { if (title.length > (prev.title || '').length) prev.title = title; if (!prev.country && country) prev.country = country; }
    });
    return [...byUrl.values()].filter((c) => (c.title || '').length >= 6);
  };

  const findMore = () =>
    [...document.querySelectorAll('.facetwp-load-more, a.facetwp-load-more, button, a')]
      .find((b) => /load more|더\s*보기|더보기|show more/i.test(b.textContent || '') && b.offsetParent !== null);

  let guard = 0, lastLinks = -1, stall = 0;
  console.log('▶ Load more 자동 클릭 시작(3.5초 간격, Cloudflare 회피)…');
  while (guard++ < 300) {
    const btn = findMore();
    if (!btn) { console.log('· Load more 버튼 없음(끝 또는 차단).'); break; }
    btn.click();
    await sleep(3500);                                  // 천천히 → 403 회피
    let w = 0;
    while (document.querySelector('.facetwp-loading, .facetwp-load-more.loading') && w++ < 40) await sleep(300);
    const n = document.querySelectorAll('a[href*="/innovations/"]').length;
    window.__opsi = collect();                          // 매회 저장(중간에 깨져도 보존)
    if (n === lastLinks) { if (++stall >= 3) { console.log('· 더 안 늘어남(끝).'); break; } }
    else { stall = 0; lastLinks = n; console.log('  …링크', n, '개 · 케이스', window.__opsi.length, '건'); }
  }

  const cases = collect();
  window.__opsi = cases;
  console.log('✅ 최종 수집:', cases.length, '건');

  // 1) 파일 자동 다운로드 (포커스 불필요 · 가장 확실)
  try {
    const blob = new Blob([JSON.stringify(cases, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'opsi_cases_' + cases.length + '.json';
    document.body.appendChild(a); a.click(); a.remove();
    console.log('💾 Downloads\\' + a.download + ' 저장됨 →  python overseas\\import_cases.py %USERPROFILE%\\Downloads\\' + a.download);
  } catch (e) { console.log('다운로드 실패:', e); }

  // 2) 클립보드도 시도(--watch-clip용). 실패해도 위 파일이 있으니 괜찮음.
  try { copy(JSON.stringify(cases, null, 2)); console.log('📋 클립보드에도 복사됨(--watch-clip 자동 임포트).'); }
  catch (e) { console.log('(clipboard 복사는 실패 — 위 다운로드 파일을 쓰세요. 또는 콘솔 클릭 후: copy(JSON.stringify(window.__opsi)) )'); }

  return cases.length;
})();
