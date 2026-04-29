from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import json
import hashlib
import statistics
from collections import defaultdict, deque
from app import db


class DeviceStatus(Enum):
    ONLINE = 'online'
    OFFLINE = 'offline'
    MAINTENANCE = 'maintenance'
    ERROR = 'error'
    UNKNOWN = 'unknown'


class SensorType(Enum):
    TEMPERATURE = 'temperature'
    HUMIDITY = 'humidity'
    VIBRATION = 'vibration'
    CURRENT = 'current'
    VOLTAGE = 'voltage'
    POWER = 'power'
    RUN_TIME = 'run_time'
    LOCATION = 'location'
    RFID = 'rfid'
    QR_SCANNER = 'qr_scanner'


class AlertSeverity(Enum):
    CRITICAL = 'critical'
    WARNING = 'warning'
    INFO = 'info'


class AlertStatus(Enum):
    ACTIVE = 'active'
    ACKNOWLEDGED = 'acknowledged'
    RESOLVED = 'resolved'


class InventoryStatus(Enum):
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'


@dataclass
class IoTGateway:
    gateway_id: str
    name: str
    location: str
    ip_address: str
    mac_address: str
    
    status: DeviceStatus = DeviceStatus.OFFLINE
    last_heartbeat: Optional[datetime] = None
    
    connected_devices: List[str] = field(default_factory=list)
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    config: Dict[str, Any] = field(default_factory=dict)
    notes: str = ''
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'gateway_id': self.gateway_id,
            'name': self.name,
            'location': self.location,
            'ip_address': self.ip_address,
            'mac_address': self.mac_address,
            'status': self.status.value,
            'last_heartbeat': self.last_heartbeat.isoformat() if self.last_heartbeat else None,
            'connected_devices_count': len(self.connected_devices),
            'created_at': self.created_at.isoformat()
        }


@dataclass
class IoTDevice:
    device_id: str
    name: str
    device_type: str
    asset_id: Optional[int] = None
    
    gateway_id: Optional[str] = None
    location: str = ''
    
    status: DeviceStatus = DeviceStatus.UNKNOWN
    last_seen: Optional[datetime] = None
    
    manufacturer: str = ''
    model: str = ''
    serial_number: str = ''
    firmware_version: str = ''
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    config: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'device_id': self.device_id,
            'name': self.name,
            'device_type': self.device_type,
            'asset_id': self.asset_id,
            'gateway_id': self.gateway_id,
            'location': self.location,
            'status': self.status.value,
            'last_seen': self.last_seen.isoformat() if self.last_seen else None,
            'manufacturer': self.manufacturer,
            'model': self.model,
            'firmware_version': self.firmware_version,
            'created_at': self.created_at.isoformat()
        }


@dataclass
class DeviceSensor:
    sensor_id: str
    device_id: str
    sensor_type: SensorType
    
    name: str = ''
    unit: str = ''
    
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    warning_threshold: Optional[float] = None
    critical_threshold: Optional[float] = None
    
    is_active: bool = True
    last_reading: Optional[float] = None
    last_reading_at: Optional[datetime] = None
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    config: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'sensor_id': self.sensor_id,
            'device_id': self.device_id,
            'sensor_type': self.sensor_type.value,
            'name': self.name,
            'unit': self.unit,
            'min_value': self.min_value,
            'max_value': self.max_value,
            'warning_threshold': self.warning_threshold,
            'critical_threshold': self.critical_threshold,
            'is_active': self.is_active,
            'last_reading': self.last_reading,
            'last_reading_at': self.last_reading_at.isoformat() if self.last_reading_at else None
        }


@dataclass
class SensorReading:
    reading_id: str
    sensor_id: str
    device_id: str
    
    value: float
    raw_value: Optional[str] = None
    
    reading_at: datetime = field(default_factory=datetime.utcnow)
    received_at: datetime = field(default_factory=datetime.utcnow)
    
    is_anomaly: bool = False
    anomaly_score: float = 0.0
    
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    
    meta: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'reading_id': self.reading_id,
            'sensor_id': self.sensor_id,
            'device_id': self.device_id,
            'value': self.value,
            'raw_value': self.raw_value,
            'reading_at': self.reading_at.isoformat(),
            'received_at': self.received_at.isoformat(),
            'is_anomaly': self.is_anomaly,
            'anomaly_score': self.anomaly_score,
            'location': {
                'lat': self.location_lat,
                'lng': self.location_lng
            } if self.location_lat and self.location_lng else None
        }


@dataclass
class DeviceAlert:
    alert_id: str
    device_id: str
    sensor_id: Optional[str]
    
    severity: AlertSeverity
    title: str
    message: str
    
    status: AlertStatus = AlertStatus.ACTIVE
    
    reading_value: Optional[float] = None
    threshold_value: Optional[float] = None
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[int] = None
    resolved_at: Optional[datetime] = None
    resolved_by: Optional[int] = None
    
    resolution_notes: str = ''
    related_work_order_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'alert_id': self.alert_id,
            'device_id': self.device_id,
            'sensor_id': self.sensor_id,
            'severity': self.severity.value,
            'title': self.title,
            'message': self.message,
            'status': self.status.value,
            'reading_value': self.reading_value,
            'threshold_value': self.threshold_value,
            'created_at': self.created_at.isoformat(),
            'acknowledged_at': self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            'resolved_at': self.resolved_at.isoformat() if self.resolved_at else None
        }


@dataclass
class AutomatedInventory:
    inventory_id: str
    name: str
    description: str = ''
    
    location: str = ''
    gateway_id: Optional[str] = None
    
    status: InventoryStatus = InventoryStatus.PENDING
    
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    total_assets_expected: int = 0
    total_assets_found: int = 0
    total_assets_missing: int = 0
    
    created_by: Optional[int] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    scanned_tags: List[str] = field(default_factory=list)
    missing_tags: List[str] = field(default_factory=list)
    unexpected_tags: List[str] = field(default_factory=list)
    
    config: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'inventory_id': self.inventory_id,
            'name': self.name,
            'description': self.description,
            'location': self.location,
            'gateway_id': self.gateway_id,
            'status': self.status.value,
            'scheduled_at': self.scheduled_at.isoformat() if self.scheduled_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'stats': {
                'expected': self.total_assets_expected,
                'found': self.total_assets_found,
                'missing': self.total_assets_missing,
                'unexpected': len(self.unexpected_tags)
            },
            'created_at': self.created_at.isoformat()
        }


class AnomalyDetector:
    def __init__(self, window_size: int = 100):
        self.window_size = window_size
        self.reading_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=window_size))
        self.baselines: Dict[str, Dict[str, float]] = {}
    
    def add_reading(self, sensor_id: str, value: float) -> Tuple[bool, float]:
        history = self.reading_history[sensor_id]
        history.append(value)
        
        if len(history) < 10:
            return False, 0.0
        
        if sensor_id not in self.baselines:
            self._calculate_baseline(sensor_id)
        
        baseline = self.baselines.get(sensor_id, {'mean': value, 'std': 1.0})
        
        mean = baseline['mean']
        std = baseline['std']
        
        if std == 0:
            return False, 0.0
        
        z_score = abs(value - mean) / std
        
        is_anomaly = z_score > 3.0
        anomaly_score = min(1.0, z_score / 5.0)
        
        if len(history) % 10 == 0:
            self._calculate_baseline(sensor_id)
        
        return is_anomaly, anomaly_score
    
    def _calculate_baseline(self, sensor_id: str):
        history = self.reading_history[sensor_id]
        if len(history) < 5:
            return
        
        values = list(history)
        mean = statistics.mean(values)
        std = statistics.stdev(values) if len(values) > 1 else 0.0
        
        self.baselines[sensor_id] = {
            'mean': mean,
            'std': std,
            'min': min(values),
            'max': max(values)
        }
    
    def get_sensor_stats(self, sensor_id: str) -> Optional[Dict[str, float]]:
        return self.baselines.get(sensor_id)


class IoTMonitorService:
    def __init__(self):
        self.gateways: Dict[str, IoTGateway] = {}
        self.devices: Dict[str, IoTDevice] = {}
        self.sensors: Dict[str, DeviceSensor] = {}
        self.readings: Dict[str, List[SensorReading]] = defaultdict(list)
        self.alerts: Dict[str, DeviceAlert] = {}
        self.inventories: Dict[str, AutomatedInventory] = {}
        
        self.anomaly_detector = AnomalyDetector(window_size=200)
        
        self.reading_counter = 0
        self.alert_counter = 0
        self.inventory_counter = 0
        
        self.device_asset_mapping: Dict[str, int] = {}
    
    def _generate_reading_id(self) -> str:
        self.reading_counter += 1
        return f"RD-{datetime.now().strftime('%Y%m%d%H%M%S')}-{self.reading_counter:08d}"
    
    def _generate_alert_id(self) -> str:
        self.alert_counter += 1
        return f"AL-{datetime.now().strftime('%Y%m%d%H%M%S')}-{self.alert_counter:06d}"
    
    def _generate_inventory_id(self) -> str:
        self.inventory_counter += 1
        return f"AINV-{datetime.now().strftime('%Y%m%d')}-{self.inventory_counter:06d}"
    
    def register_device(self,
                        device_id: str,
                        name: str,
                        device_type: str,
                        asset_id: Optional[int] = None,
                        gateway_id: Optional[str] = None,
                        location: str = '',
                        manufacturer: str = '',
                        model: str = '',
                        serial_number: str = '') -> IoTDevice:
        device = IoTDevice(
            device_id=device_id,
            name=name,
            device_type=device_type,
            asset_id=asset_id,
            gateway_id=gateway_id,
            location=location,
            manufacturer=manufacturer,
            model=model,
            serial_number=serial_number,
            status=DeviceStatus.ONLINE
        )
        
        self.devices[device_id] = device
        
        if asset_id:
            self.device_asset_mapping[device_id] = asset_id
        
        return device
    
    def add_sensor(self,
                   sensor_id: str,
                   device_id: str,
                   sensor_type: SensorType,
                   name: str = '',
                   unit: str = '',
                   min_value: Optional[float] = None,
                   max_value: Optional[float] = None,
                   warning_threshold: Optional[float] = None,
                   critical_threshold: Optional[float] = None) -> Optional[DeviceSensor]:
        if device_id not in self.devices:
            return None
        
        sensor = DeviceSensor(
            sensor_id=sensor_id,
            device_id=device_id,
            sensor_type=sensor_type,
            name=name,
            unit=unit,
            min_value=min_value,
            max_value=max_value,
            warning_threshold=warning_threshold,
            critical_threshold=critical_threshold
        )
        
        self.sensors[sensor_id] = sensor
        return sensor
    
    def record_reading(self,
                       sensor_id: str,
                       device_id: str,
                       value: float,
                       raw_value: Optional[str] = None,
                       reading_at: Optional[datetime] = None,
                       location_lat: Optional[float] = None,
                       location_lng: Optional[float] = None) -> SensorReading:
        sensor = self.sensors.get(sensor_id)
        if sensor:
            sensor.last_reading = value
            sensor.last_reading_at = reading_at or datetime.utcnow()
        
        is_anomaly, anomaly_score = self.anomaly_detector.add_reading(sensor_id, value)
        
        reading = SensorReading(
            reading_id=self._generate_reading_id(),
            sensor_id=sensor_id,
            device_id=device_id,
            value=value,
            raw_value=raw_value,
            reading_at=reading_at or datetime.utcnow(),
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score,
            location_lat=location_lat,
            location_lng=location_lng
        )
        
        self.readings[sensor_id].append(reading)
        
        if sensor and is_anomaly:
            self._check_and_create_alert(sensor, reading)
        
        device = self.devices.get(device_id)
        if device:
            device.last_seen = datetime.utcnow()
            device.status = DeviceStatus.ONLINE
        
        return reading
    
    def _check_and_create_alert(self, sensor: DeviceSensor, reading: SensorReading):
        if sensor.critical_threshold is not None:
            if reading.value > sensor.critical_threshold:
                self._create_alert(
                    sensor.device_id,
                    sensor.sensor_id,
                    AlertSeverity.CRITICAL,
                    f"{sensor.name} 超过临界阈值",
                    f"传感器读数 {reading.value} {sensor.unit} 超过临界阈值 {sensor.critical_threshold} {sensor.unit}",
                    reading.value,
                    sensor.critical_threshold
                )
                return
        
        if sensor.warning_threshold is not None:
            if reading.value > sensor.warning_threshold:
                self._create_alert(
                    sensor.device_id,
                    sensor.sensor_id,
                    AlertSeverity.WARNING,
                    f"{sensor.name} 超过警告阈值",
                    f"传感器读数 {reading.value} {sensor.unit} 超过警告阈值 {sensor.warning_threshold} {sensor.unit}",
                    reading.value,
                    sensor.warning_threshold
                )
    
    def _create_alert(self,
                      device_id: str,
                      sensor_id: Optional[str],
                      severity: AlertSeverity,
                      title: str,
                      message: str,
                      reading_value: Optional[float] = None,
                      threshold_value: Optional[float] = None) -> DeviceAlert:
        alert = DeviceAlert(
            alert_id=self._generate_alert_id(),
            device_id=device_id,
            sensor_id=sensor_id,
            severity=severity,
            title=title,
            message=message,
            reading_value=reading_value,
            threshold_value=threshold_value
        )
        
        self.alerts[alert.alert_id] = alert
        return alert
    
    def acknowledge_alert(self, alert_id: str, user_id: int) -> Tuple[bool, str]:
        alert = self.alerts.get(alert_id)
        if not alert:
            return False, "告警不存在"
        
        if alert.status != AlertStatus.ACTIVE:
            return False, f"告警状态不是活动状态: {alert.status.value}"
        
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_at = datetime.utcnow()
        alert.acknowledged_by = user_id
        
        return True, "告警已确认"
    
    def resolve_alert(self, alert_id: str, user_id: int, notes: str = '') -> Tuple[bool, str]:
        alert = self.alerts.get(alert_id)
        if not alert:
            return False, "告警不存在"
        
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.utcnow()
        alert.resolved_by = user_id
        alert.resolution_notes = notes
        
        return True, "告警已解决"
    
    def start_automated_inventory(self,
                                   name: str,
                                   location: str,
                                   gateway_id: Optional[str] = None,
                                   expected_tags: List[str] = None,
                                   created_by: Optional[int] = None) -> AutomatedInventory:
        inventory = AutomatedInventory(
            inventory_id=self._generate_inventory_id(),
            name=name,
            location=location,
            gateway_id=gateway_id,
            status=InventoryStatus.IN_PROGRESS,
            started_at=datetime.utcnow(),
            total_assets_expected=len(expected_tags) if expected_tags else 0,
            created_by=created_by
        )
        
        self.inventories[inventory.inventory_id] = inventory
        return inventory
    
    def record_rfid_scan(self,
                         inventory_id: str,
                         tag_id: str,
                         device_id: str,
                         scan_time: Optional[datetime] = None) -> Tuple[bool, str]:
        inventory = self.inventories.get(inventory_id)
        if not inventory:
            return False, "盘点任务不存在"
        
        if inventory.status != InventoryStatus.IN_PROGRESS:
            return False, f"盘点任务状态不是进行中: {inventory.status.value}"
        
        if tag_id not in inventory.scanned_tags:
            inventory.scanned_tags.append(tag_id)
        
        return True, "扫描记录已添加"
    
    def complete_inventory(self,
                           inventory_id: str,
                           expected_tags: List[str] = None) -> Tuple[bool, str, AutomatedInventory]:
        inventory = self.inventories.get(inventory_id)
        if not inventory:
            return False, "盘点任务不存在", None
        
        inventory.status = InventoryStatus.COMPLETED
        inventory.completed_at = datetime.utcnow()
        
        if expected_tags:
            expected_set = set(expected_tags)
            scanned_set = set(inventory.scanned_tags)
            
            inventory.total_assets_expected = len(expected_set)
            inventory.total_assets_found = len(expected_set & scanned_set)
            inventory.total_assets_missing = len(expected_set - scanned_set)
            inventory.missing_tags = list(expected_set - scanned_set)
            inventory.unexpected_tags = list(scanned_set - expected_set)
        
        return True, "盘点已完成", inventory
    
    def get_device_sensor_readings(self,
                                    device_id: str,
                                    sensor_id: Optional[str] = None,
                                    start_time: Optional[datetime] = None,
                                    end_time: Optional[datetime] = None,
                                    limit: int = 100) -> List[SensorReading]:
        readings = []
        
        if sensor_id:
            readings = self.readings.get(sensor_id, [])
        else:
            device_sensors = [
                s.sensor_id for s in self.sensors.values()
                if s.device_id == device_id
            ]
            for sid in device_sensors:
                readings.extend(self.readings.get(sid, []))
        
        filtered_readings = [
            r for r in readings
            if (not start_time or r.reading_at >= start_time) and
               (not end_time or r.reading_at <= end_time)
        ]
        
        filtered_readings.sort(key=lambda r: r.reading_at, reverse=True)
        return filtered_readings[:limit]
    
    def get_active_alerts(self,
                          severity: Optional[AlertSeverity] = None,
                          device_id: Optional[str] = None) -> List[DeviceAlert]:
        alerts = [
            a for a in self.alerts.values()
            if a.status == AlertStatus.ACTIVE
        ]
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        
        if device_id:
            alerts = [a for a in alerts if a.device_id == device_id]
        
        return alerts
    
    def get_device_status(self, device_id: str) -> Optional[Dict[str, Any]]:
        device = self.devices.get(device_id)
        if not device:
            return None
        
        device_sensors = [
            s for s in self.sensors.values()
            if s.device_id == device_id
        ]
        
        latest_readings = {}
        for sensor in device_sensors:
            readings = self.readings.get(sensor.sensor_id, [])
            if readings:
                latest_readings[sensor.sensor_id] = {
                    'value': readings[-1].value,
                    'at': readings[-1].reading_at.isoformat(),
                    'is_anomaly': readings[-1].is_anomaly
                }
        
        return {
            'device': device.to_dict(),
            'sensors': [s.to_dict() for s in device_sensors],
            'latest_readings': latest_readings,
            'asset_id': self.device_asset_mapping.get(device_id)
        }
    
    def get_monitor_stats(self) -> Dict[str, Any]:
        total_devices = len(self.devices)
        online_devices = sum(
            1 for d in self.devices.values()
            if d.status == DeviceStatus.ONLINE
        )
        
        total_sensors = len(self.sensors)
        active_sensors = sum(
            1 for s in self.sensors.values()
            if s.is_active
        )
        
        active_alerts = sum(
            1 for a in self.alerts.values()
            if a.status == AlertStatus.ACTIVE
        )
        critical_alerts = sum(
            1 for a in self.alerts.values()
            if a.status == AlertStatus.ACTIVE and a.severity == AlertSeverity.CRITICAL
        )
        
        active_inventories = sum(
            1 for i in self.inventories.values()
            if i.status == InventoryStatus.IN_PROGRESS
        )
        
        return {
            'devices': {
                'total': total_devices,
                'online': online_devices,
                'offline': total_devices - online_devices
            },
            'sensors': {
                'total': total_sensors,
                'active': active_sensors
            },
            'alerts': {
                'active': active_alerts,
                'critical': critical_alerts
            },
            'inventories': {
                'active': active_inventories,
                'total': len(self.inventories)
            },
            'generated_at': datetime.utcnow().isoformat()
        }
