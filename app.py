import streamlit as st
import base64
import io
import uuid
import time
import requests
import json
import re
from PIL import Image

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
        "gender": "女", # 預設
        "height": 160,  # 預設
        "weight": 50,   # 新增預設
        "measurements": {"bust": 32, "waist": 24, "hips": 34}, # 新增三圍
        "style_pref": "簡約休閒"
    }

if 'stylist_profile' not in st.session_state:
    st.session_state.stylist_profile = {
        "name": "你的專屬 Stylist",
        # 移除了 avatar_type 和 avatar_emoji 的選擇邏輯，只保留 image
        "avatar_image": None, 
        "persona": "一位貼心的專業形象顧問，語氣親切、專業。",
        "current_weather": "晴朗 24°C"
    }

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

# --- 3. 頁面設定與 CSS (重點修改) ---
st.set_page_config(page_title="My Stylist", page_icon="👗", layout="wide")

st.markdown("""
    <style>
    /* 對話框內的圖片樣式 */
    div[data-testid="stImage"] {
        background-color: #f9f9f9;
        border-radius: 10px;
        padding: 5px;
        display: flex;
        justify-content: center;
        align-items: center;
    }
    div[data-testid="stImage"] img {
        height: 180px !important; 
        object-fit: contain !important;
    }
    
    /* Sidebar 容器 */
    .stylist-container {
        background-color: #ffffff;
        border-radius: 0px; /* 變成長方型 */
        padding: 0px;
        text-align: center;
        margin-bottom: 20px;
        overflow: hidden;
    }

    /* 新的長方形 Stylist 頭像框 */
    .stylist-avatar-box {
        width: 100%;
        height: 300px; /* 固定高度，讓它看起來像一張海報/卡片 */
        background-color: #f0f2f6;
        display: flex;
        justify-content: center;
        align-items: center;
        overflow: hidden;
        border-radius: 10px;
        margin-bottom: 10px;
        border: 1px solid #ddd;
    }
    
    /* 當有圖片時 */
    .stylist-avatar-box img {
        width: 100%;
        height: 100%;
        object-fit: cover; /* 填滿整個框 */
    }

    /* 當沒有圖片時 (預設星星) */
    .default-star {
        font-size: 100px;
        color: #FFD700;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
    }

    button[kind="secondary"] { border: 1px solid #ddd; }
    </style>
""", unsafe_allow_html=True)

# --- 4. 核心功能 ---

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
        except Exception:
            continue
            
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

# --- 5. Dialogs ---

@st.dialog("✏️ 編輯單品")
def edit_item_dialog(item, index):
    st.caption(f"正在編輯 Item #{index}")
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
    st.subheader("👤 我的身體密碼")
    st.caption("提供準確數據，AI 才能給你最顯瘦的建議！")
    
    p = st.session_state.user_profile
    
    # 基本資料
    c1, c2 = st.columns(2)
    p['name'] = c1.text_input("暱稱", value=p['name'])
    p['location'] = c2.selectbox("地區", ["香港", "台北", "東京", "首爾", "倫敦"], index=0)
    
    # 身型數據 (新增)
    st.markdown("---")
    c_gen, c_h, c_w = st.columns(3)
    p['gender'] = c_gen.selectbox("性別", ["女", "男", "其他"], index=0 if p.get('gender')=='女' else 1)
    p['height'] = c_h.number_input("身高 (cm)", value=p.get('height', 160))
    p['weight'] = c_w.number_input("體重 (kg)", value=p.get('weight', 50))
    
    # 三圍數據 (新增)
    st.caption("三圍 (吋/cm 自選)")
    c_b, c_wa, c_hi = st.columns(3)
    p['measurements']['bust'] = c_b.number_input("胸圍", value=p['measurements'].get('bust', 0))
    p['measurements']['waist'] = c_wa.number_input("腰圍", value=p['measurements'].get('waist', 0))
    p['measurements']['hips'] = c_hi.number_input("臀圍", value=p['measurements'].get('hips', 0))
    
    st.subheader("✨ Stylist 形象設定")
    s = st.session_state.stylist_profile
    s['name'] = st.text_input("Stylist 名字", value=s['name'])
    
    # 強制使用圖片上傳，沒有 emoji 選項了
    f = st.file_uploader("上傳 Stylist 照片 (長方形效果最佳)", type=['png','jpg'])
    if f: 
        s['avatar_image'] = f.getvalue()
        st.success("照片已更新！")
    
    # 清除照片按鈕
    if s['avatar_image'] and st.button("還原預設星星圖"):
        s['avatar_image'] = None
        st.rerun()

    s['persona'] = st.text_area("指令 (Persona)", value=s['persona'])
    if st.button("完成並儲存", type="primary", use_container_width=True): st.rerun()

# --- 6. 聊天功能 ---
@st.dialog("💬 與 Stylist 對話", width="large")
def chat_dialog():
    s = st.session_state.stylist_profile
    p = st.session_state.user_profile
    
    # 聊天室頂部資訊
    c1, c2 = st.columns([1, 5])
    with c1:
        # 小圓頭像 (僅在對話框顯示小圖)
        if s['avatar_image']:
            st.image(s['avatar_image'], width=50)
        else:
            st.markdown("✨")
    with c2:
        st.subheader(s['name'])
        st.caption(f"📍 {p['location']} | {s['current_weather']}")

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
            with st.spinner("Stylist 正在思考..."):
                # 構建 Prompt：加入用戶詳細身型數據
                measure_str = f"胸{p['measurements']['bust']}/腰{p['measurements']['waist']}/臀{p['measurements']['hips']}"
                user_details = f"{p['gender']}, 身高{p['height']}cm, 體重{p['weight']}kg, 三圍: {measure_str}"
                
                sys_msg = (
                    f"你是{s['name']}。{s['persona']}\n"
                    f"用戶資料：{p['name']}, {p['location']}, {user_details}。\n"
                    f"用戶問：{user_in}\n"
                    f"**請根據用戶的身型數據提供修飾身形的建議。**\n"
                    f"**規則：建議單品時，必須標註 [ID: 數字]。**\n"
                    f"衣櫃清單："
                )
                img_list = []
                for i, item in enumerate(st.session_state.wardrobe):
                    img_list.append(item['image'])
                    size_str = f"L:{item['size_data']['length']} W:{item['size_data']['width']}"
                    sys_msg += f"\n- [ID: {i}] {item['category']} (尺碼:{size_str})"

                reply = ask_openrouter_direct(sys_msg, img_list)
                
                found_ids = extract_ids_from_text(reply)
                st.write(reply)
                if found_ids:
                    st.caption("✨ 建議單品：")
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

# --- 7. 主介面 (Sidebar 改版) ---
with st.sidebar:
    s = st.session_state.stylist_profile
    p = st.session_state.user_profile
    
    st.caption(f"System v13.0 (Full UI) | Ready")

    # --- 新的 Stylist 頭像區 ---
    # 使用 HTML/CSS 繪製長方形框
    if s['avatar_image']:
        # 如果有圖片，轉成 Base64 顯示在 HTML img 標籤中以符合 CSS
        b64_img = base64.b64encode(s['avatar_image']).decode()
        avatar_html = f"""
        <div class="stylist-avatar-box">
            <img src="data:image/png;base64,{b64_img}">
        </div>
        """
    else:
        # 如果沒有圖片，顯示預設大星星
        avatar_html = """
        <div class="stylist-avatar-box">
            <div class="default-star">✨</div>
        </div>
        """
    
    st.markdown(avatar_html, unsafe_allow_html=True)
    # ---------------------------
    
    st.markdown(f"<h3 style='text-align: center;'>{s['name']}</h3>", unsafe_allow_html=True)
    
    c_btn = st.columns([1,2,1])
    with c_btn[1]:
        if st.button("⚙️ 設定 / 完善資料"): settings_dialog()
    
    st.caption(f"早安 {p['name']} | {s['current_weather']}")
    
    if st.button("💬 開始對話", type="primary", use_container_width=True):
        chat_dialog()

    st.divider()

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
