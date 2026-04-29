import os
from app import create_app, db
from app.models import (
    User, Department, Asset, Budget, PurchaseRequest, 
    AssetBorrow, Maintenance, Notification
)
from flask_migrate import Migrate

app = create_app(os.getenv('FLASK_CONFIG') or 'default')
migrate = Migrate(app, db)

@app.shell_context_processor
def make_shell_context():
    return dict(
        db=db,
        User=User,
        Department=Department,
        Asset=Asset,
        Budget=Budget,
        PurchaseRequest=PurchaseRequest,
        AssetBorrow=AssetBorrow,
        Maintenance=Maintenance,
        Notification=Notification
    )

@app.cli.command()
def init_db():
    """Initialize the database."""
    db.create_all()
    print('Database initialized.')

@app.cli.command()
def seed():
    """Seed the database with test data."""
    from datetime import datetime, timedelta
    
    # 创建部门
    dept1 = Department(name='技术部', description='负责技术研发和系统维护')
    dept2 = Department(name='行政部', description='负责行政管理和后勤保障')
    dept3 = Department(name='财务部', description='负责财务核算和预算管理')
    
    db.session.add_all([dept1, dept2, dept3])
    db.session.flush()
    
    # 创建用户
    admin = User(
        username='admin',
        email='admin@company.com',
        name='系统管理员',
        role='admin',
        department_id=dept2.id
    )
    admin.password = 'admin123'
    
    manager1 = User(
        username='tech_manager',
        email='tech_manager@company.com',
        name='张经理',
        role='manager',
        department_id=dept1.id
    )
    manager1.password = 'manager123'
    
    user1 = User(
        username='employee1',
        email='employee1@company.com',
        name='李员工',
        role='employee',
        department_id=dept1.id
    )
    user1.password = 'employee123'
    
    user2 = User(
        username='employee2',
        email='employee2@company.com',
        name='王员工',
        role='employee',
        department_id=dept1.id
    )
    user2.password = 'employee123'
    
    db.session.add_all([admin, manager1, user1, user2])
    db.session.flush()
    
    # 更新部门经理
    dept1.manager_id = manager1.id
    dept2.manager_id = admin.id
    dept3.manager_id = admin.id
    
    # 创建预算
    budget1 = Budget(
        department_id=dept1.id,
        year=datetime.now().year,
        total_budget=500000.00,
        used_budget=150000.00,
        remaining_budget=350000.00,
        warning_threshold=80.0,
        status='active'
    )
    
    budget2 = Budget(
        department_id=dept2.id,
        year=datetime.now().year,
        total_budget=200000.00,
        used_budget=50000.00,
        remaining_budget=150000.00,
        warning_threshold=80.0,
        status='active'
    )
    
    db.session.add_all([budget1, budget2])
    
    # 创建资产
    asset1 = Asset(
        asset_code='ASSET-2024-001',
        name='联想笔记本电脑 ThinkPad X1 Carbon',
        category='电子设备',
        model='ThinkPad X1 Carbon Gen 10',
        specification='i7-1260P/16GB/512GB SSD',
        unit='台',
        quantity=1,
        unit_price=12999.00,
        total_value=12999.00,
        purchase_date=datetime.now() - timedelta(days=180),
        warranty_period=36,
        location='技术部办公室-A101',
        department_id=dept1.id,
        status='in_use',
        description='高级开发人员专用笔记本'
    )
    
    asset2 = Asset(
        asset_code='ASSET-2024-002',
        name='惠普台式机 ProDesk 600 G6',
        category='电子设备',
        model='ProDesk 600 G6',
        specification='i5-10500/8GB/256GB SSD',
        unit='台',
        quantity=1,
        unit_price=5999.00,
        total_value=5999.00,
        purchase_date=datetime.now() - timedelta(days=90),
        warranty_period=24,
        location='技术部办公室-A102',
        department_id=dept1.id,
        status='in_stock',
        description='备用台式机'
    )
    
    asset3 = Asset(
        asset_code='ASSET-2024-003',
        name='爱普生投影仪 EB-C765XN',
        category='办公设备',
        model='EB-C765XN',
        specification='5000流明/1024×768分辨率',
        unit='台',
        quantity=1,
        unit_price=8500.00,
        total_value=8500.00,
        purchase_date=datetime.now() - timedelta(days=365),
        warranty_period=12,
        location='会议室B',
        department_id=dept2.id,
        status='in_stock',
        description='会议室专用投影仪'
    )
    
    asset4 = Asset(
        asset_code='ASSET-2024-004',
        name='理光复印机 MP 3055SP',
        category='办公设备',
        model='MP 3055SP',
        specification='A3黑白数码复合机',
        unit='台',
        quantity=1,
        unit_price=15800.00,
        total_value=15800.00,
        purchase_date=datetime.now() - timedelta(days=180),
        warranty_period=24,
        location='打印室',
        department_id=dept2.id,
        status='in_use',
        description='办公区域复印机'
    )
    
    db.session.add_all([asset1, asset2, asset3, asset4])
    db.session.flush()
    
    # 创建借用记录
    borrow1 = AssetBorrow(
        borrow_no=f'BR{datetime.now().strftime("%Y%m%d")}001',
        asset_id=asset1.id,
        borrower_id=user1.id,
        borrow_type='use',
        purpose='日常开发工作使用',
        expected_return_date=datetime.now() + timedelta(days=180),
        actual_return_date=None,
        status='borrowed',
        borrow_date=datetime.now() - timedelta(days=90)
    )
    
    db.session.add(borrow1)
    
    # 创建维护计划
    try:
        from app.models import MaintenancePlan
        plan1 = MaintenancePlan(
            asset_category='电子设备',
            plan_type='category',
            maintenance_type='maintenance',
            interval_days=90,
            next_maintenance_date=datetime.now() + timedelta(days=30),
            duration=2.0,
            description='电子设备季度维护：清洁、系统更新、硬件检测',
            is_active=True
        )
        
        plan2 = MaintenancePlan(
            asset_category='办公设备',
            plan_type='category',
            maintenance_type='inspection',
            interval_days=60,
            next_maintenance_date=datetime.now() + timedelta(days=15),
            duration=1.0,
            description='办公设备双月检查：运行状态、耗材检查',
            is_active=True
        )
        
        db.session.add_all([plan1, plan2])
    except:
        pass
    
    # 创建通知
    notification1 = Notification(
        user_id=manager1.id,
        title='系统通知',
        content='欢迎使用固定资产管理系统。本月底将进行季度资产盘点，请提前做好准备。',
        notification_type='system',
        is_read=False,
        send_method='system',
        sent_at=datetime.now()
    )
    
    notification2 = Notification(
        user_id=user1.id,
        title='借用提醒',
        content='您借用的联想笔记本电脑 ThinkPad X1 Carbon (ASSET-2024-001) 将于 90 天后到期，请及时归还或申请延期。',
        notification_type='borrow_return',
        related_type='borrow',
        related_id=borrow1.id,
        is_read=False,
        send_method='system',
        sent_at=datetime.now()
    )
    
    db.session.add_all([notification1, notification2])
    
    db.session.commit()
    
    print('Test data has been seeded.')
    print('')
    print('Default accounts:')
    print('  - Admin: username=admin, password=admin123')
    print('  - Manager: username=tech_manager, password=manager123')
    print('  - Employee: username=employee1, password=employee123')
    print('  - Employee: username=employee2, password=employee123')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
