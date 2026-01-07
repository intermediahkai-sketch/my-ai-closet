import streamlit as st
import google.generativeai as genai
from PIL import Image
import uuid
import io
import time
import random
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
    st.session_state.user_profile = {
        "name": "User", 
        "location": "香港",
        "gender": "女",
        "height": 160, 
        "measurements": {"bust": 0, "waist": 0, "hips": 0},
        "style_pref": "簡約休閒"
    }

if 'stylist_profile' not in st.session_state:
    st.session_state.stylist_profile = {
        "name": "莫弈",
        "avatar_type": "emoji", 
        "avatar_emoji": "🤵",
        "avatar_image": None,
        "persona": "一位品味高雅、語氣溫柔沉穩的專業形象設計師。語氣要優雅、知性、帶有淡淡的關懷。",
        "current_weather_info": "天氣晴朗" # 暫存天氣資訊
    }

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

# --- CSS 美化 ---
st.set_page_config(page_title="My Stylist", page_icon="✨", layout="wide")

st.markdown("""
    <style>
    /* 1. 圖片卡片 */
    div[data-testid="stImage"] {
        width: 100%;
        height: 300px;
        overflow: hidden;
        display: flex;
        justify_content: center;
        align-items: center;
        background-color: #f9f9f9;
        border-radius: 10px;
    }
    div[data-testid="stImage"] img {
        width: 100% !important;
        height: 100% !important;
        object-fit: cover !important;
        max-width: none !important;
    }
    
    /* 2. 去除按鈕灰框 */
    button[kind="secondary"] {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
    }
    button[kind="secondary"]:hover {
        color: #06b6d4 !important;
    }

    /* 3. File Uploader */
    section[data-testid="stFileUploader"] label { display: none; }
    div[data-testid="stFileUploader"] { padding-top: 0px; }
    
    /* 4. 造型師卡片 (Avatar Button Hack) */
    .stylist-container {
        text-align: center;
        padding: 10px;
        background: #f0f2f6;
        border-radius: 15px;
        margin-bottom: 20px;
    }
    /* 讓頭像按鈕變圓形且大 */
    div.avatar-btn button {
        border-radius: 50% !important;
        height: 80px !important;
        width: 80px !important;
        font-size: 40px !important;
        background-color: #ffffff !important;
        border: 2px solid #06b6d4 !important;
        margin: 0 auto !important;
        display: block !important;
        overflow: hidden !important;
        padding: 0 !important;
    }
    div.avatar-btn img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    
    /* 設定按鈕微調 */
    div.settings-btn button {
        padding: 0 !important;
        color: #888 !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- AI 功能函數 ---

# 1. AI 自動分類
def ai_classify_image(image):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = "Analyze this fashion item. Classify it into exactly one of these categories: [上衣, 下身褲裝, 下身裙裝, 連身裙, 外套, 鞋履, 配件]. Return ONLY the category name."
        response = model.generate_content([prompt, image])
        category = response.text.strip()
        # 簡單驗證回傳值，如果 AI 亂回傳，預設為上衣
        valid_cats = ["上衣", "下身褲裝", "下身裙裝", "連身裙", "外套", "鞋履", "配件"]
        if category not in valid_cats:
            return "上衣"
        return category
    except:
        return "上衣" # 失敗回退

# 2. 處理上傳 (自動去背 + 自動分類)
def process_upload(files, season):
    if not files: return
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, uploaded_file in enumerate(files):
        status_text.caption(f"處理中: {uploaded_file.name} (AI 去背及分類中...)")
        try:
            image = Image.open(uploaded_file)
            
            # A. 自動去背
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            output_bytes = remove_bg(img_byte_arr.getvalue())
            final_image = Image.open(io.BytesIO(output_bytes))
            
            # B. AI 自動分類 (使用去背後的圖或原圖皆可，這裡用原圖可能特徵更多)
            detected_category = ai_classify_image(image)
            
            # C. 存入
            st.session_state.wardrobe.append({
                'id': str(uuid.uuid4()),
                'image': final_image,
                'category': detected_category, 
                'season': season,
                'size_data': {'length': '', 'width': '', 'waist': ''}
            })
        except Exception as e:
            st.error(f"Error: {e}")
        
        progress_bar.progress((i + 1) / len(files))
    
    status_text.empty()
    progress_bar.empty()
    st.session_state.uploader_key += 1
    st.toast(f"成功加入 {len(files)} 件單品！", icon="✅")
    time.sleep(0.5)
    st.rerun()

# 3. 生成模擬天氣 (根據地點)
def get_simulated_weather(location):
    # 簡單的模擬邏輯
    loc_map = {
        "香港": ["潮濕有霧 22°C", "陽光普照 28°C", "微涼有雨 19°C"],
        "東京": ["乾燥寒冷 8°C", "櫻花盛開 15°C", "有雨 12°C"],
        "首爾": ["零下嚴寒 -2°C", "清涼舒適 18°C", "乾燥 10°C"],
        "台北": ["悶熱 30°C", "陰天有雨 24°C"],
        "曼谷": ["炎熱 35°C", "雷雨 32°C"],
        "倫敦": ["多雲有霧 11°C", "細雨紛飛 9°C"],
    }
    # 如果找不到，就用通用
    options = loc_map.get(location, ["晴朗 25°C", "多雲 20°C"])
    return random.choice(options)

# --- 彈出視窗 (Dialogs) ---

@st.dialog("✏️ 編輯單品")
def edit_item_dialog(item):
    c1, c2 = st.columns([1, 1])
    with c1: st.image(item['image'], use_column_width=True)
    with c2:
        cat_opts = ["上衣", "下身褲裝", "下身裙裝", "連身裙/套裝", "外套", "鞋履", "配件"]
        # 如果 AI 分錯了，這裡可以手動改
        item['category'] = st.selectbox("分類", cat_opts, index=cat_opts.index(item['category']) if item['category'] in cat_opts else 0)
        
        st.caption("詳細尺碼")
        if any(x in item['category'] for x in ["上衣", "外套", "連身裙"]):
            item['size_data']['length'] = st.text_input("衣長 (cm)", value=item['size_data']['length'])
            item['size_data']['width'] = st.text_input("胸寬 (cm)", value=item['size_data']['width'])
        elif any(x in item['category'] for x in ["下身", "褲", "裙"]):
            item['size_data']['length'] = st.text_input("褲/裙長 (cm)", value=item['size_data']['length'])
            item['size_data']['waist'] = st.text_input("腰圍 (吋/cm)", value=item['size_data']['waist'])
        else:
            item['size_data']['width'] = st.text_input("備註", value=item['size_data']['width'])
            
        st.divider()
        if st.button("🗑️ 刪除", type="primary", use_container_width=True):
            st.session_state.wardrobe.remove(item)
            st.rerun()

@st.dialog("⚙️ 設定檔案 & 造型師")
def settings_dialog():
    tab1, tab2 = st.tabs(["👤 個人", "✨ 造型師"])
    with tab1:
        st.session_state.user_profile['name'] = st.text_input("暱稱", value=st.session_state.user_profile['name'])
        
        # 地點選擇
        locs = ["香港", "東京", "大阪", "首爾", "台北", "曼谷", "倫敦", "紐約", "其他"]
        curr_loc = st.session_state.user_profile['location']
        if curr_loc not in locs: locs.append(curr_loc)
        st.session_state.user_profile['location'] = st.selectbox("居住/旅遊地區", locs, index=locs.index(curr_loc) if curr_loc in locs else 0)
        
        # 三圍
        c1, c2, c3 = st.columns(3)
        with c1: st.session_state.user_profile['measurements']['bust'] = st.number_input("胸圍", value=st.session_state.user_profile['measurements']['bust'])
        with c2: st.session_state.user_profile['measurements']['waist'] = st.number_input("腰圍", value=st.session_state.user_profile['measurements']['waist'])
        with c3: st.session_state.user_profile['measurements']['hips'] = st.number_input("臀圍 (Hips)", value=st.session_state.user_profile['measurements']['hips'])
        
        st.session_state.user_profile['height'] = st.number_input("身高", value=st.session_state.user_profile['height'])

    with tab2:
        c_name, c_emoji = st.columns([3, 1])
        with c_name: st.session_state.stylist_profile['name'] = st.text_input("造型師名字", value=st.session_state.stylist_profile['name'])
        with c_emoji: 
            avatar_mode = st.toggle("用圖片頭像?", value=(st.session_state.stylist_profile['avatar_type'] == 'image'))

        if not avatar_mode:
            st.session_state.stylist_profile['avatar_type'] = 'emoji'
            st.session_state.stylist_profile['avatar_emoji'] = st.text_input("Emoji", value=st.session_state.stylist_profile['avatar_emoji'])
        else:
            st.session_state.stylist_profile['avatar_type'] = 'image'
            uploaded_avatar = st.file_uploader("上傳頭像", type=["jpg", "png"])
            if uploaded_avatar:
                img = Image.open(uploaded_avatar)
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')
                st.session_state.stylist_profile['avatar_image'] = img_byte_arr.getvalue()

        st.divider()
        st.caption("🎭 **快速選擇人設** (選完即套用)")
        
        personas = {
            "專業莫弈": "你現在是「莫弈」，一位品味高雅、語氣溫柔沉穩的專業形象設計師。語氣要優雅、知性、帶有淡淡的關懷。請用紳士的角度給予建議，像一位相識多年的知己。",
            "霸道總裁": "你現在是霸道總裁男友。語氣要自信、強勢但充滿寵溺。叫用戶『笨蛋』或『寶貝』。如果衣服太露，要表現出吃醋，說『這只能在家穿給我看』。",
            "溫柔奶狗": "你現在是年下的溫柔男友。語氣要超級甜，充滿愛意，叫用戶『姐姐』或『BB』。不管穿什麼都瘋狂稱讚，最在意你有沒有穿暖。",
            "毒舌主編": "你現在是頂級時尚雜誌的主編。眼光極高，說話尖酸刻薄但一針見血。看到搭配不好會直接說『這簡直是災難』，但給出的建議絕對專業。",
            "貼身管家": "你現在是皇家級貼身管家。語氣要極度恭敬、正式，稱呼用戶為『大小姐』。為您服務是我的榮幸。"
        }
        
        # Logic to update text area when selectbox changes
        selected_key = st.selectbox("人設清單", list(personas.keys()), key="persona_selector")
        
        # 這裡的邏輯：如果這個 key 變了，就更新下面的 text area
        if "last_selected_persona" not in st.session_state:
            st.session_state.last_selected_persona = selected_key
        
        if st.session_state.last_selected_persona != selected_key:
            st.session_state.stylist_profile['persona'] = personas[selected_key]
            st.session_state.last_selected_persona = selected_key
            st.rerun() # Refresh to update text area value

        # 顯示並允許手動修改
        st.session_state.stylist_profile['persona'] = st.text_area(
            "人設指令 (可手動修改)", 
            value=st.session_state.stylist_profile['persona'], 
            height=120
        )

# --- 聊天對話視窗 ---
@st.dialog("💬 與造型師對話", width="large")
def chat_dialog():
    s = st.session_state.stylist_profile
    p = st.session_state.user_profile
    
    # Header
    col_av, col_nm = st.columns([1, 5])
    with col_av:
        if s['avatar_type'] == 'image' and s['avatar_image']:
            st.image(s['avatar_image'], width=60)
        else:
            st.markdown(f"<h1 style='text-align: center; margin: 0;'>{s['avatar_emoji']}</h1>", unsafe_allow_html=True)
    with col_nm:
        st.subheader(s['name'])
        # 顯示即時生成的天氣
        st.caption(f"📍 {p['location']} | {s['current_weather_info']}")

    st.divider()

    # 自動開場 (如果無歷史)
    if not st.session_state.chat_history:
        # 生成天氣
        weather_info = get_simulated_weather(p['location'])
        s['current_weather_info'] = weather_info # 更新顯示
        
        # AI 開場白
        with st.spinner(f"{s['name']} 正在查看 {p['location']} 天氣..."):
            opening_prompt = (
                f"你現在是「{s['name']}」，{s['persona']}\n"
                f"用戶 {p['name']} 在 {p['location']}。\n"
                f"現在天氣是：{weather_info}。\n"
                f"任務：\n"
                f"1. 扮演你的角色向用戶打招呼。\n"
                f"2. 告訴用戶當地的天氣狀況。\n"
                f"3. 詢問用戶今天要去哪裡或想穿什麼風格。\n"
            )
            try:
                model = genai.GenerativeModel('gemini-1.5-flash')
                response = model.generate_content(opening_prompt)
                st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                st.rerun()
            except:
                pass

    # 顯示歷史
    for msg in st.session_state.chat_history:
        avatar = None
        if msg["role"] == "assistant":
            if s['avatar_type'] == 'image' and s['avatar_image']:
                avatar = Image.open(io.BytesIO(s['avatar_image']))
            else:
                avatar = s['avatar_emoji']
        
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # 輸入框
    if prompt := st.chat_input(f"回應 {s['name']}..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        st.rerun()

    # 處理 AI 回應 (在 rerun 後執行)
    if st.session_state.chat_history and st.session_state.chat_history[-1]["role"] == "user":
        with st.chat_message("assistant"):
            with st.spinner("思考搭配中..."):
                try:
                    # 準備 Context
                    user_info = f"用戶:{p['name']}, 身高:{p['height']}cm, 三圍(胸/腰/臀):{p['measurements']['bust']}/{p['measurements']['waist']}/{p['measurements']['hips']}"
                    
                    sys_prompt = (
                        f"你現在是「{s['name']}」。{s['persona']}\n"
                        f"【用戶資料】{user_info}。\n"
                        f"【環境】地點:{p['location']}, 天氣:{s['current_weather_info']}。\n"
                        f"【對話歷史】(見上方)\n"
                        f"【最新訊息】{st.session_state.chat_history[-1]['content']}\n"
                        f"【任務】\n"
                        f"1. 回應用戶，並從衣櫃中挑選合適的單品建議。\n"
                        f"2. 必須列出建議單品的「編號」和「類別」。\n"
                        f"3. 解釋搭配理由 (天氣/修飾身形)。\n"
                    )
                    
                    inputs = [sys_prompt]
                    if st.session_state.wardrobe:
                        items_slice = st.session_state.wardrobe[:20]
                        for i, item in enumerate(items_slice):
                            info = item['size_data']
                            desc = f"圖#{i+1}[{item['category']}] 尺碼:長{info['length']}/闊{info['width']}/腰{info['waist']}"
                            inputs.append(desc)
                            inputs.append(item['image'])
                    else:
                        inputs.append("(衣櫃目前是空的，請提醒用戶去上傳衣服)")

                    model = genai.GenerativeModel('gemini-1.5-flash')
                    response = model.generate_content(inputs)
                    
                    st.markdown(response.text)
                    st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"Error: {e}")


# --- 側邊欄 ---
with st.sidebar:
    s = st.session_state.stylist_profile
    p = st.session_state.user_profile
    
    # 1. 造型師卡片 (放在最頂)
    with st.container():
        st.markdown('<div class="stylist-container">', unsafe_allow_html=True)
        
        c_avatar, c_info = st.columns([1, 1.5])
        
        with c_avatar:
            # 這是 "Avatar Button" 的 Hack，點擊觸發 chat_dialog
            # 使用 CSS class 'avatar-btn' 來控制樣式
            st.markdown('<div class="avatar-btn">', unsafe_allow_html=True)
            if s['avatar_type'] == 'image' and s['avatar_image']:
                # 為了讓圖像是按鈕，我們需要一個透明按鈕蓋在上面，或者使用 st.button 顯示圖片
                # 這裡使用 st.button 但內容是空的，背景圖由 CSS 控制比較難，
                # 最簡單是直接顯示圖片，然後下面放一個 invisible button，但 Streamlit 限制多。
                # 妥協方案：直接用 st.button 顯示 Emoji 或 "Chat"，如果是圖片就顯示圖片
                # 這裡我們用一個簡單的 Button，標籤是 Emoji (如果是圖片模式，就顯示預設 icon)
                 if st.button("💬", key="open_chat_img"): 
                     chat_dialog()
            else:
                 if st.button(s['avatar_emoji'], key="open_chat_emo"):
                     chat_dialog()
            st.markdown('</div>', unsafe_allow_html=True)

        with c_info:
            st.markdown(f"<h3 style='margin:0; padding-top:10px;'>{s['name']}</h3>", unsafe_allow_html=True)
            # 設定按鈕
            st.markdown('<div class="settings-btn">', unsafe_allow_html=True)
            if st.button("⚙️ 設定", key="btn_settings"):
                settings_dialog()
            st.markdown('</div>', unsafe_allow_html=True)
        
        # 下方問候語
        greeting_text = f"早安 {p['name']}，{p['location']} 天氣不錯。" # 這裡可以是動態的
        st.caption(greeting_text)
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.divider()
    
    # 2. 加入衣櫃 (移除了分類 Dropdown)
    st.subheader("📥 加入衣櫃")
    st.info("💡 直接拖入圖片，AI 會自動分類！")
    
    season = st.selectbox("季節", ["四季", "春夏", "秋冬"], label_visibility="collapsed")
    
    files = st.file_uploader("Drop files", type=["jpg","png","webp"], accept_multiple_files=True, key=f"up_{st.session_state.uploader_key}")
    if files: process_upload(files, season)

    st.divider()
    if st.button("🗑️ 清空衣櫃", use_container_width=True):
        st.session_state.wardrobe = []
        st.rerun()

# --- 主畫面 (只顯示衣櫃) ---

st.subheader("🧥 我的衣櫃")

if not st.session_state.wardrobe:
    st.info("👈 點擊左上角頭像找造型師傾偈，或者拖曳圖片入衣櫃！")
else:
    # 篩選
    all_cats = list(set([item['category'] for item in st.session_state.wardrobe]))
    selected_cats = st.multiselect("🔍", all_cats, placeholder="篩選分類 (顯示全部)")
    display_items = [item for item in st.session_state.wardrobe if item['category'] in selected_cats] if selected_cats else st.session_state.wardrobe
    
    cols = st.columns(5)
    for i, item in enumerate(display_items):
        with cols[i % 5]:
            st.image(item['image'])
            if st.button("✏️", key=f"edit_{item['id']}", use_container_width=True):
                edit_item_dialog(item)
