# modules/records.py

import streamlit as st
import pandas as pd
from modules import supabase_db as db


def show():
    st.markdown("<h2>最高記録</h2>", unsafe_allow_html=True)

    all_data = db.fetch_sales_data()
    if not all_data:
        st.info("データがありません。")
        return

    df = pd.DataFrame(all_data)
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month

    _show_annual_record(df)
    st.markdown("---")
    _show_monthly_record(df)
    st.markdown("---")
    _show_daily_record(df)


# --- 年間売上レコード ---
def _show_annual_record(df: pd.DataFrame):
    st.markdown("### 年間売上レコード")

    annual = df.groupby("year")["actual_sales"].sum().reset_index()
    annual = annual.rename(columns={"actual_sales": "年間売上"})
    annual = annual.sort_values("年間売上", ascending=False).reset_index(drop=True)

    if annual.empty:
        st.info("データがありません。")
        return

    ranking = annual.head(3).copy()
    ranking.index = ranking.index + 1
    ranking["年"] = ranking["year"].apply(lambda y: f"{y}年")
    ranking["年間売上"] = ranking["年間売上"].apply(lambda x: f"¥{int(x):,}")
    _render_table(ranking[["年", "年間売上"]])


# --- 単月売上レコード ---
def _show_monthly_record(df: pd.DataFrame):
    st.markdown("### 単月売上レコード")

    df["year_month"] = df["date"].dt.to_period("M")
    monthly = df.groupby("year_month")["actual_sales"].sum().reset_index()
    monthly = monthly.rename(columns={"actual_sales": "月間売上"})
    monthly = monthly.sort_values("月間売上", ascending=False).reset_index(drop=True)

    if monthly.empty:
        st.info("データがありません。")
        return

    ranking = monthly.head(3).copy()
    ranking.index = ranking.index + 1
    ranking["年月"] = ranking["year_month"].apply(str)
    ranking["月間売上"] = ranking["月間売上"].apply(lambda x: f"¥{int(x):,}")
    _render_table(ranking[["年月", "月間売上"]])


# --- 単日売上レコード ---
def _show_daily_record(df: pd.DataFrame):
    st.markdown("### 単日売上レコード")
    st.caption("※ 店舗売上が0円の日を除く / 「その他売上」を含まない金額")

    # 店舗売上が0の日を除外し、店舗売上＋デリバリー売上を集計
    daily = df[df["store_sales"] > 0].copy()
    daily["日別売上"] = daily["store_sales"] + daily["delivery_sales"]

    daily_grouped = daily.groupby("date").agg(
        store_sales=("store_sales", "sum"),
        delivery_sales=("delivery_sales", "sum"),
        日別売上=("日別売上", "sum")
    ).reset_index()

    # 集計後も store_sales > 0 を保証
    daily_grouped = daily_grouped[daily_grouped["store_sales"] > 0]
    daily_grouped = daily_grouped.sort_values("日別売上", ascending=False).reset_index(drop=True)

    if daily_grouped.empty:
        st.info("データがありません。")
        return

    ranking = daily_grouped.head(3).copy()
    ranking.index = ranking.index + 1
    ranking["日付"] = ranking["date"].dt.strftime("%Y/%m/%d")
    ranking["店舗売上"] = ranking["store_sales"].apply(lambda x: f"¥{int(x):,}")
    ranking["デリバリー売上"] = ranking["delivery_sales"].apply(lambda x: f"¥{int(x):,}")
    ranking["合計（その他除く）"] = ranking["日別売上"].apply(lambda x: f"¥{int(x):,}")
    _render_table(ranking[["日付", "店舗売上", "デリバリー売上", "合計（その他除く）"]])


def _render_table(df: pd.DataFrame):
    html_table = df.to_html(escape=False)
    st.markdown(
        f"""
        <div style="overflow-x: auto; border-radius:10px; border: 1px solid #efefef; margin-bottom: 1em;">
            <style>
                table {{
                    border-collapse: separate;
                    border-spacing: 0;
                    width: 100%;
                }}
                th {{
                    position: sticky;
                    top: 0;
                    z-index: 2;
                    white-space: nowrap;
                    text-align: center !important;
                    background-color: #006a38;
                    color: #ffffff;
                    padding: 8px 12px;
                }}
                td {{
                    white-space: nowrap;
                    text-align: right;
                    padding: 6px 12px;
                }}
                td:first-child {{
                    text-align: center;
                    background-color: #f0f2f6;
                    font-weight: bold;
                }}
                th:first-child {{
                    text-align: center;
                    background-color: #006a38;
                }}
            </style>
            {html_table}
        </div>
        """,
        unsafe_allow_html=True
    )
