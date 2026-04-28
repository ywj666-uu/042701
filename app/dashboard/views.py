from datetime import datetime, timedelta
from flask import render_template, jsonify, request
from flask_login import login_required, current_user
from app.dashboard import dashboard
from app import db
from app.models import (
    Asset, Department, PurchaseRequest, Budget, User,
    Maintenance, Inventory, AssetBorrow, Supplier
)
from app.auth.views import role_required, manager_required
from sqlalchemy import func


@dashboard.route('/')
@login_required
@manager_required
def index():
    today = datetime.utcnow()
    current_month = today.month
    current_year = today.year
    
    # 基础统计数据
    total_assets = Asset.query.count()
    in_use_assets = Asset.query.filter_by(status='in_use').count()
    in_stock_assets = Asset.query.filter_by(status='in_stock').count()
    maintenance_assets = Asset.query.filter_by(status='maintenance').count()
    disposed_assets = Asset.query.filter_by(status='disposed').count()
    
    # 部门统计
    departments = Department.query.all()
    department_assets = []
    for dept in departments:
        asset_count = Asset.query.filter_by(department_id=dept.id).count()
        in_use_count = Asset.query.filter_by(department_id=dept.id, status='in_use').count()
        department_assets.append({
            'id': dept.id,
            'name': dept.name,
            'total': asset_count,
            'in_use': in_use_count,
            'in_stock': asset_count - in_use_count
        })
    
    # 采购统计
    monthly_purchases = get_monthly_purchases(current_year)
    department_budgets = get_department_budgets(current_year)
    
    # 借用统计
    borrowed_count = AssetBorrow.query.filter_by(status='borrowed').count()
    pending_borrows = AssetBorrow.query.filter_by(status='pending').count()
    
    # 维护统计
    maintenance_count = Maintenance.query.filter_by(status='in_progress').count()
    scheduled_maintenance = Maintenance.query.filter_by(status='scheduled').count()
    
    # 资产类别统计
    category_stats = get_asset_category_stats()
    
    # 预算使用情况
    budget_stats = get_budget_stats(current_year)
    
    return render_template('dashboard/index.html', 
        title='数据可视化看板',
        today=today,
        current_year=current_year,
        # 资产统计
        total_assets=total_assets,
        in_use_assets=in_use_assets,
        in_stock_assets=in_stock_assets,
        maintenance_assets=maintenance_assets,
        disposed_assets=disposed_assets,
        # 部门资产
        department_assets=department_assets,
        # 采购统计
        monthly_purchases=monthly_purchases,
        # 借用维护
        borrowed_count=borrowed_count,
        pending_borrows=pending_borrows,
        maintenance_count=maintenance_count,
        scheduled_maintenance=scheduled_maintenance,
        # 类别和预算
        category_stats=category_stats,
        budget_stats=budget_stats,
        department_budgets=department_budgets
    )


def get_monthly_purchases(year):
    """获取月度采购统计"""
    monthly_data = []
    for month in range(1, 13):
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        purchases = PurchaseRequest.query.filter(
            PurchaseRequest.created_at >= start_date,
            PurchaseRequest.created_at < end_date,
            PurchaseRequest.status == 'approved'
        ).all()
        
        count = len(purchases)
        amount = sum(p.total_amount for p in purchases)
        
        monthly_data.append({
            'month': month,
            'count': count,
            'amount': round(amount, 2)
        })
    
    return monthly_data


def get_department_budgets(year):
    """获取部门预算统计"""
    budgets = Budget.query.filter_by(year=year, status='active').all()
    
    result = []
    for budget in budgets:
        dept = Department.query.get(budget.department_id)
        result.append({
            'department_id': budget.department_id,
            'department_name': dept.name if dept else '未知部门',
            'total_budget': budget.total_budget,
            'used_budget': budget.used_budget,
            'remaining_budget': budget.remaining_budget,
            'usage_percentage': round(budget.usage_percentage, 2)
        })
    
    return result


def get_asset_category_stats():
    """获取资产类别统计"""
    categories = db.session.query(
        Asset.category,
        func.count(Asset.id).label('count'),
        func.sum(Asset.total_value).label('total_value')
    ).filter(
        Asset.status != 'disposed'
    ).group_by(Asset.category).all()
    
    result = []
    for cat in categories:
        result.append({
            'category': cat.category or '未分类',
            'count': cat.count,
            'total_value': round(cat.total_value or 0, 2)
        })
    
    return result


def get_budget_stats(year):
    """获取预算统计"""
    budgets = Budget.query.filter_by(year=year, status='active').all()
    
    total_budget = sum(b.total_budget for b in budgets)
    total_used = sum(b.used_budget for b in budgets)
    total_remaining = sum(b.remaining_budget for b in budgets)
    
    avg_usage = 0
    if budgets:
        avg_usage = sum(b.usage_percentage for b in budgets) / len(budgets)
    
    return {
        'total_budget': round(total_budget, 2),
        'total_used': round(total_used, 2),
        'total_remaining': round(total_remaining, 2),
        'avg_usage': round(avg_usage, 2)
    }


@dashboard.route('/api/asset-distribution')
@login_required
@manager_required
def api_asset_distribution():
    """获取资产分布数据（图表用）"""
    # 按状态分布
    status_stats = db.session.query(
        Asset.status,
        func.count(Asset.id).label('count')
    ).group_by(Asset.status).all()
    
    status_data = []
    status_labels = {
        'in_stock': '在库',
        'in_use': '使用中',
        'maintenance': '维护中',
        'disposed': '已报废'
    }
    for s in status_stats:
        status_data.append({
            'name': status_labels.get(s.status, s.status),
            'value': s.count
        })
    
    # 按部门分布
    dept_stats = db.session.query(
        Asset.department_id,
        func.count(Asset.id).label('count')
    ).filter(
        Asset.status != 'disposed'
    ).group_by(Asset.department_id).all()
    
    dept_data = []
    for d in dept_stats:
        dept = Department.query.get(d.department_id)
        dept_data.append({
            'name': dept.name if dept else '未分配',
            'value': d.count
        })
    
    # 按类别分布
    category_stats = db.session.query(
        Asset.category,
        func.count(Asset.id).label('count')
    ).filter(
        Asset.status != 'disposed'
    ).group_by(Asset.category).all()
    
    category_data = []
    for c in category_stats:
        category_data.append({
            'name': c.category or '未分类',
            'value': c.count
        })
    
    return jsonify({
        'status_data': status_data,
        'department_data': dept_data,
        'category_data': category_data
    })


@dashboard.route('/api/purchase-trend')
@login_required
@manager_required
def api_purchase_trend():
    """获取采购趋势数据"""
    year = request.args.get('year', datetime.now().year, type=int)
    
    monthly_data = []
    for month in range(1, 13):
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        purchases = PurchaseRequest.query.filter(
            PurchaseRequest.created_at >= start_date,
            PurchaseRequest.created_at < end_date,
            PurchaseRequest.status == 'approved'
        ).all()
        
        count = len(purchases)
        amount = sum(p.total_amount for p in purchases)
        
        monthly_data.append({
            'month': f'{month}月',
            'count': count,
            'amount': round(amount, 2)
        })
    
    # 按部门统计
    dept_purchases = db.session.query(
        PurchaseRequest.department_id,
        func.count(PurchaseRequest.id).label('count'),
        func.sum(PurchaseRequest.total_amount).label('amount')
    ).filter(
        PurchaseRequest.status == 'approved',
        func.strftime('%Y', PurchaseRequest.created_at) == str(year)
    ).group_by(PurchaseRequest.department_id).all()
    
    dept_data = []
    for d in dept_purchases:
        dept = Department.query.get(d.department_id)
        dept_data.append({
            'name': dept.name if dept else '未知',
            'count': d.count,
            'amount': round(d.amount or 0, 2)
        })
    
    return jsonify({
        'monthly_data': monthly_data,
        'department_data': dept_data,
        'year': year
    })


@dashboard.route('/api/budget-usage')
@login_required
@manager_required
def api_budget_usage():
    """获取预算使用数据"""
    year = request.args.get('year', datetime.now().year, type=int)
    
    budgets = Budget.query.filter_by(year=year, status='active').all()
    
    budget_data = []
    for budget in budgets:
        dept = Department.query.get(budget.department_id)
        budget_data.append({
            'department': dept.name if dept else '未知',
            'total_budget': budget.total_budget,
            'used_budget': budget.used_budget,
            'remaining_budget': budget.remaining_budget,
            'usage_percentage': round(budget.usage_percentage, 2)
        })
    
    # 总体统计
    total_budget = sum(b.total_budget for b in budgets)
    total_used = sum(b.used_budget for b in budgets)
    total_remaining = sum(b.remaining_budget for b in budgets)
    
    return jsonify({
        'budget_data': budget_data,
        'summary': {
            'total_budget': round(total_budget, 2),
            'total_used': round(total_used, 2),
            'total_remaining': round(total_remaining, 2),
            'usage_percentage': round((total_used / total_budget * 100) if total_budget > 0 else 0, 2)
        },
        'year': year
    })


@dashboard.route('/api/department-assets')
@login_required
@manager_required
def api_department_assets():
    """获取部门资产占用率"""
    departments = Department.query.all()
    
    dept_data = []
    for dept in departments:
        total_assets = Asset.query.filter_by(department_id=dept.id).count()
        in_use_assets = Asset.query.filter_by(department_id=dept.id, status='in_use').count()
        in_stock_assets = Asset.query.filter_by(department_id=dept.id, status='in_stock').count()
        maintenance_assets = Asset.query.filter_by(department_id=dept.id, status='maintenance').count()
        
        # 计算资产价值
        total_value = db.session.query(
            func.sum(Asset.total_value)
        ).filter_by(department_id=dept.id).scalar() or 0
        
        dept_data.append({
            'department': dept.name,
            'total_assets': total_assets,
            'in_use_assets': in_use_assets,
            'in_stock_assets': in_stock_assets,
            'maintenance_assets': maintenance_assets,
            'total_value': round(total_value, 2),
            'usage_rate': round((in_use_assets / total_assets * 100) if total_assets > 0 else 0, 2)
        })
    
    return jsonify({
        'department_data': dept_data
    })


@dashboard.route('/api/maintenance-stats')
@login_required
@manager_required
def api_maintenance_stats():
    """获取维护保养统计"""
    year = request.args.get('year', datetime.now().year, type=int)
    
    # 按类型统计
    type_stats = db.session.query(
        Maintenance.maintenance_type,
        func.count(Maintenance.id).label('count'),
        func.sum(Maintenance.cost).label('cost')
    ).filter(
        func.strftime('%Y', Maintenance.created_at) == str(year)
    ).group_by(Maintenance.maintenance_type).all()
    
    type_data = []
    type_labels = {
        'repair': '维修',
        'maintenance': '保养',
        'inspection': '巡检'
    }
    for t in type_stats:
        type_data.append({
            'name': type_labels.get(t.maintenance_type, t.maintenance_type),
            'count': t.count,
            'cost': round(t.cost or 0, 2)
        })
    
    # 月度统计
    monthly_data = []
    for month in range(1, 13):
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
        
        maintenances = Maintenance.query.filter(
            Maintenance.created_at >= start_date,
            Maintenance.created_at < end_date
        ).all()
        
        count = len(maintenances)
        cost = sum(m.cost for m in maintenances)
        
        monthly_data.append({
            'month': f'{month}月',
            'count': count,
            'cost': round(cost, 2)
        })
    
    return jsonify({
        'type_data': type_data,
        'monthly_data': monthly_data,
        'year': year
    })


@dashboard.route('/api/supplier-stats')
@login_required
@manager_required
def api_supplier_stats():
    """获取供应商统计"""
    # 按状态统计
    active_suppliers = Supplier.query.filter_by(status='active').count()
    inactive_suppliers = Supplier.query.filter_by(status='inactive').count()
    blacklisted_suppliers = Supplier.query.filter_by(status='blacklisted').count()
    
    # 按评分统计
    top_suppliers = Supplier.query.filter_by(status='active').order_by(
        Supplier.rating.desc()
    ).limit(10).all()
    
    top_data = []
    for s in top_suppliers:
        top_data.append({
            'name': s.name,
            'rating': s.rating,
            'total_orders': s.total_orders,
            'total_amount': round(s.total_amount, 2)
        })
    
    # 采购金额统计
    amount_by_supplier = db.session.query(
        PurchaseRequest.supplier_id,
        func.count(PurchaseRequest.id).label('count'),
        func.sum(PurchaseRequest.total_amount).label('amount')
    ).filter(
        PurchaseRequest.supplier_id.isnot(None),
        PurchaseRequest.status == 'approved'
    ).group_by(PurchaseRequest.supplier_id).order_by(
        func.sum(PurchaseRequest.total_amount).desc()
    ).limit(10).all()
    
    supplier_amount_data = []
    for s in amount_by_supplier:
        supplier = Supplier.query.get(s.supplier_id)
        supplier_amount_data.append({
            'name': supplier.name if supplier else '未知',
            'count': s.count,
            'amount': round(s.amount or 0, 2)
        })
    
    return jsonify({
        'status_summary': {
            'active': active_suppliers,
            'inactive': inactive_suppliers,
            'blacklisted': blacklisted_suppliers
        },
        'top_suppliers': top_data,
        'purchase_amount_data': supplier_amount_data
    })
