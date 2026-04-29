from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import math
import statistics
from collections import defaultdict
from app import db


class FailureRiskLevel(Enum):
    CRITICAL = 'critical'
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'
    NEGLIGIBLE = 'negligible'


class MaintenancePriority(Enum):
    P0 = 'p0'
    P1 = 'p1'
    P2 = 'p2'
    P3 = 'p3'


@dataclass
class MaintenanceFeature:
    feature_name: str
    feature_value: float
    feature_type: str
    importance: float = 0.0
    description: str = ''


@dataclass
class DeviceHealthScore:
    asset_id: int
    overall_score: float
    sub_scores: Dict[str, float]
    risk_level: FailureRiskLevel
    last_updated: datetime
    factors: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class FailurePrediction:
    prediction_id: str
    asset_id: int
    failure_type: str
    failure_risk: float
    risk_level: FailureRiskLevel
    predicted_days_to_failure: int
    confidence: float
    features_contribution: Dict[str, float]
    created_at: datetime
    is_acknowledged: bool = False
    acknowledged_by: Optional[int] = None
    acknowledged_at: Optional[datetime] = None


@dataclass
class MaintenanceWorkOrder:
    order_id: str
    asset_id: int
    prediction_id: Optional[str]
    work_order_type: str
    priority: MaintenancePriority
    title: str
    description: str
    scheduled_date: Optional[datetime]
    due_date: Optional[datetime]
    estimated_duration_hours: float
    status: str
    assigned_to: Optional[int]
    created_at: datetime
    completed_at: Optional[datetime] = None
    cost_estimate: Optional[float] = None
    actual_cost: Optional[float] = None
    notes: List[str] = field(default_factory=list)


class MaintenanceModel:
    def __init__(self):
        self.model_version = '1.0.0'
        self.model_type = 'rule_based_ensemble'
        self.feature_weights = self._get_feature_weights()
        self.failure_patterns = self._get_failure_patterns()
    
    def _get_feature_weights(self) -> Dict[str, float]:
        return {
            'age_factor': 0.25,
            'usage_hours_factor': 0.20,
            'maintenance_frequency_factor': 0.15,
            'last_maintenance_days_factor': 0.15,
            'failure_history_factor': 0.15,
            'sensor_anomaly_factor': 0.10
        }
    
    def _get_failure_patterns(self) -> Dict[str, Dict[str, Any]]:
        return {
            'hardware_failure': {
                'trigger_threshold': 0.75,
                'average_days_to_failure': 14,
                'confidence_base': 0.85,
                'key_features': ['age_factor', 'usage_hours_factor', 'failure_history_factor']
            },
            'component_degradation': {
                'trigger_threshold': 0.60,
                'average_days_to_failure': 30,
                'confidence_base': 0.70,
                'key_features': ['age_factor', 'last_maintenance_days_factor', 'maintenance_frequency_factor']
            },
            'calibration_needed': {
                'trigger_threshold': 0.50,
                'average_days_to_failure': 60,
                'confidence_base': 0.60,
                'key_features': ['last_maintenance_days_factor', 'sensor_anomaly_factor']
            },
            'preventive_maintenance_due': {
                'trigger_threshold': 0.40,
                'average_days_to_failure': 90,
                'confidence_base': 0.90,
                'key_features': ['last_maintenance_days_factor', 'usage_hours_factor']
            }
        }
    
    def calculate_risk_score(self, features: Dict[str, float]) -> float:
        total_score = 0.0
        total_weight = 0.0
        
        for feature_name, weight in self.feature_weights.items():
            if feature_name in features:
                total_score += features[feature_name] * weight
                total_weight += weight
        
        if total_weight > 0:
            return total_score / total_weight
        return 0.0
    
    def determine_risk_level(self, risk_score: float) -> FailureRiskLevel:
        if risk_score >= 0.8:
            return FailureRiskLevel.CRITICAL
        elif risk_score >= 0.6:
            return FailureRiskLevel.HIGH
        elif risk_score >= 0.4:
            return FailureRiskLevel.MEDIUM
        elif risk_score >= 0.2:
            return FailureRiskLevel.LOW
        else:
            return FailureRiskLevel.NEGLIGIBLE
    
    def predict_failure(self, features: Dict[str, float], asset_id: int) -> List[FailurePrediction]:
        predictions = []
        risk_score = self.calculate_risk_score(features)
        
        for failure_type, pattern in self.failure_patterns.items():
            key_feature_scores = [
                features.get(f, 0) 
                for f in pattern['key_features']
                if f in features
            ]
            
            if not key_feature_scores:
                continue
            
            avg_key_score = statistics.mean(key_feature_scores)
            trigger_threshold = pattern['trigger_threshold']
            
            if avg_key_score >= trigger_threshold * 0.8:
                confidence = pattern['confidence_base'] * (
                    0.5 + 0.5 * min(1.0, avg_key_score / trigger_threshold)
                )
                
                days_adjustment = int(
                    pattern['average_days_to_failure'] * 
                    (1.0 - 0.5 * max(0, avg_key_score - trigger_threshold))
                )
                
                prediction = FailurePrediction(
                    prediction_id=f"FP_{asset_id}_{int(datetime.now().timestamp())}_{failure_type[:4]}",
                    asset_id=asset_id,
                    failure_type=failure_type,
                    failure_risk=avg_key_score,
                    risk_level=self.determine_risk_level(avg_key_score),
                    predicted_days_to_failure=max(1, days_adjustment),
                    confidence=round(confidence, 4),
                    features_contribution={
                        f: features.get(f, 0) 
                        for f in pattern['key_features']
                    },
                    created_at=datetime.utcnow()
                )
                
                predictions.append(prediction)
        
        predictions.sort(key=lambda x: (x.risk_level.value, -x.confidence))
        return predictions
    
    def calculate_health_score(self, features: Dict[str, float], asset_id: int) -> DeviceHealthScore:
        risk_score = self.calculate_risk_score(features)
        health_score = 100 * (1 - risk_score)
        
        sub_scores = {}
        for feature_name, value in features.items():
            sub_scores[feature_name] = 100 * (1 - value)
        
        risk_level = self.determine_risk_level(risk_score)
        
        factors = []
        recommendations = []
        
        if features.get('age_factor', 0) > 0.6:
            factors.append("设备老化程度高")
            recommendations.append("建议评估设备更新必要性")
        
        if features.get('usage_hours_factor', 0) > 0.5:
            factors.append("使用强度高")
            recommendations.append("考虑增加维护频率")
        
        if features.get('last_maintenance_days_factor', 0) > 0.4:
            factors.append("维护间隔过长")
            recommendations.append("建议尽快安排预防性维护")
        
        if features.get('failure_history_factor', 0) > 0.3:
            factors.append("历史故障率较高")
            recommendations.append("建议增加检测频次")
        
        return DeviceHealthScore(
            asset_id=asset_id,
            overall_score=round(health_score, 2),
            sub_scores={k: round(v, 2) for k, v in sub_scores.items()},
            risk_level=risk_level,
            last_updated=datetime.utcnow(),
            factors=factors,
            recommendations=recommendations
        )


class MaintenancePredictor:
    def __init__(self):
        self.model = MaintenanceModel()
    
    def extract_features_from_asset(self, asset, maintenance_history: List[Dict], 
                                    sensor_data: Optional[List[Dict]] = None) -> Dict[str, float]:
        features = {}
        
        if asset.warranty_period:
            purchase_age = (datetime.utcnow() - (asset.purchase_date or datetime.utcnow())).days
            warranty_days = asset.warranty_period * 365
            features['age_factor'] = min(1.0, purchase_age / max(warranty_days, 365))
        else:
            purchase_age = (datetime.utcnow() - (asset.purchase_date or datetime.utcnow())).days
            features['age_factor'] = min(1.0, purchase_age / (5 * 365))
        
        total_maintenance = len(maintenance_history)
        if total_maintenance > 0:
            last_maintenance = max(m.get('completed_at', datetime.utcnow()) for m in maintenance_history)
            days_since_maintenance = (datetime.utcnow() - last_maintenance).days
            features['last_maintenance_days_factor'] = min(1.0, days_since_maintenance / 180)
            
            avg_interval = purchase_age / max(total_maintenance, 1)
            features['maintenance_frequency_factor'] = min(1.0, 180 / max(avg_interval, 30))
        else:
            features['last_maintenance_days_factor'] = min(1.0, purchase_age / 180)
            features['maintenance_frequency_factor'] = 0.0
        
        failure_count = sum(1 for m in maintenance_history if m.get('type') == 'repair')
        features['failure_history_factor'] = min(1.0, failure_count / max(total_maintenance, 1))
        
        if sensor_data:
            anomalies = sum(1 for s in sensor_data if s.get('is_anomaly', False))
            features['sensor_anomaly_factor'] = min(1.0, anomalies / max(len(sensor_data), 1))
        else:
            features['sensor_anomaly_factor'] = 0.0
        
        features['usage_hours_factor'] = 0.3
        
        return features
    
    def predict_for_asset(self, asset, maintenance_history: List[Dict],
                           sensor_data: Optional[List[Dict]] = None) -> Tuple[List[FailurePrediction], DeviceHealthScore]:
        features = self.extract_features_from_asset(asset, maintenance_history, sensor_data)
        
        predictions = self.model.predict_failure(features, asset.id)
        
        health_score = self.model.calculate_health_score(features, asset.id)
        
        return predictions, health_score
    
    def generate_work_order(self, prediction: FailurePrediction, asset) -> MaintenanceWorkOrder:
        priority_map = {
            FailureRiskLevel.CRITICAL: MaintenancePriority.P0,
            FailureRiskLevel.HIGH: MaintenancePriority.P1,
            FailureRiskLevel.MEDIUM: MaintenancePriority.P2,
            FailureRiskLevel.LOW: MaintenancePriority.P3,
            FailureRiskLevel.NEGLIGIBLE: MaintenancePriority.P3
        }
        
        priority = priority_map.get(prediction.risk_level, MaintenancePriority.P3)
        
        scheduled_date = datetime.utcnow() + timedelta(
            days=min(prediction.predicted_days_to_failure // 2, 7)
        )
        due_date = datetime.utcnow() + timedelta(days=prediction.predicted_days_to_failure)
        
        type_descriptions = {
            'hardware_failure': '硬件故障预警',
            'component_degradation': '部件老化预警',
            'calibration_needed': '校准需求预警',
            'preventive_maintenance_due': '预防性维护到期'
        }
        
        return MaintenanceWorkOrder(
            order_id=f"WO_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            asset_id=asset.id,
            prediction_id=prediction.prediction_id,
            work_order_type=prediction.failure_type,
            priority=priority,
            title=f"{type_descriptions.get(prediction.failure_type, '维护需求')} - {asset.name}",
            description=f"根据预测性维护分析，设备 {asset.name} (编号: {asset.asset_code}) "
                       f"存在 {prediction.risk_level.value} 级别故障风险。\n"
                       f"预测故障类型: {prediction.failure_type}\n"
                       f"置信度: {prediction.confidence * 100:.1f}%\n"
                       f"预计故障时间: {prediction.predicted_days_to_failure} 天内",
            scheduled_date=scheduled_date,
            due_date=due_date,
            estimated_duration_hours=4.0,
            status='pending',
            assigned_to=None,
            created_at=datetime.utcnow()
        )


class PredictiveMaintenanceService:
    def __init__(self):
        self.predictor = MaintenancePredictor()
        self.active_predictions: Dict[int, List[FailurePrediction]] = defaultdict(list)
        self.active_work_orders: Dict[str, MaintenanceWorkOrder] = {}
    
    def analyze_asset(self, asset, maintenance_history: List[Dict],
                       sensor_data: Optional[List[Dict]] = None) -> Dict[str, Any]:
        predictions, health_score = self.predictor.predict_for_asset(
            asset, maintenance_history, sensor_data
        )
        
        self.active_predictions[asset.id] = predictions
        
        result = {
            'asset_id': asset.id,
            'asset_code': asset.asset_code,
            'asset_name': asset.name,
            'health_score': {
                'overall': health_score.overall_score,
                'sub_scores': health_score.sub_scores,
                'risk_level': health_score.risk_level.value,
                'factors': health_score.factors,
                'recommendations': health_score.recommendations
            },
            'predictions': [
                {
                    'prediction_id': p.prediction_id,
                    'failure_type': p.failure_type,
                    'failure_risk': p.failure_risk,
                    'risk_level': p.risk_level.value,
                    'predicted_days_to_failure': p.predicted_days_to_failure,
                    'confidence': p.confidence,
                    'features_contribution': p.features_contribution
                }
                for p in predictions
            ],
            'work_orders_generated': len([p for p in predictions if p.risk_level in [FailureRiskLevel.CRITICAL, FailureRiskLevel.HIGH]])
        }
        
        high_risk_predictions = [
            p for p in predictions 
            if p.risk_level in [FailureRiskLevel.CRITICAL, FailureRiskLevel.HIGH]
        ]
        
        for pred in high_risk_predictions:
            work_order = self.predictor.generate_work_order(pred, asset)
            self.active_work_orders[work_order.order_id] = work_order
            result.setdefault('work_orders', []).append({
                'order_id': work_order.order_id,
                'priority': work_order.priority.value,
                'title': work_order.title,
                'scheduled_date': work_order.scheduled_date.isoformat() if work_order.scheduled_date else None,
                'due_date': work_order.due_date.isoformat() if work_order.due_date else None
            })
        
        return result
    
    def get_work_order(self, order_id: str) -> Optional[MaintenanceWorkOrder]:
        return self.active_work_orders.get(order_id)
    
    def acknowledge_prediction(self, prediction_id: str, user_id: int) -> bool:
        for asset_id, predictions in self.active_predictions.items():
            for p in predictions:
                if p.prediction_id == prediction_id:
                    p.is_acknowledged = True
                    p.acknowledged_by = user_id
                    p.acknowledged_at = datetime.utcnow()
                    return True
        return False
    
    def get_high_risk_assets(self) -> List[Dict[str, Any]]:
        high_risk = []
        for asset_id, predictions in self.active_predictions.items():
            high_risk_preds = [
                p for p in predictions 
                if p.risk_level in [FailureRiskLevel.CRITICAL, FailureRiskLevel.HIGH]
                and not p.is_acknowledged
            ]
            if high_risk_preds:
                high_risk.append({
                    'asset_id': asset_id,
                    'predictions': [
                        {
                            'id': p.prediction_id,
                            'type': p.failure_type,
                            'risk_level': p.risk_level.value,
                            'days_to_failure': p.predicted_days_to_failure
                        }
                        for p in high_risk_preds
                    ]
                })
        return high_risk
    
    def generate_maintenance_plan(self, assets_data: List[Dict]) -> Dict[str, Any]:
        schedule = defaultdict(list)
        
        for asset_data in assets_data:
            asset = asset_data.get('asset')
            maintenance_history = asset_data.get('maintenance_history', [])
            sensor_data = asset_data.get('sensor_data')
            
            if asset:
                predictions, health_score = self.predictor.predict_for_asset(
                    asset, maintenance_history, sensor_data
                )
                
                if predictions:
                    earliest_prediction = min(
                        predictions, 
                        key=lambda p: (p.risk_level.value, p.predicted_days_to_failure)
                    )
                    
                    schedule_date = datetime.utcnow() + timedelta(
                        days=earliest_prediction.predicted_days_to_failure // 2
                    )
                    schedule_key = schedule_date.strftime('%Y-%U')
                    
                    schedule[schedule_key].append({
                        'asset_id': asset.id,
                        'asset_name': asset.name,
                        'asset_code': asset.asset_code,
                        'prediction_id': earliest_prediction.prediction_id,
                        'failure_type': earliest_prediction.failure_type,
                        'risk_level': earliest_prediction.risk_level.value,
                        'scheduled_date': schedule_date.isoformat(),
                        'priority': self._get_priority_from_risk(earliest_prediction.risk_level)
                    })
        
        return {
            'generated_at': datetime.utcnow().isoformat(),
            'total_assets_analyzed': len(assets_data),
            'maintenance_tasks': [
                {
                    'week': week,
                    'tasks': sorted(tasks, key=lambda x: x['priority'])
                }
                for week, tasks in sorted(schedule.items())
            ]
        }
    
    def _get_priority_from_risk(self, risk_level: FailureRiskLevel) -> int:
        priority_order = {
            FailureRiskLevel.CRITICAL: 0,
            FailureRiskLevel.HIGH: 1,
            FailureRiskLevel.MEDIUM: 2,
            FailureRiskLevel.LOW: 3,
            FailureRiskLevel.NEGLIGIBLE: 4
        }
        return priority_order.get(risk_level, 4)
