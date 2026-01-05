import streamlit as st
import pandas as pd
import io

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="AdMob LTV Analyzer V7", layout="wide", page_icon="💎")

# --- SIDEBAR: CLEAR CACHE ---
with st.sidebar:
    st.header("⚙️ Công cụ")
    st.write("Nếu upload file mới mà thấy số liệu cũ, hãy bấm nút này:")
    if st.button("🗑️ Clear Cache & Reset Data", type="primary"):
        st.cache_data.clear()
        st.rerun()

# --- HÀM LOAD DATA ---
@st.cache_data
def load_data(file):
    encodings = ['utf-8', 'utf-16', 'utf-16le', 'latin1']
    delimiters = [',', '\t', ';']
    
    df = None
    file.seek(0)
    bytes_data = file.read()
    
    for enc in encodings:
        try:
            content = bytes_data.decode(enc)
            # Tự động detect separator
            first_line = content.split('\n')[0]
            detected_sep = ','
            max_count = 0
            for d in delimiters:
                if first_line.count(d) > max_count:
                    max_count = first_line.count(d)
                    detected_sep = d
            
            df = pd.read_csv(io.StringIO(content), sep=detected_sep)
            if len(df.columns) > 1:
                break
        except:
            continue
            
    if df is None:
        st.error("❌ File hỏng hoặc sai định dạng encoding.")
        st.stop()

    df.columns = df.columns.str.strip()
    
    # Mapping cột linh hoạt
    column_mapping = {
        'Install date': ['Date', 'Cohort Date', 'install_date'],
        'Days since install': ['Day', 'Days', 'days_since_install'],
        'LTV (USD)': ['LTV', 'ltv', 'LTV ($)'],
        'Installs': ['Users', 'New Users', 'installs'],
        'Install country': ['Country', 'Region', 'install_country']
    }
    
    rename_dict = {}
    for standard_col, variations in column_mapping.items():
        if standard_col not in df.columns:
            for var in variations:
                if var in df.columns:
                    rename_dict[var] = standard_col
                    break
    if rename_dict:
        df = df.rename(columns=rename_dict)
        
    if 'Install date' in df.columns:
        df['Install date'] = pd.to_datetime(df['Install date'], errors='coerce')
        
    return df

# --- GIAO DIỆN CHÍNH ---
st.title("💎 AdMob LTV Analyzer (V7 - Flexible UI)")
st.markdown("---")

uploaded_file = st.file_uploader("Upload file admob-report.csv", type=['csv', 'txt'])

if uploaded_file:
    df = load_data(uploaded_file)
    
    # --- KHU VỰC BỘ LỌC (FILTERS) ---
    col_filter_1, col_filter_2 = st.columns(2)
    
    with col_filter_1:
        # 1. Filter Country
        country_list = sorted(df['Install country'].dropna().unique().tolist())
        selected_country = st.selectbox("🌍 Chọn Quốc Gia (Country):", ["All"] + country_list)
    
    if selected_country != "All":
        df_filtered = df[df['Install country'] == selected_country].copy()
    else:
        df_filtered = df.copy()

    # --- XỬ LÝ DATA (PIVOT) ---
    try:
        # Tổng hợp data
        df_agg = df_filtered.groupby(['Install date', 'Days since install']).agg({
            'LTV (USD)': 'mean', 
            'Installs': 'max'    
        }).reset_index()

        # Pivot: Date x Days = LTV
        df_pivot = df_agg.pivot(index='Install date', columns='Days since install', values='LTV (USD)')
        
        # Lấy cột Installs
        df_installs = df_filtered[df_filtered['Days since install'] == 0].groupby('Install date')['Installs'].sum()
        
        # Join lại
        df_final = pd.DataFrame(df_installs).join(df_pivot)
        df_final['Country'] = selected_country
        df_final = df_final.sort_index(ascending=False)
        
    except Exception as e:
        st.error(f"❌ Lỗi cấu trúc file: {e}")
        st.stop()

    # --- TÙY CHỌN HIỂN THỊ CỘT (DYNAMIC COLUMNS) ---
    all_available_days = sorted([col for col in df_final.columns if isinstance(col, (int, float))])
    default_days = [d for d in [0, 1, 2, 3] if d in all_available_days]
    
    with col_filter_2:
        # 2. Filter Columns
        selected_days = st.multiselect(
            "📊 Chọn các cột LTV muốn hiển thị:",
            options=all_available_days,
            default=default_days
        )
    
    # --- CHUẨN BỊ DATAFRAME HIỂN THỊ ---
    display_df = df_final.reset_index()
    base_cols = ['Country', 'Install date', 'Installs']
    final_cols = base_cols + selected_days
    display_df = display_df[final_cols]

    rename_map = {d: f"LTV D{d}" for d in selected_days}
    display_df = display_df.rename(columns=rename_map)

    # --- HIỂN THỊ METRICS TỔNG QUAN ---
    st.subheader(f"📈 Hiệu suất trung bình ({selected_country})")
    
    metric_cols_count = min(len(selected_days), 5)
    if metric_cols_count > 0:
        cols = st.columns(metric_cols_count)
        for i in range(metric_cols_count):
            day = selected_days[i]
            col_name = f"LTV D{day}"
            valid_rows = display_df.dropna(subset=[col_name])
            if not valid_rows.empty and valid_rows['Installs'].sum() > 0:
                w_avg = (valid_rows[col_name] * valid_rows['Installs']).sum() / valid_rows['Installs'].sum()
                cols[i].metric(f"Avg {col_name}", f"${w_avg:.5f}")
            else:
                cols[i].metric(f"Avg {col_name}", "N/A")

    st.markdown("---")
    
    # --- TÙY CHỈNH KÍCH THƯỚC BẢNG (NEW FEATURE) ---
    with st.expander("🛠️ Tùy chỉnh kích thước bảng (Table Settings)", expanded=False):
        col_setting_1, col_setting_2 = st.columns(2)
        
        with col_setting_1:
            # Checkbox để bật tắt chế độ Full Width
            use_full_width = st.checkbox("↔️ Full Width (Tràn màn hình)", value=True)
            
            custom_width = None
            if not use_full_width:
                # Nếu tắt Full Width thì hiện slider chỉnh pixel
                custom_width = st.slider("Độ rộng bảng (px)", min_value=400, max_value=2000, value=1000, step=50)
        
        with col_setting_2:
            # Slider chỉnh chiều cao
            table_height = st.slider("↕️ Chiều cao bảng (px)", min_value=200, max_value=1500, value=600, step=50)

    # --- DATA TABLE CHI TIẾT ---
    st.markdown("### 📋 Bảng chi tiết")
    
    column_config = {
        "Install date": st.column_config.DateColumn("Cohort Date", format="YYYY-MM-DD"),
        "Installs": st.column_config.NumberColumn("Users", format="%d"),
        "Country": st.column_config.TextColumn("Country"),
    }
    
    for day in selected_days:
        column_config[f"LTV D{day}"] = st.column_config.NumberColumn(
            f"LTV D{day}", 
            format="$%.5f" 
        )

    st.dataframe(
        display_df, 
        column_config=column_config, 
        hide_index=True,
        use_container_width=use_full_width, # Dynamic Width (True/False)
        width=custom_width,                 # Dynamic Width (px - chỉ nhận khi use_container_width=False)
        height=table_height                 # Dynamic Height
    )

else:
    st.info("👋 Chào sếp! Upload file CSV để bắt đầu soi LTV nhé.")