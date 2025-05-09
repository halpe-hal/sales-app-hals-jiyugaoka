# modules/sales_list.py

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

    view_mode = st.selectbox("表示モード", ["日別", "月別"], key="view_mode")

    if view_mode == "日別":
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            year = st.selectbox("年", list(range(2024, 2101)), index=list(range(2024, 2101)).index(datetime.now().year))
        with col2:
            month = st.selectbox("月", list(range(1, 13)), index=datetime.now().month - 1, format_func=lambda m: f"{m}月")
        with col3:
            category = st.selectbox("カテゴリ", ["全体合計", "カフェ合計", "ランチ", "ディナー", "ベーグル"])
        show_daily_supabase(year, month, category)

    elif view_mode == "月別":
        col1, col2 = st.columns(2)
        with col1:
            year = st.selectbox("年", list(range(2024, 2101)), index=list(range(2024, 2101)).index(datetime.now().year), key="monthly_year")
        with col2:
            category = st.selectbox("カテゴリ", ["全体合計", "カフェ合計", "ランチ", "ディナー", "ベーグル"], key="monthly_category")
        show_monthly_supabase(year, category)

# --- Supabase対応版：日別表示 ---
def show_daily_supabase(year, month, category):
    sales_data = db.fetch_sales_data(year, month)
    targets_data = db.fetch_targets(year, month)

    sales_df = pd.DataFrame(sales_data)
    targets_df = pd.DataFrame(targets_data)

    if sales_df.empty:
        st.info("該当するデータがありません。")
        return

    sales_df["date"] = pd.to_datetime(sales_df["date"])
    targets_df["date"] = pd.to_datetime(targets_df["date"])

    # --- CSVダウンロード用データ作成 ---
    export_df = sales_df.copy()
    export_df["date"] = pd.to_datetime(export_df["date"])
    export_df["date"] = export_df["date"].dt.strftime("%Y/%m/%d")

    if category == "ディナー":
        cafe_df = export_df[export_df["category"] == "カフェ合計"].set_index("date")
        lunch_df = export_df[export_df["category"] == "ランチ"].set_index("date")
        df = pd.DataFrame()
        df["store_sales"] = cafe_df["store_sales"] - lunch_df["store_sales"]
        df["delivery_sales"] = cafe_df["delivery_sales"] - lunch_df["delivery_sales"]
        df["other_sales"] = cafe_df["other_sales"] - lunch_df["other_sales"]
        df["actual_sales"] = cafe_df["actual_sales"] - lunch_df["actual_sales"]
        df["customer_count"] = cafe_df["customer_count"] - lunch_df["customer_count"]
        df["客単価"] = df["store_sales"] / df["customer_count"]
        df = df.reset_index()
        df["category"] = "ディナー"
        df = df[["date", "category", "store_sales", "delivery_sales", "other_sales", "actual_sales", "customer_count", "客単価"]]

    elif category == "全体合計":
        df = export_df[export_df["category"].isin(["カフェ合計", "ベーグル"])]
        df = df.groupby("date").agg({
            "store_sales": "sum",
            "delivery_sales": "sum",
            "other_sales": "sum",
            "actual_sales": "sum",
            "customer_count": "sum"
        }).reset_index()
        df["category"] = "全体合計"
        df["客単価"] = df["store_sales"] / df["customer_count"]
        df = df[["date", "category", "store_sales", "delivery_sales", "other_sales", "actual_sales", "customer_count", "客単価"]]

    else:
        df = export_df[export_df["category"] == category]
        df["客単価"] = df["store_sales"] / df["customer_count"]
        df = df[["date", "category", "store_sales", "delivery_sales", "other_sales", "actual_sales", "customer_count", "客単価"]]

    df = df.fillna(0)
    df["客単価"] = df["客単価"].round(0).astype(int)

    # CSV出力
    csv = df.to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        label="📥 CSVダウンロード（日別）",
        data=csv,
        file_name=f"{year}_{month:02d}_{category}_daily.csv",
        mime="text/csv"
    )

    def pivot(df, value):
        return df.pivot(index="date", columns="category", values=value)

    pivots = {
        col: pivot(sales_df, col)
        for col in ["actual_sales", "store_sales", "delivery_sales", "other_sales", "customer_count"]
    }
    pivot_target = pivot(targets_df, "target_sales")

    rows = []
    totals = defaultdict(float)

    for dt in sorted(sales_df["date"].dt.date.unique()):
        d = pd.to_datetime(dt)

        if category == "ディナー":
            actual = pivots["actual_sales"].at[d, "カフェ合計"] - pivots["actual_sales"].at[d, "ランチ"]
            store = pivots["store_sales"].at[d, "カフェ合計"] - pivots["store_sales"].at[d, "ランチ"]
            delivery = pivots["delivery_sales"].at[d, "カフェ合計"] - pivots["delivery_sales"].at[d, "ランチ"]
            other = pivots["other_sales"].at[d, "カフェ合計"] - pivots["other_sales"].at[d, "ランチ"]
            cust = pivots["customer_count"].at[d, "カフェ合計"] - pivots["customer_count"].at[d, "ランチ"]
        elif category == "全体合計":
            store = delivery = other = actual = cust = 0
            for col in ["カフェ合計", "ベーグル"]:
                for metric in pivots:
                    val = pivots[metric].at[d, col] if col in pivots[metric].columns and d in pivots[metric].index else 0
                    if metric == "store_sales":
                        store += val
                    elif metric == "delivery_sales":
                        delivery += val
                    elif metric == "other_sales":
                        other += val
                    elif metric == "actual_sales":
                        actual += val
                    elif metric == "customer_count":
                        cust += utils.safe_convert_to_int(val)
        else:
            actual = pivots["actual_sales"].at[d, category] if category in pivots["actual_sales"].columns else 0
            store = pivots["store_sales"].at[d, category] if category in pivots["store_sales"].columns else 0
            delivery = pivots["delivery_sales"].at[d, category] if category in pivots["delivery_sales"].columns else 0
            other = pivots["other_sales"].at[d, category] if category in pivots["other_sales"].columns else 0
            cust = pivots["customer_count"].at[d, category] if category in pivots["customer_count"].columns else 0

        target = pivot_target.at[d, category] if category in pivot_target.columns and d in pivot_target.index else None
        achievement = round(actual * 100 / target, 2) if target else None
        unit_price = store / cust if cust else None

        totals["target"] += target if target else 0
        totals["actual"] += actual
        totals["store"] += store
        totals["delivery"] += delivery
        totals["other"] += other
        totals["cust"] += utils.safe_convert_to_int(cust)

        weekday_jp = d.strftime('%a')
        weekday_jp = {"Mon": "月", "Tue": "火", "Wed": "水", "Thu": "木", "Fri": "金", "Sat": "土", "Sun": "日"}.get(weekday_jp, weekday_jp)
        if weekday_jp in ["土", "日"] or jpholiday.is_holiday(d):
            weekday_jp = f"<span style='color: red'>{weekday_jp}</span>"

        rows.append({
            "日付": d.strftime("%Y/%m/%d"),
            "曜日": weekday_jp,
            "達成率": format_achievement(achievement),
            "目標売上": format_currency(target),
            "実績": format_currency(actual),
            "店舗売上": format_currency(store),
            "デリバリー売上": format_currency(delivery),
            "その他売上": format_currency(other),
            "客数": format_count(cust),
            "客単価": format_currency(unit_price)
        })

    # NaNを明示的に0に変換
    for key in ["target", "actual", "store", "delivery", "other", "cust"]:
        if pd.isna(totals[key]):
            totals[key] = 0

    summary = {
        "日付": "<b>合計</b>",
        "曜日": "",
        "達成率": format_achievement(totals["actual"] * 100 / totals["target"]) if totals["target"] else "",
        "目標売上": f"<b>{int(totals['target']):,}円</b>",
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
def show_monthly_supabase(year, category):
    sales_data = db.fetch_sales_data(year=year)
    targets_data = db.fetch_targets(year=year)

    sales_df = pd.DataFrame(sales_data)
    targets_df = pd.DataFrame(targets_data)

    if sales_df.empty:
        st.info("該当するデータがありません。")
        return

    sales_df["date"] = pd.to_datetime(sales_df["date"])
    sales_df["month"] = sales_df["date"].dt.month
    sales_df["customer_count"] = sales_df["customer_count"].apply(utils.safe_convert_to_int)

    if category == "全体合計":
        df_filtered = sales_df[sales_df["category"].isin(["カフェ合計", "ベーグル"])]
        df_grouped = df_filtered.groupby("month").agg({
            "store_sales": "sum",
            "delivery_sales": "sum",
            "other_sales": "sum",
            "actual_sales": "sum",
            "customer_count": "sum"
        }).reset_index()
    elif category == "ディナー":
        cafe = sales_df[sales_df["category"] == "カフェ合計"]
        lunch = sales_df[sales_df["category"] == "ランチ"]
        df = pd.merge(cafe, lunch, on="date", suffixes=("_cafe", "_lunch"))
        df["month"] = df["date"].dt.month
        df["store_sales"] = df["store_sales_cafe"] - df["store_sales_lunch"]
        df["delivery_sales"] = df["delivery_sales_cafe"] - df["delivery_sales_lunch"]
        df["other_sales"] = df["other_sales_cafe"] - df["other_sales_lunch"]
        df["actual_sales"] = df["actual_sales_cafe"] - df["actual_sales_lunch"]
        df["customer_count"] = df["customer_count_cafe"] - df["customer_count_lunch"]
        df_grouped = df.groupby("month").agg({
            "store_sales": "sum",
            "delivery_sales": "sum",
            "other_sales": "sum",
            "actual_sales": "sum",
            "customer_count": "sum"
        }).reset_index()
    else:
        df_filtered = sales_df[sales_df["category"] == category]
        df_grouped = df_filtered.groupby("month").agg({
            "store_sales": "sum",
            "delivery_sales": "sum",
            "other_sales": "sum",
            "actual_sales": "sum",
            "customer_count": "sum"
        }).reset_index()

    targets_df = targets_df[targets_df["category"] == category]
    targets_df["month"] = pd.to_datetime(targets_df["date"]).dt.month
    target_grouped = targets_df.groupby("month").agg({"target_sales": "sum"}).reset_index()

    df_merged = pd.merge(df_grouped, target_grouped, on="month", how="left")
    df_merged["客単価"] = df_merged.apply(lambda r: r["store_sales"] / r["customer_count"] if r["customer_count"] else 0, axis=1)
    df_merged["達成率"] = df_merged.apply(lambda r: round(r["actual_sales"] * 100 / r["target_sales"], 2) if r["target_sales"] else None, axis=1)
    df_merged["月"] = df_merged["month"].apply(lambda m: f"{m}月")

    df_display = df_merged[["月", "達成率", "target_sales", "actual_sales", "store_sales", "delivery_sales", "other_sales", "customer_count", "客単価"]]
    df_display = df_display.rename(columns={
        "target_sales": "目標売上",
        "actual_sales": "実績",
        "store_sales": "店舗売上",
        "delivery_sales": "デリバリー売上",
        "other_sales": "その他売上",
        "customer_count": "客数"
    })

    total_row = {
        "月": "<b>合計</b>",
        "達成率": format_achievement(df_display["実績"].sum() * 100 / df_display["目標売上"].sum()) if df_display["目標売上"].sum() else "",
        "目標売上": f"<b>{int(df_display['目標売上'].sum()):,}円</b>",
        "実績": f"<b>{int(df_display['実績'].sum()):,}円</b>",
        "店舗売上": f"<b>{int(df_display['店舗売上'].sum()):,}円</b>",
        "デリバリー売上": f"<b>{int(df_display['デリバリー売上'].sum()):,}円</b>",
        "その他売上": f"<b>{int(df_display['その他売上'].sum()):,}円</b>",
        "客数": f"<b>{int(df_display['客数'].sum()):,}人</b>",
        "客単価": f"<b>{int(df_display['店舗売上'].sum() / df_display['客数'].sum()):,}円</b>" if df_display["客数"].sum() else ""
    }

    df_display = pd.concat([pd.DataFrame([total_row]), df_display], ignore_index=True)
    # 合計行以外だけ達成率にformat_achievementを適用
    df_display.loc[1:, "達成率"] = df_display.loc[1:, "達成率"].apply(format_achievement)


    for col in ["目標売上", "実績", "店舗売上", "デリバリー売上", "その他売上", "客単価"]:
        df_display[col] = df_display[col].apply(lambda x: f"{int(x):,}円" if isinstance(x, (int, float)) else x)
    df_display["客数"] = df_display["客数"].apply(lambda x: f"{int(x):,}人" if isinstance(x, (int, float)) else x)

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