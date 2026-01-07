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
        "avatar_type": "emoji", # emoji or image
        "avatar_emoji": "🤵",
        "avatar_image": None,
        "persona": "一位品味高雅、語氣溫柔沉穩的專業形象設計師。",
        "current_weather": "晴朗 24°C"
    }

if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0

# --- 3. 頁面設定與 CSS (簡潔版) ---
st.set_page_config(page_title="My Stylist", page_icon="✨", layout="wide")

st.markdown("""
    <style>
    /* 圖片卡片樣式 */
    div[data-testid="stImage"] {
        background-color: #f9f9f9;
        border-radius: 10px;
        padding: 5px;
    }
    div[data-testid="stImage"] img {
        height: 250px !important;
        object-fit: contain !important; /* 確保整件衫睇得哂 */
    }
    
    /* 側邊欄造型師區塊 */
    .stylist-box {
        text-align: center;
        background: #f0f2f6;
        padding: 20px;
        border-radius: 15px;
        margin-bottom: 20px;
    }
    
    /* 去除按鈕多餘邊框 */
    button[kind="secondary"] {
        border: 1px solid #ddd;
    }
    </style>
""", unsafe_allow_html=True)

# --- 4. 核心功能函數 ---

# 嘗試連接 AI，失敗則回傳 None
def try_get_ai_response(prompt_inputs):
    try:
        # 嘗試使用標準 Flash 模型
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt_inputs)
        return response.text
    except Exception as e:
        # 如果失敗，嘗試使用舊版 Pro 模型作為後備
        try:
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(prompt_inputs)
            return response.text
        except:
            return f"⚠️ 連線不穩 ({str(e)})，請重試。"

# 處理上載 (去背 + 存入)
def process_upload(files, category, season):
    if not files: return
    
    # 顯示進度條
    progress_bar = st.progress(0)
    
    for i, uploaded_file in enumerate(files):
        try:
            image = Image.open(uploaded_file)
            
            # 去背
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            output_bytes = remove_bg(img_byte_arr.getvalue())
            final_image = Image.open(io.BytesIO(output_bytes))
            
            # 存入
            st.session_state.wardrobe.append({
                'id': str(uuid.uuid4()),
                'image': final_image,
                'category': category, # 使用手動選擇的分類
                'season': season,
                'size_data': {'length': '', 'width': '', 'waist': ''}
            })
        except:
            pass # 忽略錯誤圖片
        progress_bar.progress((i + 1) / len(files))
    
    time.sleep(0.5)
    progress_bar.empty()
    st.session_state.uploader_key += 1
    st.toast(f"✅ 已加入 {len(files)} 件單品", icon="🧥")
    st.rerun()

# 模擬天氣 (簡單版)
def update_weather_if_needed():
    loc = st.session_state.user_profile['location']
    weathers = ["晴朗 28°C", "多雲 22°C", "有雨 19°C", "乾燥 25°C"]
    # 這裡可以加入邏輯，不用每次都變
    if "last_loc" not in st.session_state or st.session_state.last_loc != loc:
        st.session_state.stylist_profile['current_weather'] = random.choice(weathers)
        st.session_state.last_loc = loc

# --- 5. 彈出視窗 (Dialogs) ---

# A. 編輯單品
@st.dialog("✏️ 編輯單品")
def edit_item_dialog(item):
    col_img, col_form = st.columns([1, 1])
    with col_img:
        st.image(item['image'], use_column_width=True)
    with col_form:
        # 分類
        cats = ["上衣", "下身褲裝", "下身裙裝", "連身裙/套裝", "外套", "鞋履", "配件"]
        default_idx = cats.index(item['category']) if item['category'] in cats else 0
        item['category'] = st.selectbox("分類", cats, index=default_idx)
        
        # 尺碼
        if "上衣" in item['category'] or "外套" in item['category']:
            item['size_data']['length'] = st.text_input("衣長", value=item['size_data']['length'])
            item['size_data']['width'] = st.text_input("胸寬", value=item['size_data']['width'])
        elif "下身" in item['category']:
            item['size_data']['length'] = st.text_input("褲/裙長", value=item['size_data']['length'])
            item['size_data']['waist'] = st.text_input("腰圍", value=item['size_data']['waist'])
        
        st.divider()
        if st.button("🗑️ 刪除單品", type="primary", use_container_width=True):
            st.session_state.wardrobe.remove(item)
            st.rerun()

# B. 設定 (使用 Callback 即時更新)
def update_persona_callback():
    """當下拉選單改變時，直接更新人設文字"""
    presets = {
        "專業莫弈": "你現在是「莫弈」，一位品味高雅、語氣溫柔沉穩的專業形象設計師。語氣要優雅、知性、帶有淡淡的關懷。",
        "霸道總裁": "你現在是霸道總裁男友。語氣要自信、強勢但充滿寵溺。叫用戶『笨蛋』或『寶貝』。如果衣服太露，要表現出吃醋。",
        "溫柔奶狗": "你現在是年下的溫柔男友。語氣要超級甜，充滿愛意，叫用戶『姐姐』或『BB』。不管穿什麼都瘋狂稱讚。",
        "毒舌主編": "你現在是頂級時尚雜誌的主編。眼光極高，說話尖酸刻薄但一針見血。看到搭配不好會直接說『這簡直是災難』。"
    }
    selected = st.session_state.persona_selector
    if selected in presets:
        st.session_state.stylist_profile['persona'] = presets[selected]

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
    
    # 頭像設定
    use_image = st.toggle("使用圖片頭像?", value=(s['avatar_type']=='image'))
    if use_image:
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

    # 人設 (修正：選擇後文字框會變)
    st.selectbox(
        "快速選擇人設", 
        ["專業莫弈", "霸道總裁", "溫柔奶狗", "毒舌主編"], 
        key="persona_selector",
        index=None,
        placeholder="請選擇...",
        on_change=update_persona_callback # 關鍵修正
    )
    
    s['persona'] = st.text_area("人設指令 (可手動修改)", value=s['persona'], height=100)

    if st.button("完成", type="primary", use_container_width=True):
        st.rerun()

# C. 聊天 (修復 Crash)
@st.dialog("💬 與造型師對話", width="large")
def chat_dialog():
    s = st.session_state.stylist_profile
    p = st.session_state.user_profile
    
    # 頂部顯示
    c1, c2 = st.columns([1, 4])
    with c1:
        if s['avatar_type'] == 'image' and s['avatar_image']:
            st.image(s['avatar_image'], width=80)
        else:
            st.markdown(f"<h1 style='text-align:center'>{s['avatar_emoji']}</h1>", unsafe_allow_html=True)
    with c2:
        st.subheader(s['name'])
        st.caption(f"📍 {p['location']} | {s['current_weather']}")

    st.divider()
    
    # 初始化天氣
    update_weather_if_needed()

    # 自動開場
    if not st.session_state.chat_history:
        with st.spinner("連線中..."):
            prompt = (
                f"你是{s['name']}，{s['persona']}。\n"
                f"用戶{p['name']}在{p['location']}，天氣{s['current_weather']}。\n"
                f"請簡短打招呼並問用戶想點襯。"
            )
            reply = try_get_ai_response([prompt])
            st.session_state.chat_history.append({"role": "assistant", "content": reply})
            st.rerun()

    # 顯示歷史
    for msg in st.session_state.chat_history:
        role = msg["role"]
        with st.chat_message(role):
            st.write(msg["content"])

    # 輸入
    if user_in := st.chat_input("輸入訊息..."):
        st.session_state.chat_history.append({"role": "user", "content": user_in})
        st.rerun()

    # AI 回應 (在 rerun 後)
    if st.session_state.chat_history and st.session_state.chat_history[-1]['role'] == 'user':
        with st.chat_message("assistant"):
            with st.spinner("思考中..."):
                # 構建 Prompt
                sys_msg = (
                    f"你是{s['name']}。{s['persona']}\n"
                    f"用戶資料：{p['name']}, 身高{p['height']}, {p['location']} ({s['current_weather']})。\n"
                    f"歷史對話在上方。最新用戶訊息：{st.session_state.chat_history[-1]['content']}\n"
                    f"請從衣櫃挑選單品建議 (如有)。"
                )
                inputs = [sys_msg]
                # 傳送衣櫃 (限制數量以免太慢)
                for i, item in enumerate(st.session_state.wardrobe[:15]): 
                    inputs.append(f"單品#{i+1} ({item['category']})")
                    inputs.append(item['image'])
                
                reply = try_get_ai_response(inputs)
                st.markdown(reply)
                st.session_state.chat_history.append({"role": "assistant", "content": reply})


# --- 6. 側邊欄 UI (乾淨版) ---
with st.sidebar:
    s = st.session_state.stylist_profile
    p = st.session_state.user_profile
    
    # 造型師卡片 (使用原生 Layout，不 Hack)
    with st.container(border=True):
        # 1. 頭像 (置中)
        c_av = st.columns([1, 2, 1])
        with c_av[1]: # 中間
            if s['avatar_type'] == 'image' and s['avatar_image']:
                # 顯示圓形圖片效果需要一點小 CSS，但直接顯示圖片最穩定
                st.image(s['avatar_image'], use_column_width=True)
            else:
                st.markdown(f"<h1 style='text-align:center; font-size:80px; margin:0;'>{s['avatar_emoji']}</h1>", unsafe_allow_html=True)
        
        # 2. 名字與設定
        c_nm, c_st = st.columns([4, 1])
        with c_nm:
            st.markdown(f"<h3 style='text-align:center; margin:0;'>{s['name']}</h3>", unsafe_allow_html=True)
        with c_st:
            if st.button("⚙️", help="設定"):
                settings_dialog()
        
        # 3. 問候
        st.caption(f"早安 {p['name']} | {s['current_weather']}")
        
        # 4. 聊天按鈕 (這是最穩定的做法)
        if st.button("💬 開始對話", type="primary", use_container_width=True):
            chat_dialog()

    st.divider()
    
    # 加入衣櫃 (手動分類 - 最快最準)
    st.subheader("📥 加入衣櫃")
    
    col_cat, col_sea = st.columns(2)
    with col_cat:
        cat_input = st.selectbox("分類", ["上衣", "下身褲裝", "下身裙裝", "連身裙", "外套", "鞋履", "配件"])
    with col_sea:
        sea_input = st.selectbox("季節", ["四季", "春夏", "秋冬"])
    
    files = st.file_uploader("拖曳圖片到此 (自動去背)", type=['jpg','png','webp'], accept_multiple_files=True, key=f"up_{st.session_state.uploader_key}")
    
    if files:
        process_upload(files, cat_input, sea_input)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🗑️ 清空衣櫃", use_container_width=True):
        st.session_state.wardrobe = []
        st.rerun()

# --- 7. 主畫面 ---
st.subheader("🧥 我的衣櫃")

if not st.session_state.wardrobe:
    st.info("👈 左側拖曳圖片加入單品，然後點擊「開始對話」！")
else:
    # 篩選
    cats = list(set([x['category'] for x in st.session_state.wardrobe]))
    sel = st.multiselect("🔍", cats, placeholder="篩選分類")
    items = [x for x in st.session_state.wardrobe if x['category'] in sel] if sel else st.session_state.wardrobe
    
    # Grid 顯示
    cols = st.columns(5)
    for i, item in enumerate(items):
        with cols[i % 5]:
            st.image(item['image'], use_column_width=True)
            if st.button("✏️", key=f"btn_{item['id']}", use_container_width=True):
                edit_item_dialog(item)
