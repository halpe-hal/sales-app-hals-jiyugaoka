# modules/target_setting.py（段階3：Supabase対応 完全版 + 自動集計汎用化）

import streamlit as st
import pandas as pd
import calendar
from datetime import datetime, date
import jpholiday
from modules import utils
from modules import supabase_db as db

def show():
    st.markdown("<h2>売上目標の設定</h2>", unsafe_allow_html=True)

    # 管理者チェック
    if st.session_state["user"]["email"] not in ["nishimura@kklia.com"]:
        st.warning("この画面にはアクセスできません。")
        st.stop()

    current_year = datetime.now().year
    col1, col2, col3 = st.columns(3)
    with col1:
        year = st.selectbox("年", list(range(2024, 2101)), index=list(range(2024, 2101)).index(current_year))
    with col2:
        month = st.selectbox("月", list(range(1, 13)), format_func=lambda m: f"{m}月")
    with col3:
        category = st.selectbox("カテゴリ", ["全体合計", "カフェ合計", "ランチ", "ディナー", "ベーグル"])

    # --- 一括登録 ---
    if category in ["全体合計", "カフェ合計"]:
        st.info(f"{category}は自動集計のため直接編集できません。")
    else:
        st.subheader("月間一括登録（平日・休日）")
        col4, col5 = st.columns(2)
        with col4:
            weekday_target = st.number_input("平日の目標売上 (円)", 0, 2000000, step=1000)
        with col5:
            holiday_target = st.number_input("土日祝の目標売上 (円)", 0, 2000000, step=1000)

        col_space, col_btn = st.columns([8, 2])
        with col_btn:
            if st.button("一括登録（上書きあり）"):
                for day in range(1, calendar.monthrange(year, month)[1] + 1):
                    dt = date(year, month, day)
                    value = holiday_target if utils.is_holiday_or_weekend(dt) else weekday_target
                    db.upsert_target(year, month, dt.strftime("%Y-%m-%d"), category, value)
                db.update_auto_targets_in_range(year, month)
                st.success("一括登録が完了しました！")
                st.rerun()

        # --- 個別日設定 ---
        st.subheader("個別日設定")
        col6, col7 = st.columns(2)
        with col6:
            selected_date = st.date_input("対象日を選択", date(year, month, 1))
        with col7:
            individual_target = st.number_input("個別日の目標売上 (円)", 0, 2000000, step=1000)

        col_space2, col_btn2 = st.columns([8, 2])
        with col_btn2:
            if st.button("個別日を保存"):
                db.upsert_target(selected_date.year, selected_date.month, selected_date.strftime("%Y-%m-%d"), category, individual_target)
                db.update_auto_targets(selected_date)
                st.success("個別日の目標を保存しました！")
                st.rerun()

    # --- 表示 ---
    targets_data = db.fetch_targets(year, month, category)
    df = pd.DataFrame(targets_data)
    if df.empty:
        st.info("この月のデータは未設定です。")
        return

    df["date"] = pd.to_datetime(df["date"])
    target_map = {d.date(): v for d, v in zip(df["date"], df["target_sales"])}
    cal = calendar.Calendar(firstweekday=6)
    weeks = cal.monthdatescalendar(year, month)

    table = "<table style='border-collapse: collapse; width: 100%; text-align: center;'>"
    table += "<tr>" + "".join([f"<th>{d}</th>" for d in ["日", "月", "火", "水", "木", "金", "土"]]) + "</tr>"
    for week in weeks:
        table += "<tr>"
        for day in week:
            if day.month != month:
                table += "<td style='background-color: #f0f0f0;'>-</td>"
            else:
                value = f"\u00a5{int(target_map.get(day, 0)):,}" if day in target_map else "未設定"
                color = "red" if utils.is_holiday_or_weekend(day) else "black"
                table += f"<td style='padding: 4px; border: 1px solid #ddd; color: {color};'>{day.day}<br><small>{value}</small></td>"
        table += "</tr>"
    table += "</table>"
    st.markdown(table, unsafe_allow_html=True)
    st.subheader(f"月間合計目標売上: \u00a5{int(sum(target_map.values())):,}")
