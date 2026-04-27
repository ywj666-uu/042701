import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_apscheduler import APScheduler
from config import config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
scheduler = APScheduler()

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)
    
    db.init_app(app)
    login_manager.init_app(app)
    
    # 初始化调度器
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        scheduler.init_app(app)
        scheduler.start()
    
    # 注册蓝图
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)
    
    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')
    
    from .assets import assets as assets_blueprint
    app.register_blueprint(assets_blueprint, url_prefix='/assets')
    
    from .budget import budget as budget_blueprint
    app.register_blueprint(budget_blueprint, url_prefix='/budget')
    
    from .inventory import inventory as inventory_blueprint
    app.register_blueprint(inventory_blueprint, url_prefix='/inventory')
    
    from .maintenance import maintenance as maintenance_blueprint
    app.register_blueprint(maintenance_blueprint, url_prefix='/maintenance')
    
    from .notification import notification as notification_blueprint
    app.register_blueprint(notification_blueprint, url_prefix='/notification')
    
    return app
