import streamlit as st
import base64
import io
import uuid
import time
import requests
import json
import re
from PIL import Image

# --- 1. 頁面設定 ---
st.set_page_config(page_title="My Stylist", page_icon="👗", layout="wide")

# --- 2. CSS ---
st.markdown("""
    <style>
    div[data-testid="stImage"] {
        background-color: transparent;
        border-radius: 10px;
        padding: 5px;
        display: flex;
        justify-content: center;
        align-items: center;
    }
    div[data-testid="stImage"] img {
        height: 220px !important; 
        object-fit: cover !important;
        border-radius: 10px;
    }
    .stylist-container {
        background-color: #f0f2f6;
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        border: 1px solid #e0e0e0;
        margin-bottom: 20px;
    }
    section[data-testid="stSidebar"] div.block-container {
        padding-top: 2rem;
    }
    header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# --- 3. 常數與 Key ---
CATEGORIES = ["上衣", "下身", "連身裙", "外套", "鞋", "配件"]
SEASONS = ["四季", "春夏", "秋冬"]

try:
    OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
except:
    OPENROUTER_API_KEY = ""

# --- 4. 初始化 Session State ---
if 'wardrobe' not in st.session_state:
    st.session_state.wardrobe = [] 

if 'user_profile' not in st.session_state:
    st.session_state.user_profile = {
        "name": "User", 
        "location": "香港",
        "gender": "女",
        "height": 160,
        "weight": 50,
        "measurements": {"bust": 32, "waist": 24, "hips": 34},
        "style_pref": "簡約休閒"
    }

if 'stylist_profile' not in st.session_state:
    st.session_state.stylist_profile = {
        "name": "你的專屬 Stylist",
        "avatar_image": None, 
        "persona": "一位貼心的專業形象顧問，語氣親切、專業。",
        "last_preset": None,
        "weather_cache": "查詢中..."
    }

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

# --- 5. 核心函式 ---

def get_real_weather(city):
    coords = {
        "香港": {"lat": 22.3193, "lon": 114.1694},
        "台北": {"lat": 25.0330, "lon": 121.5654},
        "東京": {"lat": 35.6762, "lon": 139.6503},
        "首爾": {"lat": 37.5665, "lon": 126.9780},
        "倫敦": {"lat": 51.5074, "lon": -0.1278}
    }
    if city not in coords: return "未知天氣"
    try:
        lat, lon = coords[city]["lat"], coords[city]["lon"]
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code&timezone=auto"
        res = requests.get(url, timeout=5)
        data = res.json()
        temp = data['current']['temperature_2m']
        return f"現時 {temp}°C"
    except:
        return "24°C"

def encode_image(image):
    buffered = io.BytesIO()
    image = image.convert('RGB')
    image.thumbnail((512, 512))
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def ask_openrouter_direct(text_prompt, image_list=None):
    if not OPENROUTER_API_KEY:
        return "⚠️ 請先設定 API Key 才能使用 AI 功能。"
        
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY.strip()}",
        "HTTP-Referer": "https://localhost:8501",
        "X-Title": "My Stylist App",
        "Content-Type": "application/json"
    }
    content_parts = [{"type": "text", "text": text_prompt}]
    if image_list:
        for img in image_list:
            b64 = encode_image(img)
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
            })
    
    models_to_try = [
        "google/gemini-2.0-flash-exp:free",
        "google/gemini-1.5-flash:free",
        "meta-llama/llama-3.2-11b-vision-instruct:free",
    ]
    
    for model in models_to_try:
        payload = {
            "model": model, 
            "messages": [{"role": "user", "content": content_parts}],
            "temperature": 0.7
        }
        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=25)
            if response.status_code == 200:
                data = response.json()
                if 'choices' in data and len(data['choices']) > 0:
                    content = data['choices'][0]['message']['content']
                    if content: return content
            time.sleep(1)
        except:
            pass
            
    return "⚠️ 線路繁忙 (API Busy)，AI 暫時無法回應，請稍後再試。"

def extract_ids_from_text(text):
    ids = re.findall(r"ID[:：]\s*(\d+)", text, re.IGNORECASE)
    return [int(id_str) for id_str in ids]

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
                'size_data': {'length': '', 'width': '', 'waist': ''}
            })
        except: pass
    st.session_state.uploader_key += 1
    st.toast(f"✅ 已加入 {len(files)} 件", icon="🧥")
    time.sleep(0.5)
    st.rerun()

# --- 6. Dialogs (編輯 & 設定) ---

@st.dialog("✏️ 編輯單品")
def edit_item_dialog(item, real_id):
    st.caption(f"正在編輯 Item [ID: {real_id}]")
    c1, c2 = st.columns([1, 1])
    with c1: st.image(item['image'])
    with c2:
        # 使用 unique key 防止不同衣服混亂
        uid = item['id']
        
        current_cat = item.get('category', '上衣')
        if current_cat not in CATEGORIES: current_cat = CATEGORIES[0]
        
        new_cat = st.selectbox("分類", CATEGORIES, index=CATEGORIES.index(current_cat), key=f"cat_{uid}")
        item['category'] = new_cat
        
        current_season = item.get('season', '四季')
        if current_season not in SEASONS: current_season = SEASONS[0]
        item['season'] = st.selectbox("季節", SEASONS, index=SEASONS.index(current_season), key=f"sea_{uid}")
        
        st.caption("詳細尺碼")
        if 'size_data' not in item: item['size_data'] = {}

        if any(x in item['category'] for x in ["上衣", "外套", "連身裙"]):
            item['size_data']['length'] = st.text_input("衣長 (cm)", value=item['size_data'].get('length',''), key=f"len_{uid}")
            item['size_data']['width'] = st.text_input("胸寬 (cm)", value=item['size_data'].get('width',''), key=f"wid_{uid}")
        elif any(x in item['category'] for x in ["下身", "褲", "裙"]):
            item['size_data']['length'] = st.text_input("褲/裙長 (cm)", value=item['size_data'].get('length',''), key=f"len_{uid}")
            item['size_data']['waist'] = st.text_input("腰圍 (吋/cm)", value=item['size_data'].get('waist',''), key=f"wai_{uid}")
        else:
            item['size_data']['width'] = st.text_input("備註", value=item['size_data'].get('width',''), key=f"rem_{uid}")
        
        st.divider()
        if st.button("🗑️ 刪除", type="primary", key=f"del_{uid}"):
            st.session_state.wardrobe.remove(item)
            st.rerun()

@st.dialog("⚙️ 設定")
def settings_dialog():
    st.subheader("👤 用戶資料")
    p = st.session_state.user_profile
    new_loc = st.selectbox("地區", ["香港", "台北", "東京", "首爾", "倫敦"], index=0)
    if new_loc != p['location']:
        p['location'] = new_loc
        st.session_state.stylist_profile['weather_cache'] = get_real_weather(new_loc)
    p['name'] = st.text_input("暱稱", value=p['name'])
    st.divider()
    s = st.session_state.stylist_profile
    s['name'] = st.text_input("Stylist 名字", value=s['name'])
    if st.button("完成", type="primary"): st.rerun()

@st.dialog("💬 與 Stylist 對話", width="large")
def chat_dialog():
    s = st.session_state.stylist_profile
    p = st.session_state.user_profile
    c1, c2 = st.columns([1, 4])
    with c1:
        if s['avatar_image']: st.image(s['avatar_image'])
        else: st.image("https://cdn-icons-png.flaticon.com/512/6833/6833605.png", width=60)
    with c2:
        st.subheader(s['name'])
        st.caption(f"📍 {p['location']} | {s['weather_cache']}")
    st.divider()
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if "related_ids" in msg and msg["related_ids"]:
                cols = st.columns(len(msg["related_ids"]))
                for idx, item_id in enumerate(msg["related_ids"]):
                    if 0 <= item_id < len(st.session_state.wardrobe):
                        with cols[idx]:
                            item = st.session_state.wardrobe[item_id]
                            st.image(item['image'], caption=f"ID: {item_id}")
    if user_in := st.chat_input("想問咩？"):
        st.session_state.chat_history.append({"role": "user", "content": user_in})
        with st.chat_message("user"): st.write(user_in)
        with st.chat_message("assistant"):
            with st.spinner("Stylist 正在思考..."):
                m = p['measurements']
                body_info = f"{p['height']}cm/{p['weight']}kg"
                sys_msg = (f"你是{s['name']}。{s['persona']}\n用戶：{p['name']} ({body_info}), {p['location']} ({s['weather_cache']})。\n用戶問：{user_in}\n**規則：建議單品時，必須明確標註 [ID: 數字]。**\n衣櫃清單：")
                img_list = []
                for i, item in enumerate(st.session_state.wardrobe):
                    img_list.append(item['image'])
                    sys_msg += f"\n- [ID: {i}] {item['category']}"
                reply = ask_openrouter_direct(sys_msg, img_list)
                found_ids = extract_ids_from_text(reply)
                st.write(reply)
                valid_ids = []
                if found_ids:
                    st.caption("✨ 建議搭配：")
                    cols = st.columns(len(found_ids))
                    for idx, item_id in enumerate(found_ids):
                        if 0 <= item_id < len(st.session_state.wardrobe):
                            valid_ids.append(item_id)
                            with cols[idx]:
                                item = st.session_state.wardrobe[item_id]
                                st.image(item['image'], caption=f"ID: {item_id}")
                st.session_state.chat_history.append({"role": "assistant", "content": reply, "related_ids": valid_ids})

# --- 7. 主程式 ---

if st.session_state.stylist_profile['weather_cache'] == "查詢中...":
    loc = st.session_state.user_profile['location']
    st.session_state.stylist_profile['weather_cache'] = get_real_weather(loc)

with st.sidebar:
    s = st.session_state.stylist_profile
    p = st.session_state.user_profile
    st.markdown('<div class="stylist-container">', unsafe_allow_html=True)
    if s['avatar_image']: st.image(s['avatar_image'], use_column_width=True)
    else: st.image("https://cdn-icons-png.flaticon.com/512/6833/6833605.png", width=100)
    
    c_name, c_gear = st.columns([4, 1])
    with c_name: st.markdown(f"### {s['name']}")
    with c_gear: 
        if st.button("⚙️"): settings_dialog()
            
    st.caption(f"{p['location']} | {s['weather_cache']}")
    st.markdown('</div>', unsafe_allow_html=True)
    if st.button("💬 開始對話", type="primary", use_container_width=True): chat_dialog()

    # --- 試身室 (Final Fix) ---
    with st.expander("👗 試身室 (Mix & Match)", expanded=True):
        # 1. 在繪製選單前，檢查是否有按鈕發出的更新請求
        if 'force_update_top' in st.session_state:
            st.session_state['sb_top'] = st.session_state.pop('force_update_top')
        if 'force_update_bot' in st.session_state:
            st.session_state['sb_bot'] = st.session_state.pop('force_update_bot')

        if not st.session_state.wardrobe:
            st.caption("衣櫃是空的")
        else:
            tops = [i for i, x in enumerate(st.session_state.wardrobe) if x['category'] in ["上衣","外套","連身裙"]]
            bots = [i for i, x in enumerate(st.session_state.wardrobe) if x['category'] in ["下身","褲","裙"]]
            if not tops: tops = []
            if not bots: bots = []
            
            top_options = tops + [x for x in range(len(st.session_state.wardrobe)) if x not in tops and x not in bots]
            bot_options = bots + [x for x in range(len(st.session_state.wardrobe)) if x not in tops and x not in bots]

            c1, c2 = st.columns(2)
            
            t = c1.selectbox("上", top_options, format_func=lambda x: f"ID:{x}", key="sb_top")
            if t is not None: st.image(st.session_state.wardrobe[t]['image'])
            
            b = c2.selectbox("下", bot_options, format_func=lambda x: f"ID:{x}", key="sb_bot")
            if b is not None: st.image(st.session_state.wardrobe[b]['image'])

    st.divider()
    st.subheader("📥 加入衣櫃")
    c1, c2 = st.columns(2)
    cat = c1.selectbox("分類", CATEGORIES) 
    sea = c2.selectbox("季節", SEASONS)
    files = st.file_uploader("圖片", accept_multiple_files=True, key=f"up_{st.session_state.uploader_key}")
    if files: process_upload(files, cat, sea)
    if st.button("🗑️ 清空"):
        st.session_state.wardrobe = []
        st.rerun()

# 主畫面
st.subheader("🧥 我的衣櫃")
season_filter = st.radio("季節篩選", ["全部", "春夏", "秋冬"], index=0, horizontal=True, label_visibility="collapsed")

if not st.session_state.wardrobe:
    st.info("👈 左側加入衣物，然後點「開始對話」！")
else:
    filtered_items = []
    for item in st.session_state.wardrobe:
        iseason = item.get('season', '四季')
        if season_filter == "全部": filtered_items.append(item)
        elif season_filter == "春夏" and iseason in ["四季", "春夏"]: filtered_items.append(item)
        elif season_filter == "秋冬" and iseason in ["四季", "秋冬"]: filtered_items.append(item)

    cats_available = list(set([x['category'] for x in filtered_items]))
    sel = st.multiselect("🔍", cats_available, placeholder="篩選分類")
    final_display = [x for x in filtered_items if x['category'] in sel] if sel else filtered_items
    
    cols = st.columns(5)
    for i, item in enumerate(final_display):
        with cols[i % 5]:
            real_id = st.session_state.wardrobe.index(item)
            st.image(item['image'], caption=f"ID: {real_id}")
            
            c_edit, c_try = st.columns([1, 1])
            with c_edit:
                if st.button("✏️", key=f"e_{item['id']}"):
                     edit_item_dialog(item, real_id)
            
            with c_try:
                # --- 試身按鈕 修復版 ---
                if st.button("👕", key=f"t_{item['id']}"):
                    if item['category'] in ["上衣", "外套", "連身裙"]:
                        # 不要直接修改 sb_top，改為設定「更新指令」
                        st.session_state['force_update_top'] = real_id
                    else:
                        st.session_state['force_update_bot'] = real_id
                    
                    st.toast(f"已穿上 ID:{real_id}", icon="✅")
                    st.rerun() # 重新載入，讓側邊欄執行指令
