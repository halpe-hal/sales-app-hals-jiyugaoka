# modules/dashboard.py（新店舗版：sales-app と同一仕様）

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from modules import supabase_db as db
from modules import utils


def _fetch_sales_multi_year(years: list[int]) -> pd.DataFrame:
    frames = []
    for y in years:
        data = db.fetch_sales_data(year=y)
        df = pd.DataFrame(data)
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    df_all = pd.concat(frames, ignore_index=True)
    df_all["date"] = pd.to_datetime(df_all["date"])
    return df_all.sort_values("date")


def _fetch_targets_multi_year(years: list[int]) -> pd.DataFrame:
    frames = []
    for y in years:
        data = db.fetch_targets(year=y)
        df = pd.DataFrame(data)
        if not df.empty:
            frames.append(df)
    if not frames:
        return pd.DataFrame()
    df_all = pd.concat(frames, ignore_index=True)
    df_all["date"] = pd.to_datetime(df_all["date"])
    return df_all.sort_values("date")


def _build_summary(df_source: pd.DataFrame) -> pd.DataFrame:
    """
    新店舗版はカテゴリ分岐なし：
    日次で store_sales / actual_sales / customer_count を集計して unit_price を計算
    """
    if df_source.empty:
        return pd.DataFrame()

    df = df_source.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["customer_count"] = df["customer_count"].apply(utils.safe_convert_to_int)

    summary = df.groupby("date").agg({
        "store_sales": "sum",
        "actual_sales": "sum",
        "customer_count": "sum"
    }).reset_index()

    if summary.empty:
        return pd.DataFrame()

    # 客単価 = 店舗売上 ÷ 客数
    summary["unit_price"] = summary.apply(
        lambda r: r["store_sales"] / r["customer_count"] if r["customer_count"] else 0,
        axis=1
    )
    summary["date"] = pd.to_datetime(summary["date"])
    return summary.sort_values("date")


def _render_kpi(actual_total: float, target_total: float, title_prefix: str = ""):
    if target_total > 0:
        achievement = round(actual_total * 100 / target_total, 2)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(f"{title_prefix}達成率", f"{achievement:.2f}%")
        with col2:
            st.metric(f"{title_prefix}目標", f"¥{int(target_total):,}")
        with col3:
            st.metric(f"{title_prefix}実績", f"¥{int(actual_total):,}")
    else:
        st.info("目標が設定されていません。")


def show():
    st.markdown("<h2>ダッシュボード</h2>", unsafe_allow_html=True)

    today = datetime.today()
    current_year = today.year
    year_candidates = list(range(current_year, current_year - 6, -1))

    selected_year = st.selectbox(
        "表示年",
        year_candidates,
        index=0,
        key="dashboard_selected_year"
    )

    show_dashboard("HAL'S BAGEL. 自由が丘店", selected_year)


def show_dashboard(name: str, selected_year: int):
    st.markdown(f"<h3>{name} の年間目標達成率</h3>", unsafe_allow_html=True)

    # --- 年間（選択年）データ ---
    sales_year_df = _fetch_sales_multi_year([selected_year])
    if sales_year_df.empty:
        st.info("売上データが存在しません。")
        return

    year_summary = _build_summary(sales_year_df)
    if year_summary.empty:
        st.info("該当するデータがありません。")
        return

    start_of_year_dt = datetime(selected_year, 1, 1)
    end_of_year_dt = datetime(selected_year, 12, 31, 23, 59, 59)

    # その年のデータ最終日を基準日（途中まででも自然）
    last_data_dt = year_summary["date"].max()
    base_end_dt = min(last_data_dt, end_of_year_dt)

    actual_year_total = year_summary[
        (year_summary["date"] >= start_of_year_dt) & (year_summary["date"] <= base_end_dt)
    ]["actual_sales"].sum()

    targets_year_df = _fetch_targets_multi_year([selected_year])
    if targets_year_df.empty:
        target_year_total = 0
    else:
        target_year_total = targets_year_df[
            (targets_year_df["date"] >= start_of_year_dt) & (targets_year_df["date"] <= base_end_dt)
        ]["target_sales"].sum()

    _render_kpi(actual_year_total, target_year_total, title_prefix="年間")

    # ============================================================
    # 期間タブ：1月〜12月 + 任意期間（全体タブなし）
    # 任意期間は年跨ぎOK（必要年を複数fetchして結合）
    # ============================================================
    tab_names = [f"{m}月" for m in range(1, 13)] + ["任意期間"]
    tf_tabs = st.tabs(tab_names)

    default_free_start = (base_end_dt - timedelta(days=30)).date()
    default_free_end = base_end_dt.date()

    for i, t in enumerate(tf_tabs):
        with t:
            label = tab_names[i]

            # --- 期間決定 ---
            if label.endswith("月"):
                month = int(label.replace("月", ""))

                start_date = datetime(selected_year, month, 1)
                if month == 12:
                    end_date = datetime(selected_year, 12, 31, 23, 59, 59)
                else:
                    end_date = datetime(selected_year, month + 1, 1) - timedelta(seconds=1)

                # 選択年が途中までなら基準日で頭打ち
                end_date = min(end_date, base_end_dt)
                if end_date < start_date:
                    st.info("該当するデータがありません。")
                    continue

                df_source = sales_year_df.copy()
                targets_source = targets_year_df.copy()
                kpi_title_prefix = f"{month}月"

            else:
                col1, col2 = st.columns(2)
                free_start = col1.date_input(
                    "開始日",
                    value=default_free_start,
                    key=f"free_start_{selected_year}"
                )
                free_end = col2.date_input(
                    "終了日",
                    value=default_free_end,
                    key=f"free_end_{selected_year}"
                )

                start_date = datetime.combine(free_start, datetime.min.time())
                end_date = datetime.combine(free_end, datetime.max.time())

                if end_date < start_date:
                    st.info("終了日は開始日以降にしてください。")
                    continue

                years_needed = list(range(start_date.year, end_date.year + 1))
                df_source = _fetch_sales_multi_year(years_needed)
                targets_source = _fetch_targets_multi_year(years_needed)
                kpi_title_prefix = "期間"

            if df_source.empty:
                st.info("該当するデータがありません。")
                continue

            # --- 期間サマリー ---
            df_period = df_source.copy()
            df_period["date"] = pd.to_datetime(df_period["date"])
            df_period = df_period[(df_period["date"] >= start_date) & (df_period["date"] <= end_date)]

            summary = _build_summary(df_period)
            if summary.empty:
                st.info("該当するデータがありません。")
                continue

            # --- 月（期間）KPI ---
            actual_total = summary["actual_sales"].sum()

            if targets_source.empty:
                target_total = 0
            else:
                target_total = targets_source[
                    (targets_source["date"] >= start_date) & (targets_source["date"] <= end_date)
                ]["target_sales"].sum()

            _render_kpi(actual_total, target_total, title_prefix=f"{kpi_title_prefix} ")

            # --- 表示用整形 ---
            summary_display = summary.copy()
            summary_display["date"] = summary_display["date"].dt.strftime("%Y/%m/%d")

            # --- グラフ ---
            fig_sales = px.line(
                summary_display, x="date", y="actual_sales",
                title="売上推移", labels={"actual_sales": "売上（円）"}
            )
            fig_sales.update_traces(mode="lines+markers")
            fig_sales.update_layout(xaxis_title="日付")
            fig_sales.update_yaxes(tickformat=",")
            st.plotly_chart(
                fig_sales,
                use_container_width=True,
                key=f"sales_chart_{selected_year}_{label}_{start_date.year}_{end_date.year}"
            )

            fig_customers = px.line(
                summary_display, x="date", y="customer_count",
                title="客数推移", labels={"customer_count": "客数（人）"}
            )
            fig_customers.update_traces(mode="lines+markers")
            fig_customers.update_layout(xaxis_title="日付")
            st.plotly_chart(
                fig_customers,
                use_container_width=True,
                key=f"customers_chart_{selected_year}_{label}_{start_date.year}_{end_date.year}"
            )

            fig_unit = px.line(
                summary_display, x="date", y="unit_price",
                title="客単価推移", labels={"unit_price": "客単価（円）"}
            )
            fig_unit.update_traces(mode="lines+markers")
            fig_unit.update_layout(xaxis_title="日付")
            fig_unit.update_yaxes(tickformat=",")
            st.plotly_chart(
                fig_unit,
                use_container_width=True,
                key=f"unit_price_chart_{selected_year}_{label}_{start_date.year}_{end_date.year}"
            )
