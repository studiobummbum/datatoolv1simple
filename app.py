import streamlit as st
import pandas as pd
import io

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="Pro Monetization Analyzer", layout="wide")

# --- HÀM XỬ LÝ ĐỌC FILE "BẤT TỬ" (AUTO-DETECT ENCODING) ---
def load_robust_csv(uploaded_file):
    """
    Hàm này chuyên trị các lỗi encoding khó chịu như utf-8 codec can't decode byte 0xff.
    """
    try_encodings = [
        ('utf-8', ','),          
        ('utf-16', '\t'),        
        ('utf-16', ','),         
        ('utf-16-le', '\t'),     
        ('iso-8859-1', ','),     
        ('cp1252', ',')          
    ]

    for encoding, sep in try_encodings:
        try:
            uploaded_file.seek(0) 
            df = pd.read_csv(uploaded_file, encoding=encoding, sep=sep)
            if df.shape[1] > 1:
                return df, None 
        except Exception:
            continue 

    return None, "Không thể đọc file. Vui lòng đảm bảo file là CSV hoặc Text định dạng chuẩn."

# --- HÀM XỬ LÝ DATA MONETIZATION ---
def process_data(df):
    # 1. Chuẩn hóa tên cột: về chữ thường, bỏ khoảng trắng thừa
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
    
    # 2. Mapping các tên cột phổ biến (ĐÃ UPDATE THÊM ADMOB)
    col_mapping = {
        # Mapping Date
        'day': 'date', 
        'time': 'date',
        'install_date': 'date', # <-- Fix cho AdMob
        
        # Mapping Country
        'country_code': 'country', 
        'geo': 'country',
        'install_country': 'country', # <-- Fix cho AdMob
        
        # Mapping Installs
        'installs': 'installs', 
        'install': 'installs',
        
        # Mapping Revenue & LTV (Nếu file có sẵn LTV thì map luôn)
        'revenue': 'revenue', 
        'estimated_revenue': 'revenue',
        'ltv_(usd)': 'ltv_total', # <-- AdMob hay có cột này
        
        # Các cột Cohort Revenue (ví dụ)
        'r0': 'd0_rev', 'revenue_d0': 'd0_rev',
        'r1': 'd1_rev', 'revenue_d1': 'd1_rev',
        'r3': 'd3_rev', 'revenue_d3': 'd3_rev',
        'r7': 'd7_rev', 'revenue_d7': 'd7_rev',
    }
    df.rename(columns=col_mapping, inplace=True)

    # 3. Kiểm tra các cột bắt buộc
    required_cols = ['date', 'country', 'installs']
    missing_cols = [c for c in required_cols if c not in df.columns]
    
    if missing_cols:
        return None, f"File thiếu các cột bắt buộc: {', '.join(missing_cols)}. Hãy kiểm tra header file CSV."

    # 4. Xử lý kiểu dữ liệu
    try:
        df['date'] = pd.to_datetime(df['date'])
    except:
        return None, "Lỗi định dạng cột Date. Hãy đảm bảo format ngày tháng chuẩn."

    # Fill NaN bằng 0 cho các cột số
    numeric_cols = ['installs', 'd0_rev', 'd1_rev', 'd3_rev', 'd7_rev', 'ltv_total']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # 5. Tính toán chỉ số LTV (Key Metrics)
    # Nếu file AdMob đã có sẵn cột LTV (ltv_total) thì dùng luôn, không cần chia lại
    # Còn nếu là file raw doanh thu theo ngày (d0, d1...) thì mới tính toán
    
    if 'd0_rev' in df.columns:
        df['ltv_d0'] = df['d0_rev'] / df['installs']
    
    # Xử lý chia cho 0 (nếu installs = 0) -> thay bằng 0
    df = df.replace([float('inf'), -float('inf')], 0)

    return df, None

# --- GIAO DIỆN CHÍNH ---
st.title("💰 Mobile App Monetization Analyzer (Pro)")
st.markdown("---")

# Upload File
uploaded_file = st.file_uploader("Upload file CSV (Report từ MAX/Ironsource/AdMob/Excel):", type=['csv', 'txt'])

if uploaded_file is not None:
    # GỌI HÀM ĐỌC FILE BẤT TỬ
    df_raw, error_read = load_robust_csv(uploaded_file)
    
    if error_read:
        st.error(f"❌ {error_read}")
        st.info("Tip: File export từ Excel thường bị lỗi encoding. Code này đã cố gắng fix nhưng file của sếp có thể bị hỏng cấu trúc.")
    else:
        # Xử lý data
        df_processed, error_process = process_data(df_raw)
        
        if error_process:
            st.error(f"❌ {error_process}")
            with st.expander("Xem dữ liệu thô để debug"):
                st.write(df_raw.head())
        else:
            # --- DASHBOARD ---
            
            # 1. Bộ lọc (Filter)
            st.sidebar.header("🔍 Filter Data")
            
            # Filter Country
            country_list = ['All'] + sorted(df_processed['country'].astype(str).unique().tolist())
            selected_country = st.sidebar.selectbox("Country", country_list)
            
            # Filter Date
            min_date = df_processed['date'].min()
            max_date = df_processed['date'].max()
            date_range = st.sidebar.date_input("Date Range", [min_date, max_date])

            # Áp dụng filter
            df_view = df_processed.copy()
            if selected_country != 'All':
                df_view = df_view[df_view['country'] == selected_country]
            
            if len(date_range) == 2:
                df_view = df_view[
                    (df_view['date'].dt.date >= date_range[0]) & 
                    (df_view['date'].dt.date <= date_range[1])
                ]

            # 2. Hiển thị Metrics tổng quan (KPIs)
            st.subheader("📊 Performance Overview")
            total_installs = df_view['installs'].sum()
            
            # Tính Weighted Average LTV
            # Logic: Nếu có cột ltv_total (từ AdMob) thì tính trung bình, nếu có d0_rev thì tính từ revenue
            avg_ltv = 0
            if 'ltv_total' in df_view.columns:
                 # AdMob report thường trả về LTV trung bình sẵn, nhưng để tính tổng quan phải nhân ngược lại install
                 total_revenue = (df_view['ltv_total'] * df_view['installs']).sum()
                 avg_ltv = total_revenue / total_installs if total_installs > 0 else 0
            elif 'd0_rev' in df_view.columns:
                 avg_ltv = df_view['d0_rev'].sum() / total_installs if total_installs > 0 else 0
            
            col1, col2 = st.columns(2)
            col1.metric("Total Installs", f"{int(total_installs):,}")
            col2.metric("Avg LTV (Est.)", f"${avg_ltv:.4f}")

            # 3. Hiển thị Bảng dữ liệu chi tiết
            st.subheader("📋 Detailed Data")
            
            # Chọn cột để hiển thị cho gọn
            default_cols = ['date', 'country', 'installs']
            # Tự động lấy thêm các cột LTV hoặc Revenue nếu có
            optional_cols = ['ltv_total', 'ltv_d0', 'd0_rev', 'retention']
            available_cols = [c for c in optional_cols if c in df_view.columns]
            
            final_cols = default_cols + available_cols
            
            # Config format hiển thị số
            column_config = {
                "date": st.column_config.DateColumn("Date", format="YYYY-MM-DD"),
                "installs": st.column_config.NumberColumn("Installs", format="%d"),
                "ltv_total": st.column_config.NumberColumn("LTV (Total)", format="$%.4f"),
                "ltv_d0": st.column_config.NumberColumn("LTV D0", format="$%.4f"),
            }

            st.dataframe(
                df_view[final_cols].sort_values(by='date', ascending=False),
                use_container_width=True,
                column_config=column_config,
                hide_index=True
            )
            
            # 4. Chart đơn giản (Trend Installs)
            st.subheader("📈 Install Trend")
            chart_data = df_view.groupby('date')['installs'].sum()
            st.line_chart(chart_data)

else:
    st.info("👋 Chào sếp! Vui lòng upload file report CSV để bắt đầu phân tích.")