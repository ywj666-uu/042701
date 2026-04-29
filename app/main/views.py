from datetime import datetime, timedelta
from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.main import main
from app import db
from app.models import (
    User, Department, Asset, AssetBorrow, Maintenance, 
    Notification, PurchaseRequest, Budget, Inventory
)

@main.route('/')
@login_required
def index():
    today = datetime.utcnow()
    
    # 统计数据
    total_assets = Asset.query.count()
    in_use_assets = Asset.query.filter_by(status='in_use').count()
    in_stock_assets = Asset.query.filter_by(status='in_stock').count()
    maintenance_assets = Asset.query.filter_by(status='maintenance').count()
    
    # 待办事项
    pending_approval_count = 0
    if current_user.role in ['manager', 'admin']:
        from app.models import Approval
        pending_approval_count = Approval.query.filter_by(
            approver_id=current_user.id, 
            status='pending'
        ).count()
    
    # 即将到期的借用
    upcoming_returns = AssetBorrow.query.filter(
        AssetBorrow.status == 'borrowed',
        AssetBorrow.expected_return_date <= today + timedelta(days=3)
    ).all()
    
    # 即将到期的维保
    upcoming_maintenances = Maintenance.query.filter(
        Maintenance.status == 'scheduled',
        Maintenance.schedule_date <= today + timedelta(days=7)
    ).all()
    
    # 未读通知
    unread_notifications = Notification.query.filter_by(
        user_id=current_user.id, 
        is_read=False
    ).count()
    
    # 预算使用情况（如果是部门经理或管理员）
    budget_info = None
    if current_user.role in ['manager', 'admin']:
        dept_id = current_user.department_id if current_user.department_id else None
        if dept_id:
            budget = Budget.query.filter_by(
                department_id=dept_id, 
                year=today.year,
                status='active'
            ).first()
            if budget:
                budget_info = {
                    'total': budget.total_budget,
                    'used': budget.used_budget,
                    'remaining': budget.remaining_budget,
                    'percentage': (budget.used_budget / budget.total_budget * 100) if budget.total_budget > 0 else 0
                }
    
    return render_template('index.html', 
        title='仪表盘',
        total_assets=total_assets,
        in_use_assets=in_use_assets,
        in_stock_assets=in_stock_assets,
        maintenance_assets=maintenance_assets,
        pending_approval_count=pending_approval_count,
        upcoming_returns=upcoming_returns,
        upcoming_maintenances=upcoming_maintenances,
        unread_notifications=unread_notifications,
        budget_info=budget_info,
        today=today
    )

@main.route('/dashboard')
@login_required
def dashboard():
    return redirect(url_for('main.index'))

@main.route('/profile')
@login_required
def profile():
    return render_template('profile.html', 
        title='个人中心',
        user=current_user
    )
