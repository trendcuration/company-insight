"""DART 기업코드(CORPCODE.xml)에서 상장사만 뽑아 작은 색인(data/corp_index.json)을 만든다.

배경: 런타임에 30MB XML을 내려받고(DART가 느리면 수 분) 요청마다 통째로 파싱(약 3초·200MB)하면
무료 서버에서 첫 요청이 타임아웃/메모리 부족으로 실패한다. 상장사(약 3,900곳)만 담은 색인을
저장소에 넣어두고 런타임엔 이 JSON만 읽는다.

사용법 (상장사 변동이 있을 때 가끔 갱신하면 된다):
    DART_API_KEY=... python scripts/build_corp_index.py            # DART에서 내려받아 생성
    python scripts/build_corp_index.py path/to/CORPCODE.xml        # 이미 받은 XML로 생성
"""
from __future__ import annotations

import io
import json
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = ROOT / "data" / "corp_index.json"


def _load_xml_bytes(argv: list[str]) -> bytes:
    if len(argv) > 1:
        return Path(argv[1]).read_bytes()
    key = os.getenv("DART_API_KEY")
    if not key:
        sys.exit("DART_API_KEY 환경변수가 필요합니다 (또는 CORPCODE.xml 경로를 인자로 전달).")
    url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={key}"
    with urllib.request.urlopen(url, timeout=600) as resp:  # DART가 느릴 수 있어 넉넉히
        raw = resp.read()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        return zf.read(zf.namelist()[0])


def main(argv: list[str]) -> None:
    xml_bytes = _load_xml_bytes(argv)
    by_stock: dict[str, dict[str, str]] = {}
    for _event, elem in ET.iterparse(io.BytesIO(xml_bytes), events=("end",)):
        if elem.tag != "list":
            continue
        stock_code = (elem.findtext("stock_code") or "").strip()
        corp_code = (elem.findtext("corp_code") or "").strip()
        corp_name = (elem.findtext("corp_name") or "").strip()
        if stock_code and corp_code and corp_name:
            by_stock[stock_code] = {"corp_code": corp_code, "corp_name": corp_name}
        elem.clear()

    OUT_PATH.parent.mkdir(exist_ok=True)
    OUT_PATH.write_text(
        json.dumps({"by_stock": by_stock}, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"상장사 {len(by_stock):,}곳 → {OUT_PATH} ({OUT_PATH.stat().st_size / 1024:.0f}KB)")


if __name__ == "__main__":
    main(sys.argv)
