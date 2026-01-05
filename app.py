import streamlit as st
import pandas as pd
import io

# Cấu hình trang
st.set_page_config(page_title="AdMob Cohort Analyzer", layout="wide")

st.title("📊 AdMob Cohort LTV Analyzer (V3.2 - Fix Encoding)")
st.markdown("Upload file CSV AdMob Cohort. Hệ thống tự động xử lý lỗi font (UTF-8/UTF-16) và xoay chiều dữ liệu.")

# Upload file
uploaded_file = st.file_uploader("Chọn file CSV từ AdMob", type=['csv'])

if uploaded_file is not None:
    try:
        # --- 1. XỬ LÝ ENCODING (VÒNG LẶP DÒ MÃ) ---
        # Đây là phần fix cho lỗi 0xff sếp gặp phải
        # File Excel/AdMob thường là utf-16, file thường là utf-8
        encodings_to_try = ['utf-8', 'utf-16', 'latin1', 'iso-8859-1']
        df = None
        
        for encoding in encodings_to_try:
            try:
                uploaded_file.seek(0) # Reset con trỏ về đầu file trước mỗi lần thử
                # Thử đọc bỏ qua 2 dòng đầu (format chuẩn AdMob)
                df = pd.read_csv(uploaded_file, skiprows=2, encoding=encoding, on_bad_lines='skip')
                
                # Check nhanh xem có cột nào chứa từ khóa ngày tháng không để confirm đọc đúng
                # Vì nếu đọc sai encoding nó sẽ ra toàn ký tự lạ
                if any('date' in str(col).lower() for col in df.columns) or \
                   any('country' in str(col).lower() for col in df.columns):
                    break # Đọc thành công, thoát vòng lặp
            except Exception:
                continue # Thử encoding tiếp theo
        
        # Nếu vẫn chưa đọc được, thử lại với header=0 (trường hợp file đã clean header)
        if df is None or len(df.columns) < 2:
            for encoding in encodings_to_try:
                try:
                    uploaded_file.seek(0)
                    df = pd.read_csv(uploaded_file, header=0, encoding=encoding, on_bad_lines='skip')
                    if len(df) > 0: break
                except:
                    continue

        if df is None:
            st.error("❌ Không thể đọc file với bất kỳ định dạng mã hóa nào. Vui lòng kiểm tra lại file CSV.")
            st.stop()

        # --- 2. CLEAN DATA & SMART MAPPING ---
        df.columns = df.columns.astype(str).str.strip() # Xóa khoảng trắng thừa
        
        # Hàm tìm cột thông minh
        def find_column(keywords, columns):
            for col in columns:
                for kw in keywords:
                    if kw.lower() in col.lower():
                        return col
            return None

        # Mapping các biến thể tên cột
        col_date = find_column(['install date', 'date', 'ngày'], df.columns)
        
        # Tìm cột Country (bao gồm cả 'install country' của sếp)
        col_country = find_column(['install country', 'country', 'region', 'geography', 'territory', 'quốc gia'], df.columns)
        
        col_day = find_column(['days since install', 'day', 'ngày kể từ'], df.columns)
        
        # Cột Installs: Logic loại trừ để không bắt nhầm cột khác
        col_installs = None
        for col in df.columns:
            c_low = col.lower()
            if 'install' in c_low and 'day' not in c_low and 'date' not in c_low and 'country' not in c_low:
                col_installs = col
                break
        
        col_ltv = find_column(['ltv', 'revenue', 'earnings', 'doanh thu'], df.columns)

        # --- 3. KIỂM TRA CỘT ---
        missing_cols = []
        if not col_date: missing_cols.append("Date")
        if not col_day: missing_cols.append("Day")
        if not col_ltv: missing_cols.append("LTV")
        
        # Fallback cho Country nếu không tìm thấy
        if not col_country:
            st.warning("⚠️ Không tìm thấy cột Country. Hệ thống sẽ gộp chung data.")
            df['Country_Fake'] = 'All'
            col_country = 'Country_Fake'

        if missing_cols:
            st.error(f"❌ File thiếu các cột quan trọng: {', '.join(missing_cols)}")
            st.write("Các cột hệ thống đọc được:", list(df.columns))
            st.stop()

        # Đổi tên về chuẩn để dễ xử lý
        df = df.rename(columns={
            col_date: 'Date',
            col_country: 'Country',
            col_day: 'Day',
            col_installs: 'Installs',
            col_ltv: 'LTV'
        })

        # --- 4. XỬ LÝ DATA TYPE ---
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.date
        df = df.dropna(subset=['Date']) 
        
        if col_installs is None:
             df['Installs'] = 0
        else:
             # Xử lý số có dấu phẩy (ví dụ: 1,000)
             if df['Installs'].dtype == object:
                df['Installs'] = df['Installs'].astype(str).str.replace(',', '').astype(float)

        if df['LTV'].dtype == object:
             df['LTV'] = df['LTV'].astype(str).str.replace(r'[$,₫]', '', regex=True).astype(float)

        # --- 5. XOAY TRỤC (PIVOT) ---
        target_days = [0, 1, 3, 7, 14, 28, 30, 60] # List mốc retention/LTV quan trọng
        
        # Chỉ lấy những dòng có Day nằm trong list target để pivot cho gọn
        df_filtered = df[df['Day'].isin(target_days)].copy()

        # Pivot: Index là Date/Country/Installs, Cột là Day, Giá trị là LTV
        pivot_df = df_filtered.pivot_table(
            index=['Date', 'Country', 'Installs'], 
            columns='Day', 
            values='LTV', 
            aggfunc='sum'
        ).reset_index()

        # Làm đẹp tên cột
        pivot_df.columns.name = None
        rename_map = {d: f'LTV D{d}' for d in target_days}
        pivot_df = pivot_df.rename(columns=rename_map)
        
        # Fill NaN bằng 0 (cho những ngày chưa có data)
        pivot_df = pivot_df.fillna(0)
        
        # Sắp xếp giảm dần theo ngày
        pivot_df = pivot_df.sort_values(by=['Date', 'Installs'], ascending=[False, False])

        # --- 6. HIỂN THỊ KẾT QUẢ ---
        st.subheader("✅ Kết quả (Đã fix lỗi Encoding & Tên cột)")
        
        # Format hiển thị
        format_dict = {'Installs': '{:,.0f}'}
        for col in pivot_df.columns:
            if 'LTV' in col:
                format_dict[col] = '${:.4f}'

        st.dataframe(
            pivot_df.style.format(format_dict).background_gradient(cmap='Greens', subset=[c for c in pivot_df.columns if 'LTV' in c]),
            use_container_width=True,
            height=800
        )

    except Exception as e:
        st.error(f"❌ Lỗi hệ thống: {str(e)}")
        st.write("Chi tiết lỗi để debug:", e)

else:
    st.info("👋 Sếp upload lại file đi ạ. Lần này em bao test vụ lỗi font rồi!")