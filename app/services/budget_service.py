from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from app import db
from app.models import Budget, BudgetUsageLog
from sqlalchemy import text


@dataclass
class BudgetCheckResult:
    is_available: bool
    is_over_budget: bool
    special_approval_required: bool
    remaining_budget: float
    usage_percentage: float
    message: str


class BudgetService:
    @staticmethod
    def get_budget(department_id: int, year: int) -> Optional[Budget]:
        return Budget.query.filter_by(
            department_id=department_id,
            year=year,
            status='active'
        ).first()
    
    @staticmethod
    def get_budget_for_update(department_id: int, year: int) -> Optional[Budget]:
        return Budget.query.filter_by(
            department_id=department_id,
            year=year,
            status='active'
        ).with_for_update().first()
    
    @staticmethod
    def check_budget_availability(
        department_id: int,
        year: int,
        amount: float
    ) -> BudgetCheckResult:
        if amount <= 0:
            return BudgetCheckResult(
                is_available=False,
                is_over_budget=False,
                special_approval_required=False,
                remaining_budget=0,
                usage_percentage=0,
                message='金额必须大于0'
            )
        
        budget = BudgetService.get_budget(department_id, year)
        
        if not budget:
            return BudgetCheckResult(
                is_available=True,
                is_over_budget=False,
                special_approval_required=False,
                remaining_budget=0,
                usage_percentage=0,
                message='未找到对应预算，假设可用'
            )
        
        is_available = budget.remaining_budget >= amount
        is_over_budget = not is_available
        
        projected_used = budget.used_budget + amount
        projected_percentage = (projected_used / budget.total_budget * 100) if budget.total_budget > 0 else 0
        
        special_approval_required = False
        if is_over_budget:
            special_approval_required = True
        
        if is_available and projected_percentage >= budget.warning_threshold:
            special_approval_required = False
        
        message = '预算充足' if is_available else f'预算不足。剩余: {budget.remaining_budget:.2f}, 申请: {amount:.2f}'
        
        return BudgetCheckResult(
            is_available=is_available,
            is_over_budget=is_over_budget,
            special_approval_required=special_approval_required,
            remaining_budget=budget.remaining_budget,
            usage_percentage=budget.usage_percentage,
            message=message
        )
    
    @staticmethod
    def allocate_budget(
        department_id: int,
        year: int,
        amount: float,
        operator_id: Optional[int] = None,
        description: str = '',
        related_request_id: Optional[int] = None
    ) -> Tuple[bool, str, Optional[BudgetUsageLog]]:
        if amount <= 0:
            return False, '金额必须大于0', None
        
        budget = BudgetService.get_budget_for_update(department_id, year)
        
        if not budget:
            return False, '未找到对应预算', None
        
        if amount > budget.remaining_budget:
            return (
                False,
                f'预算不足。剩余: {budget.remaining_budget:.2f}, 申请: {amount:.2f}',
                None
            )
        
        try:
            budget.used_budget += amount
            budget.remaining_budget = budget.total_budget - budget.used_budget
            
            usage_log = BudgetUsageLog(
                budget_id=budget.id,
                amount=amount,
                usage_type='purchase',
                related_request_id=related_request_id,
                description=description or f'预算分配: {amount:.2f}',
                operator_id=operator_id
            )
            
            db.session.add(usage_log)
            db.session.commit()
            
            return True, '预算分配成功', usage_log
            
        except Exception as e:
            db.session.rollback()
            return False, f'预算分配失败: {str(e)}', None
    
    @staticmethod
    def release_budget(
        department_id: int,
        year: int,
        amount: float,
        operator_id: Optional[int] = None,
        description: str = ''
    ) -> Tuple[bool, str, Optional[BudgetUsageLog]]:
        if amount <= 0:
            return False, '金额必须大于0', None
        
        budget = BudgetService.get_budget_for_update(department_id, year)
        
        if not budget:
            return False, '未找到对应预算', None
        
        if amount > budget.used_budget:
            return (
                False,
                f'释放金额不能超过已使用预算。已使用: {budget.used_budget:.2f}, 释放: {amount:.2f}',
                None
            )
        
        try:
            budget.used_budget -= amount
            budget.remaining_budget = budget.total_budget - budget.used_budget
            
            usage_log = BudgetUsageLog(
                budget_id=budget.id,
                amount=-amount,
                usage_type='adjustment',
                description=description or f'预算释放: {amount:.2f}',
                operator_id=operator_id
            )
            
            db.session.add(usage_log)
            db.session.commit()
            
            return True, '预算释放成功', usage_log
            
        except Exception as e:
            db.session.rollback()
            return False, f'预算释放失败: {str(e)}', None
    
    @staticmethod
    def get_budget_status(department_id: int, year: int) -> Optional[Dict[str, Any]]:
        budget = BudgetService.get_budget(department_id, year)
        
        if not budget:
            return None
        
        return {
            'department_id': budget.department_id,
            'year': budget.year,
            'total_budget': budget.total_budget,
            'used_budget': budget.used_budget,
            'remaining_budget': budget.remaining_budget,
            'usage_percentage': budget.usage_percentage,
            'warning_threshold': budget.warning_threshold,
            'is_over_warning': budget.is_over_warning,
            'status': budget.status
        }
    
    @staticmethod
    def check_and_set_purchase_budget_flags(purchase_request) -> BudgetCheckResult:
        if not purchase_request.department_id or not purchase_request.budget_year:
            purchase_request.is_over_budget = False
            purchase_request.special_approval_required = False
            return BudgetCheckResult(
                is_available=True,
                is_over_budget=False,
                special_approval_required=False,
                remaining_budget=0,
                usage_percentage=0,
                message='部门或年度未设置，跳过预算检查'
            )
        
        result = BudgetService.check_budget_availability(
            department_id=purchase_request.department_id,
            year=purchase_request.budget_year,
            amount=purchase_request.total_amount
        )
        
        purchase_request.is_over_budget = result.is_over_budget
        purchase_request.special_approval_required = result.special_approval_required
        
        return result
