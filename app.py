import streamlit as st
import google.generativeai as genai
from PIL import Image

# --- 從 Secrets 獲取密碼 (這是最安全的做法) ---
# 如果你在本機跑，請確保你的 .streamlit/secrets.toml 有設定
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("找不到 API Key，請在 Streamlit Cloud 的 Secrets 設定中加入 GOOGLE_API_KEY")
    st.stop()

# --- 初始化 Session State ---
if 'wardrobe' not in st.session_state:
    st.session_state.wardrobe = [] 
if 'user_profile' not in st.session_state:
    st.session_state.user_profile = {
        "height": 160, 
        "body_type": "標準",
        "measurements": {"bust": 0, "waist": 0, "hips": 0},
        "style_pref": "休閒舒適"
    }

st.set_page_config(page_title="AI 私人造型師 Ultimate", page_icon="💃", layout="wide")
st.title("造型師 莫弈")

# --- 側邊欄 ---
with st.sidebar:
    st.header("1. 👤 你的詳細檔案")
    h = st.number_input("身高 (cm)", value=st.session_state.user_profile['height'])
    st.session_state.user_profile['height'] = h
    st.session_state.user_profile['body_type'] = st.selectbox(
        "體型描述", ["偏瘦 (H型)", "標準", "梨形 (A型)", "蘋果型 (O型)", "沙漏型 (X型)", "健碩/肌肉"], index=1)
    
    with st.expander("輸入三圍數字 (選填)"):
        b = st.number_input("胸圍 (cm/inch)", value=st.session_state.user_profile['measurements']['bust'])
        w = st.number_input("腰圍 (cm/inch)", value=st.session_state.user_profile['measurements']['waist'])
        hip = st.number_input("臀圍 (cm/inch)", value=st.session_state.user_profile['measurements']['hips'])
        st.session_state.user_profile['measurements'] = {"bust": b, "waist": w, "hips": hip}

    st.session_state.user_profile['style_pref'] = st.selectbox(
        "喜歡的穿搭風格", 
        ["簡約休閒", "日系層次", "韓系溫柔", "歐美型格", "復古", "正式/上班", "街頭潮流"]
    )
    
    st.divider()
    st.header("2. ➕ 放入衣櫃")
    uploaded_file = st.file_uploader("上傳照片", type=["jpg", "png", "jpeg"])
    
    if uploaded_file:
        st.image(uploaded_file, caption="預覽", use_column_width=True)
        col1, col2 = st.columns(2)
        with col1:
            cat = st.selectbox("分類", ["上衣", "下身褲裝", "下身裙裝", "連身裙/套裝", "外套", "鞋履", "手袋", "配件"])
        with col2:
            season = st.selectbox("適用季節", ["春夏", "秋冬", "四季通用"])
        info = st.text_input("尺寸備註", "標準碼")
        
        if st.button("📥 存入衣櫃"):
            image = Image.open(uploaded_file)
            item_data = {'image': image, 'category': cat, 'season': season, 'info': info}
            st.session_state.wardrobe.append(item_data)
            st.success("成功加入！")

    st.divider()
    if st.button("🗑️ 清空衣櫃"):
        st.session_state.wardrobe = []
        st.rerun()

# --- 主畫面 ---
tab1, tab2 = st.tabs(["👀 瀏覽衣櫃", "✨ 智能穿搭"])

with tab1:
    filter_cat = st.multiselect("篩選分類", ["上衣", "下身褲裝", "下身裙裝", "外套"], default=[])
    display_items = st.session_state.wardrobe
    if filter_cat:
        display_items = [item for item in display_items if item['category'] in filter_cat]

    if display_items:
        cols = st.columns(4)
        for i, item in enumerate(display_items):
            with cols[i % 4]:
                st.image(item['image'], use_column_width=True)
                st.caption(f"[{item['season']}] {item['category']}")
                st.caption(f"📏 {item['info']}")
    else:
        st.info("暫無衣物")

with tab2:
    st.header("🌤️ 今日穿搭顧問")
    col_w1, col_w2, col_w3 = st.columns(3)
    with col_w1: weather = st.text_input("天氣", "晴天")
    with col_w2: temp = st.text_input("氣溫 (°C)", "25")
    with col_w3: occasion = st.text_input("場合", "出街")

    if st.button("開始分析"):
        if len(st.session_state.wardrobe) < 2:
            st.warning("請至少上傳 2 件衣服！")
        else:
            with st.spinner("AI 正在思考..."):
                try:
                    p = st.session_state.user_profile
                    measure_str = f"胸{p['measurements']['bust']}-腰{p['measurements']['waist']}-臀{p['measurements']['hips']}"
                    prompt = (
                        f"你是一位頂級時尚顧問。請根據以下詳細資料建議一套穿搭。\n"
                        f"【用戶檔案】身高: {p['height']}cm, 體型: {p['body_type']}, 三圍: {measure_str}。\n"
                        f"【風格偏好】{p['style_pref']}。\n"
                        f"【今日環境】天氣: {weather}, 氣溫: {temp}°C, 場合: {occasion}。\n"
                        f"【任務要求】\n"
                        f"1. 請從附圖中挑選最適合的一套 (包含鞋包)。\n"
                        f"2. 必須考慮「氣溫」是否合適。\n"
                        f"3. 必須分析「三圍/身形」優缺點。\n"
                        f"4. 請用親切的廣東話回答。\n"
                    )
                    inputs = [prompt]
                    for i, item in enumerate(st.session_state.wardrobe):
                        inputs.append(f"#{i+1}: {item['category']} ({item['season']}) - {item['info']}")
                        inputs.append(item['image'])
                    
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    response = model.generate_content(inputs)
                    st.markdown(response.text)
                except Exception as e:
                    st.error(f"出錯了: {e}")
