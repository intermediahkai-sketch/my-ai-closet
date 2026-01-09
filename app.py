import streamlit as st
import base64
import io
import uuid
import time
import requests
import json
import re
from PIL import Image
from datetime import datetime

# --- 1. 設定 API Key ---
try:
    OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
except:
    st.error("⚠️ 找不到 API Key！請去 Streamlit 網頁版 -> Settings -> Secrets 貼上 Key。")
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
        "name": "Stylist",
        "avatar_type": "emoji",
        "avatar_emoji": "✨",
        "avatar_image": None,
        "persona": "一位貼心的專業形象顧問，語氣親切、專業。",
        "weather_cache": "查詢中..."
    }

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

# --- 3. 頁面設定與 CSS ---
st.set_page_config(page_title="My Stylist", page_icon="👗", layout="wide")

st.markdown("""
    <style>
    /* 圖片樣式 */
    div[data-testid="stImage"] {
        background-color: #f9f9f9;
        border-radius: 8px;
        padding: 5px;
        display: flex;
        justify-content: center;
        align-items: center;
    }
    div[data-testid="stImage"] img {
        height: 180px !important; 
        object-fit: contain !important;
    }
    
    /* 側邊欄風格 */
    .stylist-container {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 15px;
        text-align: center;
        border: 1px solid #e0e0e0;
        margin-bottom: 20px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    
    /* 方形頭像 */
    .avatar-box {
        width: 100px;
        height: 100px;
        margin: 0 auto 10px auto;
        border: 2px solid #333;
        background-color: white;
        display: flex;
        justify-content: center;
        align-items: center;
        overflow: hidden;
        font-size: 50px;
        border-radius: 12px; /* 輕微圓角 */
    }
    .avatar-box img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }

    /* 試身室樣式 */
    .fitting-room-item {
        border: 1px dashed #ccc;
        padding: 10px;
        margin-bottom: 10px;
        text-align: center;
        background: white;
    }
    </style>
""", unsafe_allow_html=True)

# --- 4. 核心功能 (API & Weather) ---

def get_real_weather(city):
    """使用 Open-Meteo 免費 API 獲取天氣"""
    # 城市座標對照表
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
        code = data['current']['weather_code']
        
        # 簡單的天氣代碼轉換
        weather_desc = "晴朗"
        if code in [1, 2, 3]: weather_desc = "多雲"
        elif code in [45, 48]: weather_desc = "有霧"
        elif code >= 51: weather_desc = "有雨"
        
        return f"{weather_desc} {temp}°C"
    except:
        return "連線天氣失敗"

def encode_image(image):
    buffered = io.BytesIO()
    image = image.convert('RGB')
    image.thumbnail((512, 512))
    image.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def ask_openrouter_direct(text_prompt, image_list=None):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY.strip()}",
        "HTTP-Referer": "https://myapp.com",
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
    
    # 自動切換模型
    models_to_try = [
        "google/gemini-2.0-flash-exp:free",
        "google/gemini-1.5-flash:free",
        "meta-llama/llama-3.2-11b-vision-instruct:free"
    ]
    
    for model in models_to_try:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": content_parts}]
        }
        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=20)
            if response.status_code == 200:
                data = response.json()
                if 'choices' in data and len(data['choices']) > 0:
                    content = data['choices'][0]['message']['content']
                    if content: return content
            time.sleep(1)
            continue 
        except:
            continue
            
    return "⚠️ 線路繁忙，請稍後再試。"

def extract_ids_from_text(text):
    ids = re.findall(r"ID[:：]\s*(\d+)", text, re.IGNORECASE)
    return [int(id_str) for id_str in ids]

# --- 處理上傳 ---
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

# --- 5. Dialogs & Settings ---

@st.dialog("✏️ 編輯單品")
def edit_item_dialog(item, index):
    c1, c2 = st.columns([1, 1])
    with c1: st.image(item['image'])
    with c2:
        # 使用 unique key 避免互相影響
        u_key = item['id']
        
        cats = ["上衣", "下身褲裝", "下身裙裝", "連身裙", "外套", "鞋履", "配件"]
        # 安全獲取 index
        try: idx = cats.index(item['category'])
        except: idx = 0
            
        item['category'] = st.selectbox("分類", cats, index=idx, key=f"cat_{u_key}")
        
        seasons = ["四季", "春夏", "秋冬"]
        try: s_idx = seasons.index(item['season'])
        except: s_idx = 0
        item['season'] = st.selectbox("季節", seasons, index=s_idx, key=f"sea_{u_key}")

        st.divider()
        if st.button("🗑️ 刪除", type="primary", key=f"del_{u_key}"):
            st.session_state.wardrobe.remove(item)
            st.rerun()

@st.dialog("⚙️ 設定")
def settings_dialog():
    st.subheader("👤 用戶資料")
    p = st.session_state.user_profile
    p['name'] = st.text_input("暱稱", value=p['name'])
    
    # 改變地點會觸發天氣更新
    new_loc = st.selectbox("地區", ["香港", "台北", "東京", "首爾", "倫敦"], index=0)
    if new_loc != p['location']:
        p['location'] = new_loc
        st.session_state.stylist_profile['weather_cache'] = get_real_weather(new_loc)
    
    st.divider()
    
    st.subheader("✨ Stylist 設定")
    s = st.session_state.stylist_profile
    c_s1, c_s2 = st.columns([3, 1])
    with c_s1:
        s['name'] = st.text_input("Stylist 名字", value=s['name'])
    with c_s2:
        use_img = st.toggle("用圖", value=(s['avatar_type']=='image'))
    
    if use_img:
        s['avatar_type'] = 'image'
        f = st.file_uploader("頭像", type=['png','jpg'], label_visibility="collapsed")
        if f: s['avatar_image'] = f.getvalue()
    else:
        s['avatar_type'] = 'emoji'
        s['avatar_emoji'] = st.text_input("Emoji", value=s['avatar_emoji'])
    
    # 人設即時生效，不用按套用
    presets = {
        "專業顧問": "一位貼心的專業形象顧問，語氣親切、專業。",
        "毒舌專家": "眼光極高的時尚主編，說話尖酸刻薄但一針見血。",
        "溫柔男友": "充滿愛意的男友，不管穿什麼都稱讚。",
        "霸道總裁": "強勢但寵溺的總裁，不准穿太露。"
    }
    
    sel_p = st.selectbox("人設風格", list(presets.keys()))
    # 自動填入 Prompt
    if s.get('last_preset') != sel_p:
        s['persona'] = presets[sel_p]
        s['last_preset'] = sel_p
        
    s['persona'] = st.text_area("指令 (可手動修改)", value=s['persona'])
    
    if st.button("完成", type="primary", use_container_width=True):
        st.rerun()

# --- 6. 聊天功能 ---
@st.dialog("💬 與 Stylist 對話", width="large")
def chat_dialog():
    s = st.session_state.stylist_profile
    p = st.session_state.user_profile
    
    # Header
    c1, c2 = st.columns([1, 5])
    with c1:
        if s['avatar_type'] == 'image' and s['avatar_image']:
            st.image(s['avatar_image'], width=60)
        else:
            st.write(f"### {s['avatar_emoji']}")
    with c2:
        st.write(f"**{s['name']}**")
        st.caption(f"📍 {p['location']} | {s['weather_cache']}")

    st.divider()

    # History
    for msg in st.session_state.chat_history:
        role = msg["role"]
        with st.chat_message(role):
            st.write(msg["content"])
            if "related_ids" in msg and msg["related_ids"]:
                cols = st.columns(len(msg["related_ids"]))
                for idx, item_id in enumerate(msg["related_ids"]):
                    if 0 <= item_id < len(st.session_state.wardrobe):
                        with cols[idx]:
                            item = st.session_state.wardrobe[item_id]
                            st.image(item['image'], caption=f"ID: {item_id}")

    # Input
    if user_in := st.chat_input("想問咩？"):
        st.session_state.chat_history.append({"role": "user", "content": user_in})
        with st.chat_message("user"):
            st.write(user_in)
        
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                sys_msg = (
                    f"你是{s['name']}。{s['persona']}\n"
                    f"用戶：{p['name']}, {p['location']} ({s['weather_cache']})。\n"
                    f"用戶問：{user_in}\n"
                    f"**規則：建議單品時必須標註 [ID: 數字]。**\n"
                    f"衣櫃："
                )
                img_list = []
                for i, item in enumerate(st.session_state.wardrobe):
                    img_list.append(item['image'])
                    sys_msg += f"\n- [ID: {i}] {item['category']} ({item['season']})"

                reply = ask_openrouter_direct(sys_msg, img_list)
                found_ids = extract_ids_from_text(reply)
                
                st.write(reply)
                if found_ids:
                    st.caption("✨ 建議搭配：")
                    cols = st.columns(len(found_ids))
                    valid_ids = []
                    for idx, item_id in enumerate(found_ids):
                        if 0 <= item_id < len(st.session_state.wardrobe):
                            valid_ids.append(item_id)
                            with cols[idx]:
                                item = st.session_state.wardrobe[item_id]
                                st.image(item['image'], caption=f"ID: {item_id}")
                    
                    st.session_state.chat_history.append({
                        "role": "assistant", 
                        "content": reply,
                        "related_ids": valid_ids
                    })
                else:
                    st.session_state.chat_history.append({"role": "assistant", "content": reply})

# --- 7. 主介面 (UI 裝修) ---

# 初始化天氣
if s := st.session_state.stylist_profile:
    if s['weather_cache'] == "查詢中...":
        s['weather_cache'] = get_real_weather(st.session_state.user_profile['location'])

with st.sidebar:
    s = st.session_state.stylist_profile
    p = st.session_state.user_profile
    
    # Stylist Card
    st.markdown('<div class="stylist-container">', unsafe_allow_html=True)
    
    # Avatar 邏輯修復：只顯示一個
    st.markdown('<div class="avatar-box">', unsafe_allow_html=True)
    if s['avatar_type'] == 'image' and s['avatar_image']:
        st.image(s['avatar_image'], use_column_width=True)
    else:
        st.markdown(s['avatar_emoji'])
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Name + Settings Gear
    c_name, c_gear = st.columns([5, 1])
    with c_name:
        st.markdown(f"<h3 style='margin:0'>{s['name']}</h3>", unsafe_allow_html=True)
    with c_gear:
        if st.button("⚙️"): settings_dialog()
    
    st.caption(f"{p['location']} | {s['weather_cache']}")
    st.markdown('</div>', unsafe_allow_html=True)
    
    if st.button("💬 開始對話", type="primary", use_container_width=True):
        chat_dialog()

    st.divider()

    st.subheader("📥 加入衣櫃")
    # 分類和季節放在上面，避免每次刷新
    c_up1, c_up2 = st.columns(2)
    with c_up1:
        up_cat = st.selectbox("分類", ["上衣", "下身", "連身裙", "外套", "鞋", "袋"], key="up_cat")
    with c_up2:
        up_sea = st.selectbox("季節", ["四季", "春夏", "秋冬"], key="up_sea")
        
    files = st.file_uploader("圖片", accept_multiple_files=True, label_visibility="collapsed", key=f"up_{st.session_state.uploader_key}")
    if files: process_upload(files, up_cat, up_sea)
    
    if st.button("🗑️ 清空衣櫃"):
        st.session_state.wardrobe = []
        st.rerun()

# --- Main Area: Tabs ---
tab1, tab2 = st.tabs(["🧥 我的衣櫃", "👗 試身室 (Mix & Match)"])

with tab1:
    # 季節 Switch
    season_filter = st.radio("季節", ["全部", "春夏", "秋冬"], horizontal=True, label_visibility="collapsed")
    
    # Filter Logic
    if not st.session_state.wardrobe:
        st.info("👈 左邊加入衣物啦！")
    else:
        # Filter items
        display_items = []
        for item in st.session_state.wardrobe:
            if season_filter == "全部":
                display_items.append(item)
            elif season_filter == "春夏" and item['season'] in ["四季", "春夏"]:
                display_items.append(item)
            elif season_filter == "秋冬" and item['season'] in ["四季", "秋冬"]:
                display_items.append(item)
        
        st.caption(f"顯示 {len(display_items)} 件單品")
        
        # Display Grid
        cols = st.columns(5)
        for i, item in enumerate(display_items):
            with cols[i % 5]:
                # 找出真實 ID 以便編輯
                real_id = st.session_state.wardrobe.index(item)
                st.image(item['image'], caption=f"ID: {real_id}")
                if st.button("✏️", key=f"edit_{item['id']}", use_container_width=True):
                    edit_item_dialog(item, real_id)

with tab2:
    st.subheader("Mix & Match 預覽")
    if not st.session_state.wardrobe:
        st.warning("衣櫃無衫呀！")
    else:
        c_sel, c_view = st.columns([1, 2])
        
        with c_sel:
            # 獲取各分類的單品
            tops = [x for x in st.session_state.wardrobe if x['category'] in ["上衣", "連身裙", "外套"]]
            bottoms = [x for x in st.session_state.wardrobe if x['category'] in ["下身", "褲", "裙", "下身褲裝", "下身裙裝"]]
            shoes = [x for x in st.session_state.wardrobe if x['category'] == "鞋"]
            
            # 建立選項 (ID: 類別)
            def format_func(item):
                return f"ID {st.session_state.wardrobe.index(item)}: {item['category']}"
            
            sel_top = st.selectbox("上身", tops, format_func=format_func) if tops else None
            sel_btm = st.selectbox("下身", bottoms, format_func=format_func) if bottoms else None
            sel_shoe = st.selectbox("鞋", shoes, format_func=format_func) if shoes else None
            
        with c_view:
            # 垂直顯示拼貼效果
            if sel_top: st.image(sel_top['image'], width=200)
            if sel_btm: st.image(sel_btm['image'], width=200)
            if sel_shoe: st.image(sel_shoe['image'], width=200)
            
            if not (sel_top or sel_btm or sel_shoe):
                st.info("請在左側選擇單品進行拼湊")
