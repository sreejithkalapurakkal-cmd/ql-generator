"""Temporal Analyzer — signal trend and window prediction engine.

Provides time-series analysis of signals to detect acceleration,
recurring patterns, and predict optimal action windows.
"""
import math
import logging
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Action window predictions by signal type
ACTION_WINDOWS = {
    "executive_change": {
        "window_days": 60,
        "label": "New leader vendor review window",
        "description": "New executives typically complete initial vendor landscape reviews within {window_days} days",
    },
    "champion_job_change": {
        "window_days": 45,
        "label": "Champion re-engagement window",
        "description": "Former champions are most receptive in the first {window_days} days at a new company",
    },
    "funding": {
        "window_days": 90,
        "label": "Post-funding build-out window",
        "description": "Companies typically begin vendor evaluation within {window_days} days post-funding",
    },
    "hiring_surge": {
        "window_days": 30,
        "label": "Active buildout window",
        "description": "Hiring surges indicate active procurement within {window_days} days",
    },
    "tech_adoption": {
        "window_days": 120,
        "label": "Technology integration window",
        "description": "New tech adoption often triggers adjacent tool evaluation within {window_days} days",
    },
    "earnings_report": {
        "window_days": 30,
        "label": "Post-earnings initiative window",
        "description": "Budget reallocations typically happen within {window_days} days of earnings",
    },
    "product_launch": {
        "window_days": 60,
        "label": "Post-launch scaling window",
        "description": "Post-launch is when supporting infrastructure decisions are made",
    },
    "expansion": {
        "window_days": 90,
        "label": "Expansion vendor selection window",
        "description": "Expansion drives new vendor needs within {window_days} days",
    },
}


class TemporalAnalyzer:
    """Analyzes signal trends over time for a company."""

    def detect_acceleration(
        self,
        signals: list[dict],
        window_days: int = 30,
    ) -> dict:
        """Detect if signal frequency is accelerating.

        Compares the rate of signals in the recent window vs the previous window.

        Args:
            signals: List of signal dicts with 'detected_at' datetime
            window_days: Window size in days for comparison

        Returns:
            {
                "is_accelerating": bool,
                "recent_count": int,
                "previous_count": int,
                "acceleration_ratio": float,  # >1.0 = accelerating
                "trend": "accelerating" | "decelerating" | "stable",
                "window_days": int,
            }
        """
        now = datetime.now(timezone.utc)
        recent_cutoff = now - timedelta(days=window_days)
        previous_cutoff = recent_cutoff - timedelta(days=window_days)

        recent_count = 0
        previous_count = 0

        for s in signals:
            detected = s.get("detected_at")
            if not detected:
                continue
            if isinstance(detected, str):
                try:
                    detected = datetime.fromisoformat(detected.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    continue
            if not detected.tzinfo:
                detected = detected.replace(tzinfo=timezone.utc)

            if detected >= recent_cutoff:
                recent_count += 1
            elif detected >= previous_cutoff:
                previous_count += 1

        if previous_count == 0:
            ratio = float(recent_count) if recent_count > 0 else 1.0
        else:
            ratio = recent_count / previous_count

        if ratio > 1.3:
            trend = "accelerating"
        elif ratio < 0.7:
            trend = "decelerating"
        else:
            trend = "stable"

        return {
            "is_accelerating": ratio > 1.3,
            "recent_count": recent_count,
            "previous_count": previous_count,
            "acceleration_ratio": round(ratio, 2),
            "trend": trend,
            "window_days": window_days,
        }

    def detect_pattern(
        self,
        signals: list[dict],
        min_occurrences: int = 2,
    ) -> list[dict]:
        """Identify recurring signal patterns.

        Looks for signals of the same type that recur on a predictable schedule.

        Returns:
            List of detected patterns:
            [
                {
                    "signal_type": str,
                    "occurrences": int,
                    "avg_interval_days": float,
                    "pattern": "quarterly" | "monthly" | "biweekly" | "irregular",
                    "next_expected": str (ISO date),
                    "confidence": float,
                }
            ]
        """
        # Group signals by type
        by_type: dict[str, list[datetime]] = defaultdict(list)
        for s in signals:
            detected = s.get("detected_at")
            if not detected:
                continue
            if isinstance(detected, str):
                try:
                    detected = datetime.fromisoformat(detected.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    continue
            if not detected.tzinfo:
                detected = detected.replace(tzinfo=timezone.utc)
            by_type[s.get("signal_type", "unknown")].append(detected)

        patterns = []
        for signal_type, dates in by_type.items():
            if len(dates) < min_occurrences:
                continue

            dates.sort()
            intervals = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
            if not intervals:
                continue

            avg_interval = sum(intervals) / len(intervals)
            std_dev = math.sqrt(sum((x - avg_interval) ** 2 for x in intervals) / len(intervals)) if len(intervals) > 1 else avg_interval

            # Classify pattern
            if 80 <= avg_interval <= 100:
                pattern_type = "quarterly"
            elif 25 <= avg_interval <= 35:
                pattern_type = "monthly"
            elif 12 <= avg_interval <= 16:
                pattern_type = "biweekly"
            elif 5 <= avg_interval <= 9:
                pattern_type = "weekly"
            else:
                pattern_type = "irregular"

            # Confidence based on regularity (lower std_dev = higher confidence)
            confidence = max(0.0, min(1.0, 1.0 - (std_dev / (avg_interval + 1))))
            next_expected = dates[-1] + timedelta(days=avg_interval)

            patterns.append({
                "signal_type": signal_type,
                "occurrences": len(dates),
                "avg_interval_days": round(avg_interval, 1),
                "pattern": pattern_type,
                "next_expected": next_expected.isoformat(),
                "confidence": round(confidence, 2),
            })

        return sorted(patterns, key=lambda p: p["confidence"], reverse=True)

    def predict_window(
        self,
        signal: dict,
    ) -> dict:
        """Predict the optimal action window for a signal.

        Based on signal type and historical data about when actions
        are most effective after each signal type.

        Returns:
            {
                "signal_type": str,
                "window_start": str (ISO date),
                "window_end": str (ISO date),
                "window_days": int,
                "label": str,
                "description": str,
                "days_remaining": int,
                "urgency": "immediate" | "soon" | "open" | "closing" | "expired",
            }
        """
        signal_type = signal.get("signal_type", "")
        detected_at = signal.get("detected_at")

        if isinstance(detected_at, str):
            try:
                detected_at = datetime.fromisoformat(detected_at.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                detected_at = datetime.now(timezone.utc)
        elif detected_at is None:
            detected_at = datetime.now(timezone.utc)
        if not detected_at.tzinfo:
            detected_at = detected_at.replace(tzinfo=timezone.utc)

        window_config = ACTION_WINDOWS.get(signal_type, {
            "window_days": 60,
            "label": "Standard action window",
            "description": "Act within {window_days} days for best results",
        })

        window_days = window_config["window_days"]
        window_start = detected_at
        window_end = detected_at + timedelta(days=window_days)
        now = datetime.now(timezone.utc)
        days_remaining = max(0, (window_end - now).days)
        days_elapsed = (now - window_start).days

        # Determine urgency
        pct_elapsed = days_elapsed / window_days if window_days > 0 else 1.0
        if days_remaining <= 0:
            urgency = "expired"
        elif pct_elapsed < 0.1:
            urgency = "immediate"
        elif pct_elapsed < 0.5:
            urgency = "soon"
        elif pct_elapsed < 0.8:
            urgency = "open"
        else:
            urgency = "closing"

        return {
            "signal_type": signal_type,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "window_days": window_days,
            "label": window_config["label"],
            "description": window_config["description"].format(window_days=window_days),
            "days_remaining": days_remaining,
            "urgency": urgency,
        }


# Module-level singleton
temporal_analyzer = TemporalAnalyzer()
