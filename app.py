import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import json

st.set_page_config(page_title="My Taiwan Tech Dashboard", layout="wide")
st.title("🚀 科技供應鏈與陣地戰情報儀表板")
st.caption("對標 SemiAnalysis 拆解邏輯 | 整合動態均線 (MA)、機構目標價與精準新聞情報")

# 1. 預設選單
INITIAL_STOCKS = {
    "2368 (金像電)": "2368.TW",
    "5498 (凱崴)": "5498.TWO",
    "1785 (光洋科)": "1785.TWO",
    "6451 (訊芯-KY)": "6451.TW",
    "2317 (鴻海)": "2317.TW",
    "6223 (旺矽)": "6223.TW",
    "6515 (穎崴)": "6515.TWO",
    "3081 (聯亞)": "3081.TWO"
}

if 'stocks' not in st.session_state:
    st.session_state.stocks = INITIAL_STOCKS.copy()

# --- 台股中文名稱查詢函數 (自動查詢 TWSE / TPEx API) ---
@st.cache_data(ttl=86400)
def get_tw_stock_name(code):
    try:
        # 向證交所開放 API 查詢股票名稱
        url = f"https://openapi.twse.com.tw/v1/opendata/t187ap03_L"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode('utf-8'))
            for item in data:
                if item.get('公司代號') == code:
                    return item.get('公司簡稱', '')
    except:
        pass

    try:
        # 若上市查無，向櫃買中心開放 API 查詢
        url_otc = f"https://www.tpex.org.tw/openapi/v1/mops_t187ap03_R"
        req_otc = urllib.request.Request(url_otc, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_otc, timeout=3) as response:
            data_otc = json.loads(response.read().decode('utf-8'))
            for item in data_otc:
                if item.get('公司代號') == code:
                    return item.get('公司簡稱', '')
    except:
        pass
        
    return ""

# --- 側邊欄控制區 ---
st.sidebar.header("🎯 供應鏈標的選單")

selected_name = st.sidebar.selectbox(
    "🔍 選擇或搜尋標的", 
    options=list(st.session_state.stocks.keys())
)
stock_ticker = st.session_state.stocks[selected_name]

st.sidebar.markdown("---")

# 快速新增標的
st.sidebar.subheader("➕ 快速新增標的")
input_code = st.sidebar.text_input("輸入台股代號 (例: 2408)", placeholder="例如: 2408")

if st.sidebar.button("確認新增"):
    code = input_code.strip()
    if code:
        test_ticker_tw = f"{code}.TW"
        test_ticker_two = f"{code}.TWO"
        
        check_data = yf.Ticker(test_ticker_tw).history(period="1d")
        if not check_data.empty:
            final_ticker = test_ticker_tw
        else:
            check_data_two = yf.Ticker(test_ticker_two).history(period="1d")
            if not check_data_two.empty:
                final_ticker = test_ticker_two
            else:
                final_ticker = None

        if final_ticker:
            # 抓取中文簡稱
            cn_name = get_tw_stock_name(code)
            if cn_name:
                label = f"{code} ({cn_name})"
            else:
                label = f"{code}"

            st.session_state.stocks[label] = final_ticker
            st.sidebar.success(f"已成功新增: {label}")
            st.rerun()
        else:
            st.sidebar.error("查無此股票數據，請確認代號！")

st.sidebar.markdown("---")

if st.sidebar.button(f"🗑️ 刪除目前選中的「{selected_name}」"):
    if len(st.session_state.stocks) > 1:
        del st.session_state.stocks[selected_name]
        st.sidebar.success(f"已刪除 {selected_name}")
        st.rerun()

# --- 原生 XML 解析 Google News RSS ---
@st.cache_data(ttl=1800)
def fetch_google_news_native(query):
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    articles = []
    try:
        req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            
            for item in root.findall('.//item')[:6]:
                title = item.find('title').text if item.find('title') is not None else "無標題"
                link = item.find('link').text if item.find('link') is not None else "#"
                pub_date = item.find('pubDate').text if item.find('pubDate') is not None else ""
                articles.append({'title': title, 'link': link, 'published': pub_date})
    except Exception as e:
        pass
    return articles

# --- 行情與機構資料抓取 ---
@st.cache_data(ttl=1800)
def fetch_stock_all(ticker):
    stock = yf.Ticker(ticker)
    df = stock.history(period="2y")
    
    # 計算移動平均線 (MA)
    df['MA5'] = df['Close'].rolling(window=5).mean()
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    df['MA240'] = df['Close'].rolling(window=240).mean()
    
    df_display = df.tail(252).copy()
    
    try:
        info = stock.info
    except:
        info = {}
        
    return df_display, info

df, info = fetch_stock_all(stock_ticker)

if not df.empty:
    df = df.reset_index()
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    price_change = latest['Close'] - prev['Close']
    pct_change = (price_change / prev['Close']) * 100

    # 頂部行情列
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("最新收盤價", f"{latest['Close']:.2f} TWD", delta=f"{pct_change:.2f}%")
    col2.metric("最高價", f"{latest['High']:.2f}")
    col3.metric("最低價", f"{latest['Low']:.2f}")
    col4.metric("成交量", f"{int(latest['Volume']/1000):,} 張")
    st.markdown("---")

    # 🏛️ 模組 1：機構評等與目標價分析
    st.header("🏛️ 市場機構目標價與評等分析")
    
    target_mean = info.get('targetMeanPrice') or info.get('targetMedianPrice')
    target_high = info.get('targetHighPrice')
    target_low = info.get('targetLowPrice')
    current_price = latest['Close']

    if target_mean and target_mean > 0:
        upside = ((target_mean - current_price) / current_price) * 100
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("機構平均目標價", f"{target_mean:.2f} TWD", delta=f"潛在空間 {upside:+.1f}%")
        m2.metric("最高機構目標價", f"{target_high:.2f} TWD" if target_high else "N/A")
        m3.metric("最低機構目標價", f"{target_low:.2f} TWD" if target_low else "N/A")
        
        rec = str(info.get('recommendationKey', 'N/A')).upper()
        m4.metric("市場綜合共識評等", rec)
    else:
        st.warning("⚠️ 數據源說明：該標的為台灣上櫃或中小型股，美股連線數據源未公開外資研究報告目標價。下方技術線型與即時新聞依然即時更新！")

    st.markdown("---")

    # 📈 模組 2：K 線與動態均線圖形
    st.header("📈 股價走勢與技術線型 (均線分析)")
    
    c1, c2, c3, c4 = st.columns(4)
    show_ma5 = c1.checkbox("5 日線 (週線)", value=True)
    show_ma20 = c2.checkbox("20 日線 (月線)", value=True)
    show_ma60 = c3.checkbox("60 日線 (季線)", value=True)
    show_ma240 = c4.checkbox("240 日線 (年線)", value=False)

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df['Date'], y=df['Close'],
        mode='lines', name='收盤價',
        line=dict(color='white', width=1.5)
    ))

    if show_ma5:
        fig.add_trace(go.Scatter(
            x=df['Date'], y=df['MA5'],
            mode='lines', name='5日線 (MA5)',
            line=dict(color='#FFD700', width=1.2)
        ))
    if show_ma20:
        fig.add_trace(go.Scatter(
            x=df['Date'], y=df['MA20'],
            mode='lines', name='20日線 (月線)',
            line=dict(color='#00FFFF', width=1.5)
        ))
    if show_ma60:
        fig.add_trace(go.Scatter(
            x=df['Date'], y=df['MA60'],
            mode='lines', name='60日線 (季線)',
            line=dict(color='#FF00FF', width=1.5)
        ))
    if show_ma240:
        fig.add_trace(go.Scatter(
            x=df['Date'], y=df['MA240'],
            mode='lines', name='240日線 (年線)',
            line=dict(color='#00FF00', width=1.8)
        ))

    fig.update_layout(
        title=f"{selected_name} 動態技術線型分析",
        xaxis_title="日期",
        yaxis_title="價格 (TWD)",
        template="plotly_dark",
        hovermode="x unified"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # 📰 模組 3：精簡版 Google News 折疊選單
    news_list = fetch_google_news_native(selected_name)
    
    with st.expander(f"📰 查看「{selected_name}」最新市場新聞與即時動態 ({len(news_list)} 則)"):
        if news_list:
            for item in news_list:
                st.markdown(f"• [{item['title']}]({item['link']}) — <span style='color:gray; font-size:12px;'>{item['published']}</span>", unsafe_allow_html=True)
        else:
            st.write("目前尚無搜尋到相關新聞。")

    # 隱藏式歷史數據
    with st.expander("📄 查看詳細原始數據表格"):
        st.dataframe(df.sort_values(by='Date', ascending=False), use_container_width=True)
else:
    st.error(f"目前無法載入「{stock_ticker}」的數據。")
