import streamlit as st
import google.generativeai as genai
from PIL import Image

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

st.set_page_config(page_title="AI 智能衣櫃 (尺碼版)", page_icon="👗", layout="wide")
st.title("莫弈")

# --- 側邊欄：用戶資料 & 批量上載 ---
with st.sidebar:
    st.header("1. 👤 設定身型數據")
    st.caption("輸入你的實際數據，讓 AI 幫你對比衣服尺碼")
    
    h = st.number_input("你的身高 (cm)", value=st.session_state.user_profile['height'])
    st.session_state.user_profile['height'] = h
    
    with st.expander("輸入你的三圍 (重要)", expanded=True):
        b = st.number_input("胸圍 (cm/inch)", value=st.session_state.user_profile['measurements']['bust'])
        w = st.number_input("腰圍 (cm/inch)", value=st.session_state.user_profile['measurements']['waist'])
        hip = st.number_input("臀圍 (cm/inch)", value=st.session_state.user_profile['measurements']['hips'])
        st.session_state.user_profile['measurements'] = {"bust": b, "waist": w, "hips": hip}

    st.session_state.user_profile['style_pref'] = st.selectbox(
        "喜歡的穿搭風格", 
        ["簡約休閒", "日系層次", "韓系溫柔", "歐美型格", "復古", "正式/上班", "街頭潮流"]
    )
    
    st.divider()
    
    st.header("2. ➕ 批量加衫")
    st.info("先上載圖片，然後在右邊主畫面輸入詳細尺碼。")
    
    # 這裡只設定大分類，詳細數字留待主畫面輸入
    col1, col2 = st.columns(2)
    with col1:
        batch_cat = st.selectbox("這批是?", ["上衣", "下身褲裝", "下身裙裝", "連身裙", "外套", "鞋履", "配件"])
    with col2:
        batch_season = st.selectbox("季節?", ["四季", "春夏", "秋冬"])
    
    uploaded_files = st.file_uploader("選擇多張圖片", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
    
    if uploaded_files:
        if st.button("📥 存入衣櫃"):
            for uploaded_file in uploaded_files:
                image = Image.open(uploaded_file)
                item_data = {
                    'image': image, 
                    'category': batch_cat, 
                    'season': batch_season,
                    # 預設空的尺碼資料
                    'size_data': {'length': '', 'width': '', 'waist': ''}
                }
                st.session_state.wardrobe.append(item_data)
            st.success(f"已加入 {len(uploaded_files)} 件！請在右側輸入尺碼。")
            st.rerun()

    st.divider()
    if st.button("🗑️ 清空衣櫃"):
        st.session_state.wardrobe = []
        st.rerun()

# --- 主畫面 ---
tab1, tab2 = st.tabs(["📝 管理衣櫃 (輸入尺碼)", "✨ AI 形象顧問"])

with tab1:
    if not st.session_state.wardrobe:
        st.info("👈 請先在左側上載衣服")
    else:
        st.write(f"共有 {len(st.session_state.wardrobe)} 件單品。請點擊 **「✏️ 尺碼」** 輸入數據。")
        
        # 使用 5 格排列
        cols = st.columns(5)
        for i, item in enumerate(st.session_state.wardrobe):
            with cols[i % 5]:
                st.image(item['image'], use_column_width=True)
                st.caption(f"#{i+1} {item['category']}")
                
                # --- 這裡是新增的：每件衣服的獨立編輯區 ---
                with st.expander("✏️ 編輯尺碼"):
                    # 使用 key 來區分每一個輸入框
                    l = st.text_input("衣/褲長", value=item['size_data']['length'], key=f"len_{i}", placeholder="例如: 70cm")
                    w = st.text_input("闊度/胸圍", value=item['size_data']['width'], key=f"wid_{i}", placeholder="例如: 50cm")
                    wa = st.text_input("腰圍", value=item['size_data']['waist'], key=f"wai_{i}", placeholder="例如: 30吋")
                    
                    # 即時更新資料
                    st.session_state.wardrobe[i]['size_data']['length'] = l
                    st.session_state.wardrobe[i]['size_data']['width'] = w
                    st.session_state.wardrobe[i]['size_data']['waist'] = wa

with tab2:
    st.header("✨ AI 形象顧問 (數據分析版)")
    col_w1, col_w2, col_w3 = st.columns(3)
    with col_w1: weather = st.text_input("天氣", "晴天")
    with col_w2: temp = st.text_input("氣溫 (°C)", "25")
    with col_w3: occasion = st.text_input("場合", "出街")

    if st.button("🪄 分析並建議"):
        if len(st.session_state.wardrobe) < 2:
            st.warning("請至少有上身和下身！")
        else:
            with st.spinner("AI 正在比對你的三圍與衣服尺碼..."):
                try:
                    p = st.session_state.user_profile
                    # 組合用戶數據
                    user_stats = f"身高{p['height']}cm, 胸{p['measurements']['bust']}, 腰{p['measurements']['waist']}, 臀{p['measurements']['hips']}"
                    
                    prompt = (
                        f"你是一位精通剪裁與比例的形象顧問。請根據以下數據進行嚴格的尺碼比對與穿搭建議。\n"
                        f"【用戶身體數據】{user_stats}。\n"
                        f"【風格】{p['style_pref']}。\n"
                        f"【環境】天氣: {weather}, 氣溫: {temp}°C, 場合: {occasion}。\n\n"
                        f"【任務重點】\n"
                        f"1. **尺碼檢核 (最重要)**: 必須檢查衣服的「腰圍/長度」是否適合用戶的身高與三圍。如果衣服腰圍比用戶腰圍小，請明確警告「穿不下」。如果衣長太長，請建議「攝衫」或「改短」。\n"
                        f"2. **體型修飾**: 根據三圍判斷體型 (如梨形)，並挑選最顯瘦的搭配。\n"
                        f"3. **搭配建議**: 從附圖中選一套 (列出編號)。\n"
                        f"4. 語氣: 專業、客觀，用廣東話回答。\n"
                    )
                    
                    inputs = [prompt]
                    for i, item in enumerate(st.session_state.wardrobe):
                        # 將輸入的尺碼數據傳送給 AI
                        size_info = f"衣長:{item['size_data']['length']}, 闊度:{item['size_data']['width']}, 腰圍:{item['size_data']['waist']}"
                        inputs.append(f"圖#{i+1} [{item['category']}] - 尺碼數據: {size_info}")
                        inputs.append(item['image'])
                    
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    response = model.generate_content(inputs)
                    st.markdown(response.text)
                except Exception as e:
                    st.error(f"出錯了: {e}")
