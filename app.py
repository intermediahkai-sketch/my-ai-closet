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

# 更新：預設名字改為 "你的專屬 Stylist"
if 'stylist_profile' not in st.session_state:
    st.session_state.stylist_profile = {
        "name": "你的專屬 Stylist", # Updated Name
        "avatar_type": "emoji",
        "avatar_emoji": "✨",       # Updated Default Emoji
        "avatar_image": None,
        "persona": "一位貼心的專業形象顧問，語氣親切、專業，會根據你的身型提供最適合的建議。",
        "current_weather": "晴朗 24°C"
    }

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

# --- 3. 頁面設定 ---
st.set_page_config(page_title="My Stylist", page_icon="👗", layout="wide")

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
    button[kind="secondary"] {
        border: 1px solid #e0e0e0;
    }
    </style>
""", unsafe_allow_html=True)

# --- 4. 核心函數 ---

def compress_image(image):
    image = image.convert('RGB')
    image.thumbnail((400, 400)) # 進一步縮小以確保穩定
    return image

def safe_ask_ai(inputs):
    """安全 AI 連線：失敗時回傳預設訊息，防止 Crash"""
    models = ["gemini-1.5-flash", "gemini-pro"]
    for model_name in models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(inputs)
            return response.text
        except:
            continue
    return "⚠️ 連線有點不穩，但我建議你可以試試用「上寬下窄」的搭配法則！(AI 暫時離線)"

def process_upload(files, category, season):
    if not files: return
    progress = st.progress(0)
    for i, file in enumerate(files):
        try:
            img = Image.open(file)
            # 嘗試去背，如果失敗就用原圖 (防止記憶體爆導致 Crash)
            try:
                b = io.BytesIO()
                img.save(b, format='PNG')
                res = remove_bg(b.getvalue())
                final_img = Image.open(io.BytesIO(res))
            except:
                final_img = img
            
            st.session_state.wardrobe.append({
                'id': str(uuid.uuid4()), 'image': final_img,
                'category': category, 'season': season,
                'size_data': {'length': '', 'width': '', 'waist': ''}
            })
        except: pass
        progress.progress((i+1)/len(files))
    
    st.session_state.uploader_key += 1
    st.toast(f"已加入 {len(files)} 件", icon="✅")
    time.sleep(1)
    st.rerun()

# --- 5. Dialogs ---

@st.dialog("✏️ 編輯")
def edit_item_dialog(item):
    c1, c2 = st.columns([1, 1])
    with c1: st.image(item['image'])
    with c2:
        cats = ["上衣", "下身褲裝", "下身裙裝", "連身裙", "外套", "鞋履", "配件"]
        idx = cats.index(item['category']) if item['category'] in cats else 0
        item['category'] = st.selectbox("分類", cats, index=idx)
        
        # 簡單尺碼
        item['size_data']['width'] = st.text_input("尺碼/備註", value=item['size_data']['width'])
        
        if st.button("🗑️ 刪除", type="primary"):
            st.session_state.wardrobe.remove(item)
            st.rerun()

@st.dialog("⚙️ 設定")
def settings_dialog():
    st.subheader("👤 用戶")
    p = st.session_state.user_profile
    p['name'] = st.text_input("暱稱", value=p['name'])
    p['location'] = st.selectbox("地區", ["香港", "台北", "東京", "首爾", "倫敦"], index=0)
    
    st.subheader("✨ Stylist 設定")
    s = st.session_state.stylist_profile
    s['name'] = st.text_input("Stylist 名字", value=s['name']) # 預設已經係 "你的專屬 Stylist"
    
    # 簡化頭像設定
    use_img = st.checkbox("用圖片頭像")
    if use_img:
        s['avatar_type'] = 'image'
        f = st.file_uploader("上傳頭像", type=['png','jpg'])
        if f: s['avatar_image'] = f.getvalue()
    else:
        s['avatar_type'] = 'emoji'
        s['avatar_emoji'] = st.text_input("Emoji", value=s['avatar_emoji'])

    # 人設
    presets = {
        "專業顧問": "一位貼心的專業形象顧問，語氣親切、專業。",
        "毒舌專家": "眼光極高的時尚主編，說話尖酸刻薄但一針見血。",
        "溫柔男友": "充滿愛意的男友，不管穿什麼都稱讚。",
        "霸道總裁": "強勢但寵溺的總裁，不准穿太露。"
    }
    k = st.selectbox("人設風格", list(presets.keys()))
    if st.button("套用人設"):
        s['persona'] = presets[k]
        st.success("已更新！")
    
    s['persona'] = st.text_area("指令", value=s['persona'])

    if st.button("完成", type="primary"):
        st.rerun()

# --- 6. 聊天功能 (防閃退版) ---
@st.dialog("💬 與 Stylist 對話", width="large")
def chat_dialog():
    s = st.session_state.stylist_profile
    p = st.session_state.user_profile
    
    # Header
    c1, c2 = st.columns([1, 5])
    with c1:
        if s['avatar_type'] == 'image' and s['avatar_image']:
            try: st.image(s['avatar_image'])
            except: st.write(s['avatar_emoji'])
        else:
            st.markdown(f"<h1>{s['avatar_emoji']}</h1>", unsafe_allow_html=True)
    with c2:
        st.subheader(s['name'])
        st.caption(f"📍 {p['location']}")

    st.divider()

    # 顯示歷史
    for msg in st.session_state.chat_history:
        role = msg["role"]
        with st.chat_message(role):
            st.write(msg["content"])

    # 輸入區 (關鍵修改：避免 Rerun 導致彈走)
    if user_in := st.chat_input("想問咩？"):
        # 1. 直接顯示用戶訊息
        st.session_state.chat_history.append({"role": "user", "content": user_in})
        with st.chat_message("user"):
            st.write(user_in)
        
        # 2. 顯示 AI 思考中...
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                sys_msg = (
                    f"你是{s['name']}。{s['persona']}\n"
                    f"用戶：{p['name']}, {p['location']}。\n"
                    f"用戶問：{user_in}\n"
                    f"請從衣櫃給建議 (如有)。"
                )
                
                inputs = [sys_msg]
                # 只傳前 5 件衫，確保極速
                for i, item in enumerate(st.session_state.wardrobe[:5]):
                    try:
                        inputs.append(f"單品#{i+1} ({item['category']})")
                        inputs.append(compress_image(item['image']))
                    except: pass
                
                # 獲取回應
                reply = safe_ask_ai(inputs)
                
                # 直接寫出回應 (不 Rerun，保持視窗穩定)
                st.write(reply)
                
                # 存入歷史
                st.session_state.chat_history.append({"role": "assistant", "content": reply})

# --- 7. 主介面 ---
with st.sidebar:
    s = st.session_state.stylist_profile
    
    with st.container(border=True):
        if s['avatar_type'] == 'image' and s['avatar_image']:
            try: st.image(s['avatar_image'], use_column_width=True)
            except: st.header(s['avatar_emoji'])
        else:
            st.markdown(f"<h1 style='text-align:center'>{s['avatar_emoji']}</h1>", unsafe_allow_html=True)
            
        st.markdown(f"<h3 style='text-align:center'>{s['name']}</h3>", unsafe_allow_html=True)
        
        c1, c2 = st.columns(2)
        if c1.button("⚙️ 設定"): settings_dialog()
        if c2.button("💬 對話", type="primary"): chat_dialog()

    st.subheader("📥 加入衣櫃")
    cat = st.selectbox("分類", ["上衣", "下身", "連身裙", "外套", "鞋", "袋"])
    season = st.selectbox("季節", ["四季", "春夏", "秋冬"])
    files = st.file_uploader("拖曳圖片", accept_multiple_files=True, key=f"up_{st.session_state.uploader_key}")
    if files: process_upload(files, cat, season)
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🗑️ 清空"):
        st.session_state.wardrobe = []
        st.rerun()

st.subheader("🧥 我的衣櫃")
if not st.session_state.wardrobe:
    st.info("👈 請先在左側加入衣物")
else:
    cols = st.columns(5)
    for i, item in enumerate(st.session_state.wardrobe):
        with cols[i % 5]:
            st.image(item['image'])
            if st.button("✏️", key=f"e_{item['id']}", use_container_width=True):
                edit_item_dialog(item)
