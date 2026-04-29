from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from app import db
from app.models import PurchaseRequest, PurchaseRequestItem
from app.services import BudgetService, EventService, EventType, EventPriority


class PurchaseService:
    @staticmethod
    def create_purchase_request(
        department_id: int,
        requester_id: int,
        title: str,
        budget_year: int,
        total_amount: float,
        supplier_id: Optional[int] = None,
        description: str = ''
    ) -> Tuple[bool, str, Optional[PurchaseRequest]]:
        purchase = PurchaseRequest(
            request_no=PurchaseService._generate_request_no(),
            department_id=department_id,
            requester_id=requester_id,
            title=title,
            budget_year=budget_year,
            total_amount=total_amount,
            supplier_id=supplier_id,
            description=description,
            status='pending'
        )
        
        BudgetService.check_and_set_purchase_budget_flags(purchase)
        
        try:
            db.session.add(purchase)
            db.session.commit()
            
            event_service = EventService()
            event_service.publish_async(
                event_type=EventType.PURCHASE_SUBMITTED,
                data={
                    'purchase_request_id': purchase.id,
                    'request_no': purchase.request_no,
                    'department_id': department_id,
                    'requester_id': requester_id,
                    'total_amount': total_amount,
                    'is_over_budget': purchase.is_over_budget,
                    'special_approval_required': purchase.special_approval_required
                },
                priority=EventPriority.MEDIUM,
                source='PurchaseService.create'
            )
            
            return True, '采购申请创建成功', purchase
            
        except Exception as e:
            db.session.rollback()
            return False, f'采购申请创建失败: {str(e)}', None
    
    @staticmethod
    def update_purchase_request(
        purchase_request: PurchaseRequest,
        **kwargs
    ) -> Tuple[bool, str]:
        allowed_fields = [
            'title', 'description', 'total_amount', 
            'supplier_id', 'budget_year', 'department_id'
        ]
        
        for key, value in kwargs.items():
            if key in allowed_fields:
                setattr(purchase_request, key, value)
        
        BudgetService.check_and_set_purchase_budget_flags(purchase_request)
        
        try:
            db.session.commit()
            return True, '采购申请更新成功'
        except Exception as e:
            db.session.rollback()
            return False, f'采购申请更新失败: {str(e)}'
    
    @staticmethod
    def approve_purchase_request(
        purchase_request: PurchaseRequest,
        approver_id: int,
        comment: str = ''
    ) -> Tuple[bool, str]:
        if purchase_request.status != 'pending':
            return False, '只能审批待处理的采购申请'
        
        if purchase_request.is_over_budget and purchase_request.special_approval_required:
            pass
        
        purchase_request.status = 'approved'
        
        BudgetService.check_and_set_purchase_budget_flags(purchase_request)
        
        try:
            db.session.commit()
            
            event_service = EventService()
            event_service.publish_async(
                event_type=EventType.PURCHASE_APPROVED,
                data={
                    'purchase_request_id': purchase_request.id,
                    'request_no': purchase_request.request_no,
                    'department_id': purchase_request.department_id,
                    'requester_id': purchase_request.requester_id,
                    'approver_id': approver_id,
                    'total_amount': purchase_request.total_amount,
                    'supplier_id': purchase_request.supplier_id,
                    'comment': comment
                },
                priority=EventPriority.HIGH,
                source='PurchaseService.approve'
            )
            
            return True, '采购申请审批通过'
            
        except Exception as e:
            db.session.rollback()
            return False, f'采购申请审批失败: {str(e)}'
    
    @staticmethod
    def reject_purchase_request(
        purchase_request: PurchaseRequest,
        approver_id: int,
        comment: str = ''
    ) -> Tuple[bool, str]:
        if purchase_request.status != 'pending':
            return False, '只能审批待处理的采购申请'
        
        purchase_request.status = 'rejected'
        
        try:
            db.session.commit()
            
            event_service = EventService()
            event_service.publish_async(
                event_type=EventType.PURCHASE_REJECTED,
                data={
                    'purchase_request_id': purchase_request.id,
                    'request_no': purchase_request.request_no,
                    'department_id': purchase_request.department_id,
                    'requester_id': purchase_request.requester_id,
                    'approver_id': approver_id,
                    'total_amount': purchase_request.total_amount,
                    'comment': comment
                },
                priority=EventPriority.MEDIUM,
                source='PurchaseService.reject'
            )
            
            return True, '采购申请已拒绝'
            
        except Exception as e:
            db.session.rollback()
            return False, f'采购申请拒绝失败: {str(e)}'
    
    @staticmethod
    def complete_purchase_request(
        purchase_request: PurchaseRequest
    ) -> Tuple[bool, str]:
        if purchase_request.status != 'approved':
            return False, '只能完成已批准的采购申请'
        
        purchase_request.status = 'completed'
        
        try:
            db.session.commit()
            return True, '采购申请已完成'
        except Exception as e:
            db.session.rollback()
            return False, f'采购申请完成失败: {str(e)}'
    
    @staticmethod
    def _generate_request_no() -> str:
        now = datetime.now()
        timestamp = now.strftime('%Y%m%d%H%M%S')
        return f'PR{timestamp}'
    
    @staticmethod
    def add_purchase_item(
        purchase_request_id: int,
        name: str,
        quantity: int,
        unit_price: float,
        category: str = '',
        model: str = '',
        specification: str = '',
        unit: str = '台',
        description: str = ''
    ) -> Tuple[bool, str, Optional[PurchaseRequestItem]]:
        if quantity <= 0:
            return False, '数量必须大于0', None
        if unit_price < 0:
            return False, '单价不能为负数', None
        
        item = PurchaseRequestItem(
            purchase_request_id=purchase_request_id,
            name=name,
            quantity=quantity,
            unit_price=unit_price,
            total_price=quantity * unit_price,
            category=category,
            model=model,
            specification=specification,
            unit=unit,
            description=description
        )
        
        try:
            db.session.add(item)
            db.session.commit()
            
            purchase = PurchaseRequest.query.get(purchase_request_id)
            if purchase:
                total = sum(i.total_price for i in purchase.items)
                purchase.total_amount = total
                BudgetService.check_and_set_purchase_budget_flags(purchase)
                db.session.commit()
            
            return True, '采购物品添加成功', item
            
        except Exception as e:
            db.session.rollback()
            return False, f'采购物品添加失败: {str(e)}', None
    
    @staticmethod
    def get_purchase_budget_check(
        department_id: int,
        budget_year: int,
        total_amount: float
    ) -> Dict[str, Any]:
        result = BudgetService.check_budget_availability(
            department_id=department_id,
            year=budget_year,
            amount=total_amount
        )
        
        return {
            'is_available': result.is_available,
            'is_over_budget': result.is_over_budget,
            'special_approval_required': result.special_approval_required,
            'remaining_budget': result.remaining_budget,
            'usage_percentage': result.usage_percentage,
            'message': result.message
        }
