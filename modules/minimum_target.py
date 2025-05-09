# modules/minimum_target.py

import streamlit as st
import pandas as pd
import calendar
from datetime import datetime
from modules import supabase_db as db

def show():
    st.markdown("<h2>最低目標の設定</h2>", unsafe_allow_html=True)

    # 管理者チェック
    if st.session_state["user"]["email"] not in ["nishimura@kklia.com"]:
        st.warning("この画面にはアクセスできません。")
        st.stop()

    today = datetime.today()
    selected_year = st.selectbox("年を選択", list(range(2024, 2101)),
                                 index=list(range(2024, 2101)).index(today.year), key="min_goal_year")

    # --- 実績売上の取得（対象カテゴリ：カフェ合計・ベーグル） ---
    sales = db.fetch_sales_data(year=selected_year)
    df_sales = pd.DataFrame(sales)
    if not df_sales.empty:
        df_sales = df_sales[df_sales["category"].isin(["カフェ合計", "ベーグル"])]
        df_sales["month"] = pd.to_datetime(df_sales["date"]).dt.month
        df_sales_grouped = df_sales.groupby("month")["actual_sales"].sum().reset_index()
        df_sales_grouped.rename(columns={"actual_sales": "total_actual"}, inplace=True)
    else:
        df_sales_grouped = pd.DataFrame(columns=["month", "total_actual"])

    # --- 最低目標データの取得 ---
    df_min = pd.DataFrame(db.fetch_minimum_targets())
    if not df_min.empty:
        df_min["month"] = df_min["month"].astype(int)
    else:
        df_min = pd.DataFrame(columns=["month", "min_sales"])

    # --- 実績と目標をマージ ---
    df_merged = pd.merge(df_min, df_sales_grouped, on="month", how="left")
    df_merged["total_actual"] = df_merged["total_actual"].fillna(0)

    # --- 各月の貯金額（当月までに確定済みの月のみ） ---
    savings_rows = []
    savings_total = 0

    for _, row in df_merged.iterrows():
        m = int(row['month'])
        last_day = calendar.monthrange(selected_year, m)[1]
        cutoff = datetime(selected_year, m, last_day)
        if today >= cutoff:
            savings = row['total_actual'] - row['min_sales']
            savings_total += savings
            savings_rows.append({
                "月": f"{m}月",
                "実績": f"¥{int(row['total_actual']):,}",
                "最低目標": f"¥{int(row['min_sales']):,}",
                "貯金額": f"¥{int(savings):,}"
            })

    # --- 表示：貯金額一覧 + 合計 ---
    if savings_rows:
        st.markdown("<h3>各月の貯金額</h3>", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(savings_rows), use_container_width=True)
        st.markdown(f"<div style='text-align: right; font-weight: bold;'>💡 合計貯金額: ¥{int(savings_total):,}</div>", unsafe_allow_html=True)
    else:
        st.info("まだ締めた月がないため貯金額は計算できません。")

    # --- 最低目標の登録フォーム ---
    st.subheader("月別最低目標設定")
    month = st.selectbox("月", list(range(1, 13)), format_func=lambda m: f"{m}月", key="min_goal_month")
    min_goal = st.number_input("最低目標売上 (円)", min_value=0, step=1000)

    # --- 保存ボタン（右寄せ）
    with st.container():
        col_space, col_btn = st.columns([9, 1])
        with col_btn:
            if st.button("保存"):
                db.insert_minimum_target(month, min_goal)
                st.success(f"{month}月の最低目標を ¥{min_goal:,} として保存しました")
                st.rerun()

    # --- 設定済みの最低目標一覧 ---
    st.subheader("設定済みの最低目標一覧")
    df_min = pd.DataFrame(db.fetch_minimum_targets())
    if not df_min.empty:
        df_min["月"] = df_min["month"].astype(int).apply(lambda m: f"{m}月")
        df_min["最低目標"] = df_min["min_sales"].apply(lambda x: f"¥{int(x):,}")
        st.dataframe(df_min[["月", "最低目標"]], use_container_width=True)
        total_min = df_min["min_sales"].sum()
        st.markdown(f"<div style='text-align: right; font-weight: bold;'>✅ 最低目標の合計額: ¥{int(total_min):,}</div>", unsafe_allow_html=True)
