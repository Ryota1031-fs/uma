"""競馬予想の画面（Streamlit）。  起動: streamlit run app.py"""
import hmac

import streamlit as st

st.set_page_config(page_title="競馬予想", page_icon="🏇", layout="wide")


def _password() -> str:
    """Web版の管理画面（Secrets）に app_password があれば、それを知っている人だけが見られる。PC版では空。"""
    try:
        return st.secrets.get("app_password", "")
    except Exception:  # Secrets が未設定
        return ""


pw = _password()
if pw and not st.session_state.get("unlocked"):
    st.markdown("### 🏇 競馬予想")
    typed = st.text_input("パスワード", type="password")
    if typed and hmac.compare_digest(typed, pw):
        st.session_state["unlocked"] = True
        st.rerun()
    elif typed:
        st.error("パスワードが違います。")
    st.stop()

st.navigation([
    st.Page("views/yosou.py", title="予想", icon="🏇", default=True),
    st.Page("views/guide.py", title="見方ガイド", icon="📖"),
]).run()
