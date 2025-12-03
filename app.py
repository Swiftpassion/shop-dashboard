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
# 1. CONFIG & SETUP
# ==========================================
st.set_page_config(page_title="Shop Analytics Dashboard", layout="wide", page_icon="📊")

# CSS Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Sarabun:wght@300;400;600;700&family=Prompt:wght@300;400;500;600&display=swap');
    html, body, [class*="css"] { font-family: 'Sarabun', sans-serif; }
    .stApp { background-color: #f4f6f9; }
    .block-container { padding-top: 2rem !important; }
    .header-bar { background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%); padding: 15px 20px; border-radius: 10px; margin-bottom: 20px; color: white; display:flex; align-items:center; }
    .header-title { font-size: 22px; font-weight: 700; margin: 0; color: white !important; }
    .metric-container { display: flex; gap: 15px; margin-bottom: 20px; flex-wrap: wrap; }
    .custom-card { background: white; border-radius: 10px; padding: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); flex: 1; min-width: 180px; border-left: 5px solid #ddd; }
    .card-label { color: #666; font-size: 13px; font-weight: 600; }
    .card-value { color: #333; font-size: 24px; font-weight: 700; }
</style>""", unsafe_allow_html=True)

# ---------------- SETTINGS ----------------
FOLDER_ID_DATA = "1ciI_X2m8pVcsjRsPuUf5sg--6uPSPPDp"
FOLDER_ID_ADS = "1ZE76TXNA_vNeXjhAZfLgBQQGIV0GY7w8"
SHEET_MASTER_URL = "https://docs.google.com/spreadsheets/d/1Q3akHm1GKkDI2eilGfujsd9pO7aOjJvyYJNuXd98lzo/edit"

# ---------------- DRIVE CONNECTION ----------------
@st.cache_resource
def get_drive_service():
    if "gcp_service_account" not in st.secrets:
        st.error("ไม่พบกุญแจ Secrets กรุณาตั้งค่าใน Advanced Settings")
        st.stop()
    creds_dict = dict(st.secrets["gcp_service_account"])
    scopes = ['https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/spreadsheets']
    return service_account.Credentials.from_service_account_info(creds_dict, scopes=scopes)

@st.cache_data(ttl=0) # ปิด Cache ชั่วคราวเพื่อให้แน่ใจว่าโหลดใหม่จริง
def load_data_robust():
    creds = get_drive_service()
    service = build('drive', 'v3', credentials=creds)
    gc = gspread.authorize(creds)

    # 1. LOAD MASTER (สำคัญที่สุด)
    df_master = pd.DataFrame()
    df_fix = pd.DataFrame()
    
    try:
        sh = gc.open_by_url(SHEET_MASTER_URL)
        df_master = pd.DataFrame(sh.worksheet("MASTER_ITEM").get_all_records())
        try: df_fix = pd.DataFrame(sh.worksheet("FIX_COST").get_all_records())
        except: 
            try: df_fix = pd.DataFrame(sh.worksheet("FIXED_COST").get_all_records()) # เผื่อกรณีชื่อเดิม
            except: pass
    except Exception as e:
        st.error(f"Error Loading Master: {e}")

    # 2. LOAD DATA
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

    files_data = get_files(FOLDER_ID_DATA)
    df_list = [read_file(f['id'], f['name']) for f in files_data]
    df_list = [d for d in df_list if d is not None]
    df_main = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()
    if not df_main.empty and 'หมายเลขคำสั่งซื้อออนไลน์' in df_main.columns:
         df_main['หมายเลขคำสั่งซื้อออนไลน์'] = df_main['หมายเลขคำสั่งซื้อออนไลน์'].astype(str).str.replace(r'\.0$', '', regex=True)

    # 3. LOAD ADS
    files_ads = get_files(FOLDER_ID_ADS)
    df_ads_list = [read_file(f['id'], f['name']) for f in files_ads]
    df_ads_list = [d for d in df_ads_list if d is not None]
    df_ads = pd.concat(df_ads_list, ignore_index=True) if df_ads_list else pd.DataFrame()

    return df_main, df_ads, df_master, df_fix

# ---------------- PROCESSING LOGIC ----------------
try:
    with st.spinner('กำลังดึงข้อมูล...'):
        df_main, df_ads, df_master, df_fix = load_data_robust()

    if df_master.empty:
        st.error("❌ ไม่พบข้อมูล Master Item")
        st.stop()

    # >>>>> จุดแก้ปัญหา: CLEAN MASTER COLUMNS <<<<<
    # 1. ลบช่องว่างหัวท้ายออกจากชื่อคอลัมน์ทั้งหมด
    df_master.columns = df_master.columns.astype(str).str.strip()

    # 2. เช็คว่ามีคอลัมน์ 'ชื่อสินค้า' หรือไม่?
    if 'ชื่อสินค้า' not in df_master.columns:
        # ถ้าไม่มี ให้ลองหาชื่ออื่นที่ใกล้เคียง
        found = False
        for alt_name in ['Name', 'Product Name', 'Product', 'ชื่อ', 'DESCRIPTION']:
            if alt_name in df_master.columns:
                df_master.rename(columns={alt_name: 'ชื่อสินค้า'}, inplace=True)
                found = True
                break
        
        # 3. ไม้ตาย: ถ้ายังไม่เจออีก ให้ใช้คอลัมน์ที่ 2 (Index 1) เป็นชื่อสินค้าเลย (เพราะจากรูปคือ Column B)
        if not found and len(df_master.columns) >= 2:
            col_b_name = df_master.columns[1] # ชื่อคอลัมน์ B จริงๆ ที่ระบบอ่านได้
            st.toast(f"ℹ️ ระบบใช้คอลัมน์ '{col_b_name}' เป็นชื่อสินค้าอัตโนมัติ")
            df_master.rename(columns={col_b_name: 'ชื่อสินค้า'}, inplace=True)
            
        # 4. ถ้าไม่มีทางออกจริงๆ สร้าง Dummy
        if 'ชื่อสินค้า' not in df_master.columns:
             df_master['ชื่อสินค้า'] = df_master['SKU'] if 'SKU' in df_master.columns else "Unknown"

    # --- DEBUG INFO (กดดูได้ถ้ามีปัญหา) ---
    with st.expander("🛠️ Debug: ตรวจสอบข้อมูล Master (กดเพื่อดู)"):
        st.write("คอลัมน์ที่อ่านได้จริง:", df_master.columns.tolist())
        st.dataframe(df_master.head(3))

    # --- Process Calculation (ส่วนที่เหลือเหมือนเดิม) ---
    cols_money = ['ต้นทุน', 'ราคากล่อง', 'ค่าส่งเฉลี่ย']
    cols_percent = ['ค่าคอมมิชชั่น Admin', 'ค่าคอมมิชชั่น Telesale', 'J&T Express', 'Flash Express', 'ThailandPost', 'DHL_1', 'LEX TH', 'SPX Express', 'Express Delivery - ส่งด่วน', 'Standard Delivery - ส่งธรรมดาในประเทศ']
    
    def clean_pct(val):
        if pd.isna(val) or val == "": return 0.0
        s = str(val).replace('%','').replace(',','').replace('฿','').strip()
        try: 
            f = float(s)
            return f/100 if f > 1.0 else f 
        except: return 0.0

    for c in cols_money:
        if c in df_master.columns: df_master[c] = pd.to_numeric(df_master[c].astype(str).str.replace(',','').str.replace('฿',''), errors='coerce').fillna(0)
    for c in cols_percent:
        if c in df_master.columns: df_master[c] = df_master[c].apply(clean_pct)

    if 'SKU' in df_master.columns: df_master['SKU'] = df_master['SKU'].astype(str).str.strip()

    # Prepare Main Data
    if not df_main.empty:
        df_main['Date'] = pd.to_datetime(df_main['เวลาสั่งซื้อ']).dt.date
        df_main['SKU_Main'] = df_main['รูปแบบสินค้า'].astype(str).str.split('-').str[0].str.strip()
        
        # Safe Merge
        req_cols = [c for c in cols_money + cols_percent + ['SKU', 'ชื่อสินค้า'] if c in df_master.columns]
        df_merged = pd.merge(df_main, df_master[req_cols].drop_duplicates('SKU'), left_on='SKU_Main', right_on='SKU', how='left')

        # Calcs
        df_merged['CAL_COST'] = df_merged['จำนวน'] * df_merged['ต้นทุน'].fillna(0)
        
        shipping_map = {"J&T Express": "J&T Express", "J&T": "J&T Express", "Flash Express": "Flash Express", "Flash": "Flash Express", "Kerry Express": "Kerry Express", "Kerry": "Kerry Express", "Thailand Post": "ThailandPost", "DHL Domestic": "DHL_1", "Shopee Express": "SPX Express", "SPX Express": "SPX Express", "Lazada Express": "LEX TH"}
        def get_ship_rate(row):
            c = str(row.get('บริษัทขนส่ง','')).strip()
            k = shipping_map.get(c, c)
            return row.get(k, row.get('Standard Delivery - ส่งธรรมดาในประเทศ', 0))

        df_merged['SHIP_RATE'] = df_merged.apply(get_ship_rate, axis=1)
        is_cod = df_merged['วิธีการชำระเงิน'].astype(str).str.contains('COD|ปลายทาง', case=False, na=False)
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
        if not df_ads.empty:
            col_cost = next((c for c in ['จำนวนเงินที่ใช้จ่ายไป (THB)', 'Cost', 'Amount'] if c in df_ads.columns), None)
            col_date = next((c for c in ['วัน', 'Date'] if c in df_ads.columns), None)
            col_camp = next((c for c in ['ชื่อแคมเปญ', 'Campaign'] if c in df_ads.columns), None)
            if col_cost and col_date and col_camp:
                df_ads['Date'] = pd.to_datetime(df_ads[col_date]).dt.date
                df_ads['SKU_Main'] = df_ads[col_camp].astype(str).str.extract(r'\[(.*?)\]')
                df_ads_agg = df_ads.groupby(['Date', 'SKU_Main'])[col_cost].sum().reset_index(name='Ads_Amount')
            else: df_ads_agg = pd.DataFrame()
        else: df_ads_agg = pd.DataFrame()

        # Aggregation
        df_daily = df_merged.groupby(['Date', 'SKU_Main']).agg({
            'ชื่อสินค้า': 'first', 'หมายเลขคำสั่งซื้อออนไลน์': 'count', 'จำนวน': 'sum', 'รายละเอียดยอดที่ชำระแล้ว': 'sum',
            'CAL_COST': 'sum', 'ราคากล่อง': 'sum', 'ค่าส่งเฉลี่ย': 'sum', 'CAL_COD_COST': 'sum', 'CAL_COM_ADMIN': 'sum', 'CAL_COM_TELESALE': 'sum'
        }).reset_index()
        df_daily.rename(columns={'หมายเลขคำสั่งซื้อออนไลน์': 'จำนวนออเดอร์', 'ราคากล่อง': 'BOX_COST', 'ค่าส่งเฉลี่ย': 'DELIV_COST'}, inplace=True)
        
        if not df_ads_agg.empty: df_daily = pd.merge(df_daily, df_ads_agg, on=['Date', 'SKU_Main'], how='outer').fillna(0)
        else: df_daily['Ads_Amount'] = 0

        df_daily['Other_Costs'] = df_daily['BOX_COST'] + df_daily['DELIV_COST'] + df_daily['CAL_COD_COST'] + df_daily['CAL_COM_ADMIN'] + df_daily['CAL_COM_TELESALE']
        df_daily['Total_Cost'] = df_daily['CAL_COST'] + df_daily['Other_Costs'] + df_daily['Ads_Amount']
        df_daily['Net_Profit'] = df_daily['รายละเอียดยอดที่ชำระแล้ว'] - df_daily['Total_Cost']
        
        df_daily['Year'] = pd.to_datetime(df_daily['Date']).dt.year
        df_daily['Month_Num'] = pd.to_datetime(df_daily['Date']).dt.month
        thai_months = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]
        df_daily['Month_Thai'] = df_daily['Month_Num'].apply(lambda x: thai_months[x-1] if 1<=x<=12 else "")
        df_daily['Day'] = pd.to_datetime(df_daily['Date']).dt.day
        
        # Prepare Maps
        name_map = df_daily.groupby('SKU_Main')['ชื่อสินค้า'].last().to_dict()
        if 'ชื่อสินค้า' in df_master.columns: name_map.update(df_master.set_index('SKU')['ชื่อสินค้า'].to_dict())
        sku_list = sorted(list(set(df_daily['SKU_Main'].dropna().unique().tolist())))
    else:
        df_daily = pd.DataFrame()
        name_map = {}
        sku_list = []

    # ---------------- UI DASHBOARD ----------------
    page = st.radio("เลือกหน้าจอ:", ["📊 REPORT_MONTH", "📅 REPORT_DAILY", "📈 PRODUCT GRAPH", "📈 YEARLY P&L", "💰 COMMISSION"], horizontal=True)

    if not df_fix.empty and 'เดือน' in df_fix.columns: df_fix['Key'] = df_fix['เดือน'].astype(str).str.strip() + "-" + df_fix['ปี'].astype(str)

    if page == "📊 REPORT_MONTH":
        st.markdown('<div class="header-bar"><div class="header-title"><i class="fas fa-chart-line"></i> สรุปรายเดือน</div></div>', unsafe_allow_html=True)
        if df_daily.empty: st.warning("ไม่พบข้อมูลการขาย")
        else:
            c1, c2 = st.columns([1,1])
            sel_year = c1.selectbox("เลือกปี", sorted(df_daily['Year'].unique(), reverse=True))
            sel_month = c2.selectbox("เลือกเดือน", thai_months, index=datetime.now().month-1)
            
            df_view = df_daily[(df_daily['Year']==sel_year) & (df_daily['Month_Thai']==sel_month)]
            
            if df_view.empty: st.info(f"ไม่มีข้อมูลในเดือน {sel_month} {sel_year}")
            else:
                fix_c = 0
                if not df_fix.empty:
                    match = df_fix[df_fix['Key'] == f"{sel_month}-{sel_year}"]
                    if not match.empty: fix_c = match['Fix_Cost'].iloc[0]
                
                sales = df_view['รายละเอียดยอดที่ชำระแล้ว'].sum()
                ads = df_view['Ads_Amount'].sum()
                profit = df_view['Net_Profit'].sum() - fix_c
                
                st.markdown(f"""<div class="metric-container">
                <div class="custom-card border-blue"><div class="card-label">ยอดขาย</div><div class="card-value">{sales:,.0f}</div></div>
                <div class="custom-card border-green"><div class="card-label">กำไรสุทธิ</div><div class="card-value">{profit:,.0f}</div></div>
                </div>""", unsafe_allow_html=True)
                
                pivot = df_view.groupby('SKU_Main').agg({'รายละเอียดยอดที่ชำระแล้ว':'sum', 'Net_Profit':'sum', 'Ads_Amount':'sum'}).reset_index()
                pivot['ชื่อสินค้า'] = pivot['SKU_Main'].map(name_map)
                st.dataframe(pivot, use_container_width=True)

    elif page == "📅 REPORT_DAILY":
        if df_daily.empty: st.warning("ไม่พบข้อมูล")
        else:
            d_s = st.date_input("Start", datetime.now().replace(day=1))
            d_e = st.date_input("End", datetime.now())
            df_d = df_daily[(pd.to_datetime(df_daily['Date']) >= pd.to_datetime(d_s)) & (pd.to_datetime(df_daily['Date']) <= pd.to_datetime(d_e))]
            st.dataframe(df_d)

    # (ส่วนอื่นๆ ของ Dashboard คงเดิมได้ครับ...)

except Exception as e:
    st.error(f"เกิดข้อผิดพลาดร้ายแรง: {e}")
