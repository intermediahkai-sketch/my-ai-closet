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

# --- 2. CSS (保持 V11 Perfect Layout) ---
st.markdown("""
    <style>
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
    </style>
""", unsafe_allow_html=True)

# --- 3. 設定 API Key ---
try:
    OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
except:
    st.error("⚠️ 找不到 API Key！請去 Streamlit 網頁版 -> Settings -> Secrets 貼上 Key。")
    st.stop()

# --- 4. 初始化 ---
if 'wardrobe' not in st.session_state:
    st.session_state.wardrobe = [] 
if 'user_profile' not in st.session_state:
    st.session_state.user_profile = {"name": "User", "location": "香港", "gender": "女", "height": 160, "measurements": {"bust": 0, "waist": 0, "hips": 0}, "style_pref": "簡約休閒"}
if 'stylist_profile' not in st.session_state:
    st.session_state.stylist_profile = {"name": "你的專屬 Stylist", "avatar_type": "emoji", "avatar_emoji": "✨", "avatar_image": None, "persona": "一位貼心的專業形象顧問，語氣親切、專業。", "current_weather": "晴朗 24°C"}
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

# --- 5. 核心功能 (Aggressive Retry) ---

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
    
    # 擴充模型清單，增加成功率
    models = [
        "google/gemini-2.0-flash-exp:free",      # 首選
        "google/gemini-1.5-flash:free",          # 次選
        "meta-llama/llama-3.2-11b-vision-instruct:free", # Meta
        "google/gemini-1.5-pro:free",            # Pro版
    ]
    
    max_retries = 10  # 🔥 死纏爛打模式：試 10 次
    
    for i in range(max_retries):
        # 輪流切換模型
        model = models[i % len(models)]
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": content_parts}]
        }
        
        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=25)
            
            if response.status_code == 200:
                data = response.json()
                if 'choices' in data and len(data['choices']) > 0:
                    content = data['choices'][0]['message']['content']
                    if content: return content # 成功！
            
            # 失敗處理：顯示 Toast 告訴用戶正在重試
            error_msg = f"({response.status_code})"
            st.toast(f"⚠️ 線路繁忙 {error_msg}，正在切換至 {models[(i+1) % len(models)]}...", icon="🔄")
            time.sleep(1.5) # 等 1.5 秒再試
            
        except Exception as e:
            st.toast(f"⚠️ 網絡波動，重連中 ({i+1}/{max_retries})...", icon="📶")
            time.sleep(1)
            continue
            
    return "⚠️ 試了 10 次所有線路都爆滿，OpenRouter 現在真的太忙了，請稍後再試。"

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

# --- 6. Dialogs ---

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
    
    presets = {
        "專業顧問": "一位貼心的專業形象顧問，語氣親切、專業。",
        "毒舌專家": "眼光極高的時尚主編，說話尖酸刻薄但一針見血。",
        "溫柔男友": "充滿愛意的男友，不管穿什麼都稱讚。",
        "霸道總裁": "強勢但寵溺的總裁，不准穿太露。"
    }
    
    selected_p = st.selectbox("人設風格", list(presets.keys()))
    if st.button("⬇️ 套用人設"):
        s['persona'] = presets[selected_p]
        st.success(f"已切換為：{selected_p}")
        time.sleep(0.5)
        st.rerun()
    
    s['persona'] = st.text_area("指令", value=s['persona'])
    if st.button("完成", type="primary"): st.rerun()

# --- 7. 主介面 ---
with st.sidebar:
    s = st.session_state.stylist_profile
    p = st.session_state.user_profile
    
    st.caption(f"System v15.0 (Aggressive Retry) | Ready")

    st.markdown('<div class="stylist-container">', unsafe_allow_html=True)
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
    
    st.caption(f"早安 {p['name']} | {s['current_weather']}")
    st.markdown('</div>', unsafe_allow_html=True)
    
    if st.button("💬 開始對話", type="primary", use_container_width=True):
        chat_dialog()

    st.divider()

    # --- 👗 試身室 (保留) ---
    with st.expander("👗 試身室 (Mix & Match)", expanded=True):
        if not st.session_state.wardrobe:
            st.caption("衣櫃是空的")
        else:
            tops = [i for i, x in enumerate(st.session_state.wardrobe) if "上" in x['category'] or "外" in x['category']]
            bottoms = [i for i, x in enumerate(st.session_state.wardrobe) if "下" in x['category'] or "褲" in x['category'] or "裙" in x['category']]
            if not tops: tops = list(range(len(st.session_state.wardrobe)))
            if not bottoms: bottoms = list(range(len(st.session_state.wardrobe)))

            c1, c2 = st.columns(2)
            sel_top = c1.selectbox("上身", tops, format_func=lambda x: f"ID: {x}")
            sel_bot = c2.selectbox("下身", bottoms, format_func=lambda x: f"ID: {x}")
            if sel_top is not None and sel_bot is not None:
                st.image(st.session_state.wardrobe[sel_top]['image'], caption="Top", use_container_width=True)
                st.image(st.session_state.wardrobe[sel_bot]['image'], caption="Bottom", use_container_width=True)

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

# --- 8. 右側主畫面 ---
@st.dialog("💬 與 Stylist 對話", width="large")
def chat_dialog():
    s = st.session_state.stylist_profile
    p = st.session_state.user_profile
    
    c1, c2 = st.columns([1, 4])
    with c1:
        if s['avatar_type'] == 'image' and s['avatar_image']:
             st.markdown(f"""<style>div[data-testid="stImage"] img {{ height: 60px !important; }}</style>""", unsafe_allow_html=True)
             try: st.image(s['avatar_image'])
             except: st.write(s['avatar_emoji'])
        else:
            st.markdown(f"<h1>{s['avatar_emoji']}</h1>", unsafe_allow_html=True)
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
            with st.spinner("Stylist 正在思考... (如果線路繁忙會自動重試)"):
                sys_msg = (
                    f"你是{s['name']}。{s['persona']}\n"
                    f"用戶：{p['name']}, {p['location']} ({s['current_weather']})。\n"
                    f"用戶問：{user_in}\n"
                    f"**重要規則：當你建議某件單品時，必須明確標註它的ID，格式為 [ID: 數字]。**\n"
                    f"衣櫃清單："
                )
                img_list = []
                for i, item in enumerate(st.session_state.wardrobe):
                    img_list.append(item['image'])
                    size_str = f"L:{item['size_data']['length']} W:{item['size_data']['width']}"
                    sys_msg += f"\n- [ID: {i}] {item['category']} ({size_str})"

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

# --- 右側：我的衣櫃 ---
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
