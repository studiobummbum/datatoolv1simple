import streamlit as st
import pandas as pd
import io

# Cấu hình trang (Phải đặt đầu tiên)
st.set_page_config(page_title="Monetization Data Tool", layout="wide")

st.title("🛠️ Monetization Data Cleaner")
st.markdown("Tool xử lý file CSV lỗi format, lệch dòng (IronSource, AppLovin, AdMob, etc.)")

# --- HÀM XỬ LÝ LOGIC (Đã nâng cấp Auto-Detect Encoding) ---
def clean_currency(x):
    if isinstance(x, str):
        # Xóa $, dấu phẩy, khoảng trắng thừa
        return x.replace('$', '').replace(',', '').strip()
    return x

@st.cache_data(ttl=300)
def process_monetization_report(uploaded_file):
    # Danh sách các encoding thường gặp trong report Ad Tech
    encodings_to_try = ['utf-8', 'utf-16', 'utf-8-sig', 'latin-1', 'cp1252']
    
    df_temp = None
    used_encoding = None
    error_msg = ""

    # 1. Thử đọc file với các encoding khác nhau
    for encoding in encodings_to_try:
        try:
            uploaded_file.seek(0) # Reset con trỏ về đầu file trước mỗi lần thử
            # Đọc thử 20 dòng để check encoding và tìm header
            df_temp = pd.read_csv(uploaded_file, header=None, nrows=20, encoding=encoding, sep=None, engine='python')
            used_encoding = encoding
            break # Đọc được rồi thì thoát vòng lặp
        except Exception as e:
            error_msg = str(e)
            continue

    if df_temp is None:
        return None, f"Không đọc được file với các định dạng phổ biến. Lỗi cuối cùng: {error_msg}"

    try:
        # 2. Tìm dòng Header (Logic dò tìm thông minh)
        header_row_index = 0
        found = False
        
        # Reset file pointer để đọc full file với encoding đã tìm được
        uploaded_file.seek(0)
        
        # Duyệt qua bảng tạm để tìm keywords
        for idx, row in df_temp.iterrows():
            row_str = row.astype(str).str.lower().tolist()
            # Tìm keywords đặc trưng của report (Date, Country, Impressions, Est. Earnings...)
            keywords = ['date', 'country', 'ad unit', 'application', 'impressions', 'estimated earnings', 'requests']
            if any(k in str(s) for s in row_str for k in keywords):
                header_row_index = idx
                found = True
                break
        
        # 3. Đọc lại toàn bộ file với header đúng
        # Lưu ý: sep=None và engine='python' giúp tự động nhận diện dấu phẩy hoặc tab
        df = pd.read_csv(uploaded_file, header=header_row_index, encoding=used_encoding, sep=None, engine='python')
        
        # 4. Chuẩn hóa dữ liệu
        df.columns = df.columns.str.strip() # Xóa khoảng trắng ở tên cột
        
        # Xử lý cột Date (nếu có)
        date_cols = [c for c in df.columns if 'date' in c.lower()]
        if date_cols:
            col_name = date_cols[0]
            df[col_name] = pd.to_datetime(df[col_name], errors='coerce')
            df = df.dropna(subset=[col_name]) # Bỏ dòng tổng cộng hoặc rác ở cuối

        # Xử lý Số (Currency, Number)
        # Loại trừ các cột text
        exclude_cols = ['Date', 'Country', 'Campaign', 'Ad Network', 'Ad Unit', 'App', 'Platform']
        numeric_cols = [c for c in df.columns if not any(ex in c for ex in exclude_cols)]
        
        for col in numeric_cols:
            # Chỉ xử lý nếu cột kiểu object (string)
            if df[col].dtype == 'object':
                df[col] = df[col].apply(clean_currency)
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        return df, f"Encoding: {used_encoding} | Header line: {header_row_index}"

    except Exception as e:
        return None, f"Lỗi xử lý data: {str(e)}"

# --- GIAO DIỆN CHÍNH ---

uploaded_file = st.file_uploader("Upload file CSV report vào đây sếp ơi", type=['csv', 'txt'])

if uploaded_file is not None:
    with st.spinner('Đang soi encoding và xử lý dữ liệu...'):
        df_result, debug_info = process_monetization_report(uploaded_file)
        
        if df_result is not None:
            st.success(f"✅ Xử lý thành công! ({debug_info})")
            
            # Hiển thị thống kê nhanh
            st.write(f"📊 **Tổng quan:** {df_result.shape[0]} dòng dữ liệu.")
            
            # Hiển thị data
            st.dataframe(df_result, use_container_width=True)
            
            # Nút download
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df_result.to_excel(writer, index=False, sheet_name='Cleaned Data')
                
            st.download_button(
                label="📥 Tải về file Excel sạch đẹp",
                data=buffer,
                file_name="cleaned_monet_data.xlsx",
                mime="application/vnd.ms-excel"
            )
        else:
            st.error(f"❌ Vẫn lỗi sếp ơi: {debug_info}")

else:
    st.info("👈 Chưa có file nào được upload.")