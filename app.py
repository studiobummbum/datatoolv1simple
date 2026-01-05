import streamlit as st
import pandas as pd
import io

# Cấu hình trang (Phải đặt đầu tiên)
st.set_page_config(page_title="Monetization Data Tool", layout="wide")

st.title("🛠️ Monetization Data Cleaner")
st.markdown("Tool xử lý file CSV lỗi format, lệch dòng (IronSource, AppLovin, etc.)")

# --- HÀM XỬ LÝ LOGIC (Đã tối ưu cho Streamlit) ---
def clean_currency(x):
    if isinstance(x, str):
        return x.replace('$', '').replace(',', '').strip()
    return x

@st.cache_data(ttl=300) # Cache data để tránh reload lại nặng server
def process_monetization_report(uploaded_file):
    try:
        # Đọc file buffer
        uploaded_file.seek(0)
        
        # Tìm header (Logic cũ em đã viết)
        header_row_index = 0
        df_temp = pd.read_csv(uploaded_file, header=None, nrows=15) # Đọc thử 15 dòng
        uploaded_file.seek(0)

        found = False
        for idx, row in df_temp.iterrows():
            row_str = row.astype(str).str.lower().tolist()
            # Tìm keywords đặc trưng
            if any(k in str(s) for s in row_str for k in ['country', 'installs', 'date']):
                header_row_index = idx
                found = True
                break
        
        # Đọc lại với header đúng
        df = pd.read_csv(uploaded_file, header=header_row_index)
        
        # Chuẩn hóa cột
        df.columns = df.columns.str.strip()
        
        # Xử lý Date
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df = df.dropna(subset=['Date'])

        # Xử lý Số
        numeric_cols = [c for c in df.columns if c not in ['Date', 'Country', 'Campaign', 'Ad Network']]
        for col in numeric_cols:
            df[col] = df[col].apply(clean_currency)
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        return df, header_row_index

    except Exception as e:
        return None, str(e)

# --- GIAO DIỆN CHÍNH ---

uploaded_file = st.file_uploader("Upload file CSV report vào đây sếp ơi", type=['csv'])

if uploaded_file is not None:
    with st.spinner('Đang xử lý dữ liệu...'):
        df_result, debug_info = process_monetization_report(uploaded_file)
        
        if df_result is not None:
            st.success(f"✅ Xử lý thành công! Tìm thấy header tại dòng: {debug_info}")
            
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
            st.error(f"❌ Lỗi rồi sếp ơi: {debug_info}")

else:
    st.info("👈 Chưa có file nào được upload.")