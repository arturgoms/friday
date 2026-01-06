"""
Friday Insights Engine - Delivery Manager

Orchestrates insight delivery across all channels.
"""

import logging
from typing import Any, Dict, List

from settings import settings
from src.awareness.decision.engine import DecisionEngine, DeliveryAction
from src.awareness.delivery.channels import get_channel_registry
from src.awareness.delivery.loader import get_routing_config, initialize_channels
from src.awareness.models import Category, DeliveryChannel, Insight, Priority
from src.awareness.store import InsightsStore


def get_brt():
    return settings.TIMEZONE

logger = logging.getLogger(__name__)


class DeliveryManager:
    """
    Central manager for all insight delivery.

    Responsibilities:
    - Process insights through decision engine
    - Route to appropriate delivery channels
    - Generate and send scheduled reports
    - Track delivery status
    """

    def __init__(self, config: dict, store: InsightsStore):
        self.config = config
        self.store = store
        self.decision = DecisionEngine(config, store)

        # Initialize delivery channels
        num_channels = initialize_channels()
        logger.info(f"[DELIVERY] Initialized {num_channels} delivery channel(s)")

        # Get channel registry and routing config
        self.channel_registry = get_channel_registry()
        self.routing_config = get_routing_config()

    def process_insights(self, insights: List[Insight]) -> Dict[str, int]:
        """Process a batch of insights from analyzers.

        Args:
            insights: List of insights to process

        Returns:
            Stats: {"delivered": N, "batched": N, "skipped": N}
        """
        stats = {"delivered": 0, "batched": 0, "queued": 0, "skipped": 0}

        # Run through decision engine
        decisions = self.decision.process(insights)

        # Process each decision
        for insight in decisions[DeliveryAction.DELIVER_NOW]:
            success = self._deliver_immediate(insight)
            if success:
                stats["delivered"] += 1
            else:
                stats["queued"] += 1

        for insight in decisions[DeliveryAction.BATCH_REPORT]:
            self._batch_for_report(insight)
            stats["batched"] += 1

        for insight in decisions[DeliveryAction.QUEUE_LATER]:
            self._queue_for_later(insight)
            stats["queued"] += 1

        stats["skipped"] = len(decisions[DeliveryAction.SKIP])

        logger.info(f"[DELIVERY] Processed {len(insights)} insights: delivered={stats.get('delivered', 0)}, batched={stats.get('batched', 0)}, queued={stats.get('queued', 0)}, skipped={stats.get('skipped', 0)}")
        return stats

    def _deliver_immediate(self, insight: Insight) -> bool:
        """Deliver an insight immediately via configured channels."""
        try:
            # Determine which channels to use based on priority
            channels_to_use = self._get_channels_for_insight(insight)

            if not channels_to_use:
                logger.warning(f"[DELIVERY] No channels configured for insight: {insight.title}")
                return False

            # Send to all configured channels
            any_success = False
            for channel in channels_to_use:
                try:
                    success = channel.send_insight_sync(insight)
                    if success:
                        self.decision.record_delivery(insight, DeliveryChannel.TELEGRAM)  # TODO: Map channel to enum
                        any_success = True
                        logger.info(f"[DELIVERY] Sent insight via {channel.name}: {insight.title}")
                except Exception as e:
                    logger.error(f"[DELIVERY] Failed to send via {channel.name}: {e}")

            return any_success

        except Exception as e:
            logger.error(f"[DELIVERY] Failed to deliver insight '{insight.title}': {e}")
            return False

    def _batch_for_report(self, insight: Insight):
        """Save insight for inclusion in next report."""
        try:
            self.store.save_insight(insight)
            logger.debug(f"Batched insight for report: {insight.title}")
        except Exception as e:
            logger.error(f"Failed to batch insight: {e}")

    def _queue_for_later(self, insight: Insight):
        """Save insight for later delivery (when budget available/quiet hours end)."""
        try:
            self.store.save_insight(insight)
            logger.debug(f"Queued insight for later: {insight.title}")
        except Exception as e:
            logger.error(f"Failed to queue insight: {e}")

    def process_queued_insights(self) -> int:
        """Process insights that were queued (after quiet hours end, etc).

        Returns:
            Number of insights delivered
        """
        pending = self.decision.get_pending_for_delivery()
        delivered = 0

        for insight in pending:
            if self._deliver_immediate(insight):
                delivered += 1

        if delivered > 0:
            logger.info(f"Delivered {delivered} queued insights")

        return delivered


    def _get_channels_for_insight(self, insight: Insight) -> List:
        """Get delivery channels for an insight based on routing config.

        Args:
            insight: The insight to deliver

        Returns:
            List of channels to use
        """
        # Get routing for insights
        insights_routing = self.routing_config.get("insights", {})
        priority_str = insight.priority.value.lower()
        channel_names = insights_routing.get(priority_str, ["telegram"])

        # Get enabled channels
        channels = []
        for name in channel_names:
            channel = self.channel_registry.get(name)
            if channel and channel.enabled:
                channels.append(channel)

        # Fallback: use all enabled channels if no routing configured
        if not channels:
            channels = self.channel_registry.get_enabled_channels()

        return channels


    def send_alert(self, message: str, level: str = "info") -> bool:
        """Send an alert via configured channels.

        Args:
            message: Alert message
            level: Alert level (info, warning, critical)

        Returns:
            True if sent to at least one channel
        """
        # Get routing for alerts
        alerts_routing = self.routing_config.get("alerts", {})
        channel_names = alerts_routing.get(level, ["telegram"])

        # Get enabled channels
        channels = []
        for name in channel_names:
            channel = self.channel_registry.get(name)
            if channel and channel.enabled:
                channels.append(channel)

        # Fallback: use all enabled channels
        if not channels:
            channels = self.channel_registry.get_enabled_channels()

        # Send to all channels
        any_success = False
        for channel in channels:
            try:
                success = channel.send_alert_sync(message, level)
                if success:
                    any_success = True
                    logger.info(f"[DELIVERY] Sent alert via {channel.name}")
            except Exception as e:
                logger.error(f"[DELIVERY] Failed to send alert via {channel.name}: {e}")

        return any_success
