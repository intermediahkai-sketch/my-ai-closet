import streamlit as st
import google.generativeai as genai
from PIL import Image
import uuid
import io
from rembg import remove as remove_bg

# --- 設定 API Key ---
if "GOOGLE_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
else:
    st.error("找不到 API Key，請檢查 Secrets 設定")
    st.stop()

# --- 初始化 Session State ---
if 'wardrobe' not in st.session_state:
    st.session_state.wardrobe = [] 

# 初始化用戶設定 (現在包含名字、地區)
if 'user_profile' not in st.session_state:
    st.session_state.user_profile = {
        "name": "User", # 預設名
        "location": "香港", # 預設地區
        "gender": "女",
        "height": 160, 
        "measurements": {"bust": 0, "waist": 0, "hips": 0},
        "style_pref": "簡約休閒"
    }

if 'uploader_key' not in st.session_state:
    st.session_state.uploader_key = 0
if 'edit_modes' not in st.session_state:
    st.session_state.edit_modes = {}

# --- 頁面設定 & CSS 美化 (重點修改) ---
st.set_page_config(page_title="莫弈的衣帽間", page_icon="🎩", layout="wide")

# 注入 CSS 來去除按鈕灰框、統一圖片大小、置中
st.markdown("""
    <style>
    /* 1. 針對 Grid 內的按鈕去除邊框和背景，變成純 Icon */
    div[data-testid="stHorizontalBlock"] button[kind="secondary"] {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
        padding: 0px !important;
        color: #555 !important;
    }
    div[data-testid="stHorizontalBlock"] button[kind="secondary"]:hover {
        color: #06b6d4 !important; /* 滑過變 Cyan 色 */
        background: transparent !important;
    }
    
    /* 2. 讓圖片容器盡量統一高度 (視乎圖片比例，這只能盡量對齊) */
    div[data-testid="stImage"] img {
        max-height: 200px;
        object-fit: contain; /* 保持比例 */
    }
    
    /* 3. 隱藏 File Uploader 的預設文字，模擬成一個 Button */
    /* 這是比較進階的 Hack，視乎瀏覽器支援 */
    section[data-testid="stFileUploader"] {
        padding-top: 0;
    }
    </style>
""", unsafe_allow_html=True)

# --- 定義「設定」彈出視窗 (Dialog) ---
@st.dialog("👤 個人檔案設定")
def open_settings():
    st.caption("請輸入你的資料，讓莫弈更了解你。")
    
    # 1. 基本資料
    new_name = st.text_input("你的暱稱", value=st.session_state.user_profile['name'])
    new_loc = st.text_input("居住地區 (供天氣參考)", value=st.session_state.user_profile['location'])
    
    st.divider()
    
    # 2. 身體數據
    new_gender = st.radio("性別", ["女", "男", "通用"], index=["女", "男", "通用"].index(st.session_state.user_profile['gender']), horizontal=True)
    new_h = st.number_input("身高 (cm)", value=st.session_state.user_profile['height'])
    
    c1, c2, c3 = st.columns(3)
    with c1: new_b = st.number_input("胸圍", value=st.session_state.user_profile['measurements']['bust'])
    with c2: new_w = st.number_input("腰圍", value=st.session_state.user_profile['measurements']['waist'])
    with c3: new_hip = st.number_input("臀圍", value=st.session_state.user_profile['measurements']['hips'])
    
    new_style = st.selectbox("風格偏好", ["簡約休閒", "日系層次", "韓系溫柔", "歐美型格", "復古", "正式/上班", "街頭潮流", "紳士/雅痞"], index=0)

    if st.button("💾 儲存設定", use_container_width=True, type="primary"):
        # 更新 Session State
        st.session_state.user_profile.update({
            "name": new_name,
            "location": new_loc,
            "gender": new_gender,
            "height": new_h,
            "measurements": {"bust": new_b, "waist": new_w, "hips": new_hip},
            "style_pref": new_style
        })
        st.rerun()

# --- 側邊欄 (精簡化) ---
with st.sidebar:
    # 1. 加入衣櫃區
    st.header("📥 加入衣櫃")
    
    col1, col2 = st.columns(2)
    with col1:
        cat_options = ["上衣", "下身褲裝", "下身裙裝", "連身裙/套裝", "外套", "鞋履", "配件/包包"]
        batch_cat = st.selectbox("分類", cat_options, label_visibility="collapsed")
    with col2:
        batch_season = st.selectbox("季節", ["四季", "春夏", "秋冬"], label_visibility="collapsed")
    
    # 上載按鈕
    uploaded_files = st.file_uploader(
        "選擇圖片", # 這裡標籤改成了簡單文字，配合 CSS
        type=["jpg", "png", "jpeg", "webp"], 
        accept_multiple_files=True,
        key=f"uploader_{st.session_state.uploader_key}",
        label_visibility="visible" # 顯示 "選擇圖片" 作為標題
    )
    
    if uploaded_files:
        do_remove_bg = st.checkbox("✨ 自動去背", value=True)
        if st.button("確認存入", type="primary", use_container_width=True):
            progress_bar = st.progress(0)
            for i, uploaded_file in enumerate(uploaded_files):
                image = Image.open(uploaded_file)
                final_image = image
                if do_remove_bg:
                    try:
                        img_byte_arr = io.BytesIO()
                        image.save(img_byte_arr, format='PNG')
                        output_bytes = remove_bg(img_byte_arr.getvalue())
                        final_image = Image.open(io.BytesIO(output_bytes))
                    except: pass

                item_id = str(uuid.uuid4())
                st.session_state.wardrobe.append({
                    'id': item_id,
                    'image': final_image,
                    'category': batch_cat, 
                    'season': batch_season,
                    'size_data': {'length': '', 'width': '', 'waist': ''}
                })
                st.session_state.edit_modes[item_id] = False
                progress_bar.progress((i + 1) / len(uploaded_files))
            
            st.session_state.uploader_key += 1
            st.success("成功！")
            st.rerun()

    st.divider()
    
    # 2. 清空與設定
    if st.button("🗑️ 清空衣櫃", use_container_width=True):
        st.session_state.wardrobe = []
        st.session_state.edit_modes = {}
        st.rerun()
        
    # 設定按鈕 (放在最下方)
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("⚙️ 設定個人檔案", use_container_width=True):
        open_settings()


# --- 主畫面 ---
tab1, tab2 = st.tabs(["🧥 我的衣櫃", "✨ 莫弈"])

with tab1:
    # 頂部：個人化打招呼
    p = st.session_state.user_profile
    st.caption(f"👋 Hi {p['name']}, {p['location']} 今日天氣不錯。")

    if not st.session_state.wardrobe:
        st.info("👈 左側點擊「選擇圖片」來豐富你的衣櫃吧！")
    else:
        # 篩選器
        all_cats = list(set([item['category'] for item in st.session_state.wardrobe]))
        selected_cats = st.multiselect("🔍 篩選", all_cats, placeholder="顯示全部")
        
        display_items = [item for item in st.session_state.wardrobe if item['category'] in selected_cats] if selected_cats else st.session_state.wardrobe
            
        # 顯示網格 (5 columns)
        cols = st.columns(5)
        for i, item in enumerate(display_items):
            with cols[i % 5]:
                # 圖片
                st.image(item['image'], use_column_width=True)
                
                # 按鈕區 (置中、無框、緊湊)
                # 使用 nested columns 來控制按鈕位置
                b_col1, b_col2, b_col3 = st.columns([1, 1, 1])
                with b_col2: # 放在中間
                    # 這裡放兩個按鈕在同一格其實很難置中，所以我們用 CSS 控制
                    # 我們將兩個按鈕分開 columns 放，盡量靠近
                    pass
                
                # 重新排版按鈕：使用兩個極窄的 column 在中間
                btn_c1, btn_c2 = st.columns([1, 1])
                with btn_c1:
                    # 編輯按鈕
                    icon = "📝" if st.session_state.edit_modes.get(item['id'], False) else "✏️"
                    if st.button(icon, key=f"edit_{item['id']}"):
                        st.session_state.edit_modes[item['id']] = not st.session_state.edit_modes.get(item['id'], False)
                        st.rerun()
                with btn_c2:
                    # 刪除按鈕
                    if st.button("🗑️", key=f"del_{item['id']}"):
                        st.session_state.wardrobe.remove(item)
                        if item['id'] in st.session_state.edit_modes: del st.session_state.edit_modes[item['id']]
                        st.rerun()

                # 編輯模式 (上中下排列，根據分類顯示不同欄位)
                if st.session_state.edit_modes.get(item['id'], False):
                    with st.container():
                        st.markdown("---")
                        # 修改分類
                        new_cat = st.selectbox("分類", cat_options, index=cat_options.index(item['category']) if item['category'] in cat_options else 0, key=f"cat_{item['id']}")
                        if new_cat != item['category']:
                            item['category'] = new_cat
                            st.rerun()
                        
                        # 智能欄位顯示
                        # 如果是上衣/外套/連身裙 -> 顯示 衣長、衣闊
                        if any(x in item['category'] for x in ["上衣", "外套", "連身裙"]):
                            item['size_data']['length'] = st.text_input("衣長 (cm)", value=item['size_data']['length'], key=f"l_{item['id']}")
                            item['size_data']['width'] = st.text_input("衣闊/胸寬 (cm)", value=item['size_data']['width'], key=f"w_{item['id']}")
                        
                        # 如果是下身 -> 顯示 褲長/裙長、腰圍
                        elif any(x in item['category'] for x in ["下身", "褲", "裙"]):
                            item['size_data']['length'] = st.text_input("褲/裙長 (cm)", value=item['size_data']['length'], key=f"l_{item['id']}")
                            item['size_data']['waist'] = st.text_input("腰圍 (吋/cm)", value=item['size_data']['waist'], key=f"wa_{item['id']}")
                        
                        # 其他 (鞋/袋) -> 顯示 備註
                        else:
                            item['size_data']['width'] = st.text_input("備註/尺碼", value=item['size_data']['width'], key=f"w_{item['id']}")
                        
                        st.markdown("---")

with tab2:
    st.subheader(f"✨ 莫弈: 早安，{p['name']}")
    
    # 這裡可以簡單顯示當前設定的環境
    st.caption(f"📍 {p['location']} | 🌡️ {st.session_state.get('last_temp', '未設定')}°C")

    col_w1, col_w2, col_w3 = st.columns(3)
    with col_w1: weather = st.text_input("天氣", "晴朗")
    with col_w2: temp = st.text_input("氣溫 (°C)", "24")
    with col_w3: occasion = st.text_input("場合", "約會")
    
    # 記住上次輸入的溫度方便顯示
    if temp: st.session_state['last_temp'] = temp

    if st.button("🪄 請求建議", type="primary"):
        if len(st.session_state.wardrobe) < 2:
            st.warning("衣櫃太少衫啦，加入多啲先啦！")
        else:
            with st.spinner("莫弈正在思考..."):
                try:
                    # 構建 Prompt
                    user_info = f"名稱:{p['name']}, 性別:{p['gender']}, 身高:{p['height']}cm, 三圍:{p['measurements']['bust']}/{p['measurements']['waist']}/{p['measurements']['hips']}"
                    
                    prompt = (
                        f"你現在是「莫弈」，用戶 {p['name']} 的專屬形象設計師。\n"
                        f"【用戶檔案】{user_info}。\n"
                        f"【風格偏好】{p['style_pref']}。\n"
                        f"【今日情報】地點:{p['location']}, 天氣:{weather}, 氣溫:{temp}°C, 場合:{occasion}。\n\n"
                        f"【任務】\n"
                        f"請從衣櫃中搭配一套造型。打招呼時請用「Hi {p['name']}」開頭，並加入對 {p['location']} 天氣的關懷。\n"
                        f"語氣要優雅、沉穩、帶有磁性，像一位紳士在給予專業建議。\n"
                    )
                    
                    inputs = [prompt]
                    items_to_send = display_items if 'display_items' in locals() and display_items else st.session_state.wardrobe

                    for i, item in enumerate(items_to_send):
                        # 根據不同分類傳送不同尺碼資料
                        s = item['size_data']
                        size_str = ""
                        if 'length' in s and s['length']: size_str += f"長:{s['length']} "
                        if 'width' in s and s['width']: size_str += f"闊:{s['width']} "
                        if 'waist' in s and s['waist']: size_str += f"腰:{s['waist']} "
                        
                        inputs.append(f"#{i+1}[{item['category']}] {size_str}")
                        inputs.append(item['image'])
                    
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    response = model.generate_content(inputs)
                    st.markdown(response.text)
                except Exception as e:
                    st.error(f"發生意外: {e}")
