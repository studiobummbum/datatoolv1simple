import streamlit as st
import pandas as pd
import io

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="AdMob LTV & eCPM Analyzer V8.5", layout="wide", page_icon="💎")

# --- SIDEBAR: CLEAR CACHE ---
with st.sidebar:
    st.header("⚙️ Công cụ")
    st.write("Nếu upload file mới mà thấy số liệu cũ, hãy bấm nút này:")
    if st.button("🗑️ Clear Cache & Reset Data", type="primary"):
        st.cache_data.clear()
        st.rerun()

# --- HÀM LÀM SẠCH DỮ LIỆU SỐ ---
def clean_numeric_column(series):
    s = series.astype(str).str.replace('%', '', regex=False)
    s = s.str.replace('$', '', regex=False)
    s = s.str.replace(',', '', regex=False)
    return pd.to_numeric(s, errors='coerce')

# --- HÀM LOAD DATA ---
@st.cache_data
def load_data(file, file_type="cohort"):
    encodings = ['utf-8', 'utf-16', 'utf-16le', 'latin1']
    delimiters = [',', '\t', ';']
    
    df = None
    file.seek(0)
    bytes_data = file.read()
    
    for enc in encodings:
        try:
            content = bytes_data.decode(enc)
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
        return None

    df.columns = df.columns.str.strip()
    
    if file_type == "cohort":
        column_mapping = {
            'Install date': ['Date', 'Cohort Date', 'install_date'],
            'Days since install': ['Day', 'Days', 'days_since_install'],
            'LTV (USD)': ['LTV', 'ltv', 'LTV ($)'],
            'Installs': ['Users', 'New Users', 'installs'],
            'Install country': ['Country', 'Region', 'install_country']
        }
    else: 
        column_mapping = {
            'Date': ['Date', 'date', 'Time'],
            'Country': ['Country', 'Region', 'Country/Region'],
            'eCPM': ['eCPM', 'RPM', 'Observed eCPM', 'eCPM ($)', 'Observed eCPM (USD)'] 
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
        
    date_col = 'Install date' if file_type == "cohort" else 'Date'
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
    
    if file_type == "network":
        for col in df.columns:
            if col not in ['Date', 'Country']:
                sample = df[col].dropna().iloc[0] if not df[col].dropna().empty else ""
                if isinstance(sample, str):
                    df[col] = clean_numeric_column(df[col])
                    
    return df

# --- GIAO DIỆN CHÍNH ---
st.title("💎 AdMob LTV & eCPM Analyzer (V8.5)")
st.markdown("---")

col_upload_1, col_upload_2 = st.columns(2)

with col_upload_1:
    st.subheader("1. File Cohort (LTV)")
    cohort_file = st.file_uploader("Upload file Cohort Report", type=['csv', 'txt'], key="cohort")

with col_upload_2:
    st.subheader("2. File Network (eCPM)")
    network_file = st.file_uploader("Upload file Network Report", type=['csv', 'txt'], key="network")

if cohort_file:
    # 1. XỬ LÝ FILE COHORT
    df_cohort = load_data(cohort_file, file_type="cohort")
    
    if df_cohort is None:
        st.error("❌ File Cohort lỗi encoding.")
        st.stop()
        
    col_filter_1, col_filter_2 = st.columns(2)
    
    with col_filter_1:
        country_list = sorted(df_cohort['Install country'].dropna().unique().tolist())
        selected_country = st.selectbox("🌍 Chọn Quốc Gia (Country):", ["All"] + country_list)
    
    if selected_country != "All":
        df_filtered = df_cohort[df_cohort['Install country'] == selected_country].copy()
    else:
        df_filtered = df_cohort.copy()

    try:
        df_agg = df_filtered.groupby(['Install date', 'Days since install']).agg({
            'LTV (USD)': 'mean', 
            'Installs': 'max'    
        }).reset_index()

        df_pivot = df_agg.pivot(index='Install date', columns='Days since install', values='LTV (USD)')
        df_installs = df_filtered[df_filtered['Days since install'] == 0].groupby('Install date')['Installs'].sum()
        
        # Base DataFrame (Index là Install date)
        df_final = pd.DataFrame(df_installs).join(df_pivot)
        df_final['Country'] = selected_country
        
    except Exception as e:
        st.error(f"❌ Lỗi cấu trúc file Cohort: {e}")
        st.stop()

    # 2. XỬ LÝ FILE NETWORK
    available_network_metrics = []
    
    if network_file:
        df_network = load_data(network_file, file_type="network")
        
        if df_network is not None and 'eCPM' in df_network.columns:
            has_country_col = 'Country' in df_network.columns
            
            if selected_country != "All" and has_country_col:
                df_net_filtered = df_network[df_network['Country'] == selected_country].copy()
            else:
                df_net_filtered = df_network.copy()
                if selected_country != "All" and not has_country_col:
                    st.warning(f"⚠️ Lưu ý: Dữ liệu Network là Global (chung), đang ghép vào Cohort của {selected_country}.")

            numeric_cols = df_net_filtered.select_dtypes(include=['float64', 'int64']).columns.tolist()
            exclude_cols = ['Date', 'Country', 'eCPM'] 
            available_network_metrics = [c for c in numeric_cols if c not in exclude_cols]

    # --- TÙY CHỌN HIỂN THỊ CỘT ---
    all_available_days = sorted([col for col in df_final.columns if isinstance(col, (int, float))])
    default_days = [d for d in [0, 1, 3, 7] if d in all_available_days]
    
    with col_filter_2:
        selected_days = st.multiselect(
            "📊 Chọn cột LTV (Days):",
            options=all_available_days,
            default=default_days
        )
        
        selected_net_metrics = []
        if available_network_metrics:
            selected_net_metrics = st.multiselect(
                "📈 Chọn thêm chỉ số Network (Optional):",
                options=available_network_metrics,
                default=[] 
            )

    # --- JOIN DATA NETWORK VÀO COHORT ---
    if network_file and df_network is not None:
        agg_dict = {'eCPM': 'mean'} 
        sum_keywords = ['earnings', 'impressions', 'clicks', 'requests', 'bids', 'users', 'viewers']
        
        for metric in selected_net_metrics:
            metric_lower = metric.lower()
            if any(k in metric_lower for k in sum_keywords) and 'rate' not in metric_lower and 'ctr' not in metric_lower:
                agg_dict[metric] = 'sum'
            else:
                agg_dict[metric] = 'mean' 
        
        df_net_grouped = df_net_filtered.groupby('Date').agg(agg_dict)
        
        # Merge an toàn
        df_final = df_final.join(df_net_grouped, how='left')

    # Sort lại theo ngày giảm dần
    df_final = df_final.sort_index(ascending=False)
    
    # --- CHUẨN BỊ DATAFRAME HIỂN THỊ ---
    display_df = df_final.reset_index()
    
    if 'index' in display_df.columns:
        display_df = display_df.rename(columns={'index': 'Install date'})
    
    base_cols = ['Country', 'Install date', 'Installs']
    
    network_cols_to_show = []
    if 'eCPM' in display_df.columns:
        network_cols_to_show.append('eCPM')
    
    valid_selected_metrics = [m for m in selected_net_metrics if m in display_df.columns]
    network_cols_to_show.extend(valid_selected_metrics)
    
    final_cols = base_cols + network_cols_to_show + selected_days
    final_cols = [c for c in final_cols if c in display_df.columns]
    
    display_df = display_df[final_cols].copy()

    rename_map = {d: f"LTV D{d}" for d in selected_days}
    display_df = display_df.rename(columns=rename_map)

    # --- HIỂN THỊ METRICS TỔNG QUAN ---
    st.subheader(f"📈 Hiệu suất trung bình ({selected_country})")
    
    total_metrics = len(selected_days) + len(network_cols_to_show)
    cols = st.columns(min(total_metrics + 1, 6))
    
    col_idx = 0
    
    for net_metric in network_cols_to_show:
        if col_idx < len(cols):
            avg_val = display_df[net_metric].mean()
            if "rate" in net_metric.lower() or "ctr" in net_metric.lower():
                val_str = f"{avg_val:.2f}%"
            elif "earnings" in net_metric.lower() or "usd" in net_metric.lower() or "ecpm" in net_metric.lower():
                val_str = f"${avg_val:.2f}"
            else:
                val_str = f"{avg_val:,.0f}"
                
            cols[col_idx].metric(f"Avg {net_metric}", val_str)
            col_idx += 1

    for day in selected_days:
        if col_idx < len(cols):
            col_name = f"LTV D{day}"
            valid_rows = display_df.dropna(subset=[col_name])
            if not valid_rows.empty and valid_rows['Installs'].sum() > 0:
                w_avg = (valid_rows[col_name] * valid_rows['Installs']).sum() / valid_rows['Installs'].sum()
                cols[col_idx].metric(f"Avg {col_name}", f"${w_avg:.5f}")
            col_idx += 1

    st.markdown("---")
    
    # --- TÙY CHỈNH KÍCH THƯỚC BẢNG ---
    with st.expander("🛠️ Tùy chỉnh kích thước bảng (Table Settings)", expanded=False):
        col_setting_1, col_setting_2 = st.columns(2)
        with col_setting_1:
            use_full_width = st.checkbox("↔️ Full Width (Tràn màn hình)", value=True)
            custom_width = None
            if not use_full_width:
                custom_width = st.slider("Độ rộng bảng (px)", 400, 2000, 1000, 50)
        with col_setting_2:
            table_height = st.slider("↕️ Chiều cao bảng (px)", 200, 1500, 600, 50)

    # --- DATA TABLE CHI TIẾT ---
    st.markdown("### 📋 Bảng chi tiết")
    
    column_config = {
        "Install date": st.column_config.DateColumn("Date", format="YYYY-MM-DD", width="small"),
        "Installs": st.column_config.NumberColumn("Users", format="%d", width="small"),
        "Country": st.column_config.TextColumn("Country", width="small"),
    }
    
    if 'eCPM' in display_df.columns:
        column_config["eCPM"] = st.column_config.NumberColumn("eCPM", format="$%.2f", width="small")

    for metric in valid_selected_metrics:
        metric_lower = metric.lower()
        if "rate" in metric_lower or "ctr" in metric_lower:
             column_config[metric] = st.column_config.NumberColumn(metric, format="%.2f%%", width="small")
        elif "earnings" in metric_lower or "usd" in metric_lower:
             column_config[metric] = st.column_config.NumberColumn(metric, format="$%.2f", width="medium") 
        else:
             column_config[metric] = st.column_config.NumberColumn(metric, format="%d", width="small")

    for day in selected_days:
        column_config[f"LTV D{day}"] = st.column_config.NumberColumn(
            f"LTV D{day}", 
            format="$%.5f",
            width="small" 
        )

    st.dataframe(
        display_df, 
        column_config=column_config, 
        hide_index=True,
        use_container_width=use_full_width,
        width=custom_width,
        height=table_height
    )

    # =================================================================
    # --- [NEW FEATURE V8.5] BIỂU ĐỒ TRỰC QUAN ---
    # =================================================================
    st.markdown("---")
    st.subheader("📊 Biểu đồ xu hướng (Trend Charts)")
    
    # Chuẩn bị dữ liệu cho biểu đồ (cần index là Date để vẽ trục X)
    chart_df = display_df.set_index('Install date').sort_index()
    
    # Lấy danh sách các cột số có thể vẽ được (trừ Country)
    plottable_cols = [c for c in chart_df.columns if c != 'Country']
    
    # Mặc định chọn một vài chỉ số quan trọng nếu có
    default_plot = []
    if 'eCPM' in plottable_cols: default_plot.append('eCPM')
    if f"LTV D{default_days[0]}" in plottable_cols: default_plot.append(f"LTV D{default_days[0]}")
    
    # UI chọn Metric để vẽ
    col_chart_opt_1, col_chart_opt_2 = st.columns([3, 1])
    
    with col_chart_opt_1:
        selected_plot_metrics = st.multiselect(
            "Chọn chỉ số để vẽ biểu đồ (Metrics to plot):",
            options=plottable_cols,
            default=default_plot
        )
    
    with col_chart_opt_2:
        chart_type = st.radio("Loại biểu đồ:", ["Line Chart", "Area Chart", "Bar Chart"], horizontal=True)

    if selected_plot_metrics:
        # Vẽ biểu đồ
        if chart_type == "Line Chart":
            st.line_chart(chart_df[selected_plot_metrics])
        elif chart_type == "Area Chart":
            st.area_chart(chart_df[selected_plot_metrics])
        else:
            st.bar_chart(chart_df[selected_plot_metrics])
            
        st.caption(f"💡 Tip: Sếp nên chọn các chỉ số có cùng đơn vị (ví dụ: cùng là $ hoặc cùng là %) để biểu đồ dễ nhìn hơn.")
    else:
        st.info("👈 Vui lòng chọn ít nhất một chỉ số để hiển thị biểu đồ.")

else:
    st.info("👋 Chào sếp! Vui lòng upload file Cohort trước.")