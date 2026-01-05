import streamlit as st
import pandas as pd
import plotly.express as px

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="UA Report Mapper V2.1 (Fix Encoding)",
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
st.title("🎯 UA Report Mapper V2.1")
st.markdown("**Logic mới:** Phân tích trực tiếp từ 1 file Cohort (chứa cả Cost & Revenue).")
st.markdown("---")

# --- BƯỚC 1: UPLOAD FILE ---
st.sidebar.header("📂 1. Upload Data")
uploaded_file = st.sidebar.file_uploader("Chọn file CSV Cohort của sếp", type=["csv"])

if uploaded_file:
    try:
        # --- FIX LỖI ENCODING Ở ĐÂY ---
        # Thử đọc bằng utf-8 trước, nếu lỗi thì thử utf-16 (format thường gặp của AdMob/Excel)
        try:
            df = pd.read_csv(uploaded_file, encoding='utf-8')
        except UnicodeDecodeError:
            uploaded_file.seek(0) # Reset con trỏ file về đầu
            df = pd.read_csv(uploaded_file, encoding='utf-16', sep='\t') # UTF-16 thường đi kèm dấu phân cách tab (\t)
        except pd.errors.ParserError:
             # Fallback: Thử đọc utf-16 nhưng dấu phẩy (ít gặp hơn nhưng cứ thủ sẵn)
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, encoding='utf-16')

        st.sidebar.success(f"Đã load: {uploaded_file.name}")
        
        # Hiển thị raw data để sếp dễ mapping
        with st.expander("👀 Xem trước dữ liệu thô (5 dòng đầu)"):
            st.dataframe(df.head())

        # --- BƯỚC 2: MAPPING CỘT (QUAN TRỌNG) ---
        st.sidebar.header("⚙️ 2. Mapping Cột")
        st.sidebar.info("Chọn cột tương ứng trong file CSV của sếp:")
        
        all_columns = df.columns.tolist()
        
        # Tự động đoán tên cột (nếu có)
        def get_index(options, keywords):
            for i, opt in enumerate(options):
                if any(k.lower() in opt.lower() for k in keywords):
                    return i
            return 0

        col_date = st.sidebar.selectbox("Cột Ngày (Date):", all_columns, index=get_index(all_columns, ['date', 'day', 'time']))
        col_country = st.sidebar.selectbox("Cột Quốc gia (Country):", all_columns, index=get_index(all_columns, ['country', 'geo', 'region']))
        col_cost = st.sidebar.selectbox("Cột Chi phí (Cost/Spend):", all_columns, index=get_index(all_columns, ['cost', 'spend', 'amount']))
        col_installs = st.sidebar.selectbox("Cột Installs:", all_columns, index=get_index(all_columns, ['install', 'download']))
        col_revenue = st.sidebar.selectbox("Cột Doanh thu (LTV/Revenue):", all_columns, index=get_index(all_columns, ['revenue', 'ltv', 'earnings', 'value']))

        # --- BƯỚC 3: XỬ LÝ DATA ---
        # Chuẩn hóa dữ liệu
        df_clean = df.copy()
        df_clean[col_date] = pd.to_datetime(df_clean[col_date], errors='coerce')
        
        # Ép kiểu số (loại bỏ ký tự lạ như '$', ',')
        for col in [col_cost, col_installs, col_revenue]:
            # Chuyển về string -> replace -> numeric. Handle cả trường hợp cột đã là số sẵn.
            df_clean[col] = pd.to_numeric(df_clean[col].astype(str).str.replace(r'[$,]', '', regex=True), errors='coerce').fillna(0)

        # Đổi tên cột về chuẩn để code dễ xử lý
        df_clean = df_clean.rename(columns={
            col_date: 'Date',
            col_country: 'Country',
            col_cost: 'Cost',
            col_installs: 'Installs',
            col_revenue: 'Revenue'
        })

        # Xóa các dòng mà Date bị NaT (do file csv có thể có dòng tổng cộng ở cuối)
        df_clean = df_clean.dropna(subset=['Date'])

        # Tính toán các chỉ số KPI
        # Tránh chia cho 0
        df_clean['CPI'] = df_clean.apply(lambda x: x['Cost'] / x['Installs'] if x['Installs'] > 0 else 0, axis=1)
        df_clean['ROAS'] = df_clean.apply(lambda x: (x['Revenue'] / x['Cost']) * 100 if x['Cost'] > 0 else 0, axis=1)
        
        # --- BƯỚC 4: BỘ LỌC (FILTER) ---
        st.header("🔍 Bộ lọc dữ liệu")
        col1, col2 = st.columns(2)
        
        with col1:
            # Lọc theo ngày
            if not df_clean.empty:
                min_date = df_clean['Date'].min()
                max_date = df_clean['Date'].max()
                date_range = st.date_input("Chọn khoảng thời gian:", [min_date, max_date])
            else:
                st.warning("Không tìm thấy dữ liệu ngày tháng hợp lệ.")
                st.stop()
        
        with col2:
            # Lọc theo Country
            unique_countries = ['All'] + sorted(df_clean['Country'].unique().astype(str).tolist())
            selected_country = st.selectbox("Chọn Quốc gia:", unique_countries)

        # Áp dụng bộ lọc
        if len(date_range) == 2:
            mask = (df_clean['Date'] >= pd.to_datetime(date_range[0])) & (df_clean['Date'] <= pd.to_datetime(date_range[1]))
            if selected_country != 'All':
                mask = mask & (df_clean['Country'] == selected_country)
            
            df_filtered = df_clean[mask]

            # --- BƯỚC 5: HIỂN THỊ METRICS TỔNG QUAN ---
            st.markdown("### 📊 Tổng quan hiệu suất")
            
            total_spend = df_filtered['Cost'].sum()
            total_installs = df_filtered['Installs'].sum()
            total_revenue = df_filtered['Revenue'].sum()
            
            avg_cpi = total_spend / total_installs if total_installs > 0 else 0
            avg_roas = (total_revenue / total_spend * 100) if total_spend > 0 else 0
            net_profit = total_revenue - total_spend

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Tổng Chi Phí (Spend)", f"${total_spend:,.2f}")
            m2.metric("Tổng Installs", f"{total_installs:,.0f}")
            m3.metric("CPI Trung Bình", f"${avg_cpi:,.3f}", delta_color="inverse") # CPI thấp là tốt
            m4.metric("Tổng Doanh Thu (LTV)", f"${total_revenue:,.2f}")
            m5.metric("ROAS Tổng", f"{avg_roas:,.2f}%", delta=f"{avg_roas-100:.2f}% (vs BEP)" if avg_roas > 0 else None)

            # --- BƯỚC 6: BIỂU ĐỒ ---
            st.markdown("---")
            c1, c2 = st.columns(2)

            # Chart 1: Xu hướng Spend vs Revenue
            with c1:
                st.subheader("💸 Xu hướng Spend vs Revenue")
                daily_stats = df_filtered.groupby('Date')[['Cost', 'Revenue']].sum().reset_index()
                fig_trend = px.line(daily_stats, x='Date', y=['Cost', 'Revenue'], 
                                    color_discrete_map={"Cost": "#ef553b", "Revenue": "#00cc96"},
                                    markers=True)
                st.plotly_chart(fig_trend, use_container_width=True)

            # Chart 2: Scatter Plot CPI vs ROAS (theo Country)
            with c2:
                st.subheader("🌍 Hiệu suất theo Quốc gia (Bubble Chart)")
                country_stats = df_filtered.groupby('Country').agg({
                    'Cost': 'sum',
                    'Installs': 'sum',
                    'Revenue': 'sum'
                }).reset_index()
                
                country_stats['CPI'] = country_stats['Cost'] / country_stats['Installs']
                country_stats['ROAS'] = (country_stats['Revenue'] / country_stats['Cost']) * 100
                
                # Chỉ hiện country có spend > 0 để đỡ rối
                country_stats = country_stats[country_stats['Cost'] > 0]

                fig_bubble = px.scatter(country_stats, x="CPI", y="ROAS",
                                        size="Cost", color="Country",
                                        hover_name="Country",
                                        title="Tương quan CPI vs ROAS (Size = Spend)",
                                        template="plotly_white")
                # Kẻ đường hòa vốn (ROAS 100%)
                fig_bubble.add_hline(y=100, line_dash="dash", line_color="green", annotation_text="Break Even (100%)")
                st.plotly_chart(fig_bubble, use_container_width=True)

            # --- BƯỚC 7: BẢNG CHI TIẾT ---
            st.markdown("### 📑 Chi tiết dữ liệu")
            st.dataframe(
                df_filtered.sort_values(by='Date', ascending=False).style.format({
                    "Cost": "${:,.2f}",
                    "Revenue": "${:,.2f}",
                    "CPI": "${:,.3f}",
                    "ROAS": "{:,.2f}%",
                    "Installs": "{:,.0f}"
                }),
                use_container_width=True
            )
        else:
            st.info("Vui lòng chọn khoảng thời gian hợp lệ.")

    except Exception as e:
        st.error(f"Vẫn có lỗi xảy ra sếp ơi: {e}")
        st.info("Sếp thử mở file CSV bằng Excel -> Save As -> Chọn định dạng 'CSV UTF-8 (Comma delimited) (*.csv)' rồi upload lại xem sao nhé!")

else:
    st.info("👈 Sếp vui lòng upload file CSV Cohort bên thanh menu trái nhé!")
    st.markdown("""
    ### Hướng dẫn chuẩn bị file CSV:
    File CSV của sếp cần có tối thiểu các cột sau (tên cột không quan trọng, tool cho phép map lại):
    1.  **Date:** Ngày phát sinh install.
    2.  **Country:** Quốc gia.
    3.  **Cost/Spend:** Số tiền đã chạy ads.
    4.  **Installs:** Số lượng cài đặt.
    5.  **Revenue/LTV:** Doanh thu (có thể là D0, D7 hoặc Total LTV tùy mục đích sếp muốn soi).
    """)