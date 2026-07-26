// build_fiscal.mjs — 세출예산 xlsx/csv → data/fiscal.json 전처리 (연 1회 수동 실행)
//
// 원본: 공공데이터포털 '재정경제부_세목 예산편성현황(총지출)' 등. 인증키 불필요.
// 사업명+연도로 집계해 사업별 예산 시계열(series)을 만든다.
//
// 준비 (최초 1회): xlsx 리더 설치
//   npm install xlsx
//
// 사용법 (저장소 루트에서, 파일을 그 폴더에 두고):
//   node scripts/build_fiscal.mjs fiscal_by_project_2020.xlsx fiscal_by_project_2021.xlsx ^
//        fiscal_by_project_2022.xlsx fiscal_by_project_2023.xlsx fiscal_by_project_2024.xlsx
//   → data/fiscal.json 생성  (.csv 도 함께 지원)

import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

// 실제 헤더: 사업명 · 소관부처 · 연도 · 예산액. 공백 무시 부분일치로 찾는다.
const NAME_COLS = ["사업명", "세부사업명", "세부사업", "detailBizNm"];
const MINISTRY_COLS = ["소관부처", "소관부처명", "부처명", "deptNm"];
const YEAR_COLS = ["연도", "회계연도", "fyr", "YEAR"];
const AMOUNT_COLS = ["예산액", "국회확정", "확정액", "예산현액", "amount"];
const AMOUNT_UNIT = "원";

function decodeSmart(buf) {
  let s = new TextDecoder("utf-8", {fatal: false}).decode(buf);
  if ((s.match(/�/g) || []).length > 5) {
    try { s = new TextDecoder("euc-kr").decode(buf); } catch { /* keep */ }
  }
  return s.replace(/^﻿/, "");
}

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

let XLSX = null;
function readRows(file) {
  if (/\.(xlsx|xls)$/i.test(file)) {
    if (!XLSX) {
      try { XLSX = createRequire(import.meta.url)("xlsx"); }
      catch { console.error("xlsx 모듈이 없습니다. 먼저 실행: npm install xlsx"); process.exit(1); }
    }
    const wb = XLSX.readFile(file);
    const ws = wb.Sheets[wb.SheetNames[0]];
    return XLSX.utils.sheet_to_json(ws, {header: 1, raw: true, defval: ""});
  }
  return parseCsv(decodeSmart(fs.readFileSync(file))).filter(r => r.length > 1);
}

function colIndex(header, candidates) {
  const norm = header.map(h => String(h).replace(/\s/g, ""));
  for (const cand of candidates) {
    const c = cand.replace(/\s/g, "");
    let i = norm.findIndex(h => h === c);
    if (i < 0) i = norm.findIndex(h => h.includes(c));
    if (i >= 0) return i;
  }
  return -1;
}

const files = process.argv.slice(2);
if (!files.length) {
  console.error("사용법: node scripts/build_fiscal.mjs <xlsx|csv...>");
  process.exit(1);
}

const acc = new Map();
for (const file of files) {
  const rows = readRows(file);
  if (!rows.length) { console.error(`[비어있음] ${file}`); continue; }
  const header = rows[0];
  const iName = colIndex(header, NAME_COLS);
  const iMin = colIndex(header, MINISTRY_COLS);
  const iYear = colIndex(header, YEAR_COLS);
  const iAmt = colIndex(header, AMOUNT_COLS);
  if (iName < 0 || iYear < 0 || iAmt < 0) {
    console.error(`[건너뜀] ${file}: 필요한 컬럼을 못 찾음.`);
    console.error("  실제 헤더:", header.join(" | "));
    continue;
  }
  for (const r of rows.slice(1)) {
    const name = String(r[iName] ?? "").trim();
    if (!name) continue;
    const year = parseInt(String(r[iYear] ?? "").replace(/\D/g, ""), 10);
    const amount = parseInt(String(r[iAmt] ?? "0").replace(/[^\d-]/g, ""), 10) || 0;
    if (!year) continue;
    if (!acc.has(name)) acc.set(name, {name, ministry: String(r[iMin] ?? "").trim(), series: new Map()});
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

fs.mkdirSync("data", {recursive: true});
const outPath = path.join("data", "fiscal.json");
fs.writeFileSync(outPath, JSON.stringify(
  {unit: AMOUNT_UNIT, built: files, items: out}, null, 0), "utf-8");
console.error(`\n완료: ${outPath} — 사업 ${out.length}개 (금액 단위 ${AMOUNT_UNIT})`);
