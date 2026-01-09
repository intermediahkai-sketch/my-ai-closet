import streamlit as st
import base64
import io
import uuid
import time
import requests
import json
import re
import random
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
    
    section[data-testid="stSidebar"] div.block-container {
        padding-top: 2rem;
    }
    /* 讓 Pills 排列更整齊 */
    div[data-testid="stPills"] {
        gap: 8px;
        flex-wrap: wrap;
        margin-bottom: 10px;
    }
    header {visibility: hidden;}
    
    /* 修改：試身室樣式 - 背景透明，移除白框與陰影 */
    .fitting-room-box {
        background-color: transparent; /* 改為透明 */
        border: none;
        padding: 10px;
        margin-top: 0px; /* 稍微縮減上方間距 */
        text-align: center;
        /* box-shadow: 0 2px 5px rgba(0,0,0,0.05); 已移除陰影 */
    }
    
    /* 調整按鈕樣式，讓設定齒輪緊湊一點 */
    button[key="setting_btn"] {
        padding: 0px 10px;
    }
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

# --- 試身室狀態管理 ---
if 'show_fitting_room' not in st.session_state:
    st.session_state.show_fitting_room = False 
if 'wearing_top' not in st.session_state:
    st.session_state.wearing_top = None 
if 'wearing_bottom' not in st.session_state:
    st.session_state.wearing_bottom = None 

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
        "name": "Kelly", 
        "avatar_image": None, 
        "persona": "一位貼心的專業形象顧問，語氣親切、專業。",
        "last_preset": "專業顧問", 
        "weather_cache": "查詢中..."
    }

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

# --- 5. 核心函式 ---

def get_real_weather(city, user_name="User"):
    coords = {
        "香港": {"lat": 22.3193, "lon": 114.1694},
        "台北": {"lat": 25.0330, "lon": 121.5654},
        "東京": {"lat": 35.6762, "lon": 139.6503},
        "首爾": {"lat": 37.5665, "lon": 126.9780},
        "倫敦": {"lat": 51.5074, "lon": -0.1278}
    }
    
    default_msg = f"Hi {user_name}, {city} 天氣不錯！"
    
    if city not in coords: return default_msg
    try:
        lat, lon = coords[city]["lat"], coords[city]["lon"]
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,weather_code&timezone=auto"
        res = requests.get(url, timeout=5)
        data = res.json()
        
        temp = data['current']['temperature_2m']
        wcode = data['current']['weather_code']
        
        condition_msg = "天氣不錯"
        if wcode <= 3:
            condition_msg = "天晴，心情都要靚靚！"
        elif wcode in [45, 48]:
            condition_msg = "有霧，出門小心。"
        elif wcode in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
            condition_msg = "出面落緊雨，記得帶遮呀！"
        elif wcode >= 95:
            condition_msg = "有雷暴，留在室內安全啲！"
        
        return f"Hi {user_name}, {city}依家 {temp}°C, {condition_msg}"
        
    except:
        return f"Hi {user_name}, {city} 暫時無法連線。"

def encode_image(image):
    buffered = io.BytesIO()
    image = image.convert('RGB')
    image.thumbnail((512, 512))
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def ask_openrouter_direct(text_prompt, image_list=None):
    if not OPENROUTER_API_KEY:
        return generate_mock_response()
        
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY.strip()}",
        "HTTP-Referer": "https://localhost:8501",
        "X-Title": "My Stylist App",
        "Content-Type": "application/json"
    }
    content_parts = [{"type": "text", "text": text_prompt}]
    
    if image_list:
        selected_imgs = image_list[:5] 
        for img in selected_imgs:
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
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=15)
            if response.status_code == 200:
                data = response.json()
                if 'choices' in data and len(data['choices']) > 0:
                    content = data['choices'][0]['message']['content']
                    if content: return content
            time.sleep(1)
        except:
            pass
            
    return generate_mock_response()

# --- AI 備用邏輯 ---
def generate_mock_response():
    wardrobe = st.session_state.wardrobe
    if not wardrobe:
        return "⚠️ (AI 忙線中) 你的衣櫃還是空的，快去加點衣服吧！"
    
    tops_indices = [i for i, x in enumerate(wardrobe) if x['category'] in ["上衣", "外套", "連身裙"]]
    bottoms_indices = [i for i, x in enumerate(wardrobe) if x['category'] in ["下身", "褲", "裙"]]

    if not tops_indices or not bottoms_indices:
        pick_idx = random.choice(range(len(wardrobe)))
        return f"⚠️ (AI 連線繁忙) 建議你穿上 [ID: {pick_idx}]，但我找不到完整的上衣+褲子搭配，記得去補貨喔！"

    t_idx = random.choice(tops_indices)
    b_idx = random.choice(bottoms_indices)
    
    ids_str = f"[ID: {t_idx}] + [ID: {b_idx}]"
    
    msgs = [
        f"⚠️ (AI 連線繁忙，切換至備用線路)\n\n這種天氣，我覺得 {ids_str} 是絕配！試試看？",
        f"⚠️ (AI 正在休息)\n\n不用想太多，直接穿 {ids_str} 出門吧，簡單又好看。",
        f"⚠️ (系統忙碌中)\n\n幫你挑了 {ids_str}，這一套絕對安全不出錯。"
    ]
    return random.choice(msgs)

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
        uid = item['id']
        current_cat = item.get('category', '上衣')
        if current_cat not in CATEGORIES: current_cat = CATEGORIES[0]
        
        new_cat = st.pills("分類", CATEGORIES, default=current_cat, key=f"cat_{uid}", selection_mode="single")
        if new_cat: item['category'] = new_cat
        else: new_cat = current_cat 
        
        current_season = item.get('season', '四季')
        if current_season not in SEASONS: current_season = SEASONS[0]
        
        new_season = st.pills("季節", SEASONS, default=current_season, key=f"sea_{uid}", selection_mode="single")
        if new_season: item['season'] = new_season
        
        st.divider()
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
    
    # Update weather if location changes
    if new_loc != p['location']:
        p['location'] = new_loc
        st.session_state.stylist_profile['weather_cache'] = get_real_weather(new_loc, p['name'])
    
    p['name'] = st.text_input("暱稱", value=p['name'])
    st.subheader("📏 身體密碼")
    c1, c2, c3 = st.columns(3)
    p['height'] = c1.number_input("身高(cm)", value=p['height'])
    p['weight'] = c2.number_input("體重(kg)", value=p['weight'])
    p['gender'] = c3.selectbox("性別", ["女", "男"], index=0)
    st.caption("三圍 (吋/cm)")
    c4, c5, c6 = st.columns(3)
    p['measurements']['bust'] = c4.number_input("胸", value=p['measurements']['bust'])
    p['measurements']['waist'] = c5.number_input("腰", value=p['measurements']['waist'])
    p['measurements']['hips'] = c6.number_input("臀", value=p['measurements']['hips'])
    st.divider()
    st.subheader("✨ Stylist 設定")
    s = st.session_state.stylist_profile
    s['name'] = st.text_input("Stylist 名字", value=s['name'])
    f = st.file_uploader("更換頭像 (長方形效果最佳)", type=['png','jpg'])
    if f: s['avatar_image'] = f.getvalue()
    
    presets = {
        "專業顧問": "一位貼心的專業形象顧問，語氣親切、專業。",
        "毒舌專家": "眼光極高的時尚主編，說話尖酸刻薄但一針見血。",
        "溫柔男友": "充滿愛意的男友，不管穿什麼都稱讚。"
    }
    current_preset = None
    for k, v in presets.items():
        if v == s['persona']:
            current_preset = k
            break
            
    try:
        idx = list(presets.keys()).index(current_preset) if current_preset else 0
    except:
        idx = 0

    sel_p = st.selectbox("人設風格", list(presets.keys()), index=idx, key="style_select")
    
    if sel_p != s.get('last_preset'):
        s['persona'] = presets[sel_p]
        s['last_preset'] = sel_p
        st.rerun() 
    
    s['persona'] = st.text_area("指令 (可手動修改)", value=s['persona'])
    
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
        st.caption(s['weather_cache'])
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
                sys_msg = (f"你是{s['name']}。{s['persona']}\n用戶：{p['name']} ({body_info}), {s['weather_cache']}。\n用戶問：{user_in}\n**規則：建議單品時，必須明確標註 [ID: 數字]。**\n衣櫃清單：")
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

# 確保天氣有 User 名字的客製化
if st.session_state.stylist_profile['weather_cache'] == "查詢中..." or "Hi User" in st.session_state.stylist_profile['weather_cache']:
    loc = st.session_state.user_profile['location']
    name = st.session_state.user_profile['name']
    st.session_state.stylist_profile['weather_cache'] = get_real_weather(loc, name)

# --- 側邊欄 ---
with st.sidebar:
    s = st.session_state.stylist_profile
    p = st.session_state.user_profile
    
    # 頭像
    if s['avatar_image']: st.image(s['avatar_image'], use_column_width=True)
    else: st.image("https://cdn-icons-png.flaticon.com/512/6833/6833605.png", width=100)
    
    # 標題 + 齒輪
    c_title, c_gear = st.columns([5, 1])
    with c_title:
        role = s.get('last_preset', '專屬顧問')
        st.markdown(f"### 你的{role} {s['name']}") 
    with c_gear:
        if st.button("⚙️", key="setting_btn"): 
            settings_dialog()
            
    st.caption(s['weather_cache']) 
    
    # 開始對話按鈕
    if st.button("💬 開始對話", type="primary", use_container_width=True): chat_dialog()
    
    # 試身室按鈕 (已修改名稱)
    if st.button("🎽 試身室", use_container_width=True):
        st.session_state.show_fitting_room = not st.session_state.show_fitting_room
    
    # 試身室面板 (已移除白框背景)
    if st.session_state.show_fitting_room:
        st.markdown('<div class="fitting-room-box">', unsafe_allow_html=True)
        st.caption("目前搭配")
        
        # 上衣區
        if st.session_state.wearing_top is not None and st.session_state.wearing_top < len(st.session_state.wardrobe):
            st.image(st.session_state.wardrobe[st.session_state.wearing_top]['image'])
        else:
            st.markdown("Waiting<br>Top", unsafe_allow_html=True)

        # 褲子區
        if st.session_state.wearing_bottom is not None and st.session_state.wearing_bottom < len(st.session_state.wardrobe):
            st.image(st.session_state.wardrobe[st.session_state.wearing_bottom]['image'])
        else:
            st.markdown("Waiting<br>Bottom", unsafe_allow_html=True)
                
        st.markdown('</div>', unsafe_allow_html=True)

    st.divider()
    st.subheader("📥 加入衣櫃")
    
    cat = st.pills("分類", CATEGORIES, default=CATEGORIES[0], selection_mode="single")
    sea = st.pills("季節", SEASONS, default=SEASONS[0], selection_mode="single")
    
    files = st.file_uploader("圖片", accept_multiple_files=True, key=f"up_{st.session_state.uploader_key}")
    if files: process_upload(files, cat or CATEGORIES[0], sea or SEASONS[0])
    
    if st.button("🗑️ 清空"):
        st.session_state.wardrobe = []
        st.session_state.wearing_top = None
        st.session_state.wearing_bottom = None
        st.rerun()

# 主畫面
st.subheader("🧥 我的衣櫃")

season_filter = st.pills("季節篩選", ["全部", "春夏", "秋冬"], default="全部", selection_mode="single")
if not season_filter: season_filter = "全部"

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
    if cats_available:
        st.caption("🔍 篩選分類 (可多選)")
        options = ["全部"] + cats_available
        sel = st.pills("Category Filter", options, selection_mode="multi", label_visibility="collapsed")
    else:
        sel = []

    if not sel or "全部" in sel:
        final_display = filtered_items
    else:
        final_display = [x for x in filtered_items if x['category'] in sel]
    
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
                if st.button("👕", key=f"t_{item['id']}"):
                    if item['category'] in ["上衣", "外套", "連身裙"]:
                        st.session_state.wearing_top = real_id
                        st.toast(f"上身已換: ID {real_id}", icon="👚")
                    else:
                        st.session_state.wearing_bottom = real_id
                        st.toast(f"下身已換: ID {real_id}", icon="👖")
                    st.rerun()
