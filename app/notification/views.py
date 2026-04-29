from datetime import datetime, timedelta
from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.notification import notification
from app import db
from app.models import (
    Notification, User, AssetBorrow, Maintenance, MaintenancePlan,
    Approval, Asset, Budget
)

@notification.route('/')
@login_required
def list():
    page = request.args.get('page', 1, type=int)
    is_read = request.args.get('is_read', type=bool)
    notification_type = request.args.get('notification_type', '')
    
    query = Notification.query.filter_by(user_id=current_user.id)
    
    if is_read is not None:
        query = query.filter_by(is_read=is_read)
    
    if notification_type:
        query = query.filter_by(notification_type=notification_type)
    
    pagination = query.order_by(Notification.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    notifications = pagination.items
    
    # 统计未读数量
    unread_count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    
    return render_template('notification/list.html', 
        title='通知中心',
        notifications=notifications,
        pagination=pagination,
        unread_count=unread_count,
        is_read=is_read,
        notification_type=notification_type
    )

@notification.route('/<int:notification_id>')
@login_required
def detail(notification_id):
    notification_obj = Notification.query.get_or_404(notification_id)
    
    # 验证权限
    if notification_obj.user_id != current_user.id and current_user.role != 'admin':
        flash('您没有权限查看此通知', 'danger')
        return redirect(url_for('notification.list'))
    
    # 标记为已读
    if not notification_obj.is_read:
        notification_obj.is_read = True
        notification_obj.read_at = datetime.utcnow()
        db.session.commit()
    
    return render_template('notification/detail.html', 
        title='通知详情',
        notification=notification_obj
    )

@notification.route('/mark-read/<int:notification_id>', methods=['POST'])
@login_required
def mark_read(notification_id):
    notification_obj = Notification.query.get_or_404(notification_id)
    
    if notification_obj.user_id != current_user.id and current_user.role != 'admin':
        return jsonify({'success': False, 'message': '权限不足'}), 403
    
    notification_obj.is_read = True
    notification_obj.read_at = datetime.utcnow()
    db.session.commit()
    
    return jsonify({'success': True})

@notification.route('/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    notifications = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).all()
    
    for n in notifications:
        n.is_read = True
        n.read_at = datetime.utcnow()
    
    db.session.commit()
    
    flash('所有通知已标记为已读', 'success')
    return redirect(url_for('notification.list'))

@notification.route('/api/unread-count')
@login_required
def api_unread_count():
    count = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    
    return jsonify({
        'count': count,
        'success': True
    })

@notification.route('/api/latest')
@login_required
def api_latest():
    limit = request.args.get('limit', 5, type=int)
    
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).limit(limit).all()
    
    return jsonify([{
        'id': n.id,
        'title': n.title,
        'content': n.content,
        'notification_type': n.notification_type,
        'is_read': n.is_read,
        'created_at': n.created_at.isoformat() if n.created_at else None
    } for n in notifications])

# 通知服务类
class NotificationService:
    @staticmethod
    def create_notification(user_id, title, content, notification_type, 
                           related_type=None, related_id=None, send_method='system'):
        notification_obj = Notification(
            user_id=user_id,
            title=title,
            content=content,
            notification_type=notification_type,
            related_type=related_type,
            related_id=related_id,
            send_method=send_method,
            sent_at=datetime.utcnow()
        )
        db.session.add(notification_obj)
        db.session.commit()
        
        # 如果需要通过企业微信或短信发送
        if send_method in ['wechat', 'sms', 'email']:
            NotificationService._send_external_notification(notification_obj)
        
        return notification_obj
    
    @staticmethod
    def _send_external_notification(notification_obj):
        user = User.query.get(notification_obj.user_id)
        if not user:
            return
        
        # 这里可以实现具体的外部通知发送逻辑
        # 例如企业微信机器人、短信服务、邮件等
        
        # 企业微信示例
        if notification_obj.send_method == 'wechat':
            NotificationService._send_wechat_notification(user, notification_obj)
        
        # 短信示例
        if notification_obj.send_method == 'sms':
            NotificationService._send_sms_notification(user, notification_obj)
        
        # 邮件示例
        if notification_obj.send_method == 'email':
            NotificationService._send_email_notification(user, notification_obj)
    
    @staticmethod
    def _send_wechat_notification(user, notification_obj):
        # 实现企业微信通知发送
        # 这里可以使用企业微信机器人或企业微信应用消息
        import requests
        from flask import current_app
        
        webhook = current_app.config.get('WECHAT_WEBHOOK')
        if not webhook:
            return
        
        message = {
            'msgtype': 'markdown',
            'markdown': {
                'content': f'**{notification_obj.title}**\n\n'
                          f'{notification_obj.content}\n\n'
                          f'发送时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'
            }
        }
        
        try:
            requests.post(webhook, json=message, timeout=5)
        except Exception as e:
            current_app.logger.error(f'企业微信通知发送失败: {e}')
    
    @staticmethod
    def _send_sms_notification(user, notification_obj):
        # 实现短信通知发送
        # 这里可以接入阿里云、腾讯云等短信服务
        pass
    
    @staticmethod
    def _send_email_notification(user, notification_obj):
        # 实现邮件通知发送
        # 使用Flask-Mail
        from flask_mail import Message
        from app import mail
        from flask import current_app
        
        if not user.email:
            return
        
        msg = Message(
            subject=notification_obj.title,
            recipients=[user.email],
            body=notification_obj.content,
            sender=current_app.config.get('MAIL_USERNAME')
        )
        
        try:
            mail.send(msg)
        except Exception as e:
            current_app.logger.error(f'邮件通知发送失败: {e}')

# 定时任务
class ScheduledTasks:
    @staticmethod
    def check_maintenance_reminders():
        """检查维保到期提醒"""
        today = datetime.utcnow().date()
        reminder_days = [7, 3, 1]  # 提前7天、3天、1天提醒
        
        for days in reminder_days:
            target_date = today + timedelta(days=days)
            
            # 检查预约的维护
            scheduled_maintenances = Maintenance.query.filter(
                Maintenance.status == 'scheduled',
                db.func.date(Maintenance.schedule_date) == target_date
            ).all()
            
            for m in scheduled_maintenances:
                # 获取资产负责人或部门经理
                asset = m.asset
                if asset and asset.department:
                    # 给部门经理发通知
                    from app.models import User
                    manager = User.query.filter_by(
                        department_id=asset.department_id,
                        role='manager'
                    ).first()
                    
                    if manager:
                        NotificationService.create_notification(
                            user_id=manager.id,
                            title='维保到期提醒',
                            content=f'资产 {asset.name} ({asset.asset_code}) 的维护保养将于 {days} 天后到期，请及时处理。',
                            notification_type='maintenance_reminder',
                            related_type='maintenance',
                            related_id=m.id,
                            send_method='wechat'  # 同时通过企业微信发送
                        )
        
        # 检查维护计划
        for days in reminder_days:
            target_date = today + timedelta(days=days)
            
            plans = MaintenancePlan.query.filter(
                MaintenancePlan.is_active == True,
                db.func.date(MaintenancePlan.next_maintenance_date) == target_date
            ).all()
            
            for plan in plans:
                # 获取相关资产
                if plan.plan_type == 'specific' and plan.asset_id:
                    assets = [Asset.query.get(plan.asset_id)]
                else:
                    assets = Asset.query.filter_by(
                        category=plan.asset_category,
                        status='in_use'
                    ).all()
                
                for asset in assets:
                    if asset and asset.department:
                        from app.models import User
                        manager = User.query.filter_by(
                            department_id=asset.department_id,
                            role='manager'
                        ).first()
                        
                        if manager:
                            NotificationService.create_notification(
                                user_id=manager.id,
                                title='维保计划提醒',
                                content=f'根据维护计划，资产类别 {plan.asset_category} 的资产 {asset.name} ({asset.asset_code}) 应于 {days} 天后进行维护保养。',
                                notification_type='maintenance_reminder',
                                related_type='maintenance_plan',
                                related_id=plan.id,
                                send_method='wechat'
                            )
    
    @staticmethod
    def check_borrow_return_reminders():
        """检查借用归还提醒"""
        today = datetime.utcnow().date()
        reminder_days = [3, 1]  # 提前3天、1天提醒
        
        for days in reminder_days:
            target_date = today + timedelta(days=days)
            
            borrows = AssetBorrow.query.filter(
                AssetBorrow.status == 'borrowed',
                db.func.date(AssetBorrow.expected_return_date) == target_date
            ).all()
            
            for borrow in borrows:
                # 给借用人发通知
                NotificationService.create_notification(
                    user_id=borrow.borrower_id,
                    title='借用归还提醒',
                    content=f'您借用的资产 {borrow.asset.name} ({borrow.asset.asset_code}) 将于 {days} 天后到期，请及时归还。',
                    notification_type='borrow_return',
                    related_type='borrow',
                    related_id=borrow.id,
                    send_method='wechat'
                )
                
                # 给资产管理员或部门经理发通知
                if borrow.asset.department:
                    from app.models import User
                    manager = User.query.filter_by(
                        department_id=borrow.asset.department_id,
                        role='manager'
                    ).first()
                    
                    if manager:
                        NotificationService.create_notification(
                            user_id=manager.id,
                            title='借用即将到期提醒',
                            content=f'员工 {borrow.borrower.name} 借用的资产 {borrow.asset.name} ({borrow.asset.asset_code}) 将于 {days} 天后到期。',
                            notification_type='borrow_return',
                            related_type='borrow',
                            related_id=borrow.id,
                            send_method='system'
                        )
    
    @staticmethod
    def check_approval_reminders():
        """检查审批提醒"""
        # 获取待审批的申请
        pending_approvals = Approval.query.filter_by(
            status='pending'
        ).all()
        
        for approval in pending_approvals:
            # 检查是否超过24小时未处理
            if approval.created_at:
                hours_since_created = (datetime.utcnow() - approval.created_at).total_seconds() / 3600
                
                if hours_since_created >= 24:
                    # 发送提醒
                    title = '待办审批提醒'
                    
                    if approval.approval_type == 'purchase':
                        content = '您有一个采购申请待审批，已超过24小时未处理，请及时处理。'
                    elif approval.approval_type == 'borrow':
                        content = '您有一个资产领用/借用申请待审批，已超过24小时未处理，请及时处理。'
                    elif approval.approval_type == 'disposal':
                        content = '您有一个资产处置申请待审批，已超过24小时未处理，请及时处理。'
                    elif approval.approval_type == 'transfer':
                        content = '您有一个资产调拨申请待审批，已超过24小时未处理，请及时处理。'
                    else:
                        content = '您有一个待审批事项，已超过24小时未处理，请及时处理。'
                    
                    NotificationService.create_notification(
                        user_id=approval.approver_id,
                        title=title,
                        content=content,
                        notification_type='approval',
                        related_type='approval',
                        related_id=approval.id,
                        send_method='wechat'
                    )
    
    @staticmethod
    def check_budget_warnings():
        """检查预算预警"""
        today = datetime.utcnow()
        current_year = today.year
        
        budgets = Budget.query.filter_by(
            year=current_year,
            status='active'
        ).all()
        
        for budget in budgets:
            if budget.total_budget <= 0:
                continue
            
            usage_percentage = (budget.used_budget / budget.total_budget) * 100
            
            # 检查是否达到预警阈值
            if usage_percentage >= budget.warning_threshold:
                # 给部门经理发通知
                if budget.department:
                    from app.models import User
                    manager = User.query.filter_by(
                        department_id=budget.department_id,
                        role='manager'
                    ).first()
                    
                    if manager:
                        NotificationService.create_notification(
                            user_id=manager.id,
                            title='预算预警提醒',
                            content=f'您部门 {budget.year} 年度预算使用率已达到 {usage_percentage:.1f}%，预算预警阈值为 {budget.warning_threshold}%，请注意控制采购支出。',
                            notification_type='budget_warning',
                            related_type='budget',
                            related_id=budget.id,
                            send_method='wechat'
                        )
            
            # 检查预算是否用尽
            if usage_percentage >= 100:
                if budget.department:
                    from app.models import User
                    manager = User.query.filter_by(
                        department_id=budget.department_id,
                        role='manager'
                    ).first()
                    
                    if manager:
                        NotificationService.create_notification(
                            user_id=manager.id,
                            title='预算用尽警告',
                            content=f'您部门 {budget.year} 年度预算已用尽，后续采购需要上级特批。',
                            notification_type='budget_warning',
                            related_type='budget',
                            related_id=budget.id,
                            send_method='wechat'
                        )
