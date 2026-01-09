import streamlit as st
import pandas as pd
import numpy as np
import io
import re
from scipy.optimize import curve_fit
import plotly.graph_objects as go # Import thêm thư viện Plotly

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="AdMob Super Tool V9.8 - Pro Edition", layout="wide", page_icon="💎")

# ==============================================================================
# 1. KHỞI TẠO SESSION STATE (KHO CHỨA DỮ LIỆU)
# ==============================================================================
# --- State cho Tab 1 (Cũ) ---
if 'tab1_cohort_df' not in st.session_state:
    st.session_state.tab1_cohort_df = None
if 'tab1_network_df' not in st.session_state:
    st.session_state.tab1_network_df = None

# --- State cho Tab 2 (Pending) ---
if 'tab2_data_list' not in st.session_state:
    st.session_state.tab2_data_list = [] 
if 'tab2_names' not in st.session_state:
    st.session_state.tab2_names = {} 

# ==============================================================================
# 2. CÁC HÀM XỬ LÝ DỮ LIỆU & TOÁN HỌC (HELPER FUNCTIONS)
# ==============================================================================

# --- [TAB 1] HÀM LÀM SẠCH DỮ LIỆU SỐ ---
def clean_numeric_column(series):
    s = series.astype(str)
    s = s.str.replace('$', '', regex=False)
    s = s.str.replace(',', '', regex=False)
    s = s.str.replace('%', '', regex=False)
    return pd.to_numeric(s, errors='coerce')

# --- [TAB 1] HÀM LOAD DATA CƠ BẢN ---
@st.cache_data
def load_data(file_content, file_name, file_type="cohort"):
    encodings = ['utf-8', 'utf-16', 'utf-16le', 'latin1']
    delimiters = [',', '\t', ';']
    
    df = None
    for enc in encodings:
        try:
            content = file_content.decode(enc)
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
            
    if df is None: return None

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
        percent_keywords = ['rate', 'ctr', 'match', 'show', 'fill', '%']
        for col in df.columns:
            if col not in ['Date', 'Country']:
                df[col] = clean_numeric_column(df[col])
                col_lower = col.lower()
                if any(k in col_lower for k in percent_keywords) and '(%)' not in col and '%' not in col:
                     df = df.rename(columns={col: f"{col} (%)"})

    return df

# ==============================================================================
# SIDEBAR NAVIGATION
# ==============================================================================
with st.sidebar:
    st.title("💎 Monet Tool V9.8")
    st.caption("Fullstack Edition - Plotly Upgrade")
    
    st.header("📂 Menu")
    selected_tab = st.radio(
        "Chọn tính năng:",
        ["📊 LTV & Ecpm (Tab 1)", "🔮 LTV Projection (Pending)"],
        index=0
    )
    
    st.markdown("---")
    st.header("⚙️ System")
    if st.button("🗑️ Hard Reset All Data", type="primary"):
        for key in st.session_state.keys():
            del st.session_state[key]
        st.cache_data.clear()
        st.rerun()

# ==============================================================================
# MAIN CONTENT AREA
# ==============================================================================

# ------------------------------------------------------------------------------
# TAB 1: LTV & ECPM
# ------------------------------------------------------------------------------
if selected_tab == "📊 LTV & Ecpm (Tab 1)":
    st.title("📊 Phân tích LTV & eCPM")
    
    # --- KHU VỰC UPLOAD ---
    with st.expander("📂 Upload Data Area", expanded=True):
        col_up1, col_up2 = st.columns(2)
        
        # 1. Upload Cohort
        with col_up1:
            st.subheader("1. File Cohort")
            if st.session_state.tab1_cohort_df is not None:
                st.success("✅ Dữ liệu Cohort đang được lưu.")
                if st.button("❌ Xóa Cohort Data", key="clear_cohort"):
                    st.session_state.tab1_cohort_df = None
                    st.rerun()
            else:
                cohort_file = st.file_uploader("Upload Cohort Report", type=['csv', 'txt'], key="u_cohort")
                if cohort_file:
                    bytes_data = cohort_file.read()
                    df_processed = load_data(bytes_data, cohort_file.name, "cohort")
                    if df_processed is not None:
                        st.session_state.tab1_cohort_df = df_processed
                        st.rerun()

        # 2. Upload Network
        with col_up2:
            st.subheader("2. File Network")
            if st.session_state.tab1_network_df is not None:
                st.success("✅ Dữ liệu Network đang được lưu.")
                if st.button("❌ Xóa Network Data", key="clear_network"):
                    st.session_state.tab1_network_df = None
                    st.rerun()
            else:
                network_file = st.file_uploader("Upload Network Report", type=['csv', 'txt'], key="u_network")
                if network_file:
                    bytes_data = network_file.read()
                    df_processed = load_data(bytes_data, network_file.name, "network")
                    if df_processed is not None:
                        st.session_state.tab1_network_df = df_processed
                        st.rerun()

    st.markdown("---")

    # --- XỬ LÝ VÀ HIỂN THỊ DỮ LIỆU ---
    df_cohort = st.session_state.tab1_cohort_df
    df_network = st.session_state.tab1_network_df

    if df_cohort is not None:
        col_filter_1, col_filter_2 = st.columns(2)
        
        with col_filter_1:
            country_list = sorted(df_cohort['Install country'].dropna().unique().tolist())
            selected_country = st.selectbox("🌍 Chọn Quốc Gia (Country):", ["All"] + country_list, key="country_select_tab1")
        
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
            
            df_final = pd.DataFrame(df_installs).join(df_pivot)
            df_final['Country'] = selected_country
            
        except Exception as e:
            st.error(f"❌ Lỗi xử lý dữ liệu: {e}")
            st.stop()

        available_network_metrics = []
        if df_network is not None and 'eCPM' in df_network.columns:
             has_country_col = 'Country' in df_network.columns
             if selected_country != "All" and has_country_col:
                 df_net_filtered = df_network[df_network['Country'] == selected_country].copy()
             else:
                 df_net_filtered = df_network.copy()
            
             numeric_cols = df_net_filtered.select_dtypes(include=['float64', 'int64']).columns.tolist()
             exclude_cols = ['Date', 'Country', 'eCPM'] 
             available_network_metrics = [c for c in numeric_cols if c not in exclude_cols]
             
             agg_dict = {'eCPM': 'mean'}
             sum_keywords = ['earnings', 'impressions', 'clicks', 'requests', 'bids', 'users', 'revenue']
             
             for metric in available_network_metrics:
                 metric_lower = metric.lower()
                 if any(k in metric_lower for k in sum_keywords) and 'rate' not in metric_lower and 'ctr' not in metric_lower:
                     agg_dict[metric] = 'sum'
                 else:
                     agg_dict[metric] = 'mean'
                 
             df_net_grouped = df_net_filtered.groupby('Date').agg(agg_dict)
             df_final = df_final.join(df_net_grouped, how='left')

        df_final = df_final.sort_index(ascending=False)
        display_df = df_final.reset_index().rename(columns={'index': 'Install date'})

        all_days = sorted([c for c in df_final.columns if isinstance(c, (int, float))])
        default_days = [d for d in [0, 1, 3, 7] if d in all_days]
        
        with col_filter_2:
            selected_days = st.multiselect("📊 Chọn cột LTV (Bảng):", all_days, default=default_days)
            selected_net_metrics = []
            if available_network_metrics:
                selected_net_metrics = st.multiselect("📈 Chỉ số Network (Bảng):", available_network_metrics)

        cols_to_show = ['Install date', 'Installs', 'Country']
        if 'eCPM' in display_df.columns: cols_to_show.append('eCPM')
        cols_to_show.extend(selected_net_metrics)
        cols_to_show.extend(selected_days)
        
        final_view = display_df[[c for c in cols_to_show if c in display_df.columns]].copy()
        
        rename_map = {d: f"LTV D{d}" for d in selected_days}
        final_view = final_view.rename(columns=rename_map)

        st.subheader("📋 Bảng dữ liệu tổng hợp")
        st.dataframe(final_view, use_container_width=True, height=500, hide_index=True)
        
        # --- KHU VỰC CHART OPTIONS (UPDATED FOR PLOTLY) ---
        st.markdown("---")
        st.subheader("📈 Biểu đồ trực quan (Interactive)")
        
        potential_metrics = [c for c in final_view.columns if c not in ['Install date', 'Country', 'Installs']]
        selected_plot_metrics = st.multiselect(
            "👁️ Chọn chỉ số hiển thị trên Chart:", 
            potential_metrics,
            default=potential_metrics
        )

        if selected_plot_metrics:
            # Chuyển đổi dữ liệu để vẽ
            chart_data = final_view.sort_values('Install date')
            
            # Tạo Figure Plotly
            fig = go.Figure()

            # Loop qua từng metric được chọn và thêm vào biểu đồ
            for metric in selected_plot_metrics:
                fig.add_trace(go.Scatter(
                    x=chart_data['Install date'], 
                    y=chart_data[metric],
                    mode='lines+markers', # Hiển thị cả đường và điểm
                    name=metric,
                    hovertemplate='%{y:.2f}' # Format số hiển thị khi hover (2 số thập phân)
                ))

            # Cấu hình Layout để hiển thị tooltip unified (Quan trọng!)
            fig.update_layout(
                hovermode="x unified", # Đây là chìa khóa: Hiển thị tất cả metric cùng lúc trên trục X
                xaxis_title="Date",
                yaxis_title="Value",
                legend=dict(
                    orientation="h", # Legend nằm ngang
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                ),
                height=500,
                margin=dict(l=20, r=20, t=50, b=20)
            )
            
            # Render biểu đồ
            st.plotly_chart(fig, use_container_width=True)
            
        else:
            st.warning("⚠️ Vui lòng chọn ít nhất 1 chỉ số để vẽ biểu đồ.")

    else:
        st.info("👈 Vui lòng upload file Cohort ở phần trên để bắt đầu phân tích.")

# ------------------------------------------------------------------------------
# TAB 2: PENDING
# ------------------------------------------------------------------------------
elif selected_tab == "🔮 LTV Projection (Pending)":
    st.title("🔮 LTV Projection")
    st.markdown("""
    <div style="padding: 20px; background-color: #f0f9ff; border-radius: 10px; border: 1px solid #bae6fd;">
        <h3 style="color: #0284c7; margin-top: 0;">🚧 Tính năng đang được bảo trì</h3>
        <p style="color: #334155;">
            Phần dự phóng LTV (Projection) đang được tạm ẩn để tối ưu hóa trải nghiệm người dùng. 
            Sếp vui lòng quay lại sử dụng <b>Tab 1</b> để phân tích dữ liệu thực tế trước nhé!
        </p>
    </div>
    """, unsafe_allow_html=True)

# --- FOOTER ---
st.markdown("---")
st.markdown('<div style="text-align: center; color: #9CA3AF;">Built by Mobile App Monetization Expert | Powered by Streamlit</div>', unsafe_allow_html=True)