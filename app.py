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

# 初始化造型師 (移除 greeting，加入 custom_avatar_image)
if 'stylist_profile' not in st.session_state:
    st.session_state.stylist_profile = {
        "name": "莫弈",
        "avatar_type": "emoji", # 'emoji' or 'image'
        "avatar_emoji": "🤵",
        "avatar_image": None,   # 儲存上傳的圖片數據
        "persona": "一位品味高雅、語氣溫柔沉穩的專業形象設計師。語氣要優雅、知性、帶有淡淡的關懷。"
    }

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

# --- CSS 美化 ---
st.set_page_config(page_title="My Stylist", page_icon="✨", layout="wide")

st.markdown("""
    <style>
    /* 1. 強制圖片卡片尺寸 (200x300) */
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

    /* 3. File Uploader 簡化 */
    section[data-testid="stFileUploader"] label { display: none; }
    div[data-testid="stFileUploader"] { padding-top: 0px; }
    
    /* 4. 側邊欄造型師卡片樣式 */
    .stylist-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 20px;
        border: 1px solid #e0e0e0;
    }
    </style>
""", unsafe_allow_html=True)

# --- 功能函數 ---

def process_upload(files, category, season):
    if not files: return
    progress_bar = st.progress(0)
    status_text = st.empty()
    for i, uploaded_file in enumerate(files):
        status_text.caption(f"處理中: {uploaded_file.name}")
        try:
            image = Image.open(uploaded_file)
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            output_bytes = remove_bg(img_byte_arr.getvalue())
            final_image = Image.open(io.BytesIO(output_bytes))
            st.session_state.wardrobe.append({
                'id': str(uuid.uuid4()),
                'image': final_image,
                'category': category, 
                'season': season,
                'size_data': {'length': '', 'width': '', 'waist': ''}
            })
        except: pass
        progress_bar.progress((i + 1) / len(files))
    status_text.empty()
    progress_bar.empty()
    st.session_state.uploader_key += 1
    st.toast(f"已加入 {len(files)} 件！", icon="✅")
    time.sleep(1)
    st.rerun()

# --- 彈出視窗 (Dialogs) ---

@st.dialog("✏️ 編輯單品")
def edit_item_dialog(item):
    c1, c2 = st.columns([1, 1])
    with c1: st.image(item['image'], use_column_width=True)
    with c2:
        cat_opts = ["上衣", "下身褲裝", "下身裙裝", "連身裙/套裝", "外套", "鞋履", "配件/包包"]
        item['category'] = st.selectbox("分類", cat_opts, index=cat_opts.index(item['category']) if item['category'] in cat_opts else 0)
        st.caption("詳細尺碼 (自動儲存)")
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
        st.session_state.user_profile['location'] = st.text_input("居住地區", value=st.session_state.user_profile['location'])
        c1, c2 = st.columns(2)
        with c1: st.session_state.user_profile['height'] = st.number_input("身高", value=st.session_state.user_profile['height'])
        with c2: st.session_state.user_profile['measurements']['waist'] = st.number_input("腰圍", value=st.session_state.user_profile['measurements']['waist'])
    
    with tab2:
        st.session_state.stylist_profile['name'] = st.text_input("造型師名字", value=st.session_state.stylist_profile['name'])
        
        # 頭像設定
        avatar_mode = st.radio("頭像類型", ["Emoji", "上傳圖片"], horizontal=True)
        if avatar_mode == "Emoji":
            st.session_state.stylist_profile['avatar_type'] = 'emoji'
            st.session_state.stylist_profile['avatar_emoji'] = st.text_input("Emoji", value=st.session_state.stylist_profile['avatar_emoji'])
        else:
            st.session_state.stylist_profile['avatar_type'] = 'image'
            uploaded_avatar = st.file_uploader("上傳頭像", type=["jpg", "png"])
            if uploaded_avatar:
                img = Image.open(uploaded_avatar)
                # 轉為 bytes 儲存
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')
                st.session_state.stylist_profile['avatar_image'] = img_byte_arr.getvalue()

        # 人設選擇
        st.write("---")
        st.write("🎭 **選擇人設**")
        
        personas = {
            "莫弈 (專業優雅)": "你現在是「莫弈」，一位品味高雅、語氣溫柔沉穩的專業形象設計師。語氣要優雅、知性、帶有淡淡的關懷。請用紳士的角度給予建議，像一位相識多年的知己。",
            "霸道總裁 (佔有慾)": "你現在是霸道總裁男友。語氣要自信、強勢但充滿寵溺。叫用戶『笨蛋』或『寶貝』。如果衣服太露，要表現出吃醋，說『這只能在家穿給我看』。",
            "溫柔奶狗 (暖男)": "你現在是年下的溫柔男友。語氣要超級甜，充滿愛意，叫用戶『姐姐』或『BB』。不管穿什麼都瘋狂稱讚，最在意你有沒有穿暖。",
            "毒舌主編 (犀利)": "你現在是頂級時尚雜誌的主編。眼光極高，說話尖酸刻薄但一針見血。看到搭配不好會直接說『這簡直是災難』，但給出的建議絕對專業。",
            "貼身管家 (尊貴)": "你現在是皇家級貼身管家。語氣要極度恭敬、正式，稱呼用戶為『大小姐』。為您服務是我的榮幸。"
        }
        
        sel_p = st.selectbox("快速套用", list(personas.keys()))
        if st.button("套用此人設"):
            st.session_state.stylist_profile['persona'] = personas[sel_p]
            st.rerun()
            
        st.session_state.stylist_profile['persona'] = st.text_area("人設指令 (可手動修改)", value=st.session_state.stylist_profile['persona'], height=100)

    if st.button("儲存設定", use_container_width=True, type="primary"):
        st.rerun()

# --- 聊天對話視窗 ---
@st.dialog("💬 與造型師對話", width="large")
def chat_dialog():
    s = st.session_state.stylist_profile
    p = st.session_state.user_profile
    
    # 顯示造型師資訊
    col_av, col_nm = st.columns([1, 4])
    with col_av:
        if s['avatar_type'] == 'image' and s['avatar_image']:
            st.image(s['avatar_image'], width=60)
        else:
            st.markdown(f"<h1 style='text-align: center; margin: 0;'>{s['avatar_emoji']}</h1>", unsafe_allow_html=True)
    with col_nm:
        st.subheader(s['name'])
        st.caption(s['persona'][:50] + "...")

    st.divider()

    # 自動開場白 (如果沒有歷史記錄)
    if not st.session_state.chat_history:
        # 模擬天氣 (因為無 API)
        weathers = ["天晴，陽光普照", "有微雨，比較濕", "多雲，秋高氣爽", "氣溫驟降，好凍"]
        random_weather = random.choice(weathers)
        
        # 構造開場 Prompt
        opening_prompt = (
            f"你現在是「{s['name']}」，{s['persona']}\n"
            f"用戶現在在 {p['location']}。\n"
            f"請根據這個地點，虛構一個合理的當下天氣狀況（例如：{random_weather}）。\n"
            f"任務：\n"
            f"1. 先向用戶 {p['name']} 打招呼。\n"
            f"2. 報告當地的天氣狀況。\n"
            f"3. 溫柔地詢問用戶今天打算去哪裡，或者想要什麼風格的穿搭。\n"
            f"4. 保持角色人設語氣。\n"
        )
        
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(opening_prompt)
            st.session_state.chat_history.append({"role": "assistant", "content": response.text})
        except:
            st.session_state.chat_history.append({"role": "assistant", "content": f"Hi {p['name']}，今日天氣點呀？想我幫你襯咩衫？"})

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
    if prompt := st.chat_input(f"話俾 {s['name']} 知你去邊..."):
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("思考搭配中..."):
                try:
                    # 準備 Prompt
                    sys_prompt = (
                        f"你現在是「{s['name']}」。{s['persona']}\n"
                        f"【用戶】{p['name']}, 身高{p['height']}cm, 住{p['location']}。\n"
                        f"【對話歷史】之前的對話在上方。\n"
                        f"【用戶新訊息】{prompt}\n"
                        f"【任務】\n"
                        f"1. 根據用戶需求和天氣，從衣櫃挑選衣服。\n"
                        f"2. 明確列出建議穿著的單品 (參考附圖)。\n"
                        f"3. 保持人設語氣。\n"
                    )
                    
                    inputs = [sys_prompt]
                    if st.session_state.wardrobe:
                        # 只傳送前 20 件以防 Token 爆
                        for i, item in enumerate(st.session_state.wardrobe[:20]):
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
    
    # 1. 造型師卡片 Widget
    st.markdown('<div class="stylist-card">', unsafe_allow_html=True)
    
    # 顯示頭像 (處理圖片置中)
    col_center = st.columns([1,2,1])
    with col_center[1]:
        if s['avatar_type'] == 'image' and s['avatar_image']:
            st.image(s['avatar_image'], width=100)
        else:
            st.markdown(f"<h1 style='font-size: 60px; margin:0;'>{s['avatar_emoji']}</h1>", unsafe_allow_html=True)
            
    st.markdown(f"<h3>{s['name']}</h3>", unsafe_allow_html=True)
    st.caption("專屬形象顧問")
    
    # 按鈕列
    b1, b2 = st.columns([3, 1])
    with b1:
        if st.button("💬 進入互動", type="primary", use_container_width=True):
            chat_dialog()
    with b2:
        if st.button("⚙️", help="設定"):
            settings_dialog()
            
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.divider()
    
    # 2. 加入衣櫃
    st.subheader("📥 加入衣櫃")
    c1, c2 = st.columns(2)
    with c1: cat = st.selectbox("分類", ["上衣", "下身褲裝", "下身裙裝", "連身裙", "外套", "鞋履", "配件"], label_visibility="collapsed")
    with c2: season = st.selectbox("季節", ["四季", "春夏", "秋冬"], label_visibility="collapsed")
    
    files = st.file_uploader("Drop files", type=["jpg","png","webp"], accept_multiple_files=True, key=f"up_{st.session_state.uploader_key}")
    if files: process_upload(files, cat, season)

    st.divider()
    if st.button("🗑️ 清空衣櫃", use_container_width=True):
        st.session_state.wardrobe = []
        st.rerun()

# --- 主畫面 (只顯示衣櫃) ---

# 標題區
st.subheader("🧥 我的衣櫃")

if not st.session_state.wardrobe:
    st.info("👈 點擊左側「進入互動」來獲取建議，或直接拖曳圖片上傳衣服！")
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
