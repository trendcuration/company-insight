(function () {
  const form = document.getElementById('search-form');
  const input = document.getElementById('company-input');
  const btn = document.getElementById('submit-btn');
  const loading = document.getElementById('loading');
  const errorBox = document.getElementById('error-box');
  const errorMsg = document.getElementById('error-msg');
  const resultSection = document.getElementById('result-section');
  const resultTitle = document.getElementById('result-title');
  const resultImg = document.getElementById('result-img');
  const downloadBtn = document.getElementById('download-btn');

  let currentObjectUrl = null;

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

  function showResult(url, name) {
    if (currentObjectUrl) {
      URL.revokeObjectURL(currentObjectUrl);
    }
    currentObjectUrl = url;
    resultImg.src = url;
    resultTitle.textContent = `${name} 인포그래픽 리포트`;
    downloadBtn.href = url;
    downloadBtn.download = `${name}_company_insight.png`;
    hide(loading);
    hide(errorBox);
    show(resultSection);
  }

  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    const name = input.value.trim();
    if (!name) return;

    hide(errorBox);
    hide(resultSection);
    show(loading);
    setLoading(true);

    try {
      const resp = await fetch(
        `/api/report/${encodeURIComponent(name)}`,
        { method: 'POST' }
      );

      if (resp.ok) {
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        showResult(url, name);
      } else {
        let detail = '서버 오류가 발생했습니다.';
        try {
          const json = await resp.json();
          detail = json.detail || json.error || detail;
        } catch (_) {}
        showError(detail);
      }
    } catch (err) {
      showError('네트워크 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
    } finally {
      setLoading(false);
    }
  });

  // Enter key on input
  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
      form.dispatchEvent(new Event('submit'));
    }
  });
})();
