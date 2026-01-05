import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="AdMob LTV Report", layout="wide", page_icon="💰")

# --- HÀM LOAD DATA ---
@st.cache_data
def load_data(file):
    try:
        # Thử đọc mặc định
        df = pd.read_csv(file)
    except:
        # Fallback nếu lỗi encoding
        file.seek(0)
        df = pd.read_csv(file, encoding='latin1')
    
    # Chuẩn hóa tên cột: Xóa khoảng trắng thừa đầu đuôi
    df.columns = df.columns.str.strip()
    
    # Convert Install date sang datetime
    if 'Install date' in df.columns:
        df['Install date'] = pd.to_datetime(df['Install date'])
        
    return df

# --- GIAO DIỆN ---
st.title("💰 AdMob LTV Analyzer (Corrected)")
st.markdown("Phân tích LTV từ file report chi tiết (đã có cột `LTV (USD)` cumulative).")

uploaded_file = st.file_uploader("Upload file admob-report.csv", type=['csv'])

if uploaded_file:
    df = load_data(uploaded_file)
    
    # 1. BỘ LỌC QUỐC GIA (BẮT BUỘC)
    if 'Install country' in df.columns:
        country_list = sorted(df['Install country'].unique().tolist())
        selected_country = st.selectbox("🌍 Chọn Quốc Gia (Country):", country_list)
        
        # Lọc data theo nước đã chọn
        df_country = df[df['Install country'] == selected_country].copy()
    else:
        st.warning("Không tìm thấy cột 'Install country'. Đang hiển thị toàn bộ data.")
        df_country = df.copy()
        selected_country = "All"
    
    # 2. XỬ LÝ PIVOT DATA
    # Logic: Index = Install date, Columns = Days since install, Values = LTV (USD)
    
    # Pivot LTV
    # Dùng aggfunc='max' để lấy giá trị duy nhất của ngày đó
    df_pivot = df_country.pivot_table(
        index='Install date', 
        columns='Days since install', 
        values='LTV (USD)',
        aggfunc='max'
    )
    
    # Lấy cột Installs. 
    # Lưu ý: Installs là số user cài trong ngày đó, nó lặp lại ở mọi dòng 'Days since install'.
    # Ta chỉ cần lấy 1 dòng đại diện (ví dụ dòng Days=0) để lấy số Install.
    df_installs = df_country[df_country['Days since install'] == 0][['Install date', 'Installs']]
    df_installs = df_installs.set_index('Install date')
    
    # Merge lại để có bảng full: Cột đầu là Installs, các cột sau là LTV D0, D1...
    df_final = df_installs.join(df_pivot, how='inner') # Dùng inner để đảm bảo ngày nào có install mới hiện
    
    # Sắp xếp theo ngày mới nhất lên đầu
    df_final = df_final.sort_index(ascending=False)

    # 3. HIỂN THỊ METRICS (Weighted Average 30 ngày gần nhất)
    st.subheader(f"📊 Hiệu suất LTV - {selected_country}")
    
    recent_df = df_final.head(30) # Lấy 30 cohort gần nhất để tính trung bình
    
    cols = st.columns(4)
    metrics_to_show = [0, 1, 3, 7, 14, 30] # Các mốc LTV quan trọng
    
    # Hiển thị 4 chỉ số đầu tiên lên top, các chỉ số sau (D14, D30) sếp xem ở bảng
    display_metrics = metrics_to_show[:4] 
    
    for i, d in enumerate(display_metrics):
        if d in recent_df.columns:
            # Tính Weighted Avg: Sum(LTV_day_i * Installs) / Sum(Installs)
            # Chỉ tính trên những dòng mà LTV ngày đó không bị NaN (chưa có dữ liệu)
            valid_rows = recent_df.dropna(subset=[d])
            
            if not valid_rows.empty and valid_rows['Installs'].sum() > 0:
                w_avg = (valid_rows[d] * valid_rows['Installs']).sum() / valid_rows['Installs'].sum()
                cols[i].metric(f"Avg LTV D{d}", f"${w_avg:.4f}")
            else:
                cols[i].metric(f"Avg LTV D{d}", "N/A")
        else:
             cols[i].metric(f"Avg LTV D{d}", "No Data")

    # 4. BIỂU ĐỒ (CHART)
    st.subheader("📈 Xu hướng LTV theo Cohort")
    
    fig = go.Figure()
    
    # Màu sắc cho từng đường LTV
    colors = {0: '#9ca3af', 1: '#3b82f6', 3: '#f59e0b', 7: '#10b981', 14: '#8b5cf6', 30: '#ef4444'}
    
    for d in metrics_to_show:
        if d in df_final.columns:
            fig.add_trace(go.Scatter(
                x=df_final.index, 
                y=df_final[d], 
                mode='lines+markers',
                name=f'LTV D{d}',
                line=dict(color=colors.get(d, 'black'), width=2 if d==0 else 3),
                connectgaps=True, # Nối điểm đứt quãng
                hovertemplate=f'Date: %{{x|%Y-%m-%d}}<br>LTV D{d}: $%{{y:.4f}}<extra></extra>'
            ))

    fig.update_layout(
        hovermode="x unified",
        xaxis_title="Cohort Date",
        yaxis_title="LTV ($)",
        yaxis_tickformat='$.4f',
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

    # 5. DATA TABLE CHI TIẾT
    st.subheader("📋 Bảng chi tiết (Pivot Table)")
    
    # Reset index để hiển thị cột Date đẹp hơn
    display_df = df_final.reset_index()
    
    # Tạo config format cột
    column_config = {
        "Install date": st.column_config.DateColumn("Cohort Date", format="YYYY-MM-DD"),
        "Installs": st.column_config.NumberColumn("Users", format="%d"),
    }
    
    # Format các cột LTV D0, D1... thành tiền tệ
    for col in display_df.columns:
        if isinstance(col, int) or (isinstance(col, str) and col.isdigit()):
            column_config[col] = st.column_config.NumberColumn(f"D{col}", format="$%.4f")

    st.dataframe(
        display_df,
        column_config=column_config,
        hide_index=True,
        use_container_width=True,
        height=600
    )

else:
    st.info("Sếp upload file CSV đi ạ. Em đang đợi đây...")