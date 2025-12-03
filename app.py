import streamlit as st
import pandas as pd
import numpy as np
import io
import gspread
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import altair as alt
import calendar
from datetime import datetime, date

# ==========================================
# 1. CONFIG & CSS (DARK MODE & CUSTOM COLORS)
# ==========================================
st.set_page_config(page_title="Shop Analytics Dashboard", layout="wide", page_icon="📊")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;600;700&family=Prompt:wght@300;400;500;600&display=swap');
    
    /* 1. FORCE DARK BACKGROUND */
    .stApp { background-color: #0e1117 !important; color: #ffffff !important; }
    
    html, body, [class*="css"] { font-family: 'Sarabun', sans-serif; }
    .block-container { padding-top: 2rem !important; }
    
    h1, h2, h3, h4, h5, h6, p, span, label, div { color: #ffffff !important; }
    
    /* 2. Header Bar */
    .header-bar {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 15px 20px; border-radius: 10px; margin-bottom: 20px;
        display: flex; align-items: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        border: 1px solid #444;
    }
    .header-title { font-size: 22px; font-weight: 700; margin: 0; color: white !important; }
    
    /* 3. Navigation Group */
    div[role="radiogroup"] {
        background-color: #1c1c1c; padding: 5px; border-radius: 10px;
        border: 1px solid #444; display: flex; justify-content: center;
        margin-top: 10px; margin-bottom: 20px;
    }
    
    /* 4. Inputs */
    .stTextInput input, .stSelectbox div[data-baseweb="select"], .stDateInput input {
        background-color: #262730 !important;
        color: white !important;
        border: 1px solid #555 !important;
    }
    div[role="listbox"] ul { background-color: #262730 !important; }
    div[role="listbox"] li { color: white !important; }

    /* 5. Metrics Cards */
    .metric-container { display: flex; gap: 15px; margin-bottom: 20px; flex-wrap: wrap; }
    .custom-card {
        background: #1c1c1c; border-radius: 10px; padding: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.5); flex: 1; min-width: 180px;
        border-left: 5px solid #ddd; border: 1px solid #333;
    }
    .card-label { color: #aaa !important; font-size: 13px; font-weight: 600; margin-bottom: 5px; }
    .card-value { color: #fff !important; font-size: 24px; font-weight: 700; }
    
    .border-blue { border-left-color: #3498db; }
    .border-purple { border-left-color: #9b59b6; }
    .border-orange { border-left-color: #e67e22; }
    .border-green { border-left-color: #27ae60; }

    /* 6. Tables */
    .table-wrapper {
        overflow: auto; width: 100%; max-height: 800px;
        margin-top: 10px; background: #1c1c1c;
        border-radius: 8px; border: 1px solid #444;
        padding-bottom: 10px;
    }
    .custom-table {
        width: 100%; min-width: 1000px;
        border-collapse: separate; border-spacing: 0;
        font-family: 'Sarabun', sans-serif; font-size: 12px; color: #ddd;
    }
    .custom-table th, .custom-table td {
        padding: 5px 8px; text-align: center;
        border-bottom: 1px solid #333; border-right: 1px solid #333; white-space: nowrap;
    }
    .daily-table thead th, .month-table thead th {
        position: sticky; top: 0; z-index: 100;
        background-color: #1e3c72; color: white !important;
        font-weight: 700; border-bottom: 2px solid #555;
    }

    /* --- CUSTOM TABLE COLORS (GRAY SCALE) --- */
    .custom-table tbody tr:nth-child(odd) td { background-color: #2b2b2b !important; } /* Dark Gray */
    .custom-table tbody tr:nth-child(even) td { background-color: #3f3f3f !important; } /* Light Gray */
    
    .custom-table tbody tr:hover td { background-color: #555 !important; }
    
    /* Footer */
    .footer-row td {
        position: sticky; bottom: 0; z-index: 100;
        background-color: #333 !important; font-weight: bold; color: white !important; border-top: 2px solid #f1c40f;
    }
    
    /* Buttons */
    div.stButton > button {
        width: 100%; border-radius: 6px; height: 42px; font-weight: bold;
        background-color: #333; color: white; border: 1px solid #555;
    }
    div.stButton > button:hover { border-color: #00d2ff; color: #00d2ff; }
    
    /* P&L Table */
    .pnl-table { width: 100%; border-collapse: collapse; font-size: 14px; background-color: #1c1c1c; }
    .pnl-table th { text-align: left; padding: 12px; color: #aaa; border-bottom: 1px solid #444; }
    .pnl-table td { padding: 12px; border-bottom: 1px solid #333; color: #ddd; }
    
    .col-small { font-size: 10px; color: #aaa; }
</style>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
""", unsafe_allow_html=True)

# ==========================================
# 2. SETTINGS
# ==========================================
FOLDER_ID_DATA = "1ciI_X2m8pVcsjRsPuUf5sg--6uPSPPDp"
FOLDER_ID_ADS = "1ZE76TXNA_vNeXjhAZfLgBQQGIV0GY7w8"
SHEET_MASTER_URL = "https://docs.google.com/spreadsheets/d/1Q3akHm1GKkDI2eilGfujsd9pO7aOjJvyYJNuXd98lzo/edit"

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
def safe_float(val):
    if pd.isna(val) or val == "" or val is None: return 0.0
    s = str(val).strip().replace(',', '').replace('฿', '').replace(' ', '')
    if s in ['-', 'nan', 'NaN', 'None']: return 0.0
    try:
        if '%' in s: return float(s.replace('%', '')) / 100
        return float(s)
    except: return 0.0

def safe_date(val):
    try: return pd.to_datetime(val).date()
    except: return None

# ==========================================
# 4. BACKEND: LOAD & PROCESS DATA
# ==========================================
@st.cache_resource
def get_drive_service():
    if "gcp_service_account" not in st.secrets:
        st.error("Error: ไม่พบ Secrets กรุณาตรวจสอบการตั้งค่า")
        st.stop()
    creds_dict = dict(st.secrets["gcp_service_account"])
    scopes = ['https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/spreadsheets']
    return service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)

def load_raw_files():
    creds = get_drive_service()
    service = build('drive', 'v3', credentials=creds)
    gc = gspread.authorize(creds)

    def get_files(folder_id):
        try:
            results = service.files().list(q=f"'{folder_id}' in parents and trashed=false", fields="files(id, name)").execute()
            return results.get('files', [])
        except: return []

    def read_file(file_id, filename):
        try:
            request = service.files().get_media(fileId=file_id)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while done is False: status, done = downloader.next_chunk()
            fh.seek(0)
            if filename.lower().endswith('.csv'): return pd.read_csv(fh, dtype={'หมายเลขคำสั่งซื้อออนไลน์': str})
            elif filename.lower().endswith(('.xlsx', '.xls')): return pd.read_excel(fh)
        except: pass
        return None

    # Load DATA
    files_data = get_files(FOLDER_ID_DATA)
    df_list = []
    for f in files_data:
        df = read_file(f['id'], f['name'])
        if df is not None:
            if 'หมายเลขคำสั่งซื้อออนไลน์' in df.columns:
                df['หมายเลขคำสั่งซื้อออนไลน์'] = df['หมายเลขคำสั่งซื้อออนไลน์'].astype(str).str.replace(r'\.0$', '', regex=True)
            df_list.append(df)
    df_data = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()

    # Load ADS
    files_ads = get_files(FOLDER_ID_ADS)
    df_ads_list = []
    for f in files_ads:
        df = read_file(f['id'], f['name'])
        if df is not None: df_ads_list.append(df)
    df_ads_raw = pd.concat(df_ads_list, ignore_index=True) if df_ads_list else pd.DataFrame()

    # Load MASTER
    df_master = pd.DataFrame()
    try:
        sh = gc.open_by_url(SHEET_MASTER_URL)
        df_master = pd.DataFrame(sh.worksheet("MASTER_ITEM").get_all_records())
    except: pass
    
    # ** NO FIXED COST LOAD NEEDED **
    df_fix = pd.DataFrame() 

    return df_data, df_ads_raw, df_master, df_fix

@st.cache_data(ttl=600)
def process_all_data():
    df_data, df_ads_raw, df_master, _ = load_raw_files()

    if df_data.empty: return pd.DataFrame(), pd.DataFrame(), {}, []

    # --- 1. CLEAN MASTER ---
    if not df_master.empty:
        df_master.columns = df_master.columns.astype(str).str.strip()
        # Auto-detect 'ชื่อสินค้า'
        if 'ชื่อสินค้า' not in df_master.columns:
            if len(df_master.columns) >= 2:
                col_b = df_master.columns[1]
                df_master.rename(columns={col_b: 'ชื่อสินค้า'}, inplace=True)
            else:
                df_master['ชื่อสินค้า'] = df_master['SKU'] if 'SKU' in df_master.columns else "Unknown"

    cols_money = ['ต้นทุน', 'ราคากล่อง', 'ค่าส่งเฉลี่ย']
    cols_percent = ['ค่าคอมมิชชั่น Admin', 'ค่าคอมมิชชั่น Telesale', 
                    'J&T Express', 'Flash Express', 'ThailandPost', 'DHL_1', 'LEX TH', 'SPX Express',
                    'Express Delivery - ส่งด่วน', 'Standard Delivery - ส่งธรรมดาในประเทศ']

    for col in cols_money:
        if col in df_master.columns: df_master[col] = df_master[col].apply(safe_float)
    for col in cols_percent:
        if col in df_master.columns: df_master[col] = df_master[col].apply(safe_float)

    if 'SKU' in df_master.columns: df_master['SKU'] = df_master['SKU'].astype(str).str.strip()

    # --- 2. PROCESS ADS ---
    df_ads_agg = pd.DataFrame(columns=['Date', 'SKU_Main', 'Ads_Amount'])
    if not df_ads_raw.empty:
        col_cost = next((c for c in ['จำนวนเงินที่ใช้จ่ายไป (THB)', 'Cost', 'Amount'] if c in df_ads_raw.columns), None)
        col_date = next((c for c in ['วัน', 'Date'] if c in df_ads_raw.columns), None)
        col_camp = next((c for c in ['ชื่อแคมเปญ', 'Campaign'] if c in df_ads_raw.columns), None)

        if col_cost and col_date and col_camp:
            df_ads_raw['Date'] = df_ads_raw[col_date].apply(safe_date)
            df_ads_raw = df_ads_raw.dropna(subset=['Date'])
            df_ads_raw[col_cost] = df_ads_raw[col_cost].apply(safe_float)
            df_ads_raw['SKU_Main'] = df_ads_raw[col_camp].astype(str).str.extract(r'\[(.*?)\]')
            df_ads_agg = df_ads_raw.groupby(['Date', 'SKU_Main'])[col_cost].sum().reset_index(name='Ads_Amount')

    # --- 3. PROCESS TRANSACTIONS ---
    cols = [c for c in ['หมายเลขคำสั่งซื้อออนไลน์', 'สถานะคำสั่งซื้อ', 'บริษัทขนส่ง', 'เวลาสั่งซื้อ', 'รูปแบบสินค้า', 'จำนวน', 'รายละเอียดยอดที่ชำระแล้ว', 'ผู้สร้างคำสั่งซื้อ', 'วิธีการชำระเงิน', 'ชื่อสินค้า', 'ประเภทการทำงาน'] if c in df_data.columns]
    df = df_data[cols].copy()

    if 'สถานะคำสั่งซื้อ' in df.columns:
        df = df[~df['สถานะคำสั่งซื้อ'].isin(['ยกเลิก'])]

    df['Date'] = df['เวลาสั่งซื้อ'].apply(safe_date)
    df = df.dropna(subset=['Date'])
    df['SKU_Main'] = df['รูปแบบสินค้า'].astype(str).str.split('-').str[0].str.strip()

    master_cols = [c for c in cols_money + cols_percent + ['SKU', 'ชื่อสินค้า'] if c in df_master.columns]
    df_merged = pd.merge(df, df_master[master_cols].drop_duplicates('SKU'), left_on='SKU_Main', right_on='SKU', how='left')

    if 'ชื่อสินค้า_y' in df_merged.columns: df_merged.rename(columns={'ชื่อสินค้า_y': 'ชื่อสินค้า'}, inplace=True)
    if 'ชื่อสินค้า' not in df_merged.columns: df_merged['ชื่อสินค้า'] = df_merged['SKU_Main']

    # Force Numeric
    df_merged['จำนวน'] = df_merged['จำนวน'].apply(safe_float)
    df_merged['ต้นทุน'] = df_merged['ต้นทุน'].fillna(0).apply(safe_float)
    df_merged['รายละเอียดยอดที่ชำระแล้ว'] = df_merged['รายละเอียดยอดที่ชำระแล้ว'].apply(safe_float)

    df_merged['CAL_COST'] = df_merged['จำนวน'] * df_merged['ต้นทุน']

    shipping_map = {"J&T Express": "J&T Express", "J&T": "J&T Express", "Flash Express": "Flash Express", "Flash": "Flash Express", "Kerry Express": "Kerry Express", "Kerry": "Kerry Express", "Thailand Post": "ThailandPost", "ThailandPost": "ThailandPost", "DHL Domestic": "DHL_1", "DHL": "DHL_1", "Shopee Express": "SPX Express", "SPX Express": "SPX Express", "Lazada Express": "LEX TH", "LEX": "LEX TH"}
    
    def get_ship_rate(row):
        c = str(row.get('บริษัทขนส่ง','')).strip()
        k = shipping_map.get(c, c)
        val = row.get(k, row.get('Standard Delivery - ส่งธรรมดาในประเทศ', 0))
        return safe_float(val)

    df_merged['SHIP_RATE'] = df_merged.apply(get_ship_rate, axis=1)
    is_cod = df_merged['วิธีการชำระเงิน'].astype(str).str.contains('COD|ปลายทาง', case=False, na=False)
    
    df_merged['CAL_COD_COST'] = np.where(is_cod, (df_merged['รายละเอียดยอดที่ชำระแล้ว'] * df_merged['SHIP_RATE']) * 1.07, 0)

    def get_role(row):
        t = str(row.get('ประเภทการทำงาน','')) + " " + str(row.get('ผู้สร้างคำสั่งซื้อ',''))
        if 'admin' in t.lower() or 'แอดมิน' in t: return 'Admin'
        if 'tele' in t.lower() or 'เทเล' in t: return 'Telesale'
        return 'Unknown'
    
    df_merged['Calculated_Role'] = df_merged.apply(get_role, axis=1)
    
    com_admin = df_merged.get('ค่าคอมมิชชั่น Admin', 0).fillna(0).apply(safe_float)
    com_tele = df_merged.get('ค่าคอมมิชชั่น Telesale', 0).fillna(0).apply(safe_float)

    df_merged['CAL_COM_ADMIN'] = np.where((df_merged['Calculated_Role'] == 'Admin'), df_merged['รายละเอียดยอดที่ชำระแล้ว'] * com_admin, 0)
    df_merged['CAL_COM_TELESALE'] = np.where((df_merged['Calculated_Role'] == 'Telesale'), df_merged['รายละเอียดยอดที่ชำระแล้ว'] * com_tele, 0)

    # --- 4. FINAL GROUPING ---
    agg_dict = {
        'ชื่อสินค้า': 'first', 'หมายเลขคำสั่งซื้อออนไลน์': 'count', 'จำนวน': 'sum', 'รายละเอียดยอดที่ชำระแล้ว': 'sum',
        'CAL_COST': 'sum', 'ราคากล่อง': 'max', 'ค่าส่งเฉลี่ย': 'max', 'CAL_COD_COST': 'sum',
        'CAL_COM_ADMIN': 'sum', 'CAL_COM_TELESALE': 'sum'
    }
    
    for c in agg_dict.keys():
        if c not in df_merged.columns: df_merged[c] = 0

    df_daily = df_merged.groupby(['Date', 'SKU_Main']).agg(agg_dict).reset_index()
    df_daily.rename(columns={'หมายเลขคำสั่งซื้อออนไลน์': 'จำนวนออเดอร์', 'ราคากล่อง': 'BOX_COST', 'ค่าส่งเฉลี่ย': 'DELIV_COST'}, inplace=True)

    if not df_ads_agg.empty:
        df_daily = pd.merge(df_daily, df_ads_agg, on=['Date', 'SKU_Main'], how='outer')
    else: df_daily['Ads_Amount'] = 0

    df_daily = df_daily.fillna(0)
    
    # Force Numeric
    num_cols = ['BOX_COST', 'DELIV_COST', 'CAL_COD_COST', 'CAL_COM_ADMIN', 'CAL_COM_TELESALE', 'CAL_COST', 'Ads_Amount', 'รายละเอียดยอดที่ชำระแล้ว']
    for c in num_cols: df_daily[c] = df_daily[c].apply(safe_float)

    df_daily['Other_Costs'] = df_daily['BOX_COST'] + df_daily['DELIV_COST'] + df_daily['CAL_COD_COST'] + df_daily['CAL_COM_ADMIN'] + df_daily['CAL_COM_TELESALE']
    df_daily['Total_Cost'] = df_daily['CAL_COST'] + df_daily['Other_Costs'] + df_daily['Ads_Amount']
    
    # ** NO FIX COST IN NET PROFIT **
    df_daily['Net_Profit'] = df_daily['รายละเอียดยอดที่ชำระแล้ว'] - df_daily['Total_Cost']

    # Date Helpers
    df_daily['Date'] = pd.to_datetime(df_daily['Date'])
    df_daily['Year'] = df_daily['Date'].dt.year
    df_daily['Month_Num'] = df_daily['Date'].dt.month
    thai_months = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
    df_daily['Month_Thai'] = df_daily['Month_Num'].apply(lambda x: thai_months[x-1] if 1<=x<=12 else "")
    df_daily['Day'] = df_daily['Date'].dt.day
    df_daily['Date'] = df_daily['Date'].dt.date 

    sku_map = df_daily.groupby('SKU_Main')['ชื่อสินค้า'].last().to_dict()
    if 'ชื่อสินค้า' in df_master.columns: sku_map.update(df_master.set_index('SKU')['ชื่อสินค้า'].to_dict())
    sku_list = sorted(list(set(df_daily['SKU_Main'].unique())))

    return df_daily, pd.DataFrame(), sku_map, sku_list

# ==========================================
# 5. FRONTEND: UI
# ==========================================
try:
    df_daily, _, sku_name_lookup, daily_skus = process_all_data()
    
    if df_daily.empty:
        st.warning("⚠️ ยังไม่พบข้อมูลใน Google Drive")
        st.stop()

    thai_months = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
    
    if 'selected_skus' not in st.session_state: st.session_state.selected_skus = []
    if 'selected_skus_d' not in st.session_state: st.session_state.selected_skus_d = []
    if 'selected_skus_g' not in st.session_state: st.session_state.selected_skus_g = []
    
    sku_options = [f"{sku} : {sku_name_lookup.get(sku, '')}" for sku in daily_skus]
    sku_map_rev = {f"{sku} : {sku_name_lookup.get(sku, '')}": sku for sku in daily_skus}

    def cb_add_m():
        term = st.session_state.search_m.lower()
        if term:
            found = [o for o in sku_options if term in o.lower()]
            st.session_state.selected_skus = list(set(st.session_state.selected_skus).union(set(found)))
    def cb_clear_m(): st.session_state.selected_skus = []
    
    def cb_add_d():
        term = st.session_state.search_d.lower()
        if term:
            found = [o for o in sku_options if term in o.lower()]
            st.session_state.selected_skus_d = list(set(st.session_state.selected_skus_d).union(set(found)))
    def cb_clear_d(): st.session_state.selected_skus_d = []

    def cb_add_g():
        term = st.session_state.search_g.lower()
        if term:
            found = [o for o in sku_options if term in o.lower()]
            st.session_state.selected_skus_g = list(set(st.session_state.selected_skus_g).union(set(found)))
    def cb_clear_g(): st.session_state.selected_skus_g = []

    page = st.radio("เลือกหน้าจอ:", ["📊 REPORT_MONTH", "📅 REPORT_DAILY", "📈 PRODUCT GRAPH", "📈 YEARLY P&L", "📅 MONTHLY P&L", "💰 COMMISSION"], horizontal=True)

    # ---------------- PAGE 1: MONTHLY ----------------
    if page == "📊 REPORT_MONTH":
        st.markdown('<div class="header-bar"><div class="header-title"><i class="fas fa-chart-line"></i> สรุปยอดขายรายเดือน</div></div>', unsafe_allow_html=True)
        
        with st.container():
            c1, c2, c3 = st.columns([1,1,2])
            sel_year = c1.selectbox("เลือกปี", sorted(df_daily['Year'].unique(), reverse=True), key='m_y')
            sel_month = c2.selectbox("เลือกเดือน", thai_months, index=datetime.now().month-1, key='m_m')
            filter_mode = c3.selectbox("เงื่อนไข", ["📦 แสดงรายการที่มีการเคลื่อนไหว", "💰 เฉพาะรายการที่ขายได้", "💸 ผลาญงบ (มี Ads แต่ขายไม่ได้)", "📋 แสดง Master ทั้งหมด"], key='m_f')
            
            c4, c5, c6, c7, c8 = st.columns([1.5, 3.5, 0.4, 0.4, 0.8])
            c4.text_input("ค้นหา SKU:", key="search_m")
            c5.multiselect("รายการที่เลือก:", sku_options, key="selected_skus")
            c6.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
            c6.button("➕", on_click=cb_add_m, use_container_width=True)
            c7.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
            c7.button("🧹", on_click=cb_clear_m, use_container_width=True)
            c8.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
            c8.button("🚀 ประมวลผล", type="primary", use_container_width=True)

        df_view = df_daily[(df_daily['Year']==sel_year) & (df_daily['Month_Thai']==sel_month)]
        
        sku_stats = df_view.groupby('SKU_Main').agg({'รายละเอียดยอดที่ชำระแล้ว':'sum', 'Ads_Amount':'sum'}).reset_index()
        auto_skus = []
        if "ขายได้" in filter_mode: auto_skus = sku_stats[sku_stats['รายละเอียดยอดที่ชำระแล้ว']>0]['SKU_Main'].tolist()
        elif "ผลาญงบ" in filter_mode: auto_skus = sku_stats[(sku_stats['Ads_Amount']>0) & (sku_stats['รายละเอียดยอดที่ชำระแล้ว']==0)]['SKU_Main'].tolist()
        elif "Master" in filter_mode: auto_skus = daily_skus
        else: auto_skus = sku_stats[(sku_stats['รายละเอียดยอดที่ชำระแล้ว']>0)|(sku_stats['Ads_Amount']>0)]['SKU_Main'].tolist()
        
        final_skus = [sku_map_rev[x] for x in st.session_state.selected_skus] if st.session_state.selected_skus else auto_skus
        df_view = df_view[df_view['SKU_Main'].isin(final_skus)]

        if df_view.empty: st.info(f"ไม่มีข้อมูลในเดือน {sel_month} {sel_year}")
        else:
            days_in_m = calendar.monthrange(sel_year, thai_months.index(sel_month)+1)[1]
            
            sales = df_view['รายละเอียดยอดที่ชำระแล้ว'].sum()
            ads = df_view['Ads_Amount'].sum()
            cost_ops = df_view['Total_Cost'].sum() - ads
            profit = sales - cost_ops - ads
            
            p_cost = (cost_ops/sales*100) if sales else 0
            p_ads = (ads/sales*100) if sales else 0
            p_prof = (profit/sales*100) if sales else 0

            st.markdown(f"""<div class="metric-container">
            <div class="custom-card border-blue"><div class="card-label">ยอดขายรวม</div><div class="card-value">{sales:,.0f}</div><div class="card-sub">100%</div></div>
            <div class="custom-card border-purple"><div class="card-label">ทุนสินค้า+ค่าใช้จ่าย</div><div class="card-value">{cost_ops:,.0f}</div><div class="card-sub" style="color:#e74c3c !important">{p_cost:,.1f}%</div></div>
            <div class="custom-card border-orange"><div class="card-label">ค่าโฆษณา</div><div class="card-value">{ads:,.0f}</div><div class="card-sub" style="color:#e74c3c !important">{p_ads:,.1f}%</div></div>
            <div class="custom-card border-green"><div class="card-label">กำไรสุทธิ</div><div class="card-value" style="color:{'#2ecc71' if profit>=0 else '#e74c3c'} !important;">{profit:,.0f}</div><div class="card-sub">{p_prof:,.1f}%</div></div>
            </div>""", unsafe_allow_html=True)
            
            all_days = range(1, days_in_m + 1)
            matrix = []
            for d in all_days:
                dd = df_view[df_view['Day'] == d]
                row = {'วันที่': str(d), 'รวม': dd['รายละเอียดยอดที่ชำระแล้ว'].sum(), 'กำไร': dd['Net_Profit'].sum()}
                for s in final_skus:
                    row[s] = dd[dd['SKU_Main']==s]['Net_Profit'].sum()
                matrix.append(row)
            
            df_mat = pd.DataFrame(matrix)
            def fmt(v): return f"{v:,.0f}" if v!=0 else "-"
            def fmt_p(v): return f"{v:,.1f}%" if v!=0 else "-"
            
            h = '<div class="table-wrapper"><table class="custom-table month-table"><thead><tr>'
            h += '<th class="col-fix-1" style="background:#2c3e50;color:white;">รวม</th>'
            h += '<th class="col-fix-2" style="background:#27ae60;color:white;">กำไร</th>'
            h += '<th class="col-fix-3">วันที่</th>'
            for s in final_skus: h += f'<th>{s}<br><span class="col-small">{sku_name_lookup.get(s,"")[:10]}..</span></th>'
            h += '</tr></thead><tbody>'
            for _, r in df_mat.iterrows():
                pc = "#2ecc71" if r['กำไร'] >= 0 else "#e74c3c"
                h += f'<tr><td class="col-fix-1" style="font-weight:bold;">{fmt(r["รวม"])}</td>'
                h += f'<td class="col-fix-2" style="font-weight:bold; color:{pc};">{fmt(r["กำไร"])}</td>'
                h += f'<td class="col-fix-3">{r["วันที่"]}</td>'
                for s in final_skus:
                    v = r.get(s, 0)
                    c = "#ddd" if v >= 0 else "#e74c3c"
                    if v==0: c="#555"
                    h += f'<td style="color:{c};">{fmt(v)}</td>'
                h += '</tr>'
            
            # Footer
            g_sales = df_view['รายละเอียดยอดที่ชำระแล้ว'].sum()
            g_profit = df_view['Net_Profit'].sum()
            g_ads = df_view['Ads_Amount'].sum()
            g_cost = df_view['Total_Cost'].sum() - g_ads
            
            def create_footer_row(row_cls, label, data_dict, val_type='num', dark_bg=False):
                bg_color = "#ffffff"
                if "row-cost" in row_cls: bg_color = "#e8f8f5"
                elif "row-sales" in row_cls: bg_color = "#d4efdf"
                elif "row-profit" in row_cls: bg_color = "#a9dfbf"
                elif "row-ads" in row_cls: bg_color = "#abebc6"
                elif "row-pct-profit" in row_cls: bg_color = "#e1bee7"
                elif "row-pct-ads" in row_cls: bg_color = "#884ea0"
                elif "row-pct-cost" in row_cls: bg_color = "#154360"

                grand_val = 0
                if label == "รวมทุนสินค้า": grand_val = g_cost
                elif label == "รวมยอดขาย": grand_val = g_sales
                elif label == "รวมกำไร": grand_val = g_profit
                elif label == "รวมค่าแอด": grand_val = g_ads
                elif label == "กำไร / ยอดขาย": grand_val = (g_profit/g_sales*100) if g_sales else 0
                elif label == "ค่าแอด / ยอดขาย": grand_val = (g_ads/g_sales*100) if g_sales else 0
                elif label == "ทุน/ยอดขาย": grand_val = (g_cost/g_sales*100) if g_sales else 0

                txt_val = fmt_p(grand_val) if val_type=='pct' else fmt_n(grand_val)
                grand_text_col = "#000000"
                if grand_val < 0: grand_text_col = "#c0392b"
                elif dark_bg: grand_text_col = "#ffffff"

                row_html = f'<tr class="{row_cls}"><td class="col-fix-1" style="background-color:{bg_color}; color:#000000;">{label}</td>'
                row_html += f'<td class="col-fix-2" style="background-color:{bg_color}; color:{grand_text_col};">{txt_val}</td>'
                row_html += f'<td class="col-fix-3" style="background-color:{bg_color};"></td>'

                for sku in final_skus:
                    val = 0
                    dd = df_view[df_view['SKU_Main']==sku]
                    if label == "รวมทุนสินค้า": val = dd['Total_Cost'].sum() - dd['Ads_Amount'].sum()
                    elif label == "รวมยอดขาย": val = dd['รายละเอียดยอดที่ชำระแล้ว'].sum()
                    elif label == "รวมกำไร": val = dd['Net_Profit'].sum()
                    elif label == "รวมค่าแอด": val = dd['Ads_Amount'].sum()
                    
                    # Percent Calcs
                    s = dd['รายละเอียดยอดที่ชำระแล้ว'].sum()
                    if label == "กำไร / ยอดขาย": val = (dd['Net_Profit'].sum()/s*100) if s else 0
                    elif label == "ค่าแอด / ยอดขาย": val = (dd['Ads_Amount'].sum()/s*100) if s else 0
                    elif label == "ทุน/ยอดขาย": val = ((dd['Total_Cost'].sum() - dd['Ads_Amount'].sum())/s*100) if s else 0

                    txt = fmt_p(val) if val_type=='pct' else fmt_n(val)
                    cell_text_col = "#000000"
                    if val < 0: cell_text_col = "#c0392b"
                    elif dark_bg: cell_text_col = "#ffffff"

                    row_html += f'<td style="background-color:{bg_color}; color:{cell_text_col};">{txt}</td>'
                row_html += '</tr>'
                return row_html
            
            # Generate Footer Rows
            h += create_footer_row("row-cost", "รวมทุนสินค้า", df_view, 'num')
            h += create_footer_row("row-sales", "รวมยอดขาย", df_view, 'num')
            h += create_footer_row("row-profit", "รวมกำไร", df_view, 'num')
            h += create_footer_row("row-ads", "รวมค่าแอด", df_view, 'num')
            h += create_footer_row("row-pct-profit", "กำไร / ยอดขาย", df_view, 'pct')
            h += create_footer_row("row-pct-ads", "ค่าแอด / ยอดขาย", df_view, 'pct', dark_bg=True)
            h += create_footer_row("row-pct-cost", "ทุน/ยอดขาย", df_view, 'pct', dark_bg=True)
            h += '</tbody></table></div>'
            st.markdown(h, unsafe_allow_html=True)

    # --- PAGE 2 ---
    elif selected_page == "📅 REPORT_DAILY":
        st.markdown('<div class="header-bar"><div class="header-title">สรุปการขายรายวัน (ตามช่วงเวลา)</div></div>', unsafe_allow_html=True)

        with st.container():
            c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
            with c1: sel_year_d = st.selectbox("เลือกปี", sorted(df_daily['Year'].unique(), reverse=True), key="d_y")
            with c2: start_d = st.date_input("เริ่มวันที่", datetime.now().replace(day=1), key="d_s")
            with c3: end_d = st.date_input("ถึงวันที่", datetime.now(), key="d_e")
            with c4: filter_mode_d = st.selectbox("เงื่อนไขสินค้า (Fast Filter)", ["📦 แสดงรายการที่มีการเคลื่อนไหว", "💰 เฉพาะรายการที่ขายได้", "💸 ผลาญงบ (มี Ads แต่ขายไม่ได้)", "📋 แสดง Master ทั้งหมด"], key="d_m")

            c1_d, c2_d, c3_d, c4_d, c5_d = st.columns([1.5, 3.5, 0.4, 0.4, 0.8])
            with c1_d: st.text_input("ค้นหา SKU / ชื่อสินค้า (Daily):", placeholder="...", key="search_d")
            with c2_d: st.multiselect("รายการที่เลือก (Choose options):", sku_options_list_global, key="selected_skus_d")
            with c3_d:
                st.markdown("<div style='margin-top: 29px;'></div>", unsafe_allow_html=True)
                st.button("➕", use_container_width=True, key="btn_add_d", on_click=cb_add_d)
            with c4_d:
                st.markdown("<div style='margin-top: 29px;'></div>", unsafe_allow_html=True)
                st.button("🧹", type="secondary", use_container_width=True, key="btn_clear_d", on_click=cb_clear_d)
            with c5_d:
                st.markdown("<div style='margin-top: 29px;'></div>", unsafe_allow_html=True)
                st.button("🚀 ประมวลผล", type="primary", use_container_width=True, key="btn_run_d")

        mask = (df_daily['Date'] >= pd.to_datetime(start_d).date()) & (df_daily['Date'] <= pd.to_datetime(end_d).date())
        df_range = df_daily[mask]

        df_grouped = df_range.groupby(['SKU_Main']).agg({
            'ชื่อสินค้า': 'last', 'จำนวนออเดอร์': 'sum', 'จำนวน': 'sum', 'รายละเอียดยอดที่ชำระแล้ว': 'sum',
            'CAL_COST': 'sum', 'BOX_COST': 'sum', 'DELIV_COST': 'sum', 'CAL_COD_COST': 'sum',
            'CAL_COM_ADMIN': 'sum', 'CAL_COM_TELESALE': 'sum', 'Ads_Amount': 'sum', 'Net_Profit': 'sum'
        }).reset_index()
        df_grouped['ชื่อสินค้า'] = df_grouped['SKU_Main'].map(sku_name_lookup).fillna("ไม่ระบุชื่อ")

        auto_skus_d = []
        if "เฉพาะรายการที่ขายได้" in filter_mode_d: auto_skus_d = df_grouped[df_grouped['รายละเอียดยอดที่ชำระแล้ว'] > 0]['SKU_Main'].tolist()
        elif "ผลาญงบ" in filter_mode_d: auto_skus_d = df_grouped[(df_grouped['Ads_Amount'] > 0) & (df_grouped['รายละเอียดยอดที่ชำระแล้ว'] == 0)]['SKU_Main'].tolist()
        elif "แสดง Master ทั้งหมด" in filter_mode_d: auto_skus_d = all_skus_global
        else: auto_skus_d = df_grouped[(df_grouped['รายละเอียดยอดที่ชำระแล้ว'] > 0) | (df_grouped['Ads_Amount'] > 0)]['SKU_Main'].tolist()

        selected_labels_d = st.session_state.selected_skus_d
        selected_skus_real_d = [sku_map_reverse_global[l] for l in selected_labels_d]
        final_skus_d = sorted(selected_skus_real_d) if selected_skus_real_d else sorted(auto_skus_d)

        df_final_d = df_grouped[df_grouped['SKU_Main'].isin(final_skus_d)].copy()

        if df_final_d.empty: st.warning("⚠️ ไม่พบข้อมูลตามเงื่อนไขในช่วงเวลานี้")
        else:
            sum_sales = df_final_d['รายละเอียดยอดที่ชำระแล้ว'].sum()
            sum_ads = df_final_d['Ads_Amount'].sum()
            sum_ops = df_final_d['BOX_COST'].sum() + df_final_d['DELIV_COST'].sum() + df_final_d['CAL_COD_COST'].sum() + df_final_d['CAL_COM_ADMIN'].sum() + df_final_d['CAL_COM_TELESALE'].sum()
            sum_cost_prod = df_final_d['CAL_COST'].sum()
            sum_total_cost_ops = sum_cost_prod + sum_ops
            sum_profit = df_final_d['Net_Profit'].sum() # No Fix Cost
            p_cost = (sum_total_cost_ops / sum_sales * 100) if sum_sales > 0 else 0
            p_ads = (sum_ads / sum_sales * 100) if sum_sales > 0 else 0
            p_prof = (sum_profit / sum_sales * 100) if sum_sales > 0 else 0

            st.markdown(f"""
            <div class="metric-container">
                <div class="custom-card border-blue"><div class="card-label">ยอดขายรวม</div><div class="card-value">{sum_sales:,.0f}</div><div class="card-sub txt-gray">100%</div></div>
                <div class="custom-card border-purple"><div class="card-label">ทุนสินค้า + ค่าใช้จ่าย</div><div class="card-value">{sum_total_cost_ops:,.0f}</div><div class="card-sub txt-red">{p_cost:,.1f}% ของยอดขาย</div></div>
                <div class="custom-card border-orange"><div class="card-label">ค่าโฆษณา</div><div class="card-value">{sum_ads:,.0f}</div><div class="card-sub txt-red">{p_ads:,.1f}% ของยอดขาย</div></div>
                <div class="custom-card border-green"><div class="card-label">กำไรสุทธิ</div><div class="card-value {'pos' if sum_profit>=0 else 'neg'}">{sum_profit:,.0f}</div><div class="card-sub {'txt-green' if p_prof>=0 else 'txt-red'}">{p_prof:,.1f}% ของยอดขาย</div></div>
            </div>""", unsafe_allow_html=True)

            df_final_d['กำไร/ขาดทุน'] = df_final_d['Net_Profit']
            df_final_d['ROAS'] = np.where(df_final_d['Ads_Amount']>0, df_final_d['รายละเอียดยอดที่ชำระแล้ว']/df_final_d['Ads_Amount'], 0)
            sls = df_final_d['รายละเอียดยอดที่ชำระแล้ว']
            df_final_d['% ทุนสินค้า'] = np.where(sls>0, (df_final_d['CAL_COST']/sls)*100, 0)
            oth = df_final_d['BOX_COST']+df_final_d['DELIV_COST']+df_final_d['CAL_COD_COST']+df_final_d['CAL_COM_ADMIN']+df_final_d['CAL_COM_TELESALE']
            df_final_d['% ทุนอื่น'] = np.where(sls>0, (oth/sls)*100, 0)
            df_final_d['% Ads'] = np.where(sls>0, (df_final_d['Ads_Amount']/sls)*100, 0)
            df_final_d['% กำไร'] = np.where(sls>0, (df_final_d['Net_Profit']/sls)*100, 0)
            df_final_d = df_final_d.sort_values('กำไร/ขาดทุน', ascending=False)

            def fmt(val, is_percent=False):
                if val == 0 or pd.isna(val): return "-"
                text = f"{val:,.2f}%" if is_percent else f"{val:,.2f}"
                return text

            st.markdown("##### 📋 รายละเอียดสินค้า")
            cols_cfg = [('SKU', 'SKU_Main', ''), ('ชื่อสินค้า', 'ชื่อสินค้า', ''), ('จำนวน', 'จำนวน', ''), ('ยอดขาย', 'รายละเอียดยอดที่ชำระแล้ว', ''), ('ต้นทุน', 'CAL_COST', ''), ('ค่ากล่อง', 'BOX_COST', ''), ('ค่าส่ง', 'DELIV_COST', ''), ('COD', 'CAL_COD_COST', ''), ('Admin', 'CAL_COM_ADMIN', ''), ('Tele', 'CAL_COM_TELESALE', ''), ('ค่า Ads', 'Ads_Amount', ''), ('กำไร', 'Net_Profit', ''), ('ROAS', 'ROAS', 'col-small'), ('%ทุน', '% ทุนสินค้า', 'col-small'), ('%อื่น', '% ทุนอื่น', 'col-small'), ('%Ads', '% Ads', 'col-small'), ('%กำไร', '% กำไร', 'col-small')]

            html = '<div class="table-wrapper"><table class="custom-table daily-table"><thead><tr>'
            for title, _, cls in cols_cfg: html += f'<th class="{cls}">{title}</th>'
            html += '</tr></thead><tbody>'

            def get_color(val): return "#c0392b" if val < 0 else "#1e3c72"

            for _, r in df_final_d.iterrows():
                html += '<tr>'
                html += f'<td style="font-weight:bold;color:#1e3c72;">{r["SKU_Main"]}</td>'
                html += f'<td style="text-align:left;font-size:11px;color:#1e3c72;">{r["ชื่อสินค้า"]}</td>'

                html += f'<td style="color:{get_color(r["จำนวน"])};">{fmt(r["จำนวน"])}</td>'
                html += f'<td style="color:{get_color(r["รายละเอียดยอดที่ชำระแล้ว"])};">{fmt(r["รายละเอียดยอดที่ชำระแล้ว"])}</td>'
                html += f'<td style="color:{get_color(r["CAL_COST"])};">{fmt(r["CAL_COST"])}</td>'
                html += f'<td style="color:{get_color(r["BOX_COST"])};">{fmt(r["BOX_COST"])}</td>'
                html += f'<td style="color:{get_color(r["DELIV_COST"])};">{fmt(r["DELIV_COST"])}</td>'
                html += f'<td style="color:{get_color(r["CAL_COD_COST"])};">{fmt(r["CAL_COD_COST"])}</td>'
                html += f'<td style="color:{get_color(r["CAL_COM_ADMIN"])};">{fmt(r["CAL_COM_ADMIN"])}</td>'
                html += f'<td style="color:{get_color(r["CAL_COM_TELESALE"])};">{fmt(r["CAL_COM_TELESALE"])}</td>'

                html += f'<td style="color:#e67e22;">{fmt(r["Ads_Amount"])}</td>'
                html += f'<td style="color:{get_color(r["Net_Profit"])};">{fmt(r["Net_Profit"])}</td>'

                html += f'<td class="col-small" style="color:#1e3c72;">{fmt(r["ROAS"])}</td>'
                html += f'<td class="col-small" style="color:#1e3c72;">{fmt(r["% ทุนสินค้า"],True)}</td>'
                html += f'<td class="col-small" style="color:#1e3c72;">{fmt(r["% ทุนอื่น"],True)}</td>'
                html += f'<td class="col-small" style="color:#1e3c72;">{fmt(r["% Ads"],True)}</td>'
                html += f'<td class="col-small" style="color:{get_color(r["% กำไร"])};">{fmt(r["% กำไร"],True)}</td>'
                html += '</tr>'

            html += '<tr class="footer-row"><td>TOTAL</td><td></td>'
            ts = df_final_d['รายละเอียดยอดที่ชำระแล้ว'].sum(); tp = df_final_d['Net_Profit'].sum()
            ta = df_final_d['Ads_Amount'].sum(); tc = df_final_d['CAL_COST'].sum()
            t_oth = df_final_d['BOX_COST'].sum() + df_final_d['DELIV_COST'].sum() + df_final_d['CAL_COD_COST'].sum() + df_final_d['CAL_COM_ADMIN'].sum() + df_final_d['CAL_COM_TELESALE'].sum()

            def get_tot_col(val): return "#c0392b" if val < 0 else "#ffffff"

            html += f'<td style="color:{get_tot_col(df_final_d["จำนวน"].sum())};">{fmt(df_final_d["จำนวน"].sum())}</td>'
            html += f'<td style="color:{get_tot_col(ts)};">{fmt(ts)}</td>'
            html += f'<td style="color:{get_tot_col(tc)};">{fmt(tc)}</td>'
            html += f'<td style="color:{get_tot_col(df_final_d["BOX_COST"].sum())};">{fmt(df_final_d["BOX_COST"].sum())}</td>'
            html += f'<td style="color:{get_tot_col(df_final_d["DELIV_COST"].sum())};">{fmt(df_final_d["DELIV_COST"].sum())}</td>'
            html += f'<td style="color:{get_tot_col(df_final_d["CAL_COD_COST"].sum())};">{fmt(df_final_d["CAL_COD_COST"].sum())}</td>'
            html += f'<td style="color:{get_tot_col(df_final_d["CAL_COM_ADMIN"].sum())};">{fmt(df_final_d["CAL_COM_ADMIN"].sum())}</td>'
            html += f'<td style="color:{get_tot_col(df_final_d["CAL_COM_TELESALE"].sum())};">{fmt(df_final_d["CAL_COM_TELESALE"].sum())}</td>'
            html += f'<td style="color:{get_tot_col(ta)};">{fmt(ta)}</td>'
            html += f'<td style="color:{get_tot_col(tp)};">{fmt(tp)}</td>'

            f_roas = ts/ta if ta>0 else 0
            f_pp = (tp/ts*100) if ts>0 else 0
            html += f'<td class="col-small" style="color:#ffffff;">{fmt(f_roas)}</td>'
            html += f'<td class="col-small" style="color:#ffffff;">{fmt((tc/ts*100) if ts>0 else 0,True)}</td>'
            html += f'<td class="col-small" style="color:#ffffff;">{fmt((t_oth/ts*100) if ts>0 else 0,True)}</td>'
            html += f'<td class="col-small" style="color:#ffffff;">{fmt((ta/ts*100) if ts>0 else 0,True)}</td>'
            html += f'<td class="col-small" style="color:{get_tot_col(f_pp)};">{fmt(f_pp,True)}</td></tr></tbody></table></div>'
            st.markdown(html, unsafe_allow_html=True)

    # --- PAGE 3 ---
    elif selected_page == "📈 PRODUCT GRAPH":
        st.markdown('<div class="header-bar"><div class="header-title"><i class="fas fa-chart-line"></i> กราฟแสดงแนวโน้มยอดขายรายสินค้า</div></div>', unsafe_allow_html=True)

        with st.container():
            c_g1, c_g2, c_g3 = st.columns([1, 1, 2])
            with c_g1: start_g = st.date_input("เริ่มวันที่", datetime.now().replace(day=1), key="g_s")
            with c_g2: end_g = st.date_input("ถึงวันที่", datetime.now(), key="g_e")
            with c_g3: filter_mode_g = st.selectbox("เงื่อนไขสินค้า (Fast Filter)",
                ["📦 แสดงรายการที่มีการเคลื่อนไหว", "💰 เฉพาะรายการที่ขายได้", "💸 ผลาญงบ (มี Ads แต่ขายไม่ได้)", "📋 แสดง Master ทั้งหมด"], key="g_m")

            # Layout Input Row 2: SKU Selector
            c1_g, c2_g, c3_g, c4_g, c5_g = st.columns([1.5, 3.5, 0.4, 0.4, 0.8])
            with c1_g: st.text_input("ค้นหา SKU / ชื่อสินค้า (Graph):", placeholder="...", key="search_g")
            with c2_g: st.multiselect("เลือกสินค้าที่ต้องการดูกราฟ:", sku_options_list_global, key="selected_skus_g")
            with c3_g:
                st.markdown("<div style='margin-top: 29px;'></div>", unsafe_allow_html=True)
                st.button("➕", use_container_width=True, key="btn_add_g", on_click=cb_add_g)
            with c4_g:
                st.markdown("<div style='margin-top: 29px;'></div>", unsafe_allow_html=True)
                st.button("🧹", type="secondary", use_container_width=True, key="btn_clear_g", on_click=cb_clear_g)
            with c5_g:
                st.markdown("<div style='margin-top: 29px;'></div>", unsafe_allow_html=True)
                st.button("🚀 สร้างกราฟ", type="primary", use_container_width=True, key="btn_run_g")

        mask_g_date = (df_daily['Date'] >= pd.to_datetime(start_g).date()) & (df_daily['Date'] <= pd.to_datetime(end_g).date())
        df_range_g = df_daily[mask_g_date]

        sku_stats_g = df_range_g.groupby('SKU_Main').agg({'รายละเอียดยอดที่ชำระแล้ว': 'sum', 'Ads_Amount': 'sum'}).reset_index()
        auto_skus_g = []

        if "เฉพาะรายการที่ขายได้" in filter_mode_g:
            auto_skus_g = sku_stats_g[sku_stats_g['รายละเอียดยอดที่ชำระแล้ว'] > 0]['SKU_Main'].tolist()
        elif "ผลาญงบ" in filter_mode_g:
            auto_skus_g = sku_stats_g[(sku_stats_g['Ads_Amount'] > 0) & (sku_stats_g['รายละเอียดยอดที่ชำระแล้ว'] == 0)]['SKU_Main'].tolist()
        elif "แสดง Master ทั้งหมด" in filter_mode_g:
            auto_skus_g = all_skus_global
        else: # แสดงรายการที่มีการเคลื่อนไหว
            auto_skus_g = sku_stats_g[(sku_stats_g['รายละเอียดยอดที่ชำระแล้ว'] > 0) | (sku_stats_g['Ads_Amount'] > 0)]['SKU_Main'].tolist()

        selected_labels_g = st.session_state.selected_skus_g
        real_selected_g = [sku_map_reverse_global[l] for l in selected_labels_g]

        final_skus_g = sorted(real_selected_g) if real_selected_g else sorted(auto_skus_g)

        if not final_skus_g:
            st.info("👈 ไม่พบข้อมูลตามเงื่อนไข หรือกรุณาเลือกสินค้า")
        else:
            df_graph = df_range_g[df_range_g['SKU_Main'].isin(final_skus_g)].copy()

            if df_graph.empty:
                st.warning("⚠️ ไม่พบข้อมูลการขายของสินค้าที่เลือกในช่วงเวลานี้")
            else:
                df_chart = df_graph.groupby(['Date', 'SKU_Main']).agg({
                    'รายละเอียดยอดที่ชำระแล้ว': 'sum',
                    'จำนวน': 'sum'
                }).reset_index()

                df_chart['Product_Name'] = df_chart['SKU_Main'].apply(lambda x: f"{x} : {sku_name_lookup.get(x, '')}")
                # Date to string for Altair safety
                df_chart['DateStr'] = df_chart['Date'].astype(str)

                st.markdown("##### 📈 แนวโน้มยอดขายรายวัน (Sales Trend)")
                chart_line = alt.Chart(df_chart).mark_line(point=True).encode(
                    x=alt.X('DateStr', title='วันที่'),
                    y=alt.Y('รายละเอียดยอดที่ชำระแล้ว', title='ยอดขาย (บาท)'),
                    color=alt.Color('Product_Name', title='สินค้า'),
                    tooltip=['DateStr', 'Product_Name', alt.Tooltip('รายละเอียดยอดที่ชำระแล้ว', format=',.0f'), 'จำนวน']
                ).interactive()
                st.altair_chart(chart_line, use_container_width=True)

                st.markdown("---")
                c_bar1, c_bar2 = st.columns(2)

                with c_bar1:
                    st.markdown("##### 📊 สรุปยอดขายรวมตามช่วงเวลา (Total Sales)")
                    df_bar_sum = df_chart.groupby('Product_Name')['รายละเอียดยอดที่ชำระแล้ว'].sum().reset_index()
                    chart_bar = alt.Chart(df_bar_sum).mark_bar().encode(
                        x=alt.X('Product_Name', title=None, axis=alt.Axis(labels=False)),
                        y=alt.Y('รายละเอียดยอดที่ชำระแล้ว', title='ยอดขายรวม (บาท)'),
                        color=alt.Color('Product_Name', legend=None),
                        tooltip=['Product_Name', alt.Tooltip('รายละเอียดยอดที่ชำระแล้ว', format=',.0f')]
                    )
                    st.altair_chart(chart_bar, use_container_width=True)

                with c_bar2:
                    st.markdown("##### 📦 สรุปจำนวนชิ้นที่ขายได้ (Total Units)")
                    df_qty_sum = df_chart.groupby('Product_Name')['จำนวน'].sum().reset_index()
                    chart_bar_qty = alt.Chart(df_qty_sum).mark_bar().encode(
                        x=alt.X('Product_Name', title=None, axis=alt.Axis(labels=False)),
                        y=alt.Y('จำนวน', title='จำนวน (ชิ้น)'),
                        color=alt.Color('Product_Name', legend=None),
                        tooltip=['Product_Name', alt.Tooltip('จำนวน', format=',.0f')]
                    )
                    st.altair_chart(chart_bar_qty, use_container_width=True)

    # --- PAGE 4 ---
    elif selected_page == "📈 YEARLY P&L":
        st.markdown('<div class="pnl-container">', unsafe_allow_html=True)
        st.markdown("""
        <div class="header-gradient-pnl">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h1 class="header-title-pnl">แดชบอร์ดกำไร-ขาดทุน (รายปี)</h1>
                    <p class="header-sub-pnl">ภาพรวมผลประกอบการรายปี</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        c_year, c_dummy = st.columns([1, 5])
        with c_year:
            sel_year_pnl = st.selectbox("เลือกปีงบประมาณ", sorted(df_daily['Year'].unique(), reverse=True), key="pnl_year")

        df_yr = df_daily[df_daily['Year'] == sel_year_pnl].copy()

        if df_yr.empty:
            st.warning("ไม่พบข้อมูลสำหรับปีที่เลือก")
        else:
            df_m = df_yr.groupby('Month_Num').agg({
                'รายละเอียดยอดที่ชำระแล้ว': 'sum',
                'CAL_COST': 'sum', 'BOX_COST': 'sum',
                'DELIV_COST': 'sum', 'CAL_COD_COST': 'sum', 'CAL_COM_ADMIN': 'sum', 'CAL_COM_TELESALE': 'sum', 'Ads_Amount': 'sum',
                'Net_Profit': 'sum'
            }).reset_index()

            df_template = pd.DataFrame({'Month_Num': range(1, 13)})
            df_merged = pd.merge(df_template, df_m, on='Month_Num', how='left').fillna(0)
            df_merged['Month_Thai'] = df_merged['Month_Num'].apply(lambda x: thai_months[x-1])
            
            # Calculate Aggregates
            df_merged['COGS_Total'] = df_merged['CAL_COST'] + df_merged['BOX_COST']
            df_merged['Selling_Exp'] = df_merged['DELIV_COST'] + df_merged['CAL_COD_COST'] + df_merged['CAL_COM_ADMIN'] + df_merged['CAL_COM_TELESALE'] + df_merged['Ads_Amount']
            df_merged['Total_Exp'] = df_merged['COGS_Total'] + df_merged['Selling_Exp'] # No Fix Cost
            df_merged['Net_Profit_Final'] = df_merged['รายละเอียดยอดที่ชำระแล้ว'] - df_merged['Total_Exp']

            total_sales = df_merged['รายละเอียดยอดที่ชำระแล้ว'].sum()
            total_exp = df_merged['Total_Exp'].sum()
            total_profit = df_merged['Net_Profit_Final'].sum()

            pct_net_income = (total_sales / total_sales * 100) if total_sales else 0
            pct_exp = (total_exp / total_sales * 100) if total_sales else 0
            net_margin = (total_profit / total_sales * 100) if total_sales else 0

            def fmt(v): return f"{v:,.0f}"
            def fmt_p(v): return f"{v:,.2f}%"

            kpi_html = f"""
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 25px;">
                <div class="kpi-card-pnl b-blue">
                    <div class="kpi-label-pnl">ยอดขายรวม</div>
                    <div class="kpi-value-pnl">{fmt(total_sales)}</div>
                    <div class="kpi-sub-pnl">บาท</div>
                </div>
                <div class="kpi-card-pnl b-teal">
                    <div class="kpi-label-pnl">รายได้สุทธิ</div>
                    <div class="kpi-value-pnl">{fmt(total_sales)}</div>
                    <div class="kpi-sub-pnl t-teal">คิดเป็น {fmt_p(pct_net_income)} ของยอดขาย</div>
                </div>
                <div class="kpi-card-pnl b-red">
                    <div class="kpi-label-pnl">ค่าใช้จ่ายรวม</div>
                    <div class="kpi-value-pnl">{fmt(total_exp)}</div>
                    <div class="kpi-sub-pnl t-red">คิดเป็น {fmt_p(pct_exp)} ของรายได้</div>
                </div>
                <div class="kpi-card-pnl b-indigo">
                    <div class="kpi-label-pnl">กำไรสุทธิ</div>
                    <div class="kpi-value-pnl">{fmt(total_profit)}</div>
                    <div class="kpi-sub-pnl t-indigo">Margin: {fmt_p(net_margin)}</div>
                </div>
            </div>
            """
            st.markdown(kpi_html, unsafe_allow_html=True)

            c_chart1, c_chart2 = st.columns(2)

            with c_chart1:
                st.markdown('<div class="chart-box"><div class="chart-header"><span class="pill" style="background:#3b82f6"></span> ภาพรวมยอดขาย & กำไรสุทธิ (รายปี)</div>', unsafe_allow_html=True)
                base = alt.Chart(df_merged).encode(x=alt.X('Month_Thai', sort=thai_months, title=None))
                # Bar: Sales
                bar1 = base.mark_bar(color='#3b82f6', opacity=0.8, cornerRadiusEnd=4).encode(
                    y=alt.Y('รายละเอียดยอดที่ชำระแล้ว', title='บาท'),
                    tooltip=['Month_Thai', alt.Tooltip('รายละเอียดยอดที่ชำระแล้ว', title='ยอดขาย', format=',.0f')]
                )
                # Line: Net Profit
                line1 = base.mark_line(color='#10b981', strokeWidth=3, point=True).encode(
                    y=alt.Y('Net_Profit_Final', title='กำไรสุทธิ'),
                    tooltip=['Month_Thai', alt.Tooltip('Net_Profit_Final', title='กำไรสุทธิ', format=',.0f')]
                )
                st.altair_chart((bar1 + line1).interactive(), use_container_width=True)
                st.markdown('</div>', unsafe_allow_html=True)

            with c_chart2:
                st.markdown('<div class="chart-box"><div class="chart-header"><span class="pill" style="background:#f87171"></span> สัดส่วนค่าใช้จ่าย (ทั้งปี)</div>', unsafe_allow_html=True)
                # --- FULL BREAKDOWN PIE CHART ---
                exp_data = pd.DataFrame([
                    {'Type': 'ต้นทุนสินค้า', 'Value': df_merged['CAL_COST'].sum()},
                    {'Type': 'ค่ากล่อง', 'Value': df_merged['BOX_COST'].sum()},
                    {'Type': 'ค่าส่ง', 'Value': df_merged['DELIV_COST'].sum()},
                    {'Type': 'ค่า COD', 'Value': df_merged['CAL_COD_COST'].sum()},
                    {'Type': 'ค่าคอม Admin', 'Value': df_merged['CAL_COM_ADMIN'].sum()},
                    {'Type': 'ค่าคอม Tele', 'Value': df_merged['CAL_COM_TELESALE'].sum()},
                    {'Type': 'ค่า Ads', 'Value': df_merged['Ads_Amount'].sum()}
                ])
                # Filter out zero values to avoid clutter
                exp_data = exp_data[exp_data['Value'] > 0]

                if not exp_data.empty:
                    donut = alt.Chart(exp_data).mark_arc(innerRadius=70).encode(
                        theta=alt.Theta("Value", stack=True),
                        color=alt.Color("Type", scale=alt.Scale(scheme='tableau10'), legend=alt.Legend(orient='right')),
                        tooltip=["Type", alt.Tooltip("Value", format=",.0f")]
                    )
                    st.altair_chart(donut, use_container_width=True)
                else:
                    st.info("ไม่มีข้อมูลค่าใช้จ่าย")
                st.markdown('</div>', unsafe_allow_html=True)

            st.markdown('<div class="chart-box"><div class="chart-header">งบกำไรขาดทุน (Profit & Loss Statement)</div>', unsafe_allow_html=True)

            # --- CALC DETAILED BREAKDOWN ---
            t_sales = df_merged['รายละเอียดยอดที่ชำระแล้ว'].sum()

            t_prod_cost = df_merged['CAL_COST'].sum()
            t_box_cost = df_merged['BOX_COST'].sum()

            # Calculate Gross Profit after Product + Box
            t_gross = t_sales - t_prod_cost - t_box_cost

            t_ship = df_merged['DELIV_COST'].sum()
            t_cod = df_merged['CAL_COD_COST'].sum()
            t_admin = df_merged['CAL_COM_ADMIN'].sum()
            t_tele = df_merged['CAL_COM_TELESALE'].sum()
            t_ads = df_merged['Ads_Amount'].sum()
            # No Fix

            t_net = t_gross - t_ship - t_cod - t_admin - t_tele - t_ads

            def row_html(label, val, is_head=False, is_neg=False, is_sub=False):
                cls = "pnl-row-head" if is_head else ("sub-item" if is_sub else "")
                val_cls = "neg" if val < 0 else ""
                return f'<tr class="{cls}"><td>{label}</td><td class="num-cell {val_cls}">{fmt(val)}</td></tr>'

            table_html = f"""
            <table class="pnl-table">
                <thead><tr><th>รายการ (Accounts)</th><th style="text-align:right">จำนวนเงิน (THB)</th></tr></thead>
                <tbody>
                    {row_html("รายได้จากการขาย (Sales Revenue)", t_sales, True)}
                    {row_html("หัก ต้นทุนสินค้า (Product Cost)", -t_prod_cost)}
                    {row_html("หัก ค่ากล่อง (Box Cost)", -t_box_cost)}
                    {row_html("กำไรขั้นต้น (Gross Profit)", t_gross, True, t_gross<0)}
                    {row_html("หัก ค่าส่ง (Shipping)", -t_ship, is_sub=True)}
                    {row_html("หัก ค่า COD", -t_cod, is_sub=True)}
                    {row_html("หัก ค่าคอม Admin", -t_admin, is_sub=True)}
                    {row_html("หัก ค่าคอม Telesale", -t_tele, is_sub=True)}
                    {row_html("หัก ค่า ADS", -t_ads, is_sub=True)}
                    {row_html("กำไร(ขาดทุน) สุทธิ (Net Profit)", t_net, True, t_net<0)}
                </tbody>
            </table>
            """
            st.markdown(table_html, unsafe_allow_html=True)
            st.markdown('</div></div>', unsafe_allow_html=True)

    # --- PAGE 5 ---
    elif selected_page == "📅 MONTHLY P&L":
        st.markdown('<div class="pnl-container">', unsafe_allow_html=True)
        st.markdown("""
        <div class="header-gradient-pnl">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <h1 class="header-title-pnl">แดชบอร์ดกำไร-ขาดทุน (รายเดือน)</h1>
                    <p class="header-sub-pnl">เจาะลึกรายละเอียดรายเดือน</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        c_y, c_m, c_d = st.columns([1, 1, 4])
        with c_y: sel_y_m = st.selectbox("เลือกปี", sorted(df_daily['Year'].unique(), reverse=True), key="pm_y")
        with c_m: sel_m_m = st.selectbox("เลือกเดือน", thai_months, index=datetime.now().month-1, key="pm_m")

        df_m_data = df_daily[(df_daily['Year'] == sel_y_m) & (df_daily['Month_Thai'] == sel_m_m)].copy()

        days_in_m = calendar.monthrange(sel_y_m, thai_months.index(sel_m_m)+1)[1]
        df_full_days = pd.DataFrame({'Day': range(1, days_in_m + 1)})

        if df_m_data.empty:
            st.warning(f"ไม่พบข้อมูลการขายสำหรับเดือน {sel_m_m} {sel_y_m}")
            df_d_agg_raw = pd.DataFrame(columns=['Day', 'รายละเอียดยอดที่ชำระแล้ว', 'Ads_Amount', 'CAL_COST', 'BOX_COST', 'DELIV_COST', 'CAL_COD_COST', 'CAL_COM_ADMIN', 'CAL_COM_TELESALE'])
        else:
            df_d_agg_raw = df_m_data.groupby('Day').agg({
                'รายละเอียดยอดที่ชำระแล้ว': 'sum',
                'Ads_Amount': 'sum',
                'CAL_COST': 'sum', 'BOX_COST': 'sum',
                'DELIV_COST': 'sum', 'CAL_COD_COST': 'sum', 'CAL_COM_ADMIN': 'sum', 'CAL_COM_TELESALE': 'sum'
            }).reset_index()

        df_d_agg = pd.merge(df_full_days, df_d_agg_raw, on='Day', how='left').fillna(0)

        df_d_agg['Daily_Total_Exp'] = df_d_agg['CAL_COST'] + df_d_agg['BOX_COST'] + \
                                      df_d_agg['DELIV_COST'] + df_d_agg['CAL_COD_COST'] + \
                                      df_d_agg['CAL_COM_ADMIN'] + df_d_agg['CAL_COM_TELESALE'] + \
                                      df_d_agg['Ads_Amount'] # No Fix

        df_d_agg['Daily_Net_Profit'] = df_d_agg['รายละเอียดยอดที่ชำระแล้ว'] - df_d_agg['Daily_Total_Exp']

        m_sales = df_d_agg['รายละเอียดยอดที่ชำระแล้ว'].sum()
        m_total_exp = df_d_agg['Daily_Total_Exp'].sum()
        m_net_profit = df_d_agg['Daily_Net_Profit'].sum()

        pct_net = (m_net_profit / m_sales * 100) if m_sales else 0
        pct_exp_ratio = (m_total_exp / m_sales * 100) if m_sales else 0

        def fmt(v): return f"{v:,.0f}"
        def fmt_p(v): return f"{v:,.2f}%"

        kpi_html_m = f"""
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 25px;">
            <div class="kpi-card-pnl b-blue">
                <div class="kpi-label-pnl">ยอดขาย ({sel_m_m})</div>
                <div class="kpi-value-pnl">{fmt(m_sales)}</div>
                <div class="kpi-sub-pnl">บาท</div>
            </div>
            <div class="kpi-card-pnl b-teal">
                <div class="kpi-label-pnl">รายได้สุทธิ</div>
                <div class="kpi-value-pnl">{fmt(m_sales)}</div>
                <div class="kpi-sub-pnl t-teal">100%</div>
            </div>
            <div class="kpi-card-pnl b-red">
                <div class="kpi-label-pnl">ค่าใช้จ่ายรวม (No FixCost)</div>
                <div class="kpi-value-pnl">{fmt(m_total_exp)}</div>
                <div class="kpi-sub-pnl t-red">คิดเป็น {fmt_p(pct_exp_ratio)} ของยอดขาย</div>
            </div>
            <div class="kpi-card-pnl b-indigo">
                <div class="kpi-label-pnl">กำไรสุทธิ</div>
                <div class="kpi-value-pnl">{fmt(m_net_profit)}</div>
                <div class="kpi-sub-pnl t-indigo">Margin: {fmt_p(pct_net)}</div>
            </div>
        </div>
        """
        st.markdown(kpi_html_m, unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown('<div class="chart-box"><div class="chart-header"><span class="pill" style="background:#3b82f6"></span> แนวโน้มรายวัน (ยอดขาย vs ค่าใช้จ่าย)</div>', unsafe_allow_html=True)
            base_d = alt.Chart(df_d_agg).encode(x=alt.X('Day:O', title='วันที่'))
            bar_d = base_d.mark_bar(color='#3b82f6', opacity=0.7).encode(y=alt.Y('รายละเอียดยอดที่ชำระแล้ว', title='บาท'), tooltip=['Day', 'รายละเอียดยอดที่ชำระแล้ว'])
            line_d = base_d.mark_line(color='#ef4444').encode(y='Daily_Total_Exp', tooltip=['Day', 'Daily_Total_Exp'])
            st.altair_chart((bar_d + line_d).interactive(), use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with c2:
            st.markdown('<div class="chart-box"><div class="chart-header"><span class="pill" style="background:#f87171"></span> สัดส่วนค่าใช้จ่าย (เดือนนี้)</div>', unsafe_allow_html=True)
            # --- FULL BREAKDOWN PIE CHART (MONTHLY) ---
            m_prod = df_d_agg['CAL_COST'].sum()
            m_box = df_d_agg['BOX_COST'].sum()
            m_ship = df_d_agg['DELIV_COST'].sum()
            m_cod = df_d_agg['CAL_COD_COST'].sum()
            m_admin = df_d_agg['CAL_COM_ADMIN'].sum()
            m_tele = df_d_agg['CAL_COM_TELESALE'].sum()
            m_ads = df_d_agg['Ads_Amount'].sum()

            pie_data = pd.DataFrame([
                {'Type': 'ต้นทุนสินค้า', 'Value': m_prod},
                {'Type': 'ค่ากล่อง', 'Value': m_box},
                {'Type': 'ค่าส่ง', 'Value': m_ship},
                {'Type': 'ค่า COD', 'Value': m_cod},
                {'Type': 'ค่าคอม Admin', 'Value': m_admin},
                {'Type': 'ค่าคอม Tele', 'Value': m_tele},
                {'Type': 'ค่า Ads', 'Value': m_ads}
            ])
            pie_data = pie_data[pie_data['Value'] > 0]

            if not pie_data.empty:
                donut_m = alt.Chart(pie_data).mark_arc(innerRadius=80).encode(
                    theta=alt.Theta("Value", stack=True),
                    color=alt.Color("Type", scale=alt.Scale(scheme='tableau10'), legend=alt.Legend(orient='right')),
                    tooltip=["Type", alt.Tooltip("Value", format=",.0f")]
                )
                st.altair_chart(donut_m, use_container_width=True)
            else:
                st.info("ไม่มีข้อมูลค่าใช้จ่าย")
            st.markdown('</div>', unsafe_allow_html=True)

        c3, c4 = st.columns(2)
        with c3:
            st.markdown('<div class="chart-box"><div class="chart-header"><span class="pill" style="background:#14b8a6"></span> กำไรสุทธิรายวัน</div>', unsafe_allow_html=True)
            chart_profit_d = alt.Chart(df_d_agg).mark_line(point=True, color='#14b8a6').encode(
                x=alt.X('Day:O', title='วันที่'),
                y=alt.Y('Daily_Net_Profit', title='บาท'),
                tooltip=['Day', alt.Tooltip('Daily_Net_Profit', format=',.0f')]
            ).properties(height=400).interactive()
            st.altair_chart(chart_profit_d, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with c4:
            st.markdown('<div class="chart-box"><div class="chart-header"><span class="pill" style="background:#6366f1"></span> สินค้าขายดีประจำเดือน (Top 12)</div>', unsafe_allow_html=True)
            if not df_m_data.empty:
                top_sku_m = df_m_data.groupby('SKU_Main')['รายละเอียดยอดที่ชำระแล้ว'].sum().nlargest(12).reset_index()
                # MAP NAME HERE AS WELL
                top_sku_m['Display_Name'] = top_sku_m['SKU_Main'].apply(lambda x: f"{x} : {sku_name_lookup.get(x, 'ไม่ระบุชื่อ')}")

                chart_sku_m = alt.Chart(top_sku_m).mark_bar(cornerRadiusEnd=4).encode(
                    x=alt.X('รายละเอียดยอดที่ชำระแล้ว', title='ยอดขาย'),
                    y=alt.Y('Display_Name', sort='-x', title='สินค้า'),
                    color=alt.Color('Display_Name', legend=None, scale=alt.Scale(scheme='tableau10')),
                    tooltip=['Display_Name', alt.Tooltip('รายละเอียดยอดที่ชำระแล้ว', format=',.0f')]
                ).properties(height=400)
                st.altair_chart(chart_sku_m, use_container_width=True)
            else:
                st.info("ไม่มีข้อมูลสินค้าขายดี")
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="chart-box"><div class="chart-header">งบกำไรขาดทุน (Monthly Statement)</div>', unsafe_allow_html=True)

        # --- MONTHLY BREAKDOWN ---
        m_sales = df_d_agg['รายละเอียดยอดที่ชำระแล้ว'].sum()

        m_prod_cost = df_d_agg['CAL_COST'].sum()
        m_box_cost = df_d_agg['BOX_COST'].sum()

        m_gross = m_sales - m_prod_cost - m_box_cost

        m_ship = df_d_agg['DELIV_COST'].sum()
        m_cod = df_d_agg['CAL_COD_COST'].sum()
        m_admin = df_d_agg['CAL_COM_ADMIN'].sum()
        m_tele = df_d_agg['CAL_COM_TELESALE'].sum()
        m_ads = df_d_agg['Ads_Amount'].sum()
        # No Fix

        m_net = m_gross - m_ship - m_cod - m_admin - m_tele - m_ads

        def row_html(label, val, is_head=False, is_neg=False, is_sub=False):
            cls = "pnl-row-head" if is_head else ("sub-item" if is_sub else "")
            val_cls = "neg" if val < 0 else ""
            return f'<tr class="{cls}"><td>{label}</td><td class="num-cell {val_cls}">{fmt(val)}</td></tr>'

        table_html_m = f"""
        <table class="pnl-table">
            <thead><tr><th>รายการ (Accounts)</th><th style="text-align:right">จำนวนเงิน (THB)</th></tr></thead>
            <tbody>
                {row_html("รายได้จากการขาย (Sales)", m_sales, True)}
                {row_html("หัก ต้นทุนสินค้า (Product Cost)", -m_prod_cost)}
                {row_html("หัก ค่ากล่อง (Box Cost)", -m_box_cost)}
                {row_html("กำไรขั้นต้น (Gross Profit)", m_gross, True, m_gross<0)}
                {row_html("หัก ค่าส่ง (Shipping)", -m_ship, is_sub=True)}
                {row_html("หัก ค่า COD", -m_cod, is_sub=True)}
                {row_html("หัก ค่าคอม Admin", -m_admin, is_sub=True)}
                {row_html("หัก ค่าคอม Telesale", -m_tele, is_sub=True)}
                {row_html("หัก ค่า ADS", -m_ads, is_sub=True)}
                {row_html("กำไร(ขาดทุน) สุทธิ (Net Profit)", m_net, True, m_net<0)}
            </tbody>
        </table>
        """
        st.markdown(table_html_m, unsafe_allow_html=True)
        st.markdown('</div></div>', unsafe_allow_html=True)

    # --- PAGE 6 ---
    elif selected_page == "💰 COMMISSION":
        st.markdown('<div class="header-bar"><div class="header-title"><i class="fas fa-coins"></i> สรุปค่าคอมมิชชั่น (Admin & Telesale)</div></div>', unsafe_allow_html=True)

        with st.container():
            # Layout Filters
            c_c1, c_c2, c_c3 = st.columns([1, 1, 3])
            with c_c1: sel_year_c = st.selectbox("เลือกปี", sorted(df_daily['Year'].unique(), reverse=True), key="c_y")
            with c_c2: sel_month_c = st.selectbox("เลือกเดือน", thai_months, index=datetime.now().month-1, key="c_m")

        # --- Part 1: Monthly Detail ---
        st.markdown(f"### 📅 ประจำเดือน: {sel_month_c} {sel_year_c}")

        # Filter Data for Month
        df_comm = df_daily[(df_daily['Year'] == sel_year_c) & (df_daily['Month_Thai'] == sel_month_c)].copy()

        # 1. Prepare Full Month Days Range (Ensure graph shows 1-30/31)
        month_idx = thai_months.index(sel_month_c) + 1
        days_in_m = calendar.monthrange(sel_year_c, month_idx)[1]
        df_full_days = pd.DataFrame({'Day': range(1, days_in_m + 1)})

        if df_comm.empty:
            st.warning(f"⚠️ ไม่พบข้อมูลสำหรับเดือน {sel_month_c} {sel_year_c}")
            # Create empty chart data for visual consistency if needed, or just stop
            df_merged_c = df_full_days.copy()
            df_merged_c['CAL_COM_ADMIN'] = 0
            df_merged_c['CAL_COM_TELESALE'] = 0
            total_admin = 0
            total_tele = 0
            total_all = 0
        else:
            # Calculate Totals
            total_admin = df_comm['CAL_COM_ADMIN'].sum()
            total_tele = df_comm['CAL_COM_TELESALE'].sum()
            total_all = total_admin + total_tele

            # Metric Cards
            st.markdown(f"""
            <div class="metric-container">
                <div class="custom-card border-blue"><div class="card-label">ค่าคอมรวมทั้งหมด</div><div class="card-value">{total_all:,.0f}</div><div class="card-sub txt-gray">บาท</div></div>
                <div class="custom-card border-purple"><div class="card-label">Admin Commission</div><div class="card-value">{total_admin:,.0f}</div><div class="card-sub txt-gray">{(total_admin/total_all*100) if total_all else 0:.1f}% ของทั้งหมด</div></div>
                <div class="custom-card border-orange"><div class="card-label">Telesale Commission</div><div class="card-value">{total_tele:,.0f}</div><div class="card-sub txt-gray">{(total_tele/total_all*100) if total_all else 0:.1f}% ของทั้งหมด</div></div>
            </div>""", unsafe_allow_html=True)

            c_chart, c_table = st.columns([2, 1])

            with c_chart:
                st.markdown("##### 📈 แนวโน้มค่าคอมรายวัน (Daily Trend)")

                # 2. Aggregate Actual Data
                df_chart_c = df_comm.groupby('Day').agg({
                    'CAL_COM_ADMIN': 'sum',
                    'CAL_COM_TELESALE': 'sum'
                }).reset_index()

                # 3. Merge with Full Days (Fill NaN with 0)
                df_merged_c = pd.merge(df_full_days, df_chart_c, on='Day', how='left').fillna(0)

                # 4. Melt for Layered Chart
                df_melt = df_merged_c.melt(id_vars=['Day'], value_vars=['CAL_COM_ADMIN', 'CAL_COM_TELESALE'], var_name='Role', value_name='Commission')
                df_melt['Role'] = df_melt['Role'].map({'CAL_COM_ADMIN': 'Admin', 'CAL_COM_TELESALE': 'Telesale'})

                chart_comm = alt.Chart(df_melt).mark_line(point=True).encode(
                    x=alt.X('Day:O', title='วันที่'),
                    y=alt.Y('Commission', title='ค่าคอม (บาท)'),
                    color=alt.Color('Role', scale=alt.Scale(domain=['Admin', 'Telesale'], range=['#9b59b6', '#e67e22'])),
                    tooltip=['Day', 'Role', alt.Tooltip('Commission', format=',.0f')]
                ).interactive()
                st.altair_chart(chart_comm, use_container_width=True)

            with c_table:
                st.markdown("##### 📋 สรุปตามทีม (Team Summary)")
                # Create Summary Table
                comm_data = [
                    {'กลุ่มพนักงาน (Team)': 'Admin', 'ค่าคอมรวม (บาท)': total_admin},
                    {'กลุ่มพนักงาน (Team)': 'Telesale', 'ค่าคอมรวม (บาท)': total_tele},
                    {'กลุ่มพนักงาน (Team)': 'รวมทั้งหมด', 'ค่าคอมรวม (บาท)': total_all}
                ]
                df_table_c = pd.DataFrame(comm_data)

                # Formatter
                st.dataframe(
                    df_table_c.style.format({'ค่าคอมรวม (บาท)': '{:,.2f}'}),
                    use_container_width=True,
                    hide_index=True
                )

        # --- Part 2: Yearly Overview (Full 12 Months) ---
        st.markdown("---")
        st.markdown(f"### 📅 ภาพรวมทั้งปี: {sel_year_c}")

        # 1. Create Template with all 12 months
        df_template_months = pd.DataFrame({
            'Month_Num': range(1, 13),
            'Month_Thai': thai_months
        })

        df_year_comm = df_daily[df_daily['Year'] == sel_year_c].copy()

        if not df_year_comm.empty:
            # 2. Aggregate Actual Data
            df_year_agg = df_year_comm.groupby(['Month_Num']).agg({
                'CAL_COM_ADMIN': 'sum',
                'CAL_COM_TELESALE': 'sum'
            }).reset_index()
        else:
            # If no data at all for that year, create dummy zero data
            df_year_agg = pd.DataFrame(columns=['Month_Num', 'CAL_COM_ADMIN', 'CAL_COM_TELESALE'])

        # 3. Merge Template with Actual Data (Left Join)
        # Note: We drop 'Month_Thai' from right df (if exists) or just merge on Num
        df_final_chart = pd.merge(df_template_months, df_year_agg, on='Month_Num', how='left').fillna(0)

        # 4. Melt
        df_year_melt = df_final_chart.melt(id_vars=['Month_Num', 'Month_Thai'],
                                        value_vars=['CAL_COM_ADMIN', 'CAL_COM_TELESALE'],
                                        var_name='Role', value_name='Commission')
        df_year_melt['Role'] = df_year_melt['Role'].map({'CAL_COM_ADMIN': 'Admin', 'CAL_COM_TELESALE': 'Telesale'})

        # 5. Chart
        chart_year = alt.Chart(df_year_melt).mark_bar().encode(
            x=alt.X('Month_Thai', sort=thai_months, title='เดือน'),
            y=alt.Y('Commission', title='ค่าคอม (บาท)'),
            color=alt.Color('Role', scale=alt.Scale(domain=['Admin', 'Telesale'], range=['#9b59b6', '#e67e22'])),
            tooltip=['Month_Thai', 'Role', alt.Tooltip('Commission', format=',.0f')]
        ).properties(height=350).interactive()

        st.altair_chart(chart_year, use_container_width=True)

except Exception as e:
    st.error(f"เกิดข้อผิดพลาดร้ายแรง: {e}")