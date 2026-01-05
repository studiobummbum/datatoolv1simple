import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Monetization Report V3.0 (No Cost Support)",
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
st.title("💰 Monetization & LTV Report V3.0")
st.markdown("**Update:** Hỗ trợ file không có cột Cost (AdMob/Mediation Reports).")
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
        # Thêm option "Không có" vào đầu list
        cost_options = ["🚫 Không có (No Cost Data)"] + all_columns
        # Cố gắng tìm cột cost, nếu không thấy thì default về 0 (Option "Không có")
        default_cost_idx = 0
        for i, opt in enumerate(cost_options):
            if any(k in str(opt).lower() for k in ['cost', 'spend', 'amount']) and opt != "🚫 Không có (No Cost Data)":
                default_cost_idx = i
                break
        
        col_cost_raw = st.sidebar.selectbox("Cột Chi phí (Cost/Spend) - Optional:", cost_options, index=default_cost_idx)

        # --- BƯỚC 3: XỬ LÝ DATA ---
        # Logic: Chỉ lấy cột cần thiết -> Rename -> Xử lý type
        
        # 1. Xác định cột cần lấy
        cols_to_keep = [col_date_raw, col_country_raw, col_installs_raw, col_revenue_raw]
        has_cost = col_cost_raw != "🚫 Không có (No Cost Data)"
        
        if has_cost:
            cols_to_keep.append(col_cost_raw)

        df_clean = df[cols_to_keep].copy()

        # 2. Rename
        rename_map = {
            col_date_raw: 'Date',
            col_country_raw: 'Country',
            col_installs_raw: 'Installs',
            col_revenue_raw: 'Revenue'
        }
        if has_cost:
            rename_map[col_cost_raw] = 'Cost'
        
        df_clean = df_clean.rename(columns=rename_map)

        # 3. Nếu không có cột Cost, tạo cột Cost toàn số 0
        if not has_cost:
            df_clean['Cost'] = 0.0

        # 4. Clean Data Types
        df_clean['Date'] = pd.to_datetime(df_clean['Date'], errors='coerce')
        
        for col in ['Installs', 'Revenue', 'Cost']:
            df_clean[col] = pd.to_numeric(
                df_clean[col].astype(str).str.replace(r'[$,]', '', regex=True), 
                errors='coerce'
            ).fillna(0)

        df_clean = df_clean.dropna(subset=['Date'])

        # 5. Tính KPI
        # Vì file AdMob của sếp là dạng Long Format (mỗi ngày 1 dòng), 
        # LTV trong file sếp gửi là "LTV (USD)" tích lũy theo ngày (Days since install).
        # Để view tổng quan, ta thường lấy max LTV của cohort hoặc sum revenue (tùy logic file).
        # Với file này: Cột "LTV (USD)" là giá trị trung bình trên user (Average LTV) hay Tổng Revenue?
        # Check logic: Nếu cột là "LTV (USD)" thường là per user. Nếu là "Revenue" là tổng.
        # Dựa vào data sếp gửi: LTV (USD) ~ 0.02 -> Đây là Average LTV per User.
        # => Total Revenue = Installs * LTV (USD).
        
        # Logic tự động phát hiện: Nếu Revenue < 100 và Installs > 100 (ví dụ), khả năng cao cột đó là ARPU/LTV per user.
        # Nhưng để an toàn, ta giả định cột sếp chọn là Total Revenue. 
        # NẾU sếp chọn cột "LTV (USD)" thì ta cần nhân với Installs để ra Total Revenue.
        
        # SỬA LOGIC CHO FILE ADMOB CỤ THỂ CỦA SẾP:
        # File sếp: Cột "LTV (USD)" là Average LTV. Cột "Installs" là số install của cohort đó.
        # Total Revenue thực tế = Installs * LTV (USD) (tại dòng max day).
        # Tuy nhiên, để đơn giản hóa hiển thị trên Streamlit, ta sẽ tính toán lại.
        
        # Ta tạo thêm cột 'Total_Revenue_Real'
        if "LTV" in col_revenue_raw:
             df_clean['Revenue'] = df_clean['Revenue'] * df_clean['Installs']
        
        df_clean['CPI'] = np.where(df_clean['Installs'] > 0, df_clean['Cost'] / df_clean['Installs'], 0)
        df_clean['ROAS'] = np.where(df_clean['Cost'] > 0, (df_clean['Revenue'] / df_clean['Cost']) * 100, 0)

        # --- BƯỚC 4: BỘ LỌC ---
        st.header("🔍 Bộ lọc dữ liệu")
        col1, col2 = st.columns(2)
        
        min_date = df_clean['Date'].min().date()
        max_date = df_clean['Date'].max().date()

        with col1:
            date_range = st.date_input("Chọn khoảng thời gian:", value=(min_date, max_date))
        
        with col2:
            unique_countries = ['All'] + sorted(df_clean['Country'].unique().astype(str).tolist())
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
            # Group data để hiển thị tổng quan (Tránh cộng dồn sai do file dạng cohort daily)
            # File AdMob dạng: Date - Country - Day 0, Day 1...
            # Để tính tổng Revenue đúng, ta cần lấy giá trị LTV cao nhất của mỗi Cohort (Date + Country).
            
            # Group theo Cohort (Date + Country) và lấy Max Revenue (vì LTV tích lũy)
            df_cohort_summary = df_filtered.groupby(['Date', 'Country']).agg({
                'Installs': 'max', # Số install không đổi theo ngày
                'Revenue': 'max',  # Lấy LTV tích lũy cao nhất (Total Revenue của cohort)
                'Cost': 'max'      # Cost (nếu có) cũng là total cho cohort
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
                avg_roas = (total_revenue / total_spend * 100)
                cols[2].metric("Tổng Chi Phí", f"${total_spend:,.2f}")
                cols[3].metric("ROAS Tổng", f"{avg_roas:,.2f}%")
            else:
                cols[2].metric("ARPU (Avg Revenue/User)", f"${(total_revenue/total_installs if total_installs else 0):,.3f}")
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
        st.error(f"Có lỗi xảy ra: {e}")
        st.write("Debug Info - Columns:", df.columns.tolist())
else:
    st.info("👈 Upload file AdMob CSV để bắt đầu phân tích nhé sếp!")