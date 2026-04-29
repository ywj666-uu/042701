from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import time
from collections import OrderedDict
from app import db


class TransactionType(Enum):
    ASSET_CREATION = 'asset_creation'
    ASSET_TRANSFER = 'asset_transfer'
    ASSET_BORROW = 'asset_borrow'
    ASSET_RETURN = 'asset_return'
    ASSET_DISPOSAL = 'asset_disposal'
    ASSET_MAINTENANCE = 'asset_maintenance'
    ASSET_INVENTORY = 'asset_inventory'
    PURCHASE_APPROVAL = 'purchase_approval'
    BUDGET_ALLOCATION = 'budget_allocation'


class VerificationStatus(Enum):
    PENDING = 'pending'
    VERIFIED = 'verified'
    INVALID = 'invalid'


@dataclass
class AssetTransaction:
    transaction_id: str
    transaction_type: TransactionType
    asset_id: int
    
    from_department_id: Optional[int] = None
    to_department_id: Optional[int] = None
    from_user_id: Optional[int] = None
    to_user_id: Optional[int] = None
    
    operator_id: int
    operator_name: str = ''
    
    transaction_date: datetime = field(default_factory=datetime.utcnow)
    
    previous_state: Dict[str, Any] = field(default_factory=dict)
    new_state: Dict[str, Any] = field(default_factory=dict)
    
    metadata: Dict[str, Any] = field(default_factory=dict)
    description: str = ''
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    block_hash: Optional[str] = None
    block_height: Optional[int] = None
    
    verification_status: VerificationStatus = VerificationStatus.PENDING
    verified_at: Optional[datetime] = None
    verified_by: Optional[int] = None
    
    def calculate_hash(self) -> str:
        transaction_data = OrderedDict({
            'transaction_id': self.transaction_id,
            'transaction_type': self.transaction_type.value,
            'asset_id': self.asset_id,
            'from_department_id': self.from_department_id,
            'to_department_id': self.to_department_id,
            'from_user_id': self.from_user_id,
            'to_user_id': self.to_user_id,
            'operator_id': self.operator_id,
            'transaction_date': self.transaction_date.isoformat() if self.transaction_date else None,
            'previous_state': self.previous_state,
            'new_state': self.new_state,
            'metadata': self.metadata,
            'description': self.description,
            'created_at': self.created_at.isoformat()
        })
        
        json_str = json.dumps(transaction_data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(json_str.encode('utf-8')).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'transaction_id': self.transaction_id,
            'transaction_type': self.transaction_type.value,
            'asset_id': self.asset_id,
            'from_department_id': self.from_department_id,
            'to_department_id': self.to_department_id,
            'from_user_id': self.from_user_id,
            'to_user_id': self.to_user_id,
            'operator_id': self.operator_id,
            'operator_name': self.operator_name,
            'transaction_date': self.transaction_date.isoformat(),
            'previous_state': self.previous_state,
            'new_state': self.new_state,
            'metadata': self.metadata,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'block_hash': self.block_hash,
            'block_height': self.block_height,
            'verification_status': self.verification_status.value,
            'hash': self.calculate_hash()
        }


@dataclass
class TransactionProof:
    proof_id: str
    transaction_id: str
    merkle_path: List[str]
    
    root_hash: str
    block_hash: str
    block_height: int
    
    generated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'proof_id': self.proof_id,
            'transaction_id': self.transaction_id,
            'merkle_path': self.merkle_path,
            'root_hash': self.root_hash,
            'block_hash': self.block_hash,
            'block_height': self.block_height,
            'generated_at': self.generated_at.isoformat()
        }


@dataclass
class MerkleTree:
    root_hash: str
    leaf_hashes: List[str]
    tree_structure: List[List[str]]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'root_hash': self.root_hash,
            'leaf_count': len(self.leaf_hashes),
            'tree_depth': len(self.tree_structure)
        }


@dataclass
class BlockchainNode:
    block_height: int
    block_hash: str
    previous_hash: str
    
    merkle_root: str
    transaction_count: int
    transactions: List[str]
    
    timestamp: float
    nonce: int = 0
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def calculate_block_hash(self) -> str:
        block_data = OrderedDict({
            'block_height': self.block_height,
            'previous_hash': self.previous_hash,
            'merkle_root': self.merkle_root,
            'transaction_count': self.transaction_count,
            'transactions': self.transactions,
            'timestamp': self.timestamp,
            'nonce': self.nonce
        })
        
        json_str = json.dumps(block_data, sort_keys=True)
        return hashlib.sha256(json_str.encode('utf-8')).hexdigest()
    
    def mine_block(self, difficulty: int = 4) -> int:
        target = '0' * difficulty
        self.nonce = 0
        
        while True:
            hash_result = self.calculate_block_hash()
            if hash_result.startswith(target):
                self.block_hash = hash_result
                return self.nonce
            self.nonce += 1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'block_height': self.block_height,
            'block_hash': self.block_hash,
            'previous_hash': self.previous_hash,
            'merkle_root': self.merkle_root,
            'transaction_count': self.transaction_count,
            'timestamp': self.timestamp,
            'nonce': self.nonce,
            'created_at': self.created_at.isoformat()
        }


class BlockchainService:
    def __init__(self, difficulty: int = 2, block_size: int = 10):
        self.difficulty = difficulty
        self.block_size = block_size
        
        self.chain: List[BlockchainNode] = []
        self.pending_transactions: List[AssetTransaction] = []
        
        self.transactions: Dict[str, AssetTransaction] = {}
        self.proofs: Dict[str, TransactionProof] = {}
        
        self.transaction_counter = 0
        self.proof_counter = 0
        
        self._create_genesis_block()
    
    def _create_genesis_block(self):
        genesis_block = BlockchainNode(
            block_height=0,
            block_hash='0',
            previous_hash='0',
            merkle_root='0',
            transaction_count=0,
            transactions=[],
            timestamp=time.time()
        )
        genesis_block.block_hash = genesis_block.calculate_block_hash()
        self.chain.append(genesis_block)
    
    def _generate_transaction_id(self) -> str:
        self.transaction_counter += 1
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        return f"TX-{timestamp}-{self.transaction_counter:08d}"
    
    def _generate_proof_id(self) -> str:
        self.proof_counter += 1
        return f"PRF-{datetime.now().strftime('%Y%m%d%H%M%S')}-{self.proof_counter:06d}"
    
    def _build_merkle_tree(self, transaction_hashes: List[str]) -> MerkleTree:
        if not transaction_hashes:
            return MerkleTree(
                root_hash='0',
                leaf_hashes=[],
                tree_structure=[]
            )
        
        leaf_hashes = sorted(transaction_hashes)
        tree_structure = [leaf_hashes.copy()]
        
        current_level = leaf_hashes
        while len(current_level) > 1:
            next_level = []
            
            for i in range(0, len(current_level), 2):
                left = current_level[i]
                right = current_level[i + 1] if i + 1 < len(current_level) else left
                
                combined = left + right
                hash_result = hashlib.sha256(combined.encode('utf-8')).hexdigest()
                next_level.append(hash_result)
            
            tree_structure.append(next_level)
            current_level = next_level
        
        return MerkleTree(
            root_hash=current_level[0] if current_level else '0',
            leaf_hashes=leaf_hashes,
            tree_structure=tree_structure
        )
    
    def _get_merkle_path(self, merkle_tree: MerkleTree, leaf_hash: str) -> List[str]:
        path = []
        
        if leaf_hash not in merkle_tree.leaf_hashes:
            return path
        
        current_index = merkle_tree.leaf_hashes.index(leaf_hash)
        
        for level in range(len(merkle_tree.tree_structure) - 1):
            current_level = merkle_tree.tree_structure[level]
            
            is_left = current_index % 2 == 0
            sibling_index = current_index + 1 if is_left else current_index - 1
            
            if sibling_index < len(current_level):
                path.append({
                    'hash': current_level[sibling_index],
                    'position': 'right' if is_left else 'left'
                })
            
            current_index = current_index // 2
        
        return [p['hash'] for p in path]
    
    def create_transaction(self,
                          transaction_type: TransactionType,
                          asset_id: int,
                          operator_id: int,
                          operator_name: str = '',
                          from_department_id: Optional[int] = None,
                          to_department_id: Optional[int] = None,
                          from_user_id: Optional[int] = None,
                          to_user_id: Optional[int] = None,
                          previous_state: Dict[str, Any] = None,
                          new_state: Dict[str, Any] = None,
                          metadata: Dict[str, Any] = None,
                          description: str = '') -> AssetTransaction:
        transaction = AssetTransaction(
            transaction_id=self._generate_transaction_id(),
            transaction_type=transaction_type,
            asset_id=asset_id,
            from_department_id=from_department_id,
            to_department_id=to_department_id,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            operator_id=operator_id,
            operator_name=operator_name,
            previous_state=previous_state or {},
            new_state=new_state or {},
            metadata=metadata or {},
            description=description
        )
        
        self.transactions[transaction.transaction_id] = transaction
        self.pending_transactions.append(transaction)
        
        if len(self.pending_transactions) >= self.block_size:
            self.mine_block()
        
        return transaction
    
    def mine_block(self) -> Optional[BlockchainNode]:
        if not self.pending_transactions:
            return None
        
        transaction_hashes = [
            tx.calculate_hash()
            for tx in self.pending_transactions
        ]
        
        merkle_tree = self._build_merkle_tree(transaction_hashes)
        
        previous_block = self.chain[-1]
        
        new_block = BlockchainNode(
            block_height=len(self.chain),
            block_hash='',
            previous_hash=previous_block.block_hash,
            merkle_root=merkle_tree.root_hash,
            transaction_count=len(self.pending_transactions),
            transactions=transaction_hashes,
            timestamp=time.time()
        )
        
        new_block.mine_block(difficulty=self.difficulty)
        
        for tx in self.pending_transactions:
            tx.block_hash = new_block.block_hash
            tx.block_height = new_block.block_height
            tx.verification_status = VerificationStatus.VERIFIED
            tx.verified_at = datetime.utcnow()
        
        self.chain.append(new_block)
        self.pending_transactions = []
        
        return new_block
    
    def get_transaction(self, transaction_id: str) -> Optional[AssetTransaction]:
        return self.transactions.get(transaction_id)
    
    def get_transactions_for_asset(self, asset_id: int) -> List[AssetTransaction]:
        return [
            tx for tx in self.transactions.values()
            if tx.asset_id == asset_id
        ]
    
    def get_transactions_by_type(self, transaction_type: TransactionType) -> List[AssetTransaction]:
        return [
            tx for tx in self.transactions.values()
            if tx.transaction_type == transaction_type
        ]
    
    def generate_proof(self, transaction_id: str) -> Optional[TransactionProof]:
        transaction = self.transactions.get(transaction_id)
        if not transaction:
            return None
        
        if not transaction.block_hash:
            return None
        
        tx_hash = transaction.calculate_hash()
        
        for block in self.chain:
            if block.block_hash == transaction.block_hash:
                transaction_hashes = block.transactions
                merkle_tree = self._build_merkle_tree(transaction_hashes)
                
                merkle_path = self._get_merkle_path(merkle_tree, tx_hash)
                
                proof = TransactionProof(
                    proof_id=self._generate_proof_id(),
                    transaction_id=transaction_id,
                    merkle_path=merkle_path,
                    root_hash=merkle_tree.root_hash,
                    block_hash=block.block_hash,
                    block_height=block.block_height
                )
                
                self.proofs[proof.proof_id] = proof
                return proof
        
        return None
    
    def verify_transaction(self, transaction_id: str) -> Tuple[bool, str]:
        transaction = self.transactions.get(transaction_id)
        if not transaction:
            return False, "交易不存在"
        
        if transaction.verification_status == VerificationStatus.VERIFIED:
            return True, "交易已验证"
        
        if not transaction.block_hash:
            return False, "交易尚未上链"
        
        for block in self.chain:
            if block.block_hash == transaction.block_hash:
                recalculated_hash = transaction.calculate_hash()
                
                if recalculated_hash in block.transactions:
                    transaction.verification_status = VerificationStatus.VERIFIED
                    transaction.verified_at = datetime.utcnow()
                    return True, "交易验证通过"
                else:
                    transaction.verification_status = VerificationStatus.INVALID
                    return False, "交易哈希不匹配，可能被篡改"
        
        return False, "未找到对应的区块"
    
    def verify_chain(self) -> Tuple[bool, str]:
        for i in range(1, len(self.chain)):
            current_block = self.chain[i]
            previous_block = self.chain[i - 1]
            
            if current_block.previous_hash != previous_block.block_hash:
                return False, f"区块 {i} 的前区块哈希不匹配"
            
            if current_block.block_hash != current_block.calculate_block_hash():
                return False, f"区块 {i} 的哈希无效"
        
        return True, "区块链完整有效"
    
    def get_latest_block(self) -> BlockchainNode:
        return self.chain[-1]
    
    def get_block_by_height(self, height: int) -> Optional[BlockchainNode]:
        if 0 <= height < len(self.chain):
            return self.chain[height]
        return None
    
    def get_chain_stats(self) -> Dict[str, Any]:
        return {
            'chain_length': len(self.chain),
            'total_transactions': len(self.transactions),
            'pending_transactions': len(self.pending_transactions),
            'latest_block': {
                'height': self.get_latest_block().block_height,
                'hash': self.get_latest_block().block_hash,
                'timestamp': self.get_latest_block().created_at.isoformat()
            },
            'difficulty': self.difficulty,
            'generated_at': datetime.utcnow().isoformat()
        }
    
    def create_asset_transfer_transaction(self,
                                           asset_id: int,
                                           operator_id: int,
                                           operator_name: str,
                                           from_department_id: int,
                                           to_department_id: int,
                                           from_user_id: Optional[int] = None,
                                           to_user_id: Optional[int] = None,
                                           previous_state: Dict[str, Any] = None,
                                           new_state: Dict[str, Any] = None,
                                           description: str = '') -> AssetTransaction:
        return self.create_transaction(
            transaction_type=TransactionType.ASSET_TRANSFER,
            asset_id=asset_id,
            operator_id=operator_id,
            operator_name=operator_name,
            from_department_id=from_department_id,
            to_department_id=to_department_id,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            previous_state=previous_state,
            new_state=new_state,
            description=description or f"资产从部门 {from_department_id} 调拨到部门 {to_department_id}"
        )
    
    def create_asset_borrow_transaction(self,
                                         asset_id: int,
                                         operator_id: int,
                                         operator_name: str,
                                         from_user_id: int,
                                         to_user_id: int,
                                         previous_state: Dict[str, Any] = None,
                                         new_state: Dict[str, Any] = None,
                                         description: str = '') -> AssetTransaction:
        return self.create_transaction(
            transaction_type=TransactionType.ASSET_BORROW,
            asset_id=asset_id,
            operator_id=operator_id,
            operator_name=operator_name,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            previous_state=previous_state,
            new_state=new_state,
            description=description or f"用户 {from_user_id} 将资产借给用户 {to_user_id}"
        )
    
    def create_asset_disposal_transaction(self,
                                           asset_id: int,
                                           operator_id: int,
                                           operator_name: str,
                                           previous_state: Dict[str, Any] = None,
                                           new_state: Dict[str, Any] = None,
                                           description: str = '') -> AssetTransaction:
        return self.create_transaction(
            transaction_type=TransactionType.ASSET_DISPOSAL,
            asset_id=asset_id,
            operator_id=operator_id,
            operator_name=operator_name,
            previous_state=previous_state,
            new_state=new_state,
            description=description or "资产处置"
        )
    
    def get_asset_history(self, asset_id: int) -> List[Dict[str, Any]]:
        transactions = self.get_transactions_for_asset(asset_id)
        transactions.sort(key=lambda x: x.created_at)
        
        return [
            {
                'transaction_id': tx.transaction_id,
                'type': tx.transaction_type.value,
                'from_department': tx.from_department_id,
                'to_department': tx.to_department_id,
                'from_user': tx.from_user_id,
                'to_user': tx.to_user_id,
                'operator': tx.operator_name,
                'timestamp': tx.created_at.isoformat(),
                'block_hash': tx.block_hash,
                'verified': tx.verification_status == VerificationStatus.VERIFIED
            }
            for tx in transactions
        ]
