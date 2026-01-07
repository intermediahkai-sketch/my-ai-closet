import streamlit as st
import google.generativeai as genai
from PIL import Image
import uuid
import time
import random

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
        "name": "你的專屬 Stylist",
        "avatar_type": "emoji",
        "avatar_emoji": "✨",
        "avatar_image": None,
        "persona": "一位貼心的專業形象顧問，語氣親切、專業。",
        "current_weather": "晴朗 24°C" # 還原天氣
    }

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

# --- 3. 頁面設定與 CSS (還原你最愛的 UI) ---
st.set_page_config(page_title="My Stylist", page_icon="👗", layout="wide")

st.markdown("""
    <style>
    /* 1. 圖片卡片 */
    div[data-testid="stImage"] {
        background-color: #f9f9f9;
        border-radius: 10px;
        padding: 5px;
        display: flex;
        justify-content: center;
        align-items: center;
    }
    div[data-testid="stImage"] img {
        height: 220px !important;
        object-fit: contain !important;
    }
    
    /* 2. 造型師卡片 (大頭像風格) */
    .stylist-container {
        background-color: #f0f2f6;
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        border: 1px solid #e0e0e0;
        margin-bottom: 20px;
    }
    .avatar-circle {
        width: 100px;
        height: 100px;
        border-radius: 50%;
        margin: 0 auto 10px auto;
        border: 3px solid #06b6d4;
        background-color: white;
        display: flex;
        justify-content: center;
        align-items: center;
        overflow: hidden;
        font-size: 50px;
    }
    .avatar-circle img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    
    /* 3. 按鈕微調 */
    button[kind="secondary"] { border: 1px solid #ddd; }
    </style>
""", unsafe_allow_html=True)

# --- 4. 核心功能 ---

def compress_image(image):
    """壓縮圖片防斷線"""
    image = image.convert('RGB')
    image.thumbnail((512, 512))
    return image

def ask_gemini(inputs):
    """AI 連線 (已對應新版 requirements)"""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(inputs)
        return response.text
    except Exception as e:
        # 如果 Flash 失敗，自動試 Pro
        try:
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(inputs)
            return response.text
        except:
            return f"⚠️ 連線失敗: {str(e)} (請確認 requirements.txt 已更新)"

def process_upload(files, category, season):
    if not files: return
    for file in files:
        try:
            img = Image.open(file)
            st.session_state.wardrobe.append({
                'id': str(uuid.uuid4()), 
                'image': img, 
                'category': category, 
                'season': season,
                'size_data': {'length': '', 'width': '', 'waist': ''} # 初始化尺碼欄位
            })
        except: pass
    st.session_state.uploader_key += 1
    st.toast(f"✅ 已加入 {len(files)} 件", icon="🧥")
    time.sleep(0.5)
    st.rerun()

# --- 5. Dialogs (功能修復) ---

@st.dialog("✏️ 編輯單品")
def edit_item_dialog(item):
    c1, c2 = st.columns([1, 1])
    with c1: st.image(item['image'])
    with c2:
        cats = ["上衣", "下身褲裝", "下身裙裝", "連身裙", "外套", "鞋履", "配件"]
        idx = cats.index(item['category']) if item['category'] in cats else 0
        item['category'] = st.selectbox("分類", cats, index=idx)
        
        # 還原詳細尺碼輸入
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
        if st.button("🗑️ 刪除", type="primary"):
            st.session_state.wardrobe.remove(item)
            st.rerun()

@st.dialog("⚙️ 設定")
def settings_dialog():
    st.subheader("👤 用戶資料")
    p = st.session_state.user_profile
    p['name'] = st.text_input("暱稱", value=p['name'])
    p['location'] = st.selectbox("地區", ["香港", "台北", "東京", "首爾", "倫敦"], index=0)
    
    st.subheader("✨ Stylist 設定")
    s = st.session_state.stylist_profile
    s['name'] = st.text_input("Stylist 名字", value=s['name'])
    
    use_img = st.checkbox("使用圖片頭像")
    if use_img:
        s['avatar_type'] = 'image'
        f = st.file_uploader("上傳頭像", type=['png','jpg'])
        if f: s['avatar_image'] = f.getvalue()
    else:
        s['avatar_type'] = 'emoji'
        s['avatar_emoji'] = st.text_input("Emoji", value=s['avatar_emoji'])

    # 人設修復
    presets = {
        "專業顧問": "一位貼心的專業形象顧問，語氣親切、專業。",
        "毒舌專家": "眼光極高的時尚主編，說話尖酸刻薄但一針見血。",
        "溫柔男友": "充滿愛意的男友，不管穿什麼都稱讚。",
        "霸道總裁": "強勢但寵溺的總裁，不准穿太露。"
    }
    
    # 使用 Button 確保更新
    selected_p = st.selectbox("人設風格", list(presets.keys()))
    if st.button("⬇️ 套用人設"):
        s['persona'] = presets[selected_p]
        st.success(f"已切換為：{selected_p}")
        time.sleep(0.5)
        st.rerun() # 強制刷新確保文字框更新
    
    s['persona'] = st.text_area("指令", value=s['persona'])
    if st.button("完成", type="primary"): st.rerun()

# --- 6. 聊天功能 (防彈版) ---
@st.dialog("💬 與 Stylist 對話", width="large")
def chat_dialog():
    s = st.session_state.stylist_profile
    p = st.session_state.user_profile
    
    # 頂部
    c1, c2 = st.columns([1, 4])
    with c1:
        if s['avatar_type'] == 'image' and s['avatar_image']:
            try: st.image(s['avatar_image'], width=60)
            except: st.write(s['avatar_emoji'])
        else:
            st.markdown(f"<h1>{s['avatar_emoji']}</h1>", unsafe_allow_html=True)
    with c2:
        st.subheader(s['name'])
        st.caption(f"📍 {p['location']} | {s['current_weather']}") # 天氣回來了

    st.divider()

    # 顯示歷史
    for msg in st.session_state.chat_history:
        role = msg["role"]
        with st.chat_message(role):
            st.write(msg["content"])

    # 輸入區
    if user_in := st.chat_input("想問咩？"):
        st.session_state.chat_history.append({"role": "user", "content": user_in})
        with st.chat_message("user"):
            st.write(user_in)
        
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                sys_msg = (
                    f"你是{s['name']}。{s['persona']}\n"
                    f"用戶：{p['name']}, {p['location']} ({s['current_weather']})。\n"
                    f"用戶問：{user_in}\n"
                    f"請從衣櫃給建議 (如有)。"
                )
                inputs = [sys_msg]
                for i, item in enumerate(st.session_state.wardrobe[:5]):
                    try:
                        # 傳送詳細尺碼給 AI
                        size_str = f"L:{item['size_data']['length']} W:{item['size_data']['width']}"
                        inputs.append(f"單品#{i+1} ({item['category']}) 尺碼:{size_str}")
                        inputs.append(compress_image(item['image']))
                    except: pass
                
                reply = ask_gemini(inputs)
                st.write(reply) 
                st.session_state.chat_history.append({"role": "assistant", "content": reply})

# --- 7. 主介面 (還原側邊欄) ---
with st.sidebar:
    s = st.session_state.stylist_profile
    p = st.session_state.user_profile
    
    # 造型師卡片 Container
    st.markdown('<div class="stylist-container">', unsafe_allow_html=True)
    
    # 頭像
    st.markdown('<div class="avatar-circle">', unsafe_allow_html=True)
    if s['avatar_type'] == 'image' and s['avatar_image']:
        try: st.image(s['avatar_image'], use_column_width=True)
        except: st.markdown(s['avatar_emoji'])
    else:
        st.markdown(s['avatar_emoji'])
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown(f"<h3>{s['name']}</h3>", unsafe_allow_html=True)
    
    c_btn = st.columns([1,2,1])
    with c_btn[1]:
        if st.button("⚙️ 設定"): settings_dialog()
    
    st.caption(f"早安 {p['name']} | {s['current_weather']}") # 顯示天氣
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    if st.button("💬 開始對話", type="primary", use_container_width=True):
        chat_dialog()

    st.divider()

    # 加入衣櫃
    st.subheader("📥 加入衣櫃")
    c1, c2 = st.columns(2)
    cat = c1.selectbox("分類", ["上衣", "下身", "連身裙", "外套", "鞋", "袋"])
    sea = c2.selectbox("季節", ["四季", "春夏", "秋冬"])
    files = st.file_uploader("拖曳圖片", accept_multiple_files=True, key=f"up_{st.session_state.uploader_key}")
    if files: process_upload(files, cat, sea)
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🗑️ 清空"):
        st.session_state.wardrobe = []
        st.rerun()

# --- 8. 主衣櫃顯示 ---
st.subheader("🧥 我的衣櫃")
if not st.session_state.wardrobe:
    st.info("👈 左側加入衣物，然後點「開始對話」！")
else:
    cats = list(set([x['category'] for x in st.session_state.wardrobe]))
    sel = st.multiselect("🔍", cats, placeholder="篩選分類")
    items = [x for x in st.session_state.wardrobe if x['category'] in sel] if sel else st.session_state.wardrobe
    
    cols = st.columns(5)
    for i, item in enumerate(items):
        with cols[i % 5]:
            st.image(item['image'])
            if st.button("✏️", key=f"e_{item['id']}", use_container_width=True):
                edit_item_dialog(item)
