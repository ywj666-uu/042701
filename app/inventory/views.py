from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.inventory import inventory
from app import db
from app.models import (
    Inventory, InventoryItem, Asset, Department, User
)
from app.auth.views import role_required, manager_required

@inventory.route('/')
@login_required
def list():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    inventory_type = request.args.get('inventory_type', '')
    department_id = request.args.get('department_id', type=int)
    
    query = Inventory.query
    
    if status:
        query = query.filter_by(status=status)
    
    if inventory_type:
        query = query.filter_by(inventory_type=inventory_type)
    
    if department_id:
        query = query.filter_by(department_id=department_id)
    
    # 如果不是管理员，只看自己部门的
    if current_user.role not in ['manager', 'admin']:
        query = query.filter_by(department_id=current_user.department_id)
    
    pagination = query.order_by(Inventory.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    inventories = pagination.items
    departments = Department.query.all()
    
    return render_template('inventory/list.html', 
        title='资产盘点',
        inventories=inventories,
        pagination=pagination,
        departments=departments,
        status=status,
        inventory_type=inventory_type,
        department_id=department_id
    )

@inventory.route('/create', methods=['GET', 'POST'])
@login_required
@manager_required
def create():
    if request.method == 'POST':
        name = request.form.get('name')
        inventory_type = request.form.get('inventory_type', 'annual')
        department_id = request.form.get('department_id', type=int) or current_user.department_id
        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        description = request.form.get('description')
        
        # 创建盘点计划
        inventory_obj = Inventory(
            inventory_no=f'INV{datetime.now().strftime("%Y%m%d%H%M%S")}',
            name=name,
            inventory_type=inventory_type,
            operator_id=current_user.id,
            department_id=department_id,
            start_date=datetime.strptime(start_date, '%Y-%m-%d') if start_date else None,
            end_date=datetime.strptime(end_date, '%Y-%m-%d') if end_date else None,
            status='pending',
            description=description
        )
        
        db.session.add(inventory_obj)
        db.session.flush()  # 获取ID
        
        # 获取需要盘点的资产
        assets_query = Asset.query
        
        if department_id:
            assets_query = assets_query.filter_by(department_id=department_id)
        
        # 排除已报废的资产
        assets_query = assets_query.filter(Asset.status != 'disposed')
        
        assets = assets_query.all()
        
        # 创建盘点项目
        for asset in assets:
            inventory_item = InventoryItem(
                inventory_id=inventory_obj.id,
                asset_id=asset.id,
                expected_quantity=asset.quantity,
                actual_quantity=0,
                expected_location=asset.location,
                actual_location='',
                expected_status=asset.status,
                actual_status='',
                inventory_result='pending'
            )
            db.session.add(inventory_item)
        
        # 更新统计信息
        inventory_obj.total_assets = len(assets)
        inventory_obj.inventoried_assets = 0
        inventory_obj.profit_assets = 0
        inventory_obj.loss_assets = 0
        
        db.session.commit()
        
        flash('盘点计划创建成功！', 'success')
        return redirect(url_for('inventory.detail', inventory_id=inventory_obj.id))
    
    departments = Department.query.all()
    return render_template('inventory/create.html', 
        title='创建盘点计划',
        departments=departments
    )

@inventory.route('/<int:inventory_id>')
@login_required
def detail(inventory_id):
    inventory_obj = Inventory.query.get_or_404(inventory_id)
    
    # 获取盘点项目
    page = request.args.get('page', 1, type=int)
    inventory_result = request.args.get('inventory_result', '')
    
    query = InventoryItem.query.filter_by(inventory_id=inventory_id)
    
    if inventory_result:
        query = query.filter_by(inventory_result=inventory_result)
    
    pagination = query.order_by(InventoryItem.created_at).paginate(
        page=page, per_page=50, error_out=False
    )
    
    items = pagination.items
    
    # 统计信息
    stats = {
        'total': inventory_obj.total_assets,
        'inventoried': inventory_obj.inventoried_assets,
        'profit': inventory_obj.profit_assets,
        'loss': inventory_obj.loss_assets,
        'normal': db.session.query(InventoryItem).filter(
            InventoryItem.inventory_id == inventory_id,
            InventoryItem.inventory_result == 'normal'
        ).count(),
        'discrepancy': db.session.query(InventoryItem).filter(
            InventoryItem.inventory_id == inventory_id,
            InventoryItem.inventory_result == 'discrepancy'
        ).count()
    }
    
    return render_template('inventory/detail.html', 
        title='盘点详情',
        inventory=inventory_obj,
        items=items,
        pagination=pagination,
        stats=stats,
        inventory_result=inventory_result
    )

@inventory.route('/<int:inventory_id>/start', methods=['POST'])
@login_required
@manager_required
def start(inventory_id):
    inventory_obj = Inventory.query.get_or_404(inventory_id)
    
    if inventory_obj.status != 'pending':
        flash('该盘点计划已开始或已完成', 'danger')
        return redirect(url_for('inventory.detail', inventory_id=inventory_id))
    
    inventory_obj.status = 'in_progress'
    db.session.commit()
    
    flash('盘点计划已开始！员工可以开始扫码盘点', 'success')
    return redirect(url_for('inventory.detail', inventory_id=inventory_id))

@inventory.route('/<int:inventory_id>/complete', methods=['POST'])
@login_required
@manager_required
def complete(inventory_id):
    inventory_obj = Inventory.query.get_or_404(inventory_id)
    
    if inventory_obj.status != 'in_progress':
        flash('该盘点计划不在进行中', 'danger')
        return redirect(url_for('inventory.detail', inventory_id=inventory_id))
    
    # 检查是否所有资产都已盘点
    pending_count = InventoryItem.query.filter_by(
        inventory_id=inventory_id,
        inventory_result='pending'
    ).count()
    
    if pending_count > 0:
        flash(f'还有{pending_count}项资产未盘点，是否确认完成？', 'warning')
        # 可以添加确认逻辑
    
    inventory_obj.status = 'completed'
    db.session.commit()
    
    flash('盘点已完成！', 'success')
    return redirect(url_for('inventory.detail', inventory_id=inventory_id))

@inventory.route('/scan', methods=['GET', 'POST'])
@login_required
def scan():
    if request.method == 'POST':
        asset_code = request.form.get('asset_code')
        inventory_id = request.form.get('inventory_id', type=int)
        actual_quantity = request.form.get('actual_quantity', 1, type=int)
        actual_location = request.form.get('actual_location')
        actual_status = request.form.get('actual_status')
        remark = request.form.get('remark')
        
        # 查找资产
        asset = Asset.query.filter_by(asset_code=asset_code).first()
        
        if not asset:
            flash('未找到该资产', 'danger')
            return redirect(url_for('inventory.scan'))
        
        # 查找盘点项目
        inventory_item = None
        if inventory_id:
            inventory_item = InventoryItem.query.filter_by(
                inventory_id=inventory_id,
                asset_id=asset.id
            ).first()
        
        if not inventory_item:
            # 查找进行中的盘点计划
            active_inventory = Inventory.query.filter(
                Inventory.status == 'in_progress',
                Inventory.department_id == asset.department_id
            ).first()
            
            if active_inventory:
                inventory_item = InventoryItem.query.filter_by(
                    inventory_id=active_inventory.id,
                    asset_id=asset.id
                ).first()
        
        if not inventory_item:
            flash('该资产不在当前盘点计划中或盘点计划未开始', 'danger')
            return redirect(url_for('inventory.scan'))
        
        # 更新盘点项目
        inventory_item.actual_quantity = actual_quantity
        inventory_item.actual_location = actual_location or asset.location
        inventory_item.actual_status = actual_status or asset.status
        inventory_item.inventory_date = datetime.utcnow()
        inventory_item.inventory_by = current_user.id
        inventory_item.remark = remark
        
        # 判断盘点结果
        if inventory_item.expected_quantity == actual_quantity and \
           inventory_item.expected_location == actual_location and \
           inventory_item.expected_status == actual_status:
            inventory_item.inventory_result = 'normal'
        elif actual_quantity > inventory_item.expected_quantity:
            inventory_item.inventory_result = 'profit'
        elif actual_quantity < inventory_item.expected_quantity:
            inventory_item.inventory_result = 'loss'
        else:
            inventory_item.inventory_result = 'discrepancy'
        
        # 更新盘点统计
        inventory_obj = inventory_item.inventory
        inventory_obj.inventoried_assets = InventoryItem.query.filter_by(
            inventory_id=inventory_obj.id,
            inventory_result='pending'
        ).count()
        
        inventory_obj.profit_assets = InventoryItem.query.filter_by(
            inventory_id=inventory_obj.id,
            inventory_result='profit'
        ).count()
        
        inventory_obj.loss_assets = InventoryItem.query.filter_by(
            inventory_id=inventory_obj.id,
            inventory_result='loss'
        ).count()
        
        # 计算已盘点数量
        inventoried = InventoryItem.query.filter(
            InventoryItem.inventory_id == inventory_obj.id,
            InventoryItem.inventory_result != 'pending'
        ).count()
        inventory_obj.inventoried_assets = inventoried
        
        db.session.commit()
        
        flash(f'资产 {asset.name} 盘点完成！结果：{inventory_item.inventory_result}', 'success')
        return redirect(url_for('inventory.scan', inventory_id=inventory_obj.id))
    
    # 获取进行中的盘点计划
    active_inventories = Inventory.query.filter(
        Inventory.status == 'in_progress'
    ).all()
    
    # 如果只有一个进行中的盘点，自动选中
    selected_inventory = None
    if len(active_inventories) == 1:
        selected_inventory = active_inventories[0]
    
    return render_template('inventory/scan.html', 
        title='扫码盘点',
        active_inventories=active_inventories,
        selected_inventory=selected_inventory
    )

@inventory.route('/<int:inventory_id>/report')
@login_required
@manager_required
def report(inventory_id):
    inventory_obj = Inventory.query.get_or_404(inventory_id)
    
    # 获取所有盘点项目
    all_items = InventoryItem.query.filter_by(inventory_id=inventory_id).all()
    
    # 统计信息
    stats = {
        'total': len(all_items),
        'inventoried': sum(1 for item in all_items if item.inventory_result != 'pending'),
        'pending': sum(1 for item in all_items if item.inventory_result == 'pending'),
        'normal': sum(1 for item in all_items if item.inventory_result == 'normal'),
        'profit': sum(1 for item in all_items if item.inventory_result == 'profit'),
        'loss': sum(1 for item in all_items if item.inventory_result == 'loss'),
        'discrepancy': sum(1 for item in all_items if item.inventory_result == 'discrepancy')
    }
    
    # 盘盈资产
    profit_items = [item for item in all_items if item.inventory_result == 'profit']
    
    # 盘亏资产
    loss_items = [item for item in all_items if item.inventory_result == 'loss']
    
    # 差异资产
    discrepancy_items = [item for item in all_items if item.inventory_result == 'discrepancy']
    
    return render_template('inventory/report.html', 
        title='盘盈盘亏报告',
        inventory=inventory_obj,
        stats=stats,
        profit_items=profit_items,
        loss_items=loss_items,
        discrepancy_items=discrepancy_items
    )

@inventory.route('/api/asset-info')
@login_required
def api_asset_info():
    asset_code = request.args.get('asset_code', '')
    
    if not asset_code:
        return jsonify({'error': '请提供资产编码'}), 400
    
    asset = Asset.query.filter_by(asset_code=asset_code).first()
    
    if not asset:
        return jsonify({'error': '未找到该资产'}), 404
    
    return jsonify({
        'id': asset.id,
        'asset_code': asset.asset_code,
        'name': asset.name,
        'category': asset.category,
        'model': asset.model,
        'specification': asset.specification,
        'location': asset.location,
        'status': asset.status,
        'quantity': asset.quantity,
        'unit': asset.unit,
        'department': asset.department.name if asset.department else None
    })
