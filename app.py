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
        "persona": "一位品味高雅、語氣溫柔沉穩的專業形象設計師。",
        "current_weather_info": "天氣晴朗" 
    }

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

# --- CSS 美化 (修復 Layout 災難) ---
st.set_page_config(page_title="My Stylist", page_icon="✨", layout="wide")

st.markdown("""
    <style>
    /* 1. 圖片卡片 (衣櫃) */
    div[data-testid="stImage"] {
        width: 100%;
        height: 250px;
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
    }
    
    /* 2. 隱藏 File Uploader 文字 */
    section[data-testid="stFileUploader"] label { display: none; }
    div[data-testid="stFileUploader"] { padding-top: 0px; }
    
    /* 3. 側邊欄造型師容器 */
    .stylist-container {
        position: relative;
        text-align: center;
        padding: 20px 10px;
        background: #f0f2f6;
        border-radius: 15px;
        margin-bottom: 20px;
        border: 1px solid #e0e0e0;
    }

    /* 4. 頭像統一圓形樣式 (180x180) */
    .avatar-circle {
        width: 180px;
        height: 180px;
        border-radius: 50%;
        overflow: hidden;
        margin: 0 auto 10px auto;
        border: 4px solid #06b6d4;
        background-color: white;
        display: flex;
        justify_content: center;
        align-items: center;
    }
    .avatar-circle img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    .avatar-emoji {
        font-size: 100px;
        line-height: 180px;
    }

    /* 5. 隱形按鈕 Hack (覆蓋在頭像上) */
    .invisible-btn {
        position: absolute;
        top: 20px; /* Adjust based on container padding */
        left: 50%;
        transform: translateX(-50%);
        width: 180px;
        height: 180px;
        z-index: 10;
        opacity: 0; /* 完全透明 */
    }
    /* 必須讓 Streamlit 的 button 填滿這個 div */
    .invisible-btn button {
        width: 100% !important;
        height: 100% !important;
        padding: 0 !important;
        border: none !important;
    }

    /* 6. 名字與設定 */
    .name-row {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 10px;
        margin-top: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# --- AI 功能函數 (修復 Crash & 分類) ---

def get_gemini_response(inputs):
    """
    智能模型切換器：
    嘗試不同的模型名稱，避免 404 錯誤。
    """
    # 優先順序：最新的 Flash -> 標準 Flash -> 舊版 Pro -> 免費版 Pro
    models_to_try = [
        'gemini-1.5-flash', 
        'gemini-1.5-flash-latest', 
        'gemini-1.5-pro',
        'gemini-pro'
    ]
    
    last_error = None
    for model_name in models_to_try:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(inputs)
            return response.text
        except Exception as e:
            # 記錄錯誤但繼續嘗試下一個
            last_error = e
            continue 
    
    return f"⚠️ 連線失敗: 無法連接任何 AI 模型。請檢查 API Key 或稍後再試。({last_error})"

def ai_classify_image(image):
    """
    修復：使用【原圖】進行分類，並優化 Prompt。
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        # 優化 Prompt：要求更明確
        prompt = (
            "Look at this fashion item. Classify it into exactly one category.\n"
            "Options: [上衣, 下身褲裝, 下身裙裝, 連身裙, 外套, 鞋履, 配件].\n"
            "Rule: T-shirts, shirts, sweaters are '上衣'. Jeans, trousers, shorts are '下身褲裝'. Skirts are '下身裙裝'.\n"
            "Return ONLY the category name."
        )
        response = model.generate_content([prompt, image])
        cat = response.text.strip()
        valid = ["上衣", "下身褲裝", "下身裙裝", "連身裙", "外套", "鞋履", "配件"]
        # 如果 AI 回傳了多餘的字，嘗試清洗
        for v in valid:
            if v in cat:
                return v
        return "上衣" # 默認值
    except:
        return "上衣"

def process_upload(files, season):
    if not files: return
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, uploaded_file in enumerate(files):
        status_text.caption(f"處理中: {uploaded_file.name} (AI 分析中...)")
        try:
            # 1. 讀取原圖 (用作 AI 分類)
            original_image = Image.open(uploaded_file)
            
            # 2. AI 分類 (使用原圖，準確度更高)
            detected_cat = ai_classify_image(original_image)
            
            # 3. 去背 (用於展示)
            img_byte_arr = io.BytesIO()
            original_image.save(img_byte_arr, format='PNG')
            output_bytes = remove_bg(img_byte_arr.getvalue())
            final_image = Image.open(io.BytesIO(output_bytes))
            
            # 4. 存入
            st.session_state.wardrobe.append({
                'id': str(uuid.uuid4()),
                'image': final_image,
                'category': detected_cat, 
                'season': season,
                'size_data': {'length': '', 'width': '', 'waist': ''}
            })
        except Exception as e:
            st.error(f"Error processing {uploaded_file.name}: {e}")
            time.sleep(2)
        
        progress_bar.progress((i + 1) / len(files))
    
    status_text.empty()
    progress_bar.empty()
    st.session_state.uploader_key += 1
    st.toast(f"成功加入 {len(files)} 件！", icon="✅")
    time.sleep(0.5)
    st.rerun()

def get_simulated_weather(location):
    loc_map = {
        "香港": ["潮濕有霧 22°C", "陽光普照 28°C", "微涼有雨 19°C"],
        "東京": ["乾燥寒冷 8°C", "櫻花盛開 15°C", "有雨 12°C"],
        "首爾": ["零下嚴寒 -2°C", "清涼舒適 18°C", "乾燥 10°C"],
        "台北": ["悶熱 30°C", "陰天有雨 24°C"],
    }
    return random.choice(loc_map.get(location, ["晴朗 25°C", "多雲 20°C"]))

# --- Dialogs ---

@st.dialog("✏️ 編輯單品")
def edit_item_dialog(item):
    c1, c2 = st.columns([1, 1])
    with c1: st.image(item['image'], use_column_width=True)
    with c2:
        cat_opts = ["上衣", "下身褲裝", "下身裙裝", "連身裙/套裝", "外套", "鞋履", "配件"]
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
        
        locs = ["香港", "東京", "大阪", "首爾", "台北", "曼谷", "倫敦", "紐約", "其他"]
        curr_loc = st.session_state.user_profile['location']
        if curr_loc not in locs: locs.append(curr_loc)
        st.session_state.user_profile['location'] = st.selectbox("居住/旅遊地區", locs, index=locs.index(curr_loc) if curr_loc in locs else 0)
        
        c1, c2, c3 = st.columns(3)
        with c1: st.session_state.user_profile['measurements']['bust'] = st.number_input("胸圍", value=st.session_state.user_profile['measurements']['bust'])
        with c2: st.session_state.user_profile['measurements']['waist'] = st.number_input("腰圍", value=st.session_state.user_profile['measurements']['waist'])
        with c3: st.session_state.user_profile['measurements']['hips'] = st.number_input("臀圍", value=st.session_state.user_profile['measurements']['hips'])
        st.session_state.user_profile['height'] = st.number_input("身高", value=st.session_state.user_profile['height'])

    with tab2:
        st.session_state.stylist_profile['name'] = st.text_input("造型師名字", value=st.session_state.stylist_profile['name'])
        
        avatar_mode = st.radio("頭像類型", ["Emoji", "上傳圖片"], horizontal=True)
        if avatar_mode == "Emoji":
            st.session_state.stylist_profile['avatar_type'] = 'emoji'
            st.session_state.stylist_profile['avatar_emoji'] = st.text_input("輸入 Emoji", value=st.session_state.stylist_profile['avatar_emoji'])
        else:
            st.session_state.stylist_profile['avatar_type'] = 'image'
            uploaded_avatar = st.file_uploader("上傳頭像", type=["jpg", "png"])
            if uploaded_avatar:
                img = Image.open(uploaded_avatar)
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')
                st.session_state.stylist_profile['avatar_image'] = img_byte_arr.getvalue()
                st.success("圖片已上載！")

        st.divider()
        st.caption("🎭 **快速選擇人設**")
        
        personas = {
            "專業莫弈": "你現在是「莫弈」，一位品味高雅、語氣溫柔沉穩的專業形象設計師。語氣要優雅、知性、帶有淡淡的關懷。請用紳士的角度給予建議。",
            "霸道總裁": "你現在是霸道總裁男友。語氣要自信、強勢但充滿寵溺。叫用戶『笨蛋』或『寶貝』。如果衣服太露，要表現出吃醋。",
            "溫柔奶狗": "你現在是年下的溫柔男友。語氣要超級甜，充滿愛意，叫用戶『姐姐』或『BB』。不管穿什麼都瘋狂稱讚。",
            "毒舌主編": "你現在是頂級時尚雜誌的主編。眼光極高，說話尖酸刻薄但一針見血。看到搭配不好會直接說『這簡直是災難』。",
            "貼身管家": "你現在是皇家級貼身管家。語氣要極度恭敬、正式，稱呼用戶為『大小姐』。為您服務是我的榮幸。"
        }
        
        selected_key = st.selectbox("人設清單", list(personas.keys()))
        if st.button("套用此人設 (OK)"):
             st.session_state.stylist_profile['persona'] = personas[selected_key]
             st.success(f"已切換為：{selected_key}")
             time.sleep(0.5)
             st.rerun()

        st.session_state.stylist_profile['persona'] = st.text_area(
            "人設指令", value=st.session_state.stylist_profile['persona'], height=100
        )

    if st.button("完成", use_container_width=True, type="primary"):
        st.rerun()

# --- 聊天 Dialog ---
@st.dialog("💬 與造型師對話", width="large")
def chat_dialog():
    s = st.session_state.stylist_profile
    p = st.session_state.user_profile
    
    col_av, col_nm = st.columns([1, 5])
    with col_av:
        # 小頭像顯示
        if s['avatar_type'] == 'image' and s['avatar_image']:
            st.image(s['avatar_image'], width=60)
        else:
            st.markdown(f"<h1 style='text-align: center; margin: 0;'>{s['avatar_emoji']}</h1>", unsafe_allow_html=True)
    with col_nm:
        st.subheader(s['name'])
        st.caption(f"📍 {p['location']} | {s['current_weather_info']}")

    st.divider()

    if not st.session_state.chat_history:
        weather_info = get_simulated_weather(p['location'])
        s['current_weather_info'] = weather_info
        
        with st.spinner("連線中..."):
            opening_prompt = (
                f"你現在是「{s['name']}」，{s['persona']}\n"
                f"用戶 {p['name']} 在 {p['location']}，天氣：{weather_info}。\n"
                f"任務：向用戶打招呼，報告天氣，並詢問穿搭需求。\n"
            )
            # 使用增強版函數
            ai_reply = get_gemini_response([opening_prompt])
            st.session_state.chat_history.append({"role": "assistant", "content": ai_reply})
            st.rerun()

    for msg in st.session_state.chat_history:
        avatar = None
        if msg["role"] == "assistant":
            if s['avatar_type'] == 'image' and s['avatar_image']:
                avatar = Image.open(io.BytesIO(s['avatar_image']))
            else:
                avatar = s['avatar_emoji']
        
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    if prompt := st.chat_input(f"回應 {s['name']}..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        st.rerun()

    if st.session_state.chat_history and st.session_state.chat_history[-1]["role"] == "user":
        with st.chat_message("assistant"):
            with st.spinner("思考搭配中..."):
                user_info = f"用戶:{p['name']}, 身高:{p['height']}cm, 三圍:{p['measurements']['bust']}/{p['measurements']['waist']}/{p['measurements']['hips']}"
                sys_prompt = (
                    f"你現在是「{s['name']}」。{s['persona']}\n"
                    f"【用戶資料】{user_info}。\n"
                    f"【環境】地點:{p['location']}, 天氣:{s['current_weather_info']}。\n"
                    f"【對話歷史】(見上方)\n"
                    f"【最新訊息】{st.session_state.chat_history[-1]['content']}\n"
                    f"【任務】\n"
                    f"1. 回應用戶，從衣櫃挑選單品。\n"
                    f"2. 必須列出建議單品的「編號」和「類別」。\n"
                    f"3. 保持人設語氣。\n"
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
                    inputs.append("(衣櫃空，提醒用戶上傳)")

                ai_reply = get_gemini_response(inputs)
                st.markdown(ai_reply)
                st.session_state.chat_history.append({"role": "assistant", "content": ai_reply})

# --- 側邊欄 ---
with st.sidebar:
    s = st.session_state.stylist_profile
    p = st.session_state.user_profile
    
    # 1. 造型師卡片 (修復版)
    with st.container():
        st.markdown('<div class="stylist-container">', unsafe_allow_html=True)
        
        # A. 視覺層 (HTML/CSS)
        st.markdown('<div class="avatar-circle">', unsafe_allow_html=True)
        if s['avatar_type'] == 'image' and s['avatar_image']:
            # 這裡有點 hacky, 為了在 markdown 顯示 bytes image, 我們用 st.image 但要蓋住
            # 簡化方案：只顯示空殼，用 CSS background? 不行，image data 是動態的
            # 妥協方案：這裡用 st.image 顯示，但被 invisible-btn 覆蓋
            pass 
        else:
            st.markdown(f'<div class="avatar-emoji">{s["avatar_emoji"]}</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # B. 邏輯層 (隱形按鈕)
        # 這是覆蓋在上面的透明按鈕
        st.markdown('<div class="invisible-btn">', unsafe_allow_html=True)
        if st.button(" ", key="clk_avatar"):
            chat_dialog()
        st.markdown('</div>', unsafe_allow_html=True)

        # C. 補救措施：如果是 Image 模式，我們需要在這裡真的畫出那張圖
        # 因為 HTML 無法直接讀取 session_state 的 bytes
        if s['avatar_type'] == 'image' and s['avatar_image']:
            # 我們利用 columns 把圖片塞進那個圓形區域 (視覺微調可能需要)
            # 由於 Streamlit 限制，最簡單是放在下面，或者用 CSS 負 margin
            # 這裡為了穩定，我們把圖放在按鈕「下方」
            # 但因為 CSS 設定了 avatar-circle 的位置，我們可以用 st.image 顯示在 container 頂部
            # 其實最簡單係：
             st.markdown("""
                <style>
                /* 當有圖片時，隱藏 emoji 框，改為顯示圖片 */
                /* 這是個難點，Streamlit 難以精確控制 DOM */
                </style>
            """, unsafe_allow_html=True)
             # 直接在卡片中間顯示圖片，然後用負 Margin 拉上去？
             # 不，最穩定的方法是：不顯示 HTML 圓圈，直接顯示 st.image，然後用 CSS 把 st.image 變圓
             st.markdown("""
                <style>
                div[data-testid="stImage"] > img {
                    border-radius: 50%;
                    width: 180px !important;
                    height: 180px !important;
                    object-fit: cover;
                    border: 4px solid #06b6d4;
                    margin: 0 auto;
                }
                </style>
             """, unsafe_allow_html=True)
             st.image(s['avatar_image'])
             # 恢復下方 CSS 防止影響主衣櫃
             st.markdown("""
                <style>
                /* Reset for other images */
                </style>
             """, unsafe_allow_html=True)

        # 名字與設定 (並排)
        c_name, c_gear = st.columns([5, 1])
        with c_name:
            st.markdown(f"<h3 style='text-align:right; margin:0;'>{s['name']}</h3>", unsafe_allow_html=True)
        with c_gear:
            if st.button("⚙️", key="btn_settings_small"):
                settings_dialog()
        
        st.caption(f"早安 {p['name']}，{p['location']} 天氣不錯。\n(點擊頭像對話)")
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.divider()
    
    # 2. 加入衣櫃 (AI 自動分類修復版)
    st.subheader("📥 加入衣櫃")
    st.info("拖放圖片，AI 自動分類 (上衣/下身/鞋) ✨")
    
    season = st.selectbox("季節", ["四季", "春夏", "秋冬"], label_visibility="collapsed")
    
    files = st.file_uploader("Drop files", type=["jpg","png","webp"], accept_multiple_files=True, key=f"up_{st.session_state.uploader_key}")
    if files: process_upload(files, season)

    st.divider()
    if st.button("🗑️ 清空衣櫃", use_container_width=True):
        st.session_state.wardrobe = []
        st.rerun()

# --- 主畫面 ---
st.subheader("🧥 我的衣櫃")

if not st.session_state.wardrobe:
    st.info("👈 點擊左上角頭像找造型師傾偈，或者拖曳圖片入衣櫃！")
else:
    all_cats = list(set([item['category'] for item in st.session_state.wardrobe]))
    selected_cats = st.multiselect("🔍", all_cats, placeholder="篩選分類")
    display_items = [item for item in st.session_state.wardrobe if item['category'] in selected_cats] if selected_cats else st.session_state.wardrobe
    
    cols = st.columns(5)
    for i, item in enumerate(display_items):
        with cols[i % 5]:
            # 這裡需要重設 CSS，因為上面為了頭像改了 stImage 樣式
            # 我們使用 inline style 或者特定的 class (Streamlit 難以做到)
            # 解決方案：上面的 CSS 只針對側邊欄？很難。
            # 妥協：我們在 loop 裡強制 CSS
            st.markdown("""
                <style>
                div[data-testid="stColumn"] div[data-testid="stImage"] > img {
                    border-radius: 10px !important; /* 方角圓邊 */
                    width: 100% !important;
                    height: 250px !important;
                    border: none !important;
                }
                </style>
            """, unsafe_allow_html=True)
            st.image(item['image'])
            
            if st.button("✏️", key=f"edit_{item['id']}", use_container_width=True):
                edit_item_dialog(item)
