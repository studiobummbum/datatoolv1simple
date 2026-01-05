import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Monetization Cohort Report V4.0",
    page_icon="💰",
    layout="wide"
)

# --- CSS ---
st.markdown("""
<style>
    .metric-card { background-color: #f0f2f6; border-radius: 10px; padding: 20px; text-align: center; }
    div[data-testid="stDataFrame"] { width: 100%; }
</style>
""", unsafe_allow_html=True)

st.title("💰 Monetization & LTV Report V4.0")
st.markdown("**Tính năng:** Fix lỗi ngày 1970 & Hiển thị LTV theo D0, D1, D3, D7...")
st.markdown("---")

# --- BƯỚC 1: UPLOAD ---
st.sidebar.header("📂 1. Upload Data")
uploaded_file = st.sidebar.file_uploader("Chọn file CSV Cohort", type=["csv"])

if uploaded_file:
    try:
        # Load data linh hoạt encoding
        try:
            df = pd.read_csv(uploaded_file, encoding='utf-8')
        except:
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, encoding='utf-16', sep='\t')

        st.sidebar.success(f"Đã load file. Số dòng: {len(df)}")

        # --- BƯỚC 2: MAPPING CỘT ---
        st.sidebar.header("⚙️ 2. Mapping Cột")
        cols = df.columns.tolist()

        # Helper tìm cột
        def find_col(keywords):
            for i, c in enumerate(cols):
                if any(k in c.lower() for k in keywords): return i
            return 0

        # Mapping
        c_date = st.sidebar.selectbox("Cột Ngày Install (Install Date):", cols, index=find_col(['date', 'day']))
        c_country = st.sidebar.selectbox("Cột Quốc gia (Country):", cols, index=find_col(['country', 'region']))
        c_days = st.sidebar.selectbox("Cột Ngày tuổi (Days since install):", cols, index=find_col(['days', 'since']))
        c_installs = st.sidebar.selectbox("Cột Installs:", cols, index=find_col(['install', 'user']))
        c_ltv = st.sidebar.selectbox("Cột Giá trị LTV (LTV/Revenue):", cols, index=find_col(['ltv', 'revenue', 'value']))
        
        # --- BƯỚC 3: XỬ LÝ DATA ---
        df_clean = pd.DataFrame()
        
        # 1. Xử lý Ngày tháng (Quan trọng: Fix lỗi 1970)
        # Thử ép kiểu datetime với dayfirst=True (cho định dạng DD/MM/YYYY) hoặc infer
        df_clean['Install Date'] = pd.to_datetime(df[c_date], dayfirst=True, errors='coerce')
        
        # Nếu convert thất bại quá nhiều, thử parse kiểu khác
        if df_clean['Install Date'].isna().sum() > 0.5 * len(df_clean):
             df_clean['Install Date'] = pd.to_datetime(df[c_date], format='mixed', errors='coerce')

        df_clean = df_clean.dropna(subset=['Install Date']) # Bỏ dòng lỗi ngày

        # 2. Lấy dữ liệu khác
        df_clean['Country'] = df[c_country]
        df_clean['Days Since Install'] = pd.to_numeric(df[c_days], errors='coerce').fillna(0).astype(int)
        
        # 3. Xử lý tiền nong (Clean string -> float)
        def clean_money(x):
            if isinstance(x, str):
                return float(x.replace('$','').replace(',','').replace('%','').strip() or 0)
            return float(x or 0)

        df_clean['Installs'] = df[c_installs].apply(clean_money)
        df_clean['LTV_Value'] = df[c_ltv].apply(clean_money)

        # 4. Logic LTV vs Revenue
        # Nếu cột chọn là LTV (giá trị nhỏ < 100), ta giữ nguyên.
        # Nếu cột chọn là Revenue (giá trị to), ta chia cho Install để ra LTV.
        # Ở đây giả định input là LTV ($/user) như tên cột gợi ý.
        
        # --- BƯỚC 4: TẠO BẢNG PIVOT LTV (CORE FEATURE) ---
        # Lọc các ngày quan trọng: D0, D1, D3, D7, D14, D30...
        target_days = [0, 1, 3, 7, 14, 28, 30, 60, 90]
        df_filtered_days = df_clean[df_clean['Days Since Install'].isin(target_days)]

        # Pivot: Index=[Date, Country], Columns=[Days Since Install], Values=[LTV_Value]
        # Lưu ý: Một ngày install + 1 country chỉ có 1 giá trị install cố định
        
        # Bước 4.1: Group để lấy LTV trung bình tại mỗi Day
        # (Đôi khi data bị duplicate dòng, nên lấy mean hoặc sum tùy cấu trúc file, ở đây lấy max hoặc mean an toàn)
        df_pivot = df_filtered_days.pivot_table(
            index=['Install Date', 'Country', 'Installs'], 
            columns='Days Since Install', 
            values='LTV_Value', 
            aggfunc='max' # Lấy giá trị LTV tích lũy tại ngày đó
        ).reset_index()

        # Rename cột cho đẹp (0 -> D0, 1 -> D1...)
        new_cols = {col: f"LTV D{col}" for col in target_days if col in df_pivot.columns}
        df_pivot = df_pivot.rename(columns=new_cols)

        # Fill NaN bằng 0 (hoặc ffill nếu muốn LTV giữ nguyên giá trị cũ)
        df_pivot = df_pivot.fillna(0)

        # --- BƯỚC 5: HIỂN THỊ ---
        
        # Bộ lọc
        st.header("🔍 Filter")
        col1, col2 = st.columns(2)
        countries = ['All'] + sorted(df_pivot['Country'].astype(str).unique().tolist())
        selected_country = col1.selectbox("Quốc gia:", countries)
        
        if selected_country != 'All':
            df_display = df_pivot[df_pivot['Country'] == selected_country]
        else:
            df_display = df_pivot

        # Sắp xếp theo ngày giảm dần
        df_display = df_display.sort_values('Install Date', ascending=False)

        # Format lại ngày hiển thị
        df_display['Install Date'] = df_display['Install Date'].dt.strftime('%Y-%m-%d')

        st.subheader(f"📊 Bảng LTV Cohort ({selected_country})")
        
        # Tô màu (Heatmap style)
        # Chọn các cột LTV Dx hiện có
        ltv_cols = [c for c in df_display.columns if "LTV D" in str(c)]
        
        st.dataframe(
            df_display.style.format({
                "Installs": "{:,.0f}",
                **{c: "${:.4f}" for c in ltv_cols} # Format 4 số thập phân cho LTV
            }).background_gradient(subset=ltv_cols, cmap="Greens", axis=None),
            use_container_width=True,
            height=600
        )

        # Chart so sánh D0 vs D3 vs D7
        if len(ltv_cols) >= 2:
            st.subheader("📈 Xu hướng LTV theo thời gian")
            chart_data = df_display.melt(id_vars=['Install Date'], value_vars=ltv_cols, var_name='Day', value_name='LTV')
            fig = px.line(chart_data, x='Install Date', y='LTV', color='Day', title="LTV Growth Curve")
            st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Lỗi xử lý: {e}")
        st.warning("Sếp check lại xem có đúng cột 'Days since install' (0, 1, 2...) không nhé?")