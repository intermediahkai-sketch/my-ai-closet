import streamlit as st
import google.generativeai as genai
from PIL import Image
import uuid
import io
import time
import random
from rembg import remove as remove_bg

# --- 1. 設定 API Key ---
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("❌ 找不到 API Key，請檢查 Secrets 設定")
    st.stop()

# --- 2. 初始化資料 ---
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
        "current_weather": "晴朗 24°C"
    }

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

# --- 3. 頁面設定與 CSS ---
st.set_page_config(page_title="My Stylist", page_icon="✨", layout="wide")

st.markdown("""
    <style>
    /* 圖片卡片樣式 */
    div[data-testid="stImage"] {
        background-color: #f9f9f9;
        border-radius: 10px;
        padding: 5px;
        display: flex;
        justify-content: center; 
    }
    div[data-testid="stImage"] img {
        height: 250px !important;
        object-fit: contain !important;
    }
    /* 按鈕樣式微調 */
    button[kind="secondary"] {
        border: 1px solid #e0e0e0;
    }
    /* 聊天室優化 */
    .chat-container {
        padding-bottom: 50px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 4. 核心功能函數 (防彈版) ---

def compress_image(image):
    """將圖片縮小以加快 AI 傳輸速度，防止斷線"""
    image = image.convert('RGB')
    image.thumbnail((512, 512)) # 縮小到 512px
    return image

def safe_ask_ai(inputs):
    """
    超級安全的 AI 連線函數：
    1. 嘗試多個模型
    2. 捕捉所有錯誤，絕不 Crash
    """
    # 優先嘗試的模型列表
    models = ["gemini-1.5-flash", "gemini-1.5-flash-latest", "gemini-pro"]
    
    error_log = []
    
    for model_name in models:
        try:
            model = genai.GenerativeModel(model_name)
            # 設定生成參數，減少超時機會
            config = genai.types.GenerationConfig(
                max_output_tokens=500, 
                temperature=0.7
            )
            response = model.generate_content(inputs, generation_config=config)
            return response.text
        except Exception as e:
            error_log.append(f"{model_name}: {str(e)}")
            continue # 試下一個
            
    # 如果全部失敗，回傳錯誤訊息，但不要讓程式崩潰
    return f"⚠️ 抱歉，AI 線路繁忙 (連線失敗)。請稍後再試。\n(錯誤代碼: {error_log[-1] if error_log else 'Unknown'})"

def process_upload(files, category, season):
    if not files: return
    progress_bar = st.progress(0)
    
    for i, uploaded_file in enumerate(files):
        try:
            image = Image.open(uploaded_file)
            # 去背
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
    
    time.sleep(0.5)
    progress_bar.empty()
    st.session_state.uploader_key += 1
    st.toast(f"✅ 已加入 {len(files)} 件單品", icon="🧥")
    st.rerun()

def update_weather_if_needed():
    loc = st.session_state.user_profile['location']
    if "last_loc" not in st.session_state or st.session_state.last_loc != loc:
        weathers = ["晴朗 28°C", "多雲 22°C", "微雨 19°C", "乾燥 25°C"]
        st.session_state.stylist_profile['current_weather'] = random.choice(weathers)
        st.session_state.last_loc = loc

# --- 5. 彈出視窗 ---

@st.dialog("✏️ 編輯單品")
def edit_item_dialog(item):
    c1, c2 = st.columns([1, 1])
    with c1: st.image(item['image'], use_column_width=True)
    with c2:
        cats = ["上衣", "下身褲裝", "下身裙裝", "連身裙/套裝", "外套", "鞋履", "配件"]
        idx = cats.index(item['category']) if item['category'] in cats else 0
        item['category'] = st.selectbox("分類", cats, index=idx)
        
        if any(x in item['category'] for x in ["上衣", "外套", "連身裙"]):
            item['size_data']['length'] = st.text_input("衣長", value=item['size_data']['length'])
            item['size_data']['width'] = st.text_input("胸寬", value=item['size_data']['width'])
        elif any(x in item['category'] for x in ["下身", "褲", "裙"]):
            item['size_data']['length'] = st.text_input("褲/裙長", value=item['size_data']['length'])
            item['size_data']['waist'] = st.text_input("腰圍", value=item['size_data']['waist'])
        
        st.divider()
        if st.button("🗑️ 刪除", type="primary", use_container_width=True):
            st.session_state.wardrobe.remove(item)
            st.rerun()

@st.dialog("⚙️ 設定")
def settings_dialog():
    st.subheader("👤 個人資料")
    p = st.session_state.user_profile
    p['name'] = st.text_input("暱稱", value=p['name'])
    p['location'] = st.selectbox("地區", ["香港", "台北", "東京", "首爾", "倫敦"], index=0)
    
    c1, c2, c3 = st.columns(3)
    p['height'] = c1.number_input("身高", value=p['height'])
    p['measurements']['waist'] = c2.number_input("腰圍", value=p['measurements']['waist'])
    p['measurements']['hips'] = c3.number_input("臀圍", value=p['measurements']['hips'])

    st.divider()
    st.subheader("✨ 造型師設定")
    s = st.session_state.stylist_profile
    s['name'] = st.text_input("造型師名字", value=s['name'])
    
    use_img = st.toggle("使用圖片頭像?", value=(s['avatar_type']=='image'))
    if use_img:
        s['avatar_type'] = 'image'
        up_img = st.file_uploader("上傳頭像", type=['png','jpg'])
        if up_img:
            img = Image.open(up_img)
            b = io.BytesIO()
            img.save(b, format='PNG')
            s['avatar_image'] = b.getvalue()
    else:
        s['avatar_type'] = 'emoji'
        s['avatar_emoji'] = st.text_input("Emoji", value=s['avatar_emoji'])

    # 人設選擇 (Callback 模式)
    def on_persona_change():
        presets = {
            "專業莫弈": "你現在是「莫弈」，一位品味高雅、語氣溫柔沉穩的專業形象設計師。語氣要優雅、知性、帶有淡淡的關懷。",
            "霸道總裁": "你現在是霸道總裁男友。語氣要自信、強勢但充滿寵溺。叫用戶『笨蛋』或『寶貝』。如果衣服太露，要表現出吃醋。",
            "溫柔奶狗": "你現在是年下的溫柔男友。語氣要超級甜，充滿愛意，叫用戶『姐姐』或『BB』。不管穿什麼都瘋狂稱讚。",
            "毒舌主編": "你現在是頂級時尚雜誌的主編。眼光極高，說話尖酸刻薄但一針見血。看到搭配不好會直接說『這簡直是災難』。"
        }
        val = st.session_state.persona_select_box
        if val in presets:
            st.session_state.stylist_profile['persona'] = presets[val]

    st.selectbox(
        "快速選擇人設", 
        ["專業莫弈", "霸道總裁", "溫柔奶狗", "毒舌主編"], 
        key="persona_select_box",
        index=None,
        placeholder="請選擇...",
        on_change=on_persona_change
    )
    
    s['persona'] = st.text_area("人設指令", value=s['persona'], height=100)

    if st.button("完成", type="primary", use_container_width=True):
        st.rerun()

# --- 聊天 Dialog (防崩潰版) ---
@st.dialog("💬 與造型師對話", width="large")
def chat_dialog():
    s = st.session_state.stylist_profile
    p = st.session_state.user_profile
    
    # 頂部
    c1, c2 = st.columns([1, 4])
    with c1:
        if s['avatar_type'] == 'image' and s['avatar_image']:
            st.image(s['avatar_image'], width=80)
        else:
            st.markdown(f"<h1 style='text-align:center; margin:0'>{s['avatar_emoji']}</h1>", unsafe_allow_html=True)
    with c2:
        st.subheader(s['name'])
        st.caption(f"📍 {p['location']} | {s['current_weather']}")
    
    st.divider()
    update_weather_if_needed()

    # 自動開場
    if not st.session_state.chat_history:
        # 這裡不呼叫 AI，直接用預設文字，避免開場就斷線 Crash
        welcome_msg = f"早安 {p['name']}！我是{s['name']}。今日天氣 {s['current_weather']}，想我點幫你襯？"
        st.session_state.chat_history.append({"role": "assistant", "content": welcome_msg})
        st.rerun()

    # 顯示歷史
    for msg in st.session_state.chat_history:
        role = msg["role"]
        with st.chat_message(role):
            st.write(msg["content"])

    # 輸入區
    if user_in := st.chat_input("輸入訊息..."):
        # 1. 加入用戶訊息
        st.session_state.chat_history.append({"role": "user", "content": user_in})
        
        # 2. 準備 AI 回應 (在 Spinner 裡面)
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                sys_msg = (
                    f"你是{s['name']}。{s['persona']}\n"
                    f"用戶：{p['name']}, 身高{p['height']}, {p['location']} ({s['current_weather']})。\n"
                    f"最新訊息：{user_in}\n"
                    f"請從衣櫃建議穿搭 (如有)。"
                )
                
                inputs = [sys_msg]
                # 傳送衣櫃 (只傳前 10 件，並壓縮圖片)
                if st.session_state.wardrobe:
                    for i, item in enumerate(st.session_state.wardrobe[:10]):
                        # 壓縮圖片防止 payload 太大
                        resized_img = compress_image(item['image'])
                        inputs.append(f"單品#{i+1} ({item['category']})")
                        inputs.append(resized_img)
                
                # 呼叫安全函數
                reply = safe_ask_ai(inputs)
                
                # 顯示並儲存
                st.markdown(reply)
                st.session_state.chat_history.append({"role": "assistant", "content": reply})
        
        # 強制刷新一次以更新狀態 (不需要，st.chat_input 會自動刷新)
        st.rerun()
        
    # 清除記錄按鈕
    if st.button("清除對話記錄", type="secondary", help="如果對話卡住，請按此"):
        st.session_state.chat_history = []
        st.rerun()

# --- 6. 側邊欄 ---
with st.sidebar:
    s = st.session_state.stylist_profile
    p = st.session_state.user_profile
    
    with st.container(border=True):
        # 頭像
        c_av = st.columns([1, 2, 1])
        with c_av[1]:
            if s['avatar_type'] == 'image' and s['avatar_image']:
                st.image(s['avatar_image'], use_column_width=True)
            else:
                st.markdown(f"<div style='text-align:center; font-size:80px;'>{s['avatar_emoji']}</div>", unsafe_allow_html=True)
        
        # 名字
        st.markdown(f"<h3 style='text-align:center; margin:0;'>{s['name']}</h3>", unsafe_allow_html=True)
        
        # 設定按鈕
        if st.button("⚙️ 設定", use_container_width=True):
            settings_dialog()
            
        st.caption(f"早安 {p['name']} | {s['current_weather']}")
        
        st.divider()
        
        # 聊天按鈕
        if st.button("💬 開始對話", type="primary", use_container_width=True):
            chat_dialog()

    # 加入衣櫃
    st.subheader("📥 加入衣櫃")
    c1, c2 = st.columns(2)
    cat = c1.selectbox("分類", ["上衣", "下身褲裝", "下身裙裝", "連身裙", "外套", "鞋履", "配件"])
    sea = c2.selectbox("季節", ["四季", "春夏", "秋冬"])
    
    files = st.file_uploader("拖曳圖片 (自動去背)", type=['jpg','png','webp'], accept_multiple_files=True, key=f"up_{st.session_state.uploader_key}")
    if files: process_upload(files, cat, sea)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🗑️ 清空衣櫃", use_container_width=True):
        st.session_state.wardrobe = []
        st.rerun()

# --- 7. 主畫面 ---
st.subheader("🧥 我的衣櫃")

if not st.session_state.wardrobe:
    st.info("👈 左側加入單品，然後點「開始對話」！")
else:
    cats = list(set([x['category'] for x in st.session_state.wardrobe]))
    sel = st.multiselect("🔍", cats, placeholder="篩選分類")
    items = [x for x in st.session_state.wardrobe if x['category'] in sel] if sel else st.session_state.wardrobe
    
    cols = st.columns(5)
    for i, item in enumerate(items):
        with cols[i % 5]:
            st.image(item['image'])
            if st.button("✏️", key=f"b_{item['id']}", use_container_width=True):
                edit_item_dialog(item)
