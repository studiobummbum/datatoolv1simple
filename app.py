import streamlit as st
import pandas as pd
import io
import re

# --- CONFIG ---
st.set_page_config(page_title="UA Report Mapper V14 (Python)", layout="wide")

# --- UTILS FUNCTIONS (Logic giống hệt React) ---

def clean_currency(value):
    """Làm sạch dữ liệu tiền tệ/số: bỏ $, %, dấu phẩy"""
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    
    clean_str = str(value).replace('$', '').replace('%', '').replace(',', '').strip()
    try:
        return float(clean_str)
    except ValueError:
        return 0.0

def normalize_date(date_series):
    """Chuẩn hóa ngày tháng về dạng YYYY-MM-DD"""
    return pd.to_datetime(date_series, errors='coerce').dt.strftime('%Y-%m-%d')

def find_column(columns, keywords):
    """Tìm tên cột dựa trên từ khóa (Case insensitive)"""
    lower_cols = [str(c).lower().strip() for c in columns]
    for keyword in keywords:
        for idx, col in enumerate(lower_cols):
            if keyword in col:
                return columns[idx]
    return None

def process_data(cohort_file, ads_file):
    # --- FIX LỖI ENCODING Ở ĐÂY ---
    # Hàm phụ để đọc file csv bất chấp encoding
    def read_csv_safe(uploaded_file):
        try:
            # Thử đọc bằng utf-8 trước (chuẩn phổ biến)
            uploaded_file.seek(0)
            return pd.read_csv(uploaded_file, encoding='utf-8')
        except UnicodeDecodeError:
            try:
                # Nếu lỗi, thử đọc bằng utf-16 (thường gặp ở AdMob export)
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file, encoding='utf-16', sep='\t') # AdMob utf-16 thường dùng tab separator
            except Exception:
                 # Nếu vẫn lỗi, thử utf-16-le hoặc cp1252
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file, encoding='utf-16-le', sep='\t')
        except Exception as e:
             return None

    # 1. Đọc file Cohort (Dùng hàm safe mới)
    df_cohort = read_csv_safe(cohort_file)
    
    if df_cohort is None:
        st.error("Lỗi: Không thể đọc file Cohort. Vui lòng kiểm tra lại định dạng file (CSV/Excel).")
        return None, []

    # Chuẩn hóa tên cột để dễ xử lý
    df_cohort.columns = [c.strip() for c in df_cohort.columns]
    
    # ... (PHẦN CÒN LẠI CỦA HÀM GIỮ NGUYÊN NHƯ CŨ) ...
    
    # 2. Detect Country Column (Logic React: Auto-detect)
    country_col = find_column(df_cohort.columns, ['country', 'geo', 'region', 'location', 'country_code'])
    
    # Nếu không có cột Country, tạo cột giả định là 'Global'
    if not country_col:
        df_cohort['Country_Normalized'] = 'Global'
    else:
        df_cohort['Country_Normalized'] = df_cohort[country_col].astype(str).str.upper().str.strip()

    # 3. Detect Format (AdMob Long vs MMP Wide)
    days_since_install_col = find_column(df_cohort.columns, ['days since install', 'day index', 'days_since_install'])
    
    final_data = []

    if days_since_install_col:
        # --- LOGIC ADMOB (LONG FORMAT) ---
        date_col = find_column(df_cohort.columns, ['date', 'install date'])
        installs_col = find_column(df_cohort.columns, ['installs', 'users'])
        ltv_col = find_column(df_cohort.columns, ['ltv', 'total ltv', 'earnings'])
        
        if not date_col or not installs_col:
            st.error("Không tìm thấy cột Date hoặc Installs trong file AdMob.")
            return None, []

        df_cohort['Date_Normalized'] = normalize_date(df_cohort[date_col])
        grouped = df_cohort.groupby(['Date_Normalized', 'Country_Normalized'])
        
        processed_rows = []
        for (date, country), group in grouped:
            day0_row = group[group[days_since_install_col].apply(clean_currency) == 0]
            installs = 0
            ltv_d0 = 0
            if not day0_row.empty:
                installs = clean_currency(day0_row.iloc[0][installs_col])
                ltv_d0 = clean_currency(day0_row.iloc[0][ltv_col]) if ltv_col else 0
            
            ltv_d1 = 0
            ltv_d3 = 0
            day1_row = group[group[days_since_install_col].apply(clean_currency) == 1]
            if not day1_row.empty: ltv_d1 = clean_currency(day1_row.iloc[0][ltv_col])
            day3_row = group[group[days_since_install_col].apply(clean_currency) == 3]
            if not day3_row.empty: ltv_d3 = clean_currency(day3_row.iloc[0][ltv_col])

            processed_rows.append({
                'Date': date, 'Country': country, 'Installs': installs, 'Cost': 0.0,
                'LTV D0': ltv_d0, 'LTV D1': ltv_d1, 'LTV D3': ltv_d3
            })
        df_processed = pd.DataFrame(processed_rows)

    else:
        # --- LOGIC MMP (WIDE FORMAT) ---
        date_col = find_column(df_cohort.columns, ['date', 'day', 'time'])
        install_col = find_column(df_cohort.columns, ['install', 'conversions', 'inst'])
        cost_col = find_column(df_cohort.columns, ['cost', 'spend', 'amount'])
        d1_col = find_column(df_cohort.columns, ['d1', 'day1', 'retention_value_1', 'r1_ltv', 'ltv_d1'])
        d3_col = find_column(df_cohort.columns, ['d3', 'day3', 'retention_value_3', 'r3_ltv', 'ltv_d3'])

        if not date_col:
            st.error("Không tìm thấy cột Date.")
            return None, []

        df_cohort['Date_Normalized'] = normalize_date(df_cohort[date_col])
        cols_to_clean = [install_col, cost_col, d1_col, d3_col]
        for c in cols_to_clean:
            if c: df_cohort[c] = df_cohort[c].apply(clean_currency)

        agg_dict = {}
        if install_col: agg_dict[install_col] = 'sum'
        if cost_col: agg_dict[cost_col] = 'sum'
        if d1_col: agg_dict[d1_col] = 'sum'
        if d3_col: agg_dict[d3_col] = 'sum'

        df_grouped = df_cohort.groupby(['Date_Normalized', 'Country_Normalized']).agg(agg_dict).reset_index()
        
        df_processed = pd.DataFrame()
        df_processed['Date'] = df_grouped['Date_Normalized']
        df_processed['Country'] = df_grouped['Country_Normalized']
        df_processed['Installs'] = df_grouped[install_col] if install_col else 0
        df_processed['Cost'] = df_grouped[cost_col] if cost_col else 0
        df_processed['LTV D0'] = 0.0
        
        installs_vec = df_processed['Installs'].replace(0, 1)
        val_d1 = df_grouped[d1_col] if d1_col else 0
        df_processed['LTV D1'] = val_d1 / installs_vec if (d1_col and df_grouped[d1_col].mean() > 10) else val_d1
        val_d3 = df_grouped[d3_col] if d3_col else 0
        df_processed['LTV D3'] = val_d3 / installs_vec if (d3_col and df_grouped[d3_col].mean() > 10) else val_d3

    # 4. Process Ads File (Optional) - Cũng dùng hàm safe read
    if ads_file:
        try:
            df_ads = read_csv_safe(ads_file) # Dùng hàm safe ở đây luôn
            if df_ads is not None:
                df_ads.columns = [c.strip() for c in df_ads.columns]
                
                date_col_a = find_column(df_ads.columns, ['date', 'day'])
                country_col_a = find_column(df_ads.columns, ['country', 'geo', 'region'])
                cost_col_a = find_column(df_ads.columns, ['cost', 'spend'])
                arpv_col_a = find_column(df_ads.columns, ['arpv', 'arpu', 'average revenue'])
                
                if date_col_a:
                    df_ads['Date_Normalized'] = normalize_date(df_ads[date_col_a])
                    if not country_col_a: df_ads['Country_Normalized'] = 'Global'
                    else: df_ads['Country_Normalized'] = df_ads[country_col_a].astype(str).str.upper().str.strip()
                    
                    agg_ads = {}
                    if cost_col_a: agg_ads[cost_col_a] = 'sum'
                    if arpv_col_a: agg_ads[arpv_col_a] = 'mean'
                    
                    if agg_ads:
                        df_ads_grouped = df_ads.groupby(['Date_Normalized', 'Country_Normalized']).agg(agg_ads).reset_index()
                        df_processed = pd.merge(df_processed, df_ads_grouped, left_on=['Date', 'Country'], right_on=['Date_Normalized', 'Country_Normalized'], how='left')
                        
                        if cost_col_a:
                            df_processed['Cost'] = df_processed.apply(lambda row: row[cost_col_a] if (pd.notna(row[cost_col_a]) and row['Cost'] == 0) else row['Cost'], axis=1)
                        if arpv_col_a:
                            df_processed['LTV D0'] = df_processed.apply(lambda row: row[arpv_col_a] if pd.notna(row[arpv_col_a]) else row['LTV D0'], axis=1)
        except Exception as e:
            st.warning(f"Có lỗi khi xử lý file Ads: {e}")

    final_cols = ['Date', 'Country', 'Cost', 'Installs', 'LTV D0', 'LTV D1', 'LTV D3']
    for c in final_cols:
        if c not in df_processed.columns: df_processed[c] = 0.0
            
    return df_processed[final_cols], sorted(df_processed['Country'].unique())

# --- MAIN UI ---

st.title("🚀 UA Report Mapper V14 (Python Edition)")
st.markdown("""
**Tính năng:**
*   ✅ **Auto-Detect Country:** Tự nhận diện cột Country/Geo.
*   ✅ **Multi-Geo Logic:** Tách dữ liệu theo từng quốc gia (Date + Country).
*   ✅ **Smart Merge:** Ghép file Ads (Cost) vào file Cohort chuẩn xác.
""")

col1, col2 = st.columns(2)
with col1:
    cohort_file = st.file_uploader("1. Upload Cohort File (CSV)", type=['csv'])
with col2:
    ads_file = st.file_uploader("2. Upload Ads File (Optional - CSV)", type=['csv'])

if cohort_file:
    if st.button("Analyze Data", type="primary"):
        with st.spinner("Đang xử lý dữ liệu Multi-Geo..."):
            processed_df, available_countries = process_data(cohort_file, ads_file)
            
            if processed_df is not None:
                st.session_state['data'] = processed_df
                st.session_state['countries'] = available_countries
                st.success("Xử lý xong!")

# --- RESULT VIEW ---

if 'data' in st.session_state:
    df = st.session_state['data']
    countries = st.session_state['countries']

    st.divider()
    
    # --- FILTER SECTION ---
    st.subheader("🔍 Filters & Analysis")
    
    f_col1, f_col2, f_col3 = st.columns([1, 1, 2])
    
    with f_col1:
        # COUNTRY FILTER (Logic React: Dropdown)
        selected_country = st.selectbox("Chọn Quốc Gia (Country):", ["All"] + countries)
    
    with f_col2:
        sort_order = st.selectbox("Sắp xếp theo ngày:", ["Mới nhất (Desc)", "Cũ nhất (Asc)"])

    # Filter Data Logic
    filtered_df = df.copy()
    
    if selected_country != "All":
        filtered_df = filtered_df[filtered_df['Country'] == selected_country]
        
    if sort_order == "Mới nhất (Desc)":
        filtered_df = filtered_df.sort_values(by='Date', ascending=False)
    else:
        filtered_df = filtered_df.sort_values(by='Date', ascending=True)

    # Format hiển thị cho đẹp
    display_df = filtered_df.copy()
    display_df['Cost'] = display_df['Cost'].apply(lambda x: f"${x:,.2f}")
    display_df['Installs'] = display_df['Installs'].apply(lambda x: f"{int(x):,}")
    display_df['LTV D0'] = display_df['LTV D0'].apply(lambda x: f"${x:.4f}")
    display_df['LTV D1'] = display_df['LTV D1'].apply(lambda x: f"${x:.4f}")
    display_df['LTV D3'] = display_df['LTV D3'].apply(lambda x: f"${x:.4f}")

    # --- METRICS SUMMARY ---
    # Tính tổng dựa trên dữ liệu đã filter
    total_installs = filtered_df['Installs'].sum()
    total_cost = filtered_df['Cost'].sum()
    avg_ltv_d1 = filtered_df['LTV D1'].mean() # Lấy trung bình đơn giản cho nhanh, chuẩn là weighted avg

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Installs", f"{int(total_installs):,}")
    m2.metric("Total Cost", f"${total_cost:,.2f}")
    m3.metric("Avg LTV D1", f"${avg_ltv_d1:.4f}")

    # --- TABLE SETTINGS (NEW FEATURE) ---
    st.markdown("### ⚙️ Tùy chỉnh bảng")
    with st.expander("Hiển thị & Kích thước", expanded=False):
        ts_col1, ts_col2 = st.columns([3, 1])
        
        with ts_col1:
            all_columns = display_df.columns.tolist()
            selected_columns = st.multiselect(
                "👁️ Chọn cột hiển thị:",
                options=all_columns,
                default=all_columns
            )
            
        with ts_col2:
            table_height = st.slider(
                "📏 Chiều cao bảng (px):",
                min_value=200, 
                max_value=1500, 
                value=500, 
                step=50
            )

    # --- DATA TABLE ---
    if selected_columns:
        st.dataframe(
            display_df[selected_columns], 
            use_container_width=True, 
            height=table_height
        )
    else:
        st.warning("Vui lòng chọn ít nhất 1 cột để hiển thị.")
    
    # --- DOWNLOAD ---
    csv = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label=f"Download CSV ({selected_country})",
        data=csv,
        file_name=f'ua_report_{selected_country}.csv',
        mime='text/csv',
    )