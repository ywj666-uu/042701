from datetime import datetime, timedelta
from flask import render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import login_required, current_user
from app.maintenance import maintenance
from app import db
from app.models import (
    Maintenance, MaintenancePlan, Asset, Department, User, AssetStatusLog
)
from app.auth.views import role_required, manager_required

@maintenance.route('/')
@login_required
def list():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    maintenance_type = request.args.get('maintenance_type', '')
    
    query = Maintenance.query
    
    if status:
        query = query.filter_by(status=status)
    
    if maintenance_type:
        query = query.filter_by(maintenance_type=maintenance_type)
    
    # 如果不是管理员，只看自己部门的
    if current_user.role not in ['manager', 'admin']:
        query = query.join(Asset).filter(
            Asset.department_id == current_user.department_id
        )
    
    pagination = query.order_by(Maintenance.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    maintenances = pagination.items
    
    return render_template('maintenance/list.html', 
        title='维修保养',
        maintenances=maintenances,
        pagination=pagination,
        status=status,
        maintenance_type=maintenance_type
    )

@maintenance.route('/plans')
@login_required
@manager_required
def plans():
    page = request.args.get('page', 1, type=int)
    is_active = request.args.get('is_active', type=bool)
    
    query = MaintenancePlan.query
    
    if is_active is not None:
        query = query.filter_by(is_active=is_active)
    
    pagination = query.order_by(MaintenancePlan.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    plans = pagination.items
    
    return render_template('maintenance/plans.html', 
        title='维护计划',
        plans=plans,
        pagination=pagination,
        is_active=is_active
    )

@maintenance.route('/plans/create', methods=['GET', 'POST'])
@login_required
@manager_required
def plan_create():
    if request.method == 'POST':
        plan_type = request.form.get('plan_type', 'category')
        asset_category = request.form.get('asset_category')
        asset_id = request.form.get('asset_id', type=int)
        maintenance_type = request.form.get('maintenance_type', 'maintenance')
        interval_days = request.form.get('interval_days', type=int)
        next_maintenance_date = request.form.get('next_maintenance_date')
        duration = request.form.get('duration', 0.0, type=float)
        description = request.form.get('description')
        
        # 验证
        if plan_type == 'category' and not asset_category:
            flash('请选择资产类别', 'danger')
            return redirect(url_for('maintenance.plan_create'))
        
        if plan_type == 'specific' and not asset_id:
            flash('请选择具体资产', 'danger')
            return redirect(url_for('maintenance.plan_create'))
        
        # 创建维护计划
        plan = MaintenancePlan(
            asset_category=asset_category if plan_type == 'category' else None,
            asset_id=asset_id if plan_type == 'specific' else None,
            plan_type=plan_type,
            maintenance_type=maintenance_type,
            interval_days=interval_days,
            next_maintenance_date=datetime.strptime(next_maintenance_date, '%Y-%m-%d') if next_maintenance_date else None,
            duration=duration,
            description=description,
            is_active=True
        )
        
        db.session.add(plan)
        db.session.commit()
        
        flash('维护计划创建成功！', 'success')
        return redirect(url_for('maintenance.plans'))
    
    # 获取所有资产类别
    categories = db.session.query(Asset.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    
    # 获取所有资产
    assets = Asset.query.filter(Asset.status != 'disposed').all()
    
    return render_template('maintenance/plan_create.html', 
        title='创建维护计划',
        categories=categories,
        assets=assets
    )

@maintenance.route('/plans/<int:plan_id>/edit', methods=['GET', 'POST'])
@login_required
@manager_required
def plan_edit(plan_id):
    plan = MaintenancePlan.query.get_or_404(plan_id)
    
    if request.method == 'POST':
        plan_type = request.form.get('plan_type', 'category')
        asset_category = request.form.get('asset_category')
        asset_id = request.form.get('asset_id', type=int)
        maintenance_type = request.form.get('maintenance_type', 'maintenance')
        interval_days = request.form.get('interval_days', type=int)
        next_maintenance_date = request.form.get('next_maintenance_date')
        duration = request.form.get('duration', 0.0, type=float)
        description = request.form.get('description')
        is_active = request.form.get('is_active') == 'on'
        
        plan.plan_type = plan_type
        plan.asset_category = asset_category if plan_type == 'category' else None
        plan.asset_id = asset_id if plan_type == 'specific' else None
        plan.maintenance_type = maintenance_type
        plan.interval_days = interval_days
        plan.next_maintenance_date = datetime.strptime(next_maintenance_date, '%Y-%m-%d') if next_maintenance_date else None
        plan.duration = duration
        plan.description = description
        plan.is_active = is_active
        
        db.session.commit()
        
        flash('维护计划更新成功！', 'success')
        return redirect(url_for('maintenance.plans'))
    
    # 获取所有资产类别
    categories = db.session.query(Asset.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    
    # 获取所有资产
    assets = Asset.query.filter(Asset.status != 'disposed').all()
    
    return render_template('maintenance/plan_edit.html', 
        title='编辑维护计划',
        plan=plan,
        categories=categories,
        assets=assets
    )

@maintenance.route('/schedule', methods=['GET', 'POST'])
@login_required
def schedule():
    if request.method == 'POST':
        asset_id = request.form.get('asset_id', type=int)
        maintenance_type = request.form.get('maintenance_type', 'maintenance')
        description = request.form.get('description')
        schedule_date = request.form.get('schedule_date')
        duration = request.form.get('duration', 0.0, type=float)
        
        # 创建维护预约
        maintenance_obj = Maintenance(
            maintenance_no=f'MT{datetime.now().strftime("%Y%m%d%H%M%S")}',
            asset_id=asset_id,
            operator_id=current_user.id,
            maintenance_type=maintenance_type,
            description=description,
            schedule_date=datetime.strptime(schedule_date, '%Y-%m-%d %H:%M') if schedule_date else None,
            duration=duration,
            status='scheduled'
        )
        
        db.session.add(maintenance_obj)
        db.session.commit()
        
        flash('维护预约创建成功！', 'success')
        return redirect(url_for('maintenance.detail', maintenance_id=maintenance_obj.id))
    
    # 获取可预约的资产
    assets = Asset.query.filter(
        Asset.status.notin_(['disposed', 'maintenance'])
    ).all()
    
    return render_template('maintenance/schedule.html', 
        title='预约维护',
        assets=assets
    )

@maintenance.route('/<int:maintenance_id>')
@login_required
def detail(maintenance_id):
    maintenance_obj = Maintenance.query.get_or_404(maintenance_id)
    
    return render_template('maintenance/detail.html', 
        title='维护详情',
        maintenance=maintenance_obj
    )

@maintenance.route('/scan-start', methods=['GET', 'POST'])
@login_required
def scan_start():
    if request.method == 'POST':
        asset_code = request.form.get('asset_code')
        maintenance_id = request.form.get('maintenance_id', type=int)
        
        # 查找资产
        asset = Asset.query.filter_by(asset_code=asset_code).first()
        
        if not asset:
            flash('未找到该资产', 'danger')
            return redirect(url_for('maintenance.scan_start'))
        
        # 查找维护记录
        maintenance_obj = None
        if maintenance_id:
            maintenance_obj = Maintenance.query.filter_by(
                id=maintenance_id,
                asset_id=asset.id
            ).first()
        
        if not maintenance_obj:
            # 查找最近的预约维护
            maintenance_obj = Maintenance.query.filter(
                Maintenance.asset_id == asset.id,
                Maintenance.status == 'scheduled'
            ).order_by(Maintenance.schedule_date).first()
        
        if not maintenance_obj:
            # 创建新的维护记录
            maintenance_obj = Maintenance(
                maintenance_no=f'MT{datetime.now().strftime("%Y%m%d%H%M%S")}',
                asset_id=asset.id,
                operator_id=current_user.id,
                maintenance_type='maintenance',
                status='in_progress',
                actual_date=datetime.utcnow()
            )
            db.session.add(maintenance_obj)
        else:
            maintenance_obj.status = 'in_progress'
            maintenance_obj.actual_date = datetime.utcnow()
        
        # 更新资产状态
        previous_status = asset.status
        asset.status = 'maintenance'
        
        # 记录状态变更日志
        status_log = AssetStatusLog(
            asset_id=asset.id,
            status='maintenance',
            previous_status=previous_status,
            description='开始维护保养',
            operator_id=current_user.id
        )
        db.session.add(status_log)
        
        # 记录开始时间到session
        session[f'maintenance_start_{maintenance_obj.id}'] = datetime.utcnow().isoformat()
        
        db.session.commit()
        
        flash(f'资产 {asset.name} 已开始维护', 'success')
        return redirect(url_for('maintenance.scan_end', maintenance_id=maintenance_obj.id))
    
    # 获取进行中的维护
    active_maintenances = Maintenance.query.filter_by(
        status='in_progress'
    ).all()
    
    return render_template('maintenance/scan_start.html', 
        title='扫码开机',
        active_maintenances=active_maintenances
    )

@maintenance.route('/scan-end/<int:maintenance_id>', methods=['GET', 'POST'])
@login_required
def scan_end(maintenance_id):
    maintenance_obj = Maintenance.query.get_or_404(maintenance_id)
    
    if maintenance_obj.status != 'in_progress':
        flash('该维护不在进行中', 'danger')
        return redirect(url_for('maintenance.list'))
    
    if request.method == 'POST':
        asset_code = request.form.get('asset_code')
        cost = request.form.get('cost', 0.0, type=float)
        remark = request.form.get('remark')
        
        # 验证资产
        asset = Asset.query.filter_by(asset_code=asset_code).first()
        
        if not asset or asset.id != maintenance_obj.asset_id:
            flash('资产编码不匹配', 'danger')
            return redirect(url_for('maintenance.scan_end', maintenance_id=maintenance_id))
        
        # 计算运行时长
        start_time_str = session.get(f'maintenance_start_{maintenance_obj.id}')
        if start_time_str:
            start_time = datetime.fromisoformat(start_time_str)
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds() / 3600  # 转换为小时
            maintenance_obj.duration = round(duration, 2)
        
        # 更新维护记录
        maintenance_obj.status = 'completed'
        maintenance_obj.cost = cost
        maintenance_obj.remark = remark
        
        # 如果有维护计划，更新下次维护时间
        try:
            plan = MaintenancePlan.query.filter(
                db.or_(
                    MaintenancePlan.asset_id == asset.id,
                    db.and_(
                        MaintenancePlan.asset_category == asset.category,
                        MaintenancePlan.plan_type == 'category'
                    )
                ),
                MaintenancePlan.is_active == True
            ).first()
            
            if plan and plan.interval_days:
                maintenance_obj.next_maintenance_date = datetime.utcnow() + timedelta(days=plan.interval_days)
        except:
            pass
        
        # 更新资产状态
        previous_status = asset.status
        asset.status = 'in_stock'
        
        # 记录状态变更日志
        status_log = AssetStatusLog(
            asset_id=asset.id,
            status='in_stock',
            previous_status=previous_status,
            description='维护保养完成',
            operator_id=current_user.id
        )
        db.session.add(status_log)
        
        # 清除session
        session.pop(f'maintenance_start_{maintenance_obj.id}', None)
        
        db.session.commit()
        
        flash(f'资产 {asset.name} 维护完成！运行时长：{maintenance_obj.duration} 小时', 'success')
        return redirect(url_for('maintenance.detail', maintenance_id=maintenance_obj.id))
    
    # 获取开始时间
    start_time_str = session.get(f'maintenance_start_{maintenance_obj.id}')
    current_duration = 0
    if start_time_str:
        start_time = datetime.fromisoformat(start_time_str)
        current_duration = round((datetime.utcnow() - start_time).total_seconds() / 3600, 2)
    
    return render_template('maintenance/scan_end.html', 
        title='扫码关机',
        maintenance=maintenance_obj,
        current_duration=current_duration
    )

@maintenance.route('/upcoming')
@login_required
def upcoming():
    today = datetime.utcnow()
    week_later = today + timedelta(days=7)
    
    # 获取即将到期的维护
    scheduled_maintenances = Maintenance.query.filter(
        Maintenance.status == 'scheduled',
        Maintenance.schedule_date <= week_later
    ).order_by(Maintenance.schedule_date).all()
    
    # 获取即将到期的维护计划
    upcoming_plans = MaintenancePlan.query.filter(
        MaintenancePlan.is_active == True,
        MaintenancePlan.next_maintenance_date <= week_later
    ).order_by(MaintenancePlan.next_maintenance_date).all()
    
    return render_template('maintenance/upcoming.html', 
        title='即将到期的维护',
        scheduled_maintenances=scheduled_maintenances,
        upcoming_plans=upcoming_plans,
        today=today
    )
