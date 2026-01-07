import streamlit as st
import google.generativeai as genai
from PIL import Image
import uuid # 用來給每件衫一個獨一無二的編號

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
    st.session_state.user_profile = {
        "height": 160, 
        "measurements": {"bust": 0, "waist": 0, "hips": 0},
        "style_pref": "簡約休閒"
    }
# 這是一個計數器，用來強制重置上載元件
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

st.set_page_config(page_title="AI 智能衣櫃 (Pro版)", page_icon="👗", layout="wide")
st.title("👗 AI 智能衣櫃 (管理增強版)")

# --- 側邊欄 ---
with st.sidebar:
    st.header("1. 👤 身型數據")
    h = st.number_input("身高 (cm)", value=st.session_state.user_profile['height'])
    st.session_state.user_profile['height'] = h
    
    with st.expander("輸入三圍", expanded=True):
        b = st.number_input("胸圍", value=st.session_state.user_profile['measurements']['bust'])
        w = st.number_input("腰圍", value=st.session_state.user_profile['measurements']['waist'])
        hip = st.number_input("臀圍", value=st.session_state.user_profile['measurements']['hips'])
        st.session_state.user_profile['measurements'] = {"bust": b, "waist": w, "hips": hip}

    st.session_state.user_profile['style_pref'] = st.selectbox(
        "風格偏好", 
        ["簡約休閒", "日系層次", "韓系溫柔", "歐美型格", "復古", "正式/上班", "街頭潮流"]
    )
    
    st.divider()
    
    # --- 批量上載區 ---
    st.header("2. ➕ 批量加衫")
    
    col1, col2 = st.columns(2)
    with col1:
        # 這裡提供完整的分類選項
        cat_options = ["上衣", "下身褲裝", "下身裙裝", "連身裙", "外套", "鞋履", "配件"]
        batch_cat = st.selectbox("這批是?", cat_options)
    with col2:
        batch_season = st.selectbox("季節?", ["四季", "春夏", "秋冬"])
    
    # 使用動態 Key (key=...)，每次存入後數字加 1，Streamlit 就會當佢係新元件，從而清空舊圖
    uploaded_files = st.file_uploader(
        "選擇圖片", 
        type=["jpg", "png", "jpeg"], 
        accept_multiple_files=True,
        key=f"uploader_{st.session_state.uploader_key}" 
    )
    
    if uploaded_files:
        if st.button("📥 存入衣櫃"):
            for uploaded_file in uploaded_files:
                image = Image.open(uploaded_file)
                # 為每件衫生成一個 ID，確保刪除時唔會刪錯
                item_id = str(uuid.uuid4())
                item_data = {
                    'id': item_id,
                    'image': image, 
                    'category': batch_cat, 
                    'season': batch_season,
                    'size_data': {'length': '', 'width': '', 'waist': ''}
                }
                st.session_state.wardrobe.append(item_data)
            
            # 成功後，將 Key 加 1，令上載框重置
            st.session_state.uploader_key += 1
            st.success(f"已加入 {len(uploaded_files)} 件！")
            st.rerun()

    st.divider()
    # 清空所有 (保留作為大清洗用)
    if st.button("⚠️ 清空所有"):
        st.session_state.wardrobe = []
        st.rerun()

# --- 主畫面 ---
tab1, tab2 = st.tabs(["📝 管理衣櫃", "✨ AI 形象顧問"])

with tab1:
    if not st.session_state.wardrobe:
        st.info("👈 衣櫃空空如也，請先在左側上載")
    else:
        # 加入篩選功能，方便管理
        all_cats = list(set([item['category'] for item in st.session_state.wardrobe]))
        selected_cats = st.multiselect("🔍 分類篩選", all_cats, default=all_cats)
        
        # 過濾顯示清單
        display_items = [item for item in st.session_state.wardrobe if item['category'] in selected_cats]
        st.caption(f"顯示 {len(display_items)} 件單品")

        cols = st.columns(5)
        for i, item in enumerate(display_items):
            with cols[i % 5]:
                st.image(item['image'], use_column_width=True)
                
                # 這裡使用 Expander 作為編輯菜單，標題只用 Icon
                with st.expander(f"{item['category']} ⚙️"):
                    
                    # 1. 修改分類 (防止上載時揀錯)
                    new_cat = st.selectbox(
                        "分類", 
                        cat_options, 
                        index=cat_options.index(item['category']) if item['category'] in cat_options else 0,
                        key=f"cat_{item['id']}" # 使用 ID 作為 key，防止數據錯亂
                    )
                    # 即時更新分類
                    if new_cat != item['category']:
                        item['category'] = new_cat
                        st.rerun()

                    # 2. 輸入尺碼
                    st.caption("詳細尺碼")
                    item['size_data']['length'] = st.text_input("長", value=item['size_data']['length'], key=f"l_{item['id']}", placeholder="cm")
                    item['size_data']['width'] = st.text_input("闊/胸", value=item['size_data']['width'], key=f"w_{item['id']}", placeholder="cm")
                    item['size_data']['waist'] = st.text_input("腰", value=item['size_data']['waist'], key=f"wa_{item['id']}", placeholder="吋")

                    # 3. 刪除按鈕 (只用 Icon)
                    if st.button("🗑️ 刪除", key=f"del_{item['id']}"):
                        # 從原始清單中移除
                        st.session_state.wardrobe.remove(item)
                        st.rerun()

with tab2:
    st.header("✨ AI 形象顧問")
    col_w1, col_w2, col_w3 = st.columns(3)
    with col_w1: weather = st.text_input("天氣", "晴天")
    with col_w2: temp = st.text_input("氣溫 (°C)", "25")
    with col_w3: occasion = st.text_input("場合", "出街")

    if st.button("🪄 分析並建議"):
        if len(st.session_state.wardrobe) < 2:
            st.warning("請至少有上身和下身！")
        else:
            with st.spinner("AI 正在分析數據..."):
                try:
                    p = st.session_state.user_profile
                    user_stats = f"身高{p['height']}cm, 胸{p['measurements']['bust']}, 腰{p['measurements']['waist']}, 臀{p['measurements']['hips']}"
                    
                    prompt = (
                        f"你是一位精通剪裁與比例的形象顧問。\n"
                        f"【用戶數據】{user_stats}。\n"
                        f"【風格】{p['style_pref']}。\n"
                        f"【環境】天氣: {weather}, 氣溫: {temp}°C, 場合: {occasion}。\n\n"
                        f"【任務】\n"
                        f"1. **尺碼檢核**: 檢查衣服「腰圍/長度」是否合適。若太小請警告「穿不下」。\n"
                        f"2. **體型修飾**: 分析體型並挑選顯瘦搭配。\n"
                        f"3. **搭配建議**: 從附圖中選一套 (列出編號)。\n"
                        f"4. 語氣: 專業、客觀，用廣東話回答。\n"
                    )
                    
                    inputs = [prompt]
                    for i, item in enumerate(st.session_state.wardrobe):
                        size_info = f"衣長:{item['size_data']['length']}, 闊度:{item['size_data']['width']}, 腰圍:{item['size_data']['waist']}"
                        inputs.append(f"圖分類[{item['category']}] - 尺碼:{size_info}")
                        inputs.append(item['image'])
                    
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    response = model.generate_content(inputs)
                    st.markdown(response.text)
                except Exception as e:
                    st.error(f"出錯了: {e}")
