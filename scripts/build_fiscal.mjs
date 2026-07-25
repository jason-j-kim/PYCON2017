// build_fiscal.mjs — 세출예산 CSV → data/fiscal.json 전처리 (연 1회 수동 실행)
//
// 원본: 공공데이터포털 '재정경제부_세목 예산편성현황(총지출)'
//   https://www.data.go.kr/data/15083329/fileData.do  (CSV·XLSX, 인증키 불필요)
// 세목 단위 행을 '세부사업명 + 연도'로 집계해 만 단위로 줄인다. 세목까지 내려가지 않는다.
//
// 사용법 (저장소 루트에서, CSV로 내려받은 뒤):
//   node scripts/build_fiscal.mjs 2022.csv 2023.csv 2024.csv 2025.csv 2026.csv
//   → data/fiscal.json 생성
//
// 컬럼명은 파일마다 다를 수 있다. 실제 헤더를 확인해 아래 후보를 조정하라.
// 금액 단위(원/천원/백만원)도 원본에서 확인해 통일하고, AMOUNT_UNIT에 적어라.

import fs from "node:fs";
import path from "node:path";

const NAME_COLS = ["세부사업명", "세부사업", "detailBizNm", "BIZ_NM"];
const MINISTRY_COLS = ["소관부처명", "소관부처", "부처명", "deptNm"];
const YEAR_COLS = ["회계연도", "연도", "fyr", "YEAR"];
// 예산구분이 여러 값이면 국회확정을 쓴다(정부안은 집행 증거가 아니다).
const AMOUNT_COLS = ["국회확정", "확정액", "예산현액", "예산액", "amount"];
const AMOUNT_UNIT = "원";  // 원본에서 확인해 맞출 것

// ── 간단한 CSV 파서(따옴표·쉼표 처리) ──
function parseCsv(text) {
  const rows = [];
  let row = [], field = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') q = false;
      else field += c;
    } else if (c === '"') q = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n") { row.push(field); rows.push(row); row = []; field = ""; }
    else if (c !== "\r") field += c;
  }
  if (field.length || row.length) { row.push(field); rows.push(row); }
  return rows;
}

function colIndex(header, candidates) {
  for (const cand of candidates) {
    const i = header.findIndex(h => h.trim() === cand);
    if (i >= 0) return i;
  }
  return -1;
}

const files = process.argv.slice(2);
if (!files.length) {
  console.error("사용법: node scripts/build_fiscal.mjs <csv...>");
  process.exit(1);
}

const acc = new Map();  // name → {name, ministry, series: Map(year→amount)}
for (const file of files) {
  const raw = fs.readFileSync(file, "utf-8");
  const rows = parseCsv(raw).filter(r => r.length > 1);
  if (!rows.length) continue;
  const header = rows[0];
  const iName = colIndex(header, NAME_COLS);
  const iMin = colIndex(header, MINISTRY_COLS);
  const iYear = colIndex(header, YEAR_COLS);
  const iAmt = colIndex(header, AMOUNT_COLS);
  if (iName < 0 || iYear < 0 || iAmt < 0) {
    console.error(`[건너뜀] ${file}: 필요한 컬럼을 못 찾음. 헤더=`, header);
    continue;
  }
  for (const r of rows.slice(1)) {
    const name = (r[iName] || "").trim();
    if (!name) continue;
    const year = parseInt((r[iYear] || "").replace(/\D/g, ""), 10);
    const amount = parseInt((r[iAmt] || "0").replace(/[^\d-]/g, ""), 10) || 0;
    if (!year) continue;
    if (!acc.has(name)) acc.set(name, {name, ministry: (r[iMin] || "").trim(), series: new Map()});
    const g = acc.get(name);
    g.series.set(year, (g.series.get(year) || 0) + amount);
  }
  console.error(`[읽음] ${file}: 누적 사업 ${acc.size}개`);
}

const out = [...acc.values()].map(g => ({
  name: g.name, ministry: g.ministry,
  series: [...g.series.entries()].sort((a, b) => a[0] - b[0])
    .map(([year, amount]) => ({year, amount})),
}));

const outPath = path.join("data", "fiscal.json");
fs.mkdirSync("data", {recursive: true});
fs.writeFileSync(outPath, JSON.stringify(
  {unit: AMOUNT_UNIT, built: files, items: out}, null, 0), "utf-8");
console.error(`\n완료: ${outPath} — 사업 ${out.length}개 (금액 단위 ${AMOUNT_UNIT})`);
