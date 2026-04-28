from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import CheckConstraint, event
from sqlalchemy.orm import validates
from app import db, login_manager


MODELS_WITH_UPDATED_AT = [
    'Asset', 'PurchaseRequest', 'AssetBorrow', 'AssetDisposal',
    'Budget', 'Inventory', 'Maintenance', 'MaintenancePlan',
    'Approval', 'AssetTransfer', 'Supplier', 'SupplierEvaluation',
    'InventoryResult', 'QRCodeRecord'
]

MODELS_WITH_CREATED_AT = [
    'User', 'Department', 'Asset', 'AssetStatusLog', 'PurchaseRequest',
    'PurchaseRequestItem', 'AssetEntry', 'AssetEntryItem', 'AssetBorrow',
    'AssetDisposal', 'Budget', 'BudgetUsageLog', 'Inventory', 'InventoryItem',
    'Maintenance', 'MaintenancePlan', 'Approval', 'AssetTransfer', 'Notification',
    'Supplier', 'SupplierEvaluation', 'InventoryResult', 'QRCodeRecord'
]


@event.listens_for(db.session, 'before_flush')
def before_flush_handler(session, flush_context, instances):
    current_time = datetime.utcnow()
    
    for instance in session.new:
        class_name = instance.__class__.__name__
        
        if class_name in MODELS_WITH_CREATED_AT:
            if hasattr(instance, 'created_at') and instance.created_at is None:
                instance.created_at = current_time
        
        if class_name in MODELS_WITH_UPDATED_AT:
            if hasattr(instance, 'updated_at'):
                instance.updated_at = current_time
        
        if class_name == 'PurchaseRequest':
            validate_purchase_request_budget_before_flush(instance)
    
    for instance in session.dirty:
        class_name = instance.__class__.__name__
        
        if class_name in MODELS_WITH_UPDATED_AT:
            if hasattr(instance, 'updated_at'):
                instance.updated_at = current_time
        
        if class_name == 'PurchaseRequest':
            validate_purchase_request_budget_before_flush(instance)


def validate_purchase_request_budget_before_flush(purchase_request):
    if not purchase_request.department_id or not purchase_request.budget_year:
        purchase_request.is_over_budget = False
        purchase_request.special_approval_required = False
        return
    
    budget = db.session.query(Budget).filter_by(
        department_id=purchase_request.department_id,
        year=purchase_request.budget_year,
        status='active'
    ).first()
    
    if not budget:
        purchase_request.is_over_budget = False
        purchase_request.special_approval_required = False
        return
    
    if purchase_request.total_amount > budget.remaining_budget:
        purchase_request.is_over_budget = True
        purchase_request.special_approval_required = True
    else:
        purchase_request.is_over_budget = False
        
        usage_percentage = ((budget.used_budget + purchase_request.total_amount) / budget.total_budget) * 100
        if usage_percentage >= budget.warning_threshold:
            purchase_request.special_approval_required = False
        else:
            purchase_request.special_approval_required = False


class BudgetConstraint:
    @staticmethod
    def validate_budget_amount(mapper, connection, target):
        if hasattr(target, 'total_budget') and hasattr(target, 'used_budget'):
            if target.total_budget < 0:
                raise ValueError('预算总额不能为负数')
            if target.used_budget < 0:
                raise ValueError('已使用预算不能为负数')
            if target.used_budget > target.total_budget:
                raise ValueError('已使用预算不能超过总预算')
            if hasattr(target, 'remaining_budget'):
                expected_remaining = target.total_budget - target.used_budget
                if abs(target.remaining_budget - expected_remaining) > 0.01:
                    target.remaining_budget = expected_remaining


@event.listens_for(Budget, 'before_insert')
@event.listens_for(Budget, 'before_update')
def validate_budget(mapper, connection, target):
    BudgetConstraint.validate_budget_amount(mapper, connection, target)





class User(UserMixin, db.Model):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(120), unique=True, index=True, nullable=False)
    name = db.Column(db.String(64), nullable=False)
    role = db.Column(db.String(20), default='employee', nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        CheckConstraint("role IN ('employee', 'manager', 'admin')", name='ck_user_role'),
    )
    
    borrows = db.relationship('AssetBorrow', backref='borrower', lazy='dynamic')
    inventories = db.relationship('Inventory', backref='operator', lazy='dynamic')
    maintenances = db.relationship('Maintenance', backref='operator', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')
    approvals = db.relationship('Approval', backref='approver', lazy='dynamic')
    
    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')
    
    @password.setter
    def password(self, password):
        if not password or len(password) < 6:
            raise ValueError('密码长度至少为6位')
        self.password_hash = generate_password_hash(password)
    
    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    @validates('role')
    def validate_role(self, key, role):
        valid_roles = ['employee', 'manager', 'admin']
        if role not in valid_roles:
            raise ValueError(f'无效的角色: {role}。有效角色: {valid_roles}')
        return role
    
    def __repr__(self):
        return f'<User {self.username}>'


class Department(db.Model):
    __tablename__ = 'department'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, index=True, nullable=False)
    description = db.Column(db.String(200))
    manager_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    users = db.relationship('User', backref='department', lazy='dynamic', 
                           foreign_keys='User.department_id')
    assets = db.relationship('Asset', backref='department', lazy='dynamic')
    budgets = db.relationship('Budget', backref='department', lazy='dynamic')
    purchase_requests = db.relationship('PurchaseRequest', backref='department', lazy='dynamic')
    
    def __repr__(self):
        return f'<Department {self.name}>'


class Asset(db.Model):
    __tablename__ = 'asset'
    
    VALID_STATUSES = ['in_stock', 'in_use', 'maintenance', 'disposed']
    
    id = db.Column(db.Integer, primary_key=True)
    asset_code = db.Column(db.String(64), unique=True, index=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    category = db.Column(db.String(64))
    model = db.Column(db.String(64))
    specification = db.Column(db.String(128))
    unit = db.Column(db.String(20), default='台')
    quantity = db.Column(db.Integer, default=1, nullable=False)
    unit_price = db.Column(db.Float, default=0.0, nullable=False)
    total_value = db.Column(db.Float, default=0.0, nullable=False)
    purchase_date = db.Column(db.DateTime)
    warranty_period = db.Column(db.Integer)
    location = db.Column(db.String(128))
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    status = db.Column(db.String(20), default='in_stock', nullable=False)
    description = db.Column(db.Text)
    qr_code = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"status IN ('in_stock', 'in_use', 'maintenance', 'disposed')", 
                       name='ck_asset_status'),
        CheckConstraint('quantity >= 0', name='ck_asset_quantity'),
        CheckConstraint('unit_price >= 0', name='ck_asset_unit_price'),
        CheckConstraint('total_value >= 0', name='ck_asset_total_value'),
    )
    
    borrows = db.relationship('AssetBorrow', backref='asset', lazy='dynamic')
    inventories = db.relationship('InventoryItem', backref='asset', lazy='dynamic')
    maintenances = db.relationship('Maintenance', backref='asset', lazy='dynamic')
    status_logs = db.relationship('AssetStatusLog', backref='asset', lazy='dynamic')
    
    @validates('status')
    def validate_status(self, key, status):
        if status not in self.VALID_STATUSES:
            raise ValueError(f'无效的状态: {status}。有效状态: {self.VALID_STATUSES}')
        return status
    
    @validates('quantity', 'unit_price')
    def validate_positive(self, key, value):
        if value < 0:
            raise ValueError(f'{key} 不能为负数')
        return value
    
    def __repr__(self):
        return f'<Asset {self.asset_code} - {self.name}>'


@event.listens_for(Asset, 'before_insert')
@event.listens_for(Asset, 'before_update')
def calculate_asset_total_value(mapper, connection, target):
    if target.quantity is not None and target.unit_price is not None:
        target.total_value = target.quantity * target.unit_price


class AssetStatusLog(db.Model):
    __tablename__ = 'asset_status_log'
    
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    previous_status = db.Column(db.String(20))
    description = db.Column(db.Text)
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
    
    def __repr__(self):
        return f'<AssetStatusLog {self.asset_id}: {self.previous_status} -> {self.status}>'


class PurchaseRequest(db.Model):
    __tablename__ = 'purchase_request'
    
    VALID_STATUSES = ['pending', 'approved', 'rejected', 'completed']
    
    id = db.Column(db.Integer, primary_key=True)
    request_no = db.Column(db.String(64), unique=True, index=True, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False)
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'))
    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    total_amount = db.Column(db.Float, default=0.0, nullable=False)
    budget_year = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)
    is_over_budget = db.Column(db.Boolean, default=False, nullable=False)
    special_approval_required = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"status IN ('pending', 'approved', 'rejected', 'completed')", 
                       name='ck_purchase_request_status'),
        CheckConstraint('total_amount >= 0', name='ck_purchase_request_amount'),
    )
    
    items = db.relationship('PurchaseRequestItem', backref='request', lazy='dynamic', 
                           cascade='all, delete-orphan')
    approvals = db.relationship('Approval', backref='purchase_request', lazy='dynamic',
                               cascade='all, delete-orphan')
    
    @validates('status')
    def validate_status(self, key, status):
        if status not in self.VALID_STATUSES:
            raise ValueError(f'无效的状态: {status}')
        return status
    
    def check_budget_available(self):
        if not self.department_id or not self.budget_year:
            return True
        
        budget = Budget.query.filter_by(
            department_id=self.department_id,
            year=self.budget_year,
            status='active'
        ).first()
        
        if not budget:
            return True
        
        return budget.remaining_budget >= self.total_amount
    
    def get_remaining_budget(self):
        if not self.department_id or not self.budget_year:
            return None
        
        budget = Budget.query.filter_by(
            department_id=self.department_id,
            year=self.budget_year,
            status='active'
        ).first()
        
        return budget.remaining_budget if budget else None
    
    def __repr__(self):
        return f'<PurchaseRequest {self.request_no}>'


@event.listens_for(PurchaseRequestItem, 'before_insert')
@event.listens_for(PurchaseRequestItem, 'before_update')
def calculate_item_total_price(mapper, connection, target):
    if target.quantity is not None and target.unit_price is not None:
        target.total_price = target.quantity * target.unit_price


class PurchaseRequestItem(db.Model):
    __tablename__ = 'purchase_request_item'
    
    id = db.Column(db.Integer, primary_key=True)
    purchase_request_id = db.Column(db.Integer, db.ForeignKey('purchase_request.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    category = db.Column(db.String(64))
    model = db.Column(db.String(64))
    specification = db.Column(db.String(128))
    unit = db.Column(db.String(20), default='台')
    quantity = db.Column(db.Integer, default=1, nullable=False)
    unit_price = db.Column(db.Float, default=0.0, nullable=False)
    total_price = db.Column(db.Float, default=0.0, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint('quantity >= 0', name='ck_pri_quantity'),
        CheckConstraint('unit_price >= 0', name='ck_pri_unit_price'),
        CheckConstraint('total_price >= 0', name='ck_pri_total_price'),
    )
    
    @validates('quantity', 'unit_price')
    def validate_positive(self, key, value):
        if value < 0:
            raise ValueError(f'{key} 不能为负数')
        return value
    
    def __repr__(self):
        return f'<PurchaseRequestItem {self.name}>'


class AssetEntry(db.Model):
    __tablename__ = 'asset_entry'
    
    id = db.Column(db.Integer, primary_key=True)
    entry_no = db.Column(db.String(64), unique=True, index=True, nullable=False)
    purchase_request_id = db.Column(db.Integer, db.ForeignKey('purchase_request.id'))
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    entry_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    total_items = db.Column(db.Integer, default=0, nullable=False)
    total_value = db.Column(db.Float, default=0.0, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint('total_items >= 0', name='ck_asset_entry_items'),
        CheckConstraint('total_value >= 0', name='ck_asset_entry_value'),
    )
    
    items = db.relationship('AssetEntryItem', backref='entry', lazy='dynamic',
                           cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<AssetEntry {self.entry_no}>'


class AssetEntryItem(db.Model):
    __tablename__ = 'asset_entry_item'
    
    id = db.Column(db.Integer, primary_key=True)
    asset_entry_id = db.Column(db.Integer, db.ForeignKey('asset_entry.id'), nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    unit_price = db.Column(db.Float, default=0.0, nullable=False)
    total_price = db.Column(db.Float, default=0.0, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint('quantity >= 0', name='ck_aei_quantity'),
        CheckConstraint('unit_price >= 0', name='ck_aei_unit_price'),
        CheckConstraint('total_price >= 0', name='ck_aei_total_price'),
    )
    
    def __repr__(self):
        return f'<AssetEntryItem {self.asset_id}>'


class AssetBorrow(db.Model):
    __tablename__ = 'asset_borrow'
    
    VALID_STATUSES = ['pending', 'approved', 'borrowed', 'returned', 'rejected']
    VALID_TYPES = ['borrow', 'use']
    
    id = db.Column(db.Integer, primary_key=True)
    borrow_no = db.Column(db.String(64), unique=True, index=True, nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    borrower_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    borrow_type = db.Column(db.String(20), default='borrow', nullable=False)
    purpose = db.Column(db.String(256))
    expected_return_date = db.Column(db.DateTime)
    actual_return_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='pending', nullable=False)
    borrow_date = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"status IN ('pending', 'approved', 'borrowed', 'returned', 'rejected')", 
                       name='ck_asset_borrow_status'),
        CheckConstraint(f"borrow_type IN ('borrow', 'use')", 
                       name='ck_asset_borrow_type'),
    )
    
    approvals = db.relationship('Approval', backref='asset_borrow', lazy='dynamic',
                               cascade='all, delete-orphan')
    
    @validates('status')
    def validate_status(self, key, status):
        if status not in self.VALID_STATUSES:
            raise ValueError(f'无效的状态: {status}')
        return status
    
    @validates('borrow_type')
    def validate_borrow_type(self, key, borrow_type):
        if borrow_type not in self.VALID_TYPES:
            raise ValueError(f'无效的借用类型: {borrow_type}')
        return borrow_type
    
    def __repr__(self):
        return f'<AssetBorrow {self.borrow_no}>'


class AssetDisposal(db.Model):
    __tablename__ = 'asset_disposal'
    
    VALID_STATUSES = ['pending', 'approved', 'rejected', 'completed']
    VALID_TYPES = ['scrap', 'sell', 'donate', 'lost']
    
    id = db.Column(db.Integer, primary_key=True)
    disposal_no = db.Column(db.String(64), unique=True, index=True, nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    applicant_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    disposal_type = db.Column(db.String(20), nullable=False)
    reason = db.Column(db.Text, nullable=False)
    estimated_value = db.Column(db.Float, default=0.0, nullable=False)
    actual_value = db.Column(db.Float, default=0.0, nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False)
    disposal_date = db.Column(db.DateTime)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"status IN ('pending', 'approved', 'rejected', 'completed')", 
                       name='ck_asset_disposal_status'),
        CheckConstraint(f"disposal_type IN ('scrap', 'sell', 'donate', 'lost')", 
                       name='ck_asset_disposal_type'),
        CheckConstraint('estimated_value >= 0', name='ck_disposal_estimated_value'),
        CheckConstraint('actual_value >= 0', name='ck_disposal_actual_value'),
    )
    
    approvals = db.relationship('Approval', backref='asset_disposal', lazy='dynamic',
                               cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<AssetDisposal {self.disposal_no}>'


class Budget(db.Model):
    __tablename__ = 'budget'
    
    VALID_STATUSES = ['active', 'closed']
    
    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    total_budget = db.Column(db.Float, default=0.0, nullable=False)
    used_budget = db.Column(db.Float, default=0.0, nullable=False)
    remaining_budget = db.Column(db.Float, default=0.0, nullable=False)
    warning_threshold = db.Column(db.Float, default=80.0, nullable=False)
    status = db.Column(db.String(20), default='active', nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"status IN ('active', 'closed')", name='ck_budget_status'),
        CheckConstraint('total_budget >= 0', name='ck_budget_total'),
        CheckConstraint('used_budget >= 0', name='ck_budget_used'),
        CheckConstraint('remaining_budget >= 0', name='ck_budget_remaining'),
        CheckConstraint('warning_threshold >= 0 AND warning_threshold <= 100', 
                       name='ck_budget_threshold'),
        CheckConstraint('used_budget <= total_budget', name='ck_budget_used_le_total'),
        db.UniqueConstraint('department_id', 'year', name='uq_budget_dept_year'),
    )
    
    usage_logs = db.relationship('BudgetUsageLog', backref='budget', lazy='dynamic',
                                 cascade='all, delete-orphan')
    
    @validates('warning_threshold')
    def validate_threshold(self, key, value):
        if value < 0 or value > 100:
            raise ValueError('预警阈值必须在0-100之间')
        return value
    
    @property
    def usage_percentage(self):
        if self.total_budget > 0:
            return (self.used_budget / self.total_budget) * 100
        return 0
    
    @property
    def is_over_warning(self):
        return self.usage_percentage >= self.warning_threshold
    
    def check_available(self, amount):
        if amount <= 0:
            raise ValueError('金额必须大于0')
        return self.remaining_budget >= amount
    
    def allocate(self, amount, operator_id=None, description='', related_request_id=None):
        if not self.check_available(amount):
            raise ValueError(f'预算不足。剩余预算: {self.remaining_budget}, 申请金额: {amount}')
        
        self.used_budget += amount
        self.remaining_budget = self.total_budget - self.used_budget
        
        usage_log = BudgetUsageLog(
            budget_id=self.id,
            amount=amount,
            usage_type='purchase',
            related_request_id=related_request_id,
            description=description or f'预算分配: {amount}',
            operator_id=operator_id
        )
        db.session.add(usage_log)
        
        return usage_log
    
    def release(self, amount, operator_id=None, description=''):
        if amount <= 0:
            raise ValueError('释放金额必须大于0')
        if amount > self.used_budget:
            raise ValueError(f'释放金额不能超过已使用预算。已使用: {self.used_budget}')
        
        self.used_budget -= amount
        self.remaining_budget = self.total_budget - self.used_budget
        
        usage_log = BudgetUsageLog(
            budget_id=self.id,
            amount=-amount,
            usage_type='adjustment',
            description=description or f'预算释放: {amount}',
            operator_id=operator_id
        )
        db.session.add(usage_log)
        
        return usage_log
    
    def __repr__(self):
        return f'<Budget {self.department_id} - {self.year}>'


class BudgetUsageLog(db.Model):
    __tablename__ = 'budget_usage_log'
    
    VALID_TYPES = ['purchase', 'adjustment']
    
    id = db.Column(db.Integer, primary_key=True)
    budget_id = db.Column(db.Integer, db.ForeignKey('budget.id'), nullable=False)
    amount = db.Column(db.Float, default=0.0, nullable=False)
    usage_type = db.Column(db.String(20), nullable=False)
    related_request_id = db.Column(db.Integer, db.ForeignKey('purchase_request.id'))
    description = db.Column(db.Text)
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"usage_type IN ('purchase', 'adjustment')", 
                       name='ck_budget_usage_type'),
    )
    
    def __repr__(self):
        return f'<BudgetUsageLog {self.budget_id} - {self.amount}>'


class Inventory(db.Model):
    __tablename__ = 'inventory'
    
    VALID_STATUSES = ['pending', 'in_progress', 'completed']
    VALID_TYPES = ['annual', 'quarterly', 'temporary']
    
    id = db.Column(db.Integer, primary_key=True)
    inventory_no = db.Column(db.String(64), unique=True, index=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    inventory_type = db.Column(db.String(20), default='annual', nullable=False)
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='pending', nullable=False)
    total_assets = db.Column(db.Integer, default=0, nullable=False)
    inventoried_assets = db.Column(db.Integer, default=0, nullable=False)
    profit_assets = db.Column(db.Integer, default=0, nullable=False)
    loss_assets = db.Column(db.Integer, default=0, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"status IN ('pending', 'in_progress', 'completed')", 
                       name='ck_inventory_status'),
        CheckConstraint(f"inventory_type IN ('annual', 'quarterly', 'temporary')", 
                       name='ck_inventory_type'),
        CheckConstraint('total_assets >= 0', name='ck_inventory_total'),
        CheckConstraint('inventoried_assets >= 0', name='ck_inventory_inventoried'),
        CheckConstraint('profit_assets >= 0', name='ck_inventory_profit'),
        CheckConstraint('loss_assets >= 0', name='ck_inventory_loss'),
    )
    
    items = db.relationship('InventoryItem', backref='inventory', lazy='dynamic',
                           cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Inventory {self.inventory_no}>'


class InventoryItem(db.Model):
    __tablename__ = 'inventory_item'
    
    VALID_RESULTS = ['pending', 'normal', 'profit', 'loss', 'discrepancy']
    
    id = db.Column(db.Integer, primary_key=True)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.id'), nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    expected_quantity = db.Column(db.Integer, default=1, nullable=False)
    actual_quantity = db.Column(db.Integer, default=0, nullable=False)
    expected_location = db.Column(db.String(128))
    actual_location = db.Column(db.String(128))
    expected_status = db.Column(db.String(20))
    actual_status = db.Column(db.String(20))
    inventory_result = db.Column(db.String(20), default='pending')
    inventory_date = db.Column(db.DateTime)
    inventory_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"inventory_result IN ('pending', 'normal', 'profit', 'loss', 'discrepancy')", 
                       name='ck_inventory_item_result'),
        CheckConstraint('expected_quantity >= 0', name='ck_ii_expected_qty'),
        CheckConstraint('actual_quantity >= 0', name='ck_ii_actual_qty'),
    )
    
    def __repr__(self):
        return f'<InventoryItem {self.asset_id} - {self.inventory_result}>'


class Maintenance(db.Model):
    __tablename__ = 'maintenance'
    
    VALID_STATUSES = ['scheduled', 'in_progress', 'completed', 'cancelled']
    VALID_TYPES = ['repair', 'maintenance', 'inspection']
    
    id = db.Column(db.Integer, primary_key=True)
    maintenance_no = db.Column(db.String(64), unique=True, index=True, nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    maintenance_type = db.Column(db.String(20), nullable=False)
    description = db.Column(db.Text)
    schedule_date = db.Column(db.DateTime)
    actual_date = db.Column(db.DateTime)
    duration = db.Column(db.Float, default=0.0, nullable=False)
    cost = db.Column(db.Float, default=0.0, nullable=False)
    status = db.Column(db.String(20), default='scheduled', nullable=False)
    next_maintenance_date = db.Column(db.DateTime)
    remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"status IN ('scheduled', 'in_progress', 'completed', 'cancelled')", 
                       name='ck_maintenance_status'),
        CheckConstraint(f"maintenance_type IN ('repair', 'maintenance', 'inspection')", 
                       name='ck_maintenance_type'),
        CheckConstraint('duration >= 0', name='ck_maintenance_duration'),
        CheckConstraint('cost >= 0', name='ck_maintenance_cost'),
    )
    
    def __repr__(self):
        return f'<Maintenance {self.maintenance_no}>'


class MaintenancePlan(db.Model):
    __tablename__ = 'maintenance_plan'
    
    VALID_PLAN_TYPES = ['category', 'specific']
    VALID_MAINTENANCE_TYPES = ['repair', 'maintenance', 'inspection']
    
    id = db.Column(db.Integer, primary_key=True)
    asset_category = db.Column(db.String(64))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    plan_type = db.Column(db.String(20), nullable=False)
    maintenance_type = db.Column(db.String(20), nullable=False)
    interval_days = db.Column(db.Integer)
    next_maintenance_date = db.Column(db.DateTime)
    duration = db.Column(db.Float, default=0.0, nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"plan_type IN ('category', 'specific')", 
                       name='ck_maintenance_plan_type'),
        CheckConstraint(f"maintenance_type IN ('repair', 'maintenance', 'inspection')", 
                       name='ck_mp_maintenance_type'),
        CheckConstraint('interval_days > 0 OR interval_days IS NULL', 
                       name='ck_mp_interval_days'),
        CheckConstraint('duration >= 0', name='ck_mp_duration'),
    )
    
    def __repr__(self):
        return f'<MaintenancePlan {self.asset_category or self.asset_id}>'


class Approval(db.Model):
    __tablename__ = 'approval'
    
    VALID_STATUSES = ['pending', 'approved', 'rejected']
    VALID_TYPES = ['purchase', 'borrow', 'disposal', 'transfer']
    
    id = db.Column(db.Integer, primary_key=True)
    approval_no = db.Column(db.String(64), unique=True, index=True, nullable=False)
    approver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    approval_type = db.Column(db.String(20), nullable=False)
    purchase_request_id = db.Column(db.Integer, db.ForeignKey('purchase_request.id'))
    asset_borrow_id = db.Column(db.Integer, db.ForeignKey('asset_borrow.id'))
    asset_disposal_id = db.Column(db.Integer, db.ForeignKey('asset_disposal.id'))
    asset_transfer_id = db.Column(db.Integer, db.ForeignKey('asset_transfer.id'))
    status = db.Column(db.String(20), default='pending', nullable=False)
    comment = db.Column(db.Text)
    approval_date = db.Column(db.DateTime)
    level = db.Column(db.Integer, default=1, nullable=False)
    is_final = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"status IN ('pending', 'approved', 'rejected')", 
                       name='ck_approval_status'),
        CheckConstraint(f"approval_type IN ('purchase', 'borrow', 'disposal', 'transfer')", 
                       name='ck_approval_type'),
        CheckConstraint('level >= 1', name='ck_approval_level'),
    )
    
    def __repr__(self):
        return f'<Approval {self.approval_no}>'


class AssetTransfer(db.Model):
    __tablename__ = 'asset_transfer'
    
    VALID_STATUSES = ['pending', 'approved', 'rejected', 'completed']
    
    id = db.Column(db.Integer, primary_key=True)
    transfer_no = db.Column(db.String(64), unique=True, index=True, nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    from_department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False)
    to_department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False)
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    applicant_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    transfer_reason = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending', nullable=False)
    transfer_date = db.Column(db.DateTime)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"status IN ('pending', 'approved', 'rejected', 'completed')", 
                       name='ck_asset_transfer_status'),
    )
    
    approvals = db.relationship('Approval', backref='asset_transfer', lazy='dynamic',
                               cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<AssetTransfer {self.transfer_no}>'


class Notification(db.Model):
    __tablename__ = 'notification'
    
    VALID_TYPES = ['maintenance_reminder', 'borrow_return', 'approval', 'budget_warning', 'system']
    VALID_METHODS = ['system', 'wechat', 'sms', 'email']
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(128), nullable=False)
    content = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(20), default='system', nullable=False)
    related_type = db.Column(db.String(20))
    related_id = db.Column(db.Integer)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    send_method = db.Column(db.String(20), default='system', nullable=False)
    sent_at = db.Column(db.DateTime)
    read_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"notification_type IN ('maintenance_reminder', 'borrow_return', 'approval', 'budget_warning', 'system')", 
                       name='ck_notification_type'),
        CheckConstraint(f"send_method IN ('system', 'wechat', 'sms', 'email')", 
                       name='ck_notification_method'),
    )
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()
    
    def __repr__(self):
        return f'<Notification {self.user_id}: {self.title}>'


class Supplier(db.Model):
    __tablename__ = 'supplier'
    
    VALID_STATUSES = ['active', 'inactive', 'blacklisted']
    
    id = db.Column(db.Integer, primary_key=True)
    supplier_code = db.Column(db.String(64), unique=True, index=True, nullable=False)
    name = db.Column(db.String(128), nullable=False)
    short_name = db.Column(db.String(64))
    contact_person = db.Column(db.String(64))
    contact_phone = db.Column(db.String(32))
    contact_email = db.Column(db.String(120))
    address = db.Column(db.String(256))
    tax_id = db.Column(db.String(64))
    bank_name = db.Column(db.String(128))
    bank_account = db.Column(db.String(64))
    
    qualification_level = db.Column(db.String(20), default='general')
    business_scope = db.Column(db.Text)
    qualification_certificates = db.Column(db.Text)
    cooperation_start_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='active', nullable=False)
    
    rating = db.Column(db.Float, default=5.0)
    total_orders = db.Column(db.Integer, default=0)
    total_amount = db.Column(db.Float, default=0.0)
    
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"status IN ('active', 'inactive', 'blacklisted')", 
                       name='ck_supplier_status'),
        CheckConstraint('rating >= 0 AND rating <= 5', name='ck_supplier_rating'),
        CheckConstraint('total_orders >= 0', name='ck_supplier_total_orders'),
        CheckConstraint('total_amount >= 0', name='ck_supplier_total_amount'),
    )
    
    evaluations = db.relationship('SupplierEvaluation', backref='supplier', lazy='dynamic',
                                   cascade='all, delete-orphan')
    purchase_requests = db.relationship('PurchaseRequest', backref='supplier', lazy='dynamic')
    
    @validates('rating')
    def validate_rating(self, key, value):
        if value < 0 or value > 5:
            raise ValueError('评分必须在0-5之间')
        return value
    
    def __repr__(self):
        return f'<Supplier {self.supplier_code} - {self.name}>'


class SupplierEvaluation(db.Model):
    __tablename__ = 'supplier_evaluation'
    
    VALID_TYPES = ['delivery', 'quality', 'service', 'comprehensive']
    
    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('supplier.id'), nullable=False)
    purchase_request_id = db.Column(db.Integer, db.ForeignKey('purchase_request.id'))
    evaluator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    evaluation_type = db.Column(db.String(20), default='comprehensive', nullable=False)
    quality_rating = db.Column(db.Float, default=5.0)
    delivery_rating = db.Column(db.Float, default=5.0)
    price_rating = db.Column(db.Float, default=5.0)
    service_rating = db.Column(db.Float, default=5.0)
    overall_rating = db.Column(db.Float, default=5.0)
    
    comment = db.Column(db.Text)
    evaluation_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"evaluation_type IN ('delivery', 'quality', 'service', 'comprehensive')", 
                       name='ck_supplier_eval_type'),
        CheckConstraint('quality_rating >= 0 AND quality_rating <= 5', name='ck_eval_quality_rating'),
        CheckConstraint('delivery_rating >= 0 AND delivery_rating <= 5', name='ck_eval_delivery_rating'),
        CheckConstraint('price_rating >= 0 AND price_rating <= 5', name='ck_eval_price_rating'),
        CheckConstraint('service_rating >= 0 AND service_rating <= 5', name='ck_eval_service_rating'),
        CheckConstraint('overall_rating >= 0 AND overall_rating <= 5', name='ck_eval_overall_rating'),
    )
    
    @validates('quality_rating', 'delivery_rating', 'price_rating', 'service_rating', 'overall_rating')
    def validate_rating(self, key, value):
        if value < 0 or value > 5:
            raise ValueError('评分必须在0-5之间')
        return value
    
    def calculate_overall_rating(self):
        ratings = [self.quality_rating, self.delivery_rating, self.price_rating, self.service_rating]
        valid_ratings = [r for r in ratings if r is not None]
        if valid_ratings:
            self.overall_rating = sum(valid_ratings) / len(valid_ratings)
        return self.overall_rating
    
    def __repr__(self):
        return f'<SupplierEvaluation {self.supplier_id} - {self.overall_rating}>'


class InventoryResult(db.Model):
    __tablename__ = 'inventory_result'
    
    VALID_TYPES = ['profit', 'loss', 'adjustment']
    VALID_STATUSES = ['pending', 'approved', 'rejected', 'completed']
    
    id = db.Column(db.Integer, primary_key=True)
    result_no = db.Column(db.String(64), unique=True, index=True, nullable=False)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.id'), nullable=False)
    inventory_item_id = db.Column(db.Integer, db.ForeignKey('inventory_item.id'), nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    
    result_type = db.Column(db.String(20), nullable=False)
    expected_quantity = db.Column(db.Integer, nullable=False)
    actual_quantity = db.Column(db.Integer, nullable=False)
    difference_quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, default=0.0)
    
    reason = db.Column(db.Text)
    suggestion = db.Column(db.Text)
    
    status = db.Column(db.String(20), default='pending', nullable=False)
    approver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    approval_comment = db.Column(db.Text)
    approval_date = db.Column(db.DateTime)
    
    handler_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    handle_date = db.Column(db.DateTime)
    handle_remark = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"result_type IN ('profit', 'loss', 'adjustment')", 
                       name='ck_inventory_result_type'),
        CheckConstraint(f"status IN ('pending', 'approved', 'rejected', 'completed')", 
                       name='ck_inventory_result_status'),
        CheckConstraint('total_amount >= 0', name='ck_inventory_result_amount'),
    )
    
    inventory = db.relationship('Inventory', backref='results')
    inventory_item = db.relationship('InventoryItem', backref='result')
    asset = db.relationship('Asset', backref='inventory_results')
    
    @validates('result_type')
    def validate_result_type(self, key, value):
        valid_types = ['profit', 'loss', 'adjustment']
        if value not in valid_types:
            raise ValueError(f'无效的结果类型: {value}。有效类型: {valid_types}')
        return value
    
    def calculate_amount(self):
        if self.unit_price and self.difference_quantity:
            self.total_amount = abs(self.difference_quantity) * self.unit_price
        return self.total_amount
    
    def __repr__(self):
        return f'<InventoryResult {self.result_no} - {self.result_type}>'


class QRCodeRecord(db.Model):
    __tablename__ = 'qr_code_record'
    
    VALID_TYPES = ['asset_detail', 'borrow', 'return', 'inventory', 'maintenance']
    VALID_STATUSES = ['active', 'used', 'expired']
    
    id = db.Column(db.Integer, primary_key=True)
    qr_code = db.Column(db.String(256), unique=True, index=True, nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    
    qr_type = db.Column(db.String(20), default='asset_detail', nullable=False)
    qr_content = db.Column(db.Text, nullable=False)
    qr_image_path = db.Column(db.String(256))
    
    scan_count = db.Column(db.Integer, default=0)
    last_scan_at = db.Column(db.DateTime)
    
    valid_from = db.Column(db.DateTime)
    valid_until = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='active', nullable=False)
    
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"qr_type IN ('asset_detail', 'borrow', 'return', 'inventory', 'maintenance')", 
                       name='ck_qr_code_type'),
        CheckConstraint(f"status IN ('active', 'used', 'expired')", 
                       name='ck_qr_code_status'),
        CheckConstraint('scan_count >= 0', name='ck_qr_scan_count'),
    )
    
    asset = db.relationship('Asset', backref='qr_codes')
    
    @validates('qr_type')
    def validate_qr_type(self, key, value):
        valid_types = ['asset_detail', 'borrow', 'return', 'inventory', 'maintenance']
        if value not in valid_types:
            raise ValueError(f'无效的二维码类型: {value}。有效类型: {valid_types}')
        return value
    
    def is_valid(self):
        if self.status != 'active':
            return False
        now = datetime.utcnow()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return True
    
    def record_scan(self):
        self.scan_count += 1
        self.last_scan_at = datetime.utcnow()
        return self.scan_count
    
    def __repr__(self):
        return f'<QRCodeRecord {self.id} - {self.asset_id}>'


@event.listens_for(PurchaseRequest, 'before_insert')
@event.listens_for(PurchaseRequest, 'before_update')
def update_purchase_supplier_stats(mapper, connection, target):
    if target.supplier_id and target.status == 'approved':
        supplier = Supplier.query.get(target.supplier_id)
        if supplier:
            supplier.total_orders = (supplier.total_orders or 0) + 1
            supplier.total_amount = (supplier.total_amount or 0) + target.total_amount


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
