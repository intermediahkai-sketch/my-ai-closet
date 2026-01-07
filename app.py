import streamlit as st
import google.generativeai as genai
from PIL import Image
import uuid
import io
import time
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

# 初始化用戶與造型師設定
if 'user_profile' not in st.session_state:
    st.session_state.user_profile = {
        "name": "User", 
        "location": "香港",
        "gender": "女",
        "height": 160, 
        "measurements": {"bust": 0, "waist": 0, "hips": 0},
        "style_pref": "簡約休閒"
    }

# 初始化造型師人格 (新增)
if 'stylist_profile' not in st.session_state:
    st.session_state.stylist_profile = {
        "name": "莫弈",
        "avatar": "🤵", # 預設頭像
        "persona": "一位品味高雅、語氣溫柔沉穩的專業形象設計師。語氣要優雅、知性、帶有淡淡的關懷。", # 人設Prompt
        "greeting": "早安"
    }

# 聊天記錄
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

# --- CSS 美化 (強制圖片尺寸 200x300 & UI優化) ---
st.set_page_config(page_title="My Stylist", page_icon="✨", layout="wide")

st.markdown("""
    <style>
    /* 1. 強制圖片卡片尺寸 (200x300) 與 填滿模式 */
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
        object-fit: cover !important; /* 裁切以填滿 */
        max-width: none !important;
    }
    
    /* 2. 去除按鈕灰框，變成純 Icon */
    button[kind="secondary"] {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
    }
    button[kind="secondary"]:hover {
        color: #06b6d4 !important;
        background: transparent !important;
    }

    /* 3. 隱藏 File Uploader 的預設文字，讓它更簡潔 */
    section[data-testid="stFileUploader"] label {
        display: none;
    }
    div[data-testid="stFileUploader"] {
        padding-top: 0px;
    }
    
    /* 4. 互動按鈕樣式 (仿照你提供的圖) */
    .chat-btn-container {
        display: flex;
        align-items: center;
        justify-content: flex-end;
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 15px;
        cursor: pointer;
        margin-bottom: 20px;
        border: 1px solid #e0e0e0;
    }
    .chat-text {
        text-align: right;
        margin-right: 15px;
        color: #333;
    }
    .chat-avatar {
        width: 50px;
        height: 50px;
        border-radius: 50%;
        background-color: #06b6d4;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

# --- 功能函數 ---

# 1. 自動去背與儲存
def process_upload(files, category, season):
    if not files: return
    
    # 顯示進度條
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, uploaded_file in enumerate(files):
        status_text.caption(f"正在處理: {uploaded_file.name} (自動去背中...)")
        try:
            image = Image.open(uploaded_file)
            # 自動去背
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            output_bytes = remove_bg(img_byte_arr.getvalue())
            final_image = Image.open(io.BytesIO(output_bytes))
            
            # 存入
            st.session_state.wardrobe.append({
                'id': str(uuid.uuid4()),
                'image': final_image,
                'category': category, 
                'season': season,
                'size_data': {'length': '', 'width': '', 'waist': ''}
            })
        except Exception as e:
            st.error(f"處理失敗: {e}")
        
        progress_bar.progress((i + 1) / len(files))
    
    status_text.empty()
    progress_bar.empty()
    st.session_state.uploader_key += 1 # 重置上傳器
    st.toast(f"已成功加入 {len(files)} 件單品！", icon="✅")
    time.sleep(1) # 稍作停留讓用戶看到
    st.rerun()

# 2. 單品編輯彈出視窗 (Dialog)
@st.dialog("✏️ 編輯單品")
def edit_item_dialog(item):
    c1, c2 = st.columns([1, 1])
    with c1:
        st.image(item['image'], use_column_width=True)
    with c2:
        # 修改分類
        cat_options = ["上衣", "下身褲裝", "下身裙裝", "連身裙/套裝", "外套", "鞋履", "配件/包包"]
        new_cat = st.selectbox("分類", cat_options, index=cat_options.index(item['category']) if item['category'] in cat_options else 0)
        item['category'] = new_cat # Auto save logic: updating session state object directly

        # 尺碼 (Auto save on blur)
        st.caption("詳細尺碼 (輸入後點擊空白處即自動儲存)")
        if any(x in item['category'] for x in ["上衣", "外套", "連身裙"]):
            item['size_data']['length'] = st.text_input("衣長 (cm)", value=item['size_data']['length'])
            item['size_data']['width'] = st.text_input("衣闊/胸寬 (cm)", value=item['size_data']['width'])
        elif any(x in item['category'] for x in ["下身", "褲", "裙"]):
            item['size_data']['length'] = st.text_input("褲/裙長 (cm)", value=item['size_data']['length'])
            item['size_data']['waist'] = st.text_input("腰圍 (吋/cm)", value=item['size_data']['waist'])
        else:
            item['size_data']['width'] = st.text_input("備註/尺碼", value=item['size_data']['width'])

        st.divider()
        if st.button("🗑️ 刪除此單品", type="primary", use_container_width=True):
            st.session_state.wardrobe.remove(item)
            st.rerun()

# 3. 設定彈出視窗
@st.dialog("⚙️ 設定檔案 & 造型師")
def settings_dialog():
    tab_user, tab_stylist = st.tabs(["👤 個人資料", "✨ 造型師設定"])
    
    with tab_user:
        st.session_state.user_profile['name'] = st.text_input("你的暱稱", value=st.session_state.user_profile['name'])
        st.session_state.user_profile['location'] = st.text_input("居住地區", value=st.session_state.user_profile['location'])
        st.session_state.user_profile['gender'] = st.radio("性別", ["女", "男", "通用"], index=["女", "男", "通用"].index(st.session_state.user_profile['gender']), horizontal=True)
        
        c1, c2, c3 = st.columns(3)
        with c1: st.session_state.user_profile['height'] = st.number_input("身高", value=st.session_state.user_profile['height'])
        with c2: st.session_state.user_profile['measurements']['bust'] = st.number_input("胸圍", value=st.session_state.user_profile['measurements']['bust'])
        with c3: st.session_state.user_profile['measurements']['waist'] = st.number_input("腰圍", value=st.session_state.user_profile['measurements']['waist'])
        
    with tab_stylist:
        st.info("在這裡設定你想 AI 扮演的角色，例如男友、管家或毒舌專家。")
        st.session_state.stylist_profile['name'] = st.text_input("造型師名字", value=st.session_state.stylist_profile['name'])
        st.session_state.stylist_profile['avatar'] = st.text_input("頭像 Emoji", value=st.session_state.stylist_profile['avatar'])
        st.session_state.stylist_profile['greeting'] = st.text_input("打招呼方式", value=st.session_state.stylist_profile['greeting'], placeholder="例如: 早安 BB")
        
        persona_presets = {
            "專業莫弈": "一位品味高雅、語氣溫柔沉穩的專業形象設計師。語氣要優雅、知性、帶有淡淡的關懷。",
            "霸道總裁": "一位強勢但寵溺的總裁男友。語氣要自信、直接，叫用戶『笨蛋』或『寶貝』，會吃醋。",
            "溫柔男友": "一位超級暖男，無微不至。語氣充滿愛意，叫用戶『BB』，經常稱讚。",
            "毒舌閨蜜": "一位說話直接、尖酸刻薄但眼光獨到的時尚編輯。語氣要潑辣、幽默、一針見血。"
        }
        
        selected_preset = st.selectbox("快速選擇人設", list(persona_presets.keys()))
        if st.button("套用人設"):
            st.session_state.stylist_profile['persona'] = persona_presets[selected_preset]
            
        st.session_state.stylist_profile['persona'] = st.text_area("人設指令 (Prompt)", value=st.session_state.stylist_profile['persona'], height=100)

    if st.button("完成", use_container_width=True):
        st.rerun()

# --- 側邊欄 (極簡化) ---
with st.sidebar:
    # 頂部：設定按鈕
    if st.button("⚙️", help="設定個人檔案及造型師"):
        settings_dialog()
    
    st.divider()
    
    # 加入衣櫃區
    st.subheader("📥 加入衣櫃")
    
    c1, c2 = st.columns(2)
    with c1: cat = st.selectbox("分類", ["上衣", "下身褲裝", "下身裙裝", "連身裙/套裝", "外套", "鞋履", "配件/包包"], label_visibility="collapsed")
    with c2: season = st.selectbox("季節", ["四季", "春夏", "秋冬"], label_visibility="collapsed")
    
    # 拖曳上傳 (無按鈕，自動觸發)
    files = st.file_uploader("Drop files", type=["jpg","png","webp"], accept_multiple_files=True, key=f"up_{st.session_state.uploader_key}")
    
    if files:
        process_upload(files, cat, season)

    st.divider()
    if st.button("🗑️ 清空衣櫃", use_container_width=True):
        st.session_state.wardrobe = []
        st.rerun()

# --- 主畫面 ---
# 頂部打招呼區 (左上角)
p = st.session_state.user_profile
s = st.session_state.stylist_profile

col_header, col_weather = st.columns([2, 1])
with col_header:
    st.title(f"{s['avatar']} {s['name']}: {s['greeting']}, {p['name']}")
with col_weather:
    st.caption(f"📍 {p['location']} | 🌡️ {st.session_state.get('last_temp', '24')}°C")

# 分頁
tab1, tab2 = st.tabs(["🧥 我的衣櫃", "💬 互動穿搭"])

with tab1:
    if not st.session_state.wardrobe:
        st.info("👈 左側直接拖曳圖片即可加入衣櫃 (自動去背)！")
    else:
        # 篩選
        all_cats = list(set([item['category'] for item in st.session_state.wardrobe]))
        selected_cats = st.multiselect("🔍", all_cats, placeholder="篩選分類 (顯示全部)")
        
        display_items = [item for item in st.session_state.wardrobe if item['category'] in selected_cats] if selected_cats else st.session_state.wardrobe
        
        # Grid 顯示 (4 columns for 200px width look)
        cols = st.columns(5)
        for i, item in enumerate(display_items):
            with cols[i % 5]:
                # 圖片 (CSS 強制 200x300)
                st.image(item['image'])
                
                # 只有一個鉛筆按鈕
                if st.button("✏️", key=f"edit_{item['id']}", use_container_width=True):
                    edit_item_dialog(item)

with tab2:
    # 模仿你圖片的互動入口
    st.markdown(f"""
    <div class="chat-btn-container">
        <div class="chat-text">
            <strong>有穿搭煩惱？問我啦！</strong><br>
            <span style="font-size: 12px; color: #666;">點擊開始與 {s['name']} 對話</span>
        </div>
        <div class="chat-avatar">{s['avatar']}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # 環境設定
    c1, c2, c3 = st.columns(3)
    with c1: weather = st.text_input("天氣", "晴朗")
    with c2: temp = st.text_input("氣溫", "24")
    with c3: occasion = st.text_input("場合", "約會")
    if temp: st.session_state['last_temp'] = temp

    # 聊天歷史顯示
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"], avatar=s['avatar'] if msg["role"] == "assistant" else None):
            st.markdown(msg["content"])
            if "image" in msg:
                st.image(msg["image"], width=200)

    # 聊天輸入框
    if prompt := st.chat_input(f"同 {s['name']} 講你想點襯..."):
        # 1. 用戶訊息
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. AI 思考與回應
        with st.chat_message("assistant", avatar=s['avatar']):
            with st.spinner(f"{s['name']} 正在配搭中..."):
                try:
                    # 構建 Prompt
                    user_info = f"用戶:{p['name']}, 性別:{p['gender']}, 身高:{p['height']}cm, 三圍:{p['measurements']['bust']}/{p['measurements']['waist']}"
                    
                    sys_prompt = (
                        f"你現在的身分是「{s['name']}」。{s['persona']}\n"
                        f"【用戶資料】{user_info}。\n"
                        f"【今日情報】地點:{p['location']}, 天氣:{weather}, 氣溫:{temp}°C, 場合:{occasion}。\n"
                        f"【你的任務】\n"
                        f"用戶問：「{prompt}」。請從衣櫃中挑選衣服回應。\n"
                        f"回應格式：\n"
                        f"1. 先用你的人設語氣回應 (例如男友口吻)。\n"
                        f"2. 明確列出你建議穿哪幾件 (編號+名稱)。\n"
                        f"3. 解釋為什麼這樣配 (針對天氣/場合/身形)。\n"
                    )
                    
                    inputs = [sys_prompt]
                    # 加入衣櫃圖片供 AI 參考
                    items_to_send = display_items if 'display_items' in locals() and display_items else st.session_state.wardrobe
                    for i, item in enumerate(items_to_send):
                        s_info = item['size_data']
                        size_str = f"L:{s_info['length']} W:{s_info['width']} Waist:{s_info['waist']}"
                        inputs.append(f"圖#{i+1} [{item['category']}] ({size_str})")
                        inputs.append(item['image'])
                    
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    response = model.generate_content(inputs)
                    
                    st.markdown(response.text)
                    st.session_state.chat_history.append({"role": "assistant", "content": response.text})
                    
                except Exception as e:
                    st.error(f"AI 發生錯誤: {e}")
