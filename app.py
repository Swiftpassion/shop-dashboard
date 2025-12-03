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
from datetime import datetime

# ==========================================
# 1. CONFIG & CSS (DARK MODE & UI SETUP)
# ==========================================
st.set_page_config(page_title="Shop Analytics Dashboard", layout="wide", page_icon="📊")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;600;700&family=Prompt:wght@300;400;500;600&display=swap');
    
    /* FORCE DARK MODE */
    .stApp { background-color: #0e1117 !important; color: #ffffff !important; }
    
    html, body, [class*="css"] { font-family: 'Sarabun', sans-serif; }
    .block-container { padding-top: 2rem !important; }
    
    /* Header */
    .header-bar {
        background: linear-gradient(90deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
        padding: 15px 20px; border-radius: 10px; margin-bottom: 20px;
        color: white; display:flex; align-items:center; box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        border: 1px solid #333;
    }
    .header-title { font-size: 22px; font-weight: 700; margin: 0; color: #4facfe !important; }
    
    /* Navigation Group */
    div[role="radiogroup"] {
        background-color: #1c1c1c; padding: 10px; border-radius: 10px;
        border: 1px solid #333; display: flex; justify-content: center; margin-bottom: 20px;
    }
    
    /* Cards */
    .metric-container { display: flex; gap: 15px; margin-bottom: 20px; flex-wrap: wrap; }
    .custom-card {
        background: #1c1c1c; border-radius: 10px; padding: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.5); flex: 1; min-width: 180px;
        border-left: 5px solid #555; border: 1px solid #333;
    }
    .card-label { color: #aaa; font-size: 13px; font-weight: 600; }
    .card-value { color: #fff; font-size: 24px; font-weight: 700; }
    .card-sub { font-size: 12px; margin-top: 5px; color: #888; }
    
    .border-blue { border-left-color: #3498db; }
    .border-green { border-left-color: #27ae60; }
    .border-red { border-left-color: #e74c3c; }
    .border-purple { border-left-color: #9b59b6; }
    .border-orange { border-left-color: #e67e22; }

    /* Inputs */
    .stTextInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #262730 !important; color: white !important; border-color: #444 !important;
    }
    .stDateInput input { color: white !important; }
    div[role="listbox"] li { background-color: #262730 !important; color: white !important; }

    /* Tables (Dark) */
    .table-wrapper {
        overflow: auto; width: 100%; max-height: 800px;
        margin-top: 10px; background: #1c1c1c;
        border-radius: 8px; border: 1px solid #333; padding-bottom: 10px;
    }
    .custom-table {
        width: 100%; min-width: 1000px; border-collapse: separate; border-spacing: 0;
        font-family: 'Sarabun', sans-serif; font-size: 11px; color: #ddd;
    }
    .custom-table th, .custom-table td {
        padding: 4px 6px; line-height: 1.2; text-align: center;
        border-bottom: 1px solid #333; border-right: 1px solid #333; white-space: nowrap;
    }
    .custom-table thead th {
        position: sticky; top: 0; z-index: 100;
        background-color: #2c3e50; color: #4facfe; font-weight: 700;
        border-bottom: 2px solid #555;
    }
    .custom-table tbody tr:nth-child(even) td { background-color: #262626; }
    .custom-table tbody tr:nth-child(odd) td { background-color: #1c1c1c; }
    .custom-table tbody tr:hover td { background-color: #333; }
    
    .col-small { font-size: 10px; color: #aaa; }
    .footer-row td { background-color: #333 !important; font-weight: bold; color: #fff !important; border-top: 2px solid #f1c40f; }
</style>""", unsafe_allow_html=True)

# ==========================================
# 2. SETTINGS
# ==========================================
FOLDER_ID_DATA = "1ciI_X2m8pVcsjRsPuUf5sg--6uPSPPDp"
FOLDER_ID_ADS = "1ZE76TXNA_vNeXjhAZfLgBQQGIV0GY7w8"
SHEET_MASTER_URL = "https://docs.google.com/spreadsheets/d/1Q3akHm1GKkDI2eilGfujsd9pO7aOjJvyYJNuXd98lzo/edit"

# ==========================================
# 3. GOOGLE DRIVE CONNECTION (BACKEND)
# ==========================================
@st.cache_resource
def get_drive_service():
    if "gcp_service_account" not in st.secrets:
        st.error("ไม่พบกุญแจ (Secrets) กรุณาตั้งค่าใน Streamlit Cloud")
        st.stop()
    creds_dict = dict(st.secrets["gcp_service_account"])
    scopes = ['https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/spreadsheets']
    return service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)

@st.cache_data(ttl=600)
def load_and_process_data():
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

    # Load Data
    files_data = get_files(FOLDER_ID_DATA)
    df_list = []
    for f in files_data:
        df = read_file(f['id'], f['name'])
        if df is not None:
            if 'หมายเลขคำสั่งซื้อออนไลน์' in df.columns:
                df['หมายเลขคำสั่งซื้อออนไลน์'] = df['หมายเลขคำสั่งซื้อออนไลน์'].astype(str).str.replace(r'\.0$', '', regex=True)
            df_list.append(df)
    df_main = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()

    # Load Ads
    files_ads = get_files(FOLDER_ID_ADS)
    df_ads_list = []
    for f in files_ads:
        df = read_file(f['id'], f['name'])
        if df is not None: df_ads_list.append(df)
    df_ads_raw = pd.concat(df_ads_list, ignore_index=True) if df_ads_list else pd.DataFrame()

    # Load Master & Fix Cost
    df_master = pd.DataFrame()
    df_fix = pd.DataFrame()
    try:
        sh = gc.open_by_url(SHEET_MASTER_URL)
        df_master = pd.DataFrame(sh.worksheet("MASTER_ITEM").get_all_records())
        try: df_fix = pd.DataFrame(sh.worksheet("FIX_COST").get_all_records())
        except: 
            try: df_fix = pd.DataFrame(sh.worksheet("FIXED_COST").get_all_records())
            except: df_fix = pd.DataFrame()
    except: pass

    if df_main.empty: return pd.DataFrame(), pd.DataFrame(), [], {}

    # --- PROCESSING LOGIC (Cell 1 Equivalent) ---
    
    # 1. Clean Master & Fix Columns
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
    
    def clean_pct(val):
        if pd.isna(val) or val == "": return 0.0
        s = str(val).replace('%','').replace(',','').replace('฿','').strip()
        try: return float(s)/100 if float(s) > 1.0 else float(s)
        except: return 0.0

    for c in cols_money:
        if c in df_master.columns: df_master[c] = pd.to_numeric(df_master[c].astype(str).str.replace(',','').str.replace('฿',''), errors='coerce').fillna(0)
    for c in cols_percent:
        if c in df_master.columns: df_master[c] = df_master[c].apply(clean_pct)

    df_main['Date'] = pd.to_datetime(df_main['เวลาสั่งซื้อ']).dt.date
    df_main['SKU_Main'] = df_main['รูปแบบสินค้า'].astype(str).str.split('-').str[0].str.strip()
    if 'SKU' in df_master.columns: df_master['SKU'] = df_master['SKU'].astype(str).str.strip()

    # Merge
    master_cols = [c for c in cols_money + cols_percent + ['SKU', 'ชื่อสินค้า'] if c in df_master.columns]
    df_merged = pd.merge(df_main, df_master[master_cols].drop_duplicates('SKU'), left_on='SKU_Main', right_on='SKU', how='left')

    if 'ชื่อสินค้า' not in df_merged.columns: df_merged['ชื่อสินค้า'] = df_merged['SKU_Main']

    # --- CALCULATION ---
    df_merged['CAL_COST'] = df_merged['จำนวน'] * df_merged['ต้นทุน'].fillna(0)

    shipping_map = {"J&T Express": "J&T Express", "J&T": "J&T Express", "Flash Express": "Flash Express", "Flash": "Flash Express", "Kerry Express": "Kerry Express", "Kerry": "Kerry Express", "Thailand Post": "ThailandPost", "DHL Domestic": "DHL_1", "Shopee Express": "SPX Express", "SPX Express": "SPX Express", "Lazada Express": "LEX TH"}
    def get_ship_rate(row):
        c = str(row.get('บริษัทขนส่ง','')).strip()
        k = shipping_map.get(c, c)
        return row.get(k, row.get('Standard Delivery - ส่งธรรมดาในประเทศ', 0))

    df_merged['SHIP_RATE'] = df_merged.apply(get_ship_rate, axis=1)
    is_cod = df_merged['วิธีการชำระเงิน'].astype(str).str.contains('COD|ปลายทาง', case=False, na=False)
    
    # *** KEY FIX: Force Numeric to prevent 'subtract' error ***
    df_merged['รายละเอียดยอดที่ชำระแล้ว'] = pd.to_numeric(df_merged['รายละเอียดยอดที่ชำระแล้ว'], errors='coerce').fillna(0)
    df_merged['SHIP_RATE'] = pd.to_numeric(df_merged['SHIP_RATE'], errors='coerce').fillna(0)
    
    df_merged['CAL_COD_COST'] = np.where(is_cod, (df_merged['รายละเอียดยอดที่ชำระแล้ว'] * df_merged['SHIP_RATE']) * 1.07, 0)

    def get_role(row):
        t = str(row.get('ประเภทการทำงาน','')) + " " + str(row.get('ผู้สร้างคำสั่งซื้อ',''))
        if 'admin' in t.lower() or 'แอดมิน' in t: return 'Admin'
        if 'tele' in t.lower() or 'เทเล' in t: return 'Telesale'
        return 'Unknown'
    
    df_merged['Role'] = df_merged.apply(get_role, axis=1)
    df_merged['CAL_COM_ADMIN'] = np.where(df_merged['Role']=='Admin', df_merged['รายละเอียดยอดที่ชำระแล้ว'] * df_merged.get('ค่าคอมมิชชั่น Admin',0), 0)
    df_merged['CAL_COM_TELESALE'] = np.where(df_merged['Role']=='Telesale', df_merged['รายละเอียดยอดที่ชำระแล้ว'] * df_merged.get('ค่าคอมมิชชั่น Telesale',0), 0)

    # Ads
    if not df_ads_raw.empty:
        col_cost = next((c for c in ['จำนวนเงินที่ใช้จ่ายไป (THB)', 'Cost', 'Amount'] if c in df_ads_raw.columns), None)
        col_date = next((c for c in ['วัน', 'Date'] if c in df_ads_raw.columns), None)
        col_camp = next((c for c in ['ชื่อแคมเปญ', 'Campaign'] if c in df_ads_raw.columns), None)
        if col_cost and col_date and col_camp:
            df_ads_raw['Date'] = pd.to_datetime(df_ads_raw[col_date]).dt.date
            df_ads_raw['SKU_Main'] = df_ads_raw[col_camp].astype(str).str.extract(r'\[(.*?)\]')
            df_ads_agg = df_ads_raw.groupby(['Date', 'SKU_Main'])[col_cost].sum().reset_index(name='Ads_Amount')
        else: df_ads_agg = pd.DataFrame()
    else: df_ads_agg = pd.DataFrame()

    # Final Group
    df_daily = df_merged.groupby(['Date', 'SKU_Main']).agg({
        'ชื่อสินค้า': 'first', 'หมายเลขคำสั่งซื้อออนไลน์': 'count', 'จำนวน': 'sum', 'รายละเอียดยอดที่ชำระแล้ว': 'sum',
        'CAL_COST': 'sum', 'ราคากล่อง': 'sum', 'ค่าส่งเฉลี่ย': 'sum', 'CAL_COD_COST': 'sum', 'CAL_COM_ADMIN': 'sum', 'CAL_COM_TELESALE': 'sum'
    }).reset_index()
    df_daily.rename(columns={'หมายเลขคำสั่งซื้อออนไลน์': 'จำนวนออเดอร์', 'ราคากล่อง': 'BOX_COST', 'ค่าส่งเฉลี่ย': 'DELIV_COST'}, inplace=True)
    
    if not df_ads_agg.empty: df_daily = pd.merge(df_daily, df_ads_agg, on=['Date', 'SKU_Main'], how='outer').fillna(0)
    else: df_daily['Ads_Amount'] = 0

    # *** KEY FIX: Force Numeric AGAIN before Subtraction ***
    for col in ['BOX_COST', 'DELIV_COST', 'CAL_COD_COST', 'CAL_COM_ADMIN', 'CAL_COM_TELESALE', 'CAL_COST', 'Ads_Amount', 'รายละเอียดยอดที่ชำระแล้ว']:
        df_daily[col] = pd.to_numeric(df_daily[col], errors='coerce').fillna(0)

    df_daily['Other_Costs'] = df_daily['BOX_COST'] + df_daily['DELIV_COST'] + df_daily['CAL_COD_COST'] + df_daily['CAL_COM_ADMIN'] + df_daily['CAL_COM_TELESALE']
    df_daily['Total_Cost'] = df_daily['CAL_COST'] + df_daily['Other_Costs'] + df_daily['Ads_Amount']
    df_daily['Net_Profit'] = df_daily['รายละเอียดยอดที่ชำระแล้ว'] - df_daily['Total_Cost']
    
    df_daily['Year'] = pd.to_datetime(df_daily['Date']).dt.year
    df_daily['Month_Num'] = pd.to_datetime(df_daily['Date']).dt.month
    thai_months = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
    df_daily['Month_Thai'] = df_daily['Month_Num'].apply(lambda x: thai_months[x-1] if 1<=x<=12 else "")
    df_daily['Day'] = pd.to_datetime(df_daily['Date']).dt.day
    
    if not df_fix.empty and 'เดือน' in df_fix.columns: df_fix['Key'] = df_fix['เดือน'].astype(str).str.strip() + "-" + df_fix['ปี'].astype(str)

    name_map = df_daily.groupby('SKU_Main')['ชื่อสินค้า'].last().to_dict()
    if 'ชื่อสินค้า' in df_master.columns: name_map.update(df_master.set_index('SKU')['ชื่อสินค้า'].to_dict())
    sku_list = sorted(list(set(df_daily['SKU_Main'].dropna().unique().tolist())))
    
    return df_daily, df_fix, sku_list, name_map

# ==========================================
# 4. DASHBOARD UI (Cell 2 Equivalent)
# ==========================================
try:
    df_daily, df_fix_cost, master_sku_list, sku_name_map = load_and_process_data()
    
    if df_daily.empty:
        st.warning("⚠️ ยังไม่พบข้อมูลใน Google Drive")
        st.stop()

    thai_months = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
    
    # --- State Management for SKU Selection ---
    if 'selected_skus' not in st.session_state: st.session_state.selected_skus = []
    
    sku_options = [f"{sku} : {sku_name_map.get(sku, '')}" for sku in master_sku_list]
    sku_map_rev = {f"{sku} : {sku_name_map.get(sku, '')}": sku for sku in master_sku_list}

    def cb_add():
        term = st.session_state.search_term.lower()
        if term:
            found = [o for o in sku_options if term in o.lower()]
            st.session_state.selected_skus = list(set(st.session_state.selected_skus).union(set(found)))
    
    def cb_clear(): st.session_state.selected_skus = []

    page = st.radio("เลือกหน้าจอ:", ["📊 REPORT_MONTH", "📅 REPORT_DAILY", "📈 PRODUCT GRAPH", "📈 YEARLY P&L", "💰 COMMISSION"], horizontal=True)

    # ---------------- PAGE 1: MONTHLY ----------------
    if page == "📊 REPORT_MONTH":
        st.markdown('<div class="header-bar"><div class="header-title"><i class="fas fa-chart-line"></i> สรุปรายเดือน</div></div>', unsafe_allow_html=True)
        
        with st.container():
            c1, c2, c3 = st.columns([1,1,2])
            sel_year = c1.selectbox("เลือกปี", sorted(df_daily['Year'].unique(), reverse=True))
            sel_month = c2.selectbox("เลือกเดือน", thai_months, index=datetime.now().month-1)
            filter_mode = c3.selectbox("เงื่อนไข", ["📦 แสดงรายการที่มีการเคลื่อนไหว", "💰 เฉพาะรายการที่ขายได้", "💸 ผลาญงบ (มี Ads แต่ขายไม่ได้)", "📋 แสดง Master ทั้งหมด"])
            
            c4, c5, c6, c7 = st.columns([2, 3, 0.5, 0.5])
            c4.text_input("ค้นหา SKU:", key="search_term")
            c5.multiselect("รายการที่เลือก:", sku_options, key="selected_skus")
            c6.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
            c6.button("➕", on_click=cb_add, use_container_width=True)
            c7.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
            c7.button("🧹", on_click=cb_clear, use_container_width=True)

        df_view = df_daily[(df_daily['Year']==sel_year) & (df_daily['Month_Thai']==sel_month)]
        
        # Filter Logic
        sku_stats = df_view.groupby('SKU_Main').agg({'รายละเอียดยอดที่ชำระแล้ว':'sum', 'Ads_Amount':'sum'}).reset_index()
        auto_skus = []
        if "ขายได้" in filter_mode: auto_skus = sku_stats[sku_stats['รายละเอียดยอดที่ชำระแล้ว']>0]['SKU_Main'].tolist()
        elif "ผลาญงบ" in filter_mode: auto_skus = sku_stats[(sku_stats['Ads_Amount']>0) & (sku_stats['รายละเอียดยอดที่ชำระแล้ว']==0)]['SKU_Main'].tolist()
        elif "Master" in filter_mode: auto_skus = master_sku_list
        else: auto_skus = sku_stats[(sku_stats['รายละเอียดยอดที่ชำระแล้ว']>0)|(sku_stats['Ads_Amount']>0)]['SKU_Main'].tolist()
        
        final_skus = [sku_map_rev[x] for x in st.session_state.selected_skus] if st.session_state.selected_skus else auto_skus
        df_view = df_view[df_view['SKU_Main'].isin(final_skus)]

        if df_view.empty: st.info(f"ไม่มีข้อมูลในเดือน {sel_month} {sel_year}")
        else:
            days_in_m = calendar.monthrange(sel_year, thai_months.index(sel_month)+1)[1]
            fix_c = 0
            if not df_fix_cost.empty:
                match = df_fix_cost[df_fix_cost['Key'] == f"{sel_month}-{sel_year}"]
                if not match.empty: fix_c = match['Fix_Cost'].iloc[0]
            
            sales = df_view['รายละเอียดยอดที่ชำระแล้ว'].sum()
            ads = df_view['Ads_Amount'].sum()
            cost_ops = df_view['Total_Cost'].sum() - ads
            profit = sales - cost_ops - ads - fix_c
            
            st.markdown(f"""<div class="metric-container">
            <div class="custom-card border-blue"><div class="card-label">ยอดขาย</div><div class="card-value">{sales:,.0f}</div></div>
            <div class="custom-card border-purple"><div class="card-label">ทุนสินค้า+ค่าใช้จ่าย</div><div class="card-value">{cost_ops:,.0f}</div></div>
            <div class="custom-card border-orange"><div class="card-label">ค่าโฆษณา</div><div class="card-value">{ads:,.0f}</div></div>
            <div class="custom-card border-green"><div class="card-label">กำไรสุทธิ</div><div class="card-value" style="color:{'#2ecc71' if profit>=0 else '#e74c3c'} !important;">{profit:,.0f}</div></div>
            </div>""", unsafe_allow_html=True)
            
            # Matrix Table Logic
            all_days = range(1, days_in_m + 1)
            fix_daily = fix_c / days_in_m if days_in_m > 0 else 0
            matrix = []
            for d in all_days:
                dd = df_view[df_view['Day'] == d]
                row = {'วันที่': str(d), 'รวม': dd['รายละเอียดยอดที่ชำระแล้ว'].sum(), 'กำไร': dd['Net_Profit'].sum() - fix_daily}
                for s in final_skus:
                    row[s] = dd[dd['SKU_Main']==s]['Net_Profit'].sum()
                matrix.append(row)
            
            df_mat = pd.DataFrame(matrix)
            
            def fmt(v): return f"{v:,.0f}" if v!=0 else "-"
            
            # HTML Table
            h = '<div class="table-wrapper"><table class="custom-table"><thead><tr>'
            h += '<th style="position:sticky;left:0;z-index:10;background:#2c3e50;color:white;">รวม</th>'
            h += '<th style="position:sticky;left:60px;z-index:10;background:#2c3e50;color:white;">กำไร</th>'
            h += '<th>วันที่</th>'
            for s in final_skus: h += f'<th>{s}<br><span class="col-small">{sku_name_map.get(s,"")[:10]}..</span></th>'
            h += '</tr></thead><tbody>'
            
            for _, r in df_mat.iterrows():
                pc = "#2ecc71" if r['กำไร'] >= 0 else "#e74c3c"
                h += f'<tr><td style="position:sticky;left:0;background:#333;font-weight:bold;">{fmt(r["รวม"])}</td>'
                h += f'<td style="position:sticky;left:60px;background:#333;font-weight:bold;color:{pc};">{fmt(r["กำไร"])}</td>'
                h += f'<td>{r["วันที่"]}</td>'
                for s in final_skus:
                    v = r.get(s, 0)
                    c = "#ddd" if v >= 0 else "#e74c3c"
                    if v==0: c="#555"
                    h += f'<td style="color:{c};">{fmt(v)}</td>'
                h += '</tr>'
            h += '</tbody></table></div>'
            st.markdown(h, unsafe_allow_html=True)

    # ---------------- PAGE 2: DAILY ----------------
    elif page == "📅 REPORT_DAILY":
        st.markdown('<div class="header-bar"><div class="header-title">สรุปรายวัน</div></div>', unsafe_allow_html=True)
        d_start = st.date_input("เริ่ม", datetime.now().replace(day=1))
        d_end = st.date_input("ถึง", datetime.now())
        
        mask = (pd.to_datetime(df_daily['Date']) >= pd.to_datetime(d_start)) & (pd.to_datetime(df_daily['Date']) <= pd.to_datetime(d_end))
        df_d = df_daily[mask]
        
        if df_d.empty: st.warning("ไม่พบข้อมูลในช่วงเวลานี้")
        else:
            sum_sales = df_d['รายละเอียดยอดที่ชำระแล้ว'].sum()
            sum_profit = df_d['Net_Profit'].sum()
            st.markdown(f"**ยอดขายรวม:** {sum_sales:,.0f} บาท | **กำไรสุทธิ (เบื้องต้น):** {sum_profit:,.0f} บาท")
            
            g = df_d.groupby('SKU_Main').agg({'ชื่อสินค้า':'last', 'จำนวน':'sum', 'รายละเอียดยอดที่ชำระแล้ว':'sum', 'Ads_Amount':'sum', 'Net_Profit':'sum'}).reset_index()
            st.dataframe(g, use_container_width=True)

    # ---------------- PAGE 3: GRAPH ----------------
    elif page == "📈 PRODUCT GRAPH":
        st.markdown('<div class="header-bar"><div class="header-title">กราฟแนวโน้ม</div></div>', unsafe_allow_html=True)
        skus = st.multiselect("เลือกสินค้า", master_sku_list)
        if skus:
            df_g = df_daily[df_daily['SKU_Main'].isin(skus)]
            chart = alt.Chart(df_g).mark_line(point=True).encode(
                x='Date', y='รายละเอียดยอดที่ชำระแล้ว', color='SKU_Main', tooltip=['Date','SKU_Main','รายละเอียดยอดที่ชำระแล้ว']
            ).interactive()
            st.altair_chart(chart, use_container_width=True)

    # ---------------- PAGE 4: P&L ----------------
    elif page == "📈 YEARLY P&L":
        st.markdown('<div class="header-bar"><div class="header-title">งบกำไรขาดทุน (รายปี)</div></div>', unsafe_allow_html=True)
        sel_year_pnl = st.selectbox("เลือกปี", sorted(df_daily['Year'].unique(), reverse=True))
        
        df_yr = df_daily[df_daily['Year'] == sel_year_pnl]
        if not df_yr.empty:
            sales = df_yr['รายละเอียดยอดที่ชำระแล้ว'].sum()
            cost_prod = df_yr['CAL_COST'].sum()
            cost_box = df_yr['BOX_COST'].sum()
            gross = sales - cost_prod - cost_box
            
            ship = df_yr['DELIV_COST'].sum()
            cod = df_yr['CAL_COD_COST'].sum()
            admin = df_yr['CAL_COM_ADMIN'].sum()
            tele = df_yr['CAL_COM_TELESALE'].sum()
            ads = df_yr['Ads_Amount'].sum()
            
            fix = 0
            if not df_fix_cost.empty:
                fix = df_fix_cost[df_fix_cost['Key'].str.contains(str(sel_year_pnl))]['Fix_Cost'].sum()
            
            net = gross - ship - cod - admin - tele - ads - fix
            
            def row(label, val, is_h=False, is_sub=False):
                style = "font-weight:bold; background:#333;" if is_h else ""
                pad = "padding-left:30px;" if is_sub else ""
                col = "#e74c3c" if val < 0 else "#ddd"
                return f"<tr style='{style}'> <td style='{pad}'>{label}</td> <td style='text-align:right; color:{col};'>{val:,.0f}</td> </tr>"
            
            html = f"""<table class='pnl-table'>
            {row('รายได้จากการขาย', sales, True)}
            {row('หัก ต้นทุนสินค้า', -cost_prod)}
            {row('หัก ค่ากล่อง', -cost_box)}
            {row('กำไรขั้นต้น', gross, True)}
            {row('หัก ค่าขนส่ง', -ship, is_sub=True)}
            {row('หัก ค่า COD', -cod, is_sub=True)}
            {row('หัก ค่าคอม Admin', -admin, is_sub=True)}
            {row('หัก ค่าคอม Telesale', -tele, is_sub=True)}
            {row('หัก ค่าโฆษณา (Ads)', -ads, is_sub=True)}
            {row('หัก ค่าใช้จ่ายคงที่', -fix, is_sub=True)}
            {row('กำไรสุทธิ', net, True)}
            </table>"""
            st.markdown(html, unsafe_allow_html=True)

    # ---------------- PAGE 5: COMMISSION ----------------
    elif page == "💰 COMMISSION":
        st.markdown('<div class="header-bar"><div class="header-title">ค่าคอมมิชชั่น</div></div>', unsafe_allow_html=True)
        c1, c2 = st.columns([1,1])
        sel_year_c = c1.selectbox("เลือกปี", sorted(df_daily['Year'].unique(), reverse=True), key='cy')
        sel_month_c = c2.selectbox("เลือกเดือน", thai_months, index=datetime.now().month-1, key='cm')
        
        df_c = df_daily[(df_daily['Year']==sel_year_c) & (df_daily['Month_Thai']==sel_month_c)]
        
        if df_c.empty: st.warning("ไม่มีข้อมูล")
        else:
            admin_c = df_c['CAL_COM_ADMIN'].sum()
            tele_c = df_c['CAL_COM_TELESALE'].sum()
            st.metric("Admin Commission", f"{admin_c:,.0f} บาท")
            st.metric("Telesale Commission", f"{tele_c:,.0f} บาท")
            
            chart_c = df_c.groupby('Day')[['CAL_COM_ADMIN','CAL_COM_TELESALE']].sum().reset_index().melt('Day')
            c = alt.Chart(chart_c).mark_bar().encode(x='Day', y='value', color='variable')
            st.altair_chart(c, use_container_width=True)

except Exception as e:
    st.error(f"เกิดข้อผิดพลาด: {e}")