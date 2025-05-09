# modules/dashboard.py

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
from modules import supabase_db as db
from modules import utils

def show():
    st.markdown("<h2>ダッシュボード</h2>", unsafe_allow_html=True)

    today = datetime.today()
    col1, col2 = st.columns(2)

    with col1:
        category = st.selectbox(
            "カテゴリを選択",
            ["全体合計", "カフェ合計", "ランチ", "ディナー", "ベーグル"],
            key="dashboard_category"
        )

    with col2:
        period_option = st.selectbox(
            "グラフ表示期間",
            ["今月", "先月", "直近3ヶ月", "直近1年", "全体", "任意期間"],
            key="dashboard_period"
        )

    st.markdown("<h3>年間目標達成率（選択したカテゴリ）</h3>", unsafe_allow_html=True)

    sales_data = db.fetch_sales_data(year=today.year)
    sales_df = pd.DataFrame(sales_data)
    if sales_df.empty:
        st.info("⚠️ 売上データが存在しません。")
        return

    sales_df["date"] = pd.to_datetime(sales_df["date"])
    sales_df = sales_df.sort_values("date")

    if category == "全体合計":
        df_filtered = sales_df[sales_df["category"].isin(["カフェ合計", "ベーグル"])]
    elif category == "ディナー":
        df_cafe = sales_df[sales_df["category"] == "カフェ合計"]
        df_lunch = sales_df[sales_df["category"] == "ランチ"]
        df_merged = pd.merge(df_cafe, df_lunch, on="date", suffixes=("_cafe", "_lunch"))
        df_filtered = pd.DataFrame()
        df_filtered["date"] = df_merged["date"]
        df_filtered["actual_sales"] = df_merged["actual_sales_cafe"] - df_merged["actual_sales_lunch"]
    else:
        df_filtered = sales_df[sales_df["category"] == category]

    if df_filtered.empty:
        st.info("⚠️ 選択カテゴリにデータがありません。")
        return

    last_date = df_filtered["date"].max().strftime("%Y-%m-%d")
    start_of_year = datetime(today.year, 1, 1).strftime("%Y-%m-%d")

    # --- 実績合計の計算 ---
    actual_total = df_filtered[
        (df_filtered["date"] >= start_of_year) & (df_filtered["date"] <= last_date)
    ]["actual_sales"].sum()

    # --- 目標売上の取得 ---
    targets = db.fetch_targets(year=today.year, category=category)
    targets_df = pd.DataFrame(targets)
    targets_df["date"] = pd.to_datetime(targets_df["date"])
    targets_total = targets_df[
        (targets_df["date"] >= start_of_year) & (targets_df["date"] <= last_date)
    ]["target_sales"].sum()

    if targets_total > 0:
        achievement = round(actual_total * 100 / targets_total, 2)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("達成率", f"{achievement:.2f}%")
        with col2:
            st.metric("年間目標", f"¥{int(targets_total):,}")
        with col3:
            st.metric("実績合計", f"¥{int(actual_total):,}")
    else:
        st.info("⚠️ 目標が設定されていません。")

    # --- グラフ用日付選択 ---
    timeframe_options = {
        "今月": (datetime(today.year, today.month, 1), today),
        "先月": (
            datetime(today.year, today.month - 1, 1) if today.month > 1 else datetime(today.year - 1, 12, 1),
            datetime(today.year, today.month, 1) - timedelta(days=1)
        ),
        "直近3ヶ月": (today - timedelta(days=90), today),
        "直近1年": (today - timedelta(days=365), today),
        "全体": (datetime(2024, 1, 1), today)
    }

    if period_option == "任意期間":
        col1, col2 = st.columns(2)
        start_date = col1.date_input("開始日", value=today - timedelta(days=30))
        end_date = col2.date_input("終了日", value=today)
        start_date = datetime.combine(start_date, datetime.min.time())
        end_date = datetime.combine(end_date, datetime.max.time())
    else:
        start_date, end_date = timeframe_options[period_option]

    df = sales_df.copy()
    df["customer_count"] = df["customer_count"].apply(utils.safe_convert_to_int)
    df = df[(df["date"] >= start_date) & (df["date"] <= end_date)]

    if category == "全体合計":
        df = df[df["category"].isin(["カフェ合計", "ベーグル"])]
        summary = df.groupby("date").agg({"actual_sales": "sum", "customer_count": "sum"}).reset_index()
    elif category == "ディナー":
        cafe = df[df["category"] == "カフェ合計"].set_index("date")
        lunch = df[df["category"] == "ランチ"].set_index("date")
        combined = pd.DataFrame()
        combined["actual_sales"] = cafe["actual_sales"] - lunch["actual_sales"]
        combined["customer_count"] = cafe["customer_count"] - lunch["customer_count"]
        combined = combined.reset_index()
        summary = combined
    else:
        df = df[df["category"] == category]
        summary = df.groupby("date").agg({"actual_sales": "sum", "customer_count": "sum"}).reset_index()

    summary["unit_price"] = summary["actual_sales"] / summary["customer_count"]
    summary["date"] = summary["date"].dt.strftime("%Y/%m/%d")

    yaxis_limits = {
        "全体合計": {"売上": 1200000, "客数": 900, "客単価": 4000},
        "ランチ": {"売上": 700000, "客数": 300, "客単価": 2500},
        "ディナー": {"売上": 500000, "客数": 150, "客単価": 4500},
        "ベーグル": {"売上": 70000, "客数": 50, "客単価": 2500},
        "カフェ合計": {"売上": 1000000, "客数": 500, "客単価": 3000}
    }

    limits = yaxis_limits.get(category, {"売上": None, "客数": None, "客単価": None})

    fig_sales = px.line(summary, x="date", y="actual_sales", title="売上推移", labels={"actual_sales": "売上（円）"})
    fig_sales.update_traces(mode="lines+markers")
    fig_sales.update_layout(yaxis=dict(range=[0, limits["売上"]]), xaxis_title="日付")
    fig_sales.update_yaxes(tickformat=",")
    st.plotly_chart(fig_sales, use_container_width=True)

    fig_customers = px.line(summary, x="date", y="customer_count", title="客数推移", labels={"customer_count": "客数（人）"})
    fig_customers.update_traces(mode="lines+markers")
    fig_customers.update_layout(yaxis=dict(range=[0, limits["客数"]]), xaxis_title="日付")
    st.plotly_chart(fig_customers, use_container_width=True)

    fig_unit = px.line(summary, x="date", y="unit_price", title="客単価推移", labels={"unit_price": "客単価（円）"})
    fig_unit.update_traces(mode="lines+markers")
    fig_unit.update_layout(yaxis=dict(range=[0, limits["客単価"]]), xaxis_title="日付")
    fig_unit.update_yaxes(tickformat=",")
    st.plotly_chart(fig_unit, use_container_width=True)
