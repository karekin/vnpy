from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

import requests

from vnpy.web.contracts.tenx_hunter import (
    TenxFreshnessRow,
    TenxMarket,
    TenxPoliticalDisclosureSummaryRow,
    TenxPoliticalMentionRow,
    TenxPoliticalSignalResponse,
    TenxPoliticalTradeRow,
)


class PoliticalSignalService:
    """Track political market catalysts without mixing them into social heat."""

    OPEN_CABINET_TRUMP_URL = "https://open-cabinet.org/officials/trump-donald-j"

    _MENTION_SEEDS: tuple[dict[str, str], ...] = (
        {
            "symbol": "PLTR",
            "name": "Palantir Technologies",
            "event_date": "2026-04-10",
            "event_type": "public-praise",
            "status": "confirmed",
            "evidence_grade": "B",
            "headline": "特朗普公开称赞 Palantir 的军事能力",
            "summary": "多家媒体报道称特朗普在社交平台点名 Palantir 的战斗能力。该线索应进入事件驱动复核，而不是直接当作买入信号。",
            "source": "Bloomberg / TipRanks media reports",
            "source_url": "https://www.bloomberg.com/news/articles/2026-04-10/trump-singles-out-palantir-s-war-fighting-capabilities-in-post",
            "verification_note": "已由主流媒体报道，但还应补齐原始帖文截图或归档链接。",
            "next_action": "核对发言原文、合同/预算催化和期权拥挤度。",
            "watchlist_rule": "若已在 Discover 且基本面主线成立，可创建 P2 事件追踪。",
        },
        {
            "symbol": "INTC",
            "name": "Intel",
            "event_date": "2026-01-14",
            "event_type": "policy-stake",
            "status": "watching",
            "evidence_grade": "B",
            "headline": "特朗普谈及美国政府入股 Intel 以及后续跟随资金",
            "summary": "半导体政策与政府持股叙事会显著影响 INTC 的风险偏好，需要和真实披露、政策文件、价格是否已反映分开看。",
            "source": "Tom's Hardware report",
            "source_url": "https://www.tomshardware.com/tech-industry/trumps-cryptic-remark-states-apple-has-invested-in-intel-tells-press-apple-went-in-nvidia-went-in-a-lot-of-smart-people-went-in",
            "verification_note": "媒体有报道，但需补官方记者会原文。",
            "next_action": "跟踪白宫/商务部半导体公告、政府持股变化和公司 8-K。",
            "watchlist_rule": "政策线索若叠加价格突破和机构 OI，可从候选升为观察。",
        },
        {
            "symbol": "IBM",
            "name": "International Business Machines",
            "event_date": "2026-05-30",
            "event_type": "reported-quote",
            "status": "needs-verification",
            "evidence_grade": "D",
            "headline": "社群截图称特朗普表示 IBM 股票还会涨很多",
            "summary": "当前证据来自聊天截图和二级传播，不能直接记作已确认声援。先进入待核实队列。",
            "source": "user-supplied screenshot",
            "source_url": "",
            "verification_note": "缺少原始发言、视频、Truth Social 链接或白宫文字稿。",
            "next_action": "搜索原始发言和可信媒体确认，再判断是否升级为 B/C 证据。",
            "watchlist_rule": "未升级前只做提醒线索，不进入 Watchlist。",
        },
        {
            "symbol": "DELL",
            "name": "Dell Technologies",
            "event_date": "2026-05-08",
            "event_type": "reported-praise",
            "status": "needs-verification",
            "evidence_grade": "D",
            "headline": "截图称特朗普点名戴尔",
            "summary": "截图中出现 DELL，但没有原始出处。需要补来源后再关联股价表现。",
            "source": "user-supplied screenshot",
            "source_url": "",
            "verification_note": "未核验原始发言与语境。",
            "next_action": "核对白宫活动、公开发言和公司新闻稿。",
            "watchlist_rule": "原文确认前不升级，只保留待核实标签。",
        },
        {
            "symbol": "MU",
            "name": "Micron Technology",
            "event_date": "2026-05-22",
            "event_type": "reported-praise",
            "status": "needs-verification",
            "evidence_grade": "D",
            "headline": "截图称特朗普公开夸赞美光",
            "summary": "MU 属于半导体政策敏感标的，但截图本身不能证明总统声援。",
            "source": "user-supplied screenshot",
            "source_url": "",
            "verification_note": "缺少可引用原文。",
            "next_action": "补原文、检查 CHIPS/国防/数据中心相关政策催化。",
            "watchlist_rule": "若补到原始证据，再进入 Discover 政治催化标签。",
        },
        {
            "symbol": "AAPL",
            "name": "Apple",
            "event_date": "2026-03-11",
            "event_type": "reported-mention",
            "status": "needs-verification",
            "evidence_grade": "D",
            "headline": "截图称特朗普谈及苹果 CEO",
            "summary": "AAPL 的政治信号通常要区分供应链、关税和制造投资，不应只看截图中的涨幅。",
            "source": "user-supplied screenshot",
            "source_url": "",
            "verification_note": "缺少原始文本和交易披露交叉验证。",
            "next_action": "核对白宫投资页面、公司制造投资公告和关税表态。",
            "watchlist_rule": "必须同时满足原文确认和可交易事件窗口。",
        },
        {
            "symbol": "TMO",
            "name": "Thermo Fisher Scientific",
            "event_date": "2026-03-11",
            "event_type": "reported-visit",
            "status": "needs-verification",
            "evidence_grade": "D",
            "headline": "截图称特朗普参访并称赞 Thermo Fisher",
            "summary": "TMO 的线索更像政策/产业参访，需确认是否涉及订单、投资或监管催化。",
            "source": "user-supplied screenshot",
            "source_url": "",
            "verification_note": "截图不足以构成公司事件证据。",
            "next_action": "找官方行程、公司公告和媒体报道。",
            "watchlist_rule": "没有订单/政策细节前不进入观察池。",
        },
    )

    def __init__(self, timeout: int = 10) -> None:
        self._timeout = timeout
        self._session = requests.Session()

    @staticmethod
    def _now_label() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    @staticmethod
    def _int_from_text(value: str | None) -> int | None:
        if not value:
            return None
        digits = re.sub(r"[^\d]", "", value)
        return int(digits) if digits else None

    @staticmethod
    def _compact(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    def _load_open_cabinet_html(self) -> str:
        response = self._session.get(
            self.OPEN_CABINET_TRUMP_URL,
            timeout=self._timeout,
            headers={"User-Agent": "TenX Hunter Political Signals contact@tenxhunter.local"},
        )
        response.raise_for_status()
        return response.text

    def _default_disclosure(self, detail: str) -> TenxPoliticalDisclosureSummaryRow:
        return TenxPoliticalDisclosureSummaryRow(
            source="Open Cabinet / U.S. Office of Government Ethics",
            source_url=self.OPEN_CABINET_TRUMP_URL,
            filing_type="OGE 278-T Periodic Transaction Report",
            latest_filing_date="",
            transaction_window="",
            detail=detail,
        )

    def _parse_disclosure(self, html: str) -> tuple[TenxPoliticalDisclosureSummaryRow, list[TenxPoliticalTradeRow]]:
        try:
            from bs4 import BeautifulSoup
        except ImportError as exc:  # pragma: no cover - optional parser fallback
            raise RuntimeError("BeautifulSoup is required to parse Open Cabinet HTML.") from exc

        soup = BeautifulSoup(html, "html.parser")
        text = self._compact(soup.get_text(" ", strip=True))

        latest_filing_date = ""
        transaction_window = ""
        last_filing_match = re.search(
            r"Last filing:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})\s*\|\s*Transactions:\s*([A-Za-z]+\s+\d{1,2},\s+\d{4}\s*–\s*[A-Za-z]+\s+\d{1,2},\s+\d{4})",
            text,
        )
        if last_filing_match:
            latest_filing_date = last_filing_match.group(1)
            transaction_window = self._compact(last_filing_match.group(2))

        stats_match = re.search(
            r"(\d[\d,]*)\s+trades\s+(\d[\d,]*)\s+sales\s+(\d[\d,]*)\s+purchases\s+(\d[\d,]*)\s+late\s+filings",
            text,
        )
        total_trades = sales = purchases = late_filings = None
        if stats_match:
            total_trades = self._int_from_text(stats_match.group(1))
            sales = self._int_from_text(stats_match.group(2))
            purchases = self._int_from_text(stats_match.group(3))
            late_filings = self._int_from_text(stats_match.group(4))

        late_filing_pct = round(late_filings / total_trades * 100, 1) if total_trades and late_filings is not None else None
        detail_match = re.search(r"(President Donald J\. Trump.*?STOCK Act\.)", text)
        detail = detail_match.group(1) if detail_match else "特朗普披露交易需要按 OGE/278-T 原始文件复核；金额通常是区间而不是精确值。"

        trades: list[TenxPoliticalTradeRow] = []
        table = soup.find("table")
        if table is not None:
            for row in table.find_all("tr"):
                cells = [self._compact(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"], recursive=False)]
                if len(cells) != 6 or cells[0] == "Date":
                    continue
                source_link = row.find("a", href=True)
                description = re.sub(r"\s+Late$", "", cells[1]).strip()
                trades.append(
                    TenxPoliticalTradeRow(
                        date=cells[0],
                        description=description,
                        symbol=cells[2] if cells[2] != "—" else "",
                        trade_type=cells[3],
                        amount=cells[4],
                        is_late="Late" in cells[1],
                        source_url=str(source_link["href"]) if source_link else self.OPEN_CABINET_TRUMP_URL,
                    )
                )
                if len(trades) >= 12:
                    break

        disclosure = TenxPoliticalDisclosureSummaryRow(
            source="Open Cabinet / U.S. Office of Government Ethics",
            source_url=self.OPEN_CABINET_TRUMP_URL,
            filing_type="OGE 278-T Periodic Transaction Report",
            latest_filing_date=latest_filing_date,
            transaction_window=transaction_window,
            total_trades=total_trades,
            purchases=purchases,
            sales=sales,
            late_filings=late_filings,
            late_filing_pct=late_filing_pct,
            detail=detail,
        )
        return disclosure, trades

    def _mention_rows(self) -> list[TenxPoliticalMentionRow]:
        return [TenxPoliticalMentionRow(**item) for item in self._MENTION_SEEDS]

    def get_snapshot(self, market: str = "US", person: str = "trump") -> TenxPoliticalSignalResponse:
        normalized_market: TenxMarket = "US" if market.upper() == "US" else "CN"
        snapshot_at = self._now_label()
        notes: list[str] = [
            "政治声援不是基本面结论；只有完成原文、披露、价格结构三层复核后，才允许进入观察池。",
            "OGE 披露存在 30-45 天报告窗口，不能当成实时持仓流。",
        ]
        disclosure = self._default_disclosure("等待拉取 Open Cabinet / OGE 披露数据。")
        trades: list[TenxPoliticalTradeRow] = []
        data_complete = False

        try:
            disclosure, trades = self._parse_disclosure(self._load_open_cabinet_html())
            data_complete = bool(disclosure.latest_filing_date)
        except Exception as exc:  # pragma: no cover - network fallback
            notes.append(f"Open Cabinet 拉取失败：{exc}")

        return TenxPoliticalSignalResponse(
            market=normalized_market,
            person=person,
            snapshot_at=snapshot_at,
            thesis="把特朗普相关信号拆成披露交易、公开点名、政策受益三条线，先判定证据等级，再决定是否进入 Discover 或 Watchlist。",
            freshness=TenxFreshnessRow(
                updated_at=snapshot_at,
                data_complete=data_complete,
                source_summary="Open Cabinet + OGE filings + curated public-mention queue",
                coverage="Trump disclosure monitor, public mention candidates, verification workflow",
            ),
            disclosure=disclosure,
            recent_trades=trades,
            mentions=self._mention_rows(),
            monitoring_rules=[
                "A 级：OGE 原始披露、官方文字稿或公司正式公告，可直接进入事件复核。",
                "B 级：Reuters/Bloomberg/主流财经媒体且有明确原始出处，可进入 Discover 政治催化标签。",
                "C 级：二级媒体或社群转述，需要人工补原文。",
                "D 级：截图/聊天记录/无链接传闻，只能作为待核实线索。",
                "若某标的同时出现持仓披露、公开声援和价格突破，自动建议创建 P2 事件提醒。",
            ],
            notes=notes,
        )
