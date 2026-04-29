from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import math
import json
from collections import defaultdict
from app import db
from app.models import (
    AssetListing, AssetRequest, AssetMatch, AssetTransferProposal,
    MatchingConfig, MatchTask
)
from app.services.event_service import (
    EventService, EventType, EventPriority
)


class AssetCondition(Enum):
    EXCELLENT = 'excellent'
    GOOD = 'good'
    FAIR = 'fair'
    POOR = 'poor'


class ListingStatus(Enum):
    ACTIVE = 'active'
    PENDING = 'pending'
    RESERVED = 'reserved'
    TRANSFERRED = 'transferred'
    EXPIRED = 'expired'
    CANCELLED = 'cancelled'


class RequestStatus(Enum):
    OPEN = 'open'
    MATCHED = 'matched'
    RESERVED = 'reserved'
    FULFILLED = 'fulfilled'
    EXPIRED = 'expired'
    CANCELLED = 'cancelled'


class MatchStatus(Enum):
    PENDING = 'pending'
    PROPOSED = 'proposed'
    ACCEPTED = 'accepted'
    REJECTED = 'rejected'
    COMPLETED = 'completed'


class UrgencyLevel(Enum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'


@dataclass
class MatchResult:
    match_id: int
    match_no: str
    listing_id: int
    request_id: int
    overall_score: float
    scores: Dict[str, float]
    matched_quantity: int
    matched_value: float
    status: str
    listing: Optional[Dict[str, Any]] = None
    request: Optional[Dict[str, Any]] = None


class MatchingAlgorithm:
    def __init__(self, config: Optional[MatchingConfig] = None):
        self.config = config or self._get_default_config()
        
        self.weights = self.config.get_weights()
        
        self.condition_values = {
            'excellent': 1.0,
            'good': 0.8,
            'fair': 0.5,
            'poor': 0.2
        }
        
        self.urgency_values = {
            'low': 0.25,
            'medium': 0.5,
            'high': 0.75,
            'critical': 1.0
        }
    
    def _get_default_config(self) -> MatchingConfig:
        default_config = MatchingConfig.query.filter_by(
            config_type='global',
            is_active=True
        ).order_by(MatchingConfig.priority.desc()).first()
        
        if default_config:
            return default_config
        
        return self._create_default_config_in_memory()
    
    def _create_default_config_in_memory(self) -> MatchingConfig:
        config = MatchingConfig(
            config_name='Default Matching Config',
            config_type='global',
            category_weight=0.25,
            condition_weight=0.20,
            value_weight=0.20,
            quantity_weight=0.15,
            urgency_weight=0.10,
            tag_weight=0.10,
            min_match_score=0.5,
            max_matches_per_listing=5,
            max_matches_per_request=5,
            auto_approve_threshold=0.9,
            is_active=True,
            priority=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        return config
    
    def update_weights(self, config: MatchingConfig):
        self.config = config
        self.weights = config.get_weights()
    
    def get_min_match_score(self) -> float:
        return self.config.min_match_score if self.config else 0.5
    
    def get_max_matches_per_listing(self) -> int:
        return self.config.max_matches_per_listing if self.config else 5
    
    def get_max_matches_per_request(self) -> int:
        return self.config.max_matches_per_request if self.config else 5
    
    def get_auto_approve_threshold(self) -> float:
        return self.config.auto_approve_threshold if self.config else 0.9
    
    def calculate_category_match(self, listing: AssetListing, request: AssetRequest) -> float:
        if not request.required_category:
            return 0.5
        
        listing_category = (listing.category or '').lower()
        request_category = request.required_category.lower()
        
        if listing_category == request_category:
            return 1.0
        
        if request_category in listing_category or listing_category in request_category:
            return 0.7
        
        listing_words = set(listing_category.split())
        request_words = set(request_category.split())
        
        if listing_words & request_words:
            return 0.5
        
        return 0.0
    
    def calculate_condition_match(self, listing: AssetListing, request: AssetRequest) -> float:
        preferred_conditions = request.get_preferred_conditions()
        if not preferred_conditions:
            return 0.5
        
        listing_value = self.condition_values.get(listing.condition, 0.5)
        
        best_match = 0.0
        for preferred in preferred_conditions:
            preferred_value = self.condition_values.get(preferred, 0.5)
            match = 1.0 - abs(listing_value - preferred_value)
            best_match = max(best_match, match)
        
        return best_match
    
    def calculate_value_match(self, listing: AssetListing, request: AssetRequest) -> float:
        if request.max_budget is None or request.max_budget <= 0:
            return 0.8
        
        listing_value = listing.suggested_transfer_value
        
        if listing_value <= 0:
            return 0.3
        
        if listing_value <= request.max_budget:
            ratio = listing_value / request.max_budget
            return 0.5 + 0.5 * (1 - ratio)
        else:
            ratio = request.max_budget / listing_value
            return max(0.0, 0.5 * ratio)
    
    def calculate_quantity_match(self, listing: AssetListing, request: AssetRequest) -> float:
        listing_qty = listing.available_quantity
        request_qty = request.required_quantity
        
        if listing_qty >= request_qty:
            return 1.0
        elif listing_qty >= listing.minimum_transfer_quantity:
            return listing_qty / request_qty
        else:
            return 0.0
    
    def calculate_urgency_match(self, listing: AssetListing, request: AssetRequest) -> float:
        listing_urgency = self.urgency_values.get(listing.urgency, 0.5)
        request_urgency = self.urgency_values.get(request.urgency, 0.5)
        
        if listing_urgency >= 0.75 or request_urgency >= 0.75:
            return 1.0
        elif listing_urgency >= 0.5 or request_urgency >= 0.5:
            return 0.75
        else:
            return 0.5
    
    def calculate_tag_match(self, listing: AssetListing, request: AssetRequest) -> float:
        listing_tags = listing.get_tags()
        request_tags = request.get_tags()
        
        if not listing_tags or not request_tags:
            return 0.3
        
        listing_tag_set = set(tag.lower() for tag in listing_tags)
        request_tag_set = set(tag.lower() for tag in request_tags)
        
        if not request_tag_set:
            return 0.3
        
        matches = listing_tag_set & request_tag_set
        return len(matches) / len(request_tag_set) if request_tag_set else 0.3
    
    def calculate_overall_score(self, listing: AssetListing, request: AssetRequest) -> Tuple[float, Dict[str, float]]:
        category_score = self.calculate_category_match(listing, request)
        condition_score = self.calculate_condition_match(listing, request)
        value_score = self.calculate_value_match(listing, request)
        quantity_score = self.calculate_quantity_match(listing, request)
        urgency_score = self.calculate_urgency_match(listing, request)
        tag_score = self.calculate_tag_match(listing, request)
        
        overall_score = (
            category_score * self.weights.get('category', 0.25) +
            condition_score * self.weights.get('condition', 0.20) +
            value_score * self.weights.get('value', 0.20) +
            quantity_score * self.weights.get('quantity', 0.15) +
            urgency_score * self.weights.get('urgency', 0.10) +
            tag_score * self.weights.get('tag', 0.10)
        )
        
        return round(overall_score, 4), {
            'category': round(category_score, 4),
            'condition': round(condition_score, 4),
            'value': round(value_score, 4),
            'quantity': round(quantity_score, 4),
            'urgency': round(urgency_score, 4),
            'tag': round(tag_score, 4)
        }
    
    def find_matches_for_listing(
        self,
        listing: AssetListing,
        department_id: Optional[int] = None,
        category: Optional[str] = None,
        limit: int = 10
    ) -> List[Tuple[AssetRequest, float, Dict[str, float]]]:
        query = AssetRequest.query.filter(
            AssetRequest.status == 'open',
            AssetRequest.requester_department_id != listing.owner_department_id
        )
        
        if department_id:
            query = query.filter(AssetRequest.requester_department_id == department_id)
        
        if category:
            query = query.filter(
                db.or_(
                    AssetRequest.required_category == category,
                    AssetRequest.required_category.like(f'%{category}%')
                )
            )
        
        if listing.expires_at and listing.expires_at < datetime.utcnow():
            return []
        
        candidates = query.all()
        
        matches = []
        min_score = self.get_min_match_score()
        
        for request in candidates:
            if request.expires_at and request.expires_at < datetime.utcnow():
                continue
            
            overall_score, scores = self.calculate_overall_score(listing, request)
            
            if overall_score >= min_score:
                matches.append((request, overall_score, scores))
        
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:limit]
    
    def find_listings_for_request(
        self,
        request: AssetRequest,
        department_id: Optional[int] = None,
        category: Optional[str] = None,
        limit: int = 10
    ) -> List[Tuple[AssetListing, float, Dict[str, float]]]:
        query = AssetListing.query.filter(
            AssetListing.status == 'active',
            AssetListing.owner_department_id != request.requester_department_id
        )
        
        if department_id:
            query = query.filter(AssetListing.owner_department_id == department_id)
        
        if category:
            query = query.filter(
                db.or_(
                    AssetListing.category == category,
                    AssetListing.category.like(f'%{category}%')
                )
            )
        elif request.required_category:
            query = query.filter(
                db.or_(
                    AssetListing.category == request.required_category,
                    AssetListing.category.like(f'%{request.required_category}%')
                )
            )
        
        candidates = query.all()
        
        matches = []
        min_score = self.get_min_match_score()
        
        for listing in candidates:
            if listing.expires_at and listing.expires_at < datetime.utcnow():
                continue
            
            overall_score, scores = self.calculate_overall_score(listing, request)
            
            if overall_score >= min_score:
                matches.append((listing, overall_score, scores))
        
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:limit]


class MarketplaceService:
    def __init__(self, config: Optional[MatchingConfig] = None):
        self.matching_algorithm = MatchingAlgorithm(config)
        self.event_service = EventService()
    
    def _generate_listing_no(self) -> str:
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        count = AssetListing.query.filter(
            AssetListing.listing_no.like(f'LIST-{timestamp}-%')
        ).count()
        return f'LIST-{timestamp}-{count + 1:06d}'
    
    def _generate_request_no(self) -> str:
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        count = AssetRequest.query.filter(
            AssetRequest.request_no.like(f'REQ-{timestamp}-%')
        ).count()
        return f'REQ-{timestamp}-{count + 1:06d}'
    
    def _generate_match_no(self) -> str:
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f'MATCH-{timestamp}-{int(datetime.now().timestamp() * 1000000) % 10000:04d}'
    
    def _generate_proposal_no(self) -> str:
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f'PROP-{timestamp}-{int(datetime.now().timestamp() * 1000000) % 10000:04d}'
    
    def _generate_task_no(self) -> str:
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f'TASK-{timestamp}-{int(datetime.now().timestamp() * 1000000) % 10000:04d}'
    
    def create_listing(
        self,
        asset_id: int,
        owner_department_id: int,
        owner_user_id: Optional[int],
        title: str,
        description: str,
        category: str,
        original_value: float,
        current_value: float,
        suggested_transfer_value: float,
        available_quantity: int = 1,
        condition: str = 'good',
        condition_description: str = '',
        model: Optional[str] = None,
        specification: Optional[str] = None,
        tags: List[str] = None,
        urgency: str = 'low',
        expires_days: int = 30,
        auto_match: bool = True
    ) -> Tuple[bool, str, Optional[AssetListing]]:
        try:
            listing = AssetListing(
                listing_no=self._generate_listing_no(),
                asset_id=asset_id,
                owner_department_id=owner_department_id,
                owner_user_id=owner_user_id,
                title=title,
                description=description,
                category=category,
                model=model,
                specification=specification,
                condition=condition,
                condition_description=condition_description,
                original_value=original_value,
                current_value=current_value,
                suggested_transfer_value=suggested_transfer_value,
                available_quantity=available_quantity,
                minimum_transfer_quantity=1,
                status='active',
                urgency=urgency,
                listed_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=expires_days),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            if tags:
                listing.set_tags(tags)
            
            db.session.add(listing)
            db.session.commit()
            
            if auto_match:
                self.schedule_match_for_listing(listing.id, owner_user_id)
            
            return True, '挂牌创建成功', listing
            
        except Exception as e:
            db.session.rollback()
            return False, f'挂牌创建失败: {str(e)}', None
    
    def create_request(
        self,
        requester_department_id: int,
        requester_user_id: int,
        title: str,
        description: str,
        required_quantity: int = 1,
        required_category: Optional[str] = None,
        max_budget: Optional[float] = None,
        preferred_conditions: List[str] = None,
        tags: List[str] = None,
        urgency: str = 'medium',
        need_by_days: Optional[int] = None,
        expires_days: int = 30,
        auto_match: bool = True
    ) -> Tuple[bool, str, Optional[AssetRequest]]:
        try:
            request = AssetRequest(
                request_no=self._generate_request_no(),
                requester_department_id=requester_department_id,
                requester_user_id=requester_user_id,
                title=title,
                description=description,
                required_category=required_category,
                required_quantity=required_quantity,
                max_budget=max_budget,
                urgency=urgency,
                need_by_date=datetime.utcnow() + timedelta(days=need_by_days) if need_by_days else None,
                status='open',
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(days=expires_days),
                updated_at=datetime.utcnow()
            )
            
            if preferred_conditions:
                request.set_preferred_conditions(preferred_conditions)
            
            if tags:
                request.set_tags(tags)
            
            db.session.add(request)
            db.session.commit()
            
            if auto_match:
                self.schedule_match_for_request(request.id, requester_user_id)
            
            return True, '需求创建成功', request
            
        except Exception as e:
            db.session.rollback()
            return False, f'需求创建失败: {str(e)}', None
    
    def schedule_match_for_listing(
        self,
        listing_id: int,
        created_by: Optional[int] = None,
        config_id: Optional[int] = None
    ) -> Tuple[bool, str, Optional[MatchTask]]:
        try:
            task = MatchTask(
                task_no=self._generate_task_no(),
                task_type='listing_match',
                listing_id=listing_id,
                config_id=config_id,
                status='pending',
                scheduled_at=datetime.utcnow(),
                created_by=created_by,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.session.add(task)
            db.session.commit()
            
            self.event_service.publish_async(
                event_type=EventType.MATCH_TASK_CREATED,
                data={
                    'task_id': task.id,
                    'task_no': task.task_no,
                    'task_type': 'listing_match',
                    'listing_id': listing_id
                },
                priority=EventPriority.MEDIUM,
                source='MarketplaceService'
            )
            
            return True, '匹配任务已创建', task
            
        except Exception as e:
            db.session.rollback()
            return False, f'匹配任务创建失败: {str(e)}', None
    
    def schedule_match_for_request(
        self,
        request_id: int,
        created_by: Optional[int] = None,
        config_id: Optional[int] = None
    ) -> Tuple[bool, str, Optional[MatchTask]]:
        try:
            task = MatchTask(
                task_no=self._generate_task_no(),
                task_type='request_match',
                request_id=request_id,
                config_id=config_id,
                status='pending',
                scheduled_at=datetime.utcnow(),
                created_by=created_by,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.session.add(task)
            db.session.commit()
            
            self.event_service.publish_async(
                event_type=EventType.MATCH_TASK_CREATED,
                data={
                    'task_id': task.id,
                    'task_no': task.task_no,
                    'task_type': 'request_match',
                    'request_id': request_id
                },
                priority=EventPriority.MEDIUM,
                source='MarketplaceService'
            )
            
            return True, '匹配任务已创建', task
            
        except Exception as e:
            db.session.rollback()
            return False, f'匹配任务创建失败: {str(e)}', None
    
    def execute_match_task(self, task_id: int) -> Tuple[bool, str, int]:
        task = MatchTask.query.get(task_id)
        if not task:
            return False, '任务不存在', 0
        
        if task.status != 'pending':
            return False, f'任务状态不是待处理: {task.status}', 0
        
        try:
            task.status = 'processing'
            task.started_at = datetime.utcnow()
            db.session.commit()
            
            matches_created = 0
            
            if task.task_type == 'listing_match':
                listing = AssetListing.query.get(task.listing_id)
                if listing:
                    matches_created = self._create_matches_for_listing(listing, task.config_id)
            
            elif task.task_type == 'request_match':
                request = AssetRequest.query.get(task.request_id)
                if request:
                    matches_created = self._create_matches_for_request(request, task.config_id)
            
            task.status = 'completed'
            task.completed_at = datetime.utcnow()
            task.matches_created = matches_created
            db.session.commit()
            
            return True, '匹配任务执行完成', matches_created
            
        except Exception as e:
            task.status = 'failed'
            task.failed_at = datetime.utcnow()
            task.error_message = str(e)
            db.session.commit()
            return False, f'匹配任务执行失败: {str(e)}', 0
    
    def _create_matches_for_listing(
        self,
        listing: AssetListing,
        config_id: Optional[int] = None
    ) -> int:
        config = None
        if config_id:
            config = MatchingConfig.query.get(config_id)
        
        if config:
            self.matching_algorithm.update_weights(config)
        
        limit = self.matching_algorithm.get_max_matches_per_listing()
        
        matches = self.matching_algorithm.find_matches_for_listing(
            listing=listing,
            limit=limit * 2
        )
        
        matches_created = 0
        
        for request, score, scores in matches:
            existing_match = AssetMatch.query.filter_by(
                listing_id=listing.id,
                request_id=request.id
            ).first()
            
            if existing_match:
                continue
            
            if matches_created >= limit:
                break
            
            try:
                match = AssetMatch(
                    match_no=self._generate_match_no(),
                    listing_id=listing.id,
                    request_id=request.id,
                    overall_score=score,
                    category_match_score=scores['category'],
                    condition_match_score=scores['condition'],
                    value_match_score=scores['value'],
                    quantity_match_score=scores['quantity'],
                    urgency_match_score=scores['urgency'],
                    tag_match_score=scores['tag'],
                    matched_quantity=min(listing.available_quantity, request.required_quantity),
                    matched_value=min(listing.available_quantity, request.required_quantity) * listing.suggested_transfer_value,
                    status='pending',
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                db.session.add(match)
                matches_created += 1
                
                listing.match_count = (listing.match_count or 0) + 1
                request.match_count = (request.match_count or 0) + 1
                
            except Exception:
                db.session.rollback()
                continue
        
        if matches_created > 0:
            db.session.commit()
        
        return matches_created
    
    def _create_matches_for_request(
        self,
        request: AssetRequest,
        config_id: Optional[int] = None
    ) -> int:
        config = None
        if config_id:
            config = MatchingConfig.query.get(config_id)
        
        if config:
            self.matching_algorithm.update_weights(config)
        
        limit = self.matching_algorithm.get_max_matches_per_request()
        
        matches = self.matching_algorithm.find_listings_for_request(
            request=request,
            limit=limit * 2
        )
        
        matches_created = 0
        
        for listing, score, scores in matches:
            existing_match = AssetMatch.query.filter_by(
                listing_id=listing.id,
                request_id=request.id
            ).first()
            
            if existing_match:
                continue
            
            if matches_created >= limit:
                break
            
            try:
                match = AssetMatch(
                    match_no=self._generate_match_no(),
                    listing_id=listing.id,
                    request_id=request.id,
                    overall_score=score,
                    category_match_score=scores['category'],
                    condition_match_score=scores['condition'],
                    value_match_score=scores['value'],
                    quantity_match_score=scores['quantity'],
                    urgency_match_score=scores['urgency'],
                    tag_match_score=scores['tag'],
                    matched_quantity=min(listing.available_quantity, request.required_quantity),
                    matched_value=min(listing.available_quantity, request.required_quantity) * listing.suggested_transfer_value,
                    status='pending',
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                
                db.session.add(match)
                matches_created += 1
                
                listing.match_count = (listing.match_count or 0) + 1
                request.match_count = (request.match_count or 0) + 1
                
            except Exception:
                db.session.rollback()
                continue
        
        if matches_created > 0:
            db.session.commit()
        
        return matches_created
    
    def propose_match(
        self,
        match_id: int,
        proposer_id: int
    ) -> Tuple[bool, str, Optional[AssetMatch]]:
        match = AssetMatch.query.get(match_id)
        if not match:
            return False, '匹配不存在', None
        
        if match.status != 'pending':
            return False, f'匹配状态不是待处理: {match.status}', None
        
        try:
            match.status = 'proposed'
            match.proposed_at = datetime.utcnow()
            
            listing = AssetListing.query.get(match.listing_id)
            if listing:
                listing.status = 'pending'
            
            request = AssetRequest.query.get(match.request_id)
            if request:
                request.status = 'matched'
            
            db.session.commit()
            
            self.event_service.publish_async(
                event_type=EventType.MATCH_PROPOSED,
                data={
                    'match_id': match.id,
                    'match_no': match.match_no,
                    'listing_id': match.listing_id,
                    'request_id': match.request_id,
                    'overall_score': match.overall_score,
                    'proposer_id': proposer_id
                },
                priority=EventPriority.MEDIUM,
                source='MarketplaceService'
            )
            
            return True, '匹配已提议', match
            
        except Exception as e:
            db.session.rollback()
            return False, f'匹配提议失败: {str(e)}', None
    
    def accept_match(
        self,
        match_id: int,
        acceptor_id: int
    ) -> Tuple[bool, str, Optional[AssetTransferProposal]]:
        match = AssetMatch.query.get(match_id)
        if not match:
            return False, '匹配不存在', None
        
        if match.status not in ['proposed', 'pending']:
            return False, f'匹配状态不允许接受: {match.status}', None
        
        listing = AssetListing.query.get(match.listing_id)
        request = AssetRequest.query.get(match.request_id)
        
        if not listing or not request:
            return False, '关联的挂牌或请求不存在', None
        
        try:
            match.status = 'accepted'
            match.accepted_at = datetime.utcnow()
            
            auto_approve_threshold = self.matching_algorithm.get_auto_approve_threshold()
            should_auto_approve = match.overall_score >= auto_approve_threshold
            
            proposal = AssetTransferProposal(
                proposal_no=self._generate_proposal_no(),
                match_id=match.id,
                listing_id=match.listing_id,
                request_id=match.request_id,
                from_department_id=listing.owner_department_id,
                to_department_id=request.requester_department_id,
                from_user_id=listing.owner_user_id,
                to_user_id=request.requester_user_id,
                asset_id=listing.asset_id,
                quantity=match.matched_quantity,
                transfer_value=match.matched_value,
                status='approved' if should_auto_approve else 'pending',
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            if should_auto_approve:
                proposal.approved_at = datetime.utcnow()
                proposal.approved_by = acceptor_id
                proposal.approval_comments = '系统自动批准（高匹配分数）'
            
            listing.status = 'reserved'
            listing.reserved_by = acceptor_id
            listing.reserved_at = datetime.utcnow()
            
            request.status = 'reserved'
            
            db.session.add(proposal)
            db.session.commit()
            
            self.event_service.publish_async(
                event_type=EventType.MATCH_ACCEPTED,
                data={
                    'match_id': match.id,
                    'match_no': match.match_no,
                    'proposal_id': proposal.id,
                    'proposal_no': proposal.proposal_no,
                    'auto_approved': should_auto_approve,
                    'acceptor_id': acceptor_id
                },
                priority=EventPriority.HIGH,
                source='MarketplaceService'
            )
            
            return True, '匹配已接受，转让提议已生成', proposal
            
        except Exception as e:
            db.session.rollback()
            return False, f'匹配接受失败: {str(e)}', None
    
    def reject_match(
        self,
        match_id: int,
        rejector_id: int,
        reason: str
    ) -> Tuple[bool, str]:
        match = AssetMatch.query.get(match_id)
        if not match:
            return False, '匹配不存在'
        
        if match.status not in ['pending', 'proposed']:
            return False, f'匹配状态不允许拒绝: {match.status}'
        
        try:
            match.status = 'rejected'
            match.rejected_at = datetime.utcnow()
            match.rejection_reason = reason
            
            listing = AssetListing.query.get(match.listing_id)
            if listing and listing.status == 'pending':
                listing.status = 'active'
            
            request = AssetRequest.query.get(match.request_id)
            if request and request.status == 'matched':
                request.status = 'open'
            
            db.session.commit()
            
            self.event_service.publish_async(
                event_type=EventType.MATCH_REJECTED,
                data={
                    'match_id': match.id,
                    'match_no': match.match_no,
                    'rejector_id': rejector_id,
                    'reason': reason
                },
                priority=EventPriority.MEDIUM,
                source='MarketplaceService'
            )
            
            return True, '匹配已拒绝'
            
        except Exception as e:
            db.session.rollback()
            return False, f'匹配拒绝失败: {str(e)}'
    
    def approve_proposal(
        self,
        proposal_id: int,
        approver_id: int,
        comments: str = ''
    ) -> Tuple[bool, str]:
        proposal = AssetTransferProposal.query.get(proposal_id)
        if not proposal:
            return False, '提议不存在'
        
        if proposal.status != 'pending':
            return False, f'提议状态不是待审批: {proposal.status}'
        
        try:
            proposal.status = 'approved'
            proposal.approved_at = datetime.utcnow()
            proposal.approved_by = approver_id
            proposal.approval_comments = comments
            
            db.session.commit()
            
            self.event_service.publish_async(
                event_type=EventType.TRANSFER_PROPOSAL_APPROVED,
                data={
                    'proposal_id': proposal.id,
                    'proposal_no': proposal.proposal_no,
                    'match_id': proposal.match_id,
                    'approver_id': approver_id
                },
                priority=EventPriority.HIGH,
                source='MarketplaceService'
            )
            
            return True, '转让提议已批准'
            
        except Exception as e:
            db.session.rollback()
            return False, f'提议批准失败: {str(e)}'
    
    def reject_proposal(
        self,
        proposal_id: int,
        rejector_id: int,
        reason: str
    ) -> Tuple[bool, str]:
        proposal = AssetTransferProposal.query.get(proposal_id)
        if not proposal:
            return False, '提议不存在'
        
        if proposal.status != 'pending':
            return False, f'提议状态不是待审批: {proposal.status}'
        
        try:
            proposal.status = 'rejected'
            proposal.rejected_at = datetime.utcnow()
            proposal.rejected_by = rejector_id
            proposal.rejection_reason = reason
            
            match = AssetMatch.query.get(proposal.match_id)
            if match:
                match.status = 'rejected'
                match.rejection_reason = f'转让提议被拒绝: {reason}'
            
            listing = AssetListing.query.get(proposal.listing_id)
            if listing:
                listing.status = 'active'
                listing.reserved_by = None
                listing.reserved_at = None
            
            request = AssetRequest.query.get(proposal.request_id)
            if request:
                request.status = 'open'
            
            db.session.commit()
            
            self.event_service.publish_async(
                event_type=EventType.TRANSFER_PROPOSAL_REJECTED,
                data={
                    'proposal_id': proposal.id,
                    'proposal_no': proposal.proposal_no,
                    'rejector_id': rejector_id,
                    'reason': reason
                },
                priority=EventPriority.MEDIUM,
                source='MarketplaceService'
            )
            
            return True, '转让提议已拒绝'
            
        except Exception as e:
            db.session.rollback()
            return False, f'提议拒绝失败: {str(e)}'
    
    def complete_transfer(
        self,
        proposal_id: int,
        handler_id: int
    ) -> Tuple[bool, str]:
        proposal = AssetTransferProposal.query.get(proposal_id)
        if not proposal:
            return False, '提议不存在'
        
        if proposal.status != 'approved':
            return False, f'提议状态不是已批准: {proposal.status}'
        
        try:
            proposal.status = 'completed'
            proposal.completed_at = datetime.utcnow()
            proposal.transfer_date = datetime.utcnow()
            
            match = AssetMatch.query.get(proposal.match_id)
            if match:
                match.status = 'completed'
                match.completed_at = datetime.utcnow()
            
            listing = AssetListing.query.get(proposal.listing_id)
            if listing:
                listing.available_quantity -= proposal.quantity
                if listing.available_quantity <= 0:
                    listing.status = 'transferred'
                else:
                    listing.status = 'active'
                    listing.reserved_by = None
                    listing.reserved_at = None
            
            request = AssetRequest.query.get(proposal.request_id)
            if request:
                request.required_quantity -= proposal.quantity
                if request.required_quantity <= 0:
                    request.status = 'fulfilled'
                else:
                    request.status = 'open'
            
            db.session.commit()
            
            self.event_service.publish_async(
                event_type=EventType.ASSET_TRANSFER_COMPLETED,
                data={
                    'proposal_id': proposal.id,
                    'proposal_no': proposal.proposal_no,
                    'asset_id': proposal.asset_id,
                    'from_department_id': proposal.from_department_id,
                    'to_department_id': proposal.to_department_id,
                    'quantity': proposal.quantity,
                    'transfer_value': proposal.transfer_value,
                    'handler_id': handler_id
                },
                priority=EventPriority.HIGH,
                source='MarketplaceService'
            )
            
            return True, '资产转让已完成'
            
        except Exception as e:
            db.session.rollback()
            return False, f'转让完成失败: {str(e)}'
    
    def get_listing_matches(self, listing_id: int) -> List[Dict[str, Any]]:
        matches = AssetMatch.query.filter_by(listing_id=listing_id).order_by(
            AssetMatch.overall_score.desc()
        ).all()
        
        return [
            {
                'id': m.id,
                'match_no': m.match_no,
                'request_id': m.request_id,
                'overall_score': m.overall_score,
                'status': m.status,
                'matched_quantity': m.matched_quantity,
                'matched_value': m.matched_value,
                'created_at': m.created_at.isoformat() if m.created_at else None
            }
            for m in matches
        ]
    
    def get_request_matches(self, request_id: int) -> List[Dict[str, Any]]:
        matches = AssetMatch.query.filter_by(request_id=request_id).order_by(
            AssetMatch.overall_score.desc()
        ).all()
        
        return [
            {
                'id': m.id,
                'match_no': m.match_no,
                'listing_id': m.listing_id,
                'overall_score': m.overall_score,
                'status': m.status,
                'matched_quantity': m.matched_quantity,
                'matched_value': m.matched_value,
                'created_at': m.created_at.isoformat() if m.created_at else None
            }
            for m in matches
        ]
    
    def get_marketplace_stats(self) -> Dict[str, Any]:
        total_listings = AssetListing.query.count()
        active_listings = AssetListing.query.filter_by(status='active').count()
        pending_listings = AssetListing.query.filter_by(status='pending').count()
        
        total_requests = AssetRequest.query.count()
        open_requests = AssetRequest.query.filter_by(status='open').count()
        matched_requests = AssetRequest.query.filter_by(status='matched').count()
        
        total_matches = AssetMatch.query.count()
        pending_matches = AssetMatch.query.filter_by(status='pending').count()
        proposed_matches = AssetMatch.query.filter_by(status='proposed').count()
        completed_matches = AssetMatch.query.filter_by(status='completed').count()
        
        total_proposals = AssetTransferProposal.query.count()
        pending_proposals = AssetTransferProposal.query.filter_by(status='pending').count()
        approved_proposals = AssetTransferProposal.query.filter_by(status='approved').count()
        completed_proposals = AssetTransferProposal.query.filter_by(status='completed').count()
        
        total_value = db.session.query(
            db.func.sum(AssetListing.suggested_transfer_value * AssetListing.available_quantity)
        ).filter(AssetListing.status == 'active').scalar() or 0
        
        total_pending_tasks = MatchTask.query.filter_by(status='pending').count()
        total_processing_tasks = MatchTask.query.filter_by(status='processing').count()
        
        return {
            'listings': {
                'total': total_listings,
                'active': active_listings,
                'pending': pending_listings
            },
            'requests': {
                'total': total_requests,
                'open': open_requests,
                'matched': matched_requests
            },
            'matches': {
                'total': total_matches,
                'pending': pending_matches,
                'proposed': proposed_matches,
                'completed': completed_matches
            },
            'proposals': {
                'total': total_proposals,
                'pending': pending_proposals,
                'approved': approved_proposals,
                'completed': completed_proposals
            },
            'tasks': {
                'pending': total_pending_tasks,
                'processing': total_processing_tasks
            },
            'marketplace_value': round(total_value, 2),
            'generated_at': datetime.utcnow().isoformat()
        }
    
    def create_matching_config(
        self,
        config_name: str,
        config_type: str = 'global',
        category_weight: float = 0.25,
        condition_weight: float = 0.20,
        value_weight: float = 0.20,
        quantity_weight: float = 0.15,
        urgency_weight: float = 0.10,
        tag_weight: float = 0.10,
        min_match_score: float = 0.5,
        max_matches_per_listing: int = 5,
        max_matches_per_request: int = 5,
        auto_approve_threshold: float = 0.9,
        target_department_id: Optional[int] = None,
        target_category: Optional[str] = None,
        priority: int = 0,
        description: str = ''
    ) -> Tuple[bool, str, Optional[MatchingConfig]]:
        total_weight = (
            category_weight + condition_weight + value_weight +
            quantity_weight + urgency_weight + tag_weight
        )
        
        if abs(total_weight - 1.0) > 0.001:
            return False, f'权重总和必须为1.0，当前为 {total_weight}', None
        
        try:
            config = MatchingConfig(
                config_name=config_name,
                config_type=config_type,
                category_weight=category_weight,
                condition_weight=condition_weight,
                value_weight=value_weight,
                quantity_weight=quantity_weight,
                urgency_weight=urgency_weight,
                tag_weight=tag_weight,
                min_match_score=min_match_score,
                max_matches_per_listing=max_matches_per_listing,
                max_matches_per_request=max_matches_per_request,
                auto_approve_threshold=auto_approve_threshold,
                target_department_id=target_department_id,
                target_category=target_category,
                is_active=True,
                priority=priority,
                description=description,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            db.session.add(config)
            db.session.commit()
            
            return True, '匹配配置创建成功', config
            
        except Exception as e:
            db.session.rollback()
            return False, f'匹配配置创建失败: {str(e)}', None
    
    def get_active_config(self, department_id: Optional[int] = None, category: Optional[str] = None) -> Optional[MatchingConfig]:
        query = MatchingConfig.query.filter_by(is_active=True)
        
        if department_id:
            query = query.filter(
                db.or_(
                    MatchingConfig.config_type == 'global',
                    MatchingConfig.target_department_id == department_id
                )
            )
        
        if category:
            query = query.filter(
                db.or_(
                    MatchingConfig.config_type == 'global',
                    MatchingConfig.target_category == category
                )
            )
        
        return query.order_by(MatchingConfig.priority.desc()).first()
