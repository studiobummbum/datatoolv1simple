import streamlit as st
import pandas as pd
import numpy as np
import io

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="LTV Dashboard V4.0", layout="wide")

# --- CSS TÙY CHỈNH (CHO ĐẸP) ---
st.markdown("""
<style>
    .stDataFrame {border: 1px solid #e0e0e0; border-radius: 5px;}
    .metric-card {background-color: #f0f2f6; padding: 15px; border-radius: 10px; text-align: center;}
</style>
""", unsafe_allow_html=True)

# --- TIÊU ĐỀ ---
st.title("🚀 Mobile App LTV Dashboard - V4.0")
st.markdown("Analyze your monetization performance like a Pro!")

# --- HÀM XỬ LÝ DỮ LIỆU (CORE LOGIC) ---
@st.cache_data
def process_data(df):
    try:
        # 1. Chuẩn hóa tên cột (xóa khoảng trắng thừa, về chữ thường)
        df.columns = df.columns.str.strip().str.lower()
        
        # 2. Map tên cột từ file CSV sang tên chuẩn của code
        # Sếp có thể thêm các biến thể tên cột vào đây nếu file CSV thay đổi
        col_mapping = {
            'date': 'date',
            'country': 'country',
            'installs': 'installs',
            'd0 ad revenue': 'd0_rev', 'd0 revenue': 'd0_rev',
            'd1 ad revenue': 'd1_rev', 'd1 revenue': 'd1_rev',
            'd3 ad revenue': 'd3_rev', 'd3 revenue': 'd3_rev',
            # Nếu sếp muốn thêm D7, D14 sau này thì thêm vào đây
        }
        
        df = df.rename(columns=col_mapping)
        
        # 3. Kiểm tra các cột bắt buộc
        required_cols = ['date', 'country', 'installs', 'd0_rev', 'd1_rev', 'd3_rev']
        missing_cols = [c for c in required_cols if c not in df.columns]
        
        if missing_cols:
            return None, f"Thiếu cột trong file CSV: {', '.join(missing_cols)}"

        # 4. Xử lý dữ liệu
        df['date'] = pd.to_datetime(df['date'])
        
        # Chuyển đổi số liệu sang numeric (xử lý lỗi nếu có ký tự lạ)
        numeric_cols = ['installs', 'd0_rev', 'd1_rev', 'd3_rev']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # 5. Tính toán LTV (Revenue / Installs)
        # Tránh chia cho 0
        df['ltv_d0'] = np.where(df['installs'] > 0, df['d0_rev'] / df['installs'], 0)
        df['ltv_d1'] = np.where(df['installs'] > 0, (df['d0_rev'] + df['d1_rev']) / df['installs'], 0)
        df['ltv_d3'] = np.where(df['installs'] > 0, (df['d0_rev'] + df['d1_rev'] + df['d3_rev']) / df['installs'], 0)

        # Sắp xếp
        df = df.sort_values(by='date', ascending=False)
        
        return df, None
        
    except Exception as e:
        return None, f"Lỗi xử lý dữ liệu: {str(e)}"

# --- SIDEBAR: UPLOAD & CONTROLS ---
with st.sidebar:
    st.header("📂 Data Input")
    
    # Nút Clear Cache
    if st.button("🗑️ Xóa Cache & Reset Data", type="primary"):
        st.cache_data.clear()
        if 'uploaded_file' in st.session_state:
            del st.session_state['uploaded_file']
        st.rerun()

    uploaded_file = st.file_uploader("Upload CSV Report", type=['csv'])

    st.markdown("---")
    st.header("⚙️ Hiển thị")

# --- MAIN APP ---
if uploaded_file is not None:
    # Đọc file
    try:
        df_raw = pd.read_csv(uploaded_file)
        df_processed, error_msg = process_data(df_raw)

        if error_msg:
            st.error(f"❌ {error_msg}")
        else:
            # --- BỘ LỌC (FILTERS) ---
            st.subheader("🔍 Bộ lọc dữ liệu")
            col_f1, col_f2 = st.columns(2)
            
            with col_f1:
                # Lọc Country
                all_countries = ['All'] + sorted(df_processed['country'].unique().tolist())
                selected_country = st.selectbox("Chọn Quốc gia:", all_countries)
            
            with col_f2:
                # Lọc Date Range
                min_date = df_processed['date'].min()
                max_date = df_processed['date'].max()
                date_range = st.date_input(
                    "Chọn khoảng thời gian:",
                    value=(min_date, max_date),
                    min_value=min_date,
                    max_value=max_date
                )

            # Áp dụng bộ lọc
            df_view = df_processed.copy()
            
            if selected_country != 'All':
                df_view = df_view[df_view['country'] == selected_country]
            
            if len(date_range) == 2:
                start_date, end_date = date_range
                df_view = df_view[(df_view['date'].dt.date >= start_date) & (df_view['date'].dt.date <= end_date)]

            # --- TÙY CHỌN CỘT HIỂN THỊ (TOGGLE COLUMNS) ---
            with st.sidebar:
                st.subheader("👁️ Chọn cột hiển thị")
                
                # Mặc định các cột này luôn hiện
                default_cols = ['date', 'country', 'installs']
                
                # Các cột có thể bật tắt
                toggle_options = {
                    'LTV D0': 'ltv_d0',
                    'LTV D1': 'ltv_d1',
                    'LTV D3': 'ltv_d3',
                    'Revenue D0': 'd0_rev', # Thêm option xem doanh thu gốc nếu cần
                    'Revenue D1': 'd1_rev',
                    'Revenue D3': 'd3_rev'
                }
                
                selected_metrics = []
                # Mặc định tích chọn LTV D0, D1, D3
                if st.checkbox("LTV D0", value=True): selected_metrics.append('ltv_d0')
                if st.checkbox("LTV D1", value=True): selected_metrics.append('ltv_d1')
                if st.checkbox("LTV D3", value=True): selected_metrics.append('ltv_d3')
                
                st.markdown("---")
                st.caption("Raw Revenue Metrics:")
                if st.checkbox("Rev D0", value=False): selected_metrics.append('d0_rev')
                if st.checkbox("Rev D1", value=False): selected_metrics.append('d1_rev')
                if st.checkbox("Rev D3", value=False): selected_metrics.append('d3_rev')

            # --- HIỂN THỊ BẢNG ---
            st.success(f"✅ Đã tải xong! Hiển thị {len(df_view)} dòng dữ liệu.")
            
            # Chuẩn bị cột cuối cùng để hiển thị
            final_cols = default_cols + selected_metrics
            
            # Format hiển thị cho đẹp ($ và 4 số thập phân)
            column_config = {
                "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                "country": "Country",
                "installs": st.column_config.NumberColumn("Installs", format="%d"),
                "ltv_d0": st.column_config.NumberColumn("LTV D0", format="$%.4f"),
                "ltv_d1": st.column_config.NumberColumn("LTV D1", format="$%.4f"),
                "ltv_d3": st.column_config.NumberColumn("LTV D3", format="$%.4f"),
                "d0_rev": st.column_config.NumberColumn("Rev D0", format="$%.2f"),
                "d1_rev": st.column_config.NumberColumn("Rev D1", format="$%.2f"),
                "d3_rev": st.column_config.NumberColumn("Rev D3", format="$%.2f"),
            }

            st.dataframe(
                df_view[final_cols],
                use_container_width=True,
                column_config=column_config,
                hide_index=True
            )
            
            # --- DEBUG INFO (Ẩn trong expander cho gọn) ---
            with st.expander("🛠️ Debug: Thông số file raw"):
                st.write(df_raw.head())
                st.write(df_raw.dtypes)

    except Exception as e:
        st.error(f"Lỗi đọc file: {e}")
else:
    # Màn hình chờ
    st.info("👈 Sếp ơi, upload file CSV bên trái để bắt đầu soi LTV nhé!")
    
    # Hướng dẫn format file
    with st.expander("ℹ️ Hướng dẫn format file CSV chuẩn"):
        st.markdown("""
        File CSV cần có các cột sau (tên không phân biệt hoa thường):
        - **Date**: Ngày tháng
        - **Country**: Quốc gia
        - **Installs**: Số lượng cài đặt
        - **D0 Revenue**: Doanh thu ngày 0
        - **D1 Revenue**: Doanh thu ngày 1
        - **D3 Revenue**: Doanh thu ngày 3
        """)