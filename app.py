import streamlit as st
import pandas as pd
import io

# Cấu hình trang
st.set_page_config(page_title="AdMob Cohort Analyzer", layout="wide")

st.title("📊 AdMob Cohort LTV Analyzer (Auto-Pivot)")
st.markdown("Upload file CSV AdMob Cohort. Hệ thống sẽ tự động xoay dữ liệu từ Dọc sang Ngang.")

# Upload file
uploaded_file = st.file_uploader("Chọn file CSV từ AdMob", type=['csv'])

if uploaded_file is not None:
    try:
        # --- 1. ĐỌC FILE & XỬ LÝ LỖI SYNTAX ---
        # AdMob CSV đôi khi bị lỗi dòng hoặc format lạ, dùng on_bad_lines='skip' để an toàn
        # skiprows=2: Thường report AdMob có 2 dòng tiêu đề thừa ở trên cùng
        try:
            df = pd.read_csv(uploaded_file, skiprows=2, on_bad_lines='skip')
        except:
            # Nếu lỗi encoding hoặc format, thử đọc lại với encoding khác và không skip dòng
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, encoding='utf-16', sep='\t', on_bad_lines='skip')

        # --- 2. CLEAN DATA (Làm sạch) ---
        df.columns = df.columns.str.strip() # Xóa khoảng trắng thừa ở tên cột
        
        # Tự động tìm cột dựa trên từ khóa (Smart Mapping)
        cols = df.columns.str.lower()
        
        col_date = next((c for c in df.columns if 'date' in c.lower()), None)
        col_country = next((c for c in df.columns if 'country' in c.lower()), None)
        col_day = next((c for c in df.columns if 'day' in c.lower() and 'install' in c.lower()), None) # Days since install
        col_installs = next((c for c in df.columns if 'install' in c.lower() and 'day' not in c.lower() and 'date' not in c.lower()), None)
        
        # Tìm cột LTV (Ưu tiên cột tổng hợp, nếu không có thì lấy cột doanh thu)
        col_ltv = next((c for c in df.columns if 'ltv' in c.lower()), None)
        if not col_ltv:
             col_ltv = next((c for c in df.columns if 'revenue' in c.lower() or 'estimated earnings' in c.lower()), None)

        # Kiểm tra nếu thiếu cột quan trọng
        if not all([col_date, col_country, col_day, col_ltv]):
            st.error("❌ Không nhận diện được cấu trúc file. Sếp kiểm tra lại xem có đúng file Cohort không nhé.")
            st.write("Các cột tìm được:", {"Date": col_date, "Country": col_country, "Day": col_day, "LTV": col_ltv})
            st.stop()

        # Đổi tên về chuẩn
        df = df.rename(columns={
            col_date: 'Date',
            col_country: 'Country',
            col_day: 'Day',
            col_installs: 'Installs',
            col_ltv: 'LTV'
        })

        # Convert Date
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.date
        df = df.dropna(subset=['Date']) # Bỏ dòng không có ngày tháng

        # --- 3. LOGIC XOAY TRỤC (PIVOT) ---
        # Đây là bước biến đổi dữ liệu như em giải thích
        
        # Chỉ lấy D0, D1, D3 (Sếp muốn thêm D7, D14 thì thêm vào list này)
        target_days = [0, 1, 3]
        df_filtered = df[df['Day'].isin(target_days)].copy()

        # Pivot Table:
        # - Giữ nguyên cột Date, Country, Installs làm mốc (Index)
        # - Lấy giá trị cột 'Day' biến thành các cột mới (Columns)
        # - Điền giá trị 'LTV' vào các ô tương ứng (Values)
        pivot_df = df_filtered.pivot_table(
            index=['Date', 'Country', 'Installs'], 
            columns='Day', 
            values='LTV', 
            aggfunc='sum' # Dùng sum để gom nếu có dòng trùng, nhưng thường là lấy giá trị duy nhất
        ).reset_index()

        # Đổi tên cột 0, 1, 3 thành LTV D0, LTV D1...
        pivot_df.columns.name = None
        rename_map = {d: f'LTV D{d}' for d in target_days}
        pivot_df = pivot_df.rename(columns=rename_map)

        # Fill 0 cho những ô bị trống (ví dụ mới chạy hôm nay thì chưa có D1, D3)
        pivot_df = pivot_df.fillna(0)
        
        # Sắp xếp
        pivot_df = pivot_df.sort_values(by=['Date', 'Installs'], ascending=[False, False])

        # --- 4. HIỂN THỊ ---
        st.subheader("✅ Bảng dữ liệu đã xử lý")
        
        # Format hiển thị
        st.dataframe(
            pivot_df.style.format({
                'Installs': '{:,.0f}',
                'LTV D0': '${:.4f}',
                'LTV D1': '${:.4f}',
                'LTV D3': '${:.4f}'
            }).background_gradient(subset=['LTV D0', 'LTV D1', 'LTV D3'], cmap='Greens'),
            use_container_width=True,
            height=600
        )

    except Exception as e:
        st.error(f"❌ Lỗi nghiêm trọng: {str(e)}")
        st.warning("Sếp thử mở file CSV bằng Excel, Save As lại dạng 'CSV (Comma delimited)' rồi upload lại xem sao ạ.")

else:
    st.info("👋 Chờ sếp upload file CSV...")