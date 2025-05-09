# modules/supabase_db.py

from modules.supabase_client import supabase
from datetime import datetime, date

# --- salesテーブルの取得 ---
def fetch_sales_data(year=None, month=None, category=None):
    query = supabase.table("sales").select("*")
    if year:
        query = query.eq("year", year)
    if month:
        query = query.eq("month", month)
    if category:
        query = query.eq("category", category)
    response = query.execute()
    return response.data

# --- salesテーブルへの登録・更新（UPSERT） ---
def insert_sales(data):
    for record in data:
        year = record["year"]
        month = record["month"]
        date = record["date"]
        category = record["category"]

        existing = supabase.table("sales") \
            .select("id") \
            .eq("date", date) \
            .eq("category", category) \
            .execute()

        if existing.data:
            supabase.table("sales").update(record).eq("id", existing.data[0]["id"]).execute()
        else:
            record.pop("id", None)  # 念のため削除
            supabase.table("sales").insert(record).execute()



# --- salesデータの削除（日付＋カテゴリ指定） ---
def delete_sales_by_date(date_str, category):
    response = supabase.table("sales") \
        .delete() \
        .eq("date", date_str) \
        .eq("category", category) \
        .execute()
    return response

# --- targetsテーブルの取得 ---
def fetch_targets(year=None, month=None, category=None):
    query = supabase.table("targets").select("*")
    if year:
        query = query.eq("year", year)
    if month:
        query = query.eq("month", month)
    if category:
        query = query.eq("category", category)
    response = query.execute()
    return response.data

# --- targetsテーブルへの登録・更新 ---
def insert_target(data):
    response = supabase.table("targets").upsert(data).execute()
    return response

# --- minimum_targetsの取得 ---
def fetch_minimum_targets():
    response = supabase.table("minimum_targets").select("*").order("month", desc=False).execute()
    return response.data

# --- minimum_targetsへの登録・更新 ---
def insert_minimum_target(month, min_sales):
    response = supabase.table("minimum_targets").upsert([
        {"month": month, "min_sales": min_sales}
    ]).execute()
    return response

# --- 目標売上の単件アップサート ---
def upsert_target(year, month, date_str, category, target_sales):
    data = {
        "year": year,
        "month": month,
        "date": date_str,
        "category": category,
        "target_sales": target_sales
    }

    existing = supabase.table("targets") \
        .select("id") \
        .eq("year", year) \
        .eq("month", month) \
        .eq("date", date_str) \
        .eq("category", category) \
        .execute()

    if existing.data:
        supabase.table("targets").update(data).eq("id", existing.data[0]["id"]).execute()
    else:
        supabase.table("targets").insert(data).execute()

# --- カフェ合計・全体合計の自動更新（1日単位） ---
def update_auto_targets(dt):
    dt_str = dt.strftime("%Y-%m-%d")
    year = dt.year
    month = dt.month

    # ランチ + ディナー = カフェ合計
    lunch = get_target_by_category_and_date("ランチ", dt_str)
    dinner = get_target_by_category_and_date("ディナー", dt_str)
    cafe_total = (lunch or 0) + (dinner or 0)
    upsert_target(year, month, dt_str, "カフェ合計", cafe_total)

    # カフェ合計 + ベーグル = 全体合計
    bagel = get_target_by_category_and_date("ベーグル", dt_str)
    all_total = cafe_total + (bagel or 0)
    upsert_target(year, month, dt_str, "全体合計", all_total)

# --- 日付とカテゴリで目標を取得 ---
def get_target_by_category_and_date(category, date_str):
    response = supabase.table("targets") \
        .select("target_sales") \
        .eq("category", category) \
        .eq("date", date_str) \
        .execute()
    if response.data:
        return response.data[0]["target_sales"]
    return 0

# --- 月全体の自動更新 ---
def update_auto_targets_in_range(year, month):
    import calendar
    for day in range(1, calendar.monthrange(year, month)[1] + 1):
        dt = date(year, month, day)
        update_auto_targets(dt)

def get_last_sales_date(category):
    if category == "全体合計":
        cats = ["カフェ合計", "ベーグル"]
    elif category == "ディナー":
        cats = ["カフェ合計"]
    else:
        cats = [category]
    res = supabase.table("sales").select("date").in_("category", cats).order("date", desc=True).limit(1).execute()
    return res.data[0]["date"] if res.data else None


def fetch_sales_data_range(start_date, end_date, categories):
    res = supabase.table("sales") \
        .select("*") \
        .gte("date", start_date.strftime("%Y-%m-%d")) \
        .lte("date", end_date.strftime("%Y-%m-%d")) \
        .in_("category", categories) \
        .execute()
    return res.data or []


def fetch_targets_in_range(start_date, end_date, categories):
    res = supabase.table("targets") \
        .select("*") \
        .gte("date", start_date.strftime("%Y-%m-%d")) \
        .lte("date", end_date.strftime("%Y-%m-%d")) \
        .in_("category", categories) \
        .execute()
    return res.data or []
