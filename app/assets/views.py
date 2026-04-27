from datetime import datetime, timedelta
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.assets import assets
from app import db
from app.models import (
    Asset, Department, User, AssetBorrow, AssetDisposal, 
    AssetTransfer, Approval, AssetStatusLog, AssetEntry, AssetEntryItem
)
from app.auth.views import role_required, manager_required

@assets.route('/')
@login_required
def list():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    category = request.args.get('category', '')
    department_id = request.args.get('department_id', type=int)
    
    query = Asset.query
    
    if search:
        query = query.filter(
            db.or_(
                Asset.asset_code.contains(search),
                Asset.name.contains(search),
                Asset.model.contains(search)
            )
        )
    
    if status:
        query = query.filter_by(status=status)
    
    if category:
        query = query.filter_by(category=category)
    
    if department_id:
        query = query.filter_by(department_id=department_id)
    
    pagination = query.order_by(Asset.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    assets_list = pagination.items
    
    # 获取所有部门用于筛选
    departments = Department.query.all()
    
    # 获取所有资产类别
    categories = db.session.query(Asset.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]
    
    return render_template('assets/list.html', 
        title='资产列表',
        assets=assets_list,
        pagination=pagination,
        departments=departments,
        categories=categories,
        search=search,
        status=status,
        category=category,
        department_id=department_id
    )

@assets.route('/<int:asset_id>')
@login_required
def detail(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    
    # 获取资产的历史记录
    status_logs = AssetStatusLog.query.filter_by(
        asset_id=asset_id
    ).order_by(AssetStatusLog.created_at.desc()).all()
    
    # 获取借用记录
    borrow_records = AssetBorrow.query.filter_by(
        asset_id=asset_id
    ).order_by(AssetBorrow.created_at.desc()).all()
    
    # 获取维护记录
    maintenances = []
    try:
        from app.models import Maintenance
        maintenances = Maintenance.query.filter_by(
            asset_id=asset_id
        ).order_by(Maintenance.created_at.desc()).all()
    except ImportError:
        pass
    
    return render_template('assets/detail.html', 
        title=f'资产详情 - {asset.name}',
        asset=asset,
        status_logs=status_logs,
        borrow_records=borrow_records,
        maintenances=maintenances
    )

@assets.route('/create', methods=['GET', 'POST'])
@login_required
@manager_required
def create():
    if request.method == 'POST':
        asset_code = request.form.get('asset_code')
        name = request.form.get('name')
        category = request.form.get('category')
        model = request.form.get('model')
        specification = request.form.get('specification')
        unit = request.form.get('unit', '台')
        quantity = request.form.get('quantity', 1, type=int)
        unit_price = request.form.get('unit_price', 0.0, type=float)
        purchase_date = request.form.get('purchase_date')
        warranty_period = request.form.get('warranty_period', type=int)
        location = request.form.get('location')
        department_id = request.form.get('department_id', type=int)
        description = request.form.get('description')
        
        # 验证必填字段
        if not asset_code or not name:
            flash('资产编码和名称为必填项', 'danger')
            return redirect(url_for('assets.create'))
        
        # 检查资产编码是否已存在
        if Asset.query.filter_by(asset_code=asset_code).first():
            flash('资产编码已存在', 'danger')
            return redirect(url_for('assets.create'))
        
        # 创建资产
        asset = Asset(
            asset_code=asset_code,
            name=name,
            category=category,
            model=model,
            specification=specification,
            unit=unit,
            quantity=quantity,
            unit_price=unit_price,
            total_value=unit_price * quantity,
            purchase_date=datetime.strptime(purchase_date, '%Y-%m-%d') if purchase_date else None,
            warranty_period=warranty_period,
            location=location,
            department_id=department_id,
            status='in_stock',
            description=description
        )
        
        db.session.add(asset)
        db.session.commit()
        
        # 记录状态变更日志
        status_log = AssetStatusLog(
            asset_id=asset.id,
            status='in_stock',
            previous_status=None,
            description='资产入库',
            operator_id=current_user.id
        )
        db.session.add(status_log)
        db.session.commit()
        
        flash('资产创建成功！', 'success')
        return redirect(url_for('assets.detail', asset_id=asset.id))
    
    departments = Department.query.all()
    return render_template('assets/create.html', 
        title='新增资产',
        departments=departments
    )

@assets.route('/<int:asset_id>/edit', methods=['GET', 'POST'])
@login_required
@manager_required
def edit(asset_id):
    asset = Asset.query.get_or_404(asset_id)
    
    if request.method == 'POST':
        asset.name = request.form.get('name')
        asset.category = request.form.get('category')
        asset.model = request.form.get('model')
        asset.specification = request.form.get('specification')
        asset.unit = request.form.get('unit', '台')
        asset.quantity = request.form.get('quantity', 1, type=int)
        asset.unit_price = request.form.get('unit_price', 0.0, type=float)
        asset.total_value = asset.unit_price * asset.quantity
        purchase_date = request.form.get('purchase_date')
        asset.purchase_date = datetime.strptime(purchase_date, '%Y-%m-%d') if purchase_date else None
        asset.warranty_period = request.form.get('warranty_period', type=int)
        asset.location = request.form.get('location')
        asset.department_id = request.form.get('department_id', type=int)
        asset.description = request.form.get('description')
        
        db.session.commit()
        
        flash('资产信息更新成功！', 'success')
        return redirect(url_for('assets.detail', asset_id=asset.id))
    
    departments = Department.query.all()
    return render_template('assets/edit.html', 
        title='编辑资产',
        asset=asset,
        departments=departments
    )

@assets.route('/borrow', methods=['GET', 'POST'])
@login_required
def borrow():
    if request.method == 'POST':
        asset_id = request.form.get('asset_id', type=int)
        borrow_type = request.form.get('borrow_type', 'borrow')
        purpose = request.form.get('purpose')
        expected_return_date = request.form.get('expected_return_date')
        
        asset = Asset.query.get_or_404(asset_id)
        
        # 检查资产状态
        if asset.status not in ['in_stock', 'in_use']:
            flash('该资产当前不可领用/借用', 'danger')
            return redirect(url_for('assets.borrow'))
        
        # 创建借用记录
        borrow_record = AssetBorrow(
            borrow_no=f'BR{datetime.now().strftime("%Y%m%d%H%M%S")}',
            asset_id=asset_id,
            borrower_id=current_user.id,
            borrow_type=borrow_type,
            purpose=purpose,
            expected_return_date=datetime.strptime(expected_return_date, '%Y-%m-%d') if expected_return_date else None,
            status='pending'
        )
        
        db.session.add(borrow_record)
        
        # 创建审批
        approval = Approval(
            approval_no=f'AP{datetime.now().strftime("%Y%m%d%H%M%S")}',
            approval_type='borrow',
            asset_borrow_id=borrow_record.id,
            status='pending',
            level=1
        )
        
        # 查找审批人（部门经理或管理员）
        if current_user.department:
            dept_manager = User.query.filter_by(
                department_id=current_user.department_id,
                role='manager'
            ).first()
            if dept_manager:
                approval.approver_id = dept_manager.id
        
        db.session.add(approval)
        db.session.commit()
        
        flash('领用/借用申请已提交，等待审批', 'success')
        return redirect(url_for('assets.my_borrows'))
    
    # 获取可领用的资产
    available_assets = Asset.query.filter(
        Asset.status.in_(['in_stock', 'in_use'])
    ).all()
    
    return render_template('assets/borrow.html', 
        title='资产领用/借用',
        assets=available_assets
    )

@assets.route('/my-borrows')
@login_required
def my_borrows():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    
    query = AssetBorrow.query.filter_by(borrower_id=current_user.id)
    
    if status:
        query = query.filter_by(status=status)
    
    pagination = query.order_by(AssetBorrow.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    borrows = pagination.items
    
    return render_template('assets/my_borrows.html', 
        title='我的领用/借用',
        borrows=borrows,
        pagination=pagination,
        status=status
    )

@assets.route('/borrow/<int:borrow_id>/return', methods=['POST'])
@login_required
def return_asset(borrow_id):
    borrow_record = AssetBorrow.query.get_or_404(borrow_id)
    
    if borrow_record.borrower_id != current_user.id and current_user.role not in ['manager', 'admin']:
        flash('您没有权限归还此资产', 'danger')
        return redirect(url_for('assets.my_borrows'))
    
    if borrow_record.status != 'borrowed':
        flash('该资产当前不在借用状态', 'danger')
        return redirect(url_for('assets.my_borrows'))
    
    # 更新借用记录
    borrow_record.status = 'returned'
    borrow_record.actual_return_date = datetime.utcnow()
    
    # 更新资产状态
    asset = borrow_record.asset
    previous_status = asset.status
    asset.status = 'in_stock'
    
    # 记录状态变更日志
    status_log = AssetStatusLog(
        asset_id=asset.id,
        status='in_stock',
        previous_status=previous_status,
        description='资产归还入库',
        operator_id=current_user.id
    )
    db.session.add(status_log)
    
    db.session.commit()
    
    flash('资产归还成功！', 'success')
    return redirect(url_for('assets.my_borrows'))

@assets.route('/dispose', methods=['GET', 'POST'])
@login_required
@manager_required
def dispose():
    if request.method == 'POST':
        asset_id = request.form.get('asset_id', type=int)
        disposal_type = request.form.get('disposal_type')
        reason = request.form.get('reason')
        estimated_value = request.form.get('estimated_value', 0.0, type=float)
        
        asset = Asset.query.get_or_404(asset_id)
        
        # 检查资产状态
        if asset.status in ['disposed', 'maintenance']:
            flash('该资产当前不可处置', 'danger')
            return redirect(url_for('assets.dispose'))
        
        # 创建处置申请
        disposal = AssetDisposal(
            disposal_no=f'DP{datetime.now().strftime("%Y%m%d%H%M%S")}',
            asset_id=asset_id,
            applicant_id=current_user.id,
            disposal_type=disposal_type,
            reason=reason,
            estimated_value=estimated_value,
            status='pending'
        )
        
        db.session.add(disposal)
        
        # 创建审批
        approval = Approval(
            approval_no=f'AP{datetime.now().strftime("%Y%m%d%H%M%S")}',
            approval_type='disposal',
            asset_disposal_id=disposal.id,
            status='pending',
            level=1
        )
        
        # 查找审批人（管理员）
        admin = User.query.filter_by(role='admin').first()
        if admin:
            approval.approver_id = admin.id
        
        db.session.add(approval)
        db.session.commit()
        
        flash('资产处置申请已提交，等待审批', 'success')
        return redirect(url_for('assets.disposal_list'))
    
    # 获取可处置的资产
    available_assets = Asset.query.filter(
        ~Asset.status.in_(['disposed', 'maintenance'])
    ).all()
    
    return render_template('assets/dispose.html', 
        title='资产处置',
        assets=available_assets
    )

@assets.route('/disposals')
@login_required
def disposal_list():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    
    query = AssetDisposal.query
    
    if status:
        query = query.filter_by(status=status)
    
    # 如果不是管理员，只显示自己申请的
    if current_user.role not in ['manager', 'admin']:
        query = query.filter_by(applicant_id=current_user.id)
    
    pagination = query.order_by(AssetDisposal.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    disposals = pagination.items
    
    return render_template('assets/disposal_list.html', 
        title='处置申请列表',
        disposals=disposals,
        pagination=pagination,
        status=status
    )

@assets.route('/scan/<asset_code>')
@login_required
def scan_asset(asset_code):
    asset = Asset.query.filter_by(asset_code=asset_code).first()
    
    if not asset:
        flash('未找到该资产', 'danger')
        return redirect(url_for('assets.list'))
    
    return redirect(url_for('assets.detail', asset_id=asset.id))

@assets.route('/api/search')
@login_required
def api_search():
    query = request.args.get('q', '')
    limit = request.args.get('limit', 10, type=int)
    
    assets = Asset.query.filter(
        db.or_(
            Asset.asset_code.contains(query),
            Asset.name.contains(query),
            Asset.model.contains(query)
        )
    ).limit(limit).all()
    
    return jsonify([{
        'id': asset.id,
        'asset_code': asset.asset_code,
        'name': asset.name,
        'model': asset.model,
        'category': asset.category,
        'status': asset.status
    } for asset in assets])
