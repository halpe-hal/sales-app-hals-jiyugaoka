# modules/sales_list.py（カテゴリなし版）

import streamlit as st
import pandas as pd
import math
from collections import defaultdict
from datetime import datetime
import jpholiday
from modules import utils
from modules import supabase_db as db

def show():
    st.markdown("<h2>売上一覧</h2>", unsafe_allow_html=True)

    # --- 年選択のみ ---
    year = st.selectbox("年", list(range(2024, 2101)),
                        index=list(range(2024, 2101)).index(datetime.now().year),
                        key="year_common")

    # --- 表示モードをタブで切り替え（日別・月別） ---
    tabs = st.tabs(["日別", "月別"])

    with tabs[0]:  # 日別
        month_tabs = st.tabs([f"{m}月" for m in range(1, 13)])
        for i, m in enumerate(range(1, 13)):
            with month_tabs[i]:
                show_daily_supabase(year, m)

    with tabs[1]:  # 月別
        show_monthly_supabase(year)


# --- Supabase対応版：日別表示 ---
def show_daily_supabase(year, month):
    sales_data = db.fetch_sales_data(year, month)
    targets_data = db.fetch_targets(year, month)
    prev_sales_data = db.fetch_sales_data(year - 1, month)

    sales_df = pd.DataFrame(sales_data)
    targets_df = pd.DataFrame(targets_data)

    if sales_df.empty:
        st.info("該当するデータがありません。")
        return

    sales_df["date"] = pd.to_datetime(sales_df["date"])
    targets_df["date"] = pd.to_datetime(targets_df["date"])

    # 前年データを日→実績のdictに変換
    prev_actual_by_day = {}
    if prev_sales_data:
        prev_df = pd.DataFrame(prev_sales_data)
        prev_df["date"] = pd.to_datetime(prev_df["date"])
        for prev_dt, grp in prev_df.groupby(prev_df["date"].dt.day):
            prev_actual_by_day[prev_dt] = grp["actual_sales"].sum()

    # --- CSVダウンロード用データ作成 ---
    export_df = sales_df.copy()
    export_df["date"] = export_df["date"].dt.strftime("%Y/%m/%d")
    export_df["客単価"] = export_df.apply(
        lambda r: r["store_sales"] / r["customer_count"] if r["customer_count"] else 0, axis=1
    )
    export_df["客単価"] = export_df["客単価"].fillna(0).round(0).astype(int)

    csv = export_df.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        label="📥 CSVダウンロード（日別）",
        data=csv,
        file_name=f"{year}_{month:02d}_daily.csv",
        mime="text/csv"
    )

    rows = []
    totals = defaultdict(float)

    for dt in sorted(sales_df["date"].dt.date.unique()):
        d = pd.to_datetime(dt)

        daily_df = sales_df[sales_df["date"].dt.date == d.date()]
        target_df = targets_df[targets_df["date"].dt.date == d.date()]

        actual = daily_df["actual_sales"].sum()
        store = daily_df["store_sales"].sum()
        delivery = daily_df["delivery_sales"].sum()
        other = daily_df["other_sales"].sum()
        cust = daily_df["customer_count"].sum()
        target = target_df["target_sales"].sum() if not target_df.empty else None

        achievement = round(actual * 100 / target, 2) if target else None
        unit_price = store / cust if cust else None

        prev_actual = prev_actual_by_day.get(d.day)
        yoy = round(actual * 100 / prev_actual, 2) if prev_actual else None

        totals["target"] += target if target else 0
        totals["actual"] += actual
        totals["store"] += store
        totals["delivery"] += delivery
        totals["other"] += other
        totals["cust"] += utils.safe_convert_to_int(cust)
        totals["prev_actual"] += prev_actual if prev_actual else 0

        weekday_jp = d.strftime('%a')
        weekday_jp = {"Mon": "月", "Tue": "火", "Wed": "水", "Thu": "木",
                      "Fri": "金", "Sat": "土", "Sun": "日"}.get(weekday_jp, weekday_jp)
        if weekday_jp in ["土", "日"] or jpholiday.is_holiday(d):
            weekday_jp = f"<span style='color: red'>{weekday_jp}</span>"

        rows.append({
            "日付": d.strftime("%Y/%m/%d"),
            "曜日": weekday_jp,
            "目標達成率": format_achievement(achievement),
            "前年比": format_achievement(yoy),
            "目標売上": format_currency(target),
            "実績": format_currency(actual),
            "店舗売上": format_currency(store),
            "デリバリー売上": format_currency(delivery),
            "その他売上": format_currency(other),
            "客数": format_count(cust),
            "客単価": format_currency(unit_price)
        })

    # --- 合計行 ---
    total_yoy = round(totals["actual"] * 100 / totals["prev_actual"], 2) if totals["prev_actual"] else None
    summary = {
        "日付": "<b>合計</b>",
        "曜日": "",
        "目標達成率": format_achievement(
            totals["actual"] * 100 / totals["target"]
        ) if totals["target"] else "",
        "前年比": format_achievement(total_yoy),
        "目標売上": f"<b>{int(totals['target']):,}円</b>" if totals["target"] else "",
        "実績": f"<b>{int(totals['actual']):,}円</b>",
        "店舗売上": f"<b>{int(totals['store']):,}円</b>",
        "デリバリー売上": f"<b>{int(totals['delivery']):,}円</b>",
        "その他売上": f"<b>{int(totals['other']):,}円</b>",
        "客数": f"<b>{int(totals['cust']):,}人</b>",
        "客単価": f"<b>{int(totals['store'] / totals['cust']) if totals['cust'] else 0:,}円</b>"
    }

    df_result = pd.DataFrame([summary] + rows)
    render_styled_table(df_result)


# --- Supabase対応：月別表示 ---
def show_monthly_supabase(year):
    sales_data = db.fetch_sales_data(year=year)
    targets_data = db.fetch_targets(year=year)
    prev_sales_data = db.fetch_sales_data(year=year - 1)

    sales_df = pd.DataFrame(sales_data)
    targets_df = pd.DataFrame(targets_data)

    if sales_df.empty:
        st.info("該当するデータがありません。")
        return

    sales_df["date"] = pd.to_datetime(sales_df["date"])
    sales_df["month"] = sales_df["date"].dt.month
    sales_df["customer_count"] = sales_df["customer_count"].apply(utils.safe_convert_to_int)

    df_grouped = sales_df.groupby("month").agg({
        "store_sales": "sum",
        "delivery_sales": "sum",
        "other_sales": "sum",
        "actual_sales": "sum",
        "customer_count": "sum"
    }).reset_index()

    targets_df["month"] = pd.to_datetime(targets_df["date"]).dt.month
    target_grouped = targets_df.groupby("month").agg({"target_sales": "sum"}).reset_index()

    # 前年月別実績
    prev_actual_by_month = {}
    if prev_sales_data:
        prev_df = pd.DataFrame(prev_sales_data)
        prev_df["month"] = pd.to_datetime(prev_df["date"]).dt.month
        prev_grouped = prev_df.groupby("month")["actual_sales"].sum()
        prev_actual_by_month = prev_grouped.to_dict()

    df_merged = pd.merge(df_grouped, target_grouped, on="month", how="left")
    df_merged["客単価"] = df_merged.apply(
        lambda r: r["store_sales"] / r["customer_count"] if r["customer_count"] else 0, axis=1
    )
    df_merged["目標達成率"] = df_merged.apply(
        lambda r: round(r["actual_sales"] * 100 / r["target_sales"], 2)
        if r["target_sales"] else None, axis=1
    )
    df_merged["前年比"] = df_merged.apply(
        lambda r: round(r["actual_sales"] * 100 / prev_actual_by_month[r["month"]], 2)
        if r["month"] in prev_actual_by_month and prev_actual_by_month[r["month"]] else None, axis=1
    )
    df_merged["月"] = df_merged["month"].apply(lambda m: f"{m}月")

    df_display = df_merged[["月", "目標達成率", "前年比", "target_sales", "actual_sales",
                           "store_sales", "delivery_sales", "other_sales", "customer_count", "客単価"]]
    df_display = df_display.rename(columns={
        "target_sales": "目標売上",
        "actual_sales": "実績",
        "store_sales": "店舗売上",
        "delivery_sales": "デリバリー売上",
        "other_sales": "その他売上",
        "customer_count": "客数"
    })

    prev_total = sum(prev_actual_by_month.values())
    total_actual = df_display["実績"].sum()
    total_row = {
        "月": "<b>合計</b>",
        "目標達成率": format_achievement(
            total_actual * 100 / df_display["目標売上"].sum()
        ) if df_display["目標売上"].sum() else "",
        "前年比": format_achievement(
            total_actual * 100 / prev_total
        ) if prev_total else "",
        "目標売上": f"<b>{int(df_display['目標売上'].sum()):,}円</b>",
        "実績": f"<b>{int(total_actual):,}円</b>",
        "店舗売上": f"<b>{int(df_display['店舗売上'].sum()):,}円</b>",
        "デリバリー売上": f"<b>{int(df_display['デリバリー売上'].sum()):,}円</b>",
        "その他売上": f"<b>{int(df_display['その他売上'].sum()):,}円</b>",
        "客数": f"<b>{int(df_display['客数'].sum()):,}人</b>",
        "客単価": f"<b>{int(df_display['店舗売上'].sum() / df_display['客数'].sum()):,}円</b>"
        if df_display["客数"].sum() else ""
    }

    df_display = pd.concat([pd.DataFrame([total_row]), df_display], ignore_index=True)
    df_display.loc[1:, "目標達成率"] = df_display.loc[1:, "目標達成率"].apply(format_achievement)
    df_display.loc[1:, "前年比"] = df_display.loc[1:, "前年比"].apply(format_achievement)

    for col in ["目標売上", "実績", "店舗売上", "デリバリー売上", "その他売上", "客単価"]:
        df_display[col] = df_display[col].apply(
            lambda x: f"{int(x):,}円" if isinstance(x, (int, float)) and pd.notnull(x) else x
        )
    df_display["客数"] = df_display["客数"].apply(
        lambda x: f"{int(x):,}人" if isinstance(x, (int, float)) and pd.notnull(x) else x
    )

    render_styled_table(df_display)


# --- 共通関数 ---
def format_currency(x):
    return f"{int(x):,}円" if pd.notna(x) and x != "" else ""

def format_count(x):
    return f"{int(x):,}人" if pd.notna(x) and x != "" else ""

def format_achievement(x):
    try:
        x_float = float(x)
        return f"<span style='color: blue'>{x_float:.2f}%</span>" if x_float >= 100 else f"<span style='color: red'>{x_float:.2f}%</span>"
    except:
        return ""

def render_styled_table(df):
    html_table = df.to_html(escape=False, index=False)
    st.markdown(
        f"""
        <div style="overflow-x: auto; overflow-y: auto; height: 300px; border-radius:10px; border: 1px solid #efefef">
            <style>
                table {{
                    border-collapse: separate;
                    border-spacing: 0;
                }}
                th {{
                    position: sticky;
                    top: 0;
                    z-index: 2;
                    white-space: nowrap;
                    text-align :center !important;
                    background-color: #006a38;
                    color: #ffffff;
                }}
                td {{
                    white-space: nowrap;
                    text-align: right;
                    height: 50px;
                }}
                th:first-child {{
                    left: 0;
                    z-index: 3;
                    background-color: #006a38;
                    color: #ffffff;
                }}
                td:first-child {{
                    position: sticky;
                    left: 0;
                    background-color: #f0f2f6;
                    z-index: 1;
                }}
            </style>
            {html_table}
        </div>
        """,
        unsafe_allow_html=True
    )
