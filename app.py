import streamlit as st
import pandas as pd
import io

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="AdMob Cohort Analyzer Pro", layout="wide")

st.title("💰 AdMob Cohort LTV Analyzer (V3.6 - Stable)")
st.markdown("""
<style>
    .stAlert { padding: 10px; border-radius: 5px; }
    .success { background-color: #d4edda; color: #155724; }
</style>
""", unsafe_allow_html=True)

st.info("💡 Upload file `admob-report.csv`. Hệ thống tự động nhận diện header, encoding và dấu ngăn cách.")

# --- HÀM XỬ LÝ DATA ---
def load_data(uploaded_file):
    # Danh sách encoding hay gặp
    encodings = ['utf-16', 'utf-8', 'latin1', 'cp1252'] 
    # Danh sách dấu ngăn cách hay gặp (Tab hoặc Phẩy)
    separators = ['\t', ','] 
    
    df = None
    used_encoding = None
    used_sep = None
    header_row = 0
    
    # Logic dò tìm "trâu bò": Thử combo (Encoding + Separator + Skiprows)
    possible_skiprows = [0, 1, 2] 
    
    for enc in encodings:
        for sep in separators:
            for skip in possible_skiprows:
                try:
                    uploaded_file.seek(0)
                    # Đọc thử vài dòng để check
                    temp_df = pd.read_csv(uploaded_file, skiprows=skip, encoding=enc, sep=sep, on_bad_lines='skip', nrows=10)
                    
                    # Nếu đọc ra mà chỉ có 1 cột thì khả năng cao là sai separator -> Bỏ qua
                    if len(temp_df.columns) < 2:
                        continue

                    # Check xem tên cột có chứa từ khóa quan trọng không
                    col_str = " ".join([str(c).lower() for c in temp_df.columns])
                    if ('date' in col_str or 'ngày' in col_str) and ('country' in col_str or 'install' in col_str):
                        # Nếu OK thì đọc full file
                        uploaded_file.seek(0)
                        df = pd.read_csv(uploaded_file, skiprows=skip, encoding=enc, sep=sep, on_bad_lines='skip')
                        used_encoding = enc
                        used_sep = sep
                        header_row = skip
                        break
                except:
                    continue
            if df is not None: break
        if df is not None: break
            
    return df, used_encoding, used_sep, header_row

# --- UI CHÍNH ---
uploaded_file = st.file_uploader("📂 Kéo thả file CSV vào đây sếp ơi", type=['csv', 'txt'])

if uploaded_file is not None:
    with st.spinner('Đang soi data của sếp...'):
        df, encoding, sep, header_row = load_data(uploaded_file)

    if df is None:
        st.error("❌ Em chịu thua! Không đọc được file. Sếp check lại xem có phải CSV chuẩn không?")
        st.stop()

    # --- XỬ LÝ TÊN CỘT (MAPPING) ---
    df.columns = df.columns.astype(str).str.strip()
    
    mapping_rules = {
        'Date': ['install date', 'date', 'ngày'],
        'Country': ['install country', 'country', 'quốc gia', 'region'],
        'Day': ['days since install', 'day', 'ngày kể từ'],
        'LTV': ['ltv (usd)', 'ltv', 'revenue', 'doanh thu'],
        'Installs': ['installs', 'lượt cài đặt', 'cài đặt']
    }

    final_rename_map = {}
    found_cols = []

    for target_name, keywords in mapping_rules.items():
        match_col = None
        for col in df.columns:
            col_lower = col.lower()
            if any(kw in col_lower for kw in keywords):
                if target_name == 'Installs' and ('date' in col_lower or 'day' in col_lower or 'country' in col_lower or 'ltv' in col_lower):
                    continue
                if target_name == 'LTV' and ('iap' in col_lower or 'ads' in col_lower or 'sub' in col_lower):
                    continue     
                match_col = col
                break
        
        if match_col:
            final_rename_map[match_col] = target_name
            found_cols.append(target_name)

    # --- DEBUG INFO ---
    with st.expander("🕵️‍♂️ Debug: Thông số file"):
        st.write(f"**Encoding:** `{encoding}` | **Separator:** `{repr(sep)}`")
        st.write("**Mapping:**", final_rename_map)

    required_cols = ['Date', 'Day', 'LTV']
    missing = [col for col in required_cols if col not in found_cols]
    
    if missing:
        st.error(f"❌ Toang rồi sếp ơi! Em không tìm thấy cột: {', '.join(missing)}.")
        st.stop()

    # --- ÁP DỤNG RENAME & CLEAN ---
    df = df.rename(columns=final_rename_map)

    try:
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.date
        df = df.dropna(subset=['Date'])

        cols_to_numeric = ['LTV']
        if 'Installs' in df.columns:
            cols_to_numeric.append('Installs')
        
        for col in cols_to_numeric:
            if df[col].dtype == object:
                df[col] = df[col].astype(str).str.replace(r'[$,₫a-zA-Z()]', '', regex=True)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        if 'Installs' not in df.columns:
            df['Installs'] = 1 

    except Exception as e:
        st.error(f"❌ Lỗi khi clean data: {e}")
        st.stop()

    # --- PIVOT TABLE ---
    target_days = [0, 1, 3, 7, 14, 28, 30, 60]
    df_filtered = df[df['Day'].isin(target_days)].copy()

    if 'Country' not in df.columns:
        df_filtered['Country'] = 'Global'

    df_installs = df[df['Day'] == 0][['Date', 'Country', 'Installs']].drop_duplicates()
    df_installs = df_installs.groupby(['Date', 'Country'], as_index=False)['Installs'].sum()
    
    df_ltv = df_filtered.pivot_table(
        index=['Date', 'Country'],
        columns='Day',
        values='LTV',
        aggfunc='sum'
    ).reset_index()
    
    final_df = pd.merge(df_installs, df_ltv, on=['Date', 'Country'], how='left')
    
    new_cols = {d: f'LTV D{d}' for d in target_days if d in final_df.columns}
    final_df = final_df.rename(columns=new_cols)
    final_df = final_df.fillna(0)
    final_df = final_df.sort_values(by='Date', ascending=False)

    # --- HIỂN THỊ KẾT QUẢ ---
    st.success("✅ Ngon lành rồi sếp ơi!")
    
    format_config = {'Installs': '{:,.0f}'}
    ltv_cols = [c for c in final_df.columns if 'LTV' in c]
    for c in ltv_cols:
        format_config[c] = '${:.4f}'

    # Fix lỗi: Bỏ background_gradient để không cần matplotlib
    st.dataframe(
        final_df.style.format(format_config),
        use_container_width=True,
        height=600
    )