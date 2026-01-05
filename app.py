import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import io

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="AdMob LTV Analyzer V5", layout="wide", page_icon="🛡️")

# --- HÀM LOAD DATA (GIỮ NGUYÊN VÌ ĐÃ CHẠY NGON) ---
@st.cache_data
def load_data(file):
    encodings = ['utf-8', 'utf-16', 'utf-16le', 'latin1']
    delimiters = [',', '\t', ';']
    
    df = None
    file.seek(0)
    bytes_data = file.read()
    
    for enc in encodings:
        try:
            content = bytes_data.decode(enc)
            first_line = content.split('\n')[0]
            detected_sep = ','
            max_count = 0
            for d in delimiters:
                if first_line.count(d) > max_count:
                    max_count = first_line.count(d)
                    detected_sep = d
            
            df = pd.read_csv(io.StringIO(content), sep=detected_sep)
            if len(df.columns) > 1:
                break
        except:
            continue
            
    if df is None:
        st.error("❌ File hỏng không đọc được.")
        st.stop()

    df.columns = df.columns.str.strip()
    
    # Mapping cột
    column_mapping = {
        'Install date': ['Date', 'Cohort Date', 'install_date'],
        'Days since install': ['Day', 'Days', 'days_since_install'],
        'LTV (USD)': ['LTV', 'ltv', 'LTV ($)'],
        'Installs': ['Users', 'New Users', 'installs'],
        'Install country': ['Country', 'Region', 'install_country']
    }
    
    rename_dict = {}
    for standard_col, variations in column_mapping.items():
        if standard_col not in df.columns:
            for var in variations:
                if var in df.columns:
                    rename_dict[var] = standard_col
                    break
    if rename_dict:
        df = df.rename(columns=rename_dict)
        
    if 'Install date' in df.columns:
        df['Install date'] = pd.to_datetime(df['Install date'], errors='coerce')
        
    return df

# --- GIAO DIỆN CHÍNH ---
st.title("🛡️ AdMob LTV Analyzer (V5 - Clean View)")

uploaded_file = st.file_uploader("Upload file admob-report.csv", type=['csv', 'txt'])

if uploaded_file:
    df = load_data(uploaded_file)
    
    # 1. BỘ LỌC QUỐC GIA
    country_list = sorted(df['Install country'].dropna().unique().tolist())
    selected_country = st.selectbox("🌍 Chọn Quốc Gia (Country):", ["All"] + country_list)
    
    if selected_country != "All":
        df_filtered = df[df['Install country'] == selected_country].copy()
    else:
        df_filtered = df.copy()

    # 2. XỬ LÝ PIVOT DATA (LOGIC MỚI ĐỂ KHÔNG BỊ LỖI CỘT)
    try:
        # Pivot bảng LTV: Dòng là Date, Cột là Days (0, 1, 2...), Giá trị là LTV
        # Nếu chọn "All" country thì phải tính trung bình có trọng số (Weighted Avg) hơi phức tạp
        # Nên ở đây ta group by Date và Days trước để tính tổng LTV và Installs
        
        # Bước 1: Tổng hợp data theo Date và Days
        df_agg = df_filtered.groupby(['Install date', 'Days since install']).agg({
            'LTV (USD)': 'mean', # LTV trong file AdMob thường là Cumulative Avg LTV rồi, nên lấy mean hoặc max
            'Installs': 'max'    # Installs của ngày đó là cố định cho cohort
        }).reset_index()

        # Bước 2: Pivot
        df_pivot = df_agg.pivot(index='Install date', columns='Days since install', values='LTV (USD)')
        
        # Bước 3: Lấy cột Installs (chỉ cần lấy ở Day 0)
        df_installs = df_filtered[df_filtered['Days since install'] == 0].groupby('Install date')['Installs'].sum()
        
        # Bước 4: Ghép lại thành bảng final
        df_final = pd.DataFrame(df_installs).join(df_pivot)
        
        # Bước 5: Thêm cột Country cho bảng hiển thị
        df_final['Country'] = selected_country
        
        # Sắp xếp giảm dần theo ngày
        df_final = df_final.sort_index(ascending=False)
        
    except Exception as e:
        st.error(f"❌ Lỗi xử lý data: {e}")
        st.stop()

    # 3. CHỈNH SỬA BẢNG HIỂN THỊ (QUAN TRỌNG)
    # Reset index để đưa 'Install date' thành cột bình thường
    display_df = df_final.reset_index()
    
    # Chọn các cột cần hiển thị: Country, Date, Installs, D0 -> D3
    cols_to_show = ['Country', 'Install date', 'Installs']
    
    # Chỉ lấy D0, D1, D2, D3 như sếp yêu cầu
    target_days = [0, 1, 2, 3]
    available_days = [col for col in target_days if col in display_df.columns]
    
    final_cols = cols_to_show + available_days
    display_df = display_df[final_cols]

    # Đổi tên cột cho đẹp (0 -> LTV D0)
    rename_map = {d: f"LTV D{d}" for d in available_days}
    display_df = display_df.rename(columns=rename_map)

    # 4. HIỂN THỊ METRICS TỔNG QUAN (D0 -> D3)
    st.subheader(f"📊 Hiệu suất LTV (D0 - D3) - {selected_country}")
    metric_cols = st.columns(4)
    
    for i, day in enumerate(target_days):
        col_name = f"LTV D{day}"
        if col_name in display_df.columns:
            # Tính Weighted Avg LTV
            valid_rows = display_df.dropna(subset=[col_name])
            if not valid_rows.empty and valid_rows['Installs'].sum() > 0:
                # Công thức chuẩn: Tổng (LTV * User) / Tổng User
                w_avg = (valid_rows[col_name] * valid_rows['Installs']).sum() / valid_rows['Installs'].sum()
                metric_cols[i].metric(f"Avg {col_name}", f"${w_avg:.4f}")
            else:
                metric_cols[i].metric(f"Avg {col_name}", "N/A")

    # 5. DATA TABLE
    st.subheader("📋 Bảng chi tiết (Theo yêu cầu)")
    
    # Cấu hình format hiển thị
    column_config = {
        "Install date": st.column_config.DateColumn("Cohort Date", format="YYYY-MM-DD"),
        "Installs": st.column_config.NumberColumn("Users", format="%d"),
        "Country": st.column_config.TextColumn("Country"),
    }
    
    # Format các cột LTV thành tiền tệ 4 số thập phân
    for day in available_days:
        column_config[f"LTV D{day}"] = st.column_config.NumberColumn(f"LTV D{day}", format="$%.4f")

    st.dataframe(
        display_df, 
        column_config=column_config, 
        hide_index=True,  # Ẩn cái cột số thứ tự vô duyên đi
        use_container_width=True
    )

else:
    st.info("Sếp upload file đi ạ, code V5 này bao chuẩn form!")