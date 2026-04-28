from datetime import datetime
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.supplier import supplier
from app import db
from app.models import (
    Supplier, SupplierEvaluation, PurchaseRequest, User, Department
)
from app.auth.views import role_required, manager_required


@supplier.route('/')
@login_required
def list():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    search = request.args.get('search', '')
    status = request.args.get('status', '')
    qualification_level = request.args.get('qualification_level', '')
    
    query = Supplier.query
    
    if search:
        query = query.filter(
            db.or_(
                Supplier.supplier_code.contains(search),
                Supplier.name.contains(search),
                Supplier.short_name.contains(search),
                Supplier.contact_person.contains(search)
            )
        )
    
    if status:
        query = query.filter_by(status=status)
    
    if qualification_level:
        query = query.filter_by(qualification_level=qualification_level)
    
    pagination = query.order_by(Supplier.rating.desc(), Supplier.total_amount.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    suppliers = pagination.items
    
    return render_template('supplier/list.html', 
        title='供应商管理',
        suppliers=suppliers,
        pagination=pagination,
        search=search,
        status=status,
        qualification_level=qualification_level
    )


@supplier.route('/<int:supplier_id>')
@login_required
def detail(supplier_id):
    supplier_obj = Supplier.query.get_or_404(supplier_id)
    
    # 获取采购记录
    purchase_requests = PurchaseRequest.query.filter_by(
        supplier_id=supplier_id
    ).order_by(PurchaseRequest.created_at.desc()).all()
    
    # 获取评价记录
    evaluations = SupplierEvaluation.query.filter_by(
        supplier_id=supplier_id
    ).order_by(SupplierEvaluation.evaluation_date.desc()).all()
    
    # 统计信息
    stats = {
        'total_orders': supplier_obj.total_orders,
        'total_amount': supplier_obj.total_amount,
        'avg_rating': supplier_obj.rating,
        'evaluation_count': len(evaluations)
    }
    
    return render_template('supplier/detail.html', 
        title=f'供应商详情 - {supplier_obj.name}',
        supplier=supplier_obj,
        purchase_requests=purchase_requests,
        evaluations=evaluations,
        stats=stats
    )


@supplier.route('/create', methods=['GET', 'POST'])
@login_required
@manager_required
def create():
    if request.method == 'POST':
        supplier_code = request.form.get('supplier_code')
        name = request.form.get('name')
        short_name = request.form.get('short_name')
        contact_person = request.form.get('contact_person')
        contact_phone = request.form.get('contact_phone')
        contact_email = request.form.get('contact_email')
        address = request.form.get('address')
        tax_id = request.form.get('tax_id')
        bank_name = request.form.get('bank_name')
        bank_account = request.form.get('bank_account')
        qualification_level = request.form.get('qualification_level', 'general')
        business_scope = request.form.get('business_scope')
        qualification_certificates = request.form.get('qualification_certificates')
        cooperation_start_date = request.form.get('cooperation_start_date')
        status = request.form.get('status', 'active')
        description = request.form.get('description')
        
        # 验证必填字段
        if not supplier_code or not name:
            flash('供应商编码和名称为必填项', 'danger')
            return redirect(url_for('supplier.create'))
        
        # 检查编码是否已存在
        if Supplier.query.filter_by(supplier_code=supplier_code).first():
            flash('供应商编码已存在', 'danger')
            return redirect(url_for('supplier.create'))
        
        # 创建供应商
        supplier_obj = Supplier(
            supplier_code=supplier_code,
            name=name,
            short_name=short_name,
            contact_person=contact_person,
            contact_phone=contact_phone,
            contact_email=contact_email,
            address=address,
            tax_id=tax_id,
            bank_name=bank_name,
            bank_account=bank_account,
            qualification_level=qualification_level,
            business_scope=business_scope,
            qualification_certificates=qualification_certificates,
            cooperation_start_date=datetime.strptime(cooperation_start_date, '%Y-%m-%d') if cooperation_start_date else None,
            status=status,
            description=description
        )
        
        db.session.add(supplier_obj)
        db.session.commit()
        
        flash('供应商创建成功！', 'success')
        return redirect(url_for('supplier.detail', supplier_id=supplier_obj.id))
    
    return render_template('supplier/create.html', 
        title='新增供应商'
    )


@supplier.route('/<int:supplier_id>/edit', methods=['GET', 'POST'])
@login_required
@manager_required
def edit(supplier_id):
    supplier_obj = Supplier.query.get_or_404(supplier_id)
    
    if request.method == 'POST':
        supplier_obj.name = request.form.get('name')
        supplier_obj.short_name = request.form.get('short_name')
        supplier_obj.contact_person = request.form.get('contact_person')
        supplier_obj.contact_phone = request.form.get('contact_phone')
        supplier_obj.contact_email = request.form.get('contact_email')
        supplier_obj.address = request.form.get('address')
        supplier_obj.tax_id = request.form.get('tax_id')
        supplier_obj.bank_name = request.form.get('bank_name')
        supplier_obj.bank_account = request.form.get('bank_account')
        supplier_obj.qualification_level = request.form.get('qualification_level', 'general')
        supplier_obj.business_scope = request.form.get('business_scope')
        supplier_obj.qualification_certificates = request.form.get('qualification_certificates')
        cooperation_start_date = request.form.get('cooperation_start_date')
        if cooperation_start_date:
            supplier_obj.cooperation_start_date = datetime.strptime(cooperation_start_date, '%Y-%m-%d')
        supplier_obj.status = request.form.get('status', 'active')
        supplier_obj.description = request.form.get('description')
        
        db.session.commit()
        
        flash('供应商信息更新成功！', 'success')
        return redirect(url_for('supplier.detail', supplier_id=supplier_obj.id))
    
    return render_template('supplier/edit.html', 
        title='编辑供应商',
        supplier=supplier_obj
    )


@supplier.route('/<int:supplier_id>/evaluate', methods=['GET', 'POST'])
@login_required
@manager_required
def evaluate(supplier_id):
    supplier_obj = Supplier.query.get_or_404(supplier_id)
    
    if request.method == 'POST':
        purchase_request_id = request.form.get('purchase_request_id', type=int)
        evaluation_type = request.form.get('evaluation_type', 'comprehensive')
        quality_rating = request.form.get('quality_rating', 5.0, type=float)
        delivery_rating = request.form.get('delivery_rating', 5.0, type=float)
        price_rating = request.form.get('price_rating', 5.0, type=float)
        service_rating = request.form.get('service_rating', 5.0, type=float)
        comment = request.form.get('comment')
        
        # 创建评价
        evaluation = SupplierEvaluation(
            supplier_id=supplier_id,
            purchase_request_id=purchase_request_id,
            evaluator_id=current_user.id,
            evaluation_type=evaluation_type,
            quality_rating=quality_rating,
            delivery_rating=delivery_rating,
            price_rating=price_rating,
            service_rating=service_rating,
            comment=comment,
            evaluation_date=datetime.utcnow()
        )
        
        # 计算综合评分
        evaluation.calculate_overall_rating()
        
        db.session.add(evaluation)
        
        # 更新供应商平均评分
        evaluations = SupplierEvaluation.query.filter_by(supplier_id=supplier_id).all()
        if evaluations:
            avg_rating = sum(e.overall_rating for e in evaluations) / len(evaluations)
            supplier_obj.rating = round(avg_rating, 2)
        
        db.session.commit()
        
        flash('供应商评价提交成功！', 'success')
        return redirect(url_for('supplier.detail', supplier_id=supplier_id))
    
    # 获取该供应商的采购订单
    purchase_requests = PurchaseRequest.query.filter_by(
        supplier_id=supplier_id,
        status='approved'
    ).order_by(PurchaseRequest.created_at.desc()).all()
    
    return render_template('supplier/evaluate.html', 
        title='供应商评价',
        supplier=supplier_obj,
        purchase_requests=purchase_requests
    )


@supplier.route('/api/search')
@login_required
def api_search():
    query = request.args.get('q', '')
    limit = request.args.get('limit', 10, type=int)
    
    suppliers = Supplier.query.filter(
        db.or_(
            Supplier.supplier_code.contains(query),
            Supplier.name.contains(query),
            Supplier.short_name.contains(query)
        ),
        Supplier.status == 'active'
    ).order_by(Supplier.rating.desc()).limit(limit).all()
    
    return jsonify([{
        'id': s.id,
        'supplier_code': s.supplier_code,
        'name': s.name,
        'short_name': s.short_name,
        'contact_person': s.contact_person,
        'contact_phone': s.contact_phone,
        'rating': s.rating
    } for s in suppliers])


@supplier.route('/api/stats/<int:supplier_id>')
@login_required
@manager_required
def api_stats(supplier_id):
    supplier_obj = Supplier.query.get_or_404(supplier_id)
    
    # 获取年度采购统计
    current_year = datetime.now().year
    purchase_requests = PurchaseRequest.query.filter(
        PurchaseRequest.supplier_id == supplier_id,
        PurchaseRequest.status == 'approved',
        db.func.strftime('%Y', PurchaseRequest.created_at) == str(current_year)
    ).all()
    
    monthly_data = {}
    for pr in purchase_requests:
        month = pr.created_at.month
        if month not in monthly_data:
            monthly_data[month] = {'count': 0, 'amount': 0}
        monthly_data[month]['count'] += 1
        monthly_data[month]['amount'] += pr.total_amount
    
    return jsonify({
        'total_orders': supplier_obj.total_orders,
        'total_amount': supplier_obj.total_amount,
        'rating': supplier_obj.rating,
        'monthly_data': monthly_data,
        'current_year': current_year
    })
