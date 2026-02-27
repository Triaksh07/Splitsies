import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import text
from sqlalchemy.orm import Session
from decimal import Decimal
from datetime import date, timedelta

CATEGORY_COLORS = {
    "food": "#f97316", "transport": "#3b82f6", "accommodation": "#8b5cf6",
    "utilities": "#10b981", "entertainment": "#ec4899", "shopping": "#f59e0b",
    "other": "#6b7280",
}
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e2e8f0", family="Inter, sans-serif"),
    margin=dict(l=10, r=10, t=40, b=10),
)


def _fig_to_html(fig) -> str:
    return fig.to_html(full_html=False, include_plotlyjs=False,
                       config={"displayModeBar": False})


def monthly_spend_trend(group_id: int, db: Session, months: int = 6) -> str:
    sql = text("""
        SELECT strftime('%Y-%m', date) AS month, SUM(amount_inr) AS total
        FROM expenses WHERE group_id = :gid
        GROUP BY month ORDER BY month DESC LIMIT :m
    """)
    df = pd.read_sql(sql, db.bind, params={"gid": group_id, "m": months})
    if df.empty:
        return "<p class='text-base-content/50 text-center py-8'>No data yet</p>"
    df = df.sort_values("month")
    df["total"] = df["total"].astype(float)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["month"], y=df["total"], mode="lines+markers",
        name="Spend", line=dict(color="#818cf8", width=2.5), marker=dict(size=7, color="#818cf8")))

    if len(df) >= 3:
        x_num = np.arange(len(df))
        z = np.polyfit(x_num, df["total"].values, 1)
        trend = np.poly1d(z)(x_num)
        fig.add_trace(go.Scatter(x=df["month"], y=trend, mode="lines", name="Trend",
            line=dict(color="#f472b6", width=1.5, dash="dot")))

    fig.update_layout(**PLOTLY_LAYOUT, title="Monthly Spend (₹)", showlegend=True,
                      legend=dict(bgcolor="rgba(0,0,0,0)"))
    fig.update_yaxes(tickprefix="₹", gridcolor="rgba(255,255,255,0.05)")
    fig.update_xaxes(gridcolor="rgba(255,255,255,0.05)")
    return _fig_to_html(fig)


def category_breakdown(group_id: int, db: Session, months: int = 3) -> str:
    cutoff = (date.today() - timedelta(days=months * 30)).isoformat()
    sql = text("""
        SELECT category, SUM(amount_inr) AS total FROM expenses
        WHERE group_id = :gid AND date >= :cutoff GROUP BY category ORDER BY total DESC
    """)
    df = pd.read_sql(sql, db.bind, params={"gid": group_id, "cutoff": cutoff})
    if df.empty:
        return "<p class='text-base-content/50 text-center py-8'>No data yet</p>"
    df["total"] = df["total"].astype(float)
    colors = [CATEGORY_COLORS.get(c, "#6b7280") for c in df["category"]]
    fig = px.pie(df, values="total", names="category", color_discrete_sequence=colors, hole=0.4)
    fig.update_traces(textposition="inside", textinfo="percent+label",
                      marker=dict(line=dict(color="#1e293b", width=2)))
    fig.update_layout(**PLOTLY_LAYOUT, title=f"Category Breakdown (last {months}mo)", showlegend=False)
    return _fig_to_html(fig)


def per_person_contribution(group_id: int, db: Session) -> str:
    sql = text("""
        SELECT p.display_name, SUM(e.amount_inr) AS total
        FROM expenses e JOIN participants p ON e.paid_by_id = p.id
        WHERE e.group_id = :gid AND p.is_guest = 0
        GROUP BY p.id, p.display_name ORDER BY total DESC
    """)
    df = pd.read_sql(sql, db.bind, params={"gid": group_id})
    if df.empty:
        return "<p class='text-base-content/50 text-center py-8'>No data yet</p>"
    df["total"] = df["total"].astype(float)
    fig = px.bar(df, x="total", y="display_name", orientation="h",
                 color="total", color_continuous_scale=["#3b82f6", "#818cf8", "#ec4899"])
    fig.update_layout(**PLOTLY_LAYOUT, title="Who's Paid Most (₹)",
                      coloraxis_showscale=False, yaxis_title="", xaxis_title="₹ Paid")
    fig.update_xaxes(tickprefix="₹", gridcolor="rgba(255,255,255,0.05)")
    return _fig_to_html(fig)


def spending_velocity(group_id: int, db: Session) -> dict:
    sql = text("""
        SELECT strftime('%Y-%m', date) AS month, SUM(amount_inr) AS total
        FROM expenses WHERE group_id = :gid GROUP BY month ORDER BY month DESC LIMIT 2
    """)
    df = pd.read_sql(sql, db.bind, params={"gid": group_id})
    if len(df) < 2:
        return {"current": float(df.iloc[0]["total"]) if len(df) == 1 else 0,
                "last": 0, "change_pct": None, "trend": "neutral"}
    current, last = float(df.iloc[0]["total"]), float(df.iloc[1]["total"])
    change_pct = ((current - last) / last * 100) if last > 0 else None
    return {"current": current, "last": last,
            "change_pct": round(change_pct, 1) if change_pct is not None else None,
            "trend": "up" if (change_pct or 0) > 0 else "down" if (change_pct or 0) < 0 else "neutral"}


def fairness_score(group_id: int, db: Session) -> float | None:
    sql = text("""
        SELECT p.id, SUM(e.amount_inr) AS total FROM expenses e
        JOIN participants p ON e.paid_by_id = p.id
        WHERE e.group_id = :gid AND p.is_guest = 0 GROUP BY p.id
    """)
    df = pd.read_sql(sql, db.bind, params={"gid": group_id})
    if len(df) < 2:
        return None
    vals = df["total"].astype(float).values
    mean, std = vals.mean(), vals.std()
    if mean == 0:
        return 100.0
    return round(max(0.0, 100.0 - (std / mean) * 100.0), 1)


def top_spender(group_id: int, db: Session, month: str | None = None) -> dict | None:
    where_extra = "AND strftime('%Y-%m', e.date) = :month" if month else ""
    sql = text(f"""
        SELECT p.display_name, SUM(e.amount_inr) AS total,
               (SELECT category FROM expenses e2 WHERE e2.group_id = :gid
                AND e2.paid_by_id = p.id {where_extra}
                GROUP BY category ORDER BY COUNT(*) DESC LIMIT 1) AS top_cat
        FROM expenses e JOIN participants p ON e.paid_by_id = p.id
        WHERE e.group_id = :gid AND p.is_guest = 0 {where_extra}
        GROUP BY p.id ORDER BY total DESC LIMIT 1
    """)
    params = {"gid": group_id}
    if month:
        params["month"] = month
    row = db.execute(sql, params).fetchone()
    if not row:
        return None
    return {"name": row.display_name, "amount_inr": float(row.total), "top_category": row.top_cat}


def anomaly_flags(group_id: int, db: Session) -> list[dict]:
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    sql = text("""
        SELECT e.id, e.description, e.amount_inr, e.category, e.date,
               p.display_name AS paid_by
        FROM expenses e JOIN participants p ON e.paid_by_id = p.id
        WHERE e.group_id = :gid
    """)
    df = pd.read_sql(sql, db.bind, params={"gid": group_id})
    if df.empty:
        return []
    df["amount_inr"] = df["amount_inr"].astype(float)
    flags = []
    for category, group in df.groupby("category"):
        if len(group) < 3:
            continue
        mean, std = group["amount_inr"].mean(), group["amount_inr"].std()
        if std == 0:
            continue
        for _, row in group[group["date"] >= cutoff].iterrows():
            z = (row["amount_inr"] - mean) / std
            if z > 2.0:
                flags.append({
                    "expense_id": int(row["id"]), "description": row["description"],
                    "amount_inr": row["amount_inr"], "category": row["category"],
                    "z_score": round(float(z), 2), "paid_by": row["paid_by"],
                })
    return sorted(flags, key=lambda x: x["z_score"], reverse=True)


def natural_language_summary(group_id: int, db: Session) -> str:
    this_month = date.today().strftime("%Y-%m")
    velocity = spending_velocity(group_id, db)
    spender = top_spender(group_id, db, month=this_month)
    score = fairness_score(group_id, db)

    if velocity["current"] == 0:
        return "No expenses recorded yet this month. Add your first one!"

    parts = [f"Your group spent ₹{velocity['current']:,.0f} this month"]
    if velocity["change_pct"] is not None:
        direction = "more" if velocity["trend"] == "up" else "less"
        parts[0] += f", {abs(velocity['change_pct'])}% {direction} than last month"
    parts[0] += "."

    if spender:
        parts.append(f"{spender['name']} has paid the most, mostly on {spender['top_category'] or 'various things'}.")

    if score is not None:
        if score >= 80:
            parts.append("Spending is well-distributed across the group. 👍")
        elif score >= 50:
            parts.append("Spending is somewhat uneven — some members are carrying more.")
        else:
            parts.append("Spending is quite uneven. Consider rebalancing who pays.")

    return " ".join(parts)
