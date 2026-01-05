import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import io

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="AdMob LTV Report V4 - Ultimate Fix", layout="wide", page_icon="🛡️")

# --- HÀM LOAD DATA (PHIÊN BẢN SIÊU TRÂU BÒ) ---
@st.cache_data
def load_data(file):
    # Danh sách các encoding phổ biến có thể gặp
    encodings = ['utf-8', 'utf-16', 'utf-16le', 'latin1', 'cp1252']
    delimiters = [',', '\t', ';'] # Phẩy, Tab, Chấm phẩy
    
    df = None
    error_log = []

    # Reset file pointer về đầu
    file.seek(0)
    bytes_data = file.read()
    
    # Thử từng encoding
    for enc in encodings:
        try:
            # Decode bytes thành string để check delimiter
            content = bytes_data.decode(enc)
            
            # Auto-detect delimiter bằng cách đếm dòng đầu tiên
            first_line = content.split('\n')[0]
            detected_sep = ',' # Mặc định
            
            # Logic đơn giản: cái nào xuất hiện nhiều nhất ở dòng đầu thì là separator
            max_count = 0
            for d in delimiters:
                if first_line.count(d) > max_count:
                    max_count = first_line.count(d)
                    detected_sep = d
            
            # Đọc dữ liệu với encoding và separator tìm được
            df = pd.read_csv(io.StringIO(content), sep=detected_sep)
            
            # Nếu đọc được và có ít nhất 1 cột thì break ngay
            if len(df.columns) > 1:
                break
        except Exception as e:
            error_log.append(f"Thử {enc} thất bại: {str(e)}")
            continue
            
    if df is None:
        st.error("❌ Không thể đọc file với mọi loại encoding. File có thể bị hỏng.")
        st.stop()

    # --- XỬ LÝ DATA SAU KHI ĐỌC ĐƯỢC ---
    
    # 1. Chuẩn hóa tên cột (xóa khoảng trắng thừa)
    df.columns = df.columns.str.strip()
    
    # 2. AUTO-MAPPING: Tự động đổi tên cột về chuẩn
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
        
    # 3. Convert Date
    if 'Install date' in df.columns:
        df['Install date'] = pd.to_datetime(df['Install date'], errors='coerce')
        
    return df

# --- GIAO DIỆN ---
st.title("🛡️ AdMob LTV Analyzer (V4 - Encoding Fix)")
st.markdown("Phiên bản này chấp hết các loại file UTF-16, Tab-separated hay Comma-separated.")

uploaded_file = st.file_uploader("Upload file admob-report.csv", type=['csv', 'txt'])

if uploaded_file:
    df = load_data(uploaded_file)
    
    # --- DEBUG: CHECK CỘT ---
    required_columns = ['Install date', 'Days since install', 'LTV (USD)', 'Installs']
    missing_cols = [col for col in required_columns if col not in df.columns]
    
    if missing_cols:
        st.error(f"❌ **LỖI FILE: Thiếu các cột bắt buộc sau:** {missing_cols}")
        st.warning("⚠️ **Các cột hiện có trong file (đã đọc được):**")
        st.code(list(df.columns))
        st.info("💡 Sếp kiểm tra lại tên cột. Code đã cố gắng tự sửa tên nhưng chưa khớp.")
        st.stop()
        
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
    st.info("Sếp upload lại file đi ạ. Lần này em bao thầu cả UTF-16 lẫn Tab separator luôn!")