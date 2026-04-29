from datetime import datetime
import json
from typing import Tuple, Dict, Any
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import CheckConstraint, event
from sqlalchemy.orm import validates
from app import db, login_manager


MODELS_WITH_UPDATED_AT = [
    'Asset', 'PurchaseRequest', 'AssetBorrow', 'AssetDisposal',
    'Budget', 'Inventory', 'Maintenance', 'MaintenancePlan',
    'Approval', 'AssetTransfer', 'Supplier', 'SupplierEvaluation',
    'InventoryResult', 'QRCodeRecord',
    'AssetListing', 'AssetRequest', 'AssetMatch', 'AssetTransferProposal',
    'MatchingConfig', 'MatchTask'
]

MODELS_WITH_CREATED_AT = [
    'User', 'Department', 'Asset', 'AssetStatusLog', 'PurchaseRequest',
    'PurchaseRequestItem', 'AssetEntry', 'AssetEntryItem', 'AssetBorrow',
    'AssetDisposal', 'Budget', 'BudgetUsageLog', 'Inventory', 'InventoryItem',
    'Maintenance', 'MaintenancePlan', 'Approval', 'AssetTransfer', 'Notification',
    'Supplier', 'SupplierEvaluation', 'InventoryResult', 'QRCodeRecord',
    'AssetListing', 'AssetRequest', 'AssetMatch', 'AssetTransferProposal',
    'MatchingConfig', 'MatchTask'
]


@event.listens_for(db.session, 'before_flush')
def before_flush_handler(session, flush_context, instances):
    current_time = datetime.utcnow()
    
    for instance in session.dirty:
        class_name = instance.__class__.__name__
        
        if class_name in MODELS_WITH_UPDATED_AT:
            if hasattr(instance, 'updated_at'):
                instance.updated_at = current_time


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


class AssetListing(db.Model):
    __tablename__ = 'asset_listing'
    
    LISTING_STATUSES = ['active', 'pending', 'reserved', 'transferred', 'expired', 'cancelled']
    URGENCY_LEVELS = ['low', 'medium', 'high', 'critical']
    CONDITION_LEVELS = ['excellent', 'good', 'fair', 'poor']
    
    id = db.Column(db.Integer, primary_key=True)
    listing_no = db.Column(db.String(64), unique=True, index=True, nullable=False)
    
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False, index=True)
    
    owner_department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False, index=True)
    owner_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), index=True)
    
    title = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text)
    
    category = db.Column(db.String(128), index=True)
    model = db.Column(db.String(128))
    specification = db.Column(db.Text)
    
    condition = db.Column(db.String(32), default='good', nullable=False)
    condition_description = db.Column(db.Text)
    
    original_value = db.Column(db.Float, default=0.0, nullable=False)
    current_value = db.Column(db.Float, default=0.0, nullable=False)
    suggested_transfer_value = db.Column(db.Float, default=0.0, nullable=False)
    
    available_quantity = db.Column(db.Integer, default=1, nullable=False)
    minimum_transfer_quantity = db.Column(db.Integer, default=1, nullable=False)
    
    status = db.Column(db.String(32), default='active', nullable=False, index=True)
    urgency = db.Column(db.String(32), default='low', nullable=False)
    
    listed_at = db.Column(db.DateTime, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, index=True)
    
    reserved_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    reserved_at = db.Column(db.DateTime)
    
    view_count = db.Column(db.Integer, default=0)
    interest_count = db.Column(db.Integer, default=0)
    match_count = db.Column(db.Integer, default=0)
    
    tags_json = db.Column(db.Text)
    images_json = db.Column(db.Text)
    notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint("status IN ('active', 'pending', 'reserved', 'transferred', 'expired', 'cancelled')", 
                       name='ck_asset_listing_status'),
        CheckConstraint("urgency IN ('low', 'medium', 'high', 'critical')", 
                       name='ck_asset_listing_urgency'),
        CheckConstraint("condition IN ('excellent', 'good', 'fair', 'poor')", 
                       name='ck_asset_listing_condition'),
        CheckConstraint('available_quantity >= 0', name='ck_asset_listing_qty'),
        CheckConstraint('minimum_transfer_quantity >= 1', name='ck_asset_listing_min_qty'),
        CheckConstraint('original_value >= 0', name='ck_asset_listing_original_value'),
        CheckConstraint('current_value >= 0', name='ck_asset_listing_current_value'),
        CheckConstraint('suggested_transfer_value >= 0', name='ck_asset_listing_transfer_value'),
        db.Index('idx_listing_category_status', 'category', 'status'),
        db.Index('idx_listing_department_status', 'owner_department_id', 'status'),
        db.Index('idx_listing_listed_at', 'listed_at'),
    )
    
    asset = db.relationship('Asset', backref='listings')
    matches = db.relationship('AssetMatch', backref='listing', lazy='dynamic',
                              foreign_keys='AssetMatch.listing_id')
    proposals = db.relationship('AssetTransferProposal', backref='listing', lazy='dynamic',
                                foreign_keys='AssetTransferProposal.listing_id')
    
    @validates('status')
    def validate_status(self, key, value):
        if value not in self.LISTING_STATUSES:
            raise ValueError(f'无效的状态: {value}')
        return value
    
    @validates('urgency')
    def validate_urgency(self, key, value):
        if value not in self.URGENCY_LEVELS:
            raise ValueError(f'无效的紧急度: {value}')
        return value
    
    @validates('condition')
    def validate_condition(self, key, value):
        if value not in self.CONDITION_LEVELS:
            raise ValueError(f'无效的状态: {value}')
        return value
    
    def get_tags(self):
        if self.tags_json:
            import json
            return json.loads(self.tags_json)
        return []
    
    def set_tags(self, tags):
        import json
        self.tags_json = json.dumps(tags, ensure_ascii=False)
    
    def get_images(self):
        if self.images_json:
            import json
            return json.loads(self.images_json)
        return []
    
    def set_images(self, images):
        import json
        self.images_json = json.dumps(images, ensure_ascii=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'listing_no': self.listing_no,
            'asset_id': self.asset_id,
            'owner_department_id': self.owner_department_id,
            'owner_user_id': self.owner_user_id,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'model': self.model,
            'specification': self.specification,
            'condition': self.condition,
            'condition_description': self.condition_description,
            'original_value': self.original_value,
            'current_value': self.current_value,
            'suggested_transfer_value': self.suggested_transfer_value,
            'available_quantity': self.available_quantity,
            'minimum_transfer_quantity': self.minimum_transfer_quantity,
            'status': self.status,
            'urgency': self.urgency,
            'listed_at': self.listed_at.isoformat() if self.listed_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'reserved_by': self.reserved_by,
            'reserved_at': self.reserved_at.isoformat() if self.reserved_at else None,
            'view_count': self.view_count,
            'interest_count': self.interest_count,
            'match_count': self.match_count,
            'tags': self.get_tags(),
            'images': self.get_images()
        }
    
    def __repr__(self):
        return f'<AssetListing {self.listing_no}>'


class AssetRequest(db.Model):
    __tablename__ = 'asset_request'
    
    REQUEST_STATUSES = ['open', 'matched', 'reserved', 'fulfilled', 'expired', 'cancelled']
    URGENCY_LEVELS = ['low', 'medium', 'high', 'critical']
    CONDITION_LEVELS = ['excellent', 'good', 'fair', 'poor']
    
    id = db.Column(db.Integer, primary_key=True)
    request_no = db.Column(db.String(64), unique=True, index=True, nullable=False)
    
    requester_department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False, index=True)
    requester_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    
    title = db.Column(db.String(256), nullable=False)
    description = db.Column(db.Text)
    
    required_category = db.Column(db.String(128), index=True)
    required_quantity = db.Column(db.Integer, default=1, nullable=False)
    
    max_budget = db.Column(db.Float)
    
    preferred_conditions_json = db.Column(db.Text)
    
    urgency = db.Column(db.String(32), default='medium', nullable=False)
    need_by_date = db.Column(db.DateTime, index=True)
    
    tags_json = db.Column(db.Text)
    alternative_options = db.Column(db.Text)
    
    status = db.Column(db.String(32), default='open', nullable=False, index=True)
    
    created_at = db.Column(db.DateTime, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, index=True)
    
    view_count = db.Column(db.Integer, default=0)
    match_count = db.Column(db.Integer, default=0)
    
    notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint("status IN ('open', 'matched', 'reserved', 'fulfilled', 'expired', 'cancelled')", 
                       name='ck_asset_request_status'),
        CheckConstraint("urgency IN ('low', 'medium', 'high', 'critical')", 
                       name='ck_asset_request_urgency'),
        CheckConstraint('required_quantity >= 1', name='ck_asset_request_qty'),
        CheckConstraint('max_budget >= 0 OR max_budget IS NULL', name='ck_asset_request_budget'),
        db.Index('idx_request_category_status', 'required_category', 'status'),
        db.Index('idx_request_department_status', 'requester_department_id', 'status'),
        db.Index('idx_request_created_at', 'created_at'),
    )
    
    matches = db.relationship('AssetMatch', backref='request', lazy='dynamic',
                              foreign_keys='AssetMatch.request_id')
    proposals = db.relationship('AssetTransferProposal', backref='request', lazy='dynamic',
                                foreign_keys='AssetTransferProposal.request_id')
    
    @validates('status')
    def validate_status(self, key, value):
        if value not in self.REQUEST_STATUSES:
            raise ValueError(f'无效的状态: {value}')
        return value
    
    @validates('urgency')
    def validate_urgency(self, key, value):
        if value not in self.URGENCY_LEVELS:
            raise ValueError(f'无效的紧急度: {value}')
        return value
    
    def get_preferred_conditions(self):
        if self.preferred_conditions_json:
            import json
            return json.loads(self.preferred_conditions_json)
        return ['excellent', 'good']
    
    def set_preferred_conditions(self, conditions):
        import json
        self.preferred_conditions_json = json.dumps(conditions, ensure_ascii=False)
    
    def get_tags(self):
        if self.tags_json:
            import json
            return json.loads(self.tags_json)
        return []
    
    def set_tags(self, tags):
        import json
        self.tags_json = json.dumps(tags, ensure_ascii=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'request_no': self.request_no,
            'requester_department_id': self.requester_department_id,
            'requester_user_id': self.requester_user_id,
            'title': self.title,
            'description': self.description,
            'required_category': self.required_category,
            'required_quantity': self.required_quantity,
            'max_budget': self.max_budget,
            'preferred_conditions': self.get_preferred_conditions(),
            'urgency': self.urgency,
            'need_by_date': self.need_by_date.isoformat() if self.need_by_date else None,
            'tags': self.get_tags(),
            'alternative_options': self.alternative_options,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'view_count': self.view_count,
            'match_count': self.match_count
        }
    
    def __repr__(self):
        return f'<AssetRequest {self.request_no}>'


class AssetMatch(db.Model):
    __tablename__ = 'asset_match'
    
    MATCH_STATUSES = ['pending', 'proposed', 'accepted', 'rejected', 'completed']
    
    id = db.Column(db.Integer, primary_key=True)
    match_no = db.Column(db.String(64), unique=True, index=True, nullable=False)
    
    listing_id = db.Column(db.Integer, db.ForeignKey('asset_listing.id'), nullable=False, index=True)
    request_id = db.Column(db.Integer, db.ForeignKey('asset_request.id'), nullable=False, index=True)
    
    overall_score = db.Column(db.Float, default=0.0, nullable=False)
    category_match_score = db.Column(db.Float, default=0.0)
    condition_match_score = db.Column(db.Float, default=0.0)
    value_match_score = db.Column(db.Float, default=0.0)
    quantity_match_score = db.Column(db.Float, default=0.0)
    urgency_match_score = db.Column(db.Float, default=0.0)
    tag_match_score = db.Column(db.Float, default=0.0)
    
    matched_quantity = db.Column(db.Integer, default=0, nullable=False)
    matched_value = db.Column(db.Float, default=0.0, nullable=False)
    
    status = db.Column(db.String(32), default='pending', nullable=False, index=True)
    
    proposed_at = db.Column(db.DateTime)
    accepted_at = db.Column(db.DateTime)
    rejected_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    rejection_reason = db.Column(db.Text)
    
    notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'proposed', 'accepted', 'rejected', 'completed')", 
                       name='ck_asset_match_status'),
        CheckConstraint('overall_score >= 0 AND overall_score <= 1', name='ck_match_overall_score'),
        CheckConstraint('category_match_score >= 0 AND category_match_score <= 1', name='ck_match_category_score'),
        CheckConstraint('condition_match_score >= 0 AND condition_match_score <= 1', name='ck_match_condition_score'),
        CheckConstraint('value_match_score >= 0 AND value_match_score <= 1', name='ck_match_value_score'),
        CheckConstraint('quantity_match_score >= 0 AND quantity_match_score <= 1', name='ck_match_quantity_score'),
        CheckConstraint('urgency_match_score >= 0 AND urgency_match_score <= 1', name='ck_match_urgency_score'),
        CheckConstraint('tag_match_score >= 0 AND tag_match_score <= 1', name='ck_match_tag_score'),
        CheckConstraint('matched_quantity >= 0', name='ck_match_qty'),
        CheckConstraint('matched_value >= 0', name='ck_match_value'),
        db.UniqueConstraint('listing_id', 'request_id', name='uq_match_listing_request'),
        db.Index('idx_match_status', 'status'),
        db.Index('idx_match_created_at', 'created_at'),
    )
    
    proposals = db.relationship('AssetTransferProposal', backref='match', lazy='dynamic',
                                foreign_keys='AssetTransferProposal.match_id')
    
    @validates('status')
    def validate_status(self, key, value):
        if value not in self.MATCH_STATUSES:
            raise ValueError(f'无效的状态: {value}')
        return value
    
    def to_dict(self):
        return {
            'id': self.id,
            'match_no': self.match_no,
            'listing_id': self.listing_id,
            'request_id': self.request_id,
            'overall_score': self.overall_score,
            'scores': {
                'category': self.category_match_score,
                'condition': self.condition_match_score,
                'value': self.value_match_score,
                'quantity': self.quantity_match_score,
                'urgency': self.urgency_match_score,
                'tags': self.tag_match_score
            },
            'matched_quantity': self.matched_quantity,
            'matched_value': self.matched_value,
            'status': self.status,
            'proposed_at': self.proposed_at.isoformat() if self.proposed_at else None,
            'accepted_at': self.accepted_at.isoformat() if self.accepted_at else None,
            'rejected_at': self.rejected_at.isoformat() if self.rejected_at else None,
            'rejection_reason': self.rejection_reason,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<AssetMatch {self.match_no}>'


class AssetTransferProposal(db.Model):
    __tablename__ = 'asset_transfer_proposal'
    
    PROPOSAL_STATUSES = ['pending', 'approved', 'rejected', 'completed', 'cancelled']
    
    id = db.Column(db.Integer, primary_key=True)
    proposal_no = db.Column(db.String(64), unique=True, index=True, nullable=False)
    
    match_id = db.Column(db.Integer, db.ForeignKey('asset_match.id'), nullable=False, index=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('asset_listing.id'), nullable=False, index=True)
    request_id = db.Column(db.Integer, db.ForeignKey('asset_request.id'), nullable=False, index=True)
    
    from_department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False, index=True)
    to_department_id = db.Column(db.Integer, db.ForeignKey('department.id'), nullable=False, index=True)
    
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    
    transfer_value = db.Column(db.Float, default=0.0, nullable=False)
    transfer_date = db.Column(db.DateTime)
    
    status = db.Column(db.String(32), default='pending', nullable=False, index=True)
    
    approved_at = db.Column(db.DateTime)
    approved_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    approval_comments = db.Column(db.Text)
    
    rejected_at = db.Column(db.DateTime)
    rejected_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    rejection_reason = db.Column(db.Text)
    
    completed_at = db.Column(db.DateTime)
    
    notes = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'approved', 'rejected', 'completed', 'cancelled')", 
                       name='ck_transfer_proposal_status'),
        CheckConstraint('quantity >= 1', name='ck_transfer_proposal_qty'),
        CheckConstraint('transfer_value >= 0', name='ck_transfer_proposal_value'),
        db.Index('idx_proposal_status', 'status'),
        db.Index('idx_proposal_created_at', 'created_at'),
    )
    
    asset = db.relationship('Asset', backref='transfer_proposals')
    
    @validates('status')
    def validate_status(self, key, value):
        if value not in self.PROPOSAL_STATUSES:
            raise ValueError(f'无效的状态: {value}')
        return value
    
    def to_dict(self):
        return {
            'id': self.id,
            'proposal_no': self.proposal_no,
            'match_id': self.match_id,
            'listing_id': self.listing_id,
            'request_id': self.request_id,
            'from_department_id': self.from_department_id,
            'to_department_id': self.to_department_id,
            'from_user_id': self.from_user_id,
            'to_user_id': self.to_user_id,
            'asset_id': self.asset_id,
            'quantity': self.quantity,
            'transfer_value': self.transfer_value,
            'transfer_date': self.transfer_date.isoformat() if self.transfer_date else None,
            'status': self.status,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'approved_by': self.approved_by,
            'approval_comments': self.approval_comments,
            'rejected_at': self.rejected_at.isoformat() if self.rejected_at else None,
            'rejection_reason': self.rejection_reason,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<AssetTransferProposal {self.proposal_no}>'


class MatchingConfig(db.Model):
    __tablename__ = 'matching_config'
    
    CONFIG_TYPES = ['global', 'department', 'category']
    
    id = db.Column(db.Integer, primary_key=True)
    config_name = db.Column(db.String(128), nullable=False)
    config_type = db.Column(db.String(32), default='global', nullable=False)
    
    target_department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    target_category = db.Column(db.String(128))
    
    category_weight = db.Column(db.Float, default=0.25, nullable=False)
    condition_weight = db.Column(db.Float, default=0.20, nullable=False)
    value_weight = db.Column(db.Float, default=0.20, nullable=False)
    quantity_weight = db.Column(db.Float, default=0.15, nullable=False)
    urgency_weight = db.Column(db.Float, default=0.10, nullable=False)
    tag_weight = db.Column(db.Float, default=0.10, nullable=False)
    
    min_match_score = db.Column(db.Float, default=0.5, nullable=False)
    max_matches_per_listing = db.Column(db.Integer, default=5)
    max_matches_per_request = db.Column(db.Integer, default=5)
    
    auto_approve_threshold = db.Column(db.Float, default=0.9)
    
    condition_values_json = db.Column(db.Text)
    urgency_values_json = db.Column(db.Text)
    
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    priority = db.Column(db.Integer, default=0)
    
    description = db.Column(db.Text)
    
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint("config_type IN ('global', 'department', 'category')", 
                       name='ck_matching_config_type'),
        CheckConstraint('category_weight >= 0 AND category_weight <= 1', name='ck_config_category_weight'),
        CheckConstraint('condition_weight >= 0 AND condition_weight <= 1', name='ck_config_condition_weight'),
        CheckConstraint('value_weight >= 0 AND value_weight <= 1', name='ck_config_value_weight'),
        CheckConstraint('quantity_weight >= 0 AND quantity_weight <= 1', name='ck_config_quantity_weight'),
        CheckConstraint('urgency_weight >= 0 AND urgency_weight <= 1', name='ck_config_urgency_weight'),
        CheckConstraint('tag_weight >= 0 AND tag_weight <= 1', name='ck_config_tag_weight'),
        CheckConstraint('min_match_score >= 0 AND min_match_score <= 1', name='ck_config_min_score'),
        CheckConstraint('max_matches_per_listing >= 1', name='ck_config_max_listing_matches'),
        CheckConstraint('max_matches_per_request >= 1', name='ck_config_max_request_matches'),
        CheckConstraint('auto_approve_threshold >= 0 AND auto_approve_threshold <= 1', name='ck_config_auto_approve'),
        db.Index('idx_matching_config_type_active', 'config_type', 'is_active'),
    )
    
    @validates('config_type')
    def validate_config_type(self, key, value):
        if value not in self.CONFIG_TYPES:
            raise ValueError(f'无效的配置类型: {value}')
        return value
    
    def get_weights(self) -> dict:
        return {
            'category': self.category_weight,
            'condition': self.condition_weight,
            'value': self.value_weight,
            'quantity': self.quantity_weight,
            'urgency': self.urgency_weight,
            'tag': self.tag_weight
        }
    
    def get_condition_values(self) -> Dict[str, float]:
        if self.condition_values_json:
            try:
                return json.loads(self.condition_values_json)
            except:
                pass
        return {
            'excellent': 1.0,
            'good': 0.8,
            'fair': 0.5,
            'poor': 0.2
        }
    
    def set_condition_values(self, values: Dict[str, float]):
        self.condition_values_json = json.dumps(values, ensure_ascii=False)
    
    def get_urgency_values(self) -> Dict[str, float]:
        if self.urgency_values_json:
            try:
                return json.loads(self.urgency_values_json)
            except:
                pass
        return {
            'low': 0.25,
            'medium': 0.5,
            'high': 0.75,
            'critical': 1.0
        }
    
    def set_urgency_values(self, values: Dict[str, float]):
        self.urgency_values_json = json.dumps(values, ensure_ascii=False)
    
    def get_full_config(self) -> Dict[str, Any]:
        return {
            'weights': self.get_weights(),
            'condition_values': self.get_condition_values(),
            'urgency_values': self.get_urgency_values(),
            'min_match_score': self.min_match_score,
            'max_matches_per_listing': self.max_matches_per_listing,
            'max_matches_per_request': self.max_matches_per_request,
            'auto_approve_threshold': self.auto_approve_threshold
        }
    
    def validate_weights(self) -> Tuple[bool, str]:
        total = (
            self.category_weight +
            self.condition_weight +
            self.value_weight +
            self.quantity_weight +
            self.urgency_weight +
            self.tag_weight
        )
        
        if abs(total - 1.0) > 0.001:
            return False, f'权重总和必须为1.0，当前为 {total}'
        
        return True, '权重配置有效'
    
    def to_dict(self):
        return {
            'id': self.id,
            'config_name': self.config_name,
            'config_type': self.config_type,
            'target_department_id': self.target_department_id,
            'target_category': self.target_category,
            'weights': self.get_weights(),
            'min_match_score': self.min_match_score,
            'max_matches_per_listing': self.max_matches_per_listing,
            'max_matches_per_request': self.max_matches_per_request,
            'auto_approve_threshold': self.auto_approve_threshold,
            'is_active': self.is_active,
            'priority': self.priority,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<MatchingConfig {self.config_name}>'


class MatchTask(db.Model):
    __tablename__ = 'match_task'
    
    TASK_TYPES = ['listing_match', 'request_match', 'batch_match']
    TASK_STATUSES = ['pending', 'processing', 'completed', 'failed', 'cancelled']
    
    id = db.Column(db.Integer, primary_key=True)
    task_no = db.Column(db.String(64), unique=True, index=True, nullable=False)
    
    task_type = db.Column(db.String(32), nullable=False)
    
    listing_id = db.Column(db.Integer, db.ForeignKey('asset_listing.id'))
    request_id = db.Column(db.Integer, db.ForeignKey('asset_request.id'))
    
    target_department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    target_category = db.Column(db.String(128))
    
    config_id = db.Column(db.Integer, db.ForeignKey('matching_config.id'))
    
    status = db.Column(db.String(32), default='pending', nullable=False, index=True)
    
    scheduled_at = db.Column(db.DateTime, index=True)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    failed_at = db.Column(db.DateTime)
    
    matches_found = db.Column(db.Integer, default=0)
    matches_created = db.Column(db.Integer, default=0)
    
    error_message = db.Column(db.Text)
    
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    created_at = db.Column(db.DateTime, nullable=False, index=True)
    updated_at = db.Column(db.DateTime, nullable=False)
    
    __table_args__ = (
        CheckConstraint("task_type IN ('listing_match', 'request_match', 'batch_match')", 
                       name='ck_match_task_type'),
        CheckConstraint("status IN ('pending', 'processing', 'completed', 'failed', 'cancelled')", 
                       name='ck_match_task_status'),
        CheckConstraint('matches_found >= 0', name='ck_match_task_found'),
        CheckConstraint('matches_created >= 0', name='ck_match_task_created'),
        db.Index('idx_match_task_status_created', 'status', 'created_at'),
        db.Index('idx_match_task_scheduled', 'scheduled_at'),
    )
    
    config = db.relationship('MatchingConfig', backref='tasks')
    
    @validates('task_type')
    def validate_task_type(self, key, value):
        if value not in self.TASK_TYPES:
            raise ValueError(f'无效的任务类型: {value}')
        return value
    
    @validates('status')
    def validate_status(self, key, value):
        if value not in self.TASK_STATUSES:
            raise ValueError(f'无效的状态: {value}')
        return value
    
    def to_dict(self):
        return {
            'id': self.id,
            'task_no': self.task_no,
            'task_type': self.task_type,
            'listing_id': self.listing_id,
            'request_id': self.request_id,
            'target_department_id': self.target_department_id,
            'target_category': self.target_category,
            'config_id': self.config_id,
            'status': self.status,
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'matches_found': self.matches_found,
            'matches_created': self.matches_created,
            'error_message': self.error_message,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def __repr__(self):
        return f'<MatchTask {self.task_no}>'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
