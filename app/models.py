from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import CheckConstraint, event, DDL
from sqlalchemy.orm import validates
from app import db, login_manager


MODELS_WITH_UPDATED_AT = [
    'Asset', 'PurchaseRequest', 'AssetBorrow', 'AssetDisposal',
    'Budget', 'Inventory', 'Maintenance', 'MaintenancePlan',
    'Approval', 'AssetTransfer'
]


@event.listens_for(db.session, 'before_flush')
def update_timestamps(session, flush_context, instances):
    for instance in session.dirty:
        class_name = instance.__class__.__name__
        if class_name in MODELS_WITH_UPDATED_AT:
            if hasattr(instance, 'updated_at'):
                instance.updated_at = datetime.utcnow()


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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"status IN ({','.join([':' + s for s in VALID_STATUSES])})", 
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f'<AssetStatusLog {self.asset_id}: {self.previous_status} -> {self.status}>'


class PurchaseRequest(db.Model):
    __tablename__ = 'purchase_request'
    
    VALID_STATUSES = ['pending', 'approved', 'rejected', 'completed']
    
    id = db.Column(db.Integer, primary_key=True)
    request_no = db.Column(db.String(64), unique=True, index=True, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    total_amount = db.Column(db.Float, default=0.0, nullable=False)
    budget_year = db.Column(db.Integer)
    status = db.Column(db.String(20), default='pending', nullable=False)
    is_over_budget = db.Column(db.Boolean, default=False, nullable=False)
    special_approval_required = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"status IN ({','.join([':' + s for s in VALID_STATUSES])})", 
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
    
    def __repr__(self):
        return f'<PurchaseRequest {self.request_no}>'


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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
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


@event.listens_for(PurchaseRequestItem, 'before_insert')
@event.listens_for(PurchaseRequestItem, 'before_update')
def calculate_item_total_price(mapper, connection, target):
    if target.quantity is not None and target.unit_price is not None:
        target.total_price = target.quantity * target.unit_price


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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"status IN ({','.join([':' + s for s in VALID_STATUSES])})", 
                       name='ck_asset_borrow_status'),
        CheckConstraint(f"borrow_type IN ({','.join([':' + s for s in VALID_TYPES])})", 
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"status IN ({','.join([':' + s for s in VALID_STATUSES])})", 
                       name='ck_asset_disposal_status'),
        CheckConstraint(f"disposal_type IN ({','.join([':' + s for s in VALID_TYPES])})", 
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"status IN ({','.join([':' + s for s in VALID_STATUSES])})", 
                       name='ck_budget_status'),
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"usage_type IN ({','.join([':' + s for s in VALID_TYPES])})", 
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"status IN ({','.join([':' + s for s in VALID_STATUSES])})", 
                       name='ck_inventory_status'),
        CheckConstraint(f"inventory_type IN ({','.join([':' + s for s in VALID_TYPES])})", 
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"inventory_result IN ({','.join([':' + s for s in VALID_RESULTS])})", 
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"status IN ({','.join([':' + s for s in VALID_STATUSES])})", 
                       name='ck_maintenance_status'),
        CheckConstraint(f"maintenance_type IN ({','.join([':' + s for s in VALID_TYPES])})", 
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"plan_type IN ({','.join([':' + s for s in VALID_PLAN_TYPES])})", 
                       name='ck_maintenance_plan_type'),
        CheckConstraint(f"maintenance_type IN ({','.join([':' + s for s in VALID_MAINTENANCE_TYPES])})", 
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"status IN ({','.join([':' + s for s in VALID_STATUSES])})", 
                       name='ck_approval_status'),
        CheckConstraint(f"approval_type IN ({','.join([':' + s for s in VALID_TYPES])})", 
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
    from_department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    to_department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    applicant_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    transfer_reason = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending', nullable=False)
    transfer_date = db.Column(db.DateTime)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"status IN ({','.join([':' + s for s in VALID_STATUSES])})", 
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        CheckConstraint(f"notification_type IN ({','.join([':' + s for s in VALID_TYPES])})", 
                       name='ck_notification_type'),
        CheckConstraint(f"send_method IN ({','.join([':' + s for s in VALID_METHODS])})", 
                       name='ck_notification_method'),
    )
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = datetime.utcnow()
    
    def __repr__(self):
        return f'<Notification {self.user_id}: {self.title}>'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
