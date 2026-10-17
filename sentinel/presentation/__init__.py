"""M3 presentation layer: wording, timeline, dashboard model, evidence export. No cv2/PIL imports."""
from sentinel.presentation.evidence import SnapshotPaths, build_evidence, save_snapshot, snapshot_basename
from sentinel.presentation.model import DashboardModel, StepCard, build_dashboard_model
from sentinel.presentation.timeline import TimelineEntry, build_timeline

__all__ = ["SnapshotPaths", "build_evidence", "save_snapshot", "snapshot_basename", "DashboardModel",
           "StepCard", "build_dashboard_model", "TimelineEntry", "build_timeline"]
