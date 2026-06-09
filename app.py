import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
from openai import OpenAI
import pdfplumber
import feedparser
import io
import urllib.parse
import re
import smtplib
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

st.set_page_config(page_title="국내 주식 대시보드", page_icon="📈", layout="wide")

# 10개 종목 corp_code 매핑 — corpcode.csv 기준 (stock_code로 확인)
DART_CORP_CODES = {
    "삼성전자":       "00126380",  # stock_code 005930
    "SK하이닉스":     "00164779",  # stock_code 000660
    "LG에너지솔루션": "01515323",  # stock_code 373220
    "삼성바이오로직스":"00877059",  # stock_code 207940
    "현대차":         "00164742",  # stock_code 005380 (현대자동차)
    "NAVER":          "00266961",  # stock_code 035420
    "카카오":         "00258801",  # stock_code 035720
    "POSCO홀딩스":    "00155319",  # stock_code 005490
    "셀트리온":       "00413046",  # stock_code 068270
    "KB금융":         "00688996",  # stock_code 105560
}

CORP_CODE_CSV = "corpcode.csv"

STOCKS = {
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "LG에너지솔루션": "373220.KS",
    "삼성바이오로직스": "207940.KS",
    "현대차": "005380.KS",
    "NAVER": "035420.KS",
    "카카오": "035720.KS",
    "POSCO홀딩스": "005490.KS",
    "셀트리온": "068270.KS",
    "KB금융": "105560.KS",
}

st.title("📈 국내 주식 대시보드")
st.markdown("KOSPI 주요 10개 종목 실시간 데이터")

# 사이드바
st.sidebar.header("설정")

# DART API Key 입력
st.sidebar.subheader("📋 DART 공시")
dart_api_key = st.sidebar.text_input(
    "OpenDART API Key",
    type="password",
    value="f2cb796f5e36fd9a6ce6f530871c65e90e2d0be1",
    help="https://opendart.fss.or.kr 에서 발급",
)

# OpenAI API Key 입력
st.sidebar.subheader("🤖 AI 챗봇")
openai_api_key = st.sidebar.text_input(
    "OpenAI API Key",
    type="password",
    placeholder="sk-...",
    help="GPT-4o-mini 챗봇을 사용하려면 API 키를 입력하세요.",
)

# 이메일 설정
st.sidebar.subheader("📧 이메일 보고서")
smtp_sender = st.sidebar.text_input(
    "발신 Gmail 계정",
    placeholder="your@gmail.com",
    key="smtp_sender",
)
smtp_app_pw = st.sidebar.text_input(
    "Gmail 앱 비밀번호",
    type="password",
    placeholder="앱 비밀번호 16자리",
    key="smtp_app_pw",
)
smtp_recipient = st.sidebar.text_input(
    "수신 이메일",
    placeholder="recipient@example.com",
    key="smtp_recipient",
)

period_map = {"1개월": "1mo", "3개월": "3mo", "6개월": "6mo", "1년": "1y", "2년": "2y"}
selected_period_label = st.sidebar.selectbox("조회 기간", list(period_map.keys()), index=2)
period = period_map[selected_period_label]

selected_stocks = st.sidebar.multiselect(
    "종목 선택",
    list(STOCKS.keys()),
    default=list(STOCKS.keys())[:5],
)


@st.cache_data(ttl=300)
def load_stock_data(tickers: list, period: str):
    data = {}
    for name, ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period=period)
            if not hist.empty:
                hist = hist.copy()
                if hasattr(hist.index, "tz") and hist.index.tz is not None:
                    hist.index = hist.index.tz_localize(None)
                for col in list(hist.columns):
                    try:
                        hist[col] = hist[col].astype(float)
                    except (ValueError, TypeError):
                        hist = hist.drop(columns=[col])
                fi = stock.fast_info
                info = {
                    "market_cap": float(fi.market_cap) if getattr(fi, "market_cap", None) is not None else None,
                    "shares":     float(fi.shares)     if getattr(fi, "shares",     None) is not None else None,
                }
                data[name] = {"hist": hist, "info": info, "ticker": ticker}
        except Exception:
            pass
    return data


with st.spinner("데이터 불러오는 중..."):
    ticker_pairs = [(name, STOCKS[name]) for name in selected_stocks] if selected_stocks else []
    stock_data = load_stock_data(ticker_pairs, period)

if not stock_data:
    st.warning("종목을 선택해 주세요.")
    st.stop()

# 요약 카드
st.subheader("📊 종목 요약")
cols = st.columns(min(len(stock_data), 5))
items = list(stock_data.items())

for i, (name, data) in enumerate(items):
    col = cols[i % 5]
    hist = data["hist"]
    if len(hist) >= 2:
        prev_close = hist["Close"].iloc[-2]
        cur_close = hist["Close"].iloc[-1]
        change = cur_close - prev_close
        change_pct = (change / prev_close) * 100
        delta_str = f"{change:+,.0f} ({change_pct:+.2f}%)"
        col.metric(label=name, value=f"₩{cur_close:,.0f}", delta=delta_str)

if len(items) > 5:
    cols2 = st.columns(min(len(items) - 5, 5))
    for i, (name, data) in enumerate(items[5:]):
        col = cols2[i % 5]
        hist = data["hist"]
        if len(hist) >= 2:
            prev_close = hist["Close"].iloc[-2]
            cur_close = hist["Close"].iloc[-1]
            change = cur_close - prev_close
            change_pct = (change / prev_close) * 100
            delta_str = f"{change:+,.0f} ({change_pct:+.2f}%)"
            col.metric(label=name, value=f"₩{cur_close:,.0f}", delta=delta_str)

st.divider()

# 주가 차트
st.subheader("📉 주가 추이 (정규화)")
fig = go.Figure()
for name, data in stock_data.items():
    hist = data["hist"]
    normalized = hist["Close"] / hist["Close"].iloc[0] * 100
    fig.add_trace(go.Scatter(
        x=hist.index, y=normalized, mode="lines", name=name,
        hovertemplate=f"{name}<br>날짜: %{{x|%Y-%m-%d}}<br>수익률: %{{y:.1f}}<extra></extra>",
    ))
fig.update_layout(
    title=f"기준일 대비 수익률 (%) — {selected_period_label}",
    xaxis_title="날짜", yaxis_title="수익률 지수 (시작=100)",
    hovermode="x unified", height=450,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig, use_container_width=True)

# 개별 캔들스틱
st.subheader("🕯️ 개별 종목 캔들스틱")
selected_candle = st.selectbox("종목 선택", list(stock_data.keys()))

if selected_candle and selected_candle in stock_data:
    hist = stock_data[selected_candle]["hist"]
    candle_fig = go.Figure(data=[go.Candlestick(
        x=hist.index, open=hist["Open"], high=hist["High"],
        low=hist["Low"], close=hist["Close"], name=selected_candle,
        increasing_line_color="#FF4B4B", decreasing_line_color="#4169E1",
    )])
    hist_copy = hist.copy()
    hist_copy["MA20"] = hist_copy["Close"].rolling(20).mean()
    hist_copy["MA60"] = hist_copy["Close"].rolling(60).mean()
    candle_fig.add_trace(go.Scatter(x=hist_copy.index, y=hist_copy["MA20"], mode="lines", name="MA20", line=dict(color="orange", width=1)))
    candle_fig.add_trace(go.Scatter(x=hist_copy.index, y=hist_copy["MA60"], mode="lines", name="MA60", line=dict(color="purple", width=1)))
    candle_fig.update_layout(
        title=f"{selected_candle} 캔들스틱 차트",
        xaxis_title="날짜", yaxis_title="가격 (원)", height=500, xaxis_rangeslider_visible=False,
    )
    st.plotly_chart(candle_fig, use_container_width=True)

    vol_fig = go.Figure(go.Bar(x=hist.index, y=hist["Volume"], name="거래량", marker_color="steelblue"))
    vol_fig.update_layout(title=f"{selected_candle} 거래량", height=200, margin=dict(t=40))
    st.plotly_chart(vol_fig, use_container_width=True)

st.divider()

# 수익률 비교
st.subheader("📊 기간 수익률 비교")
returns = []
for name, data in stock_data.items():
    hist = data["hist"]
    if len(hist) >= 2:
        ret = (hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100
        returns.append({"종목": name, "수익률(%)": round(ret, 2)})

if returns:
    df_ret = pd.DataFrame(returns).sort_values("수익률(%)", ascending=False)
    bar_fig = px.bar(
        df_ret, x="종목", y="수익률(%)", color="수익률(%)",
        color_continuous_scale=["#4169E1", "#FFFFFF", "#FF4B4B"],
        color_continuous_midpoint=0, title=f"{selected_period_label} 수익률 비교", text="수익률(%)",
    )
    bar_fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
    bar_fig.update_layout(height=400, coloraxis_showscale=False)
    st.plotly_chart(bar_fig, use_container_width=True)

# 원시 데이터 테이블
st.subheader("📋 최근 데이터")
with st.expander("종목별 최근 10일 데이터 보기"):
    for name, data in stock_data.items():
        st.markdown(f"**{name}**")
        hist = data["hist"][["Open", "High", "Low", "Close", "Volume"]].tail(10).copy()
        hist.index = hist.index.strftime("%Y-%m-%d")
        hist.columns = ["시가", "고가", "저가", "종가", "거래량"]
        for col in ["시가", "고가", "저가", "종가"]:
            hist[col] = hist[col].map(lambda x: f"₩{x:,.0f}")
        hist["거래량"] = hist["거래량"].map(lambda x: f"{x:,}")
        st.dataframe(hist, use_container_width=True)

st.caption(f"데이터 출처: Yahoo Finance | 마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ── 기업 뉴스 ──────────────────────────────────────────────────────────────────
st.divider()
st.subheader("📰 기업 관련 뉴스")


@st.cache_data(ttl=600)
def fetch_news(query: str, max_items: int = 10) -> list:
    encoded = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:max_items]:
        pub = ""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            pub = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d %H:%M")
        source = ""
        if hasattr(entry, "source") and hasattr(entry.source, "title"):
            source = entry.source.title
        summary = re.sub(r"<[^>]+>", "", getattr(entry, "summary", "")).strip()
        items.append({
            "title": entry.title, "link": entry.link,
            "published": pub, "source": source, "summary": summary,
        })
    return items


tab_names = list(stock_data.keys()) + ["🔍 통합 검색"]
news_tabs = st.tabs(tab_names)

for i, name in enumerate(stock_data.keys()):
    with news_tabs[i]:
        col_refresh, col_count = st.columns([3, 1])
        news_count = col_count.selectbox("기사 수", [5, 10, 20], index=1, key=f"nc_{name}")
        with st.spinner(f"{name} 뉴스 수집 중..."):
            news_items = fetch_news(name, news_count)
        if not news_items:
            st.warning("뉴스를 가져오지 못했습니다. 잠시 후 다시 시도해 주세요.")
        else:
            for item in news_items:
                with st.container():
                    title_col, meta_col = st.columns([5, 2])
                    with title_col:
                        st.markdown(f"**[{item['title']}]({item['link']})**")
                        if item["summary"]:
                            st.caption(item["summary"][:120] + ("..." if len(item["summary"]) > 120 else ""))
                    with meta_col:
                        if item["source"]:
                            st.caption(f"🗞 {item['source']}")
                        if item["published"]:
                            st.caption(f"🕐 {item['published']}")
                    st.markdown("---")

with news_tabs[-1]:
    search_col, btn_col = st.columns([4, 1])
    custom_query = search_col.text_input(
        "검색어 입력", placeholder="예: 코스피, 반도체, 금리, POSCO...",
        label_visibility="collapsed", key="news_search_input",
    )
    search_count = st.selectbox("기사 수", [5, 10, 20, 30], index=1, key="nc_search")
    if custom_query:
        with st.spinner(f"'{custom_query}' 뉴스 검색 중..."):
            search_items = fetch_news(custom_query, search_count)
        if not search_items:
            st.warning("검색 결과가 없습니다.")
        else:
            st.success(f"**{len(search_items)}건** 검색됨")
            for item in search_items:
                with st.container():
                    title_col, meta_col = st.columns([5, 2])
                    with title_col:
                        st.markdown(f"**[{item['title']}]({item['link']})**")
                        if item["summary"]:
                            st.caption(item["summary"][:120] + ("..." if len(item["summary"]) > 120 else ""))
                    with meta_col:
                        if item["source"]:
                            st.caption(f"🗞 {item['source']}")
                        if item["published"]:
                            st.caption(f"🕐 {item['published']}")
                    st.markdown("---")
    else:
        st.info("검색어를 입력하면 해당 키워드 관련 최신 뉴스를 가져옵니다.")

# ── 챗봇 ───────────────────────────────────────────────────────────────────────
st.divider()
st.subheader("🤖 주식 AI 챗봇 (GPT-4o-mini)")

if not openai_api_key:
    st.info("사이드바에 OpenAI API 키를 입력하면 주식 데이터를 기반으로 질문할 수 있습니다.")
else:
    def extract_pdf_text(file_bytes: bytes) -> str:
        text_parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    text_parts.append(f"[{i+1}페이지]\n{text.strip()}")
        return "\n\n".join(text_parts)

    with st.expander("📄 PDF 파일 업로드 (문서 기반 질문)", expanded=False):
        uploaded_pdf = st.file_uploader(
            "PDF 파일을 업로드하면 해당 내용을 기반으로 답변합니다.",
            type="pdf", key="pdf_uploader",
        )
        if uploaded_pdf is not None:
            if "pdf_name" not in st.session_state or st.session_state.pdf_name != uploaded_pdf.name:
                with st.spinner("PDF 텍스트 추출 중..."):
                    pdf_bytes = uploaded_pdf.read()
                    extracted = extract_pdf_text(pdf_bytes)
                    MAX_CHARS = 12000
                    if len(extracted) > MAX_CHARS:
                        extracted = extracted[:MAX_CHARS] + "\n\n...(이하 생략)"
                    st.session_state.pdf_text = extracted
                    st.session_state.pdf_name = uploaded_pdf.name
                st.success(f"✅ '{uploaded_pdf.name}' 로드 완료 ({len(st.session_state.pdf_text):,}자)")
            if st.button("PDF 내용 초기화", key="clear_pdf"):
                for key in ("pdf_text", "pdf_name"):
                    st.session_state.pop(key, None)
                st.rerun()
        if "pdf_name" in st.session_state:
            st.caption(f"현재 로드된 PDF: **{st.session_state.pdf_name}**")
            with st.expander("추출된 텍스트 미리보기"):
                st.text(st.session_state.get("pdf_text", "")[:1000] + "...")

    def build_news_context(stock_names: list, max_per_stock: int = 3) -> str:
        parts = []
        for name in stock_names:
            articles = fetch_news(name, max_per_stock)
            if not articles:
                continue
            lines = [f"[{name} 관련 뉴스]"]
            for a in articles:
                headline = f"• {a['title']}"
                if a["published"]:
                    headline += f" ({a['published']})"
                if a["source"]:
                    headline += f" — {a['source']}"
                lines.append(headline)
                if a["summary"]:
                    lines.append(f"  {a['summary'][:200]}")
            parts.append("\n".join(lines))
        total = "\n\n".join(parts)
        if len(total) > 8000:
            total = total[:8000] + "\n...(이하 생략)"
        return total

    def build_dart_context() -> str:
        items = st.session_state.get("dart_results", [])
        company = st.session_state.get("dart_company", "")
        if not items:
            return ""
        lines = [f"[DART 공시 정보 — {company}] (최근 {len(items)}건)"]
        for it in items:
            rcept_dt = it.get("rcept_dt", "")
            date_str = f"{rcept_dt[:4]}-{rcept_dt[4:6]}-{rcept_dt[6:]}" if len(rcept_dt) == 8 else rcept_dt
            report_nm = it.get("report_nm", "").strip()
            flr_nm    = it.get("flr_nm", "").strip()
            rm        = it.get("rm", "").strip()
            rcept_no  = it.get("rcept_no", "")
            line = f"• [{date_str}] {report_nm}"
            if flr_nm:
                line += f" / 제출인: {flr_nm}"
            if rm:
                line += f" / 비고: {rm}"
            line += f" (접수번호: {rcept_no})"
            lines.append(line)
        result = "\n".join(lines)
        if len(result) > 6000:
            result = result[:6000] + "\n...(이하 생략)"
        return result

    def build_stock_context(stock_data: dict, period_label: str) -> str:
        lines = [f"조회 기간: {period_label}", ""]
        for name, d in stock_data.items():
            hist = d["hist"]
            cur = hist["Close"].iloc[-1]
            start = hist["Close"].iloc[0]
            ret = (cur / start - 1) * 100
            high = hist["High"].max()
            low = hist["Low"].min()
            avg_vol = hist["Volume"].mean()
            lines.append(
                f"[{name}] 현재가: ₩{cur:,.0f} | 기간수익률: {ret:+.2f}% | "
                f"기간고가: ₩{high:,.0f} | 기간저가: ₩{low:,.0f} | 평균거래량: {avg_vol:,.0f}"
            )
        return "\n".join(lines)

    pdf_loaded = "pdf_text" in st.session_state and st.session_state.pdf_text

    SYSTEM_PROMPT = """당신은 한국 주식 시장 전문 애널리스트입니다.
사용자가 제공한 실시간 주식 데이터, DART 공시 정보, 최신 뉴스, 업로드된 PDF 문서를 종합하여 정확하고 유용한 분석을 제공합니다.
- DART 공시 정보가 제공된 경우 공시 날짜·제목·제출인을 인용하여 기업의 최근 공시 동향을 설명합니다.
- 뉴스가 제공된 경우 최신 시장 동향과 기업 이슈를 분석에 반영합니다.
- 답변은 한국어로 작성하며, 구체적인 수치와 출처를 인용해 설명합니다.
- 투자 판단은 사용자 본인의 책임임을 명시하고, 참고용 정보임을 안내합니다."""

    stock_context = build_stock_context(stock_data, selected_period_label)
    dart_context  = build_dart_context()

    include_news = st.checkbox(
        "📰 뉴스 컨텍스트 포함 (선택된 종목의 최신 뉴스를 챗봇 답변에 반영)",
        value=True, key="include_news_ctx",
    )
    news_context = ""
    if include_news and stock_data:
        with st.spinner("뉴스 컨텍스트 수집 중..."):
            news_context = build_news_context(list(stock_data.keys()), max_per_stock=3)

    active_sources = ["📈 실시간 주식 데이터"]
    if dart_context:
        dart_company = st.session_state.get("dart_company", "")
        dart_cnt     = len(st.session_state.get("dart_results", []))
        active_sources.append(f"📋 DART 공시 ({dart_company} {dart_cnt}건)")
    if include_news and news_context:
        active_sources.append("📰 최신 뉴스")
    if pdf_loaded:
        active_sources.append(f"📄 {st.session_state.pdf_name}")
    st.caption("현재 답변 컨텍스트: " + " · ".join(active_sources))

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    chat_container = st.container(height=400)
    with chat_container:
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    user_input = st.chat_input("주식 데이터에 대해 질문하세요...")

    if user_input:
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        with chat_container:
            with st.chat_message("user"):
                st.markdown(user_input)

        try:
            client_gpt = OpenAI(api_key=openai_api_key)

            context_block = f"[현재 주식 데이터]\n{stock_context}"
            if dart_context:
                context_block += f"\n\n{dart_context}"
            if include_news and news_context:
                context_block += f"\n\n[최신 뉴스]\n{news_context}"
            if pdf_loaded:
                context_block += f"\n\n[업로드된 PDF 문서: {st.session_state.pdf_name}]\n{st.session_state.pdf_text}"
            context_block += f"\n\n[질문]\n{user_input}"

            messages_for_api = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context_block},
            ]
            if len(st.session_state.chat_messages) > 1:
                history = st.session_state.chat_messages[:-1][-10:]
                messages_for_api = (
                    [messages_for_api[0]]
                    + [{"role": m["role"], "content": m["content"]} for m in history]
                    + [messages_for_api[1]]
                )

            with chat_container:
                with st.chat_message("assistant"):
                    response_placeholder = st.empty()
                    full_response = ""
                    stream = client_gpt.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages_for_api,
                        stream=True, temperature=0.7, max_tokens=1024,
                    )
                    for chunk in stream:
                        delta = chunk.choices[0].delta.content or ""
                        full_response += delta
                        response_placeholder.markdown(full_response + "▌")
                    response_placeholder.markdown(full_response)

            st.session_state.chat_messages.append({"role": "assistant", "content": full_response})

        except Exception as e:
            st.error(f"API 오류: {e}")

    if st.session_state.chat_messages:
        if st.button("대화 초기화", use_container_width=False):
            st.session_state.chat_messages = []
            st.rerun()

# ── 이메일 보고서 ──────────────────────────────────────────────────────────────
st.divider()
st.subheader("📧 주식 보고서 이메일 발송")


def build_report_html(stock_data: dict, period_label: str, news_per_stock: int = 5) -> str:
    now = datetime.now().strftime("%Y년 %m월 %d일 %H:%M")
    rows = ""
    for name, d in stock_data.items():
        hist = d["hist"]
        cur = hist["Close"].iloc[-1]
        start = hist["Close"].iloc[0]
        ret = (cur / start - 1) * 100
        high = hist["High"].max()
        low = hist["Low"].min()
        color = "#c0392b" if ret >= 0 else "#2980b9"
        arrow = "▲" if ret >= 0 else "▼"
        rows += f"""
        <tr>
          <td style="padding:8px 12px;font-weight:bold;">{name}</td>
          <td style="padding:8px 12px;text-align:right;">₩{cur:,.0f}</td>
          <td style="padding:8px 12px;text-align:right;color:{color};">{arrow} {ret:+.2f}%</td>
          <td style="padding:8px 12px;text-align:right;">₩{high:,.0f}</td>
          <td style="padding:8px 12px;text-align:right;">₩{low:,.0f}</td>
        </tr>"""

    news_html = ""
    for name in stock_data.keys():
        articles = fetch_news(name, news_per_stock)
        if not articles:
            continue
        items_html = ""
        for a in articles:
            meta = f"{a['published']} | {a['source']}" if a["source"] else a["published"]
            items_html += f"""
            <li style="margin-bottom:10px;">
              <a href="{a['link']}" style="color:#2c3e50;font-weight:bold;text-decoration:none;">{a['title']}</a><br>
              <span style="font-size:12px;color:#7f8c8d;">{meta}</span>
              {"<br><span style='font-size:13px;color:#555;'>" + a['summary'][:180] + "...</span>" if a['summary'] else ""}
            </li>"""
        news_html += f"""
        <h3 style="color:#2c3e50;border-bottom:1px solid #ddd;padding-bottom:6px;">{name}</h3>
        <ul style="padding-left:18px;">{items_html}</ul>"""

    return f"""<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"><title>주식 보고서</title></head>
<body style="font-family:'Malgun Gothic',Arial,sans-serif;color:#2c3e50;max-width:800px;margin:0 auto;padding:20px;">
  <div style="background:linear-gradient(135deg,#1a252f,#2c3e50);color:white;padding:30px;border-radius:10px;margin-bottom:24px;">
    <h1 style="margin:0;font-size:24px;">📈 KOSPI 주식 보고서</h1>
    <p style="margin:8px 0 0;opacity:.8;">생성일시: {now} | 조회 기간: {period_label}</p>
  </div>
  <h2 style="color:#2c3e50;">종목별 현황</h2>
  <table style="width:100%;border-collapse:collapse;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.1);border-radius:8px;overflow:hidden;">
    <thead>
      <tr style="background:#34495e;color:white;">
        <th style="padding:10px 12px;text-align:left;">종목</th>
        <th style="padding:10px 12px;text-align:right;">현재가</th>
        <th style="padding:10px 12px;text-align:right;">기간수익률</th>
        <th style="padding:10px 12px;text-align:right;">기간고가</th>
        <th style="padding:10px 12px;text-align:right;">기간저가</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
  <h2 style="color:#2c3e50;margin-top:32px;">📰 최신 뉴스</h2>
  {news_html}
  <hr style="margin-top:32px;border:none;border-top:1px solid #ddd;">
  <p style="font-size:12px;color:#95a5a6;text-align:center;">
    본 보고서는 참고용이며 투자 판단의 책임은 본인에게 있습니다.<br>
    데이터 출처: Yahoo Finance / Google News
  </p>
</body>
</html>"""


def send_report_email(sender: str, app_pw: str, recipient: str, html_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[주식 보고서] {datetime.now().strftime('%Y-%m-%d %H:%M')} KOSPI 종목 현황"
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, app_pw)
        server.sendmail(sender, recipient, msg.as_string())


email_ready = smtp_sender and smtp_app_pw and smtp_recipient

if not email_ready:
    st.info("사이드바에서 **발신 Gmail 계정**, **앱 비밀번호**, **수신 이메일**을 모두 입력하면 보고서를 발송할 수 있습니다.")
    with st.expander("Gmail 앱 비밀번호 발급 방법"):
        st.markdown("""
1. Google 계정 → **보안** 탭 이동
2. **2단계 인증** 활성화 (필수)
3. 검색창에 **"앱 비밀번호"** 검색 → 새 앱 비밀번호 생성
4. 생성된 **16자리 비밀번호**를 사이드바에 입력
        """)
else:
    col_preview, col_send = st.columns([1, 1])
    with col_preview:
        news_count_report = st.selectbox("보고서 종목당 뉴스 수", [3, 5, 10], index=1, key="report_news_count")
    with col_send:
        st.markdown("<br>", unsafe_allow_html=True)
        send_btn = st.button("📨 보고서 발송", type="primary", use_container_width=True)

    with st.expander("📄 보고서 미리보기", expanded=False):
        with st.spinner("보고서 생성 중..."):
            preview_html = build_report_html(stock_data, selected_period_label, news_count_report)
        st.components.v1.html(preview_html, height=600, scrolling=True)

    if send_btn:
        with st.spinner("보고서 생성 및 발송 중..."):
            try:
                report_html = build_report_html(stock_data, selected_period_label, news_count_report)
                send_report_email(smtp_sender, smtp_app_pw, smtp_recipient, report_html)
                st.success(f"✅ 보고서가 **{smtp_recipient}** 으로 발송되었습니다!")
            except smtplib.SMTPAuthenticationError:
                st.error("❌ 인증 실패: Gmail 계정 또는 앱 비밀번호를 확인해 주세요.")
            except smtplib.SMTPException as e:
                st.error(f"❌ 메일 발송 오류: {e}")
            except Exception as e:
                st.error(f"❌ 오류 발생: {e}")

# ── DART 공시 정보 ─────────────────────────────────────────────────────────────
st.divider()
st.subheader("📋 DART 공시 정보")

DART_REPORT_TYPES = {
    "전체": "",
    "사업보고서": "A001",
    "반기보고서": "A002",
    "분기보고서": "A003",
    "주요사항보고서": "B001",
    "발행공시": "C001",
    "지분공시": "D001",
    "기타공시": "E001",
    "외부감사관련": "F001",
    "펀드공시": "G001",
    "자산유동화": "H001",
    "거래소공시": "I001",
    "공정위공시": "J001",
}


@st.cache_data(ttl=600)
def fetch_dart_disclosures(api_key: str, corp_code: str, bgn_de: str, end_de: str,
                            pblntf_ty: str = "", page_count: int = 20) -> dict:
    params = {
        "crtfc_key": api_key, "corp_code": corp_code,
        "bgn_de": bgn_de, "end_de": end_de, "page_count": page_count,
    }
    if pblntf_ty:
        params["pblntf_ty"] = pblntf_ty
    resp = requests.get("https://opendart.fss.or.kr/api/list.json", params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


@st.cache_data
def load_corp_codes_from_csv() -> pd.DataFrame:
    df = pd.read_csv(CORP_CODE_CSV, dtype=str).fillna("")
    return df


if not dart_api_key:
    st.info("사이드바에 **OpenDART API 키**를 입력하면 공시 정보를 조회할 수 있습니다.")
    with st.expander("DART API 키 발급 방법"):
        st.markdown("""
1. [https://opendart.fss.or.kr](https://opendart.fss.or.kr) 접속
2. **회원가입 → 로그인** 후 **API 신청** 메뉴
3. 사용 목적 입력 후 신청 → 발급된 키를 사이드바에 입력
        """)
else:
    dart_col1, dart_col2, dart_col3 = st.columns([2, 2, 2])
    with dart_col1:
        dart_stock = st.selectbox("조회 종목", list(stock_data.keys()), key="dart_stock")
    with dart_col2:
        dart_rtype = st.selectbox("공시 유형", list(DART_REPORT_TYPES.keys()), key="dart_rtype")
    with dart_col3:
        dart_period = st.selectbox("조회 기간", ["1개월", "3개월", "6개월", "1년"], index=1, key="dart_period")

    dart_count = st.slider("최대 조회 건수", 10, 100, 20, step=10, key="dart_count")

    if st.button("🔍 공시 조회", type="primary", key="dart_fetch_btn"):
        corp_code = DART_CORP_CODES.get(dart_stock)
        if not corp_code:
            st.error(f"'{dart_stock}'의 corp_code를 찾을 수 없습니다.")
        else:
            period_days = {"1개월": 30, "3개월": 90, "6개월": 180, "1년": 365}[dart_period]
            end_dt = datetime.now()
            bgn_dt = end_dt - timedelta(days=period_days)
            bgn_de = bgn_dt.strftime("%Y%m%d")
            end_de = end_dt.strftime("%Y%m%d")
            pblntf_ty = DART_REPORT_TYPES[dart_rtype]

            with st.spinner(f"{dart_stock} 공시 정보 조회 중..."):
                try:
                    result = fetch_dart_disclosures(dart_api_key, corp_code, bgn_de, end_de, pblntf_ty, dart_count)
                    status = result.get("status", "")
                    message = result.get("message", "")
                    if status == "000":
                        items = result.get("list", [])
                        st.session_state["dart_results"] = items
                        st.session_state["dart_company"] = dart_stock
                        st.success(f"**{dart_stock}** 공시 **{len(items)}건** 조회 완료")
                    elif status == "013":
                        st.warning("조회 기간 내 공시가 없습니다.")
                        st.session_state["dart_results"] = []
                    else:
                        st.error(f"DART API 오류 [{status}]: {message}")
                        st.session_state["dart_results"] = []
                except requests.exceptions.HTTPError as e:
                    st.error(f"HTTP 오류: {e}")
                except Exception as e:
                    st.error(f"오류 발생: {e}")

    if st.session_state.get("dart_results"):
        items = st.session_state["dart_results"]
        company = st.session_state.get("dart_company", "")

        search_kw = st.text_input("공시 제목 검색", placeholder="키워드 입력...", key="dart_kw")
        filtered = [it for it in items if search_kw.lower() in it.get("report_nm", "").lower()] if search_kw else items
        st.caption(f"총 {len(filtered)}건 표시 중")

        for it in filtered:
            rcept_no  = it.get("rcept_no", "")
            report_nm = it.get("report_nm", "제목 없음")
            rcept_dt  = it.get("rcept_dt", "")
            flr_nm    = it.get("flr_nm", "")
            rm        = it.get("rm", "")
            date_str  = f"{rcept_dt[:4]}-{rcept_dt[4:6]}-{rcept_dt[6:]}" if len(rcept_dt) == 8 else rcept_dt
            dart_url  = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"

            with st.container():
                c1, c2 = st.columns([6, 2])
                with c1:
                    st.markdown(f"**[{report_nm}]({dart_url})**")
                    if flr_nm:
                        st.caption(f"제출인: {flr_nm}" + (f" | 비고: {rm}" if rm else ""))
                with c2:
                    st.caption(f"📅 {date_str}")
                    st.caption(f"접수번호: {rcept_no}")
                st.markdown("---")

    with st.expander("🔎 기업코드 검색 (corpcode.csv 기반)"):
        st.markdown("**corpcode.csv** 파일에서 기업명으로 corp_code를 검색합니다.")
        corp_search_kw = st.text_input("기업명 검색", placeholder="예: 현대모비스, LG전자...", key="corp_search_kw")
        if corp_search_kw:
            try:
                df_corps = load_corp_codes_from_csv()
                matched = df_corps[df_corps["corp_name"].str.contains(corp_search_kw, na=False)]
                if matched.empty:
                    st.warning("검색 결과가 없습니다.")
                else:
                    st.caption(f"{len(matched)}건 검색됨")
                    st.dataframe(
                        matched[["corp_code", "corp_name", "corp_eng_name", "stock_code", "modify_date"]].rename(
                            columns={"corp_code": "고유번호", "corp_name": "기업명",
                                     "corp_eng_name": "영문명", "stock_code": "종목코드",
                                     "modify_date": "최종변경일"}
                        ).reset_index(drop=True),
                        use_container_width=True,
                    )
            except FileNotFoundError:
                st.error(f"corpcode.csv 파일을 찾을 수 없습니다.")
            except Exception as e:
                st.error(f"오류: {e}")
