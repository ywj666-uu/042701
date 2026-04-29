from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import math
from collections import defaultdict
from app import db


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
class AssetListing:
    listing_id: str
    asset_id: int
    owner_department_id: int
    owner_user_id: Optional[int]
    
    title: str
    description: str
    category: str
    model: Optional[str]
    specification: Optional[str]
    
    condition: AssetCondition
    condition_description: str
    
    original_value: float
    current_value: float
    suggested_transfer_value: float
    
    available_quantity: int
    minimum_transfer_quantity: int = 1
    
    tags: List[str] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    
    status: ListingStatus = ListingStatus.ACTIVE
    urgency: UrgencyLevel = UrgencyLevel.LOW
    
    listed_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    reserved_by: Optional[int] = None
    reserved_at: Optional[datetime] = None
    
    view_count: int = 0
    interest_count: int = 0
    match_count: int = 0
    
    notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'listing_id': self.listing_id,
            'asset_id': self.asset_id,
            'owner_department_id': self.owner_department_id,
            'owner_user_id': self.owner_user_id,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'model': self.model,
            'specification': self.specification,
            'condition': self.condition.value,
            'condition_description': self.condition_description,
            'original_value': self.original_value,
            'current_value': self.current_value,
            'suggested_transfer_value': self.suggested_transfer_value,
            'available_quantity': self.available_quantity,
            'minimum_transfer_quantity': self.minimum_transfer_quantity,
            'tags': self.tags,
            'status': self.status.value,
            'urgency': self.urgency.value,
            'listed_at': self.listed_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'view_count': self.view_count,
            'interest_count': self.interest_count,
            'match_count': self.match_count
        }


@dataclass
class AssetRequest:
    request_id: str
    requester_department_id: int
    requester_user_id: int
    
    title: str
    description: str
    required_category: Optional[str]
    required_quantity: int = 1
    
    preferred_conditions: List[AssetCondition] = field(default_factory=lambda: [AssetCondition.EXCELLENT, AssetCondition.GOOD])
    max_budget: Optional[float] = None
    
    urgency: UrgencyLevel = UrgencyLevel.MEDIUM
    need_by_date: Optional[datetime] = None
    
    tags: List[str] = field(default_factory=list)
    alternative_options: str = ''
    
    status: RequestStatus = RequestStatus.OPEN
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    view_count: int = 0
    match_count: int = 0
    
    notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'request_id': self.request_id,
            'requester_department_id': self.requester_department_id,
            'requester_user_id': self.requester_user_id,
            'title': self.title,
            'description': self.description,
            'required_category': self.required_category,
            'required_quantity': self.required_quantity,
            'preferred_conditions': [c.value for c in self.preferred_conditions],
            'max_budget': self.max_budget,
            'urgency': self.urgency.value,
            'need_by_date': self.need_by_date.isoformat() if self.need_by_date else None,
            'tags': self.tags,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'view_count': self.view_count,
            'match_count': self.match_count
        }


@dataclass
class AssetMatch:
    match_id: str
    listing_id: str
    request_id: str
    
    listing: Optional[AssetListing] = None
    request: Optional[AssetRequest] = None
    
    overall_score: float = 0.0
    category_match_score: float = 0.0
    condition_match_score: float = 0.0
    value_match_score: float = 0.0
    quantity_match_score: float = 0.0
    urgency_match_score: float = 0.0
    tag_match_score: float = 0.0
    
    matched_quantity: int = 0
    matched_value: float = 0.0
    
    status: MatchStatus = MatchStatus.PENDING
    
    proposed_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    rejection_reason: str = ''
    
    notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'match_id': self.match_id,
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
            'status': self.status.value,
            'proposed_at': self.proposed_at.isoformat() if self.proposed_at else None,
            'accepted_at': self.accepted_at.isoformat() if self.accepted_at else None,
            'listing': self.listing.to_dict() if self.listing else None,
            'request': self.request.to_dict() if self.request else None
        }


@dataclass
class AssetTransferProposal:
    proposal_id: str
    match_id: str
    listing_id: str
    request_id: str
    
    from_department_id: int
    to_department_id: int
    
    asset_id: int
    quantity: int
    
    transfer_value: float
    transfer_date: Optional[datetime] = None
    
    status: str = 'pending'
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    approval_comments: str = ''
    rejection_reason: str = ''
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'proposal_id': self.proposal_id,
            'match_id': self.match_id,
            'listing_id': self.listing_id,
            'request_id': self.request_id,
            'from_department_id': self.from_department_id,
            'to_department_id': self.to_department_id,
            'asset_id': self.asset_id,
            'quantity': self.quantity,
            'transfer_value': self.transfer_value,
            'transfer_date': self.transfer_date.isoformat() if self.transfer_date else None,
            'status': self.status,
            'created_at': self.created_at.isoformat()
        }


class MatchingAlgorithm:
    def __init__(self):
        self.weights = {
            'category': 0.25,
            'condition': 0.20,
            'value': 0.20,
            'quantity': 0.15,
            'urgency': 0.10,
            'tags': 0.10
        }
        
        self.condition_values = {
            AssetCondition.EXCELLENT: 1.0,
            AssetCondition.GOOD: 0.8,
            AssetCondition.FAIR: 0.5,
            AssetCondition.POOR: 0.2
        }
        
        self.urgency_values = {
            UrgencyLevel.LOW: 0.25,
            UrgencyLevel.MEDIUM: 0.5,
            UrgencyLevel.HIGH: 0.75,
            UrgencyLevel.CRITICAL: 1.0
        }
    
    def calculate_category_match(self, listing: AssetListing, request: AssetRequest) -> float:
        if not request.required_category:
            return 0.5
        
        listing_category = listing.category.lower()
        request_category = request.required_category.lower()
        
        if listing_category == request_category:
            return 1.0
        
        if request_category in listing_category or listing_category in request_category:
            return 0.7
        
        return 0.0
    
    def calculate_condition_match(self, listing: AssetListing, request: AssetRequest) -> float:
        if not request.preferred_conditions:
            return 0.5
        
        listing_value = self.condition_values.get(listing.condition, 0.5)
        
        best_match = 0.0
        for preferred in request.preferred_conditions:
            preferred_value = self.condition_values.get(preferred, 0.5)
            match = 1.0 - abs(listing_value - preferred_value)
            best_match = max(best_match, match)
        
        return best_match
    
    def calculate_value_match(self, listing: AssetListing, request: AssetRequest) -> float:
        if request.max_budget is None:
            return 0.8
        
        listing_value = listing.suggested_transfer_value
        
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
        if not listing.tags or not request.tags:
            return 0.3
        
        listing_tags = set(tag.lower() for tag in listing.tags)
        request_tags = set(tag.lower() for tag in request.tags)
        
        if not request_tags:
            return 0.3
        
        matches = listing_tags & request_tags
        return len(matches) / len(request_tags) if request_tags else 0.3
    
    def calculate_overall_score(self, listing: AssetListing, request: AssetRequest) -> Tuple[float, Dict[str, float]]:
        category_score = self.calculate_category_match(listing, request)
        condition_score = self.calculate_condition_match(listing, request)
        value_score = self.calculate_value_match(listing, request)
        quantity_score = self.calculate_quantity_match(listing, request)
        urgency_score = self.calculate_urgency_match(listing, request)
        tag_score = self.calculate_tag_match(listing, request)
        
        overall_score = (
            category_score * self.weights['category'] +
            condition_score * self.weights['condition'] +
            value_score * self.weights['value'] +
            quantity_score * self.weights['quantity'] +
            urgency_score * self.weights['urgency'] +
            tag_score * self.weights['tags']
        )
        
        return overall_score, {
            'category': category_score,
            'condition': condition_score,
            'value': value_score,
            'quantity': quantity_score,
            'urgency': urgency_score,
            'tags': tag_score
        }
    
    def find_matches(self, listing: AssetListing, 
                     requests: List[AssetRequest],
                     min_score: float = 0.5) -> List[Tuple[AssetRequest, float, Dict[str, float]]]:
        matches = []
        
        for request in requests:
            if request.status != RequestStatus.OPEN:
                continue
            
            if listing.owner_department_id == request.requester_department_id:
                continue
            
            overall_score, scores = self.calculate_overall_score(listing, request)
            
            if overall_score >= min_score:
                matches.append((request, overall_score, scores))
        
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches
    
    def find_listings_for_request(self, request: AssetRequest,
                                   listings: List[AssetListing],
                                   min_score: float = 0.5) -> List[Tuple[AssetListing, float, Dict[str, float]]]:
        matches = []
        
        for listing in listings:
            if listing.status != ListingStatus.ACTIVE:
                continue
            
            if listing.owner_department_id == request.requester_department_id:
                continue
            
            overall_score, scores = self.calculate_overall_score(listing, request)
            
            if overall_score >= min_score:
                matches.append((listing, overall_score, scores))
        
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches


class MarketplaceService:
    def __init__(self):
        self.listings: Dict[str, AssetListing] = {}
        self.requests: Dict[str, AssetRequest] = {}
        self.matches: Dict[str, AssetMatch] = {}
        self.proposals: Dict[str, AssetTransferProposal] = {}
        
        self.matching_algorithm = MatchingAlgorithm()
        
        self.listing_counter = 0
        self.request_counter = 0
        self.match_counter = 0
        self.proposal_counter = 0
    
    def _generate_listing_id(self) -> str:
        self.listing_counter += 1
        timestamp = datetime.now().strftime('%Y%m%d')
        return f"LIST-{timestamp}-{self.listing_counter:06d}"
    
    def _generate_request_id(self) -> str:
        self.request_counter += 1
        timestamp = datetime.now().strftime('%Y%m%d')
        return f"REQ-{timestamp}-{self.request_counter:06d}"
    
    def _generate_match_id(self) -> str:
        self.match_counter += 1
        return f"MATCH-{datetime.now().strftime('%Y%m%d%H%M%S')}-{self.match_counter:04d}"
    
    def _generate_proposal_id(self) -> str:
        self.proposal_counter += 1
        return f"PROP-{datetime.now().strftime('%Y%m%d%H%M%S')}-{self.proposal_counter:04d}"
    
    def create_listing(self, 
                       asset_id: int,
                       owner_department_id: int,
                       owner_user_id: Optional[int],
                       title: str,
                       description: str,
                       category: str,
                       original_value: float,
                       current_value: float,
                       suggested_transfer_value: float,
                       available_quantity: int,
                       condition: AssetCondition = AssetCondition.GOOD,
                       condition_description: str = '',
                       model: Optional[str] = None,
                       specification: Optional[str] = None,
                       tags: List[str] = None,
                       urgency: UrgencyLevel = UrgencyLevel.LOW,
                       expires_days: int = 30) -> AssetListing:
        listing = AssetListing(
            listing_id=self._generate_listing_id(),
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
            tags=tags or [],
            urgency=urgency,
            expires_at=datetime.utcnow() + timedelta(days=expires_days)
        )
        
        self.listings[listing.listing_id] = listing
        
        self._run_matching_for_listing(listing)
        
        return listing
    
    def create_request(self,
                       requester_department_id: int,
                       requester_user_id: int,
                       title: str,
                       description: str,
                       required_quantity: int = 1,
                       required_category: Optional[str] = None,
                       max_budget: Optional[float] = None,
                       preferred_conditions: List[AssetCondition] = None,
                       tags: List[str] = None,
                       urgency: UrgencyLevel = UrgencyLevel.MEDIUM,
                       need_by_days: Optional[int] = None,
                       expires_days: int = 30) -> AssetRequest:
        request = AssetRequest(
            request_id=self._generate_request_id(),
            requester_department_id=requester_department_id,
            requester_user_id=requester_user_id,
            title=title,
            description=description,
            required_category=required_category,
            required_quantity=required_quantity,
            max_budget=max_budget,
            preferred_conditions=preferred_conditions or [AssetCondition.EXCELLENT, AssetCondition.GOOD],
            tags=tags or [],
            urgency=urgency,
            need_by_date=datetime.utcnow() + timedelta(days=need_by_days) if need_by_days else None,
            expires_at=datetime.utcnow() + timedelta(days=expires_days)
        )
        
        self.requests[request.request_id] = request
        
        self._run_matching_for_request(request)
        
        return request
    
    def _run_matching_for_listing(self, listing: AssetListing):
        active_requests = [
            r for r in self.requests.values() 
            if r.status == RequestStatus.OPEN
            and r.requester_department_id != listing.owner_department_id
        ]
        
        matches = self.matching_algorithm.find_matches(
            listing, active_requests, min_score=0.5
        )
        
        for request, score, scores in matches[:5]:
            existing_match = self._find_existing_match(listing.listing_id, request.request_id)
            if existing_match:
                continue
            
            match = AssetMatch(
                match_id=self._generate_match_id(),
                listing_id=listing.listing_id,
                request_id=request.request_id,
                listing=listing,
                request=request,
                overall_score=score,
                category_match_score=scores['category'],
                condition_match_score=scores['condition'],
                value_match_score=scores['value'],
                quantity_match_score=scores['quantity'],
                urgency_match_score=scores['urgency'],
                tag_match_score=scores['tags'],
                matched_quantity=min(listing.available_quantity, request.required_quantity),
                matched_value=min(listing.available_quantity, request.required_quantity) * listing.suggested_transfer_value,
                status=MatchStatus.PENDING
            )
            
            self.matches[match.match_id] = match
            listing.match_count += 1
            request.match_count += 1
    
    def _run_matching_for_request(self, request: AssetRequest):
        active_listings = [
            l for l in self.listings.values()
            if l.status == ListingStatus.ACTIVE
            and l.owner_department_id != request.requester_department_id
        ]
        
        matches = self.matching_algorithm.find_listings_for_request(
            request, active_listings, min_score=0.5
        )
        
        for listing, score, scores in matches[:5]:
            existing_match = self._find_existing_match(listing.listing_id, request.request_id)
            if existing_match:
                continue
            
            match = AssetMatch(
                match_id=self._generate_match_id(),
                listing_id=listing.listing_id,
                request_id=request.request_id,
                listing=listing,
                request=request,
                overall_score=score,
                category_match_score=scores['category'],
                condition_match_score=scores['condition'],
                value_match_score=scores['value'],
                quantity_match_score=scores['quantity'],
                urgency_match_score=scores['urgency'],
                tag_match_score=scores['tags'],
                matched_quantity=min(listing.available_quantity, request.required_quantity),
                matched_value=min(listing.available_quantity, request.required_quantity) * listing.suggested_transfer_value,
                status=MatchStatus.PENDING
            )
            
            self.matches[match.match_id] = match
            listing.match_count += 1
            request.match_count += 1
    
    def _find_existing_match(self, listing_id: str, request_id: str) -> Optional[AssetMatch]:
        for match in self.matches.values():
            if match.listing_id == listing_id and match.request_id == request_id:
                return match
        return None
    
    def propose_match(self, match_id: str, proposer_id: int) -> Tuple[bool, str, Optional[AssetMatch]]:
        match = self.matches.get(match_id)
        if not match:
            return False, "匹配不存在", None
        
        if match.status != MatchStatus.PENDING:
            return False, f"匹配状态不是待处理: {match.status.value}", None
        
        match.status = MatchStatus.PROPOSED
        match.proposed_at = datetime.utcnow()
        
        listing = self.listings.get(match.listing_id)
        request = self.requests.get(match.request_id)
        
        if listing:
            listing.status = ListingStatus.PENDING
        if request:
            request.status = RequestStatus.MATCHED
        
        return True, "匹配已提议", match
    
    def accept_match(self, match_id: str, acceptor_id: int) -> Tuple[bool, str, Optional[AssetTransferProposal]]:
        match = self.matches.get(match_id)
        if not match:
            return False, "匹配不存在", None
        
        if match.status not in [MatchStatus.PROPOSED, MatchStatus.PENDING]:
            return False, f"匹配状态不允许接受: {match.status.value}", None
        
        match.status = MatchStatus.ACCEPTED
        match.accepted_at = datetime.utcnow()
        
        listing = self.listings.get(match.listing_id)
        request = self.requests.get(match.request_id)
        
        if listing and request:
            proposal = AssetTransferProposal(
                proposal_id=self._generate_proposal_id(),
                match_id=match.match_id,
                listing_id=match.listing_id,
                request_id=match.request_id,
                from_department_id=listing.owner_department_id,
                to_department_id=request.requester_department_id,
                asset_id=listing.asset_id,
                quantity=match.matched_quantity,
                transfer_value=match.matched_value
            )
            
            self.proposals[proposal.proposal_id] = proposal
            listing.status = ListingStatus.RESERVED
            request.status = RequestStatus.RESERVED
            
            return True, "匹配已接受，已生成转让提议", proposal
        
        return False, "关联的挂牌或请求不存在", None
    
    def reject_match(self, match_id: str, rejector_id: int, reason: str) -> Tuple[bool, str]:
        match = self.matches.get(match_id)
        if not match:
            return False, "匹配不存在"
        
        match.status = MatchStatus.REJECTED
        match.rejected_at = datetime.utcnow()
        match.rejection_reason = reason
        
        listing = self.listings.get(match.listing_id)
        request = self.requests.get(match.request_id)
        
        if listing:
            listing.status = ListingStatus.ACTIVE
        if request:
            request.status = RequestStatus.OPEN
        
        return True, "匹配已拒绝"
    
    def get_matches_for_listing(self, listing_id: str) -> List[AssetMatch]:
        return [
            m for m in self.matches.values()
            if m.listing_id == listing_id
        ]
    
    def get_matches_for_request(self, request_id: str) -> List[AssetMatch]:
        return [
            m for m in self.matches.values()
            if m.request_id == request_id
        ]
    
    def get_active_listings(self, department_id: Optional[int] = None) -> List[AssetListing]:
        listings = [
            l for l in self.listings.values()
            if l.status == ListingStatus.ACTIVE
        ]
        
        if department_id:
            listings = [l for l in listings if l.owner_department_id == department_id]
        
        return listings
    
    def get_active_requests(self, department_id: Optional[int] = None) -> List[AssetRequest]:
        requests = [
            r for r in self.requests.values()
            if r.status == RequestStatus.OPEN
        ]
        
        if department_id:
            requests = [r for r in requests if r.requester_department_id == department_id]
        
        return requests
    
    def get_marketplace_stats(self) -> Dict[str, Any]:
        total_listings = len(self.listings)
        active_listings = sum(1 for l in self.listings.values() if l.status == ListingStatus.ACTIVE)
        pending_listings = sum(1 for l in self.listings.values() if l.status == ListingStatus.PENDING)
        
        total_requests = len(self.requests)
        open_requests = sum(1 for r in self.requests.values() if r.status == RequestStatus.OPEN)
        matched_requests = sum(1 for r in self.requests.values() if r.status == RequestStatus.MATCHED)
        
        total_matches = len(self.matches)
        pending_matches = sum(1 for m in self.matches.values() if m.status == MatchStatus.PENDING)
        proposed_matches = sum(1 for m in self.matches.values() if m.status == MatchStatus.PROPOSED)
        completed_matches = sum(1 for m in self.matches.values() if m.status == MatchStatus.COMPLETED)
        
        total_value = sum(
            l.suggested_transfer_value * l.available_quantity
            for l in self.listings.values()
            if l.status == ListingStatus.ACTIVE
        )
        
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
            'marketplace_value': round(total_value, 2),
            'generated_at': datetime.utcnow().isoformat()
        }
