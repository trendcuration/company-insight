import './style.css';
import { loadFullScreenAd, showFullScreenAd } from '@apps-in-toss/web-framework';

// ── 설정 ─────────────────────────────────────────────────────────
// 백엔드(FastAPI) 배포 주소. 빌드 시 VITE_API_BASE_URL 환경변수로 지정.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

// 앱인토스 전면광고 그룹 ID
const AD_GROUP_ID = 'ait.v2.live.a557ea481b1d4248';

// ── DOM ──────────────────────────────────────────────────────────
const form = document.getElementById('search-form');
const input = document.getElementById('company-input');
const btn = document.getElementById('submit-btn');
const loading = document.getElementById('loading');
const errorBox = document.getElementById('error-box');
const errorMsg = document.getElementById('error-msg');
const resultSection = document.getElementById('result-section');
const reportEl = document.getElementById('report');

function show(el) { el.classList.remove('hidden'); }
function hide(el) { el.classList.add('hidden'); }

function setLoading(active) {
  btn.disabled = active;
  btn.textContent = active ? '분석 중…' : '리포트 생성';
}

function showError(msg) {
  errorMsg.textContent = msg || '알 수 없는 오류가 발생했습니다.';
  show(errorBox);
  hide(loading);
  hide(resultSection);
}

// ── 포맷 헬퍼 ─────────────────────────────────────────────────────
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
}[c]));

function fmtEok(v) {
  if (v == null) return 'N/A';
  if (Math.abs(v) >= 10000) return `${(v / 10000).toFixed(1)}조`;
  return `${Math.round(v).toLocaleString('ko-KR')}억`;
}

function fmtWon(v) {
  return v == null ? 'N/A' : `${v.toLocaleString('ko-KR')}원`;
}

const signClass = (v) => (v == null ? '' : v >= 0 ? 'up' : 'down');

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

// ── 리포트 HTML 렌더링 ────────────────────────────────────────────
function renderReport(data) {
  const si = data.stock_info;
  const parts = [];

  // 헤더
  parts.push(`
    <div class="rp-head">
      <h2>${esc(data.company_name)}${data.stock_code ? ` <span class="rp-code">${esc(data.stock_code)}</span>` : ''}</h2>
    </div>
  `);

  // 현재 주가 + 투자지표 + 52주 범위
  if (si && si.current_price != null) {
    const chg = si.price_change;
    const chgHtml = chg != null
      ? `<span class="rp-change ${signClass(chg)}">${chg >= 0 ? '▲' : '▼'} ${Math.abs(chg).toFixed(2)}%</span>`
      : '';

    const kvs = [
      si.market_cap ? ['시가총액', si.market_cap] : null,
      si.per != null ? ['PER', `${si.per.toFixed(1)}배`] : null,
      si.pbr != null ? ['PBR', `${si.pbr.toFixed(2)}배`] : null,
      si.eps != null ? ['EPS', fmtWon(Math.round(si.eps))] : null,
      si.bps != null ? ['BPS', fmtWon(Math.round(si.bps))] : null,
      si.volume ? ['거래량', si.volume] : null,
      si.foreign_ratio != null ? ['외국인 비율', `${si.foreign_ratio.toFixed(1)}%`] : null,
    ].filter(Boolean);
    const grid = kvs.length
      ? `<div class="rp-grid">${kvs.map(([k, v]) => `<div class="rp-kv"><span>${k}</span><strong>${esc(v)}</strong></div>`).join('')}</div>`
      : '';

    // 52주 범위 바
    let range = '';
    if (si.high_52w && si.low_52w && si.high_52w > si.low_52w) {
      const pos = Math.min(100, Math.max(0,
        ((si.current_price - si.low_52w) / (si.high_52w - si.low_52w)) * 100));
      range = `
        <div class="rp-range">
          <div class="rp-range-labels">
            <span>52주 최저 ${fmtWon(si.low_52w)}</span>
            <span>52주 최고 ${fmtWon(si.high_52w)}</span>
          </div>
          <div class="rp-range-bar">
            <div class="rp-range-fill" style="width:${pos.toFixed(1)}%"></div>
            <div class="rp-range-dot" style="left:${pos.toFixed(1)}%"></div>
          </div>
        </div>`;
    }

    parts.push(`
      <div class="rp-card">
        <div class="rp-label">현재 주가</div>
        <div class="rp-price ${signClass(chg)}">${fmtWon(si.current_price)}${chgHtml}</div>
        ${grid}${range}
      </div>
    `);
  }

  // 재무제표 (손익)
  if (data.financials && data.financials.length) {
    const fins = [...data.financials].sort((a, b) => a.year - b.year);
    const rows = fins.map((f) => `
      <tr>
        <td>${esc(f.label || String(f.year))}</td>
        <td>${fmtEok(f.revenue)}</td>
        <td class="${signClass(f.operating_income)}">${fmtEok(f.operating_income)}</td>
        <td class="${signClass(f.net_income)}">${fmtEok(f.net_income)}</td>
      </tr>
    `).join('');
    parts.push(`
      <div class="rp-card">
        <div class="rp-label">실적 <small>(연결 기준, 단위: 억원)</small></div>
        <table class="rp-table">
          <thead><tr><th>연도</th><th>매출액</th><th>영업이익</th><th>순이익</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `);

    // 재무상태 (자산/부채/자본)
    const hasBS = fins.some((f) => f.total_assets != null);
    if (hasBS) {
      const bsRows = fins.map((f) => `
        <tr>
          <td>${esc(f.label || String(f.year))}</td>
          <td>${fmtEok(f.total_assets)}</td>
          <td>${fmtEok(f.total_liabilities)}</td>
          <td>${fmtEok(f.total_equity)}</td>
        </tr>
      `).join('');
      parts.push(`
        <div class="rp-card">
          <div class="rp-label">재무 상태 <small>(단위: 억원)</small></div>
          <table class="rp-table">
            <thead><tr><th>연도</th><th>자산</th><th>부채</th><th>자본</th></tr></thead>
            <tbody>${bsRows}</tbody>
          </table>
        </div>
      `);
    }
  }

  // 배당 (DART 우선, 없으면 시세 API의 배당수익률)
  const dv = data.dividend;
  const divItems = [];
  if (dv && dv.dps != null) divItems.push(['주당배당금', fmtWon(dv.dps)]);
  if (dv && dv.payout_ratio != null) divItems.push(['배당성향', `${dv.payout_ratio.toFixed(1)}%`]);
  const dYield = (dv && dv.dividend_yield != null) ? dv.dividend_yield
    : (si && si.dividend_yield != null ? si.dividend_yield : null);
  if (dYield != null) divItems.push(['시가배당률', `${dYield.toFixed(2)}%`]);
  if (divItems.length) {
    parts.push(`
      <div class="rp-card">
        <div class="rp-label">배당</div>
        <div class="rp-stats">
          ${divItems.map(([k, v]) => `<div class="rp-stat"><span>${k}</span><strong>${esc(v)}</strong></div>`).join('')}
        </div>
      </div>
    `);
  }

  // 증권가 전망
  const con = data.consensus;
  if (con && con.target_avg != null) {
    const range = con.target_high != null && con.target_low != null
      ? `<div class="rp-meta">최고 ${fmtWon(con.target_high)} · 최저 ${fmtWon(con.target_low)}</div>`
      : '';
    const upside = si && si.current_price
      ? `<div class="rp-meta">현재가 대비 상승여력 <strong class="${signClass(con.target_avg - si.current_price)}">${(((con.target_avg / si.current_price) - 1) * 100).toFixed(1)}%</strong></div>`
      : '';
    let opinions = '';
    if (con.buy_count != null || con.neutral_count != null || con.sell_count != null) {
      opinions = `
        <div class="rp-opinions">
          <span class="op buy">매수 ${con.buy_count ?? 0}</span>
          <span class="op neutral">중립 ${con.neutral_count ?? 0}</span>
          <span class="op sell">매도 ${con.sell_count ?? 0}</span>
        </div>`;
    }
    parts.push(`
      <div class="rp-card">
        <div class="rp-label">증권가 전망</div>
        <div class="rp-target">목표주가 평균 <strong>${fmtWon(con.target_avg)}</strong></div>
        ${range}${upside}${opinions}
      </div>
    `);
  }

  // 주요 뉴스
  if (data.news && data.news.length) {
    const newsRows = data.news.map((n) => {
      const meta = [n.press, n.date].filter(Boolean).join(' · ');
      const inner = `
        <div class="rp-news-title">${esc(n.title)}</div>
        ${meta ? `<div class="rp-news-meta">${esc(meta)}</div>` : ''}`;
      return n.url
        ? `<a class="rp-news-item" href="${esc(n.url)}" target="_blank" rel="noopener">${inner}</a>`
        : `<div class="rp-news-item">${inner}</div>`;
    }).join('');
    parts.push(`
      <div class="rp-card">
        <div class="rp-label">주요 뉴스</div>
        <div class="rp-news">${newsRows}</div>
      </div>
    `);
  }

  if (parts.length <= 1) {
    parts.push(`<div class="rp-card"><div class="rp-meta">수집된 데이터가 없습니다.</div></div>`);
  }

  parts.push(`
    <div class="rp-footer">
      데이터 출처: DART Open API · 네이버 금융 | 투자 판단의 책임은 본인에게 있습니다
    </div>
  `);

  reportEl.innerHTML = parts.join('');
  hide(loading);
  hide(errorBox);
  show(resultSection);
}

// ── 전면광고 ──────────────────────────────────────────────────────
// 데이터 수신이 끝난 뒤에만 호출한다 (조회 중에 광고부터 뜨면 안 됨).
// 광고 종료(dismissed) 후 결과를 보여준다. 토스 앱 밖(일반 브라우저)이나
// 광고 실패 시에는 광고 없이 바로 결과를 보여준다 (앱 중단 금지).
function runInterstitialAd() {
  return new Promise((resolve) => {
    let settled = false;
    const done = () => {
      if (!settled) {
        settled = true;
        resolve();
      }
    };
    // 광고가 10초 안에 못 뜨면 결과 표시를 막지 않는다
    const timeout = setTimeout(done, 10000);

    try {
      loadFullScreenAd({
        options: { adGroupId: AD_GROUP_ID },
        onEvent: (event) => {
          if (event.type === 'loaded') {
            try {
              showFullScreenAd({
                options: { adGroupId: AD_GROUP_ID },
                onEvent: (showEvent) => {
                  if (showEvent.type === 'dismissed' || showEvent.type === 'failedToShow') {
                    clearTimeout(timeout);
                    done();
                  }
                },
                onError: () => {
                  clearTimeout(timeout);
                  done();
                },
              });
            } catch {
              clearTimeout(timeout);
              done();
            }
          }
        },
        onError: () => {
          clearTimeout(timeout);
          done();
        },
      });
    } catch {
      // 토스 앱 밖(일반 브라우저)에서는 SDK 브릿지가 없어 예외 발생 — 광고 생략
      clearTimeout(timeout);
      done();
    }
  });
}

// ── 리포트 생성 ───────────────────────────────────────────────────
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const name = input.value.trim();
  if (!name) return;

  hide(errorBox);
  hide(resultSection);
  show(loading);
  setLoading(true);

  try {
    // 데이터를 먼저 모두 받아온 뒤 — 광고 없이 실패하면 바로 오류 표시.
    // 성공했을 때만 0.5초 뒤 전면광고를 띄우고, 광고가 끝나면 결과를 보여준다.
    const response = await fetch(`${API_BASE_URL}/api/data/${encodeURIComponent(name)}`);

    if (response.ok) {
      const data = await response.json();
      await sleep(2000);
      await runInterstitialAd();
      renderReport(data);
    } else {
      let detail = '서버 오류가 발생했습니다.';
      try {
        const json = await response.json();
        detail = json.detail || json.error || detail;
      } catch {}
      showError(detail);
    }
  } catch {
    showError('네트워크 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
  } finally {
    setLoading(false);
  }
});
