import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="UA Report Mapper V2.3 (Fix KeyError)",
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
    .stDataFrame {
        border: 1px solid #ddd;
        border-radius: 5px;
    }
</style>
""", unsafe_allow_html=True)

# --- HEADER ---
st.title("🎯 UA Report Mapper V2.3")
st.markdown("**Logic mới:** Fix lỗi mất cột 'Cost' và chuẩn hóa quy trình xử lý dữ liệu.")
st.markdown("---")

# --- BƯỚC 1: UPLOAD FILE ---
st.sidebar.header("📂 1. Upload Data")
uploaded_file = st.sidebar.file_uploader("Chọn file CSV Cohort của sếp", type=["csv"])

if uploaded_file:
    try:
        # --- FIX LỖI ENCODING ---
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

        # Người dùng chọn cột từ file gốc
        col_date_raw = st.sidebar.selectbox("Cột Ngày (Date):", all_columns, index=get_index(all_columns, ['date', 'day', 'time']))
        col_country_raw = st.sidebar.selectbox("Cột Quốc gia (Country):", all_columns, index=get_index(all_columns, ['country', 'geo', 'region']))
        col_cost_raw = st.sidebar.selectbox("Cột Chi phí (Cost/Spend):", all_columns, index=get_index(all_columns, ['cost', 'spend', 'amount']))
        col_installs_raw = st.sidebar.selectbox("Cột Installs:", all_columns, index=get_index(all_columns, ['install', 'download']))
        col_revenue_raw = st.sidebar.selectbox("Cột Doanh thu (LTV/Revenue):", all_columns, index=get_index(all_columns, ['revenue', 'ltv', 'earnings', 'value']))

        # --- BƯỚC 3: XỬ LÝ DATA (LOGIC ĐÃ SỬA) ---
        df_clean = df.copy()

        # 1. Đổi tên cột NGAY LẬP TỨC về chuẩn chung để tránh lỗi KeyError
        # Chỉ giữ lại các cột cần thiết để tránh rác
        df_clean = df_clean[[col_date_raw, col_country_raw, col_cost_raw, col_installs_raw, col_revenue_raw]].copy()
        
        df_clean = df_clean.rename(columns={
            col_date_raw: 'Date',
            col_country_raw: 'Country',
            col_cost_raw: 'Cost',
            col_installs_raw: 'Installs',
            col_revenue_raw: 'Revenue'
        })
        
        # 2. Xử lý ngày tháng trên cột chuẩn 'Date'
        df_clean['Date'] = pd.to_datetime(df_clean['Date'], errors='coerce')
        
        # 3. Xử lý số liệu trên các cột chuẩn 'Cost', 'Installs', 'Revenue'
        for col in ['Cost', 'Installs', 'Revenue']:
            # Chuyển về string, xóa ký tự lạ ($, dấu phẩy), rồi chuyển về số
            df_clean[col] = pd.to_numeric(
                df_clean[col].astype(str).str.replace(r'[$,]', '', regex=True), 
                errors='coerce'
            ).fillna(0)

        # 4. Xóa dòng lỗi Date (NaT)
        df_clean = df_clean.dropna(subset=['Date'])

        # 5. Tính KPI (Lúc này chắc chắn đã có cột Cost, Installs, Revenue)
        df_clean['CPI'] = np.where(df_clean['Installs'] > 0, df_clean['Cost'] / df_clean['Installs'], 0)
        df_clean['ROAS'] = np.where(df_clean['Cost'] > 0, (df_clean['Revenue'] / df_clean['Cost']) * 100, 0)
        
        # --- BƯỚC 4: BỘ LỌC ---
        st.header("🔍 Bộ lọc dữ liệu")
        
        if df_clean.empty:
            st.error("Dữ liệu sau khi xử lý bị rỗng. Vui lòng kiểm tra lại file CSV.")
            st.stop()

        col1, col2 = st.columns(2)
        
        min_date = df_clean['Date'].min().date()
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

        # Logic lọc
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
            mask = (df_clean['Date'].dt.date >= start_date) & (df_clean['Date'].dt.date <= end_date)
            
            if selected_country != 'All':
                mask = mask & (df_clean['Country'] == selected_country)
            
            df_filtered = df_clean[mask]
        else:
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
                # Group by Date
                daily_stats = df_filtered.groupby('Date')[['Cost', 'Revenue']].sum().reset_index()
                if not daily_stats.empty:
                    fig_trend = px.line(daily_stats, x='Date', y=['Cost', 'Revenue'], 
                                        color_discrete_map={"Cost": "#ef553b", "Revenue": "#00cc96"},
                                        markers=True)
                    st.plotly_chart(fig_trend, use_container_width=True)

            with c2:
                st.subheader("🌍 Top Quốc gia (Spend)")
                # Group by Country
                country_stats = df_filtered.groupby('Country').agg({
                    'Cost': 'sum', 'Installs': 'sum', 'Revenue': 'sum'
                }).reset_index()
                
                country_stats['CPI'] = np.where(country_stats['Installs']>0, country_stats['Cost']/country_stats['Installs'], 0)
                country_stats['ROAS'] = np.where(country_stats['Cost']>0, (country_stats['Revenue']/country_stats['Cost'])*100, 0)
                
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
        st.error(f"Lỗi hệ thống chi tiết: {e}")
        # In ra columns hiện tại để debug nếu vẫn lỗi
        st.write("Các cột hiện có trong DataFrame:", df.columns.tolist())

else:
    st.info("👈 Sếp vui lòng upload file CSV Cohort bên thanh menu trái nhé!")