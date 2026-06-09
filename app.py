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

st.set_page_config(page_title="援?궡 二쇱떇 ??쒕낫??, page_icon="?뱢", layout="wide")

# 10媛?醫낅ぉ corp_code 留ㅽ븨 ??corpcode.csv 湲곗? (stock_code濡??뺤씤)
DART_CORP_CODES = {
    "?쇱꽦?꾩옄":       "00126380",  # stock_code 005930
    "SK?섏씠?됱뒪":     "00164779",  # stock_code 000660
    "LG?먮꼫吏?붾（??: "01515323",  # stock_code 373220
    "?쇱꽦諛붿씠?ㅻ줈吏곸뒪":"00877059",  # stock_code 207940
    "?꾨?李?:         "00164742",  # stock_code 005380 (?꾨??먮룞李?
    "NAVER":          "00266961",  # stock_code 035420
    "移댁뭅??:         "00258801",  # stock_code 035720
    "POSCO??⑹뒪":    "00155319",  # stock_code 005490
    "??몃━??:       "00413046",  # stock_code 068270
    "KB湲덉쑖":         "00688996",  # stock_code 105560
}

CORP_CODE_CSV = r"C:\Users\Hansol\Desktop\260609_?ㅼ쟾\corpcode.csv"

STOCKS = {
    "?쇱꽦?꾩옄": "005930.KS",
    "SK?섏씠?됱뒪": "000660.KS",
    "LG?먮꼫吏?붾（??: "373220.KS",
    "?쇱꽦諛붿씠?ㅻ줈吏곸뒪": "207940.KS",
    "?꾨?李?: "005380.KS",
    "NAVER": "035420.KS",
    "移댁뭅??: "035720.KS",
    "POSCO??⑹뒪": "005490.KS",
    "??몃━??: "068270.KS",
    "KB湲덉쑖": "105560.KS",
}

st.title("?뱢 援?궡 二쇱떇 ??쒕낫??)
st.markdown("KOSPI 二쇱슂 10媛?醫낅ぉ ?ㅼ떆媛??곗씠??)

# ?ъ씠?쒕컮
st.sidebar.header("?ㅼ젙")

# DART API Key ?낅젰
st.sidebar.subheader("?뱥 DART 怨듭떆")
dart_api_key = st.sidebar.text_input(
    "OpenDART API Key",
    type="password",
    value="f2cb796f5e36fd9a6ce6f530871c65e90e2d0be1",
    help="https://opendart.fss.or.kr ?먯꽌 諛쒓툒",
)

# OpenAI API Key ?낅젰
st.sidebar.subheader("?쨼 AI 梨쀫큸")
openai_api_key = st.sidebar.text_input(
    "OpenAI API Key",
    type="password",
    placeholder="sk-...",
    help="GPT-4o-mini 梨쀫큸???ъ슜?섎젮硫?API ?ㅻ? ?낅젰?섏꽭??",
)

# ?대찓???ㅼ젙
st.sidebar.subheader("?벁 ?대찓??蹂닿퀬??)
smtp_sender = st.sidebar.text_input(
    "諛쒖떊 Gmail 怨꾩젙",
    placeholder="your@gmail.com",
    key="smtp_sender",
)
smtp_app_pw = st.sidebar.text_input(
    "Gmail ??鍮꾨?踰덊샇",
    type="password",
    placeholder="??鍮꾨?踰덊샇 16?먮━",
    key="smtp_app_pw",
)
smtp_recipient = st.sidebar.text_input(
    "?섏떊 ?대찓??,
    placeholder="recipient@example.com",
    key="smtp_recipient",
)

period_map = {"1媛쒖썡": "1mo", "3媛쒖썡": "3mo", "6媛쒖썡": "6mo", "1??: "1y", "2??: "2y"}
selected_period_label = st.sidebar.selectbox("議고쉶 湲곌컙", list(period_map.keys()), index=2)
period = period_map[selected_period_label]

selected_stocks = st.sidebar.multiselect(
    "醫낅ぉ ?좏깮",
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
                # pickle-safe: timezone ?쒓굅 ???쒖닔 float 而щ읆留??④릿 DataFrame 蹂듭궗
                hist = hist.copy()
                if hasattr(hist.index, "tz") and hist.index.tz is not None:
                    hist.index = hist.index.tz_localize(None)
                for col in hist.columns:
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

with st.spinner("?곗씠??遺덈윭?ㅻ뒗 以?.."):
    ticker_pairs = [(name, STOCKS[name]) for name in selected_stocks] if selected_stocks else []
    stock_data = load_stock_data(ticker_pairs, period)

if not stock_data:
    st.warning("醫낅ぉ???좏깮??二쇱꽭??")
    st.stop()

# ?붿빟 移대뱶
st.subheader("?뱤 醫낅ぉ ?붿빟")
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
        col.metric(
            label=name,
            value=f"??cur_close:,.0f}",
            delta=delta_str,
        )

# ??踰덉㎏ ??if len(items) > 5:
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
            col.metric(
                label=name,
                value=f"??cur_close:,.0f}",
                delta=delta_str,
            )

st.divider()

# 二쇨? 李⑦듃
st.subheader("?뱣 二쇨? 異붿씠 (?뺢퇋??")

fig = go.Figure()
for name, data in stock_data.items():
    hist = data["hist"]
    normalized = hist["Close"] / hist["Close"].iloc[0] * 100
    fig.add_trace(go.Scatter(
        x=hist.index,
        y=normalized,
        mode="lines",
        name=name,
        hovertemplate=f"{name}<br>?좎쭨: %{{x|%Y-%m-%d}}<br>?섏씡瑜? %{{y:.1f}}<extra></extra>",
    ))

fig.update_layout(
    title=f"湲곗????鍮??섏씡瑜?(%) ??{selected_period_label}",
    xaxis_title="?좎쭨",
    yaxis_title="?섏씡瑜?吏??(?쒖옉=100)",
    hovermode="x unified",
    height=450,
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig, width='stretch')

# 媛쒕퀎 罹붾뱾?ㅽ떛
st.subheader("?빉截?媛쒕퀎 醫낅ぉ 罹붾뱾?ㅽ떛")
selected_candle = st.selectbox("醫낅ぉ ?좏깮", list(stock_data.keys()))

if selected_candle and selected_candle in stock_data:
    hist = stock_data[selected_candle]["hist"]
    candle_fig = go.Figure(data=[go.Candlestick(
        x=hist.index,
        open=hist["Open"],
        high=hist["High"],
        low=hist["Low"],
        close=hist["Close"],
        name=selected_candle,
        increasing_line_color="#FF4B4B",
        decreasing_line_color="#4169E1",
    )])

    # ?대룞?됯퇏??    hist_copy = hist.copy()
    hist_copy["MA20"] = hist_copy["Close"].rolling(20).mean()
    hist_copy["MA60"] = hist_copy["Close"].rolling(60).mean()

    candle_fig.add_trace(go.Scatter(
        x=hist_copy.index, y=hist_copy["MA20"],
        mode="lines", name="MA20",
        line=dict(color="orange", width=1),
    ))
    candle_fig.add_trace(go.Scatter(
        x=hist_copy.index, y=hist_copy["MA60"],
        mode="lines", name="MA60",
        line=dict(color="purple", width=1),
    ))

    candle_fig.update_layout(
        title=f"{selected_candle} 罹붾뱾?ㅽ떛 李⑦듃",
        xaxis_title="?좎쭨",
        yaxis_title="媛寃?(??",
        height=500,
        xaxis_rangeslider_visible=False,
    )
    st.plotly_chart(candle_fig, width='stretch')

    # 嫄곕옒??    vol_fig = go.Figure(go.Bar(
        x=hist.index,
        y=hist["Volume"],
        name="嫄곕옒??,
        marker_color="steelblue",
    ))
    vol_fig.update_layout(title=f"{selected_candle} 嫄곕옒??, height=200, margin=dict(t=40))
    st.plotly_chart(vol_fig, width='stretch')

st.divider()

# ?섏씡瑜?鍮꾧탳 留됰?
st.subheader("?뱤 湲곌컙 ?섏씡瑜?鍮꾧탳")

returns = []
for name, data in stock_data.items():
    hist = data["hist"]
    if len(hist) >= 2:
        ret = (hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100
        returns.append({"醫낅ぉ": name, "?섏씡瑜?%)": round(ret, 2)})

if returns:
    df_ret = pd.DataFrame(returns).sort_values("?섏씡瑜?%)", ascending=False)
    bar_fig = px.bar(
        df_ret,
        x="醫낅ぉ",
        y="?섏씡瑜?%)",
        color="?섏씡瑜?%)",
        color_continuous_scale=["#4169E1", "#FFFFFF", "#FF4B4B"],
        color_continuous_midpoint=0,
        title=f"{selected_period_label} ?섏씡瑜?鍮꾧탳",
        text="?섏씡瑜?%)",
    )
    bar_fig.update_traces(texttemplate="%{text:.2f}%", textposition="outside")
    bar_fig.update_layout(height=400, coloraxis_showscale=False)
    st.plotly_chart(bar_fig, width='stretch')

# ?먯떆 ?곗씠???뚯씠釉?st.subheader("?뱥 理쒓렐 ?곗씠??)
with st.expander("醫낅ぉ蹂?理쒓렐 10???곗씠??蹂닿린"):
    for name, data in stock_data.items():
        st.markdown(f"**{name}**")
        hist = data["hist"][["Open", "High", "Low", "Close", "Volume"]].tail(10).copy()
        hist.index = hist.index.strftime("%Y-%m-%d")
        hist.columns = ["?쒓?", "怨좉?", "?媛", "醫낃?", "嫄곕옒??]
        for col in ["?쒓?", "怨좉?", "?媛", "醫낃?"]:
            hist[col] = hist[col].map(lambda x: f"??x:,.0f}")
        hist["嫄곕옒??] = hist["嫄곕옒??].map(lambda x: f"{x:,}")
        st.dataframe(hist, width='stretch')

st.caption(f"?곗씠??異쒖쿂: Yahoo Finance | 留덉?留??낅뜲?댄듃: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ?? 湲곗뾽 ?댁뒪 ?????????????????????????????????????????????????????????????????
st.divider()
st.subheader("?벐 湲곗뾽 愿???댁뒪")

@st.cache_data(ttl=600)
def fetch_news(query: str, max_items: int = 10) -> list[dict]:
    encoded = urllib.parse.quote(query)
    url = (
        f"https://news.google.com/rss/search"
        f"?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
    )
    feed = feedparser.parse(url)
    items = []
    for entry in feed.entries[:max_items]:
        # ?좎쭨 ?뚯떛
        pub = ""
        if hasattr(entry, "published_parsed") and entry.published_parsed:
            pub = datetime(*entry.published_parsed[:6]).strftime("%Y-%m-%d %H:%M")
        # 異쒖쿂 異붿텧
        source = ""
        if hasattr(entry, "source") and hasattr(entry.source, "title"):
            source = entry.source.title
        # HTML ?쒓렇 ?쒓굅
        summary = re.sub(r"<[^>]+>", "", getattr(entry, "summary", "")).strip()
        items.append({
            "title": entry.title,
            "link": entry.link,
            "published": pub,
            "source": source,
            "summary": summary,
        })
    return items

# ?댁뒪 ??援ъ꽦: 媛쒕퀎 醫낅ぉ ??+ ?꾩껜 ??tab_names = list(stock_data.keys()) + ["?뵇 ?듯빀 寃??]
news_tabs = st.tabs(tab_names)

for i, name in enumerate(stock_data.keys()):
    with news_tabs[i]:
        col_refresh, col_count = st.columns([3, 1])
        news_count = col_count.selectbox("湲곗궗 ??, [5, 10, 20], index=1, key=f"nc_{name}")
        with st.spinner(f"{name} ?댁뒪 ?섏쭛 以?.."):
            news_items = fetch_news(name, news_count)

        if not news_items:
            st.warning("?댁뒪瑜?媛?몄삤吏 紐삵뻽?듬땲?? ?좎떆 ???ㅼ떆 ?쒕룄??二쇱꽭??")
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
                            st.caption(f"?뿛 {item['source']}")
                        if item["published"]:
                            st.caption(f"?븧 {item['published']}")
                    st.markdown("---")

# ?듯빀 寃????with news_tabs[-1]:
    search_col, btn_col = st.columns([4, 1])
    custom_query = search_col.text_input(
        "寃?됱뼱 ?낅젰",
        placeholder="?? 肄붿뒪?? 諛섎룄泥? 湲덈━, POSCO...",
        label_visibility="collapsed",
        key="news_search_input",
    )
    search_count = st.selectbox("湲곗궗 ??, [5, 10, 20, 30], index=1, key="nc_search")

    if custom_query:
        with st.spinner(f"'{custom_query}' ?댁뒪 寃??以?.."):
            search_items = fetch_news(custom_query, search_count)
        if not search_items:
            st.warning("寃??寃곌낵媛 ?놁뒿?덈떎.")
        else:
            st.success(f"**{len(search_items)}嫄?* 寃?됰맖")
            for item in search_items:
                with st.container():
                    title_col, meta_col = st.columns([5, 2])
                    with title_col:
                        st.markdown(f"**[{item['title']}]({item['link']})**")
                        if item["summary"]:
                            st.caption(item["summary"][:120] + ("..." if len(item["summary"]) > 120 else ""))
                    with meta_col:
                        if item["source"]:
                            st.caption(f"?뿛 {item['source']}")
                        if item["published"]:
                            st.caption(f"?븧 {item['published']}")
                    st.markdown("---")
    else:
        st.info("寃?됱뼱瑜??낅젰?섎㈃ ?대떦 ?ㅼ썙??愿??理쒖떊 ?댁뒪瑜?媛?몄샃?덈떎.")

# ?? 梨쀫큸 ?????????????????????????????????????????????????????????????????????
st.divider()
st.subheader("?쨼 二쇱떇 AI 梨쀫큸 (GPT-4o-mini)")

if not openai_api_key:
    st.info("?ъ씠?쒕컮??OpenAI API ?ㅻ? ?낅젰?섎㈃ 二쇱떇 ?곗씠?곕? 湲곕컲?쇰줈 吏덈Ц?????덉뒿?덈떎.")
else:
    # PDF ?띿뒪??異붿텧
    def extract_pdf_text(file_bytes: bytes) -> str:
        text_parts = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    text_parts.append(f"[{i+1}?섏씠吏]\n{text.strip()}")
        return "\n\n".join(text_parts)

    # PDF ?낅줈??UI
    with st.expander("?뱞 PDF ?뚯씪 ?낅줈??(臾몄꽌 湲곕컲 吏덈Ц)", expanded=False):
        uploaded_pdf = st.file_uploader(
            "PDF ?뚯씪???낅줈?쒗븯硫??대떦 ?댁슜??湲곕컲?쇰줈 ?듬??⑸땲??",
            type="pdf",
            key="pdf_uploader",
        )

        if uploaded_pdf is not None:
            if (
                "pdf_name" not in st.session_state
                or st.session_state.pdf_name != uploaded_pdf.name
            ):
                with st.spinner("PDF ?띿뒪??異붿텧 以?.."):
                    pdf_bytes = uploaded_pdf.read()
                    extracted = extract_pdf_text(pdf_bytes)
                    # ?좏겙 珥덇낵 諛⑹?: 理쒕? 12,000??(??3,000 ?좏겙)
                    MAX_CHARS = 12000
                    if len(extracted) > MAX_CHARS:
                        extracted = extracted[:MAX_CHARS] + "\n\n...(?댄븯 ?앸왂)"
                    st.session_state.pdf_text = extracted
                    st.session_state.pdf_name = uploaded_pdf.name
                st.success(f"??'{uploaded_pdf.name}' 濡쒕뱶 ?꾨즺 ({len(st.session_state.pdf_text):,}??")

            if st.button("PDF ?댁슜 珥덇린??, key="clear_pdf"):
                for key in ("pdf_text", "pdf_name"):
                    st.session_state.pop(key, None)
                st.rerun()

        if "pdf_name" in st.session_state:
            st.caption(f"?꾩옱 濡쒕뱶??PDF: **{st.session_state.pdf_name}**")
            with st.expander("異붿텧???띿뒪??誘몃━蹂닿린"):
                st.text(st.session_state.get("pdf_text", "")[:1000] + "...")

    # ?댁뒪 而⑦뀓?ㅽ듃 ?앹꽦
    def build_news_context(stock_names: list, max_per_stock: int = 3) -> str:
        parts = []
        for name in stock_names:
            articles = fetch_news(name, max_per_stock)
            if not articles:
                continue
            lines = [f"[{name} 愿???댁뒪]"]
            for a in articles:
                headline = f"??{a['title']}"
                if a["published"]:
                    headline += f" ({a['published']})"
                if a["source"]:
                    headline += f" ??{a['source']}"
                lines.append(headline)
                if a["summary"]:
                    lines.append(f"  {a['summary'][:200]}")
            parts.append("\n".join(lines))
        total = "\n\n".join(parts)
        MAX_NEWS_CHARS = 8000
        if len(total) > MAX_NEWS_CHARS:
            total = total[:MAX_NEWS_CHARS] + "\n...(?댄븯 ?앸왂)"
        return total

    # DART 怨듭떆 而⑦뀓?ㅽ듃 ?앹꽦
    def build_dart_context() -> str:
        items = st.session_state.get("dart_results", [])
        company = st.session_state.get("dart_company", "")
        if not items:
            return ""
        lines = [f"[DART 怨듭떆 ?뺣낫 ??{company}] (理쒓렐 {len(items)}嫄?"]
        for it in items:
            rcept_dt = it.get("rcept_dt", "")
            date_str = f"{rcept_dt[:4]}-{rcept_dt[4:6]}-{rcept_dt[6:]}" if len(rcept_dt) == 8 else rcept_dt
            report_nm = it.get("report_nm", "").strip()
            flr_nm    = it.get("flr_nm", "").strip()
            rm        = it.get("rm", "").strip()
            rcept_no  = it.get("rcept_no", "")
            line = f"??[{date_str}] {report_nm}"
            if flr_nm:
                line += f" / ?쒖텧?? {flr_nm}"
            if rm:
                line += f" / 鍮꾧퀬: {rm}"
            line += f" (?묒닔踰덊샇: {rcept_no})"
            lines.append(line)
        result = "\n".join(lines)
        MAX_DART_CHARS = 6000
        if len(result) > MAX_DART_CHARS:
            result = result[:MAX_DART_CHARS] + "\n...(?댄븯 ?앸왂)"
        return result

    # 二쇱떇 ?곗씠??而⑦뀓?ㅽ듃 ?앹꽦
    def build_stock_context(stock_data: dict, period_label: str) -> str:
        lines = [f"議고쉶 湲곌컙: {period_label}", ""]
        for name, d in stock_data.items():
            hist = d["hist"]
            cur = hist["Close"].iloc[-1]
            start = hist["Close"].iloc[0]
            ret = (cur / start - 1) * 100
            high = hist["High"].max()
            low = hist["Low"].min()
            avg_vol = hist["Volume"].mean()
            lines.append(
                f"[{name}] ?꾩옱媛: ??cur:,.0f} | "
                f"湲곌컙?섏씡瑜? {ret:+.2f}% | "
                f"湲곌컙怨좉?: ??high:,.0f} | "
                f"湲곌컙?媛: ??low:,.0f} | "
                f"?됯퇏嫄곕옒?? {avg_vol:,.0f}"
            )
        return "\n".join(lines)

    pdf_loaded = "pdf_text" in st.session_state and st.session_state.pdf_text

    SYSTEM_PROMPT = """?뱀떊? ?쒓뎅 二쇱떇 ?쒖옣 ?꾨Ц ?좊꼸由ъ뒪?몄엯?덈떎.
?ъ슜?먭? ?쒓났???ㅼ떆媛?二쇱떇 ?곗씠?? DART 怨듭떆 ?뺣낫, 理쒖떊 ?댁뒪, ?낅줈?쒕맂 PDF 臾몄꽌瑜?醫낇빀?섏뿬 ?뺥솗?섍퀬 ?좎슜??遺꾩꽍???쒓났?⑸땲??
- DART 怨듭떆 ?뺣낫媛 ?쒓났??寃쎌슦 怨듭떆 ?좎쭨쨌?쒕ぉ쨌?쒖텧?몄쓣 ?몄슜?섏뿬 湲곗뾽??理쒓렐 怨듭떆 ?숉뼢???ㅻ챸?⑸땲??
- ?댁뒪媛 ?쒓났??寃쎌슦 理쒖떊 ?쒖옣 ?숉뼢怨?湲곗뾽 ?댁뒋瑜?遺꾩꽍??諛섏쁺?⑸땲??
- ?듬?? ?쒓뎅?대줈 ?묒꽦?섎ŉ, 援ъ껜?곸씤 ?섏튂? 異쒖쿂瑜??몄슜???ㅻ챸?⑸땲??
- ?ъ옄 ?먮떒? ?ъ슜??蹂몄씤??梨낆엫?꾩쓣 紐낆떆?섍퀬, 李멸퀬???뺣낫?꾩쓣 ?덈궡?⑸땲??"""

    stock_context = build_stock_context(stock_data, selected_period_label)
    dart_context  = build_dart_context()

    # ?댁뒪 而⑦뀓?ㅽ듃 ?ы븿 ?щ? ?좏깮
    include_news = st.checkbox(
        "?벐 ?댁뒪 而⑦뀓?ㅽ듃 ?ы븿 (?좏깮??醫낅ぉ??理쒖떊 ?댁뒪瑜?梨쀫큸 ?듬???諛섏쁺)",
        value=True,
        key="include_news_ctx",
    )
    news_context = ""
    if include_news and stock_data:
        with st.spinner("?댁뒪 而⑦뀓?ㅽ듃 ?섏쭛 以?.."):
            news_context = build_news_context(list(stock_data.keys()), max_per_stock=3)

    # ?꾩옱 ?쒖꽦 而⑦뀓?ㅽ듃 ?쒖떆
    active_sources = ["?뱢 ?ㅼ떆媛?二쇱떇 ?곗씠??]
    if dart_context:
        dart_company = st.session_state.get("dart_company", "")
        dart_cnt     = len(st.session_state.get("dart_results", []))
        active_sources.append(f"?뱥 DART 怨듭떆 ({dart_company} {dart_cnt}嫄?")
    if include_news and news_context:
        active_sources.append("?벐 理쒖떊 ?댁뒪")
    if pdf_loaded:
        active_sources.append(f"?뱞 {st.session_state.pdf_name}")
    st.caption("?꾩옱 ?듬? 而⑦뀓?ㅽ듃: " + " 쨌 ".join(active_sources))

    # ?몄뀡 硫붿떆吏 珥덇린??    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    # 梨꾪똿 湲곕줉 ?쒖떆
    chat_container = st.container(height=400)
    with chat_container:
        for msg in st.session_state.chat_messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # ?낅젰李?    user_input = st.chat_input("二쇱떇 ?곗씠?곗뿉 ???吏덈Ц?섏꽭??..")

    if user_input:
        # ?ъ슜??硫붿떆吏 異붽?
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        with chat_container:
            with st.chat_message("user"):
                st.markdown(user_input)

        # GPT ?몄텧
        try:
            client_gpt = OpenAI(api_key=openai_api_key)

            # 泥?踰덉㎏ ?ъ슜??硫붿떆吏??而⑦뀓?ㅽ듃 紐⑤몢 ?ы븿
            context_block = f"[?꾩옱 二쇱떇 ?곗씠??\n{stock_context}"
            if dart_context:
                context_block += f"\n\n{dart_context}"
            if include_news and news_context:
                context_block += f"\n\n[理쒖떊 ?댁뒪]\n{news_context}"
            if pdf_loaded:
                context_block += f"\n\n[?낅줈?쒕맂 PDF 臾몄꽌: {st.session_state.pdf_name}]\n{st.session_state.pdf_text}"
            context_block += f"\n\n[吏덈Ц]\n{user_input}"

            messages_for_api = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context_block},
            ]
            # ?댁쟾 ???而⑦뀓?ㅽ듃 ?ы븿 (理쒓렐 10??
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
                        stream=True,
                        temperature=0.7,
                        max_tokens=1024,
                    )
                    for chunk in stream:
                        delta = chunk.choices[0].delta.content or ""
                        full_response += delta
                        response_placeholder.markdown(full_response + "??)
                    response_placeholder.markdown(full_response)

            st.session_state.chat_messages.append(
                {"role": "assistant", "content": full_response}
            )

        except Exception as e:
            st.error(f"API ?ㅻ쪟: {e}")

    # ???珥덇린??踰꾪듉
    if st.session_state.chat_messages:
        if st.button("???珥덇린??, width='content'):
            st.session_state.chat_messages = []
            st.rerun()

# ?? ?대찓??蹂닿퀬??????????????????????????????????????????????????????????????????
st.divider()
st.subheader("?벁 二쇱떇 蹂닿퀬???대찓??諛쒖넚")

def build_report_html(stock_data: dict, period_label: str, news_per_stock: int = 5) -> str:
    now = datetime.now().strftime("%Y??%m??%d??%H:%M")
    rows = ""
    for name, d in stock_data.items():
        hist = d["hist"]
        cur = hist["Close"].iloc[-1]
        start = hist["Close"].iloc[0]
        ret = (cur / start - 1) * 100
        high = hist["High"].max()
        low = hist["Low"].min()
        color = "#c0392b" if ret >= 0 else "#2980b9"
        arrow = "?? if ret >= 0 else "??
        rows += f"""
        <tr>
          <td style="padding:8px 12px;font-weight:bold;">{name}</td>
          <td style="padding:8px 12px;text-align:right;">??cur:,.0f}</td>
          <td style="padding:8px 12px;text-align:right;color:{color};">{arrow} {ret:+.2f}%</td>
          <td style="padding:8px 12px;text-align:right;">??high:,.0f}</td>
          <td style="padding:8px 12px;text-align:right;">??low:,.0f}</td>
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

    return f"""
<!DOCTYPE html>
<html lang="ko">
<head><meta charset="UTF-8"><title>二쇱떇 蹂닿퀬??/title></head>
<body style="font-family:'Malgun Gothic',Arial,sans-serif;color:#2c3e50;max-width:800px;margin:0 auto;padding:20px;">
  <div style="background:linear-gradient(135deg,#1a252f,#2c3e50);color:white;padding:30px;border-radius:10px;margin-bottom:24px;">
    <h1 style="margin:0;font-size:24px;">?뱢 KOSPI 二쇱떇 蹂닿퀬??/h1>
    <p style="margin:8px 0 0;opacity:.8;">?앹꽦?쇱떆: {now} | 議고쉶 湲곌컙: {period_label}</p>
  </div>

  <h2 style="color:#2c3e50;">醫낅ぉ蹂??꾪솴</h2>
  <table style="width:100%;border-collapse:collapse;background:#fff;box-shadow:0 1px 4px rgba(0,0,0,.1);border-radius:8px;overflow:hidden;">
    <thead>
      <tr style="background:#34495e;color:white;">
        <th style="padding:10px 12px;text-align:left;">醫낅ぉ</th>
        <th style="padding:10px 12px;text-align:right;">?꾩옱媛</th>
        <th style="padding:10px 12px;text-align:right;">湲곌컙?섏씡瑜?/th>
        <th style="padding:10px 12px;text-align:right;">湲곌컙怨좉?</th>
        <th style="padding:10px 12px;text-align:right;">湲곌컙?媛</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>

  <h2 style="color:#2c3e50;margin-top:32px;">?벐 理쒖떊 ?댁뒪</h2>
  {news_html}

  <hr style="margin-top:32px;border:none;border-top:1px solid #ddd;">
  <p style="font-size:12px;color:#95a5a6;text-align:center;">
    蹂?蹂닿퀬?쒕뒗 李멸퀬?⑹씠硫??ъ옄 ?먮떒??梨낆엫? 蹂몄씤?먭쾶 ?덉뒿?덈떎.<br>
    ?곗씠??異쒖쿂: Yahoo Finance / Google News
  </p>
</body>
</html>"""

def send_report_email(sender: str, app_pw: str, recipient: str, html_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[二쇱떇 蹂닿퀬?? {datetime.now().strftime('%Y-%m-%d %H:%M')} KOSPI 醫낅ぉ ?꾪솴"
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender, app_pw)
        server.sendmail(sender, recipient, msg.as_string())

email_ready = smtp_sender and smtp_app_pw and smtp_recipient

if not email_ready:
    st.info("?ъ씠?쒕컮?먯꽌 **諛쒖떊 Gmail 怨꾩젙**, **??鍮꾨?踰덊샇**, **?섏떊 ?대찓??*??紐⑤몢 ?낅젰?섎㈃ 蹂닿퀬?쒕? 諛쒖넚?????덉뒿?덈떎.")
    with st.expander("Gmail ??鍮꾨?踰덊샇 諛쒓툒 諛⑸쾿"):
        st.markdown("""
1. Google 怨꾩젙 ??**蹂댁븞** ???대룞
2. **2?④퀎 ?몄쬆** ?쒖꽦??(?꾩닔)
3. 寃?됱갹??**"??鍮꾨?踰덊샇"** 寃????????鍮꾨?踰덊샇 ?앹꽦
4. ?앹꽦??**16?먮━ 鍮꾨?踰덊샇**瑜??ъ씠?쒕컮???낅젰
        """)
else:
    col_preview, col_send = st.columns([1, 1])

    with col_preview:
        news_count_report = st.selectbox("蹂닿퀬??醫낅ぉ???댁뒪 ??, [3, 5, 10], index=1, key="report_news_count")

    with col_send:
        st.markdown("<br>", unsafe_allow_html=True)
        send_btn = st.button("?벂 蹂닿퀬??諛쒖넚", type="primary", width='stretch')

    with st.expander("?뱞 蹂닿퀬??誘몃━蹂닿린", expanded=False):
        with st.spinner("蹂닿퀬???앹꽦 以?.."):
            preview_html = build_report_html(stock_data, selected_period_label, news_count_report)
        st.components.v1.html(preview_html, height=600, scrolling=True)

    if send_btn:
        with st.spinner("蹂닿퀬???앹꽦 諛?諛쒖넚 以?.."):
            try:
                report_html = build_report_html(stock_data, selected_period_label, news_count_report)
                send_report_email(smtp_sender, smtp_app_pw, smtp_recipient, report_html)
                st.success(f"??蹂닿퀬?쒓? **{smtp_recipient}** ?쇰줈 諛쒖넚?섏뿀?듬땲??")
            except smtplib.SMTPAuthenticationError:
                st.error("???몄쬆 ?ㅽ뙣: Gmail 怨꾩젙 ?먮뒗 ??鍮꾨?踰덊샇瑜??뺤씤??二쇱꽭??")
            except smtplib.SMTPException as e:
                st.error(f"??硫붿씪 諛쒖넚 ?ㅻ쪟: {e}")
            except Exception as e:
                st.error(f"???ㅻ쪟 諛쒖깮: {e}")

# ?? DART 怨듭떆 ?뺣낫 ????????????????????????????????????????????????????????????????
st.divider()
st.subheader("?뱥 DART 怨듭떆 ?뺣낫")

DART_REPORT_TYPES = {
    "?꾩껜": "",
    "?ъ뾽蹂닿퀬??: "A001",
    "諛섍린蹂닿퀬??: "A002",
    "遺꾧린蹂닿퀬??: "A003",
    "二쇱슂?ы빆蹂닿퀬??: "B001",
    "諛쒗뻾怨듭떆": "C001",
    "吏遺꾧났??: "D001",
    "湲고?怨듭떆": "E001",
    "?몃?媛먯궗愿??: "F001",
    "??쒓났??: "G001",
    "?먯궛?좊룞??: "H001",
    "嫄곕옒?뚭났??: "I001",
    "怨듭젙?꾧났??: "J001",
}

@st.cache_data(ttl=600)
def fetch_dart_disclosures(
    api_key: str,
    corp_code: str,
    bgn_de: str,
    end_de: str,
    pblntf_ty: str = "",
    page_count: int = 20,
) -> dict:
    params = {
        "crtfc_key": api_key,
        "corp_code": corp_code,
        "bgn_de": bgn_de,
        "end_de": end_de,
        "page_count": page_count,
    }
    if pblntf_ty:
        params["pblntf_ty"] = pblntf_ty
    resp = requests.get(
        "https://opendart.fss.or.kr/api/list.json",
        params=params,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()

@st.cache_data
def load_corp_codes_from_csv() -> pd.DataFrame:
    """corpcode.csv?먯꽌 ?꾩껜 湲곗뾽肄붾뱶 DataFrame 諛섑솚"""
    df = pd.read_csv(CORP_CODE_CSV, dtype=str).fillna("")
    return df

if not dart_api_key:
    st.info("?ъ씠?쒕컮??**OpenDART API ??*瑜??낅젰?섎㈃ 怨듭떆 ?뺣낫瑜?議고쉶?????덉뒿?덈떎.")
    with st.expander("DART API ??諛쒓툒 諛⑸쾿"):
        st.markdown("""
1. [https://opendart.fss.or.kr](https://opendart.fss.or.kr) ?묒냽
2. **?뚯썝媛????濡쒓렇??* ??**API ?좎껌** 硫붾돱
3. ?ъ슜 紐⑹쟻 ?낅젰 ???좎껌 ??諛쒓툒???ㅻ? ?ъ씠?쒕컮???낅젰
        """)
else:
    dart_col1, dart_col2, dart_col3 = st.columns([2, 2, 2])

    with dart_col1:
        dart_stock = st.selectbox(
            "議고쉶 醫낅ぉ",
            list(stock_data.keys()),
            key="dart_stock",
        )
    with dart_col2:
        dart_rtype = st.selectbox(
            "怨듭떆 ?좏삎",
            list(DART_REPORT_TYPES.keys()),
            key="dart_rtype",
        )
    with dart_col3:
        dart_period = st.selectbox(
            "議고쉶 湲곌컙",
            ["1媛쒖썡", "3媛쒖썡", "6媛쒖썡", "1??],
            index=1,
            key="dart_period",
        )

    dart_count = st.slider("理쒕? 議고쉶 嫄댁닔", 10, 100, 20, step=10, key="dart_count")

    if st.button("?뵇 怨듭떆 議고쉶", type="primary", key="dart_fetch_btn"):
        corp_code = DART_CORP_CODES.get(dart_stock)
        if not corp_code:
            st.error(f"'{dart_stock}'??corp_code瑜?李얠쓣 ???놁뒿?덈떎.")
        else:
            period_days = {"1媛쒖썡": 30, "3媛쒖썡": 90, "6媛쒖썡": 180, "1??: 365}[dart_period]
            end_dt = datetime.now()
            bgn_dt = end_dt - timedelta(days=period_days)
            bgn_de = bgn_dt.strftime("%Y%m%d")
            end_de = end_dt.strftime("%Y%m%d")
            pblntf_ty = DART_REPORT_TYPES[dart_rtype]

            with st.spinner(f"{dart_stock} 怨듭떆 ?뺣낫 議고쉶 以?.."):
                try:
                    result = fetch_dart_disclosures(
                        dart_api_key, corp_code, bgn_de, end_de, pblntf_ty, dart_count
                    )
                    status = result.get("status", "")
                    message = result.get("message", "")

                    if status == "000":
                        items = result.get("list", [])
                        st.session_state["dart_results"] = items
                        st.session_state["dart_company"] = dart_stock
                        st.success(f"**{dart_stock}** 怨듭떆 **{len(items)}嫄?* 議고쉶 ?꾨즺")
                    elif status == "013":
                        st.warning("議고쉶 湲곌컙 ??怨듭떆媛 ?놁뒿?덈떎.")
                        st.session_state["dart_results"] = []
                    else:
                        st.error(f"DART API ?ㅻ쪟 [{status}]: {message}")
                        st.session_state["dart_results"] = []
                except requests.exceptions.HTTPError as e:
                    st.error(f"HTTP ?ㅻ쪟: {e}")
                except Exception as e:
                    st.error(f"?ㅻ쪟 諛쒖깮: {e}")

    # 議고쉶 寃곌낵 ?쒖떆
    if st.session_state.get("dart_results"):
        items = st.session_state["dart_results"]
        company = st.session_state.get("dart_company", "")

        # 寃???꾪꽣
        search_kw = st.text_input("怨듭떆 ?쒕ぉ 寃??, placeholder="?ㅼ썙???낅젰...", key="dart_kw")
        filtered = [
            it for it in items
            if search_kw.lower() in it.get("report_nm", "").lower()
        ] if search_kw else items

        st.caption(f"珥?{len(filtered)}嫄??쒖떆 以?)

        for it in filtered:
            rcept_no  = it.get("rcept_no", "")
            report_nm = it.get("report_nm", "?쒕ぉ ?놁쓬")
            rcept_dt  = it.get("rcept_dt", "")
            flr_nm    = it.get("flr_nm", "")   # ?쒖텧??            rm        = it.get("rm", "")        # 鍮꾧퀬

            # ?좎쭨 ?щ㎎
            date_str = f"{rcept_dt[:4]}-{rcept_dt[4:6]}-{rcept_dt[6:]}" if len(rcept_dt) == 8 else rcept_dt
            dart_url  = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept_no}"

            with st.container():
                c1, c2 = st.columns([6, 2])
                with c1:
                    st.markdown(f"**[{report_nm}]({dart_url})**")
                    if flr_nm:
                        st.caption(f"?쒖텧?? {flr_nm}" + (f" | 鍮꾧퀬: {rm}" if rm else ""))
                with c2:
                    st.caption(f"?뱟 {date_str}")
                    st.caption(f"?묒닔踰덊샇: {rcept_no}")
                st.markdown("---")

    # 湲곗뾽肄붾뱶 寃??(corpcode.csv 湲곕컲)
    with st.expander("?뵊 湲곗뾽肄붾뱶 寃??(corpcode.csv 湲곕컲)"):
        st.markdown("**corpcode.csv** ?뚯씪?먯꽌 湲곗뾽紐낆쑝濡?corp_code瑜?寃?됲빀?덈떎.")
        corp_search_kw = st.text_input("湲곗뾽紐?寃??, placeholder="?? ?꾨?紐⑤퉬?? LG?꾩옄...", key="corp_search_kw")
        if corp_search_kw:
            try:
                df_corps = load_corp_codes_from_csv()
                matched = df_corps[df_corps["corp_name"].str.contains(corp_search_kw, na=False)]
                if matched.empty:
                    st.warning("寃??寃곌낵媛 ?놁뒿?덈떎.")
                else:
                    st.caption(f"{len(matched)}嫄?寃?됰맖")
                    st.dataframe(
                        matched[["corp_code", "corp_name", "corp_eng_name", "stock_code", "modify_date"]].rename(
                            columns={
                                "corp_code": "怨좎쑀踰덊샇",
                                "corp_name": "湲곗뾽紐?,
                                "corp_eng_name": "?곷Ц紐?,
                                "stock_code": "醫낅ぉ肄붾뱶",
                                "modify_date": "理쒖쥌蹂寃쎌씪",
                            }
                        ).reset_index(drop=True),
                        width='stretch',
                    )
            except FileNotFoundError:
                st.error(f"corpcode.csv ?뚯씪??李얠쓣 ???놁뒿?덈떎: `{CORP_CODE_CSV}`")
            except Exception as e:
                st.error(f"?ㅻ쪟: {e}")

