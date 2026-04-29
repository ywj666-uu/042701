from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List, Callable
from queue import Queue
import threading
import json
from app import db
from app.models import Supplier


class EventType(Enum):
    PURCHASE_APPROVED = 'purchase_approved'
    PURCHASE_REJECTED = 'purchase_rejected'
    PURCHASE_SUBMITTED = 'purchase_submitted'
    
    ASSET_BORROW_APPROVED = 'asset_borrow_approved'
    ASSET_RETURNED = 'asset_returned'
    
    MAINTENANCE_SCHEDULED = 'maintenance_scheduled'
    MAINTENANCE_COMPLETED = 'maintenance_completed'
    
    INVENTORY_COMPLETED = 'inventory_completed'
    INVENTORY_RESULT_APPROVED = 'inventory_result_approved'
    
    BUDGET_ALLOCATED = 'budget_allocated'
    BUDGET_WARNING = 'budget_warning'
    
    NOTIFICATION_SEND = 'notification_send'
    
    MATCH_TASK_CREATED = 'match_task_created'
    MATCH_TASK_COMPLETED = 'match_task_completed'
    MATCH_TASK_FAILED = 'match_task_failed'
    
    LISTING_CREATED = 'listing_created'
    LISTING_EXPIRED = 'listing_expired'
    LISTING_TRANSFERRED = 'listing_transferred'
    
    REQUEST_CREATED = 'request_created'
    REQUEST_FULFILLED = 'request_fulfilled'
    REQUEST_EXPIRED = 'request_expired'
    
    MATCH_PROPOSED = 'match_proposed'
    MATCH_ACCEPTED = 'match_accepted'
    MATCH_REJECTED = 'match_rejected'
    MATCH_COMPLETED = 'match_completed'
    
    TRANSFER_PROPOSAL_APPROVED = 'transfer_proposal_approved'
    TRANSFER_PROPOSAL_REJECTED = 'transfer_proposal_rejected'
    ASSET_TRANSFER_COMPLETED = 'asset_transfer_completed'


class EventPriority(Enum):
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'


class Event:
    def __init__(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        priority: EventPriority = EventPriority.MEDIUM,
        source: str = 'system'
    ):
        self.event_type = event_type
        self.data = data
        self.priority = priority
        self.source = source
        self.created_at = datetime.utcnow()
        self.event_id = f"{event_type.value}_{int(self.created_at.timestamp() * 1000000)}"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'data': self.data,
            'priority': self.priority.value,
            'source': self.source,
            'created_at': self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        return cls(
            event_type=EventType(data['event_type']),
            data=data['data'],
            priority=EventPriority(data.get('priority', 'medium')),
            source=data.get('source', 'system')
        )


class EventHandler:
    def __init__(self, handler_func: Callable, event_types: List[EventType] = None):
        self.handler_func = handler_func
        self.event_types = event_types or []
    
    def can_handle(self, event: Event) -> bool:
        if not self.event_types:
            return True
        return event.event_type in self.event_types
    
    def handle(self, event: Event) -> Any:
        return self.handler_func(event)


class EventService:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._handlers: List[EventHandler] = []
        self._event_queue: Queue = Queue()
        self._running = False
        self._worker_thread: Optional[threading.Thread] = None
        self._initialized = True
    
    def register_handler(
        self, 
        handler_func: Callable, 
        event_types: List[EventType] = None
    ) -> EventHandler:
        handler = EventHandler(handler_func, event_types)
        self._handlers.append(handler)
        return handler
    
    def unregister_handler(self, handler: EventHandler):
        if handler in self._handlers:
            self._handlers.remove(handler)
    
    def publish(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        priority: EventPriority = EventPriority.MEDIUM,
        source: str = 'system'
    ) -> Event:
        event = Event(event_type, data, priority, source)
        
        if priority == EventPriority.HIGH:
            self._process_event(event)
        else:
            self._event_queue.put(event)
        
        return event
    
    def publish_async(
        self,
        event_type: EventType,
        data: Dict[str, Any],
        priority: EventPriority = EventPriority.MEDIUM,
        source: str = 'system'
    ) -> Event:
        event = Event(event_type, data, priority, source)
        self._event_queue.put(event)
        return event
    
    def _process_event(self, event: Event):
        for handler in self._handlers:
            if handler.can_handle(event):
                try:
                    handler.handle(event)
                except Exception as e:
                    print(f"Error handling event {event.event_id}: {e}")
    
    def start_worker(self):
        if self._running:
            return
        
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()
    
    def stop_worker(self):
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=5.0)
    
    def _worker_loop(self):
        while self._running:
            try:
                event = self._event_queue.get(timeout=1.0)
                if event:
                    self._process_event(event)
                    self._event_queue.task_done()
            except Exception:
                continue
    
    def get_queue_size(self) -> int:
        return self._event_queue.qsize()


def update_supplier_statistics_handler(event: Event):
    if event.event_type != EventType.PURCHASE_APPROVED:
        return
    
    purchase_request_id = event.data.get('purchase_request_id')
    supplier_id = event.data.get('supplier_id')
    total_amount = event.data.get('total_amount', 0.0)
    
    if not supplier_id:
        return
    
    try:
        supplier = Supplier.query.get(supplier_id)
        if supplier:
            supplier.total_orders = (supplier.total_orders or 0) + 1
            supplier.total_amount = (supplier.total_amount or 0) + total_amount
            db.session.commit()
            print(f"Updated supplier statistics for supplier {supplier_id}: "
                  f"orders={supplier.total_orders}, amount={supplier.total_amount}")
    except Exception as e:
        print(f"Error updating supplier statistics: {e}")
        db.session.rollback()


event_service = EventService()

event_service.register_handler(
    update_supplier_statistics_handler,
    [EventType.PURCHASE_APPROVED]
)
