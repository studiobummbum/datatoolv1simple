import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="AdMob LTV Report V3", layout="wide", page_icon="🛡️")

# --- HÀM LOAD DATA ---
@st.cache_data
def load_data(file):
    try:
        df = pd.read_csv(file)
    except:
        file.seek(0)
        df = pd.read_csv(file, encoding='latin1')
    
    # 1. Chuẩn hóa tên cột (xóa khoảng trắng)
    df.columns = df.columns.str.strip()
    
    # 2. AUTO-MAPPING: Tự động đổi tên cột về chuẩn nếu tên khác
    # Dictionary map: {Tên chuẩn: [Các tên có thể gặp]}
    column_mapping = {
        'Install date': ['Date', 'Cohort Date', 'install_date'],
        'Days since install': ['Day', 'Days', 'days_since_install'],
        'LTV (USD)': ['LTV', 'ltv', 'LTV ($)'],
        'Installs': ['Users', 'New Users', 'installs'],
        'Install country': ['Country', 'Region', 'install_country']
    }
    
    # Duyệt qua map để rename
    rename_dict = {}
    for standard_col, variations in column_mapping.items():
        if standard_col not in df.columns: # Nếu chưa có tên chuẩn
            for var in variations:
                if var in df.columns: # Nếu tìm thấy biến thể
                    rename_dict[var] = standard_col
                    break
    
    if rename_dict:
        df = df.rename(columns=rename_dict)
        
    # 3. Convert Date
    if 'Install date' in df.columns:
        df['Install date'] = pd.to_datetime(df['Install date'], errors='coerce')
        
    return df

# --- GIAO DIỆN ---
st.title("🛡️ AdMob LTV Analyzer (V3 - Debug Mode)")
st.markdown("Phiên bản này tự động sửa tên cột và báo lỗi chi tiết nếu file không đúng format.")

uploaded_file = st.file_uploader("Upload file admob-report.csv", type=['csv'])

if uploaded_file:
    df = load_data(uploaded_file)
    
    # --- DEBUG: CHECK CỘT ---
    required_columns = ['Install date', 'Days since install', 'LTV (USD)', 'Installs']
    missing_cols = [col for col in required_columns if col not in df.columns]
    
    if missing_cols:
        st.error(f"❌ **LỖI FILE: Thiếu các cột bắt buộc sau:** {missing_cols}")
        st.warning("⚠️ **Các cột hiện có trong file của sếp:**")
        st.code(list(df.columns))
        st.info("💡 Sếp kiểm tra lại file CSV hoặc đổi tên cột trong file cho khớp nhé.")
        st.stop() # Dừng chương trình tại đây để không bị crash
        
    # --- NẾU ĐỦ CỘT THÌ CHẠY TIẾP ---
    
    # 1. BỘ LỌC QUỐC GIA
    if 'Install country' in df.columns:
        country_list = sorted(df['Install country'].dropna().unique().tolist())
        selected_country = st.selectbox("🌍 Chọn Quốc Gia (Country):", ["All"] + country_list)
        
        if selected_country != "All":
            df_country = df[df['Install country'] == selected_country].copy()
        else:
            df_country = df.copy()
    else:
        st.warning("⚠️ Không tìm thấy cột Quốc gia (Install country). Đang hiển thị toàn bộ data.")
        df_country = df.copy()
        selected_country = "All"
    
    # 2. XỬ LÝ PIVOT DATA
    try:
        # Pivot LTV
        df_pivot = df_country.pivot_table(
            index='Install date', 
            columns='Days since install', 
            values='LTV (USD)',
            aggfunc='max'
        )
        
        # Lấy cột Installs (Lấy ở ngày 0)
        df_installs = df_country[df_country['Days since install'] == 0][['Install date', 'Installs']]
        # Group by date để tránh duplicate index nếu data bị lỗi
        df_installs = df_installs.groupby('Install date')['Installs'].sum()
        
        # Merge
        df_final = pd.DataFrame(df_installs).join(df_pivot, how='inner')
        df_final = df_final.sort_index(ascending=False)
        
    except Exception as e:
        st.error(f"❌ Lỗi khi xử lý dữ liệu: {e}")
        st.stop()

    # 3. HIỂN THỊ METRICS
    st.subheader(f"📊 Hiệu suất LTV - {selected_country}")
    
    recent_df = df_final.head(30)
    cols = st.columns(4)
    metrics_to_show = [0, 1, 3, 7, 14, 30]
    display_metrics = metrics_to_show[:4] 
    
    for i, d in enumerate(display_metrics):
        if d in recent_df.columns:
            valid_rows = recent_df.dropna(subset=[d])
            if not valid_rows.empty and valid_rows['Installs'].sum() > 0:
                w_avg = (valid_rows[d] * valid_rows['Installs']).sum() / valid_rows['Installs'].sum()
                cols[i].metric(f"Avg LTV D{d}", f"${w_avg:.4f}")
            else:
                cols[i].metric(f"Avg LTV D{d}", "N/A")
        else:
             cols[i].metric(f"Avg LTV D{d}", "No Data")

    # 4. BIỂU ĐỒ
    st.subheader("📈 Xu hướng LTV theo Cohort")
    fig = go.Figure()
    colors = {0: '#9ca3af', 1: '#3b82f6', 3: '#f59e0b', 7: '#10b981', 14: '#8b5cf6', 30: '#ef4444'}
    
    for d in metrics_to_show:
        if d in df_final.columns:
            fig.add_trace(go.Scatter(
                x=df_final.index, 
                y=df_final[d], 
                mode='lines+markers',
                name=f'LTV D{d}',
                line=dict(color=colors.get(d, 'black'), width=2 if d==0 else 3),
                hovertemplate=f'Date: %{{x|%Y-%m-%d}}<br>LTV D{d}: $%{{y:.4f}}<extra></extra>'
            ))

    fig.update_layout(height=500, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    # 5. DATA TABLE
    st.subheader("📋 Bảng chi tiết")
    display_df = df_final.reset_index()
    
    column_config = {
        "Install date": st.column_config.DateColumn("Cohort Date", format="YYYY-MM-DD"),
        "Installs": st.column_config.NumberColumn("Users", format="%d"),
    }
    for col in display_df.columns:
        if isinstance(col, int) or (isinstance(col, str) and col.isdigit()):
            column_config[col] = st.column_config.NumberColumn(f"D{col}", format="$%.4f")

    st.dataframe(display_df, column_config=column_config, hide_index=True, use_container_width=True)

else:
    st.info("Sếp upload file CSV đi ạ. Em đang đợi đây...")