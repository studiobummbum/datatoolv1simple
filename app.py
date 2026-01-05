import streamlit as st
import pandas as pd
import io

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="AdMob Cohort Analyzer Pro", layout="wide")

st.title("💰 AdMob Cohort LTV Analyzer (V3.4 - Bulletproof)")
st.markdown("""
<style>
    .stAlert { padding: 10px; border-radius: 5px; }
    .success { background-color: #d4edda; color: #155724; }
</style>
""", unsafe_allow_html=True)

st.info("💡 Upload file `admob-report.csv`. Hệ thống tự động nhận diện header và encoding.")

# --- HÀM XỬ LÝ DATA ---
def load_data(uploaded_file):
    # Danh sách encoding hay gặp của AdMob/Excel
    encodings = ['utf-8', 'utf-16', 'latin1', 'iso-8859-1', 'cp1252']
    
    df = None
    used_encoding = None
    header_row = 0
    
    # 1. Thử đọc với các encoding và vị trí header khác nhau
    # AdMob thường có 2 dòng đầu là Title, dòng 3 mới là Header (skiprows=2)
    # Nhưng file sếp gửi có thể Header nằm ngay dòng 0
    
    possible_skiprows = [0, 2] # Ưu tiên dòng 0 trước theo file mẫu sếp gửi
    
    for skip in possible_skiprows:
        for enc in encodings:
            try:
                uploaded_file.seek(0)
                temp_df = pd.read_csv(uploaded_file, skiprows=skip, encoding=enc, on_bad_lines='skip')
                
                # Check nhanh xem có cột nào trông giống Date hoặc Country không
                col_str = " ".join([str(c).lower() for c in temp_df.columns])
                if 'date' in col_str and ('country' in col_str or 'install' in col_str):
                    df = temp_df
                    used_encoding = enc
                    header_row = skip
                    break
            except:
                continue
        if df is not None:
            break
            
    return df, used_encoding, header_row

# --- UI CHÍNH ---
uploaded_file = st.file_uploader("📂 Kéo thả file CSV vào đây sếp ơi", type=['csv'])

if uploaded_file is not None:
    with st.spinner('Đang soi data của sếp...'):
        df, encoding, header_row = load_data(uploaded_file)

    if df is None:
        st.error("❌ Em chịu thua! Không đọc được file. Sếp check lại xem có phải CSV chuẩn không?")
        st.stop()

    # --- XỬ LÝ TÊN CỘT (MAPPING) ---
    # Chuẩn hóa tên cột hiện tại về chữ thường, bỏ khoảng trắng thừa
    df.columns = df.columns.astype(str).str.strip()
    
    # Dictionary từ khóa để map (Ưu tiên từ khóa dài trước)
    # File sếp: "Install date", "Install country", "Days since install", "LTV (USD)"
    mapping_rules = {
        'Date': ['install date', 'date', 'ngày'],
        'Country': ['install country', 'country', 'quốc gia', 'region'],
        'Day': ['days since install', 'day', 'ngày kể từ'],
        'LTV': ['ltv', 'revenue', 'doanh thu', 'earnings'],
        'Installs': ['installs', 'lượt cài đặt', 'cài đặt']
    }

    final_rename_map = {}
    found_cols = []

    # Logic tìm cột thông minh
    for target_name, keywords in mapping_rules.items():
        match_col = None
        for col in df.columns:
            # So sánh case-insensitive
            if any(kw in col.lower() for kw in keywords):
                # Logic loại trừ đặc biệt cho cột Installs (tránh nhầm với Install Date)
                if target_name == 'Installs' and ('date' in col.lower() or 'day' in col.lower() or 'country' in col.lower()):
                    continue
                match_col = col
                break
        
        if match_col:
            final_rename_map[match_col] = target_name
            found_cols.append(target_name)

    # --- HIỂN THỊ TRẠNG THÁI MAPPING (DEBUG) ---
    with st.expander("🕵️‍♂️ Debug: Em đã map các cột như thế này (Sếp check nhé)"):
        st.write(f"**Encoding:** `{encoding}` | **Header Row:** `{header_row}`")
        st.json(final_rename_map)
        st.write("Data gốc 5 dòng đầu:")
        st.dataframe(df.head())

    # Kiểm tra cột bắt buộc
    required_cols = ['Date', 'Day', 'LTV']
    missing = [col for col in required_cols if col not in found_cols]
    
    if missing:
        st.error(f"❌ Toang rồi sếp ơi! Em không tìm thấy cột: {', '.join(missing)}")
        st.stop()

    # --- ÁP DỤNG RENAME ---
    df = df.rename(columns=final_rename_map)

    # --- CLEAN DATA TYPES ---
    try:
        # 1. Date
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.date
        df = df.dropna(subset=['Date'])

        # 2. LTV & Installs (Xử lý dấu phẩy, dấu $)
        cols_to_numeric = ['LTV']
        if 'Installs' in df.columns:
            cols_to_numeric.append('Installs')
        
        for col in cols_to_numeric:
            if df[col].dtype == object:
                df[col] = df[col].astype(str).str.replace(r'[$,₫a-zA-Z()]', '', regex=True)
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        if 'Installs' not in df.columns:
            df['Installs'] = 1 # Fallback nếu không có cột install

    except Exception as e:
        st.error(f"❌ Lỗi khi clean data: {e}")
        st.stop()

    # --- PIVOT TABLE (COHORT) ---
    # Chỉ lấy các ngày quan trọng
    target_days = [0, 1, 3, 7, 14, 28, 30, 60]
    df_filtered = df[df['Day'].isin(target_days)].copy()

    # Group by để tính tổng LTV theo Date và Country
    # Lưu ý: File sếp là dạng flat (mỗi dòng 1 ngày), cần pivot
    
    # Nếu không có cột Country (trường hợp xấu nhất), tạo cột All
    if 'Country' not in df.columns:
        df_filtered['Country'] = 'Global'

    # Pivot: Index=(Date, Country, Installs), Col=Day, Val=LTV
    # Cần aggregate Installs theo Date+Country trước (vì Installs lặp lại ở mỗi dòng Day 0,1,2...)
    # Logic chuẩn: Lấy Installs tại Day 0 làm gốc cho Cohort đó
    
    df_installs = df[df['Day'] == 0][['Date', 'Country', 'Installs']].drop_duplicates()
    
    # Pivot LTV
    df_ltv = df_filtered.pivot_table(
        index=['Date', 'Country'],
        columns='Day',
        values='LTV',
        aggfunc='sum'
    ).reset_index()
    
    # Merge Installs vào bảng LTV
    final_df = pd.merge(df_installs, df_ltv, on=['Date', 'Country'], how='left')
    
    # Đổi tên cột LTV D...
    new_cols = {d: f'LTV D{d}' for d in target_days if d in final_df.columns}
    final_df = final_df.rename(columns=new_cols)
    
    # Fill NaN = 0
    final_df = final_df.fillna(0)
    
    # Sắp xếp
    final_df = final_df.sort_values(by='Date', ascending=False)

    # --- HIỂN THỊ KẾT QUẢ ---
    st.success("✅ Xử lý xong! Mời sếp xơi.")
    
    # Format hiển thị
    format_config = {'Installs': '{:,.0f}'}
    ltv_cols = [c for c in final_df.columns if 'LTV' in c]
    for c in ltv_cols:
        format_config[c] = '${:.4f}'

    st.dataframe(
        final_df.style.format(format_config)
        .background_gradient(cmap='Greens', subset=ltv_cols),
        use_container_width=True,
        height=600
    )
    
    # Tính tổng ARPU Global
    st.subheader("📈 Tổng hợp ARPU (Weighted Average)")
    total_installs = final_df['Installs'].sum()
    if total_installs > 0:
        avg_data = {}
        for col in ltv_cols:
            # Tính tổng doanh thu của cột đó / tổng install
            # Lưu ý: Đây là tính trung bình cộng gia quyền
            revenue_col = (final_df[col] * final_df['Installs']).sum()
            arpu = revenue_col / total_installs
            avg_data[col] = arpu
            
        st.metric("Total Installs", f"{total_installs:,.0f}")
        st.dataframe(pd.DataFrame([avg_data]).style.format('${:.4f}'))