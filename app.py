import streamlit as st
import pandas as pd
import io

# Cấu hình trang
st.set_page_config(page_title="AdMob Cohort Analyzer", layout="wide")

st.title("📊 AdMob Cohort LTV Analyzer (Auto-Pivot) - V3.1 Ultimate")
st.markdown("Upload file CSV AdMob Cohort. Hệ thống sẽ tự động xoay dữ liệu từ Dọc sang Ngang.")

# Upload file
uploaded_file = st.file_uploader("Chọn file CSV từ AdMob", type=['csv'])

if uploaded_file is not None:
    try:
        # --- 1. ĐỌC FILE & XỬ LÝ LỖI SYNTAX ---
        try:
            # Thử đọc bình thường, bỏ qua 2 dòng đầu (thường là title report)
            df = pd.read_csv(uploaded_file, skiprows=2, on_bad_lines='skip')
            # Check nhanh xem có cột Date không
            if not any('date' in col.lower() for col in df.columns):
                 raise ValueError("Header mismatch")
        except:
            # Fallback: Đọc lại từ đầu, tự tìm header
            uploaded_file.seek(0)
            df = pd.read_csv(uploaded_file, header=0, on_bad_lines='skip')

        # --- 2. CLEAN DATA & SMART MAPPING (Quan trọng) ---
        df.columns = df.columns.astype(str).str.strip() # Xóa khoảng trắng thừa
        
        # Hàm tìm cột thông minh (không phân biệt hoa thường)
        def find_column(keywords, columns):
            for col in columns:
                for kw in keywords:
                    if kw.lower() in col.lower():
                        return col
            return None

        # Mapping các biến thể tên cột (Thêm 'install country' vào list ưu tiên)
        col_date = find_column(['install date', 'date', 'ngày'], df.columns)
        
        # KEY FIX: Thêm 'install country' lên đầu để bắt dính file của sếp
        col_country = find_column(['install country', 'country', 'region', 'geography', 'territory', 'quốc gia'], df.columns)
        
        col_day = find_column(['days since install', 'day', 'ngày kể từ'], df.columns)
        
        # Cột Installs: Tránh nhầm với 'Day'
        col_installs = None
        for col in df.columns:
            c_low = col.lower()
            # Tìm cột có chữ install nhưng không phải là date hay country hay day
            if 'install' in c_low and 'day' not in c_low and 'date' not in c_low and 'country' not in c_low:
                col_installs = col
                break
        
        # Cột LTV/Revenue
        col_ltv = find_column(['ltv', 'revenue', 'earnings', 'doanh thu'], df.columns)

        # --- 3. XỬ LÝ NGOẠI LỆ ---
        missing_cols = []
        if not col_date: missing_cols.append("Date (Ngày)")
        if not col_day: missing_cols.append("Day (Ngày retention)")
        if not col_ltv: missing_cols.append("LTV/Revenue")
        
        # Fallback cho Country
        if not col_country:
            st.warning("⚠️ Không tìm thấy cột Country. Hệ thống sẽ gộp chung thành 'Global'.")
            df['Country_Fake'] = 'Global'
            col_country = 'Country_Fake'

        if missing_cols:
            st.error(f"❌ File thiếu các cột: {', '.join(missing_cols)}")
            st.write("Các cột hiện có:", list(df.columns))
            st.stop()

        # Đổi tên về chuẩn
        df = df.rename(columns={
            col_date: 'Date',
            col_country: 'Country',
            col_day: 'Day',
            col_installs: 'Installs',
            col_ltv: 'LTV'
        })

        # Convert dữ liệu
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce').dt.date
        df = df.dropna(subset=['Date']) 
        
        if col_installs is None:
             df['Installs'] = 0
        else:
             if df['Installs'].dtype == object:
                df['Installs'] = df['Installs'].astype(str).str.replace(',', '').astype(float)

        if df['LTV'].dtype == object:
             df['LTV'] = df['LTV'].astype(str).str.replace(r'[$,₫]', '', regex=True).astype(float)

        # --- 4. LOGIC XOAY TRỤC (PIVOT) ---
        target_days = [0, 1, 3, 7, 14, 28] # Em mở rộng thêm D7, D14, D28 cho sếp luôn
        
        df_filtered = df[df['Day'].isin(target_days)].copy()

        pivot_df = df_filtered.pivot_table(
            index=['Date', 'Country', 'Installs'], 
            columns='Day', 
            values='LTV', 
            aggfunc='sum'
        ).reset_index()

        pivot_df.columns.name = None
        rename_map = {d: f'LTV D{d}' for d in target_days}
        pivot_df = pivot_df.rename(columns=rename_map)
        pivot_df = pivot_df.fillna(0)
        
        pivot_df = pivot_df.sort_values(by=['Date', 'Installs'], ascending=[False, False])

        # --- 5. HIỂN THỊ ---
        st.subheader("✅ Kết quả phân tích")
        
        # Format cột động (vì có thể thiếu D7, D14 nếu data mới)
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
        st.error(f"❌ Lỗi: {str(e)}")

else:
    st.info("👋 Sếp upload file đi, code này bao sân vụ tên cột rồi!")