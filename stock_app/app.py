import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime
import sqlite3
import plotly.graph_objects as go
import os

# ==========================================
# 1. 數據庫與量化引擎
# ==========================================
def init_db():
    conn = sqlite3.connect('decision_brain.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS predictions 
                 (date TEXT, ticker TEXT, confidence REAL, conclusion TEXT, price REAL)''')
    conn.commit()
    conn.close()

def save_prediction(ticker, confidence, conclusion, price):
    try:
        conn = sqlite3.connect('decision_brain.db')
        c = conn.cursor()
        c.execute("INSERT INTO predictions VALUES (?, ?, ?, ?, ?)", 
                  (datetime.now().strftime("%Y-%m-%d %H:%M"), ticker, confidence, conclusion, price))
        conn.commit()
        conn.close()
    except Exception as e:
        st.error("數據庫錯誤: {}".format(e))

def get_all_predictions():
    try: return pd.read_sql_query("SELECT * FROM predictions", sqlite3.connect('decision_brain.db'))
    except: return pd.DataFrame()

def get_us_correlation(ticker):
    try:
        indicators = {'^IXIC': 'Nasdaq', 'NVDA': 'Nvidia'}
        multiplier = 1.0
        for symbol in indicators:
            ind = yf.Ticker(symbol).history(period="5d")
            if len(ind) >= 2 and ind['Close'].iloc[-1] > ind['Close'].iloc[0]: multiplier += 0.1
        return multiplier
    except: return 1.0

def get_tw_psychology(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="60d")
        if len(hist) < 20: return 1.0
        latest = hist.iloc[-1]
        vol_ma20 = hist['Volume'].rolling(window=20).mean().iloc[-1]
        year_high = hist['High'].max()
        modifier = 1.0
        if latest['Volume'] > vol_ma20 * 3 and latest['Close'] >= year_high * 0.95: modifier -= 0.2
        if latest['Volume'] < vol_ma20 * 0.5: modifier += 0.1
        return modifier
    except: return 1.0

def analyze_stock(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="2y")
        info = stock.info
        if len(hist) < 200: return None
        hist['MA150'] = hist['Close'].rolling(window=150).mean()
        hist['MA200'] = hist['Close'].rolling(window=200).mean()
        hist['MA50'] = hist['Close'].rolling(window=50).mean()
        latest = hist.iloc[-1]
        trend_ok = (latest['Close'] > latest['MA150'] > latest['MA200']) and \
                   (hist['MA200'].iloc[-1] > hist['MA200'].iloc[-20]) and \
                   (latest['Close'] > hist['Low'].rolling(window=252).min().iloc[-1] * 1.3) and \
                   (latest['Close'] >= hist['High'].rolling(window=252).max().iloc[-1] * 0.75)
        score, reasons = 0, []
        if info.get('quarterlyEarningsGrowth', 0) > 0.25: score += 2; reasons.append("季度EPS成長")
        if info.get('earningsGrowth', 0) > 0.15 and info.get('returnOnEquity', 0) > 0.17: score += 2; reasons.append("年度成長/ROE")
        try:
            market = yf.Ticker("^TWII").history(period="1y")
            market_change = (market['Close'].iloc[-1] / market['Close'].iloc[0]) - 1
            stock_change = (hist['Close'].iloc[-1] / hist['Close'].iloc[0]) - 1
            if stock_change > market_change: score += 2; reasons.append("相對強度(RS)領先")
        except: pass
        if info.get('institutionalOwnership', 0) > 0.4: score += 1; reasons.append("法人持股良好")
        if latest['Close'] >= hist['High'].rolling(window=252).max().iloc[-1] * 0.9: score += 1; reasons.append("高位盤整")
        if latest['Volume'] > hist['Volume'].rolling(window=20).mean().iloc[-1] * 1.5: score += 2; reasons.append("量能爆發")
        us_mult = get_us_correlation(ticker)
        tw_mod = get_tw_psychology(ticker)
        confidence = min(max((score/10)*100 * us_mult * tw_mod, 0), 100)
        year_high = hist['High'].rolling(window=252).max().iloc[-1]
        conservative_target = max(year_high, latest['Close'] * 1.15)
        optimistic_target = latest['Close'] * 1.30 
        return {
            "ticker": ticker, "name": info.get('shortName', '未知'), "sector": info.get('sector', '未知'),
            "industry": info.get('industry', '未知'), "market_cap": info.get('marketCap', 0),
            "pe": info.get('trailingPE', 'N/A'), "confidence": confidence, "trend_ok": trend_ok,
            "score": score, "reasons": reasons, "us_mult": us_mult, "tw_mod": tw_mod,
            "price": latest['Close'], "ma50": latest['MA50'], "target_low": conservative_target,
            "target_high": optimistic_target, "conclusion": "強烈看漲" if (confidence >= 80 and trend_ok) else "值得關注" if (confidence >= 60 and trend_ok) else "不建議買入",
            "history": hist
        }
    except Exception as e: return None

# ==========================================
# 3. War Room Style CSS
# ==========================================
def apply_stable_style():
    st.markdown("""
    <style>
    .stApp {
        background-color: #000000 !important;
        color: #FFFFFF !important;
        font-family: 'Inter', 'JetBrains Mono', monospace !important;
    }
    /* 戰情室掃描線效果 */
    .stApp::before {
        content: " ";
        display: block;
        position: absolute;
        top: 0; left: 0; bottom: 0; right: 0;
        background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
        z-index: 1000;
        background-size: 100% 2px, 3px 100%;
        pointer-events: none;
    }
    [data-testid="stHeader"], [data-testid="stSidebar"] {
        display: none !important;
    }
    h1, h2, h3, p, span, label {
        color: #FFFFFF !important;
    }
    .tesla-card {
        background-color: #1C1C1E !important;
        border-radius: 24px !important;
        padding: 20px !important;
        margin-bottom: 16px !important;
        border: 1px solid #2C2C2E !important;
        box-shadow: 0 0 15px rgba(232, 33, 39, 0.1) !important;
    }
    .tesla-text-secondary {
        color: #8E8E93 !important;
        font-size: 13px !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .stButton > button {
        background-color: #E82127 !important;
        color: white !important;
        border-radius: 12px !important;
        border: none !important;
        width: 100% !important;
        padding: 12px !important;
        font-weight: bold !important;
    }
    .confidence-bar-bg {
        background: #2C2C2E;
        height: 8px;
        border-radius: 4px;
        width: 100%;
        margin: 10px 0;
        overflow: hidden;
    }
    .confidence-bar-fill {
        height: 100%;
        border-radius: 4px;
    }
    .stTextInput > div > div > input {
        background-color: #1C1C1E !important;
        color: #FFFFFF !important;
        border-radius: 12px !important;
        border: 1px solid #E82127 !important;
    }
    /* 系統狀態欄 */
    .status-bar {
        display: flex;
        justify-content: space-between;
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        color: #00FFC3;
        margin-bottom: 20px;
        padding: 5px 10px;
        border: 1px solid #2C2C2E;
        border-radius: 8px;
        background: rgba(0, 255, 195, 0.05);
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 4. Streamlit UI 介面
# ==========================================
st.set_page_config(page_title="DECISION BRAIN", layout="centered")
apply_stable_style()
init_db()

if 'page' not in st.session_state:
    st.session_state.page = 'HOME'

def set_page(page_name):
    st.session_state.page = page_name

# 頂部戰情狀態欄
st.markdown(f"""
    <div class="status-bar">
        <span>SYSTEM: OPERATIONAL</span>
        <span>C-LINK: ACTIVE</span>
        <span>DATE: {datetime.now().strftime('%Y-%m-%d %H:%M')}</span>
    </div>
""", unsafe_allow_html=True)

if st.session_state.page == 'HOME':
    st.markdown("<h2 style='text-align: center; margin-bottom: 30px; letter-spacing: 3px;'>戰術決策中心</h2>", unsafe_allow_html=True)
    
    # 功能列表定義 (圖示文件, 標題, 頁面ID)
    menu_items = [
        ("icon1.webp", "個股精準診斷", "DIAGNOSIS"),
        ("icon2.webp", "強弱對決", "BATTLE"),
        ("icon3.webp", "持倉審核", "AUDIT"),
        ("icon4.webp", "預測證明牆", "PROOF"),
    ]

    for img_path, label, page in menu_items:
        # 使用列佈局模擬 Tesla Row: [圖示] [標題] [>]
        col_img, col_txt, col_arr = st.columns([1, 6, 1])
        with col_img:
            if os.path.exists(img_path):
                st.image(img_path, width=40)
            else:
                st.markdown("🖼️") # 沒圖片時顯示 fallback
        with col_txt:
            if st.button(label, key=page, use_container_width=True):
                set_page(page)
                st.rerun()
        with col_arr:
            st.markdown("<p style='text-align: center; color: #8E8E93;'>></p>", unsafe_allow_html=True)

elif st.session_state.page == 'DIAGNOSIS':
    if st.button("⬅️ 返回主選單"):
        set_page('HOME')
        st.rerun()
    st.markdown("<h2 style='text-align: center; margin-bottom: 20px;'>個股精準診斷</h2>", unsafe_allow_html=True)
    ticker = st.text_input("輸入股票代號", placeholder="例如: 2330.TW, NVDA").strip()
    if ticker:
        with st.spinner('分析數據中...'):
            res = analyze_stock(ticker)
            if res:
                st.markdown('<div class="tesla-card" style="text-align: center;">\n {0}\n <h1 style="font-size: 48px; margin: 10px 0;">${1:.2f}</h1>\n <p style="color: #8E8E93; font-size: 14px;">{2} | {3}</p>\n </div>'.format(
                    '<p class="tesla-text-secondary">{}</p>'.format(res['name']), 
                    res['price'], res['sector'], res['industry']), unsafe_allow_html=True)
                
                color = "#00FFC3" if res['confidence'] >= 60 else "#FADB14" if res['confidence'] >= 30 else "#FF3B3F"
                st.markdown('<div class="tesla-card">\n <div style="display: flex; justify-content: space-between; align-items: center;">\n <span class="tesla-text-secondary">信心指數</span>\n <span style="color: {0}; font-weight: bold;">{1:.1f}%</span>\n </div>\n <div class="confidence-bar-bg">\n <div class="confidence-bar-fill" style="width: {2}%; background-color: {0};"></div>\n </div>\n <p style="text-align: center; margin-top: 15px; font-weight: bold; font-size: 18px;">{3}</p>\n </div>'.format(
                    color, res['confidence'], res['confidence'], res['conclusion']), unsafe_allow_html=True)
                
                col_m1, col_m2 = st.columns(2)
                with col_m1: st.markdown('<div class="tesla-card" style="text-align: center;">\n <p class="tesla-text-secondary">總市值</p>\n <p style="font-weight: bold;">{0:.2f}B</p>\n </div>'.format(res['market_cap']/1e9), unsafe_allow_html=True)
                with col_m2: st.markdown('<div class="tesla-card" style="text-align: center;">\n <p class="tesla-text-secondary">本益比 (P/E)</p>\n <p style="font-weight: bold;">{0}</p>\n </div>'.format(res['pe']), unsafe_allow_html=True)
                
                fig = go.Figure(data=[go.Candlestick(x=res['history'].index, open=res['history']['Open'], high=res['history']['High'], low=res['history']['Low'], close=res['history']['Close'])])
                fig.add_trace(go.Scatter(x=res['history'].index, y=res['history']['MA50'], name='MA50', line=dict(color='#00CCFF', width=1.5)))
                fig.update_layout(template="plotly_dark", xaxis_rangeslider_visible=False, height=300, margin=dict(l=0,r=0,t=0,b=0), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig, use_container_width=True)
                
                st.markdown('<div class="tesla-card">\n <p style="font-weight: bold; margin-bottom: 10px;">⚡ 分析證據</p>\n <p class="tesla-text-secondary">趨勢: {0}</p>\n <p class="tesla-text-secondary">量化得分: {1}/10 ({2})</p>\n <p class="tesla-text-secondary">全球同步: x{3:.2f} | 心理修正: x{4:.2f}</p>\n </div>'.format(
                    '✅ 符合' if res['trend_ok'] else '❌ 不符合', res['score'], ', '.join(res['reasons']), res['us_mult'], res['tw_mod']), unsafe_allow_html=True)
                
                if st.button("💾 紀錄此預測"):
                    save_prediction(ticker, res['confidence'], res['conclusion'], res['price'])
                    st.success("已存入戰情紀錄")
                
                st.markdown('<div class="tesla-card" style="border-left: 4px solid #E82127;">\n <p class="tesla-text-secondary">目標價預測</p>\n <p style="font-size: 18px;">保守目標: <b>{0:.2f}</b></p>\n <p style="font-size: 18px;">樂觀目標: <b>{1:.2f}</b></p>\n </div>'.format(
                    res['target_low'], res['target_high']), unsafe_allow_html=True)
            else: st.error("未發現數據，請檢查股票代號。")

elif st.session_state.page == 'BATTLE':
    if st.button("⬅️ 返回主選單"):
        set_page('HOME')
        st.rerun()
    st.header("⚔️ 強弱對決")
    col_a, col_b = st.columns(2)
    with col_a: t_a = st.text_input("標的 A", "").strip()
    with col_b: t_b = st.text_input("標的 B", "").strip()
    if t_a and t_b:
        res_a = analyze_stock(t_a); res_b = analyze_stock(t_b)
        if res_a and res_b:
            df_comp = pd.DataFrame({"指標": ["信心指數 (%)", "趨勢符合", "CAN SLIM", "美股同步", "現價"], t_a: [res_a['confidence'], res_a['trend_ok'], res_a['score'], res_a['us_mult'], res_a['price']], t_b: [res_b['confidence'], res_b['trend_ok'], res_b['score'], res_b['us_mult'], res_b['price']]})
            st.table(df_comp)
            winner = t_a if res_a['confidence'] > res_b['confidence'] else t_b
            st.success("🏆 決策結果: 優先配置 **{0}**".format(winner))
        else: st.error("數據獲取失敗。")

elif st.session_state.page == 'AUDIT':
    if st.button("⬅️ 返回主選單"):
        set_page('HOME')
        st.rerun()
    st.header("📉 持倉審核")
    col1, col2, col3 = st.columns([2, 2, 2])
    with col1: ticker = st.text_input("股票代號", "").strip()
    with col2: entry_price = st.number_input("進場價格", min_value=0.0, step=0.1)
    with col3: stop_loss_pct = st.slider("止損百分比 (%)", 3, 20, 7)
    if ticker and entry_price > 0:
        res = analyze_stock(ticker)
        if res:
            st.write("現價: **{0:.2f}** | 持倉成本: **{1:.2f}**".format(res['price'], entry_price))
            status, reasons = "GREEN", []
            stop_price = entry_price * (1 - stop_loss_pct/100)
            if res['price'] < stop_price: status = "RED"; reasons.append("🚨 [止損觸發] 價格低於 {0}% 閾值 ({1:.2f})".format(stop_loss_pct, stop_price))
            if res['price'] < res['ma50']: status = "RED"; reasons.append("🚨 [趨勢崩潰] 價格低於 MA50")
            if res['tw_mod'] < 0.9: status = "YELLOW" if status != "RED" else "RED"; reasons.append("⚠️ [高位頂部] 成交量異常，考慮獲利了結")
            if res['score'] < 3: status = "YELLOW" if status != "RED" else "RED"; reasons.append("⚠️ [基本面轉弱] 不再是領頭羊")
            if status == "RED": st.error("🔴 最終決定: 立即出場")
            elif status == "YELLOW": st.warning("🟡 最終決定: 部分減碼")
            else: st.success("🟢 最終決定: 持有部位")
            for r in reasons: st.write(r)
            st.markdown("---")
            st.write("建議目標價: **{0:.2f}**".format(res['target_high']))
        else: st.error("數據獲取失敗。")

elif st.session_state.page == 'PROOF':
    if st.button("⬅️ 返回主選單"):
        set_page('HOME')
        st.rerun()
    st.header("📜 預測證明牆")
    df = get_all_predictions()
    if not df.empty:
        def check_perf(row):
            try:
                curr = yf.Ticker(row['ticker']).history(period="1d")['Close'].iloc[-1]
                return ((curr / row['price']) - 1) * 100
            except: return np.nan
        df['實際漲跌%'] = df.apply(check_perf, axis=1)
        def highlight_row(row):
            if row['實際漲跌%'] > 0 and row['confidence'] >= 60: return ['background-color: #1e3a1e'] * len(row)
            if row['實際漲跌%'] < 0 and row['confidence'] < 60: return ['background-color: #3a1e1a'] * len(row)
            return ['background-color: #1A1A1A'] * len(row)
        st.dataframe(df.style.apply(highlight_row, axis=1))
        correct = len(df[((df['實際漲跌%'] > 0) & (df['confidence'] >= 60)) | ((df['實際漲跌%'] < 0) & (df['confidence'] < 60))])
        st.metric("預測準確率", "{0:.1f}%".format((correct/len(df)*100)))
    else: st.info("目前尚無紀錄。")
