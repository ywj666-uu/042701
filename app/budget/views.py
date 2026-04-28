from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.budget import budget
from app import db
from app.models import (
    Budget, Department, User, PurchaseRequest, PurchaseRequestItem,
    Approval, BudgetUsageLog
)
from app.auth.views import role_required, manager_required

@budget.route('/')
@login_required
@manager_required
def list():
    page = request.args.get('page', 1, type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    
    # 获取所有部门的预算
    query = Budget.query.filter_by(year=year)
    
    # 如果是部门经理，只看自己部门的
    if current_user.role == 'manager':
        query = query.filter_by(department_id=current_user.department_id)
    
    pagination = query.order_by(Budget.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    budgets = pagination.items
    
    # 获取所有年份用于筛选
    years = db.session.query(Budget.year).distinct().order_by(Budget.year.desc()).all()
    years = [y[0] for y in years]
    if not years:
        years = [datetime.now().year]
    
    return render_template('budget/list.html', 
        title='预算管理',
        budgets=budgets,
        pagination=pagination,
        years=years,
        current_year=year
    )

@budget.route('/create', methods=['GET', 'POST'])
@login_required
@manager_required
def create():
    if request.method == 'POST':
        department_id = request.form.get('department_id', type=int)
        year = request.form.get('year', datetime.now().year, type=int)
        total_budget = request.form.get('total_budget', 0.0, type=float)
        warning_threshold = request.form.get('warning_threshold', 80.0, type=float)
        description = request.form.get('description')
        
        # 检查是否已存在该部门该年份的预算
        existing_budget = Budget.query.filter_by(
            department_id=department_id,
            year=year
        ).first()
        
        if existing_budget:
            flash('该部门该年度的预算已存在', 'danger')
            return redirect(url_for('budget.create'))
        
        # 创建预算
        budget_obj = Budget(
            department_id=department_id,
            year=year,
            total_budget=total_budget,
            used_budget=0.0,
            remaining_budget=total_budget,
            warning_threshold=warning_threshold,
            status='active',
            description=description
        )
        
        db.session.add(budget_obj)
        db.session.commit()
        
        flash('预算创建成功！', 'success')
        return redirect(url_for('budget.detail', budget_id=budget_obj.id))
    
    departments = Department.query.all()
    return render_template('budget/create.html', 
        title='创建预算',
        departments=departments,
        current_year=datetime.now().year
    )

@budget.route('/<int:budget_id>')
@login_required
@manager_required
def detail(budget_id):
    budget_obj = Budget.query.get_or_404(budget_id)
    
    # 获取预算使用记录
    usage_logs = BudgetUsageLog.query.filter_by(
        budget_id=budget_id
    ).order_by(BudgetUsageLog.created_at.desc()).all()
    
    # 获取相关的采购申请
    purchase_requests = PurchaseRequest.query.join(
        BudgetUsageLog,
        BudgetUsageLog.related_request_id == PurchaseRequest.id
    ).filter(
        BudgetUsageLog.budget_id == budget_id
    ).distinct().all()
    
    return render_template('budget/detail.html', 
        title='预算详情',
        budget=budget_obj,
        usage_logs=usage_logs,
        purchase_requests=purchase_requests
    )

@budget.route('/<int:budget_id>/edit', methods=['GET', 'POST'])
@login_required
@manager_required
def edit(budget_id):
    budget_obj = Budget.query.get_or_404(budget_id)
    
    if request.method == 'POST':
        total_budget = request.form.get('total_budget', 0.0, type=float)
        warning_threshold = request.form.get('warning_threshold', 80.0, type=float)
        description = request.form.get('description')
        status = request.form.get('status', 'active')
        
        # 更新预算
        budget_obj.total_budget = total_budget
        budget_obj.remaining_budget = total_budget - budget_obj.used_budget
        budget_obj.warning_threshold = warning_threshold
        budget_obj.description = description
        budget_obj.status = status
        
        db.session.commit()
        
        flash('预算更新成功！', 'success')
        return redirect(url_for('budget.detail', budget_id=budget_obj.id))
    
    departments = Department.query.all()
    return render_template('budget/edit.html', 
        title='编辑预算',
        budget=budget_obj,
        departments=departments
    )

@budget.route('/purchase')
@login_required
def purchase_list():
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    department_id = request.args.get('department_id', type=int)
    
    query = PurchaseRequest.query
    
    if status:
        query = query.filter_by(status=status)
    
    if department_id:
        query = query.filter_by(department_id=department_id)
    
    # 如果不是管理员，只看自己部门的或自己申请的
    if current_user.role not in ['manager', 'admin']:
        query = query.filter(
            db.or_(
                PurchaseRequest.requester_id == current_user.id,
                PurchaseRequest.department_id == current_user.department_id
            )
        )
    
    pagination = query.order_by(PurchaseRequest.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    purchase_requests = pagination.items
    departments = Department.query.all()
    
    return render_template('budget/purchase_list.html', 
        title='采购申请',
        purchase_requests=purchase_requests,
        pagination=pagination,
        departments=departments,
        status=status,
        department_id=department_id
    )

@budget.route('/purchase/create', methods=['GET', 'POST'])
@login_required
def purchase_create():
    if request.method == 'POST':
        # 获取表单数据
        department_id = request.form.get('department_id', type=int) or current_user.department_id
        title = request.form.get('title')
        description = request.form.get('description')
        budget_year = request.form.get('budget_year', datetime.now().year, type=int)
        
        # 获取采购物品列表
        item_names = request.form.getlist('item_name[]')
        item_categories = request.form.getlist('item_category[]')
        item_models = request.form.getlist('item_model[]')
        item_specifications = request.form.getlist('item_specification[]')
        item_units = request.form.getlist('item_unit[]')
        item_quantities = request.form.getlist('item_quantity[]')
        item_prices = request.form.getlist('item_price[]')
        item_descriptions = request.form.getlist('item_description[]')
        
        # 计算总金额
        total_amount = 0.0
        items = []
        for i in range(len(item_names)):
            if item_names[i]:
                quantity = int(item_quantities[i]) if item_quantities[i] else 1
                price = float(item_prices[i]) if item_prices[i] else 0.0
                total_price = quantity * price
                total_amount += total_price
                
                items.append({
                    'name': item_names[i],
                    'category': item_categories[i],
                    'model': item_models[i],
                    'specification': item_specifications[i],
                    'unit': item_units[i] or '台',
                    'quantity': quantity,
                    'unit_price': price,
                    'total_price': total_price,
                    'description': item_descriptions[i]
                })
        
        # 检查预算
        budget_obj = None
        is_over_budget = False
        special_approval_required = False
        
        if department_id:
            budget_obj = Budget.query.filter_by(
                department_id=department_id,
                year=budget_year,
                status='active'
            ).first()
            
            if budget_obj:
                # 检查是否超预算
                if budget_obj.remaining_budget < total_amount:
                    is_over_budget = True
                    special_approval_required = True
                    flash('采购金额超出部门预算，需要上级特批', 'warning')
                
                # 检查是否达到预警阈值
                usage_percentage = ((budget_obj.used_budget + total_amount) / budget_obj.total_budget) * 100
                if usage_percentage >= budget_obj.warning_threshold:
                    flash(f'预算使用率已达到{usage_percentage:.1f}%，请注意控制', 'warning')
        
        # 创建采购申请
        purchase_request = PurchaseRequest(
            request_no=f'PR{datetime.now().strftime("%Y%m%d%H%M%S")}',
            department_id=department_id,
            requester_id=current_user.id,
            title=title,
            description=description,
            total_amount=total_amount,
            budget_year=budget_year,
            status='pending',
            is_over_budget=is_over_budget,
            special_approval_required=special_approval_required
        )
        
        db.session.add(purchase_request)
        db.session.flush()  # 获取ID
        
        # 创建采购物品
        for item in items:
            pr_item = PurchaseRequestItem(
                purchase_request_id=purchase_request.id,
                name=item['name'],
                category=item['category'],
                model=item['model'],
                specification=item['specification'],
                unit=item['unit'],
                quantity=item['quantity'],
                unit_price=item['unit_price'],
                total_price=item['total_price'],
                description=item['description']
            )
            db.session.add(pr_item)
        
        # 创建审批
        approval = Approval(
            approval_no=f'AP{datetime.now().strftime("%Y%m%d%H%M%S")}',
            approval_type='purchase',
            purchase_request_id=purchase_request.id,
            status='pending',
            level=2 if special_approval_required else 1
        )
        
        # 查找审批人
        if special_approval_required:
            # 需要管理员审批
            admin = User.query.filter_by(role='admin').first()
            if admin:
                approval.approver_id = admin.id
        else:
            # 部门经理审批
            if department_id:
                dept_manager = User.query.filter_by(
                    department_id=department_id,
                    role='manager'
                ).first()
                if dept_manager:
                    approval.approver_id = dept_manager.id
        
        db.session.add(approval)
        db.session.commit()
        
        flash('采购申请已提交，等待审批', 'success')
        return redirect(url_for('budget.purchase_detail', request_id=purchase_request.id))
    
    departments = Department.query.all()
    return render_template('budget/purchase_create.html', 
        title='创建采购申请',
        departments=departments,
        current_year=datetime.now().year
    )

@budget.route('/purchase/<int:request_id>')
@login_required
def purchase_detail(request_id):
    purchase_request = PurchaseRequest.query.get_or_404(request_id)
    
    # 获取采购物品
    items = PurchaseRequestItem.query.filter_by(
        purchase_request_id=request_id
    ).all()
    
    # 获取审批记录
    approvals = Approval.query.filter_by(
        purchase_request_id=request_id
    ).order_by(Approval.created_at).all()
    
    return render_template('budget/purchase_detail.html', 
        title='采购申请详情',
        purchase_request=purchase_request,
        items=items,
        approvals=approvals
    )

@budget.route('/purchase/<int:request_id>/approve', methods=['POST'])
@login_required
@manager_required
def purchase_approve(request_id):
    purchase_request = PurchaseRequest.query.get_or_404(request_id)
    
    # 检查是否有权限审批
    approval = Approval.query.filter_by(
        purchase_request_id=request_id,
        approver_id=current_user.id,
        status='pending'
    ).first()
    
    if not approval:
        flash('您没有权限审批此申请或申请已被处理', 'danger')
        return redirect(url_for('budget.purchase_detail', request_id=request_id))
    
    comment = request.form.get('comment', '')
    
    # 更新审批
    approval.status = 'approved'
    approval.comment = comment
    approval.approval_date = datetime.utcnow()
    
    # 更新采购申请状态
    purchase_request.status = 'approved'
    
    # 如果有预算，更新预算使用
    if purchase_request.department_id and purchase_request.budget_year:
        budget_obj = Budget.query.filter_by(
            department_id=purchase_request.department_id,
            year=purchase_request.budget_year,
            status='active'
        ).first()
        
        if budget_obj:
            # 检查预算是否足够
            if budget_obj.remaining_budget >= purchase_request.total_amount:
                budget_obj.used_budget += purchase_request.total_amount
                budget_obj.remaining_budget -= purchase_request.total_amount
                
                # 记录预算使用日志
                usage_log = BudgetUsageLog(
                    budget_id=budget_obj.id,
                    amount=purchase_request.total_amount,
                    usage_type='purchase',
                    related_request_id=purchase_request.id,
                    description=f'采购申请 {purchase_request.request_no} 审批通过',
                    operator_id=current_user.id
                )
                db.session.add(usage_log)
            else:
                flash('预算不足，无法审批通过', 'danger')
                return redirect(url_for('budget.purchase_detail', request_id=request_id))
    
    db.session.commit()
    
    flash('采购申请已审批通过', 'success')
    return redirect(url_for('budget.purchase_detail', request_id=request_id))

@budget.route('/purchase/<int:request_id>/reject', methods=['POST'])
@login_required
@manager_required
def purchase_reject(request_id):
    purchase_request = PurchaseRequest.query.get_or_404(request_id)
    
    # 检查是否有权限审批
    approval = Approval.query.filter_by(
        purchase_request_id=request_id,
        approver_id=current_user.id,
        status='pending'
    ).first()
    
    if not approval:
        flash('您没有权限审批此申请或申请已被处理', 'danger')
        return redirect(url_for('budget.purchase_detail', request_id=request_id))
    
    comment = request.form.get('comment', '')
    
    # 更新审批
    approval.status = 'rejected'
    approval.comment = comment
    approval.approval_date = datetime.utcnow()
    
    # 更新采购申请状态
    purchase_request.status = 'rejected'
    
    db.session.commit()
    
    flash('采购申请已拒绝', 'warning')
    return redirect(url_for('budget.purchase_detail', request_id=request_id))

@budget.route('/api/check-budget')
@login_required
def api_check_budget():
    department_id = request.args.get('department_id', type=int)
    year = request.args.get('year', datetime.now().year, type=int)
    amount = request.args.get('amount', 0.0, type=float)
    
    budget_obj = Budget.query.filter_by(
        department_id=department_id,
        year=year,
        status='active'
    ).first()
    
    if not budget_obj:
        return jsonify({
            'has_budget': False,
            'message': '该部门该年度未设置预算'
        })
    
    is_over_budget = budget_obj.remaining_budget < amount
    usage_percentage = ((budget_obj.used_budget + amount) / budget_obj.total_budget) * 100
    is_warning = usage_percentage >= budget_obj.warning_threshold
    
    return jsonify({
        'has_budget': True,
        'total_budget': budget_obj.total_budget,
        'used_budget': budget_obj.used_budget,
        'remaining_budget': budget_obj.remaining_budget,
        'is_over_budget': is_over_budget,
        'is_warning': is_warning,
        'usage_percentage': usage_percentage,
        'warning_threshold': budget_obj.warning_threshold
    })
