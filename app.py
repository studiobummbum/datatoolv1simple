import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="LTV Cohort Analysis", layout="wide", page_icon="📊")

# --- HÀM XỬ LÝ ĐỌC FILE ---
@st.cache_data
def load_data(file):
    try:
        df = pd.read_csv(file)
    except UnicodeDecodeError:
        file.seek(0)
        df = pd.read_csv(file, encoding='latin1')
    
    # Chuẩn hóa tên cột
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
    return df

# --- HÀM XỬ LÝ LOGIC PIVOT (QUAN TRỌNG) ---
def process_cohort_data(df):
    # 1. Mapping tên cột cơ bản
    # Cần tìm các cột: install_date (cohort), days_since_install, revenue, installs (optional)
    
    # Map Date (Cohort Date)
    date_cols = ['install_date', 'date', 'cohort_date', 'acquisition_date']
    found_date = next((c for c in df.columns if c in date_cols), None)
    if not found_date:
        return None, "Không tìm thấy cột ngày cài đặt (install_date, date...)"
    df = df.rename(columns={found_date: 'install_date'})
    df['install_date'] = pd.to_datetime(df['install_date'], errors='coerce')

    # Map Days Since Install
    days_cols = ['days_since_install', 'day', 'days']
    found_days = next((c for c in df.columns if c in days_cols), None)
    if not found_days:
        return None, "Không tìm thấy cột 'days_since_install' (hoặc day, days)."
    df = df.rename(columns={found_days: 'days_since_install'})

    # Map Revenue
    rev_cols = [c for c in df.columns if 'revenue' in c or 'value' in c or 'earnings' in c]
    found_rev = rev_cols[0] if rev_cols else None
    if not found_rev:
        return None, "Không tìm thấy cột doanh thu (revenue, value...)"
    df = df.rename(columns={found_rev: 'revenue'})
    df['revenue'] = pd.to_numeric(df['revenue'], errors='coerce').fillna(0)

    # Map Installs (Nếu có - để tính LTV)
    # Lưu ý: Trong file Long Format, cột installs thường chỉ có giá trị ở dòng days_since_install = 0
    # Hoặc nó lặp lại ở mọi dòng. Ta cần xử lý khéo chỗ này.
    inst_cols = ['installs', 'users', 'downloads', 'cohort_size']
    found_inst = next((c for c in df.columns if c in inst_cols), None)
    
    if found_inst:
        df = df.rename(columns={found_inst: 'installs'})
    else:
        # Nếu không có cột installs, ta không tính được LTV chính xác, chỉ tính được ARPU hoặc Revenue
        # Tạm thời báo lỗi hoặc warning
        return None, "Cần có cột 'installs' hoặc 'cohort_size' để chia mẫu số tính LTV."

    # 2. THỰC HIỆN PIVOT DATA (Chuyển Dọc -> Ngang)
    # Mục tiêu: Index = install_date, Columns = days_since_install, Values = revenue (sum)
    
    # Bước 2.1: Lấy số lượng install chuẩn cho mỗi ngày (Cohort Size)
    # Thường lấy max installs của ngày đó (vì các dòng days > 0 vẫn chung 1 cohort size)
    cohort_sizes = df.groupby('install_date')['installs'].max()

    # Bước 2.2: Pivot Revenue theo ngày
    pivot_revenue = df.pivot_table(
        index='install_date', 
        columns='days_since_install', 
        values='revenue', 
        aggfunc='sum'
    ).fillna(0)

    # Đảm bảo có đủ các cột 0, 1, 3 (nếu data thiếu thì fill 0)
    for d in [0, 1, 3, 7, 14, 30]:
        if d not in pivot_revenue.columns:
            pivot_revenue[d] = 0.0

    # 3. TÍNH TOÁN LTV CỘNG DỒN (CUMULATIVE LTV)
    # LTV D1 = (Rev D0 + Rev D1) / Installs
    # LTV D3 = (Rev D0 + Rev D1 + Rev D2 + Rev D3) / Installs
    
    # Tính Cumulative Revenue (Doanh thu tích lũy) theo chiều ngang
    cumulative_rev = pivot_revenue.cumsum(axis=1)

    # Merge với Cohort Size (Installs)
    final_df = cumulative_rev.merge(cohort_sizes, left_index=True, right_index=True)
    
    # Tính LTV
    # Tạo DataFrame kết quả
    result = pd.DataFrame(index=final_df.index)
    result['installs'] = final_df['installs']
    
    # Tính LTV cho các mốc quan trọng (D0, D1, D3, D7...)
    # Lưu ý: Cột trong pivot_revenue là số nguyên (0, 1, 2...)
    # Cần check xem cột đó có tồn tại trong cumulative_rev không
    
    available_days = sorted([c for c in cumulative_rev.columns if isinstance(c, (int, float))])
    
    for day in [0, 1, 3, 7, 14, 30]:
        # Tìm ngày gần nhất <= day có trong data (để handle việc data bị thủng lỗ)
        valid_days = [d for d in available_days if d <= day]
        if valid_days:
            closest_day = max(valid_days)
            col_name = f'ltv_d{day}'
            # LTV = Cumulative Revenue tại ngày đó / Installs
            result[col_name] = final_df[closest_day] / final_df['installs'].replace(0, 1)
        else:
            result[f'ltv_d{day}'] = 0.0

    return result.reset_index(), None

# --- GIAO DIỆN ---
st.title("📈 LTV Cohort Analyzer (Long Format)")
st.markdown("Xử lý file dạng dọc: `install_date` | `days_since_install` | `revenue`")

uploaded_file = st.file_uploader("Upload CSV", type=['csv'])

if uploaded_file:
    df_raw = load_data(uploaded_file)
    
    # Hiển thị raw data 5 dòng đầu để sếp check
    with st.expander("Xem dữ liệu gốc (5 dòng đầu)"):
        st.dataframe(df_raw.head())

    df_ltv, error = process_cohort_data(df_raw)

    if error:
        st.error(f"Lỗi xử lý: {error}")
    else:
        # --- DASHBOARD ---
        st.success("Đã pivot dữ liệu thành công!")

        # 1. Metrics tổng quan (Trung bình 30 ngày gần nhất)
        st.subheader("📊 Average LTV (Last 30 Days)")
        last_30_days = df_ltv.sort_values('install_date', ascending=False).head(30)
        
        # Tính Weighted Average LTV
        total_installs = last_30_days['installs'].sum()
        w_avg_d0 = (last_30_days['ltv_d0'] * last_30_days['installs']).sum() / total_installs
        w_avg_d1 = (last_30_days['ltv_d1'] * last_30_days['installs']).sum() / total_installs
        w_avg_d3 = (last_30_days['ltv_d3'] * last_30_days['installs']).sum() / total_installs
        w_avg_d7 = (last_30_days['ltv_d7'] * last_30_days['installs']).sum() / total_installs

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Avg LTV D0", f"${w_avg_d0:.4f}")
        c2.metric("Avg LTV D1", f"${w_avg_d1:.4f}", delta=f"+{(w_avg_d1-w_avg_d0):.4f}")
        c3.metric("Avg LTV D3", f"${w_avg_d3:.4f}", delta=f"+{(w_avg_d3-w_avg_d1):.4f}")
        c4.metric("Avg LTV D7", f"${w_avg_d7:.4f}", delta=f"+{(w_avg_d7-w_avg_d3):.4f}")

        # 2. Chart
        st.subheader("📉 Diễn biến LTV theo Cohort Date")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_ltv['install_date'], y=df_ltv['ltv_d0'], name='D0', line=dict(color='gray')))
        fig.add_trace(go.Scatter(x=df_ltv['install_date'], y=df_ltv['ltv_d1'], name='D1', line=dict(color='blue')))
        fig.add_trace(go.Scatter(x=df_ltv['install_date'], y=df_ltv['ltv_d3'], name='D3', line=dict(color='orange')))
        fig.add_trace(go.Scatter(x=df_ltv['install_date'], y=df_ltv['ltv_d7'], name='D7', line=dict(color='green')))
        
        fig.update_layout(hovermode="x unified", yaxis_tickformat='$.3f')
        st.plotly_chart(fig, use_container_width=True)

        # 3. Data Table
        st.subheader("📋 Bảng chi tiết LTV")
        st.dataframe(
            df_ltv.sort_values('install_date', ascending=False),
            column_config={
                "install_date": st.column_config.DateColumn("Cohort Date", format="YYYY-MM-DD"),
                "installs": st.column_config.NumberColumn("Users", format="%d"),
                "ltv_d0": st.column_config.NumberColumn("LTV D0", format="$%.4f"),
                "ltv_d1": st.column_config.NumberColumn("LTV D1", format="$%.4f"),
                "ltv_d3": st.column_config.NumberColumn("LTV D3", format="$%.4f"),
                "ltv_d7": st.column_config.NumberColumn("LTV D7", format="$%.4f"),
            },
            hide_index=True,
            use_container_width=True
        )
else:
    st.info("Vui lòng upload file CSV có các cột: `install_date`, `days_since_install`, `revenue`, `installs`")