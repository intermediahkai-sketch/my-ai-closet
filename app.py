import streamlit as st
import google.generativeai as genai
from PIL import Image
import uuid
import io
import numpy as np
# 引入去背庫 (第一次執行會下載模型，需時稍長)
from rembg import remove as remove_bg

# --- 設定 API Key ---
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("找不到 API Key，請檢查 Secrets 設定")
    st.stop()

# --- 初始化 Session State ---
if 'wardrobe' not in st.session_state:
    st.session_state.wardrobe = [] 
if 'user_profile' not in st.session_state:
    # 新增 gender 欄位預設值
    st.session_state.user_profile = {
        "gender": "女",
        "height": 160, 
        "measurements": {"bust": 0, "waist": 0, "hips": 0},
        "style_pref": "簡約休閒"
    }
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0
# 用來記錄哪些單品正處於「編輯模式」
if 'edit_modes' not in st.session_state:
    st.session_state.edit_modes = {}

# --- 頁面設定 ---
# 改標題，改 Icon
st.set_page_config(page_title="莫弈的衣帽間", page_icon="🎩", layout="wide")
# 使用 subheader 代替 title，字體較小，顏色較中性
st.subheader("我的造型師莫弈")

# --- 側邊欄 ---
with st.sidebar:
    st.header("1. 👤 個人檔案")
    
    # 新增：性別選擇
    st.session_state.user_profile['gender'] = st.radio(
        "性別 (供 AI 參考剪裁)", 
        ["女", "男", "通用"], 
        index=["女", "男", "通用"].index(st.session_state.user_profile['gender']),
        horizontal=True
    )
    
    h = st.number_input("身高 (cm)", value=st.session_state.user_profile['height'])
    st.session_state.user_profile['height'] = h
    
    with st.expander("輸入三圍數字", expanded=False):
        b = st.number_input("胸圍", value=st.session_state.user_profile['measurements']['bust'])
        w = st.number_input("腰圍", value=st.session_state.user_profile['measurements']['waist'])
        hip = st.number_input("臀圍", value=st.session_state.user_profile['measurements']['hips'])
        st.session_state.user_profile['measurements'] = {"bust": b, "waist": w, "hips": hip}

    st.session_state.user_profile['style_pref'] = st.selectbox(
        "風格偏好", 
        ["簡約休閒", "日系層次", "韓系溫柔", "歐美型格", "復古", "正式/上班", "街頭潮流/型男", "紳士/雅痞"]
    )
    
    st.divider()
    
    # --- 批量上載區 ---
    st.header("2. ➕ 添加單品")
    st.caption("支援自動去背，請耐心等候處理")
    
    col1, col2 = st.columns(2)
    with col1:
        cat_options = ["上衣", "下身褲裝", "下身裙裝", "連身裙/套裝", "外套", "鞋履", "配件/包包"]
        batch_cat = st.selectbox("預設分類", cat_options)
    with col2:
        batch_season = st.selectbox("季節", ["四季", "春夏", "秋冬"])
    
    uploaded_files = st.file_uploader(
        "選擇圖片 (支援多選)", 
        type=["jpg", "png", "jpeg", "webp"], 
        accept_multiple_files=True,
        key=f"uploader_{st.session_state.uploader_key}" 
    )
    
    if uploaded_files:
        # 加入去背開關 (可選)
        do_remove_bg = st.checkbox("✨ 自動去背 (需時較長)", value=True)
        
        if st.button("📥 開始處理並存入"):
            progress_bar = st.progress(0)
            for i, uploaded_file in enumerate(uploaded_files):
                with st.spinner(f"正在處理第 {i+1}/{len(uploaded_files)} 張圖片..."):
                    # 1. 讀取圖片
                    image = Image.open(uploaded_file)
                    
                    # 2. 去背處理 (如果已勾選)
                    final_image = image
                    if do_remove_bg:
                        try:
                            # 將 PIL Image 轉為 bytes
                            img_byte_arr = io.BytesIO()
                            image.save(img_byte_arr, format='PNG')
                            img_bytes = img_byte_arr.getvalue()
                            
                            # 調用 rembg 進行去背
                            output_bytes = remove_bg(img_bytes)
                            
                            # 將結果轉回 PIL Image
                            final_image = Image.open(io.BytesIO(output_bytes))
                        except Exception as e:
                            st.warning(f"圖片 {uploaded_file.name} 去背失敗，將使用原圖。錯誤: {e}")

                    # 3. 存入資料庫
                    item_id = str(uuid.uuid4())
                    item_data = {
                        'id': item_id,
                        'image': final_image, # 儲存處理後的圖
                        'category': batch_cat, 
                        'season': batch_season,
                        'size_data': {'length': '', 'width': '', 'waist': ''}
                    }
                    st.session_state.wardrobe.append(item_data)
                    # 預設不開啟編輯模式
                    st.session_state.edit_modes[item_id] = False
                # 更新進度條
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            st.session_state.uploader_key += 1
            st.success(f"已成功存入 {len(uploaded_files)} 件單品！")
            st.rerun()

    st.divider()
    if st.button("🗑️ 清空所有衣櫃"):
        st.session_state.wardrobe = []
        st.session_state.edit_modes = {}
        st.rerun()

# --- 主畫面 ---
tab1, tab2 = st.tabs(["🧥 衣櫃管理", "✨ 莫弈的建議"])

with tab1:
    if not st.session_state.wardrobe:
        st.info("👈 衣櫃還是空的，請在左側添加你的時尚單品。")
    else:
        # 改良版篩選器：不設 default 值，預設顯示全部，樣式較清爽
        all_cats = list(set([item['category'] for item in st.session_state.wardrobe]))
        selected_cats = st.multiselect("🔍 分類篩選 (留空顯示全部)", all_cats)
        
        # 過濾邏輯
        if selected_cats:
            display_items = [item for item in st.session_state.wardrobe if item['category'] in selected_cats]
        else:
            display_items = st.session_state.wardrobe # 沒選就顯示全部
            
        st.caption(f"共顯示 {len(display_items)} 件單品")

        # 使用 columns 排列圖片
        cols = st.columns(5)
        for i, item in enumerate(display_items):
            with cols[i % 5]:
                # 1. 顯示圖片
                st.image(item['image'], use_column_width=True)
                
                # 2. 緊湊的 Icon 工具列 (Overlay 效果的替代方案)
                # 使用小比例 columns 來緊密排列按鈕
                tool_cols = st.columns([1, 1, 3]) 
                with tool_cols[0]:
                    # 編輯按鈕 (Toggle)
                    btn_label = "✏️"
                    # 如果正在編輯模式，按鈕變色提示
                    if st.session_state.edit_modes.get(item['id'], False):
                         btn_label = "📝" # 編輯中換個 Icon

                    if st.button(btn_label, key=f"edit_btn_{item['id']}", help="編輯詳情"):
                        # 切換編輯狀態
                        current_state = st.session_state.edit_modes.get(item['id'], False)
                        st.session_state.edit_modes[item['id']] = not current_state
                        st.rerun()
                        
                with tool_cols[1]:
                    # 刪除按鈕
                    if st.button("🗑️", key=f"del_btn_{item['id']}", help="刪除此單品"):
                        st.session_state.wardrobe.remove(item)
                        del st.session_state.edit_modes[item['id']]
                        st.rerun()
                        
                with tool_cols[2]:
                    # 顯示簡單分類標籤
                    st.caption(f"{item['category']}")

                # 3. 編輯表單 (只有在編輯模式下才顯示)
                if st.session_state.edit_modes.get(item['id'], False):
                    with st.container(): # 使用 container 包裹編輯區
                        st.markdown("---") # 分隔線
                        # 修改分類
                        new_cat = st.selectbox(
                            "", # 不顯示標籤以節省空間
                            cat_options, 
                            index=cat_options.index(item['category']) if item['category'] in cat_options else 0,
                            key=f"cat_select_{item['id']}",
                            label_visibility="collapsed"
                        )
                        if new_cat != item['category']:
                            item['category'] = new_cat
                            st.rerun()
                            
                        # 輸入尺碼
                        c1, c2, c3 = st.columns(3)
                        item['size_data']['length'] = c1.text_input("長", value=item['size_data']['length'], key=f"l_{item['id']}", placeholder="cm")
                        item['size_data']['width'] = c2.text_input("闊/胸", value=item['size_data']['width'], key=f"w_{item['id']}", placeholder="cm")
                        item['size_data']['waist'] = c3.text_input("腰", value=item['size_data']['waist'], key=f"wa_{item['id']}", placeholder="吋")
                        st.markdown("---")

with tab2:
    st.subheader("✨ 莫弈的造型建議")
    col_w1, col_w2, col_w3 = st.columns(3)
    with col_w1: weather = st.text_input("天氣", "晴天/微風")
    with col_w2: temp = st.text_input("氣溫 (°C)", "22")
    with col_w3: occasion = st.text_input("場合", "約會/上班/休閒")

    if st.button("🪄 請求莫弈的建議"):
        if len(st.session_state.wardrobe) < 2:
            st.warning("衣櫃單品太少，請先添加至少兩件單品（建議包含上下身或連身裙）。")
        else:
            with st.spinner("莫弈正在思考你的專屬造型..."):
                try:
                    p = st.session_state.user_profile
                    # 將性別加入 Prompt
                    user_stats = f"性別: {p['gender']}, 身高: {p['height']}cm, 三圍(胸/腰/臀): {p['measurements']['bust']}/{p['measurements']['waist']}/{p['measurements']['hips']}"
                    
                    prompt = (
                        f"你現在是「莫弈」，一位品味高雅、語氣溫柔沉穩的專業形象設計師。\n"
                        f"【客戶檔案】{user_stats}。\n"
                        f"【風格偏好】{p['style_pref']}。\n"
                        f"【今日場景】天氣: {weather}, 氣溫: {temp}°C, 場合: {occasion}。\n\n"
                        f"【你的任務】\n"
                        f"請從客戶的衣櫃（附圖）中，為她/他搭配出一套最合適的造型。\n"
                        f"1. **造型理念**: 用一段話描述這套搭配的主題和給人的感覺。\n"
                        f"2. **詳細搭配**: 列出選用的單品（需註明編號和類別），並說明搭配理由。\n"
                        f"3. **專業建議**: \n"
                        f"   - 針對客戶的性別、身高和三圍，分析這套衣服的剪裁優勢（例如：如何修飾身形、調節比例）。\n"
                        f"   - 檢查尺碼是否合適，若有過大/過小的風險請溫柔提醒。\n"
                        f"   - 根據天氣和場合，給出實用的穿著建議（例如：是否需要添衣、鞋子選擇）。\n"
                        f"4. **語氣要求**: \n"
                        f"   - 保持「莫弈」的人設：優雅、知性、語氣平和、帶有淡淡的關懷。\n"
                        f"   - 使用流暢自然的廣東話口語。\n"
                        f"   - 不要過於熱情或使用誇張的感嘆號，保持專業的距離感。\n"
                    )
                    
                    inputs = [prompt]
                    # 為了讓 AI 更容易辨識，我們只傳送目前篩選後可見的單品 (如果有的話)，或者全部
                    items_to_send = display_items if 'display_items' in locals() and display_items else st.session_state.wardrobe

                    for i, item in enumerate(items_to_send):
                        size_info = f"L:{item['size_data']['length']} W:{item['size_data']['width']} WA:{item['size_data']['waist']}"
                        # 傳送時加入原有的 index 以便對照
                        original_index = st.session_state.wardrobe.index(item) + 1
                        inputs.append(f"單品#{original_index} [{item['category']}] ({item['season']}) - 尺碼:{size_info}")
                        inputs.append(item['image'])
                    
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    response = model.generate_content(inputs)
                    st.markdown(response.text)
                except Exception as e:
                    st.error(f"發生了一點小意外: {e}")
