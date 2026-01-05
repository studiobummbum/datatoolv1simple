import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="UA Report Mapper V2.2 (Fix Logic)",
    page_icon="🎯",
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
    .metric-value {
        font-size: 24px;
        font-weight: bold;
        color: #0e1117;
    }
    .metric-label {
        font-size: 14px;
        color: #555;
    }
    .stDataFrame {
        border: 1px solid #ddd;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.title("🎯 UA Report Mapper V2.2")
st.markdown("**Logic mới:** Fix lỗi 'Ambiguous Truth Value' và tối ưu bộ lọc.")
st.markdown("---")

# --- BƯỚC 1: UPLOAD FILE ---
st.sidebar.header("📂 1. Upload Data")
uploaded_file = st.sidebar.file_uploader("Chọn file CSV Cohort của sếp", type=["csv"])

if uploaded_file:
    try:
        # --- FIX LỖI ENCODING (Giữ nguyên từ V2.1) ---
        try:
            df = pd.read_csv(uploaded_file, encoding='utf-8')
        except UnicodeDecodeError:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, encoding='utf-16', sep='\t')
        except pd.errors.ParserError:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, encoding='utf-16')

        st.sidebar.success(f"Đã load: {uploaded_file.name}")
        
        with st.expander("👀 Xem trước dữ liệu thô (5 dòng đầu)"):
            st.dataframe(df.head())

        # --- BƯỚC 2: MAPPING CỘT ---
        st.sidebar.header("⚙️ 2. Mapping Cột")
        all_columns = df.columns.tolist()
        
        def get_index(options, keywords):
            for i, opt in enumerate(options):
                if any(k.lower() in str(opt).lower() for k in keywords):
                    return i
            return 0

        col_date = st.sidebar.selectbox("Cột Ngày (Date):", all_columns, index=get_index(all_columns, ['date', 'day', 'time']))
        col_country = st.sidebar.selectbox("Cột Quốc gia (Country):", all_columns, index=get_index(all_columns, ['country', 'geo', 'region']))
        col_cost = st.sidebar.selectbox("Cột Chi phí (Cost/Spend):", all_columns, index=get_index(all_columns, ['cost', 'spend', 'amount']))
        col_installs = st.sidebar.selectbox("Cột Installs:", all_columns, index=get_index(all_columns, ['install', 'download']))
        col_revenue = st.sidebar.selectbox("Cột Doanh thu (LTV/Revenue):", all_columns, index=get_index(all_columns, ['revenue', 'ltv', 'earnings', 'value']))

        # --- BƯỚC 3: XỬ LÝ DATA ---
        df_clean = df.copy()
        
        # 1. Xử lý ngày tháng: Chuyển về datetime object chuẩn
        df_clean[col_date] = pd.to_datetime(df_clean[col_date], errors='coerce')
        
        # 2. Xử lý số liệu: Loại bỏ ký tự lạ và ép kiểu số
        for col in [col_cost, col_installs, col_revenue]:
            # Convert to string first to handle object types safely, then replace
            df_clean[col] = pd.to_numeric(
                df_clean[col].astype(str).str.replace(r'[$,]', '', regex=True), 
                errors='coerce'
            ).fillna(0)

        # 3. Đổi tên cột
        df_clean = df_clean.rename(columns={
            col_date: 'Date',
            col_country: 'Country',
            col_cost: 'Cost',
            col_installs: 'Installs',
            col_revenue: 'Revenue'
        })

        # 4. Xóa dòng lỗi Date (NaT)
        df_clean = df_clean.dropna(subset=['Date'])

        # 5. Tính KPI
        df_clean['CPI'] = np.where(df_clean['Installs'] > 0, df_clean['Cost'] / df_clean['Installs'], 0)
        df_clean['ROAS'] = np.where(df_clean['Cost'] > 0, (df_clean['Revenue'] / df_clean['Cost']) * 100, 0)
        
        # --- BƯỚC 4: BỘ LỌC (FIX LỖI AMBIGUOUS Ở ĐÂY) ---
        st.header("🔍 Bộ lọc dữ liệu")
        
        if df_clean.empty:
            st.error("Dữ liệu sau khi xử lý bị rỗng. Vui lòng kiểm tra lại file CSV hoặc mapping cột.")
            st.stop()

        col1, col2 = st.columns(2)
        
        # Lấy min/max date từ data
        min_date = df_clean['Date'].min().date() # Chuyển về .date() để lấy ngày thuần túy
        max_date = df_clean['Date'].max().date()

        with col1:
            date_range = st.date_input(
                "Chọn khoảng thời gian:", 
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date
            )
        
        with col2:
            unique_countries = ['All'] + sorted(df_clean['Country'].unique().astype(str).tolist())
            selected_country = st.selectbox("Chọn Quốc gia:", unique_countries)

        # Logic lọc an toàn hơn
        # Kiểm tra xem date_range có đủ 2 giá trị (start, end) không
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
            # Convert cột Date trong DF về .date() để so sánh chính xác
            mask = (df_clean['Date'].dt.date >= start_date) & (df_clean['Date'].dt.date <= end_date)
            
            if selected_country != 'All':
                mask = mask & (df_clean['Country'] == selected_country)
            
            df_filtered = df_clean[mask]
        else:
            # Nếu chưa chọn xong ngày, hiển thị toàn bộ hoặc data mặc định
            df_filtered = df_clean

        # --- BƯỚC 5: HIỂN THỊ DASHBOARD ---
        if not df_filtered.empty:
            st.markdown("### 📊 Tổng quan hiệu suất")
            
            total_spend = df_filtered['Cost'].sum()
            total_installs = df_filtered['Installs'].sum()
            total_revenue = df_filtered['Revenue'].sum()
            
            avg_cpi = total_spend / total_installs if total_installs > 0 else 0
            avg_roas = (total_revenue / total_spend * 100) if total_spend > 0 else 0

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Tổng Chi Phí", f"${total_spend:,.2f}")
            m2.metric("Tổng Installs", f"{total_installs:,.0f}")
            m3.metric("CPI", f"${avg_cpi:,.3f}", delta_color="inverse")
            m4.metric("Doanh Thu", f"${total_revenue:,.2f}")
            m5.metric("ROAS", f"{avg_roas:,.2f}%", delta=f"{avg_roas-100:.2f}%" if avg_roas > 0 else None)

            st.markdown("---")
            c1, c2 = st.columns(2)

            with c1:
                st.subheader("💸 Xu hướng Spend vs Revenue")
                daily_stats = df_filtered.groupby('Date')[['Cost', 'Revenue']].sum().reset_index()
                if not daily_stats.empty:
                    fig_trend = px.line(daily_stats, x='Date', y=['Cost', 'Revenue'], 
                                        color_discrete_map={"Cost": "#ef553b", "Revenue": "#00cc96"},
                                        markers=True)
                    st.plotly_chart(fig_trend, use_container_width=True)
                else:
                    st.info("Không đủ dữ liệu để vẽ biểu đồ xu hướng.")

            with c2:
                st.subheader("🌍 Hiệu suất Quốc gia (Top 20 Spend)")
                country_stats = df_filtered.groupby('Country').agg({
                    'Cost': 'sum', 'Installs': 'sum', 'Revenue': 'sum'
                }).reset_index()
                
                country_stats['CPI'] = np.where(country_stats['Installs']>0, country_stats['Cost']/country_stats['Installs'], 0)
                country_stats['ROAS'] = np.where(country_stats['Cost']>0, (country_stats['Revenue']/country_stats['Cost'])*100, 0)
                
                # Lọc top 20 spend để chart đỡ lag nếu nhiều country
                country_stats = country_stats.sort_values('Cost', ascending=False).head(20)
                country_stats = country_stats[country_stats['Cost'] > 0]

                if not country_stats.empty:
                    fig_bubble = px.scatter(country_stats, x="CPI", y="ROAS",
                                            size="Cost", color="Country",
                                            hover_name="Country",
                                            title="Top 20 Countries by Spend",
                                            template="plotly_white")
                    fig_bubble.add_hline(y=100, line_dash="dash", line_color="green")
                    st.plotly_chart(fig_bubble, use_container_width=True)
                else:
                    st.info("Chưa có dữ liệu chi tiêu.")

            st.markdown("### 📑 Chi tiết dữ liệu")
            st.dataframe(
                df_filtered.sort_values(by='Date', ascending=False).style.format({
                    "Cost": "${:,.2f}", "Revenue": "${:,.2f}", "CPI": "${:,.3f}",
                    "ROAS": "{:,.2f}%", "Installs": "{:,.0f}"
                }),
                use_container_width=True
            )
        else:
            st.warning("Không có dữ liệu nào thỏa mãn điều kiện lọc.")

    except Exception as e:
        st.error(f"Lỗi hệ thống: {e}")
        st.code(str(e)) # Hiện mã lỗi chi tiết để debug nếu cần

else:
    st.info("👈 Sếp vui lòng upload file CSV Cohort bên thanh menu trái nhé!")