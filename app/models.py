from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login_manager

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    password_hash = db.Column(db.String(128))
    email = db.Column(db.String(120), unique=True, index=True)
    name = db.Column(db.String(64))
    role = db.Column(db.String(20), default='employee')  # employee, manager, admin
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
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
        self.password_hash = generate_password_hash(password)
    
    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, index=True)
    description = db.Column(db.String(200))
    manager_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    users = db.relationship('User', backref='department', lazy='dynamic', foreign_keys='User.department_id')
    assets = db.relationship('Asset', backref='department', lazy='dynamic')
    budgets = db.relationship('Budget', backref='department', lazy='dynamic')
    purchase_requests = db.relationship('PurchaseRequest', backref='department', lazy='dynamic')
    
    def __repr__(self):
        return f'<Department {self.name}>'

class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_code = db.Column(db.String(64), unique=True, index=True)
    name = db.Column(db.String(128))
    category = db.Column(db.String(64))
    model = db.Column(db.String(64))
    specification = db.Column(db.String(128))
    unit = db.Column(db.String(20))
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float, default=0.0)
    total_value = db.Column(db.Float, default=0.0)
    purchase_date = db.Column(db.DateTime)
    warranty_period = db.Column(db.Integer)
    location = db.Column(db.String(128))
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    status = db.Column(db.String(20), default='in_stock')
    description = db.Column(db.Text)
    qr_code = db.Column(db.String(256))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    borrows = db.relationship('AssetBorrow', backref='asset', lazy='dynamic')
    inventories = db.relationship('InventoryItem', backref='asset', lazy='dynamic')
    maintenances = db.relationship('Maintenance', backref='asset', lazy='dynamic')
    status_logs = db.relationship('AssetStatusLog', backref='asset', lazy='dynamic')
    
    def __repr__(self):
        return f'<Asset {self.asset_code} - {self.name}>'

class AssetStatusLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    status = db.Column(db.String(20))
    previous_status = db.Column(db.String(20))
    description = db.Column(db.Text)
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<AssetStatusLog {self.asset_id}: {self.previous_status} -> {self.status}>'

class PurchaseRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_no = db.Column(db.String(64), unique=True, index=True)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    requester_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    title = db.Column(db.String(128))
    description = db.Column(db.Text)
    total_amount = db.Column(db.Float, default=0.0)
    budget_year = db.Column(db.Integer)
    status = db.Column(db.String(20), default='pending')
    is_over_budget = db.Column(db.Boolean, default=False)
    special_approval_required = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    items = db.relationship('PurchaseRequestItem', backref='request', lazy='dynamic')
    approvals = db.relationship('Approval', backref='purchase_request', lazy='dynamic')
    
    def __repr__(self):
        return f'<PurchaseRequest {self.request_no}>'

class PurchaseRequestItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    purchase_request_id = db.Column(db.Integer, db.ForeignKey('purchase_request.id'))
    name = db.Column(db.String(128))
    category = db.Column(db.String(64))
    model = db.Column(db.String(64))
    specification = db.Column(db.String(128))
    unit = db.Column(db.String(20))
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float, default=0.0)
    total_price = db.Column(db.Float, default=0.0)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<PurchaseRequestItem {self.name}>'

class AssetEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    entry_no = db.Column(db.String(64), unique=True, index=True)
    purchase_request_id = db.Column(db.Integer, db.ForeignKey('purchase_request.id'))
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    entry_date = db.Column(db.DateTime, default=datetime.utcnow)
    total_items = db.Column(db.Integer, default=0)
    total_value = db.Column(db.Float, default=0.0)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    items = db.relationship('AssetEntryItem', backref='entry', lazy='dynamic')
    
    def __repr__(self):
        return f'<AssetEntry {self.entry_no}>'

class AssetEntryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_entry_id = db.Column(db.Integer, db.ForeignKey('asset_entry.id'))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float, default=0.0)
    total_price = db.Column(db.Float, default=0.0)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<AssetEntryItem {self.asset_id}>'

class AssetBorrow(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    borrow_no = db.Column(db.String(64), unique=True, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    borrower_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    borrow_type = db.Column(db.String(20), default='borrow')
    purpose = db.Column(db.String(256))
    expected_return_date = db.Column(db.DateTime)
    actual_return_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='pending')
    borrow_date = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    approvals = db.relationship('Approval', backref='asset_borrow', lazy='dynamic')
    
    def __repr__(self):
        return f'<AssetBorrow {self.borrow_no}>'

class AssetDisposal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    disposal_no = db.Column(db.String(64), unique=True, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    applicant_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    disposal_type = db.Column(db.String(20))
    reason = db.Column(db.Text)
    estimated_value = db.Column(db.Float, default=0.0)
    actual_value = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='pending')
    disposal_date = db.Column(db.DateTime)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    approvals = db.relationship('Approval', backref='asset_disposal', lazy='dynamic')
    
    def __repr__(self):
        return f'<AssetDisposal {self.disposal_no}>'

class Budget(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    year = db.Column(db.Integer)
    total_budget = db.Column(db.Float, default=0.0)
    used_budget = db.Column(db.Float, default=0.0)
    remaining_budget = db.Column(db.Float, default=0.0)
    warning_threshold = db.Column(db.Float, default=80.0)
    status = db.Column(db.String(20), default='active')
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Budget {self.department_id} - {self.year}>'

class BudgetUsageLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    budget_id = db.Column(db.Integer, db.ForeignKey('budget.id'))
    amount = db.Column(db.Float, default=0.0)
    usage_type = db.Column(db.String(20))
    related_request_id = db.Column(db.Integer, db.ForeignKey('purchase_request.id'))
    description = db.Column(db.Text)
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<BudgetUsageLog {self.budget_id} - {self.amount}>'

class Inventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inventory_no = db.Column(db.String(64), unique=True, index=True)
    name = db.Column(db.String(128))
    inventory_type = db.Column(db.String(20), default='annual')
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    status = db.Column(db.String(20), default='pending')
    total_assets = db.Column(db.Integer, default=0)
    inventoried_assets = db.Column(db.Integer, default=0)
    profit_assets = db.Column(db.Integer, default=0)
    loss_assets = db.Column(db.Integer, default=0)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    items = db.relationship('InventoryItem', backref='inventory', lazy='dynamic')
    
    def __repr__(self):
        return f'<Inventory {self.inventory_no}>'

class InventoryItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.id'))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    expected_quantity = db.Column(db.Integer, default=1)
    actual_quantity = db.Column(db.Integer, default=0)
    expected_location = db.Column(db.String(128))
    actual_location = db.Column(db.String(128))
    expected_status = db.Column(db.String(20))
    actual_status = db.Column(db.String(20))
    inventory_result = db.Column(db.String(20))
    inventory_date = db.Column(db.DateTime)
    inventory_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<InventoryItem {self.asset_id} - {self.inventory_result}>'

class Maintenance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    maintenance_no = db.Column(db.String(64), unique=True, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    operator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    maintenance_type = db.Column(db.String(20))
    description = db.Column(db.Text)
    schedule_date = db.Column(db.DateTime)
    actual_date = db.Column(db.DateTime)
    duration = db.Column(db.Float, default=0.0)
    cost = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='scheduled')
    next_maintenance_date = db.Column(db.DateTime)
    remark = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Maintenance {self.maintenance_no}>'

class MaintenancePlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    asset_category = db.Column(db.String(64))
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    plan_type = db.Column(db.String(20))
    maintenance_type = db.Column(db.String(20))
    interval_days = db.Column(db.Integer)
    next_maintenance_date = db.Column(db.DateTime)
    duration = db.Column(db.Float, default=0.0)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<MaintenancePlan {self.asset_category or self.asset_id}>'

class Approval(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    approval_no = db.Column(db.String(64), unique=True, index=True)
    approver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    approval_type = db.Column(db.String(20))
    purchase_request_id = db.Column(db.Integer, db.ForeignKey('purchase_request.id'))
    asset_borrow_id = db.Column(db.Integer, db.ForeignKey('asset_borrow.id'))
    asset_disposal_id = db.Column(db.Integer, db.ForeignKey('asset_disposal.id'))
    asset_transfer_id = db.Column(db.Integer, db.ForeignKey('asset_transfer.id'))
    status = db.Column(db.String(20), default='pending')
    comment = db.Column(db.Text)
    approval_date = db.Column(db.DateTime)
    level = db.Column(db.Integer, default=1)
    is_final = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Approval {self.approval_no}>'

class AssetTransfer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    transfer_no = db.Column(db.String(64), unique=True, index=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'))
    from_department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    to_department_id = db.Column(db.Integer, db.ForeignKey('department.id'))
    from_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    to_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    applicant_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    transfer_reason = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')
    transfer_date = db.Column(db.DateTime)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    approvals = db.relationship('Approval', backref='asset_transfer', lazy='dynamic')
    
    def __repr__(self):
        return f'<AssetTransfer {self.transfer_no}>'

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    title = db.Column(db.String(128))
    content = db.Column(db.Text)
    notification_type = db.Column(db.String(20))
    related_type = db.Column(db.String(20))
    related_id = db.Column(db.Integer)
    is_read = db.Column(db.Boolean, default=False)
    send_method = db.Column(db.String(20), default='system')
    sent_at = db.Column(db.DateTime)
    read_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Notification {self.user_id}: {self.title}>'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
