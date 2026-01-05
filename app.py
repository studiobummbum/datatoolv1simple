import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Monetization Report V3.1 (Stable)",
    page_icon="💰",
    layout="wide"
)

# --- CSS TÙY CHỈNH ---
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.title("💰 Monetization & LTV Report V3.1")
st.markdown("**Trạng thái:** Đã fix lỗi xử lý dữ liệu & hỗ trợ file không có Cost.")
st.markdown("---")

# --- BƯỚC 1: UPLOAD FILE ---
st.sidebar.header("📂 1. Upload Data")
uploaded_file = st.sidebar.file_uploader("Chọn file CSV Cohort (AdMob/MMP)", type=["csv"])

if uploaded_file:
    try:
        # --- LOAD DATA ---
        try:
            df = pd.read_csv(uploaded_file, encoding='utf-8')
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, encoding='utf-16', sep='\t')
        except pd.errors.ParserError:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, encoding='utf-16')

        st.sidebar.success(f"Đã load: {uploaded_file.name}")
        
        # --- BƯỚC 2: MAPPING CỘT ---
        st.sidebar.header("⚙️ 2. Mapping Cột")
        all_columns = df.columns.tolist()
        
        def get_index(options, keywords):
            for i, opt in enumerate(options):
                if any(k.lower() in str(opt).lower() for k in keywords):
                    return i
            return 0

        # Mapping bắt buộc
        col_date_raw = st.sidebar.selectbox("Cột Ngày (Install Date):", all_columns, index=get_index(all_columns, ['date', 'day', 'time']))
        col_country_raw = st.sidebar.selectbox("Cột Quốc gia (Country):", all_columns, index=get_index(all_columns, ['country', 'geo', 'region']))
        col_installs_raw = st.sidebar.selectbox("Cột Installs:", all_columns, index=get_index(all_columns, ['install', 'download']))
        col_revenue_raw = st.sidebar.selectbox("Cột Doanh thu (LTV/Revenue):", all_columns, index=get_index(all_columns, ['ltv', 'revenue', 'value', 'earnings']))

        # Mapping tùy chọn (Cost)
        cost_options = ["🚫 Không có (No Cost Data)"] + all_columns
        default_cost_idx = 0
        for i, opt in enumerate(cost_options):
            if any(k in str(opt).lower() for k in ['cost', 'spend', 'amount']) and opt != "🚫 Không có (No Cost Data)":
                default_cost_idx = i
                break
        
        col_cost_raw = st.sidebar.selectbox("Cột Chi phí (Cost/Spend) - Optional:", cost_options, index=default_cost_idx)

        # --- BƯỚC 3: XỬ LÝ DATA (FIXED) ---
        
        # 1. Tạo DataFrame sạch
        df_clean = pd.DataFrame()
        df_clean['Date'] = df[col_date_raw]
        df_clean['Country'] = df[col_country_raw]
        df_clean['Installs'] = df[col_installs_raw]
        df_clean['Revenue'] = df[col_revenue_raw]

        has_cost = col_cost_raw != "🚫 Không có (No Cost Data)"
        if has_cost:
            df_clean['Cost'] = df[col_cost_raw]
        else:
            df_clean['Cost'] = 0.0

        # 2. Clean Data Types (Hàm xử lý an toàn)
        def clean_currency(x):
            if isinstance(x, (int, float)):
                return x
            if isinstance(x, str):
                # Xóa ký tự lạ, chỉ giữ lại số và dấu chấm
                clean_str = x.replace('$', '').replace(',', '').replace('%', '').strip()
                try:
                    return float(clean_str)
                except ValueError:
                    return 0.0
            return 0.0

        # Áp dụng hàm clean
        df_clean['Installs'] = df_clean['Installs'].apply(clean_currency)
        df_clean['Revenue'] = df_clean['Revenue'].apply(clean_currency)
        df_clean['Cost'] = df_clean['Cost'].apply(clean_currency)
        
        # Xử lý ngày tháng
        df_clean['Date'] = pd.to_datetime(df_clean['Date'], errors='coerce')
        df_clean = df_clean.dropna(subset=['Date'])

        # 3. Tính toán lại Revenue nếu cột được chọn là LTV (Logic quan trọng cho AdMob)
        # Nếu cột được chọn có chữ "LTV" trong tên, ta hiểu đó là giá trị trung bình/user -> Cần nhân với Installs
        if "ltv" in col_revenue_raw.lower():
             df_clean['Revenue'] = df_clean['Revenue'] * df_clean['Installs']

        # 4. Tính KPI phụ
        # Tránh chia cho 0
        df_clean['CPI'] = df_clean.apply(lambda row: row['Cost'] / row['Installs'] if row['Installs'] > 0 else 0, axis=1)
        df_clean['ROAS'] = df_clean.apply(lambda row: (row['Revenue'] / row['Cost'] * 100) if row['Cost'] > 0 else 0, axis=1)

        # --- BƯỚC 4: BỘ LỌC ---
        st.header("🔍 Bộ lọc dữ liệu")
        col1, col2 = st.columns(2)
        
        min_date = df_clean['Date'].min().date()
        max_date = df_clean['Date'].max().date()

        with col1:
            date_range = st.date_input("Chọn khoảng thời gian:", value=(min_date, max_date))
        
        with col2:
            unique_countries = ['All'] + sorted(df_clean['Country'].astype(str).unique().tolist())
            selected_country = st.selectbox("Chọn Quốc gia:", unique_countries)

        # Filter Logic
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
            mask = (df_clean['Date'].dt.date >= start_date) & (df_clean['Date'].dt.date <= end_date)
            if selected_country != 'All':
                mask = mask & (df_clean['Country'] == selected_country)
            df_filtered = df_clean[mask]
        else:
            df_filtered = df_clean

        # --- BƯỚC 5: DASHBOARD ---
        if not df_filtered.empty:
            # Group theo Cohort (Date + Country) và lấy Max Revenue (vì LTV tích lũy)
            # Logic: Với mỗi ngày install và mỗi quốc gia, Revenue cao nhất chính là Revenue tích lũy đến hiện tại
            df_cohort_summary = df_filtered.groupby(['Date', 'Country']).agg({
                'Installs': 'max', # Số install là hằng số cho cohort đó
                'Revenue': 'max',  # Lấy giá trị tích lũy lớn nhất
                'Cost': 'max'      # Cost cũng là hằng số
            }).reset_index()

            total_spend = df_cohort_summary['Cost'].sum()
            total_installs = df_cohort_summary['Installs'].sum()
            total_revenue = df_cohort_summary['Revenue'].sum()
            
            # Metrics
            st.markdown("### 📊 Hiệu suất Monetization")
            cols = st.columns(4)
            cols[0].metric("Tổng Installs", f"{total_installs:,.0f}")
            cols[1].metric("Tổng Doanh Thu (Est.)", f"${total_revenue:,.2f}")
            
            if has_cost and total_spend > 0:
                avg_roas = (total_revenue / total_spend * 100) if total_spend > 0 else 0
                cols[2].metric("Tổng Chi Phí", f"${total_spend:,.2f}")
                cols[3].metric("ROAS Tổng", f"{avg_roas:,.2f}%")
            else:
                arpu = total_revenue / total_installs if total_installs > 0 else 0
                cols[2].metric("ARPU (Avg Revenue/User)", f"${arpu:,.3f}")
                cols[3].metric("Trạng thái Cost", "No Data", delta_color="off")

            st.markdown("---")
            
            # Charts
            c1, c2 = st.columns(2)
            
            with c1:
                st.subheader("📈 Xu hướng Doanh thu (Cohort Date)")
                daily_trend = df_cohort_summary.groupby('Date')['Revenue'].sum().reset_index()
                fig_rev = px.bar(daily_trend, x='Date', y='Revenue', title="Revenue by Install Date", color_discrete_sequence=['#00cc96'])
                st.plotly_chart(fig_rev, use_container_width=True)

            with c2:
                st.subheader("🌍 Top Quốc gia (Revenue)")
                country_trend = df_cohort_summary.groupby('Country')['Revenue'].sum().reset_index().sort_values('Revenue', ascending=False).head(10)
                fig_country = px.pie(country_trend, values='Revenue', names='Country', hole=0.4)
                st.plotly_chart(fig_country, use_container_width=True)

            # Data Table
            st.markdown("### 📑 Chi tiết Cohort")
            st.dataframe(df_cohort_summary.sort_values('Date', ascending=False).style.format({
                "Revenue": "${:,.2f}", "Cost": "${:,.2f}", "Installs": "{:,.0f}"
            }), use_container_width=True)

    except Exception as e:
        st.error(f"Vẫn còn lỗi: {e}")
        st.write("Vui lòng chụp màn hình lỗi này gửi lại để em xử lý.")
else:
    st.info("👈 Upload file AdMob CSV để bắt đầu phân tích nhé sếp!")