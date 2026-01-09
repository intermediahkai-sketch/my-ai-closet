import streamlit as st
import base64
import io
import uuid
import time
import requests
import json
import re
from PIL import Image

# --- 1. 頁面設定 (必須放第一行) ---
st.set_page_config(page_title="My Stylist", page_icon="👗", layout="wide")

# --- 2. CSS (還原 V11 Perfect Layout + 長方形頭像) ---
st.markdown("""
    <style>
    /* 這是你最喜歡的 Layout 設定 */
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
        object-fit: cover !important; /* 填滿長方形 */
    }
    .stylist-container {
        background-color: #f0f2f6;
        border-radius: 15px;
        padding: 20px;
        text-align: center;
        border: 1px solid #e0e0e0;
        margin-bottom: 20px;
    }
    /* 調整 Sidebar 頂部間距 */
    section[data-testid="stSidebar"] div.block-container {
        padding-top: 2rem;
    }
    </style>
""", unsafe_allow_html=True)

# --- 3. 設定 API Key ---
try:
    OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
except:
    st.error("⚠️ 找不到 API Key！請去 Streamlit 網頁版 -> Settings -> Secrets 貼上 Key。")
    st.stop()

# --- 4. 初始化資料 (只做一次) ---
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
        "avatar_image": None, # 只保留圖片
        "persona": "一位貼心的專業形象顧問，語氣親切、專業。",
        "weather_cache": "查詢中...",
        "current_weather": "晴朗 24°C"
    }

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

# 預設星星圖 (Base64) - 當沒有上傳頭像時使用
DEFAULT_STAR_ICON = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADIAAAAyCAYAAAAeP4ixAAAABmJLR0QA/wD/AP+gvaeTAAAHLklEQVRogc2ae2xT5x3HP895x7Fz7DgXEqc4IYQ7QiglLRTa0g7a0g603WjXVarS0q5126R2U9qmTW23v6Zpm7Rp66Z2aNqudXTt1G60FChNoS1QCKPJgyYEh8S52I6d+D7n7Y/jiG1s44vj80i+P/zO8/t9f5/v8/19fudIGMJA2O8CDAnzC+S/iWkF0tPTEz1z5swRj8fzlM/ne9jn8z0ciUSm4vF4tFgs5rAsy6yqqjIEQTCrq6s/qa2tfbm+vv792trai/MLpKurK9rR0fG8z+d7c2xs7KBAIPDY2NjYlEAgEAJwuVxYLBaKi4spKioiIyODjIwMcnJyyMrKIiMjg9zcXAoLC1EUBUVR0DQNwzAwTRPDMDAMg4mJCcLhMKFQyIzFYslAIHAmEAi8e+HChb+vW7fu/XkF0t7e/qLf7/9zIBB4eHx8fOrw4cMAZGVlsWbNGlatWkVVVRXV1dWsWrWKkpISXC4XAAzDQNM0dF3HMAwMw0DXdTRNwzRNLMsCYHJykpGREYaGhhgaGmJoaIiBgQEGg8H4yMjIewMDA/9cs2bNqXkDomna04FA4M0jR4480t/fD0BFRQWrV6+mtraW2tpa1q5dS1FREYIgYFkWlmVhWRaCIGCaJqZpYpompmni8XgA8Hg8uFwuXC4Xbrcbv9+P3++no6ODzs5OhoaGEoFA4K329va/nVOgXR0dDzf19f35sGDB6cKCwtpbGykubmZdevWkZeXh2VZ2Lat/bH/e2xbf8Y0TVRVRVVVjh8/zqFDh4hGo4lAIHDq6NGjLzU0NHw4J0BdXd2Tvb29b5w9e/axkpISmpqa2LBhA1lZWQDYto1lWdi2bQOxbRvbtjFNE9M0MU0TwzAwDMM2dF3HMAx0XcfhcOBwOHREHA4HDocDv99PX18fPT09iYGBgbf37dv3ckNDw5/mBAiFQk/39fW9ceTIkcfq6upoampizZo1CILwJ4Qsy8K2bSzLwjRNLMvCtm0sy8I0TQzDQNM0DMNAlmVkWSYnJweHw0FxcTFNTU00NTVx7tw5uru7E8Fg8I0DBw683NDQ8Ke5AhKJRJ4eHBx888iRI4/V1tbS3NxMcXExgiBgWRaWZWGaJpZlYds2giAgCAKCIGBZFrZtY5omlmVhmia6riPLMrIsI8syTqeTvLw8mpqaaGpq4syZM3R3dyeCwWDrwYMHX2poaPjjXAEJBoNP9/f3v3H48OHHamtraWlpwe12Y9s2lmVhWRaCIGDbNoIgIAgCtm1j2zaWZWGaJoZhoOs6siwjy7KNyLKMy+WirKyM5uZmmpub6ezspKurKxEIBFofPnz4pYaGhj/NBZBgMPj0wMDAmy6X67GGhgZKS0uxbRvbtv8IwrZtBEHAtu2HAsiyjK7r6LqOqqrIsoyiKMiyTFZWFs3NzbS0tNDZ2Ul3d3ciEAhs2Ldv3sMP/NBZBgMPj0wMDAmy6X67GGhgZKS0uxbRvbtv8IwrZtBEHAtu2HAsiyjK7r6LqOqqrIsoyiKMiyTFZWFs3NzbS0tNDZ2Ul3d3ciEAhs2Ldv3sMP/NBZBgMPj0wMDAmy6X67GGhgZKS0uxbRvbtv8IwrZtBEHAtu2HAsiyjK7r6LqOqqrIsoyiKMiyTFZWFs3NzbS0tNDZ2Ul3d3ciEAhs2Ldv3sMP"

# --- 5. 核心功能函式 ---

def get_real_weather(city):
    """使用 Open-Meteo API 獲取天氣"""
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
    
    models_to_try = [
        "google/gemini-2.0-flash-exp:free",
        "google/gemini-1.5-flash:free",
        "meta-llama/llama-3.2-11b-vision-instruct:free"
    ]
    
    for model in models_to_try:
        payload = {"model": model, "messages": [{"role": "user", "content": content_parts}]}
        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=20)
            if response.status_code == 200:
                data = response.json()
                if 'choices' in data and len(data['choices']) > 0:
                    content = data['choices'][0]['message']['content']
                    if content: return content
            time.sleep(1)
        except:
            pass
    return "⚠️ 線路繁忙，請稍後再試。"

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

# --- 6. Dialogs (必須先定義) ---

@st.dialog("✏️ 編輯單品")
def edit_item_dialog(item, index):
    st.caption(f"正在編輯 Item [ID: {index}]")
    c1, c2 = st.columns([1, 1])
    with c1: st.image(item['image'])
    with c2:
        cats = ["上衣", "下身褲裝", "下身裙裝", "連身裙", "外套", "鞋履", "配件"]
        idx = cats.index(item['category']) if item['category'] in cats else 0
        item['category'] = st.selectbox("分類", cats, index=idx)
        
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
    
    # 地點與天氣
    new_loc = st.selectbox("地區", ["香港", "台北", "東京", "首爾", "倫敦"], index=0)
    if new_loc != p['location']:
        p['location'] = new_loc
        st.session_state.stylist_profile['weather_cache'] = get_real_weather(new_loc)
    
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

    st.subheader("✨ Stylist 設定")
    s = st.session_state.stylist_profile
    s['name'] = st.text_input("Stylist 名字", value=s['name'])
    
    f = st.file_uploader("更換頭像 (長方形)", type=['png','jpg'])
    if f: s['avatar_image'] = f.getvalue()
    
    if st.button("還原預設星星圖"):
        s['avatar_image'] = None
        st.rerun()

    presets = {
        "專業顧問": "一位貼心的專業形象顧問，語氣親切、專業。",
        "毒舌專家": "眼光極高的時尚主編，說話尖酸刻薄但一針見血。",
        "溫柔男友": "充滿愛意的男友，不管穿什麼都稱讚。"
    }
    sel_p = st.selectbox("人設", list(presets.keys()))
    if st.button("套用人設"):
        s['persona'] = presets[sel_p]
        st.success(f"已切換：{sel_p}")
        st.rerun()

    s['persona'] = st.text_area("指令", value=s['persona'])
    if st.button("完成", type="primary"): st.rerun()

@st.dialog("💬 與 Stylist 對話", width="large")
def chat_dialog():
    s = st.session_state.stylist_profile
    p = st.session_state.user_profile
    
    c1, c2 = st.columns([1, 4])
    with c1:
        if s['avatar_image']:
            # 對話框內強制縮小頭像
            st.markdown("""<style>div[data-testid="stImage"] img { height: 60px !important; }</style>""", unsafe_allow_html=True)
            st.image(s['avatar_image'])
        else:
            st.markdown("""<style>div[data-testid="stImage"] img { height: 60px !important; }</style>""", unsafe_allow_html=True)
            st.image(DEFAULT_STAR_ICON)
            
    with c2:
        st.subheader(s['name'])
        st.caption(f"📍 {p['location']} | {s['weather_cache']}")

    st.divider()

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

    if user_in := st.chat_input("想問咩？"):
        st.session_state.chat_history.append({"role": "user", "content": user_in})
        with st.chat_message("user"):
            st.write(user_in)
        
        with st.chat_message("assistant"):
            with st.spinner("Stylist 正在衣櫃翻找..."):
                m = p['measurements']
                body_info = f"{p['height']}cm/{p['weight']}kg, 三圍:{m['bust']}-{m['waist']}-{m['hips']}"
                sys_msg = (
                    f"你是{s['name']}。{s['persona']}\n"
                    f"用戶：{p['name']} ({body_info}), {p['location']} ({s['weather_cache']})。\n"
                    f"用戶問：{user_in}\n"
                    f"**重要規則：建議單品時，必須明確標註 [ID: 數字]。**\n"
                    f"衣櫃清單："
                )
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
                    
                st.session_state.chat_history.append({
                    "role": "assistant", 
                    "content": reply,
                    "related_ids": valid_ids
                })

# --- 7. 主程式 (Sidebar & Main) ---

# 更新天氣
if st.session_state.stylist_profile['weather_cache'] == "查詢中...":
    loc = st.session_state.user_profile['location']
    st.session_state.stylist_profile['weather_cache'] = get_real_weather(loc)

with st.sidebar:
    s = st.session_state.stylist_profile
    p = st.session_state.user_profile
    
    st.markdown('<div class="stylist-container">', unsafe_allow_html=True)
    
    # 頭像顯示
    if s['avatar_image']:
        st.image(s['avatar_image'], use_column_width=True)
    else:
        st.image(DEFAULT_STAR_ICON, use_column_width=True)
    
    c_name, c_gear = st.columns([4, 1])
    with c_name: st.markdown(f"### {s['name']}")
    with c_gear: 
        if st.button("⚙️"): settings_dialog()
            
    st.caption(f"{p['location']} | {s['weather_cache']}")
    st.markdown('</div>', unsafe_allow_html=True)
    
    if st.button("💬 開始對話", type="primary", use_container_width=True):
        chat_dialog()

    # 試身室 (側邊欄版)
    with st.expander("👗 試身室 (Mix & Match)", expanded=True):
        if not st.session_state.wardrobe:
            st.caption("衣櫃是空的")
        else:
            tops = [i for i, x in enumerate(st.session_state.wardrobe) if x['category'] in ["上衣","外套","連身裙"]]
            bots = [i for i, x in enumerate(st.session_state.wardrobe) if x['category'] in ["下身褲裝","下身裙裝","下身","褲","裙"]]
            
            # 若分類未識別，就全顯示
            if not tops: tops = list(range(len(st.session_state.wardrobe)))
            if not bots: bots = list(range(len(st.session_state.wardrobe)))

            c1, c2 = st.columns(2)
            t = c1.selectbox("上", tops, format_func=lambda x: f"ID:{x}")
            b = c2.selectbox("下", bots, format_func=lambda x: f"ID:{x}")
            
            if t is not None: st.image(st.session_state.wardrobe[t]['image'])
            if b is not None: st.image(st.session_state.wardrobe[b]['image'])

    st.divider()
    st.subheader("📥 加入衣櫃")
    c1, c2 = st.columns(2)
    cat = c1.selectbox("分類", ["上衣", "下身", "連身裙", "外套", "鞋", "袋"])
    sea = c2.selectbox("季節", ["四季", "春夏", "秋冬"])
    files = st.file_uploader("圖片", accept_multiple_files=True, key=f"up_{st.session_state.uploader_key}")
    if files: process_upload(files, cat, sea)
    
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🗑️ 清空"):
        st.session_state.wardrobe = []
        st.rerun()

# 主畫面
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
            real_id = st.session_state.wardrobe.index(item)
            st.image(item['image'], caption=f"ID: {real_id}")
            if st.button("✏️", key=f"e_{item['id']}", use_container_width=True):
                 edit_item_dialog(item, real_id)
