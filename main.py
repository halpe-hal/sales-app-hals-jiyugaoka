# main.py

import streamlit as st
from modules import supabase_db as db, login_supabase as login, dashboard, sales_input, sales_list, target_setting, minimum_target, header, records

# --- セッション初期化 ---
if "menu" not in st.session_state:
    st.session_state["menu"] = "ダッシュボード"

# --- ログイン機能 ---
login.check_login()

# --- ヘッダー表示 ---
header.show()

# --- サイドバー作成 ---
with st.sidebar:
    st.markdown("<h4>メニューを選択</h4>", unsafe_allow_html=True)
    menus = ["ダッシュボード", "売上入力フォーム", "売上一覧", "最高記録", "売上目標設定", "最低目標設定"]

    for menu_item in menus:
        if st.button(menu_item, key=f"menu_{menu_item}"):
            st.session_state["menu"] = menu_item

    st.markdown("---")
    if st.button("🔓 ログアウト", key="logout"):
        login.logout()

# --- メニューに応じた画面表示 ---
if st.session_state["menu"] == "ダッシュボード":
    dashboard.show()
elif st.session_state["menu"] == "売上入力フォーム":
    sales_input.show()
elif st.session_state["menu"] == "売上一覧":
    sales_list.show()
elif st.session_state["menu"] == "最高記録":
    records.show()
elif st.session_state["menu"] == "売上目標設定":
    target_setting.show()
elif st.session_state["menu"] == "最低目標設定":
    minimum_target.show()

# --- CSSカスタマイズ（ボタンデザイン） ---
st.markdown(
    """
    <style>
    section[data-testid="stSidebar"] div.stButton > button {
        width: 100%;
        margin-bottom: -10px;
        border: none;
        background-color: transparent;
        color: #333;
        font-weight: bold;
        padding: 0.5em 1em;
        border-radius: 8px;
    }
    section[data-testid="stSidebar"] div.stButton > button:hover {
        background-color: #006a38;
        color: #ffffff;
        border: none;
    }
    section[data-testid="stSidebar"] div.stButton > button:focus {
        background-color: #006a38 !important;
        color: white !important;
        border: 1px solid #006a38 !important;
    }

    h4 {
        margin-top: -5%;
    }
    </style>
    """,
    unsafe_allow_html=True
)
